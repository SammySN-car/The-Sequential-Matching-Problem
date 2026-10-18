# Round 2 Stage 3 - Final Interpretation and Promotion-Readiness Audit

Schema: round2_stage3_final_audit_v1.
Date: 2026-10-07. Status: INTERPRETATION AND AUDIT ONLY - no experiment run,
no code modified, no threshold created, holdout untouched.
Interpretation tags: OBSERVED / CAUSAL / DESCRIPTIVE / CAVEAT / UNKNOWN.
Companion records: report.md (Stage 3 results), summary.json (data),
preregistration.md (SHA256 FA11A2FB4DF53D507AA8C4D1A905025FD6392F5B656CC997CEE83FED4BF2D491),
run_log.txt.

## 1. Frozen research history (preserve the causal chain)

Round 1
-> A+C underperformed greedy on the primary metric (greedy .389, A+C .250,
   same protocol family, seeds 101-103).

Stage 1.5 (frozen)
-> Read-only diagnosis identified the frozen score floor as the dominant
   observed bottleneck (seed 101: 4,205 feasible -> 611 above floor -> 434
   introduced; 85.5% removed; 148/148 zero-selection days all_below_floor;
   local search 0/360; asks not the cause).

Stage 2 (frozen)
-> Pure floor ablation (frozen vs -inf, seeds 101-103) showed removing the
   floor recovered substantial useful volume (+16.7%, 17+/1/0-) with no
   evidence of meaningful quality collapse; 411/411 zero-selection days
   all_below_floor vs 0 under no-floor.

Stage 3 (pre-registered; completed exactly as written)
-> Intermediate floor at exactly float(model["floor"]) / 2.0.
   Current exact value: 0.003952587007648379
   Original frozen floor: 0.007905174015296758
   Seeds 104, 105, 106 (fresh), six variants, 18 episodes x 3 arms.

No threshold exploration is permitted after Stage 3 (preregistration.md
section 8; reaffirmed by this audit).

## 2. Stage 3 experiment (as executed)

Arms (single floor-argument difference; everything else frozen):
    A. frozen:        float(model["floor"])
    B. intermediate:  float(model["floor"]) / 2.0
    C. nofloor:       -inf

| Metric | Frozen | Intermediate | No floor |
|---|---:|---:|---:|
| MSMI/100 (primary) | .2500 | .3611 | .2778 |
| introductions/episode | 57.94 | 64.11 | 69.17 |
| mutual/intro | .1467 | .1482 | .1349 |
| coverage | .3086 | .3142 | .3153 |
| ask cost/episode | 423.3 | 417.9 | 417.9 |
| invalid | 0 | 0 | 0 |

MSMI event counts: frozen 9, intermediate 13, nofloor 10.
Paired volume: nofloor-frozen +11.22 (18+/0/0-, cluster CI [+10.5,+11.8]);
intermediate-frozen +6.17 (15+/1/2-, CI [+3.67,+8.33]).
Intermediate-frozen MSMI/100 CI: [-.167, +.250] (descriptive, 3 clusters).
Integrity: 9/9 runs exit 0; 54/54 valid; deterministic rerun identical excl.
inference_seconds; 9/9 diagnostics ALL_FIDELITY_OK; 0 fallbacks; 0 caps;
0 exceptions; frozen hashes unchanged; preregistration and shim hashes
re-verified immutable after execution; history records intact; holdout
untouched.

## 3. Final Stage 3 interpretation

### 3.1 Directly observed facts (OBSERVED / DESCRIPTIVE only)

1. Primary point estimates on seeds 104-106: intermediate .3611 >
   nofloor .2778 > frozen .2500. Event counts behind them: 13 / 10 / 9.
2. Introductions order monotonically: 57.94 < 64.11 < 69.17 per episode.
   nofloor-frozen = +11.22 with 18+/0/0-; intermediate-frozen = +6.17 with
   15+/1/2-. Cluster CIs are descriptive.
3. Intermediate recovers approximately 55% of the frozen->nofloor volume
   gap ((64.11-57.94)/(69.17-57.94) = 6.17/11.22) while its pooled
   mutual/intro (.1482) and coverage (.3142) sit above both endpoints
   (.1467/.3086 frozen; .1349/.3153 nofloor).
4. Funnel (pooled 3x6x60): frozen 9,420 feasible -> 1,369 >= floor (14.5%)
   -> 1,043 selected, with 520 zero-selection-with-cand days (100%
   all_below_floor); intermediate 3,845 feasible -> 1,755 >= floor/2
   (45.6%) -> 1,154 selected, 368 zero-selection days (100%
   all_below_floor); nofloor 2,155 -> 2,155 -> 1,245, 0 zero-selection
   days. Zero-candidate days: 8 / 160 / 503 (trajectory-dependent).
5. Four-way survivorship (selected pairs only, each arm's own trajectory):
   within the intermediate arm, ge_frozen n=707 mutual .1683 / MSMI 7 vs
   mid_band n=447 mutual .1163 / MSMI 6; within the nofloor arm, ge_frozen
   .1519 / mid_band .1146 / lt_intermediate n=183 mutual .1148 / MSMI 1.
   Frozen arm: all 1,043 ge_frozen, mutual .1467, MSMI 9.
6. Asks: day-0 asks identical for all three pairwise contrasts; first ask
   divergence never precedes first match divergence; ask totals 7,620 /
   7,523 / 7,523; intermediate-nofloor paired ask delta mean 0.00.
7. Robustness cell counts: intermediate introductions exceed frozen in all
   six variants; primary intermediate >= frozen in 5/6 variants (tie
   cold_start, lower only in delayed: 0 vs .3333 for both others);
   coverage intermediate >= frozen in 5/6 (1 tie); ask cost lower in 6/6;
   pooled mutual/intro intermediate vs frozen is mixed per variant (3 up,
   3 down) with a +.0015 pooled edge.
8. Greedy overlap rose monotonically with looser floors (overlap_of_S
   .7315 -> .7617 -> .7695) with the matcher object unchanged.
9. Integrity facts listed in section 2 are all directly observed.
10. Cross-stage observation: Stage 2's volume finding replicates on fresh
    seeds (+11.22, 18+/0/0- here vs +16.7%, 17+/1/0- there), and the
    all_below_floor zero-selection pattern replicates (520/520 vs 411/411).

Not directly supported: any claim that the intermediate floor IMPROVES
MSMI, that it is optimal, or that it beats greedy. The intermediate-frozen
primary CI [-.167,+.250] includes 0, the median paired MSMI/100 delta is
0, and per-variant cells are noise-dominated at 9-13 total events.

### 3.2 What Stage 3 causally supports (CAUSAL, scope-limited)

The intervention was pure (one floor argument; pre-state ask/edge/score
identity carried by the Stage 2 purity architecture; 9/9 diagnostic
fidelity against official digests), and arms are paired on identical
worlds. Within this protocol, horizon, and seed set:

a) The original floor WAS too restrictive as a volume gate - CAUSAL.
   The causal chain now replicates twice on independent seed sets: loosening
   the floor increases introductions (+11.22, 18+/0/0-) and eliminates
   100% all_below_floor zero-selection days (520 -> 0 for nofloor; the
   intermediate arm still blocks 368 days, all below floor/2, showing the
   intermediate setting retains a real, still-binding gate).

b) The nofloor endpoint appears too permissive on quality-per-volume -
   DESCRIPTIVE, not established as strongly as (a). Evidence consistent
   with this: nofloor has the lowest pooled mutual/intro (.1349) and the
   weakest bands in its own survivorship (mid_band .1146, lt_intermediate
   .1148 mutual/intro vs ge_frozen .1519), while carrying the largest
   weak-band share; its primary point estimate (.278) sits below the
   intermediate (.361). The paired intermediate-nofloor primary CI
   [0, +.250] TOUCHES 0 - so "nofloor is worse on quality" is NOT
   established. Correct wording: the evidence does not favor nofloor as
   the quality-volume choice, but does not prove its inferiority either.

c) floor/2 represents a PLAUSIBLE quality-volume balance - YES, as a
   plausible/promising candidate, not a proven one. It is the only tested
   interior point; it orders volume between the endpoints, recovers ~55%
   of the volume gap, posts the highest primary and pooled mutual/intro
   point estimates of the three arms, costs less ask than frozen (-1.3%),
   and shows no evidence of meaningful quality collapse on any pooled
   secondary metric (coverage and mutual/intro both above frozen;
   MSMI/intro .0113 vs .0086 point estimate only).

d) Is the observed intermediate result sufficient to claim MSMI
   improvement? NO. 13 vs 9 events; CI [-.167,+.250] includes 0; median
   paired delta 0 (11/18 ties); delayed variant moved 0 vs .3333. The
   only supportable phrase is "favorable descriptive result". This audit
   treats the primary ordering as a promising candidate signal, never as
   "statistically significant improvement", "proven best", or "optimal
   threshold".

### 3.3 What remains unresolved (UNKNOWN)

1. MSMI uncertainty: 9/13/10 total events cannot separate a real quality
   effect from noise; every quality CI includes 0 (the intermediate-nofloor
   primary CI only touches 0 at its lower bound).
2. Seed-cluster limitation: bootstrap has 3 clusters and is descriptive by
   preregistration; no inference is licensed at any level of this report.
3. Generalization: seeds 104-106 are fresh relative to design, but they
   are still development worlds from the same generator/protocol; the
   private holdout (120 worlds) remains untouched and unknown. Freshness
   reduces - not eliminates - design overfitting.
4. Long-horizon depletion: zero-candidate days 8 / 160 / 503 show the
   arms diverge in endogenous availability; +6.17 and +11.22 are
   within-horizon (60-day) quantities; behavior at longer horizons is
   unobserved.
5. Calibration: score rank-association is observed (ge_frozen converts
   better than lower bands within arms); probability calibration has never
   been measured. floor/2's absolute value has no calibrated meaning.
6. Why .3611 vs .389 does NOT establish that A+C is now better than
   greedy: (i) the two numbers come from DIFFERENT seed sets - greedy's
   .389 is Round 1 on seeds 101-103, intermediate's .3611 is Stage 3 on
   seeds 104-106 - so the comparison is unpaired and confounds policy
   with seed set; (ii) no uncertainty interval for greedy-versus-
   intermediate exists in the stored evidence (none is invented here);
   (iii) both numbers rest on handfuls of MSMI events; (iv) even taken at
   face value, .3611 < .389 means the candidate still trails greedy on
   the observed primary. What CAN be said: no floor-variant arm in
   Rounds 1-3 has yet matched greedy's observed primary.
7. Whether the intermediate advantage persists outside seeds 104-106 is
   precisely the unknown that only a separate generalization evaluation
   can answer; nothing in the development evidence answers it.

## 4. Promotion-readiness audit: is floor/2 mature enough to become the
frozen candidate for the next legitimate evaluation/promotion decision?

### A. Experimental integrity - PASS

- Preregistration before execution: PASS. preregistration.md written and
  hashed FA11A2FB... ; run_log.txt shows PRE-RUN REGISTRATION entries at
  13:55:08 for prereg, shim (A76FD0EE...), apparatus, and seeds, with
  "NO RUNS YET"; first run logged afterwards. Both hashes re-verified
  immutable after execution (final verification log entry).
- Exact intervention: PASS. Single floor argument at the one call site;
  intermediate shim halves the received registered floor (guard raises on
  any other value); endpoints identical to Stage 2 definitions; primary
  rule float(model["floor"]) / 2.0 = 0.003952587007648379 exactly as
  registered.
- Frozen artifacts: PASS. policy.py 379CC2D9..., policy_ac.py 90FB9AD3...
  unchanged; Round 1 results/artifact.sha256 untouched; Stage 1.5 probe
  digest 3897D631... intact; Stage 2 report.md (15,173 B) and
  interpretation.md (14,848 B) intact; no new git commits.
- No holdout access: PASS. No holdout file was read or written at any
  point of Stage 3; holdout performance remains unknown by design.
- Deterministic reproduction: PASS. Intermediate seed-104 rerun identical
  excl. inference_seconds; primary_score match; 9/9 diagnostic runs
  reproduce official metrics + action_sha256.
- No invalid episodes: PASS. 54/54 valid; 0 exceptions; 0 protocol
  violations; 0 zero-introduction episodes.
- No fallback/cap contamination: PASS. 0 fallback calls across all 9
  diagnostic runs; 0 candidate caps; frontier recheck 0 failures;
  instrument mismatches 0.
- No hidden policy changes: PASS. Model blob, ac_asks, matcher object,
  candidate cap, local search, fallback, evaluator, protocol, horizon all
  byte-identical to Round 1; the shim is the only behavioral delta and it
  is hash-registered.

### B. Causal interpretation - PASS

- Stage 2's floor bottleneck finding replicated: PASS. +11.22 intro/ep
  (18+/0/0-, CI [+10.5,+11.8]) on fresh seeds; 520/520 zero-selection
  days all_below_floor vs 0 under nofloor (Stage 2: 411/411 vs 0).
- Intermediate result is interpretable: PASS. Pure dose-response design -
  three floor settings, same worlds, same machinery - yields ordered
  volume (57.94 < 64.11 < 69.17) and an interior primary point estimate
  above both endpoints; the funnel shows the mechanism (14.5% -> 45.6% ->
  100% of feasible candidates passing the gate).
- Endpoints provide useful anchors: PASS. Frozen anchors the current
  policy; nofloor anchors the degenerate limit; together they bracket the
  interior so floor/2 is interpretable as a tested point between two
  measured extremes rather than a number chosen in a vacuum.
- Conclusion avoids overclaiming: PASS. This audit claims only
  "favorable descriptive result", "no evidence of meaningful quality
  collapse", "promising candidate". It explicitly does NOT claim
  significant MSMI improvement, optimality, proven superiority over
  nofloor on quality, or greedy parity.

### C. Performance evidence - PASS (as candidacy evidence; NOT as proof)

- MSMI/100: intermediate highest of the three arms (.3611 vs .2500 /
  .2778) - descriptive only; CI [-.167,+.250] includes 0; 13 events.
  Not treated as conclusive anywhere in this audit.
- Introductions: strongest result in the stage - +6.17 vs frozen
  (15+/1/2-, CI excl. 0 descriptively), monotone ordering, all six
  variants positive vs frozen.
- mutual/intro: .1482 pooled, above both endpoints; per-variant mixed
  (3 up / 3 down vs frozen) - acceptable, no collapse.
- coverage: .3142, above frozen (.3086), essentially tied with nofloor
  (.3153); 5/6 variants up vs frozen, 1 tie.
- ask cost: 417.9 vs 423.3 frozen (-1.3%), trajectory-mediated (day-0
  asks identical; divergence follows match divergence) - strictly
  favorable, no cost regression.
- Per-variant behavior: no catastrophic cell; the one adverse cell is
  delayed MSMI/100 (0 vs .3333 both others) - acknowledged as noise-
  level with these event counts.
- Comparison with Round 1 greedy: intermediate .3611 < greedy .389 -
  a real limitation recorded here and in section 6; it does not block
  candidacy (candidacy is about freezing a candidate for evaluation, not
  about having already won), but it forbids any "matches greedy" claim.

### D. Robustness - PASS

- Worked across all six variants: PASS (intro up vs frozen in 6/6;
  primary >= frozen in 5/6).
- Valid on all episodes: PASS (54/54, all three arms).
- No catastrophic behavior in sparse/cold-start/delayed/shift/drift:
  PASS. Sparse (the hard variant): intermediate .1667 primary vs frozen
  0 and nofloor .1667 - no degradation. Cold start: .5 (tied frozen,
  above nofloor's .1667). Delayed: 0 - the single adverse cell, flagged.
  Shift: .5 (above both). Drift: .5 (above both). Volumes never collapse
  (lowest variant intro still exceeds frozen's counterpart).
- Deterministic behavior: PASS (rerun identical excl. inference_seconds).
- Resource/protocol constraints: PASS (0 caps, fixed 60+40 horizon,
  same candidate cap, same evaluator, ask cost lower not higher).

### E. Research discipline - PASS

- Threshold exploration ends here: PASS - reaffirmed by this document;
  preregistration section 8 executed as written (favorable result did not
  trigger any further threshold run).
- No post-hoc threshold tuning: PASS - shim hash A76FD0EE... registered
  before execution and unchanged after; threshold value unmodified.
- Private holdout untouched: PASS.
- Historical findings frozen: PASS - Round 1, Stage 1.5, Stage 2 records
  byte-identical; Stage 2's interpretation memo and Stage 3's results
  report remain as written.
- Favorable result not used to rewrite Stage 1.5 or Stage 2: PASS - the
  causal chain in section 1 is stated exactly; Stage 3 adds a rung, it
  does not retrofit earlier conclusions; earlier caveats (survivorship
  bias, endogenous depletion, descriptive bootstrap) are carried forward
  unchanged rather than being "resolved" by the new point estimate.

## 5. Promotion decision

DECISION: 2 - READY FOR FROZEN CANDIDATE.

floor/2 (0.003952587007648379, shim SHA256 A76FD0EE..., rule
float(model["floor"]) / 2.0) may now be frozen as the candidate policy
for a SEPARATE, freshly pre-registered final/generalization/promotion
evaluation. This decision means exactly one thing: development evidence
is sufficient to stop development tuning and freeze this candidate. It
does NOT mean floor/2 is optimal, proven better than nofloor on quality,
proven to beat greedy, proven to generalize, or that its holdout
performance is known - none of which is established.

Why NOT option 1 (another development experiment): the pre-registered
chain (identify bottleneck -> causal ablation -> pre-registered interior
on fresh seeds) has completed its arc; the volume axis is causally
settled and replicated; the primary axis is favorable-descriptive and can
ONLY be resolved by evaluation on unseen data, not by more runs on the
same development generator. Another development experiment would iterate
against evidence we have already seen.

Why NOT option 3 (private holdout now): the primary CI includes 0, total
MSMI events are 13 vs 9 vs 10, only 3 seed clusters exist, and the
candidate still trails greedy's observed .389. A favorable point estimate
is explicitly insufficient justification for spending the one clean
confirmatory instrument; holdout use requires its own pre-registration
and is a decision for the promotion gate, not for this audit.

Why option 2 explicitly includes an overfitting rationale: continued
development tuning (threshold variants, model refits, ask changes) aimed
at raising .3611 or crossing .389 would consume the remaining randomness
of seeds 101-106 - converting development seeds into a tuning target and
producing selection bias no bootstrap on 3 clusters could detect. The
preregistered threshold exploration has ENDED; extending it under any
new name (finer grid, quantile floors, retuned scoring) is the same
overfitting move with different packaging. The only untested axis is
generalization to unseen worlds, which development runs cannot supply.

## 6. Comparison against the real baseline

    Round 1 greedy:        MSMI/100 = .389   (seeds 101-103, 18 episodes,
                                              Round 1 frozen evidence)
    Stage 3 intermediate:  MSMI/100 = .3611  (seeds 104-106, 18 episodes)

What this comparison MEANS: on the currently observed development
evidence, the A+C family - even at its best pre-registered interior
point - has not matched greedy's observed primary score; the headline
gap is .389 - .3611 = .028 MSMI/100 in greedy's favor.

What it does NOT mean:
- It is NOT a paired comparison: different seed sets (101-103 vs
  104-106). Any of the gap could be seed-set noise; equally, none of it
  could be. No uncertainty interval for greedy versus floor/2 exists in
  the stored evidence, and none is invented here.
- It does NOT establish greedy > floor/2 on the same worlds, nor
  floor/2 >= greedy anywhere.
- Both numbers rest on small MSMI event counts; .389 itself has not been
  re-examined under any Stage 2/3 lens.
- It does NOT show A+C "is now better than greedy" - nothing in Rounds
  1-3 supports that claim for any A+C variant.

Is the gap small enough to justify further development tuning? No.
- The gap is small in absolute terms (.028) but large relative to the
  measurement noise (single-digit event counts per arm; a couple of
  MSMI events shift the primary by >.1).
- Tuning specifically toward beating .389 would target a known
  development benchmark number - textbook overfitting to Round 1's seed
  set, and explicitly barred by the Stage 3 pre-registration's
  threshold-exploration closure (and forbidden again by this audit for
  model/ask variants aimed at the same target).
- The correct next step is generalization/holdout evaluation of the
  frozen candidate under a separate pre-registration - NOT more model
  experimentation. If the candidate fails there, that failure is
  informative; if development tuning continues first, we lose the
  ability to distinguish luck from fit.

## 7. Final recommendation

### Current best policy (what is frozen)

The frozen candidate specification - NOT a production change:
- Rule: matcher floor argument = float(model["floor"]) / 2.0
  = 0.003952587007648379 (original floor 0.007905174015296758 halved).
- Apparatus: research/round2_stage3_intermediate_floor/intermediate_policy.py
  (SHA256 A76FD0EE0C2B9579A6E6858081C62592A298066386C0D09013CF844FAA07991F),
  registered before execution.
- Everything else remains Round 1 frozen: policy.py (379CC2D9...),
  policy_ac.py (90FB9AD3...), model blob, ac_asks, matcher object,
  candidate cap, local search, fallback, evaluator, protocol, horizon.
  policy.py itself is NOT modified by this decision.
- Evidence package: preregistration.md (FA11A2FB...), report.md,
  summary.json, 9 official + 9 diagnostic JSONs, run_log.txt, this audit.

### Evidence level: MODERATE

Justification for MODERATE (not weak, not strong):
- Strongest components: experimental integrity (all PASS, double-hash
  immutability, 54/54 valid, perfect fidelity); causal volume result
  replicated across two independent seed sets (18+/0/0-, tight
  descriptive CI); zero-selection mechanism replicated (520/520 vs 0).
- Weakest components: the primary metric rests on 13 vs 9 vs 10 events
  with a CI including 0; only 3 clusters; one fresh seed set; per-variant
  primary cells are noisy (one adverse cell: delayed); calibration
  unknown; candidate still trails greedy's .389 observed primary.
- Net: enough to freeze and evaluate (development confidence), not enough
  to assert quality superiority (evaluation uncertainty remains large).

### Promotion status: 2 - READY FOR FROZEN CANDIDATE

(floor/2 frozen as candidate for a separate, freshly pre-registered
final/generalization/promotion evaluation. Not option 1: further
development tuning now risks overfitting seeds 101-106. Not option 3:
primary CI includes 0, 13 events, greedy still ahead - a favorable point
estimate is insufficient for spending the private holdout.)

### What we still do not know

1. Whether floor/2 improves MSMI/100 at all (CI includes 0; 13 events).
2. Whether its point-estimate advantage persists on unseen worlds
   (holdout performance is completely unknown).
3. How it compares to greedy on a common seed set (no paired evidence,
   no stored interval).
4. Long-horizon behavior under endogenous depletion (zero-cand days
   8/160/503 within 60 days).
5. Score calibration (rank-usefulness only).
6. Whether the delayed-variant primary drop (0 vs .3333) is noise or a
   real weakness.
7. Whether nofloor's weaker pooled mutual/intro is a stable property or
   seed noise (its CI touches 0).

### What must NOT happen next

- Threshold sweeps, finer grids, quantile floors, or any post-hoc tuning
  of the floor value or rule - the threshold exploration is ENDED.
- Creating another threshold candidate, or "temporarily" testing floor/4,
  floor*0.75, or training-quantile variants.
- Any new model/ask/matcher experiment aimed at crossing greedy's .389
  on development seeds.
- Touching the private holdout without a separate pre-registration that
  names floor/2 as the single candidate.
- Rewriting Round 1, Stage 1.5, Stage 2, or Stage 3 records to make the
  favorable result look stronger, or claiming significance from 3
  clusters / 13 MSMI events.
- Automatic promotion of any kind: promotion requires the separate
  decision this audit recommends - freezing the candidate for evaluation,
  nothing more.

## 8. Artifacts

This audit: research/round2_stage3_intermediate_floor/
final_interpretation_and_promotion_audit.md (this file).
Machine-readable summary:
research/round2_stage3_intermediate_floor/promotion_audit.json.

No experiment was executed for this audit. policy.py, policy_ac.py, the
registered threshold, the private holdout, and all historical research
records are unchanged. No new threshold candidate was created.