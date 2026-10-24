import os, sys, unittest
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dust_analysis import dust_map, compare_before_after
from wave_optimizer import find_resonance, AdaptiveController, SAFE_LIMITS, recommend_pattern
from simulator import DustSurfaceSim


def surface(dusty, seed=1):
    rng = np.random.default_rng(seed)
    g = np.full((300, 300), 140.0) + rng.normal(0, 1.5, (300, 300))
    if dusty:
        for _ in range(1500):
            x, y = rng.integers(0, 296, 2)
            g[y:y+3, x:x+3] -= 40
    g = np.clip(g, 0, 255).astype(np.uint8)
    return np.stack([g, g, g], axis=-1)


class Tests(unittest.TestCase):
    def test_dust_score_orders_clean_below_dusty(self):
        self.assertLess(dust_map(surface(False))[1], dust_map(surface(True))[1])

    def test_before_after_efficiency(self):
        r = compare_before_after(surface(True), surface(False))
        self.assertGreater(r["cleaning_efficiency_pct"], 80)

    def test_resonance_found(self):
        sim = DustSurfaceSim(seed=3)
        f = np.arange(30_000, 55_000, 250)
        res = find_resonance(f, [sim.sensor_response(x) for x in f])
        self.assertTrue(res["reliable"])
        self.assertAlmostEqual(res["resonance_hz"], sim.resonance, delta=1_000)

    def test_flat_sweep_is_not_reliable(self):
        f = np.arange(30_000, 55_000, 250)
        self.assertFalse(find_resonance(f, np.ones(f.size))["reliable"])

    def test_controller_respects_limits_and_cleans(self):
        sim = DustSurfaceSim(seed=5)
        start = sim.dust_score()
        f = np.arange(30_000, 55_000, 250)
        res = find_resonance(f, [sim.sensor_response(x) for x in f])
        ctl = AdaptiveController(res["resonance_hz"], res["bandwidth_hz"], seed=1)
        for _ in range(25):
            p = ctl.propose()
            self.assertTrue(SAFE_LIMITS["duty_min"] <= p.duty <= SAFE_LIMITS["duty_max"])
            self.assertTrue(SAFE_LIMITS["freq_min_hz"] <= p.freq_hz <= SAFE_LIMITS["freq_max_hz"])
            ctl.report(sim.apply(p.freq_hz, p.duty, p.burst_ms))
        self.assertLess(sim.dust_score(), start)

    def test_no_numbers_without_measured_sweep(self):
        self.assertIsNone(recommend_pattern("glass", 12.0)["candidate_pattern"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
