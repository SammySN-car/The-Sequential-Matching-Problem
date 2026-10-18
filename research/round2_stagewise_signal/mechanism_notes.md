# Source-Mechanism Description (isolated; not a predictive model)

Every equation below is a SOURCE-CODE FACT read from `kit.py` and verified by `ss5_mechanism.py` against the current file. Hidden generator values (`response_rate`, `bias`, `second_bias`, `truth`, `shared`, date/delay randomness) are described here ONLY. They are banned from every feature matrix (BANNED_FEATURE_EXACT) and no variance-explained claim is made from these associations.

## The two acceptance-relevant logits

**Initial acceptance** (`_prob`, kit.py L139-139): `z = -0.25 + bias_a + fit + shared + drift`, `p = sigmoid(z)`. `fit = sum_k w_k * (1 if truth_a[k]==truth_b[k] else -0.5)` over the FOUR soft truths {relationship_goal, relationship_pace, lifestyle, conversations} with default weights {0.7, 0.4, 0.25, 0.2} (kit.py L135). The `shift` variant swaps these to {0.25, 0.8, -0.25, 0.5} (L136). `drift = -0.5` in `drift` variant from day 35 (L138). `shared ~ N(0,0.45)` is pair-level randomness COMMON to both actors (L157); `bias_a` is a hidden per-member attribute (L139).

**Second-meeting intention** (kit.py L179): `p = sigmoid(0.15 + second_bias_a + shared + 0.4 * [truth_a[relationship_goal]==truth_b[relationship_goal]])`. Note: relationship-goal agreement enters BOTH logits (weight 0.7 in `fit`, +0.4 here); the other three soft truths enter ONLY the initial-acceptance `fit`.

## Stage-by-stage dependence on hidden values

| Stage | Explicit hidden dependence | Legal observable correlate |
|---|---|---|
| T1 both_responded | `response_rate` only (L159) | none (response is independent of truths) |
| T2 mutual | `response_rate`, `bias`, 4 soft `truth` (fit), `shared`, `drift` | the 7 soft channels (observed match/mismatch/unknown) partially reveal the 4 truths |
| T3 date | T2 + date randomness `p=0.78` (L171) + timing `U(1,14)` (L169) | none beyond T2 |
| T4 date_within_deadline | T3 + timing; `delayed` variant adds `U(5,12)` days (L170) | `variant` is legal at decision time |
| T5 timely_second | `response_rate`, `second_bias`, `shared`, goal-agreement `+0.4`, delay `U(1,5)` with on-time `<=3` (L180) | relationship-goal channel (observed) is the only legal correlate of the `+0.4` term |
| T6 final_msmi | T4 AND T5 (official def, L197) | inherits T4+T5 observables |
## What this predicts about the observed funnel (and how to read it)

- The T1 null (no observable signal; measured AUC 0.496, CI includes 0.5) is EXACTLY what the mechanism predicts: T1 depends only on hidden `response_rate`, which generation draws independently of every observable field.
- The relationship-goal association should APPEAR at T2 (it enters `fit` at weight 0.7) and PERSIST to T5/T6 (the +0.4 second logit). The measured funnel matches: goal match-vs-mismatch CI excludes 0 at T2, T3, T4, T5, T6 but not T1.
- `lifestyle`/`pace`/`conversations` enter `fit` but NOT the second logit, so their association should fade at T5/T6; measured: pace/conversations show T2-T4 association, but only goal (and marginally conversations) persist to T5/T6.
- T4 is nearly free (only 8 deadline misses, all `delayed`): the 30-day deadline rarely binds because `date_day` is usually well inside 30 days except under the `delayed` +U(5,12).
- T5 is the dominant collapse (1689 dates -> 174 timely-second): it compounds hidden `response_rate`, `second_bias`, `shared`, AND a pure-timing coin (`delay<=3`). The timing component is NOT predictable from any observable, which caps T5/T6 achievable AUC.

## Honesty notes

- These are mechanism facts, not measurements of real human behaviour; the simulator is synthetic and invented.
- Association of an observable channel with a stage does NOT mean the channel causes the outcome; the channel only partially reveals a hidden truth that the equation uses.
- No hidden value is used as a predictor anywhere in this study; this file is a description kept deliberately separate from the predictive analysis.
