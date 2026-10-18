# Round 2 — Goal Rule: Can a Simple Relationship-Goal Rule Exploit the Discovered Signal?

Study: `research/round2_goal_rule/`. **Status: COMPLETE — exploratory local counterfactual diagnostic.** This study does not change the deployed policy, does not implement any selector in `policy.py`, and makes no submission or next-strategy recommendation. All inference uses the 21 seed groups (six variants kept together); the 7,560 state rows and 15,304 edge rows are never treated as independent.

- `analysis_plan.md` frozen, SHA-256 `221070644a317fc0...` (Amendment 1 appended before selector computation; original freeze hash preserved inside the amendment and in `run_log.txt`).
- Validation gate: **22/22 checks PASS** (`validation.json`); seals of the four prior studies current; reconciliation targets hit.

## 0. Headline

| Arm | Selector | Positives | vs G0 (greedy) | vs G1m (baseline) | Pos/pair | States changed vs G0 | Improved/Tied/Worsened vs G0 |
|---|---|---|---|---|---|---|---|
| G0 | `original_greedy` | **90** | 0 | 2 | 0.010672 | 0 | 0/0/0 |
| G1f | `frozen_F1_reproduction_minimizes_count` | **81** | -9 | -7 | 0.009605 | 1228 | 17/7518/25 |
| G1m | `baseline_count_score_maximizing` | **88** | -2 | 0 | 0.010435 | 80 | 2/7554/4 |
| G2 | `relationship_goal_score` | **92** | 2 | 4 | 0.01091 | 696 | 8/7546/6 |
| G3 | `goal_plus_conversations` | **92** | 2 | 4 | 0.01091 | 722 | 8/7546/6 |
| G4 | `F2_SOFT_oof` | **94** | 4 | 6 | 0.011147 | 1170 | 12/7540/8 |
| G5 | `F5_oracle_reference` | **161** | 71 | 73 | 0.019092 | 831 | 70/7490/0 |

Paired seed-group bootstrap (B=2000, rng 4242) on exact per-seed totals:

| Arm | delta vs G0 CI | p/t/n | delta vs G1m CI | p/t/n | delta vs G1f CI | p/t/n |
|---|---|---|---|---|---|---|
| G2 | -0.2857;0.5714 | 3/13/5 | -0.2381;0.7143 | 3/14/4 | -0.2381;1.3333 | 7/11/3 |
| G3 | -0.2857;0.5714 | 3/13/5 | -0.2381;0.7143 | 3/14/4 | -0.2381;1.3333 | 7/11/3 |
| G4 | -0.3333;0.7143 | 7/9/5 | -0.2857;0.9524 | 7/8/6 | 0.0476;1.2381 | 11/7/3 |
| G5 | 2.2381;4.6190 | 17/4/0 | 2.2857;4.8583 | 17/4/0 | 2.6190;5.0476 | 18/3/0 |

**Bottom line (measured facts).** Relationship-goal scoring (G2) captures 92 counterfactual MSMIs versus 88 for the true maximizing baseline (G1m, +4), 90 for original greedy (G0, +2) and 81 for the frozen F1 reproduction (G1f, +11). **None of these advantages are seed-robust**: every G2 confidence interval includes 0 (-0.2381;0.7143 vs G1m, -0.2857;0.5714 vs G0, -0.2381;1.3333 vs G1f). G3 (goal + conversations) captures exactly as many as G2 (92 = 92) — conversations adds selection churn with zero net capture. Gains are concentrated: all 8 states where G2 beats greedy are goal-observable, headroom states drawn from only 3 seed groups.

## 1. Amendment 1 — the G1 sign discrepancy (found during V3)

The plan body defines G1 as *maximizing* the total number of matching observed soft fields. V3 revealed the frozen F1-SCORE arm does the opposite:

- **Source-code facts:** `s1_opportunities.py:54` writes `[-e[0], ...]`, so `day_edges.jsonl` stores POSITIVE counts (verified against `feat.pair_score`: values 0..7), while the frozen consumers `fc_selectors.py:123` and `mo_validate.py:172` apply `-e[0]`, following the stale `neg_score` documentation (`plan_implementation.md:775`).
- **Measured fact:** total match-count sums over the selected edges: G1f (frozen reproduction) = **3752**, greedy G0 = **7245**, spec-faithful maximizer G1m = **7358**. A maximizing selector cannot score below the specific matching greedy produced; the frozen arm scores at roughly half. G1m and frozen F1-SCORE disagree on **1232/7,560** states.
- **Scope:** only the F1-SCORE arm is affected. F2/F3 weights are raw OOF scores and F5 uses labels (direction-correct, V3-pinned: G1f and G4 reproduce frozen sets bit-exactly on every state).
- **Decision (study owner): report both arms.** `G1f` reconciles the frozen total G1f/F1 = **81**; `G1m` is the spec-faithful baseline (total **88**) and anchors Q1/Q2. The frozen prior artifacts are untouched; this is a documented discrepancy, not a silent fix.

## 2. Method (short)

Same 7,560 recorded states, same candidate graphs, exact cardinality `k_t` per state (`sum k_t = 8433`), same validated deterministic solver (`solve_exact_k`: lexicographically smallest optimal size-k matching, `check_matching` on every output). Weights are fixed a priori and never tuned against counterfactual outcomes: G1f = `-count`, G1m = `+count`, G2 = `+1/-0.5/0` on relationship-goal match/mismatch/unknown-declined, G3 = `0.7*goal + 0.2*conversations` (published non-shift simulator weights, STRUCTURE-INFORMED, applied uniformly to all variants), G4 = frozen OOF F2 predictions, G5 = frozen oracle sets (reference only, never deployable). G0 is the recorded greedy action set (control). Because every arm selects exactly `k_t` disjoint pairs, no comparison contains a volume component.

## 3. Answers

### Q1 — Does relationship-goal scoring capture more counterfactual MSMIs than the baseline count score?

**Yes in exact totals, no in seed-robust inference.** G2 = 92 vs G1m = 88 (+4); vs G1f = 81 (+11). Paired seed-group CIs include 0 in both comparisons (vs G1m -0.2381;0.7143 with seed p/t/n 3/14/4; vs G1f -0.2381;1.3333 with 7/11/3). Positives per selected pair: G2 0.01091 vs G1m 0.010435. The G2 rule demonstrably re-ranks (it selects 1576 goal-match edges vs G1m's 1440, and 720 mismatches vs 1301), but goal-match edges carry a pooled positive rate of only 0.020568 on recorded opportunities, so the ranking gain converts to a small, non-robust capture difference.

### Q2 — Does it improve over original greedy, or merely recover what the weaker baseline lost?

**Merely recovers — and mostly the frozen baseline's self-inflicted loss.** G2 vs G0 = +2 exact (-0.2857;0.5714, seed p/t/n 3/13/5). The frozen F1f arm sits at -9 versus greedy (and is a count-minimizer per Amendment 1); G2's +11 over F1f is therefore mostly recovery of a broken baseline, netting only +2 over greedy. Note also that greedy itself is nearly the count-maximizing selector: G1m differs from G0 on only 80 states and totals 88 vs 90 (-2). The eight G2-over-greedy improvements sit in headroom states (10 vs greedy's 2 positives within the 82 headroom states) and are partly offset by a delta of -6 in zero-headroom states (82 vs 88).

### Q3 — Does adding conversations improve on relationship-goal alone?

**No.** G3 = G2 = 92 exactly (identical headroom and zero-headroom splits too). G3 and G2 select different sets in 128 states, but **every one of those 128 states has a counterfactual delta of exactly 0** (histogram {'0': 128}); all 128 have observable conversations candidates, so the added field genuinely changes selections — it just never changes capture. Per-seed G3-G2: {'negative': 0, 'positive': 0, 'tied': 21}, CI [0.0, 0.0]. The structure-informed conversations term buys churn, not capture.

### Q4 — Are gains concentrated in a small number of headroom states or seed groups?

**Yes, both.** All 8 states where G2 beats greedy are goal-observable AND headroom states, drawn from just 3 seed groups (148(3), 149(2), 157(3)); the 6 worsening states are all zero-headroom, spread over 6 seeds. States where no candidate's goal is observable are changed by G2 in 102 cases but produce a net delta of exactly 0 — pure tie-breaks. Against the spec baseline G1m, seed 148 alone supplies +3 of the net +4 (share 0.75 of the total). Headroom split (82 states): G2 10 vs greedy 2 vs G1m 2; the 7,478 zero-headroom states: G2 82 vs greedy 88 (delta -6).

### Q5 — Are score ties limiting the rule's ability to exploit the signal?

**Yes, severely.** G2 cannot discriminate at all in 81.0% of states (every candidate's goal in the same category); the maximum itself is tied in 28.8% of states; 110 of the 696 G2 set-changes happen in states where all candidates share one score (arbitrary lex tie-breaks, and they net to zero outcome effect in the unobservable split). Only 1662 of 7,560 states have ANY observable-goal candidate; across all states G2 shows a mean of 0.78 distinct scores per state. By contrast the continuous F2 (G4) has distinct scores on nearly every edge (mean 1.53, top-tied only 11.6%) yet still captures only 94 — discrimination is necessary but not sufficient; positives are rare among feasible edges (0.011304) and that base rate dominates precision.

### Q6 — What does the study establish, and what still requires full sequential evaluation?

**Established (measured facts, reconciled 22 checks):**

- Exact selector capture on the 7,560 recorded states at identical `k_t`: G0=90, G1f=81 (frozen, reconciled), G1m=88, G2=92, G3=92, G4=94, G5=161; headroom/zero-headroom splits; per-state improved/tied/worsened counts.
- The Amendment 1 sign discrepancy in the frozen F1-SCORE arm (source-code + measured evidence).
- Descriptive association: goal-match edges 0.020568 positive rate vs goal-mismatch 0.002582 (difference 1.8 pp, seed-group CI [0.009813, 0.027527], excludes 0). Unknown/declined rates are reported but **not** ranked against mismatch (not established).
- Tie/observability structure: 1662/7560 states observable; G2 no-discrimination share 81.0%.
- Statistical inference (exploratory): G2's advantages over G0, G1m and G1f all have seed-group CIs containing 0. The only non-oracle interval excluding 0 is G4 vs G1f (0.0476;1.2381) — contingent on the frozen (minimizing) baseline definition; G4 vs G1m (-0.2857;0.9524) includes 0.

**Not established — requires full sequential evaluation:**

- Any causal or sequential improvement: selectors here face fixed recorded states; different actions change future availability and decision states, so none of these totals transfers to the deployed policy outcome.
- That G2 (or G3, or G4) is a *winning* rule: every G2 comparison CI includes 0, gains cluster in 3 seed groups, and results are labelled exploratory by design.
- Whether unknown is better than mismatch (not claimed; previous audit did not establish it).
- Whether G2's headroom gains persist when earlier decisions alter which states ever occur.

## 4. By-variant and by-seed detail

Per-variant positives (identical `k_t` within every state):

| Variant | G0 | G1f | G1m | G2 | G3 | G4 | G5 |
|---|---|---|---|---|---|---|---|
| cold_start | 21 | 19 | 21 | 21 | 21 | 20 | 33 |
| delayed | 15 | 10 | 15 | 12 | 12 | 13 | 31 |
| development | 17 | 18 | 16 | 19 | 19 | 19 | 33 |
| drift | 17 | 18 | 16 | 19 | 19 | 19 | 31 |
| shift | 17 | 14 | 17 | 18 | 18 | 19 | 28 |
| sparse | 3 | 2 | 3 | 3 | 3 | 4 | 5 |

Full per-seed (21 rows, paired deltas and p/t/n) in `per_seed_results.csv`; per-variant deltas in `per_variant_results.csv`; state-level detail (52 columns) in `per_state_results.csv`.

## 5. Relationship-goal signal on recorded opportunities

| Goal state | Edges | MSMI positives | Pooled rate | Seed-group 95% CI |
|---|---|---|---|---|
| match | 2042 | 42 | 0.0206 | [0.0126, 0.0294] |
| mismatch | 2324 | 6 | 0.0026 | [0.0005, 0.0053] |
| unknown | 9986 | 104 | 0.0104 | [0.0078, 0.0130] |
| declined | 952 | 21 | 0.0221 | [0.0102, 0.0350] |

Match-minus-mismatch = 0.0180, CI [0.0098, 0.0275] (excludes 0). Descriptive on recorded edges only — the selector results above are counterfactual-but-local, and neither is a causal or sequential claim.

Goal-state composition of chosen edges (sums = 8433 per arm):

| Arm | match | mismatch | unknown | declined |
|---|---|---|---|---|
| G0 | 1424 | 1259 | 5234 | 516 |
| G1f | 709 | 1164 | 6005 | 555 |
| G1m | 1440 | 1301 | 5172 | 520 |
| G2 | 1576 | 720 | 5596 | 541 |
| G3 | 1576 | 720 | 5597 | 540 |
| G4 | 1312 | 813 | 5736 | 572 |
| G5 | 1057 | 1236 | 5604 | 536 |

G2 mechanically shifts composition toward goal match (G2 selects 1576 match edges vs greedy 1424); notably the oracle G5 selects fewer goal-match edges than greedy (1057 vs 1424) — goal agreement is descriptive signal, not the outcome mechanism.

## 6. Validation and reconciliation

- **22/22 checks PASS** (`validation.json`): seals of round2_decision_ceiling / fixed_cardinality / missed_oracle / stagewise_signal current; plan hash frozen; 7,560 states / 15,304 edges / `sum k_t` 8433 / `sum p_t` 173; every edge has label + OOF score; orientation sorted; recomputed GREEDY == recorded action on all states; frozen totals GREEDY=90 F1=81 F2=94 F5=161; 82/7,478 headroom split; V3 G1f==F1-SCORE and G4==F2-SOFT bit-exact on every state; V4 exact `k_t`, feasible, non-overlapping for all 7 arms on all states; V6 maximizer direction (7358 >= 7245 > 3752).
- **Reconciliation targets:** G0=90, G1f/F1=81, G4/F2=94, G5/F5=161 all exact (hard assert in `gr2_evaluate.py`); G1m=88 per Amendment 1; G2=G3=92; headline table equals `per_state_results.csv` sums (re-derived at verify time).
- Prior artifacts were never modified; the ceiling `run_log.txt` append is the only tolerated seal delta (as in prior studies).

## 7. Files

`analysis_plan.md` (+ `.sha256`, Amendment 1), `report.md`, `selector_summary.csv`, `per_state_results.csv`, `per_seed_results.csv`, `per_variant_results.csv`, `validation.json`, `evaluation.json`, `tie_analysis.json`, `goal_analysis.json`, `selector_sets.jsonl`, `channel_states.json`, `scripts/gr_*.py`, `run_log.txt`, `integrity.sha256`. Reproduce in order: `gr0_validate.py` → `gr1_selectors.py` → `gr2_evaluate.py` → `gr3_goal.py` → `gr4_report.py`, then `gr_seal.py` / `gr_verify.py`.

*Exploratory local counterfactual diagnostic — no policy change, no submission decision, no next-strategy recommendation.*
