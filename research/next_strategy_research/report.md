# Next-Strategy Research Report — Romeo & Juliet (Vouchsafe Sequential Matching)

**Scope:** research/audit only. No simulator episodes run for decision-making, no retraining, no threshold tuning, no commits, no modification of frozen files (`policy.py`, `policy_ac.py`, `kit.py`, `evaluate.py`, `organise.py`, `Dockerfile`). New analysis artifacts live only under `research/next_strategy_research/`.

## 0. Header — Current State and Where the Value Is

| Item | Value | Evidence label |
|---|---|---|
| **Current best policy** | `policy.py` greedy (count-of-equal-soft-fields score, always-take, full hard-ask saturation), official promotion seeds 107–118 | established by our experiments |
| **Current best MSMI/100** | **0.4931** (intros/100 38.10, mutual/100 5.417, ask ≈203 units/episode) | established by our experiments |
| **Biggest unresolved opportunity** | **Reveal-gated scoring gap:** fully revealing the 4 outcome-relevant soft fields (REL) and switching to the analytic scorer raises expected pair-value sum by **+18.7%** (0.784 → 0.931, W/T/L 67/1/4 over 72 worlds) with **no live test yet** | established by our experiments (offline, replica-validated); transfer to live MSMI untested |
| **Biggest waste** | **Idle ask budget:** greedy burns the 12/day hard-ask budget to exhaustion by day ≈19.4, leaving **517 free ask-units per episode unused (456 of them on days 22–59)**, while the REL reveal that would fund the opportunity above costs only **≈225.5 units/episode** — the budget that could fix the score sits empty | established by our experiments |

**The one-line thesis:** the score is nearly blind to true pair value (Spearman **0.12**), the budget that could un-blind it is sitting idle, and a static replica-validated audit says fixing both together is worth +18.7% of expected pair value. Everything else (allocation, history, hard-ask expansion) has been measured and is worth ≈0.

---

## 1. Method

Five parallel research agents (policy inspection, simulator mechanics, evidence ledger, matching literature, information-acquisition literature) plus two offline audits built in this session:

- **`static_analysis.py`** → `static_analysis.json` — world-level static audit over 72 worlds (seeds 107–118 × 6 variants). Reconstructs the post-saturation feasible-pair graph, evaluates score-allocation pairs, and measures expected pair value with a transparent proxy `v_oracle` (published outcome structure, true hidden params only for *measurement*, never for deployable scores). Validation: greedy replica reproduces `kit.baseline_match` on **72/72 worlds** (`replica_all_ok: true`); official greedy assignments ≤ static edge count in all 6 seed-107 variants; and a live cross-check on research world 50000/development shows **89 introduced pairs ⊆ 90 static edges, 0 outside, 0 declined-hard members introduced**.
- **`data_analysis.py`** → `data_analysis.json` — audit of the frozen 259,696-row training data (`research/out_scale800/rows.csv`), per-day diagnostics from promotion arms (8,640 day-records), and ask-budget headroom.

Honesty controls: deployable scores use **default kit weights always** (the policy state has no variant field — `observe()` exposes no variant — so variant-aware scoring is not deployable); `v_oracle` measurement keeps variant-correct weights; delayed/drift variants are indistinguishable to static analysis (no RNG branch in `kit.generate` for them) and results for them equal development's.

---

## 2. Evidence Ledger — Axes A–F

### Axis A — Soft-Field Value-of-Information (THE opportunity)

Measured on the static graph (72 worlds, expected pair-value sum vs current greedy = 0.784):

| Condition (all deployable semantics) | Δ sum v | W/T/L | Spearman vs v_oracle | Label |
|---|---|---|---|---|
| current count score (baseline) | — | — | **0.120** | established by our experiments |
| count score + REL fully revealed | +7.5% | 56/1/15 | 0.454 | established by our experiments |
| analytic score, no new asks | +5.2% | 51/0/21 | 0.354 | established by our experiments |
| **analytic score + REL fully revealed** | **+18.7%** | **67/1/4** | 0.666 | established by our experiments (offline) |
| count score + all 7 fields revealed | +4.3% | 51/1/20 | 0.417 | established by our experiments |
| reveal cost for REL | 225.5 units/ep (declined-unaskable ≈17.5) vs 517 free | — | — | established by our experiments |

Supporting facts:
- The analytic scorer reads **only the 4 outcome-relevant fields** {goal .7, pace .4, lifestyle .25, conversations .2} with missing→prior (it never uses the 3 outcome-irrelevant fields) — hence "REL-reveal + analytic" ≡ "all-truth + analytic" identically. Revealing the 3 irrelevant fields *dilutes* the count score (+4.3% < +7.5%): **ask only what the outcome uses**. [established by our experiments]
- Gains hold per-variant under default weights: combined +0.168 development/delayed/drift, **+0.119 shift**, +0.228 cold_start, +0.030 sparse. [established by our experiments]
- Ask headroom: free units 0 / 61 / 456 by phase (days 0–10 / 11–21 / 22–59), total 517/ep, greedy spends ≈203, exhausts hard-asks day 19.43. REL fits entirely inside headroom. [established by our experiments]
- Diagnostics: pool availability grows 140.7 → 170 by day 20 then flat (availability not binding); AC-style candidates/day stay at 3–9; AC-vs-greedy chosen-set Jaccard 0.649 (scorer choice materially changes pairs). [established by our experiments]
- Caveat: `v_oracle` is a proxy (shared-first-date=0, drift ignored, date-window ignored); offline-to-live transfer unproven — this is exactly what experiment E3 tests. [plausible but untested]
- Optimizer's-curse caution: single "best edge" statistics are noisy across scores (winner-value flat ≈0.046–0.053 while allocation sums differ) — trust allocation sums over winner anecdotes. [established by our experiments]

### Axis B — MSMI-Aligned Prediction Under Selective Labels

- Direct-MSMI HistGB: AUC **0.594, CI [0.567, 0.621]**, logloss worse than constant; mutual AUC 0.613; top features relational (`soft_relationship_goal_match`, `weighted_soft_score`); world-level 640/160 split. [established by our experiments]
- Counterfactual structure in frozen data: **98.7% of greedy's pairs also carry an independent random-collector label** in the same world; same (world, pair, day) labels are **deterministic 4251/4251** (RNG keyed by seed/pair/day); label agreement across collectors 23,437/23,810 (inflated by 99%-negative base rate). [established by our experiments]
- But assignment was never randomized → deterministic propensities → **no IPS/OPE is possible from these logs**; offline evaluation structurally favors the logging policy. [suggested by literature; consistent with our data audit]
- A supervised scorer trained on the union of both collectors' labels is a *selection-biased but wide* sample; pairs neither collector touched remain unlabeled — supervised transfer only, not causal evaluation. [plausible but untested]
- Direct conclusion: **do not retrain a direct-MSMI model as the scorer** — evidence says the learnable signal lives in relational soft fields, which the analytic score already encodes from published structure. [established by our experiments + suggested by literature]

### Axis C — Matching / Allocation (STOP)

- Max-weight matching vs greedy under current scores: **+0.0008** full pool (W/T/L 35/3/34), −0.0005 at realistic 60-node subsample. [established by our experiments]
- Under the *best* score (analytic+REL-reveal): greedy 0.931 > MWM 0.911 — MWM maximizes Σscore and trades away cardinality (n 27.6 → 22.8); total value *falls*. [established by our experiments]
- Literature: greedy ≥ 1/2 of MWM worst case, typically 85–95% of optimal; batching/global optimality needs *simultaneous* batches — our setting is batch=1 with a ~99-edge daily graph. [suggested by literature]
- Verdict: allocation optimization is worth ≈0 under every score tested. **Do not run.** [established by our experiments]

### Axis D — Sequential Wait / Hold

- Official greedy waits **zero**: always takes all feasible pairs and consumes ~90% of the static graph (89/90 edges in the seed-50000 cross-check). [established by our experiments]
- Pool grows only through day 20; after that no new arrivals — waiting has option value **only days 0–19** and costs intro-days + MSMI date-window risk (especially `delayed`). [established by our experiments (structure) + plausible but untested (value)]
- Literature: waiting/thick-market effects are the big sequential lever in dynamic matching (ride-hailing, two-sided markets), but the only *measured* lesson from our own history is that suppressing volume loses (A+C floor). [suggested by literature]
- Verdict: a reservation-score gate on days 0–19 is defensible but third-tier — only after the reveal/scorer experiments resolve. [plausible but untested]

### Axis E — Cold-Start / History (STOP)

- Stage-4 history: mutual ΔAUC +0.0113 (CI excludes 0), MSMI ΔAUC +0.0087 (**CI includes 0**), no variant-level cold-start penalty, candidate-level experience explicitly STOP. [established by our experiments]
- Cold-start is better attacked with **asks than history**: `cold_start` gains the most from reveals (+0.118 count-reveal, +0.228 combined). [established by our experiments (offline)]
- Member-level bias/response-rate estimation from feedback remains the only untapped history bit, but evidence is weak. [plausible but untested]

### Axis F — Literature

- Optimizer's curse / argmax-of-estimated-score (Smith & Winkler): relevant because we choose by estimated value over ~99 edges — argues for the analytic scorer's *shrunk-to-priors* estimates over raw counts. [suggested by literature]
- Value-of-information acquisition (Baarslag et al.): ask only fields that can flip the decision — matches "REL-only, VoI-gated". [suggested by literature]
- Selective labels (Lakkaraju, Kleinberg et al.): learn-on-observed-only bias; ES funnel calibration (ESCM/ESCM2): model the funnel stages rather than the end label. [suggested by literature]
- Robust/approximate matching bounds and ride-hailing dispatch practice (below). [suggested by literature]

---

## 3. Ranked Decision Tree (experiments 1–6)

All live experiments: **new policy file only** (never touch frozen sources), paired vs official greedy on **fresh seeds × all 6 variants**, primary metric MSMI/100 (baseline 0.4931), guardrails intros/100 ≥ 36 (baseline 38.10) and mutual/100 ≥ 5.2 (baseline 5.417), ask spend ≤ 12/day; report paired W/T/L (n=12 seeds detects ~0.2-scale effects at paired SD ≈0.24; smaller expected gains need W/T/L + more seeds). Stop an arm immediately on volume collapse or budget violation.

1. **E3 — Combined candidate: analytic scorer + VoI-gated REL soft asks.** The single arm that captures the full +18.7% offline. Ask rule: for each feasible candidate edge, request unobserved REL fields only if the analytic score could change the day's allocation (VoI gate), using idle hard-ask budget (fits in 517-unit headroom). *If it wins → ship. If it fails despite offline evidence → the static→live transfer assumption broke; go to 2 to find which mechanism failed.*
2. **E1 — REL-asks only (count score unchanged).** Isolates the information mechanism (+7.5% offline). *Diagnostic decomposition of 1; also the low-risk shippable subset.*
3. **E2 — Analytic scorer only (no new asks).** Isolates the scoring mechanism (+5.2% offline), zero ask-budget risk. *Cheapest arm; if it alone reproduces gains, ship it and treat asks as follow-up.*
4. **E4 — Wait/hold gate, days 0–19 only.** Reservation: skip same-day introduction when today's best score is below a fixed structural quantile, re-queue next day. Run only if 1–3 are neutral/negative with volume intact. [plausible but untested]
5. **E5 — Member-level response/bias estimation from feedback logs.** Estimate each member's `response_rate`/bias from their observed history to sharpen expected-value for revealed fields (axis-E remainder). Weak evidence; only if 1–3 leave value on the table.
6. **Do-not-run list (unsupported by measured evidence):** MWM/global allocation; hard-field ask expansion (G+ ≈ zero gain, saturation already complete); A+C floor/threshold tuning (finished); A+C matcher tweaks (measurably inert); direct-MSMI retrain as scorer (AUC≈0.59, logloss worse than constant); variant-aware weights (variant is not observable in state).

---

## 4. Concrete Recommendation

**Run experiment 1 (E3) next, as a new policy file that (a) scores feasible pairs with the analytic scorer on default kit weights (missing→prior) and (b) spends idle budget on VoI-gated REL soft asks before the day's introductions — paired against official greedy on fresh seeds across all 6 variants.** Rationale: it is the only change that addresses the measured root cause (score-blindness, Spearman 0.12) with a measured mechanism (+18.7% offline, W/T/L 67/1/4), it fits entirely inside idle budget (225.5 of 517 free units), and its two components (E1/E2) are pre-designed diagnostic fallbacks. Keep allocation, history, and threshold lines closed — they are measured dead ends.

---

## 5. Community Wisdom

Practitioner guidance retrieved from DEV (dev.to), per the session's community-wisdom practice:

1. **"Ride-Hailing Dispatch Algorithm: How Uber DISCO & Grab DispatchGym Match Drivers"** — https://dev.to/vesviet/system-design-ride-hailing-dispatch-algorithm-how-uber-disco-grab-dispatchgym-match-drivers-pp4
   A practitioner-level walkthrough of why one-by-one greedy dispatch loses to batched global matching — and why batching *requires* simultaneous requests. Directly relevant to axis C: our setting is batch=1 with ~99 daily edges, which is why our measured MWM-vs-greedy gap is ≈0 rather than the large gains ride-hailing sees.
2. **"Debiasing Graph Neural Networks for Recommendation with Causal RL"** — https://dev.to/tasfinmahmud/debiasing-graph-neural-networks-for-recommendation-with-causal-rl-2783
   Covers exactly the axis-B trap: models trained on exposure-biased logs score well only because "the test data shares the same exposure bias as the training data," and IPS reweighting needs exposure probabilities our deterministic logs don't have. Matches our audit conclusion: no OPE from these logs; evaluate candidates live, paired.

*(Provenance: found via web search — the DevRelay MCP gateway was not available in this session.)*

---

## 6. Artifacts

- `research/next_strategy_research/static_analysis.py` / `static_analysis.json` — replica-validated static score/allocation audit (72 worlds).
- `research/next_strategy_research/data_analysis.py` / `data_analysis.json` — frozen training-data counterfactual structure, per-day diagnostics, ask headroom.
- All numbers in this report are reproducible by re-running the two scripts; no frozen file was modified.
