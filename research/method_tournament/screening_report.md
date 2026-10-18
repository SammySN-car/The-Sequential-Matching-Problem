# Method Tournament - Phase 1 Screening Report

- Worlds: 18 (seeds 143-145 x 6 variants), paired vs shared greedy control.
- Control parity: m01 digests identical to policy.py --baseline greedy on 18/18 worlds.
- Phase 1 has 18 paired worlds: no method may be called a winner from screening alone.
- m01_greedy_baseline is excluded from eligibility, ranking, and retention (parity/diagnostic only; design section 7).
- Inference clusters on seed: 6 per-variant deltas are averaged per seed -> 3 seed-level means (df = 2); screening is gate-only (design section 9).
- Screening code fingerprint: 1247e79768da7524 (verified on every row).
- Ranking metric: mean paired delta of MSMI/100 vs control. Never AUC, offline expected value, mutual acceptances, introduction counts, or ask efficiency. Absolute numbers are never compared across seed sets.

## Leaderboard (eligible, ranked by mean paired delta)

| rank | method | mean delta | cluster 95% CI | invalid | worst variant | retained |
|---|---|---|---|---|---|---|
| 1 | m19_arrival_age | +0.0278 | [-0.0917, +0.1473] | 0 | +0.0000 | YES |
| 2 | m03_reciprocal_min | +0.0000 | [+0.0000, +0.0000] | 0 | +0.0000 | YES |
| 3 | m14_mutual_regret | +0.0000 | [+0.0000, +0.0000] | 0 | +0.0000 | YES |
| 4 | m26_greedy_one_swap | +0.0000 | [+0.0000, +0.0000] | 0 | +0.0000 | YES |

## Ineligible methods

- **m02_reciprocal_sum**: catastrophic family: cold_start, shift
- **m04_reciprocal_product**: mean delta -0.0833 below -0.05; catastrophic family: development, drift, shift
- **m05_harmonic_reciprocal**: mean delta -0.0833 below -0.05; catastrophic family: development, drift, shift
- **m06_bottleneck**: catastrophic family: cold_start
- **m07_prune_and_greedy**: mean delta -0.1944 below -0.05; catastrophic family: cold_start, development, drift, shift, sparse
- **m08_weighted_compatibility**: catastrophic family: cold_start, shift
- **m09_partner_scarcity**: mean delta -0.1389 below -0.05; catastrophic family: development, drift, shift
- **m10_degree_balanced**: catastrophic family: delayed
- **m11_scarcity_x_compat**: catastrophic family: development, drift
- **m12_regret_score**: mean delta -0.0556 below -0.05; catastrophic family: development, drift
- **m13_opportunity_cost**: mean delta -0.0556 below -0.05; catastrophic family: development, drift
- **m15_reserve_high_option**: catastrophic family: delayed
- **m16_patient_policy**: mean delta -0.1944 below -0.05; catastrophic family: cold_start, development, drift, shift, sparse
- **m17_daily_quota**: mean delta -0.0833 below -0.05; catastrophic family: delayed, development, drift, shift
- **m18_time_threshold**: mean delta -0.1944 below -0.05; catastrophic family: cold_start, development, drift, shift, sparse
- **m20_new_arrival_protection**: catastrophic family: cold_start
- **m21_delay_cost_threshold**: mean delta -0.2500 below -0.05; catastrophic family: cold_start, development, drift, shift, sparse
- **m22_market_thickness**: mean delta -0.3056 below -0.05; catastrophic family: cold_start, delayed, development, drift, shift, sparse
- **m23_hybrid_patient_greedy**: mean delta -0.1111 below -0.05; catastrophic family: cold_start, sparse
- **m24_max_cardinality**: catastrophic family: development, drift
- **m25_max_weight**: mean delta -0.1944 below -0.05; catastrophic family: cold_start, development, drift, shift, sparse
- **m27_greedy_augmenting**: mean delta -0.1667 below -0.05; catastrophic family: cold_start, development, drift, shift
- **m28_conflict_aware**: mean delta -0.0556 below -0.05; catastrophic family: development, drift, shift
- **m29_uncertainty_aware**: catastrophic family: cold_start, sparse
- **m30_targeted_info**: catastrophic family: drift, sparse

## Retention decisions (design section 7)

- Retained top-5: m19_arrival_age, m03_reciprocal_min, m14_mutual_regret, m26_greedy_one_swap
- Diagnostic candidates: none beyond top-5.

## Behavioral distinctness (honesty check, never ranking)

| method | distinct action digests | worlds differing from control |
|---|---|---|
| m01_greedy_baseline | 15 | 0 |
| m02_reciprocal_sum | 16 | 17 |
| m03_reciprocal_min | 15 | 15 |
| m04_reciprocal_product | 15 | 15 |
| m05_harmonic_reciprocal | 15 | 15 |
| m06_bottleneck | 17 | 18 |
| m07_prune_and_greedy | 15 | 18 |
| m08_weighted_compatibility | 16 | 17 |
| m09_partner_scarcity | 15 | 13 |
| m10_degree_balanced | 15 | 14 |
| m11_scarcity_x_compat | 15 | 14 |
| m12_regret_score | 15 | 13 |
| m13_opportunity_cost | 15 | 13 |
| m14_mutual_regret | 15 | 0 |
| m15_reserve_high_option | 15 | 13 |
| m16_patient_policy | 13 | 18 |
| m17_daily_quota | 16 | 18 |
| m18_time_threshold | 12 | 18 |
| m19_arrival_age | 17 | 17 |
| m20_new_arrival_protection | 16 | 18 |
| m21_delay_cost_threshold | 15 | 18 |
| m22_market_thickness | 9 | 18 |
| m23_hybrid_patient_greedy | 16 | 18 |
| m24_max_cardinality | 15 | 18 |
| m25_max_weight | 16 | 18 |
| m26_greedy_one_swap | 15 | 18 |
| m27_greedy_augmenting | 15 | 18 |
| m28_conflict_aware | 15 | 15 |
| m29_uncertainty_aware | 17 | 18 |
| m30_targeted_info | 17 | 18 |

## Cross-variant dispersion (within-seed, diagnostic)

- m01_greedy_baseline: 0.0000
- m02_reciprocal_sum: 0.1735
- m03_reciprocal_min: 0.0000
- m04_reciprocal_product: 0.0913
- m05_harmonic_reciprocal: 0.0913
- m06_bottleneck: 0.4557
- m07_prune_and_greedy: 0.3134
- m08_weighted_compatibility: 0.2989
- m09_partner_scarcity: 0.2506
- m10_degree_balanced: 0.0680
- m11_scarcity_x_compat: 0.1541
- m12_regret_score: 0.0861
- m13_opportunity_cost: 0.0861
- m14_mutual_regret: 0.0000
- m15_reserve_high_option: 0.0680
- m16_patient_policy: 0.3134
- m17_daily_quota: 0.3095
- m18_time_threshold: 0.3616
- m19_arrival_age: 0.0680
- m20_new_arrival_protection: 0.4581
- m21_delay_cost_threshold: 0.4274
- m22_market_thickness: 0.4081
- m23_hybrid_patient_greedy: 0.3912
- m24_max_cardinality: 0.2693
- m25_max_weight: 0.3134
- m26_greedy_one_swap: 0.0000
- m27_greedy_augmenting: 0.2880
- m28_conflict_aware: 0.1593
- m29_uncertainty_aware: 0.4437
- m30_targeted_info: 0.3883

## Secondary diagnostics (never ranking inputs)

| method | coverage | ask cost | intros/100 | max inference s |
|---|---|---|---|---|
| m01_greedy_baseline | 0.3422 | 201.7 | 37.944 | 21.4 |
| m02_reciprocal_sum | 0.3439 | 201.7 | 38.25 | 21.0 |
| m03_reciprocal_min | 0.3422 | 201.7 | 37.889 | 20.5 |
| m04_reciprocal_product | 0.3425 | 201.7 | 37.889 | 20.4 |
| m05_harmonic_reciprocal | 0.3425 | 201.7 | 37.889 | 20.3 |
| m06_bottleneck | 0.3461 | 201.7 | 39.194 | 20.7 |
| m07_prune_and_greedy | 0.1142 | 201.7 | 9.111 | 20.1 |
| m08_weighted_compatibility | 0.3439 | 201.7 | 38.611 | 20.1 |
| m09_partner_scarcity | 0.3442 | 201.7 | 39.694 | 20.3 |
| m10_degree_balanced | 0.3422 | 201.7 | 38.417 | 19.3 |
| m11_scarcity_x_compat | 0.3425 | 201.7 | 39.333 | 19.5 |
| m12_regret_score | 0.3422 | 201.7 | 37.5 | 21.0 |
| m13_opportunity_cost | 0.3422 | 201.7 | 37.5 | 19.0 |
| m14_mutual_regret | 0.3422 | 201.7 | 37.944 | 20.8 |
| m15_reserve_high_option | 0.3422 | 201.7 | 38.417 | 23.3 |
| m16_patient_policy | 0.0831 | 201.7 | 5.944 | 19.6 |
| m17_daily_quota | 0.3428 | 201.7 | 38.194 | 19.7 |
| m18_time_threshold | 0.1142 | 201.7 | 9.5 | 26.9 |
| m19_arrival_age | 0.3425 | 201.7 | 37.944 | 44.6 |
| m20_new_arrival_protection | 0.3453 | 201.7 | 38.972 | 43.7 |
| m21_delay_cost_threshold | 0.1711 | 201.7 | 15.361 | 40.4 |
| m22_market_thickness | 0.0 | 201.7 | 0.0 | 40.3 |
| m23_hybrid_patient_greedy | 0.2739 | 201.7 | 21.056 | 28.9 |
| m24_max_cardinality | 0.3444 | 201.7 | 38.194 | 29.4 |
| m25_max_weight | 0.1767 | 201.7 | 16.0 | 35.1 |
| m26_greedy_one_swap | 0.3422 | 201.7 | 37.917 | 49.4 |
| m27_greedy_augmenting | 0.3436 | 201.7 | 38.75 | 51.2 |
| m28_conflict_aware | 0.3428 | 201.7 | 38.667 | 32.3 |
| m29_uncertainty_aware | 0.3439 | 307.7 | 35.583 | 37.1 |
| m30_targeted_info | 0.3464 | 249.2 | 36.472 | 45.2 |

## Instrument pass - screening (diagnostic only)

- Sample: seed 143 x 6 variants; digests verified against official screening rows: 30/30 match.
- Never a ranking input (design section 5).

| arm | zero-selection days | intros/100 | mutual/intro | MSMI/intro | coverage | ask cost |
|---|---|---|---|---|---|---|
| m19_arrival_age | 19.0 | 45.833 | 0.1274 | 0.0087 | 0.3575 | 206.0 |
| m03_reciprocal_min | 20.33 | 45.083 | 0.1494 | 0.0088 | 0.3575 | 206.0 |
| m14_mutual_regret | 19.83 | 45.25 | 0.149 | 0.0088 | 0.3583 | 206.0 |
| m26_greedy_one_swap | 20.0 | 45.167 | 0.1522 | 0.0088 | 0.3583 | 206.0 |
| __control__ | 19.83 | 45.25 | 0.149 | 0.0088 | 0.3583 | 206.0 |

> **Correction 2026-10-09 (label only):** the original line read "12 seed-level means (df = 11)" - a hardcoded template string written for Phase 3 (12 seeds). Verified: screening intervals were computed with df = n_seeds - 1 = 2 (3 seed clusters, seeds 143-145); recomputing from screening_rows.jsonl reproduces the published ci95 to 6 decimal places (implied t = 4.303 = t(.975,2)); df = 11 does not match. No analysis logic, retention decisions, or numeric results changed; the frozen string in analyse_tournament.py was intentionally NOT edited.
