# Pre-flight Report: Sequential Matching Method Tournament

Date: 2026-10-08
Scope: pre-execution review only. No tournament phase has been run (see section 9).
This report synthesizes the adversarial audit (`audit_review.md`), the repaired
implementation plan (`docs/superpowers/plans/2026-10-08-method-tournament.md`),
the design document (`research/method_tournament/design.md` once created by the
plan), and fresh fixture evidence (section: Evidence sources).

## 1. Statistics

- Inference clusters on seed. The 6 variants share one seeded world per seed
  (measured: development/delayed/shift/drift rosters are identical per seed;
  sparse and cold_start differ; id-aligned across all 6 = false). Deltas are
  averaged within seed first -> 12 seed-level means, df = 11 (Phases 2/3),
  3 seed-level means at screening (df = 2 for intervals; screening itself is
  gate-only).
- Conservative tabulated two-sided t criticals: 95% table (df 11 -> 2.201) and
  a 99% table (df 11 -> 3.106, df 1 -> 63.657) for the Phase-3 Bonferroni gate.
  k = 1 candidate -> 95%; k = 2 -> 99%. Both cluster intervals must clear zero.
- ICC measured at -0.1489 on the fixture variance decomposition; it is unstable
  at n = 3 and is reported honestly, not used to justify the clustering choice.
  The clustering choice follows from roster identity (structure), not ICC.
- Per-variant stratification is mandatory: no per-variant mean below -0.15 may
  be claimed credible; retention additionally requires mean >= -0.05.
- Ranking/selection uses full-precision mean paired deltas (ties by
  (round(mean, 6), method_id)); display rounding never decides anything.
- Coverage delta >= -0.05 and ask cost are guardrails: reported, not binding.
- The incumbent 0.4931 MSMI/100 is a different seed set and is never compared
  to tournament numbers.

## 2. Control equivalence

- `m01_greedy_baseline` must be byte-identical to `policy.py --baseline greedy`:
  cross-checked in tests, and the screening analysis HARD-FAILS if m01's
  `action_sha256` differs from the shared control on any of the 18 worlds.
- m01 is excluded from eligibility, ranking, and retention (parity/diagnostic
  control only); the report states this explicitly.
- The control is one shared arm per world; all method deltas are paired against it.

## 3. Latency

- Retention gate: `max_inference_seconds > 10.0` disqualifies a method;
  missing latency evidence also disqualifies (never silently accepted).
  > **Correction 2026-10-09 (execution, Task 12 review):** the operative gate is
  > design.md section 7's per-invocation reading - "all invocations valid, i.e. under
  > 10 s each". `inference_seconds` is a 120-invocation *episode total*
  > (evaluate.py: per-phase L83/90 accumulates over ~120 invokes); analysis evaluates
  > `max_inference_seconds / INVOKES_PER_EPISODE > 10.0` (INVOKES_PER_EPISODE = 120 in
  > analyse_tournament.py). The episode-total reading above would disqualify the frozen
  > control by construction (control wall 21.4 s = 0.178 s/invocation, well under 10 s).
  > The PROBLEM_STATEMENT.md "10-second limit per invocation" (L201) and design.md
  > section 7 govern; this line records the superseded reading.
- Heavy paths are fixture-tested at < 5 s per call: Hungarian (alloc-level,
  dense day-59), m24/m25 decide-level worst-case (day-30 over-cap fixture),
  and m30 VoI enumeration.
- m30 is hard-capped: `VOI_EVAL_CAP = 96` greedy recomputations per ask phase
  in fixed (member, field, option) order, with forced-truncation tests
  (cap = 1 and cap = 2 must bind).
- Measured full-rollout wall time on fixtures: 3.3-3.9 s per world.

## 4. Graph branches

- Measured across 90 fixture snapshots (3 seeds x 5 days x 6 variants):
  non-bipartite 5/90 (5.6%), nodes over the Hungarian cap 6/90, max edges 18,
  max nodes 195, day-59 max edges 5, soft not-asked pairs on day 59: max 816,
  mean 688.3.
- Both fallback branches are FORCED in tests, not merely mirrored:
  m24's odd-cycle fallback (max_cardinality -> None), m25's non-bipartite
  fallback (two_color -> None), and m25's over-cap fallback
  (HUNGARIAN_NODE_CAP -> 0) are each triggered by monkeypatch and compared
  against the reference implementation; alloc-level branches additionally get
  synthetic odd-cycle tests and a forced non-bipartite latency path.

## 5. Retention rules

- Eligible = zero invalid episodes AND mean delta >= -0.05 AND every
  per-variant mean >= -0.15 AND latency <= 10 s (evidence present).
- m01 never enters this function (excluded upstream).
- Retained = first min(5, E) by full-precision rank + next up to 3 diagnostics
  with fixed-format reasons; E = 0 -> ([], [], []) -> Phases 2 and 3 are
  SKIPPED (explicit plan branch writes `confirmation_results.json` with
  `selected: []`, runs no confirm-1 episodes, and still records the boundary
  freeze manifest).
- The human gate may only REMOVE methods (or replace within eligibility);
  the approved list is recorded in `run_log.txt` and, if changed, the
  instrument pass is rerun to match.

## 6. Asking semantics

Measured (preflight f07, all PASS):
- Daily budget 12; the control issues exactly 4 `constraints` asks (cost 3 each).
- Declined fields are charged (3) but remain declined; same-day hard-field
  fills observed (10); feasible pairs with unknown soft fields remain after
  10 days (2) -> asking is not vacuous.
- Hard-ask tests enforce: no duplicate (member, field), no unavailable members,
  no already-declined fields, cost <= remaining budget; soft asks only on
  `not_asked` fields; m29/m30 reserve 3 budget units (`SOFT_ASK_RESERVE`),
  preregistered as one fewer constraints bundle per day (ask-cost secondary).

## 7. Smoke isolation

- Smoke phase: seed 90290 x development variant only (31 episodes = 30 methods
  + control), disjoint from official seeds 143-163 and fixture seeds 90210+.
- Phase configs are unit-tested (`test_phase_configs_preregistered`); smoke
  writes only smoke-tagged outputs and never mixes with official phase rows.

## 8. Freeze scope

- After the retention gate (and after the screening instrument pass, so
  instrument defects can still be fixed), 51 files are hashed into
  `hashes/policy_freeze_after_screening.txt` with repo-root-relative paths:
  5 `methods_*.py` + 10 named files (common, alloc, registry, gen_policies,
  _cli, run_tournament, analyse_tournament, instrument, design.md, methods.json)
  + 30 policy launchers + 6 root frozen files (kit, policy, policy_ac, evaluate,
  organise, Dockerfile).
- `verify_freeze` re-verifies the manifest (base = repo root) at every later
  phase boundary; the confirm-1 boundary manifest must be byte-identical.
- Additionally: every runner row carries a pre-screening `code_sha256`
  (`code_fingerprint()` over exactly those 51 files), written once to
  `hashes/pre_screening_fingerprint.txt`; analysis hard-fails on any row with a
  foreign fingerprint; a foreign fingerprint purges stale rows to an archived
  `_v<hex8>.jsonl`; every runner invocation is logged to
  `per_phase/<phase>_attempts.jsonl`.
- From the freeze onward: no method/threshold/weight/logic edits (methods may
  be eliminated, never redesigned).

## 9. Seed freshness

- `research/method_tournament/` contains only `preflight_tools/` and
  `audit_review.md`: no `per_phase/`, no `hashes/`, no results, no run_log.
- Official seeds 143-163 have never been executed; fixtures use 90210-90217
  (smoke: 90290); prior research rounds used disjoint seeds (101-118), and
  `test_research_and_eval_seeds_are_disjoint` passes.

## 10. Leakage

- Methods see only `Simulator.observe()` (no `truth`, `seed`, `exit_day`,
  `variant`); enforced by the frozen runner test
  `test_observed_policy_never_receives_world_fields` and by the plan's AST
  scanner (banned names/attributes/literals, banned imports and calls,
  dunder access) plus runtime negative checks that patch `kit.generate` /
  `Simulator` to raise (plan Task 5, swept over all 30 methods in Task 11).
- Request/schema contract test: strict JSON, no world fields injected.

## 11. Determinism

- Hash-seed independence measured: digest
  `0c8e75658d4559cb4262369a477b1170a365cd1f8a0d0bd4aa79fa68a9be877b`
  identical under PYTHONHASHSEED 0, 1, and random.
- World generation is order-independent (frozen test); per-group determinism
  tests (same request twice, member order reversed -> same action set).
- The instrument pass replays official episodes and requires byte-identical
  `action_sha256` digests (`all_digest_match`), else exit 2.
- Runner dedupe is last-row-wins per (method, seed, variant); attempt log
  records every invocation.

## 12. Integrity

- NO-GIT-MUTATION rule: no add/commit/checkout/restore/stash anywhere in the
  plan (grep-verified); only read-only `git rev-parse`/`git status`.
  Current baseline: HEAD `a8e26b3`, 0 new commits, pre-existing ` M policy.py`.
- Plan failure paths STOP and report integrity files instead of reverting
  files with git: before/after snapshots of the non-plan tree, a frozen-file
  snapshot, a git-state snapshot, and a plan-file hash; `.dockerignore` is
  restored from a saved baseline copy (baseline: `*` + `!kit.py`,
  `!policy.py`, `!Dockerfile`), never from git.
- The six frozen files (policy, policy_ac, kit, evaluate, organise, Dockerfile)
  are never modified; hash prefixes re-verified at each integrity step.

## 13. Method diversity

- 30 preregistered methods across 5 groups (A-E) in `methods.json`/design
  section 5, spanning allocation/graph mechanisms (m24-m28), active asking
  (m29-m30), and the quota/patience/threshold families; mechanisms, not
  cosmetic parameter variants (design section 5; M17 documented).
- Honesty reporting added: per-method behavioral distinctness (distinct action
  digests, worlds differing from control), plus within-seed cross-variant
  dispersion - never used as ranking inputs, so a degenerate "copies of
  greedy" field is visible before retention.
- m01 stays in the roster as a parity control but can never win.

## 14. Final episode counts

| Phase / pass                | Formula                       | Episodes        |
|-----------------------------|-------------------------------|-----------------|
| Smoke (runner, 90290)       | 31 arms x 1 world             | 31              |
| Screening (official)        | (30 + 1) x 18                 | 558             |
| Screening instrument        | (retained 5-8 + 1) x 6        | 36 - 54         |
| Confirm-1 (official)        | (retained 5-8 + 1) x 36       | 216 - 324       |
| Confirm-2 (official)        | (selected 0-2 + 1) x 72       | 0 / 144 / 216   |
| Confirm-2 instrument        | (selected 0-2 + 1) x 6        | 0 / 12 / 18     |
| Docker parity check         | bounded sample                | <= 18           |

- Official (screening + confirm-1 + confirm-2): 774 - 1098 episodes.
- Grand total including smoke, both instruments, and docker: <= 1219 episodes.
- E = 0 path: screening 558 only; phases 2-3 and their instruments are skipped.

## 15. Adversarial audit: findings and repairs

Source: `research/method_tournament/audit_review.md` (STEP A adjudication;
STEP B repairs applied to the plan/design/tests/stats/freeze/integrity).
Headline repairs:

- F-01 statistics redesigned to seed-clustered inference with conservative
  t tables, Bonferroni levels, and honest ICC reporting (sections 1).
- F-02 runner fingerprinting: `code_fingerprint`, pre-screening fingerprint
  file, stale-row purge, attempt log (section 8).
- F-03 m01 parity hard-fail + exclusion from ranking/retention (section 2).
- F-04/F-08 forced-branch and latency tests for alloc, m24, m25, m30
  (sections 3-4).
- F-09 exact verdict sentence:
  `Greedy remains the best empirically supported policy among the evaluated candidates.`
- F-10 smoke moved to seed 90290 with preregistered phase-config tests (section 7).
- F-11 integrity rewritten to snapshot/STOP semantics with no git checkout,
  plus `.dockerignore` baseline copy (section 12).
- F-12 freeze expanded to the 51-file root-relative behavior/spec set with
  re-verification at every boundary (section 8).
- F-13/F-14 diversity and dispersion reporting (section 13).
- F-16 explicit E=0 skip branch (section 5).
- F-05/F-06/F-07/F-17 test-count, doc, and wording fixes; F-15/F-18 cleared;
  M17 confirmed and documented.

## 16. Execution prerequisites (operational, not protocol defects)

- Python environment with the repo's test dependencies (present: 144-test
  suite ran green here).
- Docker daemon for the container-parity step: the frozen integration test
  was skipped in this environment (`docker daemon not available`); start the
  daemon before that plan step.

## 17. Known limitations (documented, accepted)

- Sequential (day-by-day) coverage: methods see only observations made up to
  the current day; the design documents this as the protocol's scope, not a bug.
- MSMI is quantized at this scale (fixture values in {0.0, 0.5}); small deltas
  may be unresolved on few seeds - which is exactly why gates use clustered
  intervals and screening is gate-only.
- ICC at n = 3 is unstable and does not support effect-size claims.
- Diagnostic candidates (slots 6-8) are diagnostics: they can be retained for
  Phase 2 but never presented as evidence of beating greedy.

## Evidence sources

- `research/method_tournament/audit_review.md` - adjudicated audit findings.
- `research/method_tournament/preflight_tools/preflight_kit_checks.py` /
  `.json` - fresh rerun 2026-10-08: ALL_PASSED (roster identity, seed
  clustering, asking semantics, graph stats, hash-seed independence).
- Frozen suites: `python -m unittest test_kit test_runner test_release
  test_policy research.test_pipeline` -> 144 tests, OK (1 skipped: docker
  daemon not available), 2026-10-08.
- Git baseline (read-only): HEAD a8e26b3, 0 new commits.
- Plan: `docs/superpowers/plans/2026-10-08-method-tournament.md` (grep sweep:
  no git mutation commands, no stale verdict wording, balanced fences,
  sequential step numbering in every task).

PRE-FLIGHT VERDICT: SAFE TO RUN