from __future__ import annotations
import math
from typing import List, Optional, Tuple
from backend.config import SMOOTH_ITERATIONS, SMOOTH_LEARNING_RATE, SMOOTH_TOLERANCE, \
    SMOOTH_INTERPOLATE_SPACING_M
class PathSmoother:
    def __init__(
        self,
        iterations: int = SMOOTH_ITERATIONS,
        learning_rate: float = SMOOTH_LEARNING_RATE,
        tolerance: float = SMOOTH_TOLERANCE,
        spacing_m: float = SMOOTH_INTERPOLATE_SPACING_M,
    ) -> None:
        self._it = iterations
        self._lr = learning_rate
        self._tol = tolerance
        self._spacing = spacing_m
        self._R = 6_371_000.0
    def smooth(
        self,
        path: List[Tuple[float, float]],
        fixed: Optional[List[int]] = None,
    ) -> List[Tuple[float, float]]:
        if len(path) <= 2:
            return path
        fixed_set = set(fixed) if fixed is not None else {0, len(path) - 1}
        pts = [list(p) for p in path]
        for _ in range(self._it):
            max_delta = 0.0
            for i in range(1, len(pts) - 1):
                if i in fixed_set:
                    continue
                old_lat, old_lon = pts[i]
                avg_lat = (pts[i - 1][0] + pts[i + 1][0]) / 2.0
                avg_lon = (pts[i - 1][1] + pts[i + 1][1]) / 2.0
                pts[i][0] += self._lr * (avg_lat - old_lat)
                pts[i][1] += self._lr * (avg_lon - old_lon)
                max_delta = max(max_delta, abs(pts[i][0] - old_lat), abs(pts[i][1] - old_lon))
            if max_delta < self._tol:
                break
        smoothed = [(p[0], p[1]) for p in pts]
        return self._interpolate(smoothed)
    def _haversine(self, a: Tuple[float, float], b: Tuple[float, float]) -> float:
        dlat = math.radians(b[0] - a[0])
        dlon = math.radians(b[1] - a[1])
        sin_h = math.sin(dlat / 2) ** 2 + math.cos(math.radians(a[0])) * \
                math.cos(math.radians(b[0])) * math.sin(dlon / 2) ** 2
        return self._R * 2 * math.atan2(math.sqrt(sin_h), math.sqrt(1 - sin_h))
    def _interpolate(self, path: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        result: List[Tuple[float, float]] = []
        for i in range(len(path) - 1):
            p0, p1 = path[i], path[i + 1]
            dist = self._haversine(p0, p1)
            if dist <= self._spacing:
                if i == 0:
                    result.append(p0)
                result.append(p1)
                continue
            n = max(2, int(dist / self._spacing) + 1)
            seg = [
                (p0[0] + (p1[0] - p0[0]) * t / (n - 1),
                 p0[1] + (p1[1] - p0[1]) * t / (n - 1))
                for t in range(n)
            ]
            if i == 0:
                result.extend(seg)
            else:
                result.extend(seg[1:])
        return result