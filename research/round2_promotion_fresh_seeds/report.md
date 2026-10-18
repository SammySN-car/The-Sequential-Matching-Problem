# Round 2 Promotion - Fresh-Seed Generalization Evaluation

**Directory:** research/round2_promotion_fresh_seeds/
**Seeds:** 107-118 (12 fresh, never used in Round 1 / Stage 1.5 / Stage 2 / Stage 3 / Stage 4)
**Arms:** A greedy (descriptive reference) | B original floor (current A+C) | C floor/2 (frozen promotion candidate)
**Date:** 2026-10-07 | **Git head:** a8e26b35118c (unchanged before/after; no commits made)

---

## 1. Objective

[OBSERVED] Evaluate the already-frozen `floor/2` candidate
(`float(model['floor']) / 2.0 == 0.003952587007648379`, applied only via the
frozen Stage 3 shim `intermediate_policy.py`, sha256 A76FD0EE0C2B9579...) on
12 unseen seeds x 6 world variants x 3 arms (216 official episodes), and end
with exactly one explicit promotion decision: READY/PROMOTE,
CONDITIONAL/NEED-MORE-EVIDENCE, or REJECT. This is a generalization test of a
threshold chosen before these seeds existed for us; it is not a development
step.

## 2. What this experiment is (and is not)

[OBSERVED] DO-NOT list honored in full: `policy.py`, `policy_ac.py`,
`kit.py`, `evaluate.py`, `organise.py`, `Dockerfile`, `.dockerignore`, the
embedded model blob, the Stage 3 candidate shim, and the Stage 3
preregistration were never modified (21/21 sha256 identical before/after,
Section 18). No alternative floor was computed, tested, or discussed during
execution; no matching/ask/feature/hyperparameter change was made; no private
holdout seed was touched; no result was rerun for favorability (the one full
re-execution was a harness bug fixed uniformly for every run, Section 4).

## 3. Environment and apparatus

[OBSERVED] Windows, Python 3.13.5, scikit-learn 1.8.0; frozen candidate
apparatus = Stage 3 `intermediate_policy.py` shim (fail-fast guard: raises
unless the floor argument equals the registered value; `model['floor']`
re-verified as 0.007905174015296758 pre-run). Evaluator = frozen
`evaluate.py` (sha256 D09CC14B...), invoked as documented in its own CLI:
`--policy <file> --seeds <S> --variants all --output <path>`
(`--baseline greedy` for arm A). Diagnostics = `diag_promo.py`, a copy of the
frozen Stage 3 `diagnose3.py` with exactly three provenance edits (docstring,
output-directory note, one `sys.path` line so the frozen shim imports from the
frozen Stage 3 directory); a line diff confirms instrumentation, arms, and
fidelity checks are unchanged. Docker 29.8.0 with image
`sequential-policy:1.0` present; image `policy.py`/`kit.py` sha256 verified
byte-identical to the repo copies.

## 4. Registration and pre-run integrity

[OBSERVED] Before any run: experiment design, arm commands, primary metric,
contrast plan, seed-cluster bootstrap method, the two pre-specified criteria
(>=80% volume worlds; ~8% mutual warning reference), and the G1-G5 gate plan
were registered in `run_log.txt`; 21 frozen hashes + candidate value written
to `integrity_before.json`.

[OBSERVED] INCIDENT 1 (disclosed): the first execution attempt omitted
`--variants all` (evaluate.py defaults `--variants` to `development`), so all
41 outputs contained only 1 of 6 variants. Detected at the G1 validity sweep
(episodes=1 vs the 6-episode convention of every prior stage). All 41 partial
outputs were deleted, the incident was logged, the harness was fixed, and the
entire matrix (official + rerun + container) was re-executed from scratch. No
analysis was run on partial outputs. Root cause: the Stage 3 `run_log.txt`
abbreviates its command lines and did not show the flag; run_promo.py did not
reproduce it.

## 5. Data collected

[OBSERVED]

| class | files | episodes | notes |
|---|---|---|---|
| official | 36 (`arm_{greedy,original,floorhalf}_seed{107..118}.json`) | 216 | 6 variants x 12 seeds x 3 arms |
| determinism reruns | 4 (`..._rerun.json`: A/B/C @107, C @118) | 24 | G2 |
| container | 1 (`arm_original_seed107_container.json`) | 6 | G3 (renamed after wrong-target fix, Section 13) |
| diagnostics | 24 (`diag_{frozen,intermediate}_seed{107..118}.json`) | 4320 instrumented days | Section 11; every file `all_fidelity_ok=true` (12/12 seeds per arm) |
| **total official-protocol** | 41 | **246** | **0 invalid (G1 PASS)** |

Run wall-clock per 6-episode seed-run (post-incident runs): greedy
129.3s mean [127.0, 131.5]; original 192.3s [181.1, 199.1]; floorhalf 189.6s
[179.8, 194.9]; container run 420s; diagnostic runs 134-358s.

## 6. Metrics and definitions

[OBSERVED] Primary = **MSMI per 100 arrived members**, computed by the
frozen `evaluate.summarise()` (equal-weight mean over the 6 scenario family
means; families are equal-sized here, so it equals the 72-episode pooled
mean; cross-check: pooled 54/14400 = 0.375 for B, 58/14400 = 0.4028 for C,
71/14400 = 0.4931 for A - identical to the official primary). Secondary, all
pooled over 72 episodes per arm:

| metric (raw form) | A greedy | B original | C floor/2 |
|---|---|---|---|
| introductions per 100 arrived members | 38.10 | 31.93 | 35.96 |
| mutual-acceptance events per 100 arrived members | 5.417 | 5.090 | 5.368 |
| mutual acceptances per introduction (rate) | 0.1438 | 0.1630 | 0.1576 |
| MSMI events per 100 introductions | 1.199 | 1.192 | 1.054 |
| coverage | 0.3462 | 0.3313 | 0.3402 |
| ask cost per episode (units; constraints=3, soft=1, budget 12/day) | 203.04 | 423.44 | 419.72 |
| date rate per 100 introductions | (see summary.json) | | |
| first-introduction wait, days mean/median | 6.72 / 4.0 | 11.99 / 8.0 | 10.40 / 7.0 |
| totals: introductions / mutual / MSMI (arrived=14400/arm) | 5486 / 780 / 71 | 4598 / 733 / 54 | 5178 / 773 / 58 |
| inference seconds per episode (nondeterministic) | 19.8 | 30.2 | 29.7 |

Validity: 0 invalid episodes, 0 exceptions across all 246 official-protocol
episodes; ask counts per episode: B 156.1, C 152.6 (from diagnostics; the
official harness records ask cost only - greedy ask COUNT is [UNKNOWN] by
harness design).

## 7. Primary result

[OBSERVED] Official primary score (72 episodes per arm):

| arm | primary (MSMI/100 arrived) |
|---|---|
| A greedy | 0.4931 |
| B original floor | 0.3750 |
| **C floor/2 (candidate)** | **0.4028** |

Paired contrasts (per seed+variant world; seed-cluster bootstrap, 10000 reps,
95% percentile CI; W/T/L = sign of paired delta):

| contrast (primary) | mean delta | CI95 | worlds W/T/L | seed-level W/T/L (12) |
|---|---|---|---|---|
| **C - B (decision contrast)** | **+0.0278** | [-0.118, +0.188] | 21/31/20 | 5/2/5 |
| C - A (descriptive) | -0.0903 | [-0.257, +0.069] | 21/24/27 | 6/0/6 |
| B - A (descriptive) | -0.1181 | [-0.340, +0.076] | 16/34/22 | - |

Per-seed mean C-B primary deltas: 107 +0.250, 108 -0.167, 109 -0.250,
110 -0.167, 111 0.000, 112 +0.167, 113 +0.500, 114 -0.333, 115 -0.250,
116 +0.500, 117 0.000, 118 +0.083.

[OBSERVED] Cross-stage direction check: Stage 3 (seeds 104-106) primary
B 0.250 -> C 0.361 (C-B +0.111); this fresh-seed test B 0.375 -> C 0.403
(C-B +0.028). Both point estimates positive; the fresh-seed estimate is
smaller and its CI spans zero.

[INTERPRETATION] On fresh seeds the candidate does not degrade the primary
metric in point estimate (it is slightly positive), but with 12 independent
seeds and sparse MSMI counts (31/72 worlds tie) the CI cannot distinguish
"slightly better" from "slightly worse". The honest reading: no degradation
signal, no confirmed improvement - consistent with, but weaker than, Stage 3.

[OBSERVED] Secondary C-B deltas: assignments +8.06 [ +5.69, +10.71 ]
(65/4/3, seeds 12/0/0); introductions per 100 arrived +4.03
[ +2.79, +5.33 ]; coverage +0.0089 [ +0.0053, +0.0124 ] (52/12/8);
mutual/100 +0.278 [ -0.569, +1.090 ] (36/9/27); mutual per introduction
-0.0054 [ -0.031, +0.020 ] (29/2/41); MSMI per 100 introductions -0.138
[ -0.687, +0.454 ]; date rate -0.860 [ -2.93, +1.23 ]; ask cost -3.72
[ -5.33, -1.94 ] (C slightly cheaper, 15/6/51).

## 8. Greedy baseline - descriptive comparison only

[OBSERVED] On the common fresh worlds: A 0.4931 > C 0.4028 > B 0.3750.
C-A -0.0903 [ -0.257, +0.069 ]; B-A -0.1181 [ -0.340, +0.076 ] (both CIs
span zero). Greedy also introduces more (5486 vs 5178), asks less
(203 vs 420 cost/episode), and has shorter first-introduction waits
(6.7 vs 10.4 days), at slightly higher coverage (0.346 vs 0.340).

[OBSERVED] Round 1's greedy 0.389 primary was on seeds 101-103 (different
worlds); within-fresh-seed arm comparisons are the only inferentially
comparable ones, per pre-registration. Greedy's fresh-seed point estimate
being higher than its Round 1 number is a between-seed-set difference, not a
regression.

[INTERPRETATION] Per the task's fixed hierarchy, this section is a
descriptive benchmark: it does not by itself trigger REJECT (the promotion
question is C vs B, the deployed-policy comparison) and it does not license
any greedyward tuning.

## 9. Volume confirmation (pre-specified: >= 80% of 72 worlds)

[OBSERVED] C introductions > B in **65/72 worlds = 90.28%** (ties 4,
losses 3) - **meets the >=80% criterion**. Mean delta +8.06 introductions
per world [ +5.67, +10.60 ] (seed-cluster CI), median +6; seed-level
12/0/0 (every seed positive). Arm totals: 4598 (B) -> 5178 (C) = +12.6%;
C recovers 65.3% of the B->A gap ((5178-4598)/(5486-4598)). Per-variant
wins: development 12/0/0 (+11.0), drift 12/0/0 (+11.2), shift 12/0/0
(+11.8), delayed 11/0/1 (+7.2), cold_start 10/1/1 (+5.8), sparse 8/3/1
(+1.3). Stage 3 on seeds 104-106 showed +6.17 [ +3.67, +8.33 ] with 15/1/2
worlds - the volume mechanism replicates on fresh seeds.

## 10. Mutual no-harm (reference warning: ~8% relative degradation)

[OBSERVED] Mutual acceptances per 100 arrived members: C 5.368 vs B 5.090
= **+5.46% relative** (CI [ -9.59%, +24.56% ]); absolute paired delta
+0.278 [ -0.569, +1.111 ], worlds 36/9/27, seeds 7/0/5. Absolute mutual
totals: 733 -> 773 (+40, +5.5%). The point estimate is on the IMPROVED side
of the -8% warning threshold; it does not exceed it.

[UNKNOWN] The CI's lower bound (-9.59%) reaches slightly beyond the -8%
warning inside an otherwise wide interval; per the pre-registration this is
reported, not converted into a failure call on a noisy estimate. Secondary
nuance: mutual-per-introduction rate is -0.0054 (29/2/41) - a dilution-style
small negative point with CI spanning zero, because C adds 580 introductions
while adding 40 mutuals.

## 11. Zero-selection and floor diagnostics (section 11 scope)

[OBSERVED] 24 diagnostic runs (arms B and C x 12 seeds), each with
`all_fidelity_ok=true` against its official run (action_sha256 + all metrics
match) - the instrument measures exactly the official behavior. Pooled over
720 decisions per arm (arm-divergent trajectories; denominators are
per-arm):

| diagnostic | B original | C floor/2 |
|---|---|---|
| feasible candidates (frontier, pre-floor) | 38558 | 18130 |
| after the arm's own floor | 6589 (17.1% kept) | 8665 (47.8% kept) |
| removed by the arm's floor | 31969 (82.9%) | 9465 (52.2%) |
| days with zero candidates (world state) | 56 | 537 |
| days zero-selected WITH candidates (all `all_below_floor`) | 1816 (42.0% of decisions) | 1264 (29.3% of decisions) |
| cap hits / fallbacks / frontier-recheck fails / instrument mismatches | 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 |
| asks per episode | 156.1 | 152.6 |
| introductions | 4598 | 5178 |
| fidelity | 12/12 seeds | 12/12 seeds |

[OBSERVED] Survivorship of C's 5178 introductions by model score:
`ge_frozen` n=3394, mutual 546 (16.1%), MSMI 41 (1.21 per 100 intro);
`mid_band` (floor/2 <= s < floor, admitted only by C) n=1784, mutual 227
(12.7%), MSMI 17 (0.95 per 100 intro); `lt_intermediate` 0 (the candidate
still filters below its threshold). B's introductions are 100% `ge_frozen`
(n=4598, mutual 733 = 15.9%, MSMI 54 = 1.17 per 100 intro).

[INTERPRETATION] The Stage 3 mechanism persists on unseen seeds: floor/2
halves the floor-removed fraction, cuts all-below-floor (zero-selected with
candidates) days from 1816 to 1264 without creating zero-candidate collapse
(the two are kept distinct: C's 537 zero-candidate days reflect its own
divergent world state, not floor action), and the added mid_band volume
carries a somewhat lower quality per introduction (12.7% vs 16.1% mutual
rate) that still converts in absolute terms (+40 mutuals, +4 MSMIs vs B).
Zero-selected categories are `all_below_floor` in 100% of cases in both
arms.

## 12. Determinism reruns (G2)

[OBSERVED] Reruns of (A, B, C @ seed 107) and (C @ seed 118) vs their
originals: **4/4 byte-equal** after excluding `inference_seconds`
(including every action_sha256 digest, every metric, and
`summary.primary_score`). G2 PASS. (nondeterministic inference timing is
excluded by design; nothing else was excluded.)

## 13. Local vs container agreement (G3)

[OBSERVED] Image `sequential-policy:1.0` `policy.py` and `kit.py` sha256 are
byte-identical to the repo files (379CC2D9... and 0D2CB3D3...). The frozen
`evaluate.py` docker path runs `policy.py` with NO arguments (default mode =
`ac`), i.e. the container can only express the A+C arm; initial comparison
against local arm A legitimately mismatched (different policy), the file was
renamed to `arm_original_seed107_container.json` and compared against local
arm B: **0 diffs, all 6 action_sha256 match, primary equal** - exactly
mirroring Round 1's `ac.json` vs `ac_container.json` parity. G3 PASS within
the repository's existing verification scope. Arms A and C cannot run in the
frozen image (the frozen Dockerfile ships `kit.py`+`policy.py` only with
ENTRYPOINT `policy.py`; extending image scope would require modifying the
frozen Dockerfile, which is forbidden) - this scope limit is reported, not
worked around.

## 14. Paired design and CRN semantics

[OBSERVED] `kit.py` derives each stochastic stream from a content-addressed
seed (`SHA256(seed|actor|day)`-style), so arms share EXACT randomness for
every (pair, day) they both evaluate, and trajectories diverge only after
selections diverge. Pairing at (seed, variant) therefore gives perfectly
coupled worlds with increasingly non-identical trajectories; contrasts are
computed per paired world and aggregated; the bootstrap resamples whole seed
clusters (all 6 variants travel together). RNG code was untouched.

## 15. Statistical method and limitations

[OBSERVED] All CIs: 10000-replicate percentile bootstrap, unit = seed
cluster (12 clusters), fixed per-contrast RNG seeds - the same method family
as Stage 2/3. No multiple-comparison correction; secondary metrics are
reported, not promoted to co-primary.

[UNKNOWN / limitations] (a) 12 independent seeds is the true n - 72 worlds
are clustered, not 72 independent trials; (b) MSMI is sparse (per-world
counts 0-2), producing 31/72 ties in the primary and low power; (c) arms are
paired but not trajectory-identical after divergence (Section 14); (d) the
`~8%` warning and `>=80%` volume thresholds are references carried from
prior research, not derived here; (e) mutual-relative CI touches -9.59%
(Section 10); (f) all results are simulation-protocol results
(`status: simulated_not_observed_product_performance`), no real-product
claim; (g) greedy comparisons are descriptive (Section 8).

## 16. Scenario (per-variant) diagnosis

[OBSERVED] Primary by variant (A / B / C; C-B mean delta, W/T/L over 12
seeds; assignment C-B):

| variant | A | B | C | C-B primary | C-B W/T/L | C-B introductions |
|---|---|---|---|---|---|---|
| development | 0.792 | 0.583 | 0.583 | +0.000 | 4/4/4 | +11.0 (12/0/0) |
| drift | 0.750 | 0.542 | 0.542 | +0.000 | 4/4/4 | +11.2 (12/0/0) |
| shift | 0.625 | 0.375 | 0.500 | +0.125 | 5/4/3 | +11.8 (12/0/0) |
| delayed | 0.375 | 0.333 | 0.417 | +0.083 | 4/6/2 | +7.2 (11/0/1) |
| cold_start | 0.333 | 0.250 | 0.292 | +0.042 | 3/5/4 | +5.8 (10/1/1) |
| sparse | 0.083 | 0.167 | 0.083 | -0.083 | 1/8/3 | +1.3 (8/3/1) |

[INTERPRETATION] No scenario shows systematic candidate degradation
(sparse's -0.083 primary rests on 1 win / 8 ties / 3 losses at near-floor
absolute levels and is the known low-information scenario); volume gains are
broad but concentrated in development/drift/shift; the single largest
primary gaps vs B are neutral-to-positive for C. The B-C tie in
development/drift primary with +11 introductions each shows the added volume
did not cost MSMI there. Per-variant CIs (in summary.json) all span zero.

## 17. End of tuning cycle

[OBSERVED] Threshold exploration ENDED at Stage 3 and remains ended:
`preregistration.md` (FA11A2FB...) and
`final_interpretation_and_promotion_audit.md` (B76AE4AB...) were re-hashed
unchanged (Section 18). This promotion evaluation creates NO new threshold,
NO follow-up optimization, and NO license to re-open the floor value on
these or any seeds. Any future threshold work would require a NEW
preregistration; nothing in this report may be used to justify "one more
try" of a different floor. Seeds 107-118 are now consumed for threshold
purposes.

## 18. Integrity ledger (G1-G5 and incidents)

| gate | result |
|---|---|
| G1 validity | PASS - 246/246 official-protocol episodes valid, 0 exceptions, all 41 files complete (6 variants each) |
| G2 determinism | PASS - 4/4 reruns equal excluding inference_seconds, all digests match |
| G3 local/container | PASS - 0 diffs, all digests match vs local arm B; image policy/kit byte-identical; scope limit stated (Section 13) |
| G4 frozen hashes | PASS - 21/21 files identical before/after (`integrity_before.json` / `integrity_after.json`), git head a8e26b35118c unchanged, `git status` unchanged, zero new commits |
| G5 no holdout | PASS - only seeds 107-118 were ever passed to evaluate.py (run_log commands); worlds are generated in-process from seed (`evaluate.py:152` -> `kit.generate(...)`), no data files read; `organise.py` never executed (hash unchanged, absent from run_log); no organiser/holdout data artifacts exist in the repo (only `organise.py` + a runbook doc, both untouched); diagnostics read only this directory and frozen refs |

Incidents (both disclosed, both fixed without selective re-runs):
1. Section 4 - omitted `--variants all`; ALL 41 outputs regenerated uniformly.
2. Section 13 - container compared against the wrong local arm first; corrected by re-comparing against arm B (the policy the container actually runs); the mismatching file was renamed, not deleted; no re-execution was involved.

## 19. Decision

[OBSERVED] Pre-specified checks: volume 90.28% >= 80% -> **met**;
mutual relative +5.46% vs -8% warning -> **not exceeded** (point estimate
improved; CI disclosed); primary C-B +0.0278 with CI spanning zero ->
**no degradation signal** (Stage 3 was +0.111; direction replicates);
G1-G5 all PASS; mid_band volume mechanism replicates with disclosed
lower per-introduction conversion.

[INTERPRETATION] Every condition the task pre-specified as a failure or
hold-back trigger is absent: no integrity breach, no volume failure, no
mutual no-harm breach, no primary degradation, no scenario-level
systematic loss. The uncertainty is real but is of the "small n, sparse
outcome" kind, not of the "the candidate behaves differently on unseen
seeds" kind - on unseen seeds it behaved the same way it did on design
seeds, in the same direction, with the same mechanism.

[DECISION] **READY / PROMOTE** - the frozen `floor/2` candidate
(0.003952587007648379) is cleared for promotion on the evidence of this
fresh-seed evaluation, with the following commitments carried forward:
(1) the disclosed uncertainties stand as written (primary CI spans zero;
mutual-relative CI reaches -9.59%; 12 seeds; greedy point estimate higher
on the descriptive axis); (2) promotion authorizes NO further threshold
experimentation (Section 17); (3) any future change to the floor, matcher,
or asks is a new preregistered project, not an extension of this one.

[DECISION, alternatives not taken] CONDITIONAL/NEED-MORE-EVIDENCE would
have been the call if the primary point estimate had gone negative while
gates passed; REJECT would have required a triggered pre-specified failure
(volume < 80%, mutual beyond -8%, primary materially negative, or an
integrity breach). None occurred.

## 20. Artifacts and hashes

[OBSERVED] Frozen anchors re-verified unchanged (full 64-char values in
`integrity_before.json` / `integrity_after.json`; 16-char prefixes):
`policy.py` 379CC2D9519E8D3B | `policy_ac.py` 90FB9AD306E89BFB |
`kit.py` 0D2CB3D3B46CA2A6 | `evaluate.py` D09CC14BF634A741 |
`organise.py` DA9D6B3A197F1FF8 | `Dockerfile` FEF95FA3D6BC038F |
Stage 3 `intermediate_policy.py` A76FD0EE0C2B9579 |
`preregistration.md` FA11A2FB4DF53D50 |
`final_interpretation_and_promotion_audit.md` B76AE4ABAC72F5EB |
`promotion_audit.json` 0138D36F0B13DF42 |
Stage 3 `report.md` D47BAE2512527587 / `summary.json` C4B4EF5690B617C6 |
Stage 2 `report.md` 09E4FF744184ADFA / `interpretation.md` E46A066AC6D97E2C |
Stage 4 `report.md` 9C3CB74F081C54E4 |
`docs/superpowers/round1-research-record.md` 661115F512A41B5A |
`results/artifact.sha256` 79ACD52BDC11C909 | git head a8e26b35118c.

Experiment outputs (this directory): `report.md` (this file),
`summary.json` (full contrasts, per-seed/per-variant tables, diagnostics,
gates, runtime), `run_log.txt` (registration, commands, timings, incidents),
`integrity_before.json`, `integrity_after.json`, `gates_g2_g3.json`,
36 official + 4 rerun + 1 container arm files, 24 diagnostic files,
harness scripts (`run_promo.py`, `run_diag.py`, `diag_promo.py`,
`analyze_promo.py`, `gates.py`, `integrity_before/after.py`),
`manifest.sha256` (sha256 of every file in this directory except itself).

---
*Labels used: [OBSERVED] = measured/read directly; [INTERPRETATION] =
reasoning over observations; [UNKNOWN] = not answerable from available data;
[DECISION] = the called judgment.*