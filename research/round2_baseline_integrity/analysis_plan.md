# Cross-Study Baseline Integrity Audit - Analysis Plan

**Directory:** `research/round2_baseline_integrity/`
**Study type:** read-only research-integrity audit of score direction, comparability
and affected conclusions across historical studies.
**Status:** FROZEN. SHA-256 recorded in `analysis_plan.sha256`. Corrections only via
an appended `## Amendment` section (original body never edited in place).

Written and hashed before any corrective computation (no corrected selector
total, rank, interval or matrix row had been computed at freeze time; only
read-only source inspection and reading of already-published results).

---

## 0. Scope and non-goals

In scope: establish score-direction facts from executable source; build a
cross-study audit matrix; recompute only what saved artifacts permit; classify
every headline conclusion as supported / supported-with-qualifications /
withdraw-or-correct / still-unresolved.

Non-goals (prohibited): modifying `policy.py`, `policy_ac.py`, `kit.py`,
`evaluate.py`, `Dockerfile`, tests, or any prior study artifact; overwriting
reports or integrity manifests of completed studies; git-mutating commands;
fresh world seeds, rollouts or policy tournaments; tuning features, weights,
thresholds or hyperparameters; reading `grass.db`; selecting a next experiment,
recommending a policy, or making a submission decision. New files are created
only under `research/round2_baseline_integrity/`.

The historical score-direction defect is preserved as the record of what was
actually tested: frozen-defect reproductions (F1f/G1f) are kept as separate,
clearly labelled series; corrected analyses live in `corrected_*` outputs.

## 1. Repository inventory (actual paths, inspected before freeze)

All 15 directories listed in the audit request exist under `research/`;
additional related directories were found and are recorded:

| Path | Role in this audit |
|---|---|
| `research/out/` | Round-1 pipeline validation (440 rollouts, random+greedy collectors) |
| `research/out_scale800/` | Scale-800 pipeline validation (3,520 rollouts) |
| `research/next_method_search/` | N01 autopsy; `allocate()` = kit.baseline_match + edge metadata |
| `research/next_strategy_research/` | Static audit + strategy synthesis (document) |
| `research/e3_rel_experiment/` | REL-ask VoI experiment (4 arms, seeds 119-142) |
| `research/method_tournament/` | 30-method tournament (seeds 152-163) |
| `research/round2/` | A+C gated-policy promotion experiment (seeds 101-103) |
| `research/round2_stage1_5/`, `round2_stage2_floor_ablation/`, `round2_stage3_intermediate_floor/` | A+C floor chain |
| `research/round2_promotion_fresh_seeds/` | Promotion on fresh seeds 107-118 |
| `research/round2_stage4_history_coldstart_audit/` | Cold-start/history model audit |
| `research/round2_opr/` | OPR analytic probability study |
| `research/round2_eda/` | Root-cause EDA synthesis |
| `research/round2_decision_ceiling/` | Ceiling/headroom diagnostic; producer of `day_edges.jsonl`, `oof_scores.jsonl`, `counterfactual_pairs.jsonl` |
| `research/round2_fixed_cardinality/` | F1-SCORE..F5-ORACLE fixed-k audit (site of the direction defect) |
| `research/round2_missed_oracle/` | 60/7 decomposition; F1 arm reproduced with the defect |
| `research/round2_stagewise_signal/` | OOF stage-wise predictive signal study |
| `research/round2_goal_rule/` | G0-G5 study; reports both G1f (frozen reproduction) and G1m (corrected) |
| `research/round1_submission/` | Submission proposal document (claims index) |

## 2. Protected artifacts

- Protected code: `policy.py`, `policy_ac.py`, `kit.py`, `evaluate.py`,
  `Dockerfile`, `test_policy.py`, `test_kit.py`, `research/test_pipeline.py`
  (and any other `test_*.py` found). `bi0_inventory.py` records SHA-256 of each;
  `bi_verify.py` re-checks them at the end.
- Prior studies: every `integrity.sha256`/`*.sha256` manifest is read and
  re-verified read-only by our own checker (never by re-running their scripts,
  which could append to their logs). `run_log.txt` files that their own verify
  conventions tolerate as append-only are checked with that same tolerance;
  known pre-flagged exceptions (Sec. 8) are recorded, not "fixed".
- Expected result: all protected hashes unchanged from freeze to finish.

## 3. Evidence sources (all read-only)

Executable source (verdicts come from these, never from names or passing
tests), study reports/analysis plans, saved selector sets
(`research/round2_goal_rule/selector_sets.jsonl`), per-state tables
(`per_state_results.csv`), `selector_summary.csv`, `evaluation.json`,
`round2_decision_ceiling/day_edges.jsonl`, `oof_scores.jsonl`,
`counterfactual_pairs.jsonl`, `oracle_by_day.jsonl`,
`round2_missed_oracle/selection_diagnostics.jsonl`,
`recomputed_sets.jsonl`, `positive_edge_ranks.csv`, `decomposition_agg.json`,
`round2_fixed_cardinality` summary/statistics files, and each study's
`summary.json`/`report.md` headline tables.

## 4. Source-fact protocol (request section 2)

For each implementation below, `bi1_source_facts.py` extracts the exact
executable lines (with pattern assertions that fail if the lines move) and
records verdicts on all seven required questions: (1) whether higher or lower
raw scores are better; (2) whether the objective maximizes or minimizes the
intended score; (3) whether the score was negated when passed into a
maximizing solver; (4) how unknown / observed-mismatch / observed-match values
are scored; (5) how ties are resolved; (6) whether it reproduces sequential
greedy selection or globally optimizes a fixed-cardinality matching; (7)
whether actual output matches the report's description.

Implementations in scope:

1. `kit.py` `baseline_match` (official simulator baseline; also used by
   `test_policy.py`, `policy.py` greedy mode, tournament control).
2. `research/next_method_search/n01_autopsy.py` `allocate()` and the consumers
   of its `edges` (sign chain into `day_edges.jsonl`).
3. `research/round2_decision_ceiling/scripts/s1_opportunities.py` (the writer
   of `day_edges.jsonl`) and the stale `neg_score` docstring in `ce_common.py`.
4. `research/round2_fixed_cardinality/scripts/fc_selectors.py` F1-SCORE
   weighting and `fc_matching.solve_exact_k` objective direction.
5. `research/round2_missed_oracle/scripts/mo_validate.py` F1-SCORE weighting.
6. `research/round2_goal_rule/scripts/gr_common.py` `weight_g1f` / `weight_g1m`.
7. `policy.py` A+C path: `ac_match`, `max_score_matching`, `rule_score`,
   `ac_asks` (floor, candidate eligibility, tie order) and `policy_ac.py`.
8. `research/method_tournament/alloc.py` `greedy_take` and each retained
   method's relationship to that control.
9. **Suspected second defect:** `research/round2_missed_oracle/scripts/
   mo_analyze.py` baseline rank (`competition_rank(-raw[i][0], ...)` against
   `raw` that stores positive counts) and its downstream consumers in
   `ss4_ranking.py` / `ss6_report.py` and the missed-oracle report's
   baseline-rank claims. Direction is decided by computation (C5), not by
   code reading alone.

Eligibility parity (candidates = available x kit-feasible x never-introduced)
and unknown-field treatment are recorded for every selector.

## 5. Audit matrix protocol

`study_audit.csv`, one row per historical comparison. Inclusion rule: every
comparison that (i) formed a headline or conclusion in a study report, or
(ii) set any arm against a count-based baseline or the official GREEDY
control. Required columns (verbatim from the request): study and artifact
path; control arm; candidate arm; raw score or feature definition; intended
objective direction; actual objective direction; candidate-selection
procedure; paired on same worlds; introduction cardinality fixed; metric type
(observed full-episode MSMI vs local counterfactual MSMI); score-direction bug
applies; reproducible from saved artifacts; interpretable; corrected
interpretation; missing evidence or limitations.

Classification vocabulary (only these four, applied per comparison row, never
per whole study): `CORRECT_AND_COMPARABLE`, `CORRECT_BUT_NOT_COMPARABLE`,
`DIRECTION_BUG`, `OTHER_IMPLEMENTATION_DEFECT`,
`UNVERIFIABLE_FROM_SAVED_ARTIFACTS`. Every row carries at least one
file:line or artifact citation.

## 6. Claims under investigation and pre-stated decision rules

**A. "Learned scoring beats the simple count score."** Four distinct claims,
judged separately:
- A1: F2 beats the frozen F1-SCORE selector (94 vs 81, published +13,
  CI [0.0476, 1.2381], 11/7/3) - reproducibility check of the published number
  as actually run (defective baseline, kept as historical record).
- A2: F2 beats the correctly directed count maximizer (94 vs 88) - computed
  by C1/C2 from saved per-state data; classified by whether the seed-group CI
  excludes 0.
- A3: F2 beats the actual sequential GREEDY policy at equal cardinality
  (94 vs 90, published CI includes 0) - reproduce from saved data.
- A4: F2 improves the official realized sequential objective (MSMI/100 on full
  episodes) - rule: classify `UNVERIFIABLE_FROM_SAVED_ARTIFACTS` unless a
  saved full-sequential F2 policy run exists (searched for in bi0/bi3; none is
  known to exist).

**B. Goal-rule reconciliation.** Reproduce G0=90, G1f=81, G1m=88, G2=92,
G3=92, G4=94, G5=161 and sum(k_t)=8,433 from `per_state_results.csv`;
reproduce overlapping intervals from `evaluation.json` bit-for-bit (same
method: mean per-seed delta, paired bootstrap B=2000, rng 4242). Interpret
the goal rule against G0 (the actual greedy selector) and G1m (corrected
count), not only against G1f; always labelled a local fixed-cardinality
counterfactual diagnostic.

**C. 60/7 decomposition.** Source-assert (`bi1`) that `mo_decomp.py` inputs
are only F2, F5 and R_t (positives among top-k_t by F2); reproduce
ranking=60, conflict=7, R_t=101 from `decomposition_agg.json`. If confirmed,
the decomposition is independent of the F1 defect; F1-dependent side claims
(P_F1=81 context rows, "F2-F1=+13" checks, baseline-rank statements) are
classified separately.

**D. Stagewise findings.** Rule: predictive claims (stage AUC/PR-AUC,
lifts, prevalence, delta B-A, funnel counts) are judged only on their own OOF
evidence and are NOT withdrawn because of an unrelated selector defect.
Selection/ranking claims that read `baseline_rank`/`baseline_raw`
("count ranks positives better", "F2 outranks baseline on only 32.4%") are
recomputed under both directions by C5 and reclassified by what the data say.

**E. Earlier sequential experiments.** Rule: for A+C, REL-ask, tournament and
the round2 chain, the control is `kit.baseline_match` (or an exact replica)
unless bi1 shows otherwise; if the control is correct and runs are paired on
identical seed sets with a seed-level CI, the conclusion is preserved
regardless of the fixed-cardinality diagnostic defect.

## 7. Recomputation protocol (POST HOC integrity checks)

Every output in this section is labelled post hoc. No threshold, interval
convention or seed set changes.

Inputs: `round2_goal_rule/per_state_results.csv`, `selector_sets.jsonl`,
`evaluation.json`, `selector_summary.csv`; `round2_decision_ceiling/
day_edges.jsonl`, `oof_scores.jsonl`; `round2_missed_oracle/
selection_diagnostics.jsonl`, `positive_edge_ranks.csv`,
`decomposition_agg.json`; `round2_fixed_cardinality/selector_summary.csv`.

- **C1 totals:** per-arm positives summed over all 7,560 states
  (`corrected_totals.csv`); sum(k_t)=8,433; per-state selected count equals
  k_t for every arm.
- **C2 paired intervals** (`corrected_paired_ci.csv`): claim-relevant pairs
  (G2-G0, G2-G1m, G2-G1f, G3-G0, G3-G1m, G3-G1f, G4-G0, G4-G1m, G4-G1f,
  G1m-G0, G1f-G0, G5-G0, G5-G1m, G5-G1f). Unit: 21 seed groups; per-seed
  delta = sum over that seed's 6-variant states; statistic = mean over 21
  per-seed deltas; paired bootstrap resampling whole seed groups, B=2000,
  rng 4242, percentile 95% CI; positive/tied/negative seed counts; state
  W/T/L reported descriptively only.
- **C3 set structure** (`corrected_set_diffs.csv`): states where
  G0/G1f/G1m selections differ, pairwise; selected soft-match count sums per
  arm (counts taken from `day_edges.jsonl`); cardinality equality checks.
- **C4 headroom subset:** positives per arm on the 82 headroom states
  (flags from `selection_diagnostics.jsonl`), reproducing the published
  fixed-cardinality headroom row and the corrected G1m value.
- **C5 baseline-rank direction check** (`corrected_rank_direction.csv`):
  reproduce published mean F2 percentile (0.455), mean baseline percentile
  (0.388), F2-better share (0.324) and the missed/captured mean baseline
  ranks (2.34/4.38) from `positive_edge_ranks.csv`; recompute the baseline
  ranks from `day_edges.jsonl` with `competition_rank` applied to the stored
  counts (rank 1 = highest count, ties handled identically); report both
  frames side by side, the corrected F2-vs-baseline share, and the corrected
  mean count percentile of the 173 positives. This decides whether the
  "count ranks positives better" claims stand or invert.
- **C6 decomposition reproduction:** ranking/conflict/R_t/P_F2/P_F5 totals
  from `decomposition_agg.json` + `gap_decomposition` closure checks.
- **C7 reproduction of frozen published numbers** (must match exactly or the
  run stops): fc `selector_summary.csv` totals (81/94/85/85.25/161/90),
  fc published CIs as quoted in its report, goal_rule `evaluation.json`
  intervals for overlapping pairs, stagewise `ranking_by_stage.json` values
  cited in C5, mo P_F1=81 and F2-F1=+13.

**Statistical discipline** (request section 8): seed group is the independent
unit whenever six variants share a seed; no row/day/pair-level inference;
absolute performance is never compared across seed families (pipeline
100/800 worlds; A+C dev 101-106; promotion 107-118; REL 119-142; tournament
152-163; counterfactual 21 recorded seeds); descriptive point totals are
separated from intervals; F5/G5 and any label-aware arm remain local
hindsight, never deployable; greedy is never called optimal; a corrected
local diagnostic never establishes a full sequential policy improvement.

**Stop conditions:** any C1/C7 mismatch against a pre-registered target, or
any protected/prior-seal hash mismatch, halts the run for documentation -
numbers are never adjusted to fit expectations.

## 8. Score-convention audit checklist (request section 6)

Checked in bi1 (source) and bi4 (data), one verdict each:

1. Direction of every maximization objective incl. negation at the solver
   boundary (kit, n01, tournament, fc, mo, gr, policy).
2. Double-negation sites: `n01 -> s1 -> fc_selectors/mo_validate` and the
   suspected `mo_analyze` rank inversion (C5 decides impact).
3. Count score vs probability score misuse (F2/F3/F5 are OOF/label scores;
   F1/G1f/G1m are counts; A+C is a sigmoid model score).
4. Candidate eligibility and tie-breaking parity across baselines
   (kit sort key `(-score, canonical pair)`; solve_exact_k lex-smallest;
   F4-RANDOM R=100 seed 4242; sequential take-while-free vs global exact-k
   is a documented design difference, not a defect).
5. Unknown-value treatment (kit/n01/F1: match=1 only when both observed and
   equal, otherwise 0 - unknowns are neither matches nor penalties; G2: +1 /
   -0.5 / 0; model arms: learned soft-state features).
6. Cardinality parity (fixed-k arms must equal k_t per state; sequential
   arms are unconstrained by design and never compared as if fixed).
7. Seed-set pairing of every compared pair (same worlds, same seeds).
8. Metric/unit consistency: local counterfactual MSMI totals (this study,
   fc, mo, goal_rule) vs realized full-episode MSMI and MSMI/100 arrived
   members (official episodes) - never mixed within a comparison.
9. CI denominator/independent-unit conventions (seed-level everywhere;
   tournament seed-cluster 99% Bonferroni; stage2 18 (seed,variant) pairs
   clustered; any row-level CI found would be flagged).
10. Train/eval overlap: OOF-by-seed-group models, world-split audits -
    recorded per study from its own validation artifacts.
11. Pre-existing flagged items re-reported, not fixed: missed_oracle
    `n_captured=106` mislabel; hardcoded `positive_edges` in a checker;
    ceiling `run_log.txt` append; fc CC-01 zero-discrimination cardinality
    confound (already corrected inside fc's own report).

## 9. Evidence hierarchy protocol

`corrected_evidence_hierarchy.md`, four tiers, each entry carrying: original
claim (as published) + citation; corrected value if any; tier; whether the
overall research conclusion changes.

- **Supported:** correct implementation verdict, comparable design (paired,
  same metric/units, seed-level inference), reproducible from saved
  artifacts.
- **Supported only with qualifications:** correct but narrower estimand
  (local counterfactual, small seed count, particular baseline, descriptive
  totals only, cross-family caveats).
- **Withdraw or correct:** verified defect (reversed objective, inverted
  rank, cardinality confound, incomparable metric) that changes the number,
  direction or meaning of the claim.
- **Still unresolved:** cannot be answered from saved artifacts without new
  data or a preregistered experiment (new experiments are out of scope here).

## 10. Deliverables and run order

`analysis_plan.md` (+ `.sha256`), `study_audit.csv`,
`corrected_evidence_hierarchy.md`, `report.md` (answers the request's seven
final questions), `corrected_totals.csv`, `corrected_paired_ci.csv`,
`corrected_set_diffs.csv`, `corrected_rank_direction.csv`,
`source_facts.md`, `input_hashes.json`, `validation.json`, `run_log.txt`
(all commands + provenance), `integrity.sha256`, and scripts
`bi0_inventory.py`, `bi1_source_facts.py`, `bi2_recompute.py`,
`bi3_matrix.py`, `bi4_validate.py`, `bi5_report_check.py`, `bi_seal.py`,
`bi_verify.py` under `scripts/`.

Rerun order after any sanctioned edit: bi0 -> bi1 -> bi2 -> bi3 -> bi4 ->
(report/hierarchy authored) -> bi5 -> bi_seal -> bi_verify.

## 11. Amendments

(none at freeze)
