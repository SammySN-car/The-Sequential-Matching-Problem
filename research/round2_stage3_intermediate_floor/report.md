# Round 2 Stage 3 - Intermediate-Floor Experiment: Results Report

Schema: round2_stage3_intermediate_floor.
Date: 2026-10-07. Interpretation tags: OBSERVED / DESCRIPTIVE / CAVEAT / UNKNOWN.
Pre-registration: preregistration.md (SHA256 FA11A2FB4DF53D507AA8C4D1A905025FD6392F5B656CC997CEE83FED4BF2D491),
written and hashed BEFORE any run. Threshold exploration ENDS after this
experiment under any outcome (prereg section 8).

## 1. Design (as pre-registered; executed verbatim)

Three arms differ ONLY in the floor argument to the frozen matcher
(policy.py:591 call site; predicate e[2] >= floor at policy.py:469):

    frozen:        float(model["floor"])            = 0.007905174015296758  (policy_ac.py)
    intermediate:  float(model["floor"]) / 2.0      = 0.003952587007648379  (intermediate_policy.py)
    nofloor:       -inf                             (stage2 ablation_policy.py, unchanged)

Seeds 104, 105, 106 (fresh; never used in Round 1, Stage 1.5, or Stage 2),
all six variants, 18 episodes per arm, official evaluate.py, paired by
(seed, variant). Primary: MSMI/100 (family-mean). Secondary: introductions/ep,
mutual/ep, mutual/intro, MSMI/intro, coverage, ask cost, invalids.
Model blob, asks, matcher object, candidate cap, local search, fallback,
evaluator, protocol, and 60+40 horizon frozen. Private holdout untouched.
No sweep; no post-hoc threshold adjustment.

Arm-2 shim hash registered in run_log.txt at 13:55:08, before any run:
intermediate_policy.py SHA256 A76FD0EE0C2B9579A6E6858081C62592A298066386C0D09013CF844FAA07991F
(fail-fast guard: raises unless the received floor argument equals the
registered frozen floor; halving rule applied at call time; frozen matcher
delegated to as-is).

## 2. Integrity (OBSERVED; all gates green)

- 9/9 official runs exit=0, 54/54 episodes valid, eligible summaries.
- Determinism rerun (intermediate seed 104): episodes identical to the
  original EXCLUDING inference_seconds; primary_score match.
- Diagnostic fidelity: 9/9 diag runs ALL_FIDELITY_OK (official metrics +
  action_sha256 reproduced in-process); FALLBACK_CALLS 0 in all 9.
- Purity carried from Stage 2 architecture: same-state ask/match digests,
  frontier recheck 0 failures, instrument mismatches 0, cap hits 0,
  protocol violations 0, exceptions 0.
- Frozen hashes unchanged: policy.py 379CC2D9..., policy_ac.py 90FB9AD3...;
  Round 1 results/ + artifact.sha256 untouched; Stage 1.5 and Stage 2
  artifacts untouched; no new git commits.
- Shim pre-flight: wrong-floor guard rejects, empty-graph delegation OK,
  floor/2.0 == registered intermediate value.

## 3. Overall results (mean over 18 episodes per arm; seeds 104-106)

| Metric | frozen | intermediate | nofloor |
|---|---:|---:|---:|
| introductions/episode | 57.94 | 64.11 | 69.17 |
| mutual/episode | 8.50 | 9.50 | 9.33 |
| mutual/intro | .1467 | .1482 | .1349 |
| MSMI/episode | .50 (9 ev) | .72 (13 ev) | .56 (10 ev) |
| MSMI/intro | .0086 | .0113 | .0080 |
| **MSMI/100 (primary)** | **.2500** | **.3611** | **.2778** |
| coverage | .3086 | .3142 | .3153 |
| ask cost/ep | 423.3 | 417.9 | 417.9 |
| invalid | 0 | 0 | 0 |

Totals: introductions 1043 / 1154 / 1245; mutual 153 / 171 / 168;
MSMI 9 / 13 / 10; ask cost 7620 / 7523 / 7523.

MSMI counts are TINY (9/13/10 events total). No significance is claimed
anywhere in this report (prereg + task constraints).

## 4. Paired deltas (n=18 per contrast; DESCRIPTIVE)

intermediate - frozen:
  intro +6.17 mean, median +5, range [-3,+18], 15+/1/2-   bootstrap CI [+3.67,+8.33]
  mutual/intro +.0013 CI [-.065,+.041]  (12+/0/6-)
  MSMI/100 +.1111 CI [-.167,+.250]      (6+/11/1-)
  coverage +.0056 (13+/4/1-)   ask -5.39 (1/1/16-)
intermediate - nofloor:
  intro -5.06 (1+/2/15-)               bootstrap CI [-8.17,-2.17]
  mutual/intro +.0050 CI [-.021,+.043]
  MSMI/100 +.0833 CI [0,+.250]         (5+/11/2-)
  coverage -.0011 (2+/10/6-)   ask 0.00 (8+/5/5-)
nofloor - frozen:
  intro +11.22, 18+/0/0-               bootstrap CI [+10.50,+11.83]
  mutual/intro -.0037 CI [-.044,+.048]
  MSMI/100 +.0278 CI [-.167,+.250]
  coverage +.0067 (14+/4/0-)   ask -5.39 (2+/1/15-)

Per-seed intro deltas (intermediate - frozen): +3.67, +6.50, +8.33 (all
positive). (nofloor - frozen): +11.83, +11.33, +10.50 (all positive).
Bootstrap over 3 seed clusters is DESCRIPTIVE ONLY - not inferential.

## 5. Out-of-sample replication of Stage 2 (OBSERVED)

- Volume: nofloor - frozen = +11.22 intro/ep, 18+/0/0-, CI [+10.5,+11.8].
  Stage 2's causal volume finding (+16.7%, 17+/1/0-) REPLICATES on fresh
  seeds 104-106 (+19.4% relative here). The frozen floor's suppression of
  volume is no longer an in-sample observation.
- Primary: Stage 2 had nofloor .333 vs frozen .250; here .278 vs .250 -
  the nofloor primary advantage is smaller on new seeds and its CI includes
  0 in both stages. Quality-side claims remain weak in both stages.
- Zero-selection days: frozen 520 (100% all_below_floor) vs nofloor 0 -
  Stage 2's 411/411 pattern replicates (520/520).

## 6. Funnel (pooled 3 seeds x 6 variants x 60 days) + CAVEAT

    frozen:       9,420 feasible -> 1,369 >= floor (14.5%) -> 1,043 selected
                  zero-selection-with-cand days: 520 (cats: all_below_floor 520)
    intermediate: 3,845 feasible -> 1,755 >= floor/2 (45.6%) -> 1,154 selected
                  zero-selection-with-cand days: 368 (cats: all_below_floor 368)
    nofloor:      2,155 feasible -> 2,155 after floor -> 1,245 selected
                  zero-selection-with-cand days: 0

CAVEAT (same as Stage 2): do NOT compare feasible counts (9,420 vs 3,845 vs
2,155) as exogenous opportunity sets. Arms differ in when/how much they
introduce, which changes availability, busyness, and later candidacy -
endogenous depletion. Observed zero-candidate days: 8 / 160 / 503.

## 7. Survivorship - four-way split by score band (DESCRIPTIVE; selected pairs only)

Intermediate arm (n=1,154):
    ge_frozen       n=707  mutual .1683  MSMI .0099 (7 ev)
    mid_band        n=447  mutual .1163  MSMI .0134 (6 ev)   <- admitted by floor/2 only
Nofloor arm (n=1,245):
    ge_frozen       n=678  mutual .1519  MSMI .0059 (4 ev)
    mid_band        n=384  mutual .1146  MSMI .0130 (5 ev)
    lt_intermediate n=183  mutual .1148  MSMI .0055 (1 ev)   <- admitted by nofloor only
Frozen arm: all 1,043 are ge_frozen (mutual .1467, MSMI .0086).

Caveats (prereg + Stage 2 lessons): these are SELECTED pairs on each arm's
own trajectory - not unbiased samples of any candidate band. The mid_band
mutual rate is consistently ~30-35% below the ge_frozen rate within the
same arm (score carries ranking information), yet its MSMI counts (6/13
intermediate, 5/10 nofloor) are the bulk of each arm's MSMI events - with
counts this small this is NOT evidence that mid_band is better on MSMI,
only that the band contributes meaningfully. The lt_intermediate band
produces mutuals too (21/183 = .115) - it is weaker, not useless.

## 8. Asks (OBSERVED)

- Day-0 asks identical for all three pairwise contrasts (54/54 rows).
- First ask divergence days: if {1,2,3}, in {1,3,4,7,9,25,26}, nf {1,2};
  first match divergence is day 0 for most pairs (floors differ from the
  first decision). Ask divergence never precedes match divergence -
  ask differences are trajectory-mediated, NOT direct floor reads
  (ac_asks never reads the floor; structural, carried from Stage 2).
- Ask cost: frozen 7,620 vs intermediate 7,523 vs nofloor 7,523 (-1.3%
  for both vs frozen); intermediate vs nofloor paired mean delta 0.00.

## 9. Greedy overlap (per-episode distinct sets)

    frozen        overlap_of_S .7315  mean_jaccard .6514
    intermediate  overlap_of_S .7617  mean_jaccard .7305
    nofloor       overlap_of_S .7695  mean_jaccard .7753

With the matcher frozen and unmodified, looser floors shift selection
toward the greedy reference's picks (more greedy picks pass the looser
filter) - consistent with Stage 2's pattern; no matcher change occurred.

## 10. Outcome signals + discipline

DESCRIPTIVE dominance flags (summary.json -> dominance_signals):
    primary intermediate >= frozen        TRUE (.3611 vs .2500)
    primary intermediate >= nofloor       TRUE (.3611 vs .2778)
    intro intermediate >= frozen          TRUE (64.11 vs 57.94)
    intro intermediate <= nofloor         TRUE (64.11 vs 69.17) [sanity]
    favorable_signal_all                  TRUE

Per preregistration.md section 8 this flag is a DESCRIPTIVE SIGNAL ONLY:
threshold exploration ENDS after this experiment under any outcome. A
favorable signal is a candidate for a SEPARATE, later, freshly
pre-registered holdout-promotion decision - it never justifies trying more
threshold values. The reverse (a null result) would have closed threshold
exploration in this phase. Either way: no further threshold iteration.

What this does NOT establish: no statistical significance (3 clusters,
descriptive bootstrap); no MSMI claim (9/13/10 events; I-frozen MSMI/100
CI [-.167,+.250] includes 0); no holdout claim; no long-horizon claim
(depletion caveat section 6); survivorship bands are selected, not
unbiased; per-variant cells are noise-dominated (e.g., intermediate MSMI/100
0 in delayed vs .333 for both others).

## 11. Files (research/round2_stage3_intermediate_floor/)

preregistration.md + .sha256 (pre-run), intermediate_policy.py (shim,
hash-registered pre-run), diagnose3.py, analyze3.py, run_log.txt,
arm_{frozen,intermediate,nofloor}_seed{104,105,106}.json (9 official),
arm_intermediate_seed104_rerun.json (determinism),
diag_arm_{frozen,intermediate,nofloor}_seed{104,105,106}.json (9, all
fidelity OK), summary.json, report.md (this file).

Context anchors (frozen, cross-stage): Stage 2 seeds 101-103 - frozen .250/
66.72 intro, nofloor .333/77.83; Round 1 greedy primary .389 (same protocol
family). On fresh seeds, intermediate .361 sits between nofloor .278 and
Round 1 greedy .389 - out-of-sample, neither floor arm has passed greedy's
primary; the greedy gap remains an open question (per Stage 2 interpretation
memo section 6, unknown #7).