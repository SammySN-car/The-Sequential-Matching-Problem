# Round 2 Stagewise Reward - Experiment Plan and Protocol

Status: APPROVED by human partner (revision R1). Frozen before any experiment code runs. This file is frozen with its `.sha256` before any experiment
code runs (house convention, matching round2_fixed_cardinality / round2_goal_rule).
Implements the user brief "Round 2 Research Experiment: Stagewise Reward-Aware Matching vs Greedy"
(brief sections referenced as B.1-B.12).

## 0. Intent, hypothesis, boundaries

Hypothesis (B.Objective): at the same per-state cardinality as greedy, selecting the k feasible
non-conflicting pairs that maximise the summed predicted P(MSMI) yields higher realised MSMI per
100 arrived members in fresh full-sequential paired episodes.

In scope: randomised data collection -> stage-label derivation -> leakage-audited ~17-feature
stage models -> exact-k solver verification -> offline ranking diagnostics -> one pre-registered
paired final evaluation -> report with exactly one decision.

Anti-goals (explicit): no modification of policy.py / kit.py / evaluate.py / Dockerfile /
requirements.txt or any existing behaviour; no git-mutating commands; no promotion of the
candidate to default; no second rollout campaign after the final evaluation; no tuning against
the final evaluation set; report and stop for review.

## 1. Reconnaissance - verified prerequisites (B.1)

| # | Prerequisite | Verdict | Evidence (this session) |
|---|---|---|---|
| R1 | policy.py defaults to stock greedy | PASS | policy.py L14 `decide(request, mode='greedy')`; ask path -> `kit.baseline_asks` (L24); match path -> `kit.baseline_match` (L28); argparse default greedy (L602-603) |
| R2 | evaluate.py runs a standalone policy | PASS | L136 `--policy`; L147 command = `[sys.executable, args.policy, '--baseline', <mode>]`; stdin/stdout JSON `{phase: ask|match, state, memory}` -> `{asks|pairs, memory}`; 10 s per invoke (L45-61); 1 MiB request/response/memory limits (L17, L32, L65); response shape validated (L26-42) |
| R3 | stdlib-only runtime, no new deps | PASS | requirements.txt "No packages to install"; kit.py L1; candidate inference must be stdlib. Research-side numpy 2.3.2 already installed (32 prior research scripts import it) - reused for bootstrap/CI and training only; nothing is installed |
| R4 | previous fixed-cardinality solver available, correct, deployable | PASS (re-verified by battery S.8) | research/round2_fixed_cardinality/scripts/fc_matching.py: stdlib exact-k branch-and-bound, lexicographically smallest optimum (deterministic), explicit failure on node limit; solver_validation.json `passed: true` - 12,310 synthetic brute-force checks 0 disagreements; 7,489 real states x 4 arms 0 disagreements; over all 7,560 real states never worse than greedy (better 1,228 / equal 6,332 / worse 0), node_limit 0, max_nodes 2,101 vs limit 8,000,000 |
| R5 | prior cf_* counterfactual columns not used as labels for never-introduced pairs | PASS by construction | this pipeline creates exactly one row per actually assigned introduction (S.4/S.5); cf_* columns are never read; assertion T-LAB-1: n_rows == n_introductions |
| R6 | repository state unchanged | PASS | bi_verify re-run this session: own seal (25 files), 7 prior seals / 207 entries, 9 protected files unchanged, frozen plan e04280fc..., bi4 25/25, bi5 36/36 - ALL PASS |
| R7 | prior studies read | PASS | round2_fixed_cardinality, round2_goal_rule, round2_missed_oracle, round2_stagewise_signal, round2_baseline_integrity read during the baseline-integrity audit; seals re-verified by R6. Reusable assets: fc solver + tests, gr/fc bootstrap CI convention, n01 counterfactual funnel (never used as labels here) |
| R8 | fresh, disjoint seed ranges | PASS | historical research seeds: 101-106, 107-118, 119-142, 143-163, 301-312, 50000-50799 (800-world family), 90210, 90250-90251. Grep confirms 40001-40500 and 70001-70100 unused anywhere in research/ |

To be measured, not assumed (pilots S.3): wall-clock per episode (in-process vs subprocess
modes), solver wall-time on live dense states, memory, per-call inference time.

## 2. Outcome definition and label maturity - derived from kit.py, not assumed (B.2)

Official episode = 60 ask/match days + 40 empty advances (evaluate.py L85-101). Official MSMI is
computed by `Simulator.metrics()` (kit.py L190-203) over feedback observed by the final day.

For an introduction assigned at simulation day d (response_deadline_day = d+7, kit.py L156):

- **Stage 1 - mutual acceptance.** Two `introduction_response` events exist for every intro.
  Responding: delay = randint(1,7) (L161); a non-response is recorded as an event with
  `value=None, missing_reason='no_response', observed_day=d+7` (L162-166) - censoring is an
  explicit deadline event, never a missing row. Target 1 iff both values are 'yes' (L194).
  Label mature by **d+7**.
- **Stage 2 - timely first date.** The `date_happened` event exists only when both responded AND
  both accepted (L168). Its `occurred_day = observed_day = date_day` where
  `date_day = max(response_days) + randint(1,14)`, plus `randint(5,12)` in the `delayed` variant
  (L169-173); `value` True with probability .78, else False (the date is cancelled). MSMI requires
  `date_day - d <= 30` - **inclusive of day 30** (L197). Target: population = Stage-1 positives;
  1 iff event value True and date_day <= d+30, else 0 (0 is decidable at date_day itself).
  Latest determining day: d+7+14+12 = **d+33** (delayed variant).
- **Stage 3 - timely mutual second yes.** Population = timely-date intros. Two
  `second_meeting_intention` events (L181-183); response delay randint(1,5); non-response observed
  at date_day+5 with `value=None` (L183). Target 1 iff both values 'yes' AND each
  `occurred_day - date_day <= 3` - **inclusive of day 3** (L197). Mature by date_day+5 <= **d+35**.
- **Final MSMI label** = Stage1 AND Stage2 AND Stage3, exactly matching L197 (date event present,
  date <= 30 days, both second-yes within <= 3 days).
- **Maturity proof within 60+40.** Last assignment d=59 -> all labels decidable by 59+35 = 94,
  before the post-follow-up day 100. No hard-coded guess: the constants (7, 30, 3, 5, delayed 33)
  come from the cited lines. **Empirical gate T-MAT-1** (pilot): for every intro, the last
  relevant event observed_day <= 99, and the offline label extraction reproduces
  `metrics()` counts (mutual / dates / msmi) exactly. Any mismatch -> STOP (B.11).
- **Official denominator and metric.** `arrived_members` = members with arrived_day <= 59
  (evaluate.py L98-99); primary score = 100 x msmi / max(1, arrived) per episode (L109);
  `summarise()` (L118-131) equal-weights the six variants -> this is the B.10 primary metric.

## 3. Plumbing pilot before any scaling (B.3)

Seed group **40001** x all six variants (never reused for fitting or final evaluation).

- P1 Official greedy reference: `evaluate.py --seeds 40001 --variants all --output
  results/pilot_greedy_official.json` (default policy.py). Record action_sha256 + metrics per episode.
- P2 Adapter parity: same seeds via `--policy research/round2_stagewise_reward/policy_parity.py`.
  Required: action_sha256 identical to P1 for all 6 episodes (asks = baseline_asks, pairs =
  baseline_match, identical order; policy_parity.py shares its I/O core with policy_candidate.py,
  so parity also proves the candidate's protocol scaffolding).
- P3 Randomised collection (in-process kit.Simulator) on the same 6 worlds: write-once
  decision-time snapshots (+sha256), per-state coverage records; run the full 60+40 episode, then
  join labels offline; assert T-LAB-* and T-MAT-1.
- P4 Deterministic replay: repeat P3 -> snapshot and label files byte-identical (same hashes).
- P5 Protocol smoke of the shared core via policy_parity.py: memory pass-through, response shape,
  limits honoured (model-dependent candidate smoke happens after the S.7 freeze, gate S.8-V6).
- P6 Measurements: wall-time per episode for in-process collection vs evaluate.py subprocess
  mode; rows and positives per stage; file sizes and peak Python memory (tracemalloc);
  per-call inference time (must be far below the 10 s limit).

Pilot data are used only for pipeline debugging and timing - never for fitting, never presented
as final-evaluation evidence.

**Data-quality pilot** (separate): seeds 40002-40011 (10 groups x 6 variants) through the same
collection pipeline. Pass gate to scale up: at the largest runtime-feasible N in [300, 499]
(projected from measured wall-clock), projected Stage-3 positives >= 150 (fit gates S.7).
Otherwise report the shortfall rather than forcing a fit (B.5/B.11).

## 4. Training-data generation (B.4)

- **Range and size.** Seeds 40002-40500, each x six variants (max 499 groups). Predeclared sizing
  rule: after the quality pilot choose N = largest value in [300, 499] whose projected
  collection+label wall time <= 4 h (measured, not assumed); the exact achieved N is reported
  (never claim 300-500 if fewer ran).
- **Worlds.** `kit.generate(seed, 200, 'evaluation', variant)` - identical construction to
  evaluate.py L152.
- **Collection policy.** Asks: `kit.baseline_asks` unchanged (same budget and order as greedy).
  Pair selection: build the same feasible graph as `baseline_match` (available members,
  `eligibility(...)['status']=='feasible'`, not in `past`), assign each edge a priority draw
  `random.Random(kit.rand_for(seed, variant, day, 'collect')).random()`, take edges in descending
  priority applying the baseline disjointness rule (first-come, skip conflicts) - a randomised
  maximal matching with the same maximal-greedy structure as the baseline. Infeasible, repeat or
  overlapping pairs are never introduced (any `advance` raise = logged episode failure).
- **Selection probabilities.** Marginal inclusion probabilities of a maximal matching are not
  exactly computable, so none are claimed. Instead every candidate edge of every state records its
  uniform priority draw; with the frozen collection code the selection rule is exactly
  reconstructible offline (B.4 "only where they can be computed correctly").
- **Per-state records.** Seed group, variant, day, available-member count, feasible-edge count,
  greedy-k (reference count from baseline_match on the same state), chosen k, edge priorities,
  RNG configuration.
- **Coverage actually measured.** Over all decision states: sum of feasible (state, edge)
  opportunities; distinct pairs introduced; share of opportunities ever introduced; introduction
  count per member; edges-per-state distribution. Actual numbers reported, never assumed.
- **Row definition.** Exactly one training row per assigned introduction: unique introduction id;
  metadata (world / seed group / variant / day / both member ids); frozen feature snapshot taken
  from the observe() state immediately before assignment; stage + final labels joined only after
  the episode completes and maturity checks pass. No rows for never-introduced pairs (T-LAB-1).

## 5. Stage targets (B.5)

Three conditional targets, trained only on their eligible populations; `UNKNOWN` stored and
excluded from the supervised target; exclusion counts reported per stage.

- Stage 1 population: every actual introduction whose initial-response label matured (all, by d+7).
- Stage 2 population: Stage-1 positives only; timely date within <= 30 days (inclusive).
- Stage 3 population: timely-date intros only; both second-yes within <= 3 days (inclusive).
- Final MSMI label: joined for calibration/diagnostics only, never a training target of a stage model.

Combined estimate: P(MSMI) = P(S1) x P(S2|S1) x P(S3|S1,S2) - a conditional factorisation, not an
independence assumption. The combined probability is validated directly against observed mature
MSMI outcomes (reliability table + mean predicted vs observed, S.7/S.9).

## 6. Feature set and integrity audit (B.6)

Exactly 17 predeclared numeric features, computed by `extract_pair_features(state, day)` whose only
input is an `observe()` dict plus a feasible-degree table computed from that same dict. For a
feasible pair every HARD field of both members is observed (eligibility requires it, kit.py
L76/L87), so no HARD-derived feature can be silently missing on the training population.

| # | feature | computation (observe()-only) | class |
|---|---|---|---|
| 1 | age_diff | abs(a.age - b.age) | LEGAL OBSERVABLE |
| 2 | age_slack | min over both directions of min(partner.age - age_min, age_max - partner.age), from observed fields | LEGAL OBSERVABLE |
| 3 | gender_fit_ab | 1 if b.gender in a.fields['who_to_meet'] | LEGAL OBSERVABLE |
| 4 | gender_fit_ba | 1 if a.gender in b.fields['who_to_meet'] | LEGAL OBSERVABLE |
| 5 | zone_common | len(set(a.acceptable_zones) & set(b.acceptable_zones)) | LEGAL OBSERVABLE |
| 6 | schedule_overlap | len(set(a.schedule) & set(b.schedule)) | LEGAL OBSERVABLE |
| 7 | arrival_diff | abs(a.arrived_day - b.arrived_day) | LEGAL OBSERVABLE |
| 8 | soft_equal | count of SOFT fields both observed and equal (greedy's own score) | LEGAL OBSERVABLE |
| 9 | soft_differ | count of SOFT fields both observed and unequal | LEGAL OBSERVABLE |
| 10 | soft_missing | count of SOFT fields unobserved for either member | LEGAL OBSERVABLE |
| 11 | soft_declined | count of SOFT fields with field_status=='declined' for either member | LEGAL OBSERVABLE |
| 12 | goal_agree | 1 if both relationship_goal observed and equal, else 0 | LEGAL OBSERVABLE |
| 13 | prev_intros_mean | mean over the two members of past introduction counts (state['introductions']) | LEGAL OBSERVABLE |
| 14 | hist_yes | count of feedback events (state['feedback'], observed_day <= day) with positive value involving a or b: response 'yes' / date True / second 'yes' | LEGAL OBSERVABLE |
| 15 | current_day | state['day'] | LEGAL OBSERVABLE |
| 16 | degree_a | number of feasible candidate partners member a has in the current state graph | STRUCTURE-INFORMED |
| 17 | degree_b | same for member b | STRUCTURE-INFORMED |

Rejected outright, never read by any code in this directory: `truth`, `bias`, `second_bias`,
`response_rate`, `exit_day`, `seed`, `variant` (as features), `sim.events` / anything beyond
`state['feedback']`, `field_observed_day` values > decision day, member records not visible in
observe() (arrived later), final member state, episode/final aggregates, `cf_*` columns,
counterfactual outcomes of never-introduced pairs.

Audit and regression tests (runner writes results/feature_audit.json):
- T-FEA-1 machine-readable table: feature name, source expression, decision-time legality, class.
  Every model feature must classify as LEGAL OBSERVABLE or STRUCTURE-INFORMED. Any POTENTIAL
  LEAKAGE or ILLEGAL -> STOP before training (B.6/B.11).
- T-FEA-2 scrub test: remove truth/bias/second_bias/response_rate/exit_day/seed/variant from the
  extractor input -> output bit-identical.
- T-FEA-3 late-field test: a SOFT field unobserved at day d must appear as missing in the frozen
  snapshot; after an ask resolves it at d+1 a fresh extraction observes it while the frozen
  snapshot bytes remain unchanged (write-once hash).
- T-FEA-4 feedback horizon: extractor asserts no observed_day > decision day enters any feature.

## 7. Model training and freeze (B.7)

- Three L2-regularised logistic regressions (populations S.5). Training: numpy IRLS, features
  standardised with fit-split statistics only, lambda = 1.0 fixed on non-bias terms, deterministic,
  no hyperparameter search, no resampling or class weighting (natural prevalence preserved).
  Inference in the policy is pure stdlib (weights + means + stds from the frozen JSON).
- Split by whole seed group: sorted training seeds -> first 80% fit, last 20% calibration/validation;
  all six variants of a group stay together; no group in both partitions (assertion).
- Fit gates (predeclared, reported honestly): a stage is fit only if its fit split has >= 100
  positives AND >= 100 negatives AND events-per-variable >= 5 (17 features). Failing a gate ->
  report the stage as failed rather than forcing a fit; a failed stage blocks building P(MSMI),
  which blocks the candidate (decision STOP / PROCEED WITH CHANGES per evidence).
- Metrics (prediction diagnostics only): PR-AUC, ROC-AUC, log loss, calibration reliability
  bins, prevalence, constant-prevalence baseline - reported per stage and for the combined
  P(MSMI) against final MSMI; train-vs-val feature distributions. No accuracy claims, no policy
  claims (B.9 distinction prediction vs decision value).
- Freeze: results/model_artifact.json = feature order, per-stage weights and bias, standardisation
  constants, stage definitions, plan hash, kit hash; frozen with .sha256 and logged before any
  S.8/S.9/S.10 execution. Nothing changes after unblinding (B.11).

## 8. Solver verification (B.8)

Reuse `solve_exact_k` from research/round2_fixed_cardinality/scripts/fc_matching.py by path
import (read-only; fc files untouched; provenance R4). Battery (scripts/sr_solver_test.py ->
results/solver_validation.json):

- V1 Brute force: 2,000 fresh random small graphs (rng 4242) vs exhaustive enumeration; plus
  re-running fc's own V-SOLV suite as provenance evidence.
- V2 Determinism: repeated solves return identical matchings (lexicographically smallest optimum
  is the documented tie-break).
- V3 Exactness on live states: every pilot match-phase state - |M| == greedy-k, no duplicated
  member, no infeasible pair (cross-checked with kit.eligibility), no past pair.
- V4 Dense-state timing: worst states by edge count from pilot worlds (including day-0 states).
  Gates: wall-time max < 3.0 s, zero node-limit failures (8,000,000 nodes). Failure -> STOP,
  no approximation substitute (B.8/B.11).
- V5 Weighted objective: states with <= 14 edges compared against brute-force optimum.
- V6 Candidate live smoke (after model freeze): policy_candidate.py through evaluate.py on the
  6 pilot episodes - valid episodes, zero invalid actions/timeouts, per-state chosen count ==
  greedy-k for every decision state, solver fallback count 0, inference time per call logged.

Live fallback (documented, not silent): should solve_exact_k report failure in a live episode,
that state falls back to greedy's own k pairs and the event is logged. Any fallback during the
final evaluation is reported prominently and prevents a PROCEED decision.

The optimisation implemented is exactly B.8: maximise sum P_hat over feasible disjoint pairs
subject to |M| == k - never a sort-by-score-and-take-first heuristic (which can stall below k).

## 9. Offline ranking on observed populations (B.9)

On validation-group episodes only, using genuinely observed outcomes:

- Stagewise and final-MSMI predictive metrics (as S.7), reported separately.
- Training vs validation feature distributions (mean/std drift; share of validation values
  outside the fit-split min/max box, per feature and all-features-combined).
- Feasible-candidate score distributions: P_hat over all feasible edges of validation states;
  discrimination frequency = share of states where max P_hat - min P_hat >= 0.02;
  share of validation feasible edges never represented by any introduced training pair.
- Within-state ranking computed only for states with >= 2 introduced pairs (predicted order vs
  realised outcome order), with the selection bias stated in prose: outcomes exist only for
  introduced pairs; no top-k accuracy claim over all feasible pairs; no counterfactual labels.

## 10. Fresh paired full-sequential evaluation (B.10)

- **Seeds 70001-70100** (100 seed groups x 6 variants), entirely fresh: not used for fitting,
  calibration, feature selection, policy development, or pilots; disjoint from every historical
  research seed family (R8). Frozen before any result is seen.
- **Arms on identical (seed, variant) combos.** Arm G: official greedy -
  `evaluate.py --seeds ... --variants all` with default policy.py. Arm C:
  `evaluate.py --policy research/round2_stagewise_reward/policy_candidate.py --seeds ... --variants all`.
  Chunked invocations (10 seeds per call, separate output files) aggregated afterwards; episodes
  are independent across seeds, so chunking changes nothing statistically.
- **Precision estimate and frozen N.** Paired seed-group variability from existing studies:
  e3 seed-level CI half-width 0.062 at n=24 -> sd ~= 0.155; tournament seed-cluster 99% CI
  half-width 0.087 at n=12 -> sd ~= 0.117. Conservative sd = 0.15 gives an expected 95% CI
  half-width at N=100 of 1.96 x 0.15 / sqrt(100) = +/- 0.030 MSMI per 100 arrived (around a
  realised mean near 0.4). This is the sample-size justification; N=100 is frozen - no selective
  extension, no re-runs after inspecting outcomes. Known limitation: effects below ~0.03
  per-100-arrived will not be statistically distinguishable from zero; the study is sized to
  detect effects of roughly the size of e3's arm difference (+8% relative, ~+0.03 absolute) only
  at the boundary - the report states this explicitly.
- **Pre-unblinding checks.** Greedy parity (P2 protocol + re-check arm-G digests on the 70001
  chunk vs policy_parity.py); all episodes valid; zero invalid actions; arm-C per-state chosen
  count == greedy-k for every match phase (instrumented log; episode totals are NOT required to
  match - earlier assignments change later states, as B.10 allows); training/eval seed lists
  asserted disjoint; no training information reaches the policy process except the frozen
  model_artifact.json.
- **Primary metric (official).** Realised MSMI per 100 arrived members, equal-weighted across the
  six variants (evaluate.py summarise, L118-131).
- **Statistics - seed group is the unit.** Per group g: score(g, arm) = mean over the six
  variants of msmi_per_100; diff(g) = score_C - score_G. Report: greedy mean, candidate mean,
  mean paired diff with 95% CI = percentile bootstrap (B=2000, np.random.default_rng(4242),
  linear percentiles - the gr/fc house convention), win/tie/loss counts (|diff| <= 1e-12 =
  tie), per-variant paired means and CIs, arrived/introduction/MSMI/mutual/date counts,
  runtime (sum inference_seconds), invalid actions, crashes, episode failures. Same-seed
  episodes are never treated as independent units; no success claim from pooled totals, AUC,
  oracle comparisons or a single seed.

## 11. Stop conditions - concrete triggers (B.11)

STOP before scaling or before the final evaluation if ANY of:

- T-FEA-1..4 fail (illegal/unverifiable feature, scrub mismatch, snapshot mutation, future horizon);
- any never-introduced pair labelled negative (T-LAB-1 row-count invariant) or any cf_* use;
- T-MAT-1 fails (maturity derivation or label/metrics mismatch);
- collection or inference reads anything outside observe() (design + scrub test);
- solver battery V1-V5 fails, or V4 dense timing gates fail (solver not deployable);
- greedy parity P2 fails (digest mismatch);
- protocol breach: invalid action, invocation timeout, memory > 1 MiB, non-JSON response.

Weak out-of-sample signal (validation final-MSMI PR-AUC <= prevalence baseline, or ROC-AUC CI
including 0.5): reported as a finding; the frozen pre-registered evaluation still runs ONLY if
every integrity gate above passed - there is no tuning, no added features, no re-run afterwards.
If offline prediction improves but realised sequential MSMIs do not, the report separates
prediction quality from decision value (B.11). Any solver fallback > 0 in arm C, any invalid
episode, or any parity re-check failure during the final evaluation forces the decision below
STOP / REDESIGN or PROCEED WITH CHANGES - never PROCEED.

## 12. Deliverables and layout (B.12)

research/round2_stagewise_reward/
  analysis_plan.md (+ .sha256)                    this frozen plan and protocol
  sr_policy_core.py                               shared stdin/stdout adapter core (stdlib)
  policy_parity.py                                greedy-delegation policy (parity tests)
  policy_candidate.py                             candidate policy (frozen model + exact-k solver)
  scripts/sr_collect.py                           randomised collection (in-process simulator)
  scripts/sr_label.py                             offline labelling + maturity checks
  scripts/sr_features.py                          feature extractor + audit + T-FEA tests
  scripts/sr_train.py                             stage models + metrics + freeze
  scripts/sr_solver_test.py                       solver battery V1-V5
  scripts/sr_offline_rank.py                      S.9 diagnostics
  scripts/sr_eval_run.py                          chunked paired evaluation driver
  scripts/sr_eval_aggregate.py                    seed-group paired statistics
  scripts/sr_verify.py                            final integrity gate (seals, hashes, disjointness)
  results/                                        machine-readable outputs (pilot_*.json,
                                                  feature_audit.json, solver_validation.json,
                                                  offline_ranking.json, model_artifact.json,
                                                  evaluation_*.json, paired_stats.json)
  data/                                           snapshots/, labels/, coverage_stats.json (+hashes)
  report.md                                       answers the 10 brief questions + exactly one
                                                  decision: PROCEED / PROCEED WITH CHANGES / STOP / REDESIGN
  run_log.txt                                     exact commands with timestamps (house convention)
  integrity.sha256                               final seal over this directory

Exact run commands are appended to run_log.txt at execution time. The report does not promote the
candidate, does not claim competition readiness, and stops for review after the single decision.

## 13. Seed and RNG registry

| purpose | seeds / stream | notes |
|---|---|---|
| plumbing pilot | 40001 | excluded from fitting and final evaluation |
| quality pilot + training | 40002-40500 (N per S.4 rule) | quality-pilot groups join training (no model existed yet) |
| final evaluation | 70001-70100 (frozen) | untouched until S.10 |
| collection RNG | kit.rand_for(seed, variant, day, 'collect') priority draws | deterministic, reconstructible |
| bootstrap | np.random.default_rng(4242), B=2000, linear percentiles | house convention (gr/fc) |
| solver tests | rng 4242 | fresh graphs |

Historical families never reused: 101-106, 107-118, 119-142, 143-163, 301-312, 50000-50799,
90210, 90250-90251.

## 14. Execution order

1. Freeze this plan (sha256) -> S.3 pilots (P1-P6) -> quality pilot -> choose N.
2. S.4 collection -> S.5 labels -> S.6 audit gate (stop conditions apply here).
3. S.7 train + freeze model_artifact.json.
4. S.8 solver battery (V1-V5 may run earlier; V6 after freeze) -> must pass before S.10.
5. S.9 offline ranking report (rank results reported before policy evaluation, B.7/B.9).
6. S.10 final paired evaluation (N=100 frozen) -> S.10 statistics.
7. report.md with exactly one decision -> STOP for review. No further rollouts.

All gates are decided before arm-C outcomes are inspected; nothing changes after unblinding.

## 15. Revision R1 - builder-check resolutions

A fresh reviewer subagent read this plan (pre-R1) plus kit.py / evaluate.py / fc_matching.py and
raised five questions. All five are resolved below; sections above stay as written except where
this revision amends them. The .sha256 is regenerated for the amended file.

### R1.1 Decision matrix (amends S.11; answers "which evidence -> which decision")

Rules are applied in order; exactly one decision is emitted in report.md.

1. Any integrity stop-condition (S.11 list) fires at any point -> **STOP / REDESIGN**.
2. Solver not deployable (V4 gates fail) or greedy parity fails -> **STOP / REDESIGN**.
3. All gates pass AND the primary paired 95% CI for candidate-minus-greedy lies entirely above
   zero -> **PROCEED** ("robust improvement in actual sequential MSMIs demonstrated").
4. All gates pass AND the mean paired difference is positive but the CI includes zero, AND the
   report names one specific evidence-backed limitation that plausibly diluted the effect
   (e.g. solver fallback occurred, >2 seed groups dropped, a variant shows a consistent
   mechanism-level harm worth one controlled re-test) -> **PROCEED WITH CHANGES** ("a specific
   limitation warrants another controlled test"), with the follow-up test named precisely.
5. Otherwise (mean <= 0, or CI includes zero with no fixable limitation) -> **STOP / REDESIGN**
   ("the hypothesis has insufficient evidence to justify further investment" - at the frozen
   power of N=100 / +/-0.03 half-width, this includes a genuinely small positive effect that
   cannot be confirmed without a larger campaign, which this experiment may not launch).

Weak offline signal (validation metrics <= prevalence baseline) co-reported as context; it does
not by itself pick a rule - the paired evaluation is the decision driver once integrity passed.

### R1.2 Compute budget and parallelism (amends S.4 sizing rule)

Data collection and final-evaluation invocations may run in parallel using the standard library
only (multiprocessing), with W = min(8, os.cpu_count()) workers, fixed and recorded in the run
log before the run starts (precedent: research/run_experiment.py --workers 12). The 4-hour cap
for collection is wall-clock at W workers, with per-episode time re-measured under full worker
contention. The N sizing rule is unchanged: largest N in [300, 499] fitting the 4h wall-clock
budget at W workers. S.10 wall-clock is estimated from pilot subprocess measurements at W
workers and reported alongside the actual time.

### R1.3 Validation-state persistence for S.9 (amends S.4 records)

Per-state records keep counts/priorities for ALL training groups as before. In addition, for
validation-group episodes only, the collector persists the full feasible-edge set per match
state with the frozen 17-feature vector for every edge:
data/feasible_edges_val.jsonl (one line per edge: seed group, variant, day, pair, features).
Observed edge counts in prior studies are small (~2-15 feasible edges per state), so this file
is tens of MB. S.9 computes P_hat score distributions, discrimination frequency and the
never-introduced share directly from this file plus the frozen model - deterministic replay
(P4) remains a pipeline-correctness check, not a dependency of S.9.

### R1.4 Episode failure policy for the final evaluation (amends S.10/S.11)

- Infrastructure failure (harness timeout, crash, malformed JSON - a valid:false row not caused
  by a protocol violation): re-run that exact episode once, identically; log both attempts.
  If the second attempt also fails, drop the ENTIRE seed group from both arms (pairwise
  deletion) and report it. Dropped groups are listed in report.md; more than 5 dropped groups
  forbids PROCEED (they become a rule-4 limitation candidate).
- Policy-caused protocol violation (invalid action, memory breach, non-deterministic replay of
  a frozen component): no retry, no deletion - S.11 STOP applies immediately.
- The primary paired statistic, CI and win/tie/loss are computed only over seed groups where
  all 12 episodes (6 variants x 2 arms) are valid. The official evaluate.py summarise outputs
  are still reported verbatim per chunk.

### R1.5 Instrumentation evidence channel (amends S.8-V6/S.10)

policy_candidate.py cannot print anything besides the response JSON, and evaluate.py does not
surface memory. Evidence for per-state cardinality preservation is therefore a side-effect
JSONL file (trusted-local mode): each policy invocation appends one line to
results/instrumentation/<pid>.jsonl (directory passed via env var SR_INSTRUMENTATION_DIR; when
the variable is absent - e.g. parity runs - the policy writes nothing):
{day, phase, n_available, n_edges, k_greedy, k_chosen, solver_nodes, solver_fallback, seconds}.
The in-policy assertion k_chosen == k_greedy fires on every match phase; sr_verify.py
aggregates all instrumentation files into results/cardinality_check.json (state count,
mismatches, fallbacks, timing percentiles). This is the audit artifact for S.10's
"exact greedy cardinality per decision state" requirement.

