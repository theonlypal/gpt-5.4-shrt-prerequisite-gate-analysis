# GPT-5.4 prerequisite gate: evidence and analysis

Preregistered four-cell, 800-trial experiment on `gpt-5.4-2026-03-05`. [Frozen runner](https://github.com/theonlypal/gpt-5.4-shrt-prerequisite-gate-runner). [Analysis plan](analysis_plan.json).

Clone the runner beside this repository under its original repository name. The verifier checks both frozen Git histories.

```bash
python3 -m pip install -r requirements.txt
python3 -m pytest -q
python3 -B independent_verifier.py --root .
python3 -B analysis.py --root .
```

Verification and analysis use saved evidence and require no API key. Raw request/response bodies are retained under `raw/`. `PRE_RUN_MANIFEST.json` identifies the publicly frozen code and schedule.
