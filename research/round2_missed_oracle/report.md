# Missed-Oracle Opportunity Audit
#
# Round 2, study 3 of 3. Read-only mechanism audit over already-recorded,
# already-validated decision states. No new policy, no new tournament, no new
# world seed, no refit of F2, no strategy recommendation.
#
# Prior studies (both frozen, both seal-verified before this audit ran):
#   research/round2_decision_ceiling/    K1-K6 verdicts; only K4 supported
#   research/round2_fixed_cardinality/   exact-k_t selectors; F5 161 vs F2 94
#
# Frozen analysis plan: analysis_plan.md, sha256
#   d0006555e468c2515da76c0bc51e6515a0496ca67fa527fa485b7458159fde1f
# Written and hashed before any rank, decomposition, tail or taxonomy result
# was computed or examined.
#
# ============================================================================
# 0. The question and the one-line answer
# ============================================================================
#
#   Where does the F2-to-oracle gap come from?
#
# ANSWER (measured fact, additive and exact):
#
#   Of the 67-point gap between F2-SOFT (94) and F5-ORACLE (161),
#
#       60 points (89.6%) are RANKING failure
#        7 points (10.4%) are MATCHING conflict
#
#   and the matching constraint itself costs a further 12 positives that no
#   ranking, however good, could recover at this cardinality (161 + 12 = 173,
#   exactly the unconstrained positive count).
#
# The dominant failure is that F2's out-of-fold score does not put the
# counterfactual-positive edges at the top. It is NOT that the non-overlap
# constraint blocks them: all 67 missed positives are structurally coverable
# at k_t, and the median F2 rank of a missed positive is 3.
#
# ============================================================================
# 1. Method
# ============================================================================
#
# Validation gate (all PASS, recorded in validation.json) run before any new
# diagnostic:
#
#   V1  Rebuilt the 15,304-row frame from counterfactual_pairs.jsonl +
#       pair_state.jsonl via the ceiling study's own s3_signal.load_frame(),
#       then RECOMPUTED out-of-fold F1 and F2 scores with s3_signal.oof_scores
#       (GroupKFold on seed). Bit-exact agreement with oof_scores.jsonl:
#       max|diff| = 0.0 for both models. This single test proves feature
#       legality (assert_legal_features) AND that no score was produced by a
#       model trained on its own seed group.
#   V2  Every evaluated pair is an edge of that state's feasible graph.
#   V3  No reversed-orientation label mismatches.
#   V4  No banned, cf_*, y_*, seed or variant column among the 123 features.
#   V5  Recomputed selectors at exact k_t have exactly k_t pairs on all 7,560
#       states and reproduce the frozen study's positive counts exactly
#       (0 mismatches for GREEDY, F1, F2, F3, F5).
#   V6  Reconcile GREEDY=90, F5-F=+71, F2-F=+4, F2-F1=+13.
#   V0  Both prior integrity seals current, scoped: the ceiling seal differs
#       ONLY in run_log.txt, which the fixed-cardinality study deliberately
#       appended a deviation note to. Every substantive ceiling artifact is
#       byte-identical.
#
# The exact-k solver is the validated one from the fixed-cardinality study
# (12,310 brute-force checks, 0 disagreements). It is reused, not rewritten.
#
# ============================================================================
# 2. The additive decomposition
# ============================================================================
#
# Per state t with k_t edges chosen and p_t counterfactual positives:
#
#   P_5(t)  positives in the exact-k_t oracle set (F5)
#   P_2(t)  positives in the exact-k_t F2 set
#   R_t     positives among the k_t edges with the HIGHEST F2 score,
#           ties broken canonically. R_t deliberately IGNORES the non-overlap
#           constraint. It is a DIAGNOSTIC BOUND, never a realisable selector,
#           and is never reported as one.
#   U_t     min(p_t, k_t) = positives with perfect ranking and no overlap
#
# Then, exactly and without overlap:
#
#   P_5 - P_2 = (P_5 - R_t)  +  (R_t - P_2)
#               \_________/    \_______/
#                RANKING        CONFLICT
#
# Observed, summed over all 7,560 states (measured fact):
#
#   P_5 = 161     P_2 = 94     R_t = 101     U_t = 173
#   ranking  = P_5 - R_t =  60    (89.6% of the 67-point gap)
#   conflict = R_t - P_2 =   7    (10.4%)
#   irreducible matching cost = U_t - P_5 = 12
#
# The two components sum to 67 exactly (60 + 7 = 67). The 12-point
# irreducible cost is separately reported and NOT added to the gap: it is the
# price of requiring vertex-disjointness at cardinality k_t, and it matches
# the known unconstrained-vs-fixed-k difference (173 - 161 = 12) from the
# fixed-cardinality study.
#
# Per-state behaviour (measured fact):
#
#   ranking_component > 0 on 63 states, total +65
#   conflict_component > 0 on 29 states, total +29
#   conflict_component < 0 on 22 states, total -22
#
# A NEGATIVE conflict component is meaningful and reported, not suppressed:
# it means R_t < P_2, i.e. the naive top-k_t-by-score set contained FEWER
# positives than F2 actually kept, because the top-scoring edges overlapped
# one another and the non-overlap constraint forced F2 onto a more diverse
# set that happened to include more positives. On zero-headroom states the
# matching constraint therefore partly RECOVERS for F2's ranking rather than
# costing it (see section 5).
#
# ============================================================================
# 3. Answer to question 1: are oracle-positive edges ranked poorly by F2?
# ============================================================================
#
# Near-miss, not far-miss. (All 173 counterfactual-positive edges; see
# positive_edge_ranks.csv.)
#
#                               median F2 rank   mean F2 rank   p75
#   captured by F2   (n=94)            2              2.86          4
#   missed by F2     (n=67)            3              4.31          7
#   (max missed rank = 23)
#
# The median missed positive sits at F2 rank 3. The baseline raw score ranks
# missed positives at mean 2.34 and captured ones at 4.38, i.e. the baseline
# already puts most positives near the top; F2's soft-state features move the
# ordering only slightly.
#
# 34 of the 67 missed positives have f2_rank <= k_t, i.e. F2's ranking DID
# surface them within the permitted volume; the non-overlap constraint then
# forced F2 off them (this is the conflict component, 7 points net).
#
# Coverability is NOT the binding constraint. All 67 missed positives are
# structurally coverable at k_t: for each, max_matching_size(G_t minus its
# endpoints) >= k_t - 1. The matching constraint never makes a missed positive
# impossible; F2 simply does not score it high enough.
#
# ============================================================================
# 4. Answer to question 2: ranking failure vs matching conflicts
# ============================================================================
#
# Ranking dominates, 60 of 67 (measured fact, section 2).
#
# Per-missed-positive mechanism flags (non-exclusive; analysis_plan sec.5).
# These measure different things than the additive components and are reported
# alongside, never instead:
#
#   A  a negative in F2's set STRICTLY outranks the missed positive   46 / 67
#   B  the missed positive shares a vertex with some F2 pick          66 / 67
#   C  count of F2 negatives outranking (same predicate as A)         46 edges
#   D  the missed positive is tied with an F2 negative                37 / 67
#   E  the missed positive is blocked by a POSITIVE in F2's set        0 / 67
#
# Flag overlap patterns: AB 28, ABD 17, BD 20, A 1, B 1.
#
# HONESTY: flag B at 66/67 is near-tautological and must not be over-read.
# Once F2 has picked k_t edges, almost any missed positive in the same state
# will share a vertex with a pick. B is not evidence of a binding conflict.
# The informative signal is flag A: 46 of 67 missed positives have a
# counterfactual-negative edge that F2 scored strictly higher. That is the
# ranking failure, observed edge by edge.
#
# Flag E is 0/67: no missed positive is displaced by another positive that F2
# already selected. F2 is not "spending its positive budget on the wrong
# positives"; it is not recognising the positives at all.
#
# ============================================================================
# 5. Answer to question 3: where is the gap concentrated?
# ============================================================================
#
# Stratified by the fixed-cardinality study's headroom flag (local_gap >= 1),
# 82 headroom states vs 7,478 non-headroom states:
#
#                                       headroom   non-headroom    total
#   F2 - GREEDY                              +12            -8        +4
#   F2 - F5 (regret)                         -59            -8       -67
#   ranking_component                         +35           +25       +60
#   conflict_component                        +24           -17        +7
#
# The entire F2-over-GREEDY advantage (+12) lives in the 82 headroom states.
# On the 7,478 non-headroom states F2 is NET WORSE than greedy by 8. The
# aggregate +4 is the difference of two opposing effects, not a uniform small
# win. Seed-group bootstrap (21 seeds, B=2000, rng 4242) on F2 - GREEDY:
# CI [-0.33, +0.71], which INCLUDES 0. The +4 is not distinguishable from
# zero at the seed-group level. This matches the frozen study's own interval.
#
# Regret F5 - F2 = 67 total; seed-group bootstrap CI [+2.10, +4.29] per seed
# on average, i.e. the oracle gap is consistently positive across seeds even
# though the F2-over-greedy edge is not.
#
# ============================================================================
# 6. Answer to question 4: predictive-to-decision gap metrics
# ============================================================================
#
# Every denominator stated. All scores are held-out (out-of-fold); F2 was
# never refit on all targets.
#
#   global AUC of F2 (all 15,304 edges)              0.5634
#   within-state AUC, mean over 159 two-class states  0.5881
#   pooled recall@k_t  = 94 / 173                     0.5434
#   pooled precision of F2 = 94 / 8,433               0.01115
#
#   capture at exact k_t:   GREEDY 90   F1 81   F2 94   F5 161
#   F2 - GREEDY = +4        seed-group CI [-0.33, +0.71]  (12 win / 7,540 tie / 8 loss)
#   REGRET F5 - F2 = 67     seed-group CI [+2.10, +4.29]
#
# F2 beats the oracle on 0 states (sanity: F5 is optimal by construction).
#
# The AUC is only modestly above chance, yet F2's pooled recall@k_t is 54%.
# The two are consistent because positives are rare (173 of 15,304 = 1.13%)
# and concentrated: an AUC of 0.56 can still place more than half the
# positives inside the top k_t slots when k_t is large relative to the
# positive count. Recall@k_t is the decision-relevant metric here; AUC alone
# would mislead.
#
# ============================================================================
# 7. Answer to question 5: zero-headroom taxonomy
# ============================================================================
#
# On the 7,478 states with unconstrained local_gap = 0, the fixed-k oracle
# equals greedy by construction. Invariant P_F5 == P_GREEDY holds on every
# one of them. Mutually exclusive categories (analysis_plan sec.8):
#
#   (a) NO POSITIVE EDGES      7,394   (98.88%)
#   (b) GREEDY SET IS OPTIMAL     52   ( 0.70%)
#   (c) EXTRAS BLOCKED             0   ( 0.00%)
#   (d) ALTERNATIVE OPTIMA        32   ( 0.43%)
#
# Category (c) is empty: there is no state where extra positives exist but
# none can be added without an equal or greater loss. Where positives exist
# at all on a zero-headroom state, greedy either already holds an optimal set
# (b) or a different optimal set of the same size exists (d).
#
# 98.9% of zero-headroom states contain NO counterfactual-positive edge. This
# is the single largest reason the oracle cannot improve on greedy: on most
# days there is simply nothing better to find.
#
# HONESTY: zero additional oracle gain is NOT zero predictive signal and NOT
# zero decision alternatives. Reported separately: on these 7,478 states F2
# captures 80 positives vs greedy's 88, i.e. F2 is 8 WORSE despite the oracle
# being flat. The oracle being pinned says nothing about whether F2 is
# behaving well; the two facts are kept apart.
#
# ============================================================================
# 8. Tail signal: match vs mismatch vs unknown soft channels
# ============================================================================
#
# Soft-channel states recomputed with the ceiling study's EXACT rule, reused
# verbatim via s3_signal.derived_features_from_row (declined if either side
# declined; else unknown if either value None; else match/mismatch). Seven
# soft channels; four states.
#
# D2 - counterfactual MSMI rate, unknown-only vs mismatch-only edges
#   unknown_only  (n edges, rate)   1.321%
#   mismatch_only                  1.196%
#   both                           0.409%
#   neither                        0.000%
#   raw rate difference (unknown - mismatch) = +0.125 percentage points
#   seed-group cluster bootstrap 95% CI = [-0.300, +0.564] pp
#
# The CI INCLUDES ZERO. At the seed-group level the counterfactual MSMI rate
# for edges with an unknown soft channel is NOT distinguishable from the rate
# for edges with an observed mismatch.
#
# HONESTY: this is a NULL RESULT and is reported as one. It does NOT support
# the tempting story that "unknown preferences are better than observed
# mismatches." The raw difference is +0.125pp; the uncertainty spans zero.
# Moreover unknown_only and mismatch_only edges differ in WHICH fields were
# asked and BY WHOM, so even a significant difference would not be a causal
# effect of ignorance vs mismatch. The seed-group CI reflects sampling of
# seeds, not removal of this generation/selection confound.
#
# D3 - per-channel F2 score separation (21 comparisons, all point estimates
# inside their own CIs after correcting the bootstrap estimand). Only one
# channel separates clearly on match-vs-mismatch:
#
#   relationship_goal   match vs mismatch   d_f2 = +0.0118
#                       95% CI [+0.0094, +0.0141]   (excludes 0)
#                       n = 2,042 vs 2,324
#                       counterfactual MSMI 2.06% (match) vs 0.26% (mismatch)
#
# This is the one channel where F2's soft-state feature both separates scores
# in the expected direction AND the underlying counterfactual rate moves the
# same way (matches on relationship_goal are ~8x more likely to be MSMI
# positives than mismatches). Every other channel's match-vs-mismatch
# separation either has a CI spanning zero or moves against the MSMI rate.
#
# D4 - concentration. The ranking component is 35 of 60 on headroom states
# and 25 of 60 on non-headroom states. The gap is NOT purely a headroom
# phenomenon: a quarter of the ranking failure occurs on states where the
# oracle itself gains nothing over greedy.
#
# ============================================================================
# 9. Consistency checks
# ============================================================================
#
#   +71, +4, +13 recomputed and reconciled (V6)             PASS
#   F2 - F5 = 67 = ranking 60 + conflict 7 (exact)          PASS
#   U_t - P_5 = 12 = 173 - 161 (matches prior study)        PASS
#   identical cardinality k_t on every arm, every state     PASS (V5)
#   F2 never exceeds F5 on any state (F5 optimal)           PASS (0 states)
#   P_F5 == P_GREEDY on all 7,478 zero-headroom states      PASS
#   category counts (a)+(b)+(c)+(d) = 7,478                 PASS
#   oracle objective = counterfactual MSMI count, not proxy PASS
#   every F2/F1 score out-of-fold, bit-exact reproduce      PASS (V1)
#   maturity/label alignment, no reversed orientation       PASS (V3)
#   D2 and D3 CIs contain their point estimates             PASS (after fix)
#
# ============================================================================
# 10. Evidence classification
# ============================================================================
#
# MEASURED FACT:
#   The 60/7 ranking/conflict split and its exact additivity.
#   All 67 missed positives structurally coverable at k_t.
#   Median F2 rank of a missed positive = 3; of a captured one = 2.
#   Flag A on 46/67; flag E on 0/67.
#   F2 - GREEDY +12 headroom, -8 non-headroom, +4 net.
#   Zero-headroom taxonomy counts 7,394 / 52 / 0 / 32.
#   U_t - P_5 = 12.
#
# STATISTICAL INFERENCE (21 seed groups, B=2000, rng 4242):
#   F2 - GREEDY CI [-0.33, +0.71] includes 0.
#   Regret F5 - F2 CI [+2.10, +4.29] excludes 0.
#   D2 unknown-vs-mismatch rate difference CI includes 0.
#   D3 relationship_goal match-vs-mismatch CI excludes 0.
#
# SOURCE-CODE FACT:
#   s3_signal.load_frame / oof_scores / derived_features_from_row reused
#   verbatim; GroupKFold on seed; SOFT_CHANNELS and SOFT_STATES as declared.
#   fc_matching.solve_exact_k validated (12,310 brute-force, 0 disagreements).
#
# UNRESOLVED HYPOTHESIS (not claimed):
#   Whether the 60 ranking points are recoverable by any legal feature set, or
#   are irreducibly tied to information the policy never observes. This audit
#   cannot answer that; it would require refitting F2 on alternative feature
#   sets, which is out of scope and was not done.
#
# ============================================================================
# 11. Honesty constraints
# ============================================================================
#
#   H-01 Local one-day counterfactuals only. Alternative actions change
#        availability and every subsequent state. A local win is not a
#        horizon win. This audit cannot quantify the sequential effect and
#        does not pretend to. Every number here is a one-day quantity.
#   H-02 R_t is a diagnostic bound, never a realisable selector.
#   H-03 F5 uses hidden counterfactual labels: not deployable, not a
#        sequential oracle.
#   H-04 No refit of F2 on all targets; every prediction out-of-fold.
#   H-05 Unselected pairs' counterfactual outcomes are never presented as
#        observed.
#   H-06 Sparse statistics labelled: 159 two-class states for within-state
#        AUC; 82 headroom states; D3 cells as small as n=982.
#   H-07 Every headline number traces to a delivered CSV/JSON row.
#   H-08 No policy, tournament, submission or strategy recommendation.
#   H-09 The unknown-vs-mismatch null is reported as a null, not spun.
#
# ============================================================================
# 12. Deliverables
# ============================================================================
#
#   analysis_plan.md              frozen, sha256 d0006555e468c2515da76c0bc51e6515a0496ca67fa527fa485b7458159fde1f
#   report.md                     this file
#   positive_edge_ranks.csv       173 rows, one per counterfactual-positive edge
#   selection_diagnostics.csv     7,560 rows, one per state
#   selection_diagnostics.jsonl   same, JSONL
#   gap_decomposition.csv         mechanism counts by stratum
#   decomposition_agg.json        aggregate decomposition
#   per_seed_results.csv          21 seed groups
#   per_seed_results.jsonl        same, JSONL
#   statistics.json               bootstrap record, all CIs
#   tail_signal.json              sections 7 (D1-D4)
#   headroom_taxonomy.json        section 8 aggregate
#   headroom_taxonomy_per_state.jsonl  7,478 rows
#   validation.json               step-2 gate output
#   recomputed_sets.jsonl         recomputed selected sets per state
#   scripts/                      mo_validate, mo_analyze, mo_stats, mo_tail,
#                                 mo_taxonomy, mo_report, mo_verify
#   manifest_start.json, manifest_end.json, run_log.txt, integrity.sha256
#
# ============================================================================
# 13. Conclusion
# ============================================================================
#
# The F2-to-oracle gap is overwhelmingly a ranking failure, not a matching
# failure. 60 of the 67 missing positives are never surfaced by F2's score at
# all; only 7 are lost to the non-overlap constraint; and a further 12 are
# irrecoverable at cardinality k_t regardless of ranking. All 67 missed
# positives are structurally coverable, and their median F2 rank is 3 - so
# the failure is a near-miss in score ordering, not an impossibility.
#
# The one place F2 clearly learns something real is relationship_goal: matches
# there are scored ~0.012 higher and are ~8x more likely to be counterfactual
# MSMI positives. Every other soft channel is either uncertain or moves
# against the counterfactual rate. The hypothesis that "unknown beats
# mismatch" is NOT supported: the seed-group interval includes zero.
#
# 98.9% of zero-headroom states contain no positive edge at all, so most days
# have nothing for any ranking to find. F2's aggregate +4 over greedy is not
# distinguishable from zero and hides a +12 headroom / -8 non-headroom split.
#
# Nothing here is a policy recommendation. The audit answers where the gap
# comes from; what to do about it is a separate question, out of scope.
