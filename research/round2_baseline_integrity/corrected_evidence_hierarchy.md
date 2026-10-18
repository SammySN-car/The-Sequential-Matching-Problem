# Corrected Evidence Hierarchy — round2_baseline_integrity

Post hoc cross-study reconciliation of the F1-SCORE score-direction defect.
Computed under the frozen protocol in `analysis_plan.md`
(SHA-256 `e04280fc79e4427166608527329a0a475a4085058f4e428b7e3428c2f27da465`).
All numbers below trace to `corrected_*.csv` / `corrected_summary.json`
(recomputations C1–C7) or to cited source artifacts. Nothing prior was
altered; every corrected value is labelled **[POST HOC]**.

Statistical conventions preserved from the source studies: the seed group is
the independent unit (21 counterfactual seed groups, seeds 143–163),
B = 2000 bootstrap draws, per-study RNG conventions mirrored bit-for-bit
(C7). Intervals describe uncertainty of the *local fixed-cardinality
counterfactual* mean unless the row says otherwise. A local hindsight
selector (G5/F5) is a bound, not a deployable policy. Nothing here claims
greedy is optimal, that every learned policy is ineffective, or that a local
diagnostic implies full sequential improvement.

---

## Tier 1 — Supported (survives intact, no correction needed)

**T1.1  The missed-oracle decomposition (Claim C).**
60 ranking + 7 conflict = 67 = 161 − 94, with R_t = 101, P2 = 94,
P5 = 161, P1 = 81, P_G = 90 (C6). The identity closes exactly and the
components depend only on F2 and F5 sets — `mo_analyze.py` L166–167 has no
F1 term, source-asserted. 89.6% of the oracle gap is ranking, 10.4%
conflict. *Independent of the defect by construction.*

**T1.2  Oracle headroom at fixed cardinality (Claims B/C context).**
G5 − G0 = +71, CI [2.2381, 4.6190] (C2/gr); fc's own bootstrap reproduces [2.1905, 4.5714] (C7); 82 headroom states over
8,433 k_t-unit mass (C1); G5 captures 161 of 173 positives. The +71
interval excludes 0 in every pairing. Valid as an upper bound only —
label-aware, never deployable.

**T1.3  Every earlier keep-greedy verdict (Claim E), controls verified.**
- *round2 headline*: candidate vs greedy EXACTLY ZERO (0/72/0, CI [0,0]).
- *method tournament*: control `greedy_take` verified a true kit replica
  (`alloc.py` L22–25, sorts `-score` on positive counts — correct
  direction). m03 −0.0069 [−0.0940, +0.0801]; m14 +0.0000 [0,0].
- *e3 REL-ask*: C vs E1 +8.1% [−0.031, +0.093]; E2 +5.4% [−0.060, +0.101];
  E3 +0.9% [−0.084, +0.091]. Control verified `kit.baseline_match`
  (bi1 fact: correct sequential greedy, L210–222).
- *A+C studies* (round2, stage2, stage3, promotion): `policy.py` L415–596
  verified — descending sort keys, floor, sigmoid; no negated-weight
  solver anywhere. None of these arms touch the F1-SCORE selector.
None of these comparisons is contaminated; their verdicts stand.

**T1.4  Predictive (OOF) signal findings (Claim D, first half).**
Stage-wise model AUCs are direction-learned from labels — F1 here is a
*feature set*, not the selector arm (naming collision documented, not a
defect). out AUC 0.5218 (70 val positives); out_scale800 AUC 0.5937
CI [0.5667, 0.6208] (475 val positives; eda reproduced 0.5932); stage4
ΔAUC +0.0113 CI [+0.0063, +0.0161] on task 1 (task 2 includes 0);
stagewise B OOF AUC 0.5634, within-state 0.5881, refit bit-exact.
Kept strictly separate from selector performance, as published.

**T1.5  Promotion READY/PROMOTE on its stated basis.**
Primary C−B +0.0278 with CI spanning zero; volume 90.28% ≥ 80%;
mutual +5.46% not breached; G1–G5 PASS. The clearance is a
*no-degradation* clearance, not an MSMI superiority claim — and that
no-degradation basis is unaffected by the defect (A+C arms never used
the reversed score). See U.1 for the document-level conflict.

**T1.6  OPR analytic derivation.**
`round2_opr` contains no selector arms and no score negation; derivation
and numeric validation read kit.py mechanics only. Unaffected.

---

## Tier 2 — Qualified (conclusion survives; numbers or frame corrected)

**T2.1  "Count score ranks positives better than mid-pack; F2's global
advantage does not translate within-state" (Claim D, second half).**
Published (inverted frame): count percentile 0.388022, F2 0.454823,
F2-better share 0.323699. Recomputed under the true count direction
**[POST HOC]**: count percentile **0.343518** (median 0.25) vs F2 0.454823;
F2-better share **0.341040**; sign chain `baseline_raw == −count` verified
on all 173 rows (C5). *Qualitative claim survives with corrected values*:
the count still ranks positives below F2's mean percentile, and F2 still
outranks the count on only ~34% of positives. Only the quoted numbers
change.

**T2.2  F2 vs GREEDY at equal cardinality (Claim A3).**
+4, CI [−0.3333, +0.7619], seeds 7/9/5 — reproduced bit-for-bit (C7).
Unaffected by the defect (neither arm reversed): a valid like-for-like
local comparison. Qualified because the interval includes 0: no
seed-robust local advantage over the actual greedy selector, and it is a
local counterfactual, not a deployable-policy result.

**T2.3  Greedy is already near count-optimal at k_t (new, corrected).**
True count maximizer G1m = 88 vs greedy G0 = 90: G1m − G0 = −2,
CI [−0.4762, +0.2381] (includes 0), and the two selections differ on only
**80 of 7,560 states** (C2/C3). The corrected reading: greedy ≈ count
maximizer locally; the historical "G1f = 81" never measured count quality.

**T2.4  Near-miss structure of F2 misses.**
Missed positives sit just below the k_t cut (median missed rank 3;
34/67 with f2_rank ≤ k_t), from the correctly-directed F2 frame
(`positive_edge_ranks.csv`). Preserved as descriptive margin-ranking
evidence.

**T2.5  Stagewise qualitative ranking findings.**
The T5→T6 dip trace, C-dilutes-B at rare stages, and model-fit vs
evaluation gap (0.000020) are OOF-side facts — intact. Their *rank-percentile
quotes* are corrected under T2.1's numbers.

---

## Tier 3 — Withdraw or correct (invalidated as stated)

**T3.1  "Learned scoring beats count score, CI excludes 0" (Claim A1).**
The +13 [0.0476, 1.2381], 11/7/3 comparison (fc F2-vs-F1, mo F2−F1,
goal_rule G4-vs-G1f) is against a count **minimizer**: `day_edges` stores
`+count` (`s1_opportunities.py` L54) while `fc_selectors.py` L123 applies
`−e[0]`, feeding a maximizing solver (`fc_matching.py` L29–67). The arm
scoring 81 instead of 90 is the defect, not evidence. **Corrected:**
F2 94 vs count *maximizer* G1m 88 = **+6, CI [−0.2857, +0.9524]**,
seeds 7/8/6 — includes 0 (C2). The claim is withdrawn as stated and
corrected to *descriptive +6, not seed-robust over 21 groups*.

**T3.2  Headroom row "F1-SCORE beats greedy on headroom (+17, CI excludes 0)".**
Minimizer artifact on an 82-state subset. Corrected: maximizer G1m scores
**2 = greedy's 2** on the same states (delta 0); true headroom split
G2 10, G3 10, G4 14, G5 73, G0/G1m 2 (C4, cross-checked against mo).

**T3.3  "Baseline would have surfaced the missed ones" (captured 4.38 vs
missed 2.34 mean rank).**
Under the true count direction the ordering **reverses**: captured
positives mean rank **2.09** vs missed **2.90** (C5). The baseline ranks
*selected* positives higher, not missed ones. Withdrawn.

**T3.4  Goal-rule framing "+11 over G1f" as improvement over greedy.**
G1f is the defective arm. Replaced by: G2 − G0 = +2
[−0.2857, +0.5714], 3/13/5; G2 − G1m = +4 [−0.2381, +0.7143]; both
include 0 (C2). The goal rule shows descriptive point gains only — it
does not establish improvement over the actual greedy or the count
maximizer at fixed k_t. (G2 vs G1f's +11 was never a valid baseline.)

**T3.5  Claim A4 — "F2 improves the official realized sequential
objective".**
**UNVERIFIABLE FROM SAVED ARTIFACTS:** the bi0 scan found 20 files
referencing F2, **zero** of them policy/runner/evaluate files
(`f2_policy_like_files = []`). Every F2 number ever computed is a local
fixed-cardinality counterfactual; no full-sequential F2 policy run exists
to compare on realized MSMI/100. Not answered here; answering it would
require a new preregistered experiment (out of scope).

**T3.6  Ceiling zero-discrimination audit claim (CC-01).**
The audit argmax maximized a statistic constant within each headroom
state and, being cardinality-unconstrained, selected 323 pairs vs greedy's
307 — a volume artifact, already corrected inside fc §6 and classified
OTHER_IMPLEMENTATION_DEFECT here. Only the fixed-k oracle contrast (+71,
T1.2) is the valid statement.

---

## Tier 4 — Unresolved (flagged, not adjudicated)

**U.1  next_strategy L9 vs promotion §19.**
`next_strategy_research/report.md` L9–10 states "current best =
policy.py greedy … seeds 107–118 established by our experiments", while
`round2_promotion_fresh_seeds/report.md` issued **READY/PROMOTE** for the
floor/2 candidate on exactly those seeds (no-degradation basis). Both
documents are sealed as written. This audit records the conflict and does
**not** pick the favourable reading. (Possible reconciliation — one
describes MSMI superiority, the other a non-inferiority clearance — is
*not* asserted without the authors' statement.)

**U.2  `n_captured = 106` mislabel in mo artifacts.**
F2 actually selected 94 positives (P2 = 94; closure arithmetic uses 94 and
closes exactly). The 106 field is a mislabel recorded in the audit trail;
it does not propagate into the decomposition. Classification: documentation
defect, other-defect class, no number corrected.

**U.3  Stale `neg_score` docstring.**
`ce_common` L335 (and downstream comments) still documents scores as
negated while the writer `[-e[0], list(e[1])]` (L54) stores positive
counts. The doc is the single root cause of both defect sites
(`fc_selectors.py` L123 / `mo_validate.py` L172 negation, `mo_analyze.py`
L92 rank inversion). Repository code is *not* modified by this audit — the
stale doc remains for history; noting it here is the record.

**U.4  Tolerated seal staleness.**
`decision_ceiling`, `goal_rule`, `stagewise` run_log lines predate their
final seal state (tolerated by protocol); eda/opr manifests use
study-dir-relative path bases. All 7 prior seals verify otherwise; all
remain unmodified by this study (checked in `bi_verify`).

**U.5  `positive_edges` hardcode.**
The stagewise/mo rank path reads a hardcoded positive-edge count in one
script; verified consistent with the actual 173 rows in the saved CSVs
for this dataset (C5 row count). Recorded as a fragility, not a defect of
these results.

---

### Counting summary (42 matrix rows)

| Classification | Rows |
|---|---|
| CORRECT_AND_COMPARABLE | 29 |
| CORRECT_BUT_NOT_COMPARABLE | 4 |
| DIRECTION_BUG | 7 |
| OTHER_IMPLEMENTATION_DEFECT | 1 |
| UNVERIFIABLE_FROM_SAVED_ARTIFACTS | 1 |

Per-row evidence is in `study_audit.csv` (17 columns, citations per row).
