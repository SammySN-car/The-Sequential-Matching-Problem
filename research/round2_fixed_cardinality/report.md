# Fixed-Cardinality Counterfactual Decision Audit

**Directory:** `research/round2_fixed_cardinality/`  
**Question:** when the number of introductions is held constant at greedy's
own daily cardinality \(k_t\), can legal observable information select pairs
with better counterfactual MSMI outcomes than the existing greedy policy?

**Scope.** This is a diagnostic study over already-recorded decision states.
The deployed policy is not modified, no rollout tournament was run, no new
world seed was generated, and nothing below is a policy, tournament,
submission or strategy recommendation.

## 0. Headline answer

Holding introduction volume exactly constant **removes the volume artifact but
not the underlying headroom.** Three findings, in order of confidence:

1. **The zero-discrimination result was a cardinality artifact and does not
   survive.** The audit statistic was flat within all 82 headroom states and
   broke ties toward the *largest* matching, so it selected 323 pairs where
   greedy selected 307. Replacing it with a correct fixed-cardinality control
   (F4-RANDOM at exactly \(k_t\)) yields 85.25 positives against greedy's 90
   overall - a slight *deficit*, not an advantage.
2. **Local headroom is real and survives the cardinality control.** F5-ORACLE
   at exactly \(k_t\) reaches 161 positives against greedy's 90
   (95% seed-group CI [2.1905, 4.5714], 17 positive / 0 negative seeds). The
   unconstrained one-day oracle reached 173, so holding cardinality costs only
   12 of the 83 possible gains.
3. **No legal observable selector converts that headroom into an established
   gain over the deployed policy.** F2-SOFT and F3-OBSERV at fixed \(k_t\)
   reach 94 and 85 positives against greedy's 90, and both seed-group
   intervals include zero.

## 1. Validity gates (all passed before any comparison)

| Gate | Result |
|---|---|
| Source-data validation (V-SRC-01..16) | 16/16 checks pass |
| Solver vs exhaustive enumeration, synthetic | 12310 checks, 0 disagreements |
| Solver vs exhaustive enumeration, real states \(n_edges\le16\) | 7489 states x 4 weightings, 0 disagreements |
| Solver constraint satisfaction | 0 failures |
| Solver determinism | 0 failures |
| Solver never worse than greedy's own set | better 1228 / equal 6332 / worse 0 |
| Exact-\(k_t\) feasibility | always feasible; greedy's own set is a witness (3566 states with \(k_t=0\), max \(k_t\)=14) |
| Every arm selected exactly \(k_t\) pairs | 0 solver or constraint failures across 7,560 states |

The analysis plan was frozen and hashed before any selector comparison was
computed (`sha256 0c1ba0e7...`). The only result produced before freezing was
the source-data validation, which inspects existing artifacts and computes no
new comparison.

## 2. Arms

Every arm selects **exactly** \(k_t\) pairs on the same recorded state, so
every difference below is a pure pair-selection effect with no volume
component.

| Arm | Construction | Information used |
|---|---|---|
| GREEDY | recorded original action set | reference |
| F1-SCORE | exact-\(k_t\) max of baseline soft-match count | score |
| F2-SOFT | exact-\(k_t\) max of OOF soft-state model | score + match/mismatch/unknown |
| F3-OBSERV | exact-\(k_t\) max of OOF full-observable model | score + all legal observables |
| F4-RANDOM | exact-\(k_t\) random matching, R=100, seed 4242 | none (control) |
| F5-ORACLE | exact-\(k_t\) max of counterfactual MSMI labels | hidden labels |

Every non-oracle score is **out of fold by seed group**, so no state is scored
by a model trained on its own seed. No threshold, hyperparameter or feature
set was tuned in this study.

## 3. Primary results (all 7,560 states, 8433 introductions)

| Arm | Positives | per intro | vs GREEDY | 95% seed-group CI | seeds +/0/- | states W/T/L |
|---|---|---|---|---|---|---|
| F1-SCORE | 81 | 0.0096 | -9 | -1.4286, 0.4286 | 5/7/9 | 17/7518/25 |
| F2-SOFT | 94 | 0.0111 | +4 | -0.3333, 0.7619 | 7/9/5 | 12/7540/8 |
| F3-OBSERV | 85 | 0.0101 | -5 | -0.9048, 0.4286 | 8/5/8 | 18/7518/24 |
| F4-RANDOM | 85.25 | 0.0101 | -4.75 | -0.8814, 0.32 | 12/1/8 | 68/7440/52 |
| F5-ORACLE | 161 | 0.0191 | +71 | 2.1905, 4.5714 | 17/4/0 | 70/7490/0 |

Intervals are a **statistical inference** over the 21 independent seed groups
(bootstrap B=2000, seed 4242). The 7560 day-level rows are *not* treated as
independent and are never used as a sample size.

**F5-ORACLE is not deployable and is not a sequential policy oracle.** It uses
hidden counterfactual labels and is only an optimistic local benchmark of
selection quality at fixed volume.

## 4. Restricting to the 82 states with local headroom

These are the states where the one-day hindsight oracle beat greedy
(local_gap >= 1). They are 1.08% of all states.

| Arm | Pairs | Positives | vs GREEDY | 95% seed-group CI | states W/T/L |
|---|---|---|---|---|---|
| F1-SCORE | 307 | 19 | +17 | 0.2857, 1.4762 | 17/65/0 |
| F2-SOFT | 307 | 14 | +12 | 0.1905, 1.0 | 12/70/0 |
| F3-OBSERV | 307 | 21 | +19 | 0.4762, 1.381 | 18/64/0 |
| F4-RANDOM | 307 | 24.61 | +22.61 | 0.7152, 1.4433 | 68/12/2 |
| F5-ORACLE | 307 | 73 | +71 | 2.2857, 4.5238 | 70/12/0 |

The remaining 7,478 non-headroom states are reported separately below.

## 5. The volume control

This is the arm that quantifies volume effects. It is **not** a quality gain
and is never counted as one.

| Arm | Pairs introduced | Positives | Same volume as greedy? |
|---|---|---|---|
| GREEDY | 307 | 2 | yes |
| F5-ORACLE at exact \(k_t\) | 307 | 73 | yes |
| F4-RANDOM at exact \(k_t\) | 307 | 24.61 | yes |
| Max-cardinality (volume arm) | 323 | 323 | **no - more pairs** |

## 6. CC-01 - does the zero-discrimination result survive?

**No. It dissolves.**

The audit's decision-relevance statistic maximised total `F5_state_only`
score over *all* matchings, then broke ties toward the largest matching.
Measured directly: `F5_state_only` is **flat within all 82 of the 82 headroom
states**, so the ranking term carries zero information and the tie-break rule
alone determined the outcome. Consequently:

| Quantity | Audit statistic | Greedy | F5-ORACLE at fixed \(k_t\) |
|---|---|---|---|
| Pairs introduced | 323 | 307 | 307 |
| MSMI positives | 16 | 2 | 73 |

The audit statistic introduced **16 more pairs** than greedy and therefore
mechanically accrued more positives. Its 16 positives are also far below
the 73 a true oracle reaches at the same 307 pairs, confirming it was never
ranking anything. The correct fixed-cardinality zero-discrimination control is
F4-RANDOM, which at exactly \(k_t\) reaches 85.25 positives against greedy's
90 overall - a deficit within uncertainty, not an advantage.

## 7. Interpretation against the preregistered cases

| Case | Status | Evidence |
|---|---|---|
| A - F2/F3 beat F1 AND greedy at equal cardinality | **partly** | F2 beats F1 (+13, CI excludes 0) but F2 vs greedy includes 0 (+4) |
| B - real selectors weak but F5 headroom substantial | **yes** | F5-ORACLE +71 at fixed \(k_t\) while all real arms sit within noise of greedy |
| C - little F5 headroom at fixed cardinality | **rejected** | +71, CI excludes 0 on 17/21 seeds |
| D - F4-RANDOM beats greedy frequently | **investigated** | overall -4.75 (CI includes 0); on the 82 headroom states it wins 68/82 at identical volume |
| E - too uncertain to distinguish | **for real selectors** | every real arm's seed-group interval includes zero |

Cases A, B, D and E coexist; the evidence is not forced into one explanation.

**On Case D specifically.** F4-RANDOM beating greedy on 68 of the 82 headroom
states at *identical* cardinality is not evidence that pair identity is
irrelevant. It reflects that greedy selected only 2 positives from 307
introductions on exactly those states, so nearly any alternative looks better.
Overall F4-RANDOM is slightly *worse* than greedy (-4.75). A random control is
never treated as proof of anything merely because it wins on a skewed subset.

## 8. Where the gains live

Concentration is extreme. **7,478 of 7,560 states have zero headroom**, and on
those every alternative selector loses ground to greedy:

| Subset | States | Pairs | GREEDY | F1 | F2 | F3 | F4-RANDOM | F5-ORACLE |
|---|---|---|---|---|---|---|---|---|
| headroom | 82 | 307 | 2 | 19 | 14 | 21 | 24.61 | 73 |
| non-headroom | 7478 | 8126 | 88 | 62 | 80 | 64 | 60.64 | 88 |

By variant and day band (F5-ORACLE minus GREEDY):

| Variant | Pairs | GREEDY | F5-ORACLE | Delta |
|---|---|---|---|---|
| cold_start | 1416 | 21 | 33 | +12 |
| delayed | 1621 | 15 | 31 | +16 |
| development | 1653 | 17 | 33 | +16 |
| drift | 1656 | 17 | 31 | +14 |
| shift | 1677 | 17 | 28 | +11 |
| sparse | 410 | 3 | 5 | +2 |

| Day band | Pairs | GREEDY | F5-ORACLE | Delta |
|---|---|---|---|---|
| 0-9 | 2516 | 29 | 45 | +16 |
| 10-19 | 2395 | 22 | 43 | +21 |
| 20-39 | 2520 | 32 | 55 | +23 |
| 40-59 | 1002 | 7 | 18 | +11 |

## 9. The six required answers

**1. Does explicit soft-state information improve the counterfactual MSMI
outcomes of pairs selected at a fixed introduction count?**

Against the *baseline count score*, yes: F2-SOFT reaches 94 vs F1-SCORE's 81
a gain of 13. [statistical inference] 95% seed-group CI [0.0476, 1.2381] excluding zero, with 11
positive / 7 tied / 3 negative seeds. Against the *deployed greedy
policy*, not established: +4 with CI [-0.3333, 0.7619], which includes zero.

**2. How much local headroom remains after controlling for cardinality?**

[measured fact] F5-ORACLE at exactly \(k_t\) reaches 161 positives against
greedy's 90, a gain of 71 on 8433 introductions. [statistical inference]
95% seed-group CI [2.1905, 4.5714], 17 positive / 4 tied / 0 negative seeds. The
unconstrained one-day oracle was 173, so the cardinality control removes only
12 of 83 possible gains. **The headroom is real, not a volume artifact.**

**3. Does the zero-discrimination result survive the cardinality control?**

**No.** [measured fact] `F5_state_only` is flat within all 82 headroom states,
so the audit statistic's advantage came from its largest-matching tie-break,
which selected 323 pairs against greedy's 307. The correct fixed-\(k_t\) control
(F4-RANDOM) is 85.25 against greedy's 90 overall [statistical inference], CI
[-0.8814, 0.32], including zero.

**4. Are apparent gains concentrated in specific worlds, variants or states?**

**Yes, extremely.** [measured fact] 7,478 of 7,560 states have zero headroom,
and every alternative selector loses ground on them. All gains sit on the 82
headroom states (1.08%). Per seed group, F2-vs-F1 deltas are positive in 11,
tied in 7 and negative in 3 of 21 seeds.

**5. Which conclusions are strongly supported, suggestive or unresolved?**

*Strongly supported (seed-group interval excludes zero):*

- F5-ORACLE beats greedy at fixed cardinality: +71, CI [2.1905, 4.5714], 17/4/0 seeds.
- F2-SOFT beats F1-SCORE at fixed cardinality: +13, CI [0.0476, 1.2381], 11/7/3 seeds.
- The audit's F5 55/82 result was a cardinality artifact (CC-01).

*Suggestive (direction present, interval includes zero):*

- F2-SOFT vs GREEDY: +4, CI [-0.3333, 0.7619].

*Unresolved:*

- F1-SCORE vs GREEDY: -9, CI [-1.4286, 0.4286].
- F3-OBSERV vs GREEDY: -5, CI [-0.9048, 0.4286].
- F4-RANDOM vs GREEDY: -4.75, CI [-0.8814, 0.32].
- Whether *any* legal observable selector can convert the 71 positive
  oracle headroom into an established gain over greedy. No arm demonstrates it.

**6. What limitations prevent translating this into a conclusion about full
sequential policy performance?**

- Only **21 independent seed groups**; the intervals reflect between-seed
  variation alone. Day-level n=7560 is not an independent sample.
- These are **local, one-day counterfactuals**. An alternative action changes
  availability and every subsequent state, so a local win is not a horizon win.
- The entire recorded feasible graph contains only **173 MSMI-positive pairs**
  out of 15,304 (1.13%), so the effective positive sample is very small.
- **1.08% of states** carry all the headroom; a handful of worlds drive it.
- F5-ORACLE uses hidden labels: **not deployable, not a sequential policy
  oracle, not a global ceiling.**
- A fixed-\(k_t\) design cannot detect gains that would come from choosing a
  *different* introduction count.

## 10. Honest scope statement

This report delivers evidence only. It does **not** select a next strategy,
modify the deployed policy, or recommend any submission or tournament change.
Every headline number above traces to `per_state_results.csv`,
`selector_summary.csv`, `statistics.json` or `cardinality_confound.json`.

