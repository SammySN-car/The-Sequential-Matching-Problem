# E1/E2/E3 REL-Ask × Analytic-Score Experiment — Design (Stage A)

> For Stage B execution: bite-sized tasks in section 8. Frozen files are NEVER
> modified: `policy.py`, `policy_ac.py`, `kit.py`, `evaluate.py`, `organise.py`,
> `Dockerfile`. All new code lives under `research/e3_rel_experiment/`.

**Goal:** isolate whether realized MSMI can be improved over the incumbent greedy
policy by (A) REL information acquisition, (B) analytic pair scoring, (C) their
interaction — as a controlled 4-arm paired experiment, not as tuning.

**Architecture:** three new standalone policy files + one runner script + one
instrumented simulator subclass (subclass only, kit.py untouched) + shared
scoring/gate library module imported by the policies.

**Spec:** this file + `leakage_audit.md` + `experiment_plan.json`.

## Review Focus (failure modes most likely to invalidate the experiment)

1. **Gate degenerates into ask-everything** (E1 stops being "asks-only" and
   becomes noise) — pinned by Task 1 test (d): fixtures where a reveal cannot
   change A0 must produce NO ask.
2. **REL asks steal hard-ask budget** (breaks the hard-saturation isolation
   between C and E1/E3) — pinned by Task 1 test (c): rel_asks must subtract
   `3 * len(baseline_asks)` before spending; assert when budget == 12 and 4
   hard bundles are eligible, zero REL asks are emitted.
3. **E2/E3 matcher silently not kit's algorithm** (allocation becomes a second
   variable) — pinned by Task 1 test (a): take_free_alloc with s_count must
   equal kit.baseline_match exactly on fixtures incl. tie cases.
4. **Invalid episodes from duplicate/depleted asks** (invalidates the run) —
   pinned by Task 1 test (c) (no duplicates, `not_asked` only) plus the
   harness's own ValueError -> invalid path; smoke in Task 3.
5. **Nondeterminism from set/dict iteration** (breaks rerun parity) — pinned
   by determinism test in Task 4 (byte-identical action_sha256) and by sorting
   every collection in rel_common (Task 1 test (c) shuffles inputs).

---

## 0. Verified contract facts the design rests on (all read from source)

| Fact | Evidence |
|---|---|
| Each episode = 60 days x (ask phase -> `resolve_asks` -> match phase -> `advance`) with a FRESH subprocess per phase; memory JSON-carried, <=1 MiB | evaluate.py:85-97, 45-69, 32-33 |
| Ask results are state-visible **the same day** (match phase re-observes) | evaluate.py:88, 95; kit.py:128 |
| REL ask = `{'member_id', field}` with field in SOFT, cost 1; budget 12/day resets at `advance` | kit.py:112-122, 189 |
| Ask reveals **exact truth** for that field (`fields[k] = truth[k]`) unless status == 'declined', which is silently skipped but still charged | kit.py:127-128, 121 |
| Members must be `available` to ask (arrived, not busy, not paused, not exited); same-day duplicate (member, field) raises -> **invalid episode** | kit.py:118, 120; evaluate.py:151-154 |
| Incumbent asks = `baseline_asks` (hard constraints bundles only, up to 4/day); matches = `baseline_match` (count score, take-while-free) | policy.py:24, 28; kit.py:205-222 |
| REL = the 4 outcome fields {relationship_goal, relationship_pace, lifestyle, conversations}; the other 3 SOFT fields do not enter `kit._prob` | kit.py:12-13, 135 |
| Unused ask headroom after hard saturation: ~517 units/episode (61 on days 11-21, 456 on days 22-59); full REL reveal would need ~225.5 | research/next_strategy_research/data_analysis.json |
| Declined REL fields: ~17.5/world permanently unaskable (gate must skip them) | static_analysis.json |
| Variant/seed/truth/params are NOT in state; policy state surface listed in leakage_audit.md sec. 3 | kit.py:101-109 |

## 1. Arms (exact behavioral contracts)

All arms: identical `decide(request)` structure, identical argv handling
(accept `--baseline greedy` and ignore it — evaluate passes only
`greedy|no_asks|random`, evaluate.py:137,147), identical output protocol
(`{'asks'|'pairs', 'memory': ...}`, strict JSON, no NaN).

### Control (C)
File: existing `policy.py`, invoked `--policy policy.py --baseline greedy`.
Behavior: `baseline_asks` + `baseline_match` (policy.py:24, 28). Unchanged.

### E1 — asks-only
File: `research/e3_rel_experiment/policy_e1.py`
- **Ask phase:** `asks = baseline_asks(state)` first (hard saturation identical
  in logic to control), then REL VoI asks (section 2) with whatever budget is
  left.
- **Match phase:** `baseline_match(state)` — byte-identical to control.
- Purpose: effect of REL information alone (still flows through the count score,
  which is what revealing changes).

### E2 — score-only
File: `research/e3_rel_experiment/policy_e2.py`
- **Ask phase:** exactly `baseline_asks(state)` — zero soft asks, byte-identical
  to control.
- **Match phase:** kit's take-while-free allocation algorithm with the analytic
  scorer replacing the count score (section 3). No floor, no local search, no
  MWM: the SAME `sorted((-score, key)) -> take while both free` loop as
  kit.py:220-221.
- Purpose: effect of scoring alone on progressively-revealed observation.

### E3 — full treatment
File: `research/e3_rel_experiment/policy_e3.py`
- **Ask phase:** `baseline_asks(state)` first, then REL VoI asks (section 2).
- **Match phase:** analytic scorer + take-while-free (section 3).
- Purpose: interaction of information x scoring.

Shared library: `research/e3_rel_experiment/rel_common.py`
(scoring, allocation, VoI gate, constants). The three policy files are thin
wrappers around it, so the scorer/gate is written and tested exactly once.

## 2. The VoI gate (REL asks) — enumeration-based, truth-blind, no tunables

**Naming (preregistered language):** the offline "+18.7%" condition is the
*oracle full REL reveal* — an offline upper bound ONLY, never a live arm.
Live arms: E1 = "REL-asks-only", E2/E3 = "analytic scorer".

Objective: spend ask budget only where a legal answer could change today's
chosen introductions. The gate is a decision-change test over the PUBLIC
answer space — it never touches the actual answer.

```
def voi_rel_asks(state, score_kind, order_key):
    asks = baseline_asks(state)                     # hard first, unchanged
    spent = 3 * len(asks)
    budget = state['ask_budget_remaining'] - spent
    if budget <= 0 or no feasible edges: return asks

    edges    = candidate_edges(state)               # available, feasible, non-past
    fields   = observed fields per member
    base     = score_kind ('count' for E1, 'analytic' for E3)
    A0       = take_free_alloc(edges, base)         # today's would-be allocation

    candidates = all (m, k) with m available,
                 field_status[k] == 'not_asked' (declined/observed excluded),
                 k in REL, m incident to >=1 edge
    order candidates by order_key:  E1: (member_id, field)
                                    E3: (-W[k], member_id, field)   # published weights

    for (m, k) in candidates:
        if spent + 1 > budget: break
        # enumerate EVERY legal observable answer from the public DATA_CONTRACT
        for v in kit.OPTIONS[k]:
            A_v = take_free_alloc(edges, base with m's field k set to v)
            if A_v != A0:                           # at least one legal answer
                emit ask (m, k); spent += 1         #   could change the allocation
                break                               #   -> ask; stop enumerating
    return asks
```

- **Truth-blind:** the enumerated set is `kit.OPTIONS[k]` (the published answer
  vocabulary); the gate never reads `truth`, never marks which hypothetical is
  real, never inspects outcomes or hidden state. It asks iff >=1 legal answer
  would change the allocation.
- Single-sided reveals (partner's k also missing) are still enumerated; they
  provably cannot change either score's edge value (count needs both sides;
  analytic one-sided contribution is prior-invariant), so they never flip A0 —
  verified by test rather than assumed.
- Declined/observed excluded via `not_asked` (kit still charges declined asks —
  kit.py:121 — so the filter also protects the budget).
- Budget: hard asks already reserved; REL spends only leftovers.
- Deterministic: every collection sorted; no set iteration; no RNG.
- Cost model: uniform cost 1; fields restricted to the 4 REL fields — the
  simulator's own SOFT list, nothing invented.

## 3. Analytic scorer (E2/E3 match phase)

Exact form (mirrors static_analysis.py:52-66, decision-time inputs only):

```
W = {'relationship_goal': .7, 'relationship_pace': .4,
     'lifestyle': .25, 'conversations': .2}          # kit._prob defaults (kit.py:135)
PRIOR_EQ[k] = 1/len(OPTIONS[k])                      # uniform prior over published options

fit(a, b) = sum over k in W:
    both observed: w * (+1 if equal else -0.5)
    else:          w * (1.5*PRIOR_EQ[k] - 0.5)       # prior mean
score(a, b) = fit + 0.02 * (1.5*goal_eq_or_prior - 0.5)
```

Allocation: kit's exact take-while-free loop over `sorted((-score, key))`
(kit.py:219-221), inputs = state members' observed `fields` (kit invariant:
`fields` never holds a value observed after the current day).

## 4. STEP 4 — identifiability checklist (verified, with evidence)

| Question | Answer | Evidence |
|---|---|---|
| What REL answers can the policy request? | The 4 REL fields by name, per member, cost 1 | kit.py:119, 121; SOFT list 12-13 |
| Does asking reveal exact synthetic truth? | Yes — `fields[k] = truth[k]`, status observed | kit.py:128 |
| Declined REL vs declined hard? | Same semantics: permanently unaskable, never imputed; soft-ask on declined silently returns status declined and STILL COSTS 1 -> gate filters to `not_asked` so it is never spent | kit.py:127, 121, 131 |
| Immediately usable same day? | Yes — ask phase resolves before match phase re-observes | evaluate.py:88, 95 |
| Does asking change member state? | Only fields/status/observed_day + budget; availability, busy, past untouched | kit.py:128, 122-123 |
| Can ask results influence matching same invocation? | Yes, same day (next phase) | evaluate.py:86-97 |
| Repeated asks? | Same-day duplicate -> ValueError -> invalid; cross-day re-ask of observed/declined allowed by kit but pure waste -> policy filters on `not_asked` | kit.py:120, 127-128 |
| Does the budget permit meaningful treatment? | Yes: 12/day; hard-first consumes 12/day only while hard saturation incomplete (~day 19); 517 free units total vs ~225.5 needed for full REL | data_analysis.json |
| Enough unresolved REL for separation? | Yes: ~225.5 not_asked REL fields/world among matchable at saturation, plus progressive early-game discovery; control/E2 ask 0 REL, E1/E3 ask up to budget -> arms are separable | static_analysis.json |

**Verdict: E1/E2/E3 are identifiable. No stop condition triggered.**

## 5. Instrumentation (mechanism metrics, no frozen-file edits)

Runner: `research/e3_rel_experiment/run_experiment.py` imports `evaluate` and
passes a SUBCLASS `InstrumentedSim(evaluate.Simulator)` via the existing
`simulator_class` seam (evaluate.py:80):

- overrides `resolve_asks` to record `(day, member_id, field, cost, status)`
  then calls super() — captures REL ask counts, cost, day, declined hits.
- per episode derives: REL asks/day, REL ask cost, zero-selection days,
  introduced-pair count.
- "fraction of asks that changed the eventual candidate ranking": for each day,
  recompute the arm's match-phase allocation with vs without that day's
  newly revealed REL fields (using the arm's own score_fn from rel_common);
  fraction of days where the chosen set differs + fraction of REL asks touching
  a member introduced that day.
- "fraction of candidates/edges affected by REL revelation": share of that day's
  feasible edges incident to >=1 newly revealed field.

These run in the runner process only; policy files never see a Simulator.

## 6. Guardrails and safety (STEP 9)

- Pre-run: `python -m unittest test_kit test_runner test_release test_policy`
  and `python -m unittest research.test_pipeline` must pass BEFORE Stage B code.
- Invalid episode = evaluate `valid: false` (any protocol/ask-budget/overlap/
  feasibility error, any exception, >10s invocation) -> run ineligible ->
  **no performance interpretation** (evaluate.py:119-120, 151-154, 167).
- Determinism: rerun a fixed 12-episode slice twice; `action_sha256` and all
  metrics must match byte-for-byte (evaluate.py:93, 114).
- Latency: each invocation <= 10s (evaluate.py:45, 61); report inference
  seconds vs control.
- Integrity: SHA256 of the 6 frozen files + `git status --porcelain` captured
  before and after (`integrity_before/`, `integrity_after/`); 0 commits.
- Container fidelity: Docker 29.8.0 available; the frozen Dockerfile's CMD runs
  `policy.py`, so the official image can verify CONTROL local-vs-container
  parity; E-arms use an ADDITIONAL `research/e3_rel_experiment/Dockerfile.e3`
  (new file, derived image, frozen Dockerfile untouched) if feasible — else
  container fidelity is reported honestly as control-only with reasons.
- Nondeterminism sources ruled out by design: no set iteration in decisions,
  no dict-order dependence (sorted keys everywhere), no RNG, no wall clock.

## 7. What is explicitly OUT of scope (STEP 8)

No MWM, no local search/tuning, no floor/threshold search, no RL, no retraining,
no history features, no new feature families, no hyperparameter search, no wait/
hold rules, no hard-ask redesign (hard logic stays `baseline_asks`), no changes
to simulator, harness, or incumbent. Exactly one variable per arm.

## 8. Stage B tasks (bite-sized, in execution order)

Task 1: shared library + unit tests
- Create: `research/e3_rel_experiment/rel_common.py`,
  `research/e3_rel_experiment/test_rel_experiment.py`
- Produces: `s_count(a,b)`, `s_analytic(a,b)`, `take_free_alloc(edges, score_fn,
  overrides=None)`, `rel_asks(state, score_fn)`, constants REL/W/PRIOR_EQ.
- [ ] Step 1: write failing tests: (a) `take_free_alloc` on a fixture edge set
  equals `kit.baseline_match` output when score_fn = s_count; (b) s_analytic
  prior/observed branches match hand-computed values; (c) rel_asks never emits
  declined/observed fields, never exceeds budget, never duplicates, is
  order-deterministic (shuffle input member order -> same output);
  (d) a fixture where a reveal provably flips A0 (assert ask emitted) and a
  fixture where it cannot (assert not emitted).
- [ ] Step 2: run `python -m unittest research.e3_rel_experiment.test_rel_experiment`
  -> FAIL (module missing).
- [ ] Step 3: implement rel_common.py to spec (section 2-3 code above).
- [ ] Step 4: rerun -> PASS.
- [ ] Step 5: static leakage check script asserts rel_common/policies contain no
  banned tokens (`truth`, `bias`, `response_rate`, `second_bias`, `exit_day`,
  `variant`, `generate(`, `Simulator`, `rand_for`, `world[`, `seed`) outside
  comments — add as a test.

Task 2: the three policy wrappers
- Create: `policy_e1.py`, `policy_e2.py`, `policy_e3.py` (same dir): argparse
  accepting `--baseline` (ignored), stdin JSON -> decide -> stdout JSON,
  mode logic per section 1; each imports only rel_common + kit public contract.
- [ ] Step 1: tests: response shape passes `evaluate.validate_response` for
  both phases on a real `Simulator(generate(...))` state; E1 and E3 ask-phase
  output begins with exactly `baseline_asks(state)` (hard-first prefix);
  E2 ask-phase output equals `baseline_asks(state)` byte-for-byte; the E2/E3
  matcher on a fixture state differs from `baseline_match` ONLY through scores
  (same take-while algorithm — verified in Task 1 against kit); argv
  `--baseline greedy` accepted and ignored by all three wrappers.
- [ ] Step 2-4: run -> fail -> implement -> pass.
- [ ] Step 5: leak-token test covers the three wrappers.

Task 3: runner + instrumentation
- Create: `run_experiment.py`, `instrumented_sim.py`.
- [ ] Step 1: test: one tiny episode (seed 42, development, control) through
  `evaluate.episode(..., simulator_class=InstrumentedSim)` returns valid with
  recorded ask rows; metrics equal a plain evaluate.episode run.
- [ ] Step 2-4: fail -> implement -> pass.
- [ ] Step 5: smoke: 1 seed x 1 variant x 4 arms (24 episodes) -> all valid.

Task 4: pre-flight (no interpretation yet)
- [ ] Run full existing unittest suite (section 6) -> all pass.
- [ ] Capture `integrity_before/` (6 hashes + git status).
- [ ] Determinism smoke: 12 episodes x 2 runs -> identical action_sha256.
- [ ] Latency check: max inference_seconds/invocation < 10 (harness enforced)
  and mean <= 2x control.

Task 5: Stage-1 execution (288 episodes)
- [ ] `python research/e3_rel_experiment/run_experiment.py --stage 1`
  (seeds 119-130 x 6 variants x 4 arms) -> `per_arm/`, `run_log.txt`.
- [ ] Assert 0 invalid, guardrails green, else STOP and report invalidity.

Task 6: analysis
- [ ] Compute paired diffs (section 3 of experiment_plan.json): E1/C, E2/C,
  E3/C, E3/E1, E3/E2; seed-level t-CI, 72-unit W/T/L, per-variant table,
  mechanism metrics; write `report.md` + `summary.json`.
- [ ] Optional stage-2 (+seeds 131-142) ONLY per the pre-registered rule.

Task 7: finalize
- [ ] Deterministic rerun slice, container parity (control, and E-arms if
  Dockerfile.e3 feasible), `integrity_after/`, hashes manifest.
- [ ] Honest verdict against the final decision rule (keep greedy unless
  credible realized-MSMI improvement with all guardrails).
