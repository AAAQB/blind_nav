from __future__ import annotations
import heapq
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple
import networkx as nx
from backend.config import MAX_SEARCH_ITERATIONS, HEURISTIC_WEIGHT
from backend.utils.geoutils import euclidean_approx
logger = logging.getLogger(__name__)
@dataclass(order=True)
class _PrioritizedNode:
    f_score: float
    g_score: float = field(compare=False)
    node_id: int = field(compare=False)
class WeightedAStar:
    def __init__(
        self,
        cost_function: Callable[[int, int, Dict[str, Any], Optional[int]], float],
        heuristic_weight: float = HEURISTIC_WEIGHT,
        max_iterations: int = MAX_SEARCH_ITERATIONS,
    ) -> None:
        self._cost_fn = cost_function
        self._w = heuristic_weight
        self._max_iter = max_iterations
    def search(
        self,
        graph: nx.Graph,
        start_node: int,
        goal_node: int,
        hour: Optional[int] = None,
        progress_callback: Optional[Callable[[int, int, int], None]] = None,
    ) -> Optional[Dict[str, Any]]:
        if start_node not in graph or goal_node not in graph:
            logger.warning("start_node=%s or goal_node=%s not in graph", start_node, goal_node)
            return None
        start_pos = _node_pos(graph, start_node)
        goal_pos = _node_pos(graph, goal_node)
        frontier: List[_PrioritizedNode] = []
        heapq.heappush(frontier, _PrioritizedNode(
            f_score=self._heuristic(start_pos, goal_pos),
            g_score=0.0,
            node_id=start_node,
        ))
        g_score: Dict[int, float] = {start_node: 0.0}
        came_from: Dict[int, int] = {}
        closed: set = set()
        explored = 0
        while frontier and explored < self._max_iter:
            current = heapq.heappop(frontier)
            cid = current.node_id
            cg = current.g_score
            if cid in closed:
                continue
            if cid in g_score and cg > g_score[cid]:
                continue
            closed.add(cid)
            explored += 1
            if cid == goal_node:
                logger.info("A* finished: explored=%d, cost=%.2f", explored, cg)
                return {
                    "path": _reconstruct_path(came_from, cid, start_node),
                    "cost": cg,
                    "explored_count": explored,
                    "closed_set_size": len(closed),
                }
            for nid in graph.neighbors(cid):
                if nid in closed:
                    continue
                edge_tags = _edge_tags(graph, cid, nid)
                edge_cost = self._cost_fn(cid, nid, edge_tags, hour)
                tentative = cg + edge_cost
                if nid not in g_score or tentative < g_score[nid]:
                    g_score[nid] = tentative
                    came_from[nid] = cid
                    h = self._heuristic(_node_pos(graph, nid), goal_pos)
                    heapq.heappush(frontier, _PrioritizedNode(
                        f_score=tentative + self._w * h,
                        g_score=tentative,
                        node_id=nid,
                    ))
            if progress_callback:
                progress_callback(explored, len(closed), len(frontier))
        logger.warning("A* exhausted frontier without reaching goal (explored=%d)", explored)
        return None
    @staticmethod
    def _heuristic(a: Tuple[float, float], b: Tuple[float, float]) -> float:
        # Use approximate metric distance, more accurate than raw lon/lat Euclidean
        return euclidean_approx(a, b)
def _node_pos(graph: nx.Graph, nid: int) -> Tuple[float, float]:
    return (graph.nodes[nid].get("y", 0.0), graph.nodes[nid].get("x", 0.0))
def _edge_tags(graph: nx.Graph, u: int, v: int) -> Dict[str, Any]:
    ed = graph.get_edge_data(u, v)
    if ed is None:
        return {"highway": "unknown", "length": 0.0}
    tags = dict(ed.get("tags", {}))
    length = ed.get("length")
    if length is not None:
        tags["length"] = float(length)
    return tags
def _reconstruct_path(
    came_from: Dict[int, int], current: int, start: int,
) -> List[int]:
    path = [current]
    while current != start:
        current = came_from[current]
        path.append(current)
    path.reverse()
    return path
def edge_cost_sum(
    graph: nx.Graph,
    path: List[int],
    cost_fn: Callable[[int, int, Dict[str, Any], Optional[int]], float],
    hour: Optional[int] = None,
) -> float:
    total = 0.0
    for u, v in zip(path, path[1:]):
        total += cost_fn(u, v, _edge_tags(graph, u, v), hour)
    return total