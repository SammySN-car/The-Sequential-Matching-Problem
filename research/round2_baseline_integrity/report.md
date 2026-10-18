# Baseline Integrity Audit — Final Report

**Study:** `research/round2_baseline_integrity`
**Protocol:** `analysis_plan.md`, frozen before any corrective computation,
SHA-256 `e04280fc79e4427166608527329a0a475a4085058f4e428b7e3428c2f27da465`
**Scope:** read-only cross-study reconciliation of the F1-SCORE
score-direction defect. No prior artifact was modified; no rollouts, seeds,
tournaments, or tuning were run; `grass.db` was ignored. All corrected
numbers are **[POST HOC]** recomputations (C1–C7) under preserved
per-study statistical conventions (seed group = independent unit,
B = 2000, per-study RNG mirrored bit-for-bit per C7).
**Evidence table:** `study_audit.csv` (42 comparisons × 17 columns).
**Hierarchy:** `corrected_evidence_hierarchy.md`.

---

## Q1 — What exactly was the bug, and where was it?

The baseline score is a **count of observed equal soft fields (0–7), higher
is better**. The pipeline that materialises per-state candidate edges stores
it **positive**: `s1_opportunities.py` L54 writes `[-e[0], list(e[1])]`,
un-negating the `(-score, key)` sort keys produced by `n01.autopsy.py`
L137–163 (that producer is correct — it wants descending sort). Downstream,
two consumers applied a negation justified only by a **stale `neg_score`
docstring** (root: `ce_common` L335):

1. **Primary defect — `fc_selectors.py` L123**: weights `= -e[0]` fed to a
   *maximizing* exact-k solver (`fc_matching.py` L29–67), so the arm named
   `F1-SCORE` **minimized** the count. Reproduced faithfully by
   `mo_validate.py` L172 for the missed-oracle study. Effect: 81 positives
   where greedy scores 90 and a true count maximizer scores 88.
2. **Second site — `mo_analyze.py` L92**: `competition_rank(-raw[i][0], …)`
   applied to stored *positive* counts inverted the baseline rank frame
   (rank 1 = lowest count), which propagated into `stagewise` rank quotes.

A repo-wide scan found **zero** `-e[0]` occurrences outside fc/mo/gr plus the
documented s1 writer. The defect is **directional, not arithmetic**: every
published figure reproduces bit-for-bit from the saved artifacts (C2: 14/14
pair CIs; C7: 5 main + 5 headroom + 1 contrast CI, all exact).

## Q2 — Which claims are invalidated or weakened?

| Claim | Status |
|---|---|
| **A1** "F2 beats count score" as +13 [0.0476, 1.2381] excluding 0 | **Withdrawn as stated.** The control was a count *minimizer*. Corrected: F2 94 vs count maximizer G1m 88 = **+6, CI [−0.2857, +0.9524]**, seeds 7/8/6 — includes 0 → not seed-robust (C2). |
| Headroom "F1 beats greedy +17, CI excludes 0" | **Withdrawn** — minimizer artifact; true maximizer G1m = greedy = 2 on those 82 states (C4). |
| "Baseline would have surfaced missed ones" (captured 4.38 > missed 2.34) | **Withdrawn** — ordering **reverses** under the true direction: captured 2.09 < missed 2.90 (C5). |
| Goal-rule "+11 over G1f" as gain over greedy | **Replaced**: G2−G0 = +2 [−0.2857, +0.5714] includes 0; vs true count maximizer +4 includes 0 (C2). Descriptive gains only. |
| Rank quotes 0.388 / 0.324 (stagewise & mo) | **Corrected** to 0.343518 / 0.341040 — conclusions survive (T2.1). |
| **A4** "F2 improves the realized sequential objective" | **Unverifiable** — 0 of 20 F2-referencing files are policy/runner/evaluate; no full-sequential F2 run exists. |
| Ceiling zero-discrimination audit (CC-01) | **Other implementation defect** — unconstrained-volume artifact, already corrected inside fc §6. |

## Q3 — Which claims are intact?

- **A3** F2 vs *real* GREEDY at equal k_t: +4 [−0.3333, +0.7619] — neither
  arm reversed, reproduced bit-for-bit; unchanged (still includes 0).
- **Claim B arithmetic**: all seven G-totals (90/81/88/92/92/94/161),
  sum k_t = 8,433, headroom 82, 0 cardinality violations (C1/C3).
- **Claim C**: the 60/7 decomposition — F2/F5-only inputs
  (`mo_analyze.py` L166–167), closure 60+7 = 161−94 exact (C6).
- **Claim D predictive half**: OOF/stage AUCs direction-learned, refit
  bit-exact; 0.5937 [0.5667, 0.6208]; stage4 +0.0113 [+0.0063, +0.0161].
- **Claim E**: every earlier keep-greedy study's control verified a genuine
  GREEDY — kit replica (e3, tournament `alloc.py` L22–25, bi1
  `kit.baseline_match` L210–222) or `policy.py` A+C (descending keys, no
  negation, L415–596). Verdicts preserved: round2 **exactly zero** vs
  greedy (0/72/0, CI [0,0]); tournament m03/m14 not credible; e3 E1/E2/E3
  all include 0; promotion **READY/PROMOTE on no-degradation grounds**
  (volume 90.28%, mutual +5.46%, G1–G5 PASS).

## Q4 — Does F2 beat a correctly directed count-maximizer?

**Descriptively yes, statistically not established.** F2 = 94 vs G1m = 88
at identical k_t over the same 7,560 states: **+6, CI [−0.2857, +0.9524]**,
seeds won/tied/lost 7/8/6 — the interval **includes 0** (C2). Under the
source studies' own conventions this is a point-estimate lead, not a
seed-robust advantage. All corrected contrasts (C2, gr bootstrap): G4−G0 +4 [−0.3333, +0.7143] seeds 7/9/5; G2−G0 +2 [−0.2857, +0.5714] seeds 3/13/5; G1m−G0 −2 [−0.4762, +0.2381] seeds 1/18/2; G1f−G0 −9 [−1.3345, +0.4286] seeds 5/7/9; G4−G1f +13 [0.0476, +1.2381] seeds 11/7/3; G5−G0 +71 [2.2381, 4.6190] seeds 17/4/0. The only non-oracle interval excluding 0 anywhere remains G4−G1f +13 — the defective-baseline comparison.

*Bootstrap-convention note:* the same deterministic comparison carries slightly different CI
endpoints in the two source studies because fc consumes one shared `random.Random(4242)`
stream across arms while gr draws a fresh `np.random.default_rng(4242)` per pair —
F2-vs-greedy is [−0.3333, +0.7619] (fc, C7) but [−0.3333, +0.7143] (gr, C2) above; F1-vs-greedy is
[−1.4286, +0.4286] vs [−1.3345, +0.4286]; F5-vs-greedy is [2.1905, 4.5714] vs [2.2381, 4.6190].
Seed-level win/tie/loss counts are identical across studies (F2 7/9/5, F1 5/7/9,
F5 17/4/0), and both conventions reproduce their own publications bit-for-bit
(C7 and C2); no conclusion depends on which one is used.)

## Q5 — Does any valid full-sequential comparison show a policy beating GREEDY?

**No — none does.** The full-sequential evidence is: round2 candidate vs
greedy **exactly zero** (0/72/0, CI [0,0]); promotion candidate +0.0278 with
CI spanning zero (cleared on no-degradation, not superiority); tournament
m03 −0.0069 [−0.0940, +0.0801] and m14 [0,0]; e3 +8.1%/+5.4%/+0.9% all
including 0. The one claim that would answer it (A4, F2 deployed
sequentially) has **no run to examine** (Q2). Local counterfactuals (Q4,
oracle +71) are not sequential evidence — a local hindsight selector is a
bound, not a deployable policy.

## Q6 — What evidence remains on signal, headroom, and power?

- **Signal:** predictive signal exists and is correctly directed — 0.5937
  AUC at 800 worlds (475 positives), stagewise within-state 0.5881,
  history features +0.0113. Within-state ranking: positives sit *below*
  F2's mean percentile under the true count direction (0.3435 vs 0.4548),
  and F2 outranks count on only 34.1% of positives — count remains the
  better *ranker of positives* even though F2 has the better *global AUC*.
- **Headroom:** 82 headroom states; fixed-k oracle +71
  [2.1905, 4.5714] fc / [2.2381, 4.6190] gr; decomposition attributes 89.6% of the F5−F2 gap to
  ranking and 10.4% to conflict; missed positives sit just below the cut
  (median rank 3). Headroom is real but concentrated at the margin.
- **Power:** with 21 seed groups every non-oracle interval except G4−G1f
  (defective baseline) and the G5 oracle includes 0. The design could
  detect the oracle bound but cannot resolve ±6-totals (~±0.3/seed)
  differences. G1m−G0 = −2 with 18/21 ties shows greedy ≈ count-optimal
  locally (differ on 80/7,560 states), so *count-based* gains are largely
  exhausted; remaining headroom is label-level, not count-level.

## Q7 — What inconsistencies remain unresolved?

1. **next_strategy vs promotion (flagged, not adjudicated):**
   `next_strategy_research/report.md` L9 "current best = policy.py greedy
   … seeds 107–118 established by our experiments" vs
   `round2_promotion_fresh_seeds/report.md` **READY/PROMOTE** on exactly
   those seeds. Both sealed; this audit does not pick a reading.
2. **`n_captured = 106` mislabel** (F2 selected 94; arithmetic uses 94 and
   closes) — documentation defect, recorded, no number changes.
3. **Stale `neg_score` doc** (`ce_common` L335) remains in the repo by
   non-modification policy — the root cause of both defect sites; recorded
   here as the corrective record (U.3).
4. **Tolerated seal staleness**: run_log lines in ceiling/goal_rule/
   stagewise; eda/opr study-dir-relative path bases. All 7 seals verify
   otherwise and were untouched.
5. **Hardcoded `positive_edges`** — consistent with the actual 173 rows
   for this dataset; fragility, not a defect of published results.

---

## Status of each historical conclusion (evidence-based)

| # | Historical conclusion | Status |
|---|---|---|
| 1 | F2 beats count score (+13, CI excl 0) | **CORRECTED** — +6 vs true maximizer, CI includes 0; not seed-robust (A1) |
| 2 | F2 ≥ greedy at fixed k_t (+4, CI incl 0) | **PRESERVED** — unaffected, local counterfactual only (A3) |
| 3 | F2 improves realized sequential MSMI | **UNRESOLVABLE** from saved artifacts (A4) |
| 4 | G0–G5 totals & oracle bound +71 | **PRESERVED** — exact reproduction, 0 cardinality violations (B) |
| 5 | Goal rule improves over greedy | **CORRECTED** — +2 vs G0, CI includes 0; descriptive only (B) |
| 6 | Missed-oracle 60/7 ranking-vs-conflict split | **PRESERVED** — defect-independent (C) |
| 7 | Baseline would have surfaced missed positives | **WITHDRAWN** — ordering reverses (C5) |
| 8 | Stagewise predictive AUC / stage structure | **PRESERVED** (D, predictive half) |
| 9 | "Count ranks positives better within-state" | **PRESERVED, numbers corrected** 0.388→0.344, 32.4%→34.1% (D) |
| 10 | Round2 A+C = greedy (exactly zero) | **PRESERVED** — control verified (E) |
| 11 | Tournament: no credible candidate, keep greedy | **PRESERVED** — control verified kit replica (E) |
| 12 | E3 REL-ask inconclusive, keep greedy | **PRESERVED** — control verified (E) |
| 13 | Promotion READY/PROMOTE | **PRESERVED on its no-degradation basis**; conflicts with next_strategy L9 — flagged (U.1) |
| 14 | Ceiling zero-discrimination audit claim | **OTHER DEFECT** — volume artifact, superseded by fixed-k +71 (CC-01) |
| 15 | OPR analytic derivation | **PRESERVED** — no selector arms (T1.6) |

Overall: the defect is real and localized (one stale docstring, two
consumer sites), it **removes the strongest learned-vs-count superiority
claim**, and it **reorders one descriptive rank story** — but it leaves the
decomposition, the oracle headroom, the predictive signal, and every
keep-greedy decision untouched, because those were never built on the
reversed arm. The verdict on the historical conclusions is therefore
mixed-by-claim, not all-or-nothing.

*No next-experiment recommendation, no `policy.py` change, and no submission
decision is made here — out of scope per the frozen plan.*
