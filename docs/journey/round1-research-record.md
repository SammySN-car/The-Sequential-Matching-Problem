# Round 1 Research Record — FROZEN HISTORICAL EXPERIMENT

**Status:** Round 1 COMPLETE and FROZEN (artifact `policy.py=379cc2d9…ddb47c`, `policy_ac.py=90fb9ad3…fa56a97`).
**Purpose:** durable reconstruction source for the final hackathon report, usable without chat history.
**Separation rule:** Round 1 = this record + the files it indexes. Historical numbers here must never be rewritten.
Round 2 findings belong in separate Round 2 files and must not overwrite this record.

**Tags used below:** [OBS] observed result · [HYP] hypothesis · [INT] interpretation · [DEC] decision/ruling · [UNRES] unresolved

---

## 1. Primary sources (index)

| File | Contains |
|---|---|
| `docs/superpowers/specs/2026-10-06-a-plus-c-policy-design.md` | approved A+C design spec (tests T1-T14, constraints C1-C7, risks R1-R5, section 14 eval plan) |
| `docs/superpowers/plans/2026-10-06-a-plus-c-policy.md` | implementation plan (10 tasks, gates, pseudo-code; 2216 lines) |
| `docs/superpowers/round1-research-ledger-verbatim.md` | VERBATIM byte-identical copy of the research-phase ledger (source: `%TEMP%\opencode\smp-research-ledger.md`, ephemeral; copied 2026-10-07, SHA256 prefix 688301875B4962C4). Covers research pipeline Tasks 1-6, 440-rollout run, pre-registration for the scale-up, 3,520-rollout run, A+C design gate (amendments A1/A2), export/inference contract, plan amendment pass |
| `.superpowers/sdd/2026-10-06-a-plus-c-policy/progress.md` | implementation + evaluation ledger: all Task 1-10 entries, every ruling, gates G1-G3, latency, final results |
| `research/README.md` | pipeline description + 6 hard legality rules |
| `research/out/` (report.txt/json, rows.csv 10.7 MB, worlds.csv) | 440-rollout / 100-world experiment |
| `research/out_scale800/` (report.txt/json, rows.csv 86.7 MB, worlds.csv) | 3,520-rollout / 800-world experiment |
| `results/pre_eval_diagnostics.json` | pre-eval ranking + floor diagnostics (frozen-input) |
| `results/{greedy,no_asks,random,ac,ac_rerun,ac_container}.json` | Round 1 evaluation, 18 episodes each — FROZEN |
| `results/artifact.sha256`, `results/run_log.txt`, `results/_timing.json` | freeze hashes; eval commands/exit codes/wall times; single-episode timing record |
| `policy.py`, `policy_ac.py`, `test_policy.py` | frozen implementation + 64 root tests; research suite 63 tests (`research/test_pipeline.py`) |

## 2. Research phase

- [HYP] Primary research hypothesis: a supervised model can learn MSMI (mutual second-meeting intention) from rollout data on HELD-OUT worlds well enough to inform an A+C policy (informed asks + model-scored matching) that competes with greedy on the evaluation primary metric.
- [HYP] Secondary: asking clarifications (constraints before soft fields) increases the feasible candidate set enough to offset its cost.
- [OBS] Dataset sizes: experiment 1 = 440 rollouts (400 random / 40 greedy) across 100 worlds -> 32,044 labelled rows (`research/out/`). Experiment 2 = 800 worlds x (3,200 random + 320 greedy) = 3,520 rollouts, 60+40 days -> 259,696 rows (`research/out_scale800/rows.csv`, 86.7 MB); train 209,238 / val 50,458 rows.
- [OBS] 440-rollout result: integrity suite ALL PASS (rows audit 0, dataset audit 0, source audit clean, leakage clean, 0 immature coercions); stage signal (AP >= 1.3x prevalence) TRUE; MSMI signal (AUC >= 0.55 AND AP lift >= 1.10) FALSE at this scale -> pre-registered DECISION: **PROCEED WITH CHANGES** (MSMI too rare/weak at 32k rows; consider more rollouts / auxiliary targets). (`research/out/report.txt` F)
- [OBS] Pre-registration for scale-up recorded BEFORE launch in the verbatim ledger: gates MSMI_AUC_MIN=0.55, AP_LIFT_MSMI=1.10 (BOTH required) + 95% Hanley-McNeil CI decision rule (PASS if lift>=1.10 and CI-lo>=0.55; FAIL if CI-hi<0.55 or lift<1.10 with lo>=0.55; else INCONCLUSIVE); stop-on-failure integrity checks; NO tuning / NO feature or target changes / NO A+C implementation in that run.
- [OBS] 3,520-rollout result: all integrity checks pass (0 violations; split overlap 0 worlds/0 seeds; canonical ordering green) -> gates PASS: MSMI val AUC 0.5937, CI95 [0.5667, 0.6208], AP 0.0123 / prevalence 0.009414 -> lift 1.3037 -> DECISION **PROCEED** (report decision: PROCEED; ready to design A+C, with approval).
- [OBS] Model metrics on validation (hist_gb vs constant baseline), 800-world run:
  - MSMI: AUC 0.5937 [0.5667, 0.6208] vs 0.5000; AP 0.0123 (lift 1.30x); logloss 0.0541 vs 0.0533; brier 0.0095 vs 0.0093.
  - mutual: AUC 0.6131 [0.6058, 0.6205]; AP lift 1.40x; logloss 0.3966; brier 0.1188.
  - date: AUC 0.6064 [0.5982, 0.6146]; AP lift 1.36x; logloss 0.3406; brier 0.0971.
- [OBS] MSMI prevalence: val 475/50,458 = 0.0094 (0.94%); early probe 5/533 = 0.94% across 6 greedy seeds. Per-variant val prevalence: cold_start 0.0104, delayed 0.0093, development 0.0099, drift 0.0097, shift 0.0098, sparse 0.0116 (sparse has only 12,380 rows).
- [OBS] Split methodology: whole-world split on `(world_seed, variant)` — never row-level; split_seed=0, val_frac 0.2 -> 640 train / 160 val worlds (80/20 in run 1); measured split overlap 0.
- [OBS] Feature set: 44 symmetric decision-time pair features (`research/features.py`), NaN for unknowns, temporal masking (feedback observed_day > t dropped; fields field_observed_day > t masked), structure-informed features disclosed (weighted_soft_score, weighted_soft_covered). Top mutual predictors: soft_relationship_goal_match, weighted_soft_score, soft_relationship_pace_match, soft_match_count.
- [OBS] Feature parity (implementation): policy.py embeds the eval feature block verbatim (173 lines copied from features.py L17-L207 minus auditor/forbidden-token lines); FeatureParity tests (incl. day-45 masking, >=24 pairs), ResearchRowParity (stored rows == replay), SeedHygiene (research seeds 50000-50799 disjoint from eval 101/102/103) all green.
- [OBS] Integrity/leakage tests: forbidden-name audit clean; future-masking; only introduced pairs labelled (never store un-introduced as 0); `label None` never coerced; labels built post-episode from complete event record (horizon-stamped); static source audit for hidden member reads clean; determinism tests green. (research reports section E; research suite 63/63.)
- [OBS] Random vs greedy coverage: research collectors — run 1: random 0.5599 vs greedy 0.5523 (ratio 1.01x); run 2: random 0.5434 vs greedy 0.5366 (1.01x). Unit test pins random > greedy deterministically (seeds 9/3). Both are maximal-cardinality matchings, so the ~1x ratio is expected (coverage differences in eval come from ask/eligibility dynamics, not matching greediness).
- [OBS] Six variant findings (research): rows/positives per variant listed above; sparse is the thin variant (12,380 rows). Six variant findings (evaluation): see section 4 table.
- [OBS] Clarification-budget findings: kit daily ask budget = 12; costs 3 (constraints) / 1 (soft). Research rollouts: random collectors spent markedly more ask cost than greedy (sample rows ~273-444 vs ~150-246 per rollout; aggregate in worlds.csv). Evaluation: greedy/random mean ask_cost 206.7/episode, A+C 419.4/episode (2x), no_asks 0. Plan probe: ask-phase candidates = 111 on the day-50 replay. A+C ask design: tier1 blocked-flips (cost 3, only pairs provably flippable), tier1b fewest-missing (budget-idle mitigation), tier2 soft completion (cost 1); budget-capped, exception -> `[]`.
- [OBS] Calibration findings: quantile-bin calibration tables in both research reports (section D). MSMI hist_gb logloss/brier slightly WORSE than constant (0.0541/0.0095 vs 0.0533/0.0093): good ranking, imperfect calibration on the rare event; top bin over-predicts (0.0209 predicted vs 0.0138 observed).
- [DEC] Amendment A2 (design gate): the HistGB output is used as a **ranking/value score, not a calibrated probability** — no score-minus-prevalence thresholds; conservative wait = train-median rank floor. Amendment A1: train-split-only model (full-data refit deferred).
- [DEC] Export contract (user-approved): pure-python `_walk` must match sklearn `predict_proba` exactly (raw = baseline + sum of leaf values, no lr rescaling at inference); T12 hard gate atol=1e-9 (measured parity 2.78e-17).

## 3. A+C design decisions (approved spec)

- [DEC] Informed asks: tier ordering (blocked flips -> progressive completion -> soft), budget arithmetic 3/1/1, past-pair exclusion, deterministic ordering.
- [DEC] Matching: general-graph (single pool, single occupancy map), candidate filter available x feasible x NOT past BEFORE scoring, model score with floor gate (floor = 0.007905174015296758 from research), count-based candidate cap at >12,000 by `(-rule_score, a, b)` (never time-based), greedy seed + up to 8 strictly-improving local moves, sorted output; deterministic fallback to rule scorer only on genuine failure; outer failure -> `[]`.
- [DEC] Evaluation protocol: pre-registered section 14 — seeds 101/102/103 x 6 variants, 5 commands, G1 (validity) / G2 (determinism + local-container parity) / G3 (freeze + build) gates; private 120-episode holdout untouched by development.
- [DEC] `policy_ac.py` shim ignores `--baseline` (R5); container entry `python policy.py` with argparse default `ac`.
- [OBS] Implementation corrections discovered during planning/implementation (all ledgered in SDD progress.md): Task 1 toy fixture self-contradiction (fixture constants corrected); Task 2 `_walk` NaN branch inverted vs sklearn (fixed per plan Step 6 + toy m values swapped); Task 5 tier1 fixture unsatisfiable (added past intro to fixture); Task 7->8 sanctioned red (ask guard landed in Task 8); Task 10 S2 literal floor-gate trigger (see section 4); Task 10 git-status "exactly" expectation (results/ gitignored by pre-existing .gitignore:4; satisfied in intent, critical assert = empty infra diff).

## 4. Evaluation phase (Round 1, frozen)

- [OBS] Freeze: `results/artifact.sha256` = policy.py `379cc2d9519e8d3b9295f6c0bf2039e7a1a40d30729f6be0a9dfd17f6fddb47c`, policy_ac.py `90fb9ad306e89bfb3cc11d072c68de7ee3b1667e8709596979d04be41fa56a97`; "artifact unchanged: True" after all evals; default exporter mode never re-run (`--check` read-only: parity 2.77556e-17 <= 1e-9).
- [OBS] Docker: `sequential-policy:1.0` built post-freeze (python:3.12.7-slim, no sklearn, ENTRYPOINT `python policy.py`, read-only fs, --network=none, --cpus=2 --memory=1g).
- [OBS] Latency (hard limit 9 s / 10 s invoke): local day-50 match 0.10 s / ask 0.27 s; **container authoritative match 0.63 s / ask 0.70 s**; per-episode inference local 20.4 s vs container 68.2 s (mean; p99 77.6 s).
- [OBS] Determinism: seed-101 rerun 6/6 identical `action_sha256`; local vs container 18/18 identical.
- [OBS] Pre-eval diagnostics (frozen inputs): model AUC mean 0.600 vs rule proxy 0.499; above_floor_frac 0.5051 (25,484/50,458 stored research rows); `zero_above_floor_groups` 7,781/23,523 (33%) across all 6 variants.
- [DEC] Task 10 S2 gate ruling (human-approved): gate **satisfied in intent** — floor demonstrably passes (50.5% of rows, in every variant); groups are 2.1-pair micro-groups so the 33% zero-above rate is the arithmetic consequence of a ~50% pass rate on tiny groups, NOT global floor degeneration; disclosed as a caveat. No floor/code/retune/protocol change.
- [INT] Do NOT read the 33% as "33% of introductions skipped" — it is a research-state, introduced-pair, micro-group statistic; eval introductions are measured directly in section 4 results.
- [OBS] Evaluation results (18 episodes each, aggregate; full tables in SDD ledger lines 40-47):

  | policy | primary MSMI/100 | coverage | mutual/100 | ask_cost | invalid |
  |---|---|---|---|---|---|
  | greedy | 0.389 | 0.372 | 5.50 | 206.7 | 0 |
  | random | 0.278 | 0.377 | 5.33 | 206.7 | 0 |
  | **ac (container)** | **0.250** | 0.350 | 4.58 | 419.4 | 0 |
  | ac (local) | 0.250 (identical metrics; inference 20.4 s) | 0.350 | 4.58 | 419.4 | 0 |
  | no_asks | 0.139 | 0.143 | 1.75 | 0.0 | 0 |

- [OBS] Per-variant primary (greedy -> ac): cold_start .167->.167; delayed .500->.500; shift .500->.500; development .500->.167; drift .500->.167; sparse .167->.000.
- [OBS] Rank counts (3 seeds): ac beats no_asks 3/3, random 2/3, **loses to greedy 0/3** (per-seed ac .42/.08/.25 vs greedy .50/.33/.33).
- [OBS] Verification sweep: root suite **144/144 OK (0 skipped)**; research suite **63/63 OK**; G1/G2/G3 PASS; `git diff --stat kit.py evaluate.py Dockerfile .dockerignore .github` EMPTY.
- [DEC] **No post-evaluation tuning occurred** (spec C7): results recorded as measured; any change = new approved round.
- [INT] Honest Round 1 conclusion: A+C ranks 2nd of 4 — clearly beats not-asking, edges random, does not beat greedy while spending 2x ask cost; spec R1 pre-registered exactly this possibility.

## 5. Known limitations and caveats (consolidated)

- [OBS] R1: modest uncalibrated discrimination (AUC 0.59) may not beat greedy — realized in eval.
- [OBS] R2: CI lacks numpy/sklearn; sklearn-dependent tests skip there (root/research suites green locally).
- [OBS] R3: blob 75,560 b64 chars; decode+load ~0.17 s/invoke local (within estimate).
- [OBS] R4: worst-case inference far from 10 s (measured p99 per-invoke well under); cap path (>12,000 candidates) exercised only by unit tests — day-50 eval-like states have sparse frontiers (probe: feasible non-past 2,1,1,2,0,0 across days 10-60; day-50 = 0 for BOTH ac and baseline).
- [OBS] R5: policy_ac.py ignores --baseline (documented).
- [OBS] Calibration caveat C6: ranking score, not probability (A2).
- [OBS] Sparse frontier / 33% zero-above micro-group caveat (section 4 ruling).
- [OBS] T10 latency measured on near-empty scoring workload (consequence of sparse frontiers).

## 6. Unresolved questions (carried into Round 2)

- [UNRES] What primarily causes the A+C vs greedy gap: volume/coverage, mutual-acceptance quality, floor filtering, clarification spend, or matching? (Round 2 Stage 1 diagnostic — separate Round 2 file.)
- [UNRES] Effect of the floor at eval time (edge-level removal on eval decisions not measured).
- [UNRES] Whether ac_asks change the feasible frontier vs baseline asks (not logged in Round 1 artifacts).
- [UNRES] Calibration-vs-ranking effect on MSMI yield.
- [UNRES] Private 120-episode holdout performance (untouched by design).

---
*Record created 2026-10-07 for the hackathon report. Round 1 facts above are copied from the indexed primary sources; nothing historical was altered.*