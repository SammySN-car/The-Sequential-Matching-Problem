# Technical Report - The Sequential Matching Problem (Round 2 final build)

Team: RomeoJulietLove | Release: 1.0.0 | Report date: 16 October 2026

All numbers below were re-verified against the files cited next to them during report preparation. File paths are relative to the repository root. Evidence classes are used throughout: **[V] verified engineering correctness**, **[C] descriptive or causal finding**, **[P] policy-level (descriptive) evidence**, **[I] inconclusive statistical comparison**.

## 1. Executive summary and final submitted policy

The submitted policy is the kit's **greedy baseline**, kept as the default entrypoint of `policy.py` (`decide(request, mode='greedy')` and `--baseline` default `greedy`), as required by Round 2 spec section 8. It performs hard-constraint clarification asks (`kit.baseline_asks`) and count-score maximum matching over reciprocal-feasible edges (`kit.baseline_match`), reading only the observable decision state.

This choice is the outcome of the research programme, not a default of convenience: across roughly 25 experiments, a 30-method tournament (985 recorded method-episodes) and a pre-registered paired evaluation on 100 seed groups, **no tested alternative established a statistically reliable improvement over greedy**. Two claims that initially looked positive were withdrawn after self-audit (a sign defect; an oracle/leakage artifact). One substantial engineering result - an exact-cardinality blossom solver that fixed a genuine deployability failure - produced an **inconclusive** policy-level evaluation (delta +0.00417 MSMI/100, 95% CI [-0.0483, +0.0583]) and is therefore reported as an asset, not a claimed improvement.

All five official validation commands pass (exit 0): unit tests (144 ran, OK), data verification (`verified: true`), final evaluation (18/18 valid episodes), Docker build, and container evaluation (valid, digest-identical to local). See README.md for the command/evidence table and `results/final.json`, `results/container_check.json`.

## 2. Problem and simulator constraints

- Episodes: 60 decision days + 40-day follow-up, 200 arrived members per episode, six scenario families (`development, sparse, cold_start, delayed, shift, drift`) - `evaluate.py` L16, L100-107.
- Each day the policy answers an `ask` phase (clarification requests, budgeted and costed) and a `match` phase (a set of disjoint pairs). Reciprocal eligibility is computed from observable fields only; hidden simulator state is contractually and test-enforced off-limits (observation contract, PROBLEM_STATEMENT.md section 11; `test_runner.py` asserts the policy never receives world fields).
- Feedback arrives delayed and partially missing; day-30 snapshots are not observations from earlier decisions.
- Ranking: `evaluate.summarise` produces `primary_score` (MSMI per 100 arrived members, averaged over the six families) and `ranking_key_descending = [primary, coverage, mutual_acceptances_per_100, -ask_cost, -inference_seconds]` - confirmed from the key recorded in `results/final.json`.
- Assessment runs offline in Docker (no network, no GPU, 10 s per decision, no host mounts); a container build must succeed without credentials (docs/SUBMISSION.md L52).

## 3. Policy design and observable information

**Submitted path (greedy).** For each match phase, enumerate reciprocal-feasible, available, not-yet-introduced pairs from the observable state, score them with the kit's count-based features, and take a maximum matching; for each ask phase, emit the kit's hard-constraint clarification requests. The path uses no randomness (deterministic), no learned asset and no file/network I/O; policy memory is passed explicitly by the evaluator and reset between episodes. `policy.py` imports only the standard library plus `kit`.

**Research path (not the submission default).** The same `policy.py` also contains an optional `ac` mode: a pre-trained gradient-boosted model (44 observable features, embedded compressed blob, schema-validated at load) plus an empirical score floor that filters candidate edges before matching. It is invoked only via `--baseline ac` or the `policy_ac.py` shim, and produced the fourth arm of the comparison in `results/ac.json`. The submitted container entrypoint never executes it (`ENTRYPOINT ["python","policy.py"]`, default mode greedy; `.dockerignore` ships only `kit.py`, `policy.py`, `Dockerfile`).

## 4. Evaluation methodology, seeds, variants and scoring

**Official runs (this submission, 16 October 2026):**

```bash
python -m unittest -v                                                    # PASS, exit 0
python verify_data.py                                                    # PASS, exit 0
python evaluate.py --seeds 101,102,103 --variants all --output results/final.json            # PASS, exit 0
docker build -t sequential-policy:submission .                           # PASS, exit 0
python evaluate.py --image sequential-policy:submission --seeds 101 --output results/container_check.json  # PASS, exit 0
```

`results/final.json`: seeds 101-103 x all six variants = 18 full episodes, all `valid: true`, primary 0.3888888. `results/container_check.json`: seed 101 x `development` = 1 episode, `mode: container`, all decisions within the 10 s limit, `action_sha256` identical to the local run of the same episode (1/1 parity).

**Four-arm comparison (historical, 7 October 2026):** `results/{greedy,no_asks,random,ac}.json`, each 18 episodes over the identical (seed, variant) grid 101-103 x 6 - programmatically verified identical across arms. Generation commands and exit codes are recorded in the local, non-submitted `results/run_log.txt`.

**Statistical practice.** Research comparisons used pre-registered paired designs clustered on seed (percentile bootstrap, B = 10,000, fixed bootstrap seed), reported with 95% CIs and win/tie/loss counts. The official 18-episode runs are **smoke-scale**: per examples/REPORT_GUIDE.md L14 such reference-scale runs are "not statistically reliable performance claims". No confidence interval is claimed for the four-arm numbers in section 5; they are descriptive.

## 5. Scenario-level outcomes and four-arm comparison [P]

All values are means over 18 episodes (seeds 101-103 x 6 variants) from `results/*.json` `summary.overall` / `summary.scenario_means`.

| Arm | MSMI/100 (primary) | Coverage | Mutual acceptances/100 | Ask cost/ep | Descriptive rank on primary |
|---|---|---|---|---|---|
| greedy (submitted) | **0.3889** | 0.3717 | 5.50 | 206.7 | 1 of 4 |
| random-feasible | 0.2778 | 0.3767 | 5.33 | 206.7 | 2 of 4 |
| A+C research arm (`ac`) | 0.2500 | 0.3503 | 4.58 | 419.4 | 3 of 4 |
| no-clarification | 0.1389 | 0.1428 | 1.75 | 0.0 | 4 of 4 |

MSMI/100 by scenario family:

| Arm | development | sparse | cold_start | delayed | shift | drift |
|---|---|---|---|---|---|---|
| greedy | 0.500 | 0.167 | 0.167 | 0.500 | 0.500 | 0.500 |
| no_asks | 0.167 | 0.000 | 0.000 | 0.333 | 0.167 | 0.167 |
| random | 0.333 | 0.167 | 0.167 | 0.167 | 0.500 | 0.333 |
| ac | 0.167 | 0.000 | 0.167 | 0.500 | 0.500 | 0.167 |

Reading: clarifications matter enormously (removing them costs 0.25 MSMI/100 and 0.23 coverage); random-feasible matching is competitive with greedy on this seed grid (0.278 vs 0.389 primary, overlapping scenario pattern); A+C costs roughly double the clarification budget and does not outperform greedy here. These are descriptive differences on 18 episodes - consistent with the larger research record (section 9), which found no reliable alternative to greedy.

**Per-seed variation (REPORT_GUIDE item 5).** Each cell is the mean over the six scenario variants for that seed (one episode per seed x variant, drawn from the same 18-episode files above - no new runs). Scenarios stay separate from the seed dimension and are shown in the table above; the funnel metrics (served/unserved members, waits, ask cost, missing feedback) remain pooled in section 6 rather than duplicated at this sample size.

| Seed | greedy (submitted) | random-feasible | A+C research arm (`ac`) | no-clarification |
|---|---|---|---|---|
| 101 | 0.500 | 0.250 | 0.417 | 0.333 |
| 102 | 0.333 | 0.500 | 0.083 | 0.000 |
| 103 | 0.333 | 0.083 | 0.250 | 0.083 |

What varies: greedy leads on seeds 101 and 103 and ranks second on 102; the arm ordering changes with the seed (seed-mean MSMI spans: greedy 0.333-0.500, random-feasible 0.083-0.500, A+C 0.083-0.417, no-clarification 0.000-0.333). Coverage varies much less (greedy 0.353-0.408, random-feasible 0.354-0.412, A+C 0.315-0.390, no-clarification 0.127-0.174). This is a 3-seed, 18-episode descriptive view: no confidence intervals, significance tests or generalizable ranking are claimed from it. The A+C column carries the section 10 provenance caveat (7 October source version, no digest-level re-verification against current code, not claimed bit-identical).

## 6. Coverage, waiting times, clarification costs and missing feedback [P]

Computed from the same four `results/*.json` files. `first_introduction_wait_days` is the evaluator's per-served-member delay (first introduction day minus arrival day; `evaluate.py` L103-113); `missing_feedback` is the simulator's per-episode count of missing feedback events; both are means over the 18 episodes.

| Arm | Coverage | Served members/ep (of 200) | Unserved/ep | Mean first-introduction wait (days, served members) | Ask cost/ep | Missing feedback/ep |
|---|---|---|---|---|---|---|
| greedy | 0.3717 | 74.3 | 125.7 | 6.45 | 206.7 | 45.5 |
| random | 0.3767 | 75.3 | 124.7 | 6.54 | 206.7 | 41.9 |
| ac | 0.3503 | 70.1 | 129.9 | 11.83 | 419.4 | 33.9 |
| no_asks | 0.1428 | 28.6 | 171.4 | 4.17 | 0.0 | 13.3 |

Caveats stated rather than smoothed: waits are conditioned on being served, so `no_asks` shows a shorter wait only because it serves 28.6 members instead of ~74 (selection effect, not a latency win); A+C both serves fewer members and waits longer (11.8 days) while spending twice the clarification budget; lower `missing_feedback` counts track lower introduction volume, not better feedback handling. No arm-level causal claim is made from these descriptors.

**Failure mechanisms under partial observation (PROBLEM_STATEMENT.md L224; REPORT_GUIDE items 2 and 7).** These are structural properties of the supplied simulator that bound every arm's results. No quantified score loss is attributed to any of them: no arm-level counterfactual isolating them was run.

- *Withheld or missing answers.* Clarification cannot recover everything. Declined answers stay unavailable and are never silently imputed (`kit.py` `resolve_asks` docstring, L113-114; declined fields are skipped at L127), and a member whose hard fields are still unobserved has eligibility status `needs_clarification`, so the simulator rejects any introduction that is not `feasible` (`kit.py` L87, L151). After an introduction, a non-response arrives as `value: null` with `missing_reason: 'no_response'` (`kit.py` L163-166): the policy learns only that nothing arrived - never an acceptance or a rejection. The `missing_feedback` column in section 6 counts exactly these events (`kit.py` L198), so it measures absent information, not policy quality.
- *Competition for the same candidate.* Match batches must be disjoint (`kit.py` L147-148), each introduced member is then busy for at least 8 days (`kit.py` L167, checked at L100), and an introduced pair can never be reintroduced (`kit.py` L150). Choosing one feasible pair therefore consumes both endpoints and removes the other opportunities those two members could have appeared in - an allocation trade-off inherent to disjoint matching. What that trade-off costs in outcomes is not isolated here.
- *Sparse supply, delayed feedback, incomplete observation.* The `sparse` variant scatters members across twelve zones with exactly one acceptable zone each, while normal variants use four zones and gain a second acceptable zone 30% of the time (`kit.py` L42-43, L53), thinning reciprocal zone overlap (the zone check runs in both directions, `kit.py` L77-81). Responses arrive 1-7 days late and the `delayed` family adds 5-12 more days (`kit.py` L161, L170); only 35% of members start with a complete questionnaire (20% under `cold_start`), with individual fields of the rest observed at 0.10 probability (`kit.py` L55-56). Together these cap what any policy can confirm or act on - visible in the scenario table of section 5 as a descriptive pattern, not as a measured causal loss.

## 7. Runtime and deployment validation [V]

- **Local (host Python 3.13.5):** full official evaluation of 18 episodes in 319 s wall; mean inference 15.16 s/episode = about 0.25 s per decision, against the official 10 s-per-decision limit. `test_policy` T10 latency probes: ask phase 0.50 s, match phase 0.16 s on a day-50 replay (gates < 9 s / < 9 s passed).
- **Container (`python:3.12.7-slim`, Docker 29.8.0):** image built in 5.2 s with no credentials and a build context containing only `kit.py`, `policy.py`, `Dockerfile`; container evaluation exit 0 in 65.3 s; in-container inference 60.0 s/episode (about 1 s per decision) with every decision inside the 10 s limit; episode digest byte-identical to local (1/1).
- **Test suite:** workspace final run: 144 tests in 184.3 s, `OK` (exit 0) - 81 root tests + 63 `research/test_pipeline` tests (untracked research tree present); a pre-fix run had shown `OK (skipped=1)` (the Docker-latency test skipping itself while the daemon was still down). A fresh `git clone` of the pinned commit also passes: 81 tests, `OK (skipped=8)`, exit 0 in 31.1 s - the 8 skips are the suite's guards for research-only assets (`features.py`, `export_model.py`, `collect.py`, `rows.csv`) deliberately not part of the pinned build.
- **Data integrity:** `verify_data.py` -> `verified: true`, 71 files, counts exactly matching PROBLEM_STATEMENT.md section 14. Reproduced identically in a fresh clone of the pinned commit after `.gitattributes` (`* -text`) pinned byte-stable checkout (a machine-wide `core.autocrlf` had rewritten cloned data bytes and broken the recorded hashes).

## 8. Hypothesis-driven ablation: the score-floor filter (existing experiment) [C]/[I]

**Hypothesis under test (frozen in advance):** the A+C model's empirical score floor filters low-value pairs at no cost to selection volume.

**Design** (`research/round2_stage2_floor_ablation/`): a single-attribute ablation - Arm A is the frozen A+C policy, Arm B differs only by the floor argument passed to the matcher (`floor` -> `-inf`); `purity.json` records **11/11 checks passing** (`all_pass: true`), including frozen-hash verification before the run, identical day-0 asks on all 18 shared states, and an assertion that exactly one attribute was overridden. Seeds 101-103 x 6 variants, 18 paired episodes per arm.

**Results:**
- The floor discarded most of the opportunity: pooled over the run, 1,662 of 10,144 feasible pairs (16.4%) survived it, and **411 decision-days had feasible candidates yet zero selections, all because every candidate was below the floor** (`summary.json` funnel, Arm A pooled) [C].
- Removing the floor causally restored volume: introductions +11.11/episode (+16.65%; 3-seed-cluster bootstrap interval [5.67, 16.17]), coverage +0.0194, ask cost -5.5/episode, and zero-selection days eliminated [C].
- The score effect is **not established**: MSMI/100 +0.083 (0.250 -> 0.333), per-episode wins/ties/losses 5/10/3, and the file's own bootstrap interval [0.0, 0.167] carries the explicit caveat "only 3 seed clusters - interval is descriptive, not inferential" [I].

**Conclusion:** the floor's volume suppression is a real, causally demonstrated mechanism; turning volume back into reliable MSMI gains was not demonstrated. A follow-up intermediate floor (stage 3: threshold `floor/2 = 0.0039526`) passed its pre-registered promotion gates as `READY_FOR_FROZEN_CANDIDATE` with the explicit scope note "NOT proven optimal, NOT proven to beat greedy", and on fresh seeds 107-118 confirmed the volume effect (wins in 90.28% of 72 paired worlds vs the original floor) while its MSMI contrast vs the original floor was inconclusive (+0.0278, CI [-0.118, +0.188]) and negative-point vs greedy (-0.090, CI [-0.257, +0.069]) at clearly higher ask cost (+216.7, CI [+210.8, +222.9]). It was therefore **not adopted**; the submission remains greedy (`research/round2_promotion_fresh_seeds/summary.json`).

**Secondary ablation** (`research/round2/results/summary.json`): a maximum-weight matching arm gated by model confidence was **identical to greedy on all 72 worlds** (mean 0.0, CI [0,0], W/T/L 0/72/0), while the ungated variant was negative (-0.0486, CI95 [-0.158, +0.061]). The gate, not the matcher, carries the behavior - an instructive null result [C].

## 9. Research progression, including negative and inconclusive results

1. **Round 1 - learned ranker (A+C).** 44-feature gradient-boosted scorer with a score floor, embedded in `policy.py`; frozen at SHA `379cc2d9...` for the Round-1 era runs. The four-arm comparison in `results/` originates here (7 October 2026).
2. **Method tournament - negative.** 30 candidate methods + shared control screened and confirmed over 985 recorded episodes (`research/method_tournament/per_phase/*.jsonl`: 558 screening + 180 confirm1 + 216 confirm2 + 31 smoke). Final report verdict: **zero credible survivors**, "Greedy remains the best empirically supported policy among the evaluated candidates" (`research/method_tournament/final_report.md`).
3. **Gated matching - null.** Gated MWM == greedy (0/72/0, CI [0,0]); ungated loses (see section 8) [I/C].
4. **REL "+18.7%" - demoted to an oracle upper bound.** The leakage audit verified the arithmetic (0.931 - 0.784)/0.784 = 18.75% but showed the values came from hidden truth (`m['truth']`), making the condition "an offline oracle upper bound ONLY, never a live arm" (`research/e3_rel_experiment/leakage_audit.md` L94-128, `design.md` L95-96). The live three-arm experiment was neutral: E3 vs control +0.90% relative, mean +0.0035 MSMI/100, seed-level t-95% CI [-0.084, +0.091], W/T/L 27/90/27 over 144 episodes (`research/e3_rel_experiment/summary.json`) [I].
5. **Self-audit - withdrawn claims.** An internal integrity review found a sign defect (the "count baseline" was a count *minimizer*): the headline "+13 F2 superiority, CI excluding 0" was **withdrawn as stated**; the corrected contrast is +6, CI [-0.2857, +0.9524] (includes 0), with two further claims withdrawn and one reversed (`research/round2_baseline_integrity/report.md` L45-47). This is recorded here as a correction, not a result [V/C].
6. **Floor chain - causal success, score failure** (section 8): volume suppression demonstrated; score benefit not established; `floor/2` promoted as a frozen candidate but **not adopted**, submission stayed greedy.
7. **Exact-k solver - engineering success, evaluation inconclusive.** The original branch-and-bound exact-cardinality matcher failed its frozen runtime gate: max 17.199 s on dense day-0 states with 15 node-limit aborts, `passed: false` (`research/round2_stagewise_reward/results/solver_validation.json`). It was redesigned as a polynomial exact-k solver (dummy-vertex reduction to perfect matching, BIG-weight forcing, integer-exact lexicographic tie weights, own blossom implementation): **11,200 validation cases with 0 disagreements** vs brute force, and over 6,041 real states solver max **0.050 s**, end-to-end max **0.444 s**, all pre-registered runtime gates passing (`research/round2_stagewise_reward_solver/results/{solver_validation,runtime_benchmark}.json`) [V]. The pre-registered paired policy evaluation then ran on seeds 70001-70100 (600 episodes/arm, 100 seed groups): delta **+0.00417** MSMI/100, 95% CI **[-0.0483, +0.0583]**, W/T/L 35/25/40, cardinality audit 36,000/36,000 passed, 0 invalid episodes (`paired_stats.json`); the frozen decision rule emitted **PROCEED WITH CHANGES** (experiment valid, no superiority claim) and the directory was sealed (`research/round2_stagewise_reward_solver/report.md`). The solver is reported as an engineering asset; it is **not** part of the submitted greedy path [I].
8. **Official-seed four-arm (this submission)** - section 5: greedy descriptively first on the official ranking key; no reliable-improvement claim for any alternative.
9. **Hard-Constraint Clarification Prioritization - inconclusive (negative-leaning).** Post-snapshot paired experiment on clarification recipient allocation; details in the subsection below.

### Hard-Constraint Clarification Prioritization

**Question.** The daily hard-constraint clarification budget is spent by `baseline_asks` in eligibility/coverage order. This post-snapshot paired experiment tested whether re-allocating the *same* budget by an observable "potential-opportunity unlock" score - prioritizing eligible members whose clarification can convert candidate pairs into fully observed pairs - improves realized MSMI per 100 arrived members. The candidate differs from the carried greedy path only in which eligible member receives each clarification slot, under the frozen observable-information rules (unknown is never treated as compatible; declined is never overridden; no hidden truth; matching and acceptance behavior unchanged).

**Protocol and validity.** Protocol frozen 2026-10-16 16:35 IST before any confirmatory key; 100 fresh paired seed groups (120001-120100, verified unused before the freeze) x 6 variants x 2 arms = 1200 episodes, plus a 6-key official spot-check (parity PASS); the 3-seed pilot is excluded from the endpoint. Run 1 was invalidated by one episode (environmental day-0 policy-invocation timeout under host load; the identical episode passed in isolation); the frozen recovery rule - amendment A1, with hypothesis, endpoint and decision rules unchanged - invoked a full both-arms x all-seeds rerun. Final rerun: 1206/1206 keys, **0 invalid**.

**Result (complete final rerun).** Greedy (instrumented) 0.35583 vs candidate 0.33833; paired delta **-0.01750** MSMI/100, 95% CI **[-0.06750, +0.03250]**; group directions 35 wins / 20 ties / 45 losses. Variant-level paired deltas: cold_start **+0.085** and delayed **+0.005** are the only non-negative ones (sparse -0.015, drift -0.045, development -0.050, shift -0.085).

**Intervention audit.** Budget parity is exact in both arms (116,745 spent, 38,915 asks, 18,572 distinct recipients each; identical daily ask counts and spend on all 11,255 ask-days of the 600 paired episodes). The day-level allocation did differ: 80.1% of ask-days selected different member sets (86.3% of the 68,475 member-day decisions were taken by one arm only; 15.3% of days were identical, 4.6% the same set in a different order). In every episode both arms eventually asked exactly the same member pool (each member at most once), so the experiment tested a **day-level re-allocation/timing change within a fixed askable pool** - not a change of which population is ultimately asked - and the conclusions are limited accordingly.

**Verdict: INCONCLUSIVE (negative-leaning).** Not a statistically established improvement; not an established degradation; no evidence that clarification prioritization can never help; no causal claims from diagnostics. The candidate is **not** promoted, and the validated greedy default remains the submitted policy. Supporting evidence: `results/hard_constraint_clarification_summary.json` (machine-readable) and `results/hard_constraint_clarification_notes.md` (protocol/results note with provenance hashes).

Overall research conclusion, stated exactly as the evidence supports: **the submitted greedy policy has not been shown optimal, and no tested alternative has been shown better than it.** What the record establishes is that the alternatives tried are either indistinguishable from greedy, neutral-to-negative, or supported only by intervals spanning zero. The clarification-prioritization experiment added in this revision fits the same record: it completed in full (100 paired groups, 0 invalid) and established no reliable improvement (paired delta -0.01750, 95% CI [-0.06750, +0.03250]).

## 10. Limitations, reproducibility, provenance and remaining uncertainty

**Provenance of every submitted number.**

| Artifact | Built with | Note |
|---|---|---|
| `results/{greedy,no_asks,random,ac}.json` (7 Oct 2026) | `policy.py 379cc2d9...`, `policy_ac.py 90fb9ad3...` | Only documented change since: the spec-permitted entrypoint default flip (`ac` -> `greedy` in `decide()` and `--baseline`; `research/round2/results/summary.json` `decision.entrypoint_flip`). No scoring/matching/ask logic changed. Greedy behavior re-verified: current build reproduces **18/18** historical greedy `action_sha256` digests. The `ac` arm's logic is likewise unmodified (only the two defaults changed), but unlike greedy it has no digest-level re-verification and is not claimed bit-identical. |
| `results/final.json`, `results/container_check.json` (16 Oct 2026) | `policy.py c2ea0ffc95387c3e92ee214419a0bbde3c747e053eb4f35c5477337de5178d50` | Generated by the official commands; local and container runs digest-identical (1/1). |
| Container image `sequential-policy:submission` | `Dockerfile` (python:3.12.7-slim), manifest `sha256:033d5631a6cdd6d0772661a4d3905bba5197e7cb99f4cf77f628040788a05fcd` | Offline, no credentials, allowlisted build context. |
| `results/hard_constraint_clarification_summary.json`, `results/hard_constraint_clarification_notes.md` (17 Oct 2026) | Post-snapshot clarification experiment (instrumented greedy clone + allocation candidate) through the unmodified `evaluate.py`; research-workspace SHA-256 `70640992...` (protocol), `cb26d8f3...` (rerun records), `278ebb03...` (analyzer output) | Final rerun 1206/1206 keys, 0 invalid; the run-1 invalid episode is disclosed in section 9 and the notes. Documentation and evidence only - no executable artifact changed. |

**Limitations.**
- The official-seed comparisons (18 episodes/arm) are smoke-scale and descriptive; the research-grade intervals that matter all span zero (sections 8-9). Small true effects (well under about 0.05 MSMI/100 at n=100 paired seed groups, judging by the observed CI half-width of 0.053) cannot be resolved by any run performed here.
- The submitted policy inherits the kit's count-based score: nothing in this report demonstrates that score is rank-optimal, and the random-feasible arm's competitiveness on official seeds is a reminder that these seeds are weak discriminators.
- Research artifacts (`research/`, ~500 MB, including sealed experiment directories) are deliberately **not** part of the pinned commit; numbers cited from them are reproducible from the workspace but will not be publicly inspectable alongside the commit. The clarification experiment's compact summary and notes (17 Oct 2026) are the exception: they were added under `results/` so that experiment's headline numbers and protocol identifiers are inspectable without the research tree.
- Host (Python 3.13.5) and container (3.12.7) environments differ; action digests matched across both, but only the greedy path was cross-checked this way.
- Environment/determinism: greedy is RNG-free; no `PYTHONHASHSEED` pin is required for it. Timing figures are single-run measurements on one machine.
- `organise.py` (private holdout preparation) was never executed in this workspace; no private data exists here to leak.
- Two packaging corrections were made only after a fresh-clone validation exposed them, each minimal and re-validated: seven `test_policy.py` tests now skip cleanly when the untracked `research/` tree is absent (workspace behaviour unchanged - all 144 still run), and `.gitattributes` (`* -text`) pins byte-stable checkout so the recorded data checksums survive any cloner's `core.autocrlf`. Neither touches policy behaviour; commands C-E were unaffected and their evidence stands on unchanged source bytes.

**Real-world scope (REPORT_GUIDE item 8).** Every outcome reported here was produced inside the supplied invented simulator - the evaluator labels each episode `simulated_not_observed_product_performance` (`kit.py` L203) - and the policy has been evaluated only in this synthetic environment. These results cannot establish how real people would behave, consent, form relationships or be compatible, and no such claim is made. Any later authorised integration must use the documented adapter in `docs/INTEGRATION.md` (opaque ID mapping, explicit handling of unknown or declined answers, server-side re-validation of every batch, suggestions returned for human review) and must undergo the organiser's required validation on authorised inputs before use; this repository supplies no production licence (`docs/INTEGRATION.md`, final paragraph).

**Remaining uncertainty, in one sentence:** we have verified that the submitted build is correct, fast, deterministic and spec-compliant; we have *not* established that greedy is optimal, that any tested alternative is better, or that the demonstrated mechanisms (floor suppression, gate equivalence) would generalize beyond the seeds and variants studied.

## Evidence classification summary

| Class | Representative claims |
|---|---|
| [V] Verified engineering correctness | 144-test suite pass; data verification; 11,200-case exact-k validation (0 disagreements); 6,041-state runtime benchmark (0.050 s / 0.444 s max); container build + offline run + 1/1 digest parity; 18/18 cross-version greedy digest match; 11/11 ablation purity checks |
| [C] Descriptive or causal findings | Score floor causally suppresses selection volume (16.4% of feasible pairs survive; 411 zero-selection days) and its removal restores volume (+16.65%); the confidence gate - not the matcher - explains gated-MWM's equivalence to greedy; the "+13" claim was a sign defect, the "+18.7%" claim an oracle artifact |
| [P] Policy-level (descriptive) evidence | Four-arm outcomes and coverage/wait/cost/missing-feedback tables on seeds 101-103; tournament verdict (0 credible survivors of 30 methods, 985 episodes) |
| [I] Inconclusive statistical comparisons | Exact-k paired delta +0.00417 CI [-0.0483, +0.0583]; floor/2 vs original +0.0278 CI [-0.118, +0.188]; floor/2 vs greedy -0.090 CI [-0.257, +0.069]; live E3 vs control +0.90% CI [-0.084, +0.091]; corrected F2 vs count +6 CI [-0.286, +0.952]; ungated MWM -0.0486 CI [-0.158, +0.061]; clarification allocation -0.01750 CI [-0.06750, +0.03250] |