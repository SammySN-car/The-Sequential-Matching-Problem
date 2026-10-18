# Design: Broad Method Discovery Tournament (PREREGISTERED)

Status: written before Phase 1. Constants and rules below are frozen; changing any of them
after Phase 1 begins is a protocol violation (spec Section 8).

## 1. Purpose

Search broadly across ~30 sequential decision policy variants (mechanisms with documented
overlaps, not independent paradigms) and determine
whether any reliably outperforms greedy on realized MSMI/100 in this simulator. Greedy is the
incumbent, not the assumed winner; A+C is not assumed either. Every decision is a paired
same-world comparison.

## 2. Incumbent and non-comparability

- Incumbent: GREEDY, fresh promotion result MSMI/100 = 0.4931 (introductions/100 = 38.10,
  mutual/100 = 5.417, ask cost ~203) measured on a DIFFERENT seed set.
- That absolute number must never be compared against tournament numbers (spec Section 13).
  All tournament decisions use paired deltas vs greedy on the same (seed, variant) world.
- E1/E2/E3 line stopped as inconclusive (0.4167 / 0.4062 / 0.3889, all CIs overlapped zero).

## 3. Method inventory (30 slots, substitutions per spec Section 3)

| method_id | group | name | substitution / note |
|---|---|---|---|
| m01_greedy_baseline | A | Greedy baseline (control) | must stay byte-identical to policy.py greedy |
| m02_reciprocal_sum | A | Reciprocal sum | |
| m03_reciprocal_min | A | Reciprocal minimum | |
| m04_reciprocal_product | A | Reciprocal product | |
| m05_harmonic_reciprocal | A | Harmonic reciprocal score | redundancy risk w/ m04 (flagged) |
| m06_bottleneck | A | Bottleneck compatibility | |
| m07_prune_and_greedy | A | Prune-and-greedy | SUBSTITUTES m07_match_count_symmetric (identical to control by construction) |
| m08_weighted_compatibility | A | Weighted compatibility score | structure-only weights |
| m09_partner_scarcity | B | Partner scarcity | |
| m10_degree_balanced | B | Degree-balanced matching | |
| m11_scarcity_x_compat | B | Scarcity x compatibility | redundancy risk w/ m09 (flagged) |
| m12_regret_score | B | Regret score | |
| m13_opportunity_cost | B | Opportunity-cost score | |
| m14_mutual_regret | B | Mutual regret | |
| m15_reserve_high_option | B | Reserve high-option-value members | |
| m16_patient_policy | C | Patient policy | adapted without departure signals |
| m17_daily_quota | C | Daily quota policy | batching |
| m18_time_threshold | C | Time-dependent acceptance threshold | |
| m19_arrival_age | C | Arrival-age policy | reads arrived_day only |
| m20_new_arrival_protection | C | New-arrival protection | |
| m21_delay_cost_threshold | C | Delay-cost threshold | SUBSTITUTES m21_expiration_aware (exit_day unobservable) |
| m22_market_thickness | C | Market-thickness policy | WHEN-to-match trigger |
| m23_hybrid_patient_greedy | C | Hybrid patient-greedy | |
| m24_max_cardinality | D | Maximum-cardinality-first matching | exact on bipartite; documented fallback otherwise |
| m25_max_weight | D | Maximum-weight matching | exact for bipartite n<=180; documented fallback otherwise |
| m26_greedy_one_swap | D | Greedy + one-swap improvement | |
| m27_greedy_augmenting | D | Greedy + augmenting-path improvement | |
| m28_conflict_aware | D | Conflict-aware greedy | redundancy risk w/ m09/m10/m15 (flagged) |
| m29_uncertainty_aware | E | Uncertainty-aware policy | active asking; truth-blind |
| m30_targeted_info | E | Targeted information policy | VoI gate; truth-blind |

## 4. Phases

| Phase | Seeds x variants | Worlds | Arms | Episodes | Rule |
|---|---|---|---|---|---|
| 1 screening | 143-145 x 6 | 18 | 30 methods + shared control (m01 excluded from ranking) | 558 | rank by full-precision paired mean dMSMI/100; retain top 5 + up to 3 diagnostics (total 0-8, rule in section 7) |
| 2 confirmation | 146-151 x 6 | 36 | retained (5-8) + shared control | 216-324 | methods frozen; select at most 2 |
| 3 final | 152-163 x 6 | 72 | selected (1-2) + shared control | 144-216 | credibility verdict |

- Control = greedy (`policy.py --baseline greedy`), run once per phase over that phase's worlds.
- Smoke phase (machinery only, results never ranked): fixture seed 90290 x development, all methods + control (never a tournament seed).
- Seeds 101-142 and 50000+ are used artifacts; tests and fixtures use seed 90210+ only.

## 5. Metrics

- Primary: paired delta of `msmi_per_100_arrived_members` vs control at (seed, variant);
  inference clusters on seed (section 9) because variants share one seeded world per seed.
- Secondary (diagnostic only): introductions/100, mutual/100, mutual per introduction,
  MSMI per introduction, coverage, ask cost, zero-selection days (instrument passes at both
  screening and final, digest-verified against official rows), latency (`inference_seconds`),
  invalid count, within-seed cross-variant dispersion of deltas.
- Never ranked by: AUC, offline expected value, mutual acceptances alone, introduction
  counts alone, ask efficiency (spec Section 5).

## 6. Frozen constants (source of truth: common.py / alloc.py; enforced by test_design_constants_frozen)

| Constant | Value | Used by | Rationale |
|---|---|---|---|
| PROTECT_DAYS | 3 | m20 | three-day grace for new arrivals |
| QUOTA_DIVISOR | 2 | m17 | keep top ceil(n/QUOTA_DIVISOR) = ceil(n/2) pairs per day |
| PATIENT_MIN_SCORE | 3 | m16 | at least 3 of the 7 observed soft fields (suite strong-alignment cutoff, same as STRONG_SCORE) |
| TIME_T0 / TIME_STEP | 4 / 20 | m18 | 4 -> 3 -> 2 over the three 20-day thirds |
| DELAY_T0 / DELAY_STEP | 4 / 15 | m21 | one quality point forgiven per 15 wait-days |
| THIN_AVG_DEG | 2.0 | m22 | avg feasible degree below 2 = thin graph |
| HYBRID_MIN_SCORE | 4 | m23 | favorable top score |
| HYBRID_AVG_DEG | 3.0 | m23 | favorable density |
| STRONG_SCORE | 3 | m15 | strong-alternative cutoff |
| PRUNE_MIN_SCORE | 2 | m07 | prune cutoff |
| HUNGARIAN_NODE_CAP | 180 | m25 | O(n^3) latency guard under the 10 s limit |
| AUGMENT_ROUNDS_CAP | 50 | m27 | termination guard |
| SOFT_ASK_RESERVE | 3 | m29, m30 | reserve soft-ask budget units so hard asks cannot consume the whole daily budget; m29/m30 therefore issue one fewer constraints bundle per day (3 vs the control's 4) - preregistered trade-off, reported as secondary ask cost |
| VOI_EVAL_CAP | 96 | m30 | max greedy recomputations per ask phase in fixed (member, field, option) enumeration order; hard deterministic bound on VoI enumeration |

## 7. Retention rules (Phase 1 -> Phase 2)

Eligibility, all required: zero invalid episodes; mean paired delta >= -0.05; no catastrophic
family (every per-variant mean delta >= -0.15); latency acceptable (all invocations valid,
i.e. under 10 s each). m01_greedy_baseline is excluded from eligibility, ranking, and
retention (parity/diagnostic only). Rank eligible methods by FULL-precision mean paired
delta (descending), ties broken by (round(mean, 6), method_id) - never by display-rounded
values, never by boundary expansion. Candidates = the first min(5, E) ranked eligible
(core) plus the next up to 3 as DIAGNOSTIC retention with a fixed-format per-method reason
in screening_report.md (E = eligible count; retained total therefore 0-8). Every retained
method's survival reason is written to screening_report.md. Human review gate before Phase
2 execution may only REMOVE candidates with a documented reason; it may not add, swap, or
backfill beyond the preregistered list. If E = 0: retained = [], Phases 2 and 3 are
skipped, and the final verdict branch is keep-greedy with reason "no eligible candidates at
screening" recorded in final_results.json.

## 8. Freeze protocol

After screening analysis, sha256 the full behavior/spec set into
`hashes/policy_freeze_after_screening.txt` using repo-root-relative paths: methods_*.py,
common.py, alloc.py, _cli.py, registry.py, gen_policies.py, policies/*.py,
run_tournament.py, analyse_tournament.py, instrument.py, design.md, methods.json, plus the
repo-frozen kit.py, policy.py, policy_ac.py, evaluate.py, organise.py, Dockerfile. Tests
are excluded (documented; tests never execute inside phases). The same file list is hashed
before screening as the pre-screening code fingerprint carried on every runner row, and
analysis asserts every screening row matches it (version-safe rows; failed attempts are
kept visible in per_phase/<phase>_attempts.jsonl). The confirm1/confirm2 runners verify
the freeze manifest before executing and abort on any mismatch. No threshold, weight,
feature, logic, design.md, or methods.json edits between phases; a method may be
eliminated, never redesigned (spec Section 8).

## 9. Selection and verdict rules

- Inference unit: development/delayed/shift/drift are the SAME seeded world per seed and
  sparse/cold_start share the stream prefix (verified on fixtures), so the 6 per-variant
  deltas are averaged per seed and inference runs on the 12 seed-level means (df = 11).
  Per-variant means are reported for every phase as mandatory stratification. Screening is
  gate-only: no superiority claims; unit-level CIs are never presented as primary.
- Phase 2 selection: top 2 by FULL-precision mean paired delta over seed-level means
  (sign-independent; zero-invalid only; m01 excluded), ties by (round(mean, 6), method_id).
- Phase 3 credibility, a candidate must satisfy ALL: zero invalid episodes; seed-level mean
  paired delta > 0; cluster t-CI lower bound > 0 at the Bonferroni level for the number of
  candidates tested (k = 1 -> 95%, t = 2.201 at df 11; k = 2 -> 99%, t = 3.106 at df 11);
  no per-variant mean delta < -0.15.
- Winner: one credible candidate wins; both credible -> higher mean delta (coverage delta
  >= -0.05 and ask cost reported as guardrails, not binding); none credible -> keep greedy
  and write exactly: "Greedy remains the best empirically supported policy among the evaluated candidates." Never "optimal".
- Several candidates close together: stronger MSMI plus better robustness/guardrails (spec Section 13).

## 10. Information policy (applies to all 30 methods)

Allowed: protocol-delivered state (members incl. fields/field_status/field_observed_day/
arrived_day/available, introductions, feedback, ask_log, day, ask_budget_remaining),
kit.OPTIONS/HARD/SOFT/eligibility/baseline_asks/baseline_match, and method-owned memory
(<= 1 MiB JSON). Banned verbatim: truth, bias, response_rate, second_bias, exit_day, seed,
variant, future arrivals, future feedback, raw sim.events, hidden globals. Enforced by the
AST leak scan test_no_hidden_state_access, not by review alone.

## 11. Known threats to validity

- m16/m18/m21/m23 are adapted WITHOUT departure/expiry signals (Akbarpour et al. show patient
  wins need them); this is the honest simulator-compatible form.
- m24/m25 are exact only on bipartite graphs within the node cap; fallbacks are documented in
  methods.json, forced by dedicated odd-cycle tests, and measured on fixture worlds
  (non-bipartite 5/90 snapshots, node-cap breach 6/90 - preflight_report), so both fallback
  paths are reachable in practice. m24 overlaps m27 (augment3) and m25 overlaps m26
  (one-swap); m25 prunes zero-score edges (weight objective unaffected; cardinality may
  differ from m24).
- Seeded-world clustering: development/delayed/shift/drift are the same world draw per seed
  (verified on fixtures), so paired units within a seed are NOT independent; all inference
  clusters on seed (section 9) and per-variant stratification is reported everywhere.
- Candidate-set honesty: the ~30 entries are policy VARIANTS/mechanisms with documented
  overlaps (m01~control, m05~m04, m11~m09, m12/m13/m14, m24~m27, m25~m26, m28~m09/m10/m15),
  not 30 independent paradigms; methods whose action digest equals control on every
  screening world are listed as "no observed difference from control".
- Sequential-coverage limitation: the set emphasizes match-time scoring and modest asking
  policies; it contains little feedback-history/memory, long-horizon state, or
  field_observed_day dynamics, so a keep-greedy verdict means "among evaluated candidates",
  never global optimality.
- Registry flags redundancy risks (m05~m04, m11~m09, m28~m09/m10/m15); retention diagnostics
  may expose them; phase separation prevents tuning them away.
- Phase 1 has only 18 paired worlds: no method may be called a winner from screening alone
  (spec Sections 4 and 5).
