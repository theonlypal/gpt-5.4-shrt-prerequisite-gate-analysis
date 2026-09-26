#!/usr/bin/env python3
"""Frozen four-cell analysis. Reads independent classifications, never calls an API."""
import argparse
import csv
import json
import math
from collections import Counter
from pathlib import Path

import numpy as np
from scipy.optimize import brentq, minimize
from scipy.special import expit
from scipy.stats import chi2, fisher_exact, norm

CELLS = ("A", "B", "C", "D")
CLASSES = ("T1", "T0", "HE", "AR", "MX", "OT", "V0", "V1", "NV", "REFUSAL", "SAFETY", "TOOL", "ERROR")
N_PER_CELL = 200
INTEGRITY_COUNTERS = ("classification_disagreements", "hash_failures", "protocol_deviations", "model_substitutions", "schedule_deviations")
V0_SIGNS = np.array([-1., 1., 1., -1.])
T1_SIGNS = -V0_SIGNS
CI_METHOD = "signed sum of Bonferroni-Wilson 98.75% cell intervals; nominal simultaneous 95%"
INTERPRETATIONS = {
    "SUPPORTED": "A named linguistic prerequisite, under an explicit natural-language binding rule, causally controls observable continuation state in this frozen GPT-5.4 construction.",
    "NOT SUPPORTED": "The complete, protocol-valid experiment did not meet the preregistered primary interaction criterion.",
    "INCONCLUSIVE": "Incomplete evaluation, missing evidence, or protocol/integrity failure prevents the preregistered primary decision."
}


def wilson_interval(successes, n, alpha=0.05):
    if not (0 <= successes <= n) or n < 0 or not 0 < alpha < 1:
        raise ValueError("invalid binomial counts or alpha")
    if n == 0:
        return [None, None]
    z = float(norm.ppf(1 - alpha / 2))
    p = successes / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    radius = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return [max(0.0, center - radius), min(1.0, center + radius)]


def interaction_estimate(successes, ns, signs):
    y = np.asarray(successes, dtype=float)
    n = np.asarray(ns, dtype=float)
    signs = np.asarray(signs, dtype=float)
    if y.shape != (4,) or n.shape != (4,) or signs.shape != (4,):
        raise ValueError("four cells required in A,B,C,D order")
    if np.any(n <= 0) or np.any(y < 0) or np.any(y > n):
        raise ValueError("nonempty cells and valid counts required")
    p = y / n
    intervals = [wilson_interval(int(a), int(b), alpha=0.05 / 4) for a, b in zip(y, n)]
    low = sum(sign * interval[0 if sign > 0 else 1] for sign, interval in zip(signs, intervals))
    high = sum(sign * interval[1 if sign > 0 else 0] for sign, interval in zip(signs, intervals))
    return {
        "cell_counts": dict(zip(CELLS, map(int, y))),
        "cell_n": dict(zip(CELLS, map(int, n))),
        "cell_proportions": dict(zip(CELLS, map(float, p))),
        "delta_rule": float(np.dot(signs[:2], p[:2])),
        "delta_no_rule": float(-np.dot(signs[2:], p[2:])),
        "interaction": float(np.dot(signs, p)),
        "ci95": [float(max(-2, low)), float(min(2, high))],
        "ci_method": CI_METHOD,
        "cell_intervals_used": dict(zip(CELLS, intervals)),
    }


def penalized_loglik(eta, successes, ns):
    """Jeffreys-penalized saturated binomial likelihood, parameter constants omitted.

    Four unique full-rank rows make det(X'WX)=det(X)^2*product(w_cell).
    Thus l* = sum[(y+.5)eta - (n+1)log(1+exp(eta))] + constant.
    The SAME full-model penalty is retained for every constrained profile fit.
    """
    eta = np.asarray(eta, dtype=float)
    y = np.asarray(successes, dtype=float)
    n = np.asarray(ns, dtype=float)
    return float(np.sum((y + 0.5) * eta - (n + 1) * np.logaddexp(0, eta)))


def profile_penalized_loglik(coefficient, successes, ns):
    """Maximize l* with eta_B-eta_A+eta_C-eta_D fixed to coefficient."""
    y = np.asarray(successes, dtype=float)
    n = np.asarray(ns, dtype=float)
    full_eta = np.log((y + .5) / (n - y + .5))
    # Free parameters are eta_A, eta_C, eta_D. eta_B = b3+eta_A-eta_C+eta_D.
    transform = np.array([[1., 0., 0.], [1., -1., 1.], [0., 1., 0.], [0., 0., 1.]])
    offset = np.array([0., float(coefficient), 0., 0.])

    def objective(free):
        eta = transform @ free + offset
        return -penalized_loglik(eta, y, n)

    def gradient(free):
        eta = transform @ free + offset
        return transform.T @ ((n + 1) * expit(eta) - (y + .5))

    # Orthogonally project the unrestricted optimum onto the constraint as a start.
    projected = full_eta + V0_SIGNS * (coefficient - np.dot(V0_SIGNS, full_eta)) / 4
    start = projected[[0, 2, 3]]
    fit = minimize(objective, start, jac=gradient, method="BFGS", options={"gtol": 1e-10, "maxiter": 500})
    free = fit.x.copy()
    # Refine the same strictly convex objective analytically when line-search
    # precision stalls near its optimum. No model or penalty is changed.
    for _ in range(12):
        score = gradient(free)
        if np.max(np.abs(score)) <= 1e-9:
            break
        probability = expit(transform @ free + offset)
        weights = (n + 1) * probability * (1 - probability)
        hessian = transform.T @ (weights[:, None] * transform)
        step = np.linalg.solve(hessian, score)
        scale = 1.0
        current = objective(free)
        for _ in range(30):
            candidate = free - scale * step
            if objective(candidate) <= current + 1e-10:
                free = candidate
                break
            scale *= .5
        else:
            break
    score_norm = float(np.max(np.abs(gradient(free))))
    # BFGS can report precision loss at a valid optimum; the score is authoritative.
    if not math.isfinite(float(objective(free))) or score_norm > 1e-6:
        raise ArithmeticError("Firth profile did not converge: score_inf=%r; %s" % (score_norm, fit.message))
    eta = transform @ free + offset
    if abs(float(np.dot(V0_SIGNS, eta)) - coefficient) > 1e-8:
        raise ArithmeticError("Firth profile constraint mismatch")
    return -float(objective(free))


def firth_interaction(successes, ns, alpha=0.05):
    y = np.asarray(successes, dtype=float)
    n = np.asarray(ns, dtype=float)
    if y.shape != (4,) or n.shape != (4,) or np.any(n <= 0) or np.any(y < 0) or np.any(y > n):
        raise ValueError("four valid nonempty cells required")
    p = (y + .5) / (n + 1)
    eta = np.log(p / (1 - p))
    estimate = float(np.dot(V0_SIGNS, eta))
    maximum = penalized_loglik(eta, y, n)
    threshold = float(chi2.ppf(1 - alpha, 1))

    def lr_at(value):
        return max(0.0, 2 * (maximum - profile_penalized_loglik(value, y, n)))

    def endpoint(direction):
        distance = 1.0
        for _ in range(12):
            edge = estimate + direction * distance
            if lr_at(edge) >= threshold:
                return float(brentq(lambda v: lr_at(v) - threshold, min(edge, estimate), max(edge, estimate), xtol=1e-8))
            distance *= 2
        raise ArithmeticError("Firth profile confidence limit was not bracketed")

    interval = [endpoint(-1), endpoint(1)]
    lr = lr_at(0.)
    return {
        "model": "V0 ~ rule_present + mismatch + rule_present:mismatch",
        "coefficient": estimate,
        "se": float(np.sqrt(np.sum(1 / (n * p * (1 - p))))),
        "se_method": "ordinary binomial Fisher information evaluated at Firth estimate; profile CI is authoritative",
        "profile_ci95": interval,
        "penalized_lr": lr,
        "df": 1,
        "p_two_sided": float(chi2.sf(lr, 1)),
        "fitted_cell_probabilities": dict(zip(CELLS, map(float, p))),
        "converged": True,
        "method": "Firth saturated 2x2 Jeffreys penalty; profile retains the full-model penalty; chi-square(1) calibration",
    }


def holm_adjust(pvalues):
    p = np.asarray(pvalues, dtype=float)
    if np.any(~np.isfinite(p)) or np.any(p < 0) or np.any(p > 1):
        raise ValueError("p values must be finite probabilities")
    order = np.argsort(p, kind="stable")
    result = np.zeros(len(p))
    running = 0.
    for rank, index in enumerate(order):
        running = max(running, (len(p) - rank) * p[index])
        result[index] = min(1., running)
    return list(map(float, result))


def pairwise_tests(counts, totals):
    comparisons = (("V0", "A", "B"), ("V0", "C", "D"), ("V0", "B", "D"), ("T1", "A", "B"), ("T1", "A", "C"))
    records = []
    for outcome, first, second in comparisons:
        a, b = counts[first][outcome], counts[second][outcome]
        table = [[a, totals[first] - a], [b, totals[second] - b]]
        statistic, pvalue = fisher_exact(table, alternative="two-sided")
        records.append({"outcome": outcome, "comparison": first + "_vs_" + second, "table": table,
                        "odds_ratio": float(statistic) if math.isfinite(statistic) else None,
                        "odds_ratio_nonfinite": None if math.isfinite(statistic) else str(statistic),
                        "p_raw": float(pvalue), "alternative": "two-sided"})
    for record, adjusted in zip(records, holm_adjust([r["p_raw"] for r in records])):
        record["p_holm_secondary_family5"] = adjusted
    return {"family": "all five secondary pairwise comparisons", "adjustment": "Holm", "tests": records}


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def counters_from_report(report):
    counters = report.get("counts", {})
    result = {}
    for key in INTEGRITY_COUNTERS:
        value = report.get(key, counters.get(key))
        result[key] = len(value) if isinstance(value, list) else value
    return result


def decision_for(totals, counts, integrity_pass, primary, firth, statistical_error=None):
    if not integrity_pass or any(totals[c] != N_PER_CELL for c in CELLS) or any(counts[c]["ERROR"] for c in CELLS) or statistical_error:
        return "INCONCLUSIVE"
    if primary["interaction"] > 0 and firth["coefficient"] > 0 and firth["profile_ci95"][0] > 0:
        return "SUPPORTED"
    return "NOT SUPPORTED"


def analyze(root):
    root = Path(root).resolve()
    output = root / "results"
    verifier = load_json(output / "verifier_report.json")
    integrity = load_json(output / "protocol_integrity.json")
    manifest = load_json(root / "PRE_RUN_MANIFEST.json")
    with (output / "classification.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    counts = {cell: Counter() for cell in CELLS}
    issues = []
    slots = []
    for row in rows:
        cell, klass = row["cell"], row["class"]
        if cell not in CELLS or klass not in CLASSES:
            issues.append("invalid cell/class: " + repr((cell, klass)))
            continue
        slots.append(row["slot_id"])
        counts[cell][klass] += 1
    if len(set(slots)) != len(slots):
        issues.append("duplicate classification slot_id")
    totals = {cell: sum(counts[cell].values()) for cell in CELLS}
    counters = counters_from_report(verifier)
    integrity_counters = counters_from_report(integrity)
    for key in INTEGRITY_COUNTERS:
        available = [v for v in (counters[key], integrity_counters[key]) if v is not None]
        counters[key] = max(available) if available else None
    integrity_pass = (verifier.get("status") == "PASS" and integrity.get("status") == "PASS"
                      and all(counters[k] == 0 for k in INTEGRITY_COUNTERS) and not issues)
    summaries = []
    for cell in CELLS:
        for klass in CLASSES:
            n, k = totals[cell], counts[cell][klass]
            low, high = wilson_interval(k, n)
            summaries.append({"cell": cell, "class": klass, "count": k, "n": n, "expected_n": N_PER_CELL,
                              "proportion": k / n if n else None, "wilson95_low": low, "wilson95_high": high})
    with (output / "cell_summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summaries[0]))
        writer.writeheader()
        writer.writerows(summaries)
    interactions = {"primary_V0": None, "secondary_T1": None, "firth_primary": None, "statistical_error": None}
    tests = {"family": "all five secondary pairwise comparisons", "adjustment": "Holm", "tests": []}
    if all(totals[c] > 0 for c in CELLS):
        ns = [totals[c] for c in CELLS]
        interactions["primary_V0"] = interaction_estimate([counts[c]["V0"] for c in CELLS], ns, V0_SIGNS)
        interactions["secondary_T1"] = interaction_estimate([counts[c]["T1"] for c in CELLS], ns, T1_SIGNS)
        tests = pairwise_tests(counts, totals)
        try:
            interactions["firth_primary"] = firth_interaction([counts[c]["V0"] for c in CELLS], ns)
        except (ArithmeticError, ValueError, FloatingPointError) as exc:
            interactions["statistical_error"] = str(exc)
    else:
        interactions["statistical_error"] = "one or more cells have no recorded outcomes"
    decision = decision_for(totals, counts, integrity_pass, interactions["primary_V0"], interactions["firth_primary"], interactions["statistical_error"])
    returned = verifier.get("returned_models", integrity.get("returned_models", []))
    result = {
        "title": "Rule-Dependent Prerequisite Gating of Continuation in GPT-5.4",
        "requested_model": "gpt-5.4-2026-03-05", "returned_models": returned,
        "decision": decision, "interpretation": INTERPRETATIONS[decision],
        "metadata": manifest, "expected_per_cell": N_PER_CELL, "recorded_per_cell": totals,
        "definitive_model_outcomes_per_cell": {c: totals[c] - counts[c]["ERROR"] for c in CELLS},
        "classification_counts": {c: {k: counts[c][k] for k in CLASSES} for c in CELLS},
        "integrity_pass": integrity_pass, "integrity_counts": counters,
        "analysis_input_issues": issues, "interactions": interactions, "statistical_tests": tests,
        "denominator_rule": "All recorded terminal slots retained, including ERROR. Expected denominator is 200 per cell; incomplete data cannot support a confirmatory conclusion."
    }
    write_json(output / "interaction_analysis.json", interactions)
    write_json(output / "statistical_tests.json", tests)
    write_json(output / "RESULTS.json", result)
    (output / "RESULTS.md").write_text(render_markdown(result), encoding="utf-8")
    return result


def display(value):
    if value is None:
        return "not estimable"
    if isinstance(value, float):
        return "%.10g" % value
    if isinstance(value, list):
        return "[" + ", ".join(display(v) for v in value) + "]"
    return str(value)


def render_markdown(result):
    meta = result["metadata"]
    lines = ["# " + result["title"], "", "## Frozen model", "", "Requested: `" + result["requested_model"] + "`", "",
             "Returned model value(s): " + display(result["returned_models"]), "", "## Protocol", ""]
    labels = (("Runner", "runner_repository_url"), ("Frozen runner commit", "runner_frozen_commit"), ("Frozen runner tag", "runner_frozen_tag"),
              ("Analysis preregistration", "analysis_repository_url"), ("Preregistered analysis commit", "analysis_preregistered_commit"), ("Schedule SHA-256", "schedule_sha256"))
    for label, key in labels:
        lines.extend([label + ": `" + str(meta.get(key, "MISSING")) + "`", ""])
    lines.extend(["## Execution", ""])
    for cell in CELLS:
        lines.append("%s: %d/200 definitive model outcomes; %d recorded terminal slots" % (cell, result["definitive_model_outcomes_per_cell"][cell], result["recorded_per_cell"][cell]))
    headings = {"A": "RULE + شَرْط", "B": "RULE + شَمْس", "C": "NO RULE + شَرْط", "D": "NO RULE + شَمْس"}
    for cell in CELLS:
        lines.extend(["", "## " + cell + " — " + headings[cell], "", "| Class | Count / scheduled |", "| --- | ---: |"])
        for klass in CLASSES:
            lines.append("| %s | %d/200 |" % (klass, result["classification_counts"][cell][klass]))
    primary = result["interactions"]["primary_V0"] or {}
    secondary = result["interactions"]["secondary_T1"] or {}
    firth = result["interactions"]["firth_primary"] or {}
    lines.extend(["", "## Primary V0 interaction", ""])
    for cell in CELLS:
        lines.append("P(V0|%s) = %s" % (cell, display(primary.get("cell_proportions", {}).get(cell))))
    for label, value in (("ΔS1", primary.get("delta_rule")), ("ΔS0", primary.get("delta_no_rule")), ("I_V0", primary.get("interaction")),
                         ("95% CI", primary.get("ci95")), ("Firth rule×mismatch coefficient", firth.get("coefficient")),
                         ("Firth profile 95% CI", firth.get("profile_ci95")), ("Penalized likelihood-ratio statistic (df=1)", firth.get("penalized_lr")), ("p", firth.get("p_two_sided"))):
        lines.extend(["", label + " = " + display(value)])
    lines.extend(["", "Risk-difference CI: " + CI_METHOD + ".", "", "## Secondary T1 interaction", ""])
    for cell in CELLS:
        lines.append("P(T1|%s) = %s" % (cell, display(secondary.get("cell_proportions", {}).get(cell))))
    lines.extend(["", "I_T1 = " + display(secondary.get("interaction")), "", "95% CI = " + display(secondary.get("ci95")), "", "## Independent verifier", ""])
    for key in INTEGRITY_COUNTERS:
        lines.append(key.replace("_", " ") + " = " + display(result["integrity_counts"][key]))
    if result["interactions"]["statistical_error"]:
        lines.extend(["", "Statistical status: " + result["interactions"]["statistical_error"]])
    lines.extend(["", "## RESULT", "", result["decision"], "", result["interpretation"], ""])
    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    print(analyze(args.root)["decision"])
