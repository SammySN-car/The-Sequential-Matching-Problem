# Method Tournament - Phase 3 Final Report

- Worlds: 72 (seeds 152-163 x 6 variants), candidates: m03_reciprocal_min, m14_mutual_regret.
- Ranking metric: mean paired delta of MSMI/100 vs control. Never AUC, offline expected value, mutual acceptances, introduction counts, or ask efficiency. Absolute numbers are never compared across seed sets.
- Incumbent 0.4931 MSMI/100 is a different seed set and is never compared to these numbers.
- Coverage delta >= -0.05 and ask cost are guardrails, reported not binding (design section 9).
- Inference clusters on seed: 72 worlds -> 12 seed-level means (df = 11); per-variant gates mandatory (design section 9).
- Bonferroni: 2 candidate(s) tested -> 99% significance level (design section 9).
- Code fingerprint: fd5b92ff5999d1b8 (verified on every row).

| method | mean delta | cluster 99% CI | invalid | worst variant | credible | coverage delta | ask cost |
|---|---|---|---|---|---|---|---|
| m03_reciprocal_min | -0.0069 | [-0.0940, +0.0801] | 0 | -0.0833 | no | -0.0001 | 190.9 |
| m14_mutual_regret | +0.0000 | [+0.0000, +0.0000] | 0 | +0.0000 | no | 0.0 | 190.9 |

## Verdict

Greedy remains the best empirically supported policy among the evaluated candidates.


Keep-greedy reason: no credible candidate on Phase 3.

## Instrument pass - confirm2 (diagnostic only)

- Sample: seed 152 x 6 variants; digests verified against official confirm2 rows: 18/18 match.
- Never a ranking input (design section 5).

| arm | zero-selection days | intros/100 | mutual/intro | MSMI/intro | coverage | ask cost |
|---|---|---|---|---|---|---|
| m03_reciprocal_min | 34.0 | 24.25 | 0.1505 | 0.0 | 0.2783 | 209.0 |
| m14_mutual_regret | 34.0 | 24.25 | 0.1505 | 0.0 | 0.2783 | 209.0 |
| __control__ | 34.0 | 24.25 | 0.1505 | 0.0 | 0.2783 | 209.0 |
