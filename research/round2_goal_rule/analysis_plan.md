# Analysis Plan — Can a Simple Relationship-Goal Rule Exploit the Discovered Signal?

Study directory: `research/round2_goal_rule/`
Frozen BEFORE any new selector result is computed (SHA-256 recorded in
`analysis_plan.sha256` and in the run log). Corrections only via an appended
`## Amendment` section; the frozen body is never edited in place.

## 0. Scope and non-goals

A narrow, exploratory diagnostic experiment on EXISTING data. It tests one
hypothesis: a fixed, interpretable relationship-goal compatibility score may
exploit the stagewise-audited signal better than the baseline count score or
F2 when used as the weight of the exact-cardinality matcher.

It does NOT:

- implement any selector in `policy.py`, change the deployed policy, or make
  a submission decision;
- modify `policy.py`, `policy_ac.py`, `kit.py`, `evaluate.py`, `Dockerfile`,
  tests, or any previous research artifact;
- run git-mutating commands;
- generate fresh seed worlds or run any sequential rollout;
- retrain or tune F2, or fit any weight against counterfactual outcomes;
- start another tournament or recommend the next strategy.

All new files land under `research/round2_goal_rule/`. `grass.db` is
unrelated and ignored. This study measures counterfactual quality on
RECORDED states only; it is labelled exploratory throughout.

## 1. Evidence classes and independence

Claims are tagged: measured fact / statistical inference / source-code fact /
unresolved hypothesis. The independent unit is the SEED GROUP (21 seeds, all
six variants kept together). The 7,560 state rows and 15,304 edge rows are
NEVER treated as independent. Inference: paired seed-group bootstrap,
B=2000, rng seed 4242, percentile 95% interval (frozen convention from
round2_missed_oracle), plus positive/tied/negative seed-group counts.
Exact point totals are reported separately from inferential conclusions.

## 2. Inputs (all read-only, frozen)

- `round2_decision_ceiling/day_edges.jsonl` — 7,560 states, each with its
  feasible edges `(neg_score, key)` and the recorded GREEDY action set;
  `k_t = len(pairs)` preserved per state.
- `round2_decision_ceiling/counterfactual_pairs.jsonl` — 15,304 edges with
  frozen counterfactual labels (`cf_y_msmi`) and features; orientation keys
  sorted ascending.
- `round2_decision_ceiling/oof_scores.jsonl` — frozen OOF F2 (and F1/F4)
  predictions; no retraining.
- `round2_decision_ceiling/pair_state.jsonl` + `s3_signal.
  derived_features_from_row` — the EXACT frozen soft-channel state
  definitions (match/mismatch/unknown/declined); G2/G3 read channel states
  from here, never reimplemented.
- `round2_missed_oracle/selection_diagnostics.jsonl` — per-state `k_t`,
  `p_t`, `headroom` (82 headroom / 7,478 zero-headroom), `local_gap`.
- `round2_missed_oracle/recomputed_sets.jsonl` — validated per-arm exact-k
  sets for GREEDY / F1-SCORE / F2-SOFT / F5-ORACLE (reconciliation targets).
- `round2_fixed_cardinality/scripts/fc_matching.py` — `solve_exact_k`,
  `check_matching` (the validated solver; deterministic lex-smallest optimal
  size-k matching).

Validation gates (all must pass before results are believed):

- **V0** — seals of round2_decision_ceiling, round2_fixed_cardinality,
  round2_missed_oracle, round2_stagewise_signal still current (the recorded
  ceiling `run_log.txt` append is the only tolerated delta); this study's
  `analysis_plan.md` hash matches `analysis_plan.sha256`.
- **V1** — inputs align: 7,560 states; every edge of every state has a
  label and (where needed) an OOF score; edge keys sorted ascending;
  `k_t = len(recorded greedy pairs)`; recomputed GREEDY set equals the
  recorded action set; `sum k_t = 8,433`; `sum p_t = 173`.
- **V2** — frozen arm totals reproduce: GREEDY = 90, F1-SCORE = 81,
  F2-SOFT = 94, F5-ORACLE = 161; headroom states = 82, zero-headroom = 7,478.
- **V3** — G1 recomputed with `solve_exact_k(-neg_score)` reproduces the
  frozen F1-SCORE set on every state; G4 recomputed with
  `solve_exact_k(OOF F2 score)` reproduces frozen F2-SOFT on every state.
- **V4** — every selector output passes `check_matching`: EXACTLY `k_t`
  edges, all feasible, no member repeated.
- **V5** — labels and OOF predictions unchanged (byte-identical via V0
  seals); headline totals in the report reconcile with
  `per_state_results.csv` (re-derived at verify time).

If any reconciliation fails: STOP and document the discrepancy; prior
results are never silently changed.

## 3. Selectors (fixed scoring rules, exact-k constraint, same solver)

All score-based selectors solve `solve_exact_k(state_edges, weights, k_t)`
on the same candidate graph with the same exact cardinality; G0/G5 are
reused validated sets. Determinism: lex-smallest optimal size-k matching
(canonical edge order) — so a given weight vector always yields one fixed
set. Every selector is validated with `check_matching`.

- **G0 — Original greedy.** The exact recorded action set (control).
- **G1 — Baseline count score.** weight = `-neg_score` (count of matching
  observed soft fields). Must equal frozen F1-SCORE (V3).
- **G2 — Relationship-goal score.** weight = `+1` (both observed equal),
  `-0.5` (both observed unequal), `0` (either unknown or declined).
  Fixed diagnostic weights; NOT tuned against outcomes.
- **G3 — Goal + conversations, structure-informed.**
  weight = `0.7 * goal_score + 0.2 * conversations_score`, same category
  convention. The coefficients are the published NON-SHIFT simulator weights,
  labelled STRUCTURE-INFORMED (not learned). Applied uniformly to every
  variant; the hidden variant is never inspected or adapted to. No other
  soft field enters the score.
- **G4 — Existing F2-SOFT.** weight = frozen OOF F2_soft_state prediction;
  no retraining/tuning. Must equal frozen F2-SOFT (V3).
- **G5 — Existing F5 oracle.** Reused frozen exact-k oracle sets as an
  optimistic local reference ONLY; oracle labels are never used as features
  in any real selector (G5 is never a candidate for deployment).

Weights are computed once, before outcomes are consulted. No weight or rule
definition changes after any counterfactual result is seen.

## 4. Evaluation (identical `k_t` everywhere; zero volume component)

For each selector on all 7,560 recorded states:

- total counterfactual MSMI positives captured;
- difference vs G0 (greedy) and vs G1 (baseline), exact totals;
- positives per selected pair (positives / sum k_t = 8,433);
- number of states whose selected set differs from G0;
- number of states improved / tied / worsened vs G0 (per-state positive
  count);
- positive capture within the 82 headroom states;
- positive gains/losses within the 7,478 zero-headroom states;
- by scenario variant (6) and by seed group (21).

Because every arm chooses exactly `k_t` disjoint pairs per state, no
comparison can gain from selecting more pairs; volume effects are excluded
by construction.

## 5. Tie / discrimination analysis

Per state and per rule (G1..G4): number of feasible candidates, number of
DISTINCT scores, and number of candidates tied at the maximum score.
Aggregated: share of states where the rule cannot discriminate at all
(all candidates equal), share where the maximum itself is tied, how often
each rule changes the selected set vs G0, and whether set changes come from
discriminating states or from tie-only (arbitrary lex) states. This answers
whether the rule genuinely distinguishes alternatives or only produces
different arbitrary tie-breaks.

## 6. Relationship-goal signal examination

Using the existing counterfactual opportunities (15,304 edges): relationship-
goal match / mismatch / unknown / declined counts, MSMI positive counts and
rates, seed-group 95% CIs (pooled-rate seed bootstrap). Then:

- is G2's gain over G1/G0 concentrated in states where goal agreement is
  observable (at least one candidate with observed goal) versus states where
  every candidate's goal is unknown/declined (pure tie-break);
- concentration across headroom vs zero-headroom states and across seeds;
- what G3 adds beyond G2 (totals, paired seed CI, and where the deltas arise).

Three notions kept separate: (1) descriptive goal-agreement/MSMI
relationship; (2) selector counterfactual performance on recorded states;
(3) causal improvement of a sequential policy — NOT established here,
because different actions change future availability and decision states.
Unknown is never claimed better than mismatch (not established previously).

## 7. Statistical requirements

- 21 seed groups as sampling units; six variants stay together.
- Paired seed-group differences with bootstrap CIs and positive/tied/negative
  seed counts; exact point totals preserved alongside inference.
- No row-level independence assumptions; no post-hoc weight or rule changes.
- Results labelled EXPLORATORY: a favorable local counterfactual result does
  not establish a winning sequential policy.

## 8. Interpretation rules

- "G2 captures more than G1" only if the paired seed-group CI for
  G2-G1 excludes 0 (and exact totals are stated regardless).
- "G2 improves over greedy" only if G2-G0 CI excludes 0; otherwise the
  claim is limited to exact totals with an inconclusive CI.
- Gains confined to <= a few seed groups or to headroom states are reported
  as concentrated, not general.
- Tie-dominated set changes are reported as arbitrary tie-breaks, not signal
  exploitation.
- Nothing here recommends a policy or next strategy.

## 9. Deliverables

`analysis_plan.md` (+ `analysis_plan.sha256`), `report.md`,
`selector_summary.csv`, `per_state_results.csv`, `per_seed_results.csv`,
`per_variant_results.csv`, scripts under `scripts/` (`gr_common.py`,
`gr0_validate.py`, `gr1_selectors.py`, `gr2_evaluate.py`, `gr3_goal.py`,
`gr4_report.py`, `gr_seal.py`, `gr_verify.py`), `run_log.txt`,
`integrity.sha256`, plus supporting JSONs (`validation.json`,
`evaluation.json`, `goal_analysis.json`, `tie_analysis.json`).

## Amendment 1 (appended 2026-10-13; body above unchanged)

Original frozen SHA-256 of the body above, recorded at freeze time and in
`run_log.txt`: `f0121e1395054057d7cc1e515127db1844e2e09d6be1c231cc765e803b12375d`.

**Discrepancy found during V3 (measured facts + source-code facts).** The
plan body describes G1's weight as `-neg_score` "count of matching observed
soft fields". Empirically `day_edges.jsonl` stores POSITIVE counts
(`s1_opportunities.py:54` writes `[-e[0], ...]` over n01.allocate's
`neg_score <= 0`; verified against `feat.pair_score`), while the frozen
consumers `fc_selectors.py:123` and `mo_validate.py:172` apply `-e[0]`,
assuming the stale negated convention documented in
`plan_implementation.md:775`. Consequently the frozen **F1-SCORE arm
MAXIMIZES `-count`, i.e. MINIMIZES** the soft-match count: its total
match-count is 3,752 vs greedy's 7,245. This contradicts the body's
"maximizing" definition, so "G1 agrees with F1 where the definitions are
identical" fails by definition (sign), and the body's V3 wording is
corrected here rather than in place.

**Decision (recorded by the study owner): report both arms.**

- **G1f** = bit-exact reproduction of the frozen F1-SCORE selector
  (weight `-count`). Reconciles the frozen total G1f/F1 = **81**
  (analysis_plan.md sec.7 target). Labelled `frozen_F1_reproduction_
  minimizes_count`; it is NOT the maximizing baseline.
- **G1m** = spec-faithful baseline count score (weight `+count`,
  sec.3's "maximizing the total number of matching observed soft
  fields"). Deterministic total **88** positives; differs from frozen
  F1-SCORE on 1,232/7,560 states (expected, documented, not a failure).
- Questions Q1/Q2 anchor on **G1m** as "the baseline count score";
  both baselines appear in every comparison table.
- V3 now requires G1f == frozen F1-SCORE and G4 == frozen F2-SOFT on
  every state; G1m is expected to differ from frozen F1-SCORE and that
  difference is recorded as information.
- Frozen prior totals unchanged and re-reconciled: G0 = 90, F1 = 81,
  F2 = 94, F5 = 161. Only the F1-SCORE arm carries the sign defect;
  F2/F3/F5 weights (raw OOF scores, labels) are direction-correct.
- All other plan text (arms G2-G5, metrics, tie analysis, statistics,
  interpretation rules, deliverables) applies unchanged.
