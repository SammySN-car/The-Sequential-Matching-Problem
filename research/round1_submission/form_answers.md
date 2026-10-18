# Google Form Answers — The Sequential Matching Problem: Research Submission

Copy-paste-ready answers under the form's exact headings. Deadline: 9 October 2026, 23:59 IST. Do not submit this file — paste from it.

---

## 1. Brief summary of our approach

We treat the challenge as a sequential decision problem and test a **constraint-first policy**: each day we (1) filter candidate pairs by *reciprocal* hard feasibility using only known field values — unknowns route to clarification, declined answers are permanent and never imputed; (2) spend the 12-unit ask budget selectively, funding constraints bundles first when an answer can flip a specific pair's eligibility, and soft-field asks only when a value-of-information gate shows the answer could change the day's allocation; (3) rank feasible pairs with a bilateral score built over observed soft fields; (4) select a non-overlapping batch; and (5) explicitly decide match vs. ask vs. wait, with waiting allowed only under an arrival-scarcity guard. Our hypothesis is falsifiable: this pipeline improves realized MSMI per 100 arrived members over the supplied greedy baseline. We do not assume it does — greedy is the incumbent, and our completed experiments (a 30-method tournament, a 576-episode clarification experiment, and a decision-state autopsy) currently support keeping it. The proposal states precisely what is completed, what is proposed, and what evidence would justify adopting a more sophisticated policy.

## 2. Key papers / references considered

- **Official challenge specification** (PROBLEM_STATEMENT v1.0.0, repo `RomeoJulietLove/The-Sequential-Matching-Problem`) — authority for metric, baselines, and protocol.
- **Gale & Shapley (1962)**, *The American Mathematical Monthly* 69(1) — two-sided mutual acceptance; static, no budgets or arrivals.
- **Karp, Vazirani & Vazirani (1990)**, STOC '90 — online matching under arrivals; one-sided, no clarification.
- **Munkres (1957)**, *J. SIAM* 5(1) — maximum-weight assignment for non-overlap batches; batch, full information.
- **Li, Wang & Yan (2023)**, AAAI 37(10) — fully online matching with arrivals and departures; no reciprocity or asks.
- **Howard (1966)**, *IEEE TSSC* 2(1) — information value theory; basis of our ask-cost reasoning.
- **Golovin & Krause (2011)**, *JAIR* 42 — adaptive submodularity and greedy information gathering; our objective is not established to satisfy its assumptions.
- **Lakkaraju et al. (2017)**, KDD '17 — the selective-labels problem; outcomes exist only for chosen introductions.
- **Palomares et al. (2021)**, *Information Fusion* 69 and **Yang et al. (2024)**, KDD '24 — reciprocal recommender systems: bilateral compatibility formulation and metrics; offline list settings, no sequential budgets.

All bibliographic details were verified against publisher records (title, authors, year, venue, DOI).

## 3. Proposed method / algorithms

Layered pipeline (each layer independently ablatable): **legal-state observation** (temporal masking, NaN preserved) → **reciprocal feasibility filter** (feasible / needs-clarification / ineligible; scoring only on the feasible subgraph) → **tiered selective clarification** (blocked-flip hard bundles → progressive completion → VoI-gated soft asks; costs 3/1, budget 12/day) → **bilateral pair scoring** (count-based incumbent rule vs. transparent analytic weighted score vs. optional learned ranker; probability targets named separately: p(mutual), p(date), p(second-yes), composite p(MSMI) — used strictly as ranking scores because calibration is known to be imperfect) → **non-overlap allocation** (deterministic sort + take-while-free, optional strict-improvement swaps; coverage is a guardrail) → **match/ask/wait decision** with a scarcity guard on waiting → **compact memory** (≤1 MiB) for history-driven scoring and adaptive asking, which our audit shows is an untested surface. Work is organized as four research questions — scoring, clarification, allocation, timing — with proposed-but-untested next steps: feedback-reweighted pair scores (n02), feedback-adaptive soft-field selection (n03), and guarded lookahead waiting (n04).

## 4. How will you evaluate your approach?

Against the three official baselines **greedy** (hard-field bundle asks + count-of-observed-matching-soft-fields scoring with take-while-free non-overlap fill), **no_asks**, and **random** (same asks, seeded edge shuffle), all executed by the official `evaluate.py`. **Primary metric:** official MSMI per 100 arrived members, equally averaged over the six scenario families × 20 private seeds (120 episodes); **secondary/guardrails:** coverage, mutual/100, introductions, ask cost, conversion rates, per-family deltas. Comparisons are **paired on the same worlds** with cluster-by-seed t-intervals and Bonferroni correction for multiple candidates; screening (18 worlds) is gate-only, the candidate set and code are **frozen**, then confirmation runs on **untouched fresh seeds** (up to 72 paired worlds) with no post-confirmation tuning. Adoption criterion: positive primary delta clearing the corrected interval on fresh seeds, 0 invalid episodes, determinism and local/container parity green, latency well under the 10 s gate, coverage delta ≥ −0.05, no catastrophic family. Anything less → inconclusive → keep greedy.

## 5. GitHub or Colab or supporting material link

All material is contained in the uploaded research proposal (research_proposal.pdf) and its accompanying artifacts from our local research repository. We are not supplying an external link at this time, and we do not present the organisers' starter repository as our own work.

<!-- Optional: if the team has its own pinned public repository before the deadline, replace the paragraph above with its fixed-version URL. -->

## 6. Anything else reviewers should know?

- **Chronology is explicit.** The proposal separates completed experiments (baseline evaluation; 800-world dataset and scoring models; 576-episode VoI/clarification experiment — preregistered verdict INCONCLUSIVE; 30-method tournament — verdict "greedy remains the best empirically supported policy among the evaluated candidates"; decision-state autopsy — no supported signal) from proposed work (n02/n03/n04). Nothing untested is presented as a result.
- **Our honest position:** greedy is the incumbent and we have not beaten it; this does not prove greedy globally optimal — the tournament covered ~30 heuristic/scoring/allocation/waiting/asking mechanisms, not all sequential policies.
- **Attribution:** this work used AI coding/analysis tools; third-party libraries (numpy, scipy, scikit-learn — offline research only) were used; all rule statements trace to the official specification; external ideas are cited and paraphrased, not copied. This is offered in support of the form's acknowledgement declaration.

---

## Team metadata checklist (fill before submitting)

| Field | Value |
|---|---|
| Team Name | **[FILL IN FROM REGISTRATION]** |
| Team Leader Name | **[FILL IN FROM REGISTRATION]** |
| Registered Email | **[FILL IN FROM REGISTRATION]** (local git config hints `samarnathani0@gmail.com` — unverified, confirm before use) |
| Romeo & Juliet Code | **[FILL IN FROM REGISTRATION]** |
| College or Institution | **[FILL IN FROM REGISTRATION]** |
| Team Members | **[FILL IN FROM REGISTRATION]** (1–4 participants allowed) |