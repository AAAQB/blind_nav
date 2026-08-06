from __future__ import annotations
import math
from typing import List, Tuple
_EARTH_RADIUS = 6_371_000.0
def haversine(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    sin_h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return _EARTH_RADIUS * 2 * math.atan2(math.sqrt(sin_h), math.sqrt(1 - sin_h))
def euclidean_approx(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    dlat = (a[0] - b[0]) * 111_320
    dlon = (a[1] - b[1]) * 111_320 * math.cos(math.radians((a[0] + b[0]) / 2))
    return math.sqrt(dlat ** 2 + dlon ** 2)
def bearing(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    dlon = lon2 - lon1
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360
def path_length(coords: List[Tuple[float, float]]) -> float:
    total = 0.0
    for i in range(len(coords) - 1):
        total += haversine(coords[i], coords[i + 1])
    return total
def node_to_coord(graph, node_id: int) -> Tuple[float, float]:
    return (graph.nodes[node_id].get("y", 0.0), graph.nodes[node_id].get("x", 0.0))
def path_to_coords(graph, path: List[int]) -> List[Tuple[float, float]]:
    return [node_to_coord(graph, n) for n in path]