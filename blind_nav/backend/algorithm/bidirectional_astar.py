from __future__ import annotations
import heapq
import logging
import math
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
    """Bidirectional A* search for accessibility-aware pathfinding.

    The search expands alternately from start (forward) and goal (backward).
    When the two frontiers meet (their closed sets intersect), the algorithm
    evaluates the total cost through each meeting node and keeps the best.

    Termination: once the minimum f-scores of BOTH frontiers exceed the
    best known total cost, no better path can exist and the search stops.

    Key differences from WeightedAStar (single-direction):
    - Two frontiers, two g-score maps, two parent maps, two closed sets.
    - Meeting detection via intersection of closed sets.
    - Stale-entry filtering: nodes popped with an outdated g_score are
      skipped (same guard as WeightedAStar, was missing in original code).
    """

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
    heapq.heappush(bwd_frontier, _BiNode(f_score=h_sg, g_score=0.0, node_id=goal_node,  direction=1))

    fwd_g:      Dict[int, float] = {start_node: 0.0}
    bwd_g:      Dict[int, float] = {goal_node:  0.0}
    fwd_parent: Dict[int, int]   = {}
    bwd_parent: Dict[int, int]   = {}
    fwd_closed: Set[int]         = set()
    bwd_closed: Set[int]         = set()

    # 用列表包装，方便 _expand 内部直接写回，避免重复传参
    best: List = [None, float("inf")]   # [meet_node, total_cost]
    explored = 0
    iterations = 0

    while (fwd_frontier or bwd_frontier) and iterations < self._max_iter:
        iterations += 1
        f_best = fwd_frontier[0].f_score if fwd_frontier else float("inf")
        b_best = bwd_frontier[0].f_score if bwd_frontier else float("inf")

        if f_best <= b_best:
            self._expand(graph, fwd_frontier, fwd_g, fwd_parent, fwd_closed,
                         hour, 0, goal_node,
                         bwd_closed, bwd_g, best)
        else:
            self._expand(graph, bwd_frontier, bwd_g, bwd_parent, bwd_closed,
                         hour, 1, start_node,
                         fwd_closed, fwd_g, best)
        explored += 1

        # 终止条件：两侧 frontier 最小 f 都超过当前最优代价
        if best[1] < float("inf"):
            f_min = fwd_frontier[0].f_score if fwd_frontier else float("inf")
            b_min = bwd_frontier[0].f_score if bwd_frontier else float("inf")
            if f_min >= best[1] and b_min >= best[1]:
                break

        if progress_callback:
            progress_callback(explored, len(fwd_closed), len(bwd_closed))

    if best[0] is None:
        logger.warning("BiA* exhausted without meeting (explored=%d)", explored)
        return None

    path = _reconstruct_bi_path(fwd_parent, bwd_parent, best[0], start_node, goal_node)
    logger.info("BiA* finished: explored=%d, cost=%.2f, meet=%s", explored, best[1], best[0])
    return {
        "path": path,
        "cost": best[1],
        "explored_count": explored,
        "meet_node": best[0],
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
    opp_closed: Set[int],
    opp_g: Dict[int, float],
    best: List,
) -> None:
    if not frontier:
        return
    cur = heapq.heappop(frontier)
    cid = cur.node_id
    cg  = cur.g_score

    if cid in closed:
        return
    if cid in g_score and cg > g_score[cid]:
        return

    closed.add(cid)

    # O(1) 增量相遇检测：节点刚被 close 时就地查对面
    if cid in opp_closed:
        total = g_score[cid] + opp_g.get(cid, float("inf"))
        if total < best[1]:
            best[0], best[1] = cid, total

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
    def _heuristic(graph: nx.Graph, a: int, b: int) -> float:
        pa = _node_pos(graph, a)
        pb = _node_pos(graph, b)
        return math.sqrt((pa[0] - pb[0]) ** 2 + (pa[1] - pb[1]) ** 2)

    @staticmethod
   
def _reconstruct_bi_path(
    fwd_parent: Dict[int, int],
    bwd_parent: Dict[int, int],
    meet_node: int,
    start_node: int,
    goal_node: int,
) -> List[int]:
    """Reconstruct the full path from start → meet → goal.

    Forward half: follow fwd_parent from meet_node back to start_node.
    Backward half: follow bwd_parent from meet_node toward goal_node.

    In the backward search, bwd_parent[nid] = cid means "nid was reached
    from cid during the backward expansion (cid is closer to goal)".
    So following bwd_parent from meet_node walks toward goal_node.
    """
    # --- forward half: start → meet ---
    fwd: List[int] = []
    cur = meet_node
    while cur != start_node:
        fwd.append(cur)
        nxt = fwd_parent.get(cur)
        if nxt is None:
            # Should never happen for a valid meeting node
            break
        cur = nxt
    fwd.append(start_node)
    fwd.reverse()

    # --- backward half: meet → goal ---
    bwd: List[int] = []
    cur = meet_node
    while cur != goal_node:
        nxt = bwd_parent.get(cur)
        if nxt is None:
            # meet_node might be goal_node's immediate backward neighbour
            break
        cur = nxt
        bwd.append(cur)

    return fwd + bwd
