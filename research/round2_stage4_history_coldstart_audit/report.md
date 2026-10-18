# Round 2 Stage 4 — History-Lift (X0), Cold-Start Penalty (X1), and Simulator RNG Audit

**Directory:** `research/round2_stage4_history_coldstart_audit/`
**Date:** 2026-10-07 | **Environment:** Python 3.13.5, scikit-learn 1.8.0, Windows
**Nature:** two cheap offline diagnostics on frozen data + a read-only source audit.
No policy/model tuning, no new simulator episodes, no promotion experiment,
no holdout access, no threshold sweeps, no new episode seeds.

**Evidence tags** (applied per claim): `[OBSERVED]` measured/recorded directly ·
`[INTERPRETATION]` reasoned from observed evidence · `[HYPOTHESIS]` plausible but
untested · `[UNKNOWN]` cannot be determined from available evidence ·
`[RECOMMENDATION]` proposed action.

---

## 1. Purpose, scope, and prohibitions

Stage 4 answers four questions before the frozen candidate proceeds:
(Q1) do history features carry real predictive lift? (Q2) does the original
score floor impose a cold-start (newcomer) penalty? (Q3) how noisy is a future
promotion comparison, and does the common-random-number (CRN) design reduce it?
(Q4) PROCEED / NOT / NEED MORE EVIDENCE on promotion given the above.

Prohibitions honored `[OBSERVED — verified in §16]`:
no new policy/model tuning; frozen candidate `float(model["floor"])/2.0 =
0.003952587007648379` untouched; no promotion runs; no holdout access; no
threshold sweeps; no seeds 107–118 used as episode seeds; no Thompson/RL;
no changes to `policy.py` / `policy_ac.py` / `kit.py` / `evaluate.py` /
`organise.py` / `Dockerfile` / `.dockerignore` or any frozen Round 1–2 / Stage 2–3
artifact; the existing feature pipeline was reused exactly (X0) and stored
diagnostics were read (X1); where stored data could not support a required
stratification, the STOP rule was applied and reported (§13).

## 2. Inputs and provenance

| Input | Detail | Hash (sha256, first 16) |
|---|---|---|
| `research/out_scale800/rows.csv` | 86,711,700 B; 259,696 rows; 56 cols (12 meta + 44 `feat_*`) | `1d5cf4d9055dd6d3` |
| `research/out_scale800/report.json` | original Round 1 validation report (used as fidelity reference) | (read-only) |
| Original pipeline | `research/{run_experiment,analyze,features,labels,collect,integrity}.py` | (read-only) |
| Stage 1.5 probe | `probe_seed101_run{1,2}.json` (identical files) | `3897d631cc655ff4` both |
| Stage 2 diags | `diag_arm_{a,b}_seed{101,102,103}.json` (6) | (read-only) |
| Stage 3 diags | `diag_arm_{frozen,intermediate,nofloor}_seed{104,105,106}.json` (9) | (read-only) |
| Stage 3 runs | `arm_{frozen,intermediate,nofloor}_seed{104,105,106}.json` (9) | (read-only) |
| `kit.py` | simulator, 237 lines | `0D2CB3D3B46CA2A6` (unchanged, §16) |

Scale800 construction `[OBSERVED, report.json]`: 3,520 rollouts (3,200 random /
320 greedy), 800 worlds, 60 decision days + 40 follow-up, 6 variants, whole-world
train/val split 640/160 (209,238 / 50,458 rows; overlap 0 worlds / 0 seeds),
mutual val positives 7,108 (prev 0.1409), MSMI val positives 475 (prev 0.0094).

## 3. X0 method — exact reuse of the original pipeline

X0 retrains **Model A** (all 44 features) and **Model B** (history group
removed → 34 features) with the original code, unmodified `[OBSERVED]`:

- split: `analyze.world_split(rows, val_frac=0.2, split_seed=0)`,
  `world_key = (world_seed, variant)`, whole worlds only;
- model: `analyze.fit_models` → `HistGradientBoostingClassifier(random_state=0,
  max_iter=200, learning_rate=0.1)` (identical hyperparameters; no search);
- metrics: `analyze.evaluate` (ROC-AUC, AP, log-loss, Brier + Hanley–McNeil
  row-level CI, used only as reference);
- removed keys (Model B): `features.FEATURE_GROUPS['history']` =
  `hist_{n_intros,n_mutual,n_dates,yes_rate,n_missing}_{mean,absdiff}` —
  exactly the 5 history groups × {mean, absdiff} = 10 keys. TEMPORAL keys
  (`day`, `days_since_arrival_*`, `ask_budget`) are **not** in this group and
  stay in Model B `[OBSERVED — features.py:36-50]`;
- targets: mutual (`label_mutual`) and MSMI (`label`), per Stage 4 scope; the
  `date` target was not part of X0;
- rows loaded from `rows.csv` preserving original canonical order; empty cells
  → NaN (original convention); train/val counts asserted equal to
  `report.json` before fitting.

## 4. X0 stratification derivation and uncertainty design

**Experience** `[OBSERVED — features.py:196-199]`: `hist_n_intros_mean =
(a+b)/2` and `hist_n_intros_absdiff = |a−b|` at decision time, so
`min = mean − absdiff/2` is exactly the **less-experienced member's prior
introduction count** (integer arithmetic is exact in binary floats). Groups:
`{0, 1-2, 3+}`. **Logging policy**: the `policy` column (`random|greedy`) as
stored `[OBSERVED]`. Joint cells (3 × 2) + marginals, validation rows only.
No data was reconstructed or re-collected.

**Uncertainty** `[OBSERVED — design recorded in x0_results.json]`:
world-clustered bootstrap; clusters = the 160 validation worlds keyed
`(world_seed, variant)`; 2,000 resamples of 160 clusters with replacement;
row weight = cluster multiplicity; percentile CI [2.5, 97.5]; per-target RNG
seeds 9099 (mutual) / 9100 (MSMI) — bootstrap stream seeds, not episode seeds;
0 resamples skipped as single-class for either target.

## 5. X0 fidelity check — exact reproduction

Model A retrained from `rows.csv` reproduces the original `report.json`
`hist_gb` metrics with **difference 0.0 on all four metrics, both targets**
`[OBSERVED — x0_results.json: reproduction_check_vs_scale800_report_json]`:
roc_auc / avg_precision / log_loss / brier all `diff = 0.0`. Train/val counts
also match exactly (209,238/30,337 pos mutual; 2,094 pos MSMI; val 50,458 with
7,108 / 475 pos). The split reproduces 640/160 worlds with 0/0 overlap.
**The X0 comparison therefore runs on a bitwise-equivalent reimplementation of
the original experiment** `[INTERPRETATION]`.

## 6. X0 overall results (validation, n = 50,458)

**Mutual acceptance** `[OBSERVED]`:

| Metric | Model A (44) | Model B (34, no history) | Δ (A − B) |
|---|---|---|---|
| ROC-AUC | 0.6131 | 0.6018 | **+0.011306** |
| world-clustered 95% CI of ΔAUC | | | **[+0.006265, +0.016122]** (frac<0 = 0.000) |
| Average precision | 0.1972 | 0.1899 | +0.007243 |
| 95% CI of ΔAP | | | [+0.002644, +0.011268] |
| AP lift over prevalence | 1.40× | 1.35× | — |
| Log-loss | 0.3966 | 0.3988 | −0.002196 (A better) |
| Brier | 0.1188 | 0.1194 | −0.000630 (A better) |

**MSMI** `[OBSERVED]`:

| Metric | Model A (44) | Model B (34, no history) | Δ (A − B) |
|---|---|---|---|
| ROC-AUC | 0.5937 | 0.5850 | +0.008725 |
| world-clustered 95% CI of ΔAUC | | | **[−0.017894, +0.034163]** (frac<0 = 0.255) |
| Average precision | 0.0123 | 0.0129 | −0.000581 |
| 95% CI of ΔAP | | | [−0.006732, +0.001316] |
| AP lift over prevalence | 1.30× | 1.37× | — |
| Log-loss | 0.0541 | 0.0540 | +0.000163 (A worse) |
| Brier | 0.0095 | 0.0094 | +0.000031 (A worse) |

## 7. X0 stratified results (validation rows)

Joint experience × policy cells, ΔAUC (A − B) `[OBSERVED]`:

| Cell | mutual n / pos | mutual ΔAUC | MSMI n / pos | MSMI ΔAUC |
|---|---|---|---|---|
| 0 \| random | 28,353 / 4,183 | +0.0070 | 28,353 / 257 | +0.0024 |
| 0 \| greedy | 2,529 / 392 | +0.0207 | 2,529 / 15 | +0.1451 |
| 1-2 \| random | 14,894 / 1,970 | +0.0119 | 14,894 / 165 | −0.0025 |
| 1-2 \| greedy | 1,494 / 189 | +0.0285 | 1,494 / 16 | +0.1165 |
| 3+ \| random | 2,833 / 328 | +0.0153 | 2,833 / 21 | +0.0521 |
| 3+ \| greedy | 355 / 46 | +0.0297 | 355 / 1 | −0.1780 |

Marginals `[OBSERVED]`:

| Stratum | mutual ΔAUC | MSMI ΔAUC |
|---|---|---|
| experience 0 (n=30,882) | +0.0081 | +0.0090 |
| experience 1-2 (n=16,388) | +0.0130 | +0.0063 |
| experience 3+ (n=3,188) | +0.0169 | +0.0439 |
| policy random (n=46,080) | +0.0100 | +0.0025 |
| policy greedy (n=4,378) | +0.0277 | +0.1159 |

Val experience counts: 0 → 30,882; 1-2 → 16,388; 3+ → 3,188 `[OBSERVED]`.

**Stability warning** `[INTERPRETATION]`: MSMI joint cells rest on 1–16
positives (greedy margin: 32 positives total); those cell-level ΔAUCs are
unstable and must not be read as effects — only the pre-registered overall
clustered CIs (§6) and the mutual table are reliable at this scale.

## 8. X0 interpretation vs pre-stated heuristics

Pre-stated guides (task-provided, engineering heuristics — not significance
claims): ΔAUC < 0.01 weak (especially if CI includes 0); ΔAUC ≥ 0.02 with CI
away from 0 potentially meaningful `[OBSERVED — guide as recorded]`.

- **Mutual:** ΔAUC +0.0113 sits **above the weak band and below the
  meaningful band**; the CI excludes 0 entirely (frac<0 = 0.000) and every one
  of the 6 joint strata is positive, with a monotone rise across experience
  groups (0.0081 → 0.0130 → 0.0169) `[OBSERVED]`. History features therefore
  carry a **small but consistent** signal — real, not large `[INTERPRETATION]`.
- **MSMI:** ΔAUC CI includes 0, ΔAP is ≈0/slightly negative, and log-loss/
  Brier are marginally worse without history `[OBSERVED]` → **weak /
  inconclusive** `[INTERPRETATION]`. At 475 positives the target is too rare
  for a sub-0.02 feature-group effect to resolve `[HYPOTHESIS]`.
- The monotone experience gradient is consistent with history features being
  more informative once members have any history, and near-uninformative at
  exactly 0 `[HYPOTHESIS — not tested further; tuning forbidden]`.

## 9. X1 method and stored-data schema discovery

X1 is computed **only from frozen stored diagnostics** (Stage 1.5 probe seed 101
at the original floor; Stage 2 diags seeds 101–103; Stage 3 diags seeds
104–106, which record both the frozen and the intermediate threshold from the
same instrument pass). Schema discovery `[OBSERVED — x1_results.json:
schema_discovery]`:

- per-day match records store **counts** (`n_cand`, `n_above`, `n_below`,
  `n_ge_inter`, `n_selected`, `category`, …) — no per-candidate rows;
- per-candidate ids + scores exist only for **selected** pairs
  (`selected_scored`);
- per-variant aggregates: `feasible_total`/`cand_total`,
  `above_frozen_floor_total`, `above_intermediate_floor_total` (Stage 3),
  `zero_selected_categories`, `greedy_n`, `greedy_below_floor_n`, metrics;
- no stored key anywhere contains `hist_`, `experience`, `prior_intro`, or any
  member-history field for candidates.

## 10. X1 determinism and original-floor exclusion by variant (Stage 1.5)

`probe_seed101_run1.json` deep-equals `probe_seed101_run2.json` (sha256
identical: `3897d631cc655ff4…`) `[OBSERVED]` — the stored probe is a
deterministic artifact.

Exclusion rate at the **original floor** = 1 − above/cand, per variant
(seed 101, 60 days each) `[OBSERVED]`:

| Variant | feasible cand | above floor | excluded | all_below_floor zero-sel days (of 60) | greedy picks blocked |
|---|---|---|---|---|---|
| development | 793 | 125 | 84.24% | 17 | 85.4% |
| sparse | 327 | 19 | **94.19%** | **47** | 94.1% |
| **cold_start** | 523 | 104 | **80.11%** | 25 | 83.5% |
| delayed | 859 | 117 | 86.38% | 19 | 86.8% |
| shift | 847 | 121 | 85.71% | 22 | 87.5% |
| drift | 856 | 125 | 85.40% | 18 | 85.9% |

Cold-start exclusion is the **second-lowest** of six variants; sparsity
(profile completeness) is the dominant driver of exclusion, not newcomer
status `[INTERPRETATION]`. The floor is globally restrictive (80–94% of
feasible candidates excluded; 83–94% of greedy picks lie below it)
`[OBSERVED]` — consistent with Stage 2/3 findings, not a cold-start-specific
effect `[INTERPRETATION]`.

## 11. X1 cold-start vs other variants across all stored settings

For each of the 16 stored settings where the frozen threshold was recorded
(1 probe + 6 Stage 2 + 9 Stage 3), cold_start exclusion was compared to the
mean of the other five variants on the **same instrument pass**
(same candidate sets — Stage 3 stores both thresholds per pass)
`[OBSERVED — x1_results.json: coldstart_vs_others]`:

- cold_start **above** others' mean in only **3 of 16** settings (deltas
  +0.011, +0.032, +0.063); **below** in 13 of 16 (deltas −0.007 … −0.245);
- at the original floor specifically (probe + arm-a/frozen arms, 7 settings):
  cold_start below others' mean in 6 of 7.

**Answer to Q2 (variant level): no observed cold-start penalty** — if anything
cold_start candidates are excluded slightly *less* than other variants'
`[INTERPRETATION]`. Note the arms' trajectories differ across settings, so
this is a consistency count across independent stored measurements, not a
single paired test `[INTERPRETATION]`.

## 12. X1 day proxy, threshold recovery, zero-selection, greedy-blocked

**Day-bucket curve** of original-floor exclusion (pooled over the 6 variants,
probe seed 101) `[OBSERVED]`:

| Decision day | 0–9 | 10–19 | 20–39 | 40–59 |
|---|---|---|---|---|
| excluded | **60.32%** | 71.89% | 88.18% | **94.65%** |

Early days — when *every* member is a newcomer with zero introduction history —
have the **lowest** exclusion; exclusion rises as the episode progresses
`[OBSERVED]`. This is the opposite direction of a newcomer penalty, but day is
confounded by frontier depletion (past pairs leave the candidate set, so later
frontiers are intrinsically harder matches) and by any score drift `[HYPOTHESIS]`.
The day curve is a **proxy only, not candidate-level experience** `[INTERPRETATION]`.

**Threshold recovery** (Stage 3, both thresholds from identical candidate sets):
the half-floor recovers, on average over the 9 arm×seed settings, this share of
feasible candidates vs the original floor `[OBSERVED]`:

| Variant | cold_start | development | sparse | delayed | shift | drift |
|---|---|---|---|---|---|---|
| mean recovery | 36.9% | 32.6% | 40.5% | 34.4% | 33.0% | 32.7% |

Cold-start recovery (0.369) is modestly above development (0.326) but below
sparse (0.405) `[OBSERVED]` — the original floor's removable volume is not
dominated by the cold-start variant `[INTERPRETATION]`. Frozen-arm cold_start
exclusion at the two thresholds, per seed: frozen 84.6% / 86.2% / 78.2% vs
half-floor 44.4% / 32.1% / 19.6% `[OBSERVED]`.

Zero-selection days with candidates present (Stage 1.5, all 60 days are
`all_below_floor` when they occur): sparse 47, cold_start 25, shift 22,
delayed 19, drift 18, development 17 `[OBSERVED]` — again sparse-dominant.

## 13. X1 limitation (STOP rule): candidate-level experience not reconstructible

The required stratification — *feasible candidates grouped by the less-experienced
member's prior-intro count at decision time* — **cannot be computed from stored
data** `[OBSERVED — schema in §9]`, because:

1. below-floor candidates are stored as a **count only** (no ids, no scores,
   no member history);
2. per-candidate records (`selected_scored`) exist only for pairs the arm
   actually selected, i.e. *after* the floor filter — the very population X1
   needs is absent;
3. no stored artifact contains any history/experience field for a candidate
   pair.

Reconstructing it would require **new simulator runs**, which this stage
forbids. Per the STOP rule this sub-part is reported, not approximated away:
the exact experience-stratified cold-start penalty is `[UNKNOWN]`. Variant
identity (cold_start) and day buckets (§11–12) are used only as explicitly
labeled proxies.

## 14. Simulator RNG and outcome audit (`kit.py`, read-only)

Mechanism `[OBSERVED — kit.py]`:

1. **Content-addressed RNG** (kit.py:24–25): `rand_for(*parts)` builds a fresh
   `random.Random` from `SHA256('|'.join(parts))[:16]` — stateless, keyed by
   content, no global stream.
2. **Worlds** (kit.py:35–67): `generate(seed, …)` draws everything from
   `random.Random(seed)`; member traits `bias`, `response_rate`,
   `second_bias` are fixed per member at generation. Variant flags (`sparse`,
   `cold_start` completeness 0.2 vs 0.35, `shift` weights, `delayed`) apply at
   generation/probability time.
3. **Asks** (kit.py:112–132): **no randomness** — answers reveal stored truth
   unless the field was declined. Ask resolution cannot perturb any RNG state.
4. **Outcomes** (kit.py:141–189): for each introduced pair on day `d`,
   `r = rand_for(world_seed, a, b, d)` (line 154), then a **fixed draw
   sequence**: `shared ~ N(0, .45)`; per actor respond?/accept?/delay(1–7);
   if mutual: date delay (1–14, +5–12 if `delayed`), happened (~0.78); if
   happened: per actor answer?/delay(1–5)/yes?. `_prob` (133–140) depends on
   truth fit, `bias`, `shared`, variant weights, and `day ≥ 35` drift.
5. **Metrics** (kit.py:190–203): deterministic function of the event record.
6. **Episode worlds** (evaluate.py:152): every policy on the same
   `(seed, variant)` is handed the same `generate(seed, 200, 'evaluation',
   variant)` world.

**CRN properties** `[INTERPRETATION from the above OBSERVED source]`:

- **World-level CRN is exact:** same seed ⇒ identical members, traits, and
  arrival schedules for any policy — no shared-stream contamination is
  possible because there is no shared stream.
- **Introduction-level CRN is exact on shared (pair, day):** outcome draws are
  a pure function of `(world_seed, pair, day)`; two arms introducing the same
  pair on the same day get *identical* responses/dates/MSMI outcomes
  regardless of what else happened that day or in what order (fresh keyed RNG
  per pair; loop order at line 152 is canonical anyway).
- **Coupling limits** `[OBSERVED structure + INTERPRETATION]`: (a) the floor
  changes *which* pairs are introduced → keys diverge precisely where arms
  differ; (b) `day` is in the key, so pure timing shifts decouple outcomes;
  (c) the `drift` variant's `day ≥ 35` term makes the *probability itself*
  day-dependent; (d) conditional paths (date draws only after mutual) are
  deterministic within the key, so no policy-visible branching exists.
- Net: the simulator is a **stronger-than-usual CRN design** — coupling is
  pairwise-content-addressed rather than stream-sequential — but a floor
  ablation deliberately breaks most shared keys, so pairing buys world/traits
  sharing and partial outcome sharing, not full outcome sharing
  `[INTERPRETATION]`.

## 15. Q3 — noise of the future promotion comparison

From the frozen Stage 3 runs (stored, 3 paired development seeds 104–106)
`[OBSERVED — q3_noise_results.json]`:

| Arm | primary by seed | mean |
|---|---|---|
| frozen | 0.1667 / 0.5000 / 0.0833 | 0.2500 |
| intermediate (frozen/2) | 0.4167 / 0.3333 / 0.3333 | 0.3611 |
| nofloor | 0.1667 / 0.3333 / 0.3333 | 0.2778 |

Paired differences: intermediate − frozen mean **+0.1111**, across-seed SD
**0.2406** (SEM 0.139); nofloor − frozen mean +0.0278, SD 0.2097;
nofloor − intermediate mean −0.0833, SD 0.1443 `[OBSERVED]`.

Normal-approximation guidance (two-sided α=0.05, power 0.80,
`n = ((1.96+0.84)·SD/d)²`, SD = 0.2406) `[OBSERVED computation,
INTERPRETATION — SD itself estimated from only 3 seeds, hence unstable]`:

| detectable mean paired effect | ≈ seeds needed |
|---|---|
| 0.20 | 12 |
| 0.10 | 46 |
| 0.05 | 182 |

Rarity: MSMI events were 9 / 13 / 10 per arm over 18 episodes → Poisson
relative SE ≈ 1/√k ≈ 0.28–0.33 `[OBSERVED + INTERPRETATION]`. The primary
score's variance is dominated by rare-event counts, amplified because mutual →
date → two-timed-second-yes is a multiplicative funnel `[INTERPRETATION]`.

**CRN effect** `[INTERPRETATION]`: the paired-seed design already embeds the
§14 content-addressed coupling; the observed paired SD (0.14–0.24) is the
*realized* noise **after** that partial coupling — so these numbers are the
honest basis for planning, and they say: retain paired (same-seed) comparisons;
budget ≈ 12 paired seeds for 0.2-scale effects and ≈ 46 for 0.1-scale effects;
a 3-seed comparison (as in Stage 2/3, which is development evidence) cannot
resolve effects below ≈ 0.2 `[RECOMMENDATION]`.

## 16. Integrity and prohibition compliance

`verify_integrity.py` re-hashed 17 frozen files after all analysis
`[OBSERVED — integrity_after.json]`: **17/17 match, ALL MATCH = True**
(policy.py `379CC2D9519E8D3B`, policy_ac.py `90FB9AD306E89BFB`,
kit.py `0D2CB3D3B46CA2A6`, evaluate.py `D09CC14BF634A741`, organise.py
`DA9D6B3A197F1FF8`, Dockerfile `FEF95FA3D6BC038F`, .dockerignore
`6FA959B629F9ED8C`, Stage 3 preregistration/promotion-audit/shim/report/summary,
Stage 2 report/interpretation, round1-research-record.md, results/artifact.sha256).

Compliance checklist `[OBSERVED]`:
- frozen candidate value never written or re-derived by any script here;
- no simulator episodes executed (X0: offline training only, 109.6 s total;
  X1: JSON parsing, 0.1 s; Q3: JSON parsing);
- no seeds 107–118 used anywhere (only stored data from seeds 101–106 read;
  bootstrap RNG seeds 9099/9100 are numpy stream seeds);
- no threshold sweep: exactly two pre-stated models (44 vs 34 features) with
  the original fixed hyperparameters;
- no holdout/leaderboard data accessed; `promotion_audit.json` untouched;
- all Stage 4 outputs written only inside this directory.

---

# Decision memo

**Q1 — Is there a real history signal?**
**YES for mutual, small; NO/inconclusive for MSMI.** `[OBSERVED]` Mutual
ΔAUC = +0.0113, world-clustered CI [+0.0063, +0.0161] (excludes 0), all 6
joint strata positive, monotone across experience groups; log-loss and Brier
both improve without any tuning. MSMI ΔAUC CI includes 0 and ΔAP ≈ 0.
`[INTERPRETATION]` The signal is real but sits between the pre-stated "weak"
and "meaningful" bands for the primary-adjacent target (mutual) and is
unresolvable for the rare target (MSMI). History features are worth keeping
(obviously — they are part of the frozen feature set) but do **not** justify a
history-specific modeling project at this time.

**Q2 — Is there a newcomer (cold-start) penalty?**
**Not observed at the variant level; exact candidate-level answer is
UNKNOWN (STOP).** `[OBSERVED]` cold_start exclusion ≤ others' mean in 13/16
stored settings; Stage 1.5 cold_start 80.1% (2nd-lowest of 6; sparse highest
94.2%); day-proxy exclusion lowest when all members are new (60% days 0–9 →
95% days 40–59); half-floor recovery in cold_start (36.9%) is unexceptional.
`[UNKNOWN]` Candidate-level experience stratification cannot be reconstructed
from stored diagnostics (§13) — that specific sub-question needs new runs,
which this stage did not perform. `[INTERPRETATION]` Current evidence points
to *profile sparsity*, not newcomer status, as the floor's discriminator.

**Q3 — How noisy is the future promotion comparison? Does CRN reduce it?**
`[OBSERVED]` Paired across-seed SD of primary ≈ 0.14–0.24 (n=3, unstable);
MSMI event counts 9–13 → ~30% Poisson relative SE. `[INTERPRETATION]`
The simulator's content-addressed RNG (§14) gives exact world-level and exact
shared-(pair,day) outcome coupling — stronger than sequential-stream designs —
but a floor change breaks most shared keys, so realized noise stays rare-event
dominated. `[RECOMMENDATION]` Keep same-seed paired comparisons; budget ≈ 12
paired seeds for 0.2-scale effects, ≈ 46 for 0.1-scale effects.

**Q4 — Promotion: PROCEED / NOT / NEED MORE EVIDENCE?**
**PROCEED** (with the Stage 3 decision — frozen candidate = floor/2 — unchanged)
`[RECOMMENDATION]`. Grounds `[INTERPRETATION]`: X0 shows no blocker (history
lift is small and additive, not a hidden dependency the frozen candidate
lacks); X1 shows no cold-start penalty that the promotion would exacerbolate;
the promotion's own statistical weakness (3-seed development evidence) is a
protocol matter for the *next* comparison, already flagged by the Stage 3
audit. Exploration/cold-start work: **optional follow-up, low–moderate
priority**, not promotion-blocking. What would change this: a candidate-level
experience analysis (needs new runs — requires separate approval), or a
promotion protocol that cannot afford ≈12 paired seeds `[RECOMMENDATION]`.

---

## Evidence tag legend
`[OBSERVED]` measured/recorded · `[INTERPRETATION]` reasoned from evidence ·
`[HYPOTHESIS]` plausible, untested · `[UNKNOWN]` undeterminable from available
evidence · `[RECOMMENDATION]` proposed action.

## File inventory (this directory)
`report.md` (this file), `summary.json`, `run_log.txt`,
`x0_history_lift.py` → `x0_results.json`,
`x1_coldstart_penalty.py` → `x1_results.json`,
`q3_noise_from_stage3.py` → `q3_noise_results.json`,
`verify_integrity.py` → `integrity_after.json`.