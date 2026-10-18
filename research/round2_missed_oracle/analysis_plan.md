# Missed-Oracle Opportunity Audit - Analysis Plan
#
# STATUS: FROZEN BEFORE ANY NEW DIAGNOSTIC RESULT IS EXAMINED.
# Written after the step-2 validation gate only, which inspects and reproduces
# existing artifacts and computes no new diagnostic. Corrections after freezing
# are permitted only as an appended "## Amendment" block with reason plus a
# run_log.txt entry. Never silently edited.
#
# ============================================================================
# 0. Objective and scope
# ============================================================================
#
# Narrow question:
#
#   Where does the F2-to-oracle gap come from?
#
# Frozen prior results (fixed-cardinality study, exact k_t on all 7,560 states):
#   GREEDY 90, F1-SCORE 81, F2-SOFT 94, F3-OBSERV 85, F4-RANDOM 85.25,
#   F5-ORACLE 161. F2 - F5 = -67.
#
# This is a MECHANISM AUDIT over already-recorded, already-validated decision
# states, counterfactual labels, held-out predictions and selector outputs.
# It is NOT a new leaderboard, NOT a policy, NOT a tournament, and NOT a
# recommendation. No new world seed is generated, no label is modified, and F2
# is NOT refit or retuned after inspecting targets.
#
# ============================================================================
# 1. Data sources (all read-only)
# ============================================================================
#
# research/round2_decision_ceiling/   (validated, seal checked)
#   oof_scores.jsonl           15,304 rows; out-of-fold F1/F2/F3/F4/F5 scores,
#                              held out BY SEED GROUP (GroupKFold on seed).
#   counterfactual_pairs.jsonl 15,304 rows; cf_y_msmi labels + feat dict.
#   pair_state.jsonl           15,304 rows; per-side fields + field_status.
#   day_edges.jsonl            7,560 states; feasible graph + greedy pairs.
#   oracle_by_day.jsonl        7,560 rows; local_gap, batch_size, maxcard.
#
# research/round2_fixed_cardinality/  (validated, seal checked)
#   per_state_results.jsonl    7,560 rows; per-arm positive counts.
#   scripts/fc_matching.py     VALIDATED exact-k solver (12,310 brute-force
#                              checks, 0 disagreements). Reused, not rewritten.
#
# New: research/round2_missed_oracle/
#
# ============================================================================
# 2. Validation gate (prerequisite; PASS observed before this freeze)
# ============================================================================
#
#   V1  Rebuild the frame from counterfactual_pairs + pair_state via the
#       ceiling audit's own s3_signal.load_frame(), then RECOMPUTE out-of-fold
#       F1 and F2 scores with s3_signal.oof_scores(). Require BIT-EXACT
#       agreement with oof_scores.jsonl. This single test simultaneously
#       proves feature legality (assert_legal_features) and that no score was
#       produced by a model trained on its own seed group.
#       Observed: max|diff| = 0.0 for both F1 and F2.
#   V2  Every evaluated pair is an edge of that state's feasible graph.
#   V3  No reversed-orientation label mismatches; 15,304 labels aligned to the
#       correct world/pair/assignment day.
#   V4  No banned attribute, cf_*, y_* or seed/variant column in the features.
#   V5  Recomputed selectors at exact k_t have exactly k_t pairs on every
#       state, and their positive counts reproduce the frozen study exactly.
#   V6  Reconcile GREEDY=90, F5-F=+71, F2-F=+4, F2-F1=+13.
#   V0  Both prior integrity seals still current (ceiling seal may differ ONLY
#       in run_log.txt, which the prior study deliberately appended to).
#
# All observed PASS. Any failure stops the affected analysis.
#
# ============================================================================
# 3. Definitions
# ============================================================================
#
# State t = (seed, variant, day). G_t = (V_t, E_t) feasible graph, |E_t| = n_t.
# k_t = |greedy(t)|. Pos_t = edges whose cf_y_msmi = 1. p_t = |Pos_t|.
#
# Selectors, all constrained to EXACTLY k_t pairs:
#   M_G  greedy's recorded set        M_1  exact-k max of baseline raw score
#   M_2  exact-k max of OOF F2 score  M_5  exact-k max of cf_y_msmi (oracle)
#
# P_X(t) = number of positives in M_X(t).
# gap(t) = P_5(t) - P_2(t).  Sum of gap over all states = 161 - 94 = 67.
#
# --- Ranks (section 3) -------------------------------------------------------
# Within a state, order the n_t feasible edges by descending score, ties broken
# by canonical (u,v) key. For an edge e:
#   score_rank(e)   = 1 + #{edges with strictly greater score}  (competition)
#   tie_size(e)     = #{edges with equal score}
#   percentile(e)   = score_rank(e) / n_t
# Ranks are computed for BOTH the F2 out-of-fold score and the baseline raw
# count score, so the two rankings are directly comparable.
#
# --- Coverability ------------------------------------------------------------
# e is coverable at cardinality k_t iff
#   max_matching_size(G_t minus endpoints(e)) >= k_t - 1.
# (Any matching of size >= k_t-1 contains a sub-matching of size exactly k_t-1,
#  so this is equivalent to "some size-k_t matching contains e".)
#
# ============================================================================
# 4. The ranking-versus-conflict decomposition (primary, additive)
# ============================================================================
#
# Per state, define the diagnostic quantity
#
#   R_t = number of positives among the k_t edges with the HIGHEST F2 score
#         (ties broken canonically).
#
# R_t is NOT a valid matching in general - it deliberately ignores the
# non-overlap constraint. It is a diagnostic upper bound on what F2's ranking
# alone surfaces at the permitted volume. It must never be reported as a
# realisable selector.
#
# Then the oracle gap decomposes EXACTLY and NON-OVERLAPPINGLY:
#
#   P_5 - P_2 = (P_5 - R_t)  +  (R_t - P_2)
#               \_________/    \_______/
#                RANKING        CONFLICT
#                component      component
#
#   RANKING  component: positives F2's ranking failed to surface at all,
#            before any non-overlap constraint applies. Attributable to score
#            ordering.
#   CONFLICT component: positives F2's ranking DID surface but which the
#            non-overlap + exact-cardinality constraint forced it to drop in
#            favour of lower-ranked edges.
#
# Both components are reported signed and summed over states. If the conflict
# component is negative for a state (R_t > P_5, possible when the top-k_t
# score set is all-positive but mutually overlapping while the true optimum
# uses different positives), that sign is REPORTED, not suppressed.
#
# Context quantity, reported but never added to the decomposition:
#   U_t = min(p_t, k_t) = positives attainable with perfect ranking AND no
#   non-overlap constraint. The gap P_5 - U_t is the irreducible cost of the
#   matching constraint itself.
#
# ============================================================================
# 5. Per-missed-positive mechanism flags (overlap reported, not forced)
# ============================================================================
#
# For every positive edge e in M_5 \ M_2 (a missed oracle positive), the
# following predicates are each measured. They are NOT mutually exclusive and
# are reported both individually and as overlap patterns.
#
#   A ranking failure       exists f in M_2 with label 0 and score2(f) > score2(e)
#   B matching conflict     e shares a vertex with some f in M_2
#   C false-positive pull   count of f in M_2 with label 0 and score2(f) > score2(e)
#   D weak separation       #{edges with label 0 and |score2 - score2(e)| <= 1e-12}
#                           (a direct tie between e and negatives)
#   E blocked by a positive e shares a vertex with some f in M_2 with label 1
#
# Primary exclusive assignment uses the documented first-match order
# E, then B, then A, then D, then residual - and the FULL flag set is stored
# alongside so no information is lost by the exclusivity choice.
#
# ============================================================================
# 6. Predictive-to-decision gap metrics (section 5)
# ============================================================================
#
# Every metric is defined with its denominator.
#   Global AUC           roc_auc_score over all 15,304 edges.
#   Within-state AUC     mean over states whose edge set has both classes.
#   Recall@k_t           |M_2 intersect Pos_t| / p_t, averaged over states with
#                        p_t > 0; also reported pooled as a ratio of sums.
#   Precision of F2      P_2(t) / k_t; pooled = sum P_2 / sum k_t.
#   Capture              P_X(t) summed, for X in {G, 1, 2, 5}.
#   F2 - GREEDY          P_2(t) - P_G(t) per state.
#   REGRET               P_5(t) - P_2(t) per state; equals gap(t).
#
# Inference: 21 seed groups; all six variants of a seed stay together.
# Nonparametric bootstrap over seed groups, B = 2000, rng seed 4242, percentile
# 95% interval, plus positive/tied/negative seed counts. The 7,560 day rows are
# NEVER treated as independent.
#
# ============================================================================
# 7. Tail signal (section 6)
# ============================================================================
#
# Soft-channel state per (pair, channel) is recomputed from pair_state.jsonl
# with the ceiling audit's EXACT rule, reused verbatim:
#
#   if either side status == 'declined':      'declined'
#   elif either side value is None:           'unknown'      # status not_asked
#   elif values equal:                        'match'
#   else:                                     'mismatch'
#
# SOFT_CHANNELS (7, from s3_signal.py): relationship_goal, relationship_pace,
# lifestyle, conversations, emotional_availability, space_for_relationship,
# relocate. SOFT_STATES: match, mismatch, unknown, declined.
#
# Measurements, each labelled descriptive or cross-validated:
#   D1 mean F2 score by per-edge soft-state composition (match/mismatch/unknown
#      counts) - DESCRIPTIVE on held-out scores.
#   D2 counterfactual MSMI rate for edges with >=1 unknown soft channel vs
#      >=1 observed-mismatch channel, with seed-group bootstrap interval.
#   D3 per-channel: among the 7 soft channels, the F2-vs-F1 score delta
#      attributable to each sc_<ch>_mismatch and sc_<ch>_unknown column, via
#      a decomposition of the two models' score correlation by channel state.
#   D4 whether the F2-vs-F1 selection difference concentrates in the same
#      states where F5 has headroom.
#
# HONESTY: unknown is NOT asserted to be intrinsically better than mismatch.
# Generation and selection effects (which fields get asked, by whom, when) are
# reported alongside any raw rate difference.
#
# ============================================================================
# 8. Zero-headroom taxonomy (section 7)
# ============================================================================
#
# On the 7,478 states with unconstrained local_gap = 0, the fixed-k oracle
# equals greedy by construction (P_5 = P_G). Each such state is assigned to
# exactly one mutually exclusive category:
#
#   (a) NO POSITIVE EDGES        p_t = 0
#   (b) GREEDY SET IS OPTIMAL    p_t > 0 and M_5 == M_G (identical edge set)
#   (c) EXTRAS BLOCKED           p_t > 0, M_5 != M_G, and p_t > P_G
#                                (more positives exist than greedy found, but
#                                 none can be added without an equal or greater
#                                 loss)
#   (d) ALTERNATIVE OPTIMA       p_t > 0, M_5 != M_G, and p_t == P_G
#                                (same positive pool, different optimal choice)
#
# Zero additional oracle gain is NEVER equated with zero predictive signal or
# zero decision alternatives; F2's behaviour on these states is reported
# separately.
#
# ============================================================================
# 9. Honesty constraints
# ============================================================================
#
#   H-01 Local one-day counterfactuals only. Alternative actions change
#        availability and every subsequent state; a local win is not a horizon
#        win. This audit cannot quantify the sequential effect and does not
#        pretend to.
#   H-02 R_t is a diagnostic bound, never presented as a realisable selector.
#   H-03 F5 uses hidden labels: not deployable, not a sequential oracle.
#   H-04 No refit of F2 on all targets; all predictions stay out-of-fold.
#   H-05 Unselected pairs' counterfactual outcomes are never presented as
#        observed.
#   H-06 Sparse statistics are labelled too sparse for stable inference.
#   H-07 Every headline number traces to a row of a delivered CSV/JSON.
#   H-08 No policy, tournament, submission or strategy recommendation.
#
# ============================================================================
# 10. Deliverables
# ============================================================================
#
#   analysis_plan.md            this frozen file
#   report.md                   narrative + the five required answers
#   positive_edge_ranks.csv     one row per counterfactual-positive edge
#   selection_diagnostics.csv   one row per state (7,560)
#   gap_decomposition.csv       mechanism counts, overall and by stratum
#   per_seed_results.csv        21 seed groups
#   validation.json             step-2 gate output
#   recomputed_sets.jsonl       recomputed selected sets per state
#   statistics.json             bootstrap record
#   headroom_taxonomy.json      section-8 output
#   tail_signal.json            section-7 output
#   manifest_start/manifest_end.json, run_log.txt, integrity.sha256
#   scripts/
#
# ============================================================================
# 11. Freeze declaration
# ============================================================================
#
# Frozen now, BEFORE any rank distribution, decomposition, tail-signal or
# taxonomy result has been computed or examined.
