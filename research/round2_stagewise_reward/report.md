# Round 2 Stagewise Reward Experiment - Final Report and Single Decision (Task 11)

Status: COMPLETE. The experiment stopped before its final paired evaluation, per the
pre-registered stop conditions. This directory is sealed by `integrity.sha256` and gated by
`scripts/sr_verify.py` (all checks PASS; `results/final_integrity.json`).

Frozen specification: `research/round2_stagewise_reward/analysis_plan.md` (revision R1,
APPROVED), sha256 `80615fbcc3d09c41e052ce96ff88a57aff147c99a3a056b1a9e906fd7f80308b`
(verified against `analysis_plan.sha256`; also recorded inside `results/model_artifact.json`).

Verdict (one paragraph). The stagewise-reward pipeline was built and audited end to end:
randomised collection of 3,000 episodes (226,531 introductions), a 17-feature leakage audit
with zero ILLEGAL features, three frozen stage logistic models with all fit gates passed, an
exact-k solver that is provably correct (V1/V2/V3/V5 all clean, 0 disagreements) and whose
candidate adapter is protocol-correct (6/6 valid pilot episodes, exact greedy cardinality,
zero fallbacks). The one thing that failed is solver deployability: on the dense early-day
states that occur naturally in these worlds, the exact-k branch-and-bound reached 17.199 s
max (gate: < 3.0 s) and burned its 16,000,014-node abort on 15 of 53 timed states, while the
official harness allows only 10 s per policy invocation. Because the solver is not deployable,
the frozen analysis plan ordered a stop BEFORE the final evaluation (S.11; R1.1 rules 1-2), so
seeds 70001-70100 were never touched. Consequently the realised MSMIs and the paired effect
size + confidence interval were NEVER MEASURED and are not estimated anywhere in this report.
The single decision emitted below is STOP / REDESIGN.

## Decision: STOP / REDESIGN

Rule citations (analysis_plan.md, revision R1; rules applied in order, exactly one decision):

- Rule 1 - any integrity stop condition in S.11 fires at any point -> STOP / REDESIGN. The
  S.11 bullet "solver battery V1-V5 fails, or V4 dense timing gates fail (solver not
  deployable)" fired: V4 FAILED (`results/solver_validation.json`: `passed=false`,
  `v4_dense_timing.gates.max_seconds_lt_3=false`, `max_seconds=17.199167` against the 3.0 s
  gate, `zero_node_limit_failures=false`, `node_limit_failures=15` of 53 timed states).
- Rule 2 - solver not deployable (V4 gates fail) -> STOP / REDESIGN. Stated independently of
  rule 1 for exactly this case.
- Rules 3-5 - require a measured primary paired 95% CI from the final evaluation (S.10) and
  were therefore never reachable: Task 10 was SKIPPED, seeds 70001-70100 remain untouched
  (proved by check (d) in `results/final_integrity.json`), and no paired statistic exists.

The decision is pre-registered and cannot be revised by any finding recorded in this report.
No approximation substitute, no re-run with friendlier state selection, and no post-hoc density
cutoff were applied (controller ruling, `.superpowers/sdd/progress.md`, Task 7/Task 10 lines).

## Q1 - Which seed groups were generated and which were used?

Sources: `data/n_decision.json`, `data/coverage_stats.json`, `results/train_metrics.json`,
`results/model_artifact.json`, `results/solver_validation.json`, `run_log.txt`.

- Seed groups collected (each x 6 variants = 6 episodes): 1 plumbing pilot (40001) + 10
  quality-pilot groups (40002-40011) + 489 main-collection groups (40012-40500) = 500 groups
  = 3,000 episodes, of which 499 groups (40002-40500) form the training pool and 40001 is the
  excluded plumbing pilot (`data/coverage_stats.json` main batch: 2,934 episodes;
  `data/n_decision.json` quality pilot: 60 episodes; `results/pilot_report.json` P3:
  6 episodes).
- N was chosen by the pre-declared S.4 rule: N = 499, the largest value in [300, 499] whose
  projected wall time (4,774.8 s at W = 8 workers, measured 1.5948 s/episode in-pool) fit the
  4 h (14,400 s) cap, with projected stage-3 positives 2,395.2 >= the 150 gate; both gates
  recorded PASS (`data/n_decision.json`).
- Split, frozen before training: fit = seeds 40002-40400 (399 groups), validation =
  40401-40500 (100 groups), excluded from fitting = seed 40001 (the plumbing pilot)
  (`results/train_metrics.json` `split`; `results/model_artifact.json` `split`).
- Final-evaluation seed groups 70001-70100: NEVER TOUCHED. No file named `seed_70xxx.jsonl`
  exists under `data/`, and a full content scan of all 1,602 data files (357,177,979 bytes)
  found zero rows whose `seed`/`seed_group` starts with 70
  (`results/final_integrity.json` checks d2/d3). Also absent: `scripts/sr_eval_run.py`,
  `scripts/sr_eval_aggregate.py`, `results/paired_stats.json`,
  `results/cardinality_check.json`.

## Q2 - How many introductions were generated, and how many labelled rows exist?

Sources: `data/coverage_stats.json`, `data/n_decision.json`, `results/pilot_report.json`,
`results/train_metrics.json`, `data/labels/*.jsonl`.

- Main collection (489 groups): 221,416 introductions (`data/coverage_stats.json` total).
- Quality pilot (10 groups): 4,649 introductions (`data/n_decision.json`
  `quality_pilot_stats.intros`).
- Plumbing pilot (seed 40001): 466 introductions (`results/pilot_report.json` P3).
- Total labelled rows on disk: 226,531 (scan of `data/labels/*.jsonl`, 500 files; recorded in
  `results/final_integrity.json` check j). Of these, 226,065 are the fit+val rows used for
  training and evaluation diagnostics (180,262 fit + 45,803 val, `results/train_metrics.json`
  populations s1); the 466 pilot rows are excluded from fitting by construction.
- T-LAB-1 (no row for a never-introduced pair) passed: the label join is on
  (variant, intro_id) after the Task-3 collision fix, with 466/466 pilot rows reproduced from
  deterministic replay (`results/pilot_report.json` P3 `label_crosscheck`;
  `run_log.txt` sr_collect_test 5/5 PASS). Seed 40001 is excluded from fitting
  (`results/model_artifact.json` `split.excluded`).

## Q3 - How many mature labels exist per stage, and did maturity hold?

Sources: `results/train_metrics.json`, `results/model_artifact.json`,
`results/pilot_report.json`, `results/final_integrity.json`.

Fit split (positives / negatives), all gates passed (`results/train_metrics.json` `gates`):

- Stage 1 (mutual acceptance): 25,653 / 154,609 (n = 180,262 rows; EPV 1509).
- Stage 2 (timely first date, given S1): 20,006 / 5,647 (n = 25,653; EPV 1,176.8).
- Stage 3 (timely mutual second yes, given S1+S2): 1,870 / 18,136 (n = 20,006; EPV 110).

Validation split: s1 6,453 / 39,350; s2 5,028 / 1,425; s3 485 / 4,543
(`results/train_metrics.json` `populations`).

- UNKNOWN = 0 at every stage in every population (`excluded_unknown: 0` in all entries of
  `results/train_metrics.json`; pilot UNKNOWN counts all 0 in `results/pilot_report.json`).
- Maturity: the maximum `max_observed_day` over all 226,531 label rows is 93, below the
  60+40 = day-100 horizon (last relevant day 99; `results/final_integrity.json` check j). The
  plumbing pilot's own max was 73 (`results/pilot_report.json` P3
  `maturity_per_stage_max_observed_day`).
- T-MAT-1 (offline labels reproduce `kit.metrics()` exactly) and T-LAB-1 passed in the pilot
  and in the collection test suites (`results/pilot_report.json` P3; `run_log.txt`).

## Q4 - What coverage of the feasible-pair space was achieved?

Sources: `data/coverage_stats.json`, `data/feasible_edges_val.jsonl`,
`results/offline_ranking.json`.

- Main collection: 176,040 decision states, 415,708 feasible (state, edge) opportunities,
  221,416 introductions = 53.3% of opportunities taken as introduction rows; 96,467 DISTINCT
  pairs introduced = 23.2% of opportunities (`data/coverage_stats.json` total,
  `share_introduced` uses the distinct-pair definition stated in its `config`).
- Edges per state (main, all variants pooled): p25 = 0, p50 = 1, p75 = 3, p90 = 6, p95 = 9,
  max = 65 (`data/coverage_stats.json` total percentiles). Sparse variant is much thinner
  (p50 = 0, max = 14), cold_start maxes at 35, and delayed/development/drift/shift each max
  at 65.
- Per-member introduction counts: mean 1.70, p50 0, p90 5, max 39 (same file).
- Validation feasibility file: 87,204 feasible edges over 100 validation groups
  (`data/feasible_edges_val.jsonl`; independently counted as `n_edges_total` in
  `results/offline_ranking.json` and cross-checked `merged=87204 shard_sum=87204`).

## Q5 - What did the feature-integrity audit find?

Sources: `results/feature_audit.json`, `results/pilot_report.json`,
`results/offline_ranking.json`, `.superpowers/sdd/progress.md`.

- 17 predeclared features audited, 0 ILLEGAL, 0 POTENTIAL LEAKAGE: 15 classify
  LEGAL OBSERVABLE and 2 (degree_a, degree_b) STRUCTURE-INFORMED
  (`results/feature_audit.json`: `count: 17`, `illegal_count: 0`).
- T-FEA-1..4 passed in the unit suite: 4/4 PASS (`run_log.txt` Task 1 line), covering the
  scrub test, the late-field immutability test (frozen snapshot bytes unchanged after a SOFT
  field resolves on a later day) and the future-horizon rejection test. Snapshots are
  write-once and byte-reproducible (pilot P4 replay hashes identical,
  `results/pilot_report.json` P4).
- One ledger caveat (integrity disclosure): the controller ruled that the T-FEA-2 scrub test
  is vacuous by construction because `observe()` never contains truth/bias/second_bias/
  response_rate/exit_day/seed/variant; the intended guarantee (extractor reads only
  whitelisted state keys) rests on code review + the audit classification plus T-FEA-4
  (`.superpowers/sdd/progress.md`, Task 1 ruling).
- Dead features (reported, not fixed - no post-hoc feature edits are allowed):
  gender_fit_ab and gender_fit_ba are constant 1.0 across all 500 groups (fit_mean 1.0,
  fit_std 0.0; kit eligibility enforces mutual who_to_meet for every feasible pair), so 2 of
  17 features carry no information and the fitted weights are exactly 0
  (`results/offline_ranking.json` distribution_drift; `results/model_artifact.json` w[2]=w[3]=0;
  `.superpowers/sdd/progress.md` Task 6 observation).

## Q6 - What predictive signal did the frozen stage models show on validation?

Sources: `results/train_metrics.json` (metrics cited, not recomputed, per
`results/offline_ranking.json` `predictive_metrics_source`). Prediction quality only - these
are calibration/discrimination diagnostics, NOT evidence of decision value.

- Stage 1: val PR-AUC 0.1792 vs constant baseline 0.1409 (= prevalence 0.1409); ROC-AUC
  0.5701. This is modest but real out-of-sample signal. (Correction note: the intermediate
  `.superpowers/sdd/task-9-report.md` mis-cites 0.5792; the true value in
  `results/train_metrics.json` is roc_auc = 0.570115.)
- Stage 2: val PR-AUC 0.7778 vs baseline 0.7792; ROC-AUC 0.5040 - at/below the constant
  baseline.
- Stage 3: val PR-AUC 0.0899 vs baseline 0.0965; ROC-AUC 0.4698 - at/below the constant
  baseline, on a small validation population (n = 5,028; 485 positives).
- Combined P(MSMI) = p1 x p2 x p3 on validation: n = 5,028, PR-AUC 0.0873 vs baseline 0.0965,
  ROC-AUC 0.4656, mean predicted 0.0111 vs observed 0.0965 - roughly 9x systematic
  under-prediction (`results/train_metrics.json` `combined_pmsmi.val`).
- All three fit gates passed (s1/s2/s3 EPV 1509 / 1176.8 / 110), so the pre-registered
  weak-signal path (S.11: weak out-of-sample signal is "reported as a finding"; it does not
  by itself pick a decision rule) applied to interpretation, not to gating.

## Q7 - What did the offline ranking diagnostics show?

Sources: `results/offline_ranking.json` (validation groups 40401-40500 only, frozen artifact,
no policy runs). These are PREDICTION diagnostics on introduced pairs; they are not decision
value and they were never used to tune anything (the artifact was already frozen).

- P_hat over all 87,204 feasible validation edges: p50 0.0100, p95 0.0169, max 0.0498 -
  the scores are compressed into a very narrow band around the ~0.01 base rate.
- Within-state spread (max - min P_hat per state, 20,555 states with >= 1 edge): p50 0.0027;
  only 0.77% of states reach the plan's 0.02 discrimination threshold (99.2% below it); no
  state reaches 0.05.
- Out-of-distribution check: 0.0% of validation edges fall outside the fit min/max box, per
  feature and for all-features-combined (0 of 87,204). Therefore the tiny spread is NOT a
  coverage/OOD failure - it is the model's own behaviour on in-distribution inputs.
  Exact-vector representation is 7.82% (6,818 of 87,204 edges whose rounded 17-vector was
  seen as an introduced fit row), i.e. low exact replication but zero extrapolation.
- Train-vs-validation drift: maximum mean drift 0.0253 fit-SD (prev_intros_mean); every
  feature well inside 0.03 SD - no distribution shift.
- Within-state pairwise concordance (introduced pairs ONLY; selection-bias caveated in the
  file's own `caveats` and `selection_bias_statement`; no counterfactual labels anywhere):
  primary MSMI micro 0.5485 / macro 0.5334 over 1,155 comparable pairs across 382 states -
  mildly above chance (0.5). Stage chain: s1 micro 0.5805 / macro 0.5700 over 13,906 pairs,
  s2 micro 0.5154 (423 pairs), s3 micro 0.4862 (109 pairs). The s1 figure is consistent with
  the Task-6 val ROC-AUC 0.5701; s2/s3 are consistent with chance.
- Honest reading: the frozen model ranks introduced pairs slightly better than chance on s1
  and MSMI, but the ranking signal is too weak to expect a large sequential effect, and
  nothing here measures realised MSMI under the candidate policy.

## Q8 - What were the realised MSMIs (candidate vs greedy)?

NOT MEASURED. The pre-registered final paired evaluation (S.10: seeds 70001-70100, 100 seed
groups x 6 variants x 2 arms) was SKIPPED, so no candidate or greedy arm was ever run on the
final-evaluation seeds. This is required by S.11 ("STOP before scaling or before the final
evaluation if ANY of: ... solver battery V1-V5 fails, or V4 dense timing gates fail") and was
ruled explicitly (`.superpowers/sdd/progress.md`, Task 7 controller ruling; Task 10 line:
"SKIPPED per pre-registered stop ... seeds 70001-70100 NEVER touched"). No value is estimated,
extrapolated or proxied here. For completeness and without any decision interpretation, the
6 pilot episodes under the candidate adapter (plumbing seed 40001 only, small states) are
recorded in `results/pilot_candidate_official.json`; the pilot is explicitly excluded from
evidence per S.3.

## Q9 - What was the paired effect size and 95% confidence interval?

NOT MEASURED, for the same pre-registered reason as Q8. No paired difference, no bootstrap CI
(B=2000, default_rng(4242) as frozen in S.10), and no win/tie/loss counts exist, because the
evaluation that would have produced `results/paired_stats.json` never ran. Fabricating or
bounding an effect size from offline diagnostics would violate the plan's prediction-vs-
decision separation (S.7/S.9/S.11) and is therefore not done.

## Q10 - What failed, and what uncertainty remains?

Failures and process incidents, with sources:

1. V4 solver deployability - the decisive blocker (`results/solver_validation.json`,
   `run_log.txt` Task 7 line): 53 states timed (global top-50 by edge count across all 500
   groups, plus 3 zero-edge day-0 states); seconds p50 1.579 / p95 9.121 / max 17.199 against
   the pre-registered max < 3.0 s gate; 15 of 53 states burned the abort at 16,000,014 nodes
   (fc pass-1 limit 8,000,000, pass-2 cumulative limit 16,000,000); nodes p50 6,464,256,
   p95 16,000,014. The slowest single state was seed 40289 / drift / day 8 / 56 edges / k = 13
   at 17.199 s; the densest day-0 state was seed 40137 with 65 edges / k = 17 at ~5.94 s.
   Day-0 states number 3,000 (500 groups x 6 variants), mean 13.37 edges, max 65, and 168 of
   them have >= 30 edges - a material tail. The official harness allows only 10 s per policy
   invocation (analysis_plan.md R2), so max 17.199 s > 10 s means a fresh 100-group evaluation
   would very plausibly have produced invalid episodes and/or silent greedy fallbacks. A
   supplemental val-only top-50 timing (max 0.888 s) is recorded as diagnostic ONLY and is
   explicitly not part of the gate. Correctness was never in doubt: V1 2,000 graphs / 9,421
   checks / 0 disagreements, V2 determinism + lex-min 0 failures, V3 360 pilot live states /
   0 violations / max 21.6 ms, V5 348 states / 0 disagreements, and fc's own suite re-run
   byte-faithfully (PASSED_RERUN, prior artifact sha256 unchanged). The blocker is exclusively
   dense-state latency, not correctness. Plan-deviation disclosure: analysis_plan.md S.8
   specified "worst states by edge count from pilot worlds", but the battery timed the global
   top-50 by edge count across all 500 seed groups - a strengthening/conservative deviation
   from the plan (a wider, harsher gate), disclosed as such; the STOP decision is unaffected.
2. Task-5 compute-budget overshoot (`run_log.txt`, `.superpowers/sdd/progress.md` Task 5):
   the 10-group quality pilot measured 1.5948 s/episode in-pool and projected 4,774.8 s for
   N = 499, but the ACTUAL main collection took 31,523 s = 8.76 h against the pre-registered
   4 h cap - 10-group throughput did not predict sustained 8-worker contention. The data are
   complete and integrity is unaffected (2,934 episodes, zero episode failures); N = 499 and
   the frozen plan were honoured; the miss is reported, not repeated.
3. Task-9 concordance sign bug, found by review and corrected (`run_log.txt` three
   sr_offline_rank lines; `.superpowers/sdd/progress.md` Task 9): the first two runs reported
   MSMI concordance micro 0.4515 / macro 0.4666 (sign inverted: `(si-sj)*(yj-yi)`); after the
   one-token fix to `(si-sj)*(yi-yj)` and a bit-exact re-verification the true values are
   micro 0.5485 / macro 0.5334 over the same 1,155 pairs. Only the concordance sections
   changed; the discrimination/OOD sections (unchanged by the bug) still show 99.2% of states
   below the 0.02 threshold.
4. Task-3 intro_id cross-variant collision, found and fixed (`.superpowers/sdd/progress.md`
   Task 3 ruling): kit's intro_id = sha256(a|b|day) omits the variant, and member ids repeat
   across 4 of 6 variants per seed, so ids collided across variants within a group (~34% of
   rows on seed 90210) and an intro_id-only join would silently mis-pair labels. Fix: the
   label row carries `variant` and the join key is (variant, intro_id), with the simulator's
   canonical id kept verbatim for auditability.
5. Task-5 P6 KeyError, honest fail-then-fix (`run_log.txt`): the first pilot run failed at
   P6 with `KeyError: 'inference_seconds'`; fixed and re-run to P1-P6 PASS. Both the FAIL and
   the PASS lines are retained.
6. Scientific weakness (Q6/Q7): s2, s3 and the combined P(MSMI) are at or below the constant
   baseline on validation, combined predictions under-state observed MSMI by ~9x, and the
   within-state score spread is tiny (99.2% of states below 0.02). The only real signal is
   s1 (ROC 0.5701, PR-AUC 0.1792 vs 0.1409).
7. Small validation populations for the rare stages: val s3 has only 5,028 rows (485
   positives) and val s2 only 6,453 rows, so those stage metrics are noisy; the s3 fit gate
   passed with EPV 110 but the val estimates carry wide implicit uncertainty.
8. Residual uncertainty never resolved, because the experiment stopped: whether the ~9x
   combined under-prediction is pure calibration error or hides real pairwise discrimination;
   whether a deployable selector would improve realised MSMI at all. Neither question can be
   answered from the frozen artifacts alone.

## What would unblock a redesign

These are redesign OPTIONS for a future experiment. They are explicitly NOT authorized by
this experiment, were NOT tried here, and each requires a NEW pre-registration (a new frozen
analysis plan with its own hash) before any code runs:

- A faster exact-k path for dense early-day states, evaluated against the same V4 protocol but
  with a PRE-REGISTERED density/time threshold declared in advance (e.g. time-boxed solve with
  a documented, pre-registered truncation rule), so the gate itself is defined before any
  timing is seen.
- A cardinality-preserving approximate selector (for example a Lagrangian/greedy-with-repair
  construction that always returns exactly k disjoint feasible edges), validated head-to-head
  against the exact solver on the states where the exact solver completes, plus a pre-registered
  objective-gap bound on the states where it does not. The present V1-V5 battery gives the
  exactness baseline such a comparison would need.
- Restricting the candidate's decision states to those below a MEASURED edge-count threshold
  (the day-0 histogram in `results/solver_validation.json` makes such a threshold concrete),
  with the restricted policy evaluated as its own arm and the restriction reported as part of
  the policy definition.
- Independently of deployability: the ~9x combined under-prediction and the dead
  gender_fit features argue for revisiting the model family/calibration in the redesign -
  but only under a new plan, never by editing the frozen artifact of this experiment.

## Integrity appendix

- Final gate: `python -B scripts/sr_verify.py` -> ALL CHECKS PASS (17/17 in the sealed state),
  written to `results/final_integrity.json`; non-zero exit on any failure.
- Protected files and prior research seals: `bi_verify.py` re-run by sr_verify check (a) ->
  exit 0: own seal 25 files, 7 prior research seals / 207 entries, 9 protected files
  (policy.py, kit.py, evaluate.py, Dockerfile, requirements.txt and cohort) unchanged, frozen
  baseline plan intact, bi4 25/25 checks, bi5 36/36 checks. No protected file (kit.py,
  policy.py, evaluate.py, Dockerfile, requirements.txt) and no prior-research file was
  created, modified or deleted by this experiment. The SDD process area `.superpowers/sdd/`
  (controller ledger, briefs, review packages) sits OUTSIDE this seal and outside
  `integrity.sha256`; it is referenced here for provenance only.
- SDD ledger (`.superpowers/sdd/progress.md`) sha256 at seal time:
  `580807ad0015a9e88a91dabac23fa7177d0b986c816d14c358fd58f6caf1d75d` - process-area provenance
  outside `integrity.sha256`, made tamper-evident by being quoted inside this sealed report.
- Deliverable count: sr_verify check (e) reports "26/26 plan-S.12 deliverables present" over its
  explicit 26-file list, which is NOT verbatim the plan section 12 list. Named substitutions and
  additions: `scripts/sr_pilot.py` (Task-5 orchestrator) and `scripts/sr_candidate_test.py`
  (Task-8 test) are counted though section 12 does not name them; `results/train_metrics.json`,
  `results/model_artifact.sha256` and `data/n_decision.json` are counted beyond section 12's
  names; `results/pilot_report.json` and `results/pilot_candidate_official.json` are read under
  section 12's `pilot_*.json` glob; and the four section-12 names `scripts/sr_eval_run.py`,
  `scripts/sr_eval_aggregate.py`, `results/evaluation_*.json`, `results/paired_stats.json` are
  replaced in the count by those extras and asserted ABSENT by check (d) instead, per the
  pre-registered stop - so the count means "present against the implemented-file list", not
  "every file name printed in section 12".
- Frozen artifacts: `analysis_plan.md` == its declared sha256;
  `results/model_artifact.json` == its declared sha256 == the Task-6 recorded hash
  `7f1ddfe00211e260...`; stage statuses s1/s2/s3 all OK; `results/train_metrics.json` fit
  gates all passed.
- Seed hygiene: pilot {40001}, fit {40002..40400}, val {40401..40500} and final-eval
  {70001..70100} are pairwise disjoint, and the fit/val/excluded lists inside the frozen
  artifacts match the plan exactly. Zero 70xxx data files or rows exist (full scan of
  `data/`, 357 MB).
- Candidate status: `policy_candidate.py` exists as a plan-S.12 deliverable and passed its
  pilot smoke (6/6 valid episodes, 360/360 exact cardinality, 0 solver fallbacks, all 6
  digests differing from greedy), but it was NEVER promoted: `policy.py` is untouched, the
  default policy remains greedy, and parity with the official greedy path is 6/6 digests
  (`results/pilot_report.json` P2). No evaluation output exists for the candidate.
- Process: no git-mutating command was ever run (controller ruling RUL-1); no file outside
  this experiment directory was written except the SDD process area `.superpowers/sdd/`
  (disclosed above); no protected or prior-research file was created, modified or deleted;
  the exact-k solver is imported read-only from
  `research/round2_fixed_cardinality/scripts/fc_matching.py` (sha256
  59c852debde55fdde... recorded in `results/solver_validation.json`).
- Seal: `integrity.sha256` covers every file of `research/round2_stagewise_reward/` except
  itself and `__pycache__`, sorted, one "<hash>  <relpath>" per line; sr_verify check (i)
  recomputes every entry.

Stop for review. Exactly one decision was emitted (STOP / REDESIGN); there is nothing to
promote, no follow-up rollout authorized, and no further claims beyond the evidence cited
above.
