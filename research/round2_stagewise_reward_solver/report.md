# Round 2 Stagewise-Reward Solver Experiment - Final Report and Single Decision (Task 6)

Status: COMPLETE. Every correctness (C), runtime (R) and pre-evaluation policy-validity (P)
gate passed, and the pre-registered final paired evaluation ran to completion with zero
invalid episodes in either arm. This directory is sealed by `integrity.sha256`; the
machine-readable integrity verdict is `results/final_integrity.json`.

Frozen specification: `research/round2_stagewise_reward_solver/analysis_plan.md`, sha256
`ed1210c2a4afd47f8cd1b3c8598daced848ac6b41916e41470f5d819ae113305` (verified against
`analysis_plan.sha256`; frozen 2026-10-14 before any solver implementation and never
edited afterwards). Frozen model: parent `results/model_artifact.json`, sha256
`7f1ddfe00211e2603e88c4e8318d3a62980aeb8364f51bc41909e8875fa275f2` (verified at
pre-registration, at Task 3, immediately after the final evaluation, and at Task 6).

The ten questions below are the research programme's pre-registered Q1-Q10 structure
(same structure as the parent experiment's report); each is answered in this round's
scope, and answers that are inherited from the frozen parent experiment are cited as
inheritance rather than re-measured.

## Verdict (one paragraph)

The computational blocker that stopped the parent experiment was removed exactly as
pre-registered: a pure-stdlib polynomial-time exact-k blossom solver replaced the
17.199 s branch-and-bound, and it passed every gate this experiment defined - 11,200
brute-force correctness cases with zero objective mismatches (C1-C6 all pass),
a 6,041-state runtime corpus biased toward hard dense states with solver-only max
0.050 s and end-to-end max 0.444 s against the frozen 3.0 s thresholds (R1-R5 all
pass, all_gates_passed=true), and protocol-validity gates P1-P3 pass with a 6/6
episode pilot and exact greedy cardinality everywhere. Only then did the untouched
official evaluator run both arms over seeds 70001-70100 x 6 variants x 60 days
(600 episodes each, zero invalid episodes, cardinality audit 36,000/36,000 clean).
The realized paired effect is +0.00417 MSMI per 100 arrived members (candidate
0.3992 vs greedy 0.3950) with a 95% paired-bootstrap CI of [-0.0483, +0.0583] -
positive point estimate, but the interval includes 0, so the frozen decision rules
admit exactly one verdict: PROCEED WITH CHANGES (experiment valid, every gate
passed, result inconclusive).

## Decision: PROCEED WITH CHANGES

Rule citations (frozen `analysis_plan.md` S.9 "Decision rules", applied in order,
exactly one decision):

- PROCEED - NOT met. The rule requires mean paired improvement > 0 AND the 95% CI
  excluding 0 AND every C/R/P gate passed AND zero invalid candidate episodes AND
  runtime constraints held during evaluation. Mean > 0, all gates passed, zero
  invalid episodes and runtime held are satisfied, but the CI [-0.0483, +0.0583]
  includes 0, so the rule fails on its CI clause.
- PROCEED WITH CHANGES - MET. "The experiment is valid and every gate passed, but
  the result is inconclusive (CI includes 0), OR a specific evidence-backed
  limitation is identified that requires another controlled test." Both limbs hold:
  the result is inconclusive, and the evidence-backed limitation is that the frozen
  model's scores are compressed into a narrow ~0.01 band (Q6/Q7), which caps the
  discriminative headroom a selector can exploit and left the CI roughly +-0.05
  wide at a point estimate of +0.004. Resolving that requires another controlled
  test under a NEW pre-registration.
- STOP / REDESIGN - NOT met. No correctness, integrity, policy-validity or runtime
  gate failed, and the CI does not exclude 0 at or below 0 (it spans 0).

The decision is pre-registered and cannot be revised by any finding in this report.
No threshold changed after any result was observed; no weight, constraint, solver
behaviour or evaluation cell was tuned after outcomes; no approximate solver and no
density-threshold fallback were used; the evaluation seeds were consumed exactly once.
Per S.11 this report does not authorize a second experiment, and the candidate is
never claimed competition-approved. Any "changes" implied by this decision are
prospective guidance for a future, separately pre-registered experiment only.

## Evidence separation (S.10: four categories, never mixed)

### (a) Mathematical guarantees of the formulation

- Dummy-vertex reduction (S.4, proved pre-implementation): on G=(V,E) with
  k = |greedy's matching|, add D = n - 2k dummies joined to every original vertex
  with weight 0; every perfect matching of the augmented graph consumes exactly D
  originals, leaving exactly k original edges, and conversely any k-matching
  extends to one - so max-weight perfect matching on the augmented graph computes
  exactly the max-weight k-matching of G with the same objective value. Existence
  is guaranteed because k comes from greedy's own matching; "no perfect matching"
  is treated as a hard failure, never a fallback.
- Numerical exactness (S.4.1): every float weight is converted via
  `as_integer_ratio()` and scaled to exact integers on a common power-of-two
  denominator; the solver uses zero tolerance, zero epsilon, exact comparisons.
  Binary tie weights make the primary-optimal set unique, equal to the
  lexicographically smallest primary-optimal k-matching under canonical edge
  order; no floating-point perturbation anywhere. Determinism is structural (no
  RNG, no clock in the decision path).
- What (a) does NOT claim: the formulation's polynomial complexity is never cited
  as evidence about this implementation's runtime - only the measured R-gates in
  (b) establish runtime compliance (S.4, S.10).

### (b) Measured behaviour of this implementation

Sources: `results/solver_validation.json`, `results/runtime_benchmark.json`,
`results/benchmark_corpus.json`, `results/policy_validity.json`, evaluation
instrumentation under `results/eval_instrumentation/`.

- C-series (master seed 20261014, 11,200 generated cases = 9,071 feasible + 2,129
  infeasible, brute-force objective enumeration): C1 zero objective and zero
  feasibility mismatches; C2 zero determinism failures; C3 zero structural
  violations; C4 zero tie-policy mismatches; C5 8,406 agreements / 665
  disagreements with the old solver, all 665 explained by the old solver's float
  EPS=1e-9 and node limits, 0 cases where the new solver was suboptimal (pass
  per the pre-registered rule); C6 9,071 checked, 0 cardinality violations;
  volume 11,200 >= 10,000. `passed=true`.
- R-series (corpus fixed BEFORE timing: R-A 3,000 all day-0 + R-B 93 all
  n_edges >= 40 + R-C the fixed 53 parent stress states + R-D 3,000-row uniform
  random sample via `random.Random(20261014)` = 6,041 states; biased HARDER than
  the natural distribution; reconstruction failures 0 of 6,041):
  - R1 solver-only < 3.0 s every state: PASS - p50 0.00044 s, p95 0.0090 s,
    p99 0.0209 s, max 0.0503 s.
  - R2 end-to-end subprocess match invocation < 3.0 s every state: PASS - p50
    0.1696 s, p95 0.2183 s, p99 0.2501 s, max 0.4442 s (min 0.1225, mean 0.1740).
  - R3 zero solver failures, exceptions, malformed outputs, invalid matchings or
    silent fallbacks: PASS (all counters 0; the fallback branch does not exist).
  - R4 far below the evaluator's hard 10 s limit: PASS (max 0.4442 s).
  - R5 standard library + repo-root kit.py only: PASS (import inspection).
  - Corpus shape: n_edges p50 4 / p95 26 / p99 42.6 / max 65; k p50 3 / p95 11 /
    p99 13 / max 18. One measurement artifact is disclosed in Q10 item 2 (and in
    `runtime_benchmark.json` `remeasurement_applied`): a single record corrupted
    by harness process suspension was re-measured cleanly; thresholds, state,
    policy and corpus were unchanged by that correction.
- P-series (`results/policy_validity.json`, `passed=true`): P1 greedy parity -
  0 ask failures, 0 k failures, 0 feasibility failures across the in-process
  48-state population; candidate k is computed as `len(kit.baseline_match(state))`
  on the same state and was equal on every benchmark state (C6/P1 restated over
  all 6,041 corpus states). P2 protocol conformance - 0 failures in-process and
  6/6 valid pilot episodes (seed 40001, smoke only, excluded from claims); on the
  corpus, every one of the 6,041 end-to-end responses passed evaluate.py's own
  `validate_response`. P3 determinism - repeated invocations byte-identical
  (pilot digest `aa2b1ca5...`). Pilot: 360 instrumentation lines, 0 cardinality
  violations, solver max 0.0032 s, invocation max 0.1467 s. P4: frozen artifact
  hash verified at pre-registration, at Task 3, at candidate import time on every
  one of the 36,000 evaluation match invocations (mismatch raises), and again
  immediately after the final evaluation (all `7f1ddfe0...`).
- During evaluation (evidence, not protocol output): 36,000 instrumentation lines,
  k_chosen == k_greedy on 36,000/36,000 (0 mismatches); solver-only p50 0.0001 s,
  p95 0.0005 s, p99 0.0018 s, max 0.0140 s; in-process invocation p50 0.0878 s,
  p95 0.1200 s, max 0.3922 s; zero solver failures (any solver failure exits
  non-zero and would invalidate its episode - none occurred: both arms rc=0,
  empty stderr). Per-episode evaluator-measured inference sums: greedy mean
  13.89 s (max 19.41 s), candidate mean 18.23 s (max 37.21 s), each over 60
  per-day invocations individually capped at 10 s by the evaluator - no invocation
  reached the cap.

### (c) Frozen-model prediction metrics

Cited from the frozen parent artifacts, not recomputed here (S.3), and explicitly
NOT decision evidence: combined P(MSMI) = p1*p2*p3 over 45,803 mature validation
introductions had ROC-AUC 0.531473, PR-AUC 0.011841 vs 0.010589 prevalence, mean
predicted 0.010359 vs observed 0.010589. Per-stage validation: s1 ROC-AUC 0.5701 /
PR-AUC 0.1792 vs 0.1409 baseline; s2 ROC-AUC 0.5040; s3 ROC-AUC 0.4698; combined
under-predicts observed MSMI roughly 9x. Offline ranking diagnostics: P_hat spread
within state is tiny (99.2% of states below the 0.02 discrimination threshold),
0% out-of-distribution edges. Per S.9, AUC, log loss, oracle comparisons and any
single favourable seed are explicitly not success evidence; nothing in (c) was
produced or altered by this experiment.

### (d) Realized paired evaluation results

Sources: `results/eval_greedy.json`, `results/eval_candidate.json`,
`results/paired_stats.json` (B = 10,000 paired bootstrap over 100 seed groups,
`random.Random(71001)`, percentile CI; seed groups are the sampling units).

- Primary metric (msmi_per_100_arrived_members, evaluator's own): greedy 0.3950
  (474 MSMIs / 120,000 arrived members), candidate 0.3992 (479 MSMIs / 120,000).
- Paired effect: mean d_g = +0.00417; 95% CI [-0.0483, +0.0583]; win/tie/loss over
  the 100 seed groups = 35/25/40 (tie = |d_g| < 1e-12).
- Per-variant paired means (candidate - greedy): development -0.005, sparse +0.010,
  cold_start -0.035, delayed +0.020, shift +0.030, drift +0.005 - heterogeneous
  and all small relative to the CI width.
- Trajectory outcomes (reported, never gated; S.9): assignments 44,452 greedy vs
  44,379 candidate; mutual acceptances 6,310 vs 6,361; arrived members 120,000 =
  120,000; ask cost identical by construction (117,918 both arms - asks are
  `kit.baseline_asks` verbatim in both arms).
- Validity of the comparison: identical seed/variant cells in both arms
  (600 + 600 episodes, seeds 70001-70100 x 6 variants x 60 decision days + 40
  follow-up days), zero invalid episodes in either arm, cardinality audit clean.
- Interpretation: the interval spans roughly -0.05 to +0.06 points, so the data
  cannot distinguish a small benefit from a small harm; the correct reading is
  "inconclusive", not "no effect" and not "improvement".

## Q1 - Which seed groups were generated and which were used?

- No new training/collection seed groups were generated (retraining and
  recalibration are non-goals, S.1). Seeds used by round 2:
  - C-series battery: master seed 20261014 (documented generator seeds per
    family; 11,200 cases, `results/solver_validation.json`).
  - R-D corpus sample: `random.Random(20261014)` over the sorted
    (seed_group, variant, day) list (S.7).
  - P-series pilot: seed group 40001 - the parent's designated plumbing pilot,
    smoke only, excluded from all claims (S.8), consumed in Task 3.
  - Final evaluation: seed groups 70001-70100 - verified untouched at
    pre-registration (parent checks d2/d3), then consumed exactly once each, in
    both arms, by Task 5 (2026-10-15). They must NOT be described as untouched
    from now on (S.9).
  - Paired bootstrap: `random.Random(71001)` (S.9).
  - Benchmark world replay used the recorded parent groups 40001-40500 read-only
    (replays, no new seed consumption).
- Seed hygiene: pilot {40001}, evaluation {70001..70100} and generator seeds are
  disjoint; no evaluation output existed before Task 5 and the evaluation ran once.

## Q2 - How many introductions were generated, and how many labelled rows exist?

- Round 2 generated ZERO new labelled rows and ZERO new training introductions:
  collection and labelling are out of scope (S.1); the parent's 226,531 label
  rows and its `data/` corpus (357 MB, read-only) are reused only for state
  reconstruction fingerprints.
- Round 2's own data products: the 6,041-state benchmark corpus manifest
  (`results/benchmark_corpus.json`) and its timing checkpoint (6,041 records);
  1,200 evaluation episodes (600 per arm) whose realised introduction/assignment
  counts are reported under (d) as trajectory outcomes, not as labels; and 36,000
  candidate instrumentation lines (3,021 files) - evidence, never protocol output.

## Q3 - How many mature labels exist per stage, and did maturity hold?

Inherited unchanged from the frozen parent experiment (cited, not re-measured;
verified this round only through the artifact hash `7f1ddfe0...`, unchanged):
fit positives/negatives s1 25,653/154,609, s2 20,006/5,647, s3 1,870/18,136;
validation s1 6,453/39,350, s2 5,028/1,425, s3 485/4,543; UNKNOWN = 0 at every
stage in every population; maximum observed day 93 < the day-100 horizon. Nothing
in this round touches labels, features or maturity.

## Q4 - What coverage of the feasible-pair space was achieved?

- Inherited (cited): main collection 176,040 decision states, 415,708 feasible
  (state, edge) opportunities, 96,467 distinct pairs introduced (23.2% of
  opportunities); edges per state p50 = 1, p95 = 9, max = 65.
- This round's coverage decisions (frozen in S.7 before timing): the runtime
  corpus deliberately covers ALL day-0 states (the historically slow family),
  ALL states with n_edges >= 40 (the entire dense tail, 93 rows), the parent's
  fixed 53-state stress set, plus a uniform 3,000-row random sample of the rest -
  6,041 states whose edge distribution (p95 26, max 65) is harder than natural.
- Realized evaluation coverage: all 6 official variants x 100 seed groups x
  60 decision days + 40 follow-up days, 200 members per episode, per arm.

## Q5 - What did the feature-integrity audit find?

- Inherited (cited): 17 predeclared features, 0 ILLEGAL, 0 POTENTIAL LEAKAGE
  (15 LEGAL OBSERVABLE, 2 STRUCTURE-INFORMED); the two gender-fit features are
  dead constants (w = 0), reported but not fixed (no post-hoc feature edits).
- This round: feature code was copied byte-for-byte and verified -
  `scripts/sr_features.py` sha256 `76fc12f6...`, `sr_policy_core.py` sha256
  `02af1e6a...`, both equal to the parent originals at copy time and re-verified
  by the Task-6 integrity check. The candidate scores edges through the unchanged
  17-feature path with no rounding of P_hat. No feature, weight or threshold was
  altered anywhere in this experiment.

## Q6 - What predictive signal did the frozen stage models show on validation?

Cited from frozen parent artifacts (metrics not recomputed; prediction quality
only, never decision evidence): combined ROC-AUC 0.531473 / PR-AUC 0.011841 vs
0.010589 prevalence with mean predicted 0.010359 vs observed 0.010589; stage 1
ROC-AUC 0.5701, PR-AUC 0.1792 vs 0.1409; stages 2 and 3 at or below the constant
baseline (0.5040 / 0.4698); combined predictions under-state observed MSMI ~9x.
This is the pre-declared weak-signal context: the experiment tests whether these
existing scores improve DECISIONS, and S.3 states no positive result is expected
to be attributable to anything but selection among existing scores.

## Q7 - What did the offline ranking diagnostics show?

Cited from the frozen parent `results/offline_ranking.json`, not recomputed and
never used for tuning (the artifact was already frozen): P_hat over 87,204
feasible validation edges p50 0.0100, p95 0.0169; within-state spread p50 0.0027
with 99.2% of states below the 0.02 discrimination threshold; 0.0% OOD edges
(the narrow band is the model's own in-distribution behaviour); within-state
concordance for MSMI micro 0.5485 (mildly above chance). This round ran no new
ranking diagnostics - its offline counterpart is the correctness battery in (b),
which measures the SELECTOR, not the predictor. The inherited conclusion stands:
the ranking signal is too weak to expect a large sequential effect.

## Q8 - What were the realised MSMIs (candidate vs greedy)?

MEASURED this round, via the unmodified official evaluator on seeds 70001-70100
(x 6 variants x 60 decision days, both arms, identical cells):

- Greedy arm: 474 MSMIs over 120,000 arrived members = 0.3950 per 100 arrived
  (evaluator `summary.primary_score` 0.395, 600/600 episodes eligible).
- Candidate arm: 479 MSMIs over 120,000 arrived members = 0.3992 per 100 arrived
  (`primary_score` 0.3991666..., 600/600 episodes eligible).
- Zero invalid episodes in either arm (rc=0 both arms; any candidate solver
  failure would have failed its episode loudly - none did).
- Per-variant realised means and all secondary metrics (coverage, mutual
  acceptances, ask cost, inference seconds) are in the two `eval_*.json`
  summaries; the paired reading is Q9.

## Q9 - What was the paired effect size and 95% confidence interval?

- Point estimate: mean paired difference d_g over the 100 seed groups =
  +0.0041667 MSMI per 100 arrived members (candidate - greedy).
- 95% CI: [-0.0483333, +0.0583333], paired bootstrap over seed groups,
  B = 10,000, `random.Random(71001)`, percentile method (all fixed in S.9 before
  evaluation).
- Win/tie/loss: 35/25/40 seed groups. Per-variant paired means: development
  -0.005, sparse +0.010, cold_start -0.035, delayed +0.020, shift +0.030,
  drift +0.005.
- Reading: the CI includes 0, hence "inconclusive" under the frozen decision
  rules; it bounds any true effect to roughly -0.05..+0.06 points on this metric.
  No subgroup, variant or seed is presented as success evidence (S.9).

## Q10 - What failed, and what uncertainty remains?

Failures and process incidents, with sources (`run_log.txt` preserves every
failure line and correction; artifacts preserve original values):

1. Benchmark harness interruptions (runs 1 and 2 of Task 4): two detached-period
   runs were killed externally by shell reaping with no code error and healthy
   memory - run 1 lost all in-memory timing (no checkpoint existed), run 2 died
   during the day-0 phase. Fixes: per-state checkpoint flush +
   resume-on-relaunch (a robustness addition; thresholds, corpus and measurement
   definitions unchanged), then a fully detached launch (run 3), which completed
   6,041/6,041 states. All three incidents are logged verbatim.
2. One corrupted timing record (disclosed in full): the record
   `seed_40213/development/day_0` first emitted end2end = 9778.44 s
   (`timeout(>30s)`), failing R2/R3/R4 on its face. Diagnosis: it sits at
   checkpoint line 1274 - exactly run 2's kill point - and its 30 s subprocess
   timeout fired only after the harness unsuspended the process, so the wall
   delta measured ~2.7 h of PROCESS SUSPENSION, not policy compute. Evidence:
   8 clean re-measurements of the same state ran in 0.15-0.18 s (median 0.1545 s);
   no system-sleep event exists in the window; the other 6,040 invocations all
   ran < 0.444 s through identical policy code. Correction: that single record
   was re-measured cleanly and the gates re-emitted. The 3.0 s threshold, the
   state, the policy, the solver and the corpus were NOT changed; no easier
   state was substituted; the original 9778.44 s value and the correction are
   preserved in `runtime_benchmark.json` `remeasurement_applied` and in the run
   log. This is a measurement-integrity correction, not a gate relaxation.
3. Reconstruction clarification (S.7): the recorded parent corpus advanced via
   the parent's priority-RNG greedy `chosen`, not `kit.baseline_match`
   (the reference fingerprint). Replaying `kit.baseline_match` diverges
   (day-1 n_available 118 vs recorded 116) and would fail the binding
   reproduce-n_edges+k_greedy rule, so the parent trajectory was reimplemented
   identically (nothing imported from the sealed parent) and reproduces every
   recorded n_edges + k_greedy exactly - 0 reconstruction failures of 6,041.
   Logged as a clarification before timing began.
4. R-D sampling interpretation (logged before timing): "remaining non-day-0 rows
   not in R-B/R-C", sorted by (seed_group, variant, day), then
   `random.Random(20261014).sample(list, 3000)` - one deterministic, logged
   reading of the frozen wording.
5. C5 cross-check: 665 of 9,071 old/new solver comparisons disagree, all in the
   near-tie/last-bit families (F7 zero/near-zero: 130, F8 close-float: 535) and
   all explained by the old solver's float EPS=1e-9 and node limits; 0 cases
   where the new solver was suboptimal; pass per the pre-registered rule that
   requires every disagreement explained before C5 can pass.
6. The decisive scientific outcome: the result is INCONCLUSIVE. The point
   estimate is positive but tiny (+0.004) with CI [-0.048, +0.058] and
   win/loss 35/40 - 100 seed groups of a weak-signal model do not resolve an
   effect of this size. The limitation is evidence-backed (Q6/Q7: scores
   compressed near the ~0.01 base rate, 99.2% of states below 0.02 spread) and
   is exactly why the decision is PROCEED WITH CHANGES rather than PROCEED.
7. Runtime asymmetry observed (not gated): candidate evaluation episodes averaged
   18.23 s of evaluator-measured inference vs greedy's 13.89 s - the candidate
   pays scoring + solver overhead, though still far inside the 10 s-per-invocation
   limit (max in-process invocation 0.39 s).
8. Uncertainty that remains unresolved by construction: whether a higher-power
   design (more seed groups) or a better-calibrated frozen model would move the
   CI off zero; whether the per-variant heterogeneity (cold_start -0.035 vs shift
   +0.030) is signal or noise. Neither can be answered from these 100 groups, and
   S.11 forbids a second experiment under this registration - they require a NEW
   pre-registration, which this report does not authorize.

## Integrity appendix

- Final gate: `python scripts/srws_integrity.py` performs 14 checks - (1) this
  experiment's seal round-trip over every file (excluding `integrity.sha256` and
  `__pycache__`, parent seal format: sorted, unique, `<64-hex>  <path>`); (2) the
  PARENT experiment's 1,638-entry `integrity.sha256` re-verified READ-ONLY (the
  parent's own `sr_verify.py` is not run - it writes into the sealed directory);
  (3) kit.py / evaluate.py / Dockerfile / requirements.txt git-clean; (4) policy.py
  working-tree M is the pre-existing one (last commit 2026-10-05, noted at
  experiment start; never written by this experiment); (5-8) frozen hashes:
  analysis_plan.md == `ed1210c2...`, parent model artifact == `7f1ddfe0...`,
  sr_features.py == `76fc12f6...`, sr_policy_core.py == `02af1e6a...`;
  (9-14) presence and headline flags of solver_validation (passed=true),
  runtime_benchmark, policy_validity (passed=true), benchmark_corpus,
  paired_stats, report.md. Verdict: 14/14 checks PASS, recorded in
  `results/final_integrity.json` (the script exits non-zero on any failure).
- Protected surfaces: no file outside `research/round2_stagewise_reward_solver/`
  was written; `policy.py`, `kit.py`, `evaluate.py`, `Dockerfile`,
  `requirements.txt` and the entire sealed parent experiment are unmodified; no
  git-mutating command was ever run; the parent seal verifies unchanged.
- Frozen artifacts: plan hash verified at freeze and re-verified at Task 6; model
  artifact hash verified at pre-registration, Task 3, immediately after the final
  evaluation (P4) and Task 6; copy hashes byte-identical.
- Machine-readable outputs: `results/solver_validation.json`,
  `results/benchmark_corpus.json`, `results/runtime_benchmark.json`,
  `results/policy_validity.json`, `results/eval_greedy.json`,
  `results/eval_candidate.json`, `results/paired_stats.json`,
  `results/final_integrity.json`; process history in `run_log.txt`.
- Candidate status: `policy_candidate.py` passed every gate and the official
  evaluation, but `policy.py` remains the untouched official default; nothing was
  promoted, and no claim of competition approval is made (S.11).

## Closing

Exactly one decision was emitted - **PROCEED WITH CHANGES** - under the frozen
S.9 rules: all C/R/P gates passed, the paired evaluation was valid and complete,
and the pre-registered CI includes 0. There is nothing to promote under this
registration; any further work requires a new pre-registration with its own
frozen hash.
