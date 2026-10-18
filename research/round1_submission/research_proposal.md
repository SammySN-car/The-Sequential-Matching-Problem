# Constraint-First Sequential Matching Under Incomplete, Declinable Information

## A Testable Policy Framework for the MSMI Objective

**Round 1 Research Submission — The Sequential Matching Problem**
Applied Machine Learning Programme & Hackathon — Romeo & Juliet Ltd. × IIT Madras

| Submission metadata | |
|---|---|
| Team name | [FILL IN FROM REGISTRATION] |
| Team leader | [FILL IN FROM REGISTRATION] |
| Registered email | [FILL IN FROM REGISTRATION] |
| Romeo & Juliet code | [FILL IN FROM REGISTRATION] |
| College or institution | [FILL IN FROM REGISTRATION] |
| Date / version | 9 October 2026, v1.0 |
| Authority for all rules, metrics and baselines | Official specification [1] |

---

## A. Executive summary

This challenge is a sequential decision problem. Each decision day, a policy observes a changing population of synthetic members whose preference profiles are only partly known: 11 hard-constraint fields and 7 soft-preference fields per person, each in one of three states — observed, declined, or not yet asked. The policy must spend a daily clarification budget of 12 units (3 units for a constraints bundle, 1 unit for a named soft field), introduce non-overlapping pairs drawn from the currently available population, or wait. Feedback is delayed and censored: introductions carry a 7-day response deadline, a date must occur within 30 days of assignment, second-meeting intentions are observed only for pairs that actually dated, and a large share of responses never arrive. The objective is the official MSMI per 100 arrived members — a pair counts only if both members accepted the introduction, dated within 30 days, and both said yes to a second meeting within 3 days of that date — averaged equally across six scenario families with 20 seeds each.

The difficulty is structural rather than merely statistical. Compatibility is reciprocal: a pair is eligible only if the hard constraints of both members are satisfied by known values, and a declined answer is a permanent fact, never an imputation. Information is costly and unevenly useful: an answer can establish feasibility for one pair while changing nothing for the rest of the day's allocation. Introductions compete for the same members (non-overlap), arrivals are stochastic across scenarios, and the terminal event we optimize is rare — about 0.94% of observed introductions mature to MSMI in our dataset. Consequently, optimizing a conventional pair classifier, AUC, introduction counts, or mutual acceptance alone is insufficient: those quantities can improve while realized MSMI does not, as our completed experiments demonstrate concretely (Sections G and I).

Our hypothesis is stated as falsifiable: **a constraint-first sequential policy — reciprocal feasibility filtering first, then selective clarification chosen by decision relevance per unit cost, then bilateral pair scoring, then non-overlap allocation, with explicit consideration of arrival timing and the value of waiting — can raise realized MSMI relative to the supplied greedy baseline.** Each mechanism is a hypothesis to be tested, not a promised improvement, and the greedy baseline is the incumbent to beat, not a straw man.

Our method implements the pipeline above as a layered policy whose every layer is independently testable, and evaluates it with the official kit under a preregistered screening-and-confirmation design: cheap paired screening on a small seed set, code freeze, then confirmation on fresh seeds with cluster-by-seed confidence intervals, multiple-comparison correction, per-scenario guardrails and zero-invalid-episode gates. Success is defined in advance: a challenger replaces greedy only if its paired mean improvement in primary MSMI is credibly above zero on untouched confirmation seeds with all validity gates green; otherwise the honest conclusion is to keep greedy.

Substantial experimental work has already been completed and informs this proposal. It is reported honestly below and separated from proposed work: Table 1 marks every element as completed or proposed. The completed record includes an official-baseline evaluation, an 800-world labelled dataset and scoring models, a 576-episode clarification experiment, a 30-method tournament that ended in a keep-greedy verdict, and a decision-state autopsy that found no supported decision-time signal. None of this proves greedy globally optimal; it defines where the remaining opportunities plausibly lie.

**Table 1 — Status of work (completed vs. proposed).**

| Work item | Status | Key result or intent |
|---|---|---|
| Official-baseline evaluation (seeds 101–103 × 6 families) | Completed | greedy 0.389 > random 0.278 > learned arm 0.250 > no_asks 0.139 primary MSMI/100; learned arm lost to greedy 0/3 seeds at 2× ask cost |
| Outcome-data pipeline and scoring models (800 worlds, 259,696 labelled rows) | Completed | MSMI label AUC 0.5937 [0.5667, 0.6208]; real but weak ranking signal; used as a ranking score, not a calibrated probability |
| Clarification experiment: value-of-information asks × analytic scoring (4 arms, 576 episodes) | Completed | Preregistered verdict INCONCLUSIVE → keep greedy; 0 invalid episodes |
| 30-method tournament (screening → two confirmation phases) | Completed | Funnel 30 → 4 → 2 → 0 credible; verdict: greedy remains best among evaluated candidates |
| Decision-state autopsy (126 replayed worlds, 8,433 introductions, 33 candidate features) | Completed | Conclusion B: 0/33 primary gate passes; no supported decision-state signal |
| Static score/value audit (72 worlds) | Completed | Greedy score vs. oracle pair value Spearman 0.12; +18.7% offline expected-value bound (full-reveal condition never tested live) |
| Feedback-reweighted pair scoring (proposal n02) | Proposed | Untested: reweight pair scores by conversion history already visible in feedback/introductions |
| Feedback-adaptive soft-field asking (proposal n03) | Proposed | Untested: choose which soft field to ask next from ask_log + feedback history |
| Guarded lookahead waiting (proposal n04) | Proposed | Untested: match-now vs. preserve-value estimate with a hard no-wait guard on thin markets |

---

## B. Problem formulation

**Sequential state.** At decision day *t* the observable state comprises: the set of arrived and currently available members; each member's field table, where every hard or soft field carries a status in {observed, declined, not asked} (a missing value is never interpretable as a rejection); the interaction history — every past introduction with its assignment day, 7-day response deadline, and feedback observed by day *t* — plus the day's remaining ask budget. A size-capped memory object (≤ 1 MiB) may be carried across invokes for any state the policy chooses to persist.

**Legal actions.** Two phase-linked actions are available per day. In the ask phase the policy may submit clarification requests: a constraints bundle costs 3 units and a named soft field costs 1 unit, with total spend ≤ 12 per day; a declined field can never be asked again. In the match phase the policy submits a batch of pairs subject to hard legality: both members available; the pair feasible with respect to all known hard constraints of both members; the pair never introduced before in this episode; and no member appearing twice in the same batch. The simulator validates the whole batch atomically — any invalid action makes the episode invalid, and an invalid assessed episode makes a submission ineligible [1].

**Delayed and censored outcomes.** An introduction assigned on day *t* has a response deadline of *t + 7*; a non-response remains missing and does not establish dislike. A qualifying pair needs both directional yes responses, a date within 30 days of assignment, and both yes responses to a second meeting within 3 days of the date; a pair that never dates has no observed second-meeting preference [1]. Episodes run 60 decision days plus 40 action-less follow-up days, with metrics computed at day 100.

**Objective.** The primary metric is the official MSMI per 100 arrived members,

> MSMI/100 = 100 × (number of qualifying pairs) ÷ N(arrived members by day 59),

with one qualifying pair counted once, averaged equally over the six scenario families (standard/development, sparse, cold_start, delayed, shift, drift) at 20 seeds each — 120 episodes. Secondary metrics include coverage (distinct arrived members introduced ÷ N), mutual acceptances, introductions, clarification cost, and conversion rates (mutual per introduction, date given mutual, MSMI given introduction); ties are broken by the official order of coverage, then mutual/100, then lower ask cost, then lower inference time [1].

**Immediate compatibility vs. long-run decision value.** A pair score answers "how compatible do these two look today?" Long-run decision value answers "does introducing this pair now maximize realized MSMI over the remaining horizon?" The two diverge whenever a better alternative edge exists later or elsewhere in the same batch (non-overlap opportunity cost), whenever an unanswered field could flip eligibility (option value of asking), or whenever arrivals are scarce today and a member's introduction is better spent on a future day (value of waiting). Every mechanism in Section E exists because one of these divergences is measurable in this simulator.

---

## C. Research hypothesis and rationale

**Headline hypothesis (H).** A constraint-first sequential policy — reciprocal feasibility filtering, decision-relevance-driven clarification, bilateral scoring, non-overlap allocation, and guarded waiting — improves realized MSMI per 100 arrived members over the supplied greedy baseline under the official evaluation protocol.

We decompose H into four testable sub-hypotheses, each with its rationale and its pre-identified way of failing:

- **H1 — Feasibility-first clarification pays.** Spending hard-field ask units only where an answer can flip a specific pair's eligibility (and soft units only where they can change the day's allocation) yields more realized MSMI per ask unit than not asking and than uninformed asking. *Rationale:* on public seeds the official no_asks baseline scores 0.139 primary vs. greedy's 0.389, so information has large gross value; the open question is its marginal value under a budget. *Can fail if:* feasible sets are usually already large, so bundle answers rarely flip eligibility, or if declined answers remove targets faster than asks create them.

- **H2 — A bilateral score aligned with MSMI potential beats count-based matching.** Scoring feasible edges with a transparent bilateral score over observed soft fields (and optionally a learned ranker over decision-time features) selects edges that convert better than the count-of-matching-fields rule. *Rationale:* a static audit over 72 worlds measured Spearman 0.12 between the incumbent score and oracle pair value, and analytic scoring with fully revealed outcome-relevant fields raised offline expected pair value by 18.7% (W/T/L 67/1/4). *Can fail if:* offline expected value does not transfer to live sequential MSMI — a risk our completed clarification experiment realized directly (Section G).

- **H3 — Selective clarification concentrated on decision-relevant answers improves the objective.** A truth-blind value-of-information gate that spends soft-ask units only when the answer could change the day's allocation concentrates the budget usefully. *Rationale:* in the completed 576-episode experiment the gate was high-precision (76.6% of its asks decision-relevant, ~42 units/episode against ~517 idle units). *Status:* end-to-end MSMI improvement was inconclusive (+0.9%, CI [−0.084, +0.091]), so we refine H3 into an untested successor: the residual value lies in *adaptive selection of which field and member to ask over time* from observed feedback (Section F), not in static within-day enumeration.

- **H4 — Waiting helps only when conditionally guarded by arrival scarcity.** Dropping a pair today to preserve option value helps only when an arrival-rate-aware guard confirms thin-market conditions. *Rationale:* in the completed tournament every unconditional waiting/threshold rule failed precisely on cold_start, delayed, shift and drift. *Can fail if:* arrival-rate estimates are too noisy within 60 days, or the guard is too conservative and loses coverage.

**Incumbent null (H0).** Greedy remains the best empirically supported policy among evaluated candidates; the burden of proof is on every challenger. This is the standing conclusion of our completed tournament, explicitly not a claim of global optimality: the tournament covered heuristic, scoring, allocation, waiting and asking variants, not all conceivable sequential policies.

**Assumptions that could invalidate H.** (i) The static-to-live transfer of offline value estimates — already partly contradicted. (ii) Decision-time features carry learnable signal about conversion — our autopsy found none that passed its preregistered gate. (iii) Effect sizes are detectable with feasible confirmation sizes: paired per-seed standard deviation is ≈ 0.24 on the primary metric, so a 72-world (12-seed) confirmation resolves only effects of roughly 0.09 or larger at 99% confidence; genuinely small gains will read as inconclusive. (iv) The feedback channel and arrival processes seen in the six families are representative. (v) Our label pipeline is leakage-free — enforced by whole-world splits, temporal masking, and audits described in Section G.

---

## D. Reciprocal feasibility

Reciprocal feasibility is checked in both directions before any scoring occurs. A candidate pair is feasible only if every hard-constraint field of member A that is *observed* is satisfied by member B's corresponding known state and vice versa; the kit's eligibility result is one of three statuses — feasible, needs clarification, or ineligible [1] — and only feasible pairs may enter the match batch.

Known violations are permanent. A hard field answered with a value that makes a pair impossible (or a declined constraints answer) makes that pair ineligible for the rest of the episode; pairs are never re-introduced (the simulator rejects repeats), and a declined field can never be asked again. Declining is thus an absorbing observation about information, not about attraction.

Unknown and declined answers must not be confused with rejection, and this proposal treats the official specification as authoritative on the point: a missing response remains missing; failing to respond by the 7-day deadline does not establish dislike; a pair that never dates has no observed second-meeting preference [1]. Operationally this means:

- **No silent imputation.** Missing hard values never default to "satisfied" or "violated"; they route the pair to *needs clarification* or leave it out of the feasible set. Missing soft values contribute nothing to a score rather than being filled with a majority value.
- **Asking converts unknowns into facts, at a price.** A hard-field bundle (3 units) can move a pair from needs-clarification to feasible or ineligible — this is the only ask class that can *establish feasibility*. A soft-field ask (1 unit) can only change ranking. Tracking which pairs are "provably flippable" by one bundle is what separates H1's feasibility-first asking from asking that merely enriches the feature table.
- **Selective-label hygiene.** Only introduced pairs produce outcome labels; un-introduced pairs are unknown, not negative. This is the selective-labels structure of Lakkaraju et al. [8], and it is why our analyses (Section H) never train or validate on counterfactual outcomes and why the autopsy replayed sealed worlds byte-faithfully before examining any label.

The practical consequence for allocation: scoring runs on the feasible subgraph only, feasibility is recomputed every day as availability changes (arrivals, pauses, departures), and the needs-clarification set is the natural target of the ask phase — prioritized by whether one legal ask would change today's batch.

---

## E. Proposed method and algorithms

The proposed policy is a constraint-first pipeline with one responsibility per layer, so that each layer can be ablated, replaced, or rejected independently. Layers run in the official order: observe, ask, match.

**1. Legal-state observation.** Consume only what the interface exposes: availability, field tables with statuses, feedback observed by today, introduction history, ask log, and the memory object. All features respect temporal masking — feedback observed after day *t* and fields observed after day *t* are invisible — and NaN is preserved for unknowns. (Our completed implementation embedded this feature block verbatim in the policy and verified parity against replayed rows.)

**2. Reciprocal feasibility filtering.** Build the feasible, non-past, available edge set for today (Section D) before any score is computed. Scoring an infeasible edge is treated as a bug class, not a ranking discount. The needs-clarification set is carried forward as the ask phase's candidate pool.

**3. Selective clarification.** Under the 12-unit daily budget, ask in tiers: (i) *blocked-flip hard bundles* — bundles whose answers provably move at least one candidate pair into or out of feasibility, in descending count of flippable pairs; (ii) *progressive completion* of hard fields for members appearing in many needs-clarification pairs (budget-idle mitigation); (iii) *soft-field asks* only when a value-of-information gate says the answer could change the day's selected allocation (Section F). Declined fields are excluded by construction. Every tier is deterministic given the state.

**4. Bilateral pair scoring.** Rank feasible edges with a bilateral score computed from *observed* soft fields only. We keep three scorers under test rather than one: the official count-of-matching-fields rule (the incumbent); a transparent analytic weighted score over the outcome-relevant soft fields with explicit missing-value handling; and a learned ranker over decision-time pair features. Score comparability across days matters less than within-day edge ranking, because allocation is per-day.

**5. Non-overlap allocation.** Select a maximum-value non-overlapping subset of edges: sort by descending score with deterministic tie-breaks, then greedily take edges whose endpoints are still free (the incumbent's take-while-free structure), with an optional deterministic local-improvement pass (single swaps that strictly increase the batch score). Coverage is a guardrail, never the objective: in our baseline evaluation, random and greedy had near-identical coverage (0.377 vs. 0.372) yet very different MSMI (0.278 vs. 0.389) — reshuffling equivalent pairs does not move the metric.

**6. Sequential match / ask / wait decision.** The day-level decision is explicit: which asks to fund, which batch to submit, or to submit nothing (wait). Waiting is permitted only through the H4 scarcity guard: estimate arrival pressure from the recent availability trend, and refuse to drop a pair today unless the preserved option is expected to exceed the current edge's value *and* arrivals are not scarce. Zero-selection days are instrumented because our tournament showed unconditional waiting dying exactly on cold_start and delayed.

**7. Legal feedback and memory handling.** Persist only compact, size-capped state in memory (≤ 1 MiB): rolling per-field answer rates, per-bucket conversion counts for reweighting, and arrival-rate estimates. Completed-work audit note: all 30 tournament methods passed `memory` through untouched and none consumed `feedback` or `ask_log`; history-driven scoring and asking (proposals n02, n03) are therefore genuinely untested surfaces, not refinements of tested ideas.

**Probability model targets — stated precisely.** Where probability estimates are used, each model's target is named explicitly, and no model is described as "predicting MSMI" unless it is trained on the composite label:

| Target | Definition | Completed evidence (validation) |
|---|---|---|
| p(mutual) | Both members answer yes to the introduction | AUC 0.6131 [0.6058, 0.6205], AP lift 1.40× |
| p(date) | A date occurs within 30 days of assignment | AUC 0.6064 [0.5982, 0.6146], AP lift 1.36× |
| p(MSMI) (composite) | Both yes, date ≤ 30 days, both second-yes ≤ 3 days | AUC 0.5937 [0.5667, 0.6208], AP lift 1.30×; prevalence 0.94% |
| p(second-yes) | Both say yes to a second meeting within 3 days of the date | Not trained separately; currently visible only inside the composite label — proposed as a separate head |

Two completed findings constrain how these outputs may be used. First, ranking quality is modest but real; on the composite label the model's log-loss is *worse* than the constant-prevalence baseline, so outputs are used strictly as ranking/value scores and never as calibrated probabilities or thresholds (no score-minus-prevalence decisions). Second, directional acceptance, mutual acceptance, date completion, second-meeting intention and final MSMI are distinct random variables chained in time; a gain on any upstream target is only valuable insofar as it changes which pairs are introduced — the lesson of the completed experiment, where a high-precision asking gate produced no credible MSMI gain.

**Research questions, not a method catalog.** The layers above organize our work into four questions: *RQ1 (scoring)* which feasible edge to prefer — count rule vs. analytic vs. learned, with history reweighting (n02) proposed; *RQ2 (clarification)* which field to ask and when — tiers and VoI gate completed, feedback-adaptive selection (n03) proposed; *RQ3 (allocation)* which non-overlapping set — take-while-free, local improvement, and (only if RQ1 shows aligned scores) weighted matching; *RQ4 (timing)* match now or wait — scarcity-guarded lookahead (n04) proposed. Graph-based allocation is discussed only to the extent justified: maximum-weight assignment [4] is the natural RQ3 tool, but our completed tournament showed a graph-optimization variant changing 36/36 worlds with exactly 0.000 MSMI delta, so RQ3 is explicitly gated on RQ1 producing a score that correlates with realized value.

---

## F. Clarification strategy

**Budget shapes the design.** Twelve units per day means at most four constraints bundles, or a bundle-plus-soft mix; over a 60-day episode that is 720 units, of which the incumbent spends roughly 190–200 and a heavy-asking arm spent 419 in our evaluation. The budget is not the binding constraint in aggregate — about 517 units per episode sit idle — but it is binding *per day*, so the ordering of asks within a day is where policy quality shows.

**Hard vs. soft clarification.** Hard-field clarification is *feasibility-producing*: one bundle can flip a specific pair between needs-clarification and feasible/ineligible, and only such flips can change who exists in today's candidate set. Soft-field clarification is *ranking-producing*: it can reorder scores but cannot create a legal edge. Our tier design (Section E.3) therefore funds blocked-flip bundles first and treats soft asks as strictly subordinate; a soft ask on an already-declined field would silently cost a unit while returning status declined, so declined fields are filtered before spending.

**Value of information, tested honestly.** We implemented a truth-blind VoI gate that enumerates the public answer space for a candidate soft ask and spends the unit only if some hypothetical answer would change the day's selected allocation. Completed result (576 episodes, four arms, seeds 119–142): the gate did concentrate spending — 76.6% of its asks were decision-relevant — yet the end-to-end primary-metric effect was +0.9% with CI [−0.084, +0.091], and the preregistered stopping rules returned INCONCLUSIVE → keep greedy. The mechanism was precise but the objective did not follow.

**What the negative result teaches (and the open hypothesis).** An answer changes the objective only if it changes *which pairs date* in a way that changes conversions; within-day re-ranking of an already-selected batch cannot help (the same principle that killed the graph-optimization variant). The untested successor, proposal n03, moves selection into the temporal dimension: use ask_log and feedback history to choose which soft field of which member is worth revealing next (e.g., fields whose observed answers have historically discriminated converting from non-converting pairs in this scenario), optionally persisted in memory. Limitations to disclose in advance: history is thin early (cold_start), declined fields permanently shrink the target pool, answers on late-episode asks may arrive after their decision value has passed, and VoI enumeration itself must stay within the per-invoke latency budget (a deterministic evaluation cap applies).

---

## G. Baselines and evaluation plan

**Official baselines (verified in `kit.py` and `evaluate.py` before description).** All comparisons use the three supplied baselines exactly as implemented:

| Baseline | Ask phase | Match phase |
|---|---|---|
| **greedy** (incumbent) | Collects missing hard fields of available members into constraints bundles (3 units each, ≤ ⌊12/3⌋ = 4 per day, skipping members with declined constraints, in observation order) | Scores every feasible, non-past edge by the count of matching *observed* soft fields (7 fields); sorts by (−score, member ids); takes edges greedily while endpoints remain free |
| **no_asks** | No asks | Identical to greedy |
| **random** | Identical to greedy | Same feasible edge set shuffled with seeded RNG (seed 17 + day), then the same take-while-free fill |

Our learned arm (an embedded gradient-boosted ranker with tiered asks, evaluated as `ac`) is an experimental arm, not an official baseline, and is reported as such.

**Metrics.** Primary: official MSMI per 100 arrived members, equally averaged over the six families × 20 private seeds. Secondary: coverage, mutual/100, introductions/100, ask cost, conversion rates (mutual per introduction, date given mutual, MSMI given introduction), zero-selection days, and per-invocation inference latency. Six-family reporting is mandatory in every result table; a single pooled mean never appears without its per-family decomposition, because scenario-specific degradation is one of the known failure modes (Section I).

**Why secondary metrics cannot substitute for the primary.** Three completed observations establish this directly: (i) random and greedy reach near-identical coverage yet differ by 0.111 primary MSMI; (ii) a graph-optimization variant changed the selected pairs in 36/36 confirmation worlds with exactly 0.000 primary delta everywhere — behavioral difference without outcome difference; (iii) our learned arm improved per-introduction quality slightly (mutual/introduction 0.1705 vs. 0.1723 — i.e., no) while spending 2× the ask cost and landing 0.139 primary below greedy. Coverage, mutual counts and ask efficiency are guardrails and diagnostics; only realized MSMI moves the ranking.

**Paired evaluation on the same worlds.** Every comparison is paired: candidate and control run the same (seed, family) worlds, and the analysis unit is the per-world or per-seed mean *difference*. Absolute numbers are never compared across seed sets — a rule our own reports enforce (the incumbent's 0.4931 on seeds 107–118 is a different seed set from the 0.389 on seeds 101–103 and is never set against it).

**Uncertainty and robustness.** Deltas are reported with cluster-by-seed t-intervals (seeds as clusters, df = seeds − 1), Bonferroni-corrected significance levels when more than one candidate is tested, worst-family delta as a mandatory column, and win/tie/loss counts. A candidate is *credible* only if its interval clears zero on fresh confirmation seeds under the corrected level.

**Validity, reproducibility, determinism, container, latency.** Every reported run must satisfy: zero invalid episodes (any invalid episode disqualifies); identical `action_sha256` digests across reruns from the same seed (our records: 6/6 reruns, 18/18 local-vs-container); byte-parity between local and containerized policy behaviour (container: python:3.12.7-slim, read-only filesystem, network disabled, fixed CPU/memory limits); frozen artifact hashes recorded before evaluation and re-verified after; and per-invoke latency far below the 10-second hard gate (measured container medians ≈ 0.6–0.7 s for both phases).

---

## H. Experimental design

All evaluation uses the real protocol — official `evaluate.py`, six families, day-100 metrics, private seeds disjoint from any development seeds — rather than invented benchmarks.

**Phase structure (preregistered before any run).**

1. **Screening (cheap, gate-only).** All candidates run paired against control on a small fixed seed set (our completed tournament used 3 seeds × 6 families = 18 worlds, 558 episodes). Screening ranks only to *retain* candidates under a fixed rule; no winner may be declared from screening alone.
2. **Retention and freeze.** A preregistered retention rule (top-5 by full-precision paired mean, plus up to 3 diagnostic entrants with recorded reasons; a human gate may only remove) fixes the candidate set. Code is then hashed into a freeze manifest; every subsequent row must carry the pre-screening fingerprint or it is rejected.
3. **Confirmation on fresh seeds.** Retained candidates face one or two confirmation phases on untouched seeds (our completed design: 6 seeds × 6 families, then 12 seeds × 6 families = 72 paired worlds), with cluster-by-seed intervals and Bonferroni correction for the number of candidates tested. Guardrails ride alongside: coverage delta ≥ −0.05, ask cost reported, zero invalid, per-family gates.
4. **No tuning after confirmation.** Results observed at confirmation may not trigger parameter changes; any change starts a new preregistered cycle on new seeds. This rule exists because our completed tournament showed both positive screening leads (e.g., +0.0417) regressing to negative on fresh seeds (−0.0069, 99% CI [−0.0940, +0.0801]) — point estimates at small n are noise until proven otherwise.

**What counts as meaningful improvement.** A single number: the paired mean delta of primary MSMI/100 vs. control, credibly above zero on fresh confirmation seeds under the corrected interval, with all guardrails and validity gates green, and no family-level systematic loss. Secondary-metric gains, offline expected-value gains, AUC gains and within-sample wins do not qualify.

**Inconclusive results.** If the confirmation interval overlaps zero, the verdict is *inconclusive → keep the incumbent*, with the interval reported as-is. This is not a null being dressed as success: our clarification experiment ended exactly there (+0.9%, CI [−0.084, +0.091]), and the honest response was to keep greedy and record the mechanism finding (high-precision gate, no objective gain) for the next design.

**Power honesty.** With per-seed paired SD ≈ 0.24, a 12-seed confirmation resolves roughly |Δ| ≥ 0.09 at 99% confidence. Smaller true effects will be reported as inconclusive rather than hunted with more seeds until they turn significant; where feasible we extend the seed count *within the preregistered design*, never after peeking.

**Completed experimental record (chronology).** (1) Official-baseline evaluation on public seeds established the incumbent ordering (greedy 0.389 > random 0.278 > learned arm 0.250 > no_asks 0.139; 0 invalid; learned arm lost 0/3 seeds to greedy). (2) An 800-world data pipeline (259,696 labelled rows; whole-world train/validation split; leakage audits clean) produced the scoring models of Section E. (3) The four-arm clarification/scoring experiment (576 episodes) returned INCONCLUSIVE → keep greedy. (4) The 30-method tournament ran the full funnel above (30 → 4 eligible at screening → 2 confirmed-test candidates → 0 credible) across five families — pair scoring, scarcity/opportunity scoring, waiting thresholds, graph optimization, active asking — yielding the verdict *"Greedy remains the best empirically supported policy among the evaluated candidates."* (5) A decision-state autopsy replayed all 126 tournament worlds byte-faithfully (8,433 introductions, 7,560 decision days) and found 0/33 primary gate passes among 33 candidate decision-time features; the single exploratory lead (`edges_total`) failed its held-out rerun and was classified exploratory only. (6) A static audit located residual headroom (score–value Spearman 0.12; +18.7% offline bound under full reveal), framing the proposed work. Everything in Section E/F marked proposed (n02, n03, n04, separate second-intention head) follows from this record and has not been run.

---

## I. Expected failures and limitations

| Failure mode | Why it is plausible here | How our evaluation would detect it |
|---|---|---|
| Sparse or missing preference fields | cold_start and sparse families ship thin observations; sparse is the thinnest labelled family | Per-family primary deltas and per-family coverage; NaN-preserving scores; family-level gates flag any scenario-specific loss |
| Declined answers | Declines are permanent, shrink the askable pool, and a soft ask on a declined field still costs 1 unit | Ask-cost attribution by field status; declined-waste counter reported alongside every asking arm |
| Too few feasible reciprocal pairs | Reciprocity can empty the feasible set, especially early | Daily feasibility census, coverage, and zero-selection-day counts (instrumented since the tournament) |
| Poor calibration / score misalignment | Completed: model log-loss worse than constant prevalence; score–value Spearman 0.12 | Scores used only for ranking; calibration tables published; any threshold-style use of scores is prohibited by design |
| Selective labels / unknown counterfactuals | Only introduced pairs are labelled; un-introduced pairs are unknown, not negative [8] | Whole-world splits, temporal masking, forbidden-name audits, and sealed-world byte-faithful replay before any label analysis; no causal claims from observational rows |
| Delayed / censored outcomes | 7-day response deadlines; second intention only observable after a date | Day-100 evaluation with 40-day action-less follow-up; maturity checks (0 immature rows in completed runs) |
| Waiting too long | Completed: every unconditional drop-pair rule failed on cold_start/delayed | Scarsity guard on waiting; zero-selection days and coverage reported as guardrails; per-family deltas expose cold_start regression first |
| Over-aggressive matching | Filling batches with low-value pairs wastes members' response windows and dilutes conversion | Conversion-rate secondaries (mutual per introduction, MSMI given introduction) plus mutual no-harm guardrail |
| Scenario-specific degradation | Six families stress different mechanics (shift, drift, delayed) | Mandatory worst-family column; a candidate with any catastrophic family is ineligible regardless of pooled mean |
| Seed variance and winner's-curse selection | Completed: +0.0417 and +0.0278 screening leads both regressed on fresh seeds | Screening never declares winners; frozen candidate sets; fresh-seed confirmation with Bonferroni-corrected intervals |

**Broader limitations we state openly.** The completed tournament explored heuristic, scoring, allocation, waiting and asking *variants* — roughly 30 mechanisms, several behaviorally identical to control — and did not exhaust the space of sequential policies; its keep-greedy verdict is scoped to "evaluated candidates" for that reason. The decision-state autopsy's conclusion B means we currently have no validated decision-time feature signal, which weakens any proposal built on per-day personalization until n02/n03 supply new evidence. Offline expected-value improvements have repeatedly failed to transfer (the static +18.7% bound vs. the live +0.9% inconclusive), so we treat every offline number in this document as motivation, never as a forecast. Finally, with confirmation designs resolving only effects ≈ 0.09 or larger, a genuine but small improvement would surface as a string of inconclusive confirmations; we accept that outcome rather than relax the standard.

---

## J. References

[1] Romeo & Juliet Ltd. × IIT Madras. *The Sequential Matching Problem — Problem Statement*, v1.0.0, 5 October 2026. Repository: `github.com/RomeoJulietLove/The-Sequential-Matching-Problem` (with `docs/DATA_CONTRACT.md`, `docs/POLICY_INTERFACE.md`, `docs/SUBMISSION.md`). **Primary source for all benchmark rules, metric definitions, baselines, and horizons cited in this document.** Assumptions: it defines the synthetic world; nothing here overrides it.

[2] Gale, D., and Shapley, L. S. (1962). College Admissions and the Stability of Marriage. *The American Mathematical Monthly*, 69(1), 9–15. DOI: 10.1080/00029890.1962.11989827. — Foundational framing for *mutual* acceptance between two-sided agents. **Differs:** complete one-shot preference lists, static matching, no arrivals, no information budget — our setting adds sequential arrival, costly elicitation, and delayed outcomes.

[3] Karp, R. M., Vazirani, U. V., and Vazirani, V. V. (1990). An Optimal Algorithm for On-Line Bipartite Matching. *Proceedings of the 22nd ACM Symposium on Theory of Computing (STOC '90)*, 352–358. DOI: 10.1145/100216.100262. — The classic online-arrival matching guarantee (the Ranking algorithm) motivating arrival-aware, non-overlapping allocation. **Differs:** one-sided assignments with immediate acceptance and no clarification actions; no reciprocity or delayed feedback.

[4] Munkres, J. R. (1957). Algorithms for the Assignment and Transportation Problems. *Journal of the Society for Industrial and Applied Mathematics*, 5(1), 32–38. DOI: 10.1137/0105003. — Maximum-weight bipartite matching is the natural tool for choosing a non-overlapping daily batch once scores exist. **Differs:** batch solution with complete information; our sequential value depends on scores that are themselves uncertain and partially revealed — which is why our completed evidence gates graph allocation (Section E, RQ3) behind score alignment.

[5] Li, Q., Wang, J., and Yan, X. (2023). Fully Online Matching with Stochastic Arrivals and Departures. *Proceedings of the AAAI Conference on Artificial Intelligence*, 37(10), 12014–12021. DOI: 10.1609/aaai.v37i10.26417. — Closest formal model of our arrival/departure dynamics under uncertainty. **Differs:** no bilateral acceptance test, no ask budget, no delayed censored outcomes; it informs timing intuition, not the reciprocal-clarification core.

[6] Howard, R. A. (1966). Information Value Theory. *IEEE Transactions on Systems Science and Cybernetics*, 2(1), 22–26. DOI: 10.1109/TSSC.1966.300074. — The economic frame for spending ask units only where information can change a decision; direct ancestor of the VoI gate in Section F. **Differs:** assumes decisions with computable expected value of information; our value of an answer is bounded by whether it changes a non-overlapping batch under a daily budget — measured, not assumed.

[7] Golovin, D., and Krause, A. (2011). Adaptive Submodularity: Theory and Applications in Active Learning and Stochastic Optimization. *Journal of Artificial Intelligence Research*, 42, 427–486. — Supplies conditions under which greedy adaptive information gathering is near-optimal, framing H1/H3's tiered ask order. **Differs:** guarantees require (adaptive) submodularity of the objective; our realized-MSMI objective is not established to have this property, and the completed tournament's flat asking results are consistent with it failing — treated as an open assumption.

[8] Lakkaraju, H., Kleinberg, J., Leskovec, J., Ludwig, J., and Mullainathan, S. (2017). The Selective Labels Problem: Evaluating Algorithmic Predictions in the Presence of Unobservables. *Proceedings of the 23rd ACM SIGKDD International Conference on Knowledge Discovery and Data Mining (KDD '17)*, 275–284. DOI: 10.1145/3097983.3098066. — Names our central evaluation hazard: outcomes exist only for selected actions, so un-introduced pairs are counterfactuals. **Differs:** offline classification with historical decisions; we mitigate through sealed-world replays and paired live evaluation rather than counterfactual estimators.

[9] Palomares, I., Porcel, C., Pizzato, I. D., Guy, I., and Herrera-Viedma, E. (2021). Reciprocal Recommender Systems: Analysis of State-of-Art Literature, Challenges and Opportunities Towards Social Recommendation. *Information Fusion*, 69, 103–127. — Survey anchoring reciprocal recommendation as a distinct problem class where both parties' preferences must be satisfied. **Differs:** focuses on offline top-N list generation; our constraints are sequential feasibility, budgets and time.

[10] Yang, C., Dai, B., Hou, Y., Zhao, H., Xu, J., Song, Y., and Zhu, W. (2024). Revisiting Reciprocal Recommender Systems: Metrics, Formulation, and Method. *Proceedings of the 30th ACM SIGKDD Conference on Knowledge Discovery and Data Mining (KDD '24)*, 3714–3723. DOI: 10.1145/3637528.3671734. — Recent formulation and evaluation of bilateral (mutual) acceptance prediction, informing our separation of directional, mutual, and downstream targets in Section E. **Differs:** no sequential horizon, no ask budget, no non-overlapping allocation.

**Attribution.** This analysis, implementation, and manuscript were produced with the assistance of AI coding/analysis tools; all empirical numbers come from this repository's own experiment artifacts, all rule statements trace to the official specification [1], and third-party libraries (numpy, scipy, scikit-learn, for offline research only — the submitted policy container is pure Python) are acknowledged here. External ideas are summarized in our own words; no text passages are reproduced.

---

## K. Conclusion

We proposed a constraint-first sequential policy for the MSMI objective: reciprocal feasibility filtering, budgeted clarification ordered by feasibility-flip value and gated by decision relevance, bilateral pair scoring with precisely named probability targets, non-overlap allocation with coverage as a guardrail, and scarcity-guarded waiting — organized as four research questions (scoring, clarification, allocation, timing), each independently testable against the incumbent.

The evaluation standard is deliberately stricter than the experiments that motivate it. Completed work — the baseline evaluation, the 576-episode clarification experiment, the 30-method tournament, and the decision-state autopsy — has so far failed to produce a credible improvement over greedy, and we report that as the standing result rather than searching for a more flattering summary. The proposed work (feedback-reweighted scoring, feedback-adaptive asking, guarded lookahead waiting) targets exactly the surfaces those experiments left unconsumed: history, memory, and cross-day value.

Evidence that would justify adopting a more sophisticated policy is a single, pre-specified package: a positive paired primary delta over greedy that clears a Bonferroni-corrected cluster-by-seed interval on untouched confirmation seeds, with zero invalid episodes, green determinism/container checks, acceptable latency, coverage delta ≥ −0.05, and no catastrophic scenario family — replicated once under a fresh preregistration. Failing any element of that package, the correct decision under our own protocol is to keep greedy, and we would report it as such.