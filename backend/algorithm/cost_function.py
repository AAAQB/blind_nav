from __future__ import annotations
import logging
from typing import Any, Dict, Optional
from backend.config import (
    TACTILE_PAVING_MAP, STEPS_MAP, SURFACE_MAP, LIGHTING_MAP,
    SIDEWALK_MAP, HIGHWAY_MAP, INCLINE_COST_PER_PERCENT,
    INCLINE_MAX_COST, WIDTH_THRESHOLD_M, WIDTH_COST_PER_METER_BELOW,
    WIDTH_MAX_COST, INCLINE_STR_MAP, UNKNOWN_SCORE, WeightCoefficients, get_time_slot,
)
logger = logging.getLogger(__name__)
# Reference length (meters) for normalising accessibility cost.
# When edge length is below this value, it is still used as-is
# to avoid distortion from extremely short edges.
_REFERENCE_LENGTH: float = 1.0


class StaticCost:
    """Static accessibility cost for a single road segment.

    The cost formula:

        C_static = unit_cost * effective_length

    where:
      - unit_cost  = SUM(score_i * weight_i)   — weighted sum of accessibility scores
      - effective_length = max(edge_length, REFERENCE_LENGTH)
                      — actual edge length in meters

    With the length factor, A* can properly trade off
    "longer but more accessible" vs "shorter but less accessible" paths.
    The heuristic uses euclidean_approx returning metric distance,
    aligned with the cost dimension.
    """

    def __init__(self, weights: Optional[WeightCoefficients] = None) -> None:
        self._w = weights or WeightCoefficients()

    def compute(self, tags: Dict[str, Any]) -> float:
        length = float(tags.get("length", _REFERENCE_LENGTH))
        eff_len = max(length, _REFERENCE_LENGTH)

        unit_cost  = self._map("tactile_paving", TACTILE_PAVING_MAP, tags) * self._w.tactile_paving
        unit_cost += self._map("steps", STEPS_MAP, tags) * self._w.steps
        unit_cost += self._map("surface", SURFACE_MAP, tags) * self._w.surface
        unit_cost += self._map("lit", LIGHTING_MAP, tags) * self._w.lighting
        unit_cost += self._map("sidewalk", SIDEWALK_MAP, tags) * self._w.sidewalk
        unit_cost += self._map("highway", HIGHWAY_MAP, tags) * self._w.highway
        unit_cost += self._incline_cost(tags.get("incline")) * self._w.incline
        unit_cost += self._width_cost(tags.get("width")) * self._w.width

        return unit_cost * eff_len
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
            return INCLINE_STR_MAP.get(s, 3.0)
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

# Minimum crowd multiplier — prevents M_crowd from reaching zero when
# crowd_multiplier < 1 combined with high traffic_weight road types.
#
# Mathematical derivation:
#   M_crowd = 1.0 + (crowd_mult - 1.0) * traffic_weight
#   Current bounds: crowd_mult ∈ [0.8, 1.5], traffic_weight ∈ [0.0, 2.0]
#   Minimum achievable: 1.0 + (0.8 - 1.0) * 2.0 = 0.60 (dawn/late_night × motorway)
#   Maximum achievable: 1.0 + (1.5 - 1.0) * 2.0 = 2.00 (night × motorway)
# Setting floor = 0.6 ensures it activates precisely at the boundary case.
_M_CROWD_FLOOR: float = 0.6


class TimeDependentCost:
    """Time-dependent dynamic cost for a single road segment.

    The formula follows the project report (Section 4.2):

        C_dynamic(e, t) = C_static(e) * M_lit(t, e) * M_crowd(t, e)

    where:
      - M_lit  = slot.lighting_multiplier   if the segment is unlit/unknown
               = 1.0                        otherwise
      - M_crowd = max(_M_CROWD_FLOOR,
                      1.0 + (slot.crowd_multiplier - 1.0) * traffic_weight)

    The floor ensures the crowd factor never collapses to zero for
    high-traffic road types during low-crowd time slots (e.g. motorway
    at late_night with crowd_multiplier=0.8 would yield M_crowd >= 0.6).
    """

    def __init__(self, static: StaticCost) -> None:
        self._static = static

    def compute(self, tags: Dict[str, Any], hour: int) -> float:
        base = self._static.compute(tags)
        slot = get_time_slot(hour)

        # Lighting multiplier — only unlit / unknown segments are affected.
        lit = str(tags.get("lit", "unknown")).lower()
        M_lit = slot.lighting_multiplier if lit in ("no", "unknown", "limited") else 1.0

        # Crowd multiplier — scaled by road-type traffic weight, floored.
        hw = str(tags.get("highway", "unknown")).lower()
        tw = _TRAFFIC_WEIGHT.get(hw, 1.0)
        M_crowd = max(_M_CROWD_FLOOR, 1.0 + (slot.crowd_multiplier - 1.0) * tw)

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