# Method Tournament (Broad Discovery) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and run a 3-phase discovery tournament of ~30 sequential matching policy variants (mechanisms with documented overlaps, not independent paradigms) under `research/method_tournament/`, each paired against the validated greedy control on fresh seeds, to determine whether any policy credibly outperforms greedy on realized MSMI/100.

**Architecture:** Every method is a deterministic decision function `fn(request) -> response` invoked through the official subprocess protocol (`evaluate.episode`). Shared helpers (`common.py`, `alloc.py`) provide edge enumeration and allocation primitives; thin generated launchers in `policies/` expose each method as a policy file runnable by `evaluate.py`. A phase runner (`run_tournament.py`) executes screening/confirmation/final blocks with frozen-method hash checks; an analysis script (`analyse_tournament.py`) computes paired MSMI/100 differences, reports, and the final leaderboard.

**Tech Stack:** Python >=3.10, standard library only (`json`, `statistics`, `itertools`, `subprocess`, `concurrent.futures`, `unittest`, `ast`, `hashlib`). No third-party packages (repo has none installed). No network at policy runtime. Docker 29.8.x only for final container-parity checks.

**Spec:** User strategy brief "BROAD METHOD SEARCH / DISCOVERY TOURNAMENT" (conversation, re-sent 2026-10-08). Its protocol is materialized as the preregistered `design.md` written in Task 1; executors read both this plan and that design.md. **This project runs under a NO-COMMIT rule (spec Section 14): verification steps replace commit steps. Never run `git commit`, `git add`, or any git-mutating command.**

## Global Constraints

- Working directory for every command: `C:\Users\samar\Downloads\New folder (11)\The-Sequential-Matching-Problem` (the repo root).
- Fresh seeds only, exactly: Phase 1 screening `143,144,145`; Phase 2 confirmation `146,147,148,149,150,151`; Phase 3 final `152..163`. All x 6 variants (`development, sparse, cold_start, delayed, shift, drift`). Seeds `101-142` and `50000+` are used artifacts; never run decision experiments on them. Tests/fixtures use seed `90210+` only; the machinery smoke phase uses fixture seed `90290` only (never a tournament seed).
- Banned policy inputs (verbatim): `truth`, `bias`, `response_rate`, `second_bias`, `exit_day`, `seed`, `variant`, future arrivals, future feedback, raw `sim.events`, hidden globals. Violation of any banned input is a test failure, not a review comment.
- Ask budget 12/day (constraints bundle = 3, soft field = 1); declined answers stay unknown (never imputed); 10-second invocation limit; 1 MiB request/response/memory limits; 60-day decision horizon + 40 follow-up days; exact JSON protocol (`evaluate.validate_response`).
- Standard library only; no `PYTHONHASHSEED` is set, so all iteration must be sorted or insertion-ordered for determinism.
- Frozen files that must never be modified: `policy.py`, `policy_ac.py`, `kit.py`, `evaluate.py`, `organise.py`, `Dockerfile`, existing `test_kit.py`/`test_runner.py`/`test_release.py`/`test_policy.py`, `research/` frozen artifacts, `.dockerignore` (byte-exact; any temporary extension for image builds must be restored from the baseline copy saved at Task 16 start and re-hashed against the recorded baseline digest before task end; never restore via a git command).
- All new files live under `research/method_tournament/` (plus plan file under `docs/superpowers/plans/`).
- No commits. Baseline git state to preserve: HEAD `a8e26b3`, status ` M policy.py` + untracked `docs/superpowers/ policy_ac.py research/ test_policy.py`.
- Methods are frozen after Phase 1: no threshold, weight, or logic edits between phases; sha256 manifests enforce it. A method may be eliminated; it may not be redesigned.
- Ranking uses ONLY paired same-world `msmi_per_100_arrived_members` difference vs greedy. Never AUC, offline expected value, mutual acceptances, introduction counts, or ask efficiency. Never compare absolute numbers across different seed sets (the 0.4931 incumbent number is a different seed set).
- Selection/verdict language: if no credible winner, write exactly "Greedy remains the best empirically supported policy among the evaluated candidates." Never write "optimal".
- All here-string file writes use `Set-Content`/`WriteAllText` with UTF-8 encoding; Python files read in tests use explicit `encoding='utf-8'`.

## Review Focus

Five failure modes the spec implies but a passing happy-path test would not catch, each with the test that pins it (all live in `research/method_tournament/test_tournament.py`):

1. **Hidden-state leakage** - a method touching `truth`/`seed`/`exit_day`/`variant` (e.g. via `m['truth']` or world dict) would score perfectly in tests while being disqualifying. Test: `test_no_hidden_state_access` - AST scan of every registry module and launcher for banned names/attributes/literals plus banned imports and calls (`os`, `subprocess`, `eval`, `exec`, `getattr`, `open`, ...) and dunder attribute access, backed by runtime negative checks where `kit.generate`/`Simulator` are patched to raise (Task 5 builds the scanner; Tasks 6-10 run it; Task 11 sweeps all).
2. **Control divergence** - `m01_greedy_baseline` silently differing from the validated greedy control (e.g. different tie-breaks) would corrupt every paired delta. Test: `test_m01_matches_control_greedy` - byte-equal responses from `policy.py --baseline greedy` vs the m01 launcher across fixture requests (Task 5), plus a screening-phase assertion that m01 `action_sha256` equals the control's on all 18 worlds (Task 12).
3. **Semantics drift** - a method emitting overlapping pairs, infeasible pairs, repeat pairs, or over-budget asks would produce invalid episodes (or, in-process, a `Simulator` `ValueError`). Test: `test_full_episode_<group>` - 60-day strict in-process rollout per method through `kit.Simulator.resolve_asks/advance` (Tasks 5-10), plus the 0-invalid gate on the smoke phase (Task 11).
4. **Latency >10 s** - Hungarian/assignment or VoI enumeration on a dense day-59 state would blow the invocation limit only at runtime, invalidating whole phases late. Test: `test_heavy_method_latency` - worst-case fixtures for `m24/m25/m30` must complete in <5 s per call, with forced-branch assertions so the fallback path actually executes (never skipped by a `if colored is not None` guard), plus the preregistered `VOI_EVAL_CAP` bound on m30 enumeration (Task 4 for `alloc.py`, Task 9 for m30, Task 11 sweep for all methods).
5. **Order dependence / non-determinism** - set/dict iteration or unstable ties would make results differ across runs, invalidating pairing. Test: `test_deterministic_and_order_invariant` - calling each method twice with identical requests yields identical responses, and reversing `state['members']` order yields the same action set (Tasks 5-10, per group; Task 11 repeats across all registry entries).

---

## File Structure

```
research/method_tournament/
  methods.json            # 30-entry registry (spec Section 3 fields); written Task 1
  design.md               # preregistered protocol (seeds, metrics, constants, rules); written Task 1
  common.py               # state helpers: edges, directionals, degrees, alts, waits, ctx; Task 2
  alloc.py                # allocation: greedy_take, gates, Kuhn/Hungarian, swaps; Tasks 3-4
  methods_a.py            # m01-m08 score-function decisions; Task 5
  methods_b.py            # m09-m15 scarcity/opportunity-cost decisions; Task 6
  methods_c.py            # m16-m23 temporal/wait decisions; Task 7
  methods_d.py            # m24-m28 graph allocation decisions; Task 8
  methods_e.py            # m29-m30 information/asking decisions; Task 9
  registry.py             # REGISTRY = {method_id: decide_fn}; created Task 5, extended each group task
  _cli.py                 # stdin JSON -> fn(request) -> stdout JSON; exit 1 on error; Task 5
  gen_policies.py         # (re)generates thin launchers in policies/ from REGISTRY; Task 5
  policies/               # 30 generated launchers, one file per method_id
  run_tournament.py       # phases smoke/screening/confirm1/confirm2 + control + freeze checks; Tasks 11-15
  analyse_tournament.py   # paired stats, retention, reports, leaderboard; Tasks 12-15
  test_tournament.py      # registry/protocol/determinism/leak/latency/full-sim suite
  per_phase/              # resumable episode rows (jsonl) + phase summaries + done flags
  screening_results.json  screening_report.md        # Task 12
  confirmation_results.json  confirmation_report.md  # Task 13
  final_results.json  final_report.md                # Task 15
  run_log.txt             # append-only progress log (runner writes; tasks append milestones)
  integrity/              # before/after frozen hashes + git state snapshots (Tasks 11, 16)
  hashes/                 # method freeze manifests at each phase boundary (Tasks 12-13, 16)
  deterministic_checks/   # official rerun digest comparisons (Task 15)
  docker_checks/          # container parity for final candidates + control (Task 16)
```

Responsibilities: methods files contain ONLY `decide_*` functions and their per-group `DECISIONS` dict; all shared logic lives in `common.py`/`alloc.py`; subprocess/protocol plumbing lives in `_cli.py`; world execution lives in `run_tournament.py`; statistics/reporting live in `analyse_tournament.py`. `research/method_tournament` is imported as top-level modules (each entry point inserts its own directory onto `sys.path`), matching how `policy.py` imports `kit`.

---

### Task 1: Registry and Preregistration (methods.json + design.md)

**Files:**
- Create: `research/method_tournament/methods.json`
- Create: `research/method_tournament/design.md`
- Create: `research/method_tournament/per_phase/`, `integrity/`, `hashes/`, `deterministic_checks/`, `docker_checks/`, `policies/` (directories)
- Test: `research/method_tournament/test_tournament.py`

**Interfaces:**
- Consumes: nothing (first task).
- Produces: `methods.json` shape `{"schema_version": "1.0.0", "methods": [ {...} x30 ]}` where each entry has keys `method_id, name, group, mechanism, required_inputs, asking, waiting, matching_optimization, computational_complexity, implementation_status, known_risks, literature_inspiration, file, decide_function`, plus `substituted_from` for m07 and m21. Later tasks import nothing from this file at runtime (it is a deliverable/registry of record; `registry.py` is the executable registry keyed by the same `method_id` strings). `design.md` contains the frozen constant table that `common.py` constants must match (enforced by `test_design_constants_frozen` in Task 2).

- [ ] **Step 1: Write the failing schema tests**

Create `research/method_tournament/test_tournament.py`:

```python
"""Test suite for the method tournament. Run from repo root:
python -m unittest research.method_tournament.test_tournament -v"""
import json
import pathlib
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

METHODS_JSON = HERE / 'methods.json'
DESIGN_MD = HERE / 'design.md'
REQUIRED = ('method_id', 'name', 'mechanism', 'required_inputs', 'asking', 'waiting',
            'matching_optimization', 'computational_complexity', 'implementation_status',
            'known_risks', 'literature_inspiration')


class RegistrySchemaTests(unittest.TestCase):
    def setUp(self):
        self.methods = json.loads(METHODS_JSON.read_text(encoding='utf-8'))['methods']

    def test_thirty_entries_numbered_m01_to_m30(self):
        prefixes = [m['method_id'].split('_')[0] for m in self.methods]
        self.assertEqual(prefixes, ['m%02d' % i for i in range(1, 31)])

    def test_required_fields_and_types(self):
        for m in self.methods:
            for key in REQUIRED:
                self.assertIn(key, m, '%s missing %s' % (m.get('method_id'), key))
            self.assertIn(m['asking'], ('active', 'baseline'))
            self.assertIsInstance(m['waiting'], bool)
            self.assertIsInstance(m['matching_optimization'], bool)
            self.assertTrue(m['file'].startswith('methods_') or m['file'] == 'kit.baseline')

    def test_group_counts(self):
        counts = {}
        for m in self.methods:
            counts[m['group']] = counts.get(m['group'], 0) + 1
        self.assertEqual(counts, {'A': 8, 'B': 7, 'C': 8, 'D': 5, 'E': 2})

    def test_substitutions_documented(self):
        by_id = {m['method_id']: m for m in self.methods}
        self.assertIn('control', by_id['m07_prune_and_greedy'].get('substituted_from', ''))
        self.assertIn('exit_day', by_id['m21_delay_cost_threshold'].get('substituted_from', ''))

    def test_design_lists_every_method(self):
        text = DESIGN_MD.read_text(encoding='utf-8')
        for m in self.methods:
            self.assertIn(m['method_id'], text, m['method_id'])


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest research.method_tournament.test_tournament -v`
Expected: FAIL with `FileNotFoundError` for `methods.json`.

- [ ] **Step 3: Create the scaffold directories**

```powershell
New-Item -ItemType Directory -Force -Path research\method_tournament\per_phase, research\method_tournament\integrity, research\method_tournament\hashes, research\method_tournament\deterministic_checks, research\method_tournament\docker_checks, research\method_tournament\policies | Out-Null
```
- [ ] **Step 4: Write `methods.json`**

Create `research/method_tournament/methods.json` with exactly this content:

```json
{
  "schema_version": "1.0.0",
  "note": "Registry of record for the discovery tournament. The 30 entries are policy variants/mechanisms with documented overlaps (see known_risks and design.md section 11), not 30 independent paradigms. implementation_status is flipped from pending to implemented by each group task and must read implemented for all 30 before Phase 1 (test_registry_all_implemented).",
  "methods": [
    {"method_id": "m01_greedy_baseline", "name": "Greedy baseline (control)", "group": "A",
     "mechanism": "Observed soft-field agreement count; sort by (-score, pair_key); take non-overlapping pairs; asks = baseline_asks. Byte-identical to policy.py --baseline greedy.",
     "required_inputs": ["state.members", "state.introductions", "state.ask_budget_remaining"],
     "asking": "baseline", "waiting": false, "matching_optimization": false,
     "computational_complexity": "O(a^2) per match phase (a = available members)",
     "implementation_status": "pending",
     "known_risks": "Control reference: any divergence from policy.py corrupts every paired delta (test_m01_matches_control_greedy).",
     "literature_inspiration": "Validated greedy implementation in this repository (kit.baseline_match).",
     "file": "methods_a.py", "decide_function": "decide_m01"},
    {"method_id": "m02_reciprocal_sum", "name": "Reciprocal sum", "group": "A",
     "mechanism": "directional(a,b) = sum over SOFT fields a observed of (1 equal / 0 unequal / prior 1/|OPTIONS[k]| when b missing); score = d(a,b) + d(b,a); greedy take.",
     "required_inputs": ["state.members", "state.introductions", "kit.OPTIONS"],
     "asking": "baseline", "waiting": false, "matching_optimization": false,
     "computational_complexity": "O(a^2 * |SOFT|) per match phase",
     "implementation_status": "pending",
     "known_risks": "Collapses to 2x match-count when both sides fully observed; differentiation driven by missing fields and asked values.",
     "literature_inspiration": "Reciprocal recommender bilateral fusion (sum aggregation of directional preferences).",
     "file": "methods_a.py", "decide_function": "decide_m02"},
    {"method_id": "m03_reciprocal_min", "name": "Reciprocal minimum", "group": "A",
     "mechanism": "score = min(d(a,b), d(b,a)) with the same directional as m02; greedy take.",
     "required_inputs": ["state.members", "state.introductions", "kit.OPTIONS"],
     "asking": "baseline", "waiting": false, "matching_optimization": false,
     "computational_complexity": "O(a^2 * |SOFT|) per match phase",
     "implementation_status": "pending",
     "known_risks": "Weakest-side rule can starve asymmetric-coverage members; coarse ties on low-coverage pools.",
     "literature_inspiration": "Weakest-side reciprocity (bilateral min fusion in reciprocal recommendation).",
     "file": "methods_a.py", "decide_function": "decide_m03"},
    {"method_id": "m04_reciprocal_product", "name": "Reciprocal product", "group": "A",
     "mechanism": "score = d(a,b) * d(b,a); greedy take.",
     "required_inputs": ["state.members", "state.introductions", "kit.OPTIONS"],
     "asking": "baseline", "waiting": false, "matching_optimization": false,
     "computational_complexity": "O(a^2 * |SOFT|) per match phase",
     "implementation_status": "pending",
     "known_risks": "Zero when either direction has no observed overlap; may reduce introductions on cold_start.",
     "literature_inspiration": "Mutual scoring via product of directional preferences (bilateral compatibility).",
     "file": "methods_a.py", "decide_function": "decide_m04"},
    {"method_id": "m05_harmonic_reciprocal", "name": "Harmonic reciprocal score", "group": "A",
     "mechanism": "score = 2*d(a,b)*d(b,a)/(d(a,b)+d(b,a)), 0 when the sum is 0; greedy take.",
     "required_inputs": ["state.members", "state.introductions", "kit.OPTIONS"],
     "asking": "baseline", "waiting": false, "matching_optimization": false,
     "computational_complexity": "O(a^2 * |SOFT|) per match phase",
     "implementation_status": "pending",
     "known_risks": "Rank correlates strongly with m04 (flagged as partial redundancy for retention diagnostics).",
     "literature_inspiration": "Harmonic-mean aggregation for symmetric fit (penalizes asymmetry).",
     "file": "methods_a.py", "decide_function": "decide_m05"},
    {"method_id": "m06_bottleneck", "name": "Bottleneck compatibility", "group": "A",
     "mechanism": "score = min over the 4 REL fields of (1 equal / 0 unequal when both observed, prior 1/|OPTIONS[k]| when either missing); greedy take.",
     "required_inputs": ["state.members", "state.introductions", "kit.OPTIONS"],
     "asking": "baseline", "waiting": false, "matching_optimization": false,
     "computational_complexity": "O(a^2 * 4) per match phase",
     "implementation_status": "pending",
     "known_risks": "Only REL fields decide rank; coarse ties when REL coverage is low.",
     "literature_inspiration": "Weakest-link / bottleneck compatibility (prioritizing the weakest important dimension).",
     "file": "methods_a.py", "decide_function": "decide_m06"},
    {"method_id": "m07_prune_and_greedy", "name": "Prune-and-greedy", "group": "A",
     "mechanism": "Drop candidate pairs whose observed soft agreement is below PRUNE_MIN_SCORE=2, then greedy take on survivors using base score.",
     "required_inputs": ["state.members", "state.introductions"],
     "asking": "baseline", "waiting": false, "matching_optimization": false,
     "computational_complexity": "O(a^2) per match phase",
     "implementation_status": "pending",
     "known_risks": "Cutoff constant frozen pre-tournament; may reduce introductions when coverage is sparse.",
     "literature_inspiration": "Prune-and-greedy (Gravin, Tang, Wang: pruned search heuristics for online matching).",
     "substituted_from": "m07_match_count_symmetric: symmetric observed-soft count yields the identical ordering to greedy control by construction - honestly impossible to distinguish, replaced per spec Section 3.",
     "file": "methods_a.py", "decide_function": "decide_m07"},
    {"method_id": "m08_weighted_compatibility", "name": "Weighted compatibility score", "group": "A",
     "mechanism": "Static structure-only weights w_k = 1 - 1/|OPTIONS[k]| from kit.OPTIONS cardinalities; score = sum w_k*(1 equal / 0 unequal when both observed; w_k*p_k when exactly one observed; 0 both missing); greedy take.",
     "required_inputs": ["state.members", "state.introductions", "kit.OPTIONS"],
     "asking": "baseline", "waiting": false, "matching_optimization": false,
     "computational_complexity": "O(a^2 * |SOFT|) per match phase",
     "implementation_status": "pending",
     "known_risks": "Prior-fill terms may dominate ranking on cold_start (low coverage); no outcome fitting is used by design.",
     "literature_inspiration": "Principled field-discrimination weighting; analogous to static thresholds derived from visible option distributions.",
     "file": "methods_a.py", "decide_function": "decide_m08"},

    {"method_id": "m09_partner_scarcity", "name": "Partner scarcity", "group": "B",
     "mechanism": "score = base / max(1, min(deg_a, deg_b)) where deg = member's feasible degree in today's graph; rescues scarce members.",
     "required_inputs": ["state.members", "state.introductions"],
     "asking": "baseline", "waiting": false, "matching_optimization": false,
     "computational_complexity": "O(a^2) per match phase",
     "implementation_status": "pending",
     "known_risks": "Degree distributions differ sharply per variant; may over-rescue on sparse.",
     "literature_inspiration": "Degree-aware matching / scarce-partner preference in queueing with degree-aware admission.",
     "file": "methods_b.py", "decide_function": "decide_m09"},
    {"method_id": "m10_degree_balanced", "name": "Degree-balanced matching", "group": "B",
     "mechanism": "score = base / max(1, max(deg_a, deg_b)); penalizes consuming members who have many alternatives.",
     "required_inputs": ["state.members", "state.introductions"],
     "asking": "baseline", "waiting": false, "matching_optimization": false,
     "computational_complexity": "O(a^2) per match phase",
     "implementation_status": "pending",
     "known_risks": "Opposite bias to m09; both may suppress total introductions (guardrail metrics report this).",
     "literature_inspiration": "Opportunity-cost degree balancing (value members relative to outside options).",
     "file": "methods_b.py", "decide_function": "decide_m10"},
    {"method_id": "m11_scarcity_x_compat", "name": "Scarcity x compatibility", "group": "B",
     "mechanism": "score = base * 2/(deg_a + deg_b); multiplicative product of pair quality with average scarcity.",
     "required_inputs": ["state.members", "state.introductions"],
     "asking": "baseline", "waiting": false, "matching_optimization": false,
     "computational_complexity": "O(a^2) per match phase",
     "implementation_status": "pending",
     "known_risks": "Near-monotone with m09 in practice (flagged as redundancy risk for retention diagnostics).",
     "literature_inspiration": "Scarcity-weighted quality scoring (product form).",
     "file": "methods_b.py", "decide_function": "decide_m11"},
    {"method_id": "m12_regret_score", "name": "Regret score", "group": "B",
     "mechanism": "score = base - max(0, alt_a - base) - max(0, alt_b - base) where alt_m = m's best other feasible edge score today.",
     "required_inputs": ["state.members", "state.introductions"],
     "asking": "baseline", "waiting": false, "matching_optimization": false,
     "computational_complexity": "O(a^2) per match phase",
     "implementation_status": "pending",
     "known_risks": "Only the top alternative counts; many moderate options are ignored.",
     "literature_inspiration": "Regret / opportunity-cost matching (waiting-loss accounting for both endpoints).",
     "file": "methods_b.py", "decide_function": "decide_m12"},
    {"method_id": "m13_opportunity_cost", "name": "Opportunity-cost score", "group": "B",
     "mechanism": "score = base - max(gap_a, gap_b); conservative single-side second-best comparison.",
     "required_inputs": ["state.members", "state.introductions"],
     "asking": "baseline", "waiting": false, "matching_optimization": false,
     "computational_complexity": "O(a^2) per match phase",
     "implementation_status": "pending",
     "known_risks": "Suppresses strong pairs when one endpoint has a strong alternative (may trade MSMI for coverage).",
     "literature_inspiration": "Second-best alternative comparison (opportunity cost of consuming a member).",
     "file": "methods_b.py", "decide_function": "decide_m13"},
    {"method_id": "m14_mutual_regret", "name": "Mutual regret", "group": "B",
     "mechanism": "score = base - min(gap_a, gap_b); penalizes only when both endpoints have waiting alternatives.",
     "required_inputs": ["state.members", "state.introductions"],
     "asking": "baseline", "waiting": false, "matching_optimization": false,
     "computational_complexity": "O(a^2) per match phase",
     "implementation_status": "pending",
     "known_risks": "Weak penalty when only one side is scarce; correlates with m13 on dense pools.",
     "literature_inspiration": "Mutual (both-sides) opportunity-cost combination.",
     "file": "methods_b.py", "decide_function": "decide_m14"},
    {"method_id": "m15_reserve_high_option", "name": "Reserve high-option-value members", "group": "B",
     "mechanism": "score = base - (cnt_a + cnt_b) where cnt_m = count of m's other feasible edges with base >= STRONG_SCORE=3.",
     "required_inputs": ["state.members", "state.introductions"],
     "asking": "baseline", "waiting": false, "matching_optimization": false,
     "computational_complexity": "O(a^2) per match phase",
     "implementation_status": "pending",
     "known_risks": "Count-based rule overlaps m28 blocked-value accounting (flagged as redundancy risk).",
     "literature_inspiration": "Reservation of high-option members (avoid consuming members with many strong alternatives).",
     "file": "methods_b.py", "decide_function": "decide_m15"},

    {"method_id": "m16_patient_policy", "name": "Patient policy", "group": "C",
     "mechanism": "Wait when quality is weak: keep only pairs with base >= PATIENT_MIN_SCORE=3 (at least 3 of the 7 observed soft fields - the suite strong-alignment cutoff, same constant as STRONG_SCORE), then greedy take.",
     "required_inputs": ["state.members", "state.introductions"],
     "asking": "baseline", "waiting": true, "matching_optimization": false,
     "computational_complexity": "O(a^2) per match phase",
     "implementation_status": "pending",
     "known_risks": "Adapted WITHOUT departure signals; Akbarpour et al. show patient wins require them - may idle too much (zero-selection days diagnose this).",
     "literature_inspiration": "Patient vs greedy matching (Akbarpour, Eeckhout, Lerman, Milton, JPE 2020), adapted to a quality gate since exit_day is unobservable.",
     "file": "methods_c.py", "decide_function": "decide_m16"},
    {"method_id": "m17_daily_quota", "name": "Daily quota policy", "group": "C",
     "mechanism": "Greedy take, then keep only the top ceil(n/QUOTA_DIVISOR) = ceil(n/2) selected pairs (QUOTA_DIVISOR=2); withheld pairs remain available for later days.",
     "required_inputs": ["state.members", "state.introductions"],
     "asking": "baseline", "waiting": true, "matching_optimization": false,
     "computational_complexity": "O(a^2) per match phase",
     "implementation_status": "pending",
     "known_risks": "Half-throughput days interact badly with a fixed 60-day horizon if late days are thin.",
     "literature_inspiration": "Batching / controlled clearing (Eom & Toriello 2026: batching and greedy near-optimal in two-sided matching).",
     "file": "methods_c.py", "decide_function": "decide_m17"},
    {"method_id": "m18_time_threshold", "name": "Time-dependent acceptance threshold", "group": "C",
     "mechanism": "Gate: keep pairs with base >= max(1, TIME_T0 - day//TIME_STEP); equals 4 on days 0-19, 3 on 20-39, 2 on 40-59.",
     "required_inputs": ["state.members", "state.introductions", "state.day"],
     "asking": "baseline", "waiting": true, "matching_optimization": false,
     "computational_complexity": "O(a^2) per match phase",
     "implementation_status": "pending",
     "known_risks": "Late-horizon laxness may admit weak pairs; all constants frozen pre-tournament.",
     "literature_inspiration": "Time-decreasing acceptance thresholds (dual/delay-cost threshold policies in online matching).",
     "file": "methods_c.py", "decide_function": "decide_m18"},
    {"method_id": "m19_arrival_age", "name": "Arrival-age policy", "group": "C",
     "mechanism": "Greedy take ordered by primary key -max(wait_a, wait_b), then -base, then pair key: longest-waiting members matched first.",
     "required_inputs": ["state.members", "state.introductions", "state.day"],
     "asking": "baseline", "waiting": false, "matching_optimization": false,
     "computational_complexity": "O(a^2) per match phase",
     "implementation_status": "pending",
     "known_risks": "Priority may override strong pairs for old weak ones; reads only arrived_day (never exit_day).",
     "literature_inspiration": "Fairness / FCFS arrival-age priority in matchmaking and queue admission.",
     "file": "methods_c.py", "decide_function": "decide_m19"},
    {"method_id": "m20_new_arrival_protection", "name": "New-arrival protection", "group": "C",
     "mechanism": "Filter out any pair where min(wait_a, wait_b) < PROTECT_DAYS=3; greedy take on the rest (new members accumulate alternatives first).",
     "required_inputs": ["state.members", "state.introductions", "state.day"],
     "asking": "baseline", "waiting": true, "matching_optimization": false,
     "computational_complexity": "O(a^2) per match phase",
     "implementation_status": "pending",
     "known_risks": "Three-day grace constant frozen; reduces early-horizon throughput.",
     "literature_inspiration": "Exploration warm-up / new-arrival protection (bandit warm-up analogy).",
     "file": "methods_c.py", "decide_function": "decide_m20"},
    {"method_id": "m21_delay_cost_threshold", "name": "Delay-cost threshold", "group": "C",
     "mechanism": "Per-pair gate: keep if base >= max(0, DELAY_T0 - max(wait_a, wait_b)//DELAY_STEP); 4 for waits 0-14, 3 for 15-29, 2 for 30-44, 1 for 45-59, 0 afterwards; then greedy take.",
     "required_inputs": ["state.members", "state.introductions", "state.day"],
     "asking": "baseline", "waiting": true, "matching_optimization": false,
     "computational_complexity": "O(a^2) per match phase",
     "implementation_status": "pending",
     "known_risks": "Wait time is only a statistical proxy for remaining availability, not real expiration data.",
     "literature_inspiration": "Delay-cost threshold policies (Mari, Bernasconi, Baumann, Stoesser, Dilkina, AAMAS 2023).",
     "substituted_from": "m21_expiration_aware: requires exit_day, which is a banned unobservable input (spec Section 9) - replaced per spec Section 3.",
     "file": "methods_c.py", "decide_function": "decide_m21"},
    {"method_id": "m22_market_thickness", "name": "Market-thickness policy", "group": "C",
     "mechanism": "If today's average feasible degree 2E/V < THIN_AVG_DEG=2.0: match nothing (wait); otherwise full greedy.",
     "required_inputs": ["state.members", "state.introductions"],
     "asking": "baseline", "waiting": true, "matching_optimization": false,
     "computational_complexity": "O(a^2) per match phase",
     "implementation_status": "pending",
     "known_risks": "Binary all-day gate can idle entire days at degree just under the cutoff; no partial response.",
     "literature_inspiration": "Cost-balancing WHEN-to-match trigger (Liu, Zhang, Zhang, arXiv:2601.21858) and epsilon-proxy clearing (Kerimov et al.).",
     "file": "methods_c.py", "decide_function": "decide_m22"},
    {"method_id": "m23_hybrid_patient_greedy", "name": "Hybrid patient-greedy", "group": "C",
     "mechanism": "Favorable if max base >= HYBRID_MIN_SCORE=4 OR avg degree >= HYBRID_AVG_DEG=3.0: full greedy; otherwise match nothing (wait).",
     "required_inputs": ["state.members", "state.introductions"],
     "asking": "baseline", "waiting": true, "matching_optimization": false,
     "computational_complexity": "O(a^2) per match phase",
     "implementation_status": "pending",
     "known_risks": "OR-gate makes waiting rare (top score >= 4 happens most days); thresholds frozen pre-tournament.",
     "literature_inspiration": "Conditional patience: greedy under favorable conditions, wait under low opportunity density (Akbarpour et al.; Costabal et al. WHEN-to-match).",
     "file": "methods_c.py", "decide_function": "decide_m23"},

    {"method_id": "m24_max_cardinality", "name": "Maximum-cardinality-first matching", "group": "D",
     "mechanism": "Cardinality first: exact Kuhn augmenting-path maximum matching on the bipartite 2-coloring of today's feasible graph (adjacency sorted by -base then pair key as secondary preference); non-bipartite graphs fall back to greedy take plus length-3 augmenting exchanges (documented approximation).",
     "required_inputs": ["state.members", "state.introductions"],
     "asking": "baseline", "waiting": false, "matching_optimization": true,
     "computational_complexity": "O(V*E) Kuhn per match phase; fallback O(E * rounds)",
     "implementation_status": "pending",
     "known_risks": "Odd-cycle graphs take the approximate fallback (measured reachable: 5/90 fixture snapshots; forced by odd-cycle tests); secondary score preference is heuristic (adjacency order only); fallback mechanism overlaps m27 (flagged).",
     "literature_inspiration": "Maximum-cardinality bipartite matching (Kuhn/Hopcroft-Karp); cardinality-first allocation.",
     "file": "methods_d.py", "decide_function": "decide_m24"},
    {"method_id": "m25_max_weight", "name": "Maximum-weight matching", "group": "D",
     "mechanism": "Maximize total base-score weight: zero-score edges pruned (exact for value), Hungarian/Kuhn-Munkres O(n^3) when the graph is 2-colorable and node count <= HUNGARIAN_NODE_CAP=180; otherwise greedy take plus one-swap improvement (documented approximation).",
     "required_inputs": ["state.members", "state.introductions"],
     "asking": "baseline", "waiting": false, "matching_optimization": true,
     "computational_complexity": "O(n^3) Hungarian (n <= 180) else O(E * swaps)",
     "implementation_status": "pending",
     "known_risks": "Exact only for bipartite node count <= 180 (cap breaches measured reachable: 6/90 fixture snapshots); non-bipartite fallback shares logic with m26 (documented overlap); zero-score edge pruning leaves the weight objective exact but may reduce cardinality vs m24.",
     "literature_inspiration": "Maximum-weight assignment (Kuhn-Munkres); prophet-style value-maximizing allocation (Ezra et al.).",
     "file": "methods_d.py", "decide_function": "decide_m25"},
    {"method_id": "m26_greedy_one_swap", "name": "Greedy + one-swap improvement", "group": "D",
     "mechanism": "Greedy take, then repeat improving pair exchanges: replace (a,b)+(c,d) with (a,d)+(c,b) or (a,c)+(b,d) when both replacements are feasible, non-past, non-overlapping and strictly increase total base weight; iterate to local optimum (integer weights guarantee termination).",
     "required_inputs": ["state.members", "state.introductions"],
     "asking": "baseline", "waiting": false, "matching_optimization": true,
     "computational_complexity": "O(E^2) per pass, few passes",
     "implementation_status": "pending",
     "known_risks": "Local optimum only; O(p^2) with p = matched pairs (latency-tested).",
     "literature_inspiration": "Two-exchange local search on matchings (classic matching local improvement).",
     "file": "methods_d.py", "decide_function": "decide_m26"},
    {"method_id": "m27_greedy_augmenting", "name": "Greedy + augmenting-path improvement", "group": "D",
     "mechanism": "Greedy take, then short augmenting exchanges of length <= 3: if (x,x') is matched and free y adjacent to x and free z adjacent to x' exist with feasible edges, replace with (x',z)+(x,y), gaining +1 cardinality; loop until no gain (cap AUGMENT_ROUNDS_CAP=50).",
     "required_inputs": ["state.members", "state.introductions"],
     "asking": "baseline", "waiting": false, "matching_optimization": true,
     "computational_complexity": "O(rounds * E) per match phase",
     "implementation_status": "pending",
     "known_risks": "Length-3 only: not exact maximum cardinality (that is m24); spirit overlaps m24's non-bipartite fallback.",
     "literature_inspiration": "Berge augmenting paths; greedy + short augmenting exchange heuristics in online matching.",
     "file": "methods_d.py", "decide_function": "decide_m27"},
    {"method_id": "m28_conflict_aware", "name": "Conflict-aware greedy", "group": "D",
     "mechanism": "score = 3*base - pool_a - pool_b where pool_m = sum of base over all feasible edges incident to m (blocked-alternative value accounting; pools include the current pair).",
     "required_inputs": ["state.members", "state.introductions"],
     "asking": "baseline", "waiting": false, "matching_optimization": false,
     "computational_complexity": "O(a^2) per match phase",
     "implementation_status": "pending",
     "known_risks": "Pool sums can dominate base on dense variants; ranking overlaps degree-based m09/m10 (flagged as redundancy risk).",
     "literature_inspiration": "Conflict-aware greedy: adjust scores by the value of alternatives blocked by consuming both endpoints (auction/conflict heuristics).",
     "file": "methods_d.py", "decide_function": "decide_m28"},

    {"method_id": "m29_uncertainty_aware", "name": "Uncertainty-aware policy", "group": "E",
     "mechanism": "Active asking: hard-constraint asks first but capped to keep SOFT_ASK_RESERVE=3 budget units for soft fields; soft asks ranked by information value = number of incident feasible edges whose partner already has that field observed (immediately resolvable comparisons); ask highest value first, never declined fields. Match phase = baseline_match on the refreshed state.",
     "required_inputs": ["state.members", "state.introductions", "state.ask_budget_remaining", "kit.OPTIONS"],
     "asking": "active", "waiting": false, "matching_optimization": false,
     "computational_complexity": "O(a^2 * |SOFT|) ask scoring; O(a^2) match",
     "implementation_status": "pending",
     "known_risks": "Value counts only one-sided-resolvable edges; may under-ask when both sides miss the same field; SOFT_ASK_RESERVE trades one constraints bundle per day (3 vs the control's 4) for soft coverage - reported as secondary ask cost, never ranked.",
     "literature_inspiration": "Active preference elicitation / match-sensitive active learning (Charlin et al., ICML 2012); bandit matching with costly interviews.",
     "file": "methods_e.py", "decide_function": "decide_m29"},
    {"method_id": "m30_targeted_info", "name": "Targeted information policy", "group": "E",
     "mechanism": "VoI gate: hard-constraint asks first but capped to keep SOFT_ASK_RESERVE=3 budget units; then for each soft candidate (available member with unobserved non-declined field, sorted by member_id, field): enumerate kit.OPTIONS[k] truth-blind and ask only if at least one option changes today's greedy allocation (incident-edge score recomputation + greedy_take); budget-bounded. Match phase = baseline_match on the refreshed state.",
     "required_inputs": ["state.members", "state.introductions", "state.ask_budget_remaining", "kit.OPTIONS"],
     "asking": "active", "waiting": false, "matching_optimization": false,
     "computational_complexity": "O(c * |OPTIONS| * (deg + E log E)) VoI gate, c = soft candidates evaluated",
     "implementation_status": "pending",
     "known_risks": "Up to |OPTIONS| greedy passes per candidate, hard-capped at VOI_EVAL_CAP=96 recomputations per ask phase in fixed enumeration order (worst-case fixture-tested); measured workload <= ~800 soft-not-asked pairs/day on <= 18-edge graphs; SOFT_ASK_RESERVE trades one constraints bundle per day (3 vs 4); gate compares allocations, never truth.",
     "literature_inspiration": "Value-of-information targeted clarification (VoI gate pattern validated in research/e3_rel_experiment E1); active learning without hidden state.",
     "file": "methods_e.py", "decide_function": "decide_m30"}
  ]
}
```
```powershell
python -c "import json,pathlib; d=json.loads(pathlib.Path(r'research/method_tournament/methods.json').read_text(encoding='utf-8')); assert len(d['methods'])==30; print('30 entries OK')"
```

- [ ] **Step 5: Run tests; expect only the design test failing**

Run: `python -m unittest research.method_tournament.test_tournament -v`
Expected: `test_thirty_entries_numbered_m01_to_m30`, `test_required_fields_and_types`,
`test_group_counts`, `test_substitutions_documented` PASS; `test_design_lists_every_method`
FAILS with `FileNotFoundError: ... design.md` (not written yet).

- [ ] **Step 6: Write `design.md` (the preregistration the whole tournament obeys)**

Create `research/method_tournament/design.md` with exactly this content:

```markdown
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
```

- [ ] **Step 7: Run the full test module; expect all green**

Run: `python -m unittest research.method_tournament.test_tournament -v`
Expected: 6 tests PASS (registry schema x5 + design coverage).

- [ ] **Step 8: Log the milestone**

```powershell
Add-Content -Path research\method_tournament\run_log.txt -Value ("{0} Task1 complete: methods.json (30) + design.md preregistered" -f (Get-Date -Format o))
```

No commit (spec Section 14).

---
### Task 2: Shared State Helpers (common.py)

**Files:**
- Create: `research/method_tournament/common.py`
- Test: append classes to `research/method_tournament/test_tournament.py` (before the `if __name__ == '__main__':` block)

**Interfaces:**
- Consumes: `kit` public API (`SOFT`, `OPTIONS`, `eligibility`, `baseline_asks`, `baseline_match`), `state` shape from `kit.Simulator.observe()` (keys: `day, ask_budget_remaining, members, introductions, feedback, ask_log`).
- Produces (used by Tasks 3-9):
  - `pair_key(a: str, b: str) -> tuple[str, str]` (sorted)
  - `member_map(state) -> dict[str, dict]`
  - `past_pairs(state) -> set[tuple[str, str]]`
  - `base_score(a: dict, b: dict) -> int` (observed soft-field agreement count, identical formula to `kit.baseline_match`)
  - `feasible_edges(state, members=None) -> list[tuple[str, str, int]]` sorted by member id
  - `wait_days(m: dict, day: int) -> int`
  - `directional(a: dict, b: dict) -> float`
  - `alt_for(ctx: dict, m: str, other: str) -> int`
  - `make_ctx(state, edges=None) -> dict` with keys `state, day, members, edges, deg, inc, n_avail, avg_deg, max_base`
  - Frozen constants: `REL, PROTECT_DAYS, QUOTA_DIVISOR, PATIENT_MIN_SCORE, TIME_T0, TIME_STEP, DELAY_T0, DELAY_STEP, THIN_AVG_DEG, HYBRID_MIN_SCORE, HYBRID_AVG_DEG, STRONG_SCORE, PRUNE_MIN_SCORE, HUNGARIAN_NODE_CAP, AUGMENT_ROUNDS_CAP, SOFT_ASK_RESERVE, VOI_EVAL_CAP`

- [ ] **Step 1: Append the failing tests**

Append `CommonHelperTests` and `FrozenConstantsTests` to `test_tournament.py`:

```python
class CommonHelperTests(unittest.TestCase):
    @staticmethod
    def _state(seed=90210, variant='development', day=30):
        from kit import Simulator, generate, baseline_asks, baseline_match
        sim = Simulator(generate(seed, 200, 'evaluation', variant))
        for _ in range(day):
            sim.resolve_asks(baseline_asks(sim.observe()))
            sim.advance(baseline_match(sim.observe()))
        return sim.observe()

    def test_feasible_edges_covers_every_baseline_pair(self):
        import common
        from kit import baseline_match
        state = self._state()
        edge_keys = {common.pair_key(a, b) for a, b, s in common.feasible_edges(state)}
        for pair in baseline_match(state):
            self.assertIn(common.pair_key(*pair), edge_keys)

    def test_base_score_matches_kit_formula(self):
        import common
        from kit import SOFT
        state = self._state()
        avail = [m for m in state['members'] if m['available']]
        a, b = avail[0], avail[1]
        expected = sum(a['fields'].get(k) is not None and a['fields'].get(k) == b['fields'].get(k)
                       for k in SOFT)
        self.assertEqual(common.base_score(a, b), expected)

    def test_directional_is_asymmetric_on_missingness(self):
        import common
        from kit import SOFT
        full_a = {k: None for k in SOFT}
        full_b = {k: None for k in SOFT}
        full_a['relationship_goal'] = 'long_term'
        full_a['relationship_pace'] = 'slow'
        full_b['relationship_goal'] = 'long_term'
        self.assertGreater(common.directional(full_a, full_b), common.directional(full_b, full_a))

    def test_ctx_degrees_and_avg(self):
        import common
        state = self._state(day=0)
        ctx = common.make_ctx(state)
        total_deg = sum(ctx['deg'].values())
        self.assertEqual(total_deg, 2 * len(ctx['edges']))
        n_avail = sum(1 for m in state['members'] if m['available'])
        self.assertEqual(ctx['n_avail'], n_avail)
        self.assertAlmostEqual(ctx['avg_deg'], 2.0 * len(ctx['edges']) / max(1, n_avail))

    def test_alt_for_excludes_current_partner(self):
        import common
        state = self._state(day=10)
        ctx = common.make_ctx(state)
        a, b, s = ctx['edges'][0]
        alt = common.alt_for(ctx, a, b)
        others = [sc for sc, o in ctx['inc'][a] if o != b]
        self.assertEqual(alt, max(others) if others else 0)

    def test_wait_days(self):
        import common
        self.assertEqual(common.wait_days({'arrived_day': 7}, 10), 3)


class FrozenConstantsTests(unittest.TestCase):
    def test_design_constants_frozen_common(self):
        import common
        self.assertEqual(common.REL, ('relationship_goal', 'relationship_pace',
                                      'lifestyle', 'conversations'))
        self.assertEqual(common.PROTECT_DAYS, 3)
        self.assertEqual(common.QUOTA_DIVISOR, 2)
        self.assertEqual(common.PATIENT_MIN_SCORE, 3)
        self.assertEqual((common.TIME_T0, common.TIME_STEP), (4, 20))
        self.assertEqual((common.DELAY_T0, common.DELAY_STEP), (4, 15))
        self.assertEqual(common.THIN_AVG_DEG, 2.0)
        self.assertEqual(common.HYBRID_MIN_SCORE, 4)
        self.assertEqual(common.HYBRID_AVG_DEG, 3.0)
        self.assertEqual(common.STRONG_SCORE, 3)
        self.assertEqual(common.PRUNE_MIN_SCORE, 2)
        self.assertEqual(common.HUNGARIAN_NODE_CAP, 180)
        self.assertEqual(common.AUGMENT_ROUNDS_CAP, 50)
        self.assertEqual(common.SOFT_ASK_RESERVE, 3)
        self.assertEqual(common.VOI_EVAL_CAP, 96)
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m unittest research.method_tournament.test_tournament -v`
Expected: new tests FAIL with `ModuleNotFoundError: No module named 'common'`; Task 1 tests still PASS.

- [ ] **Step 3: Write `common.py`**

```python
"""Shared visible-state helpers for tournament methods. Stdlib + kit only.

Constants are FROZEN per design.md section 6; FrozenConstantsTests pins their values.
All iteration here is sorted: no PYTHONHASHSEED is set, so order must never depend on
set/dict hashing.
"""
from kit import SOFT, OPTIONS, eligibility

# Frozen constants (design.md section 6) -------------------------------------
REL = ('relationship_goal', 'relationship_pace', 'lifestyle', 'conversations')
PROTECT_DAYS = 3
QUOTA_DIVISOR = 2
PATIENT_MIN_SCORE = 3
TIME_T0, TIME_STEP = 4, 20
DELAY_T0, DELAY_STEP = 4, 15
THIN_AVG_DEG = 2.0
HYBRID_MIN_SCORE = 4
HYBRID_AVG_DEG = 3.0
STRONG_SCORE = 3
PRUNE_MIN_SCORE = 2
HUNGARIAN_NODE_CAP = 180
AUGMENT_ROUNDS_CAP = 50
SOFT_ASK_RESERVE = 3
VOI_EVAL_CAP = 96


def pair_key(a, b):
    return tuple(sorted((a, b)))


def member_map(state):
    return {m['member_id']: m for m in state['members']}


def past_pairs(state):
    return {pair_key(i['user_a'], i['user_b']) for i in state['introductions']}


def base_score(a, b):
    """Observed soft-field agreement count (identical formula to kit.baseline_match)."""
    return sum(a['fields'].get(k) is not None and a['fields'].get(k) == b['fields'].get(k)
               for k in SOFT)


def wait_days(m, day):
    return day - m['arrived_day']


def feasible_edges(state, members=None):
    """[(id_a, id_b, base)] for available, feasible, never-introduced pairs.
    Same graph kit.baseline_match enumerates; sorted by member id for determinism."""
    ms = members if members is not None else [m for m in state['members'] if m['available']]
    ms = sorted(ms, key=lambda m: m['member_id'])
    past = past_pairs(state)
    out = []
    for i, a in enumerate(ms):
        for b in ms[i + 1:]:
            if pair_key(a['member_id'], b['member_id']) in past:
                continue
            if eligibility(a, b)['status'] != 'feasible':
                continue
            out.append((a['member_id'], b['member_id'], base_score(a, b)))
    return out


def directional(a, b):
    """d(a->b): sum over SOFT fields a observed; equal=1, unequal=0,
    missing on b credited the uniform prior 1/|OPTIONS[k]|. Asymmetric by design."""
    total = 0.0
    for k in SOFT:
        av = a['fields'].get(k)
        if av is None:
            continue
        bv = b['fields'].get(k)
        if bv is None:
            total += 1.0 / len(OPTIONS[k])
        elif av == bv:
            total += 1.0
    return total


def make_ctx(state, edges=None):
    """Per-day context shared by every method: edges, degrees, sorted incident lists."""
    if edges is None:
        edges = feasible_edges(state)
    mfs = member_map(state)
    deg = {}
    inc = {}
    for a, b, s in edges:
        deg[a] = deg.get(a, 0) + 1
        deg[b] = deg.get(b, 0) + 1
        inc.setdefault(a, []).append((s, b))
        inc.setdefault(b, []).append((s, a))
    for m in inc:
        inc[m].sort(key=lambda t: (-t[0], t[1]))
    n_avail = sum(1 for m in state['members'] if m['available'])
    return {'state': state, 'day': state['day'], 'members': mfs, 'edges': edges,
            'deg': deg, 'inc': inc, 'n_avail': n_avail,
            'avg_deg': (2.0 * len(edges) / n_avail) if n_avail else 0.0,
            'max_base': max((s for _, _, s in edges), default=0)}


def alt_for(ctx, m, other):
    """Best base score of m's other feasible partners today (0 when none)."""
    for s, o in ctx['inc'].get(m, ()):
        if o != other:
            return s
    return 0
```

- [ ] **Step 4: Run to verify green**

Run: `python -m unittest research.method_tournament.test_tournament -v`
Expected: all tests PASS (Task 1's 6 + Task 2's 7).

- [ ] **Step 5: Log the milestone**

```powershell
Add-Content -Path research\method_tournament\run_log.txt -Value ("{0} Task2 complete: common.py helpers + frozen constants pinned" -f (Get-Date -Format o))
```

No commit (spec Section 14).

---
### Task 3: Allocation Core - Greedy Take and Temporal Gates (alloc.py, part 1)

**Files:**
- Create: `research/method_tournament/alloc.py`
- Test: append `AllocGreedyTests` to `test_tournament.py`

**Interfaces:**
- Consumes: `common.pair_key`, `common` frozen constants, `state` fixture helper from `CommonHelperTests._state`.
- Produces (used by Tasks 5-9):
  - `greedy_take(edges: list[tuple[str,str,int]]) -> list[list[str]]` - exactly `kit.baseline_match` ordering
  - `take_ordered(edges, key_fn) -> list[list[str]]` - same non-overlap scan under a custom sort key
  - `filter_min_score(edges, minimum) -> list[tuple]`
  - `quota_half(pairs) -> list[list[str]]` - keeps `ceil(n / QUOTA_DIVISOR)`
  - `protect_filter(edges, ctx) -> list[tuple]` - drops pairs touching members with `wait < PROTECT_DAYS`
  - `thin_wait(ctx) -> bool`, `hybrid_favorable(ctx) -> bool`

- [ ] **Step 1: Append the failing tests**

Append `AllocGreedyTests`:

```python
class AllocGreedyTests(unittest.TestCase):
    @staticmethod
    def _state(seed=90210, variant='development', day=30):
        from kit import Simulator, generate, baseline_asks, baseline_match
        sim = Simulator(generate(seed, 200, 'evaluation', variant))
        for _ in range(day):
            sim.resolve_asks(baseline_asks(sim.observe()))
            sim.advance(baseline_match(sim.observe()))
        return sim.observe()

    def test_greedy_take_identical_to_kit_baseline_match(self):
        import common, alloc
        from kit import baseline_match
        state = self._state()
        self.assertEqual(alloc.greedy_take(common.feasible_edges(state)),
                         baseline_match(state))

    def test_greedy_take_matches_kit_across_fixture_matrix(self):
        # F-05: seeds {90210, 90211} x 6 variants x days {0,1,5,15,30,45,59}
        import common, alloc
        from kit import Simulator, generate, baseline_asks, baseline_match
        checked = 0
        for seed in (90210, 90211):
            for variant in ('development', 'sparse', 'cold_start',
                            'delayed', 'shift', 'drift'):
                sim = Simulator(generate(seed, 200, 'evaluation', variant))
                for day in range(60):
                    if day in (0, 1, 5, 15, 30, 45, 59):
                        state = sim.observe()
                        self.assertEqual(
                            alloc.greedy_take(common.feasible_edges(state)),
                            baseline_match(state), (seed, variant, day))
                        checked += 1
                    sim.resolve_asks(baseline_asks(sim.observe()))
                    sim.advance(baseline_match(sim.observe()))
        self.assertEqual(checked, 2 * 6 * 7)

    def test_greedy_take_is_order_invariant(self):
        import common, alloc
        state = self._state()
        reversed_state = dict(state)
        reversed_state['members'] = list(reversed(state['members']))
        self.assertEqual(alloc.greedy_take(common.feasible_edges(state)),
                         alloc.greedy_take(common.feasible_edges(reversed_state)))

    def test_take_ordered_respects_primary_key(self):
        import alloc
        edges = [('a', 'b', 5), ('c', 'd', 1)]
        key_fn = lambda e: (-(9 if e[0] == 'c' else 1), -e[2])
        self.assertEqual(alloc.take_ordered(edges, key_fn), [['c', 'd'], ['a', 'b']])

    def test_filter_min_score(self):
        import alloc
        edges = [('a', 'b', 5), ('c', 'd', 2)]
        self.assertEqual(alloc.filter_min_score(edges, 3), [('a', 'b', 5)])

    def test_quota_half_ceiling(self):
        import alloc
        five = [[str(i), 'x'] for i in range(5)]
        four = [[str(i), 'x'] for i in range(4)]
        self.assertEqual(alloc.quota_half(five), five[:3])
        self.assertEqual(alloc.quota_half(four), four[:2])
        self.assertEqual(alloc.quota_half([]), [])

    def test_protect_filter_drops_new_arrivals(self):
        import alloc
        ctx = {'day': 10, 'members': {
            'a': {'arrived_day': 9}, 'b': {'arrived_day': 0},
            'c': {'arrived_day': 8}, 'd': {'arrived_day': 1}}}
        self.assertEqual(alloc.protect_filter([('a', 'b', 5), ('c', 'd', 5)], ctx), [])
        self.assertEqual(alloc.protect_filter([('b', 'd', 5)], ctx), [('b', 'd', 5)])

    def test_thin_and_hybrid_gates(self):
        import alloc
        self.assertTrue(alloc.thin_wait({'avg_deg': 1.9}))
        self.assertFalse(alloc.thin_wait({'avg_deg': 2.0}))
        self.assertTrue(alloc.hybrid_favorable({'max_base': 4, 'avg_deg': 0.0}))
        self.assertTrue(alloc.hybrid_favorable({'max_base': 1, 'avg_deg': 3.0}))
        self.assertFalse(alloc.hybrid_favorable({'max_base': 3, 'avg_deg': 2.9}))
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m unittest research.method_tournament.test_tournament -v`
Expected: 7 new tests FAIL with `ModuleNotFoundError: No module named 'alloc'`.

- [ ] **Step 3: Write `alloc.py` (part 1)**

```python
"""Allocation primitives: greedy take and temporal gates.

Constants are FROZEN per design.md section 6. Graph algorithms (Kuhn, Hungarian,
one-swap, augmenting) are added by Task 4 in the same file.
"""
from common import (pair_key, wait_days, QUOTA_DIVISOR, PROTECT_DAYS, THIN_AVG_DEG,
                    HYBRID_MIN_SCORE, HYBRID_AVG_DEG)


def _take(ordered):
    used = set()
    out = []
    for a, b in ordered:
        if a in used or b in used:
            continue
        out.append([a, b])
        used.add(a)
        used.add(b)
    return out


def greedy_take(edges):
    """Sort by (-score, pair_key) then take non-overlapping: identical to kit.baseline_match."""
    ordered = [(a, b) for a, b, s in sorted(edges, key=lambda e: (-e[2], pair_key(e[0], e[1])))]
    return _take(ordered)


def take_ordered(edges, key_fn):
    """Same non-overlap scan under a caller-supplied deterministic sort key."""
    ordered = [(a, b) for a, b, s in sorted(edges, key=key_fn)]
    return _take(ordered)


def filter_min_score(edges, minimum):
    return [e for e in edges if e[2] >= minimum]


def quota_half(pairs):
    """Keep ceil(n / QUOTA_DIVISOR) pairs; withheld pairs stay available for later days."""
    n_keep = (len(pairs) + QUOTA_DIVISOR - 1) // QUOTA_DIVISOR
    return pairs[:n_keep]


def protect_filter(edges, ctx):
    day, mfs = ctx['day'], ctx['members']
    return [e for e in edges
            if min(wait_days(mfs[e[0]], day), wait_days(mfs[e[1]], day)) >= PROTECT_DAYS]


def thin_wait(ctx):
    """m22: today's graph is thin -> wait (match nothing)."""
    return ctx['avg_deg'] < THIN_AVG_DEG


def hybrid_favorable(ctx):
    """m23: strong top pair OR dense graph -> greedy now."""
    return ctx['max_base'] >= HYBRID_MIN_SCORE or ctx['avg_deg'] >= HYBRID_AVG_DEG
```

- [ ] **Step 4: Run to verify green**

Run: `python -m unittest research.method_tournament.test_tournament -v`
Expected: all tests PASS (previous 13 + new 8 = 21).

- [ ] **Step 5: Log the milestone**

```powershell
Add-Content -Path research\method_tournament\run_log.txt -Value ("{0} Task3 complete: alloc.py greedy+gates; greedy_take == kit.baseline_match" -f (Get-Date -Format o))
```

No commit (spec Section 14).

---
### Task 4: Graph Algorithms (alloc.py, part 2)

**Files:**
- Modify: `research/method_tournament/alloc.py` (append graph section)
- Test: append `AllocGraphTests` to `test_tournament.py`

**Interfaces:**
- Consumes: `common.pair_key`, `common.HUNGARIAN_NODE_CAP`.
- Produces (used by Tasks 8-9):
  - `two_color(edges) -> (left, right) | None` - deterministic BFS 2-coloring
  - `max_cardinality(edges) -> list[list[str]] | None` - exact Kuhn on bipartite graphs; `None` when odd cycles exist (caller falls back)
  - `hungarian_max_weight(left, right, weight) -> list[tuple[str, str]]` - exact O(n^3) max-weight assignment; `weight` maps BOTH `(u,v)` and `(v,u)` to int scores; zero/absent weights are filtered from the result (exact for value)
  - `one_swap_improve(pairs, edges) -> list[list[str]]` - local search, terminating (integer weights)
  - `augment3_improve(pairs, edges) -> list[list[str]]` - length-3 augmenting exchanges, capped by `AUGMENT_ROUNDS_CAP`
  - `brute_max_weight(edges) -> (pairs, total)` - exhaustive reference for tests only (n <= 8)

- [ ] **Step 1: Append the failing tests**

Append `AllocGraphTests`:

```python
class AllocGraphTests(unittest.TestCase):
    @staticmethod
    def _random_edges(rng, n_nodes=6, p=0.6):
        import string
        nodes = [string.ascii_lowercase[i] for i in range(n_nodes)]
        return [(nodes[i], nodes[j], rng.randint(0, 7))
                for i in range(n_nodes) for j in range(i + 1, n_nodes)
                if rng.random() < p]

    @staticmethod
    def _weight_total(pairs, edges):
        import common
        w = {common.pair_key(a, b): s for a, b, s in edges}
        return sum(w[common.pair_key(x, y)] for x, y in pairs)

    def test_two_color_bipartite_and_odd_cycle(self):
        import alloc
        self.assertIsNotNone(alloc.two_color([('a', 'b', 1), ('b', 'c', 1), ('c', 'd', 1)]))
        self.assertIsNone(alloc.two_color([('a', 'b', 1), ('b', 'c', 1), ('c', 'a', 1)]))
        self.assertEqual(alloc.two_color([]), ([], []))

    def test_max_cardinality_equals_brute_on_random_bipartite(self):
        import alloc, random
        rng = random.Random(7)
        for _ in range(25):
            left = ['l%d' % i for i in range(3)]
            right = ['r%d' % i for i in range(3)]
            edges = [(u, v, rng.randint(0, 7)) for u in left for v in right
                     if rng.random() < 0.5]
            got = alloc.max_cardinality(edges)
            self.assertIsNotNone(got)
            want = alloc.brute_max_weight([(a, b, 1) for a, b, s in edges])
            self.assertEqual(len(got), want[1])
            ids = [m for p in got for m in p]
            self.assertEqual(len(ids), len(set(ids)))

    def test_hungarian_equals_brute_on_random_bipartite(self):
        import alloc, random
        rng = random.Random(11)
        for _ in range(25):
            left = ['l%d' % i for i in range(4)]
            right = ['r%d' % i for i in range(4)]
            weight = {}
            for u in left:
                for v in right:
                    if rng.random() < 0.5:
                        w = rng.randint(1, 7)
                        weight[(u, v)] = w
                        weight[(v, u)] = w
            pairs = alloc.hungarian_max_weight(left, right, weight)
            total = sum(weight[p] for p in pairs)
            edges = [(u, v, w) for (u, v), w in weight.items() if u < v]
            self.assertEqual(total, alloc.brute_max_weight(edges)[1])

    def test_max_cardinality_none_on_odd_cycle(self):
        import alloc
        self.assertIsNone(alloc.max_cardinality([('a', 'b', 1), ('b', 'c', 1), ('c', 'a', 1)]))

    def test_one_swap_improves_or_holds_and_idempotent(self):
        import alloc, random
        rng = random.Random(3)
        edges = self._random_edges(rng, 6, 0.6)
        base = alloc.greedy_take(edges)
        once = alloc.one_swap_improve(base, edges)
        twice = alloc.one_swap_improve(once, edges)
        self.assertGreaterEqual(self._weight_total(once, edges), self._weight_total(base, edges))
        self.assertEqual(twice, once)

    def test_augment3_grows_cardinality_without_overlap(self):
        import alloc, random
        rng = random.Random(5)
        edges = self._random_edges(rng, 6, 0.6)
        base = alloc.greedy_take(edges)
        grown = alloc.augment3_improve(base, edges, 50)
        self.assertGreaterEqual(len(grown), len(base))
        ids = [m for p in grown for m in p]
        self.assertEqual(len(ids), len(set(ids)))

    def test_hungarian_latency_on_dense_day59(self):
        import alloc, common, time
        from kit import Simulator, generate, baseline_asks, baseline_match
        sim = Simulator(generate(90215, 200, 'evaluation', 'development'))
        for _ in range(59):
            sim.resolve_asks(baseline_asks(sim.observe()))
            sim.advance(baseline_match(sim.observe()))
        ctx = common.make_ctx(sim.observe())
        edges = ctx['edges']
        wmap = {}
        for a, b, s in edges:
            wmap[(a, b)] = s
            wmap[(b, a)] = s
        started = time.perf_counter()
        colored = alloc.two_color(edges)
        if colored is not None:
            alloc.hungarian_max_weight(colored[0], colored[1], wmap)
        else:
            # F-08: never silently skip - exercise the non-bipartite fallback too
            alloc.one_swap_improve(alloc.greedy_take(edges), edges)
            alloc.augment3_improve(alloc.greedy_take(edges), edges, 50)
        self.assertLess(time.perf_counter() - started, 5.0)

    def test_hungarian_latency_forced_bipartite_n176(self):
        # F-06/F-08: forced branch (always bipartite), n = 176 <= HUNGARIAN_NODE_CAP
        import alloc, common, time
        left = ['l%03d' % i for i in range(88)]
        right = ['r%03d' % i for i in range(88)]
        weight = {}
        for i, u in enumerate(left):
            for j, v in enumerate(right):
                w = 1 + ((i * 17 + j * 13) % 7)
                weight[(u, v)] = w
                weight[(v, u)] = w
        edges = [(u, v, weight[(u, v)]) for u in left for v in right]
        started = time.perf_counter()
        colored = alloc.two_color(edges)
        self.assertIsNotNone(colored)
        pairs = alloc.hungarian_max_weight(colored[0], colored[1], weight)
        self.assertLess(time.perf_counter() - started, 5.0)
        self.assertTrue(pairs)

    def test_fallback_primitives_forced_odd_cycle(self):
        # F-08: forced non-bipartite branch - fallbacks must actually run
        import alloc, time
        odd = [('a', 'b', 1), ('b', 'c', 1), ('c', 'a', 1)]
        self.assertIsNone(alloc.two_color(odd))
        base = alloc.greedy_take(odd)
        started = time.perf_counter()
        fb1 = alloc.augment3_improve(base, odd, 50)
        fb2 = alloc.one_swap_improve(base, odd)
        self.assertLess(time.perf_counter() - started, 5.0)
        self.assertTrue(fb1)
        self.assertTrue(fb2)

    def test_augment3_shared_free_neighbor_skipped_safely(self):
        # F-18: single free node adjacent to both matched endpoints -> y == z skip
        import alloc
        edges = [('a', 'b', 5), ('a', 'c', 4), ('b', 'c', 4)]
        base = alloc.greedy_take(edges)
        grown = alloc.augment3_improve(base, edges, 50)
        ids = [m for p in grown for m in p]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(grown), 1)
        self.assertEqual(grown, alloc.augment3_improve(grown, edges, 50))
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m unittest research.method_tournament.test_tournament.AllocGraphTests -v`
Expected: FAIL with `AttributeError: module 'alloc' has no attribute 'two_color'`.

- [ ] **Step 3: Append the graph section to `alloc.py`**

```python
# --- Graph algorithms -------------------------------------------------------

def _adjacency(edges):
    adj = {}
    for a, b, s in edges:
        adj.setdefault(a, []).append((s, b))
        adj.setdefault(b, []).append((s, a))
    for u in adj:
        adj[u].sort(key=lambda t: (-t[0], t[1]))
    return adj


def two_color(edges):
    """Deterministic BFS 2-coloring. Returns (left, right) sorted, or None on odd cycles."""
    adj = _adjacency(edges)
    color = {}
    for start in sorted(adj):
        if start in color:
            continue
        color[start] = 0
        queue = [start]
        while queue:
            u = queue.pop(0)
            for _, v in adj[u]:
                if v not in color:
                    color[v] = 1 - color[u]
                    queue.append(v)
                elif color[v] == color[u]:
                    return None
    return (sorted(u for u in color if color[u] == 0),
            sorted(u for u in color if color[u] == 1))


def max_cardinality(edges):
    """Exact maximum-cardinality matching on bipartite graphs (Kuhn augmenting paths).
    Adjacency prefers higher base scores as the secondary heuristic. None when not bipartite."""
    colored = two_color(edges)
    if colored is None:
        return None
    left, right = colored
    adj = _adjacency(edges)
    match_r = {}

    def try_k(u, seen):
        for _, v in adj.get(u, ()):
            if v in seen:
                continue
            seen.add(v)
            if v not in match_r or try_k(match_r[v], seen):
                match_r[v] = u
                return True
        return False

    for u in sorted(left):
        try_k(u, set())
    return sorted([[match_r[v], v] for v in sorted(match_r)])


def hungarian_max_weight(left, right, weight):
    """E-maxx O(n^3) assignment maximizing sum of weight[(u, v)] over allowed pairs.
    Pads to square with dummy nodes; disallowed pairs cost MAXW and are filtered out
    afterwards (exact: zero-weight removal cannot change the optimum value).
    weight must map both orientations. Returns sorted list of (u, v) with weight > 0."""
    n0, m0 = len(left), len(right)
    if n0 == 0 or m0 == 0:
        return []
    maxw = max(weight.values()) if weight else 0
    n = max(n0, m0)
    left_p = list(left) + [None] * (n - n0)
    right_p = list(right) + [None] * (n - m0)

    def w_of(i, j):
        u, v = left_p[i], right_p[j]
        if u is None or v is None:
            return 0
        return weight.get((u, v), 0)

    a = [[0.0] * (n + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        row = a[i]
        for j in range(1, n + 1):
            row[j] = float(maxw - w_of(i - 1, j - 1))
    u = [0.0] * (n + 1)
    v = [0.0] * (n + 1)
    p = [0] * (n + 1)
    way = [0] * (n + 1)
    inf = float('inf')
    for i in range(1, n + 1):
        p[0] = i
        j0 = 0
        minv = [inf] * (n + 1)
        used = [False] * (n + 1)
        while True:
            used[j0] = True
            i0 = p[j0]
            delta = inf
            j1 = 0
            for j in range(1, n + 1):
                if used[j]:
                    continue
                cur = a[i0][j] - u[i0] - v[j]
                if cur < minv[j]:
                    minv[j] = cur
                    way[j] = j0
                if minv[j] < delta:
                    delta = minv[j]
                    j1 = j
            for j in range(n + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while j0:
            p[j0] = p[way[j0]]
            j0 = way[j0]
    pairs = []
    for j in range(1, n + 1):
        i = p[j]
        if i == 0:
            continue
        u_id, v_id = left_p[i - 1], right_p[j - 1]
        if u_id is None or v_id is None:
            continue
        if w_of(i - 1, j - 1) > 0:
            pairs.append((u_id, v_id))
    return sorted(pairs)


def one_swap_improve(pairs, edges):
    """Greedy local improvement: swap partner pairs while total base weight strictly grows.
    Integer weights guarantee termination."""
    weight = {pair_key(a, b): s for a, b, s in edges}

    def w(x, y):
        return weight.get(pair_key(x, y), -1)

    pairs = [list(p) for p in pairs]
    improved = True
    while improved:
        improved = False
        for i in range(len(pairs)):
            for j in range(i + 1, len(pairs)):
                a, b = pairs[i]
                c, d = pairs[j]
                for x, y, z, t in ((a, d, c, b), (a, c, b, d)):
                    if w(x, y) < 0 or w(z, t) < 0:
                        continue
                    if w(x, y) + w(z, t) > w(a, b) + w(c, d):
                        pairs[i], pairs[j] = [x, y], [z, t]
                        improved = True
                        break
                if improved:
                    break
            if improved:
                break
    pairs.sort(key=lambda pr: pair_key(pr[0], pr[1]))
    return pairs


def augment3_improve(pairs, edges, rounds_cap):
    """Short augmenting exchanges: unmatch (x, x'), add (x, y) with y free adjacent to x and
    (x', z) with z free adjacent to x'; cardinality grows by 1. Capped by rounds_cap."""
    adj = _adjacency(edges)
    pairs = [list(p) for p in pairs]
    for _ in range(rounds_cap):
        matched = {}
        for idx, (x, y) in enumerate(pairs):
            matched[x] = (idx, y)
            matched[y] = (idx, x)
        free = set(adj) - set(matched)
        grew = False
        for x in sorted(matched):
            idx, xp = matched[x]
            free_x = [v for _, v in adj.get(x, ()) if v in free]
            free_xp = [v for _, v in adj.get(xp, ()) if v in free]
            if not free_x or not free_xp:
                continue
            y = free_x[0]
            z = free_xp[0]
            if y == z:
                continue
            pairs[idx] = [x, y]
            pairs.append([xp, z])
            grew = True
            break
        if not grew:
            break
    pairs.sort(key=lambda pr: pair_key(pr[0], pr[1]))
    return pairs


def brute_max_weight(edges):
    """Exhaustive maximum-weight matching. TEST REFERENCE ONLY (n <= 8 nodes)."""
    weight = {pair_key(a, b): s for a, b, s in edges}
    nodes = sorted({m for a, b, s in edges for m in (a, b)})
    best = ([], 0)

    def rec(i, used, chosen, total):
        nonlocal best
        if i == len(nodes):
            if total > best[1]:
                best = (sorted(chosen), total)
            return
        u = nodes[i]
        if u in used:
            rec(i + 1, used, chosen, total)
            return
        rec(i + 1, used, chosen, total)
        for v in nodes[i + 1:]:
            if v in used or pair_key(u, v) not in weight:
                continue
            chosen.append((u, v))
            rec(i + 1, used | {v, u}, chosen, total + weight[pair_key(u, v)])
            chosen.pop()

    rec(0, set(), [], 0)
    return best
```

- [ ] **Step 4: Run to verify green**

Run: `python -m unittest research.method_tournament.test_tournament -v`
Expected: all tests PASS (previous 21 + new 10 = 31).

- [ ] **Step 5: Log the milestone**

```powershell
Add-Content -Path research\method_tournament\run_log.txt -Value ("{0} Task4 complete: alloc.py graph algorithms, brute-force parity, latency guard" -f (Get-Date -Format o))
```

No commit (spec Section 14).

---
### Task 5: Protocol Runner + Group A Scores (m01-m08)

**Files:**
- Create: `research/method_tournament/_cli.py`
- Create: `research/method_tournament/methods_a.py`
- Create: `research/method_tournament/registry.py`
- Create: `research/method_tournament/gen_policies.py`
- Generate: `research/method_tournament/policies/m01_*.py` ... `m08_*.py` (via generator)
- Modify: `research/method_tournament/methods.json` (flip group A to `implemented`)
- Test: append `run_inprocess` helper, `LeakScanTests`, `GroupATests` to `test_tournament.py`

**Interfaces:**
- Consumes: `common`, `alloc` (Tasks 2-3); `evaluate.invoke/validate_response`, `kit.VERSION` for tests.
- Produces:
  - `run(fn, ...) -> int` in `_cli.py`: reads one JSON request from stdin, calls `fn(request)`, writes the response JSON; returns 1 + stderr on any exception (protocol-correct failure for `evaluate.invoke`).
  - `methods_a.DECISIONS: dict[str, callable]` with keys `m01_greedy_baseline` ... `m08_weighted_compatibility`; every decide fn has signature `fn(request: dict) -> {'asks'|'pairs': [...], 'memory': <passthrough>}`.
  - `registry.REGISTRY: dict[str, callable]` - extended by Tasks 6-9.
  - `gen_policies.main()` - writes `policies/<method_id>.py` for every REGISTRY key; rerun after every registry change.
  - Test module-level helper `run_inprocess(fn, world, days=60) -> metrics dict`.

- [ ] **Step 1: Append the failing tests and helpers**

Append to `test_tournament.py` (before `if __name__ == '__main__':`):

```python
BANNED_NAMES = {'truth', 'bias', 'response_rate', 'second_bias', 'exit_day',
                'seed', 'variant', 'events'}
BANNED_CALLS = {'eval', 'exec', 'compile', '__import__', 'getattr', 'setattr',
                'delattr', 'globals', 'locals', 'vars', 'open'}
BANNED_DUNDERS = {'__subclasses__', '__globals__', '__builtins__', '__code__',
                  '__class__', '__bases__', '__mro__', '__dict__', '__bases__',
                  '__mro__', '__qualname__', '__module__'}
BANNED_MODULES_METHODS = {'os', 'sys', 'subprocess', 'importlib', 'inspect',
                          'builtins', 'socket', 'ssl', 'urllib', 'http',
                          'pickle', 'ctypes', 'multiprocessing', 'threading',
                          'tempfile', 'shutil', 'pathlib', 'platform'}
LAUNCHER_ALLOWED_IMPORTS = {'pathlib', 'sys', '_cli', 'registry'}
GENPOLICIES_ALLOWED_IMPORTS = {'pathlib', 'sys', 'registry'}
CLI_ALLOWED_IMPORTS = {'json', 'sys'}


def run_inprocess(fn, world, days=60):
    """Mirror evaluate.episode exactly, but call fn directly (no subprocess).
    Used by unit tests for semantics validation on small worlds; official-size (n=200)
    validation happens in the smoke phase."""
    from kit import Simulator, VERSION
    sim = Simulator(world)
    memory = None
    for _ in range(days):
        for phase in ('ask', 'match'):
            response = fn({'schema_version': VERSION, 'phase': phase,
                           'state': sim.observe(), 'memory': memory})
            memory = response['memory']
            if phase == 'ask':
                sim.resolve_asks(response['asks'])
            else:
                sim.advance(response['pairs'])
    for _ in range(40):
        sim.advance([])
    return sim.metrics()


class LeakScanTests(unittest.TestCase):
    @staticmethod
    def _imported_modules(tree):
        import ast
        mods = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                mods.update((alias.name.split('.')[0]) for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                mods.add(node.module.split('.')[0])
        return mods

    def test_no_hidden_state_access(self):
        import ast
        targets = [HERE / n for n in ('common.py', 'alloc.py', '_cli.py',
                                      'registry.py', 'gen_policies.py')]
        targets += sorted(HERE.glob('methods_*.py'))
        policies_dir = HERE / 'policies'
        if policies_dir.exists():
            targets += sorted(policies_dir.glob('*.py'))
        scanned = 0
        for path in targets:
            if not path.exists():
                continue
            scanned += 1
            tree = ast.parse(path.read_text(encoding='utf-8'))
            # F-16: import rules per file class
            mods = self._imported_modules(tree)
            if path.name.startswith('m') and path.name.endswith('.py') \
                    and path.parent.name == 'policies':
                bad_mods = mods - LAUNCHER_ALLOWED_IMPORTS
            elif path.name == 'gen_policies.py':
                bad_mods = mods - GENPOLICIES_ALLOWED_IMPORTS
            elif path.name == '_cli.py':
                bad_mods = mods - CLI_ALLOWED_IMPORTS
            elif path.name.startswith('methods_'):
                bad_mods = mods & BANNED_MODULES_METHODS
            else:
                bad_mods = mods & BANNED_MODULES_METHODS
            if bad_mods:
                self.fail('%s imports banned module(s) %r'
                          % (path.name, sorted(bad_mods)))
            for node in ast.walk(tree):
                bad = None
                if isinstance(node, ast.Name) and node.id in BANNED_NAMES:
                    bad = node.id
                elif isinstance(node, ast.Name) and node.id in BANNED_CALLS:
                    bad = node.id + ' (banned call)'
                elif isinstance(node, ast.Attribute) and node.attr in BANNED_NAMES:
                    bad = node.attr
                elif isinstance(node, ast.Attribute) and node.attr in BANNED_CALLS:
                    bad = node.attr + ' (banned call)'
                elif isinstance(node, ast.Attribute) and node.attr in BANNED_DUNDERS:
                    bad = node.attr + ' (banned dunder)'
                elif isinstance(node, ast.Constant) and isinstance(node.value, str) \
                        and node.value in BANNED_NAMES:
                    bad = node.value
                elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                        and node.func.id in BANNED_CALLS:
                    bad = node.func.id + ' (banned call)'
                if bad:
                    self.fail('%s references banned name %r at line %d'
                              % (path.name, bad, node.lineno))
        self.assertGreaterEqual(scanned, 6)

    def test_state_protocol_carries_no_banned_keys(self):
        # F-16 runtime: the observe() state itself never exposes banned inputs
        import json
        state = CommonHelperTests._state(day=30)
        blob = json.dumps(state, sort_keys=True)
        for key in ('truth', 'bias', 'response_rate', 'second_bias',
                    'exit_day', 'seed', 'variant'):
            self.assertNotIn('"%s"' % key, blob, key)

    def test_methods_never_touch_trusted_generators(self):
        # F-16 runtime negative: patch kit entry points to raise; decide fns must not notice
        import kit
        from kit import VERSION
        from registry import REGISTRY
        import evaluate
        state = CommonHelperTests._state(day=30)
        names = ('generate', 'Simulator', 'rollout', 'rand_for')
        saved = {n: getattr(kit, n) for n in names}

        def boom(*_a, **_k):
            raise AssertionError('decide fn touched a banned kit entry point')

        try:
            for n in names:
                setattr(kit, n, boom)
            for mid in sorted(REGISTRY):
                for phase in ('ask', 'match'):
                    resp = REGISTRY[mid]({'schema_version': VERSION,
                                          'phase': phase, 'state': state,
                                          'memory': None})
                    evaluate.validate_response(resp, phase)
        finally:
            for n, fn in saved.items():
                setattr(kit, n, fn)


class HashSeedTests(unittest.TestCase):
    def test_method_digests_stable_across_hash_seeds(self):
        # F-13: same actions under PYTHONHASHSEED = 0 / 1 / random
        import hashlib
        import os
        import subprocess
        import sys
        code = (
            "import json,sys;sys.path.insert(0,%r);"
            "from test_tournament import CommonHelperTests;"
            "from registry import REGISTRY;from kit import VERSION;"
            "state=CommonHelperTests._state(day=30);res={};"
            "for mid in sorted(REGISTRY):"
            " r=REGISTRY[mid]({'schema_version':VERSION,'phase':'match',"
            "'state':state,'memory':None});"
            " res[mid]=sorted(tuple(p) for p in r['pairs']);"
            "print(json.dumps(res,sort_keys=True))" % (str(HERE),))
        digests = {}
        for value in ('0', '1', 'random'):
            env = dict(os.environ, PYTHONHASHSEED=value)
            proc = subprocess.run([sys.executable, '-c', code],
                                  capture_output=True, text=True, env=env,
                                  timeout=600, cwd=str(ROOT))
            self.assertEqual(proc.returncode, 0, proc.stderr[-400:])
            digests[value] = hashlib.sha256(
                proc.stdout.strip().encode()).hexdigest()
        self.assertEqual(len(set(digests.values())), 1, digests)


class GroupATests(unittest.TestCase):
    EXPECTED = {'m01_greedy_baseline', 'm02_reciprocal_sum', 'm03_reciprocal_min',
                'm04_reciprocal_product', 'm05_harmonic_reciprocal', 'm06_bottleneck',
                'm07_prune_and_greedy', 'm08_weighted_compatibility'}

    def test_registry_contains_group_a(self):
        from registry import REGISTRY
        self.assertTrue(self.EXPECTED.issubset(set(REGISTRY)))

    def test_launchers_exist_for_registry(self):
        from registry import REGISTRY
        for mid in sorted(REGISTRY):
            self.assertTrue((HERE / 'policies' / (mid + '.py')).exists(), mid)

    def test_protocol_roundtrip_every_launcher(self):
        import evaluate
        import sys
        from kit import VERSION
        from registry import REGISTRY
        state0 = CommonHelperTests._state(day=0)
        state59 = CommonHelperTests._state(day=59)
        for mid in sorted(REGISTRY):
            cmd = [sys.executable, str(HERE / 'policies' / (mid + '.py')),
                   '--baseline', 'greedy']
            for phase, state in (('ask', state0), ('match', state59)):
                request = {'schema_version': VERSION, 'phase': phase,
                           'state': state, 'memory': None}
                response, _elapsed = evaluate.invoke(cmd, request)
                evaluate.validate_response(response, phase)

    def test_m01_matches_control_greedy(self):
        import evaluate
        import sys
        from kit import VERSION
        control = [sys.executable, str(ROOT / 'policy.py'), '--baseline', 'greedy']
        ours = [sys.executable,
                str(HERE / 'policies' / 'm01_greedy_baseline.py'), '--baseline', 'greedy']
        for phase, day in (('ask', 0), ('match', 30), ('match', 59)):
            request = {'schema_version': VERSION, 'phase': phase,
                       'state': CommonHelperTests._state(day=day), 'memory': None}
            expected, _ = evaluate.invoke(control, request)
            got, _ = evaluate.invoke(ours, request)
            self.assertEqual(got, expected, '%s@day%d' % (phase, day))

    def test_equal_float_ties_break_deterministically_by_pair_key(self):
        # F-13/m02/m08: float scores can tie exactly; pair_key must decide
        import alloc
        s1 = 1.0 / 3.0 + 1.0
        s2 = 1.0 + 2.0 / 6.0
        self.assertEqual(s1, s2)
        edges = [('b', 'c', s1), ('a', 'd', s2)]
        self.assertEqual(alloc.greedy_take(edges), [['a', 'd'], ['b', 'c']])
        self.assertEqual(alloc.greedy_take(list(reversed(edges))),
                         [['a', 'd'], ['b', 'c']])

    def test_deterministic_and_order_invariant_match_phase(self):
        import json
        from kit import VERSION
        from registry import REGISTRY
        state = CommonHelperTests._state(day=30)
        reversed_state = dict(state)
        reversed_state['members'] = list(reversed(state['members']))
        for mid in sorted(REGISTRY):
            fn = REGISTRY[mid]
            req = {'schema_version': VERSION, 'phase': 'match',
                   'state': state, 'memory': None}
            r1 = fn(dict(req))
            r2 = fn(dict(req))
            self.assertEqual(json.dumps(r1, sort_keys=True),
                             json.dumps(r2, sort_keys=True), mid)
            req2 = dict(req)
            req2['state'] = reversed_state
            r3 = fn(req2)
            self.assertEqual(sorted(tuple(p) for p in r1['pairs']),
                             sorted(tuple(p) for p in r3['pairs']), mid)

    def test_full_episode_groupA(self):
        from kit import generate
        from registry import REGISTRY
        for mid in sorted(REGISTRY):
            metrics = run_inprocess(REGISTRY[mid],
                                    generate(90210, 50, 'evaluation', 'development'))
            self.assertIn('msmi_per_100_arrived_members', metrics, mid)
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m unittest research.method_tournament.test_tournament.GroupATests research.method_tournament.test_tournament.LeakScanTests research.method_tournament.test_tournament.HashSeedTests -v`
Expected: ERROR/FAIL with `ModuleNotFoundError: No module named 'registry'`.

- [ ] **Step 3: Write `_cli.py` and `methods_a.py`**

`research/method_tournament/_cli.py`:

```python
"""Official-protocol stdin/stdout runner shared by every generated launcher."""
import json
import sys


def run(fn):
    try:
        request = json.load(sys.stdin)
        response = fn(request)
        json.dump(response, sys.stdout, allow_nan=False, sort_keys=True)
        sys.stdout.write('\n')
        return 0
    except Exception as exc:  # policy errors must surface as nonzero exit (evaluate.invoke)
        sys.stderr.write(str(exc)[:2000])
        return 1
```

`research/method_tournament/methods_a.py`:

```python
"""Group A: score-function methods (m01-m08). Ask phase = kit.baseline_asks (control parity)."""
from kit import baseline_asks, baseline_match, SOFT, OPTIONS
import common
import alloc


def decide_m01(request):
    state = request['state']
    memory = request.get('memory')
    if request['phase'] == 'ask':
        return {'asks': baseline_asks(state), 'memory': memory}
    return {'pairs': baseline_match(state), 'memory': memory}


def _scored_match(score_fn):
    def decide(request):
        state = request['state']
        memory = request.get('memory')
        if request['phase'] == 'ask':
            return {'asks': baseline_asks(state), 'memory': memory}
        ctx = common.make_ctx(state)
        mfs = ctx['members']
        scored = [(a, b, score_fn(mfs[a], mfs[b], ctx)) for a, b, s in ctx['edges']]
        return {'pairs': alloc.greedy_take(scored), 'memory': memory}
    return decide


def score_m02(a, b, ctx):
    return common.directional(a, b) + common.directional(b, a)


def score_m03(a, b, ctx):
    return min(common.directional(a, b), common.directional(b, a))


def score_m04(a, b, ctx):
    return common.directional(a, b) * common.directional(b, a)


def score_m05(a, b, ctx):
    x, y = common.directional(a, b), common.directional(b, a)
    return 0.0 if x + y == 0 else 2.0 * x * y / (x + y)


def score_m06(a, b, ctx):
    """Bottleneck over the 4 REL fields: equal=1, unequal=0, missing=uniform prior."""
    worst = 1.0
    for k in common.REL:
        av, bv = a['fields'].get(k), b['fields'].get(k)
        if av is None or bv is None:
            val = 1.0 / len(OPTIONS[k])
        else:
            val = 1.0 if av == bv else 0.0
        if val < worst:
            worst = val
    return worst


_WEIGHT = {k: 1.0 - 1.0 / len(OPTIONS[k]) for k in SOFT}


def score_m08(a, b, ctx):
    """Structure-only weights from OPTIONS cardinalities; one side observed gets w*p prior."""
    total = 0.0
    for k in SOFT:
        av, bv = a['fields'].get(k), b['fields'].get(k)
        if av is not None and bv is not None:
            if av == bv:
                total += _WEIGHT[k]
        elif av is not None or bv is not None:
            total += _WEIGHT[k] / len(OPTIONS[k])
    return total


def decide_m07(request):
    state = request['state']
    memory = request.get('memory')
    if request['phase'] == 'ask':
        return {'asks': baseline_asks(state), 'memory': memory}
    kept = alloc.filter_min_score(common.feasible_edges(state), common.PRUNE_MIN_SCORE)
    return {'pairs': alloc.greedy_take(kept), 'memory': memory}


DECISIONS = {
    'm01_greedy_baseline': decide_m01,
    'm02_reciprocal_sum': _scored_match(score_m02),
    'm03_reciprocal_min': _scored_match(score_m03),
    'm04_reciprocal_product': _scored_match(score_m04),
    'm05_harmonic_reciprocal': _scored_match(score_m05),
    'm06_bottleneck': _scored_match(score_m06),
    'm07_prune_and_greedy': decide_m07,
    'm08_weighted_compatibility': _scored_match(score_m08),
}
```

- [ ] **Step 4: Write `registry.py` and `gen_policies.py`**

`research/method_tournament/registry.py`:

```python
"""Executable registry: method_id -> decide function. Tasks 6-9 append their imports
and REGISTRY.update(...) below; rerun gen_policies.py after every change."""
from methods_a import DECISIONS as DECISIONS_A

REGISTRY = {}
REGISTRY.update(DECISIONS_A)
```

`research/method_tournament/gen_policies.py`:

```python
"""Generate thin launchers in policies/ from the registry.
Run after any registry change: python research/method_tournament/gen_policies.py"""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from registry import REGISTRY

TEMPLATE = '''"""Auto-generated launcher for {mid}. Do not edit; regenerate instead."""
import pathlib
import sys
_HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))
sys.path.insert(0, str(_HERE.parents[2]))
from _cli import run
from registry import REGISTRY
raise SystemExit(run(REGISTRY['{mid}']))
'''


def main():
    out = HERE / 'policies'
    out.mkdir(exist_ok=True)
    for mid in sorted(REGISTRY):
        (out / (mid + '.py')).write_text(TEMPLATE.format(mid=mid), encoding='utf-8')
    print('wrote %d launchers' % len(REGISTRY))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
```

- [ ] **Step 5: Generate the launchers**

Run: `python research/method_tournament/gen_policies.py`
Expected: `wrote 8 launchers`, and `research/method_tournament/policies/` contains `m01_greedy_baseline.py` ... `m08_weighted_compatibility.py`.

- [ ] **Step 6: Flip group A registry status to implemented**

```powershell
python -c "import json,pathlib; p=pathlib.Path('research/method_tournament/methods.json'); d=json.loads(p.read_text(encoding='utf-8')); [m.update(implementation_status='implemented') for m in d['methods'] if m['group']=='A']; p.write_text(json.dumps(d, indent=2, ensure_ascii=False)+chr(10), encoding='utf-8'); print('group A -> implemented')"
```

- [ ] **Step 7: Run the new tests to verify green**

Run: `python -m unittest research.method_tournament.test_tournament.GroupATests research.method_tournament.test_tournament.LeakScanTests research.method_tournament.test_tournament.HashSeedTests -v`
Expected: all PASS. Note: `test_full_episode_groupA` takes roughly 2-4 minutes (8 methods x 60 days on a 50-member world) - this is expected.

- [ ] **Step 8: Run the whole module for regressions**

Run: `python -m unittest research.method_tournament.test_tournament -v`
Expected: all PASS (Task 1-5 tests together).

- [ ] **Step 9: Log the milestone**

```powershell
Add-Content -Path research\method_tournament\run_log.txt -Value ("{0} Task5 complete: protocol runner + group A (8 methods) + leak scanner" -f (Get-Date -Format o))
```

No commit (spec Section 14).

---
### Task 6: Group B - Scarcity / Opportunity Cost (m09-m15)

**Files:**
- Create: `research/method_tournament/methods_b.py`
- Modify: `research/method_tournament/registry.py` (add group B import)
- Modify: `research/method_tournament/methods.json` (flip group B to `implemented`)
- Generate: `policies/m09_*.py` ... `m15_*.py`
- Test: append `GroupBTests` to `test_tournament.py`

**Interfaces:**
- Consumes: `common.make_ctx/alt_for/STRONG_SCORE`, `alloc.greedy_take`, `registry.REGISTRY` (Task 5).
- Produces: `methods_b.DECISIONS` with keys `m09_partner_scarcity` ... `m15_reserve_high_option`; score functions have signature `fn(ctx, a, b, base) -> float`.

- [ ] **Step 1: Append the failing tests**

Append `GroupBTests`:

```python
class GroupBTests(unittest.TestCase):
    EXPECTED = {'m09_partner_scarcity', 'm10_degree_balanced', 'm11_scarcity_x_compat',
                'm12_regret_score', 'm13_opportunity_cost', 'm14_mutual_regret',
                'm15_reserve_high_option'}

    def test_registry_contains_group_b(self):
        from registry import REGISTRY
        self.assertTrue(self.EXPECTED.issubset(set(REGISTRY)))

    def test_full_episode_groupB(self):
        from kit import generate
        from registry import REGISTRY
        for mid in sorted(self.EXPECTED):
            metrics = run_inprocess(REGISTRY[mid],
                                    generate(90211, 50, 'evaluation', 'cold_start'))
            self.assertIn('msmi_per_100_arrived_members', metrics, mid)
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m unittest research.method_tournament.test_tournament.GroupBTests -v`
Expected: FAIL `AssertionError` (registry missing group B) or `ModuleNotFoundError: methods_b`.

- [ ] **Step 3: Write `methods_b.py`**

```python
"""Group B: scarcity / opportunity-cost methods (m09-m15). Ask phase = baseline_asks."""
from kit import baseline_asks
import common
import alloc


def _scored_match(score_fn):
    def decide(request):
        state = request['state']
        memory = request.get('memory')
        if request['phase'] == 'ask':
            return {'asks': baseline_asks(state), 'memory': memory}
        ctx = common.make_ctx(state)
        scored = [(a, b, score_fn(ctx, a, b, s)) for a, b, s in ctx['edges']]
        return {'pairs': alloc.greedy_take(scored), 'memory': memory}
    return decide


def score_m09(ctx, a, b, base):
    return base / max(1, min(ctx['deg'].get(a, 1), ctx['deg'].get(b, 1)))


def score_m10(ctx, a, b, base):
    return base / max(1, max(ctx['deg'].get(a, 1), ctx['deg'].get(b, 1)))


def score_m11(ctx, a, b, base):
    return base * 2.0 / (ctx['deg'].get(a, 1) + ctx['deg'].get(b, 1))


def _gaps(ctx, a, b, base):
    gap_a = max(0, common.alt_for(ctx, a, b) - base)
    gap_b = max(0, common.alt_for(ctx, b, a) - base)
    return gap_a, gap_b


def score_m12(ctx, a, b, base):
    gap_a, gap_b = _gaps(ctx, a, b, base)
    return base - gap_a - gap_b


def score_m13(ctx, a, b, base):
    gap_a, gap_b = _gaps(ctx, a, b, base)
    return base - max(gap_a, gap_b)


def score_m14(ctx, a, b, base):
    gap_a, gap_b = _gaps(ctx, a, b, base)
    return base - min(gap_a, gap_b)


def score_m15(ctx, a, b, base):
    cnt_a = sum(1 for s, o in ctx['inc'].get(a, ()) if o != b and s >= common.STRONG_SCORE)
    cnt_b = sum(1 for s, o in ctx['inc'].get(b, ()) if o != a and s >= common.STRONG_SCORE)
    return base - cnt_a - cnt_b


DECISIONS = {
    'm09_partner_scarcity': _scored_match(score_m09),
    'm10_degree_balanced': _scored_match(score_m10),
    'm11_scarcity_x_compat': _scored_match(score_m11),
    'm12_regret_score': _scored_match(score_m12),
    'm13_opportunity_cost': _scored_match(score_m13),
    'm14_mutual_regret': _scored_match(score_m14),
    'm15_reserve_high_option': _scored_match(score_m15),
}
```

- [ ] **Step 4: Update `registry.py` (full file content)**

```python
"""Executable registry: method_id -> decide function. Tasks 7-9 append their imports
and REGISTRY.update(...) below; rerun gen_policies.py after every change."""
from methods_a import DECISIONS as DECISIONS_A
from methods_b import DECISIONS as DECISIONS_B

REGISTRY = {}
REGISTRY.update(DECISIONS_A)
REGISTRY.update(DECISIONS_B)
```

- [ ] **Step 5: Regenerate launchers and flip registry status**

```powershell
python research/method_tournament/gen_policies.py
python -c "import json,pathlib; p=pathlib.Path('research/method_tournament/methods.json'); d=json.loads(p.read_text(encoding='utf-8')); [m.update(implementation_status='implemented') for m in d['methods'] if m['group']=='B']; p.write_text(json.dumps(d, indent=2, ensure_ascii=False)+chr(10), encoding='utf-8'); print('group B -> implemented')"
```
Expected: `wrote 15 launchers`, `group B -> implemented`.

- [ ] **Step 6: Run tests to verify green**

Run: `python -m unittest research.method_tournament.test_tournament.GroupBTests -v`
Expected: PASS (full-episode on cold_start takes ~2-4 minutes).

- [ ] **Step 7: Log the milestone**

```powershell
Add-Content -Path research\method_tournament\run_log.txt -Value ("{0} Task6 complete: group B (7 methods)" -f (Get-Date -Format o))
```

No commit (spec Section 14).

---

### Task 7: Group C - Wait / Temporal Policies (m16-m23)

**Files:**
- Create: `research/method_tournament/methods_c.py`
- Modify: `research/method_tournament/registry.py` (add group C import)
- Modify: `research/method_tournament/methods.json` (flip group C to `implemented`)
- Generate: `policies/m16_*.py` ... `m23_*.py`
- Test: append `GroupCTests` to `test_tournament.py`

**Interfaces:**
- Consumes: `common.feasible_edges/make_ctx/wait_days/pair_key`, `alloc.{filter_min_score, quota_half, protect_filter, thin_wait, hybrid_favorable, greedy_take, take_ordered}`.
- Produces: `methods_c.DECISIONS` with keys `m16_patient_policy` ... `m23_hybrid_patient_greedy`.

- [ ] **Step 1: Append the failing tests**

Append `GroupCTests` (uses a controlled 2-member state so gates are exercised deterministically):

```python
class GroupCTests(unittest.TestCase):
    EXPECTED = {'m16_patient_policy', 'm17_daily_quota', 'm18_time_threshold',
                'm19_arrival_age', 'm20_new_arrival_protection',
                'm21_delay_cost_threshold', 'm22_market_thickness',
                'm23_hybrid_patient_greedy'}

    @staticmethod
    def _pair_state(base_target, day=10, wait_a=5, wait_b=5):
        """Two mutually feasible members sharing exactly base_target SOFT fields."""
        import common
        from kit import SOFT, OPTIONS
        state = dict(CommonHelperTests._state(day=day))
        edges = common.feasible_edges(state)
        if not edges:
            raise unittest.SkipTest('no feasible pair in fixture world')
        a, b, _ = edges[0]
        mfs = {m['member_id']: m for m in state['members']}
        for i, k in enumerate(SOFT):
            mfs[a]['fields'][k] = OPTIONS[k][0]
            mfs[b]['fields'][k] = OPTIONS[k][0] if i < base_target else OPTIONS[k][1]
        mfs[a]['arrived_day'] = day - wait_a
        mfs[b]['arrived_day'] = day - wait_b
        state['members'] = [mfs[a], mfs[b]]
        return state, (a, b)

    @staticmethod
    def _match(mid, state):
        from registry import REGISTRY
        from kit import VERSION
        return REGISTRY[mid]({'schema_version': VERSION, 'phase': 'match',
                              'state': state, 'memory': None})

    @staticmethod
    def _keys(pairs):
        import common
        return [common.pair_key(p[0], p[1]) for p in pairs]

    def test_registry_contains_group_c(self):
        from registry import REGISTRY
        self.assertTrue(self.EXPECTED.issubset(set(REGISTRY)))

    def test_m16_patient_gate(self):
        import common
        state, pair = self._pair_state(1, day=10)
        self.assertEqual(self._match('m16_patient_policy', state)['pairs'], [])
        state5, _ = self._pair_state(5, day=10)
        resp = self._match('m16_patient_policy', state5)
        self.assertEqual(self._keys(resp['pairs']), [common.pair_key(*pair)])

    def test_m17_quota_property(self):
        import common, alloc
        state = CommonHelperTests._state(day=30)
        full = alloc.greedy_take(common.feasible_edges(state))
        resp = self._match('m17_daily_quota', state)
        self.assertEqual(len(resp['pairs']), (len(full) + 1) // 2)

    def test_m18_time_threshold_by_phase(self):
        state3, _ = self._pair_state(3, day=10)   # day<20 -> need 4
        self.assertEqual(self._match('m18_time_threshold', state3)['pairs'], [])
        state5, pair = self._pair_state(5, day=10)
        self.assertEqual(self._keys(self._match('m18_time_threshold', state5)['pairs']),
                         [__import__('common').pair_key(*pair)])
        state2, _ = self._pair_state(2, day=50)   # day>=40 -> need 2
        self.assertNotEqual(self._match('m18_time_threshold', state2)['pairs'], [])
        state1, _ = self._pair_state(1, day=50)
        self.assertEqual(self._match('m18_time_threshold', state1)['pairs'], [])

    def test_m19_first_pair_has_longest_wait(self):
        import common
        day = 30
        state = CommonHelperTests._state(day=day)
        ctx = common.make_ctx(state)
        resp = self._match('m19_arrival_age', state)
        if not ctx['edges']:
            self.skipTest('no edges')
        waits = {m['member_id']: common.wait_days(m, day) for m in state['members']}
        want = max(max(waits[a], waits[b]) for a, b, s in ctx['edges'])
        got = max(waits[x] for x in resp['pairs'][0])
        self.assertEqual(got, want)

    def test_m20_protection_window(self):
        import common
        fresh, pair = self._pair_state(5, day=10, wait_a=0, wait_b=5)
        self.assertEqual(self._match('m20_new_arrival_protection', fresh)['pairs'], [])
        aged, _ = self._pair_state(5, day=10, wait_a=5, wait_b=5)
        resp = self._match('m20_new_arrival_protection', aged)
        self.assertEqual(self._keys(resp['pairs']), [common.pair_key(*pair)])

    def test_m21_delay_cost_threshold(self):
        import common
        # wait 45 -> required score 1 (max(0, 4 - 45//15)); wait 0 -> required 4
        late, pair = self._pair_state(1, day=50, wait_a=45, wait_b=45)
        resp = self._match('m21_delay_cost_threshold', late)
        self.assertEqual(self._keys(resp['pairs']), [common.pair_key(*pair)])
        early, _ = self._pair_state(1, day=50, wait_a=0, wait_b=0)
        self.assertEqual(self._match('m21_delay_cost_threshold', early)['pairs'], [])
        early_strong, _ = self._pair_state(4, day=50, wait_a=0, wait_b=0)
        self.assertNotEqual(self._match('m21_delay_cost_threshold', early_strong)['pairs'], [])

    def test_m22_thin_branch_and_wiring(self):
        import common, alloc
        thin, _ = self._pair_state(5, day=10)   # 2 members, 1 edge -> avg_deg 1.0 < 2.0
        self.assertEqual(self._match('m22_market_thickness', thin)['pairs'], [])
        state = CommonHelperTests._state(day=30)
        ctx = common.make_ctx(state)
        resp = self._match('m22_market_thickness', state)
        if alloc.thin_wait(ctx):
            self.assertEqual(resp['pairs'], [])
        else:
            self.assertEqual(resp['pairs'], alloc.greedy_take(ctx['edges']))

    def test_m23_hybrid_both_branches(self):
        import common, alloc
        weak, _ = self._pair_state(3, day=10)   # max_base 3 < 4 and avg_deg 1.0 < 3.0
        self.assertEqual(self._match('m23_hybrid_patient_greedy', weak)['pairs'], [])
        strong, pair = self._pair_state(5, day=10)
        resp = self._match('m23_hybrid_patient_greedy', strong)
        self.assertEqual(self._keys(resp['pairs']), [common.pair_key(*pair)])

    def test_full_episode_groupC(self):
        from kit import generate
        from registry import REGISTRY
        for mid in sorted(self.EXPECTED):
            metrics = run_inprocess(REGISTRY[mid],
                                    generate(90212, 50, 'evaluation', 'sparse'))
            self.assertIn('msmi_per_100_arrived_members', metrics, mid)
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m unittest research.method_tournament.test_tournament.GroupCTests -v`
Expected: FAIL `AssertionError` (registry missing group C) or `ModuleNotFoundError: methods_c`.

- [ ] **Step 3: Write `methods_c.py`**

```python
"""Group C: wait / temporal methods (m16-m23). Ask phase = baseline_asks: waiting is
the isolated mechanism, asking stays control-parity."""
from kit import baseline_asks
import common
import alloc


def _ask_or(state, request, pairs_fn):
    memory = request.get('memory')
    if request['phase'] == 'ask':
        return {'asks': baseline_asks(state), 'memory': memory}
    return {'pairs': pairs_fn(), 'memory': memory}


def decide_m16(request):
    state = request['state']

    def go():
        kept = alloc.filter_min_score(common.feasible_edges(state),
                                      common.PATIENT_MIN_SCORE)
        return alloc.greedy_take(kept)
    return _ask_or(state, request, go)


def decide_m17(request):
    state = request['state']

    def go():
        return alloc.quota_half(alloc.greedy_take(common.feasible_edges(state)))
    return _ask_or(state, request, go)


def decide_m18(request):
    state = request['state']

    def go():
        req = max(1, common.TIME_T0 - state['day'] // common.TIME_STEP)
        return alloc.greedy_take(alloc.filter_min_score(common.feasible_edges(state), req))
    return _ask_or(state, request, go)


def decide_m19(request):
    state = request['state']

    def go():
        ctx = common.make_ctx(state)
        day, mfs = ctx['day'], ctx['members']

        def key_fn(e):
            wait_pair = max(common.wait_days(mfs[e[0]], day),
                            common.wait_days(mfs[e[1]], day))
            return (-wait_pair, -e[2], common.pair_key(e[0], e[1]))
        return alloc.take_ordered(ctx['edges'], key_fn)
    return _ask_or(state, request, go)


def decide_m20(request):
    state = request['state']

    def go():
        ctx = common.make_ctx(state)
        return alloc.greedy_take(alloc.protect_filter(ctx['edges'], ctx))
    return _ask_or(state, request, go)


def decide_m21(request):
    state = request['state']

    def go():
        ctx = common.make_ctx(state)
        day, mfs = ctx['day'], ctx['members']
        kept = []
        for a, b, s in ctx['edges']:
            need = max(0, common.DELAY_T0
                       - max(common.wait_days(mfs[a], day),
                             common.wait_days(mfs[b], day)) // common.DELAY_STEP)
            if s >= need:
                kept.append((a, b, s))
        return alloc.greedy_take(kept)
    return _ask_or(state, request, go)


def decide_m22(request):
    state = request['state']

    def go():
        ctx = common.make_ctx(state)
        if alloc.thin_wait(ctx):
            return []
        return alloc.greedy_take(ctx['edges'])
    return _ask_or(state, request, go)


def decide_m23(request):
    state = request['state']

    def go():
        ctx = common.make_ctx(state)
        if not alloc.hybrid_favorable(ctx):
            return []
        return alloc.greedy_take(ctx['edges'])
    return _ask_or(state, request, go)


DECISIONS = {
    'm16_patient_policy': decide_m16,
    'm17_daily_quota': decide_m17,
    'm18_time_threshold': decide_m18,
    'm19_arrival_age': decide_m19,
    'm20_new_arrival_protection': decide_m20,
    'm21_delay_cost_threshold': decide_m21,
    'm22_market_thickness': decide_m22,
    'm23_hybrid_patient_greedy': decide_m23,
}
```

- [ ] **Step 4: Update `registry.py` (full file content)**

```python
"""Executable registry: method_id -> decide function. Tasks 8-9 append their imports
and REGISTRY.update(...) below; rerun gen_policies.py after every change."""
from methods_a import DECISIONS as DECISIONS_A
from methods_b import DECISIONS as DECISIONS_B
from methods_c import DECISIONS as DECISIONS_C

REGISTRY = {}
REGISTRY.update(DECISIONS_A)
REGISTRY.update(DECISIONS_B)
REGISTRY.update(DECISIONS_C)
```

- [ ] **Step 5: Regenerate launchers and flip registry status**

```powershell
python research/method_tournament/gen_policies.py
python -c "import json,pathlib; p=pathlib.Path('research/method_tournament/methods.json'); d=json.loads(p.read_text(encoding='utf-8')); [m.update(implementation_status='implemented') for m in d['methods'] if m['group']=='C']; p.write_text(json.dumps(d, indent=2, ensure_ascii=False)+chr(10), encoding='utf-8'); print('group C -> implemented')"
```
Expected: `wrote 23 launchers`, `group C -> implemented`.

- [ ] **Step 6: Run tests to verify green**

Run: `python -m unittest research.method_tournament.test_tournament.GroupCTests -v`
Expected: PASS (gate tests are fast; full-episode ~2-4 minutes).

- [ ] **Step 7: Log the milestone**

```powershell
Add-Content -Path research\method_tournament\run_log.txt -Value ("{0} Task7 complete: group C (8 methods) incl. gate branch tests" -f (Get-Date -Format o))
```

No commit (spec Section 14).

---

### Task 8: Group D - Allocation / Graph Methods (m24-m28)

**Files:**
- Create: `research/method_tournament/methods_d.py`
- Modify: `research/method_tournament/registry.py` (add group D import)
- Modify: `research/method_tournament/methods.json` (flip group D to `implemented`)
- Generate: `policies/m24_*.py` ... `m28_*.py`
- Test: append `GroupDTests` to `test_tournament.py`

**Interfaces:**
- Consumes: `common.feasible_edges/pair_key`, `alloc.{greedy_take, take_ordered, max_cardinality, two_color, hungarian_max_weight, one_swap_improve, augment3_improve}`, frozen `common.HUNGARIAN_NODE_CAP`, `common.AUGMENT_ROUNDS_CAP`.
- Produces: `methods_d.DECISIONS` with keys `m24_max_cardinality` ... `m28_conflict_aware`.

- [ ] **Step 1: Append the failing tests**

Append `GroupDTests` (reference-branch tests independently recompute what the decide
function must return; the single-edge fixture proves basic wiring for all five):

```python
class GroupDTests(unittest.TestCase):
    EXPECTED = {'m24_max_cardinality', 'm25_max_weight', 'm26_greedy_one_swap',
                'm27_greedy_augmenting', 'm28_conflict_aware'}

    @staticmethod
    def _match(mid, state):
        from registry import REGISTRY
        from kit import VERSION
        return REGISTRY[mid]({'schema_version': VERSION, 'phase': 'match',
                              'state': state, 'memory': None})

    @staticmethod
    def _keys(pairs):
        import common
        return [common.pair_key(p[0], p[1]) for p in pairs]

    def _assert_valid(self, resp, edges):
        import common
        ekeys = {common.pair_key(a, b) for a, b, s in edges}
        ids = [m for p in resp['pairs'] for m in p]
        self.assertEqual(len(ids), len(set(ids)))
        for p in resp['pairs']:
            self.assertIn(common.pair_key(p[0], p[1]), ekeys)

    def test_registry_contains_group_d(self):
        from registry import REGISTRY
        self.assertTrue(self.EXPECTED.issubset(set(REGISTRY)))

    def test_all_methods_pick_the_only_edge(self):
        import common
        state, pair = GroupCTests._pair_state(5, day=10)
        for mid in sorted(self.EXPECTED):
            resp = self._match(mid, state)
            self.assertEqual(self._keys(resp['pairs']), [common.pair_key(*pair)], mid)

    def test_m25_zero_prune_returns_empty(self):
        state, _ = GroupCTests._pair_state(0, day=10)   # all SOFT differ -> base 0
        self.assertEqual(self._match('m25_max_weight', state)['pairs'], [])

    def test_m24_matches_reference_branches(self):
        import common, alloc
        state = CommonHelperTests._state(day=30)
        edges = common.feasible_edges(state)
        expected = alloc.max_cardinality(edges)
        if expected is None:
            expected = alloc.augment3_improve(alloc.greedy_take(edges), edges,
                                              common.AUGMENT_ROUNDS_CAP)
        resp = self._match('m24_max_cardinality', state)
        self.assertEqual(resp['pairs'], expected)
        self._assert_valid(resp, edges)

    def test_m25_matches_reference_and_value_ge_greedy(self):
        import common, alloc
        state = CommonHelperTests._state(day=30)
        all_edges = common.feasible_edges(state)
        edges = [e for e in all_edges if e[2] > 0]
        colored = alloc.two_color(edges)
        if colored is not None and len(colored[0]) + len(colored[1]) <= common.HUNGARIAN_NODE_CAP:
            wmap = {}
            for a, b, s in edges:
                wmap[(a, b)] = s
                wmap[(b, a)] = s
            expected = [list(p) for p in alloc.hungarian_max_weight(colored[0], colored[1], wmap)]
        else:
            expected = alloc.one_swap_improve(alloc.greedy_take(edges), edges)
        resp = self._match('m25_max_weight', state)
        self.assertEqual(resp['pairs'], expected)
        self._assert_valid(resp, all_edges)
        w = AllocGraphTests._weight_total
        self.assertGreaterEqual(w(resp['pairs'], all_edges),
                                w(alloc.greedy_take(all_edges), all_edges))
    def test_m24_forced_fallback_when_max_cardinality_unavailable(self):
        import alloc, common
        state = CommonHelperTests._state(day=30)
        real = alloc.max_cardinality
        alloc.max_cardinality = lambda edges: None   # force the odd-cycle branch
        try:
            resp = self._match('m24_max_cardinality', state)
        finally:
            alloc.max_cardinality = real
        edges = common.feasible_edges(state)
        expected = alloc.augment3_improve(alloc.greedy_take(edges), edges,
                                          common.AUGMENT_ROUNDS_CAP)
        self.assertEqual(resp['pairs'], expected)
        self._assert_valid(resp, edges)

    def test_m25_forced_fallback_when_coloring_unavailable(self):
        import alloc, common
        state = CommonHelperTests._state(day=30)
        real = alloc.two_color
        alloc.two_color = lambda edges: None   # force the non-bipartite guard
        try:
            resp = self._match('m25_max_weight', state)
        finally:
            alloc.two_color = real
        all_edges = common.feasible_edges(state)
        edges = [e for e in all_edges if e[2] > 0]
        expected = alloc.one_swap_improve(alloc.greedy_take(edges), edges)
        self.assertEqual(resp['pairs'], expected)
        self._assert_valid(resp, all_edges)

    def test_m25_forced_fallback_on_node_cap(self):
        import alloc, common
        state = CommonHelperTests._state(day=30)
        real_cap = common.HUNGARIAN_NODE_CAP
        common.HUNGARIAN_NODE_CAP = 0   # force the over-cap guard
        try:
            resp = self._match('m25_max_weight', state)
        finally:
            common.HUNGARIAN_NODE_CAP = real_cap
        all_edges = common.feasible_edges(state)
        edges = [e for e in all_edges if e[2] > 0]
        expected = alloc.one_swap_improve(alloc.greedy_take(edges), edges)
        self.assertEqual(resp['pairs'], expected)
        self._assert_valid(resp, all_edges)

    def test_heavy_decide_latency_m24_m25_under_5s(self):
        import time
        state = CommonHelperTests._state(day=30)   # worst fixture: over-cap + non-bipartite
        for mid in ('m24_max_cardinality', 'm25_max_weight'):
            started = time.perf_counter()
            self._match(mid, state)
            self.assertLess(time.perf_counter() - started, 5.0, mid)

    def test_m26_matches_reference(self):
        import common, alloc
        state = CommonHelperTests._state(day=30)
        edges = common.feasible_edges(state)
        resp = self._match('m26_greedy_one_swap', state)
        self.assertEqual(resp['pairs'],
                         alloc.one_swap_improve(alloc.greedy_take(edges), edges))
        self._assert_valid(resp, edges)

    def test_m27_matches_reference(self):
        import common, alloc
        state = CommonHelperTests._state(day=30)
        edges = common.feasible_edges(state)
        resp = self._match('m27_greedy_augmenting', state)
        self.assertEqual(resp['pairs'],
                         alloc.augment3_improve(alloc.greedy_take(edges), edges,
                                                common.AUGMENT_ROUNDS_CAP))
        self._assert_valid(resp, edges)

    def test_m28_conflict_ranking_matches_reference(self):
        import common, alloc
        state = CommonHelperTests._state(day=30)
        edges = common.feasible_edges(state)
        pools = {}
        for a, b, s in edges:
            pools[a] = pools.get(a, 0) + s
            pools[b] = pools.get(b, 0) + s
        expected = alloc.take_ordered(
            edges, lambda e: (-(3 * e[2] - pools.get(e[0], 0) - pools.get(e[1], 0)),
                              common.pair_key(e[0], e[1])))
        resp = self._match('m28_conflict_aware', state)
        self.assertEqual(resp['pairs'], expected)
        self._assert_valid(resp, edges)

    def test_full_episode_groupD(self):
        from kit import generate
        from registry import REGISTRY
        for mid in sorted(self.EXPECTED):
            metrics = run_inprocess(REGISTRY[mid],
                                    generate(90213, 50, 'evaluation', 'development'))
            self.assertIn('msmi_per_100_arrived_members', metrics, mid)
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m unittest research.method_tournament.test_tournament.GroupDTests -v`
Expected: FAIL `AssertionError` (registry missing group D) or `ModuleNotFoundError: methods_d`.

- [ ] **Step 3: Write `methods_d.py`**

```python
"""Group D: allocation / graph methods (m24-m28). Ask phase = baseline_asks."""
from kit import baseline_asks
import common
import alloc


def _ask_or(state, request, pairs_fn):
    memory = request.get('memory')
    if request['phase'] == 'ask':
        return {'asks': baseline_asks(state), 'memory': memory}
    return {'pairs': pairs_fn(), 'memory': memory}


def decide_m24(request):
    state = request['state']

    def go():
        edges = common.feasible_edges(state)
        got = alloc.max_cardinality(edges)
        if got is None:   # non-bipartite: documented approximation
            got = alloc.augment3_improve(alloc.greedy_take(edges), edges,
                                         common.AUGMENT_ROUNDS_CAP)
        return got
    return _ask_or(state, request, go)


def decide_m25(request):
    state = request['state']

    def go():
        edges = [e for e in common.feasible_edges(state) if e[2] > 0]  # exact for value
        colored = alloc.two_color(edges)
        if colored is not None and len(colored[0]) + len(colored[1]) <= common.HUNGARIAN_NODE_CAP:
            wmap = {}
            for a, b, s in edges:
                wmap[(a, b)] = s
                wmap[(b, a)] = s
            return [list(p) for p in alloc.hungarian_max_weight(colored[0], colored[1], wmap)]
        return alloc.one_swap_improve(alloc.greedy_take(edges), edges)  # documented fallback
    return _ask_or(state, request, go)


def decide_m26(request):
    state = request['state']

    def go():
        edges = common.feasible_edges(state)
        return alloc.one_swap_improve(alloc.greedy_take(edges), edges)
    return _ask_or(state, request, go)


def decide_m27(request):
    state = request['state']

    def go():
        edges = common.feasible_edges(state)
        return alloc.augment3_improve(alloc.greedy_take(edges), edges,
                                      common.AUGMENT_ROUNDS_CAP)
    return _ask_or(state, request, go)


def decide_m28(request):
    state = request['state']

    def go():
        edges = common.feasible_edges(state)
        pools = {}
        for a, b, s in edges:          # pool includes the candidate pair itself
            pools[a] = pools.get(a, 0) + s
            pools[b] = pools.get(b, 0) + s

        def key_fn(e):
            a, b, s = e
            return (-(3 * s - pools.get(a, 0) - pools.get(b, 0)),
                    common.pair_key(a, b))
        return alloc.take_ordered(edges, key_fn)
    return _ask_or(state, request, go)


DECISIONS = {
    'm24_max_cardinality': decide_m24,
    'm25_max_weight': decide_m25,
    'm26_greedy_one_swap': decide_m26,
    'm27_greedy_augmenting': decide_m27,
    'm28_conflict_aware': decide_m28,
}
```

- [ ] **Step 4: Update `registry.py` (full file content)**

```python
"""Executable registry: method_id -> decide function. Task 9 appends its imports
and REGISTRY.update(...) below; rerun gen_policies.py after every change."""
from methods_a import DECISIONS as DECISIONS_A
from methods_b import DECISIONS as DECISIONS_B
from methods_c import DECISIONS as DECISIONS_C
from methods_d import DECISIONS as DECISIONS_D

REGISTRY = {}
REGISTRY.update(DECISIONS_A)
REGISTRY.update(DECISIONS_B)
REGISTRY.update(DECISIONS_C)
REGISTRY.update(DECISIONS_D)
```

- [ ] **Step 5: Regenerate launchers and flip registry status**

```powershell
python research/method_tournament/gen_policies.py
python -c "import json,pathlib; p=pathlib.Path('research/method_tournament/methods.json'); d=json.loads(p.read_text(encoding='utf-8')); [m.update(implementation_status='implemented') for m in d['methods'] if m['group']=='D']; p.write_text(json.dumps(d, indent=2, ensure_ascii=False)+chr(10), encoding='utf-8'); print('group D -> implemented')"
```
Expected: `wrote 28 launchers`, `group D -> implemented`.

- [ ] **Step 6: Run tests to verify green**

Run: `python -m unittest research.method_tournament.test_tournament.GroupDTests -v`
Expected: PASS (13 new tests; full-episode ~2-4 minutes).

- [ ] **Step 7: Log the milestone**

```powershell
Add-Content -Path research\method_tournament\run_log.txt -Value ("{0} Task8 complete: group D (5 methods) incl. forced-fallback-branch + latency tests" -f (Get-Date -Format o))
```

No commit (spec Section 14).

---
### Task 9: Group E - Active Asking (m29-m30)

**Files:**
- Create: `research/method_tournament/methods_e.py`
- Modify: `research/method_tournament/registry.py` (add group E import)
- Modify: `research/method_tournament/methods.json` (flip group E to `implemented`)
- Generate: `policies/m29_*.py`, `policies/m30_*.py`
- Test: append `GroupETests` to `test_tournament.py`

**Interfaces:**
- Consumes: `kit.{baseline_asks, baseline_match, OPTIONS, SOFT, VERSION}`, `common.{feasible_edges, make_ctx, pair_key, SOFT_ASK_RESERVE}`, `alloc.greedy_take`.
- Produces: `methods_e.DECISIONS` with keys `m29_uncertainty_aware`, `m30_targeted_info`.
- Ask validity rules enforced by `kit.Simulator.resolve_asks` (kit.py:112-132):
  member available, field in `['constraints']+SOFT`, no duplicate `(member, field)`,
  total cost <= `ask_budget_remaining`, declined fields never charged meaningfully
  (filter to `field_status == 'not_asked'` so cost is never wasted).

- [ ] **Step 1: Append the failing tests**

Append `GroupETests`:

```python
class GroupETests(unittest.TestCase):
    EXPECTED = {'m29_uncertainty_aware', 'm30_targeted_info'}

    @staticmethod
    def _ask(mid, state):
        from registry import REGISTRY
        from kit import VERSION
        return REGISTRY[mid]({'schema_version': VERSION, 'phase': 'ask',
                              'state': state, 'memory': None})

    def test_registry_contains_group_e(self):
        from registry import REGISTRY
        self.assertTrue(self.EXPECTED.issubset(set(REGISTRY)))

    def test_asks_respect_budget_validity_and_reserve(self):
        for day in (0, 59):
            state = CommonHelperTests._state(day=day)
            mfs = {m['member_id']: m for m in state['members']}
            for mid in sorted(self.EXPECTED):
                resp = self._ask(mid, state)
                cost = sum(3 if a['field'] == 'constraints' else 1
                           for a in resp['asks'])
                self.assertLessEqual(cost, state['ask_budget_remaining'],
                                     (mid, day))
                seen = set()
                for a in resp['asks']:
                    key = (a['member_id'], a['field'])
                    self.assertNotIn(key, seen, (mid, day))
                    seen.add(key)
                    m = mfs[a['member_id']]
                    self.assertTrue(m['available'], (mid, day))
                    if a['field'] != 'constraints':
                        self.assertEqual(m['field_status'][a['field']],
                                         'not_asked', (mid, day))
                # SOFT_ASK_RESERVE=3: hard asks capped at (12-3)//3 = 3
                hard = [a for a in resp['asks'] if a['field'] == 'constraints']
                self.assertLessEqual(len(hard), 3, (mid, day))

    def test_m29_ranks_soft_asks_by_information_value(self):
        import common
        from kit import SOFT
        state = CommonHelperTests._state(day=59)
        mfs = {m['member_id']: m for m in state['members']}
        ctx = common.make_ctx(state)
        resp = self._ask('m29_uncertainty_aware', state)
        got = []
        for a in resp['asks']:
            if a['field'] == 'constraints':
                continue
            v = sum(1 for _s, nb in ctx['inc'].get(a['member_id'], ())
                    if mfs[nb]['fields'].get(a['field']) is not None)
            self.assertGreater(v, 0, a)
            got.append((-v, a['member_id'], a['field']))
        want = []
        for m in sorted(state['members'], key=lambda x: x['member_id']):
            if not m['available']:
                continue
            for k in sorted(SOFT):
                if m['field_status'].get(k) == 'not_asked':
                    v = sum(1 for _s, nb in ctx['inc'].get(m['member_id'], ())
                            if mfs[nb]['fields'].get(k) is not None)
                    if v > 0:
                        want.append((-v, m['member_id'], k))
        want.sort()
        self.assertEqual(got, want[:len(got)])

    def test_full_episode_group_e_parity_and_aliveness(self):
        from kit import generate, baseline_match
        from registry import REGISTRY
        for mid in sorted(self.EXPECTED):
            soft_asks = []

            def fn(request, _mid=mid, _sink=soft_asks):
                resp = REGISTRY[_mid](request)
                if request['phase'] == 'ask':
                    _sink.extend(a for a in resp['asks']
                                 if a['field'] != 'constraints')
                else:
                    self.assertEqual(resp['pairs'],
                                     baseline_match(request['state']), _mid)
                return resp

            metrics = run_inprocess(fn,
                                    generate(90214, 50, 'evaluation', 'cold_start'))
            self.assertIn('msmi_per_100_arrived_members', metrics, mid)
            self.assertGreater(len(soft_asks), 0, 'gate never fired: ' + mid)

    def test_m30_ask_latency_on_dense_day59_under_5s(self):
        import time
        state = CommonHelperTests._state(day=59)
        started = time.perf_counter()
        self._ask('m30_targeted_info', state)
        self.assertLess(time.perf_counter() - started, 5.0)

    def test_m30_voi_recomputations_bounded_by_cap(self):
        import alloc, common
        state = CommonHelperTests._state(day=59)
        real = alloc.greedy_take
        calls = []

        def counting(edges, _real=real):
            calls.append(1)
            return _real(edges)

        alloc.greedy_take = counting
        try:
            resp = self._ask('m30_targeted_info', state)
        finally:
            alloc.greedy_take = real
        self.assertIn('asks', resp)
        self.assertGreaterEqual(len(calls), 1)
        self.assertLessEqual(len(calls), common.VOI_EVAL_CAP)

    def test_m30_voi_cap_forces_truncation(self):
        import alloc, common
        state = CommonHelperTests._state(day=59)
        real_take, real_cap = alloc.greedy_take, common.VOI_EVAL_CAP

        def run_with_cap(cap):
            calls = []

            def counting(edges, _real=real_take):
                calls.append(1)
                return _real(edges)

            alloc.greedy_take = counting
            common.VOI_EVAL_CAP = cap
            try:
                self._ask('m30_targeted_info', state)
            finally:
                alloc.greedy_take = real_take
                common.VOI_EVAL_CAP = real_cap
            return len(calls)

        # cap=1: the base allocation consumes the only recomputation, so the
        # candidate loop must be skipped entirely (forced truncation branch).
        self.assertEqual(run_with_cap(1), 1)
        # cap=2: at most one option evaluation may follow the base pass.
        self.assertLessEqual(run_with_cap(2), 2)
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m unittest research.method_tournament.test_tournament.GroupETests -v`
Expected: FAIL `AssertionError` (registry missing group E) or `ModuleNotFoundError: methods_e`.

- [ ] **Step 3: Write `methods_e.py`**

```python
"""Group E: active asking (m29-m30). The ask phase selects soft fields within the
daily budget (hard asks first, capped to keep SOFT_ASK_RESERVE units for soft);
the match phase is control-parity baseline_match, so ask selection is the isolated
mechanism. Truth-blind: only kit.OPTIONS enumerations, never hidden state."""
from kit import baseline_asks, baseline_match, OPTIONS, SOFT
import common
import alloc


def _hard_asks_capped(state):
    """Control's hard-constraint asks, truncated so soft budget units remain."""
    cap = max(0, state['ask_budget_remaining'] - common.SOFT_ASK_RESERVE) // 3
    return baseline_asks(state)[:cap]


def _soft_candidates(state):
    """(member, field) eligible for a soft ask, sorted by (member_id, field)."""
    out = []
    for m in sorted(state['members'], key=lambda x: x['member_id']):
        if m['available']:
            for k in sorted(SOFT):
                if m['field_status'].get(k) == 'not_asked':
                    out.append((m, k))
    return out


def _alloc_key(pairs):
    return {common.pair_key(p[0], p[1]) for p in pairs}


def decide_m29(request):
    state = request['state']
    memory = request.get('memory')
    if request['phase'] == 'ask':
        budget = state['ask_budget_remaining']
        asks = _hard_asks_capped(state)
        spent = 3 * len(asks)
        ctx = common.make_ctx(state)
        mfs = {m['member_id']: m for m in state['members']}
        ranked = []
        for m, k in _soft_candidates(state):
            mid = m['member_id']
            value = sum(1 for _s, nb in ctx['inc'].get(mid, ())
                        if mfs[nb]['fields'].get(k) is not None)
            if value > 0:   # only immediately resolvable comparisons
                ranked.append((-value, mid, k))
        ranked.sort()
        for neg_value, mid, k in ranked:
            if spent + 1 > budget:
                break
            asks.append({'member_id': mid, 'field': k})
            spent += 1
        return {'asks': asks, 'memory': memory}
    return {'pairs': baseline_match(state), 'memory': memory}


def decide_m30(request):
    state = request['state']
    memory = request.get('memory')
    if request['phase'] == 'ask':
        budget = state['ask_budget_remaining']
        asks = _hard_asks_capped(state)
        spent = 3 * len(asks)
        edges = common.feasible_edges(state)
        mfs = {m['member_id']: m for m in state['members']}
        ctx = common.make_ctx(state, edges)
        base_alloc = _alloc_key(alloc.greedy_take(edges))
        recomputations = 1   # VOI_EVAL_CAP greedy passes (design section 6 table)
        edge_idx = {}
        for i, (a, b, _s) in enumerate(edges):
            edge_idx.setdefault(a, []).append(i)
            edge_idx.setdefault(b, []).append(i)
        for m, k in _soft_candidates(state):
            if recomputations >= common.VOI_EVAL_CAP:
                break   # preregistered cap in fixed (member, field) order
            if spent + 1 > budget:
                break
            mid = m['member_id']
            # Exact skip: if no feasible partner has observed k, no option can
            # change any incident score, so the allocation is provably unchanged.
            if not any(mfs[nb]['fields'].get(k) is not None
                       for _s, nb in ctx['inc'].get(mid, ())):
                continue
            touched = edge_idx.get(mid, [])
            orig_scores = [edges[i][2] for i in touched]
            original = m['fields'].get(k)
            changed = False
            try:
                for opt in OPTIONS[k]:   # truth-blind enumeration
                    if recomputations >= common.VOI_EVAL_CAP:
                        break
                    recomputations += 1
                    m['fields'][k] = opt
                    for i in touched:
                        a, b, _s = edges[i]
                        edges[i] = (a, b, common.base_score(mfs[a], mfs[b]))
                    if _alloc_key(alloc.greedy_take(edges)) != base_alloc:
                        changed = True
                        break
            finally:
                m['fields'][k] = original
                for i, sc in zip(touched, orig_scores):
                    a, b, _s = edges[i]
                    edges[i] = (a, b, sc)
            if changed:
                asks.append({'member_id': mid, 'field': k})
                spent += 1
        return {'asks': asks, 'memory': memory}
    return {'pairs': baseline_match(state), 'memory': memory}


DECISIONS = {
    'm29_uncertainty_aware': decide_m29,
    'm30_targeted_info': decide_m30,
}
```

- [ ] **Step 4: Update `registry.py` (full file content)**

```python
"""Executable registry: method_id -> decide function. Rerun gen_policies.py after
any change (every launcher imports its decide from here)."""
from methods_a import DECISIONS as DECISIONS_A
from methods_b import DECISIONS as DECISIONS_B
from methods_c import DECISIONS as DECISIONS_C
from methods_d import DECISIONS as DECISIONS_D
from methods_e import DECISIONS as DECISIONS_E

REGISTRY = {}
REGISTRY.update(DECISIONS_A)
REGISTRY.update(DECISIONS_B)
REGISTRY.update(DECISIONS_C)
REGISTRY.update(DECISIONS_D)
REGISTRY.update(DECISIONS_E)
```

- [ ] **Step 5: Regenerate launchers and flip registry status**

```powershell
python research/method_tournament/gen_policies.py
python -c "import json,pathlib; p=pathlib.Path('research/method_tournament/methods.json'); d=json.loads(p.read_text(encoding='utf-8')); [m.update(implementation_status='implemented') for m in d['methods'] if m['group']=='E']; p.write_text(json.dumps(d, indent=2, ensure_ascii=False)+chr(10), encoding='utf-8'); print('group E -> implemented')"
```
Expected: `wrote 30 launchers`, `group E -> implemented`.

- [ ] **Step 6: Run tests to verify green**

Run: `python -m unittest research.method_tournament.test_tournament.GroupETests -v`
Expected: PASS (7 new tests; full-episode ~2-4 minutes, latency test ~10-20 s).

- [ ] **Step 7: Log the milestone**

```powershell
Add-Content -Path research\method_tournament\run_log.txt -Value ("{0} Task9 complete: group E (2 methods) incl. budget/reserve and VoI cap/gate tests" -f (Get-Date -Format o))
```

No commit (spec Section 14).

---
### Task 10: Completeness and Full Regression (all 30 wired)

**Files:**
- Test: append `RegistryCompletenessTests` to `test_tournament.py` (before `if __name__ == '__main__':`)
- No source changes. This task proves Tasks 1-9 composed correctly before any official-protocol run.

**Interfaces:**
- Consumes: `methods.json`, `registry.REGISTRY`, `policies/*.py`.
- Produces: regression evidence that every registry/launcher/status surface agrees at exactly 30.

- [ ] **Step 1: Append the completeness tests**

```python
class RegistryCompletenessTests(unittest.TestCase):
    def test_methods_json_all_implemented(self):
        data = json.loads(METHODS_JSON.read_text(encoding='utf-8'))
        self.assertEqual(len(data['methods']), 30)
        pending = [m['method_id'] for m in data['methods']
                   if m['implementation_status'] != 'implemented']
        self.assertEqual(pending, [], pending)

    def test_registry_matches_methods_json(self):
        from registry import REGISTRY
        data = json.loads(METHODS_JSON.read_text(encoding='utf-8'))
        ids = {m['method_id'] for m in data['methods']}
        self.assertEqual(set(REGISTRY), ids)
        for mid, fn in REGISTRY.items():
            self.assertTrue(callable(fn), mid)

    def test_policies_dir_exactly_matches_registry(self):
        from registry import REGISTRY
        files = sorted(p.stem for p in (HERE / 'policies').glob('*.py'))
        self.assertEqual(files, sorted(REGISTRY))
        self.assertEqual(len(files), 30)

    def test_group_counts_match_design(self):
        from collections import Counter
        data = json.loads(METHODS_JSON.read_text(encoding='utf-8'))
        counts = Counter(m['group'] for m in data['methods'])
        self.assertEqual(dict(counts), {'A': 8, 'B': 7, 'C': 8, 'D': 5, 'E': 2})
```

- [ ] **Step 2: Run the completeness tests**

Run: `python -m unittest research.method_tournament.test_tournament.RegistryCompletenessTests -v`
Expected: 4 tests PASS immediately. If any fails, a wiring step from Tasks 5-9 was
missed (status flip, launcher regeneration, registry entry) - go back and redo THAT
step's commands; do not edit these tests.

- [ ] **Step 3: Run the whole tournament module**

Run: `python -m unittest research.method_tournament.test_tournament -v`
Expected: ALL tests PASS (Tasks 1-10). This is the long run - the per-group
full-episode tests together take roughly 15-30 minutes. Any failure blocks all
official phases.

- [ ] **Step 4: Regression - frozen repo suites still pass**

Run: `python -m unittest test_kit test_runner test_release test_policy research.test_pipeline -v`
Expected: all PASS (takes several minutes; test_policy includes subprocess
integration tests). These suites are frozen - a failure means a frozen file was
touched: STOP and report the hash mismatch against `integrity/frozen_before.txt`; never edit frozen files or frozen tests, and never run a git command to fix it.

- [ ] **Step 5: Verify the git baseline is preserved**

```powershell
git status --short; git rev-parse --short HEAD
```
Expected: HEAD `a8e26b3`; status exactly:
```
 M policy.py
?? docs/superpowers/
?? policy_ac.py
?? research/
?? test_policy.py
```
(Nothing staged, nothing committed, no other modified tracked file.)

- [ ] **Step 6: Log the milestone**

```powershell
Add-Content -Path research\method_tournament\run_log.txt -Value ("{0} Task10 complete: 30/30 wired; full tournament module + frozen suites green" -f (Get-Date -Format o))
```

No commit (spec Section 14).

---
### Task 11: Phase Runner, Sweeps, Integrity Snapshot, and Smoke Gate

**Files:**
- Create: `research/method_tournament/run_tournament.py`,
  `research/method_tournament/instrument.py`
- Test: append `RunnerTests`, `AllRegistrySweepTests`, `InstrumentTests` to `test_tournament.py` (before `if __name__ == '__main__':`)
- Generate: `integrity/before.txt`, `integrity/git_before.txt`, `per_phase/smoke_rows.jsonl`, `per_phase/smoke.done`

**Interfaces:**
- Consumes: `evaluate.episode` (official 60-day subprocess protocol, returns metrics +
  `valid` + `action_sha256` + `inference_seconds`), `kit.generate`, `methods.json`,
  `registry.REGISTRY` (tests only).
- Produces:
  - `PHASES`: frozen phase configs (smoke/screening/confirm1/confirm2).
  - `load_methods(phase)`: smoke/screening -> all implemented ids; confirm1 ->
  `screening_results.json["retained"]` (written Task 12); confirm2 ->
  `confirmation_results.json["selected"]` (written Task 13). Those keys are a contract.
  - `verify_freeze(manifest, base)`: sha256 check of every line `<digest>  <relpath>`
    against `base/relpath`; raises `SystemExit` on mismatch (design.md section 8).
  - `dedupe/load_rows/row_key`: append-only jsonl semantics - later rows overwrite
    earlier ones per `(method, seed, variant)`; only valid rows count as done, so a
    transient invalid (e.g. timeout) is retried on resume.
  - `expected_keys(phase, methods)`, `worlds(phase)` - pure config helpers for tests.
  - `code_fingerprint()` / `purge_stale()` / `append_attempt()` - version-safe
    rows: every row carries `code_sha256`, foreign-fingerprint resumes purge the
    whole phase file to `per_phase/<phase>_rows_v<hex8>.jsonl`, every invocation
    lands in `per_phase/<phase>_attempts.jsonl` (design section 8).
  - Episode row: `evaluate.episode(...)` result + `phase/method/seed/variant/code_sha256`.
  - `instrument.instrument_episode/arms_for/PHASE_CFG` - the two-pass instrument
    tool (created here pre-freeze; executed in Tasks 12 and 15, design section 5).

- [ ] **Step 1: Append the failing tests**

Append `RunnerTests`, `AllRegistrySweepTests`, and `InstrumentTests`:

```python
class RunnerTests(unittest.TestCase):
    def test_phase_configs_preregistered(self):
        import run_tournament as rt
        self.assertEqual(rt.PHASES['smoke'],
                         {'seeds': (90290,), 'variants': ('development',)})
        self.assertEqual(rt.PHASES['screening']['seeds'], (143, 144, 145))
        self.assertEqual(rt.PHASES['confirm1']['seeds'], tuple(range(146, 152)))
        self.assertEqual(rt.PHASES['confirm2']['seeds'], tuple(range(152, 164)))
        self.assertEqual(tuple(rt.PHASES['screening']['variants']),
                         ('development', 'sparse', 'cold_start',
                          'delayed', 'shift', 'drift'))
        self.assertEqual(len(rt.worlds('smoke')), 1)
        self.assertEqual(len(rt.worlds('screening')), 18)
        self.assertEqual(len(rt.worlds('confirm1')), 36)
        self.assertEqual(len(rt.worlds('confirm2')), 72)

    def test_expected_episode_counts(self):
        import run_tournament as rt
        all30 = ['m%02d_dummy' % i for i in range(1, 31)]
        self.assertEqual(len(rt.expected_keys('smoke', all30 + [rt.CONTROL])), 31)
        self.assertEqual(len(rt.expected_keys('screening', all30 + [rt.CONTROL])), 558)
        self.assertEqual(len(rt.expected_keys('confirm1', all30[:5] + [rt.CONTROL])), 216)
        self.assertEqual(len(rt.expected_keys('confirm2', all30[:2] + [rt.CONTROL])), 216)

    def test_load_methods_smoke_and_screening(self):
        import run_tournament as rt
        self.assertEqual(len(rt.load_methods('smoke')), 30)
        self.assertEqual(rt.load_methods('screening'), sorted(rt.load_methods('smoke')))

    def test_resume_last_wins_and_only_valid_counts_done(self):
        import run_tournament as rt
        import tempfile
        import pathlib as pl
        with tempfile.TemporaryDirectory() as td:
            path = pl.Path(td) / 'rows.jsonl'
            rows = [
                {'method': 'mA', 'seed': 1, 'variant': 'development',
                 'valid': False, 'error': 'timeout'},
                {'method': 'mA', 'seed': 1, 'variant': 'development',
                 'valid': True, 'msmi_per_100_arrived_members': 0.5},
                {'method': 'mB', 'seed': 1, 'variant': 'development', 'valid': True},
            ]
            path.write_text(''.join(json.dumps(r) + chr(10) for r in rows),
                            encoding='utf-8')
            prior = rt.dedupe(rt.load_rows(path))
            self.assertEqual(len(prior), 2)
            done = {rt.row_key(r) for r in prior if r.get('valid')}
            self.assertEqual(done, {('mA', 1, 'development'),
                                    ('mB', 1, 'development')})
            self.assertTrue(all(r.get('valid') for r in prior))

    def test_freeze_verification_passes_then_fails_on_change(self):
        import run_tournament as rt
        import tempfile
        import hashlib
        import pathlib as pl
        with tempfile.TemporaryDirectory() as td:
            base = pl.Path(td)
            target = base / 'methods_a.py'
            target.write_text('x = 1\n', encoding='utf-8')
            manifest = base / 'freeze.txt'
            digest = hashlib.sha256(target.read_bytes()).hexdigest()
            manifest.write_text(digest + '  methods_a.py' + chr(10),
                                encoding='utf-8')
            rt.verify_freeze(manifest, base=base)
            target.write_text('x = 2\n', encoding='utf-8')
            with self.assertRaises(SystemExit):
                rt.verify_freeze(manifest, base=base)

    def test_commands_point_at_real_files(self):
        import run_tournament as rt
        ctrl = rt.control_command()
        self.assertEqual(ctrl[-3:], [str(rt.ROOT / 'policy.py'),
                                     '--baseline', 'greedy'])
        self.assertTrue(pathlib.Path(ctrl[1]).exists())
        cmd = rt.method_command('m01_greedy_baseline')
        self.assertTrue(pathlib.Path(cmd[1]).exists())

    def test_code_fingerprint_is_total_and_deterministic(self):
        import run_tournament as rt
        self.assertEqual(rt.code_fingerprint(), rt.code_fingerprint())
        fp = rt.code_fingerprint()
        self.assertEqual(len(fp), 64)
        for rel in rt.CODE_FILES:
            p = (rt.ROOT / rel) if rel in rt.ROOT_FILES else (rt.HERE / rel)
            self.assertTrue(p.exists(), 'fingerprint input missing: ' + rel)
        self.assertTrue(list((rt.HERE / 'policies').glob('*.py')))

    def test_purge_stale_archives_foreign_fingerprint_only(self):
        import run_tournament as rt
        import tempfile
        import pathlib as pl
        with tempfile.TemporaryDirectory() as td:
            path = pl.Path(td) / 'screening_rows.jsonl'
            self.assertIsNone(rt.purge_stale(path, 'f' * 64))
            path.write_text(json.dumps(
                {'method': 'm', 'seed': 1, 'variant': 'development',
                 'valid': True, 'code_sha256': 'a' * 64}) + chr(10),
                encoding='utf-8')
            self.assertIsNone(rt.purge_stale(path, 'a' * 64))
            self.assertTrue(path.exists())
            archive = rt.purge_stale(path, 'b' * 64)
            self.assertIsNotNone(archive)
            self.assertFalse(path.exists())
            self.assertTrue(archive.exists())
            self.assertTrue(archive.name.startswith('screening_rows_v'))
            self.assertEqual(
                len(list(pl.Path(td).glob('screening_rows_v*.jsonl'))), 1)

    def test_attempt_log_appends_full_record_shape(self):
        import run_tournament as rt
        import tempfile
        import pathlib as pl
        with tempfile.TemporaryDirectory() as td:
            path = pl.Path(td) / 'smoke_attempts.jsonl'
            self.assertEqual(
                rt.append_attempt(path, 'smoke', 'f' * 64, 3, 3, 0, None, 0), 0)
            recs = [json.loads(l) for l in
                    path.read_text(encoding='utf-8').splitlines() if l]
            self.assertEqual(len(recs), 1)
            self.assertEqual(set(recs[0]), {'ts', 'phase', 'fingerprint',
                                            'episodes_planned',
                                            'episodes_written', 'invalid',
                                            'purged', 'exit'})
            rt.append_attempt(path, 'smoke', 'e' * 64, 5, 2, 1,
                              'screening_rows_vdeadbeef.jsonl', 2)
            self.assertEqual(len(path.read_text(
                encoding='utf-8').splitlines()), 2)


class AllRegistrySweepTests(unittest.TestCase):
    def test_file_inventory_is_exactly_40(self):
        targets = [HERE / n for n in ('common.py', 'alloc.py', '_cli.py',
                                      'registry.py', 'gen_policies.py')]
        targets += sorted(HERE.glob('methods_*.py'))
        targets += sorted((HERE / 'policies').glob('*.py'))
        existing = [p for p in targets if p.exists()]
        # 5 shared + 5 group modules + 30 launchers; LeakScanTests scans all of them.
        self.assertEqual(len(existing), 40)

    def test_all_methods_ask_and_match_latency_day59_under_5s(self):
        import time
        from registry import REGISTRY
        from kit import VERSION
        state = CommonHelperTests._state(day=59)
        for mid in sorted(REGISTRY):
            for phase in ('ask', 'match'):
                req = {'schema_version': VERSION, 'phase': phase,
                       'state': state, 'memory': None}
                started = time.perf_counter()
                REGISTRY[mid](dict(req))
                self.assertLess(time.perf_counter() - started, 5.0, (mid, phase))

    def test_all_methods_deterministic_on_ask_and_match(self):
        from registry import REGISTRY
        from kit import VERSION
        state = CommonHelperTests._state(day=30)
        for mid in sorted(REGISTRY):
            for phase in ('ask', 'match'):
                req = {'schema_version': VERSION, 'phase': phase,
                       'state': state, 'memory': None}
                r1 = REGISTRY[mid](dict(req))
                r2 = REGISTRY[mid](dict(req))
                self.assertEqual(json.dumps(r1, sort_keys=True),
                                 json.dumps(r2, sort_keys=True), (mid, phase))


class InstrumentTests(unittest.TestCase):
    def test_episode_replica_digest_parity_and_bounds(self):
        import evaluate
        import instrument
        import run_tournament as rt
        from kit import generate
        world = generate(90217, 200, 'evaluation', 'development')
        row = instrument.instrument_episode(world, rt.control_command())
        ref = evaluate.episode(world, rt.control_command())
        self.assertEqual(row['action_sha256'], ref['action_sha256'])
        self.assertEqual(len(row['action_sha256']), 64)
        self.assertTrue(row['valid'])
        self.assertTrue(0 <= row['zero_selection_days'] <= 60)
        self.assertGreaterEqual(row['intros_per_100'], 0.0)

    def test_arms_for_both_phases(self):
        import instrument
        self.assertEqual(instrument.arms_for({}, 'selected'), [])
        self.assertEqual(instrument.arms_for({'selected': []}, 'selected'), [])
        self.assertEqual(instrument.arms_for({'selected': ['m02_x']},
                                             'selected'), ['m02_x'])
        self.assertEqual(instrument.arms_for({'retained': ['m05_z']},
                                             'retained'), ['m05_z'])
        self.assertEqual(instrument.arms_for({}, 'retained'), [])

    def test_phase_config_covers_screening_and_final(self):
        import instrument
        self.assertEqual(set(instrument.PHASE_CFG), {'screening', 'confirm2'})
        self.assertEqual(instrument.PHASE_CFG['screening']['seed'], 143)
        self.assertEqual(instrument.PHASE_CFG['confirm2']['seed'], 152)
        self.assertEqual(instrument.PHASE_CFG['screening']['key'], 'retained')
        self.assertEqual(instrument.PHASE_CFG['confirm2']['key'], 'selected')
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m unittest research.method_tournament.test_tournament.RunnerTests research.method_tournament.test_tournament.AllRegistrySweepTests research.method_tournament.test_tournament.InstrumentTests -v`
Expected: `RunnerTests` - 9 ERRORs (`ModuleNotFoundError: No module named
'run_tournament'`), `InstrumentTests` - 3 ERRORs (`No module named 'instrument'`).
`AllRegistrySweepTests` - may pass already (files exist); any latency/determinism
failure identifies a specific method to fix BEFORE any official run.

- [ ] **Step 3: Write `run_tournament.py`**

```python
"""Phase runner for the method tournament (design.md section 4).

Runs a named phase over its frozen seed x variant grid. Every arm is executed
through the official evaluate.episode subprocess protocol (60 decision days +
40 follow-up); the shared greedy control is `policy.py --baseline greedy`, run
once per world. Episode rows append to per_phase/<phase>_rows.jsonl (resumable,
later rows overwrite earlier per (method, seed, variant)); a done flag seals a
completed phase. confirm1/confirm2 verify hashes/policy_freeze_after_screening.txt
before executing (design.md section 8).
"""
import argparse
import hashlib
import json
import pathlib
import sys
import time
from concurrent.futures import ThreadPoolExecutor

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))
import evaluate  # noqa: E402  (frozen repo harness, imported after path setup)
from kit import generate  # noqa: E402

VARIANTS = ('development', 'sparse', 'cold_start', 'delayed', 'shift', 'drift')
CONTROL = '__control__'
PHASES = {
    'smoke': {'seeds': (90290,), 'variants': ('development',)},
    'screening': {'seeds': (143, 144, 145), 'variants': VARIANTS},
    'confirm1': {'seeds': (146, 147, 148, 149, 150, 151), 'variants': VARIANTS},
    'confirm2': {'seeds': (152, 153, 154, 155, 156, 157,
                           158, 159, 160, 161, 162, 163), 'variants': VARIANTS},
}
FREEZE_MANIFEST = HERE / 'hashes' / 'policy_freeze_after_screening.txt'
ROOT_FILES = frozenset(('kit.py', 'policy.py', 'policy_ac.py',
                        'evaluate.py', 'organise.py', 'Dockerfile'))
CODE_FILES = ('methods_a.py', 'methods_b.py', 'methods_c.py', 'methods_d.py',
              'methods_e.py', 'common.py', 'alloc.py', 'registry.py',
              '_cli.py', 'gen_policies.py', 'run_tournament.py',
              'analyse_tournament.py', 'instrument.py', 'design.md',
              'methods.json', 'kit.py', 'policy.py', 'policy_ac.py',
              'evaluate.py', 'organise.py', 'Dockerfile')


def code_fingerprint():
    """SHA-256 over the full behavior/spec file list (design.md section 8).

    The digest is carried on every runner row. On resume, any row with a
    foreign digest triggers a whole-phase purge to
    per_phase/<phase>_rows_v<hex8>.jsonl so two code versions can never mix
    inside one phase file; every invocation is appended to
    per_phase/<phase>_attempts.jsonl regardless of outcome.
    """
    h = hashlib.sha256()
    for rel in CODE_FILES:
        path = (ROOT / rel) if rel in ROOT_FILES else (HERE / rel)
        h.update(rel.encode('utf-8') + b'\0')
        h.update(path.read_bytes())
        h.update(b'\0')
    for launcher in sorted((HERE / 'policies').glob('*.py')):
        h.update(launcher.name.encode('utf-8') + b'\0')
        h.update(launcher.read_bytes())
        h.update(b'\0')
    return h.hexdigest()


def control_command():
    return [sys.executable, str(ROOT / 'policy.py'), '--baseline', 'greedy']


def method_command(mid):
    return [sys.executable, str(HERE / 'policies' / (mid + '.py')),
            '--baseline', 'greedy']


def worlds(phase):
    cfg = PHASES[phase]
    return [(seed, variant) for seed in cfg['seeds'] for variant in cfg['variants']]


def load_methods(phase):
    """Arms for a phase, excluding the shared control (design.md section 4)."""
    if phase in ('smoke', 'screening'):
        data = json.loads((HERE / 'methods.json').read_text(encoding='utf-8'))
        return sorted(m['method_id'] for m in data['methods']
                      if m['implementation_status'] == 'implemented')
    if phase == 'confirm1':
        return json.loads((HERE / 'screening_results.json')
                          .read_text(encoding='utf-8'))['retained']
    if phase == 'confirm2':
        return json.loads((HERE / 'confirmation_results.json')
                          .read_text(encoding='utf-8'))['selected']
    raise ValueError('unknown phase: ' + phase)


def verify_freeze(manifest=FREEZE_MANIFEST, base=None):
    """Design section 8: abort if any frozen file changed since screening.

    Manifest lines are `<digest>  <repo-root-relative path>`; default base is
    the repo root so the same manifest verifies from any working directory.
    """
    base = ROOT if base is None else base
    if not pathlib.Path(manifest).exists():
        raise SystemExit('freeze manifest missing: ' + str(manifest))
    bad = []
    for line in pathlib.Path(manifest).read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line:
            continue
        digest, rel = line.split(None, 1)
        target = base / rel.strip()
        if not target.exists() or \
                hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            bad.append(rel.strip())
    if bad:
        raise SystemExit('freeze verification FAILED: ' + ', '.join(sorted(bad)))


def row_key(row):
    return (row['method'], row['seed'], row['variant'])


def load_rows(path):
    rows = []
    if path.exists():
        for line in path.read_text(encoding='utf-8').splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows


def dedupe(rows):
    """Append-only semantics: the last row per (method, seed, variant) wins."""
    out = {}
    for row in rows:
        out[row_key(row)] = row
    return list(out.values())


def expected_keys(phase, methods):
    return {(m, seed, variant) for m in methods
            for seed, variant in worlds(phase)}


def purge_stale(rows_path, fp):
    """Archive a phase file written under a different code fingerprint.

    Whole-phase purge (design.md section 8): rows from two code versions can
    never share one file. Returns the archive path, or None when nothing was
    archived (file missing or every row already carries fp).
    """
    if not rows_path.exists():
        return None
    prior = load_rows(rows_path)
    if not any(r.get('code_sha256') != fp for r in prior):
        return None
    tag = hashlib.sha256(rows_path.read_bytes()).hexdigest()[:8]
    archive = rows_path.with_name('%s_v%s.jsonl' % (rows_path.stem, tag))
    rows_path.rename(archive)
    return archive


def append_attempt(path, phase, fingerprint, planned, written, invalid,
                   purged, code):
    """Append-only attempt history (design.md section 8).

    Every runner invocation is recorded regardless of outcome - including
    purges, incomplete runs (exit 2), and sealed-phase no-ops - so failed
    attempts stay visible in per_phase/<phase>_attempts.jsonl.
    """
    rec = {'ts': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
           'phase': phase, 'fingerprint': fingerprint,
           'episodes_planned': planned, 'episodes_written': written,
           'invalid': invalid, 'purged': purged, 'exit': code}
    with path.open('a', encoding='utf-8') as fh:
        fh.write(json.dumps(rec, sort_keys=True, allow_nan=False) + '\n')
    return code


def run_one(phase, method, seed, variant, code_sha256):
    cmd = control_command() if method == CONTROL else method_command(method)
    try:
        row = evaluate.episode(generate(seed, 200, 'evaluation', variant), cmd)
    except (ValueError, TypeError, KeyError, OSError) as error:
        row = {'valid': False, 'error': str(error)}
    row.update(phase=phase, method=method, seed=seed, variant=variant,
               code_sha256=code_sha256)
    return row


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', required=True, choices=sorted(PHASES))
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args(argv)
    phase = args.phase
    if phase in ('confirm1', 'confirm2'):
        verify_freeze()
    methods = load_methods(phase) + [CONTROL]
    per_phase = HERE / 'per_phase'
    per_phase.mkdir(exist_ok=True)
    rows_path = per_phase / (phase + '_rows.jsonl')
    done_path = per_phase / (phase + '.done')
    attempts_path = per_phase / (phase + '_attempts.jsonl')
    fp = code_fingerprint()
    if phase == 'screening':
        # First attempt records the pre-screening fingerprint; never overwritten
        # (analysis asserts every row against it - design.md section 8).
        pre = HERE / 'hashes' / 'pre_screening_fingerprint.txt'
        pre.parent.mkdir(exist_ok=True)
        if not pre.exists():
            pre.write_text(fp + '\n', encoding='utf-8')

    if done_path.exists():
        print('phase already sealed: %s (delete per_phase/%s.done to rerun)'
              % (phase, phase))
        return append_attempt(attempts_path, phase, fp, 0, 0, 0, None, 0)
    archived = purge_stale(rows_path, fp)
    purged = archived.name if archived else None
    if purged:
        print('code fingerprint changed: prior rows archived to %s' % purged,
              flush=True)
    prior = dedupe(load_rows(rows_path))
    done = {row_key(r) for r in prior if r.get('valid')}
    todo = [(m, seed, variant) for m in methods
            for seed, variant in worlds(phase)
            if (m, seed, variant) not in done]
    print('%s: %d valid rows sealed, %d episodes to run (fp %s)'
          % (phase, len(done), len(todo), fp[:16]), flush=True)
    started = time.time()
    written = 0
    if todo:
        with rows_path.open('a', encoding='utf-8') as sink, \
                ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
            futures = [pool.submit(run_one, phase, m, s, v, fp)
                       for m, s, v in todo]
            for i, future in enumerate(futures, 1):
                row = future.result()
                sink.write(json.dumps(row, sort_keys=True, allow_nan=False) + '\n')
                sink.flush()
                written = i
                if i % 10 == 0 or i == len(futures):
                    print('  %d/%d episodes written' % (i, len(futures)),
                          flush=True)
    rows = dedupe(load_rows(rows_path))
    missing = sorted(expected_keys(phase, methods) - {row_key(r) for r in rows})
    invalid = sorted(row_key(r) for r in rows if not r.get('valid'))
    summary = {'phase': phase, 'arms': methods, 'worlds': len(worlds(phase)),
               'episodes': len(rows), 'invalid': len(invalid),
               'invalid_keys': [list(k) for k in invalid],
               'missing': [list(k) for k in missing],
               'code_sha256': fp, 'purged': purged,
               'wall_seconds': round(time.time() - started, 1)}
    print(json.dumps(summary, indent=2, sort_keys=True))
    if missing:
        return append_attempt(attempts_path, phase, fp, len(todo), written, len(invalid), purged, 2)
    done_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + '\n',
                         encoding='utf-8')
    with (HERE / 'run_log.txt').open('a', encoding='utf-8') as log:
        log.write('%s phase %s sealed: %d episodes, %d invalid (fp %s)\n'
                  % (time.strftime('%Y-%m-%dT%H:%M:%S'), phase,
                     len(rows), len(invalid), fp[:16]))
    return append_attempt(attempts_path, phase, fp, len(todo), written,
                          len(invalid), purged, 0 if not invalid else 3)


if __name__ == '__main__':
    raise SystemExit(main())
```

- [ ] **Step 4: Write `instrument.py` (created here pre-freeze; executed in Tasks 12 and 15)**

```python
"""Instrument pass (design.md section 5): secondary diagnostics that official
episode rows do not carry - zero-selection days, mutual per introduction, MSMI
per introduction - computed by re-running a bounded official sample and
digest-verifying every re-run against the sealed phase rows. Two passes:

  --phase screening   seed 143 x 6 variants x (retained + control), <= 54
                      episodes; run after the retention gate and before the
                      freeze (Task 12); appends to screening_report.md.
  --phase confirm2    seed 152 x 6 variants x (selected + control), <= 18
                      episodes; run after the final verdict (Task 15); appends
                      to final_report.md; records a skipped summary when
                      Phase 3 was skipped.

Diagnostic only: instrument output is NEVER a ranking or selection input.
"""
import argparse
import hashlib
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))
import evaluate  # noqa: E402
import run_tournament as rt  # noqa: E402
from kit import VERSION, Simulator, generate  # noqa: E402

PHASE_CFG = {
    'screening': {'seed': 143, 'rows': 'screening_rows.jsonl',
                  'results': 'screening_results.json', 'key': 'retained',
                  'report': 'screening_report.md',
                  'summary': 'instrument_screening.json',
                  'rows_out': 'instrument_rows_screening.jsonl'},
    'confirm2': {'seed': 152, 'rows': 'confirm2_rows.jsonl',
                 'results': 'confirmation_results.json', 'key': 'selected',
                 'report': 'final_report.md',
                 'summary': 'instrument_summary.json',
                 'rows_out': 'instrument_rows.jsonl'},
}


def arms_for(results, key):
    """Arm list for an analysis-results file; [] when the key is absent/empty."""
    return list(results.get(key) or [])


def instrument_episode(world, command, timeout=10):
    """evaluate.episode replica that also counts zero-selection days.

    Byte-identical action_sha256 digests for the same world and command are
    required: design.md section 5 says the instrument pass is digest-verified
    against official rows.
    """
    sim = Simulator(world)
    memory = None
    digest = hashlib.sha256()
    zero_selection_days = 0
    for _ in range(60):
        made_a_match = False
        for phase in ('ask', 'match'):
            request = {'schema_version': VERSION, 'phase': phase,
                       'state': sim.observe(), 'memory': memory}
            response, _elapsed = evaluate.invoke(command, request, timeout)
            memory = response['memory']
            action = response['asks' if phase == 'ask' else 'pairs']
            digest.update(json.dumps([phase, sim.day, action],
                                     sort_keys=True).encode())
            if phase == 'ask':
                sim.resolve_asks(action)
            else:
                if action:
                    made_a_match = True
                sim.advance(action)
        if not made_a_match:
            zero_selection_days += 1
    arrived = {m['member_id']: m['arrived_day']
               for m in sim.observe()['members'] if m['arrived_day'] <= 59}
    for _ in range(40):
        sim.advance([])
    result = sim.metrics()
    first = {}
    for intro in sim.introductions:
        for member in (intro['user_a'], intro['user_b']):
            first.setdefault(member, intro['assigned_day'])
    assignments = max(1, result['assignments'])
    result.update(
        valid=True,
        zero_selection_days=zero_selection_days,
        action_sha256=digest.hexdigest(),
        arrived_members=len(arrived),
        served_members=len(first),
        coverage=len(first) / max(1, len(arrived)),
        intros_per_100=100.0 * result['assignments'] / max(1, len(arrived)),
        mutual_per_introduction=result['mutual_acceptances'] / assignments,
        msmi_per_introduction=result['mutual_second_meeting_intention'] / assignments,
    )
    return result


def _append_report(report, summary, methods, per_arm, phase):
    with report.open('a', encoding='utf-8') as fh:
        fh.write('\n## Instrument pass - %s (diagnostic only)\n\n' % phase)
        if summary.get('skipped'):
            fh.write('- Skipped: %s\n' % summary['reason'])
            return
        fh.write('- Sample: seed %d x 6 variants; digests verified against '
                 'official %s rows: %d/%d match.\n'
                 % (summary['sample_seed'], phase, summary['digest_matches'],
                    summary['episodes']))
        fh.write('- Never a ranking input (design section 5).\n\n')
        fh.write('| arm | zero-selection days | intros/100 | mutual/intro | '
                 'MSMI/intro | coverage | ask cost |\n')
        fh.write('|---|---|---|---|---|---|---|\n')
        for method in methods:
            s = per_arm[method]
            fh.write('| %s | %s | %s | %s | %s | %s | %s |\n' % (
                method, s['zero_selection_days_mean'], s['intros_per_100_mean'],
                s['mutual_per_introduction_mean'],
                s['msmi_per_introduction_mean'], s['coverage_mean'],
                s['ask_cost_mean']))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', required=True, choices=sorted(PHASE_CFG))
    args = parser.parse_args(argv)
    cfg = PHASE_CFG[args.phase]
    checks = HERE / 'deterministic_checks'
    checks.mkdir(exist_ok=True)
    res_path = HERE / cfg['results']
    results = (json.loads(res_path.read_text(encoding='utf-8'))
               if res_path.exists() else {})
    arms = arms_for(results, cfg['key'])
    report = HERE / cfg['report']
    if args.phase == 'confirm2' and not arms:
        summary = {'skipped': True, 'episodes': 0,
                   'reason': 'no Phase-3 arms '
                             '(confirmation_results.selected empty)'}
        (checks / cfg['summary']).write_text(
            json.dumps(summary, indent=2, sort_keys=True) + '\n',
            encoding='utf-8')
        if report.exists():
            _append_report(report, summary, [], {}, args.phase)
        print(json.dumps(summary, indent=2))
        return 0
    official = {}
    for r in rt.dedupe(rt.load_rows(HERE / 'per_phase' / cfg['rows'])):
        official[(r['method'], r['seed'], r['variant'])] = r
    methods = list(arms) + [rt.CONTROL]
    rows = []
    for method in methods:
        cmd = (rt.control_command() if method == rt.CONTROL
               else rt.method_command(method))
        for variant in rt.VARIANTS:
            row = instrument_episode(
                generate(cfg['seed'], 200, 'evaluation', variant), cmd)
            row.update(method=method, seed=cfg['seed'], variant=variant)
            off = official.get((method, cfg['seed'], variant))
            row['official_action_sha256'] = (off['action_sha256']
                                             if off else None)
            row['digest_match'] = bool(off and off.get('valid')) and (
                row['action_sha256'] == off['action_sha256'])
            rows.append(row)
    with (checks / cfg['rows_out']).open('w', encoding='utf-8') as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True, allow_nan=False) + '\n')
    per_arm = {}
    for method in methods:
        mrows = [r for r in rows if r['method'] == method]
        n = max(1, len(mrows))
        per_arm[method] = {
            'episodes': len(mrows),
            'zero_selection_days_mean': round(
                sum(r['zero_selection_days'] for r in mrows) / n, 2),
            'intros_per_100_mean': round(
                sum(r['intros_per_100'] for r in mrows) / n, 3),
            'mutual_per_introduction_mean': round(
                sum(r['mutual_per_introduction'] for r in mrows) / n, 4),
            'msmi_per_introduction_mean': round(
                sum(r['msmi_per_introduction'] for r in mrows) / n, 4),
            'coverage_mean': round(
                sum(r['coverage'] for r in mrows) / n, 4),
            'ask_cost_mean': round(
                sum(r['ask_cost'] for r in mrows) / n, 1),
        }
    summary = {'skipped': False, 'phase': args.phase,
               'sample_seed': cfg['seed'],
               'variants': list(rt.VARIANTS), 'episodes': len(rows),
               'digest_matches': sum(1 for r in rows if r['digest_match']),
               'all_digest_match': all(r['digest_match'] for r in rows),
               'per_arm': per_arm}
    (checks / cfg['summary']).write_text(
        json.dumps(summary, indent=2, sort_keys=True) + '\n',
        encoding='utf-8')
    if report.exists():
        _append_report(report, summary, methods, per_arm, args.phase)
    print(json.dumps({'all_digest_match': summary['all_digest_match'],
                      'episodes': len(rows)}, indent=2))
    return 0 if summary['all_digest_match'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
```

Expected: file written; `InstrumentTests` from Step 1 turns green at Step 5.
The pass itself runs later: `--phase screening` after the retention gate
(<= 54 episodes, Task 12) and `--phase confirm2` after the final verdict
(<= 18 episodes, Task 15); both digest-verify against sealed official rows
(design section 5), and outputs land in `deterministic_checks/`.

- [ ] **Step 5: Run the new tests to verify green**

Run: `python -m unittest research.method_tournament.test_tournament.RunnerTests research.method_tournament.test_tournament.AllRegistrySweepTests research.method_tournament.test_tournament.InstrumentTests -v`
Expected: all 15 PASS (RunnerTests 9, AllRegistrySweepTests 3, InstrumentTests
3; the digest-parity test runs two full episodes and takes about 1 minute -
expected).

- [ ] **Step 6: Take the integrity "before" snapshot**

```powershell
python -c "import hashlib,pathlib; root=pathlib.Path('.'); skip=('research/method_tournament','docs/superpowers/plans/'); files=sorted(p for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts and '.git' not in p.parts and p.suffix != '.pyc' and not any(p.as_posix().startswith(s) for s in skip)); out=pathlib.Path('research/method_tournament/integrity/before.txt'); out.parent.mkdir(parents=True, exist_ok=True); out.write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.as_posix()+chr(10) for p in files), encoding='utf-8'); print('hashed', len(files), 'files')"
python -c "import hashlib,pathlib; frozen=['kit.py','policy.py','policy_ac.py','evaluate.py','organise.py','Dockerfile','.dockerignore','test_kit.py','test_runner.py','test_release.py','test_policy.py','research/test_pipeline.py']; pathlib.Path('research/method_tournament/integrity/frozen_before.txt').write_text(''.join(hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()+'  '+p+chr(10) for p in frozen), encoding='utf-8'); print('frozen hashed', len(frozen))"
python -c "import hashlib,pathlib; h=hashlib.sha256(pathlib.Path('docs/superpowers/plans/2026-10-08-method-tournament.md').read_bytes()).hexdigest(); pathlib.Path('research/method_tournament/integrity/plan_before.txt').write_text(h+chr(10), encoding='utf-8'); print('plan hash', h[:16])"
$enc = New-Object System.Text.UTF8Encoding($false)
$g = @((git rev-parse HEAD)) + @(git status --short -uall)
[System.IO.File]::WriteAllLines((Join-Path $PWD 'research\method_tournament\integrity\git_before.txt'), $g, $enc)
Write-Output 'integrity before snapshot written (4 categories: frozen, other-tree, git, plan)'
```
Expected: `hashed <N> files`, `frozen hashed 12`, `plan hash <16 hex>`,
`integrity before snapshot written (4 categories...)`. Task 16 re-hashes each
category independently: frozen files and the non-plan tree are HARD gates; the
plan file hash and the tournament's own artifacts are recorded INFORMATIONALLY
(the tournament tree is allowed to grow; plan-file drift is reported, never a
gate). The skip rule lets our own `research/method_tournament/` grow.

- [ ] **Step 7: Run the smoke phase (machinery gate, never ranked)**

```powershell
python research/method_tournament/run_tournament.py --phase smoke
```
Expected: 31 episodes (30 methods + control, fixture seed 90290 x development), summary with
`invalid: 0`, exit code 0, `per_phase/smoke.done` written. Takes roughly 5-20
minutes on 4 workers. If interrupted, rerun the same command - it resumes.

- [ ] **Step 8: Assert the smoke gate**

```powershell
python -c "import json,pathlib; d=json.loads(pathlib.Path('research/method_tournament/per_phase/smoke.done').read_text(encoding='utf-8')); assert d['episodes']==31 and d['invalid']==0, d; print('smoke gate PASS: 31 episodes, 0 invalid, wall', d['wall_seconds'], 's')"
```
Expected: `smoke gate PASS: 31 episodes, 0 invalid, wall <n> s`.
If any episode is invalid: STOP. Read its `error` from
`per_phase/smoke_rows.jsonl`, fix the machinery/method (still pre-Phase-1: design
fixes allowed here), delete `per_phase/smoke.done`, and rerun Step 7.

- [ ] **Step 9: Log the milestone**

```powershell
Add-Content -Path research\method_tournament\run_log.txt -Value ("{0} Task11 complete: runner + sweeps green; smoke 31/31 valid" -f (Get-Date -Format o))
```

No commit (spec Section 14).

---
### Task 12: Screening Run, Paired Analysis, Retention Gate, and Freeze

**Files:**
- Create: `research/method_tournament/analyse_tournament.py`
- Test: append `AnalyseTests` to `test_tournament.py` (before `if __name__ == '__main__':`)
- Generate: `per_phase/screening_rows.jsonl`, `per_phase/screening.done`,
  `screening_results.json`, `screening_report.md`,
  `deterministic_checks/instrument_screening.json`,
  `deterministic_checks/instrument_rows_screening.jsonl`,
  `hashes/policy_freeze_after_screening.txt`

**Interfaces:**
- Consumes: `run_tournament.{load_rows, dedupe, CONTROL, VARIANTS}`, screening rows.
- Produces:
  - `t_critical(df, level=95)` - conservative tabulated two-sided t critical
    (nearest tabulated df at or below, so intervals are never too narrow);
    level=99 serves the Phase-3 Bonferroni gate (k=2 candidates, design
    section 9: k=1 -> 95%, t=2.201; k=2 -> 99%, t=3.106; both df=11).
  - `method_summary(rows, method, ctrl)` - n_units, n_seeds, invalid,
    full-precision mean_delta over seed-level cluster means, cluster ci95
    AND ci99 (df = n_seeds - 1, variants averaged within seed first - design
    section 9), per_variant_mean_delta (full precision), behavioral
    distinctness, secondary diagnostics, `eligible` +
    `ineligibility_reasons` (design.md section 7 gates incl. latency <= 10 s).
  - `check_control_parity(rows)` - m01 `action_sha256` vs control per world; analysis
    HARD-FAILS if any mismatch (Review Focus item 2).
  - `select_top(per, k)` - design.md section 9: top-k by FULL-precision mean
    delta, sign-independent, zero-invalid only, m01 excluded (parity control),
    ties by (round(mean, 6), method_id) - never display-rounded values.
  - `retention(per, eligible)` - design.md section 7: first min(5, E) + next
    up to 3 diagnostics with fixed-format reasons; E = 0 -> ([], [], []).
  - `credible(summary, level=95)` - section 9 Phase-3 gate: invalid==0,
    mean>0, cluster CI low>0 at the Bonferroni level for the number of
    candidates tested, no per-variant mean < -0.15.
  - `assert_code_fingerprint(rows, phase, pre=None)` - design.md section 8:
    every row must carry the pre-screening `code_sha256`; SystemExit otherwise.
  - `screening_results.json` MUST contain key `retained` (consumed by
    `run_tournament.load_methods('confirm1')`); `confirmation_results.json` MUST
    contain key `selected` (consumed by `load_methods('confirm2')`).

- [ ] **Step 1: Append the failing tests**

Append `AnalyseTests`:

```python
class AnalyseTests(unittest.TestCase):
    @staticmethod
    def _rows():
        worlds = [(143, 'development'), (143, 'sparse'),
                  (144, 'development'), (144, 'sparse')]
        rows = []
        base = {'coverage': 0.5, 'ask_cost': 200, 'assignments': 100,
                'arrived_members': 200, 'inference_seconds': 10.0, 'valid': True}
        for seed, variant in worlds:
            rows.append(dict(base, method='__control__', seed=seed, variant=variant,
                             msmi_per_100_arrived_members=0.5,
                             action_sha256='h' + str(seed) + variant))
            rows.append(dict(base, method='m02_x', seed=seed, variant=variant,
                             msmi_per_100_arrived_members=0.55, action_sha256='a'))
            rows.append(dict(base, method='m03_y', seed=seed, variant=variant,
                             msmi_per_100_arrived_members=0.40, action_sha256='b'))
        return rows

    def test_paired_deltas_and_mean(self):
        import analyse_tournament as an
        import statistics
        rows = self._rows()
        ctrl = an.control_map(rows)
        pairs = an.paired_deltas(rows, 'm02_x', ctrl)
        self.assertEqual([(s, v) for s, v, _d in pairs],
                         [(143, 'development'), (143, 'sparse'),
                          (144, 'development'), (144, 'sparse')])
        self.assertAlmostEqual(statistics.mean(d for _s, _v, d in pairs), 0.05,
                               places=10)

    def test_seed_level_clustering_and_cluster_ci(self):
        import analyse_tournament as an
        rows = self._rows()
        ctrl = an.control_map(rows)
        s = an.method_summary(rows, 'm02_x', ctrl)
        self.assertEqual(s['n_units'], 4)
        self.assertEqual(s['n_seeds'], 2)
        self.assertAlmostEqual(s['mean_delta'], 0.05, places=10)
        # identical seed means -> zero-width cluster CI (df = 1, se = 0)
        self.assertAlmostEqual(s['ci95'][0], 0.05, places=10)
        self.assertAlmostEqual(s['ci95'][1], 0.05, places=10)
        self.assertAlmostEqual(s['ci99'][0], 0.05, places=10)
        # per-variant stratification preserved at full precision
        self.assertAlmostEqual(s['per_variant_mean_delta']['development'],
                               0.05, places=10)
        self.assertTrue(s['eligible'], s['ineligibility_reasons'])
        # m03 mean -0.10 fails the -0.05 retention gate
        s3 = an.method_summary(rows, 'm03_y', ctrl)
        self.assertFalse(s3['eligible'])
        self.assertAlmostEqual(s3['mean_delta'], -0.10, places=10)

    def test_t_critical_tables_conservative(self):
        import analyse_tournament as an
        self.assertEqual(an.t_critical(17), 2.110)
        self.assertEqual(an.t_critical(71), 1.994)
        self.assertEqual(an.t_critical(22), 2.086)   # falls back to df 20
        self.assertEqual(an.t_critical(0), float('inf'))
        # 99% table for the Bonferroni Phase-3 gate (design section 9)
        self.assertEqual(an.t_critical(11, 99), 3.106)
        self.assertEqual(an.t_critical(1, 99), 63.657)
        self.assertEqual(an.t_critical(22, 99), 2.845)  # falls back to df 20
        self.assertEqual(an.t_critical(11, 95), 2.201)

    def test_eligibility_gates_including_latency(self):
        import analyse_tournament as an
        good = {'invalid_episodes': 0, 'mean_delta': -0.04, 'n_units': 18,
                'per_variant_mean_delta': {'development': -0.14, 'sparse': 0.0},
                'secondary': {'max_inference_seconds': 9.4}}
        ok, reasons = an._eligibility(good)
        self.assertTrue(ok, reasons)
        self.assertFalse(an._eligibility(dict(good, invalid_episodes=1))[0])
        self.assertFalse(an._eligibility(dict(good, mean_delta=-0.06))[0])
        self.assertFalse(an._eligibility(dict(
            good, per_variant_mean_delta={'shift': -0.16}))[0])
        slow = dict(good, secondary={'max_inference_seconds': 10.5})
        self.assertFalse(an._eligibility(slow)[0])
        no_latency = dict(good, secondary={})
        self.assertFalse(an._eligibility(no_latency)[0])

    def test_control_parity_check(self):
        import analyse_tournament as an
        rows = self._rows()
        rows.append(dict(rows[0], method='m01_greedy_baseline', action_sha256='h143development'))
        parity = an.check_control_parity(rows)
        self.assertEqual(parity['worlds_checked'], 1)
        self.assertEqual(parity['mismatched_worlds'], [])
        rows[-1]['action_sha256'] = 'DIFFERENT'
        parity = an.check_control_parity(rows)
        self.assertEqual(len(parity['mismatched_worlds']), 1)

    def test_selection_is_sign_independent_top_two(self):
        import analyse_tournament as an
        per = {'a': {'invalid_episodes': 0, 'mean_delta': -0.01},
               'b': {'invalid_episodes': 0, 'mean_delta': -0.03},
               'c': {'invalid_episodes': 2, 'mean_delta': 0.9}}
        self.assertEqual(an.select_top(per, 2), ['a', 'b'])

    def test_selection_excludes_m01_and_uses_full_precision(self):
        import analyse_tournament as an
        per = {'m01_greedy_baseline': {'invalid_episodes': 0, 'mean_delta': 0.9},
               'a': {'invalid_episodes': 0, 'mean_delta': 0.5000006},
               'b': {'invalid_episodes': 0, 'mean_delta': 0.5000004},
               'c': {'invalid_episodes': 3, 'mean_delta': 0.99}}
        # a and b both display as 0.5000; full precision (then id) decides;
        # m01 is never selected despite the highest mean (parity control).
        self.assertEqual(an.select_top(per, 2), ['a', 'b'])

    def test_credibility_gate_cluster_and_bonferroni(self):
        import analyse_tournament as an
        base = {'invalid_episodes': 0, 'mean_delta': 0.05,
                'ci95': [0.01, 0.09], 'ci99': [0.005, 0.095],
                'per_variant_mean_delta': {'drift': -0.1}}
        self.assertTrue(an.credible(base))
        self.assertTrue(an.credible(base, 99))
        self.assertFalse(an.credible(dict(base, ci95=[-0.01, 0.11])))
        # clears 95% but not the Bonferroni 99% level -> not credible at k=2
        self.assertFalse(an.credible(dict(base, ci99=[-0.01, 0.11]), 99))
        self.assertFalse(an.credible(dict(
            base, per_variant_mean_delta={'drift': -0.16})))
        self.assertFalse(an.credible(dict(base, invalid_episodes=1)))

    def test_retention_zero_through_eight(self):
        import analyse_tournament as an

        def per_for(n):
            return {'m%02d_x' % i: {'invalid_episodes': 0,
                                    'mean_delta': 1.0 - i * 0.01,
                                    'per_variant_mean_delta': {'development': 0.1}}
                    for i in range(n)}

        def ranked(per):
            return sorted(per, key=lambda m: (-per[m]['mean_delta'],
                                              round(per[m]['mean_delta'], 6), m))
        # E = 0
        self.assertEqual(an.retention({}, []), ([], [], []))
        # E = 3 -> all core, no diagnostics
        per3 = per_for(3)
        t3, d3, r3 = an.retention(per3, ranked(per3))
        self.assertEqual((len(t3), len(d3), len(r3)), (3, 0, 3))
        self.assertEqual(r3, t3)
        # E = 7 -> 5 core + 2 diagnostics with reasons
        per7 = per_for(7)
        t7, d7, r7 = an.retention(per7, ranked(per7))
        self.assertEqual((len(t7), len(d7), len(r7)), (5, 2, 7))
        self.assertEqual(r7, t7 + [d['method'] for d in d7])
        self.assertTrue(all(d['reason'] for d in d7))
        # E = 10 -> capped at 8 retained (5 + 3 diagnostics)
        per10 = per_for(10)
        t10, d10, r10 = an.retention(per10, ranked(per10))
        self.assertEqual((len(t10), len(d10), len(r10)), (5, 3, 8))

    def test_code_fingerprint_assert(self):
        import analyse_tournament as an
        import tempfile
        import pathlib as pl
        rows = [{'code_sha256': 'a' * 64}, {'code_sha256': 'a' * 64}]
        with tempfile.TemporaryDirectory() as td:
            pre = pl.Path(td) / 'pre.txt'
            pre.write_text('a' * 64 + chr(10), encoding='utf-8')
            got = an.assert_code_fingerprint(rows, 'screening', pre=pre)
            self.assertEqual(got, 'a' * 16)
            rows.append({'code_sha256': 'b' * 64})
            with self.assertRaises(SystemExit):
                an.assert_code_fingerprint(rows, 'screening', pre=pre)
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m unittest research.method_tournament.test_tournament.AnalyseTests -v`
Expected: 10 ERRORs (`ModuleNotFoundError: No module named 'analyse_tournament'`).

- [ ] **Step 3: Write `analyse_tournament.py`**

```python
"""Paired analysis, retention, selection, and verdicts for the method tournament.

design.md: section 5 (metrics), 7 (retention), 9 (selection and verdict).
Ranking uses ONLY paired same-world deltas of msmi_per_100_arrived_members versus
the shared greedy control. Never AUC, offline expected value, mutual acceptances,
introduction counts, or ask efficiency. Absolute numbers are never compared across
seed sets (the 0.4931 incumbent is a different seed set).
"""
import argparse
import json
import math
import pathlib
import statistics
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_tournament as rt  # noqa: E402

T95 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365,
       8: 2.306, 9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179, 13: 2.160,
       14: 2.145, 15: 2.131, 16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093,
       20: 2.086, 24: 2.064, 29: 2.045, 35: 2.030, 40: 2.021, 49: 2.010,
       59: 2.001, 71: 1.994, 89: 1.987, 119: 1.980}
T99 = {1: 63.657, 2: 9.925, 3: 5.841, 4: 4.604, 5: 4.032, 6: 3.707, 7: 3.499,
       8: 3.355, 9: 3.250, 10: 3.169, 11: 3.106, 12: 3.055, 13: 3.012,
       14: 2.977, 15: 2.947, 16: 2.921, 17: 2.898, 18: 2.878, 19: 2.861,
       20: 2.845, 24: 2.797, 29: 2.756, 35: 2.724, 40: 2.704, 49: 2.680,
       59: 2.660, 71: 2.640, 89: 2.620, 119: 2.601}

NOT_RANKED_NOTE = ('Ranking metric: mean paired delta of MSMI/100 vs control. '
                   'Never AUC, offline expected value, mutual acceptances, '
                   'introduction counts, or ask efficiency. Absolute numbers are '
                   'never compared across seed sets.')


def t_critical(df, level=95):
    """Conservative tabulated two-sided t critical (largest tabulated df <= df).

    level=95 for screening/secondary intervals; level=99 for the Phase-3
    Bonferroni gate when k=2 candidates are tested (design.md section 9:
    k=1 -> 95%, t=2.201; k=2 -> 99%, t=3.106; both at df=11).
    """
    if df <= 0:
        return float('inf')
    table = T99 if level == 99 else T95
    return table[max(k for k in table if k <= df)]


def load_phase_rows(phase):
    return rt.dedupe(rt.load_rows(HERE / 'per_phase' / (phase + '_rows.jsonl')))


def control_map(rows):
    return {(r['seed'], r['variant']): r for r in rows
            if r['method'] == rt.CONTROL}


def paired_deltas(rows, method, ctrl):
    """[(seed, variant, delta)] sorted; delta is None where either side is invalid."""
    out = []
    for r in rows:
        if r['method'] != method:
            continue
        key = (r['seed'], r['variant'])
        c = ctrl.get(key)
        if c is None or not r.get('valid') or not c.get('valid'):
            out.append((r['seed'], r['variant'], None))
        else:
            out.append((r['seed'], r['variant'],
                        r['msmi_per_100_arrived_members']
                        - c['msmi_per_100_arrived_members']))
    return sorted(out)


def _eligibility(s):
    """design.md section 7: every gate is required for retention.

    m01 never reaches this function - it is excluded upstream (parity control).
    """
    reasons = []
    if s['invalid_episodes']:
        reasons.append('%d invalid episode(s)' % s['invalid_episodes'])
    max_inf = (s.get('secondary') or {}).get('max_inference_seconds')
    if max_inf is None:
        reasons.append('no latency evidence (max_inference_seconds missing)')
    elif max_inf > 10.0:
        reasons.append('latency gate: max inference %.3f s exceeds 10 s' % max_inf)
    if s['n_units'] == 0:
        reasons.append('zero paired units')
    if s['mean_delta'] is None:
        reasons.append('no valid paired units')
    else:
        if s['mean_delta'] < -0.05:
            reasons.append('mean delta %.4f below -0.05' % s['mean_delta'])
        bad = sorted(v for v, m in s['per_variant_mean_delta'].items()
                     if m is None or m < -0.15)
        if bad:
            reasons.append('catastrophic family: ' + ', '.join(bad))
    return (not reasons), reasons


def seed_level_deltas(pairs):
    """[(seed, mean delta)] - the 6 variants are averaged within seed first.

    Variants share one seeded world per seed (design.md section 9), so
    inference runs on the seed-level means (df = n_seeds - 1); per-variant
    means stay in the summary as mandatory stratification.
    """
    by_seed = {}
    for s, _v, d in pairs:
        if d is not None:
            by_seed.setdefault(s, []).append(d)
    return sorted((s, statistics.mean(ds))
                  for s, ds in by_seed.items() if ds)


def method_summary(rows, method, ctrl):
    mrows = [r for r in rows if r['method'] == method]
    invalid = sum(1 for r in mrows if not r.get('valid'))
    pairs = paired_deltas(rows, method, ctrl)
    per_variant = {}
    for variant in rt.VARIANTS:
        vd = [d for _s, v, d in pairs if v == variant and d is not None]
        per_variant[variant] = statistics.mean(vd) if vd else None
    cluster = seed_level_deltas(pairs)
    cluster_vals = [m for _s, m in cluster]
    n_seeds = len(cluster_vals)
    if n_seeds:
        mean = statistics.mean(cluster_vals)
        if n_seeds >= 2:
            se = statistics.stdev(cluster_vals) / math.sqrt(n_seeds)
            dof = n_seeds - 1
            ci95 = [round(mean - t_critical(dof, 95) * se, 6),
                    round(mean + t_critical(dof, 95) * se, 6)]
            ci99 = [round(mean - t_critical(dof, 99) * se, 6),
                    round(mean + t_critical(dof, 99) * se, 6)]
        else:
            ci95, ci99 = [None, None], [None, None]
    else:
        mean, ci95, ci99 = None, [None, None], [None, None]
    valid = [r for r in mrows if r.get('valid')]
    # within-seed cross-variant dispersion of deltas (design.md section 5)
    dispersions = []
    for s in sorted({s for s, _v, d in pairs if d is not None}):
        sv = [d for s2, _v, d in pairs if s2 == s and d is not None]
        if len(sv) >= 2:
            dispersions.append(statistics.stdev(sv))
    # behavioral distinctness (honesty reporting; never a ranking input)
    distinct = len({r['action_sha256'] for r in valid})
    differing = 0
    for r in valid:
        c = ctrl.get((r['seed'], r['variant']))
        if c is not None and c.get('valid') and r['action_sha256'] != c['action_sha256']:
            differing += 1
    summary = {
        'n_units': len([d for _s, _v, d in pairs if d is not None]),
        'n_seeds': n_seeds,
        'invalid_episodes': invalid,
        'mean_delta': mean,
        'ci95': ci95,
        'ci99': ci99,
        'per_variant_mean_delta': per_variant,
        'cross_variant_dispersion_mean': (round(statistics.mean(dispersions), 6)
                                          if dispersions else None),
        'behavioral': {'distinct_digests': distinct,
                       'worlds_differing_from_control': differing},
        'secondary': {
            'coverage_mean': round(statistics.mean(
                r['coverage'] for r in valid), 4) if valid else None,
            'ask_cost_mean': round(statistics.mean(
                r['ask_cost'] for r in valid), 1) if valid else None,
            'intros_per_100_mean': round(statistics.mean(
                100.0 * r['assignments'] / max(1, r['arrived_members'])
                for r in valid), 3) if valid else None,
            'max_inference_seconds': round(max(
                r['inference_seconds'] for r in valid), 1) if valid else None,
        },
    }
    summary['eligible'], summary['ineligibility_reasons'] = _eligibility(summary)
    return summary


def check_control_parity(rows, method='m01_greedy_baseline'):
    ctrl = control_map(rows)
    mismatched, checked = [], 0
    for r in sorted(rows, key=lambda x: (x['method'], x['seed'], x['variant'])):
        if r['method'] != method:
            continue
        checked += 1
        c = ctrl.get((r['seed'], r['variant']))
        if (c is None or not r.get('valid') or not c.get('valid')
                or r['action_sha256'] != c['action_sha256']):
            mismatched.append({'seed': r['seed'], 'variant': r['variant']})
    return {'worlds_checked': checked, 'mismatched_worlds': mismatched}


def select_top(per, k=2):
    """design.md section 9: top-k by FULL-precision mean delta.

    Sign-independent; zero-invalid only (an invalid method can never satisfy
    section 9 credibility); m01_greedy_baseline excluded (parity control);
    ties broken by (round(mean, 6), method_id) - never display-rounded values.
    """
    pool = [m for m in per
            if m != 'm01_greedy_baseline'
            and per[m]['invalid_episodes'] == 0
            and per[m]['mean_delta'] is not None]
    return sorted(pool, key=lambda m: (-per[m]['mean_delta'],
                                       round(per[m]['mean_delta'], 6), m))[:k]


def credible(s, level=95):
    """design.md section 9 Phase-3 credibility: ALL conditions required.

    The cluster CI must clear zero at the Bonferroni level for the number of
    candidates tested (k=1 -> 95%, k=2 -> 99%; design.md section 9).
    """
    ci = s['ci99'] if level == 99 else s['ci95']
    return (s['invalid_episodes'] == 0
            and s['mean_delta'] is not None and s['mean_delta'] > 0
            and ci[0] is not None and ci[0] > 0
            and all(m is not None and m >= -0.15
                    for m in s['per_variant_mean_delta'].values()))


def retention(per, eligible):
    """design.md section 7: first min(5, E) core + next up to 3 diagnostics.

    eligible arrives ranked (full precision, ties by (round(mean, 6), id));
    returns (top5, diagnostics, retained). E = 0 -> ([], [], []), which
    triggers the Phase-2/3 skip branch (design.md section 7).
    """
    top5 = eligible[:5]
    diagnostics = []
    for m in eligible[5:8]:
        pv = per[m]['per_variant_mean_delta']
        valued = [(v, x) for v, x in pv.items() if x is not None]
        if valued:
            best_v, best_x = max(valued, key=lambda t: t[1])
            reason = ('next-ranked eligible (mean %+.4f); strongest family '
                      'signal %+.4f on %s' % (per[m]['mean_delta'], best_x, best_v))
        else:
            reason = ('next-ranked eligible (mean %+.4f); no family signal'
                      % per[m]['mean_delta'])
        diagnostics.append({'method': m, 'reason': reason})
    retained = top5 + [d['method'] for d in diagnostics]
    return top5, diagnostics, retained


def assert_code_fingerprint(rows, phase, pre=None):
    """design.md section 8: every row must carry the pre-screening fingerprint."""
    pre = pathlib.Path(pre) if pre else HERE / 'hashes' / 'pre_screening_fingerprint.txt'
    if not pre.exists():
        raise SystemExit('pre-screening fingerprint missing: ' + str(pre))
    want = pre.read_text(encoding='utf-8').strip()
    bad = [r for r in rows if r.get('code_sha256') != want]
    if bad:
        raise SystemExit('%d %s rows carry a foreign code_sha256 (want %s...)'
                         % (len(bad), phase, want[:16]))
    return want[:16]


def _guard_delta(rows, method, ctrl, key):
    vals = []
    for r in rows:
        if r['method'] != method:
            continue
        c = ctrl.get((r['seed'], r['variant']))
        if c is not None and r.get('valid') and c.get('valid'):
            vals.append(r[key] - c[key])
    return round(statistics.mean(vals), 4) if vals else None


def _fmt_ci(ci):
    return '[n/a]' if ci[0] is None else '[%+.4f, %+.4f]' % (ci[0], ci[1])


def _write(name, text):
    path = HERE / name
    path.write_text(text, encoding='utf-8')
    print('wrote ' + name)


def analyse_screening():
    rows = load_phase_rows('screening')
    fp16 = assert_code_fingerprint(rows, 'screening')
    ctrl = control_map(rows)
    methods = sorted({r['method'] for r in rows} - {rt.CONTROL})
    per = {m: method_summary(rows, m, ctrl) for m in methods}
    parity = check_control_parity(rows)
    if parity['mismatched_worlds'] or parity['worlds_checked'] != 18:
        print(json.dumps(parity, indent=2))
        raise SystemExit('m01 control parity FAILED (expected 18/18 identical)')
    # m01 is excluded from eligibility, ranking, and retention (design section 7)
    rank_pool = [m for m in methods if m != 'm01_greedy_baseline']
    eligible = sorted((m for m in rank_pool if per[m]['eligible']),
                      key=lambda m: (-per[m]['mean_delta'],
                                     round(per[m]['mean_delta'], 6), m))
    top5, diagnostics, retained = retention(per, eligible)
    results = {
        'phase': 'screening', 'worlds': 18,
        'seeds': [143, 144, 145], 'variants': list(rt.VARIANTS),
        'code_fingerprint': fp16,
        'control_parity': parity, 'per_method': per,
        'eligible_ranking': eligible, 'top5': top5,
        'diagnostic_candidates': diagnostics, 'retained': retained,
        'behavioral_diversity': {m: per[m]['behavioral'] for m in sorted(per)},
        'dispersion': {m: per[m]['cross_variant_dispersion_mean']
                       for m in sorted(per)},
        'm01_excluded_note': ('m01_greedy_baseline is excluded from eligibility, '
                              'ranking, and retention (parity/diagnostic only; '
                              'design section 7).'),
        'not_ranked_note': NOT_RANKED_NOTE,
        'no_winner_note': ('Phase 1 has 18 paired worlds: no method may be '
                           'called a winner from screening alone.'),
        'cluster_note': ('Inference clusters on seed: 6 per-variant deltas are '
                         'averaged per seed -> 12 seed-level means (df = 11); '
                         'screening is gate-only (design section 9).'),
    }
    _write('screening_results.json',
           json.dumps(results, indent=2, sort_keys=True, allow_nan=False) + '\n')
    _write('screening_report.md', _screening_md(results))
    print(json.dumps({'retained': retained, 'eligible': len(eligible),
                      'ineligible': len(rank_pool) - len(eligible),
                      'code_fingerprint': fp16}, indent=2))
    return 0


def _screening_md(res):
    per = res['per_method']
    parity = res['control_parity']
    lines = ['# Method Tournament - Phase 1 Screening Report', '',
             '- Worlds: %d (seeds 143-145 x 6 variants), paired vs shared '
             'greedy control.' % res['worlds'],
             '- Control parity: m01 digests identical to policy.py --baseline '
             'greedy on %d/%d worlds.' % (parity['worlds_checked'], res['worlds']),
             '- ' + res['no_winner_note'],
             '- ' + res['m01_excluded_note'],
             '- ' + res['cluster_note'],
             '- Screening code fingerprint: ' + res['code_fingerprint'] +
             ' (verified on every row).',
             '- ' + res['not_ranked_note'], '',
             '## Leaderboard (eligible, ranked by mean paired delta)', '',
             '| rank | method | mean delta | cluster 95% CI | invalid | worst variant '
             '| retained |',
             '|---|---|---|---|---|---|---|']
    retained = set(res['retained'])
    for i, m in enumerate(res['eligible_ranking'], 1):
        s = per[m]
        pv = [x for x in s['per_variant_mean_delta'].values() if x is not None]
        worst = min(pv) if pv else None
        lines.append('| %d | %s | %+.4f | %s | %d | %s | %s |' % (
            i, m, s['mean_delta'], _fmt_ci(s['ci95']), s['invalid_episodes'],
            ('%+.4f' % worst) if worst is not None else 'n/a',
            'YES' if m in retained else ''))
    lines += ['', '## Ineligible methods', '']
    ineligible = [m for m in sorted(per) if not per[m]['eligible']]
    if ineligible:
        for m in ineligible:
            lines.append('- **%s**: %s' % (m, '; '.join(
                per[m]['ineligibility_reasons'])))
    else:
        lines.append('- (none)')
    lines += ['', '## Retention decisions (design section 7)', '',
              '- Retained top-5: ' + ', '.join(res['top5'])]
    if res['diagnostic_candidates']:
        lines.append('- Diagnostic candidates (slots 6-8, human gate confirms):')
        for d in res['diagnostic_candidates']:
            lines.append('  - %s: %s' % (d['method'], d['reason']))
    else:
        lines.append('- Diagnostic candidates: none beyond top-5.')
    lines += ['', '## Behavioral distinctness (honesty check, never ranking)', '',
              '| method | distinct action digests | worlds differing from control |',
              '|---|---|---|']
    for m in sorted(res['behavioral_diversity']):
        b = res['behavioral_diversity'][m]
        lines.append('| %s | %d | %d |' % (
            m, b['distinct_digests'], b['worlds_differing_from_control']))
    lines += ['', '## Cross-variant dispersion (within-seed, diagnostic)', '']
    for m in sorted(res['dispersion']):
        d = res['dispersion'][m]
        lines.append('- %s: %s' % (
            m, 'n/a' if d is None else '%.4f' % d))
    lines += ['', '## Secondary diagnostics (never ranking inputs)', '',
              '| method | coverage | ask cost | intros/100 | max inference s |',
              '|---|---|---|---|---|']
    for m in sorted(per):
        sec = per[m]['secondary']
        lines.append('| %s | %s | %s | %s | %s |' % (
            m, sec['coverage_mean'], sec['ask_cost_mean'],
            sec['intros_per_100_mean'], sec['max_inference_seconds']))
    lines.append('')
    return '\n'.join(lines)


def analyse_confirm1():
    rows = load_phase_rows('confirm1')
    fp16 = assert_code_fingerprint(rows, 'confirm1')
    ctrl = control_map(rows)
    screening = json.loads((HERE / 'screening_results.json')
                           .read_text(encoding='utf-8'))
    methods = screening['retained']
    per = {m: method_summary(rows, m, ctrl) for m in methods}
    selected = select_top(per, 2)
    results = {
        'phase': 'confirm1', 'worlds': 36, 'arms': methods,
        'code_fingerprint': fp16,
        'per_method': per, 'selected': selected,
        'selection_rule': ('Top 2 by FULL-precision mean paired delta '
                           '(sign-independent); zero-invalid only; m01 excluded; '
                           'ties by (round(mean, 6), method_id) (design section 9).'),
        'not_ranked_note': NOT_RANKED_NOTE,
        'cluster_note': ('Inference clusters on seed: 6 per-variant deltas are '
                         'averaged per seed -> 12 seed-level means (df = 11) '
                         '(design section 9).'),
    }
    _write('confirmation_results.json',
           json.dumps(results, indent=2, sort_keys=True, allow_nan=False) + '\n')
    _write('confirmation_report.md', _confirm_md(results, 'Phase 2 Confirmation'))
    print(json.dumps({'selected': selected}, indent=2))
    return 0


def _confirm_md(res, title):
    per = res['per_method']
    lines = ['# Method Tournament - %s Report' % title, '',
             '- Worlds: %d, arms: %s + shared control.' % (res['worlds'],
                                                           ', '.join(res['arms']) or '(none)'),
             '- ' + res.get('selection_rule', ''),
             '- ' + res.get('cluster_note', '')]
    if res.get('code_fingerprint'):
        lines.append('- Code fingerprint: ' + res['code_fingerprint'] +
                     ' (verified on every row).')
    lines += ['- ' + res.get('not_ranked_note', ''), '',
              '| method | mean delta | cluster 95% CI | invalid | worst variant | '
              'coverage | ask cost |',
              '|---|---|---|---|---|---|---|']
    for m in sorted(per):
        s = per[m]
        pv = [x for x in s['per_variant_mean_delta'].values() if x is not None]
        worst = min(pv) if pv else None
        lines.append('| %s | %s | %s | %d | %s | %s | %s |' % (
            m, ('%+.4f' % s['mean_delta']) if s['mean_delta'] is not None else 'n/a',
            _fmt_ci(s['ci95']), s['invalid_episodes'],
            ('%+.4f' % worst) if worst is not None else 'n/a',
            s['secondary']['coverage_mean'], s['secondary']['ask_cost_mean']))
    lines += ['', 'Selected for Phase 3: ' + (', '.join(res['selected'])
                                              if res['selected'] else '(none)'), '']
    return '\n'.join(lines)


def analyse_confirm2():
    rows = load_phase_rows('confirm2')
    fp16 = assert_code_fingerprint(rows, 'confirm2')
    ctrl = control_map(rows)
    confirmation = json.loads((HERE / 'confirmation_results.json')
                              .read_text(encoding='utf-8'))
    candidates = confirmation['selected']
    per = {m: method_summary(rows, m, ctrl) for m in candidates}
    # Bonferroni over tested candidates (design section 9): k=1 -> 95%, k=2 -> 99%
    level = 95 if len(candidates) <= 1 else 99
    cred = sorted((m for m in candidates if credible(per[m], level)),
                  key=lambda m: (-per[m]['mean_delta'], m))
    winner = cred[0] if cred else None
    verdict = ('%s is credible on Phase 3 (72 paired units).' % winner
               if winner else
               'Greedy remains the best empirically supported policy among the evaluated candidates.')
    screen = json.loads((HERE / 'screening_results.json')
                        .read_text(encoding='utf-8'))
    retained = screen.get('retained', [])
    if winner:
        keep_reason = None
    elif not candidates and not retained:
        keep_reason = 'no eligible candidates at screening'
    elif not candidates:
        keep_reason = 'no Phase-3 arms (selection empty after Phase 2)'
    else:
        keep_reason = 'no credible candidate on Phase 3'
    results = {
        'phase': 'confirm2', 'worlds': 72, 'candidates': candidates,
        'code_fingerprint': fp16,
        'bonferroni_level': level,
        'n_seed_clusters': 12,
        'per_method': per, 'credible': cred, 'winner': winner,
        'verdict': verdict,
        'keep_greedy_reason': keep_reason,
        'coverage_delta': {m: _guard_delta(rows, m, ctrl, 'coverage')
                           for m in candidates},
        'ask_cost_mean': {m: per[m]['secondary']['ask_cost_mean']
                          for m in candidates},
        'guardrail_note': ('Coverage delta >= -0.05 and ask cost are guardrails, '
                           'reported not binding (design section 9).'),
        'not_ranked_note': NOT_RANKED_NOTE,
        'incumbent_note': ('Incumbent 0.4931 MSMI/100 is a different seed set '
                           'and is never compared to these numbers.'),
        'cluster_note': ('Inference clusters on seed: 72 worlds -> 12 seed-level '
                         'means (df = 11); per-variant gates mandatory '
                         '(design section 9).'),
    }
    _write('final_results.json',
           json.dumps(results, indent=2, sort_keys=True, allow_nan=False) + '\n')
    _write('final_report.md', _final_md(results))
    print(json.dumps({'winner': winner, 'credible': cred, 'verdict': verdict,
                      'bonferroni_level': level}, indent=2))
    return 0


def _final_md(res):
    per = res['per_method']
    level = res.get('bonferroni_level', 95)
    ci_key = 'ci99' if level == 99 else 'ci95'
    ci_label = 'cluster %d%% CI' % level
    lines = ['# Method Tournament - Phase 3 Final Report', '',
             '- Worlds: %d (seeds 152-163 x 6 variants), candidates: %s.' % (
                 res['worlds'], ', '.join(res['candidates']) or '(none)'),
             '- ' + res['not_ranked_note'],
             '- ' + res['incumbent_note'],
             '- ' + res['guardrail_note'],
             '- ' + res.get('cluster_note', ''),
             '- Bonferroni: %d candidate(s) tested -> %d%% significance level '
             '(design section 9).' % (len(res['candidates']), level)]
    if res.get('code_fingerprint'):
        lines.append('- Code fingerprint: ' + res['code_fingerprint'] +
                     ' (verified on every row).')
    lines += ['',
              '| method | mean delta | ' + ci_label + ' | invalid | worst variant | '
              'credible | coverage delta | ask cost |',
              '|---|---|---|---|---|---|---|---|']
    for m in res['candidates']:
        s = per[m]
        pv = [x for x in s['per_variant_mean_delta'].values() if x is not None]
        worst = min(pv) if pv else None
        lines.append('| %s | %s | %s | %d | %s | %s | %s | %s |' % (
            m, ('%+.4f' % s['mean_delta']) if s['mean_delta'] is not None else 'n/a',
            _fmt_ci(s[ci_key]), s['invalid_episodes'],
            ('%+.4f' % worst) if worst is not None else 'n/a',
            'YES' if m in res['credible'] else 'no',
            res['coverage_delta'][m], res['ask_cost_mean'][m]))
    lines += ['', '## Verdict', '', res['verdict'], '']
    if res.get('keep_greedy_reason'):
        lines += ['',
                  'Keep-greedy reason: %s.' % res['keep_greedy_reason']]
    lines.append('')
    return '\n'.join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', required=True,
                        choices=['screening', 'confirm1', 'confirm2'])
    args = parser.parse_args(argv)
    if args.phase == 'screening':
        return analyse_screening()
    if args.phase == 'confirm1':
        return analyse_confirm1()
    return analyse_confirm2()


if __name__ == '__main__':
    raise SystemExit(main())
```

- [ ] **Step 4: Run the analysis tests to verify green**

Run: `python -m unittest research.method_tournament.test_tournament.AnalyseTests -v`
Expected: 10 tests PASS.

- [ ] **Step 5: Run the screening phase (Phase 1, official)**

```powershell
python research/method_tournament/run_tournament.py --phase screening
```
Expected: 558 episodes (30 methods + control x 18 worlds), exit 0, sealed done flag.
This is the long official run - roughly 1.5-4 hours on 4 workers. The command is
resumable: if interrupted, rerun it.

- [ ] **Step 6: Assert the screening gate**

```powershell
python -c "import json,pathlib; d=json.loads(pathlib.Path('research/method_tournament/per_phase/screening.done').read_text(encoding='utf-8')); assert d['episodes']==558 and d['invalid']==0, d; print('screening gate PASS: 558 episodes, 0 invalid')"
```
Expected: `screening gate PASS: 558 episodes, 0 invalid`.
If invalid > 0: STOP. Identify the method(s) from `per_phase/screening_rows.jsonl`
invalid rows. Any invalidity is disqualifying for those methods (retention gate);
if it indicates a machinery bug, fix it (Phase 1 analysis has not run yet), delete
`per_phase/screening.done`, and rerun Step 5. Never edit methods to chase scores.

- [ ] **Step 7: Run the screening analysis**

```powershell
python research/method_tournament/analyse_tournament.py --phase screening
```
Expected: writes `screening_results.json` + `screening_report.md`; hard-fails if
m01 parity differs from control on any of the 18 worlds (Review Focus item 2).

- [ ] **Step 8: Assert the analysis structure**

```powershell
python -c "import json,pathlib; d=json.loads(pathlib.Path('research/method_tournament/screening_results.json').read_text(encoding='utf-8')); assert d['control_parity']=={'worlds_checked': 18, 'mismatched_worlds': []}, d['control_parity']; assert len(d['per_method'])==30; assert 5 <= len(d['retained']) <= 8; assert d['retained']==d['top5']+[x['method'] for x in d['diagnostic_candidates']]; assert len(d['code_fingerprint'])==16, d['code_fingerprint']; assert set(d['behavioral_diversity'])==set(d['per_method']), 'diversity keys must mirror per_method'; assert d['per_method']['m01_greedy_baseline']['behavioral']['worlds_differing_from_control']==0, 'm01 must be digest-identical to control'; print('screening analysis PASS; retained:', d['retained'], 'fp:', d['code_fingerprint'])"
```
Expected: prints the retained list and the 16-hex pre-screening fingerprint.

- [ ] **Step 9: Run the instrument screening pass (diagnostic, design section 5)**

```powershell
python research/method_tournament/instrument.py --phase screening
```
Expected: `{"all_digest_match": true, "episodes": N}` with N =
`(len(retained) + 1) * 6` (retained arms + shared control x 6 variants,
36-54 episodes, a few minutes), exit 0; writes
`deterministic_checks/instrument_screening.json` +
`deterministic_checks/instrument_rows_screening.jsonl` and appends the
instrument section to `screening_report.md`. Any digest mismatch exits 2 -
STOP and investigate before the gate (never edit methods to chase digests).

```powershell
python -c "import json,pathlib; mt=pathlib.Path('research/method_tournament'); s=json.loads((mt/'deterministic_checks/instrument_screening.json').read_text(encoding='utf-8')); ret=json.loads((mt/'screening_results.json').read_text(encoding='utf-8'))['retained']; assert not s['skipped'] and s['all_digest_match'], s; assert s['episodes']==(len(ret)+1)*6, (s['episodes'], len(ret)); print('instrument screening PASS:', s['episodes'], 'episodes,', s['digest_matches'], 'digest matches')"
```
Expected: `instrument screening PASS: N episodes, N digest matches`.
If the human gate in Step 10 changes the retained list, rerun both commands
in this step so the instrument arms match the approved list.

- [ ] **Step 10: HUMAN REVIEW GATE (stop here)**

STOP and present to the user, in this order:
1. `research/method_tournament/screening_report.md` (leaderboard + eligibility
   + behavioral distinctness + instrument section).
2. The proposed `retained` list (top-5 + diagnostic slots with reasons).
3. Any ineligible methods with their gate reasons.
4. `research/method_tournament/deterministic_checks/instrument_screening.json`
   (digest parity: all_digest_match true).

Ask: approve the retention list as proposed, or modify it (drop/swap methods -
within the rules: retained must be eligible methods; 5-8 total)?
- Wait for explicit approval before continuing. Record approval (or the modified
  list) in `run_log.txt`:
```powershell
Add-Content -Path research\method_tournament\run_log.txt -Value ("{0} Task12 HUMAN GATE: retention approved: <paste final retained list>" -f (Get-Date -Format o))
```
- If the user changes the list, rerun Step 9 (instrument arms must match the
  approved list), then update `screening_results.json["retained"]` to the
  approved list (only that key; nothing else).

- [ ] **Step 11: Freeze the methods (design section 8)**

```powershell
python -c "import hashlib,pathlib; root=pathlib.Path('.'); here=root/'research/method_tournament'; named=['methods_a.py','methods_b.py','methods_c.py','methods_d.py','methods_e.py','common.py','alloc.py','registry.py','_cli.py','gen_policies.py','run_tournament.py','analyse_tournament.py','instrument.py','design.md','methods.json']; files=sorted({here/n for n in named} | set((here/'policies').glob('*.py')) | {root/n for n in ('kit.py','policy.py','policy_ac.py','evaluate.py','organise.py','Dockerfile')}); out=here/'hashes'; out.mkdir(exist_ok=True); (out/'policy_freeze_after_screening.txt').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.relative_to(root).as_posix()+chr(10) for p in files), encoding='utf-8'); print('frozen', len(files), 'files')"
python -c "import sys; sys.path.insert(0,'research/method_tournament'); import run_tournament as rt; rt.verify_freeze(); print('freeze manifest verified')"
```
Expected: `frozen 51 files`, `freeze manifest verified`.
The manifest is the repo-root-relative behavior/spec set (5 methods_*.py +
10 named files + 30 policy launchers + 6 root frozen files) and is re-verified
at every later phase boundary. From this point: NO method/threshold/weight/logic
edits. Methods may be eliminated, never redesigned (spec Section 8).

- [ ] **Step 12: Log the milestone**

```powershell
Add-Content -Path research\method_tournament\run_log.txt -Value ("{0} Task12 complete: screening 558/0 valid; analysis + retention gate + instrument pass + 51-file freeze" -f (Get-Date -Format o))
```

No commit (spec Section 14).

---
### Task 13: Confirm-1 Run (Phase 2) and Selection

**Files:**
- Generate: `per_phase/confirm1_rows.jsonl`, `per_phase/confirm1.done`
- Generate: `confirmation_results.json`, `confirmation_report.md`
- Generate: `hashes/policy_freeze_after_confirm1.txt` (phase-boundary re-hash)

**Interfaces:**
- Consumes: `screening_results.json["retained"]` (the list approved at the Task 12
  human gate); freeze manifest (the runner's `main()` auto-verifies
  `hashes/policy_freeze_after_screening.txt` for confirm1/confirm2 and aborts on
  any mismatch, design section 8).
- Produces: `confirmation_results.json["selected"]` - at most 2 method ids,
  zero-invalid only, ranked sign-independently by mean paired delta (design
  section 9). Contract consumed by `run_tournament.load_methods('confirm2')`.

- [ ] **Step 1: Verify the freeze explicitly before running**

```powershell
python -c "import sys; sys.path.insert(0,'research/method_tournament'); import run_tournament as rt; rt.verify_freeze(); print('freeze verified before confirm1')"
```
Expected: `freeze verified before confirm1`.
- [ ] **Step 2: Detect the Phase-2/3 skip branch (E = 0)**

```powershell
python -c "import json,pathlib; d=json.loads(pathlib.Path('research/method_tournament/screening_results.json').read_text(encoding='utf-8')); print('retained:', d['retained'])"
```
If the output is `retained: []` (E = 0 at the screening gate - the human gate
may drop all methods), Phases 2 and 3 are SKIPPED (design section 7). Run ONLY:
  a. `python research/method_tournament/analyse_tournament.py --phase confirm1`
     - writes `confirmation_results.json` with `selected: []` and
       `confirmation_report.md` (no confirm1 rows are needed; the analysis
       tolerates a missing rows file),
  b. Step 7 (the boundary manifest is still required),
  c. Step 8 (log with `selected: []`).
Do NOT run the confirm-1 runner (0 episodes) and do NOT run Steps 3-6.
Then continue to Task 14 on the keep-greedy path.
Otherwise continue with Step 3.

- [ ] **Step 3: Run confirm-1 (Phase 2)**

```powershell
python research/method_tournament/run_tournament.py --phase confirm1
```
Expected: `(len(retained)+1) x 36` episodes (retained 5-8 arms => 216-324
episodes, roughly 1-3 hours on 4 workers), `invalid: 0`, exit 0, sealed
`per_phase/confirm1.done`. Resumable: rerun the same command if interrupted.

- [ ] **Step 4: Assert the confirm-1 gate**

```powershell
python -c "import json,pathlib; mt=pathlib.Path('research/method_tournament'); d=json.loads((mt/'per_phase/confirm1.done').read_text(encoding='utf-8')); ret=json.loads((mt/'screening_results.json').read_text(encoding='utf-8'))['retained']; exp=(len(ret)+1)*36; assert d['episodes']==exp and d['invalid']==0, d; print('confirm1 gate PASS:', exp, 'episodes, 0 invalid')"
```
Expected: `confirm1 gate PASS: <n> episodes, 0 invalid`.
If `invalid > 0`: the phase is sealed but the invalid arms are disqualified for
selection (`select_top` excludes them). Report the `invalid_keys` to the user and
STOP - never delete rows, never touch frozen methods (design section 8), never
rerun with modified code.

- [ ] **Step 5: Run the confirm-1 analysis**

```powershell
python research/method_tournament/analyse_tournament.py --phase confirm1
```
Expected: writes `confirmation_results.json` + `confirmation_report.md`; prints
`{"selected": [...]}` (0-2 arms, zero-invalid, top mean delta).

- [ ] **Step 6: Assert the selection contract**

```powershell
python -c "import json,pathlib; d=json.loads(pathlib.Path('research/method_tournament/confirmation_results.json').read_text(encoding='utf-8')); sel=d['selected']; arms=d['arms']; assert len(sel)<=2 and all(m in arms for m in sel), sel; assert all(d['per_method'][m]['invalid_episodes']==0 and d['per_method'][m]['mean_delta'] is not None for m in sel), sel; print('confirm1 selection PASS: selected =', sel)"
```
Expected: `confirm1 selection PASS: selected = [...]`. An empty list is valid
(all arms invalid/absent) and drives the Phase-3 keep-greedy path in Task 14/15.

- [ ] **Step 7: Write and verify the confirm-1 boundary manifest**

```powershell
python -c "import hashlib,pathlib; root=pathlib.Path('.'); here=root/'research/method_tournament'; named=['methods_a.py','methods_b.py','methods_c.py','methods_d.py','methods_e.py','common.py','alloc.py','registry.py','_cli.py','gen_policies.py','run_tournament.py','analyse_tournament.py','instrument.py','design.md','methods.json']; files=sorted({here/n for n in named} | set((here/'policies').glob('*.py')) | {root/n for n in ('kit.py','policy.py','policy_ac.py','evaluate.py','organise.py','Dockerfile')}); (here/'hashes').mkdir(exist_ok=True); (here/'hashes'/'policy_freeze_after_confirm1.txt').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.relative_to(root).as_posix()+chr(10) for p in files), encoding='utf-8'); a=(here/'hashes'/'policy_freeze_after_screening.txt').read_text(encoding='utf-8'); b=(here/'hashes'/'policy_freeze_after_confirm1.txt').read_text(encoding='utf-8'); assert a==b, 'behavior/spec files changed between screening and confirm1'; print('frozen', len(files), 'files; confirm1 boundary identical to screening freeze')"
python -c "import sys,pathlib; sys.path.insert(0,'research/method_tournament'); import run_tournament as rt; rt.verify_freeze(manifest=str(pathlib.Path('research/method_tournament/hashes/policy_freeze_after_confirm1.txt'))); print('confirm1 boundary manifest verified')"
```
Expected: `frozen 51 files; confirm1 boundary identical to screening
freeze`, `confirm1 boundary manifest verified`. The manifest is the same
repo-root-relative 51-file behavior/spec set as the screening freeze. Any
`AssertionError` here means a frozen file drifted - STOP and report it.

- [ ] **Step 8: Log the milestone**
```powershell
Add-Content -Path research\method_tournament\run_log.txt -Value ("{0} Task13 complete: confirm1 sealed; selected arms recorded in confirmation_results.json" -f (Get-Date -Format o))
```

No commit (spec Section 14).

---
### Task 14: Confirm-2 Run (Phase 3 Execution)

**Files:**
- Generate: `per_phase/confirm2_rows.jsonl`, `per_phase/confirm2.done`
  (only when Phase-3 arms exist)

**Interfaces:**
- Consumes: `confirmation_results.json["selected"]` (0-2 arms); freeze manifest
  (auto-verified by the runner, design section 8).
- Produces: official Phase-3 rows for seeds 152-163 x 6 variants + control -
  the evidence base for the final verdict (Task 15), the instrument pass, and
  container parity (Task 16).

- [ ] **Step 1: Run confirm-2 only if Phase-3 arms exist**

```powershell
$sel = (Get-Content research\method_tournament\confirmation_results.json -Raw | ConvertFrom-Json).selected; if (@($sel).Count -eq 0) { Add-Content -Path research\method_tournament\run_log.txt -Value ("{0} Task14: confirm2 SKIPPED (no Phase-3 arms); keep-greedy path" -f (Get-Date -Format o)); Write-Output 'selected: [] -> confirm2 skipped' } else { Write-Output ("selected arms: " + (@($sel) -join ', ')); python research\method_tournament\run_tournament.py --phase confirm2 }
```
Expected (arms exist): `(len(selected)+1) x 72` episodes (144 for 1 arm, 216 for
2), `invalid: 0`, exit 0, sealed `per_phase/confirm2.done`. Roughly 1-3 hours on
4 workers; resumable.
Expected (empty selection): `selected: [] -> confirm2 skipped`, log line written,
no done file.

- [ ] **Step 2: Assert the confirm-2 gate (handles both branches)**

```powershell
python -c "import json,pathlib; mt=pathlib.Path('research/method_tournament'); sel=json.loads((mt/'confirmation_results.json').read_text(encoding='utf-8'))['selected']; done=mt/'per_phase'/'confirm2.done'; assert (not sel)==(not done.exists()), 'confirm2 done flag disagrees with selection'; exp=(len(sel)+1)*72; d=json.loads(done.read_text(encoding='utf-8')) if done.exists() else None; assert d is None or (d['episodes']==exp and d['invalid']==0), d; print('confirm2 gate PASS:', exp, 'episodes, 0 invalid') if d else print('confirm2 skipped correctly (no arms); a run would have been', exp, 'episodes')"
```
Expected: either `confirm2 gate PASS: <n> episodes, 0 invalid` or
`confirm2 skipped correctly (no arms); a run would have been <n> episodes`.
If `invalid > 0`: STOP and report `invalid_keys` to the user (frozen methods,
rows append-only; the credibility gate in Task 15 already fails any arm with
invalid episodes).

- [ ] **Step 3: Log the milestone**

```powershell
Add-Content -Path research\method_tournament\run_log.txt -Value ("{0} Task14 complete: confirm2 gate checked" -f (Get-Date -Format o))
```

No commit (spec Section 14).

---

### Task 15: Final Analysis, Verdict, and Instrument Pass

**Files:**
- (instrument.py + InstrumentTests were created and verified green in Task 11,
  before the freeze; this task only executes the final instrument pass)
- Generate: `final_results.json`, `final_report.md`,
  `deterministic_checks/instrument_rows.jsonl`,
  `deterministic_checks/instrument_summary.json`

**Interfaces:**
- Consumes: `per_phase/confirm2_rows.jsonl` (or none when Phase 3 was skipped),
  `confirmation_results.json["selected"]`.
- Produces:
  - `analyse_tournament.analyse_confirm2` - per-candidate summaries over 72
    paired units clustered into 12 seed-level means (df = 11), `credible`
    gate at the Bonferroni level, `winner` (or None), and `verdict` (design
    section 9; exactly "Greedy remains the best empirically supported policy
    among the evaluated candidates." when no candidate is credible; never
    "optimal").
  - `instrument.instrument_episode(world, command)` - evaluate.episode replica
    that also counts `zero_selection_days` and MUST produce byte-identical
    `action_sha256` digests (design section 5: instrument pass, digest-verified
    against official rows).
  - `instrument.arms_for(results, key)` - arm list for a phase key; `[]` when absent/empty.
  - `instrument.py` appends an "Instrument pass" section to `final_report.md`
    (diagnostic only; never a ranking input).

- [ ] **Step 1: Confirm `instrument.py` from Task 11**

instrument.py and its `InstrumentTests` were created and verified green in
Task 11, before the freeze (design section 8). This task only EXECUTES the
final pass (Step 4) after the verdict. Verify presence:

```powershell
python -c "import pathlib; p=pathlib.Path('research/method_tournament/instrument.py'); assert p.exists(), 'instrument.py missing - run Task 11 first'; print('instrument.py present (created in Task 11)')"
```
Expected: `instrument.py present (created in Task 11)`.

- [ ] **Step 2: Run the final analysis (Phase 3 verdict)**

```powershell
python research/method_tournament/analyse_tournament.py --phase confirm2
```
Expected: writes `final_results.json` + `final_report.md`; prints the verdict
JSON. Runs safely when Phase 3 was skipped (empty candidate list -> keep-greedy
path; report states no Phase-3 arms).

- [ ] **Step 3: Assert the verdict contract**

```powershell
python -c "import json,pathlib; mt=pathlib.Path('research/method_tournament'); d=json.loads((mt/'final_results.json').read_text(encoding='utf-8')); v=d['verdict']; assert (d['winner'] is None) == v.startswith('Greedy remains'), (d['winner'], v); assert 'optimal' not in v.lower(), v; assert 'never compared' in d['incumbent_note'], 'incumbent cross-seed guard note missing'; print('verdict PASS:', v)"
```
Expected:\ `verdict\ PASS:\ <sentence>`\.\ Exactly\ one\ of:
-\ `Greedy\ remains\ the\ best\ empirically\ supported\ policy\ among\ the\ evaluated\ candidates\.`\ \(no\ credible\ candidate\),\ or
- `<method> is credible on Phase 3 (72 paired units).`

- [ ] **Step 4: Run the instrument pass**

```powershell
python research/method_tournament/instrument.py --phase confirm2
```
Expected: when arms exist, `episodes = (len(selected)+1) x 6` (<= 18; roughly
10-25 minutes - each re-run is a full in-process episode) and
`all_digest_match: true`, exit 0; when Phase 3 was skipped, a `skipped`
summary, exit 0. Digest mismatch (exit 2) means the replica diverged from
evaluate.episode - STOP, fix `instrument.py` only (it is not a method file),
and rerun.

- [ ] **Step 5: Assert the instrument outputs**

```powershell
python -c "import json,pathlib; mt=pathlib.Path('research/method_tournament'); d=json.loads((mt/'deterministic_checks'/'instrument_summary.json').read_text(encoding='utf-8')); assert d.get('skipped') or (d['all_digest_match'] and d['digest_matches']==d['episodes'] and d['episodes']>0), d; assert 'Instrument pass' in (mt/'final_report.md').read_text(encoding='utf-8'); print('instrument PASS:', d.get('skipped') and 'skipped summary recorded' or str(d['digest_matches'])+' digests verified')"
```
Expected: `instrument PASS: ...`.

- [ ] **Step 6: Log the milestone**

```powershell
Add-Content -Path research\method_tournament\run_log.txt -Value ("{0} Task15 complete: final analysis + instrument pass" -f (Get-Date -Format o))
```

No commit (spec Section 14).

---

### Task 16: Container Parity, Integrity After, and Deliverables

**Files:**
- Create (inside `docker_checks/`): `Dockerfile.methods`, `parity.py`
- Generate: `docker_checks/parity_results.json`,
  `integrity/after.txt`, `hashes/tournament_final_manifest.txt`
- Temporarily extend then restore `.dockerignore` (byte-exact restore from the
  baseline copy saved at Step 2, re-hashed against `integrity/frozen_before.txt`;
  never via a git command)

**Interfaces:**
- Consumes: official rows (screening or confirm2, depending on whether Phase-3
  arms exist), `confirmation_results.json["selected"]`, `integrity/before.txt`,
  `integrity/git_before.txt`, freeze manifests.
- Produces: container-parity evidence for the final candidates + control
  (spec: Docker 29.8.x only for final container-parity checks), proof that
  every non-plan file outside `research/method_tournament/` is byte-identical to the
  Task 11 snapshot (HARD), frozen files re-verified against
  `integrity/frozen_before.txt` (HARD), git baseline preserved (HARD), the plan
  hash recorded informationally, plus a final full-tree manifest and the
  delivered artifact set.

- [ ] **Step 1: Check Docker availability**

```powershell
docker version --format '{{.Server.Version}}'
```
Expected: a version string (29.8.x). If Docker is unavailable: STOP and report -
container parity is a required deliverable, not an optional step.

- [ ] **Step 2: Temporarily extend `.dockerignore`**

Write (here-string; the context needs the frozen sources plus our method tree):

```powershell
$enc2 = New-Object System.Text.UTF8Encoding($false)
Copy-Item .dockerignore research\method_tournament\integrity\dockerignore_baseline.txt
$text = @'
*
!kit.py
!policy.py
!Dockerfile
!research
!research/method_tournament
'@
[System.IO.File]::WriteAllText((Join-Path $PWD '.dockerignore'), $text, $enc2)
Get-Content .dockerignore
```
Expected: the six lines above. Note `evaluate.py` is NOT needed in images -
episodes are executed by the host harness; images only host the policy process.

- [ ] **Step 3: Write the single methods image Dockerfile**

```powershell
$enc3 = New-Object System.Text.UTF8Encoding($false)
$df = @'
FROM python:3.12.7-slim
WORKDIR /app
COPY kit.py policy.py ./
COPY research/method_tournament research/method_tournament
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER 65534:65534
'@
[System.IO.File]::WriteAllText((Join-Path $PWD 'research\method_tournament\docker_checks\Dockerfile.methods'), $df, $enc3)
docker build -f research\method_tournament\docker_checks\Dockerfile.methods -t smt-tournament:methods .
```
Expected: build succeeds. The image carries kit + policy + the whole method
tree; the per-arm command (control vs launcher) is supplied at `docker run`
time, so one image covers every arm.

- [ ] **Step 4: Write `docker_checks/parity.py`**

```python
"""Container parity (spec: Docker only for final container-parity checks).

For every final arm (shared control + Phase-3 candidates) re-runs official
worlds inside the sandboxed image and requires action_sha256 identity with the
sealed official rows. Candidate arms use seed 152 (confirm2); when Phase 3 was
skipped, only the control is checked against its screening seed 143 rows.
"""
import json
import pathlib
import sys
import uuid

HERE = pathlib.Path(__file__).resolve().parent
MT = HERE.parent
sys.path.insert(0, str(MT))
sys.path.insert(0, str(MT.parents[1]))
import evaluate  # noqa: E402
import run_tournament as rt  # noqa: E402

IMAGE = 'smt-tournament:methods'
CHECK_SEED = 152


def docker_cmd(argv_tail):
    # Same sandbox flags as evaluate.docker_command, plus an explicit command.
    return ['docker', 'run', '--rm', '-i',
            '--name', 'sequential-' + uuid.uuid4().hex,
            '--network=none', '--cpus=2', '--memory=1g', '--memory-swap=1g',
            '--pids-limit=64', '--read-only', '--cap-drop=ALL',
            '--security-opt=no-new-privileges', '--user=65534:65534',
            '--tmpfs=/tmp:rw,noexec,nosuid,size=64m', IMAGE] + argv_tail


def arm_cmd(method):
    if method == rt.CONTROL:
        return docker_cmd(['python', 'policy.py', '--baseline', 'greedy'])
    return docker_cmd(['python',
                       'research/method_tournament/policies/' + method + '.py',
                       '--baseline', 'greedy'])


def official_row(method, seed, variant, phase):
    for r in rt.dedupe(rt.load_rows(
            MT / 'per_phase' / (phase + '_rows.jsonl'))):
        if (r['method'] == method and r['seed'] == seed
                and r['variant'] == variant):
            return r
    return None


def check_arm(method, seed, phase):
    out = []
    for variant in rt.VARIANTS:
        world = rt.generate(seed, 200, 'evaluation', variant)
        docker = evaluate.episode(world, arm_cmd(method))
        off = official_row(method, seed, variant, phase)
        match = bool(off and off.get('valid')) and (
            docker['action_sha256'] == off['action_sha256'])
        out.append({'variant': variant,
                    'docker_sha256': docker['action_sha256'],
                    'official_sha256': off['action_sha256'] if off else None,
                    'match': match,
                    'docker_valid': bool(docker.get('valid'))})
    return out


def main():
    confirmation = json.loads(
        (MT / 'confirmation_results.json').read_text(encoding='utf-8'))
    selected = list(confirmation.get('selected') or [])
    if selected:
        arms = [(m, CHECK_SEED, 'confirm2') for m in selected]
        arms.append((rt.CONTROL, CHECK_SEED, 'confirm2'))
    else:
        arms = [(rt.CONTROL, 143, 'screening')]
    results = {}
    all_ok = True
    for method, seed, phase in arms:
        rows = check_arm(method, seed, phase)
        results[method] = rows
        all_ok = all_ok and all(r['match'] and r['docker_valid'] for r in rows)
    summary = {'image': IMAGE, 'arms': [a[0] for a in arms],
               'worlds_per_arm': len(rt.VARIANTS), 'results': results,
               'all_match': all_ok}
    (HERE / 'parity_results.json').write_text(
        json.dumps(summary, indent=2, sort_keys=True) + '\n',
        encoding='utf-8')
    print(json.dumps({'all_match': all_ok,
                      'arms': summary['arms']}, indent=2))
    return 0 if all_ok else 2


if __name__ == '__main__':
    raise SystemExit(main())
```

- [ ] **Step 5: Run container parity**

```powershell
python research/method_tournament/docker_checks/parity.py
```
Expected: `all_match: true`, exit 0. Cost: 6 worlds per arm, <= 18 episodes
(<= ~40 minutes - each in-episode `docker run` pays container startup).
Mismatch (exit 2): STOP and report - a digest mismatch between container and
official rows means non-determinism; do not proceed to deliverables.

- [ ] **Step 6: Restore `.dockerignore` byte-exact**

```powershell
Copy-Item research\method_tournament\integrity\dockerignore_baseline.txt .dockerignore -Force
$want = @('*', '!kit.py', '!policy.py', '!Dockerfile')
$got = @(Get-Content .dockerignore)
if (Compare-Object $want $got) { throw '.dockerignore not restored to baseline' }
Write-Output '.dockerignore restored to baseline (4 lines)'
```
Expected: `.dockerignore restored to baseline (4 lines)`.
NOTE: `.dockerignore` was extended in Step 2; restore it from the baseline copy
saved there (never via git), and this restore must happen even if a later step
failed - re-run it last if anything was written afterwards. Step 7 category 1
re-verifies it against `integrity/frozen_before.txt`.

- [ ] **Step 7: Integrity "after" snapshot and comparison**

```powershell
# Category 1 (HARD GATE): frozen-file manifest
python -c "import hashlib,pathlib; frozen=['kit.py','policy.py','policy_ac.py','evaluate.py','organise.py','Dockerfile','.dockerignore','test_kit.py','test_runner.py','test_release.py','test_policy.py','research/test_pipeline.py']; now=''.join(hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()+'  '+p+chr(10) for p in frozen); before=pathlib.Path('research/method_tournament/integrity/frozen_before.txt').read_text(encoding='utf-8'); assert now==before, 'frozen file drift: %s' % [l for l in now.splitlines() if l not in before.splitlines()]; print('frozen PASS: %d frozen files byte-identical' % len(frozen))"
# Category 2 (HARD GATE): non-plan tree outside the tournament (tournament outputs excluded by design)
python -c "import hashlib,pathlib; root=pathlib.Path('.'); skip=('research/method_tournament','docs/superpowers/plans/'); files=sorted(p for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts and '.git' not in p.parts and p.suffix != '.pyc' and not any(p.as_posix().startswith(s) for s in skip)); out=pathlib.Path('research/method_tournament/integrity/after.txt'); out.write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.as_posix()+chr(10) for p in files), encoding='utf-8'); a=pathlib.Path('research/method_tournament/integrity/before.txt').read_text(encoding='utf-8'); assert a==out.read_text(encoding='utf-8'), 'drift detected outside research/method_tournament (excluding plan files)'; print('tree PASS: every non-plan path outside the tournament byte-identical (%d files)' % len(files))"
# Category 3 (HARD GATE): tracked git state, read-only capture
$enc4 = New-Object System.Text.UTF8Encoding($false)
$g = @((git rev-parse HEAD)) + @(git status --short -uall)
[System.IO.File]::WriteAllLines((Join-Path $PWD 'research\method_tournament\integrity\git_after.txt'), $g, $enc4)
$gb = @(Get-Content research\method_tournament\integrity\git_before.txt)
if (Compare-Object $gb $g) { throw 'git state drifted from baseline (commits or file changes outside the tournament tree)' }
Write-Output 'git baseline preserved: HEAD a8e26b3, no new commits, baseline status intact'
# Category 4 (HARD GATE): freeze manifests re-verified against current files
python -c "import pathlib,sys; sys.path.insert(0,'research/method_tournament'); import run_tournament as rt; ms=sorted(pathlib.Path('research/method_tournament/hashes').glob('policy_freeze_after_*.txt')); assert ms, 'no freeze manifests found'; [rt.verify_freeze(str(m), base=pathlib.Path('.')) for m in ms]; print('freeze manifests re-verified: %d' % len(ms))"
# Category 5 (INFORMATIONAL): plan-file hash - recorded, never a gate
python -c "import hashlib,pathlib; h=hashlib.sha256(pathlib.Path('docs/superpowers/plans/2026-10-08-method-tournament.md').read_bytes()).hexdigest(); pathlib.Path('research/method_tournament/integrity/plan_after.txt').write_text(h+chr(10), encoding='utf-8'); b=pathlib.Path('research/method_tournament/integrity/plan_before.txt').read_text(encoding='utf-8').strip(); print('plan file:', 'UNCHANGED' if b==h else 'CHANGED - recorded informationally, not a gate')"
# Category 6 (INFORMATIONAL): tournament artifacts - inventoried in Step 8 final manifest
Write-Output 'tournament artifacts: inventoried in hashes/tournament_final_manifest.txt (Step 8)'
```
Expected: `frozen PASS: 12 frozen files byte-identical`, `tree PASS: every
non-plan path outside the tournament byte-identical (<N> files)`, `git baseline
preserved: ...`, `freeze manifests re-verified: 2`, `plan file: UNCHANGED` (or `CHANGED - recorded informationally,
not a gate`). Any HARD-category failure means a frozen or out-of-tree file was
touched - STOP and report exactly which paths differ. The plan hash and the
tournament's own growing artifacts are tracked but never fail the gate.

- [ ] **Step 8: Final full-tree manifest**

```powershell
python -c "import hashlib,pathlib; here=pathlib.Path('research/method_tournament'); files=sorted(p for p in here.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'); (here/'hashes'/'tournament_final_manifest.txt').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.relative_to(here).as_posix()+chr(10) for p in files), encoding='utf-8'); print('manifest over', len(files), 'tournament files')"
```
Expected: `manifest over <N> tournament files`.

- [ ] **Step 9: Full regression - frozen suites + tournament suite**

```powershell
python -m unittest test_kit test_runner test_release test_policy research.test_pipeline research.method_tournament.test_tournament 2>&1 | Select-Object -Last 5
```
Expected: final line `OK` (all frozen suites still green; tournament suite
including the ~1-minute digest-parity test green). Any failure: STOP - do not
touch frozen test files; investigate method-tree regressions only.

- [ ] **Step 10: Assert the deliverables**

```powershell
python -c "import json,pathlib; mt=pathlib.Path('research/method_tournament'); need=[mt/n for n in ('methods.json','design.md','common.py','alloc.py','methods_a.py','methods_b.py','methods_c.py','methods_d.py','methods_e.py','registry.py','_cli.py','gen_policies.py','run_tournament.py','analyse_tournament.py','instrument.py','test_tournament.py','screening_results.json','screening_report.md','confirmation_results.json','confirmation_report.md','final_results.json','final_report.md','run_log.txt','hashes/policy_freeze_after_screening.txt','hashes/policy_freeze_after_confirm1.txt','hashes/tournament_final_manifest.txt','integrity/before.txt','integrity/after.txt','integrity/git_before.txt','integrity/git_after.txt','integrity/frozen_before.txt','integrity/plan_before.txt','integrity/plan_after.txt','integrity/dockerignore_baseline.txt','hashes/pre_screening_fingerprint.txt','deterministic_checks/instrument_screening.json','deterministic_checks/instrument_summary.json','docker_checks/parity_results.json','docker_checks/Dockerfile.methods','docker_checks/parity.py')]; missing=[str(p) for p in need if not p.exists()]; missing+=[str(mt/'per_phase'/(n+'.done')) for n in ('smoke','screening','confirm1') if not (mt/'per_phase'/(n+'.done')).exists()]; pol=sorted((mt/'policies').glob('*.py')); assert len(pol)==30, 'expected 30 launchers, found %d' % len(pol); assert not missing, missing; sel=json.loads((mt/'confirmation_results.json').read_text(encoding='utf-8'))['selected']; assert bool(sel)==(mt/'per_phase'/'confirm2.done').exists(), 'confirm2 done flag vs selection'; print('deliverables PASS: 30 launchers + all results/reports/manifests present')"
```
Expected: `deliverables PASS: 30 launchers + all results/reports/manifests present`.

- [ ] **Step 11: Log the final milestone**

```powershell
Add-Content -Path research\method_tournament\run_log.txt -Value ("{0} Task16 complete: container parity + integrity after + deliverables verified - TOURNAMENT COMPLETE" -f (Get-Date -Format o))
python -c "import json,pathlib; print(json.loads(pathlib.Path('research/method_tournament/final_results.json').read_text(encoding='utf-8'))['verdict'])"
```
Expected: `TOURNAMENT COMPLETE` log line, then the final verdict sentence.

No commit (spec Section 14) - the deliverable is the verified, sealed
`research/method_tournament/` tree plus the untouched baseline git state.

**Final report to the user (in this order):**
1. Verdict sentence, verbatim from `final_results.json["verdict"]`.
2. `final_report.md` path + Phase-3 candidates table (mean delta, CI, credible).
3. `confirmation_report.md` (Phase-2 selection) and `screening_report.md`
   (retention history + any ineligible reasons).
4. Integrity evidence (4 categories): frozen manifest, non-plan tree and git
   baseline all hard-verified; plan hash recorded (informational); freeze
   manifests verified; container parity `all_match: true` (details in
   `integrity/`).
5. Known threats (design section 11) and the cross-seed comparison guard
   (incumbent 0.4931 is a different seed set).
