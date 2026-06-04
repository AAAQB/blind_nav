import sys, os, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import networkx as nx
from backend.algorithm.bidirectional_astar import BidirectionalAStar
from backend.algorithm.astar import WeightedAStar
def _grid(size=10):
    G = nx.Graph()
    for r in range(size):
        for c in range(size):
            G.add_node(r * size + c, y=r / 10.0, x=c / 10.0)
    for r in range(size):
        for c in range(size):
            n = r * size + c
            if c + 1 < size:
                G.add_edge(n, r * size + c + 1, tags={})
            if r + 1 < size:
                G.add_edge(n, (r + 1) * size + c, tags={})
    return G
def _unit(c, n, t, h):
    return 1.0
class TestBidirectionalAStar(unittest.TestCase):
    def setUp(self):
        self.G = _grid(10)
        self.searcher = BidirectionalAStar(cost_function=_unit)
    def test_path_exists(self):
        r = self.searcher.search(self.G, 0, 99)
        self.assertIsNotNone(r)
        self.assertIn("path", r)
    def test_optimal_length(self):
        r = self.searcher.search(self.G, 0, 99)
        self.assertIsNotNone(r)
        self.assertEqual(len(r["path"]) - 1, 18)
    def test_adjacent(self):
        r = self.searcher.search(self.G, 5, 6)
        self.assertIsNotNone(r)
        self.assertEqual(len(r["path"]), 2)
    def test_same_node(self):
        r = self.searcher.search(self.G, 42, 42)
        self.assertIsNotNone(r)
        self.assertEqual(r["path"], [42])
        self.assertEqual(r["cost"], 0.0)
    def test_meet_node_present(self):
        r = self.searcher.search(self.G, 0, 99)
        self.assertIn("meet_node", r)
        self.assertIsNotNone(r["meet_node"])
    def test_path_continuity(self):
        r = self.searcher.search(self.G, 0, 99)
        self.assertIsNotNone(r)
        path = r["path"]
        self.assertEqual(path[0], 0)
        self.assertEqual(path[-1], 99)
        for i in range(len(path) - 1):
            self.assertTrue(self.G.has_edge(path[i], path[i + 1]),
                            f"Missing edge {path[i]} → {path[i+1]}")
    def test_no_path(self):
        self.assertIsNone(self.searcher.search(self.G, 0, 9999))
    def test_reduced_exploration(self):
        bi = self.searcher.search(self.G, 0, 99)
        assert bi is not None
        uni = WeightedAStar(cost_function=_unit).search(self.G, 0, 99)
        assert uni is not None
        self.assertIn("forward_explored", bi)
        self.assertIn("backward_explored", bi)
        self.assertEqual(len(bi["path"]), len(uni["path"]))
if __name__ == "__main__":
    unittest.main()