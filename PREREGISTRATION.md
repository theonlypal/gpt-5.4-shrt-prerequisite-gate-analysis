# Rule-Dependent Prerequisite Gating of Continuation in GPT-5.4

Author: Sharthok Rayan Pal. Confirmatory Protocol v2. The runner and this analysis are frozen publicly before the first primary request. The separate earlier pilot is not pooled.

## Design

Exact snapshot `gpt-5.4-2026-03-05`, Chat Completions, `max_completion_tokens=32768`, `reasoning_effort=none`, `stream=false`. Temperature, top-p, tools, response format, and history are absent. Each of 800 fresh requests follows the immutable shuffled schedule, 200 per cell.

| Cell | Rule | User input |
| --- | --- | --- |
| A | Present | `شَرْط` |
| B | Present | `شَمْس` |
| C | Absent | `شَرْط` |
| D | Absent | `شَمْس` |

The exact prompt bytes, targets, request construction, retry policy, and classifier are fixed in the frozen runner. No completed model response is retried. All attempts remain in the evidence.

## Outcomes and estimates

Primary: normal-stop zero-byte class V0. `I_V0=(p_B-p_A)-(p_D-p_C)`, predicted positive. V0 requires a successful response with present string content of exactly zero UTF-8 bytes, `finish_reason=stop`, and no refusal, safety block, or tool call.

Secondary: exact byte target `شָׁרְט` (T1). `I_T1=(p_A-p_B)-(p_C-p_D)`, predicted positive. This endpoint does not determine primary support.

Report all 13 mutually exclusive classes, counts, proportions, and Wilson 95% intervals in every cell. Each interaction receives a nominal 95% interval formed from the signed sum of four Bonferroni-Wilson 98.75% cell intervals. This conservative construction is approximate, not exact finite-sample coverage. All scheduled slots remain represented; no exclusions or imputation.

## Separation-safe interaction

Fit `V0 ~ rule_present + mismatch + rule_present:mismatch` with the Firth penalty `0.5 log|X'WX|`. For this saturated full-rank four-cell design, the penalized likelihood equals `sum[(y+0.5)eta-(n+1)log(1+exp(eta))]` plus a parameter-independent constant. The unrestricted fitted cell proportions are `(y+0.5)/(n+1)`.

The interaction is `eta_B-eta_A+eta_C-eta_D`. Profile it by maximizing the same full-model penalized likelihood over the other three logits at each fixed interaction value. Do not replace the penalty with that of a reduced model. The 95% profile interval and two-sided penalized likelihood-ratio test use chi-square(1) calibration. The profile interval, not a Wald interval, governs the primary decision. Complete separation, null effects, reversed effects, and independent full-matrix likelihood equivalence are tested before freezing.

Five two-sided Fisher exact tests are secondary: V0 A/B, C/D, B/D; T1 A/B, A/C. Report raw p values and Holm adjustment over these five only.

## Decision

SUPPORTED: all 800 model outcomes complete, protocol and independent-verifier integrity pass, no substitutions or mutations, `I_V0>0`, and the Firth interaction's profile 95% lower bound is above zero.

NOT SUPPORTED: complete, intact experiment without the primary criterion.

INCONCLUSIVE: incomplete evaluation, missing evidence, protocol/integrity failure, or failure to compute the frozen primary analysis. Raw tables remain available. An unfavorable valid result is never relabeled inconclusive.

The independent verifier reconstructs raw classifications without importing runner code. `analysis_plan.json` and `analysis.py` fix the complete numerical procedure. Statistical interpretation assumes independent fresh trials; repeated calls do not establish deployment-wide universality. The identified effect concerns this linguistic construction, not an identified internal circuit or meaning-versus-string generalization.

Method references: [Firth (1993)](https://doi.org/10.1093/biomet/80.1.27), [logistf profile-likelihood documentation](https://search.r-project.org/CRAN/refmans/logistf/html/logistf-package.html).
