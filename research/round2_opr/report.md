# OPR Investigation Report (Outcome-Probability Replay)

Task: determine whether the exact outcome model inside `kit.py` can be turned
into a validated expected-MSMI estimator and used to find policy headroom
over greedy, under strict research-only constraints.

Outcome: **the estimator is exact; the headroom path is not open.**
Gate result: `OPR_NOT_VALIDATED` (preregistered gates D-C and G4 failed).
Phase 4 was therefore barred and not executed. No new policy was implemented
or compared on fresh seeds.

## Phase 1 — derivation (g0_findings.md)

Exact P(MSMI | intro of pair on day) derived from `kit.py` mechanics: shared
latent g couples acceptance and second-intent for both members; date
deadline probability is a finite sum (exactly 1 except in the `delayed`
variant); the `on_time` variable in metrics is dead code — the real
condition is `occurred_day - date_day <= 3`. Determinations:
per-intro RNG streams are independent given hidden state; other
introductions matter only through trajectory (busy windows, pauses,
policy-visible feedback); the probability is computable without modifying
kit.py; required hidden fields are truth/bias/second_bias/response_rate/
variant; those fields are barred at inference by DATA_CONTRACT/FAQ.

## Phase 2 — implementation (opr_core.py, test_opr.py)

22/22 unit tests pass, including 250 randomized equivalence trials against
`kit.Simulator` (event-level and metric-level agreement) and a quadrature
cross-check (Richardson midpoint vs adaptive Simpson < 1e-10).

## Phase 3 — preregistered validation (validation_plan.md)

Frozen before any validation number was computed. Datasets and sha256
anchors: n01_introductions.jsonl (8,433 intros / 126 worlds) and e3
C.json/E1.json (72 paired worlds per arm).

Results (validation_results.json):

| Check | Result | Verdict |
|---|---|---|
| D-A stream re-derivation | 8433/8433 exact | PASS |
| D-B global calibration | O=90, E=82.84, O/E=1.086, R=0.79 | PASS |
| D-C decile reliability | all 10 bins within 4-sigma; Spearman rho=0.778, exact p=0.0054 (threshold rho>=0.8) | **FAIL** |
| D2 replay acceptance | 144/144 digest-verified | PASS |
| G4 variance-reduction sign test | 22/59 sign agreement, exact p=0.98 | **FAIL** |

Per-variant R (report-only): cold_start +1.66, delayed -0.32, development
+0.07, drift +0.28, shift +0.58, sparse -0.71. Probability range:
min 7.5e-5, p50 0.0069, p90 0.021, p99 0.045, max 0.082.

## Interpretation

1. **The outcome model is exact.** D-A reproduces every sealed realized
   label bit-for-bit, and D-B shows no calibration bias. Any future work
   can trust `p_msmi` as the true conditional expectation.

2. **D-C failed narrowly, and not because the model is wrong.** With only
   90 MSMI events across 8,433 intros, per-decile counts are 1-15 events;
   deciles 3-4 inverted on ~1 event each. All bins passed the 4-sigma
   noise check; monotonicity is strongly significant (exact p=0.0054).
   The preregistered rho>=0.8 bar was too strict for 90-event data —
   but thresholds do not move after results are seen.

3. **G4 is the decisive scientific result.** Between two comparable
   policies (greedy vs E1), per-world expected MSMI deltas are tiny
   (mean +0.009, stdev 0.027 events) while realized deltas are +/-1
   event (stdev 0.55). Sign agreement 22/59 is worse than chance
   (Pearson r = -0.098). Expected-value optimization cannot select
   policies at this event rate: the Bernoulli noise floor dominates the
   achievable signal. This is an information limit, not an estimator
   defect — D-A proves the estimator is right.

## Phase 4 — not executed

Preregistration bars Phase 4 unless the gate reads OPR_VALIDATED. The gate
read OPR_NOT_VALIDATED, so the myopic oracle and observable scorer were not
run, and no headroom_results.json exists (by design). This also satisfies
the standing prohibition against new-policy implementation and fresh-seed
comparison.

## Verdict

- OPR estimator: VALIDATED as an exact expectation computer (D-A, D-B).
- OPR as a policy-search instrument: NOT VALIDATED (D-C marginal,
  G4 decisive).
- Round 2 standing: unchanged. Greedy remains the shipped default
  (entrypoint hash c2ea0ffc...8d50). No OPR-derived change is justified.

## Single next action

Accept the information-limit finding: do not pursue expected-MSMI policy
search on sealed worlds at current event rates. If the team wants a second
study (e.g., pooled multi-world delta prediction, or validation on a larger
labelled set), it must start with a NEW frozen preregistration that cites
this failure — not a re-run of these gates.
