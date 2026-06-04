from __future__ import annotations
import heapq
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import networkx as nx
from backend.algorithm.astar import _node_pos, _edge_tags, HEURISTIC_WEIGHT
from backend.config import MAX_SEARCH_ITERATIONS, BIDIRECTIONAL_MEET_RADIUS
logger = logging.getLogger(__name__)
@dataclass(order=True)
class _BiNode:
    f_score: float
    g_score: float = field(compare=False)
    node_id: int = field(compare=False)
    direction: int = field(compare=False)
class BidirectionalAStar:
    def __init__(
        self,
        cost_function: Callable[[int, int, Dict[str, Any], Optional[int]], float],
        heuristic_weight: float = HEURISTIC_WEIGHT,
        meet_radius: int = BIDIRECTIONAL_MEET_RADIUS,
        max_iterations: int = MAX_SEARCH_ITERATIONS,
    ) -> None:
        self._cost_fn = cost_function
        self._w = heuristic_weight
        self._radius = meet_radius
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
            return None
        if start_node == goal_node:
            return {"path": [start_node], "cost": 0.0, "explored_count": 0, "meet_node": start_node}
        fwd_frontier: List[_BiNode] = []
        bwd_frontier: List[_BiNode] = []
        h_sg = self._heuristic(graph, start_node, goal_node)
        heapq.heappush(fwd_frontier, _BiNode(f_score=h_sg, g_score=0.0, node_id=start_node, direction=0))
        heapq.heappush(bwd_frontier, _BiNode(f_score=h_sg, g_score=0.0, node_id=goal_node, direction=1))
        fwd_g: Dict[int, float] = {start_node: 0.0}
        bwd_g: Dict[int, float] = {goal_node: 0.0}
        fwd_parent: Dict[int, int] = {}
        bwd_parent: Dict[int, int] = {}
        fwd_closed: Set[int] = set()
        bwd_closed: Set[int] = set()
        best_meet: Optional[int] = None
        best_cost = float("inf")
        explored = 0
        iterations = 0
        while (fwd_frontier or bwd_frontier) and iterations < self._max_iter:
            iterations += 1
            f_best = fwd_frontier[0].f_score if fwd_frontier else float("inf")
            b_best = bwd_frontier[0].f_score if bwd_frontier else float("inf")
            if f_best <= b_best:
                self._expand(graph, fwd_frontier, fwd_g, fwd_parent, fwd_closed,
                             hour, 0, goal_node)
            else:
                self._expand(graph, bwd_frontier, bwd_g, bwd_parent, bwd_closed,
                             hour, 1, start_node)
            explored += 1
            meet, total = self._find_meeting(fwd_closed, bwd_closed, fwd_g, bwd_g,
                                              fwd_parent, bwd_parent, best_cost)
            if meet is not None and total < best_cost:
                best_meet = meet
                best_cost = total
            if best_cost < float("inf"):
                f_min = fwd_frontier[0].f_score if fwd_frontier else float("inf")
                b_min = bwd_frontier[0].f_score if bwd_frontier else float("inf")
                if f_min >= best_cost and b_min >= best_cost:
                    break
            if progress_callback:
                progress_callback(explored, len(fwd_closed), len(bwd_closed))
        if best_meet is None:
            logger.warning("BiA* exhausted without meeting (explored=%d)", explored)
            return None
        path = _reconstruct_bi_path(fwd_parent, bwd_parent, best_meet, start_node, goal_node)
        logger.info("BiA* finished: explored=%d, cost=%.2f, meet=%s", explored, best_cost, best_meet)
        return {
            "path": path,
            "cost": best_cost,
            "explored_count": explored,
            "meet_node": best_meet,
            "forward_explored": len(fwd_closed),
            "backward_explored": len(bwd_closed),
        }
    def _expand(
        self,
        graph: nx.Graph,
        frontier: List[_BiNode],
        g_score: Dict[int, float],
        parent: Dict[int, int],
        closed: Set[int],
        hour: Optional[int],
        direction: int,
        opposite_goal: int,
    ) -> None:
        if not frontier:
            return
        cur = heapq.heappop(frontier)
        cid = cur.node_id
        if cid in closed:
            return
        closed.add(cid)
        for nid in graph.neighbors(cid):
            if nid in closed:
                continue
            tags = _edge_tags(graph, cid, nid)
            ec = self._cost_fn(cid, nid, tags, hour)
            tentative = g_score[cid] + ec
            if nid not in g_score or tentative < g_score[nid]:
                g_score[nid] = tentative
                parent[nid] = cid
                h = self._heuristic(graph, nid, opposite_goal)
                heapq.heappush(frontier, _BiNode(
                    f_score=tentative + self._w * h,
                    g_score=tentative,
                    node_id=nid,
                    direction=direction,
                ))
    @staticmethod
    def _heuristic(graph: nx.Graph, a: int, b: int) -> float:
        pa = _node_pos(graph, a)
        pb = _node_pos(graph, b)
        return math.sqrt((pa[0] - pb[0]) ** 2 + (pa[1] - pb[1]) ** 2)
    @staticmethod
    def _find_meeting(
        fwd_closed: Set[int],
        bwd_closed: Set[int],
        fwd_g: Dict[int, float],
        bwd_g: Dict[int, float],
        fwd_parent: Dict[int, int],
        bwd_parent: Dict[int, int],
        best_so_far: float,
    ) -> Tuple[Optional[int], float]:
        inter = fwd_closed & bwd_closed
        best_node: Optional[int] = None
        best_cost = best_so_far
        for node in inter:
            total = fwd_g.get(node, float("inf")) + bwd_g.get(node, float("inf"))
            if total < best_cost:
                best_cost = total
                best_node = node
        return best_node, best_cost
def _reconstruct_bi_path(
    fwd_parent: Dict[int, int],
    bwd_parent: Dict[int, int],
    meet_node: int,
    start_node: int,
    goal_node: int,
) -> List[int]:
    fwd: List[int] = []
    cur = meet_node
    while cur != start_node:
        fwd.append(cur)
        cur = fwd_parent.get(cur, start_node)
    fwd.append(start_node)
    fwd.reverse()
    bwd: List[int] = []
    cur = meet_node
    while cur != goal_node:
        nxt = bwd_parent.get(cur, goal_node)
        if nxt == cur:
            break
        cur = nxt
        bwd.append(cur)
    return fwd + bwd
import math