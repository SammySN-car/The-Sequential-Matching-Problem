# SESSION HANDOFF - round2_stagewise_reward_solver

Checkpoint written 2026-10-14 (session handoff only). No experiment step was
started, rerun, or changed while writing this document. No file outside this
document was created, modified, or deleted by the handoff.

Repository root (referred to as REPO below):

    C:\Users\samar\Downloads\New folder (11)\The-Sequential-Matching-Problem

Note: the OpenCode working directory is C:\Users\samar, which is NOT the
repository. Every command must either cd to REPO or use absolute paths.

---

## 1. Current objective

We are testing whether stagewise reward-aware pair selection beats the existing
greedy baseline in the sequential matching simulator.

Current direction: a polynomial-time exact maximum-weight matching algorithm
that selects EXACTLY the same number of pairs as greedy at every decision state
(exact-k), using the existing frozen model (no retraining, no recalibration).

Research question (verbatim from analysis_plan.md S.1):

    Does reward-aware exact-k pair selection improve realized MSMIs in the full
    sequential simulator, when the candidate introduces exactly as many pairs as
    greedy in every individual decision state?

The previous experiment (research/round2_stagewise_reward/) never tested the
policy hypothesis because its branch-and-bound solver was too slow. This round
removes that computational bottleneck and, only if every gate passes, runs the
previously untouched paired evaluation.

---

## 2. Current execution state

### 2.1 Working directory and repository structure

- OpenCode cwd: C:\Users\samar (no research/ directory here).
- Repository: REPO (path above), git branch 'main'.
- Git status (read-only inspection, VERIFIED): " M policy.py" (pre-existing
  modification, file date 2026-10-12, predates this experiment), "?? policy_ac.py",
  "?? test_policy.py", "?? docs/superpowers/", "?? research/" (research/ is
  untracked as a whole). No git command that mutates state was ever run.
- Top-level protected files: policy.py, kit.py, evaluate.py, Dockerfile,
  requirements.txt.
- research/ contains 26 prior experiment directories. The two that matter here:
  - research/round2_stagewise_reward/        (SEALED prior experiment)
  - research/round2_stagewise_reward_solver/ (CURRENT experiment, in progress)

### 2.2 Files created/modified for the current experiment

All under research/round2_stagewise_reward_solver/ (SHA-256 verified this session):

| File | Bytes | SHA-256 | State |
|---|---|---|---|
| analysis_plan.md | 20362 | ed1210c2a4afd47f8cd1b3c8598daced848ac6b41916e41470f5d819ae113305 | FROZEN |
| analysis_plan.sha256 | 84 | contains the same ed1210c2... value | matches file |
| implementation_plan.md | 6783 | e178ff825d4c0439ef209cbb00e8d18a64984ce972aa0fe2983f49ffefe45ded | written, not sealed yet |
| run_log.txt | 1542 | 56cf887ca55178a08dced66f38d7cbd51f7e184a304ce51323afcafb10513172 | append-only, 8 entries, last 2026-10-14T10:58:26Z |
| sr_policy_core.py | 3064 | 02af1e6a4b7bf9dbfda9d74de998bbe07b8242d59da42ba1e2d45b108bed046d | byte-identical copy of parent |
| scripts/sr_features.py | 7436 | 76fc12f6a75f45d247cb277fe36a0ddade520891eae7156bea18dc10d080e67e | byte-identical copy of parent |
| scripts/srws_solver.py | 20170 | cfeccaf0b2b92b8ef874876c2dd979956da2a2ad434be012083414ce976259cf | IN PROGRESS (Task 1) |
| scripts/srws_solver_smoke.py | 6894 | 19a918d7fa37517fbf7dce597c37db2486a7c2d3434549b73083249b8de7e8b6 | TDD smoke, not yet green |
| results/ | (empty) | - | no result files yet |

Not yet created (planned by implementation_plan.md): policy_candidate.py,
scripts/srws_solver_test.py, scripts/srws_policy_test.py, scripts/srws_benchmark.py,
scripts/srws_eval_run.py, scripts/srws_eval_aggregate.py, scripts/srws_integrity.py,
report.md, integrity.sha256, and everything in results/.

Sibling SDD ledger (outside REPO): C:\Users\samar\.superpowers\sdd\round2_solver\progress.md
- Status: T1 DISPATCHED, T2-T6 unchecked, "Rulings: (none yet)".

### 2.3 Completed implementation / verification tasks

- [x] Pre-registration written and FROZEN (analysis_plan.md sha256 ed1210c2...,
      written BEFORE any solver code; .sha256 file matches on re-verification
      this session).
- [x] Frozen model verified: research/round2_stagewise_reward/results/model_artifact.json
      sha256 7f1ddfe00211e2603e88c4e8318d3a62980aeb8364f51bc41909e8875fa275f2
      (re-computed this session, matches).
- [x] Seeds 70001-70100 verified untouched at pre-registration (run_log entry;
      parent sr_verify.py 17/17 PASS recorded zero 70xxx data files/rows).
- [x] Parent seal intact: research/round2_stagewise_reward/integrity.sha256 has
      1638 entries (counted this session).
- [x] Byte-identical copies of sr_features.py / sr_policy_core.py recorded.
- [x] Evaluator CLI semantics documented in run_log (evaluate.py --policy ...
      --seeds csv --variants all; 10 s hard invoke limit; 60+40 day horizon).
- [x] Recorded-state corpus noted: 180000 rows; stress set = v4_dense_timing
      53 states.
- [x] Task 1 (srws_solver.py) code WRITTEN but NOT passing: TDD smoke written
      first, RED observed (ModuleNotFoundError), then implementation written.

### 2.4 Tests and runtime benchmarks - status

- Smoke test scripts/srws_solver_smoke.py: NOT GREEN. Per the previous session's
  last observation: first 3 checks passed (empty/k=0, empty/k=1 infeasible,
  k=0) then it failed at the triangle case with
  "SolverError: internal: no convergence after 1201 steps".
  >>> This outcome is NOT recorded anywhere in the repository - it comes from
  >>> session memory and MUST be re-verified by re-running the smoke script.
- 200-case brute-force mini-battery inside the smoke script: NOT reached
  (blocked by the triangle failure).
- n=60 / k=17 / 65-edge timing check (< 3.0 s): NOT reached.
- Task 2 battery (C1-C6, >= 10,000 brute-force cases): NOT STARTED.
- Policy gates P1-P3: NOT STARTED.
- Runtime benchmark gates R-A..R-D: NOT STARTED.
- Final paired evaluation: NOT STARTED (and must not start until all gates pass).

### 2.5 Pre-registration

Exists and is FROZEN: research/round2_stagewise_reward_solver/analysis_plan.md,
sha256 ed1210c2a4afd47f8cd1b3c8598daced848ac6b41916e41470f5d819ae113305,
recorded in analysis_plan.sha256 and in run_log.txt before any solver code.
Re-verified this session: recomputed hash equals the recorded hash.

### 2.6 Running processes

None. Checked: no python/pythonw processes running; results/ empty; nothing
launched in the background. Nothing needs to be killed or waited on.

### 2.7 Last completed step / precise next step

- LAST COMPLETED STEP: scripts/srws_solver.py was written (and last compiled -
  scripts/__pycache__/srws_solver.cpython-313.pyc carries the same 16:45:28
  timestamp as the .py), i.e. Task 1 implementation exists but is unverified
  and, per session memory, failing.
- NEXT EXACT ACTION: re-run the smoke test to re-establish ground truth:

      cd REPO
      $env:PYTHONIOENCODING='utf-8'
      python research\round2_stagewise_reward_solver\scripts\srws_solver_smoke.py

  then iterate on scripts/srws_solver.py until every smoke check passes
  (including the 200-case brute battery and the n=60 timing check < 3.0 s),
  then append the outcome to run_log.txt and update the SDD ledger.

### 2.8 Resume commands

All commands run from REPO (not from C:\Users\samar). This machine's shell is
PowerShell, so prefix with $env:PYTHONIOENCODING='utf-8'.

    # smoke / TDD loop
    python research\round2_stagewise_reward_solver\scripts\srws_solver_smoke.py

    # re-verify frozen artifacts at any time (read-only)
    Get-FileHash research\round2_stagewise_reward_solver\analysis_plan.md -Algorithm SHA256
    Get-FileHash research\round2_stagewise_reward\results\model_artifact.json -Algorithm SHA256

    # task order (implementation_plan.md): T1 solver -> T2 battery ->
    # T3 policy_candidate + P gates -> T4 benchmark + R gates ->
    # T5 paired evaluation (GATED) -> T6 report + seal

### 2.9 Errors, unresolved questions, blockers

- ERROR (needs re-verification): smoke test fails at the triangle case with
  SolverError: internal: no convergence after 1201 steps.
- KNOWN DIAGNOSIS from the previous session (derived, not yet applied - the
  file hash above is what is on disk, so treat the diagnosis as a hypothesis to
  re-check, not as fact):
  1. The implemented dual is the MIN-weight form; feeding positive combined
     weights makes it minimise instead of maximise. Suspected fix: feed
     negated costs c = -W' and initialise vertex duals to min_c // 2.
  2. augment() extracts the alternating path via the par[] parent chain, which
     growth-from-blossom-member breaks; suspected fix: BFS over current tight +
     matched edges before blossom expansion.
  3. The in-loop augment flip guard reads mate[] after mutation; suspected fix:
     snapshot orig = list(mate) before flipping.
- OPEN QUESTION: run_log.txt has no entry for the solver/smoke work (last entry
  10:58:26Z, files 16:45). Bring the log up to date when the smoke test passes.
- OPEN QUESTION: implementation_plan.md contains a "Realisation note" claiming
  the max-cardinality form is mathematically equivalent to the plan's negated
  form. That claim was in tension with observed behaviour and is NOT settled.
- BLOCKER: none external. All remaining work is in-process debugging.

---

## 3. Previous research findings

- policy.py currently defaults to greedy: def decide(request, mode='greedy')
  and argparse --baseline choices=['greedy','no_asks','random','ac'] with
  default 'greedy' (policy.py lines 14, 602-603). VERIFIED by reading the file.
- The previous experiment lives in research/round2_stagewise_reward/ and is
  SEALED. Its report.md contains exactly one decision: STOP / REDESIGN
  (report.md lines 23, 25, 29; also in its run_log). integrity.sha256 covers
  1638 entries; post-seal sr_verify.py re-run 17/17 PASS.
- Its branch-and-bound exact-cardinality solver passed its tested correctness
  checks (V1 9421 checks / 0 failures, V3 360 states / 0 violations, V5 348
  states / 0 discrepancies, fc_own_suite PASSED) but reached 17.199 s on dense
  states: v4 timed 53 states, max_seconds 17.199167, 15/53 states hit the
  16,000,014-node abort, against the < 3.0 s experimental gate and the 10 s
  evaluator limit. Source: parent run_log.txt and report.md lines 32, 230, 237.
- A subsequent audit corrected a population error in the combined-model
  metrics. As quoted in the frozen analysis_plan.md S.3 (background only): over
  all 45,803 mature validation introductions the frozen model's combined
  ROC-AUC was 0.531473, PR-AUC 0.011841 vs 0.010589 prevalence, mean predicted
  0.010359 vs observed 0.010589. (train_metrics.json's pre-audit combined val
  figure differs - ROC-AUC 0.4656 on n=5,028; both are recorded in their
  respective sources. 0.531473 is the audit-corrected value the current plan
  quotes.) Log loss 0.058775 vs 0.058692 constant-prevalence baseline comes
  from the same audit - it appears in session context but was NOT re-located in
  the repository this session: >>> treat as REQUIRES CHECKING.
- Stage 1 has modest predictive signal (val PR-AUC 0.1792 vs 0.1409 prevalence,
  ROC-AUC 0.570115; report.md ~line 160). Stages 2 and 3 remain weak, at or
  below the constant baseline (s2 ROC-AUC 0.5040; s3 ROC-AUC 0.4698).
- No full paired policy evaluation has established whether reward-aware
  selection beats greedy. The parent experiment's final paired evaluation was
  explicitly SKIPPED ("realized MSMIs and paired effect size + CI = NOT
  MEASURED", parent run_log).
- Seed groups 70001-70100: VERIFIED this session as still available. Evidence:
  (a) no file under REPO matches the name pattern *700* except unrelated
  seed_40262 data; (b) content grep for 70001 across REPO finds only plan text,
  source-code constants and prior run_log statements - no evaluation output;
  (c) the parent sr_verify.py d2 check recorded zero 70xxx data files/rows
  across 1602 files / 357 MB and zero eval outputs. >>> Re-run the parent's
  read-only d2-style scan before T5, as the plan requires re-verification.

---

## 4. Non-negotiable constraints

1. Do NOT modify policy.py, kit.py, evaluate.py, Dockerfile, requirements.txt,
   or any file in research/round2_stagewise_reward/ (1638-entry seal) or any
   other prior research directory.
2. Do NOT retrain or recalibrate the frozen model (model_artifact.json sha256
   7f1ddfe0...). Verify it before and after the final evaluation; any mismatch
   stops the experiment.
3. Standard library only at policy runtime (no NetworkX/SciPy/new packages, no
   network, no GPU, no external processes).
4. No silent greedy fallback: if the candidate solver fails, fail loudly
   (stderr diagnostic + non-zero exit). No approximate solver, no
   density-threshold fallback, no clarification logic.
5. Do NOT consume seeds 70001-70100 until ALL pre-evaluation correctness (C),
   parity (P) and runtime (R) gates pass.
6. No git-mutating commands (no add/commit/checkout/stash/reset/etc.).
7. Do NOT weaken or change any frozen gate after seeing results; thresholds
   stay as written in analysis_plan.md (sha256 ed1210c2...).
8. Do NOT start an alternative policy or another research direction; one
   experiment, one decision.
9. All new files under research/round2_stagewise_reward_solver/ only (this
   handoff document at repo root is the single exception, written by explicit
   instruction).

---

## 5. Integrity and continuation instructions

Frozen artifacts and hashes (re-verified 2026-10-14 this session):

- analysis_plan.md        sha256 ed1210c2a4afd47f8cd1b3c8598daced848ac6b41916e41470f5d819ae113305
- model_artifact.json     sha256 7f1ddfe00211e2603e88c4e8318d3a62980aeb8364f51bc41909e8875fa275f2
- sr_features.py (copy)   sha256 76fc12f6a75f45d247cb277fe36a0ddade520891eae7156bea18dc10d080e67e
- sr_policy_core.py(copy) sha256 02af1e6a4b7bf9dbfda9d74de998bbe07b8242d59da42ba1e2d45b108bed046d
- parent integrity.sha256 1638 entries over research/round2_stagewise_reward/
- current solver          sha256 cfeccaf0b2b92b8ef874876c2dd979956da2a2ad434be012083414ce976259cf
                          (NOT sealed; will change during debugging)

Preserve run logs. The parent run_log.txt keeps its failures and its
[CORRECTED] entries; the current run_log.txt is append-only - append, never
rewrite, and record failures as well as successes.

No secrets: this document, the plans and the logs contain no credentials, API
keys, tokens or other secrets. Keep it that way.

Do not modify any previously sealed directory.

---

## Final checklist

1. LAST VERIFIED COMPLETED STEP: pre-registration frozen and re-verified
   (analysis_plan.md hash matches analysis_plan.sha256), model artifact hash
   re-verified, parent seal (1638 entries) confirmed intact, seeds 70001-70100
   confirmed untouched, and Task 1 code written to
   research/round2_stagewise_reward_solver/scripts/srws_solver.py
   (sha256 cfeccaf0..., 20170 bytes).

2. NEXT EXACT ACTION: run
   python research\round2_stagewise_reward_solver\scripts\srws_solver_smoke.py
   from REPO with PYTHONIOENCODING=utf-8 to re-establish pass/fail status,
   then debug srws_solver.py until green. Do not start Task 2+ first.

3. PATHS THAT MUST REMAIN UNTOUCHED:
   - REPO/policy.py, kit.py, evaluate.py, Dockerfile, requirements.txt
   - REPO/research/round2_stagewise_reward/** (all 1638 sealed entries)
   - every other REPO/research/** directory (round2, round2_fixed_cardinality,
     method_tournament, e3_rel_experiment, etc.)
   - REPO/results/** (prior official evaluation outputs)
   - frozen hashes: analysis_plan.md ed1210c2..., model_artifact.json 7f1ddfe0...

4. TESTS AND GATES STILL OUTSTANDING:
   - T1: srws_solver_smoke.py fully green (triangle trap, K4, star infeasible,
     determinism x5, exact-float tie, 200-case brute battery, n=60/k=17 timing
     < 3.0 s, meta keys).
   - T2: srws_solver_test.py battery C1-C6, >= 10,000 brute-force cases,
     -> results/solver_validation.json (C5 cross-check vs
     research/round2_fixed_cardinality/scripts/fc_matching.py).
   - T3: policy_candidate.py + P1-P3 -> results/policy_validity.json
     (k_candidate == k_greedy in EVERY state, loud failure, no greedy fallback).
   - T4: benchmark corpus + R gates -> results/runtime_benchmark.json
     (solver and full match invocation strictly < 3.0 s/state; evaluator
     10 s limit).
   - T5: paired evaluation on seeds 70001-70100 (GATED on all of the above;
     model hash re-verified before and after).
   - T6: report answering the 10 questions + exactly ONE decision, then seal.

5. ACTIVE PROCESS REQUIRING SPECIAL HANDLING: none. No background commands,
   no running interpreters, empty results/ directory. The only caution when
   switching sessions is the cwd quirk: OpenCode starts in C:\Users\samar, so
   every command must target REPO explicitly.