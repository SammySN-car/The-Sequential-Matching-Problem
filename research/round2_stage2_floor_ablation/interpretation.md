# Round 2 Stage 2 - Final Interpretation Memo

Schema: round2_stage2_floor_ablation_interpretation_v1.
Companion to: research/round2_stage2_floor_ablation/report.md (results) and
summary.json (data). Status: FROZEN RECORD - do not rewrite retroactively.
Date: 2026-10-07.
Scope: rigorous interpretation of the Stage 2 floor ablation; decision on the
single next experiment. No code modified; no experiment executed; holdout
untouched; Round 1 / Stage 1.5 findings unchanged; no significance claimed
from small MSMI samples.
Claim tags: OBSERVED (measured) / CAUSAL (justified by the intervention) /
UNCERTAIN (not established).

---

## 1. What Stage 2 proves

### Directly observed facts (OBSERVED)

- Volume: introductions 66.72 -> 77.83/ep (+16.7%); paired deltas
  17+/1 tie/0- over 18 (seed, variant) pairs; every seed positive
  (+16.2, +5.7, +11.5); descriptive cluster CI [+5.7, +16.2].
- Funnel: Arm A's 411 zero-selection-with-candidates days were
  411/411 all_below_floor; Arm B had 0 such days. Seed-101 Arm A reproduces
  Stage 1.5 exactly (4,205 -> 611 -> 434).
- Quality: mutual/intro .137 -> .159 (paired CI [-.007, +.060], 10+/1/7-);
  MSMI/intro .0075 -> .0086 (9 -> 12 events total); MSMI/100 .250 -> .333
  (CI [0, +.17], touches 0); coverage 15+/2/1-; shift variant MSMI/100
  .500 -> .167 (3 events vs 1).
- Survivorship (within Arm B, same policy/states): above-floor pairs
  .1796 mutual/intro vs sub-floor .1245 (ratio 0.69); .01159 vs .00372
  MSMI/intro (ratio 0.32). Sub-floor pairs = 67/222 (30%) of B's mutuals,
  2/12 of its MSMIs.
- Asks: -1.3% cost; ac_asks never reads floor; identical on shared states;
  day-0 identical; ask divergence strictly after match divergence in all
  18 episodes.
- Integrity: purity suite 11/11; only the floor argument changed; frozen
  matcher object used; deterministic reruns; 0 invalids/exceptions/
  fallbacks/cap hits; frozen hashes unchanged; holdout untouched.

### Causal conclusions justified (CAUSAL)

Because the intervention was isolated (verified pre-state identity of asks,
edges, and scores) and evaluated paired on identical worlds, the
introduction-volume increase and the elimination of the 411 all-below-floor
zero-selection days are CAUSED BY THE FLOOR FILTER ITSELF - not by asks,
matcher, scoring, or instrumentation. The frozen floor was the binding
selection constraint whenever candidates existed.

### Conclusions that remain uncertain (UNCERTAIN)

Whether quality IMPROVED (every quality CI includes 0); any MSMI claim
(12 vs 9 events); behavior outside seeds 101-103; behavior beyond the
60-day horizon; what happens to volume under endogenous candidate depletion
at longer horizons.

### Precision about scope

Stage 2 establishes that ON THESE DEVELOPMENT WORLDS, AT THIS HORIZON, WITH
THIS PROTOCOL the floor causally suppresses volume and its removal does not
produce a LARGE quality collapse (bounded by the observed paired deltas).
It does not establish small quality effects, out-of-sample performance, or
an optimal gate.

---

## 2. What Stage 2 rules out

| Candidate explanation | Ruled out? | Evidence |
|---|---|---|
| Frozen floor as a necessary quality gate at its current threshold | YES, as "necessary" | Removing it entirely yielded no evidence of meaningful quality collapse (mutual/intro point estimate rose; MSMI indistinguishable; coverage up 15/18). A gate at THAT threshold is not required to obtain the observed quality. CAVEAT: does not rule out that SOME gate helps - within-B the floor still separates quality (0.69x/0.32x), so the threshold is too high, not meaningless. |
| Matcher as the primary Stage 1.5 bottleneck | YES | All 411 blocked days were below-floor, not matcher failures; with input unblocked and matcher code byte-identical, selection rose 1,201 -> 1,401; local search changed 0/1,080 decisions in Arm A. The matcher was never the constraint. |
| Clarification as the direct cause of the floor bottleneck | YES | Floor never read by ask code (structural); asks identical on shared states and day-0; deltas trajectory-mediated and -1.3%; Stage 1.5 already showed equal feasibility gains for equal ask spend. |
| Instrumentation/fidelity problems | YES | Purity 11/11; all 6 diagnostic runs match official digests/metrics; Arm A reproduces Round 1 on all 3 seeds; seed-101 reproduces Stage 1.5 exactly; deterministic reruns; 0 errors anywhere. |
| All sub-floor pairs are useless | YES, decisively | 538 selected sub-floor pairs produced 67 mutual acceptances and 2 MSMIs. They are weaker, not worthless. (Selection caveat in section 3 - rules out "useless", not "equally good".) |

---

## 3. What Stage 2 does NOT prove

- MSMI improvement: 12 vs 9 total events; CI [0, +.17] touches 0; median
  delta 0; shift variant moved DOWN. The +33% point estimate on MSMI/100 is
  noise-compatible. No MSMI claim of any kind is supportable.
- Generalization from 3 seed clusters: the bootstrap is descriptive only;
  with 3 clusters nothing is inferential. Worse, seeds 101-103 are the SAME
  DEVELOPMENT SEEDS used throughout Round 1 - they informed the design of
  Stage 2, so Stage 2's own results are in-sample for the seed set.
- Endogenous candidate depletion: pooled feasible counts (10,144 vs 2,541)
  are NOT comparable opportunity sets - Arm B changes availability,
  busyness, and later candidacy by introducing more, earlier. Observed: B
  has 441 zero-candidate days vs A's 65. Therefore +16.7% is a
  WITHIN-HORIZON, WITHIN-PROTOCOL number; the long-run volume advantage
  could shrink (pool exhaustion) or grow - UNKNOWN. B's throughput may be
  self-limiting.
- Selected-sub-floor survivorship bias: the 538 pairs were chosen by Arm B's
  own score-ordered matcher on Arm B's own trajectory. They are biased
  toward higher-scored, feasible, available sub-floor pairs. This is an
  outcome description of SELECTED pairs, not an unbiased estimate of all
  sub-floor candidates, and not an estimate of what an intermediate floor
  would select.
- Score calibration: Stage 2 shows only rank-association within B
  (above-floor converts better). No calibration analysis exists; the frozen
  floor itself (0.0079, the training-set median prediction) sitting above
  ~84% of eval candidates hints at training/eval distribution shift, but
  whether scores are calibrated - or merely rank-useful - is untested.
- That another threshold would outperform both endpoints: zero evidence.
  Two endpoints were tested; the interior is untouched. Nothing implies
  floor/2, floor/4, or any quantile is better - exactly the gap the next
  experiment must fill, which is why a PRE-REGISTERED SINGLE interior point
  (not a sweep) is required.
- Long-horizon behavior: 60 decision days + 40 follow-up, fixed. Depletion
  dynamics, retirement/pause accumulation, and ask-composition drift beyond
  this horizon are unobserved.

---

## 4. Best current policy interpretation

Quality vs volume: the evidence says the frozen floor trades away a large
amount of introduction volume in exchange for SOME quality separation - and
the exchange rate is poor at its current setting:

- The volume side is robust (CAUSAL): +16.7%, 17+/1/0-, all seeds positive,
  411 -> 0 blocked days.
- The quality side shows no evidence of meaningful quality collapse:
  mutual/intro's point estimate rose (.137 -> .159) though its CI includes
  0; MSMI/intro is indistinguishable at 12 vs 9 events; coverage improved
  15/18. We cannot say "quality is definitively preserved" - we can say
  nothing in this experiment suggests a MEANINGFUL degradation, and several
  point estimates move favorably.
- Meanwhile the discarded band is not junk: selected sub-floor pairs convert
  mutuals at 91% of the frozen arm's overall rate (.1245 vs .1374) and half
  its MSMI rate - while the within-B above/sub gap (0.69x/0.32x) shows the
  score DOES carry ranking information. The floor is therefore LIKELY TOO
  CONSERVATIVE: it sits at a training-distribution median that removes ~84%
  of eval candidates (OBSERVED: 16.4% pass rate pooled), blocking a
  productive band rather than a useless one.

Context (OBSERVED, cross-Round comparison, same protocol): Round 1 primary
scores were greedy 0.389, frozen A+C 0.250; Stage 2's no-floor arm reaches
0.333 on the same seeds/protocol. The floor explains a large share - but not
necessarily all - of the A+C-vs-greedy gap. Greedy remains ahead on the
primary metric, which cautions against declaring the floor question fully
closed.

---

## 5. Decision on the next experiment

CHOICE: B - Intermediate-floor experiment. Independent evaluation:

- A (Stop): REJECTED. Stage 2 answered its own causal question but left two
  live, cheap-to-test uncertainties: interior-threshold dominance (section 3)
  and out-of-sample confirmation on fresh seeds. Stopping embeds an untested
  design assumption.
- C (Ask): REJECTED. Both stages show asks are not the binding constraint
  (identical shared-state behavior; equal feasibility gains; floor-
  independent). The -1.3% delta is trajectory-mediated. No evidence points
  at asks.
- D (Match): REJECTED. Local search changed 0/1,080 Arm A decisions;
  selection rose with matcher code unchanged; greedy overlap rose without
  matcher changes. No evidence the matcher is a lever.
- E (Model): REJECTED as NEXT. Calibration is a real unknown, but Stage 2
  gives no calibration diagnostic - that requires new measurement design
  first. The floor gates existing scores, which demonstrably rank (section
  4), and is the better-evidenced lever.
- F (Other): REJECTED. Depletion/long-horizon and holdout promotion are
  premature - depletion is best monitored within B's framework; holdout
  promotion belongs to a later, separately pre-registered phase.

Pre-registered design (full text now at
research/round2_stage3_intermediate_floor/preregistration.md, SHA256
FA11A2FB4DF53D507AA8C4D1A905025FD6392F5B656CC997CEE83FED4BF2D491):

- Arms (single floor-argument difference; model, asks, matcher, candidate
  cap, local search, fallback, evaluator, protocol frozen):
  1. frozen current floor:  max_score_matching(nodes, edges, float(model["floor"]))
  2. intermediate floor:    max_score_matching(nodes, edges, float(model["floor"]) / 2.0)
  3. no floor:              max_score_matching(nodes, edges, -inf)
- Seeds 104, 105, 106 (never used in Round 1, Stage 1.5, or Stage 2);
  all six variants; 18 episodes per arm; official evaluate.py; paired by
  (seed, variant); private holdout untouched; NO threshold sweep; NO
  post-hoc adjustment regardless of outcome.
- Primary metric: MSMI/100. Secondary: introductions/ep, mutual/ep,
  mutual/intro, MSMI/intro, coverage, ask cost, invalids.
- Analysis: paired deltas (mid-frozen, mid-nofloor, nofloor-frozen);
  per-seed/per-variant tables; funnel + survivorship (selected pairs vs
  frozen floor AND vs intermediate floor); cluster bootstrap over 3 seed
  clusters, descriptive only; determinism rerun; frozen-hash verification.

Exact pre-registration rule:

    intermediate_floor = float(model["floor"]) / 2.0
                       = 0.003952587007648379
    (frozen floor = 0.007905174015296758, verified from Stage 2 artifacts)

Why principled, not tuned:

1. Zero free parameters fitted to outcomes. Arithmetic on the frozen
   constant alone: the unique bisection midpoint of the interval Stage 2
   actually tested. The filter operates on raw score in (0,1); tested
   endpoints are [frozen floor, effectively 0]; floor/2 is that interval's
   midpoint in the exact metric the predicate compares. A midpoint of a
   tested interval is determined by the interval, not by results.
2. Evidence justifies testing AN interior, not THIS interior: Stage 1.5
   shows the upper endpoint destroys throughput; Stage 2 shows the lower
   endpoint recovers volume with no evidence of meaningful quality collapse,
   yet the discarded band converts worse than the retained band. Since no
   evidence discriminates among interior points, the canonical interval
   midpoint is the only neutral choice.
3. Explicitly rejected: sweep (forbidden, stepwise tuning); eval-quantile
   target (fits outcome distribution = tuned); re-derived training-quantile
   floor (fits a parameter to data); any value chosen after seeing seeds
   104-106 (contaminates the fresh seeds).

Decision discipline: report all three arms regardless of result; threshold
exploration ENDS with this experiment under any outcome; a favorable result
is a candidate for a SEPARATE later holdout-promotion decision, not an
invitation to try more values; a null/unfavorable result closes threshold
exploration in this phase.

---

## 6. Final recommendation

Current best interpretation: the frozen floor (a training-set median applied
to eval-time candidates, passing ~16%) is LIKELY TOO CONSERVATIVE as a
volume gate: it causally suppresses introductions (+16.7% on removal,
17+/1/0-), it was the binding Stage 1.5 bottleneck (411/411 all-below-floor
blocked days), and the band it discards is productive-but-weaker (mutual
conversion ~91% of the frozen arm's overall rate on a selected-pair basis)
rather than junk - while still separating quality within Arm B
(0.69x/0.32x). There is NO EVIDENCE OF MEANINGFUL QUALITY COLLAPSE from
removal, but also no proof of quality preservation or improvement (all
quality CIs include 0; MSMI rests on 12 vs 9 events).

Proceed to the intermediate-floor experiment? YES - Choice B. It converts
the largest remaining design unknown ("would an interior point dominate
both endpoints?") into evidence, uses only fresh seeds (104-106) so the
design is out-of-sample, and is executable with one pre-registered
arithmetic rule (floor/2) and zero tuning degrees of freedom. It must be
pre-registered before running and must not be iterated afterward.

Exactly what remains unknown:

1. Whether any interior floor dominates both endpoints on primary MSMI/100
   plus volume (tested only by the experiment above).
2. Whether Stage 2's findings replicate on fresh seeds (101-103 informed
   the design) and, eventually, on the untouched private holdout.
3. Any MSMI effect (12 vs 9 events; per-variant noise; shift-variant
   regression unresolved).
4. Whether quality is truly preserved vs improved (CIs include 0; n=3
   clusters -> descriptive only).
5. Long-horizon behavior under endogenous candidate depletion (B: 441 vs 65
   zero-candidate days) - +16.7% is within-horizon only.
6. Score calibration (rank-usefulness observed; calibration untested).
7. Whether the remaining A+C-vs-greedy primary gap (0.333 vs Round 1's
   0.389) comes from asks, matcher behavior at scale, or scoring - untouched
   by this phase.

---
Constraints honored: no code modified, no experiment executed at time of
writing, holdout untouched, Round 1 / Stage 1.5 findings unchanged, no
significance claimed from small MSMI samples.