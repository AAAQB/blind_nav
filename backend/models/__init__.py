from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
@dataclass
class PathRequest:
    start_lat: float
    start_lon: float
    end_lat: float
    end_lon: float
    hour: int = 14
    mode: Optional[str] = None
    weights: Optional[Dict[str, float]] = None
    use_bidirectional: bool = True
    use_dynamic_cost: bool = True
    smooth_path: bool = True
    area: str = "kl"
@dataclass
class PathResult:
    path: List[List[float]]
    path_node_ids: List[int]
    total_cost: float
    static_cost: float
    dynamic_cost: Optional[float] = None
    total_distance_m: float = 0.0
    explored_count: int = 0
    time_slot: str = "day"
    time_slot_name: str = "day"
    algorithm: str = "weighted_a*"
    num_nodes: int = 0
    meet_node: Optional[int] = None
    forward_explored: Optional[int] = None
    backward_explored: Optional[int] = None
@dataclass
class ScenarioResult:
    name: str
    label: str
    mode: str
    hour: int
    path: List[List[float]]
    cost: float
    distance_m: float
    explored: int
    num_nodes: int