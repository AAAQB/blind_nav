import sys, os, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import networkx as nx
from backend.algorithm.astar import WeightedAStar
def _grid_3x3():
    G = nx.Graph()
    for r in range(3):
        for c in range(3):
            G.add_node(r * 3 + c, y=float(r), x=float(c))
    edges = [(0, 1), (1, 2), (3, 4), (4, 5), (6, 7), (7, 8),
             (0, 3), (3, 6), (1, 4), (4, 7), (2, 5), (5, 8)]
    for u, v in edges:
        G.add_edge(u, v, tags={})
    return G
def _unit_cost(c, n, t, h):
    return 1.0
class TestWeightedAStar(unittest.TestCase):
    def setUp(self):
        self.G = _grid_3x3()
        self.searcher = WeightedAStar(cost_function=_unit_cost)
    def test_trivial(self):
        r = self.searcher.search(self.G, 0, 0)
        self.assertIsNotNone(r)
        self.assertEqual(r["path"], [0])
        self.assertEqual(r["cost"], 0.0)
    def test_adjacent(self):
        r = self.searcher.search(self.G, 0, 1)
        self.assertIsNotNone(r)
        self.assertEqual(r["path"], [0, 1])
        self.assertEqual(r["cost"], 1.0)
    def test_diagonal(self):
        r = self.searcher.search(self.G, 0, 8)
        self.assertIsNotNone(r)
        self.assertEqual(len(r["path"]) - 1, 4)
    def cost_accumulation(self):
        r = self.searcher.search(self.G, 0, 8)
        self.assertEqual(r["cost"], len(r["path"]) - 1)
    def test_nonexistent_goal(self):
        self.assertIsNone(self.searcher.search(self.G, 0, 999))
    def test_nonexistent_start(self):
        self.assertIsNone(self.searcher.search(self.G, 999, 0))
    def test_optimality(self):
        r = self.searcher.search(self.G, 0, 8)
        self.assertEqual(len(r["path"]) - 1, 4)
class TestWeightedAStarCostAware(unittest.TestCase):
    def setUp(self):
        self.G = _grid_3x3()
        self.G.clear_edges()
        tags = [
            (0, 1, {"surface": "gravel"}), (1, 2, {"surface": "asphalt"}),
            (3, 4, {"surface": "asphalt"}), (4, 5, {"surface": "asphalt"}),
            (6, 7, {"surface": "asphalt"}), (7, 8, {"surface": "asphalt"}),
            (0, 3, {"surface": "asphalt"}), (3, 6, {"surface": "asphalt"}),
            (1, 4, {"surface": "sand"}),    (4, 7, {"surface": "asphalt"}),
            (2, 5, {"surface": "asphalt"}), (5, 8, {"surface": "asphalt"}),
        ]
        for u, v, t in tags:
            self.G.add_edge(u, v, tags=t)
    def test_avoids_high_cost_edges(self):
        from backend.algorithm.cost_function import CostFunction
        cf = CostFunction()
        def fn(cid, nid, tags, hour):
            return cf.compute_static(tags)
        searcher = WeightedAStar(cost_function=fn)
        r = searcher.search(self.G, 0, 4)
        self.assertIsNotNone(r)
        self.assertIn(3, r["path"])
if __name__ == "__main__":
    unittest.main()