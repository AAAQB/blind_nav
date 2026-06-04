import sys, os, unittest, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from backend.algorithm.cost_function import StaticCost, TimeDependentCost, CostFunction
from backend.config import WeightCoefficients
class TestStaticCost(unittest.TestCase):
    def setUp(self):
        self.cost = StaticCost()
    def _t(self, **kw):
        defaults = {
            "tactile_paving": "yes", "steps": "no", "surface": "asphalt",
            "lit": "yes", "sidewalk": "yes", "highway": "footway",
            "incline": "0%", "width": "3.0", "length": 100.0,
        }
        defaults.update(kw)
        return defaults
    def test_optimal_low(self):
        c = self.cost.compute(self._t())
        self.assertLess(c, 15.0)
    def test_worst_high(self):
        c = self.cost.compute(self._t(
            tactile_paving="no", steps="yes", surface="sand",
            lit="no", sidewalk="no", highway="motorway",
            incline="15%", width="0.5",
        ))
        self.assertGreater(c, 30.0)
    def test_empty_tags(self):
        c = self.cost.compute({})
        self.assertIsInstance(c, float)
        self.assertGreater(c, 0)
    def test_steps_penalty(self):
        w = self.cost.compute(self._t(steps="yes"))
        wo = self.cost.compute(self._t(steps="no"))
        self.assertGreater(w, wo)
    def test_lighting(self):
        unlit = self.cost.compute(self._t(lit="no"))
        lit = self.cost.compute(self._t(lit="yes"))
        self.assertGreater(unlit, lit)
    def test_surface_ordering(self):
        a = self.cost.compute(self._t(surface="asphalt"))
        g = self.cost.compute(self._t(surface="gravel"))
        s = self.cost.compute(self._t(surface="sand"))
        self.assertLess(a, g)
        self.assertLess(g, s)
    def test_custom_weights(self):
        w = WeightCoefficients(tactile_paving=10.0)
        c = StaticCost(w)
        yes = c.compute(self._t(tactile_paving="yes"))
        no_ = c.compute(self._t(tactile_paving="no"))
        self.assertAlmostEqual(no_ - yes, 90.0, delta=2.0)
class TestTimeDependentCost(unittest.TestCase):
    def setUp(self):
        self.dyn = TimeDependentCost(StaticCost())
    def _t(self, **kw):
        d = {"lit": "no", "highway": "footway", "length": 100.0}
        d.update(kw)
        return d
    def test_day_discounts_unlit(self):
        unlit = self.dyn.compute(self._t(lit="no"), hour=14)
        lit = self.dyn.compute(self._t(lit="yes"), hour=14)
        self.assertLess(unlit, lit)
    def test_night_penalises_unlit(self):
        unlit = self.dyn.compute(self._t(lit="no"), hour=21)
        lit = self.dyn.compute(self._t(lit="yes"), hour=21)
        self.assertGreater(unlit, lit * 1.5)
    def test_temporal_variation(self):
        day = self.dyn.compute(self._t(lit="no"), hour=14)
        night = self.dyn.compute(self._t(lit="no"), hour=21)
        self.assertGreater(night, day)
    def test_lit_variation_small(self):
        day = self.dyn.compute(self._t(lit="yes", highway="footway"), hour=14)
        night = self.dyn.compute(self._t(lit="yes", highway="footway"), hour=21)
        self.assertNotAlmostEqual(day, night, delta=0.01)
class TestCostFunction(unittest.TestCase):
    def test_compute_both(self):
        cf = CostFunction()
        tags = {"lit": "no", "highway": "footway", "length": 100.0}
        s, d = cf.compute_both(tags, hour=21)
        self.assertGreater(d, s)
    def test_zero_weights(self):
        """All weights zero → cost must be 0 (pure weighted sum, no length term)."""
        z = WeightCoefficients(tactile_paving=0, steps=0, surface=0,
                                lighting=0, sidewalk=0, highway=0,
                                incline=0, width=0)
        cf = CostFunction(z)
        c = cf.compute_static({"steps": "yes", "surface": "sand", "highway": "motorway"})
        self.assertAlmostEqual(c, 0.0, places=4)
if __name__ == "__main__":
    unittest.main()