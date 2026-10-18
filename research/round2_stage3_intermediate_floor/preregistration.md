# Round 2 Stage 3 - Pre-registration: Intermediate-Floor Experiment

Schema: round2_stage3_intermediate_floor.
Status: PRE-REGISTERED BEFORE ANY RUN. This file is immutable once hashed.
Date: 2026-10-07.
Interpretation tags: OBSERVED / CAUSAL / UNCERTAIN / HYPOTHESIS / UNKNOWN.

## 1. Decision provenance

- Stage 1.5 (frozen): floor = dominant bottleneck (seed 101: 4205 feasible ->
  611 above floor -> 434 introduced; 85.5% removed; 148/148 zero-selection
  days all_below_floor; local search 0/360; asks not the cause).
- Stage 2 (frozen): pure floor ablation A (frozen) vs B (no floor), seeds
  101-103 x 6 variants. Outcome A: volume +16.7% (17+/1 tie/0-), no evidence
  of meaningful quality collapse; ask delta -1.3% trajectory-mediated; all
  purity/integrity gates passed; survivorship within B shows the sub-floor
  band is productive-but-weaker (.1245 vs .1796 mutual/intro; .00372 vs
  .01159 MSMI/intro, selected pairs only - biased, not unbiased).
- Interpretation memo (session, 2026-10-07): frozen floor is likely too
  conservative at its current threshold; largest remaining design unknown is
  whether an interior floor point dominates both tested endpoints. Decision:
  next experiment = B, intermediate-floor experiment (not a sweep).

## 2. Exact pre-registration rule (single intervention)

    intermediate_floor = float(model["floor"]) / 2.0

where `model` is the frozen embedded blob in policy.py (FloorVerified:
float(model["floor"]) == 0.007905174015296758, source:
research/round2_stage2_floor_ablation/diag_arm_a_seed101.json and purity.json).

    intermediate_floor = 0.003952587007648379   # exactly floor / 2.0

Applied at the identical call site (policy.py:591 semantics):

    chosen = max_score_matching(nodes, edges, intermediate_floor)

Predicate unchanged: `e[2] >= intermediate_floor` (policy.py:469).

## 3. Why principled, not tuned

1. Zero free parameters fitted to outcomes. The value is arithmetic on the
   frozen constant alone: the unique bisection midpoint of the interval
   Stage 2 actually tested. The filter operates on raw score in (0,1); the
   tested endpoints are [frozen floor, effectively 0] (no filter passes all).
   floor/2 is that interval's midpoint in the exact metric the predicate
   compares. A midpoint of a tested interval is determined by the interval,
   not by results.
2. Existing Stage 1.5 + Stage 2 evidence justifies testing AN interior, not
   THIS interior: Stage 1.5 shows the upper endpoint destroys throughput;
   Stage 2 shows the lower endpoint recovers volume with no evidence of
   meaningful quality collapse, yet the discarded band converts worse than
   the retained band (within-B 0.69x / 0.32x ratios, selected-pair basis).
   Since no existing evidence discriminates among interior points, the
   canonical interval midpoint is the only neutral choice.
3. Explicitly rejected alternatives:
   - threshold sweep (forbidden; stepwise tuning),
   - targeting an eval pass-rate quantile (fits outcome distribution = tuned),
   - re-derived training-quantile floor (fits a parameter to data; extra machinery),
   - any value chosen after seeing seeds 104-106 (contaminates the fresh seeds).

## 4. Arms

All three arms are byte-identical to Stage 2 protocol except the single
floor argument at the matcher call site:

    Arm 1 (frozen):     max_score_matching(nodes, edges, float(model["floor"]))
                        apparatus: frozen policy_ac.py (Round 1, read-only)
    Arm 2 (intermediate): max_score_matching(nodes, edges, float(model["floor"]) / 2.0)
                        apparatus: ONE new shim mirroring
                        research/round2_stage2_floor_ablation/ablation_policy.py
                        with the sole constant changed from -inf to
                        float(model["floor"]) / 2.0. The shim must be written
                        and its SHA256 recorded in run_log.txt as the FIRST
                        step of execution, before any run.
    Arm 3 (no floor):   max_score_matching(nodes, edges, -inf)
                        apparatus: Stage 2 ablation_policy.py (unchanged)

Frozen for all arms: model blob, ac_asks clarification, matcher function
object, candidate cap (policy.py:567-584), local search, _rule_greedy
fallback, evaluator (evaluate.py), kit metrics, 60-day horizon + 40-day
follow-up, Dockerfile, Round 1 results/*.

## 5. Design

- Seeds: 104, 105, 106 (never used in Round 1, Stage 1.5, or Stage 2).
- Variants: development, sparse, cold_start, delayed, shift, drift (all six).
- Episodes: 18 per arm (3 seeds x 6 variants), paired by (seed, variant).
- Command shape: python evaluate.py --policy <arm-shim> --baseline greedy
  --seeds 104,105,106 --variants all --output research/round2_stage3_intermediate_floor/<arm>.json
- Private holdout: untouched. No threshold sweep. No post-hoc adjustment of
  the intermediate value under any outcome.

## 6. Metrics

Primary:   MSMI/100 (official family-mean definition, kit.py).
Secondary: introductions/episode, mutual/episode, mutual/intro,
           MSMI/intro, coverage, ask cost, invalids.

## 7. Analysis plan (fixed before running)

- Paired deltas for (intermediate - frozen), (intermediate - nofloor),
  (nofloor - frozen) over the 18 (seed, variant) pairs.
- Per-seed and per-variant tables; funnel counts per arm; survivorship
  classification of selected pairs vs frozen floor AND vs intermediate floor
  (selected-pair basis; biased - report as description, not causal estimate).
- Cluster bootstrap over the 3 seed clusters: DESCRIPTIVE ONLY. No
  statistical significance claims (also no claims from small MSMI counts).
- Integrity gates: frozen hashes re-verified (policy.py, policy_ac.py,
  results/artifact.sha256); one deterministic rerun per arm design (at least
  Arm 2 seed 104) must match excluding inference_seconds; zero policy
  invalids required; Arm 1 must run with the frozen shim unmodified.
- Report ALL arms and ALL metrics regardless of outcome.

## 8. Decision discipline

- Threshold exploration ENDS with this experiment under ANY outcome.
- A favorable result (intermediate >= both endpoints on primary point
  estimates without volume regression) is a candidate for a SEPARATE,
  later holdout-promotion decision - not an invitation to try more values.
- A null or unfavorable result closes threshold exploration in this phase
  and returns to ask/matcher/model diagnosis with new evidence.
- No code changes to frozen files. No holdout access. No rewriting of
  Round 1, Stage 1.5, or Stage 2 records.