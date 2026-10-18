# Method Tournament - Phase 2 Confirmation Report

- Worlds: 36, arms: m19_arrival_age, m03_reciprocal_min, m14_mutual_regret, m26_greedy_one_swap + shared control.
- Top 2 by FULL-precision mean paired delta (sign-independent); zero-invalid only; m01 excluded; ties by (round(mean, 6), method_id) (design section 9).
- Inference clusters on seed: 6 per-variant deltas are averaged per seed -> 6 seed-level means (df = 5) (design section 9).
- Code fingerprint: fd5b92ff5999d1b8 (verified on every row).
- Ranking metric: mean paired delta of MSMI/100 vs control. Never AUC, offline expected value, mutual acceptances, introduction counts, or ask efficiency. Absolute numbers are never compared across seed sets.

| method | mean delta | cluster 95% CI | invalid | worst variant | coverage | ask cost |
|---|---|---|---|---|---|---|
| m03_reciprocal_min | +0.0417 | [-0.0789, +0.1622] | 0 | +0.0000 | 0.321 | 200.1 |
| m14_mutual_regret | +0.0000 | [+0.0000, +0.0000] | 0 | +0.0000 | 0.3208 | 200.1 |
| m19_arrival_age | -0.0139 | [-0.0999, +0.0721] | 0 | -0.0833 | 0.3206 | 200.1 |
| m26_greedy_one_swap | +0.0000 | [+0.0000, +0.0000] | 0 | +0.0000 | 0.3208 | 200.1 |

Selected for Phase 3: m03_reciprocal_min, m14_mutual_regret

> **Correction 2026-10-09 (label only):** the original line read "12 seed-level means (df = 11)" - a hardcoded template string written for Phase 3 (12 seeds). Verified: intervals were computed with df = n_seeds - 1 = 5; recomputing from confirm1_rows.jsonl reproduces the published ci95/ci99 to 6 decimal places (implied t = 2.5710/4.0320 = t(.975,5)/t(.995,5)); df = 11 does not match. No analysis logic, selection, or numeric results changed; the frozen string in analyse_tournament.py was intentionally NOT edited.
