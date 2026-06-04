import sys, os, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from backend.config import (
    WeightCoefficients, PRESET_MODES, TIME_SLOTS, get_time_slot,
)
from backend.algorithm.cost_function import CostFunction
from backend.algorithm.path_smoother import PathSmoother
class TestPathSmoother(unittest.TestCase):
    def setUp(self):
        self.smoother = PathSmoother(iterations=50, learning_rate=0.5)
    def test_short_path_unchanged(self):
        p = [(0., 0.), (1., 1.)]
        self.assertEqual(self.smoother.smooth(p), p)
    def test_endpoints_fixed(self):
        p = [(0., 0.), (1., 1.), (2., 2.)]
        r = self.smoother.smooth(p)
        self.assertEqual(r[0], p[0])
        self.assertEqual(r[-1], p[-1])
    def test_interior_moved(self):
        p = [(0., 0.), (0.5, 0.), (1., 0.5), (1.5, 0.), (2., 0.)]
        r = self.smoother.smooth(p)
        changed = sum(1 for i in range(1, len(p) - 1) if r[i] != p[i])
        self.assertGreater(changed, 0)
    def test_smooth_produces_more_points(self):
        p = [(0., 0.), (0.01, 0.), (0.02, 0.01)]
        r = self.smoother.smooth(p)
        self.assertGreater(len(r), len(p))
class TestConfigConsistency(unittest.TestCase):
    def test_all_presets_have_weights(self):
        for mid, mode in PRESET_MODES.items():
            w = mode["weights"]
            self.assertIsInstance(w, WeightCoefficients)
            d = w.to_dict()
            for k in ("tactile_paving", "steps", "surface", "lighting",
                      "sidewalk", "highway", "incline", "width"):
                self.assertIn(k, d)
                self.assertGreaterEqual(d[k], 0)
    def test_time_slots_cover_24h(self):
        covered = set()
        for h in range(24):
            s = get_time_slot(h)
            covered.add(s.name)
        self.assertEqual(len(covered), len(TIME_SLOTS))
    def test_overnight_slot(self):
        s = get_time_slot(2)
        self.assertEqual(s.name, "late_night")
class TestModeCostDifferences(unittest.TestCase):
    def setUp(self):
        self.seg = {
            "tactile_paving": "no", "steps": "no", "surface": "asphalt",
            "lit": "no", "sidewalk": "yes", "highway": "residential",
            "length": 100.0,
        }
    def test_blind_rates_worse_than_balanced(self):
        b = CostFunction(PRESET_MODES["blind"]["weights"]).compute_static(self.seg)
        ba = CostFunction(PRESET_MODES["balanced"]["weights"]).compute_static(self.seg)
        self.assertGreater(b, ba)
    def test_night_rates_worse_than_balanced(self):
        n = CostFunction(PRESET_MODES["night"]["weights"]).compute_static(self.seg)
        ba = CostFunction(PRESET_MODES["balanced"]["weights"]).compute_static(self.seg)
        self.assertGreater(n, ba)
    def test_accessibility_vs_distance_only(self):
        dist_w = WeightCoefficients(tactile_paving=0, steps=0, surface=0,
                                      lighting=0, sidewalk=0, highway=0,
                                      incline=0, width=0)
        bad = {"tactile_paving": "no", "steps": "yes", "surface": "gravel",
               "lit": "no", "sidewalk": "no", "highway": "primary", "length": 100.0}
        good = {"tactile_paving": "yes", "steps": "no", "surface": "asphalt",
                "lit": "yes", "sidewalk": "yes", "highway": "footway", "length": 100.0}
        dist_cf = CostFunction(dist_w)
        acc_cf = CostFunction(WeightCoefficients())
        dd = abs(dist_cf.compute_static(bad) - dist_cf.compute_static(good))
        self.assertAlmostEqual(dd, 0.0, delta=0.001)
        ad = abs(acc_cf.compute_static(bad) - acc_cf.compute_static(good))
        self.assertGreater(ad, 30.0)
if __name__ == "__main__":
    unittest.main()