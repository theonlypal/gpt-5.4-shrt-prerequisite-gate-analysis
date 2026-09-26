import math
import csv
import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path

import numpy as np
from scipy.special import expit
from scipy.stats import chi2

from analysis import (CELLS, INTEGRITY_COUNTERS, V0_SIGNS, T1_SIGNS, analyze, decision_for, firth_interaction,
                      holm_adjust, interaction_estimate, penalized_loglik,
                      profile_penalized_loglik, wilson_interval)


class StatisticsTests(unittest.TestCase):
    def test_wilson_bounds(self):
        low, high = wilson_interval(0, 200)
        self.assertAlmostEqual(low, 0)
        self.assertAlmostEqual(high, 0.01884532637726658)
        positive = wilson_interval(200, 200)
        self.assertAlmostEqual(positive[0], 1 - high)
        self.assertEqual(wilson_interval(0, 0), [None, None])

    def test_interaction_signs_and_bounds(self):
        result = interaction_estimate([0, 200, 0, 0], [200] * 4, V0_SIGNS)
        self.assertEqual(result["interaction"], 1)
        self.assertGreater(result["ci95"][0], 0)
        self.assertLessEqual(result["ci95"][0], 1)
        self.assertGreaterEqual(result["ci95"][1], 1)
        secondary = interaction_estimate([200, 0, 0, 0], [200] * 4, T1_SIGNS)
        self.assertEqual(secondary["interaction"], 1)

    def test_holm_all_five(self):
        expected = [0.005, 0.04, 0.09, 0.4, 0.4]
        for a, b in zip(holm_adjust([.001, .01, .03, .2, .4]), expected):
            self.assertAlmostEqual(a, b)
        reversed_order = holm_adjust([.4, .2, .03, .01, .001])
        for a, b in zip(reversed_order, reversed(expected)):
            self.assertAlmostEqual(a, b)

    def test_full_matrix_jeffreys_identity(self):
        # Independent determinant calculation, not the analytic shortcut.
        x = np.array([[1, 1, 0, 0], [1, 1, 1, 1], [1, 0, 0, 0], [1, 0, 1, 0.]])
        n = np.array([170, 180, 190, 200.])
        y = np.array([20, 125, 2, 0.])
        differences = []
        for beta in ([.1, .2, -.3, 1.], [-3, 2, 1, -2], [4, -3, 5, -6]):
            eta = x @ np.array(beta)
            p = expit(eta)
            info = x.T @ np.diag(n * p * (1 - p)) @ x
            sign, logdet = np.linalg.slogdet(info)
            self.assertEqual(sign, 1)
            direct = np.sum(y * eta - n * np.logaddexp(0, eta)) + .5 * logdet
            differences.append(direct - penalized_loglik(eta, y, n))
        self.assertTrue(np.allclose(differences, differences[0], atol=1e-8))

    def test_profile_endpoints_are_likelihood_cutoff(self):
        y, n = [2, 150, 3, 10], [200] * 4
        fitted = firth_interaction(y, n)
        eta = np.log((np.array(y) + .5) / (np.array(n) - np.array(y) + .5))
        maximum = penalized_loglik(eta, y, n)
        for endpoint in fitted["profile_ci95"]:
            lr = 2 * (maximum - profile_penalized_loglik(endpoint, y, n))
            self.assertAlmostEqual(lr, chi2.ppf(.95, 1), places=5)

    def test_decision_keeps_integrity_and_direction_separate(self):
        totals = dict.fromkeys(CELLS, 200)
        counts = {c: Counter() for c in CELLS}
        primary = {"interaction": 1.}
        firth = {"coefficient": 3., "profile_ci95": [1., 5.]}
        self.assertEqual(decision_for(totals, counts, True, primary, firth), "SUPPORTED")
        self.assertEqual(decision_for(totals, counts, False, primary, firth), "INCONCLUSIVE")
        self.assertEqual(decision_for(totals, counts, True, {"interaction": -1}, firth), "NOT SUPPORTED")
        counts["B"]["ERROR"] = 1
        self.assertEqual(decision_for(totals, counts, True, primary, firth), "INCONCLUSIVE")

    def test_complete_synthetic_pipeline_and_integrity_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            results = root / "results"
            results.mkdir()
            report = {"status": "PASS", "returned_models": ["gpt-5.4-2026-03-05"]}
            report.update({k: [] for k in INTEGRITY_COUNTERS})
            for name in ("verifier_report.json", "protocol_integrity.json"):
                (results / name).write_text(json.dumps(report), encoding="utf-8")
            (root / "PRE_RUN_MANIFEST.json").write_text(json.dumps({"runner_frozen_commit": "SYNTHETIC", "analysis_preregistered_commit": "SYNTHETIC"}), encoding="utf-8")
            with (results / "classification.csv").open("w", newline="", encoding="utf-8") as handle:
                fields = ["slot_id", "cell", "class", "rule_present", "prerequisite_matched", "attempt_number", "definitive_path"]
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                for cell in CELLS:
                    for index in range(200):
                        writer.writerow({"slot_id": "%s-%03d" % (cell, index), "cell": cell,
                                         "class": "V0" if cell == "B" else "T1" if cell == "A" else "OT",
                                         "rule_present": int(cell in "AB"), "prerequisite_matched": int(cell in "AC"),
                                         "attempt_number": 1, "definitive_path": "SYNTHETIC"})
            result = analyze(root)
            self.assertEqual(result["decision"], "SUPPORTED")
            self.assertEqual(result["classification_counts"]["B"]["V0"], 200)
            self.assertEqual(result["integrity_counts"], dict.fromkeys(INTEGRITY_COUNTERS, 0))
            with (results / "cell_summary.csv").open(encoding="utf-8") as handle:
                self.assertEqual(len(list(csv.DictReader(handle))), 52)
            for filename in ("RESULTS.json", "interaction_analysis.json", "statistical_tests.json"):
                json.loads((results / filename).read_text(encoding="utf-8"))
            self.assertTrue((results / "RESULTS.md").read_text(encoding="utf-8").startswith("# Rule-Dependent"))
            report["status"] = "FAIL"
            report["hash_failures"] = ["SYNTHETIC deliberate mutation"]
            (results / "protocol_integrity.json").write_text(json.dumps(report), encoding="utf-8")
            self.assertEqual(analyze(root)["decision"], "INCONCLUSIVE")


if __name__ == "__main__":
    unittest.main()
