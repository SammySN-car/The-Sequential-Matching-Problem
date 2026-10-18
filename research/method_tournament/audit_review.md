# Method Tournament - Adversarial Audit Review (Repair Pass, STEP A)

Date: 2026-10-08
Plan under review: `docs/superpowers/plans/2026-10-08-method-tournament.md` (4467 lines, Tasks 1-16, self-consistent, fence-balanced, header complete).
Repair rules in force: no tournament execution; no seeds 143-163 anywhere in testing (fixture seeds >= 90210 only); no git-mutating commands at all; no method/threshold redesign; no optimization disguised as bug fixes.

## Evidence base

- Source: plan line references below; `kit.py` (frozen) line references; `evaluate.py:152`.
- Empirical (fixture seeds 90210-90212, kit-only, executed during this pass):
  `research/method_tournament/preflight_tools/preflight_kit_checks.py`,
  `hashseed_probe.py`, output `preflight_kit_checks.json` (all checks PASS).
- Git (read-only): HEAD `a8e26b35118cfa8e886a02f93984923e43ab64f6`, status ` M policy.py` + pre-existing untracked files; no commits, no mutations; baseline preserved.
- Tournament state: `research/method_tournament/` contains no tournament artifacts (plan not executed; no phase rows exist).

## Verdict summary

| ID | Verdict | Severity | Fix location |
|----|---------|----------|--------------|
| F-01 within-seed clustering / independence | VERIFIED | BLOCKER | design S5/S9, analyse_tournament, AnalyseTests |
| F-02 resume can mix code versions | VERIFIED | BLOCKER | run_tournament (rows, purge, attempts log), RunnerTests |
| F-03 m01 can take retention slot; rounded ranking | VERIFIED | BLOCKER | analyse_screening/select_top, AnalyseTests |
| F-04 retention rule ambiguity (top5 vs 5-8 vs <=8; no 0-case) | VERIFIED | BLOCKER | design S4/S7, analyse_screening, Task 13 |
| F-05 control-equivalence test too weak | PARTIAL | HIGH | Task 4 test matrix |
| F-06 m30/m15/m24/m25 worst-case latency | PARTIAL (severity downgraded by measurement) | HIGH | design S6 + methods.json + common.py cap + Task 9 tests |
| F-07 asking semantics | VERIFIED (semantics OK; doc defects) | MEDIUM | design S6/methods.json gloss, reserve rationale |
| F-08 graph fallback branches conditionally tested; no measurement | VERIFIED | HIGH | Task 4/8 tests + fixture measurement + design S11/methods.json docs |
| F-09 smoke uses tournament seed 143 | VERIFIED | BLOCKER | PHASES smoke seed, design S4, Task 11 |
| F-10 freeze manifest covers only 40 method files | VERIFIED | BLOCKER | Task 12/13 freeze manifest scope, design S8 |
| F-11a PATIENT_MIN_SCORE gloss says strict majority (=4) but code uses 3 | VERIFIED (keep 3; fix gloss) | MEDIUM | methods.json, design S6 |
| F-11b QUOTA_KEEP divisor semantics + 3x `git checkout` commands | VERIFIED | BLOCKER | common.py/design/methods.json/tests + Global Constraints/Task 16 |
| F-12 integrity compare conflates categories | VERIFIED | BLOCKER | Task 16 integrity redesign |
| F-13 no PYTHONHASHSEED test | VERIFIED (kit-level probe passed now) | HIGH | test suite (subprocess), Task 5/10 |
| F-14 zero-selection days only on final seeds | VERIFIED | HIGH | instrument.py screening pass, Task 12/15 |
| F-15 tournament-seed freshness / leakage | CLEARED | - | none (evidence only) |
| F-16 leak scanner too narrow (AST names only) | VERIFIED | BLOCKER | Task 5 scanner v2 + runtime negative tests |
| F-17 degenerate methods / diversity | ADJUDICATED: keep m01; add behavioral-diversity reporting | MEDIUM | screening report + design S11 + final report |
| F-18 augment3_improve edge case | CLEARED (correct; add pathological test) | LOW | Task 4 test |
| F-19 frozen root files missing from manifest | VERIFIED (fold into F-10/F-12) | BLOCKER | Task 12 freeze scope |
| M17 QUOTA_KEEP=2 reads as keep-2, acts as ceil(n/2) | VERIFIED (rename) | MEDIUM | common.py/design/methods.json/tests |
| D-VERDICT keep-greedy sentence wording | required by sponsor | BLOCKER | design S9, analyse code, tests, reports |
| D-DIVERSITY coverage/diversity honesty | required by sponsor | MEDIUM | design S11, methods.json, final report template |

Severity definitions: BLOCKER = must be fixed before any phase runs; HIGH = must be fixed and covered by tests; MEDIUM = must be fixed in docs/spec text; LOW = test hardening only.

---

## Finding details

### F-01 - Within-seed clustering breaks the 72-unit independence assumption - VERIFIED, BLOCKER

Evidence:
- Structural (kit.py:35-67): `generate()` uses one `random.Random(seed)` stream; variants `development`, `delayed`, `shift`, `drift` follow the same draw sequence and values at lines 43 (`variant=='sparse'` guard), 53 (`variant!='sparse'` guard), 55 (`variant=='cold_start'` guard). Only `sparse` (extra zone draw at line 43) and `cold_start` (different `complete` probability at line 55 feeding the short-circuit at line 56) diverge.
- Empirical (preflight_kit_checks.json, check `f01_variant_roster_identity`): for seeds 90210 and 90211, the full member dictionaries (including `truth`, `bias`, `response_rate`, `second_bias`, `exit_day`, observed fields) are byte-equal across `development`/`delayed`/`shift`/`drift` (PASS). `sparse` and `cold_start` differ; member-id alignment across all six variants is false.
- Consequence: 4 of the 6 Phase-1 "paired units" per seed are the same world with different response dynamics; deltas within a seed share one latent draw. Treating 72 units as independent in a t-test is anti-conservative.
- Measured outcome ICC on the 3x6 fixture table: -0.1489 (n=3, unstable; reported for honesty - the identity proof, not the ICC, is the basis for clustering).

Required action (Step B):
1. Inference unit = per-seed mean of the 6 variant deltas (12 seed clusters, df=11). Eligibility gates unchanged in value (grand mean equals mean of seed-level means on this balanced design) but recomputed from the same paired deltas; per-variant gates stay mandatory (stratification reported for every phase).
2. Phase-3 credibility uses the cluster-level CI with Bonferroni level: 1 candidate tested -> 95% CI (t_0.975,df11 = 2.201); 2 candidates -> 99% CI (t_0.995,df11 = 3.106). Add a T99 table (df 1..30). Screening remains gate-only with no superiority claims.
3. Report within-seed cross-variant dispersion descriptively; never present unit-level CIs as primary.

### F-02 - Resume can silently mix code versions - VERIFIED, BLOCKER

Evidence: plan runner `run_one`/resume path writes rows with no code identity; `load_rows` + dedupe (last-wins) would accept rows produced by older code after an edit-restart. No attempts history exists for failed/timeout runs (rows are appended but nothing records restarts or purge decisions).

Required action:
- Compute `code_sha256` per phase start over: `methods_*.py`, `common.py`, `alloc.py`, `_cli.py`, `registry.py`, `gen_policies.py`, `policies/*.py`, `run_tournament.py`, `analyse_tournament.py`, `instrument.py`, `kit.py`, `policy.py`, `policy_ac.py`, `evaluate.py`.
- Every row carries `code_sha256`. On load, any fingerprint mismatch purges the WHOLE phase to `per_phase/<phase>_rows_v<hex8>.jsonl` (archive, never silent partial keep) and appends an attempt record.
- Append-only `per_phase/<phase>_attempts.jsonl`: timestamp, phase, fingerprint, episodes planned/written, invalid written, purge events, exit state. Timeout/failed episodes stay visible via this log (failed rows also carry `valid=false` + `error`).
- Assert single fingerprint per phase in analysis. Tests: synthetic mixed-version purge; attempt-log append.

### F-03 - m01 (control duplicate) can occupy a retention slot; ranking uses rounded means - VERIFIED, BLOCKER

Evidence: plan `analyse_screening` (line 3515) excludes only `rt.CONTROL` (`__control__`), so `m01_greedy_baseline` (delta identically 0) is eligible and ranks near the cut; line 3522 and `select_top` (line 3479) sort on `round(mean,4)`-style values (`method_summary` stores rounded `mean_delta`), making tie order depend on display rounding.

Required action:
- Exclude `m01_greedy_baseline` from eligibility, ranking, retention, and selection everywhere (parity/diagnostic only); guard `m01 not in retained/selected`.
- Rank by full-precision mean (store `mean_full`; display stays rounded), tie-break `(round(mean_full, 6), method_id)`; no boundary expansion.

### F-04 - Retention rule ambiguity - VERIFIED, BLOCKER

Evidence: design S4/S7 says "top 5 + diagnostics 6-8"; phase table says "retain 5-8"; code retains `top5 + eligible[5:8]` (<=8) with no rule for fewer than 5 eligible, zero eligible, exactly 5, or boundary ties. No preregistered statement that the human gate may only remove.

Required action: preregister exact rule: eligible ranked list; candidates = first min(5, E) + next up to 3 diagnostics with fixed-format reasons (total <=8, possible range 0-8); human gate may only REMOVE with a documented reason (no add/swap, no backfill beyond the preregistered list); E=0 -> `retained=[]` -> Phases 2 and 3 skipped, verdict branch `keep-greedy` with reason recorded; ties at the boundary resolved by `(mean_full, method_id)` only. Update design S4/S7, phase table, `analyse_screening`, Task 13 branches and tests.

### F-05 - Control-equivalence test too weak - PARTIAL, HIGH

Evidence: `test_greedy_take_identical_to_kit_baseline_match` and `test_m01_matches_control_greedy` exist but cover a single state (seed 90210, development, day 30) plus a subprocess parity check on one world.

Required action: matrix test over seeds {90210, 90211} x all 6 variants x days {0, 1, 5, 15, 30, 45, 59} via snapshots from one rollout per (seed, variant): `alloc.greedy_take(common.feasible_edges(state)) == kit.baseline_match(state)`. Keep existing subprocess parity.

### F-06 - Worst-case latency of m30/m15/m24/m25 - PARTIAL (downgraded), HIGH

Evidence (measured, 90 snapshots over 18 fixture worlds):
- Feasible-graph edges are small: max 18 edges overall (day 0 range 0-18; day 59 max 5).
- m30 workload proxy max: day 0, 18 edges x 562 soft-not-asked pairs (max soft-not-asked at day 59: 816, mean 688.3) -> bounded, not seconds-scale; the originally feared full-enumeration blow-up does not materialize at this scale.
- Node counts reach 195 > HUNGARIAN_NODE_CAP=180 (6/90 snapshots, days 30/45) so cap-fallback paths are exercised in reality; non-bipartite graphs occur in 5/90 snapshots (days 0 and 30).
- Existing latency tests: `test_hungarian_latency_on_dense_day59` is vacuous when `two_color` returns None (plan line 1135); normal-state m30 test is not a worst-case construction.

Required action:
- Preregister a deterministic cap `VOI_EVAL_CAP` (max greedy recomputations per ask phase, fixed enumeration order) in `common.py` + design S6 + methods.json m30 + frozen-constants test; worst-case m30 fixture test (dense day-59 gate-passing state with many not-asked soft fields) with <5 s assert.
- Non-vacuous branch tests: guaranteed-bipartite synthetic for Hungarian timing (n<=180); forced odd-cycle (K3) fixtures for `two_color -> None` fallbacks (m24/m25) with <5 s asserts; assert the branch under test actually ran.

### F-07 - Asking semantics - VERIFIED (semantics OK; doc defects), MEDIUM

Evidence (runtime probe PASSED):
- `baseline_asks` returned exactly `12//3 = 4` bundles, all `field='constraints'`, day-0 budget 12.
- Hand-crafted constraints ask on a member with a declined HARD key: cost charged = 3; declined key stayed `None` (not filled, not imputed); 10/11 other HARD fields filled and visible to the same-day match phase.
- Budget after `advance()` = 12 (day reset confirmed at kit.py:189).
- Soft-unknown feasible pairs exist mid-episode (2 after 10 baseline days) - soft fields never gate feasibility (kit.py `eligibility` counts only HARD in `missing`).
- m29/m30 reserve: `SOFT_ASK_RESERVE=3` -> `(12-3)//3 = 3` hard bundles/day vs control's 4 (one fewer) - a real, preregisterable mechanism disadvantage.

Required action: fix gloss `strict majority of the 7 soft fields` -> `at least 3 of the 7 observed soft fields (suite-wide strong-alignment cutoff, same constant as STRONG_SCORE)` in methods.json + design; state the reserve rationale (soft-capped methods trade one constraints bundle/day for soft coverage) in design S6 + methods.json; keep tests asserting cost/budget/reserve.

### F-08 - Graph fallback branches conditionally tested; no frequency measurement - VERIFIED, HIGH

Evidence: plan tests guard fallbacks with `if colored is not None` / `if got is None` (lines ~1120-1137); on likely-bipartite fixtures the fallback (`augment3_improve`, `one_swap_improve`) silently never runs; no fallback-frequency measurement exists. Empirically fallback IS reachable: non-bipartite in 5/90 real snapshots; node cap exceeded in 6/90.

Required action: forced K3 odd-cycle tests asserting `two_color(...) is None` first (prevents vacuous skip), then fallback equality vs reference + latency; fixture measurement in preflight (bipartite fraction, node counts vs cap, fallback frequency) reported in design S11 + methods.json known_risks; document overlaps m24~m27 (augment3) and m25~m26 (one-swap) honestly; note m25 prunes zero-score edges (weight objective unaffected; cardinality may differ).

### F-09 - Smoke phase uses tournament seed 143 - VERIFIED, BLOCKER

Evidence: `PHASES['smoke'] = {'seeds': (143,), ...}` (plan line 3016); design phase table line 526; Task 11 text. Running machinery checks on 143 pre-loads a tournament seed before the freeze.

Required action: smoke seed -> 90290 (fixture range, never a tournament seed); update PHASES, design S4, Task 11/15 wording; keep "seeds 143-163 untouched until screening" guarantees.

### F-10 / F-19 - Freeze manifest too narrow - VERIFIED, BLOCKER

Evidence: freeze manifest (Task 12/13) hashes only the 40 `methods_*.py` files; `run_tournament.py`, `analyse_tournament.py`, `instrument.py`, `design.md`, `methods.json`, launchers, `common/alloc/_cli/registry/gen_policies`, and root frozen files (`kit.py`, `policy.py`, `policy_ac.py`, `evaluate.py`, `organise.py`, `Dockerfile`) are outside it; verify_freeze bases at `HERE`.

Required action: manifest = full behavior/statistics/spec set (repo-root-relative paths; `verify_freeze(base=ROOT)`), explicitly excluding tests (documented); design S8 updated; pre-screening `code_sha256` (F-02) covers the window before the manifest exists; analysis asserts screening rows match the pre-screening fingerprint.

### F-11a - PATIENT_MIN_SCORE gloss - VERIFIED (keep 3), MEDIUM

Evidence: `PATIENT_MIN_SCORE = 3` (tests assert 3; mechanism text uses "= 3") vs design/methods.json gloss `strict majority of the 7 soft fields` (would be 4).

Required action: keep 3 (mechanism literal, STRONG_SCORE consistency); replace gloss everywhere with `at least 3 of the 7 observed soft fields`. Do not change thresholds.

### F-11b - QUOTA_KEEP divisor semantics + git checkout commands - VERIFIED, BLOCKER

Evidence: `quota_half` computes `ceil(n / QUOTA_KEEP)` with QUOTA_KEEP=2 (plan line 985-988; tests expect five->3, four->2) - the constant is a divisor, not a keep-count. Plan lines 2807, 4229, 4399 instruct `git checkout -- ...` (git-mutating, forbidden) for .dockerignore/test restoration; Global Constraints repeat it.

Required action: rename `QUOTA_KEEP` -> `QUOTA_DIVISOR` everywhere (common.py, design S6 table+rationale, alloc docstring, methods_b/m17, methods.json, tests); replace every `git checkout` with saved-copy restoration + hash verification (save `.dockerignore` baseline copy at Task 16 start; restore by writing the copy; tests are never edited - abort and report instead); keep read-only `git rev-parse`/`git status` recording.

### F-12 - Integrity compare conflates categories - VERIFIED, BLOCKER

Evidence: Task 16 before/after integrity compares the whole tree, which fails on legitimate tournament outputs and conflates plan edits with frozen-file changes.

Required action: four recorded categories with independent verdicts: (1) frozen-file manifest (hard gate), (2) tracked git status + HEAD (hard gate, read-only capture), (3) tournament artifact inventory (informational), (4) plan-file hash (informational). No whole-tree equality gate.

### F-13 - No PYTHONHASHSEED coverage - VERIFIED (kit-level OK), HIGH

Evidence: kit-level probe (hashseed_probe.py) produced identical digests for PYTHONHASHSEED=0/1/random (world serialization + 60-day baseline ask/match actions). The plan has no such test for method code, where float/set iteration order is the actual risk (m02/m08 scores are floats with real ties; `greedy_take` tie-breaks by `pair_key` - plan line 971 - which is deterministic).

Required action: subprocess test running fixture decision digests under PYTHONHASHSEED=0/1/random (assert equality); explicit equal-float tie tests for m02/m08 via `greedy_take`; keep sorted-everywhere rules.

### F-14 - Zero-selection days only measured on final seeds - VERIFIED, HIGH

Evidence: instrument zero-selection pass runs on confirm2 (seeds 152-163) only; screening-phase waiting behaviour (methods that never match) is unreported.

Required action: instrument supports `--phase screening` (control + retained arms, worlds = 143 x 6 variants, digest-verified against screening rows) run after the retention gate; report zero-selection days at both phases; instrument.py created before freeze (moved into Task 11) so it is covered by the manifest.

### F-15 - Seed freshness / leakage - CLEARED

Evidence: no research artifact contains seeds 143-163 (e3 used 101-130 stage1, 131-142 stage2 in `s2_*.json`; round2 experiments use 101-118); `evaluate.py:152` uses `generate(seed, 200, 'evaluation', variant)` identical to the runner's world generation; plan is the only file mentioning 143-163. No action.

### F-16 - Leak scanner too narrow - VERIFIED, BLOCKER

Evidence: `BANNED_NAMES` AST scan (plan ~1410) checks Name/Attribute/Constant only; no import restrictions (os/sys/subprocess/importlib/inspect), no `eval/exec/compile/getattr/__import__/open`, no dunder attribute access. Launcher templates are clean (pathlib/sys/_cli/registry only - plan line 1689-1698); gen_policies uses pathlib/sys/registry.

Required action: scanner v2 - banned callables (eval, exec, compile, `__import__`, getattr/setattr, globals/locals/vars, open), banned modules per file class (methods_*.py: os/sys/subprocess/importlib/inspect/etc.; launchers: only pathlib/sys/_cli/registry; `_cli`: json/sys), dunder-attribute blacklist; runtime negative tests (patch `kit.generate`/`Simulator`/`rollout` to raise - decide functions must still respond; protocol-state key scan for `truth/bias/response_rate/...` leakage).

### F-17 - Method diversity / degenerate methods - ADJUDICATED (keep m01), MEDIUM

Sponsor decision: do NOT remove m01 (its parity is a feature). Instead: behavioral-diversity check from screening digests - list any method whose action digest equals control on all 18 worlds as `no observed difference from control`; describe the field as ~30 policy variants/mechanisms (not 30 independent paradigms); design S11 + methods.json known_risks carry overlap notes (m04~m05, m12~m13~m14, m24~m27, m25~m26, m01/control).

### F-18 - augment3_improve edge case - CLEARED (add test), LOW

Evidence: `_adjacency` stores `(score, neighbor)` (plan line 1153), so `for _, v in adj.get(x, ())` in `augment3_improve` (line 1325) unpacks correctly (score ignored, neighbor used); `y == z` skip is safe (no overlap possible), deterministic (first free neighbor in `(-score, node)` order), and `rounds_cap` bounds work. Heuristic limitation (does not try alternative free neighbors when y==z) is acceptable for a capped improver.

Required action: add a pathological-fixture test (only one shared free neighbor -> assert unchanged pairs, no overlap, deterministic).

### M17 - QUOTA constant naming - VERIFIED (folded into F-11b), MEDIUM

`ceil(n/2)` semantics confirmed by tests (five->3, four->2). Rename to QUOTA_DIVISOR as part of F-11b; no behaviour change.

### D-VERDICT - keep-greedy sentence - BLOCKER

Replace every occurrence of `Greedy remains the best empirically supported policy.` with exactly:
`Greedy remains the best empirically supported policy among the evaluated candidates.`
Locations: design S9, `analyse_confirm2` (plan line 3663), Task 15 asserts, Task 16 report list, Global Constraints. Never `optimal`.

### D-DIVERSITY - coverage/diversity honesty - MEDIUM

Add to design S11 + final report template: sequential-coverage limitation (candidate set spans little feedback-history/memory/long-horizon state; field_observed_day dynamics limited); candidate set described as variants/mechanisms with documented overlaps; selection remains purely mechanical.

---

## Verified-now vs enforced-at-execution

Verified during this pass (fixture seeds 90210+): roster identity; asking semantics (costs, declined handling, same-day visibility, day reset, soft-non-blocking); kit hash-seed independence; graph branch statistics (bipartite fraction, cap breaches, edge/sizes); seed freshness; freeze/git baseline; plan structure scans.

Enforced by plan tests after Step B (executed before any phase): method-level leak scan v2 + runtime negatives; equivalence matrix; forced graph branches + latencies + m30 worst-case cap; retention/selection/cluster-statistics unit tests; runner purge/attempt tests; hash-seed subprocess tests; smoke gate on fixture seed; freeze manifest scope; four-category integrity.

## Next steps

Step B applies the required actions to the plan (design, methods.json, runner, analysis, tests, freeze, integrity, constraints). Step C writes `preflight_report.md` with the verdict. Step D runs fixture-only tests. Step E stops for separate authorization.