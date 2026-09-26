import math
import unittest

from analysis import firth_interaction


class CompleteSeparationTests(unittest.TestCase):
    def test_predicted_complete_separation(self):
        result = firth_interaction([0, 200, 0, 0], [200] * 4)
        self.assertTrue(result["converged"])
        self.assertTrue(all(math.isfinite(v) for v in result["profile_ci95"]))
        self.assertGreater(result["profile_ci95"][0], 0)
        self.assertGreater(result["coefficient"], 0)
        self.assertLess(result["p_two_sided"], .05)

    def test_sign_reversal(self):
        forward = firth_interaction([0, 200, 0, 0], [200] * 4)
        reverse = firth_interaction([200, 0, 0, 0], [200] * 4)
        self.assertAlmostEqual(forward["coefficient"], -reverse["coefficient"], places=8)
        self.assertAlmostEqual(forward["profile_ci95"][0], -reverse["profile_ci95"][1], places=5)
        self.assertAlmostEqual(forward["profile_ci95"][1], -reverse["profile_ci95"][0], places=5)
        self.assertAlmostEqual(forward["p_two_sided"], reverse["p_two_sided"], places=8)

    def test_null_effect_at_all_zero_all_one_and_half(self):
        for y in ([0] * 4, [200] * 4, [100] * 4, [20, 20, 100, 100]):
            result = firth_interaction(y, [200] * 4)
            self.assertAlmostEqual(result["coefficient"], 0, places=8)
            self.assertLess(result["profile_ci95"][0], 0)
            self.assertGreater(result["profile_ci95"][1], 0)
            self.assertAlmostEqual(result["p_two_sided"], 1, places=5)

    def test_maximal_checkerboard_separation(self):
        result = firth_interaction([0, 200, 200, 0], [200] * 4)
        self.assertTrue(all(math.isfinite(v) for v in result["profile_ci95"]))
        self.assertGreater(result["profile_ci95"][0], 0)


if __name__ == "__main__":
    unittest.main()
