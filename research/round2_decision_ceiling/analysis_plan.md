# Analysis Plan — Decision Opportunity and Counterfactual Ceiling Audit

**Status:** FROZEN PREREGISTRATION. Written before any counterfactual outcome was
computed or inspected. Content may only be corrected for factual error, with the
correction and its reason appended to `run_log.txt` and referenced in `report.md`.
No metric, split, feature set, or interpretation rule may be added, removed, or
changed in response to observed results.

**Scope of this document.** This is a *diagnostic*. It does not train, select,
promote, or replace any policy. It does not run tournaments, fresh-seed rounds, or
OPR gating. It does not produce submission, strategy, or policy recommendations.
The human decides what follows from the evidence.

---

## 0. Purpose and the question being answered

Prior policy development produced candidates whose gains were not distinguishable
from noise, and the frozen OPR diagnostics were invalid. This audit asks one
question and refuses to answer any other:

> **Why did prior policy attempts fail to improve MSMI — is it because the decision
> space offered too few genuine choices, because available choices carried signal
> that was never extracted, or because choices rarely changed the MSMI outcome?**

Three separable sub-questions follow directly from the user's specification:

- **(A) Opportunity scarcity** — How many decision points contained a *genuine*
  choice, as opposed to zero-edge days or forced selections?
- **(B) Information headroom** — Can decision-time-legal observable features predict
  which feasible pair will yield MSMI better than a fixed-complexity baseline?
- **(C) Action headroom** — On a single day, with full hindsight of what every
  feasible pair would have done, how much better could a *one-day* chooser have
  done than the collector actually did?

These are reported **separately** (user spec §7). They are never combined into a
single score and never substituted for one another.

### Explicit non-goals

| Not doing | Why |
|---|---|
| Train or replace the deployed policy | Diagnostic only (§0, §8) |
| Fresh seed worlds / new tournaments | Read-only reuse of existing artifacts |
| Revisit OPR gates (D-C rho, G4) | Invalidated; frozen verdict is `OPR_NOT_VALIDATED` |
| Hidden sim attributes as features | `truth`, `bias`, `response_rate`, `second_bias`, `exit_day`, `seed`, `variant`, `future` are **excluded** (§5) |
| Sum daily oracle gains into an episode total | One-day oracle is not sequential (§6, §8) |
| Causal claims from association | §8 |

---

## 1. Protected inputs (read-only; hash before and after)

The following must be byte-identical before and after this audit. sha256 is
recorded in `run_log.txt` at start and end; any mismatch voids the run.

**Frozen code:** `kit.py`, `policy.py`, `policy_ac.py`, `evaluate.py`,
`Dockerfile`, all test files.

**Frozen research artifacts:** `research/round2_eda/` (240-line report,
evidence_inventory, run_log, 58-file integrity.sha256),
`research/round2_opr/`, `research/method_tournament/`,
`research/round2_promotion_fresh_seeds/`, `research/out*/`,
`research/next_method_search/` outputs.

**Read inputs (this audit):**

| File | Role | Expected |
|---|---|---|
| `research/round2_eda/report.md` | Frozen conclusions | read |
| `research/round2_eda/evidence_inventory.md` | Artifact map | read |
| `research/next_method_search/n01_introductions.jsonl` | Observed selected pairs | 8,433 rows |
| `research/next_method_search/n01_days.jsonl` | Per-day states | 7,560 rows; `sum(edges_total)` = 15,304 |
| `research/next_method_search/n01_replay_rows.jsonl` | Replay fidelity | 126 rows, all `all_match` |
| `research/next_method_search/n01_replay_summary.json` | Replay aggregates | 126/126 digest, 8,433 intros, 0 immature, final_day 100 |
| `research/labels.py` | Label definitions | `label_msmi` returns `None` when immature; never coerce to 0 |
| `kit.py`, `evaluate.py`, `n01_autopsy.py` | Simulator + replay harness | source of truth |

**Git constraint:** no git-mutating commands. Expected status remains the same
5 lines before and after.

---

## 2. G0 — Counterfactual replay validity (HARD GATE)

No counterfactual label may be computed or inspected until §2.1 passes. If any
test in §2.1 fails and cannot be resolved by fixing a *documented, orientation-
canonical* convention, the audit stops at `g0_replay_validation.md` with the
failure recorded, and no §4–§7 result is produced.

### 2.1 Source-code facts under test (from `kit.py`, verified by reading)

- `rand_for(*parts)` = `random.Random(int.from_bytes(sha256('|'.join(parts))[:16]))` (L24–25).
- `Simulator.advance` L152: `for a, b in sorted([sorted(p) for p in pairs])` — input
  pair orientation is normalized before use.
- L154: `r = rand_for(str(self.seed), a, b, str(self.day))` — the RNG stream for a
  pair on a day depends on `(seed, min(a,b), max(a,b), day)` only.
- L170–188: `mid = 'intro_' + sha256(f'{a}|{b}|{day}')[:24]`; date bonus and
  second-yes draws come from that same fresh `r`.
- Consequence (hypothesis, must be *empirically confirmed*, not assumed): a pair's
  outcome on a day is a pure function of `(world seed, lexicographically sorted
  pair, assignment day, member hidden attrs, world variant)`, with **no**
  cross-pair RNG interference, and `[a,b]` vs `[b,a]` are indistinguishable.

### 2.2 Validation tests

| # | Test | Method | Pass criterion |
|---|---|---|---|
| **T1** | Pair-orientation invariance | Run isolated `advance` on ≥50 sampled `(world, day, pair)` with `[[a,b]]` and `[[b,a]]` | Event streams byte-identical (same `mid`s, same flags); else stop — orientation-dependent randomness must not be exploited |
| **T2** | Batch independence | For ≥50 sampled days, run `advance([[p]])` for each feasible pair separately and compare to `advance([all pairs])` in one call | Per-pair events identical in both modes |
| **T3** | Isolated replay vs full rollout | For **all 8,433** n01 introductions: fresh `Simulator(world)`, set `sim.day = assigned_day`, transplant member `fields`/`field_status`/`field_observed_day` from the day-`d` snapshot, `advance([[a,b]])`, compare produced events + labels to the recorded originals | 100% exact match on event dicts and on every label; `mid` equal |
| **T4** | Label-sum reconciliation | Sum computed labels over the 8,433 | Equal `research/next_method_search` official aggregates (8,433 rows, 0 immature, label sums as in `n01_replay_summary.json`) |
| **T5** | Determinism | Re-run the full T3 procedure twice | Bit-identical output on both runs |

**Why transplant is required:** `advance` validates `eligibility(fields)` and
availability (`busy`, `events` pause/arrived/exit). A fresh simulator at `day = d`
does not know day-`d` field state; the transplant reproduces the decision-time
state without importing any hidden attribute into a feature (features are built
separately, §5).

**Replay horizon:** labels evaluated at protocol horizon 100 (`60` decision days +
`40` follow-up `advance([])`, `evaluate.py` L80–115). Max observed assignment day
across the corpus is 92, so `max_observed_day + 38 = 100` → every label is mature
under `research/labels.py` maturity rules. Right-censoring check: confirm zero
`None` labels in T4.

**Determinism of world regeneration:** worlds are regenerated with
`generate(seed, 200, 'evaluation', variant)` exactly as `n01_autopsy.replay_world`
does; `allocate()` is the line-for-line copy of `baseline_match`. The 126 existing
`all_match == true` rows are the standing evidence this regeneration is faithful.

**Stop rule:** T1 or T3 < 100% → halt, write `g0_replay_validation.md` with the
failure, do not proceed.

### 2.3 Deliverable

`g0_replay_validation.md` — test definitions, pass criteria, per-test results,
counts of matched/mismatched rows, orientation findings, maturity check, and an
explicit **GO / NO-GO** statement for §4.

---

## 3. §3 — How many genuine decision opportunities exist

**Source data.** The per-day candidate edge lists are **not** persisted anywhere;
only summaries are (`n01_days.jsonl`). Therefore the audit reconstructs them by
deterministic replay of the 126 existing worlds (same seeds, same variants, no new
worlds), applying `baseline_match` and recording, for every decision day `d ∈ [0,59]`
of every world:

- `available` (members with `n_available` that day),
- `edges_total` (feasible pairs after validation: availability, feasibility,
  eligibility, `past` exclusion, batch non-overlap — i.e. exactly the edges
  `allocate`/`baseline_match` may choose from),
- the selected set `M` (should reproduce `n01_days.n_pairs` and
  `n01_introductions` exactly — this is an additional integrity check).

**Reconciliation requirement (hard):** reconstructed total edges = 15,304;
reconstructed selected pairs = 8,433; reconstructed zero-selection days = 3,566
(47.17% of 7,560); days with `n_pairs ≥ 2` = 2,087. Any mismatch halts.

**Unit of analysis:** the *decision day* `(world_seed, variant, day)`, plus the
*selected introduction* for per-pair metrics.

**Strata (all reported):** world; scenario `variant` (`evaluation` variants 301–312
as recorded); day band **0–9, 10–19, 20–39, 40–59** (EDA convention; `40+` = 40–59
here since the protocol has 60 decision days).

### 3.1 Five concepts, kept strictly separate

Each is defined independently. No proxy is substituted for another.

**C1 — Many feasible edges.**
`edges_total` per day: mean, median, p90, max (source-observed max = 37),
histogram, share of days with `edges_total ∈ {0, 1, 2–4, 5–9, ≥10}`.

**C2 — Multiple feasible partners for one member.**
Degree distribution over *available* members: members with degree 0 (**isolated**),
≥1, ≥2. Report: `available` members/day, mean degree, share of available members
with ≥2 feasible partners, share isolated.

**C3 — Genuine conflict between edges (competition for members).**
For each selected pair `p ∈ M`: count of *unselected* edges sharing an endpoint
with `p` ("competing edges"). Report distribution and share of selected
introductions with ≥1 competing edge. Also: share of selected introductions whose
endpoint(s) had alternative feasible partners, i.e.
`deg(a) > 1 or deg(b) > 1`.

**C4 — Multiple valid matchings.**
Count distinct valid matchings of the day's edge graph, with a **cap at 50**
(enumeration aborts at 51 and records `>50`). Derived booleans:

- `matching_unique` — exactly one valid matching exists;
- `alt_repair_same_endpoints` — exists `M' ≠ M` with the *same* endpoint set
  (re-pairing the same members; changes `past`, therefore future candidate graphs);
- `alt_diff_endpoints` — exists `M'` with a different endpoint set (changes which
  members are marked busy, therefore future availability).

Sanity checks that must be ≈0 by construction:
- `addition_possible` (an edge disjoint from all of `M` exists) — greedy is
  maximal, so this must be exactly 0 on every day;
- for a matching of size 1, `M` cannot contain overlapping pairs (structural).

**C5 — Choice capable of changing the sequential episode.**
Report, by stratum:
- share of days with ≥2 disjoint edges (`n_pairs ≥ 2` → known to be 2,087/7,560);
- share of days where `matching_unique = False` (a different valid matching exists
  **at all** — distinct from ordering, and the answer to "could a different valid
  matching change the selected pair set?");
- share of days with `alt_repair_same_endpoints`, with `alt_diff_endpoints`;
- **frequency of cardinality-preserving replacement**: exists `e ∉ M` and `p ∈ M`
  such that `e ∩ (⋃(M \ {p})) = ∅` and `e ∩ p ≠ ∅` — a different pair could swap in
  while keeping the batch size;
- **tie at the maximum baseline score**: share of selected introductions with
  `score_is_max = 1` and with `edges_at_same_score > 1` (from
  `n01_introductions.pair_score` — note the frozen EDA report's claim that
  `pair_score` is "not persisted" is a known defect D5; it *is* persisted).

**Important caveat recorded in the plan:** C4/C5 measure *structural* choice
existence only. Whether a different matching would have *changed MSMI* is a
§6 question, not a §3 question. The two are never merged.

### 3.2 Output

`opportunity_summary.csv` — one row per `(stratum_type, stratum_value)` where
`stratum_type ∈ {overall, world, variant, day_band}`, columns = all C1–C5
metrics above, plus `n_days`, `n_edges_total`, `n_selected`.

---

## 4. §4 — Counterfactual target construction (diagnostic only)

**Definition.** For each of the 15,304 feasible `(pair, day)` opportunities in a
reconstructed decision state, replay the pair **alone** on that day in a fresh,
state-transplanted simulator and record what *would* have happened had that pair
been the one introduced that day: `cf_y_mutual`, `cf_y_date`, `cf_y_second`,
`cf_y_msmi`, `cf_mid`, `cf_assigned_day`.

**Feasibility filter.** Only pairs that `allocate` itself considered feasible are
kept: available on that day, eligibility-satisfying, not in `sim.past`, subject to
batch rules. Infeasible and previously-introduced pairs are excluded by
construction (they never appear as edges). The count must equal 15,304.

**Distinct opportunities.** `mid = sha256(a|b|day)` includes the day, so the same
pair appearing on two different days is two distinct opportunities and is counted
twice. This is intended and required. Duplicate `(pair, day, world)` keys are
checked to be zero.

**Validation checks (all must pass; recorded in `counterfactual_validation.csv`):**

| Check | Requirement |
|---|---|
| V1 Selected-pair agreement | For all 8,433 selected pairs, the pair-alone counterfactual labels equal the observed original labels **exactly**, under the documented sorted-orientation convention |
| V2 Independent replayability | T2/T3 batch-independence holds: pair-alone outcome equals pair-in-batch outcome (V1 is the selected-row instance of this) |
| V3 Maturity / right-censoring | Zero `None` labels; all horizon-100 mature |
| V4 Count integrity | 15,304 rows; 8,433 of them are `selected = 1`; per-world/per-variant sums match `n01_days`/`n01_introductions` |
| V5 Orientation | Outcome computed with `sorted(pair)`; T1 must have passed |
| V6 No leakage | Counterfactual labels are never used as features and never merged into any feature table (see §5) |

**Reporting constraint (mandatory wording).** The 6,871 unselected-pair
counterfactual outcomes are **counterfactual, unobserved by the original
collector, and never treated as observed outcomes**. Every table that contains
them carries the annotation `counterfactual_unobserved`. They are legal *targets*
for a predictive headroom study and illegal as *evidence of what the collector
knew*.

**Stratification.** Report potential opportunities and counterfactual MSMI positives
by world and by variant (user spec §4), plus by day band.

**Output columns (minimum):** `world_seed, variant, day, user_a, user_b, selected,
cf_mid, cf_assigned_day, cf_y_mutual, cf_y_date, cf_y_second, cf_y_msmi, flag`
where `flag ∈ {selected_agrees, selected_disagrees, counterfactual_unobserved}`.

---

## 5. §5 — Predictive signal across the full feasible action set

**Target.** `cf_y_msmi` on all 15,304 counterfactual rows (diagnostic-only).
Secondary targets reported but not used for primary conclusions: `cf_y_mutual`,
`cf_y_date`, `cf_y_second`.

**Feature legality (hard rule).** Every feature must be computable from
`Simulator.observe()` output at decision time — i.e. from the `state` dict
(`member_id, pool_id, synthetic, age, gender, zone, arrived_day, fields,
field_status, field_observed_day, source`) plus decision-local context. Unknown
fields are encoded as unknown, not imputed from truth.

**Permanently excluded from all feature sets:** `truth`, `bias`, `response_rate`,
`second_bias`, `exit_day`, `seed`, `variant`, any future day, any label-derived
quantity, `sim.past` counts that are not visible in the state (introductions and
feedback so far *are* visible and are included), and `cf_*` of any row.
Scenario `variant` is a **stratification/reporting variable only, never a feature**.

### 5.1 Frozen feature sets

| ID | Name | Contents |
|---|---|---|
| **F1** | Baseline count score | The collector's own `pair_score` components recoverable at decision time: available-degree terms and observable soft-feedback counts (`soft_obs_min/max`, `soft_unequal`, `soft_unknown_max`, `soft_declined_max`, `missing`) for the pair, plus `n_available`, `edges_total`, `n_intros_so_far`. Fixed, hand-written — **not fitted**. |
| **F2** | Explicit soft-state | F1 + explicit ternary status per observed feedback channel for this pair: `match` / `mismatch` / `unknown`, one-hot, per direction (A→B, B→A) and per channel (to_meet / smoking / children / schedule / availability) as available from `field_status`. |
| **F3** | F1 + F2 + public pair info | + legal profile attributes of both members: age, gender, zone, `arrived_day` (days since arrival), field completeness (`missing`), and **reciprocal-compatibility** indicators computed purely from public rules: `who_to_meet` accepts partner's gender, age within `age_min/age_max` ranges both ways, zones intersect, schedule intersects, `partner_smoking` vs `smoking`, `partner_children` vs `has_children`, `relationship_structure` equal, `wants_children` compatible. Any unknown input field yields `unknown`, not `False`. |
| **F4** | Full legal observables | F3 + all remaining decision-time-legal scalars: `feat_day`, `feat_days_since_arrival_mean/absdiff`, `feat_ask_budget`, `feat_comp_available`, `feat_comp_available_excl`, member ages/zones raw, day index, budget, arrival recency, pool-availability context — i.e. the same 44-feature `out_scale800/rows.csv` family **minus any non-legal column**, rebuilt from state rather than copied, so no frozen-bug column is inherited. |
| **F5** | State-only | Decision-state scalars only: `day`, `days_since_arrival` stats, `ask_budget`, `n_available`, `edges_total`, `n_intros_so_far`, `n_feedback_events`, `has_history`. **No pair identity or pair attributes.** Measures what state alone can predict. |

**Ablations required (spec §5):** F2−F1 (incremental soft mismatch-vs-unknown
contribution), F3−F1 (incremental public/compatibility contribution),
F4−F3 (remaining observables), F5 alone (state-only floor).

### 5.2 Frozen model and evaluation protocol

Fixed complexity, **no hyperparameter tuning, no feature selection, no early
stopping search**:

```
HistGradientBoostingClassifier(max_iter=200, learning_rate=0.06, random_state=40)
```
(mirrors the frozen EDA `s06_scoring.py` configuration for comparability;
`early_stopping` left at that call's default so the model class matches S06.)

**Split rule (spec):** whole-seed-group splits — `GroupKFold(n_splits=4)` with
`groups = world_seed` (all six variants of a seed stay on the same side).
Out-of-fold (OOF) predictions are produced for every row; **all reported metrics
are OOF only**. In-fold metrics are never reported as results.

**Uncertainty:** 95% percentile bootstrap CIs over the 21 seed-groups,
1,000 resamples, `numpy.random.default_rng(4242)`. Bootstrap unit is the
**seed-group**, never the row (rows within a world are dependent).

**Power statement (reported, mandatory):** total positives, positives per variant,
positives per feature-set row count; if any primary comparison has < 100 positives
or < 5 positive-bearing seed-groups, that comparison is flagged **underpowered**
and interpreted as such.

**Permutation null for heterogeneity (fixed):** labels permuted within world
(keeping class counts), `rng = default_rng(4242)`, 200 permutations.

### 5.3 Frozen metrics — questions A–E, reported separately

| Q | Question | Frozen metric |
|---|---|---|
| **A** | Global discrimination | OOF ROC-AUC, OOF PR-AUC (average precision), lift = AP / prevalence. Per feature set; per variant; overall. |
| **B** | Within-state discrimination | Per day-state `(seed, variant, day)` containing ≥2 candidates and both classes: per-state ROC-AUC (same as frozen `within_day_auc`). Summaries: unweighted mean over states; mean weighted by positive count; number of states; number of states with ≥1 positive. Also **top-1 hit rate**: among states with ≥1 positive, fraction where the model's highest-scored candidate is positive. |
| **C** | Incremental signal beyond the baseline | ΔAUC(F2−F1), ΔAUC(F3−F1), ΔAUC(F4−F3), each with seed-group bootstrap CI. Significance statement only if CI excludes 0; otherwise "not distinguishable from noise." |
| **D** | Collector selection | AUC on `selected = 1` rows only vs AUC on all rows, same feature set F4 (and F1). Report `E[score | selected] − E[score | not selected]` with seed-group CI. **Interpretation guard:** high value = collector's greedy already picks high-scoring pairs (selection effect), which can *suppress* measurable within-selected signal; this is reported as a selection effect, never as absence of information. |
| **E** | Decision relevance | Within the subset of day-states that have **positive local headroom** (§6) and ≥2 distinct valid matchings, does the model rank the positive edges above the non-positive edges it did not take? Metric: within-state AUC restricted to those states, plus fraction of those states where the model's argmax feasible matching would beat the collector's matching on that day (a *count* of states, not a summed MSMI gain). |

**Model weights are discarded after metric computation.** No model is saved as a
policy artifact, and no output of this section may be read as a policy proposal.

### 5.4 Output

`within_state_signal.csv` — one row per `(feature_set, stratum_type,
stratum_value)` with `n_rows, n_positives, prevalence, auc, pr_auc, lift,
within_state_auc_mean, within_state_auc_posweighted, n_states, n_states_pos,
top1_hit_rate, ci95_low, ci95_high, power_flag`.

---

## 6. §6 — Local hindsight-oracle headroom

**Definition (frozen — the only oracle in this audit).**

For a single decision day, with the reconstructed candidate edge graph `G` and
counterfactual labels `cf_y_msmi` on every edge:

- `P` = subgraph of `G` consisting of edges with `cf_y_msmi = 1`;
- **`local_oracle_positives` = maximum-cardinality matching in `P`** (i.e. the
  largest set of pairwise vertex-disjoint positive edges);
- **`collector_positives` = number of positive edges in `M`**, the matching the
  collector actually chose (`baseline_match` / `baseline-score matching`);
- **`maxcard_positives`** = positives in a maximum-cardinality matching of the
  *full* graph `G`, tie-broken by baseline score then lexicographically (a
  separate reference arm);
- **`local_gap = local_oracle_positives − collector_positives ≥ 0`** (must be ≥ 0;
  a negative value is an implementation bug and halts);
- **relative gap** = `local_gap / local_oracle_positives`, defined only when
  `local_oracle_positives ≥ 1`.

Enumeration is exact. With `edges_total ≤ 37` per day, branch-and-bound matching
enumeration is used; the positives subgraph is far smaller. Any day where exact
enumeration cannot complete is recorded as `enumeration_failed` and **excluded
with its count reported** — never approximated and called an oracle.

**Three arms are reported separately (never netted against each other):**

1. baseline-score matching (what the collector did);
2. maximum-cardinality matching (reference);
3. MSMI-informed local oracle (upper bound for *that day only*).

### 6.1 Constraints and non-claims (binding)

- This is a **myopic one-day hindsight oracle**. It is *never* called a
  "sequential policy oracle" or a "global ceiling."
- **Daily gaps are never summed.** Reporting a corpus-level number is limited to:
  the distribution of per-day gaps, the share of days with `local_gap ≥ 1`, and
  the share of *days* (not episodes) with positive headroom — each explicitly
  labelled "per-day, not per-episode."
- Interpretation:
  - **Small oracle gap** does *not* imply greedy is optimal; it implies only that
    on those days no better same-day assignment existed.
  - **Large oracle gap** does *not* imply hidden randomness is the sole cause; it
    is consistent with selection error, scoring error, or genuine stochasticity.
  - The oracle uses `cf_y_msmi`, which the policy could never observe at decision
    time — that is the point of measuring the ceiling, and is stated in every
    table.
- No heuristic maximum-matching result may be substituted and labelled "oracle."
- Nothing in this section is a policy, strategy, or tournament recommendation.

### 6.2 Strata

By world, by variant, and by **edge-density band `{1, 2–4, 5–9, ≥10}`**, plus day
bands. Also: share of days with `local_gap ≥ 1` conditional on
`local_oracle_positives ≥ 1`.

### 6.3 Output

`local_oracle_headroom.csv` — one row per `(stratum_type, stratum_value)` with
`n_days, n_days_oracle_pos_ge1, n_days_gap_ge1, share_gap_ge1_among_oracle_pos,
mean_local_gap, median_local_gap, p90_local_gap, mean_collector_positives,
mean_oracle_positives, mean_maxcard_positives, rel_gap_mean, n_enum_failed`.

---

## 7. §7 — Information headroom vs action headroom

**Method.** §5 and §6 results are placed side by side and tested against **six
candidate causes** of prior policy failure. The six are **not mutually exclusive**;
each is classified independently as *supported / suggestive / not supported /
unresolved* using only the evidence produced by this audit.

| # | Candidate cause | Evidence that would support it | Evidence source |
|---|---|---|---|
| **K1** | Too few genuine decision opportunities | Large share of zero-edge days; most days with a unique matching; most selected introductions have no competing edge | §3 (C1–C5) |
| **K2** | Available choices carry no usable information | F1..F4 within-state AUC ≈ 0.5 with tight CI; ΔAUC ablations include 0; top-1 hit rate ≈ prevalence | §5 (A, B, C) |
| **K3** | Information exists but sits in *unselected* choices (collector selection misfired) | Global AUC high while selected-only AUC collapses (or vice versa); `E[score|selected] − E[score|not]` large; within-state AUC on headroom states clearly > 0.5 | §5 (D, E) |
| **K4** | Choices rarely change the MSMI outcome | Large share of days with `local_gap = 0` despite `local_oracle_positives ≥ 1`; small per-day gap distribution | §6 |
| **K5** | Choices are structurally interchangeable but outcomes are stochastic | Many `alt_repair_same_endpoints` days yet `local_gap ≈ 0` (re-pairing changes nothing measurable) | §3 + §6 |
| **K6** | The score used by the collector is miscalibrated to MSMI | F1 (baseline count score) materially worse than F2/F3/F4 within-state, with CI excluding 0 | §5 (C) |

**Separation rule.** Information headroom (K2, K3, K6) and action headroom (K1,
K4, K5) are reported in different subsections of `report.md` §7. They are never
fused into one verdict, and neither is ever used to explain the other without an
explicit "consistent with" qualifier.

**Historical hypotheses H1–H9** (frozen EDA statuses) are *referenced* but **not
retested, not re-opened, and not re-statused**. Any apparent tension between this
audit and a frozen EDA conclusion is reported as an observation, with the EDA
artifact left untouched.

---

## 8. Interpretation safeguards (binding on `report.md`)

1. **Counterfactual ≠ observed.** Unselected-pair outcomes are counterfactual and
   are labelled `counterfactual_unobserved` everywhere they appear.
2. **One-day oracle ≠ sequential.** Never "oracle policy," never "ceiling of the
   episode," never summed across days.
3. **Prediction ≠ policy improvement.** AUC is not a policy gain. Section 5
   output is never converted into a recommendation.
4. **Independence units.** All CIs and significance statements resample or cluster
   at the seed-group level (21 groups). Row-level intervals are prohibited.
5. **No causality from association.** Correlations between features and
   `cf_y_msmi` are associations in a simulated corpus.
6. **Report all preregistered metrics**, including those that come out null or
   unfavourable. Nothing in §3–§7 may be silently dropped from the report.
7. **Do not revisit OPR gates.** The frozen `OPR_NOT_VALIDATED` verdict stands and
   is not re-computed here.
8. **Small oracle gap ≠ greedy optimal.**
9. **Large oracle gap ≠ hidden randomness is the sole cause.**
10. **No recommendations.** No policy, tournament, submission, or strategy
    suggestions appear anywhere in the deliverables.

**Evidence-class labels (required on every major conclusion in `report.md`):**

- `[measured fact]` — a count, ratio, or interval computed from the artifacts.
- `[statistical inference]` — a bootstrap/permutation statement with CI.
- `[source-code fact]` — verified by reading specific lines of `kit.py` etc.
- `[unresolved hypothesis]` — plausible but not established by this audit.

---

## 9. Deliverables

All under `research/round2_decision_ceiling/`. Nothing outside this directory is
written to (except `run_log.txt` append, which lives here too).

| File | Content |
|---|---|
| `analysis_plan.md` | This document — frozen preregistration |
| `g0_replay_validation.md` | §2 tests T1–T5, results, GO/NO-GO |
| `opportunity_summary.csv` | §3 C1–C5 by overall/world/variant/day-band |
| `counterfactual_validation.csv` | §4 V1–V6 checks + per-world/per-variant counts |
| `within_state_signal.csv` | §5 A–E metrics by feature set × stratum |
| `local_oracle_headroom.csv` | §6 headroom by stratum |
| `report.md` | §10 outline below |
| `scripts/` | Deterministic, seeded, re-runnable scripts |
| `run_log.txt` | Chronological execution log, commands, timings, hashes |
| `integrity.sha256` | sha256 of every file in this directory + protected inputs |

### `report.md` outline (fixed)

1. Executive findings (≤ 200 words, each finding evidence-classed)
2. Replay and target validity (G0 results)
3. How many genuine decision opportunities exist
4. Predictive signal across the full feasible action set
5. Explicit mismatch vs unknown signal (F2 − F1)
6. Local hindsight-oracle headroom
7. What the results establish / do not establish (K1–K6 table)
8. Remaining uncertainties
9. Ranked evidence on the causes of prior failures
10. Artifact index + integrity hashes

---

## 10. Execution order

1. Record sha256 of protected inputs → `run_log.txt`.
2. Write this file; **freeze** (no counterfactual outcome has been computed yet).
3. Run G0 (T1–T5) → `g0_replay_validation.md`. **Hard gate.**
4. Reconstruct per-day edge graphs; reconcile against 15,304 / 8,433 / 3,566 /
   2,087 → `opportunity_summary.csv` (§3).
5. Compute counterfactual targets; run V1–V6 → `counterfactual_validation.csv` (§4).
6. §5 feature sets F1–F5, frozen model, seed-group CV → `within_state_signal.csv`.
7. §6 exact local oracle → `local_oracle_headroom.csv`.
8. §7 headroom synthesis → K1–K6 classification.
9. Write `report.md`; regenerate protected-input sha256 and confirm unchanged;
   write `integrity.sha256`; append final log entries.

**Stop condition at any step:** an integrity hash mismatch, a G0 failure, or a
reconciliation mismatch in step 4 halts the run and is documented rather than
worked around.

---

## Amendment 1 (added before any result was computed or inspected)

**Filed under GC3** ("correct only by appending `## Amendment` + reason").
**Reason:** a falsifiable definitional defect, found by reading this document, not
by looking at data.

**Defect.** Section 3.1 defines `matching_unique` as "exactly one valid matching
exists", and section 3.1 C5 asks for "the share of days where
`matching_unique = False`", described as the answer to "could a different valid
matching change the selected pair set, rather than merely its ordering".

The empty set is always a valid matching. Therefore any day with at least one
feasible edge admits at least two matchings (the empty set and each singleton),
and `matching_unique` reduces *identically* to the indicator
`edges_total == 0`. The metric carries no information and the C5 bullet would
report a near-100% figure that answers nothing. The same degeneracy affects
`alt_diff_endpoints`: for any day with `|M| >= 1` the matching `M \ {p}` is a
valid matching with a different endpoint set, so that flag would also be
satisfied trivially.

This is a definitional error, not a result. Correcting it before execution does
not respond to any observed value.

**Replacement definitions (superseding the two superseded terms everywhere in
this audit).** `M` is the matching the collector actually chose; `|M|` its size;
`U` its endpoint set.

| Term | Definition | Answers |
|---|---|---|
| `alt_same_size` | `exists M' != M` with `|M'| = |M|` | Could a different valid matching of the *same batch size* change the selected pair set? |
| `alt_same_size_same_endpoints` | `exists M' != M`, `|M'| = |M|`, `endpoints(M') = U` | Pure re-pairing of the same served members (changes `past`, therefore future candidate graphs) |
| `alt_same_size_diff_endpoints` | `exists M' != M`, `|M'| = |M|`, `endpoints(M') != U` | A same-size batch serving a different set of members |
| `batch_underfill` | `max_matching_size(G) - |M|` | Did greedy leave batch slots unfilled relative to the best possible batch that day? |
| `addition_possible` | `exists e` disjoint from all of `M` | Must be exactly 0 (greedy is maximal); retained unchanged as a sanity check |

**Retained unchanged from section 3.1:** `n_matchings_capped` (cap 50, report
`>50`), `alt_repair_same_endpoints` (`exists M' != M` with `endpoints(M') = U`,
any size), `cardinality_preserving_replacement`, and all of C1, C2, C3 and the
tie-at-max-score metrics.

**Effect on report.md:** the C5 bullet is reported as `alt_same_size`,
`alt_same_size_same_endpoints`, `alt_same_size_diff_endpoints`, and
`batch_underfill`. The K1 and K5 evidence rows use these terms. No other
estimand, split, metric or interpretation rule changes.

**No result was computed, viewed, or known at the time of this amendment.**
