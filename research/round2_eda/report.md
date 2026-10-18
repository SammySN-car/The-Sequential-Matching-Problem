# Root-Cause EDA — why MSMI performance has not improved

**Scope:** exploratory diagnosis of the full experiment record (learned scoring,
A+C, clarification/REL, allocation, 30-method tournament, feature analysis,
OPR). Deliverables: this report, `evidence_inventory.md`, `tables/`, `plots/`,
`run_log.txt`, `integrity.sha256`. All analysis code lives in
`research/round2_eda/` only. No policy was trained for deployment, no
tournament or OPR experiment was run, no frozen file was modified, and no
causal claim is made beyond what paired designs and generator source facts
support. This report deliberately does NOT choose a next experiment or
recommend a policy.

## 0. Question and method

Question: across every experiment run so far, no policy change has produced a
credible improvement in the primary metric (MSMI per 100 arrived members).
Where does the system actually lose successes, and which candidate explanations
for the repeated null results are supported by existing artifacts?

Method: (i) reconcile the conflicting study conclusions from design and sample
size; (ii) decompose the outcome funnel on actual labels with world-level
uncertainty; (iii) measure scoring concordance at the right conditional level
(within-day, within-world); (iv) separate allocation volume from conversion
with paired decompositions; (v) extract the generator's outcome equations as
diagnostic-only source facts; (vi) rank hypotheses with explicit evidence tags.
Worlds/seeds are the unit of uncertainty throughout; row-level CIs are not used
for policy comparisons.

## 1. Reconciling the apparently conflicting studies

Four results looked contradictory before this EDA:

| study | design | MSMI signal |
|---|---|---|
| out (E1) | 100 worlds, 44 feats, global AUC | 0.5218 (70 val positives) |
| out_scale800 (E2) | 800 worlds, same pipeline | 0.5937 [0.5667,0.6208] (475 val positives) |
| N01 autopsy (E3) | 126 greedy worlds, 33 state feats, gated median-split | no supported feature (90 positives) |
| tournament (E4) | 30 methods, paired episodes | 0 credible (best confirm2 -0.0069) |

They are not mutually exclusive. E1 vs E2 differ mainly in positives (70 vs
475) and worlds (100 vs 800): at n=70 the AUC estimate is noise-dominated, at
n=475 a modest-but-real global ranking signal (0.59, CI excludes 0.5) appears.
E3 asked a different, harder question — does any single decision-state feature
pass a gated split on 90 events — and the answer was no; that is fully
compatible with a distributed weak signal across 44 features at 5x the
positives. E4 methods changed scoring/tie-break logic while holding volume
fixed (2,402 assignments for every confirm1 arm; S07) and conversion moved
only from 1.12% to 1.25% (m03) — sub-world-noise on 36 paired worlds. The
record is coherent: **a small global ranking signal exists, it is too weak and
too heterogeneous to move episode-level MSMI at the sample sizes tested.**

New reproduction (S06): refitting the exact pipeline on the frozen
rows.csv gives global AUC 0.5932 (frozen: 0.5937) — the pipeline is
reproducible; nothing was lost in interpretation.

## 2. Where introductions actually die (S05, actual labels)

n01 greedy funnel (8,433 intros, 126 worlds, wilson 95%):

| stage | n | conditional rate | 95% CI |
|---|---|---|---|
| assigned | 8,433 | — | — |
| both responded | 4,743 | 56.2% of assigned | [55.2, 57.3] |
| both accepted (mutual) | 1,279 | 27.0% of responded | [25.7, 28.2] |
| date happened | 965 | 75.5% of mutual | [73.0, 77.7] |
| both second-yes within 3d | 91 | **9.4% of dates** | [7.7, 11.4] |
| MSMI (date ≤ 30d) | 90 | 98.9% of second | [94.0, 99.8] |
| **MSMI from assigned** | **90** | **1.07%** | [0.87, 1.31] |

Exactly-one-no-response 37.6%; both-no-response 6.2%; among responded pairs
73.0% declined at least one side.

Cross-check, scale800 (259,696 intros, mixed rand+greedy collectors):
mutual 14.4% of assigned, date 77.7% of mutual, MSMI 8.8% of dates, 0.99%
overall. **Conversion rates are nearly identical across collector policies**
(n01 greedy 15.2% mutual/assigned and 9.3% MSMI/date vs scale800 14.4% and
8.8%). Whatever separates policies, it is not the conditional conversion of
the pairs they happen to introduce.

The two dominant losses are (a) the response gate (43.8% of pairs never get
two responses) and (b) the date -> second-intention collapse (90.6% of dated
pairs die). The 30-day deadline is nearly free (1.1% loss).

## 3. Why those losses are invisible to policy (S08, diagnostic-only)

The generator's outcome equations (kit.py L133–189, extracted in
`tables/generator_source_facts.csv`):

- Acceptance: `sigmoid(-0.25 + bias_a + fit(4 soft truths) + shared + drift)`.
  bias ~ N(0,0.7) hidden per member; shared ~ N(0,0.45) hidden per pair; drift
  -0.5 for drift-variant days ≥ 35.
- Response gate: each member responds independently with hidden
  `response_rate ~ U(0.55, 0.98)` — **independent of every observable feature**.
- Date: constant Bernoulli(0.78) given mutual — no fit dependence.
- Second intention: `sigmoid(0.15 + second_bias + shared + 0.4*[goal match])`,
  gated again by `response_rate` and a 3/5 on-time probability.
- Hard fields, age, zone, gender: feasibility only — zero outcome effect.
- History, wait days, competition, ask budget: allocation-side only — the
  conversion equations contain no state terms.

Prior-sampling of these equations (`tables/generator_prior_multipliers.csv`)
reproduces the empirical funnel without any world rollout: P(both respond)
prior 0.584 vs empirical 0.562; P(date) exactly 0.78 vs 0.754/0.777;
P(deadline ≤ 30d) 0.989 vs 0.989. The funnel is the generator design, and
most of its multiplicative loss sits in variables no policy can observe.

## 4. Scoring signal: where it lives and where it does not (S06)

- Global AUC 0.5932 reproduces; within-day mean AUC **0.5811** over 2,022
  two-class days — the signal is not purely a between-day base-rate artifact.
- But 66.0% of score variance is between days, and **per-world within-day AUC
  ranges [0.002, 0.987]** (world-mean 0.5825 ± 0.3050, n=685 two-class
  worlds). The modest global signal is wildly heterogeneous: in most worlds it
  is near-chance; a minority of worlds carry it.
- Ablations: removing ALL soft features changes AUC by +0.003 (0.596 vs
  0.5932) — soft features add nothing in-band. State-only features
  (day/budget/competition/history) give 0.5105 — chance, as the generator
  equations predict.
- Empirically, the usable signal lives in pair-level age/gender/zone-style
  features, which in the generator affect feasibility, not outcomes — their
  in-band correlation with conversion is likely composition (who becomes
  feasible together), not chemistry.

## 5. Clarification (asks): volume engine, not conversion lever (S04, S07, audit)

- Greedy's ask curve: full 12-unit spend every day 0–10 in all 72 episodes,
  tapering to zero by day ~21 when the eligible pool empties (audit;
  S04 `ask_spend_by_day.csv`). Utilization 28.2% of the 720 nominal — the
  slack is structural, not refusal.
- The no_asks ablation (paired, 72 worlds): assignments collapse 76.0 →
  19.6 per world (-75%), conversion 0.841% → 0.426%, delta MSMI -0.5556
  (volume -0.35 + conversion -0.21). **Asks are how anything gets introduced
  at all**: they unlock hard feasibility (eligibility cannot return feasible
  while any HARD field is missing).
- Soft asks unlock exactly 0 feasibility (eligibility is HARD-only); greedy
  never issues one. E1's VoI-gated REL asks changed the allocation on 76.6%
  of ask days, yet E3's primary comparison stayed non-significant — allocation
  changes did not convert to MSMI, consistent with Sections 2–3.
- 34.3% of members carry ≥1 declined HARD field (S02; audit: ~67/episode);
  declined answers are never revealed by any ask (kit.py L127) → those members
  are permanently non-introducible for every policy. This is a fixed ~33% wall
  on the member pool, identical for all arms.
- At introduction time, 42.4% of greedy intros had zero observed soft fields
  on both members (S04) — the scorer's soft view of most pairs is blank by
  construction under greedy.

## 6. Allocation structure: thin graphs, arbitrary ties (S03, S07)

- Tournament worlds: feasible edges mean 1.7–4.2 per day; 47.2% of days select
  nothing (n01_days). Zero-selection is dominated by "no feasible edges" early
  and A+C-floor exclusion (80–94% of candidates) in A+C arms (E9).
- Greedy is score-optimal (pair_score_deficit > 0 in 0/8,433 intros), but
  **65.7% of chosen pairs sit in a 2–7-way tie at the max score** (mean 3.14
  co-max edges). On those days the identity of the introduced pair is decided
  by deterministic tie-break, not information — an axis no scorer currently
  orders, because their scores are equal by definition.
- Round2 decomposition (paired, Kitagawa two-factor): gated exactly 0.0000
  (gate never fires), ungated -0.0972 (vol -0.03, conv -0.07), random ~0.
  Tournament confirm1: identical volumes, conversion 1.08–1.25%. Every
  policy lever tested so far has moved either volume (asks) or nothing;
  none has moved conversion of the introduced set.

## 7. Evidence-tagged ranking of root-cause hypotheses

Tags: **supported** = directly measured in >= 1 artifact with stated
uncertainty, plus mechanism where noted; **suggestive** = measured pattern
with plausible alternative explanations or small n; **unresolved** = cannot be
settled with persisted artifacts.

1. **H1 [supported] — The outcome funnel's dominant losses are pair-insensitive
   gates driven by hidden member/pair attributes, capping what any pairwise
   policy can achieve.** 43.8% two-response failure (response_rate hidden,
   independent of observables); second-intention collapse 90.6% (second_bias
   hidden + shared shock + 3/5 on-time + re-gating). Prior multipliers match
   the empirical funnel (S08). Conversion is nearly identical across greedy
   and mixed collectors (Section 2).

2. **H2 [supported] — Observable state carries no conversion information by
   construction; soft features add ~nothing in-band; the small global scoring
   signal is concentrated in a minority of worlds.** state-only AUC 0.5105;
   no-soft delta +0.003; per-world within-day AUC range [0.002, 0.987]
   (S06). This alone predicts the tournament's uniform null.

3. **H3 [supported] — Clarification drives introduction VOLUME, not
   conversion; greedy's unused budget is a structural empty pool, and the
   declined-HARD wall (~33% of members, ~67/ep) is unfixable by any ask.**
   no_asks -0.5556 via volume collapse; audit replay 72/72: resolvable share
   asked = 1.000, pool = 0 from day 21; kit.py L127.

4. **H4 [supported] — The allocation levers tested so far change neither the
   introduced set's composition nor its conversion: MWM gate never fires,
   method tournament holds volume fixed and moves conversion by sub-noise
   amounts, ungated floor ablation is negative.** gated 0/72; tournament
   2,402 everywhere; ungated -0.0972 (S07); floor excludes 80–94% (E9).

5. **H5 [supported] — Score ties make ~2/3 of greedy introductions
   information-free choices among co-max edges; opportunity sparsity (1.7–4.2
   edges/day, ~47% zero-selection days) bounds the action space.** 65.7% tied
   intros, mean 3.14 co-max (S07); graph tables (S03).

6. **H6 [suggestive] — Observed-soft count at introduction is NEGATIVELY
   associated with conversion (band 0: mutual 15.8%, MSMI 1.31% vs band 3-4:
   10.5%, 0.0%; CIs non-overlapping for bands 0 vs 1-2).** The mechanism is
   not identified: under greedy, soft observation is generation-random
   (complete questionnaire or 10% draw), so a causal reading is unwarranted;
   composition/confounding (arrival timing, feasibility pathway) is the
   leading explanation. Flagged because it is the opposite of what a
   soft-matching policy assumes.

7. **H7 [suggestive] — The A+C floor converts feasibility gains into discarded
   candidates, explaining why A+C asks more (~2x cost) yet introduces fewer
   pairs and scores worse than greedy on the same worlds.** intros 5,486 (A)
   > 5,178 (C) > 4,598 (B); floor excludes 83.5–94.1% of greedy picks (E7/E9);
   probe shows equal cumulative feasibility gains (273 = 273) — the loss is
   post-feasibility selection, not ask coverage.

8. **H8 [unresolved] — The pair-level shared shock N(0,0.45) is comparable to
   the full soft-fit range; unobserved pair chemistry may dominate observable
   fit, but its variance share cannot be computed from persisted artifacts.**
   No per-pair shock is logged; OPR's stage-label concordance failure
   (rho 0.778) is consistent with large unobserved outcome noise but does not
   quantify it.

9. **H9 [unresolved] — Whether any remaining lever (better tie-breaking among
   co-max edges, arrival-order effects, variant-specific drift handling)
   has a measurable in-band effect cannot be settled with persisted labels:
   the fine respond-vs-decline split, per-intro scores, and E-arm stage
   outcomes are not logged** (data gaps 1–3, 7 in evidence_inventory.md).
   Existing evidence bounds these as second-order next to H1–H3.

## 8. What this report does not say

No experiment is recommended; no policy is endorsed; no submission decision is
implied. Hypotheses are ranked by strength of existing evidence, not by
expected value of follow-up. The generator-side facts in Section 3 are
diagnostic properties of this simulator — they explain why the observed record
looks the way it does; they are not policy inputs. Empirical associations in
Sections 2, 4–6 are descriptive on collector-selected intros (selection is
acknowledged wherever it binds); only the paired decomposition in Section 6
carries a causal reading within the paired worlds.
