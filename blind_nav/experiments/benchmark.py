from __future__ import annotations
import csv
import json
import math
import os
import pickle
import random
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import networkx as nx
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from backend.algorithm.astar import WeightedAStar
from backend.algorithm.bidirectional_astar import BidirectionalAStar
from backend.algorithm.cost_function import CostFunction
from backend.config import (
    WeightCoefficients, PRESET_MODES, BENCHMARK_TRIALS,
    BENCHMARK_MIN_DISTANCE_M, BENCHMARK_TIME_HOURS,
)
from backend.utils.geoutils import haversine_distance
class BenchmarkRunner:
    def __init__(self, results_dir: str | None = None) -> None:
        self._dir = results_dir or os.path.join(os.path.dirname(__file__), "results")
        os.makedirs(self._dir, exist_ok=True)
        self._ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    def run_all(self, graph: nx.Graph) -> Dict:
        pairs = self._node_pairs(graph, BENCHMARK_TRIALS)
        results: Dict[str, Any] = {
            "metadata": {
                "timestamp": self._ts,
                "graph_nodes": graph.number_of_nodes(),
                "graph_edges": graph.number_of_edges(),
            },
            "experiments": {},
        }
        results["experiments"]["algorithm_comparison"] = self._algo_comparison(graph, pairs)
        results["experiments"]["cost_comparison"] = self._cost_comparison(graph, pairs)
        results["experiments"]["mode_comparison"] = self._mode_comparison(graph, pairs[:10])
        results["experiments"]["time_analysis"] = self._time_analysis(graph, pairs[:10])
        self._save(results)
        return results
    def _node_pairs(self, G: nx.Graph, n: int) -> List[Tuple[int, int]]:
        nodes = list(G.nodes())
        if len(nodes) < 2:
            return []
        pairs: List[Tuple[int, int]] = []
        while len(pairs) < n and len(pairs) < len(nodes) * 10:
            a, b = random.sample(nodes, 2)
            d = haversine_distance(
                (G.nodes[a].get("y", 0), G.nodes[a].get("x", 0)),
                (G.nodes[b].get("y", 0), G.nodes[b].get("x", 0)),
            )
            if d >= BENCHMARK_MIN_DISTANCE_M:
                pairs.append((a, b))
        return pairs
    def _cost_fn(self, weights: WeightCoefficients, dynamic: bool = False):
        cf = CostFunction(weights)
        def fn(cid, nid, tags, hour):
            if dynamic and hour is not None:
                return cf.compute_dynamic(tags, hour)
            return cf.compute_static(tags)
        return fn
    def _algo_comparison(self, G: nx.Graph, pairs: List[Tuple[int, int]]) -> List[Dict]:
        fn = self._cost_fn(WeightCoefficients())
        rows = []
        for start, goal in pairs:
            t0 = time.time()
            ur = WeightedAStar(cost_function=fn).search(G, start, goal)
            ut = time.time() - t0
            t0 = time.time()
            br = BidirectionalAStar(cost_function=fn).search(G, start, goal)
            bt = time.time() - t0
            rows.append({
                "start": start, "goal": goal,
                "uni_cost": ur["cost"] if ur else None,
                "uni_explored": ur["explored_count"] if ur else 0,
                "uni_time_ms": round(ut * 1000, 2),
                "uni_path_nodes": len(ur["path"]) if ur else 0,
                "bi_cost": br["cost"] if br else None,
                "bi_explored": br.get("explored_count", 0) if br else 0,
                "bi_time_ms": round(bt * 1000, 2),
                "bi_path_nodes": len(br["path"]) if br else 0,
                "found": ur is not None and br is not None,
            })
        return rows
    def _cost_comparison(self, G: nx.Graph, pairs: List[Tuple[int, int]]) -> List[Dict]:
        rows = []
        for start, goal in pairs:
            static_fn = self._cost_fn(WeightCoefficients(), dynamic=False)
            dynamic_fn = self._cost_fn(WeightCoefficients(), dynamic=True)
            sr = WeightedAStar(cost_function=static_fn).search(G, start, goal, 21)
            dr = WeightedAStar(cost_function=dynamic_fn).search(G, start, goal, 21)
            rows.append({
                "start": start, "goal": goal,
                "static_cost": sr["cost"] if sr else None,
                "dynamic_cost": dr["cost"] if dr else None,
                "static_explored": sr["explored_count"] if sr else 0,
                "dynamic_explored": dr["explored_count"] if dr else 0,
                "found": sr is not None and dr is not None,
            })
        return rows
    def _mode_comparison(self, G: nx.Graph, pairs: List[Tuple[int, int]]) -> List[Dict]:
        rows = []
        for start, goal in pairs:
            md: Dict[str, Any] = {}
            for mid, mode in PRESET_MODES.items():
                fn = self._cost_fn(mode["weights"])
                r = BidirectionalAStar(cost_function=fn).search(G, start, goal)
                md[mid] = {
                    "cost": r["cost"] if r else None,
                    "explored": r.get("explored_count", 0) if r else 0,
                    "path_nodes": len(r["path"]) if r else 0,
                } if r else None
            rows.append({"start": start, "goal": goal, "modes": md})
        return rows
    def _time_analysis(self, G: nx.Graph, pairs: List[Tuple[int, int]]) -> List[Dict]:
        rows = []
        weights = PRESET_MODES["blind"]["weights"]
        for start, goal in pairs:
            hrs: Dict[int, Any] = {}
            for h in BENCHMARK_TIME_HOURS:
                fn = self._cost_fn(weights, dynamic=True)
                r = BidirectionalAStar(cost_function=fn).search(G, start, goal, h)
                hrs[h] = {"cost": r["cost"] if r else None, "explored": r.get("explored_count", 0) if r else 0}
            rows.append({"start": start, "goal": goal, "mode": "blind", "hours": hrs})
        return rows
    def _save(self, results: Dict) -> None:
        json_path = os.path.join(self._dir, f"benchmark_{self._ts}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        for exp_name, exp_data in results["experiments"].items():
            if not exp_data:
                continue
            csv_path = os.path.join(self._dir, f"{exp_name}_{self._ts}.csv")
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                if isinstance(exp_data[0], dict):
                    w = csv.DictWriter(f, fieldnames=list(exp_data[0].keys()))
                    w.writeheader()
                    w.writerows(exp_data)
        print(f"Results saved to {self._dir}/  (json + {len(results['experiments'])} CSVs)")
def run(graph_path: Optional[str] = None, trials: int = BENCHMARK_TRIALS):
    if graph_path and os.path.exists(graph_path):
        with open(graph_path, "rb") as f:
            G = pickle.load(f)
        print(f"Loaded graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    else:
        print("No graph file; building a 50×50 synthetic grid.")
        G = nx.Graph()
        size = 50
        for r in range(size):
            for c in range(size):
                nid = r * size + c
                G.add_node(nid, y=r * 0.001, x=c * 0.001)
        for r in range(size):
            for c in range(size):
                n = r * size + c
                if c + 1 < size:
                    G.add_edge(n, r * size + c + 1, tags={})
                if r + 1 < size:
                    G.add_edge(n, (r + 1) * size + c, tags={})
        print(f"Synthetic: {G.number_of_nodes()} nodes")
    runner = BenchmarkRunner()
    results = runner.run_all(G)
    algo = results["experiments"]["algorithm_comparison"]
    if algo:
        found = [r for r in algo if r.get("found")]
        if found:
            ue = sum(r["uni_explored"] for r in found) / len(found)
            be = sum(r["bi_explored"] for r in found) / len(found)
            ut = sum(r["uni_time_ms"] for r in found) / len(found)
            bt = sum(r["bi_time_ms"] for r in found) / len(found)
            print(f"\nAlgorithm Comparison ({len(found)} trials):")
            print(f"  Uni A*:   avg {ue:.0f} nodes  {ut:.2f} ms")
            print(f"  Bi A*:    avg {be:.0f} nodes  {bt:.2f} ms")
            if ue > 0:
                print(f"  Reduction: {(1 - be / ue) * 100:.1f}%")