# OPR Validation Plan (preregistered, Phase 3a)

FROZEN before running any validation diagnostic. Written after Phase 1
derivation (g0_findings.md) and Phase 2 unit tests (22/22 green), BEFORE any
calibration or headroom number was computed. Thresholds below may not be
relaxed after results are seen; any deviation must be documented as a
protocol violation in report.md.

## 1. Datasets (immutable inputs)

D1 primary calibration — `research/next_method_search/n01_introductions.jsonl`
  sha256 25c018c29f9c6bb26578eb692fb41998d2ca7a923369e7450c6b2a1aa5f2b91a
  8,433 per-intro rows; 126 worlds = seeds 143..163 x 6 variants;
  90 realized MSMI labels. Worlds regenerated with
  kit.generate(seed, 200, 'evaluation', variant) (pool_id is a label only;
  it enters no RNG draw, so regeneration is exact for outcome purposes).

D2 variance-reduction pair —
  `research/e3_rel_experiment/per_arm/C.json`
    sha256 a245c22f5350f6146b5ae05e877dddb40b6415b68eaed999784a12309dc12951
  `research/e3_rel_experiment/per_arm/E1.json`
    sha256 89296ba543caeffcdac939a0b1a76b4361e19f9959449010c4c06d42410414d0
  72 episodes each; seeds 119..130 x 6 variants; archived per-episode
  action_sha256 and mutual_second_meeting_intention used as replay anchors.

## 2. Replay verification (D2 only)

C arm = `policy.py --baseline greedy`; E1 arm =
`research/e3_rel_experiment/policy_e1.py --baseline greedy`, both driven
through `evaluate.episode` (trusted local subprocess, same digest rule:
sha256 over `[phase, day, action]` per decision day). A replayed episode is
ACCEPTED only if BOTH archived action_sha256 AND archived
mutual_second_meeting_intention match exactly. Targets: >=144/144 accepted.
If acceptance < 90% of 144, D2 is declared UNRELIABLE and diagnostic G4 is
not evaluated; the overall gate then reads INCONCLUSIVE and Phase 4 does not
run (stop-and-document path).

## 3. Diagnostics (fixed definitions; executed once, in this order)

D-A Stream re-derivation (validity precondition)
  For every D1 intro row: regenerate its world; call
  simulate_outcome(seed, user_a, user_b, day, variant, members_index(world))
  and compare ['msmi'] to the recorded y_msmi.
  PASS = match rate exactly 1.0 (zero mismatches over all 8,433 rows).
  Any mismatch: OPR is INVALID; stop; do not run D-B..D-E; debug stream.

D-B Global calibration
  O = sum y_msmi; E = sum p_msmi over the same intros;
  R = (O - E) / sqrt(sum p_i (1 - p_i)).
  Variance justification (exact, not approximate): every intro has its own
  rand_for(seed, a, b, day) stream; pairs never repeat; therefore,
  conditional on the fixed world hidden state, intro outcomes are mutually
  independent Bernoulli with the computed p_i. Hence
  Var(O - E | world) = sum p_i(1-p_i) exactly.
  PASS: |R| <= 3 AND 0.85 <= O/E <= 1.15.

D-C Reliability by p-decile
  Sort all D1 intros by p ascending; split into 10 equal-count bins.
  Per bin: n, mean_p, empirical rate, sigma_bin = sqrt(sum p_i(1-p_i)).
  PASS: every bin with n >= 30 satisfies |emp - mean_p| <= 4 * sigma_bin;
  AND Spearman rho between the 10 bin mean_p values and the 10 empirical
  rates is >= 0.8 with one-sided exact permutation p < 0.01.
  Bins with n < 30 are reported, not gated.

D-D Per-variant calibration (report-only)
  Per variant present in D1: O, E, R as in D-B. Not individually gated;
  flagged if |R| > 4 for any variant (bias detection).

D-E Probability sanity (report-only)
  Percentiles (p50, p90, p99, max) of p over D1; all p must lie in (0, 1)
  (already enforced by unit tests; recorded here for the audit trail).

G4 Variance-reduced pairwise check (D2)
  For each accepted world w: predicted_delta(w) = sum_j p over E1 replayed
  intros minus sum_j p over C replayed intros (each p computed at that
  intro's assigned_day in the regenerated world); realized_delta(w) =
  msmi_E1 - msmi_C from archived rows.
  n_eff = worlds with predicted_delta != 0 (exact float inequality).
  S = count of n_eff worlds where sign(predicted_delta) == sign(realized_delta);
  a realized_delta of 0 with predicted_delta != 0 counts as a mismatch.
  PASS: one-sided exact binomial P(X >= S | X ~ Binomial(n_eff, 0.5)) < 0.05.
  Also reported (not gated): Pearson correlation, mean predicted_delta,
  mean realized_delta, tie count.

## 4. Gate

OPR_VALIDATED iff D-A, D-B, D-C, and G4 all pass (G4 requires D2 replay
acceptance >= 90%; otherwise INCONCLUSIVE -> stop, no Phase 4).
Any D-A failure -> INVALID -> stop immediately.

## 5. Phase 4 headroom — thresholds fixed NOW (before any Phase 4 results)

Only executed if OPR_VALIDATED. All numbers in realized MSMI per 100
arrived members (evaluate.py convention: 100 * msmi / arrived at day 59).

P4-1 Myopic state-conditional oracle bound (primary)
  Full counterfactual rollout on sealed seeds 143..163 x 6 variants:
  asks = kit.baseline_asks (same rule for oracle and control); matching each
  day = maximum-total-p non-overlapping feasible set (p from hidden truth,
  quadrature n=2001 with Richardson; spot-check on 100 random pairs must
  agree with n=8001 to < 1e-9), constrained by sim.available and
  eligibility status == 'feasible' (needs_clarification is infeasible, as
  for any policy). Control = same rollout with kit.baseline_match (greedy).
  Label everywhere: "myopic, state-conditional oracle bound" (same-day p
  mass maximization, no lookahead over busy windows).
  Report: mean MSMI/100 oracle vs greedy, paired per world.

P4-2 Observable-only scorer (secondary, decides practical headroom)
  Features: decision-time observe() only (observed-field soft matches,
  observed hard facts, zone, age, gender, day index, n_available, past
  intro/feedback counts). Target: offline p (hidden-derived) ONLY as
  training target. Model: L2-regularized logistic regression, stdlib,
  fixed lambda=1.0, 200 Newton/IRLS-free gradient steps, lr=0.5 (fixed).
  Split by whole seeds (preregistered): D1 train seeds 143..158, test
  159..163; D2 train seeds 119..125, test 126..130. No seed appears in both.
  Credible-headroom declaration requires ALL of:
    (a) scorer-oracle rollout (P4-1 machinery, p replaced by scorer p-hat)
        minus greedy on held-out test seeds >= +0.5 MSMI/100 (mean over
        test worlds, both datasets pooled);
    (b) paired bootstrap (10,000 resamples of test worlds, seed-level
        pairing) 95% CI lower bound of that difference > 0;
    (c) P4-1 oracle (hidden-p) mean gain over greedy > +0.5 MSMI/100 on the
        same test worlds (otherwise the bound itself is too thin to matter).
  If credible: PROPOSE a candidate policy direction + fresh-seed experiment
  plan in report.md; DO NOT implement or run any new policy or fresh seeds.
  If not credible: conclude oracle headroom is small on sealed worlds; OPR
  line closes with that finding.

## 6. Standing prohibitions (restated)

No edits to kit.py / policy.py / policy_ac.py / evaluate.py / Dockerfile.
No new deployed policy. No fresh-seed comparisons. No hidden-field features
at inference. Nothing under research/round2_opr/ imported by any entrypoint.
No commits. All new files stay under research/round2_opr/.
