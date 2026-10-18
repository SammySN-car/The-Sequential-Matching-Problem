# Stagewise Counterfactual Signal Audit — Report

Study: `research/round2_stagewise_signal/`. Diagnostic only; no policy is built, modified, or recommended. Independent unit = seed group (21 seeds, 6 variants each). All intervals are seed-group bootstrap (B=2000, rng=4242).

## 0. Validation gate

All 13 checks PASSED (`validation.json`).
- Prior seals current (decision-ceiling, fixed-cardinality); only the recorded `run_log.txt` append deviates.
- Isolated-replay funnel reproduces the frozen labels BIT-EXACTLY: recomputed `y_mutual/date/second/msmi/missing` equal the stored `cf_*` columns (max abs diff 0.0); all 8,433 selected pairs match the frozen n01 outcomes.
- Counts reconcile: 15,304 opportunities, 8,433 selected, 173 counterfactual MSMI positives, 90 of them selected (= the 90 original N01 MSMIs), 0 duplicate keys.
- OOF consistency: refitting A/B/C for final-MSMI reproduces `oof_scores.jsonl` bit-exactly (max abs diff 0.0), confirming the recorded F2 MSMI metrics (AUC 0.5634, within-state 0.5881, PR-AUC 0.0175, prevalence 0.0113).

## 1. The complete outcome funnel (15,304 opportunities)

| Stage | n | unconditional rate | seed-group 95% CI |
|---|---|---|---|
| T1 both responded | 9148 | 59.78% | [58.26%, 61.43%] |
| T2 mutual acceptance | 2183 | 14.26% | [13.25%, 15.45%] |
| T3 date occurred | 1689 | 11.04% | [10.27%, 11.90%] |
| T4 date within 30-day deadline | 1681 | 10.98% | [10.22%, 11.84%] |
| T5 both timely second yes | 174 | 1.14% | [0.91%, 1.37%] |
| T6 final MSMI | 173 | 1.13% | [0.91%, 1.36%] |

Counts lost between successive stages: T1->T2 6965; T2->T3 494; T3->T4 8 (deadline is nearly free); T3->T5 1515 (the dominant collapse); T5->T6 1.
Event detail preserved: 9865 explicit intro "no"s, 6156 intro no-responses, 566 second-yes responses that arrived late (>3 days), 639 missing second responses. The funnel shape is consistent across all six variants (`stage_by_variant.csv`); only `delayed` loses to the deadline (8 pairs).

## 2. Predictive signal at each stage (soft-state representation B)

Feature sets: A = baseline count score; B = explicit soft-state representation; C = full legal observables. Model frozen (HistGradientBoosting 200/0.06/rs40, GroupKFold-4 by seed), OOF.

| Stage | n_pos | AUC_B | lift | seed-group CI | CI excludes 0.5? | delta(B-A) [CI] |
|---|---|---|---|---|---|---|
| T1 both responded | 9148 | 0.495766 | 1.00 | [0.477428, 0.512459] | no | -0.0218 [-0.0385, -0.0040] |
| T2 mutual acceptance | 2183 | 0.529466 | 1.10 | [0.515651, 0.543097] | YES | +0.0331 [+0.0107, +0.0537] |
| T3 date occurred | 1689 | 0.534119 | 1.09 | [0.513554, 0.553895] | YES | +0.0451 [+0.0253, +0.0649] |
| T4 date within 30-day deadline | 1681 | 0.54224 | 1.12 | [0.525981, 0.560618] | YES | +0.0564 [+0.0384, +0.0751] |
| T5 both timely second yes | 174 | 0.593999 | 2.51 | [0.514327, 0.677555] | YES | +0.0807 [+0.0354, +0.1343] |
| T6 final MSMI | 173 | 0.563408 | 1.55 | [0.488127, 0.644772] | no | +0.0596 [+0.0277, +0.0938] |

C (full legal observables) DILUTES B at the rare stages: T5 AUC_C=0.534288 < AUC_B=0.593999; T6 AUC_C=0.523253 < AUC_B=0.563408. Adding profile/state features does not help the rare composite.
Per-seed consistency (B, fraction of 21 seeds with AUC>0.5): both_responded 9/21; mutual 18/21; date 14/21; date_within_deadline 20/21; timely_second 17/21; final_msmi 18/21.

## 3. The rare-target caveat (why T5 vs T6 is not attenuation)

T5 (174 positives) and T6 (173) differ by exactly ONE row (index [6540], a `delayed` pair whose timely second yes missed the deadline). Cross-evaluating the two OOF fits:
- Swapping only the EVALUATION target for a fixed model moves AUC by <= 0.000020 (evaluation-side gap 0.000020).
- Two models whose TRAINING labels differ by that single row yield score correlation 0.799 but a same-evaluation-label AUC gap of 0.0306.
=> The apparent T5->T6 AUC dip (0.5940 -> 0.5634) is MODEL-FIT INSTABILITY on a ~173-positive target, not loss of underlying signal.
## 4. Relationship-goal across the funnel

| Stage | match rate | mismatch rate | rate diff [CI] | score delta [CI] |
|---|---|---|---|---|
| T1 both responded | 0.622429 | 0.616609 | +0.0058 [-0.0840, +0.0913] | -0.00469 [-0.03794, +0.02092] |
| T2 mutual acceptance | 0.219393 | 0.069707 | +0.1497 [+0.1146, +0.1864] | +0.13044 [+0.11747, +0.14555] |
| T3 date occurred | 0.173359 | 0.048193 | +0.1252 [+0.0961, +0.1563] | +0.09907 [+0.09008, +0.11006] |
| T4 date within 30-day deadline | 0.17238 | 0.047332 | +0.1250 [+0.0956, +0.1569] | +0.10475 [+0.08991, +0.11785] |
| T5 both timely second yes | 0.021058 | 0.002582 | +0.0185 [+0.0101, +0.0282] | +0.01062 [+0.00755, +0.01371] |
| T6 final MSMI | 0.020568 | 0.002582 | +0.0180 [+0.0098, +0.0275] | +0.01176 [+0.00940, +0.01406] |

Goal agreement is ABSENT at T1 (CI includes 0), APPEARS at T2 mutual acceptance, and persists to T6 (~8x relative gap). Other channels (match-vs-mismatch CI excludes 0), by stage: both_responded: relationship_pace; mutual: relationship_goal,relationship_pace,conversations; date: relationship_goal,relationship_pace,conversations; date_within_deadline: relationship_goal,relationship_pace,conversations; timely_second: relationship_goal,conversations; final_msmi: relationship_goal,conversations. `lifestyle`, `emotional_availability`, `space_for_relationship`, and `relocate` show no association at any stage. 42 channel x stage contrasts were examined, so non-goal channels are treated as suggestive.

## 5. Ranking failure through stagewise results

The 173 true MSMI-positive edges, under the frozen F2 OOF score, sit at a mean within-state percentile of 0.455 (median 0.417); the baseline count score ranks them BETTER (mean 0.388), and F2 outranks baseline on only 32.4% of them. So F2's global AUC advantage does not translate into within-state top-k_t concentration - positives stay mid-pack, which is why top-k_t selection misses 67 that the label-aware oracle catches (94 captured, 161 in the F5 set).
The soft-state marginal contribution (delta B-A) GROWS down the funnel (T2 +0.033 -> T5 +0.081), so the observable signal that exists is concentrated in exactly the stages where the 60 ranking points are lost. No legal feature in C improves on B at the rare stages.

## 6. The six required questions

**Q1. Which stages contain measurable observable predictive signal?** Applying the frozen rule (seed-group AUC CI excludes 0.5, power ok): T2 mutual (AUC 0.529466), T3 date (0.534119), T4 deadline (0.54224), T5 timely_second (0.593999). T1 both_responded has NONE (AUC 0.495766, CI [0.477428,0.512459] - the mechanism-consistent null, since response depends only on hidden response_rate). T6 final_msmi is SUGGESTIVE, not certified: point AUC 0.563408 and lift 1.55 with 18/21 seeds >0.5, but the seed-group CI [0.488127,0.644772] includes 0.5 because 173 positives spread thin over 21 seeds.

**Q2. At what stage does signal weaken most sharply?** It does NOT weaken down the funnel - it STRENGTHENS: B AUC rises from 0.495766 (T1, none) to 0.529466 (T2) and peaks at 0.593999 (T5). The only apparent decline (0.593999 -> 0.563408) is model-fit noise on the ~173-positive targets (Sec. 3), not attenuation. What degrades is PRECISION: the seed-group CI widens from +/-0.014 at T2 to +/-0.08 at T5/T6 as positives collapse ~13x (2,183 -> 173). The sharp event is the APPEARANCE of signal at T2 and the positive-count collapse at T5 (date->timely_second), not a loss of association.

**Q3. Is relationship-goal robust across stages or only final?** ROBUST ACROSS STAGES. Absent at T1 (diff +0.0058, CI includes 0); appears at T2 mutual (match 0.219393 vs mismatch 0.069707, diff +0.1497 CI [+0.1146,+0.1864]); persists through T3/T4; and remains strongly associated in relative terms at T5/T6 (~8x: T6 match 0.020568 vs mismatch 0.002582, diff +0.0180 CI [+0.0098,+0.0275]). Cross-validated score separation CI excludes 0 at T2-T6. This matches the simulator (goal weight 0.7 in the acceptance fit, +0.4 in the second logit). It is a DESCRIPTIVE + PREDICTIVE association, NOT a causal effect (correlation through synthetic equations; see mechanism_notes.md).

**Q4. Does final MSMI underperform by missing intermediate signal, or does signal disappear later?** NEITHER, as stated. (a) T6 does not lose signal vs its precursor: T5 and T6 are the same target up to one deadline-missed pair, and their AUC gap is fit noise (Sec. 3). (b) The signal does not disappear - it ACCUMULATES (delta B-A grows T2->T5; goal association strengthens in relative terms). (c) The final model "underperforms" only in PRECISION: its point AUC (0.563408) is the second-highest of all stages, but 173 positives over 21 seeds give a CI that includes 0.5, so it cannot be certified measurable. The model does capture intermediate-stage signal; there are simply too few final positives to certify it. A fuller feature set (C) actively dilutes B at T6.

**Q5. What is established about the 60-point ranking component, and what is unknown?** ESTABLISHED: the 60 ranking points correspond to a within-state ranking weakness that is now located. The 173 positives sit at mean within-state percentile 0.455 under F2 - NOT concentrated near the top - and the baseline count score ranks them better (0.388); F2 beats baseline on only 32.4%. F2's global AUC advantage therefore does not yield top-k_t concentration, which is exactly why top-k_t misses 60 positives the oracle catches. The stagewise map places the missing information in the acceptance (T2) and second-meeting (T5) stages, both partially revealed by the soft channels (goal, conversations). UNKNOWN: (i) whether any LEGAL feature could rank the 60 higher - the observable signal already present in B is not amplified by C, so no evident legal feature repairs it; (ii) the 7 conflict + 12 irreducible points are structural, untouched here; (iii) whether T5/T6 signal would survive at higher positive counts (untestable at 21 seeds).

**Q6. Supported / suggestive / unresolved.**
- SUPPORTED (CI excludes null, power ok): T2-T5 contain measurable observable signal for the soft-state representation; relationship-goal match-vs-mismatch association at T2-T6; soft-state marginal contribution positive at T2-T6 (negative at T1); the T1 mechanism-consistent null; the funnel collapse is at T5, not the deadline; T6 = T5 minus 1 deadline miss; the 173 positives are mid-pack under F2 and worse-ranked than baseline.
- SUGGESTIVE (point + most seeds, but CI includes null or multiplicity): final-MSMI predictive signal (AUC 0.563408, lift 1.55, 18/21 seeds, CI includes 0.5); `conversations` persistence to T5/T6; `relationship_pace` early association (42-contrast caveat).
- UNRESOLVED (21 seeds, ~173-positive rare outcome): whether final-MSMI signal is truly measurable; whether any legal feature could repair the within-state ranking of the 60 missed positives; the share of the 60 points attributable to the unobservable T5 timing coin; any causal effect of goal agreement.

## 7. Deliverables

`analysis_plan.md` (frozen hash in `analysis_plan.sha256`), this `report.md`, `stage_counts.csv`, `stage_by_variant.csv`, `stage_by_goal_status.csv`, `stage_by_soft_channel.csv`, `stage_model_metrics.csv`, `seed_group_metrics.csv`, `ranking_by_stage.json`, `goal_signal.json`, `rare_target_sensitivity.json`, `funnel_summary.json`, `mechanism_notes.md`, `validation.json`, `run_log.txt`, `integrity.sha256`, and scripts `ss0`-`ss6`, `ss_seal`, `ss_verify` under `scripts/`.

No policy is proposed, no existing experiment is modified, no fresh tournament is run, and no submission decision is made. Diagnosis only.
