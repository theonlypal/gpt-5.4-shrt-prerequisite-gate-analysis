# GPT-5.4 prerequisite gate: evidence and analysis

Preregistered four-cell, 800-trial experiment on `gpt-5.4-2026-03-05`. [Frozen runner](https://github.com/theonlypal/gpt-5.4-shrt-prerequisite-gate-runner). [Analysis plan](analysis_plan.json).

**Result: SUPPORTED.** 800/800 definitive outcomes; independent verifier PASS.

| Cell | V0 / 200 | Exact T1 / 200 |
| --- | ---: | ---: |
| A: rule + شَرْط | 0 | 185 |
| B: rule + شَمْس | 200 | 0 |
| C: no rule + شَرْط | 0 | 0 |
| D: no rule + شَمْس | 0 | 1 |

[Full result](results/RESULTS.md) · [Machine-readable result](results/RESULTS.json) · [Raw evidence](raw/) · [Verifier](results/verifier_report.json) · [Results ZIP and checksum](https://github.com/theonlypal/gpt-5.4-shrt-prerequisite-gate-analysis/releases/tag/v1.0.0-confirmatory-results)

Clone the runner beside this repository under its original repository name. The verifier checks both frozen Git histories.

```bash
python3 -m pip install -r requirements.txt
python3 -m pytest -q
python3 -B independent_verifier.py --root .
python3 -B analysis.py --root .
```

Verification and analysis use saved evidence and require no API key. Raw request/response bodies are retained under `raw/`. `PRE_RUN_MANIFEST.json` identifies the publicly frozen code and schedule.
