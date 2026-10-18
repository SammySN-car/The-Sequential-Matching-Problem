# Decision Opportunity and Counterfactual Ceiling Audit

Read-only diagnostic. No policy was trained, selected or replaced; no tournament, fresh-seed round or OPR gate was run; no recommendation is made about what to do next. Frozen inputs were hashed before and after and are unchanged.

## 1. Executive findings

- **K1 - Too few genuine decision opportunities** [measured fact]: unresolved
- **K2 - Available choices carry no usable information** [statistical inference]: unresolved
- **K3 - Information exists but sits in unselected choices** [statistical inference]: unresolved
- **K4 - Choices rarely change the MSMI outcome** [measured fact]: supported
- **K5 - Choices structurally interchangeable but outcomes stochastic** [measured fact]: unresolved
- **K6 - The collector score is miscalibrated to MSMI** [statistical inference]: unresolved
- **Replay validity** [measured fact]: 126/126 digests reproduced, 8433/8433 selected introductions replayed in isolation with exact label agreement, 0 immature.
- **Counterfactual base rate** [measured fact]: 173 MSMI positives across 15,304 feasible pairs (1.13%); the collector captured 90 of them (1.07%), against 83 among the 6,871 pairs it did not pick (1.21%). Two-proportion z = -0.82, p = 0.41: no detectable association between selection and outcome.

## 2. Replay and target validity

| check | passed | detail |
|---|---|---|
| V1_selected_pair_agreement | yes | 8433/8433 selected pairs match frozen labels |
| V2_batch_independence | yes | established by G0 T2 (0 mismatches) |
| V3_maturity | yes | 15304 rows, 0 None labels at horizon 100 |
| V4_count_integrity | yes | total=15304 selected=8433 duplicate_keys=0 |
| V5_orientation | yes | all keys sorted ascending; G0 T1 passed |
| V6_feature_legality | yes | 34 feature columns, none banned |

G0 tests: T1 pair-orientation PASS; T2 batch independence PASS; T2L snapshot leak PASS; T5 determinism PASS. Verdict recorded in `g0_replay_validation.md`.

Section 3 reconstruction reconciled against every frozen aggregate: 7560 days, 15304 edges, 8433 introductions, 3566 zero-edge days, 2087 days with n_pairs >= 2, 0 per-day edge mismatches.

## 3. How many genuine decision opportunities exist

Five concepts kept separate (analysis_plan.md 3.1 as amended by Amendment 1). `alt_same_size` replaces the degenerate `matching_unique`: a different valid matching of the same batch size.

| stratum_type | stratum_value | n_days | sum_edges_total | sum_n_pairs | n_days_edges0 | edges_total_mean | selected_with_alt_partner_share_mean | alt_same_size_mean | alt_same_size_same_endpoints_mean | alt_same_size_diff_endpoints_mean | batch_underfill_mean | addition_possible_mean | alt_same_size_unknown_mean |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| overall | all | 7560 | 15304 | 8433 | 3566 | 2.024339 | 0.2381 | 0.302646 | 0.008201 | 0.302249 | 0.033995 | 0.0 | 0.0 |
| variant | cold_start | 1260 | 2476 | 1416 | 531 | 1.965079 | 0.253849 | 0.322222 | 0.010317 | 0.319841 | 0.027778 | 0.0 | 0.0 |
| variant | delayed | 1260 | 3023 | 1621 | 525 | 2.399206 | 0.278679 | 0.354762 | 0.009524 | 0.354762 | 0.045238 | 0.0 | 0.0 |
| variant | development | 1260 | 3089 | 1653 | 515 | 2.451587 | 0.284355 | 0.365079 | 0.010317 | 0.365079 | 0.044444 | 0.0 | 0.0 |
| variant | drift | 1260 | 3102 | 1656 | 514 | 2.461905 | 0.287133 | 0.36746 | 0.010317 | 0.36746 | 0.044444 | 0.0 | 0.0 |
| variant | shift | 1260 | 3125 | 1677 | 505 | 2.480159 | 0.286729 | 0.35873 | 0.00873 | 0.35873 | 0.04127 | 0.0 | 0.0 |
| variant | sparse | 1260 | 489 | 410 | 976 | 0.388095 | 0.037857 | 0.047619 | 0.0 | 0.047619 | 0.000794 | 0.0 | 0.0 |
| day_band | 0-9 | 1260 | 4384 | 2516 | 327 | 3.479365 | 0.256571 | 0.370635 | 0.023016 | 0.370635 | 0.092857 | 0.0 | 0.0 |
| day_band | 10-19 | 1260 | 4199 | 2395 | 228 | 3.33254 | 0.346394 | 0.488095 | 0.011111 | 0.487302 | 0.052381 | 0.0 | 0.0 |
| day_band | 20-39 | 2520 | 4648 | 2520 | 1217 | 1.844444 | 0.255457 | 0.308333 | 0.004762 | 0.30754 | 0.018651 | 0.0 | 0.0 |
| day_band | 40-59 | 2520 | 2073 | 1002 | 1794 | 0.822619 | 0.157361 | 0.170238 | 0.002778 | 0.170238 | 0.010714 | 0.0 | 0.0 |

`addition_possible_mean` is 0.000000 everywhere: greedy is always maximal, so the failure mode is never "declined a feasible edge". `alt_same_size_unknown_mean` is 0.000000 everywhere: every alternative-matching answer is exact, never truncated. The 30.3% choice-day share covers 5,912 of 8,433 introductions (70.1%), so composition choice - not batch size - is the dominant lever.

Strata are world and density bands too; full detail is in `opportunity_summary.csv`. Daily gaps are never summed anywhere in this report.

## 4. Predictive signal across the full feasible action set

| feature_set | n_rows | n_positives | prevalence | auc | pr_auc | lift | within_state_auc_mean | within_state_auc_posweighted | n_states | top1_hit_rate | ci95_low | ci95_high | power_flag |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| F1_baseline_count_score | 15304 | 173 | 0.011304 | 0.503788 | 0.013748 | 1.216197 | 0.527288 | 0.530582 | 159 | 0.207547 | 0.422945 | 0.596202 | ok |
| F2_soft_state | 15304 | 173 | 0.011304 | 0.563408 | 0.017466 | 1.545042 | 0.588117 | 0.585372 | 159 | 0.201258 | 0.491963 | 0.644951 | ok |
| F3_public_profile | 15304 | 173 | 0.011304 | 0.550785 | 0.01423 | 1.258803 | 0.544277 | 0.546937 | 159 | 0.232704 | 0.482041 | 0.626441 | ok |
| F4_full_legal_observables | 15304 | 173 | 0.011304 | 0.523253 | 0.012788 | 1.131223 | 0.517656 | 0.515793 | 159 | 0.176101 | 0.464604 | 0.598585 | ok |
| F5_state_only | 15304 | 173 | 0.011304 | 0.528903 | 0.012389 | 1.09597 | 0.5 | 0.5 | 159 | 0.188679 | 0.473473 | 0.58574 | ok |

Ablations (seed-group bootstrap, 1000 resamples):

| contrast | delta_auc | ci95_low | ci95_high | excludes_zero |
|---|---|---|---|---|
| F2_minus_F1 | 0.05962 | 0.028301 | 0.092176 | 1 |
| F3_minus_F1 | 0.046997 | -0.007549 | 0.100799 | 0 |
| F4_minus_F3 | -0.027532 | -0.071432 | 0.013631 | 0 |

Collector selection effect:

| feature_set | auc_all | auc_selected_only | score_gap_selected_minus_not | gap_ci95_low | gap_ci95_high |
|---|---|---|---|---|---|
| F1_baseline_count_score | 0.503788 | 0.501889 | -0.000667 | -0.001436 | -1.9e-05 |
| F4_full_legal_observables | 0.523253 | 0.527805 | -6e-06 | -0.000755 | 0.000606 |

A collapsed selected-only AUC alongside a large score gap is reported as a **selection effect**, not as absence of information (analysis_plan.md 8.3). No such effect is present here: the F1 gap is -0.00067 with a selected-only AUC (0.5019) indistinguishable from the all-row AUC (0.5038), so the collector is not preferentially selecting high-information pairs.

## 5. Explicit mismatch vs unknown signal

F2 (explicit soft-state, per-channel match/mismatch/unknown) minus F1 (aggregate baseline count score): delta AUC = 0.05962, 95% CI [0.028301, 0.092176], excludes zero = yes.
[statistical inference] Under the preregistered seed-group bootstrap this contrast is **distinguishable from noise**; a bootstrap interval is a statistical inference, never a measured fact.

Adding more legal observables does not improve discrimination: F4 scores 0.5233 against F2's 0.5634, and F4-F3 is -0.0275 [-0.0714, 0.0136]. The direction is consistent with overfitting at 173 positives, but that interval includes zero so the effect is not distinguishable from noise.

### 5.1 Decision relevance (question E)

Restricted to the 82 day-states with positive local headroom that also had a genuine composition choice:

| feature_set | n_headroom_choice_states | n_states_auc_defined | within_state_auc_mean | n_states_argmax_beats_collector | argmax_beats_collector_rate |
|---|---|---|---|---|---|
| F1_baseline_count_score | 82 | 82 | 0.485098 | 41 | 0.5 |
| F2_soft_state | 82 | 82 | 0.533647 | 31 | 0.378049 |
| F3_public_profile | 82 | 82 | 0.436867 | 16 | 0.195122 |
| F4_full_legal_observables | 82 | 82 | 0.495537 | 18 | 0.219512 |
| F5_state_only | 82 | 82 | 0.5 | 55 | 0.670732 |

**Control:** `F5_state_only` carries no pair-discriminating information (every edge on a day receives the same score), so its within-state AUC is exactly 0.500000 by construction - yet its argmax matching "beats" the collector on 55/82 states. That statistic is therefore confounded by maximum-cardinality effects and must not be read as signal. The models that do discriminate between pairs (F1, F2, F3, F4) beat the collector on 41, 31, 16 and 18 of 82 states respectively; F2, the best overall performer, is *worse* than greedy on the days where headroom exists.

## 6. Local hindsight-oracle headroom

Oracle solver cross-check: 7489 brute-force comparisons, 0 disagreements, enumeration failures 0. An independent networkx maximum-cardinality matching agrees on every day.

| stratum_type | stratum_value | n_days | n_days_oracle_pos_ge1 | n_days_gap_ge1 | share_gap_ge1_among_oracle_pos | mean_collector_positives | mean_oracle_positives | mean_maxcard_positives | share_days_positive_headroom | n_enum_failed |
|---|---|---|---|---|---|---|---|---|---|---|
| overall | all | 7560 | 166 | 82 | 0.493976 | 0.011905 | 0.022884 | 1.149471 | 0.010847 | 0 |
| variant | cold_start | 1260 | 34 | 13 | 0.382353 | 0.016667 | 0.026984 | 1.151587 | 0.010317 | 0 |
| variant | delayed | 1260 | 30 | 16 | 0.533333 | 0.011905 | 0.025397 | 1.331746 | 0.012698 | 0 |
| variant | development | 1260 | 35 | 20 | 0.571429 | 0.013492 | 0.029365 | 1.356349 | 0.015873 | 0 |
| variant | drift | 1260 | 33 | 18 | 0.545455 | 0.013492 | 0.027778 | 1.35873 | 0.014286 | 0 |
| variant | shift | 1260 | 29 | 13 | 0.448276 | 0.013492 | 0.02381 | 1.372222 | 0.010317 | 0 |
| variant | sparse | 1260 | 5 | 2 | 0.4 | 0.002381 | 0.003968 | 0.32619 | 0.001587 | 0 |
| day_band | 0-9 | 1260 | 44 | 17 | 0.386364 | 0.023016 | 0.037302 | 2.089683 | 0.013492 | 0 |
| day_band | 10-19 | 1260 | 47 | 26 | 0.553191 | 0.01746 | 0.038095 | 1.953175 | 0.020635 | 0 |
| day_band | 20-39 | 2520 | 55 | 26 | 0.472727 | 0.012698 | 0.023016 | 1.018651 | 0.010317 | 0 |
| day_band | 40-59 | 2520 | 20 | 13 | 0.65 | 0.002778 | 0.007937 | 0.408333 | 0.005159 | 0 |
| density_band | 1 | 1115 | 7 | 0 | 0.0 | 0.006278 | 0.006278 | 1.0 | 0.0 | 0 |
| density_band | 2-4 | 1771 | 42 | 21 | 0.5 | 0.011858 | 0.023715 | 1.739695 | 0.011858 | 0 |
| density_band | 5-9 | 817 | 62 | 32 | 0.516129 | 0.037944 | 0.077111 | 3.203182 | 0.039168 | 0 |
| density_band | 10+ | 291 | 55 | 29 | 0.527273 | 0.106529 | 0.209622 | 6.450172 | 0.099656 | 0 |

**This is a myopic one-day hindsight oracle, not a sequential policy oracle and not a global ceiling. It uses counterfactual labels the policy could never observe at decision time. Daily gaps are reported as distributions and are never summed into an episode total. The three arms (baseline-score matching, maximum-cardinality matching, MSMI-informed local oracle) are reported separately and never netted.**

Density-1 days show 7 oracle-positive days and 0 gap days, as expected: a day with a single edge has no alternative to miss.

## 7. What the results establish and do not establish

| cause | classification | evidence class |
|---|---|---|
| K1 - Too few genuine decision opportunities | unresolved | measured fact |
| K2 - Available choices carry no usable information | unresolved | statistical inference |
| K3 - Information exists but sits in unselected choices | unresolved | statistical inference |
| K4 - Choices rarely change the MSMI outcome | supported | measured fact |
| K5 - Choices structurally interchangeable but outcomes stochastic | unresolved | measured fact |
| K6 - The collector score is miscalibrated to MSMI | unresolved | statistical inference |

Information headroom (K2, K3, K6) and action headroom (K1, K4, K5) are reported separately and never fused. The six causes are not mutually exclusive. Frozen EDA hypotheses H1-H9 are referenced only: not retested, not re-statused, and no frozen artifact was modified.

Two further readings, stated with their evidence class:

- [measured fact] A perfect one-day hindsight oracle reaches 173 MSMI positives over the whole corpus where the collector reaches 90. Even that oracle is bounded by the 173 counterfactual positives that exist in the feasible action set; it is not a sequential optimum.
- [statistical inference] On the 82 days where headroom existed, no model with genuine pair discrimination out-scored greedy. This is consistent with the signal that does exist (soft channel state, F2-F1 excludes zero) being too weak and too sparse to act on, and is not evidence that no policy could ever improve.

## 8. Remaining uncertainties

- 173 counterfactual positives across 15,304 rows is the binding power limit for every interval in section 4; the overall F4 interval [0.4646, 0.5986] spans chance.
- Per-world heterogeneity permutation null (200 within-world shuffles, rng 4242): observed spread 0.162344 against null mean 0.167438, p = 0.5771. No between-world variation beyond chance was detected.
- Enumeration of distinct matchings is capped at 50 (`n_matchings_gt_cap` in `opportunity_summary.csv`); days exceeding the cap are counted, never treated as unique. The decision-relevant `alt_same_size` flag uses an exact early-exit search and its `unknown` count is 0.
- Counterfactual labels are computed pair-alone and are unobserved by the original collector (`flag = counterfactual_unobserved`). They are never presented as observed outcomes and carry no sequential consequences.
- K5's decision rule uses the qualitative terms "high" and "low" without numeric thresholds, so it cannot be applied mechanically without post-hoc threshold selection; it is recorded as unresolved with both component values shown.

## 9. Ranked evidence on the causes of prior failures

1. **K4 - Choices rarely change the MSMI outcome** [measured fact] -> supported
2. **K1 - Too few genuine decision opportunities** [measured fact] -> unresolved
3. **K2 - Available choices carry no usable information** [statistical inference] -> unresolved
4. **K3 - Information exists but sits in unselected choices** [statistical inference] -> unresolved
5. **K5 - Choices structurally interchangeable but outcomes stochastic** [measured fact] -> unresolved
6. **K6 - The collector score is miscalibrated to MSMI** [statistical inference] -> unresolved

Ranking is by strength of this audit classification only. It is not a recommendation and no policy, tournament or strategy follows from it.

## 10. Artifact index

- `ablation_deltas.csv`
- `analysis_plan.md`
- `counterfactual_pairs.jsonl`
- `counterfactual_validation.csv`
- `day_edges.jsonl`
- `decision_relevance.csv`
- `g0_replay_validation.md`
- `g0_results.json`
- `git_status_start.txt`
- `headroom_synthesis.json`
- `heterogeneity.json`
- `integrity.sha256`
- `local_oracle_headroom.csv`
- `manifest_end.json`
- `manifest_start.json`
- `oof_scores.jsonl`
- `opportunity_by_world.csv`
- `opportunity_summary.csv`
- `oracle_by_day.jsonl`
- `oracle_solver_check.json`
- `pair_state.jsonl`
- `plan_implementation.md`
- `reconciliation.json`
- `report.md`
- `run_log.txt`
- `selection_effect.csv`
- `verification_final.json`
- `within_state_signal.csv`
- `scripts/` - deterministic, seeded, re-runnable

Integrity hashes are in `integrity.sha256`; protected-input start/end hashes are in `manifest_start.json` / `manifest_end.json`.
