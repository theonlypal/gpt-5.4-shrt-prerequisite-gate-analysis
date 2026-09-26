# Rule-Dependent Prerequisite Gating of Continuation in GPT-5.4

## Frozen model

Requested: `gpt-5.4-2026-03-05`

Returned model value(s): [gpt-5.4-2026-03-05]

## Protocol

Runner: `https://github.com/theonlypal/gpt-5.4-shrt-prerequisite-gate-runner`

Frozen runner commit: `2c37c2021bc4085430ec1ab9e09c9c904e3bbd46`

Frozen runner tag: `v2.0.0-confirmatory-frozen`

Analysis preregistration: `https://github.com/theonlypal/gpt-5.4-shrt-prerequisite-gate-analysis`

Preregistered analysis commit: `da0a5ac4c8cd46ccea0e16a2580be81aa21fee07`

Schedule SHA-256: `7ca978e064ea071fc81c74ff7ff33846faaa5f76aa18b6e1d480df03197c33b4`

## Execution

A: 200/200 definitive model outcomes; 200 recorded terminal slots
B: 200/200 definitive model outcomes; 200 recorded terminal slots
C: 200/200 definitive model outcomes; 200 recorded terminal slots
D: 200/200 definitive model outcomes; 200 recorded terminal slots

## A — RULE + شَرْط

| Class | Count / scheduled |
| --- | ---: |
| T1 | 185/200 |
| T0 | 0/200 |
| HE | 10/200 |
| AR | 3/200 |
| MX | 0/200 |
| OT | 2/200 |
| V0 | 0/200 |
| V1 | 0/200 |
| NV | 0/200 |
| REFUSAL | 0/200 |
| SAFETY | 0/200 |
| TOOL | 0/200 |
| ERROR | 0/200 |

## B — RULE + شَمْس

| Class | Count / scheduled |
| --- | ---: |
| T1 | 0/200 |
| T0 | 0/200 |
| HE | 0/200 |
| AR | 0/200 |
| MX | 0/200 |
| OT | 0/200 |
| V0 | 200/200 |
| V1 | 0/200 |
| NV | 0/200 |
| REFUSAL | 0/200 |
| SAFETY | 0/200 |
| TOOL | 0/200 |
| ERROR | 0/200 |

## C — NO RULE + شَرْط

| Class | Count / scheduled |
| --- | ---: |
| T1 | 0/200 |
| T0 | 0/200 |
| HE | 1/200 |
| AR | 150/200 |
| MX | 1/200 |
| OT | 48/200 |
| V0 | 0/200 |
| V1 | 0/200 |
| NV | 0/200 |
| REFUSAL | 0/200 |
| SAFETY | 0/200 |
| TOOL | 0/200 |
| ERROR | 0/200 |

## D — NO RULE + شَمْس

| Class | Count / scheduled |
| --- | ---: |
| T1 | 1/200 |
| T0 | 0/200 |
| HE | 1/200 |
| AR | 0/200 |
| MX | 9/200 |
| OT | 189/200 |
| V0 | 0/200 |
| V1 | 0/200 |
| NV | 0/200 |
| REFUSAL | 0/200 |
| SAFETY | 0/200 |
| TOOL | 0/200 |
| ERROR | 0/200 |

## Primary V0 interaction

P(V0|A) = 0
P(V0|B) = 1
P(V0|C) = 0
P(V0|D) = 0

ΔS1 = 1

ΔS0 = -0

I_V0 = 1

95% CI = [0.9092526616, 1.030249113]

Firth rule×mismatch coefficient = 11.98792285

Firth profile 95% CI = [6.00261301, 18.83833846]

Penalized likelihood-ratio statistic (df=1) = 9.82410041

p = 0.001722399228

Risk-difference CI: signed sum of Bonferroni-Wilson 98.75% cell intervals; nominal simultaneous 95%.

## Secondary T1 interaction

P(T1|A) = 0.925
P(T1|B) = 0
P(T1|C) = 0
P(T1|D) = 0.005

I_T1 = 0.93

95% CI = [0.8046828507, 0.9990537995]

## Independent verifier

classification disagreements = 0
hash failures = 0
protocol deviations = 0
model substitutions = 0
schedule deviations = 0

## RESULT

SUPPORTED

A named linguistic prerequisite, under an explicit natural-language binding rule, causally controls observable continuation state in this frozen GPT-5.4 construction.
