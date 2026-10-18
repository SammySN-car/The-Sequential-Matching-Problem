# Fixed-Cardinality Counterfactual Decision Audit — Analysis Plan
#
# STATUS: FROZEN BEFORE ANY COMPARISON IS COMPUTED.
# This file is written before the selector comparison is run. Corrections after
# freezing are only permitted as an appended "## Amendment" block recording the
# reason, with a matching run_log.txt entry. Never silently edited.
#
# ============================================================================
# 0. Objective and scope
# ============================================================================
#
# Narrow question:
#
#   When the number of introductions is held constant at greedy's own daily
#   cardinality k_t, can legal observable information select pairs with better
#   counterfactual MSMI outcomes than the existing greedy policy?
#
# This is a DIAGNOSTIC study over already-recorded decision states. It is NOT a
# policy tournament, NOT a sequential-policy evaluation, and NOT a deployment
# recommendation. The deployed policy is not modified.
#
# The specific motivation is the round-2 ceiling audit finding that a
# zero-discrimination control (audit feature set F5_state_only) appeared to
# "beat" greedy on 55 of 82 headroom states despite having exactly chance
# within-state discrimination. The leading hypothesis, to be tested here, is
# that this was a CARDINALITY confound: the audit's decision-relevance statistic
# maximised total score over ALL matchings (size 0..max), so a flat score breaks
# ties toward LARGE matchings, and a larger matching mechanically contains more
# MSMI positives without any improvement in pair ranking.
#
# ============================================================================
# 1. Data sources (all read-only)
# ============================================================================
#
# Directory A (frozen prior audit): research/round2_decision_ceiling/
#   day_edges.jsonl           - 7,560 recorded (seed, variant, day) states with
#                               the exact feasible edge list, day context,
#                               structural metrics, and greedy's own selected
#                               pair list `pairs`.
#   counterfactual_pairs.jsonl- 15,304 feasible (state, pair) rows carrying
#                               cf_y_msmi, the validated counterfactual label.
#   oof_scores.jsonl          - 15,304 rows with out-of-fold scores for the
#                               audit's five feature sets, held out BY SEED
#                               GROUP (all six variants of a seed share a fold).
#   oracle_by_day.jsonl       - 7,560 rows with local_gap, batch_size,
#                               max_matching_size, maxcard_positives.
#   source_validation.json    - written by fc_validate.py in directory B.
#
# Directory B (new): research/round2_fixed_cardinality/
#
# No file in directory A is modified. No git-mutating command is used. No new
# world seed is generated and no rollout tournament is run.
#
# ============================================================================
# 2. Source-data validation gate (prerequisite; PASS before any computation)
# ============================================================================
#
# Implemented in scripts/fc_validate.py. All of the following must hold:
#
#   V-SRC-01  Prior integrity.sha256 still current (0 stale entries).
#   V-SRC-02  7,560 recorded states present.
#   V-SRC-03  counterfactual_pairs.jsonl has 15,304 rows.
#   V-SRC-04  Every feasible edge of every state has a cf_y_msmi label.
#   V-SRC-05  Greedy's selected pairs are a subset of that day's feasible graph.
#   V-SRC-06  Greedy's selected pairs are vertex-disjoint.
#   V-SRC-07  Exact-k_t matching is always feasible (greedy's own set is a
#             constructive witness, so infeasibility is impossible).
#   V-SRC-08  oof_scores.jsonl has 15,304 rows.
#   V-SRC-09  Every feasible edge has an out-of-fold score row.
#   V-SRC-10  oof y agrees with cf_y_msmi on all 15,304 edges.
#   V-SRC-11  Exactly 82 states have local_gap >= 1.
#   V-SRC-12  oracle_by_day covers all 7,560 states.
#   V-SRC-13  oracle batch_size equals greedy k_t on every state.
#   V-SRC-14  21 seed groups.
#   V-SRC-15  6 variants.
#   V-SRC-16  Every seed group contains all 6 variants.
#
# Any failure STOPS the affected comparison and is reported as a discrepancy.
# Actual observed result: 16/16 PASS.
#
# ============================================================================
# 3. Notation and estimands
# ============================================================================
#
# A state t is a tuple (seed, variant, day). G_t = (V_t, E_t) is the exact
# feasible graph recorded for t, with |E_t| = n_t. k_t = |greedy(t)|, the number
# of pairs the original greedy policy actually introduced on that state.
#
# For a matching M subset of E_t with |M| = k_t, define
#
#     Y(M) = sum over (a,b) in M of cf_y_msmi(a, b, t)      [0/1 MSMI positives]
#
# PRIMARY ESTIMAND (selection quality at fixed volume):
#
#     Delta_s = (1/|T|) * sum over t in T of [ Y(M_s(t)) - Y(M_greedy(t)) ]
#
# for selector s, over the state set T. Because every arm selects exactly k_t
# pairs on the same recorded states, Delta_s is a pure PAIR-SELECTION effect and
# contains no volume component by construction.
#
# SECONDARY ESTIMANDS:
#   - State-level win/tie/loss counts and fractions, per selector.
#   - Number and fraction of states whose selected SET differs from greedy's.
#   - Number and fraction of states whose counterfactual MSMI COUNT differs.
#   - The same quantities restricted to the 82 headroom states, and separately
#     to the remaining 7,478 states.
#   - Per-variant and per-day-band breakdowns.
#   - The VOLUME control: max_matching_size and maxcard_positives, reported
#     separately and never counted as a quality gain.
#
# VOLUME-ADJUSTED RATE ESTIMAND (reported for completeness, not primary):
#
#     R_s = (sum_t Y(M_s(t))) / (sum_t k_t)
#
# because all arms share the denominator sum_t k_t exactly.
#
# ============================================================================
# 4. The exact-cardinality matching solver
# ============================================================================
#
# Problem statement (EXACT-k max-weight matching):
#
#     Given edges E with weights w, and integer k, find a vertex-disjoint set
#     M subset of E with |M| = k maximising sum of w over M.
#
# Reference implementation: scripts/fc_matching.py, function
# solve_exact_k(edges, weights, k).
#
# Algorithm: depth-first branch and bound over edges sorted by descending
# weight, with lexicographic tie-break.
#   - Include-exclude branching over edge index.
#   - Size prune: current_size + (n_edges - idx) < k  =>  abandon (cannot reach
#     exactly k).
#   - Weight prune: current_weight + prefix_bound[k - current_size] <= best =>
#     abandon, where prefix_bound[j] is the sum of the j largest weights among
#     the remaining edges. This is a valid upper bound on achievable additional
#     weight.
#   - Tie-break: among all optimum matchings of size exactly k, return the
#     lexicographically smallest under the canonical edge ordering, so the
#     result is deterministic under identical inputs.
#   - A node_limit is enforced; breaching it sets a failure flag. A failed
#     solve is REPORTED, never silently downgraded to a smaller matching.
#
# VALIDATION OF THE SOLVER (required before any selector result is trusted):
#
#   V-SOLV-01  Brute-force agreement. For every state with n_edges <= 16,
#              compare solve_exact_k against exhaustive enumeration of all
#              2^n edge subsets. Require exact agreement on both the optimum
#              objective value and the size constraint, for all weightings
#              used by the study.
#   V-SOLV-02  Constraint satisfaction. Every returned matching must have
#              exactly k pairs, use only feasible edges, and contain no repeated
#              member on either side.
#   V-SOLV-03  Determinism. Re-running a state must return a bit-identical
#              matching.
#   V-SOLV-04  Witness consistency. The solver must reproduce greedy's own
#              objective value when greedy's set is itself optimal; where
#              greedy is NOT optimal the solver must return a value at least as
#              large, never smaller.
#   V-SOLV-05  Networkx cross-check on the max-cardinality special case where
#              available.
#
# If any required matching is infeasible or unvalidated, that failure is
# reported and the affected arm is marked unavailable. Cardinality is NEVER
# silently relaxed.
#
# ============================================================================
# 5. The six arms
# ============================================================================
#
# NOTE ON NAMES. The round-2 ceiling audit labelled its FEATURE SETS F1..F5.
# This study labels its SELECTORS F1..F5 per the user brief, which is a different
# numbering. To prevent any confusion, all reporting uses the explicit arm names
# below, and the mapping table is fixed here:
#
#   This study   Meaning                             Audit feature set used
#   ----------   ----------------------------------  -----------------------
#   GREEDY       recorded original greedy action set (not a model)
#   F1-SCORE     baseline soft-match count score     F1_baseline_count_score
#   F2-SOFT      explicit soft match/mismatch/       F2_soft_state
#                unknown/declined state
#   F3-OBSERV    full legal observable features      F4_full_legal_observables
#   F4-RANDOM    zero-discrimination control         (none)
#   F5-ORACLE    one-day hindsight MSMI oracle       (uses cf_y_msmi labels)
#
# The audit's own F3_public_profile and F5_state_only are NOT used as selectors
# in this study. The audit's F5_state_only was the flat-score control whose
# anomalous 55/82 result motivates this study; it is deliberately replaced by
# F4-RANDOM, which is the correct zero-discrimination control at FIXED
# cardinality.
#
# Every arm, including F5-ORACLE, selects EXACTLY k_t pairs on state t. Arms
# that cannot achieve size k_t are impossible by V-SRC-07 and are treated as a
# hard error if they occur.
#
# --- GREEDY (reference arm) -------------------------------------------------
# The recorded `pairs` list from day_edges.jsonl. Size k_t by definition.
# Never recomputed, so the study cannot drift from what was actually run.
#
# --- F1-SCORE ---------------------------------------------------------------
# Weight each feasible edge by its baseline soft-match count score. In
# day_edges.jsonl edges are stored as [neg, [a,b]], so w = -neg.
# Select the exact-k_t matching maximising total w.
# This is deliberately NOT assumed to reproduce greedy's sequential action set:
# sequential greedy is a greedy heuristic, whereas this is a cardinality-
# constrained optimum. GREEDY is retained separately as its own control.
#
# --- F2-SOFT and F3-OBSERV --------------------------------------------------
# Weight each feasible edge by its out-of-fold model score from oof_scores.jsonl
# for the corresponding audit feature set. Every score used here was produced by
# a model NOT trained on the corresponding seed group (seed-group folds), so no
# state is scored by a model that saw its own seed. No threshold, hyperparameter
# or feature-set tuning is performed in this study.
#
# --- F4-RANDOM (zero-discrimination control) --------------------------------
# Constructs exact-k_t matchings using NO pair-outcome information: repeatedly
# draw a uniformly random permutation of the feasible edges and greedily accept
# each edge if both endpoints are free, until k_t edges are accepted (always
# succeeds by V-SRC-07 in expectation; a draw that fails to reach k_t is
# retried, and the retry count is reported).
#
# Base analysis seed: 4242 (fixed before running).
# Replicates per state: R = 100.
# Per-state point estimate: the MEAN over the R replicates.
# The DISTRIBUTION is reported (min, median, max, and the per-state standard
# deviation) rather than any single lucky draw. The luckiest replicate is
# explicitly NOT reported as the control's value.
#
# --- F5-ORACLE (one-day hindsight benchmark) --------------------------------
# Weight each feasible edge by cf_y_msmi. Select the exact-k_t matching
# maximising the number of counterfactual MSMI positives.
# This arm uses hidden labels the policy never had. It is NOT deployable, is NOT
# a sequential policy oracle, and is NOT a global performance ceiling. It is
# only an optimistic local benchmark of selection quality at fixed volume.
# Validated independently against brute force by V-SOLV-01.
#
# ============================================================================
# 6. Statistical procedure
# ============================================================================
#
# Independent sampling structure: 21 seed groups. All six variants sharing a
# seed share a fold and share a resampling unit. Pair rows and day rows are NOT
# treated as independent; the day-level n = 7,560 is NEVER used as the sample
# size for inference.
#
#   S-01  Paired differences: every selector is evaluated on the SAME recorded
#         states as GREEDY, so comparisons are paired by state.
#   S-02  Aggregation unit: the seed group. Per-seed sums and means are formed
#         first (per_seed_results.csv).
#   S-03  Uncertainty: nonparametric bootstrap over the 21 seed groups with
#         replacement, B = 2000, rng seed 4242. The percentile interval is
#         reported as a 95% interval. It reflects the variation between the 21
#         independent seed groups only.
#   S-04  Direction counts: positive / tied / negative seed-group counts are
#         reported alongside the interval.
#   S-05  Effect sizes are always accompanied by their raw numerators and
#         denominators.
#   S-06  All variants of a seed are kept together in every resample.
#
# The bootstrap interval is a STATISTICAL INFERENCE and is never described as a
# measured fact.
#
# ============================================================================
# 7. Interpretation rules (preregistered)
# ============================================================================
#
# These cases are applied to the fixed-cardinality results. Several may coexist;
# evidence is never forced into a single explanation.
#
#   CASE A  F2-SOFT and/or F3-OBSERV beat F1-SCORE AND GREEDY at equal
#           cardinality, with the seed-group interval for the primary estimand
#           excluding zero. Interpretation: better legal pair information can
#           improve selection on the recorded states. Does NOT establish a
#           sequential policy gain.
#   CASE B  F2-SOFT/F3-OBSERV do not beat F1-SCORE, but F5-ORACLE retains
#           substantial headroom over GREEDY at fixed cardinality.
#           Interpretation: a gap remains between information available to a
#           real selector and hindsight-optimal selection.
#   CASE C  F5-ORACLE has little headroom even at fixed cardinality.
#           Interpretation: limited local selection opportunity on the recorded
#           states. Does NOT prove a different sequential trajectory cannot
#           help.
#   CASE D  F4-RANDOM matches or beats GREEDY frequently. Investigation of the
#           variance and volume controls is REQUIRED. A random control is never
#           treated as proof that pair identity is irrelevant merely because it
#           wins on some states.
#   CASE E  Results too uncertain to distinguish these cases. The study is
#           reported as inconclusive; no positive or negative verdict is forced.
#
# Cardality-confound test (the study's central diagnostic):
#
#   CC-01  Compare the audit's original F5_state_only argmax statistic against
#          F5-ORACLE-at-fixed-k on the same 82 headroom states. Because
#          V-SRC-16b established that F5_state_only is FLAT within all 82
#          headroom states, any excess of the original statistic over
#          fixed-k is attributable to size, not ranking. The size distributions
#          of the two selections are reported side by side.
#
# ============================================================================
# 8. Honesty constraints
# ============================================================================
#
#   H-01  Local counterfactual success over greedy's states is NOT an estimate
#         of the official full-horizon policy score. Alternative actions change
#         availability and all subsequent states.
#   H-02  F5-ORACLE is never called a sequential policy oracle or an attainable
#         ceiling.
#   H-03  No hidden simulation attribute is used as a feature by any
#         non-oracle arm.
#   H-04  Never present an unselected pair's counterfactual outcome as if it
#         were observed.
#   H-05  Every headline number must be traceable to a reproducible table row.
#   H-06  A conclusion is labelled as one of: measured fact / statistical
#         inference / source-code fact / unresolved hypothesis.
#   H-07  No policy, tournament, submission or strategy recommendation.
#
# ============================================================================
# 9. Deliverables
# ============================================================================
#
#   research/round2_fixed_cardinality/
#     analysis_plan.md              this frozen file
#     report.md                     final narrative + the six required answers
#     selector_summary.csv          per-arm totals and subset results
#     per_state_results.csv         7,560 states x arms
#     per_seed_results.csv          21 seed groups x arms
#     per_variant_results.csv       6 variants x arms
#     source_validation.json        step-2 gate output
#     solver_validation.json        step-3 gate output
#     matching_solver_check.json    brute-force comparison record
#     cardinality_confound.json     CC-01 output
#     statistics.json               seed-group bootstrap record
#     manifest_start.json / manifest_end.json
#     run_log.txt
#     integrity.sha256
#     scripts/                      fc_validate.py, fc_matching.py,
#                                   fc_solvers_test.py, fc_selectors.py,
#                                   fc_stats.py, fc_report.py
#
# ============================================================================
# 10. Freeze declaration
# ============================================================================
#
# This plan is frozen at the moment it is written, BEFORE any selector
# comparison has been computed. The only result produced so far is the
# step-2 source-data validation, which verifies existing artifacts and computes
# no new comparison.
