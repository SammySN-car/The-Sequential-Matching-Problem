# Evidence Inventory — per-study audit

Every experiment/analysis whose results this EDA reconciles or reuses. For each:
source artifact, unit of analysis, target, features, collector policy, split,
positives, metric, uncertainty treatment, and limitations relevant to
cross-study comparison. Row unit is called out explicitly because mixing
row-level and world-level uncertainty was a known past failure mode.

---

## E1. out (Round-2 learned scoring study, small)

- **Source:** `research/out/` (`rows.csv` 32,044 rows; `report.txt`; `report.json`).
- **Worlds/seeds:** 100 worlds; collectors 400 rand + 40 greedy rollouts.
- **Row unit:** one introduced pair per row (44 `feat_*` features).
- **Target:** label = official MSMI (also mutual/date labels present).
- **Positives:** 70 MSMI in the validation split (tiny).
- **Split:** by rollout/world (not row-random); train/val as frozen in report.
- **Metric:** HistGB global AUC + AP lift; **AUC MSMI 0.5218, AP lift 0.99x**;
  mutual 0.5996, date 0.6055. Class balance: train 236 pos (0.91%), val 70 (1.13%).
- **Uncertainty:** bootstrap CIs in report; with 70 positives the CI is wide.
- **Limitations for reconciliation:** 100 worlds only; validation positives = 70 →
  AUC estimate is essentially noise-dominated; do NOT compare point-estimate to
  scale800's as if same design. This study is the "AUC ~0.52, nothing works"
  data point that later studies contradict at higher n.

## E2. out_scale800 (learned scoring study, large)

- **Source:** `research/out_scale800/` (`rows.csv` 259,696 rows; `worlds.csv`
  3,520 rollouts; `report.txt`).
- **Worlds/seeds:** 800 worlds (seeds 50000+ family); collectors 3,200 rand +
  320 greedy rollouts.
- **Row unit:** introduced pair (same 44 features as E1).
- **Target:** label (MSMI), label_mutual, label_date.
- **Positives:** 475 MSMI in val (6.8x E1); 2,569 MSMI overall.
- **Metric:** **MSMI AUC 0.5937 [0.5667, 0.6208], AP lift 1.30x**; mutual 0.6131,
  date 0.6064.
- **Uncertainty:** bootstrap by world; CI excludes 0.5.
- **Limitations:** still collector-logged intros only (selection: pairs chosen by
  rand/greedy collectors, not arbitrary pairs); no within-day ranking metric
  reported (filled by EDA S06); no per-day score persistence (S06 re-fit is a
  diagnostic reproduction, not the frozen model's scores).

## E3. N01 decision-state feature autopsy (tournament-adjacent)

- **Source:** `research/next_method_search/n01_introductions.jsonl` (8,433),
  `n01_days.jsonl` (7,560), `n01_autopsy.md`, `n01_feature_results.json`.
- **Worlds:** greedy episodes on seeds 143–163 x 6 variants (126 rollouts),
  replay-validated 126/126 against official aggregates (fidelity + label sums).
- **Row unit:** introduction (33 decision-time-legal features: pair_rank,
  degree_min/max, soft_obs_min/max, history aggregates, etc.).
- **Target:** y_msmi primary (90 events); y_mutual 1,279 / y_date 965 /
  y_second 91 diagnostics.
- **Design:** gated median-split association test (discovery/confirmation), NOT
  AUC; each feature tested at fixed thresholds with wilson CIs; 47.2%
  zero-selection days; feasible edges mean 1.7–4.2.
- **Result:** conclusion B — no supported signal for any feature on y_msmi
  at n=90 positives; 0 diagnostic-only gate passes.
- **Limitations:** 90 positives is ~5x smaller than E2's val; the gated-split
  design has less power than rank metrics at the same n; labels exist only for
  greedy-chosen pairs (selection bias, stated in autopsy). NOT contradictory
  to E2's 0.5937 — different n, different design, different question.

## E4. Method tournament (30 methods)

- **Source:** `research/method_tournament/` (`final_report.md`,
  `per_phase/confirm1_rows.jsonl` 5 arms x 36 worlds, `confirmation_results.json`).
- **Row unit:** (method, seed, variant) episode with official metrics.
- **Arms:** 30 methods screened -> 4 eligible -> 2 confirmed -> **0 credible**;
  m14 is the identity method (delta exactly 0); m03 delta -0.0069 on confirm2.
- **Volume structure:** confirm1 arms all 2,402 assignments (m19: 2,408) —
  methods differ in scoring/tie-breaks, not in volume.
- **Limitations:** eligibility gates removed most methods pre-confirmation;
  final verdict is "no method credible vs baseline", which is consistent with
  E3's null and with small per-world effect sizes (S07 conversion table:
  1.08–1.25% across arms).

## E5. E1/E2/E3 REL-asking experiments (VoI clarification)

- **Source:** `research/e3_rel_experiment/report.md`, `per_arm/*_mechanism.json`.
- **Design:** C control / E1 REL-asks / E2 scorer / E3 combined; mechanism logs
  count intros per day per arm; ask telemetry in report section 3.
- **Key numbers:** E1 REL asks ~42.3/episode, 76.6% of REL-ask days changed the
  allocation, 87.6% of asks on changed days; E3: 67.7% changed-allocation days,
  18.5% edge scores changed; primary comparison not significant; verdict
  INCONCLUSIVE — keep greedy.
- **Limitations:** mechanism JSONs store aggregate intros counts, not per-stage
  outcomes; no per-intro labels persisted for E-arms (fine funnel unavailable).

## E6. Round 2 allocation arms (paired, promotion seeds)

- **Source:** `research/round2/results/eval_rows.jsonl` (arms greedy/ungated/
  gated/no_asks/random x seeds 107–118 x 6 variants = 72 worlds/arm).
- **Row unit:** (arm, seed, variant) episode; official metrics only
  (assignments, mutual, dates, msmi, coverage, ask_cost...).
- **Paired design:** same worlds for every arm (paired contrast valid).
- **Results:** gated (MWM with floor gate) delta **exactly 0.0000** (0/72;
  gate never changed allocation); ungated ablation -0.0486 (per report) /
  -0.097 on paired decomposition; no_asks -0.5556 (volume -0.35 + conversion
  -0.21 per world); random ~0. Coverage: greedy 76.0 assignments/world,
  no_asks 19.6, ungated 72.6, random 76.8.
- **Limitations:** episode totals only; per-intro outcomes not persisted
  (S07 uses aggregate decomposition).

## E7. Round 2 promotion + audit (greedy vs A+C)

- **Source:** `research/round2_promotion_fresh_seeds/` (arm_*.json, diag_*.json),
  `research/ask_coverage_audit_package.zip` (AUDIT_REPORT.md).
- **Numbers:** greedy primary 0.4931 (71 MSMI / 5,486 intros / 72 eps);
  A+C original 0.3750; A+C floor/2 0.4028; paired C-A -0.0903
  CI [-0.257, +0.069] (includes 0). Ask cost: greedy 203/ep (28.2% of 720
  nominal), A+C ~423.
- **Audit findings (read-only, replay-validated 72/72):** greedy asks every
  resolvable member (share 1.000); eligible pool empties by day ~21; the
  residual ~67 declined-HARD members/ep are permanently non-introducible
  (kit.py:127); soft asks unlock 0 feasibility; probe counterfactual gains
  273 = A+C gains 273 (asks equal on identical states).
- **Limitations:** arms confound asks + matcher + floor (audit section F.3);
  probe is 1 seed with re-ask caveat.

## E8. OPR instrument validation (frozen; gate failed)

- **Source:** `research/round2_opr/` (`validation_results.json`, `report.md`).
- **Question:** can a logged reconstruction (D-stream) reproduce assigned pairs
  and stage labels exactly?
- **Results:** D-A exact 8,433/8,433 on greedy intros; D-B pass (O/E 1.086);
  **D-C fail** (stage-label concordance rho 0.778 < 0.8; exact p 0.0054); D2
  replay 144/144; G4 sign test 22/59 p=0.98 -> no live signal. Gate:
  OPR_NOT_VALIDATED; Phase 4 barred.
- **Relevance here:** the D-A exactness certifies n01's assigned-pair records;
  the D-C rho failure is evidence that stage labels are NOT fully recoverable
  from logged state alone — consistent with hidden outcome randomness (H1/H9).
  This EDA does NOT use OPR for policy deltas or counterfactual selection.

## E9. Stage-4 history/cold-start audit

- **Source:** `research/round2_stage4_history_coldstart_audit/` (report.md,
  x1_results.json).
- **Key numbers:** A+C floor excludes 80.1–94.2% of feasible candidates;
  83.5–94.1% of greedy's picks fall below the floor; probe zero-selection days
  148/360 all `all_below_floor`; cold-start soft coverage mean 1.96/7.
- **Relevance:** explains why gated allocation changed nothing (floor discards
  what asks unlocked) and why cold_start variant has thinner soft signal.

## E10. This EDA (research/round2_eda/)

- **Scripts:** eda_common, s02_population, s03_graph, s04_asks, s05_funnel,
  s06_scoring, s07_allocation, s08_simulator; all outputs in tables/ and plots/.
- **Re-constructions:** populations regenerated deterministically from
  kit.generate(seed, 200, ...) for S02 (world materialization only, no rollout);
  S06 re-fits the 44-feature HistGB on the frozen rows.csv with 4-fold group CV
  (diagnostic instrument; model discarded; no policy training).
- **Unit discipline:** world-level CIs where paired (S07); Wilson on funnel
  rates (S05); within-day concordance with world-level aggregation (S06).

## Data gaps recorded (not filled by new experiments)

1. Fine respond/decline split (one-yes-one-no vs two-no) not persisted in
   n01 intros (only `missing` count + y_mutual) — would need per-event streams.
2. No official per-day greedy selection logs (audit used a validated
   ask-only replay; matching days for greedy remain artifact-free).
3. Scale800 lacks second-intention labels (only label/label_mutual/label_date).
4. No per-intro score predictions persisted from the frozen scale800 model.
5. Hidden member attributes (bias, response_rate, second_bias) and pair
   shared shocks are not persisted per member/pair (by generator design).
6. Per-variant deadline-loss breakdown for n01 impossible: only 1 loss event
   total (91 -> 90).
7. E-arm (E1/E3) per-stage outcomes not persisted (mechanism JSONs only).
8. One-yes-one-no second-intention pattern exists in public feedback samples
   but is not aggregated in any research artifact.
