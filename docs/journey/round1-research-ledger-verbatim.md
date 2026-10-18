# SDD ledger - plan: C:\Users\samar\AppData\Local\Temp\opencode\smp-plan.md
Pre-flight: shared interfaces - T1 labels <- T3 collect <- T6 driver; T2 features <- T3 <- T6; T2/T3 rows -> T4 integrity + T5 analyze; ruled: labels take t+events, features take (state,events,t) with t<=state['day'].
Ruling: no git commits (user rule: only when explicitly requested) - ledger substitutes for commit history - cost if wrong: none.
Ruling: research is a python package (research/__init__.py), tests in research/test_pipeline.py, run via python -m unittest research.test_pipeline -v from repo root - cost if wrong: one import path change.

Task 1: complete (labels.py, no commits per ruling; tests: python -m unittest research.test_pipeline -> 9/9 OK; repo suite run -> see line above)
Task 1 gate: python -m unittest (repo+research) -> 31 tests OK
Task 2: Ruling: pair_features must be symmetric in (a,b) - y is symmetric and scoring must not depend on argument order - replaced who_meets_a/b with who_meets_min/max, a_/b_days_since_arrival with mean/absdiff - cost if wrong: loses directional preference signal
Task 2: complete (features.py; tests: python -m unittest -> OK; rulings: symmetric feature set)
Task 3: Ruling: dropped assertion random_coverage>greedy_coverage from unit test - both are maximal matchings so sizes are comparable by construction; coverage numbers belong in the report - cost if wrong: none (measured empirically in T6)
Task 3: complete (collect.py; tests -> full suite OK; correction: the random>greedy coverage assertion WAS kept and passes deterministically for seeds 9/3 - supersedes prior ruling line
Task 4: complete (integrity.py + collect_rows now returns events; tests -> 52 OK; test fix: injected-defect direction corrected in test_immature_but_labelled)
Task 5: complete (analyze.py; tests -> 60 OK). Ruling: added stage targets label_mutual/label_date as diagnostics - MSMI prevalence measured at 0.94% (5/533 across 6 greedy seeds) so a STOP decision must distinguish too-rare from no-signal - cost if wrong: small extra code
Task 6: complete (run_experiment.py + README; smoke + full run: 440 rollouts/32044 rows/integrity all pass/decision PROCEED WITH CHANGES; suite 68 OK; git status shows only ?? research/)
Final fix pass: fixed I1 (labels from complete event record + horizon stamp), I2 (audit scoped per rollout + dataset-level audit of all 32044 rows + static source audit), I3 (assertions + audit_source), re-graded M2 (lifts vs validation prevalence) and M10-ordering (canonical row sort - MSMI AUC 0.528->0.548 across runs sat at the 0.55 gate) - tests 74 OK
Final review: dispatched fresh-context reviewer (task ses_eefc83a57ffe4Nfo842X40dAH9) -> 0 Critical, 3 Important, 10 Minor, all 7 constraints verified satisfied
Final: fixed I1 (labels from complete event record + row horizon stamp) - test_insufficient_follow_up_yields_none_labels RED->GREEN
Final: fixed I2 (audit dup key scoped to rollout; dataset audit of all 32044 rows in report; integrity suite uses CLI follow_up) - test_audit_rows_scopes_duplicates_to_one_rollout RED->GREEN
Final: fixed I3 (audit_source static scan + poisoned-state assertions) - test_static_source_audit_flags_hidden_member_reads RED->GREEN, suite 75/75
Final: re-graded M2 (lifts now vs validation prevalence) and M10-ordering (canonical sort_rows; MSMI AUC had moved 0.528->0.548 across runs straddling the 0.55 gate) - test_stage_gate_uses_validation_prevalence, test_sort_rows_makes_report_inputs_reproducible RED->GREEN
Final verification: full re-run written to research/out (dataset audit 0 violations, source audit clean, decision PROCEED WITH CHANGES); analysis reproducible from rows.csv (True); git status = ?? research/ only; suite 75 OK x3
Final: review: self-recorded deferred minors M1,M4,M5,M6,M7,M8,M9,M10a + sklearn single-class AP warning + test gaps (variant!=development rollout, spawn path, coverage_block one-sided worlds)
Ruling: ledger NOT deleted after review - user rule forbids commits, so this file is the only process record (cost if wrong: one stale temp file)

================================================================================
PRE-REGISTRATION - scale-up MSMI validation run (2026-10-06 15:17:58, BEFORE launch)
================================================================================
Ruling: new run writes to research/out_scale800/, previous research/out/ (440-rollout
  run) is preserved untouched as the comparison baseline - cost if wrong: none,
  both dirs are under research/ and reversible.
Scale: 800 worlds, 3200 random + 320 greedy = 3520 rollouts, 60+40 days, 12 workers,
  same features/labels/maturity/collectors/variants/sort_rows/split_seed=0/model.
NO tuning, NO feature changes, NO target changes, NO A+C implementation.

PRE-REGISTERED MSMI GATES (unchanged from source constants, run_experiment.py:35-36):
  MSMI_AUC_MIN  = 0.55   (validation ROC-AUC >= 0.55)
  AP_LIFT_MSMI  = 1.10   (validation AP lift >= 1.10x validation prevalence)
  PASS requires BOTH.

PRE-REGISTERED DECISION RULE (95% Hanley-McNeil CI for val AUC, CI=[lo,hi]):
  1. integrity failure                -> STOP (report failure, do not repair silently)
  2. lift >= 1.10 AND lo >= 0.55      -> PASS
  3. hi < 0.55                        -> FAIL
  4. lift < 1.10 AND lo >= 0.55       -> FAIL
  5. otherwise (CI straddles 0.55)     -> INCONCLUSIVE
Stop-on-failure integrity checks: forbidden_keys, future-masking, no-unintroduced-
negatives (rows audit), no-immature-coercion (dataset audit), zero split overlap,
canonical ordering, full test suite green before AND after.

Baseline being compared: 32044 rows, 70 val positives, AUC 0.5218, AP lift 0.99x.
================================================================================

Tasks 1-3 complete (2026-10-06 15:29:09):
- Pre-registered gates + decision rule recorded in ledger BEFORE launch (above block).
- Pre-flight suite: 75/75 OK (before changes).
- TDD additions (RED watched -> GREEN): test_auc_ci_matches_hand_computed_hanley_mcneil,
  test_evaluate_attaches_auc_ci_and_none_for_single_class,
  test_split_overlap_zero_for_real_split_and_positive_when_poisoned,
  test_train_and_evaluate_reports_zero_split_overlap,
  test_build_report_shows_gates_auc_ci_and_split_overlap.
  Production: analyze.auc_ci (Hanley-McNeil 95%), evaluate() gains auc_ci95,
  analyze.split_overlap, train_and_evaluate gains split_overlap, build_report
  renders 'split overlap (must be 0)' + 'AUC CI95', main folds zero-overlap into
  integrity_clean (overlap > 0 -> decide() STOP).
- Full suite after changes: 80/80 OK. git status: ?? research/ only.
- Smoke run end-to-end OK (temp dir): CI + overlap + gates lines present, integrity pass.
Ruling: report-text rendering verified by smoke integration (build_report unit test
  covers the two new strings) - cost if wrong: a cosmetic format slip, caught in smoke.

Run complete (2026-10-06 16:44:14) - scale-up experiment VERIFIED:
- 3520 rollouts (3200 random / 320 greedy), 800 worlds, 60+40 days, 12 workers,
  elapsed 4341s rollouts + analysis -> research/out_scale800/ (previous research/out untouched).
- Verification (fresh, this session): unittest 80/80 OK; git status '?? research/' only;
  worlds.csv assignments sum 259696 == rows.csv data rows 259696; outputs present
  (report.txt/json, rows.csv 86.7MB, worlds.csv 249KB).
- Integrity: suite ALL CHECKS PASS, dataset audit 0, source audit clean, leakage clean,
  immature 0, split overlap 0 worlds / 0 seeds, canonical ordering test green.
- MSMI val: n=50458 pos=475 neg=49983; AUC 0.5937 CI95 [0.5667, 0.6208];
  AP 0.0123 / prev 0.009414 -> lift 1.3037; logloss 0.0541; brier 0.0095.
- Pre-registered rule applied: integrity OK; lift 1.30 >= 1.10; CI lo 0.5667 >= 0.55
  -> DECISION: PASS (report decision: PROCEED). Gates unchanged from ledger.
- Stage targets re-confirmed: mutual AUC 0.6131 lift 1.40x; date AUC 0.6064 lift 1.36x.
- Caveat noted for A stage: hist_gb logloss/brier slightly WORSE than constant
  (0.0541/0.0095 vs 0.0533/0.0093) - good ranking, imperfect calibration on rare event.
- NO A+C implemented, NO Round 1 draft, NO tuning. Awaiting approval for next stage.

## 2026-10-06 A+C design gate
- Brainstorming (architectural path): decisions 1-8 approved with amendments A1 (train-split-only model; full-data refit deferred) and A2 (HistGB output is ranking score, not calibrated probability; no score-minus-prevalence thresholds; conservative wait = train-median rank floor).
- Design spec written (not committed, per no-commit rule): docs/superpowers/specs/2026-10-06-a-plus-c-policy-design.md (16 sections; self-review fixed 3 issues: local-search move inequality, phase-aware empty response, C1 file list).
- Key discovered constraint: evaluate.py --baseline choices frozen (greedy/no_asks/random), container passes no args -> policy.py default becomes ac; local ac eval via new policy_ac.py shim (--policy flag).
- CI: zero pip installs (numpy/sklearn absent), Python 3.10+3.12; docker 29.8.0 available locally. research/__init__.py exists so bare unittest discovers research tests.
- Next: user reviews spec -> writing-plans -> TDD implementation.

## 2026-10-06 export/inference contract clarification (user-required, spec approved after)
- Empirical spike (sklearn 1.8): node schema = is_leaf/feature_idx/num_threshold/left/right/missing_go_to_left/value; raw(x) = _baseline_prediction + sum(walked leaf values), NO inference-time lr scaling (lr 1.0 vs 0.1 leaf ratio exactly 10.0); pure-python vs predict_proba max abs diff 3.47e-18 (500-row probe).
- Spec updated in place: sec 4 export sources + prediction-equivalence contract + exporter self-check (non-zero exit on parity failure); sec 5 complete additive prediction + T12 hard gate (atol=1e-9, rtol=0, export invalid if fails); T13 wording: T12 = primary, T14 = secondary.
- User approved spec with Tier 1b, policy_ac.py shim, train-split model, rank floor, local search, memory, fallback, T1-T14, pre-registered eval unchanged. Next: writing-plans.

## Plan amendment pass (review findings 1-12) - COMPLETE
- File: docs/superpowers/plans/2026-10-06-a-plus-c-policy.md: 85,840 -> 120,877 bytes, 1729 -> 2216 lines
- Batches: p1-p6 (T1), q2-q8 (T2), r1-r2 (T3), t1-t5 (T6), u1 (T7), w1-w3 (T6 cap + T9), inline reps (counts, Task 8, Task 10, table, checklist, gotchas)
- Cumulative test counts now: 88 / 96 / 100 / 104 / 113 / 125 / 130 / 140 / 144 / 144
- Day-50 replay probe (seed 42, dev, n=200): available=174, intros=96, feedback=208, request=452,783 bytes < 1 MiB, allow_nan=False clean; ask-phase candidates=111
- evaluate.invoke returns (validated_response, elapsed); docker image tag: sequential-policy:1.0
- Status: READY FOR IMPLEMENTATION (no code written; plan-only pass)
