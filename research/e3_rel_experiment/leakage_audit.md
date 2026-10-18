# Leakage Audit — the "+18.7%" claim (STEP 1 + STEP 7)

Audit of `research/next_strategy_research/static_analysis.py` (382 lines, final version)
and its output `static_analysis.json`, performed BEFORE any experiment code is written.
Every line reference is to the file as it exists on disk now.

---

## 1. Reconstruction of every number

### 1.1 What "true pair value" (v_oracle) is

`pair_value()` — static_analysis.py:69-94, applied at 163-164:

    v = P(both first-stage yes) * 0.78 * P(both second-stage yes)

- fit: weighted +/- fit over the 4 outcome-relevant soft fields
  (equal -> +1, unequal -> -0.5, missing -> prior `w*(1.5*P_eq - 0.5)`),
  variant-correct weights W (W_SHIFT for shift) — measurement side knows the variant.
- first stage: `sigmoid(-0.25 + bias + fit)` per actor, times that actor's TRUE
  `response_rate` (static_analysis.py:93-94).
- second stage: `sigmoid(0.15 + second_bias + 0.4*goal_eq)` per actor times rr,
  times published DATE_HAPPEN = 0.78 (kit.py:171).
- inputs: `_soft_truth` (145) = kit truth fields (declined -> observed) and
  `_params_true` = `(m['bias'], m['response_rate'], m['second_bias'])` (147) —
  **hidden simulator state** (kit.py:64-65).
- disclosed integrations: shared N(0,.45) at mean 0, drift at 0, 30-day date
  window ignored, on-time (<=3 day) second-meeting window ignored — both windows
  are constant factors or day-level, rank-preserving within a snapshot.

Correspondence to the real DGP (kit.py `_prob` 133-140, advance 141-188, metrics
197): structure matches (same z-term shape, same weights, same 0.78, same second
stage). pair_value is an **analytic expectation of MSMI for one pair**, not a
realized outcome. No realized outcome, event, or label is used anywhere.

### 1.2 How Spearman 0.12 was calculated

- Per world: `spearmanr([s_greedy per edge], [v_oracle per edge])` over the static
  feasible edge set (static_analysis.py:232-234); NaN -> dropped.
- `s_greedy` = count of observed-equal SOFT fields on `_soft_obs`
  (157; formula at 46-49 = kit.baseline_match kit.py:217 exactly).
- Aggregate: mean of per-world rho over 72 worlds (agg 329-332) = 0.120.
- One world = one rho; edges within a world are the full census of feasible pairs
  (no sampling). Decision-time score vs oracle ruler (see classification).

### 1.3 How the analytic scorer was constructed

`s_analytic()` — static_analysis.py:52-66:

- weighted fit over the 4 REL fields using **hardcoded W_DEF** (line 28);
  all three call sites pass W_DEF (158, 160, 162) — deployable semantics,
  variant-invariant (variant is not observable in policy state).
- missing field -> prior expectation `w*(1.5*PRIOR_EQ[k] - 0.5)` with
  PRIOR_EQ from published `kit.OPTIONS` under a uniform prior (line 31).
  (Expectation of a sum = sum of expectations: no independence assumption needed
  for the prior mean.)
- plus a 0.02-weighted goal-equality term mirroring the second-meeting stage (66).
- Inputs: observed fields only. No params, no truth, no day, no seed.

### 1.4 What "full REL-field reveal" means

`_soft_rel` — static_analysis.py:138-141:

    soft_rel_only = dict(soft_obs)                      # start from observed
    for k in REL:                                       # the 4 outcome fields
        if field_status[k] != 'declined':
            soft_rel_only[k] = m['truth'][k]            # <-- HIDDEN TRUTH

So "full REL reveal" = **oracle substitution of `m['truth']`** for all 4 REL
fields of every matchable member with status != declined, at zero cost, at the
snapshot moment. Declined fields keep their observed (usually None) value —
mirroring the real unaskable-declined rule (kit.py:127).

### 1.5 How +18.7% was calculated, and what W/T/L 67/1/4 compares

- `value_of = {edge: v_oracle}` (176) — one ruler for both arms.
- For each score: `full['greedy_'+score] = alloc_value(greedy_alloc(sc[score]), value_of)`
  (194-195). `greedy_alloc` (98-106) is an exact replica of kit's take-while
  allocation (kit.py:220-221) — validated equal to `kit.baseline_match` on all
  72 worlds (181-190, `replica_all_ok: true`).
- Baseline = whole-pool static greedy allocation at the current count score;
  treatment = whole-pool static greedy allocation at analytic score over
  `_soft_rel` inputs.
- delta per world = treat sum - base sum (271-277); mean delta +0.1466 over 72
  worlds; divided by mean base 0.784 => **+18.7%**.
- W/T/L 67/1/4 = sign counts of that per-world delta with 1e-15 tolerance (277):
  worlds where the treatment allocation's summed v_oracle is higher / equal /
  lower than the baseline allocation's.

### 1.6 The 11 classification questions

| Question | Finding | Classification |
|---|---|---|
| Did full REL values come from hidden truth? | **YES** — `m['truth']` (line 141) | **oracle / upper bound only** — never deployable as-is |
| Is the calculation pair-static or state-dependent? | **pair-static**: one snapshot, post-hard-saturation, all members treated available, no days/busy/past/arrivals/budget/reveal-cost | **valid as static analysis; transfer gap to sequential live** |
| Candidate selection / exposure bias? | Edge set is the census of feasible pairs (no selection bias in the sample); but allocation is batch-whole-pool vs live daily-sequential | **valid within snapshot; sequential transfer untested** |
| Future information used? | None: no evaluate output, no events, no labels; hidden params appear only in the ruler, never in any score (scores read only `_soft_obs`/`_soft_rel`/`_soft_truth`) | **ruler = oracle; scores = clean** |
| Fields unavailable at that day? | Static assumes all REL revealed instantly; live reveals only after asks (budget 12/day, hard-first leaves slack only from ~day 11, declined 17.5/world unaskable, availability-gated) | **oracle timing in the reveal condition** |
| Uses outcomes that occur only after introduction? | No — no outcome data exists in this analysis at all | **clean** |
| Are hidden params in allocations? | Verified: `score_keys` inputs never touch `_params_true`; ruler used only for evaluation/corr/winners (176, 229, 237) | **clean** |

### 1.7 Classification of every part

| Part | Classification |
|---|---|
| `v_oracle` ruler (truth soft + true bias/rr/second_bias) | **valid but only as oracle/upper-bound measurement** (hidden DGP state; measurement only) |
| `s_greedy` (observed-equal count) | **valid and decision-time available** |
| `s_analytic` on `_soft_obs` | **valid and decision-time available** (published structure + uniform priors; variant-invariant) |
| `_soft_rel` / `s_analytic_revealed` / `s_oracle` (note: identical by construction — the analytic scorer reads only the 4 REL fields, lines 158-162) | **potentially leaked if read as deployable; valid ONLY as oracle upper bound of "free, instant, complete REL reveal"** |
| Static whole-pool greedy allocation machinery | **valid and decision-time available** (replica-validated 72/72) |
| **+18.7% (and +7.5%, +5.2%) aggregates** | **correct arithmetic; valid ONLY as static oracle-upper-bound expected-pair-value deltas. NOT a live MSMI forecast.** |
| Spearman 0.12 | **valid diagnostic** (decision-time score measured against oracle ruler) |

### 1.8 Arithmetic re-check and scale sensitivity

- 0.931 - 0.784 = 0.147; 0.147 / 0.784 = 18.75% — arithmetic confirmed against
  `static_analysis.json` (`mean_treat`, `mean_base`).
- **Scale sensitivity (same JSON, realistic 60-node subsample):**
  combined +0.047, count+reveal +0.016, analytic-only +0.014 — i.e. at realistic
  daily pool sizes the full-pool +0.147 shrinks to roughly one third.
  The honest reading: **the number's magnitude is pool-size dependent; its sign
  is stable** (full pool W/T/L 67/1/4; 60-node 102/23/15).

---

## 2. Verdict on the +18.7% claim

The number is **computed correctly but is an oracle upper bound**, not an
estimate of what a policy can achieve: it combines (a) free instant complete
REL reveal from hidden truth, (b) post-saturation batch allocation, (c) a proxy
ruler with hidden params. It must not be quoted as an expected live gain.

**This does NOT invalidate the experiment — it is the reason for it.**
Decision-time-clean components (analytic scorer, allocation replica, feasibility)
are exactly what E2 tests live; the oracle reveal component is exactly what E1
measures in realizable form (budgeted, sequential, availability-gated, declining);
E3 measures their interaction. The experiment is the instrument that converts an
oracle upper bound into a live, decision-relevant number. If live results are
neutral, the correct conclusion is that the upper bound was not realizable —
keep greedy.

## 3. STEP 7 — forbidden information for the new policies

State surface actually exposed (kit.py observe 101-109): `schema_version,
synthetic, day, ask_budget_remaining, members[{member_id, pool_id, synthetic,
age, gender, zone, arrived_day, fields, field_status, field_observed_day,
source, available}], introductions[{introduction_id, user_a, user_b,
assigned_day, response_deadline_day, logging_policy, propensity}],
feedback[events with observed_day <= day], ask_log`.

Banned inputs (static inspection will verify none appear):

- `truth`, `bias`, `response_rate`, `second_bias`, `exit_day` — never in state;
  `test_kit.py::test_no_latent_leak` pins this.
- `seed`, `variant` — not in state; introduction_id is a one-way hash of
  (a, b, day) only (kit.py:155), no seed leak; **weights stay hardcoded W_DEF
  precisely because variant is unobservable.**
- future arrivals (observe filters arrived_day > day, kit.py:104), future
  feedback (receive_feedback filters observed_day <= day, kit.py:111),
  raw `sim.events`, future `field_observed_day` values (mask pattern exists in
  policy.py:173-181; kit invariant makes raw `fields` already <= day).
- `kit.generate`, `kit.Simulator`, `kit.rollout`, `kit.rand_for`, research
  artifacts, any file I/O at runtime, any network.
- Indirect channels: memory must stay JSON <=1 MiB strict-JSON (evaluate 32-33);
  no `set` iteration in decision paths (fresh process per invocation, hash
  randomization on — sort everything, policy.py precedent); no NaN in output
  (evaluate 20-23, 610).
- Allowed by precedent (policy.py:5,11): `import kit` for `eligibility`,
  `baseline_asks`, `baseline_match`, and SOFT/HARD/OPTIONS constants only —
  which are the public DATA_CONTRACT, already used by the incumbent.

Known trap documented deliberately: `Simulator` instances in-process (if a
research runner constructs one) expose `.world['members'][i]['truth']` etc.
Policy code must never touch an attribute outside the `state`/`memory`
contract; the runner may, for scoring mechanism metrics only, and must be
separate from policy files.
