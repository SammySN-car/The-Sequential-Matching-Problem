# Next Method Search — Proposed Directions (NOT executed)

**Status:** PROPOSED ONLY. No new episodes run, no methods implemented, no tournament
scheduled. Awaiting instruction. Written after the completed tournament's Phase-3
verdict: `Greedy remains the best empirically supported policy among the evaluated
candidates.` (credible: none; Bonferroni 99%, df=11, 72 paired worlds, 0 invalid).

**Research objective (unchanged):** increase *realized* MSMI/100 beyond greedy.
Greedy is the incumbent and control, not the goal. Leverage point is exactly one:
**which pairs get introduced** (and which members get their fields observed under the
ask budget) — conversion beyond introduction is simulated, not decided.

---

## 1. What the completed tournament ruled out

Funnel: 30 methods implemented → 4 eligible at screening (of 29 non-parity arms;
25 ineligible: 15 below mean −0.05, 10 catastrophic-variant-only) → 2 selected at
Confirm-1 → **0 credible at Confirm-2**.

| family | methods | outcome | evidence |
|---|---|---|---|
| A. reciprocal/pair scoring | m01–m08 | ruled out | 6/8 ineligible at screening; best survivor m03: +0.0417 (Confirm-1) → **−0.0069** [−0.0940, +0.0801] on fresh Confirm-2 seeds — a regression, not a signal |
| B. scarcity/opportunity scoring | m09–m15 | ruled out | 7/7 ineligible at screening (means −0.056…−0.139 or catastrophic variants); sole survivor m14 is an **identity no-op**: 0/126 worlds differing from control across all three phases |
| C. waiting/threshold gates | m16–m23 | ruled out | 7/8 ineligible; catastrophic specifically on cold_start/delayed/shift/drift (idling when arrivals are scarce); best survivor m19: +0.0278 → −0.0139, never selected |
| D. graph optimization | m24–m28 | ruled out | 4/5 ineligible; m26 changed **36/36** Confirm-1 worlds yet outcome deltas were exactly 0.000 everywhere — reshuffling equivalent pairs does not move MSMI |
| E. active asking | m29–m30 | ruled out | 2/2 ineligible (cold_start/sparse/drift catastrophic; ask cost 307.7/249.2 vs 201.7 control) |

**Three structural lessons (these drive the proposals below):**
1. **Point estimates at Confirm-1 are noise** — both positive leads (m03, m19) regressed
   on fresh seeds. Any future signal must clear the cluster CI gate on fresh seeds.
2. **Behavioral difference without outcome difference** (m14, m26) proves the metric only
   moves when *which pairs date* changes in a way that changes conversions — not from
   reordering, balancing, or optimizing the same effective pairs.
3. **Unconditional waiting dies on scarce markets** — every drop-a-pair rule failed
   exactly on cold_start/delayed. Any future “wait” must be conditional and guarded.

## 2. What remains untested (verified against the code, this branch)

All 30 decided fns are pure functions of *today's observed state*:

- **`memory` is plumbed but unused:** `evaluate.episode` carries a size-capped `memory`
  object across every invoke (evaluate.py L82–91, cap at L32); all 30 methods pass it
  through untouched (`memory = request.get('memory')` → returned as-is). Zero writes,
  zero reads for decisions.
- **History signals are exposed and unconsumed:** `kit.observe()` already returns
  `feedback` (introduction outcome events with `observed_day <= day`), `introductions`
  (full history), and `ask_log` (every ask + answer). No method references `feedback`
  or `ask_log`. The helper `common.past_pairs(state)` exists and is **never called**.
- **No cross-day value estimation** anywhere (no arrival-rate modeling, no
  match-now-vs-wait comparison; m30's VoI was within-day ask value only, and failed).
- **No decision-state diagnostics exist** — official rows carry aggregates only
  (no per-day decision records), so nobody has measured *where* greedy loses.
- **Observable headroom in existing data:** coverage ≈ 0.31–0.34 (≈ 2/3 of arrived
  members never served), ≈ 33% of decision days select nobody (control instrument:
  19.8/60 screening; 34/60 on the Confirm-2 sample seed), ask budget ≈ 190–200/720 used.
- **Latency headroom:** worst observed arm 51.2 s/episode ≈ 0.43 s/invoke vs the 10 s
  per-invoke gate — computation-heavy policies are affordable.

## 3. Prioritized proposals (short list; detail in methods.json)

| # | id | direction | what it is |
|---|---|---|---|
| P1 | `n01_decision_state_autopsy` | decision-state analysis | Instrument greedy on **dev-only seeds** to dump every decision day + later outcomes; find legal decision-time features that separate converting from non-converting introductions. Diagnostic, not a method. |
| P2 | `n02_feedback_reweighted_pairs` | feedback-driven | Keep greedy's structure; reweight pair scores by conversion history *already visible* in `feedback`/`introductions`; degrade to control when history is thin. |
| P3 | `n03_adaptive_ask_from_feedback` | stateful + feedback | Use `ask_log` + `feedback` history to choose *which SOFT fields* to ask next (the untested half of asking: m29/m30 were static rules); compact rolling stats optionally carried in `memory`. |
| P4 | `n04_guarded_lookahead_wait` | sequential lookahead | Match-now vs preserve-value estimate per pair, with a hard no-wait guard on thin markets (the lesson from family C). |

**Ordering rationale:** diagnostic before mechanism (P1 is cheap, kills or funds P2–P4);
P2 is the smallest legal change targeting the metric's actual leverage (conversion of
chosen pairs); P3 attacks the other lever (field observation) that family E only tried
as static rules; P4 has the highest modeling risk and is explicitly gated on P1 evidence.

Each proposal's **mechanism / expected benefit / implementation effort / failure mode /
exact evidence needed to justify testing** is specified in
`research/next_method_search/methods.json`.

## 4. Rules for whatever comes next (non-negotiable)

- Optimize realized MSMI/100; paired comparisons on identical worlds; cluster-by-seed CIs.
- Decision-time-visible state only (no hidden state, no future information).
- Never compare absolute scores across seed sets; never claim greedy is globally optimal.
- Production `policy.py` untouched; all existing results and failed attempts preserved;
  no commits.
- Any new episodes run on **dev seeds (90210 family)** until a design addendum
  preregisters a new phase; tournament seeds (143–163) stay consumed.
- **No automatic next tournament.** Evidence gates in methods.json come first.

## 5. Decision ask

Approve: (a) run P1 autopsy only, (b) implement a specific proposal (n02/n03/n04), or
(c) revise the list. Nothing executes without instruction.