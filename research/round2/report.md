# Round 2 Report - Gated Maximum-Weight Allocation (CLOSED: keep greedy)

Competition: The Sequential Matching Problem (Romeo & Juliet Ltd. x IIT Madras)
Round 2 deliverable, deadline 2026-10-17 23:59 IST.
Preregistration: research/round2/design.md + experiment_plan.json (FROZEN 2026-10-12,
before any evaluation seed was touched). This report follows the frozen
close-this-line criterion (design.md section 9).

## Headline

The gated maximum-weight candidate achieved a primary-metric difference of
EXACTLY ZERO versus official greedy on 72 fresh paired worlds:
mean 0.0000 MSMI/100, 95% CI [0.0000, 0.0000], 99% CI [0.0000, 0.0000],
wins/ties/losses 0/72/0. Promotion criteria P1 (mean > 0) and P2 (CI lower > 0)
FAIL. Per the preregistered rule we KEEP GREEDY and close this line of
investigation. No post-hoc method is introduced.

## What the candidate did

One candidate policy, implemented exactly as preregistered (no tunable constants):

- Ask phase: identical to official greedy (kit.baseline_asks).
- Match phase, step 1: build the same feasible graph greedy uses (available
  members, kit-feasible, never-introduced pairs; official score = count of
  observed equal SOFT fields, 0-7).
- Match phase, step 2: attempt the EXACT maximum-weight assignment
  (pure-Python O(n^3) Hungarian, Vorobyev/e-maxx formulation) only when the
  graph is bipartite AND node count <= 180. Zero-score edges are KEPT
  (the fix for m25's cardinality-collapse defect).
- Match phase, step 3 (the gate): adopt the exact matching ONLY if
  (G1) it is at least as large as greedy's, AND (G2) its score sum is STRICTLY
  larger. Otherwise official greedy is returned unchanged.

The ungated ablation arm adopts the exact matching whenever the solver ran,
with no gate - this is the counterfactual that shows what the gate protects.

## Results (seeds 301-312 x 6 variants = 72 paired worlds x 5 arms = 360 episodes)

Primary score (MSMI per 100 arrived, mean of 6 families):

| Arm | Primary | Coverage | Mutual/100 | Valid |
|---|---|---|---|---|
| greedy (official) | 0.3194 | 0.3438 | 5.44 | 72/72 |
| gated (candidate) | 0.3194 | 0.3438 | 5.48 | 72/72 |
| random (official) | 0.3194 | 0.3431 | 5.44 | 72/72 |
| ungated (ablation) | 0.2708 | 0.3387 | 4.84 | 72/72 |
| no_asks (official) | 0.0417 | 0.1149 | 1.28 | 72/72 |

Paired statistics (clustered by seed, df=11):

- PRIMARY gated - greedy: mean 0.0000, CI95 [0.0000, 0.0000], CI99 [0.0000, 0.0000],
  W/T/L 0/72/0. Per-family differences all exactly 0.0.
- ABLATION ungated - greedy (descriptive): mean -0.0486, CI95 [-0.158, +0.061],
  W/T/L 10/46/16. Per-family: cold_start +0.083, development -0.083, drift -0.125,
  shift -0.125, sparse -0.042, delayed 0.0. No catastrophic family loss (P4 pass).

Promotion checks: P1 FAIL, P2 FAIL, P3 PASS (360/360 valid, 0 invalid),
P4 PASS (min family diff 0.0), P5 PASS (determinism, container parity, latency).

## What we learned (the ablation lesson)

The gate adopted the exact matching on only 5 of 4,320 match phases
(gate adoption frequency 0.12%): 3,569 rejections for no strict score gain (G2),
581 for cardinality loss (G1), 165 solver-availability rejections. On the 5
adoptions the total score gain was +5 with total cardinality change +5.

The ungated arm - the exact matching with no gate - LOST 0.0486 MSMI/100 on
average and discarded 6,769 introductions in total (cardinality delta sum
-6,769 vs greedy). This is the same failure mode Round 1 documented for m25:
on these graphs, maximum-weight matchings routinely trade many zero- or
low-score pairs (which greedy keeps and which sometimes convert) for a few
high-score pairs, and the discarded volume costs more MSMI than the gained
score is worth.

Together the two arms show the full picture: the gate works as designed
(it successfully prevented the cardinality collapse - gated cardinality is
identical to greedy on every world), but what it protects is NOT a better
policy. It protects sameness: the observable score objective almost never
strictly improves without losing cardinality, and when it does, the gain is
too small to move realized MSMI. The optimization target itself - the count
of observed equal SOFT fields - is not aligned with the outcome the
competition measures (reciprocal second-meeting intention).

This is consistent with the Round 1 autopsy: score-vs-oracle Spearman 0.12,
and with the diagnostic calibration bands collected here (gated arm, Wilson
95%): MSMI conversion by score band is small and NON-MONOTONE - band 2
(score 2) converts at 2.33% [1.31%, 4.12%], while band 7 (score 7, only 4
intros) converts at 0% [0%, 49.0%]. Higher observable agreement does not
reliably predict the measured outcome; the bands are diagnostic-only and
were never used for tuning.

## What failed, precisely

1. P1/P2: no primary-metric improvement (exactly zero difference - the gate
   almost never fires, and its rare firings do not change episode outcomes).
2. The implicit hypothesis behind the method - that a provably better
   allocation on the observable objective yields better realized MSMI - is
   NOT supported on fresh seeds. Even the conservative, cardinality-protected
   version produces no measurable change.
3. The ungated variant is actively worse (-0.0486), confirming that
   unguarded exact optimization of the observable score is harmful.

## Why greedy is retained

The final submission keeps official greedy (policy.py default mode flipped
from ac to greedy per the Round 2 spec, since greedy is the retained policy;
documented hash change, 81 root tests green, no-arg entrypoint exits 0 on
empty state). Greedy equals the gated candidate on every paired world while
being simpler, and the gated candidate exists only to test a hypothesis that
the data rejected. Random matching tying greedy at the primary score
(0.3194 vs 0.3194) is a further signal that the current observable score
car little decision-time outcome information - the remaining headroom, if
any, is in better SCORE INFORMATION (features that actually predict
reciprocal interest), not in the allocation rule.

## Status: completed vs proposed vs untested

COMPLETED (evidence in research/round2/results/):
- Preregistration (design.md, experiment_plan.json) - frozen before eval.
- Candidate implementation (alloc_core.py, policies/mw_alloc.py, runner_r2.py)
  with TDD suite (24/24 green) incl. greedy parity, Hungarian vs brute force,
  gate logic, protocol parity, official-episode action_sha256 parity.
- Full 5-arm paired evaluation (360/360 valid) on seeds 301-312, all 6
  variants, with paired clustered statistics.
- Ablation (ungated) with cardinality accounting.
- Diagnostics: gate telemetry (4,320 match phases), calibration bands with
  Wilson intervals (after fixing a diagnostic-only band-settlement defect;
  primary rows unaffected - documented in run_log.txt).
- Validity: PYTHONHASHSEED {0,1,42,random} full-episode decision-digest
  determinism; docker local/container parity 32/32 byte-identical; latency
  mean invoke 0.12s (bound 2s); memory < 1 MiB; root regression 81 tests OK.
- Entrypoint flip (spec-required): policy.py default ac -> greedy.

PROPOSED (not part of this submission's evidence):
- Any future work on score information (better features predicting
  reciprocal interest) is OUT OF SCOPE for this round per design.md
  section 9: no successor allocation method is introduced post-hoc.

UNTESTED / LIMITATIONS:
- Evaluation is simulator-only, as the competition defines it.
- The exact solver is only attempted on bipartite graphs <= 180 nodes;
  it was unavailable on 3.8% of gated-arm match phases (over-cap or
  non-bipartite), where both arms fall back to official greedy.
- Calibration bands reflect the gated arm only (diagnostic pass); late
  intros (proposed after ~day 55) cannot settle within the observation
  window and are conservatively counted in denominators only.

## Reproduction

python -B -m unittest research.round2.test_round2        # 24 tests
python -B research/round2/runner_r2.py --phase eval      # 360 episodes (resume-capable)
python -B research/round2/runner_r2.py --phase diagnostics
python -B research/round2/analyse.py                     # summary.json + console report

Integrity: integrity/manifest.sha256 (pre-eval, 13 files) and
integrity/manifest_post.sha256 (post-deliverable; the only post-eval source
changes are the documented band-settle defect fix in mw_alloc.py and the
spec-required policy.py default flip + matching test update).