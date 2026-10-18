# Round 2 Stage 2 - Frozen A+C Floor Ablation: Final Report

Schema: round2_stage2_floor_ablation. Interpretation tags: OBSERVED / INTERPRETATION / HYPOTHESIS / UNKNOWN.
Investigation phase. No tuning, no threshold search, no holdout, no production-policy modification.

Intervention (the ONLY difference between arms):

    Arm A (frozen):  max_score_matching(nodes, edges, float(model['floor']))   # policy.py:591
    Arm B (no-floor): max_score_matching(nodes, edges, -inf)                  # ablation_policy.py

Predicate `e[2] >= floor` (policy.py:469) becomes tautologically true for every finite
model score (sigmoid outputs in (0,1)) - literally equivalent to removing the filter.
No threshold substituted; frozen matcher function object called unchanged.

---

## 1. Experiment status

- **Status: COMPLETED** (0 failures, 0 retried runs needed after tooling fixes)
- **Seeds:** 101, 102, 103 (development seeds, pre-specified; seed 101 first, expanded only
  after infrastructure validated; **private 120-world holdout untouched**)
- **Variants:** all 6 (development, sparse, cold_start, delayed, shift, drift)
- **Arms:** A = frozen Round 1 A+C (`policy_ac.py` shim); B = `ablation_policy.py`
- **Episodes:** 18 official + 18 diagnostic per arm; all valid (0 invalid, 0 exceptions,
  0 fallbacks, 0 cap hits, 0 protocol violations, 0 zero-introduction episodes)
- **Deterministic:** official Arm B seed-101 rerun identical to original episodes
  (excluding wall-clock `inference_seconds`, the only nondeterministic field, same as
  Round 1); diagnostic rerun byte-identical. Arm A determinism = Round 1 ac_rerun plus
  fresh digest equality with `results/ac.json` on all 3 seeds.
- **Pure-intervention verification:** `purity.json` - **11/11 PASS**
  (P1 frozen hashes match artifact.sha256 pre/post; P2 asks identical on all 18 shared
  day-0 states; P3 memory identical; P4 pre-floor edge lists + model scores identical;
  P5a ac_match passes the same floor argument in both arms; P5b frozen matcher receives
  model floor vs -inf; P6 matcher outputs reproduced by the frozen matcher with ONLY the
  floor argument changed; P7 selection subset of shared edges; P8 frozen selects only
  score >= floor; P9 ablation overrides exactly one attribute)
- **Fidelity:** all 12 diagnostic runs match their official evaluate.py run exactly
  (action_sha256 + assignments + mutual + MSMI + MSMI/100 + coverage + ask_cost);
  Arm A reproduces Round 1 `results/ac.json` digests on all 3 seeds.
- **Files created** (only under `research/round2_stage2_floor_ablation/`):
  `ablation_policy.py`, `purity_child.py`, `purity_check.py`, `purity.json`,
  `diagnose.py`, `analyze.py`, `arm_a_run_seed{101,102,103}.json`,
  `arm_b_run_seed{101,102,103}.json`, `arm_b_run_seed101_rerun.json`,
  `diag_arm_{a,b}_seed{101,102,103}.json`, `diag_arm_b_seed101_rerun.json`,
  `summary.json`, `report.md`, `run_log.txt`
- **Not touched:** `policy.py`, `policy_ac.py`, `kit.py`, `evaluate.py`, `Dockerfile`,
  `.dockerignore`, `results/*`, Round 1 outputs, Stage 1 / Stage 1.5 outputs.

## 2. Main result table (per variant, mean over seeds 101-103; ratios pooled)

| Variant | Arm | Intro/ep | Mutual/ep | Mutual/intro | MSMI/ep | MSMI/intro | MSMI/100 | Coverage | Ask cost | Invalid |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| development | A frozen | 82.67 | 13.00 | 0.1573 | 0.33 | 0.0040 | 0.1667 | 0.4067 | 413.7 | 0 |
| development | B no-floor | 95.67 | 15.33 | 0.1603 | 1.00 | 0.0105 | 0.5000 | 0.4283 | 405.7 | 0 |
| sparse | A frozen | 14.67 | 2.33 | 0.1591 | 0.00 | 0.0000 | 0.0000 | 0.1267 | 382.7 | 0 |
| sparse | B no-floor | 17.67 | 2.00 | 0.1132 | 0.00 | 0.0000 | 0.0000 | 0.1450 | 382.7 | 0 |
| cold_start | A frozen | 59.00 | 9.00 | 0.1525 | 0.33 | 0.0056 | 0.1667 | 0.3550 | 478.7 | 0 |
| cold_start | B no-floor | 65.00 | 14.33 | 0.2205 | 0.67 | 0.0103 | 0.3333 | 0.3633 | 474.3 | 0 |
| delayed | A frozen | 79.33 | 10.67 | 0.1345 | 1.00 | 0.0126 | 0.5000 | 0.4083 | 416.0 | 0 |
| delayed | B no-floor | 92.00 | 15.00 | 0.1630 | 1.00 | 0.0109 | 0.5000 | 0.4250 | 407.3 | 0 |
| shift | A frozen | 82.00 | 7.67 | 0.0935 | 1.00 | 0.0122 | 0.5000 | 0.4017 | 411.7 | 0 |
| shift | B no-floor | 101.00 | 12.33 | 0.1221 | 0.33 | 0.0033 | 0.1667 | 0.4283 | 407.7 | 0 |
| drift | A frozen | 82.67 | 12.33 | 0.1492 | 0.33 | 0.0040 | 0.1667 | 0.4033 | 413.7 | 0 |
| drift | B no-floor | 95.67 | 15.00 | 0.1568 | 1.00 | 0.0105 | 0.5000 | 0.4283 | 405.7 | 0 |
| **OVERALL** | **A frozen** | **66.72** | **9.17** | **0.1374** | **0.50** | **0.0075** | **0.2500** | **0.3503** | **419.4** | **0** |
| **OVERALL** | **B no-floor** | **77.83** | **12.33** | **0.1585** | **0.67** | **0.0086** | **0.3333** | **0.3697** | **413.9** | **0** |

MSMI/100 = official family-mean style (evaluate.summarise). Zero-introduction episodes: 0
(all 36 episodes had introductions; ratio denominators never zero).

## 3. Paired differences (B minus A, n = 18 (seed, variant) episode pairs)

| Delta | Mean | Median | Range | + / 0 / - |
|---|---:|---:|---:|---:|
| delta_intro | +11.11 | +11.00 | [0, +26] | 17 / 1 / 0 |
| delta_mutual | +3.17 | +2.50 | [-1, +8] | 13 / 3 / 2 |
| delta_mutual_per_intro | +0.0173 | +0.0081 | [-0.0677, +0.1420] | 10 / 1 / 7 |
| delta_msmi | +0.167 | 0.000 | [-1, +2] | 5 / 10 / 3 |
| delta_msmi_per_intro | +0.0007 | 0.0000 | [-0.0182, +0.0247] | 5 / 7 / 6 |
| delta_msmi_per_100 | +0.0833 | 0.0000 | [-0.5, +1.0] | 5 / 10 / 3 |
| delta_coverage | +0.0194 | +0.0175 | [-0.0050, +0.0550] | 15 / 2 / 1 |
| delta_ask_cost | -5.50 | -5.00 | [-14, 0] | 0 / 4 / 14 |

Per-seed mean deltas (direction is positive for volume on EVERY seed):
- seed 101: d_intro +16.17, d_mut/intro -0.0071, d_msmi100 +0.1667, d_cov +0.0208, d_ask -3.0
- seed 102: d_intro +5.67, d_mut/intro +0.0602, d_msmi100 +0.0833, d_cov +0.0058, d_ask -5.7
- seed 103: d_intro +11.50, d_mut/intro -0.0010, d_msmi100 +0.0000, d_cov +0.0317, d_ask -7.8

Cluster bootstrap over whole seeds (3 clusters, 10,000 reps, descriptive only - n=3):
- delta_intro: +11.11, CI95 [+5.67, +16.17] (excludes 0)
- delta_msmi_per_100: +0.083, CI95 [+0.000, +0.167]
- delta_mutual_per_intro: +0.017, CI95 [-0.007, +0.060] (includes 0)

STATISTICAL NOTE (OBSERVED): pair rows are NOT treated as independent - inference unit is
the seed cluster; with only 3 clusters all intervals are descriptive, not inferential.
MSMI totals are 9 (A) vs 12 (B) events - far too few for significance claims.

## 4. Funnel comparison (pooled: 3 seeds x 6 variants x 60 decision days)

Arm A frozen:
```text
10,144 feasible -> 1,662 above floor (16.4%) -> 1,201 selected -> 1,201 introduced
zero-selection days with feasible candidates: 411 - category all_below_floor: 411 (100%)
zero-candidate days: 65
```

Arm B no-floor:
```text
2,541 feasible -> 2,541 after floor (100%: floor disabled) -> 1,401 selected -> 1,401 introduced
zero-selection days with feasible candidates: 0 (sanity check PASSED: after_floor == feasible
  on every day, 0 violations)
zero-candidate days: 441
```

- Seed 101 Arm A reproduces Stage 1.5 EXACTLY (4,205 -> 611 -> 434; 148 zero-selection days,
  100% all_below_floor) - continuity with the Stage 1.5 funnel is verified.
- All 411 pooled zero-selection days in Arm A are all_below_floor; Arm B has ZERO such days:
  those states became productive (INTERPRETATION: the floor was the binding constraint on
  selection whenever candidates existed).
- OBSERVED: Arm B's feasible pool is much smaller (2,541 vs 10,144). Day-0 candidate counts
  and availability are IDENTICAL across arms (verified); thereafter Arm B introduces more,
  consuming the feasible non-past pool faster and keeping members busy/paused longer, so
  late-episode candidate supply narrows (endogenous depletion). INTERPRETATION: a downstream
  causal consequence of the intervention, not an instrumentation artifact.

### Greedy overlap (diagnostic only; matcher unchanged)

Per-episode distinct pairs, mean/summed over the 18 (seed, variant) episodes:

```text
Arm A frozen:   |S|=1,201  |G|=1,093  |S n G|=853   overlap_of_S=0.710  mean Jaccard=0.627
Arm B no-floor: |S|=1,401  |G|=1,098  |S n G|=1,050  overlap_of_S=0.750  mean Jaccard=0.756
Cross A/B:      |A n B|=1,128  mean Jaccard=0.783 (cross-trajectory: arms diverge after day 0)
```

Daily-sum view (same greedy reference recomputed per state):
Arm A: greedy picks 6,211, overlap 804, of which 5,287 (85.1%) below the frozen floor
  (seed-101 subset: 2,479 / 282 / 2,149 - EXACT match to Stage 1.5);
Arm B: greedy picks 1,396 on its own (candidate-depleted) states, overlap 1,023,
  655 (46.9%) below the frozen floor.

OBSERVED: Arm B's selections align MORE with greedy than Arm A's (Jaccard 0.756 vs 0.627),
consistent with Stage 1.5's finding that the floor blocked most of what greedy would pick.
## 5. Newly admitted sub-floor pair quality (critical survivorship question)

Pooled over 18 episodes per arm (official per-introduction predicates from kit.Simulator.metrics):

| Group | n | Mutual | Mutual/intro | MSMI | MSMI/intro |
|---|---:|---:|---:|---:|---:|
| A frozen, all passed old floor | 1,201 | 165 | 0.1374 | 9 | 0.00749 |
| B passed old floor | 863 | 155 | 0.1796 | 10 | 0.01159 |
| B **newly admitted (score < floor)** | 538 | 67 | 0.1245 | 2 | 0.00372 |

Arm B newly admitted, per seed: mutual/intro 0.1368 / 0.1024 / 0.1256 (seeds 101/102/103);
MSMI/intro 0.0047 / 0.0000 / 0.0050.

- Newly admitted pairs convert WORSE than above-floor pairs (12.5% vs 18.0% mutual/intro;
  0.37% vs 1.16% MSMI/intro) but far from zero - they contributed 67 of Arm B's 222 mutual
  acceptances and 2 of its 12 MSMIs.
- CAVEAT (OBSERVED): these are outcomes of pairs the no-floor policy actually selected on
  ITS trajectory - not an unbiased estimate of all sub-floor candidates. Sample sizes are
  modest (538) and MSMI counts tiny (2).
- HYPOTHESIS: the floor does meaningful but partial filtering - it removes productive-but-
  weaker volume, not junk.

## 6. Answering the causal question

**Q1: Did disabling the floor recover volume?** YES (OBSERVED).
Introductions 66.72 -> 77.83 per episode (+16.7%); +17 / 0 / - across 18 pairs (1 tie at
sparse seed 103: 8 vs 8); every seed positive; cluster CI excludes 0. The 411 all-below-floor
zero-selection days vanished (0 in Arm B).

**Q2: Did it preserve per-introduction quality?** YES - no material destruction (OBSERVED).
Mutual/intro 0.1374 -> 0.1585 (+15.3%; CI includes 0, so direction unconfirmed but clearly
not a collapse). MSMI/intro 0.0075 -> 0.0086 (+14.3%; 9 -> 12 events - statisticaly
indistinguishable). Pair-level: mutual/intro improves in 10 pairs, ties 1, declines 7 - no
systematic degradation.

**Q3: Did MSMI/100 improve?** YES, weakly (OBSERVED): 0.2500 -> 0.3333 (+33%), cluster CI
[0.000, +0.167] touches 0; per-variant heterogeneous (up in development/cold_start/drift,
flat in delayed/sparse, DOWN in shift 0.50 -> 0.17).

**Classification: OUTCOME A** (INTERPRETATION) - volume increased substantially while
quality held or improved: "the frozen floor was unnecessarily suppressing useful
introduction volume." Per protocol: no threshold tuning performed in this task.

**Ask isolation investigation** (spec-required because ask cost was expected to be identical):
ask cost totals A 7,549 vs B 7,450 (-99, -1.3%; per-pair deltas 0 positive / 4 zero /
14 negative). Investigated (OBSERVED): (a) `ac_asks` never reads the floor (code: floor
appears only at policy.py:67/437/454-469/563-564/591); (b) asks are IDENTICAL on all 18
shared day-0 states (P2/P3); (c) day-0 asks identical in every episode pair; (d) first ask
divergence occurs strictly AFTER first match divergence in all 18 pairs (match first-diff
days {0,1,7}, ask first-diff days {1,2,3,9}). CONCLUSION: the small ask-cost difference is
trajectory-mediated (different introductions -> different busy/paused members -> different
ask targets), not a purity violation - the ask policy itself is untouched.

## 7. What this experiment rules out

- Rules OUT: the frozen floor as a necessary quality gate at its current threshold - removing
  it did NOT collapse mutual/intro or MSMI/intro (OUTCOME A).
- Rules OUT: Stage 1.5's funnel bottleneck being partly matcher-side - with the floor removed,
  100% of feasible candidates reach the matcher and selection rises to 1,401; the floor alone
  accounted for the introduction deficit vs greedy at the candidate gate.
- Rules OUT: local search, fallback, cap, protocol, instrumentation error as explanations.
  Arm A: local search changed the greedy seed on 0/1080 days (extends Stage 1.5's 0/360 to
  all 3 seeds); 0 fallbacks, 0 cap hits, 0 instrument mismatches, 0 frontier-recheck
  failures, 0 invalid episodes in both arms. (Arm B's seed-changed counter, 352/1080, is
  NOT a local-search measure: it compares the above-floor seed against a matcher whose
  input includes sub-floor edges - not comparable by construction. The matcher code itself
  is proven identical by purity check P6.)
- Rules OUT: asks as the causal channel for the volume change (identical on shared states;
  day-0 identical; divergence strictly post-match-divergence; -1.3% cost).
- PARTIALLY answers survivorship: sub-floor pairs are productive-but-weaker (12.5% vs 18.0%
  mutual/intro) - not junk, not equal.
- Rules OUT: determinism/infrastructure concerns (reruns identical; Arm A reproduces Round 1).

## 8. What remains unknown

- Whether a particular INTERMEDIATE floor would dominate BOTH arms (keep most of B's volume,
  recover some of the 5.5pp mutual/intro gap between B's groups). NOT tested - no threshold
  search permitted here.
- Whether results generalize beyond the 3 development seeds (private holdout untouched;
  n=3 clusters give only descriptive statistics).
- Whether score calibration / ranking improvements could outperform both arms.
- The shift-variant MSMI regression (0.50 -> 0.17 per 100) - 3 events vs 1; HYPOTHESIS: noise,
  but unresolved.
- Long-horizon behavior of Arm B's endogenous candidate depletion (441 vs 65 zero-candidate
  days) beyond 60 decision days.
- Unresolved ask interaction at the trajectory level (composition diverges on 12-48 of 60 days
  per episode even though the policy code is identical).
- Whether mutual/intro gains are real (CI [-0.007, +0.060] includes 0).

## 9. ONE next recommendation (NOT executed)

**Pre-registered floor-redesign experiment on NEW seeds.** Design (decide BEFORE running):
select ONE redesigned floor rule motivated only by Stage 1.5/Stage 2 diagnostics - no
threshold search, single candidate (e.g., keep no-floor's matcher input but re-admit a
weak score gate only if survivorship demands it; the survivorship gap 12.5% vs 18.0% is the
design input) - then run a paired 3-arm comparison (frozen A+C vs redesigned vs no-floor) on
NEW pre-registered development seeds (e.g., 104-106) x 6 variants, same official evaluator,
primary metric MSMI/100, secondary intro volume + mutual/intro + ask cost, same validity and
determinism gates. This simultaneously tests (a) whether Stage 2 generalizes beyond seeds
101-103 and (b) whether an intermediate rule can dominate both arms. NOT PERFORMED in this
task.