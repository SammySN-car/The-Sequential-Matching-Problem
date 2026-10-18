# Round 2 Stagewise Reward - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and run the approved stagewise-reward experiment end to end: randomised data
collection, leakage-audited stagewise logistic models, verified exact-k solver, and one frozen
paired evaluation of a candidate policy against official greedy.

**Architecture:** Pure-Python research pipeline under research/round2_stagewise_reward/ that
drives the public kit.Simulator in-process for data generation, and the official evaluate.py
subprocess protocol for the paired final evaluation via a standalone policy adapter. Policy-side
files are stdlib-only; research scripts may use the already-installed numpy 2.3.2.

**Tech Stack:** Python >= 3.10, stdlib (+ numpy for research scripts only), PowerShell host.

**Spec:** research/round2_stagewise_reward/analysis_plan.md (APPROVED, revision R1,
sha256 80615fbcc3d09c41e052ce96ff88a57aff147c99a3a056b1a9e906fd7f80308b). The plan argues
from that spec; executors read both.

## Global Constraints

- All new files under research/round2_stagewise_reward/ only. NEVER modify: policy.py, kit.py,
  evaluate.py, Dockerfile, requirements.txt, or any pre-existing research directory.
- NO git-mutating commands (add/commit/checkout/reset/restore). The template's "commit" steps
  are replaced by: append the exact command + key output line to run_log.txt (house convention).
- Policy files (sr_policy_core.py, policy_parity.py, policy_candidate.py): standard library
  ONLY. Research scripts: stdlib + numpy (already installed; install nothing, ever).
- Test convention: standalone python scripts printing [PASS]/[FAIL] lines and writing
  results/<name>.json (no pytest in requirements). Unit-test worlds use seeds 90210/90211
  (repo fixture convention); they are never training or evaluation seeds.
- Seed registry (plan S.13): plumbing pilot 40001; quality+training 40002-40500; final eval
  70001-70100. No overlap between purposes; asserted in Task 11.
- PowerShell text handling: write with @'...'@ | Out-File -Encoding utf8 (BOM); Python reads
  utf-8-sig where needed; set $env:PYTHONIOENCODING='utf-8' before every python run.
- Parallelism: W = min(8, os.cpu_count()) stdlib multiprocessing workers; W recorded in
  run_log.txt before each multi-process run (plan R1.2).
- Official protocol facts: 60 ask/match days + 40 follow-up; ask budget 12/day
  (constraints=3, soft=1); official metric = 100 x msmi / members arrived by day 59,
  equal-weighted across the 6 variants by evaluate.summarise().
- Reused solver: research/round2_fixed_cardinality/scripts/fc_matching.py `solve_exact_k
  (edges: Sequence[tuple[str,str]], weights: Sequence[float], k: int)
  -> (matching: list[tuple[str,str]] | None, value: float, nodes: int, failed: bool)` -
  import by sys.path insert, never modify.

## Review Focus

Failure modes most likely to bite, each pinned to the task that owns it:

1. Feature leakage or snapshot mutation (a field observed after decision day creeping into a
   frozen snapshot) -> Task 1 tests T-FEA-2 (scrub) and T-FEA-3 (late-field immutability).
2. Label/maturity off-by-one at the inclusive <=30 / <=3 day boundaries (kit.py L197)
   -> Task 2 test T-MAT-1 compares offline labels against sim.metrics() counts exactly.
3. Parity digest mismatch from pair-order differences (action_sha256 covers order)
   -> Task 4 test compares evaluate.py action_sha256 for all 6 pilot episodes.
4. Solver cardinality or feasibility defects on live states (not recorded states)
   -> Task 7 V3 (every pilot state: |M|==k, disjoint, feasible, not-past) and Task 8 V6.
5. Seed leakage between fit / validation / final-eval partitions
   -> Task 11 sr_verify.py asserts pairwise-disjoint seed lists and artifact hashes.

---

### Task 1: Feature extractor and integrity audit

**Files:**
- Create: research/round2_stagewise_reward/scripts/sr_features.py
- Test: research/round2_stagewise_reward/scripts/sr_features_test.py
- Output: research/round2_stagewise_reward/results/feature_audit.json

**Interfaces (Consumes: kit.py observe() dicts. Produces - used by Tasks 3, 6, 8, 9):**
- `build_feasible_edges(state: dict) -> tuple[list[tuple[str, str]], dict[str, int]]` -
  canonical (sorted-id) pairs among available members with eligibility=='feasible' and not in
  past (mirrors kit.baseline_match L213-216 exactly); plus per-member feasible degree
  (default 0 for unavailable members).
- `extract_pair_features(state: dict, degree: dict[str, int], a: str, b: str) -> list[float]`
  - the 17 features in the plan S.6 table order. Only reads state['members'/'day'/
  'introductions'/'feedback']; asserts every feedback observed_day <= state['day'].
- `feature_audit_rows() -> list[dict]` - {name, source, legality, class} for the machine-readable
  audit; all 17 must classify LEGAL OBSERVABLE or STRUCTURE-INFORMED.

- [ ] Step 1: Write sr_features_test.py with four test functions:
  test_audit_classification (all 17 rows legal; no duplicates; length 17),
  test_scrub_invariance (deep-copy an observe() dict, delete keys truth/bias/second_bias/
  response_rate/exit_day/seed/variant wherever present, assert extract output bit-identical),
  test_late_field_immutable (world=kit.generate(90210,200,'test','development'); day-0 snapshot
  pair; resolve_asks to reveal a SOFT field on day 1; assert day-0 stored values unchanged and
  fresh extraction at day 1 differs), test_future_feedback_rejected (state whose feedback has
  observed_day>day raises AssertionError).
- [ ] Step 2: Run `python scripts/sr_features_test.py` from the experiment dir -> expect FAIL
  (ImportError).
- [ ] Step 3: Implement sr_features.py per the S.6 table (constants SOFT/HARD imported from kit;
  no other kit internals read).
- [ ] Step 4: Run test -> expect 4x [PASS], results/feature_audit.json written, zero ILLEGAL.
- [ ] Step 5: Append command + PASS count to run_log.txt.

### Task 2: Offline labelling and maturity

**Files:**
- Create: scripts/sr_label.py; Test: scripts/sr_label_test.py

**Interfaces (Consumes: sim.introductions + sim.events after 60+40. Produces - Task 3):**
- `stage_labels(intro: dict, events: list[dict], horizon_day: int = 100) -> dict` with keys
  's1','s2','s3','msmi' each in {0, 1, 'UNKNOWN'}; constants S1_WINDOW=7, S2_WINDOW=33,
  S3_WINDOW=35 (derived bounds, plan S.2) asserted as comments citing kit.py lines.
- `maturity_report(intros: list[dict], events: list[dict]) -> dict` - max relevant
  observed_day per stage; raises if any > horizon_day-1.

- [ ] Step 1: sr_label_test.py: test_matches_metrics (rollout seed 90210 across all 6 variants,
  60 days baseline then 40 empty advances; for each intro compare stage_labels against
  independent recomputation of kit.metrics() logic; assert totals mutual/dates/msmi equal),
  test_unknown_excluded (synthetic intro dict with no events -> all UNKNOWN),
  test_boundaries (date exactly assigned+30 -> stage2=1; assigned+31 -> 0; second yes at
  date+3 -> 1; date+4 -> 0).
- [ ] Step 2: Run -> FAIL (missing module).
- [ ] Step 3: Implement sr_label.py from the exact event semantics (kit L156-197).
- [ ] Step 4: Run -> PASS x3; append run_log.txt.

### Task 3: Randomised collection pipeline

**Files:**
- Create: scripts/sr_collect.py; Test: scripts/sr_collect_test.py
- Outputs: data/snapshots/seed_<g>.jsonl, data/labels/seed_<g>.jsonl, data/states.jsonl,
  data/feasible_edges_val.jsonl, data/coverage_stats.json

**Interfaces (Consumes: kit.generate/Simulator, Task 1, Task 2. Produces: training rows for
Task 6; val-edge file for Task 9):**
- `collect_group(seed: int, variants: tuple[str,...], val_from: int | None) -> dict` stats
  {intros, rows, s1_pos, s2_pos, s3_pos, msmi_pos, states, feasible_edges_total, seconds}.
- Collection policy: asks = kit.baseline_asks(state); edges = build_feasible_edges(state);
  priority per edge from random.Random(int.from_bytes(sha256(f'{seed}|{variant}|{day}|collect')
  .digest()[:16],'big')).random() assigned in canonical edge order; take edges descending
  priority, skip conflicts (randomised maximal matching, plan S.4).
- Snapshot row (one per introduction): {intro_id, seed_group, variant, day, members:[a,b],
  features:[17 floats], degree_a, degree_b, n_edges, k_greedy, k_chosen, priority_a, priority_b}.
  Label row joined only after the full 60+40 episode: {intro_id, s1, s2, s3, msmi,
  max_observed_day}.
- Val groups (seed >= val_from): also append every feasible edge's 17-feature vector per match
  state to data/feasible_edges_val.jsonl (plan R1.3).
- CLI: `python scripts/sr_collect.py --seeds 40012-40451 --val-from 40362 --workers W`.

- [ ] Step 1: sr_collect_test.py: test_rows_equal_intros (T-LAB-1 invariant on seed 90210 x all
  variants), test_deterministic_replay (collect twice -> identical sha256 of snapshot+label
  files), test_no_infeasible_pairs (Simulator.advance raises on any invalid pair - run with
  raise-propagation; zero episode failures), test_priorities_recorded.
- [ ] Step 2: Run -> FAIL.
- [ ] Step 3: Implement sr_collect.py (multiprocessing.Pool over seed groups, W workers;
  deterministic file writes sorted by (seed, variant, day, pair)).
- [ ] Step 4: Run -> PASS x4.
- [ ] Step 5: Append run_log.txt.

### Task 4: Adapter core + parity policy

**Files:**
- Create: sr_policy_core.py, policy_parity.py (experiment root); Test: scripts/sr_parity_test.py

**Interfaces (Produces: shared adapter for Task 8; parity evidence for Tasks 5/10):**
- `run_adapter(ask_fn: Callable[[dict], list], match_fn: Callable[[dict], tuple[list, dict]],
  instrumentation_path: str | None) -> None` - reads one JSON request from stdin
  ({schema_version, phase, state, memory}), dispatches, writes {asks|pairs, memory} to stdout;
  memory pass-through (kept <= 1 MiB by not accumulating); if instrumentation_path set, match
  phase appends one JSON line {day, n_available, n_edges, k_greedy, k_chosen, solver_nodes,
  solver_fallback, seconds} from match_fn's meta dict.
- policy_parity.py: argparse accepts --baseline (values greedy|no_asks|random; greedy only
  supported, others error); ask_fn = kit.baseline_asks, match_fn = (kit.baseline_match(state),
  meta) with k_greedy = k_chosen = len(pairs).

- [ ] Step 1: sr_parity_test.py: run `evaluate.py --seeds 40001 --variants all` (default
  policy.py) and `evaluate.py --policy <abs path policy_parity.py> --seeds 40001 --variants
  all`, assert action_sha256 equal for all 6 episodes and metrics fields equal.
- [ ] Step 2: Run -> FAIL.
- [ ] Step 3: Implement sr_policy_core.py + policy_parity.py (stdlib only).
- [ ] Step 4: Run -> PASS; append run_log.txt.

### Task 5: Plumbing pilot orchestration (plan S.3)

**Files:**
- Create: scripts/sr_pilot.py; Output: results/pilot_report.json, results/pilot_greedy_official.json

**Interfaces:** orchestrates P1-P6: P1 official greedy on 40001 (subprocess evaluate.py), P2
parity (Task 4), P3 collect_group(40001, all variants), P4 replay + hash compare, P6 timing +
tracemalloc + per-call inference times. Emits pass/fail per step + measured seconds/episode
(in-process vs subprocess) + stage positive counts.

- [ ] Step 1: Write sr_pilot.py (no separate unit test - it IS the test; asserts inside,
  non-zero exit on any failure).
- [ ] Step 2: Run it -> pilot_report.json with all steps PASS; inspect: T-MAT-1 ok, replay
  hashes equal, 6/6 parity digests equal, subprocess seconds/episode recorded.
- [ ] Step 3: Data-quality pilot: collect seeds 40002-40011; compute projected stage-3 positives
  and runtime at candidate N values; choose N per plan S.4 rule (>=300, <=499, <=4h at W
  workers) and write data/n_decision.json {N, val_from, projection, W, rationale}.
- [ ] Step 4: Append run_log.txt with N decision.

### Task 6: Stage-model training and freeze

**Files:**
- Create: scripts/sr_train.py; Test: scripts/sr_train_test.py
- Output: results/model_artifact.json + .sha256, results/train_metrics.json

**Interfaces (Consumes: data/labels + snapshots. Produces: frozen artifact for Tasks 8/9):**
- `fit_stage(X: list[list[float]], y: list[int], lam: float = 1.0) -> dict` {w, bias, mu, sigma}
  - numpy IRLS, standardisation from X only, deterministic.
- `predict_stage(stage: dict, x: list[float]) -> float`; combined
  P_MSMI = p1 * p2 * p3 (missing stage probability -> row excluded from that metric).
- Split: sorted collected seeds; fit = first 80%, val = last 20% (whole groups; assertion
  no seed in both). Fit gates per plan S.7 (>=100 pos, >=100 neg, EPV>=5) - failed stage ->
  artifact records stage as FAILED and exits non-zero for the runner to stop.
- Metrics (fit + val separately): PR-AUC, ROC-AUC, log loss, 10-bin calibration, prevalence,
  constant-prevalence baseline; plus combined P_MSMI vs observed MSMI reliability on val.

- [ ] Step 1: sr_train_test.py: test_artifact_deterministic (fit twice on fixture data ->
  identical artifact bytes), test_split_disjoint, test_gate_enforced (fixture with 3 positives
  -> stage FAILED, non-zero exit).
- [ ] Step 2: Run -> FAIL.
- [ ] Step 3: Implement sr_train.py.
- [ ] Step 4: Run tests PASS; then run the real training on collected data -> artifact frozen,
  sha256 logged; append run_log.txt. DO NOT proceed if a stage gate fails (report instead).

### Task 7: Solver verification battery (plan S.8 V1-V5)

**Files:**
- Create: scripts/sr_solver_test.py; Output: results/solver_validation.json

- [ ] Step 1: Implement battery: V1 2,000 random graphs (rng 4242) vs brute_force_exact_k;
  V2 determinism (solve twice, identical); V3 every match state of the pilot collection
  (replayed in-process): |M|==k_greedy, disjoint, kit.eligibility=='feasible', not-past;
  V4 dense timing on top-50 states by edge count incl day-0: p50/p95/max seconds + nodes,
  gates max<3.0s and zero node-limit failures; V5 <=14-edge states vs brute force.
- [ ] Step 2: Run -> solver_validation.json with passed:true; append run_log.txt. Failure ->
  STOP (report blocker, no substitute).

### Task 8: Candidate policy + live smoke (plan S.8 V6)

**Files:**
- Create: policy_candidate.py (experiment root); Test: scripts/sr_candidate_test.py

**Interfaces (Consumes: Task 4 core, Task 6 artifact, Task 7 solver. Produces: arm-C for Task 10):**
- policy_candidate.py (stdlib only): loads results/model_artifact.json at import (path relative
  to __file__); ask_fn = kit.baseline_asks; match_fn:
  1. edges, degree = build_feasible_edges(state) (Task 1);
  2. k = len(kit.baseline_match(state));
  3. P_hat per edge via extract_pair_features + frozen stage weights (pure-python dot products);
  4. matching, value, nodes, failed = solve_exact_k(edges, P_hat, k);
  5. if failed: fall back to kit.baseline_match(state), solver_fallback=1 (assert never in
     tests/smoke); meta = {day, n_available, n_edges, k_greedy:k, k_chosen:len(matching),
     solver_nodes, solver_fallback, seconds}.
  Instrumentation via SR_INSTRUMENTATION_DIR env var (absent -> no writes, plan R1.5).

- [ ] Step 1: sr_candidate_test.py: test_exact_cardinality (6 pilot episodes via evaluate.py
  with SR_INSTRUMENTATION_DIR set: every match state k_chosen==k_greedy, fallback==0, episodes
  valid), test_deterministic (same episode twice -> identical action_sha256), test_inference_budget
  (max per-call seconds < 2.0).
- [ ] Step 2: Run -> FAIL.
- [ ] Step 3: Implement policy_candidate.py.
- [ ] Step 4: Run -> PASS (this IS plan gate V6); append run_log.txt.

### Task 9: Offline ranking report (plan S.9)

**Files:**
- Create: scripts/sr_offline_rank.py; Output: results/offline_ranking.json

- [ ] Step 1: Implement: read data/feasible_edges_val.jsonl + frozen artifact; compute per-stage
  and final metrics on val rows (PR-AUC/ROC-AUC/logloss/calibration/prevalence/constant
  baseline); train-vs-val distribution drift + OOD share (per-feature and all-features outside
  fit min/max box); P_hat distributions over ALL feasible val edges; discrimination frequency
  (max-min >= 0.02); share of feasible val edges never represented by an introduced fit row;
  within-state ranking on val states with >=2 introduced pairs (predicted vs realised order,
  selection bias stated in the JSON 'caveats' field).
- [ ] Step 2: Run -> offline_ranking.json; verify caveats present and no counterfactual labels
  anywhere; append run_log.txt. (This report is produced BEFORE the final evaluation, per
  plan S.14.)

### Task 10: Paired final evaluation (plan S.10 + R1.4)

**Files:**
- Create: scripts/sr_eval_run.py, scripts/sr_eval_aggregate.py
- Outputs: results/evaluation_g_<chunk>.json, results/evaluation_c_<chunk>.json,
  results/instrumentation/*.jsonl, results/paired_stats.json

- [ ] Step 1: sr_eval_run.py: chunks of 10 seeds from 70001-70100; arm G = default policy.py,
  arm C = policy_candidate.py with SR_INSTRUMENTATION_DIR per chunk; W parallel evaluate.py
  subprocesses (stdlib multiprocessing); R1.4 retry-once on valid:false rows; every command +
  W recorded in run_log.txt BEFORE launching; N and seed list taken from data/n_decision.json
  minus the frozen eval list (assert disjoint from fit/val lists).
- [ ] Step 2: sr_eval_aggregate.py: seed-group unit; score_g = mean over 6 variants of
  msmi_per_100; diff_g; mean + 95% percentile bootstrap CI (B=2000, np.random.default_rng(4242),
  linear percentiles); W/T/L (tie: |diff| <= 1e-12); per-variant paired means+CIs; counts
  (arrived/intros/msmi/mutual/dates per arm); runtime, retries, dropped groups;
  results/paired_stats.json. Also aggregate instrumentation -> results/cardinality_check.json
  (state count, mismatches, fallbacks, timing percentiles) - zero mismatches and zero fallbacks
  required before the decision (plan R1.1 rules 1-2).
- [ ] Step 3: Run both; sanity-check row counts (120 episodes per arm per chunk set; 1,200
  total episodes), all valid, no dropped group > 5; append run_log.txt.

### Task 11: Final verification, report, seal (plan S.12 + R1.1)

**Files:**
- Create: scripts/sr_verify.py, research/round2_stagewise_reward/report.md
- Output: results/final_integrity.json, integrity.sha256

- [ ] Step 1: sr_verify.py checks: analysis_plan.md hash matches its .sha256; model_artifact
  frozen hash unchanged since Task 6; protected files (policy.py, kit.py, evaluate.py,
  Dockerfile, requirements.txt) hashes match the baseline-integrity seal values (read
  research/round2_baseline_integrity/baseline_hashes.sha256); seed lists pairwise disjoint
  (pilot/training-fit/training-val/final-eval); zero cardinality mismatches/fallbacks;
  every report deliverable file exists; no file outside the experiment directory modified
  (git status read-only, no mutations).
- [ ] Step 2: Write report.md answering the 10 brief questions with numbers pulled from the
  machine-readable results, ending with exactly one decision per the R1.1 rule ordering.
- [ ] Step 3: Seal integrity.sha256 over the experiment directory; re-run sr_verify.py ->
  all PASS; complete run_log.txt; STOP for review (no further rollouts).

## Self-review notes

- Spec coverage: plan S.1 -> recon doc (analysis_plan S.1, done pre-approval); S.2 -> Task 2;
  S.3 -> Tasks 4-5; S.4 -> Task 3; S.5 -> Tasks 2-3; S.6 -> Task 1; S.7 -> Task 6;
  S.8 -> Tasks 7-8; S.9 -> Task 9; S.10 -> Task 10; S.11 -> gates inside tasks 1-8, 10-11;
  S.12 -> Task 11. No gaps.
- No git steps anywhere (Global Constraints override the template).
- Type consistency: build_feasible_edges/extract_pair_features (Task 1) are the only feature
  source for Tasks 3, 6, 8, 9; stage_labels (Task 2) the only label source for Task 3;
  solve_exact_k used only via the pinned signature in Task 7-8.
