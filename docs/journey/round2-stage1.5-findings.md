# Round 2 Stage 1.5 - Diagnostic Findings (measurement only)

**Status:** Complete. Read-only probe of the FROZEN Round 1 A+C policy. No tuning, no
factorial, no holdout access. Round 1 artifacts untouched (hashes re-verified after the run).

**Artifacts**
- `research/round2_stage1_5/probe.py` (schema `round2_stage1_5_probe_v2`)
- `research/round2_stage1_5/probe_seed101_run1.json` / `probe_seed101_run2.json`
- SHA256 (both runs identical): `3897D631CC655FF433DE7A6F0961AD7E6B920470F1E4DF704487727299209C2C`
- Frozen artifacts re-checked post-run: `policy.py`, `policy_ac.py` match `results/artifact.sha256`.

**Probe scope:** seed 101 x 6 evaluation variants, 60 ask/match days + 40 follow-up days
(360 decisions), in-process `policy.decide(req, mode='ac')` mirroring `evaluate.episode`.

**Validity gates (all green)**
- `ALL_FIDELITY_OK True` - assignments/mutual/MSMI/ask_cost/action digest match
  `results/ac.json` seed 101 for all 6 variants (probe reproduces Round 1 exactly).
- `FALLBACK_CALLS 0`, `branch_errors 0`, `instrument_mismatches 0`,
  `frontier_recheck_failures 0`, `cap_hits 0`, `seed_changed 0/360`, `greedy_not_in_cand 0`.
- Determinism: run1 == run2 byte-identical (hash above).

Tag legend: **OBSERVED** = directly measured | **HYPOTHESIS** = causal claim, untested |
**INTERPRETATION** = reasoned reading of observations | **UNKNOWN** = not measured.

---

## 1. Diagnostic table (seed 101, 6 variants, 360 decisions)

| metric | overall | development | sparse | cold_start | delayed | shift | drift |
|---|---|---|---|---|---|---|---|
| candidates (feasible, non-past) | 4205 | 793 | 327 | 523 | 859 | 847 | 856 |
| candidates/day (mean) | 11.68 | 13.22 | 5.45 | 8.72 | 14.32 | 14.12 | 14.27 |
| removed by floor | 3594 (**85.5%**) | 84.2% | 94.2% | 80.1% | 86.4% | 85.7% | 85.4% |
| above floor | 611 (14.5%) | 125 | 19 | 104 | 117 | 121 | 125 |
| selected (introduced) | 434 | 88 | 17 | 69 | 83 | 89 | 88 |
| zero-candidate days | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| zero-selected days WITH candidates | 148/360 (41.1%) | 17 | 47 | 25 | 19 | 22 | 18 |
| ...all categorized `all_below_floor` | 148/148 (100%) | 17 | 47 | 25 | 19 | 22 | 18 |
| greedy picks (same states) | 2479 | 458 | 237 | 369 | 461 | 480 | 474 |
| ...below A+C floor | 2149 (**86.7%**) | 391 | 223 | 308 | 400 | 420 | 407 |
| A+C picks also picked by greedy | 282/434 (65.0%) | 58 | 14 | 49 | 51 | 52 | 58 |
| seed changed by local search | 0/360 (0%) | 0 | 0 | 0 | 0 | 0 | 0 |
| ask cost A+C (sent) | 2404 | 394 | 377 | 460 | 394 | 385 | 394 |
| ask cost baseline counterfactual | 2226 | 354 | 375 | 435 | 354 | 354 | 354 |
| ...of which constraints | 2226 (742 asks x3) | - | - | - | - | - | - |
| ...of which soft | 178 (178 asks x1) | 40 | 2 | 25 | 40 | 31 | 40 |
| feasibility gains: A+C / baseline / con-only / soft-only | 273 / 273 / 273 / **0** | 51/46/51/0 | 14/25/14/0 | 56/57/56/0 | 50/48/50/0 | 51/51/51/0 | 51/46/51/0 |
| lost pairs (A+C / baseline) | 0 / 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| cost per gain: A+C / baseline | 8.81 / 8.15 | - | - | - | - | - | - |

Round 1 reference, same seed (from `results/*.json`, read-only):

| | assignments | mutual | MSMI | ask cost |
|---|---|---|---|---|
| greedy | 528 | 91 | 6 | 1230 |
| A+C | 434 | 74 | 5 | 2404 |
| A+C vs greedy | **-17.8%** | -18.7% | -16.7% | +95% |

Quality per introduction (seed 101): mutual/intro A+C 0.1705 vs greedy 0.1723;
MSMI/intro A+C 0.01152 vs greedy 0.01136 - essentially equal (OBSERVED).

## 2. Funnel diagnosis

**OBSERVED** (seed 101, 360 decisions):

```
feasible non-past candidates        4205   (0 days with zero candidates)
  -> floor removes                  3594   85.5%      <-- DOMINANT LOSS
  -> above floor                     611   14.5%
  -> greedy-seed + local search      434   71.0% of above-floor
  -> actually introduced             434   (seed changed by local search: 0/360)
```

Stage-by-stage verdicts:

1. **asks -> frontier: ALIVE.** Constraints asks open exactly as much feasibility as the
   baseline asker (273 gains each, 0 lost each). Clarification efficiency: A+C 8.81 cost
   per new feasible pair vs baseline 8.15 - within 8%. Soft asks contribute **0**
   feasibility gains (OBSERVED) because soft fields are not in the eligibility predicate
   (kit.eligibility checks HARD fields only) - soft asks buy score, not frontier
   (INTERPRETATION).
2. **feasible -> floor: THE BOTTLENECK.** Floor removes 85.5% of candidates (14.5%
   pass rate on the eval trajectory, vs 50.5% floor-pass reported on research edges in
   Round 1 - see UNKNOWN #5). On 148/360 days (41%) EVERY candidate was below floor;
   `all_below_floor` is 100% of zero-selected reasons. No `no_candidates`, no
   `fallback_empty`, no exceptions (OBSERVED).
3. **floor -> matcher: NOT A BOTTLENECK.** Greedy seed takes 71% of above-floor pairs
   (434/611; the other 177 lose to disjointness). Local search never changes the seed
   (0/360, pairs_changed_total 0). Fallback never fires. So matcher-stage loss is
   structural (shared members), not algorithmic (OBSERVED).
4. **matcher -> introduction: 100%.** Every selected pair is introduced (validation
   in `sim.advance` never rejects; branch_errors 0).

**Greedy cross-check (OBSERVED):** run `kit.baseline_match` on the SAME A+C states:
greedy would pick 2479 pairs; 86.7% of those sit below A+C's floor. A+C's 434 picks
overlap greedy's choices only 65%. The floor, not the candidate set, is what separates
the two policies' volumes: `greedy_not_in_cand = 0` (both draw from the identical
candidate set).

## 3. Top explanations for "A+C produces ~16% fewer introductions than greedy"

**#1 - The score floor starves volume. STRONG evidence, minor uncertainty about transfer.**
- Evidence: 85.5% of candidates removed; 41% of days zero because of floor alone;
  86.7% of greedy's picks fall below floor; seed101 volume gap -17.8% tracks the
  Round-1 18-episode gap (-16%); quality per intro is equal, so the gap is pure volume.
- Mechanism (HYPOTHESIS, not yet tested causally): floor was calibrated to protect
  match quality, but at 0.0079 it excludes ~7/8 of feasible supply on eval trajectories,
  including most pairs greedy happily introduces at equal mutual/MSMI conversion.
- Remaining uncertainty: single seed; counterfactual "what would introductions be with
  floor removed" not run (that is the ablation experiment, NOT performed here).

**#2 - Clarification spends budget without frontier payoff. MODERATE evidence, may be a red herring.**
- Evidence: A+C asks cost 2404 vs greedy 1230 (+95%) for -18% introductions; soft asks
  (178 cost) yield 0 feasibility gains; A+C and baseline ask almost disjoint members
  (87/742 = 11.7% overlap) yet identical total gains (273 = 273).
- INTERPRETATION: ask COST explains the ask-spending half of the primary-metric loss
  (ask_cost is a ranked objective) but does NOT explain the introduction gap - the
  baseline counterfactual spends 2226 and gains exactly the same 273 pairs.
- UNKNOWN: whether A+C's specific ask *targets* (vs baseline's) produce better-scoring
  pairs later; gains are counted per-day, not tracked to eventual introductions.

**#3 - Matching stage ruled out as the volume cause. STRONG (negative result).**
- Evidence: seed changed 0/360, fallback 0, cap 0, branch errors 0, instrument
  mismatches 0. The matcher faithfully converts 71% of above-floor pairs and nothing
  else. greedy overlap shows the SAME candidate set, so candidate generation is also
  ruled out (OBSERVED).

## 4. What is ruled out (for the volume gap, seed 101)

- Empty candidate pools (0 zero-candidate days) - RULED OUT (OBSERVED)
- Matcher/local-search defect, fallback path, 12k cap (all never fired) - RULED OUT
- Candidate-set divergence from greedy (`greedy_not_in_cand = 0`) - RULED OUT
- Probe fidelity/determinism artifacts (fidelity exact, hashes identical) - RULED OUT
- Per-introduction quality deficit (mutual/intro 0.1705 vs 0.1723; MSMI/intro 0.01152
  vs 0.01136) - RULED OUT as the *primary* driver; the gap is volume, not conversion

## 5. What remains UNKNOWN

1. Causal effect of removing/lowering the floor on introductions, mutual, MSMI, and
   primary rank (requires the ablation experiment - NOT run).
2. Whether sub-floor pairs would convert at the same mutual/MSMI rate if introduced
   (survivorship: we only observe conversions of pairs the floor let through).
3. Multi-seed generalization: probe is seed 101 only; Round-1 aggregate says the
   direction holds (A+C intro < greedy in 6/6 variants over 18 episodes).
4. Soft asks' actual payoff: 0 feasibility gains OBSERVED, but soft fields feed
   `_score_pair` - whether soft answers push pairs ABOVE the floor is not measured.
5. Floor pass rate discrepancy: 14.5% on eval trajectory (this probe) vs 50.5% on
   research edges (Round 1 S2). Different populations (research vs eval worlds, edge
   sampling); not reconciled.
6. Member-level ask targeting value (see #3 above).
7. Round-1 greedy asks only 1230 because greedy uses `baseline_asks` (constraints-only,
   3/day max) while A+C buys soft asks too; the like-for-like constraints component is
   2226 vs A+C's 2226 - identical. The "+95% ask cost" is almost entirely soft asks and
   the baseline's stricter budget behavior (INTERPRETATION).

## 6. Recommended next experiment (choose ONE; NOT performed)

**Floor ablation:** re-run the A+C policy on the same 6 variants x seeds with the floor
disabled (floor = -inf) or lowered, keeping everything else frozen, and compare
introductions / mutual / MSMI / ask / primary rank against frozen A+C and greedy.

Rationale: the floor is the single stage where 85.5% of supply is lost, it alone
accounts for 100% of zero-selected days, the matcher is proven inert, and ask strategy
is proven neutral for frontier growth. One variable, directly measured bottleneck.
Alternatives considered and deprioritized: ask ablation (asks proven neutral for
frontier), matcher ablation (matcher proven inert).