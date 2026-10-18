# Analysis Plan — Stagewise Counterfactual Signal Audit

Study directory: `research/round2_stagewise_signal/`
Frozen BEFORE any new stagewise result is computed (hash recorded in
`analysis_plan.sha256` and in the run log). Amendments only by appending a
`## Amendment` section; the frozen body is never edited in place.

## 0. Scope and non-goals

This is a DIAGNOSTIC study. It reuses the validated counterfactual
opportunities from `research/round2_decision_ceiling/` and the selector
reconstructions from `research/round2_missed_oracle/`. It:

- does NOT modify `policy.py`, `policy_ac.py`, `kit.py`, `evaluate.py`,
  `Dockerfile`, any test, or any prior experiment artifact;
- does NOT run git-mutating commands;
- does NOT generate fresh world seeds or new policy rollouts;
- does NOT build or deploy a policy model;
- does NOT recommend a strategy or make a submission decision.

All new files land under `research/round2_stagewise_signal/`.
`grass.db` is unrelated and ignored.

## 1. Evidence classes and independence

Every claim is tagged with one of: **measured fact** (directly computed from
frozen artifacts), **statistical inference** (seed-group bootstrap),
**source-code fact** (read from `kit.py` / prior validated code), or
**unresolved hypothesis**.

The independent unit is the SEED GROUP (21 seeds; all 6 variants of a seed
stay together). The 15,304 edge-day rows and the 7,560 states are NEVER
treated as independent observations. Bootstrap: nonparametric resampling of
whole seed groups, B=2000, rng seed 4242, percentile 95% interval — the
same convention as `round2_missed_oracle/scripts/mo_stats.py`.

## 2. Stage targets (frozen definitions)

For each of the 15,304 feasible `(world, pair, decision_day)` opportunities
the exact isolated replay (`ce_common.run_pair_isolated`, the validated
implementation used by `s2_counterfactual.py`) is re-run from the frozen
decision-time snapshot, followed to horizon day 100. Stage labels are read
from the simulator's actual event records (`introduction_response`,
`date_happened`, `second_meeting_intention`) using the official outcome
definitions — never derived from rounded summary statistics.

Unconditional targets (each a binary label on all 15,304 rows):

- **T1 `both_responded`** — both `introduction_response` events carry an
  actual yes/no `value` (not `None` / `missing_reason='no_response'`).
- **T2 `mutual`** — both initial responses are `yes`
  (`ce_common.labels_from_events` `y_mutual`).
- **T3 `date`** — the simulator records a successful first date
  (`date_happened` with `value=True`) (`y_date`).
- **T4 `date_within_deadline`** — the successful date occurred no more than
  30 simulation days after assignment:
  `date_happened.occurred_day - assigned_day <= 30`.
- **T5 `timely_second`** — both `second_meeting_intention` values are `yes`
  and each `occurred_day - date_happened.occurred_day <= 3`
  (`y_second`).
- **T6 `final_msmi`** — all official conditions hold: T4 AND T5
  (`y_msmi`).

Event-detail discriminators preserved per row (for diagnosis, not targets):
`n_intro_no_response`, `n_intro_explicit_no`, `n_intro_yes`
(each 0..2); `date_happened_flag` (True/False); `n_second_yes`,
`n_second_no`, `n_second_missing`, `n_second_late` (yes but >3 days).

Nesting (source-code fact, `kit.Simulator.advance`): T2 implies T1; T3
implies T2; T5 implies T3; T6 = T4 AND T5. T4 and T5 are parallel filters on
T3 (a pair can have a timely second yes yet miss the 30-day deadline, which
the `delayed` variant makes possible).

## 3. Feature sets (frozen, reused verbatim)

No new feature is invented. Predictor columns come from
`round2_decision_ceiling/scripts/s3_signal.py` (`FEATURE_SETS`,
`derived_features_from_row`) and the `feat` payload of
`counterfactual_pairs.jsonl`:

- **A. Baseline count score** = `F1_baseline_count_score`
  (`pair_score`, `pair_score_deficit`, `score_is_max`, `edges_total`,
  `edges_at_same_score`, `n_available`, `n_intros_so_far`).
- **B. Explicit soft-state representation** = `F2_soft_state`
  (A + 8x2x3 hard-channel one-hots + 7x4 soft-channel one-hots over
  `match/mismatch/unknown/declined`, the exact missed-oracle definitions).
- **C. Full legal observable features** = `F4_full_legal_observables`
  (B + public profile + state features), legally available at decision time
  with a valid frozen prediction procedure.

Banned from every feature matrix (unchanged): `seed`, `variant`, `exit_day`,
`truth`, `bias`, `response_rate`, `second_bias`, and any column prefixed
`cf_`/`y_`/`label`. Hidden generator values never enter a predictor.

The feature frame is rebuilt with `s3_signal.load_frame()` — the identical
row order and columns used by the frozen ceiling study — and every stage
label is aligned to that frame by the key
`(seed, variant, day, user_a, user_b)`, asserted 1:1.

## 4. Model specification (frozen)

`sklearn.ensemble.HistGradientBoostingClassifier(max_iter=200,
learning_rate=0.06, random_state=40)` — the ceiling study's `MODEL_KW`, no
tuning, no feature selection, identical complexity for every stage target.

Out-of-fold predictions via `GroupKFold(n_splits=4)` with `groups=seed`
(21 seed groups; all 6 variants of a seed share a fold). Each feature set is
fit separately per stage target.

For T6 `final_msmi` the EXISTING frozen OOF scores in
`oof_scores.jsonl` are reused for the headline tables, and additionally
REFIT bit-exactly as the pipeline consistency check (Section 6 V5).

## 5. Metrics

Per (feature set x target), on the unconditional 15,304-row frame:

- ROC-AUC, PR-AUC (average precision), prevalence, positive count,
  lift = PR-AUC / prevalence (a constant-prevalence predictor has lift 1);
- seed-group bootstrap 95% CI for ROC-AUC (B=2000, rng 4242);
- power flag: `ok` if positives >= 100 AND >= 5 distinct seed groups contain
  a positive; otherwise `inconclusive` (very-small-positive targets are
  reported but never promoted).

Conditional diagnostics (explicitly labelled) reuse the UNCONDITIONAL OOF
score restricted to an outcome-defined subset (e.g. T3 among T2 rows). Such
subsets are defined using an outcome unknown at decision time; a higher
conditional AUC is NOT evidence that a policy could know subset membership,
and is never read as deployable.

## 6. Validation scheme (all must pass before results are believed)

- **V0 seal** — `integrity.sha256` of `round2_decision_ceiling/` and
  `round2_fixed_cardinality/` still current (the known `run_log.txt`
  append-only deviation of the ceiling study is the sole tolerated delta).
- **V1 replay fidelity** — every selected (GREEDY) opportunity's recomputed
  labels match the frozen `n01_introductions` labels (`ref_agrees==1` on all
  8,433 selected rows), reproducing `s2_counterfactual.py`'s check.
- **V2 label agreement** — recomputed `y_mutual`, `y_date`, `y_second`,
  `y_msmi`, `missing` equal the stored `cf_*` columns of
  `counterfactual_pairs.jsonl` bit-exactly (max abs diff 0.0) on all rows.
- **V3 counts** — 15,304 rows, 8,433 selected, 173 T6 positives, 90 T6
  positives among selected (the 90 original N01 MSMIs), 0 duplicate keys.
- **V4 feature legality** — no banned column in any feature matrix.
- **V5 OOF consistency** — refitting A/B/C for T6 reproduces
  `oof_scores.jsonl` bit-exactly (max abs diff 0.0); consequently the
  recorded F2 MSMI metrics reproduce: global ROC-AUC 0.563408, within-state
  AUC 0.588117, PR-AUC 0.017466, prevalence 0.011304
  (`within_state_signal.csv`, `statistics.json`).

If an event cannot be reproduced or distinguished from the existing
artifacts, the limitation is documented — no label is invented.

## 7. Funnel description and stratification (Section 3 of the brief)

Unconditional counts/rates for T1..T6 over all 15,304 rows, plus
conditional conversion rates (T2|T1, T3|T2, T5|T3, T4|T3, T6|all) with the
counts lost between successive stages. Stratified by:

- scenario variant (6);
- decision-day band (0-9, 10-19, 20-39, 40-59);
- baseline pair score (`feat['pair_score']`, 0..7);
- number of observed soft fields (count of the 7 channels whose pair state
  is `match` or `mismatch`, 0..7, from the frozen soft-state columns);
- relationship-goal status (`match`/`mismatch`/`unknown`/`declined`);
- GREEDY-selected flag (`selected` / recomputed `GREEDY` set);
- F2-SOFT-selected flag in the fixed-cardinality audit (membership in the
  `F2-SOFT` set of `round2_missed_oracle/recomputed_sets.jsonl`);
- membership in one of the 82 local-headroom states
  (`selection_diagnostics.jsonl` `headroom==1`).

Selected-vs-unselected contrasts are DESCRIPTIVE differences against
counterfactual simulator labels, never claimed as observed outcomes under
the original policy. Seed-group uncertainty accompanies reported intervals.

## 8. Relationship-goal analysis (Section 5 of the brief)

For each of T1..T6: exact counts, denominators, rates and seed-group CIs for
relationship-goal `match` / `mismatch` / `unknown` (and `declined` when
present), reproducing the frozen soft-state definition. The match-vs-mismatch
stage-rate difference carries a two-sample seed-group cluster bootstrap CI
(the `mo_tail.cluster_boot_diff` estimand). The same per-stage analysis is
repeated for the other six soft channels using the frozen definitions; no
channel is promoted on a point estimate alone.

Three distinct notions are kept apart:
1. descriptive outcome-rate association (this section);
2. cross-validated predictive separation (F2 OOF score mean by channel
   state, with CI — the `mo_tail.D3` analogue per stage);
3. causal effect — NOT established here; goal agreement correlates with
   outcomes through the simulator's acceptance equations, and correlation is
   not a causal estimate.

## 9. Ranking-failure analysis (Section 6 of the brief)

Using the existing OOF F2 predictions and
`round2_missed_oracle/positive_edge_ranks.csv` (173 positive edges with
f2_rank, f2_percentile, flags):

- per stage, the F2-score ROC-AUC for that stage target (from Section 5
  metrics) — how the association weakens from T1..T5 to T6;
- the F2-minus-F1 AUC delta per stage (the soft-state representation's
  marginal ranking contribution, both feature sets already frozen);
- for the 173 T6-positive edges: F2 rank/percentile distribution per stage
  positivity, and whether T6-positive edges rank better or worse than
  earlier-stage-positive edges;
- per-seed consistency of these quantities (spread across the 21 seed
  groups, not row-level claims).

Findings about intermediate outcomes are reported separately from findings
about final MSMI. Better prediction of T2/T3 is NOT claimed to raise T6.

## 10. Mechanism description (Section 7 of the brief)

A source-mechanism description (not a predictive model) derived from
`kit.py`, kept isolated in `mechanism_notes.md`, explaining which stages
contain explicit dependence on: hidden `response_rate`; hidden `bias`;
shared pair-level randomness (`shared ~ N(0,0.45)`); the four soft truths
used by the acceptance mechanism (`relationship_goal`, `relationship_pace`,
`lifestyle`, `conversations` with variant-dependent weights); hidden
`second_bias`; relationship-goal agreement (`+0.4` in the second-meeting
logit); and date-occurrence randomness (`p=0.78`) plus response timing
(delays 1-7 intro, 1-5 second, `delayed` variant extra +5-12 days). Hidden
generator values stay out of every feature matrix; no variance-explained
claim is made from these associations.

## 11. Interpretation rules

- A stage "contains measurable observable predictive signal" only if the
  seed-group CI for ROC-AUC excludes 0.5 (or PR-AUC lift CI excludes 1)
  AND the power flag is `ok`.
- "Signal weakens most sharply" = the largest stage-to-stage drop in the
  F2 ROC-AUC (or lift), reported with both point values; ties and CI
  overlap are stated.
- Relationship-goal is "robust across multiple stages" only if the
  match-vs-mismatch rate difference CI excludes 0 at >= 2 stages with
  `ok` power; otherwise it is called a final-outcome-only or suggestive
  association.
- The 60-point ranking component is "explained" only to the extent the
  stagewise results account for it; anything beyond is listed as unresolved.

## 12. Deliverables

`analysis_plan.md` (this file), `analysis_plan.sha256`, `report.md`,
`stage_counts.csv`, `stage_by_variant.csv`, `stage_by_goal_status.csv`,
`stage_by_soft_channel.csv`, `stage_model_metrics.csv`,
`seed_group_metrics.csv`, `ranking_by_stage.json`, `mechanism_notes.md`,
`validation.json`, `run_log.txt`, `integrity.sha256`, and the reproducible
scripts under `scripts/` (`ss_common.py`, `ss0_validate.py`, `ss1_counts.py`,
`ss2_models.py`, `ss3_goal.py`, `ss4_ranking.py`, `ss5_mechanism.py`,
`ss6_report.py`, `ss_seal.py`, `ss_verify.py`).
