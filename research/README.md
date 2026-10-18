# Research - the team's local research program

This directory is the team's local research program for the Sequential Matching
Problem (Romeo & Juliet Ltd. x IIT Madras): the experiments, diagnostics and
audits the team ran while exploring the challenge, collected from the local
research clone. None of it was committed anywhere before 2026-10-19; it is
curated into this branch for the first time.

**Curation note.** The following are deliberately absent and rebuildable via
the kept scripts: `round2_stagewise_reward/data/` (training
snapshots/states/labels), `hard_constraint_clarification/tmp/` and
`hard_constraint_clarification/logs/`, and every file >= 5 MB - the six large
raw dumps: `states.jsonl` (85 MB), `out_scale800/rows.csv` (83 MB),
`pair_state.jsonl` (39 MB), `feasible_edges_val.jsonl` (23 MB),
`counterfactual_pairs.jsonl` (17 MB) and `out/rows.csv` (10 MB).

Each entry in the index below states: name -> question -> verdict -> key
numbers -> entry-point file. Claims are strictly from that folder's own
artifacts; where the artifacts record no verdict, the entry says so. The
appendix at the bottom preserves the imported Round 1 pipeline README.

## Index

### e3_rel_experiment
- **Question:** can a live (non-oracle) REL value-of-information ask phase
  and/or an analytic scorer beat the greedy control, after Stage A showed the
  static "+18.7%" estimate was an oracle upper bound?
- **Verdict:** INCONCLUSIVE - keep greedy (preregistered stopping rules).
- **Key numbers:** pooled MSMI/100 - C 0.3854; E1 0.4167 (+8.1%, CI
  [-0.031, +0.093]); E2 0.4062 (+5.4%, CI [-0.060, +0.101]); E3 0.3889
  (+0.9%, CI [-0.084, +0.091]); 576 episodes, 0 invalid.
- **Entry point:** `e3_rel_experiment/report.md`

### hard_constraint_clarification
- **Question:** does unlock-prioritizing the daily hard-constraint clarification
  bundles (recipient order only; identical ask volume; no model, no soft asks)
  improve MSMI vs greedy?
- **Verdict:** INCONCLUSIVE - point estimate not positive; only 2/6
  variant-level deltas >= 0; group direction 35 positive / 20 ties / 45
  negative of 100 paired groups.
- **Key numbers:** paired delta (unlock - greedy) -0.01750, CI
  [-0.06750, +0.03250]; 100 paired groups x 6 variants on fresh seeds.
- **Entry point:** `hard_constraint_clarification/REPORT.md`

### method_tournament
- **Question:** can any of 30 candidate allocation/matching methods beat the
  greedy control on mean paired MSMI/100 (screening -> confirmation -> 72-world
  Phase 3)?
- **Verdict:** negative for the candidates - "Greedy remains the best
  empirically supported policy among the evaluated candidates"; keep greedy.
- **Key numbers:** funnel 30 screened -> 4 retained -> 2 to Phase 3 -> 0
  credible; Phase 3: m03_reciprocal_min -0.0069, CI [-0.0940, +0.0801];
  m14_mutual_regret +0.0000.
- **Entry point:** `method_tournament/final_report.md`

### next_method_search
- **Question:** does any decision-time-legal feature separate greedy's
  introduction conversion strongly enough (the `methods.json` evidence gate) to
  justify a follow-on method search?
- **Verdict:** negative - Conclusion B (no supported signal); the N01 line
  stops here.
- **Key numbers:** 0 of 33 features pass the gate (0 diagnostic-only passes);
  126/126 sealed digests reproduced; 8,433/8,433 introductions replayed.
- **Entry point:** `next_method_search/n01_autopsy.md`

### next_strategy_research
- **Question:** where is the remaining value? Audit-only review of scoring
  concordance, idle ask budget and prior evidence (no episodes, no tuning).
- **Verdict:** see report - no verdict recorded (audit only; the "+18.7%"
  opportunity is explicitly untested live).
- **Key numbers:** Spearman 0.12 between the collector score and true pair
  value; +18.7% offline expected pair value (replica-validated); 517 free ask
  units per episode unused; current best MSMI/100 0.4931 (seeds 107-118).
- **Entry point:** `next_strategy_research/report.md`

### out
- **Question:** can the Round 1 data pipeline collect sound rollout data and
  predict MSMI on held-out worlds (440-rollout / 100-world run)?
- **Verdict:** PROCEED WITH CHANGES (pipeline validated; MSMI signal gate false
  at this scale).
- **Key numbers:** 440 rollouts (400 random / 40 greedy), 100 worlds; 32,044
  rows; integrity suite ALL PASS, 0 violations; MSMI val AUC 0.5218.
- **Entry point:** `out/report.txt`

### out_scale800
- **Question:** same pipeline question at the pre-registered 800-world scale
  (3,520 rollouts).
- **Verdict:** PROCEED (both pre-registered gates pass).
- **Key numbers:** 3,520 rollouts; 259,696 rows; MSMI val AUC 0.5937, CI
  [0.5667, 0.6208], AP lift 1.30x; all integrity checks pass.
- **Entry point:** `out_scale800/report.txt`

### round1_submission
- **Question:** not an experiment - the Round 1 written submission package.
- **Verdict:** not applicable (submission materials; no verdict recorded).
- **Key numbers:** research proposal + form answers, v1.0 dated 9 October 2026.
- **Entry point:** `round1_submission/research_proposal.md`

### round2
- **Question:** can a gated exact maximum-weight matching beat official greedy
  on 72 fresh paired worlds?
- **Verdict:** negative / CLOSED - primary-metric difference exactly 0.0000
  (0 wins / 72 ties / 0 losses); preregistered rules keep greedy.
- **Key numbers:** primary 0.3194 in every arm (greedy / gated / random);
  ungated ablation -0.0486, CI95 [-0.158, +0.061]; 360 episodes (seeds 301-312
  x 6 variants x 5 arms), 360/360 valid.
- **Entry point:** `round2/report.md`

### round2_baseline_integrity
- **Question:** was the F1-SCORE score-direction defect real, and what do the
  affected published deltas become when corrected?
- **Verdict:** defect confirmed real; affected claims corrected - "F2 +13"
  withdrawn as stated; corrected F2 vs count-maximizer G1m = +6, includes 0,
  not seed-robust.
- **Key numbers:** F2 94 vs G1m 88 = +6, CI [-0.2857, +0.9524]; frozen F1
  reproduction 81 vs greedy 90; 42-comparison evidence table; corrections
  [POST HOC].
- **Entry point:** `round2_baseline_integrity/report.md`

### round2_decision_ceiling
- **Question:** how much genuine decision opportunity exists on already-recorded
  states (hypotheses K1-K6)?
- **Verdict:** K4 supported (choices rarely change the MSMI outcome);
  K1/K2/K3/K5/K6 unresolved; read-only diagnostic, no recommendation.
- **Key numbers:** 173 MSMI-positive feasible pairs out of 15,304 (1.13%); the
  collector captured 90; two-proportion z -0.82, p 0.41; replay 126/126
  digests, 8,433/8,433 introductions.
- **Entry point:** `round2_decision_ceiling/report.md`

### round2_eda
- **Question:** where does the system lose MSMI successes, and which candidate
  explanations for the repeated null results are supported by existing
  artifacts?
- **Verdict:** H1-H5 supported; H6-H7 suggestive; H8-H9 unresolved (diagnosis
  only; no next experiment chosen).
- **Key numbers:** introduction funnel 90 of 8,433 reach MSMI (1.07%); 65.7% of
  greedy introductions are score-tied; no_asks arm delta MSMI -0.5556 via
  volume collapse.
- **Entry point:** `round2_eda/report.md`

### round2_fixed_cardinality
- **Question:** holding introduction cardinality exactly at greedy's own daily
  k_t, can legal observable information select better counterfactual MSMI
  pairs?
- **Verdict:** negative for every legal selector (F2/F3 intervals include 0);
  the earlier zero-discrimination result was a cardinality artifact and does
  not survive; local headroom is real (F5 oracle).
- **Key numbers:** F5-ORACLE 161 positives vs greedy 90 (+71, CI
  [2.1905, 4.5714], 17 positive / 0 negative seeds); F2-SOFT 94 (+4, CI
  [-0.3333, 0.7619]); F4-RANDOM 85.25; 82 headroom states.
- **Entry point:** `round2_fixed_cardinality/report.md`

### round2_goal_rule
- **Question:** can a simple relationship-goal selector exploit the discovered
  signal (exploratory local counterfactual diagnostic)?
- **Verdict:** exploratory only - G2 improves +2 vs greedy but not seed-robust
  (CI includes 0); G3 = G2 exactly; no deployment, no recommendation.
- **Key numbers:** G2 92 vs G0 greedy 90 (+2, CI [-0.2857, +0.5714]); G1m 88;
  G1f 81; G4 94; G5 oracle 161; 22/22 validation checks pass; Amendment 1
  (G1 sign discrepancy) disclosed.
- **Entry point:** `round2_goal_rule/report.md`

### round2_missed_oracle
- **Question:** where does the F2-to-oracle gap come from?
- **Verdict:** measured fact (audit only; no new policy): the gap is dominated
  by ranking failure, not matching.
- **Key numbers:** 67-point gap = 60 ranking (89.6%) + 7 matching conflict; the
  matching constraint costs a further 12 (161 + 12 = 173); median F2 rank of a
  missed positive = 3 (captured = 2); relationship_goal matches ~8x more likely
  to be MSMI.
- **Entry point:** `round2_missed_oracle/report.md`

### round2_opr
- **Question:** can the exact outcome model inside `kit.py` become a validated
  expected-MSMI estimator and find policy headroom over greedy?
- **Verdict:** OPR_NOT_VALIDATED - preregistered gates D-C and G4 failed;
  Phase 4 barred and not executed.
- **Key numbers:** estimator exact (22/22 unit tests; 250 randomized
  equivalence trials); gate D-C decile reliability Spearman rho 0.778 < 0.8
  (FAIL).
- **Entry point:** `round2_opr/report.md`

### round2_promotion_fresh_seeds
- **Question:** does the frozen floor/2 candidate generalize to 12 fresh seeds
  (promotion test)?
- **Verdict:** READY / PROMOTE (no-degradation grounds).
- **Key numbers:** A greedy 0.4931 > C floor/2 0.4028 > B floor 0.3750; paired
  delta C - B +0.0278 (CI spans 0 - inconclusive); C introductions exceed B in
  65/72 worlds = 90.28%; 216 official episodes.
- **Entry point:** `round2_promotion_fresh_seeds/report.md`

### round2_stage1_5
- **Question:** with Round 1 A+C frozen, instrument every ask and match decision
  on seed 101 x 6 variants (floor removal, candidate counts, zero-selected
  categories, paired ask counterfactuals) - measurement only, no tuning.
- **Verdict:** no verdict recorded (measurement-only probe).
- **Key numbers:** 4,205 candidates -> 611 above the frozen floor (85.47%
  removed) -> 434 assignments; 148 zero-selected-with-candidates days; total
  feasibility 273 = 273; run 1 and run 2 byte-identical.
- **Entry point:** `round2_stage1_5/README.md`

### round2_stage2_floor_ablation
- **Question:** is the frozen A+C score floor suppressing useful introduction
  volume (ablation to -inf; seeds 101-103)?
- **Verdict:** OUTCOME A - the floor suppressed useful volume (zero-selection
  with candidates: 411 all_below_floor days vs 0 without the floor).
- **Key numbers:** introductions 66.72 -> 77.83 (+16.7%); MSMI/100 0.2500 ->
  0.3333; selection 1,201 -> 1,401; 18 + 18 episodes per arm, 0 invalid.
- **Entry point:** `round2_stage2_floor_ablation/report.md`

### round2_stage3_intermediate_floor
- **Question:** does an intermediate floor (floor/2) beat the frozen floor and
  no-floor on fresh seeds 104-106?
- **Verdict:** favorable descriptive signal for floor/2; threshold exploration
  ends after this experiment (preregistered).
- **Key numbers:** MSMI/100 - floor/2 0.3611 vs frozen 0.2500 vs no-floor
  0.2778 (tiny counts: 9/13/10 events; no significance claimed); introductions
  +6.17, bootstrap CI [3.67, 8.33]; 54/54 episodes valid.
- **Entry point:** `round2_stage3_intermediate_floor/report.md`

### round2_stage4_history_coldstart_audit
- **Question:** do history features carry real lift (Q1), does the score floor
  penalize cold-start members (Q2), is the promotion comparison adequately
  powered (Q3), and does promotion proceed (Q4)?
- **Verdict:** history real-but-small for mutual (MSMI inconclusive); no
  cold-start penalty (13/16 settings); Q4 PROCEED.
- **Key numbers:** mutual AUC delta +0.0113, CI [+0.0063, +0.0161]; MSMI
  inconclusive; 13/16 settings show no cold-start penalty.
- **Entry point:** `round2_stage4_history_coldstart_audit/report.md`

### round2_stagewise_reward
- **Question:** can a stagewise-reward pipeline (three stage logistic models +
  exact-k solver) be built and deployed for a final paired evaluation?
- **Verdict:** STOP / REDESIGN - solver not deployable (V4 timing gate); final
  evaluation skipped, realised MSMIs never measured.
- **Key numbers:** 3,000 episodes / 226,531 introductions; solver max 17.199 s
  (gate < 3.0 s); 15 of 53 timed states hit the node-limit abort; seeds
  70001-70100 untouched.
- **Entry point:** `round2_stagewise_reward/report.md`

### round2_stagewise_reward_solver
- **Question:** does a blossom-based exact-k solver remove the computational
  blocker and produce a positive paired effect over greedy?
- **Verdict:** PROCEED WITH CHANGES (valid experiment, every gate passed;
  positive point estimate, 95% CI includes 0).
- **Key numbers:** +0.00417 MSMI/100 (candidate 0.3992 vs greedy 0.3950), 95%
  CI [-0.0483, +0.0583]; win/tie/loss 35/25/40 seed groups; 600 + 600 episodes,
  0 invalid; solver max 0.050 s; 11,200 correctness cases, 0 mismatches.
- **Entry point:** `round2_stagewise_reward_solver/report.md`

### round2_stagewise_signal
- **Question:** where is the counterfactual MSMI signal located across the
  outcome funnel and per-stage models?
- **Verdict:** diagnostic only - see report; relationship_goal robust across
  stages.
- **Key numbers:** funnel 15,304 opportunities -> 173 MSMI (1.13%); stage
  deltas exclude 0 from T2 on; relationship_goal ~8x relative gap at T6 (CI
  [+0.0098, +0.0275]); 42 channel x stage contrasts examined.
- **Entry point:** `round2_stagewise_signal/report.md`

---

## Appendix: imported Round 1 pipeline README

# research/ - training-data pipeline prototype (Round 1)

Validates ONLY the data pipeline for the Sequential Matching Problem kit:
can we collect rollout data, label it soundly, extract legal features, and train
a model that predicts on HELD-OUT WORLDS? It does **not** implement the A+C
policy, RL, hyperparameter tuning, or the 10,000-rollout production run.

## Files

| file | purpose |
|---|---|
| `labels.py` | MSMI + stage labels (mutual, date); maturity rule; `None` for immature |
| `features.py` | 44 decision-time pair features, symmetric, NaN for unknowns, leakage audits |
| `collect.py` | opportunity `scan()`, `RandomCollector` (bundled asks, eps/jitter matching), `collect_rows()` |
| `integrity.py` | audits: forbidden names, temporal soundness, snapshot, label stability, determinism |
| `analyze.py` | world-level splits, HistGB + constant baseline, metrics, leakage audit |
| `run_experiment.py` | parallel driver -> `out/rows.csv`, `out/worlds.csv`, `out/report.txt` |
| `test_pipeline.py` | TDD suite for all of the above |

## Run

```powershell
# from the repo root
python -m unittest research.test_pipeline -v   # 68 tests
python -m research.run_experiment --smoke      # end-to-end smoke
python -m research.run_experiment --random-rollouts 400 --greedy-rollouts 40 --workers 12
```

## Hard rules encoded (and audited) here

1. Only introduced pairs are labelled; un-introduced pairs are never stored as 0.
2. `label is None` (immature) is never coerced to 0; rollouts run 60 + 40 days so
   every label matures (maturity = max `observed_day` of the introduction's events).
3. Features at day `t` use only feedback with `observed_day <= t`, and mask fields
   whose `field_observed_day > t`.
4. No `truth`, `bias`, `second_bias`, `response_rate`, `exit_day`, `seed`, `variant`,
   raw events, ask logs, or identifiers may appear as feature names (audited).
5. Splits are by whole world `(world_seed, variant)` - never by row.
6. Structure-informed features (`weighted_soft_score`, `weighted_soft_covered`) reuse
   the published kit weights and are disclosed, not hidden.

## Outputs

- `out/rows.csv` - one row per introduced pair: meta, `label`/`label_mutual`/`label_date`, `feat_*`
- `out/worlds.csv` - one row per rollout: metrics, coverage, timing
- `out/report.txt` - sections A-F ending in PROCEED / PROCEED WITH CHANGES / STOP
- `out/report.json` - machine-readable version of the report

New files live only in this directory; `kit.py`, `evaluate.py`, `policy.py` are untouched.
