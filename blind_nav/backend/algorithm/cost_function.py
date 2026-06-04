from __future__ import annotations
import logging
from typing import Any, Dict, Optional
from backend.config import (
    TACTILE_PAVING_MAP, STEPS_MAP, SURFACE_MAP, LIGHTING_MAP,
    SIDEWALK_MAP, HIGHWAY_MAP, INCLINE_COST_PER_PERCENT,
    INCLINE_MAX_COST, WIDTH_THRESHOLD_M, WIDTH_COST_PER_METER_BELOW,
    WIDTH_MAX_COST, UNKNOWN_SCORE, WeightCoefficients, get_time_slot,
)
logger = logging.getLogger(__name__)
class StaticCost:
    def __init__(self, weights: Optional[WeightCoefficients] = None) -> None:
        self._w = weights or WeightCoefficients()
    def compute(self, tags: Dict[str, Any]) -> float:
        raw_len = tags.get("length")
        try:
            edge_len = float(raw_len) if raw_len is not None else 0.0
        except (ValueError, TypeError):
            edge_len = 0.0
        if edge_len <= 0.0:
            edge_len = 1.0
        norm = edge_len / 100.0
        cost = edge_len * 0.02
        cost += self._map("tactile_paving", TACTILE_PAVING_MAP, tags) * self._w.tactile_paving * norm
        cost += self._map("steps", STEPS_MAP, tags) * self._w.steps * norm
        cost += self._map("surface", SURFACE_MAP, tags) * self._w.surface * norm
        cost += self._map("lit", LIGHTING_MAP, tags) * self._w.lighting * norm
        cost += self._map("sidewalk", SIDEWALK_MAP, tags) * self._w.sidewalk * norm
        cost += self._map("highway", HIGHWAY_MAP, tags) * self._w.highway * norm
        cost += self._incline_cost(tags.get("incline")) * self._w.incline * norm
        cost += self._width_cost(tags.get("width")) * self._w.width * norm
        return cost
    @staticmethod
    def _map(key: str, mapping: Dict[str, float], tags: Dict[str, Any]) -> float:
        val = tags.get(key)
        if val is None:
            return UNKNOWN_SCORE
        return mapping.get(str(val).lower(), UNKNOWN_SCORE)
    @staticmethod
    def _incline_cost(raw: Any) -> float:
        if raw is None:
            return 3.0
        s = str(raw).lower().replace("%", "").strip()
        try:
            pct = abs(float(s))
            return min(pct * INCLINE_COST_PER_PERCENT, INCLINE_MAX_COST)
        except ValueError:
            return {"steep": 8.0, "up": 4.0, "down": 4.0, "yes": 4.0}.get(s, 3.0)
    @staticmethod
    def _width_cost(raw: Any) -> float:
        if raw is None:
            return 3.0
        s = str(raw).lower().replace("m", "").strip()
        try:
            w = float(s)
            if w >= WIDTH_THRESHOLD_M:
                return 0.0
            return min((WIDTH_THRESHOLD_M - w) * WIDTH_COST_PER_METER_BELOW, WIDTH_MAX_COST)
        except ValueError:
            return 3.0
_TRAFFIC_WEIGHT: Dict[str, float] = {
    "motorway": 2.0, "trunk": 1.8, "primary": 1.6,
    "secondary": 1.4, "tertiary": 1.2, "residential": 1.0,
    "living_street": 0.8, "service": 0.8,
    "footway": 0.6, "path": 0.6, "pedestrian": 0.5,
    "steps": 0.0,
}
class TimeDependentCost:
    def __init__(self, static: StaticCost) -> None:
        self._static = static
    def compute(self, tags: Dict[str, Any], hour: int) -> float:
        base = self._static.compute(tags)
        slot = get_time_slot(hour)
        lit = str(tags.get("lit", "unknown")).lower()
        M_lit = slot.lighting_multiplier if lit in ("no", "unknown") else 1.0
        hw = str(tags.get("highway", "unknown")).lower()
        tw = _TRAFFIC_WEIGHT.get(hw, 1.0)
        M_crowd = 1.0 + (slot.crowd_multiplier - 1.0) * tw
        return base * M_lit * M_crowd
class CostFunction:
    def __init__(self, weights: Optional[WeightCoefficients] = None) -> None:
        self._w = weights or WeightCoefficients()
        self.static = StaticCost(self._w)
        self.dynamic = TimeDependentCost(self.static)
    def compute_static(self, tags: Dict[str, Any]) -> float:
        return self.static.compute(tags)
    def compute_dynamic(self, tags: Dict[str, Any], hour: int) -> float:
        return self.dynamic.compute(tags, hour)
    def compute_both(self, tags: Dict[str, Any], hour: int):
        s = self.compute_static(tags)
        d = self.compute_dynamic(tags, hour)
        return s, d