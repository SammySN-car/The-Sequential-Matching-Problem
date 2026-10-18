# N01 - Decision-State Autopsy: greedy feature x conversion analysis

- Date: 2026-10-09
- Status: complete
- **Conclusion: B (no supported signal)**
- Deliverables: this file, `n01_feature_results.json`, and the executable evidence
  (`n01_autopsy.py`, `n01_analyze.py`, replay outputs).
- Authority: N01-only authorization. No policies built, no new seeds, no
  classifier/tournament, no frozen file touched, no commits. This report is the
  end of N01; nothing downstream was implemented.

## 1. Question and scope

The 30-method tournament ended with no credible candidate and verdict
"Greedy remains the best empirically supported policy among the evaluated
candidates." N01 was the single authorized diagnostic: reconstruct greedy
(control) trajectories on the existing tournament worlds, extract
decision-time-legal features at every introduction, label each introduction
with mature official outcomes, and test whether any feature separates
conversion strongly enough (the `methods.json` evidence gate) to justify a
follow-on search. Either a conclusion A (actionable signal + exact fresh-seed
test) or a conclusion B (no supported signal), then stop.

## 2. Method and fidelity proof

### 2.1 Replay

`n01_autopsy.py` replays greedy in-process on each sealed world:

- asks from `policy.py --baseline greedy` (i.e. `kit.baseline_asks`);
- matching by a day-0 assertion-checked copy of `kit.baseline_match`
  (permute-invariance + digest gate make this byte-equivalent);
- official episode protocol: 60 decision days (fresh `observe()` -> ask ->
  `resolve_asks` -> fresh `observe()` -> match -> `advance`), then 40
  action-less follow-up days, `metrics()` at day 100;
- digest recomputed exactly as `evaluate.py` does:
  `sha256(json.dumps([phase, day, action], sort_keys=True))`.

### 2.2 Fidelity gate (ran before any analysis)

| Check | Result |
|---|---|
| Worlds requested (all consumed control worlds, seeds 143-163) | 126 (screening 18 + confirm1 36 + confirm2 72) |
| `action_sha256` digest matches sealed official row | **126/126** |
| Per-world official aggregates match (assignments, mutual, dates, second, missing, ask_cost, coverage, waits) | **126/126** |
| Per-world label sums match official row fields | **126/126** |
| Pilot before full run | 2/2 |
| Censored (immature) introductions | **0** (max observed event day 92 < 100) |
| Replay speed | ~4 s/world (full run ~8.5 min) |

Analysis refused to run on unfaithful data: `n01_analyze.py` re-asserts
digest/label/immature counts and aborts otherwise. Exit code 0 on the full run.

## 3. Population and funnel

- Worlds 126, decision days 7,560 (126 x 60), intros **8,433**.
- Split (pre-registered): **discovery seeds 143-151** (54 worlds, 3,768
  intros) / **replication seeds 152-163** (72 worlds, 4,665 intros).
- Funnel over all intros: mutual **1,279** (15.17%) -> dates **965**
  (date|mutual 75.45%) -> second intention **91** -> official MSMI
  **90** (msmi|date 9.33%; MSMI/intro 1.067%).
- Missing feedback: **4,209 / 8,433 = 49.9%** (`no_response`).
- Maturity rule: every outcome event `observed_day <= final_day`; 0 censored.
- Day-level context: zero-selection days **3,566 / 7,560 = 47.2%**
  (sparse variant 77.5%, others ~40-42%); mean available members 157-176;
  mean feasible edges when any exist 1.7 (sparse) - 4.2 (other variants).

## 4. Features (33, all decision-time legal)

Booleans: `score_is_max, same_gender, zone_same, new_arrival_today, has_prior,
has_history`.

Numbers: `pair_score, pair_score_deficit, pair_rank, batch_size, edges_total,
edges_at_same_score, age_gap, soft_obs_min, soft_obs_max, soft_unequal,
soft_unknown_max, soft_declined_max, arrival_age_min, arrival_age_max,
degree_min, degree_max, degree_excl_min, degree_excl_max, prior_intro_max,
prior_mutual_total, prior_date_total, day, ask_budget_match, n_available,
n_intros_so_far, n_mutual_so_far, n_dates_so_far`.

`seed` and `variant` are strata keys only, never features. No variant/hidden/
future/outcome features. Labels: `y_msmi` (primary), `y_mutual`, `y_date`,
`y_second` (diagnostic-only).

## 5. Pre-registered rules (quoted from `n01_analyze.py` docstring, written before results)

1. Population: mature intros from fidelity-committed worlds (126/126).
2. Primary label `y_msmi`; diagnostics reported, never sufficient for A.
3. Features: decision-time-legal lists only; seed/variant = strata.
4. Split: booleans -> (False, True); numeric -> threshold = median of the
   **discovery** pool, low <= thr, high > thr; threshold transfers unchanged
   to replication/pooled. One split per feature; no alternative thresholds.
5. Pools: discovery 143-151 (9 seeds), replication 152-163 (12 seeds),
   pooled 21 seeds; uncertainty = seed-grouped t 95% CI on the per-seed rate
   difference, df = seeds with both halves non-empty - 1.
6. Gate (`methods.json` n01 evidence gate, never weakened):
   - **G1** discovery ratio >= 2x (rate ratio);
   - **G2** minority half >= 5% of intros on >= 3 of 6 variants (discovery);
   - **G3** ratio >= 2x on >= 3 of 6 variants (discovery);
   - **G4** >= 3 replication seeds individually >= 2x (zero-event low half
     with non-zero high counts as >= 2x, flagged) **AND** replication pooled
     ratio >= 2x.
   Both-halves-zero = not testable, never counts. Gate applies to `y_msmi` only.
7. Selection bias: labels exist only for chosen pairs; associations are
   conditional on greedy's choices. Absolute scores never compared across
   seed sets.

Conclusion A := >=1 feature passes the full gate on `y_msmi`.
Conclusion B := none passes.

**Integrity note (defect disclosure).** The first execution of
`n01_analyze.py` deviated from its own docstring in two places: it computed
`ev_high / ev_low` (event-count ratio) instead of the rate ratio, and it took
the numeric threshold from the pooled pool instead of the discovery pool. That
run produced a spurious "A" (`has_prior`, `has_history` - artifacts of tiny
day-0 halves). Both defects were corrected to match the pre-registered text
before any result was accepted. Only the corrected run's output
(`n01_feature_results.json`) is authoritative. The gate and rules above were
never altered after seeing results.

**Stricter-than-letter note.** G4's "replication pooled >= 2x" is an addition
beyond the literal `methods.json` wording ("replicates on >= 3 seeds"); it was
registered before results as the held-out check. It is stricter, never weaker,
and it matters for the closest candidate (section 6.2).

## 6. Results

### 6.1 Primary gate: 0 of 33 features pass; 0 diagnostic-only passes

Near-misses on `y_msmi` (discovery ratio >= 1.9, or zero-event split):

| feature | thr | disc | rep | pooled | G1 | G2 | G3 | G4 seeds | G4 rep-pooled | gate |
|---|---|---|---|---|---|---|---|---|---|---|
| `edges_total` | <=5 / >5 | **3.32** | 1.82 | 2.31 | Y | Y (6/6) | Y (5/6) | 7/12 Y | 1.82 **N** | **FAIL** |
| `edges_at_same_score` | <=2 / >2 | 2.40 | 1.36 | 1.70 | Y | Y | Y | 4/12 Y | 1.36 N | FAIL |
| `batch_size` | <=3 / >3 | 2.61 | 1.05 | 1.56 | Y | Y | Y | 2/12 N | 1.05 N | FAIL |
| `pair_rank` | <=1 / >1 | 2.47 | **0.35** | 0.99 | Y | Y | Y | **0/12 N** | 0.35 N | FAIL (sign flip) |
| `degree_max` / `degree_excl_max` | <=2 / >2 | 2.27 | 1.07 | 1.52 | Y | Y (5/6) | **N (2/6)** | 4/12 Y | 1.07 N | FAIL |
| `soft_unknown_max` | <=6 / >6 | 1.98 | 1.21 | 1.48 | **N** | Y | Y | 3/12 Y | 1.21 N | FAIL |
| `zone_same` | bool | low_zero | low_zero | low_zero | Y | **N (0/6)** | Y | 8/12 Y | Y | FAIL (coverage) |

Counts behind the ratios (discovery, primary label): `edges_total` 11/2,166
(0.51%) vs 27/1,602 (1.69%), abs diff +1.18 pp; `pair_rank` 19/2,681 vs
19/1,087 but reversed on replication (46/3,400 vs 6/1,265); all others in
`n01_feature_results.json` (full per-pool/per-variant/per-seed tables, counts,
abs diffs, seed-grouped t95 CIs).

`pair_rank` and `batch_size` are the clearest noise signatures: discovery
2.4-2.6x collapsing to <=1.05x on held-out seeds (pair_rank even reverses) -
exactly the regression-to-mean pattern the tournament demonstrated for m03.

### 6.2 `edges_total`: closest candidate, classified exploratory (not a supported signal)

Full numbers (primary label):

| pool | low (<=5 edges) | high (>5 edges) | ratio | abs diff | minority |
|---|---|---|---|---|---|
| discovery | 11/2,166 = 0.51% | 27/1,602 = 1.69% | **3.32** | +1.18 pp | 42.5% |
| replication | 23/2,754 = 0.84% | 29/1,911 = 1.52% | **1.82** | +0.68 pp | 41.0% |
| pooled | 34/4,920 = 0.69% | 56/3,513 = 1.59% | 2.31 | +0.90 pp | 41.7% |

- Gate: G1 Y, G2 Y (6/6 variants), G3 Y (5/6), G4 seeds 7/12 Y, **G4
  replication-pooled 1.82 < 2 -> FAIL.**
- Seed-grouped t95 CI on per-seed rate diff (21 seeds, df 20):
  [+0.000011, +0.018053] - excludes zero by a hair (lower bound ~1e-5).
- Per-seed ratio >= 2x on 11/21 seeds.
- **Funnel coherence (pooled, by the same split):** mutual 1.10x, date 1.14x,
  second 2.35x, MSMI 2.31x; date|mutual 0.743 vs 0.769; **second|date 0.064
  vs 0.132**. The split is flat where statistical power is greatest (1,279
  mutual events) and lives entirely in the second-intention stage (91 events).
- Sensitivity: under a literal reading of the three `methods.json` bullets on
  the pooled population (2.31x, minority 41.7% on 6/6 variants, 11/21 seeds),
  `edges_total` would satisfy them. It fails the pre-registered held-out
  condition, has no upstream funnel coherence, and its magnitude collapsed
  3.32 -> 1.82 on fresh seeds - the m03/m19 noise signature. Registered rule
  governs: **exploratory lead, explicitly not a gate pass, not a success.**

### 6.3 `zone_same`: large ratio, fails coverage by construction

54 / 8,433 intros (0.64%) are cross-zone; 0 reached MSMI (0 vs 90).
Zero-event splits count as >= 2x and the seed-grouped CI is [+0.0062,
+0.0162] (df 12), but the minority half is < 5% on **every** variant (worst
requirement: 0/6 pass G2, max variant share 0.83%). Not testable at the
registered coverage bar; n=54 cannot carry a gate.

### 6.4 Diagnostics: the dense labels are flat

- `y_mutual` (1,279 events): best discovery ratio **1.159** (`age_gap`);
  `degree_max`/`degree_excl_max` 1.158; `soft_unknown_max` 1.108. Zero passes.
- `y_date` (965 events): best non-coverage-failing ratio 1.178 (`age_gap`);
  `zone_same` 3.44 but coverage-fails as in 6.3. Zero passes.
- `y_second` (91 events): mirrors `y_msmi` because it is nearly the same
  endpoint (90/91); zero passes.
- **0 diagnostic-only gate passes** across all three labels.

A real market-state driver should appear upstream in the denser labels; it
does not. This is the main scientific support for B.

### 6.5 Day-level context

47.2% of decision days select nobody despite ~158 available members; sparse
variant 77.5%. Feasible-edge counts are small (1.7-4.2 mean when any exist).
This documents where losses sit but is not, by itself, success evidence for
any policy (per the standing acceptance/volume prohibition).

## 7. Caveats (mandatory)

1. **Selection bias.** Labels exist only for pairs greedy actually asked.
   Every feature x conversion association is conditional on greedy's choices;
   counterfactual pairs are unobserved. No table here says what a different
   policy would achieve.
2. **Missing outcomes.** 49.9% of intros end `no_response`; those count as
   non-mutual per official `kit.metrics` semantics (missing never treated as
   success or as a special failure class beyond official behavior).
3. **Multiplicity.** 33 features x 4 gate conditions x sparse endpoint
   (90 MSMI events). The gate has no multiplicity correction (as
   pre-registered); section 6.2's lead is precisely what multiple testing
   looks like - hence the held-out rule and the coherence check.
4. **Not a confirmation.** These worlds are the already-consumed tournament
   seeds (143-163). Nothing here is fresh-seed evidence, and no confirmation
   claim is made.

## 8. Deviation from `methods.json`

`methods.json` proposed dev-only seeds (90210 family). The authorizing
instruction superseded that with deterministic replay of the existing consumed
tournament worlds (seeds 143-163) and forbade new seeds. No new seed, world,
or confirmation was created. Recorded in `n01_feature_results.json` under
`meta.deviation_from_methods_json`.

## 9. Conclusion B

**No decision-time-legal feature separates greedy conversion at the
pre-registered evidence gate (0/33 primary, 0 diagnostic passes).**

Consequences (per `methods.json` n01 `failure_mode`, this was the intended
cheap kill):

- The feedback/stateful families (n02-n04) have **no supporting signal** and
  must not be built on this evidence.
- No fresh-seed test is proposed (that deliverable belongs to conclusion A).
- No policy was implemented. N01 ends here, as authorized.

The single exploratory lead, `edges_total`, is fully documented in 6.2 for
any future work that wants to pre-register a test from scratch; it is not a
result, not a success, and it does not reopen n02-n04.

## 10. Artifacts and re-verification

| File | Role |
|---|---|
| `n01_autopsy.py` | replay + feature/label extraction (resume-safe; exit 0 only if all digests match) |
| `n01_analyze.py` | pre-registered gated analysis (self-asserting; aborts on fidelity drift) |
| `n01_replay_rows.jsonl` | 126 fidelity rows (digests, aggregates, label sums) |
| `n01_days.jsonl` | 7,560 decision-day rows |
| `n01_introductions.jsonl` | 8,433 introduction rows (features + labels) |
| `n01_replay_summary.json` | run summary (126/126, 0 immature) |
| `n01_feature_results.json` | full results (33 features x 4 labels, gates, CIs, funnel, meta) |
| `n01_autopsy.md` | this report |

Re-verify: `python research\next_method_search\n01_analyze.py` (regenerates
the JSON deterministically, exit 0) and `git status --short` (must show
exactly: ` M policy.py`, `?? docs/superpowers/`, `?? policy_ac.py`,
`?? research/`, `?? test_policy.py`).