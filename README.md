# The Sequential Matching Problem - Team MayNerd's full story

This branch (`full-story`) is the complete public record of team **MayNerd**'s work on the Sequential Matching Problem challenge: the frozen final submission, the research programme behind it (24 folders of experiments and audits), the journey documents, and the outcome - including everything that did not work. A stranger should be able to read this page alone and understand what was built, what the numbers were, and how to reproduce them.

## 1. What this repo is, and the three branches

This repository is team MayNerd's fork (`SammySN-car/The-Sequential-Matching-Problem`) of the challenge kit. It carries three branches, each with a different job:

| Branch | What it holds |
|---|---|
| `main` | The original challenge material as supplied by the organisers (`a8e26b3`). Untouched. |
| `round2-final-submission-corrected` | The frozen submitted work (`f9796de`). This is the assessed record cited by the team's final submission; the branch is never rewritten. |
| `full-story` | **This branch.** The whole story: the frozen submission tree from `round2-final-submission-corrected`, plus the research programme, `docs/journey/`, and this README. |

The team is **MayNerd**. The technical report that shipped with the submission is [`REPORT.md`](REPORT.md); it is preserved here unchanged, and the README visitors saw at submission time (with the full environment, seeds and provenance tables) still exists on `round2-final-submission-corrected`. This branch replaces it with the story.

## 2. The problem

The challenge is a synthetic relationship-matching problem. A policy watches people arrive, learns about them through costed clarifications, and decides who to introduce to whom:

- Each simulated episode has 200 members who arrive by decision day 59, runs 60 decision days plus a 40-day follow-up, and starts with empty policy memory (`PROBLEM_STATEMENT.md` section 10, `evaluate.py`).
- Every day the policy makes two kinds of decision: which clarification ("ask") requests to send from a limited, costed budget, and which disjoint set of introductions ("matches") to propose.
- Reciprocal eligibility must be established from the observable fields alone. Hidden simulator state is contractually and test-enforced off-limits.
- Feedback arrives late and is often missing: a declined answer stays declined, and a non-response never turns into an acceptance or rejection.
- Episodes are scored as MSMI per 100 arrived members - mutual second-meeting intentions - averaged over six scenario families (`development`, `sparse`, `cold_start`, `delayed`, `shift`, `drift`), with coverage, mutual acceptances, ask cost and inference time as tie-breakers.

Everything is invented: the evaluator labels each episode `simulated_not_observed_product_performance`, and no real people or real data are involved. The full statement is in [`PROBLEM_STATEMENT.md`](PROBLEM_STATEMENT.md) (or [the PDF](docs/PROBLEM_STATEMENT.pdf)).

## 3. The final policy and the headline numbers

**The submitted policy is the kit's stock greedy baseline** - hard-constraint clarification asks (`kit.baseline_asks`) plus a count-score maximum matching over reciprocal-feasible, available pairs (`kit.baseline_match`) - kept as the default entrypoint of [`policy.py`](policy.py) (`decide(request, mode='greedy')`, `--baseline` default `greedy`), as required by Round 2 spec section 8. It reads only the observable decision state, is fully deterministic (no randomness, no learned asset, no file or network I/O), and its local and container runs are digest-identical (1/1). The optional A+C research model also lives in `policy.py`, but it is never the submitted default and is never executed by the container entrypoint.

This was the conclusion of the research programme, not a default of convenience - and it is stated exactly as the evidence supports: **No tested alternative established a statistically reliable improvement over greedy.**

The four-arm comparison on the official seed grid (seeds 101-103 x all six variants = 18 episodes per arm, from `results/{greedy,no_asks,random,ac}.json`, 7 October 2026) is small and descriptive - no confidence interval is claimed from it:

| Arm | MSMI/100 (primary) | Coverage | Mutual acceptances/100 | Ask cost/episode |
|---|---|---|---|---|
| greedy (submitted) | **0.3889** | 0.3717 | 5.50 | 206.7 |
| random-feasible | 0.2778 | 0.3767 | 5.33 | 206.7 |
| A+C research arm (`ac`) | 0.2500 | 0.3503 | 4.58 | 419.4 |
| no-clarification | 0.1389 | 0.1428 | 1.75 | 0.0 |

Two readings are worth stating plainly: clarifications matter enormously (removing them costs 0.25 MSMI/100 and 0.23 coverage), and the A+C research arm spends roughly double the ask budget without beating greedy here. `REPORT.md` section 5 also notes that random-feasible matching is competitive on this seed grid - these 18 episodes are a weak discriminator, which is why the serious comparisons were run at research scale.

The research-grade paired evaluation of the exact-cardinality blossom solver (`research/round2_stagewise_reward_solver/`) came back **inconclusive**: delta **+0.00417** MSMI/100, 95% CI **[-0.0483, +0.0583]** over 100 paired seed groups (600 episodes per arm; full precision `+0.0041667`, CI `[-0.0483333, +0.0583333]`, in `research/round2_stagewise_reward_solver/results/paired_stats.json`). Its frozen decision rule emitted PROCEED WITH CHANGES: a valid experiment with no superiority claim. The solver is reported as an engineering asset, not as a policy improvement, and it is not part of the submitted greedy path.

The post-snapshot hard-constraint clarification prioritization experiment (100 paired seed groups x 6 variants x 2 arms, seeds 120001-120100; 1206/1206 keys valid, 0 invalid) was **negative-leaning and inconclusive**: paired delta **-0.01750** MSMI/100, 95% CI **[-0.06750, +0.03250]**; the candidate was not promoted. Evidence: [`results/hard_constraint_clarification_summary.json`](results/hard_constraint_clarification_summary.json) and [`results/hard_constraint_clarification_notes.md`](results/hard_constraint_clarification_notes.md).

`REPORT.md` states the overall conclusion as: "the submitted greedy policy has not been shown optimal, and no tested alternative has been shown better than it" - the alternatives tried are either indistinguishable from greedy, neutral-to-negative, or supported only by intervals spanning zero.

## 4. How we got there

1. **Round 1 - the learned ranker (A+C).** The team first built the data pipeline (`research/out/`, `research/out_scale800/`: 3,520 rollouts at the pre-registered 800-world scale), then a 44-feature gradient-boosted pair scorer with an empirical score floor, embedded in `policy.py`. The four-arm comparison above originates here; the Round-1 era policy is frozen at `policy.py 379cc2d9...`. Records: [`docs/journey/round1-research-record.md`](docs/journey/round1-research-record.md), [`docs/journey/round1-research-ledger-verbatim.md`](docs/journey/round1-research-ledger-verbatim.md), [`docs/journey/plans/2026-10-06-a-plus-c-policy.md`](docs/journey/plans/2026-10-06-a-plus-c-policy.md), [`docs/journey/specs/2026-10-06-a-plus-c-policy-design.md`](docs/journey/specs/2026-10-06-a-plus-c-policy-design.md).
2. **Method tournament.** 30 candidate methods plus a shared greedy control, screened and confirmed over 985 recorded method-episodes (558 screening + 180 confirm1 + 216 confirm2 + 31 smoke) on fresh seeds, with two finalists in a 72-world Phase 3. Result: **0 credible survivors; greedy retained.** See [`docs/journey/plans/2026-10-08-method-tournament.md`](docs/journey/plans/2026-10-08-method-tournament.md) and `research/method_tournament/final_report.md`.
3. **Stagewise explorations.** Diagnostics and audits followed: the stage-1.5 read-only probe of the frozen A+C policy on seed 101 ([`docs/journey/round2-stage1.5-findings.md`](docs/journey/round2-stage1.5-findings.md)), the score-floor ablation, an intermediate floor, a history/cold-start audit, fixed-cardinality and decision-ceiling studies, an outcomes-per-request estimator audit, and an internal baseline-integrity review. All of it is indexed folder by folder in [`research/README.md`](research/README.md).
4. **Reward models and the first exact-k solver.** A three-stage reward pipeline with an exact-cardinality matching solver was built for a final paired evaluation - and stopped: the original branch-and-bound matcher failed its frozen runtime gate (max 17.199 s on dense day-0 states, with 15 node-limit aborts), so the pre-registered stop rule fired and the final evaluation was skipped (`research/round2_stagewise_reward/report.md`).
5. **Solver rewrite - blossom-based exact-k.** The matcher was rewritten as a polynomial exact-k solver (dummy-vertex reduction to perfect matching, big-weight forcing, integer-exact lexicographic tie weights, its own blossom implementation). It validated cleanly: 11,200 validation cases with 0 disagreements against brute force, and on 6,041 real states a maximum solver time of 0.050 s (0.444 s end-to-end), with every runtime gate passing. Handoff notes: [`docs/journey/round2-solver-handoff.md`](docs/journey/round2-solver-handoff.md).
6. **The paired evaluation, and one more experiment.** The pre-registered evaluation ran on fresh seeds (70001-70100, 600 episodes per arm) and came back inconclusive - the numbers are in section 3; the sealed report is `research/round2_stagewise_reward_solver/report.md`. After the submission was frozen, a final paired experiment tested re-allocating the clarification budget by an observable "potential-opportunity unlock" score; it was also negative-leaning and not adopted (`research/hard_constraint_clarification/`).

The full negative record, with sources, is section 5 below.

## 5. What did not work

Negative results are results. One line per finding, with the source artifact:

| Finding | What the evidence showed | Source |
|---|---|---|
| "+13 F2 superiority" (a learned selector) | **Withdrawn** - a self-audit found the comparison baseline was a count *minimizer* (sign defect); corrected contrast +6, CI [-0.2857, +0.9524], includes 0. | `research/round2_baseline_integrity/report.md` |
| REL value-of-information ("+18.7%") | **Oracle artifact** - the +18.7% was computed from hidden truth, an offline upper bound only; the live three-arm experiment was neutral (+0.90% relative, CI [-0.084, +0.091], 144 episodes). | `research/e3_rel_experiment/leakage_audit.md` |
| A+C score floor | **Volume suppression, causally shown** - only 16.4% of feasible pairs survived (1,662 of 10,144), and 411 decision-days had feasible candidates yet zero selections because every candidate was below the floor. Removing it restored volume; no reliable score gain was established. | `research/round2_stage2_floor_ablation/report.md` |
| Intermediate floor (`floor/2`) | **Undecided, not adopted** - it replicated the volume effect (wins in 90.28% of 72 paired worlds), but vs the original floor the MSMI contrast was inconclusive (+0.0278, CI [-0.118, +0.188]) and vs greedy negative-leaning (-0.090, CI [-0.257, +0.069]) at higher ask cost (+216.7, CI [+210.8, +222.9]). | `research/round2_promotion_fresh_seeds/summary.json` |
| Exact-k solver, policy-level test | **Inconclusive** - valid experiment, positive point estimate, 95% CI spanning zero: +0.00417 [-0.0483, +0.0583]. Kept as an engineering asset only. | `research/round2_stagewise_reward_solver/results/paired_stats.json` |
| Clarification prioritization | **Negative-leaning, not promoted** - paired delta -0.01750, CI [-0.06750, +0.03250]; both arms eventually asked the same member pool, so this tested a day-level re-allocation, not a change of population. | `results/hard_constraint_clarification_summary.json` |
| Confidence-gated maximum-weight matching | **Null** - identical to greedy on all 72 worlds (0 wins / 72 ties / 0 losses; CI [0, 0]); the ungated variant lost (-0.0486, CI [-0.158, +0.061]). The gate, not the matcher, carried the behavior. | `research/round2/results/summary.json` |
| Method tournament | **No survivors** - 30 candidate methods over 985 recorded method-episodes produced 0 credible candidates; the two Phase-3 finalists scored -0.0069 (99% CI [-0.0940, +0.0801]) and +0.0000. "Greedy remains the best empirically supported policy among the evaluated candidates." | `research/method_tournament/final_report.md` |

Each row is also summarized in `REPORT.md` (sections 8, 9 and 10), which adds the classification of every claim as verified engineering correctness, descriptive/causal finding, policy-level evidence, or inconclusive statistical comparison.

## 6. How to run and verify

### Quick start

Install Python 3.10 or later; the submitted path uses the standard library only, so there are no dependencies to install. From the repository root:

```bash
python -m unittest -v
python verify_data.py
python evaluate.py --seeds 101 --output results/first_run.json
```

On Windows, use `py` instead of `python` if needed. On macOS/Linux, use `python3` if your Python executable has that name. The starter has no external Python dependencies. Results are written to the requested JSON file; scores measure this invented simulator only.

### Official validation commands and recorded results (2026-10-16, IST)

Run from the project root, exactly as specified in [docs/SUBMISSION.md](docs/SUBMISSION.md):

| # | Command | Status | Evidence |
|---|---|---|---|
| A | `python -m unittest -v` | **PASS** (exit 0) | Workspace final run (after the clean-checkout fix below): **144 tests, `OK`, 184.3 s, exit 0**; the 144 = 81 root tests + 63 `research/test_pipeline` tests (the untracked `research/` tree is present in this workspace). A pre-fix run had shown `OK (skipped=1)` while the Docker daemon was still down (`test_t10_docker_latency_within_eval_constraints` skips itself then; it runs and passes once the daemon is up). Independent **clean-checkout run** (fresh `git clone` of the pinned commit): **`Ran 81 tests ... OK (skipped=8)`**, exit 0 - the 8 skips are guards for research-only assets deliberately not in the pinned build. |
| B | `python verify_data.py` | **PASS** (exit 0) | `{"verified": true, "counts": {"members": 2000, "introductions": 613, "feedback": 1270, "conversations": 1129}, "files": 71}` - matches PROBLEM_STATEMENT.md section 14. The same `verified: true` output (exit 0) was reproduced in a fresh `git clone` of the pinned commit, where `.gitattributes` (`* -text`) keeps data bytes identical regardless of a clone's `core.autocrlf`. |
| C | `python evaluate.py --seeds 101,102,103 --variants all --output results/final.json` | **PASS** (exit 0) | 319 s; 18/18 episodes valid; seeds 101-103 x all 6 variants; primary 0.3888888 MSMI/100. |
| D | `docker build -t sequential-policy:submission .` | **PASS** (exit 0) | 5.2 s; image manifest `sha256:033d5631a6cdd6d0772661a4d3905bba5197e7cb99f4cf77f628040788a05fcd`; build context contains only `kit.py`, `policy.py`, `Dockerfile` (`.dockerignore` allowlist). |
| E | `python evaluate.py --image sequential-policy:submission --seeds 101 --output results/container_check.json` | **PASS** (exit 0) | 65.3 s; 1/1 episode valid (`mode: container`, seed 101, development variant); its `action_sha256` is byte-identical to the local run of the same episode in `results/final.json`. |

Container constraints match the official evaluator: offline (`--network=none`), CPU-only, 10 s per decision, no host mounts (`test_runner.RunnerTests` and `test_policy` T10 tests).

**Clean-checkout validation.** Beyond this workspace, the pinned commit was validated in a fresh `git clone` on 2026-10-16: commands A and B both pass there (81 tests `OK` with 8 research-asset skips; `verified: true`). That check exposed two packaging defects, fixed in commit `9815843` without touching policy behaviour: (1) seven `test_policy.py` tests that import research-only modules (`features`, `export_model`, `collect`) now raise `SkipTest` when `research/` is absent - the same pattern the suite already used for `rows.csv`; (2) `.gitattributes` with `* -text` pins byte-stable checkout, because a machine-wide `core.autocrlf=true` previously rewrote data files to CRLF on clone and broke `verify_data.py` checksums. Commands C, D and E do not read the modified files (`test_policy.py`, `.gitattributes`), so their recorded results - produced from unchanged `policy.py`, `kit.py`, `evaluate.py` and `Dockerfile` - remain valid.

### Docker path

To check container execution after installing Docker (commands D and E above):

```bash
docker build -t sequential-policy:submission .
python evaluate.py --image sequential-policy:submission --seeds 101 --output results/container_check.json
```

Local subprocess mode is only for trusted development code. Assessed submissions run offline containers with no host evaluation files mounted; private organiser worlds are intentionally absent from this public repository.

## 7. Where everything lives

`full-story` contains the full submission tree, unchanged, plus the research record.

- **The submission.** `policy.py` (the submitted greedy default, plus the optional A+C research mode), `policy_ac.py`, `kit.py` (the simulator), `evaluate.py` (episode runner and scoring), `verify_data.py`, `build_public_data.py`, `organise.py` (organiser-side, never executed here), the `test_*.py` suites, `Dockerfile`, `.dockerignore`, `requirements.txt`. `data/` holds the supplied synthetic dataset (2,000 adults across ten independent pools, and the counts `verify_data.py` checks: 613 introductions, 1,270 feedback events, 1,129 conversation records), with `data_manifest.json` and `data_checksums.json`. `docs/` holds the supplied organiser documentation (`SUBMISSION.md`, `POLICY_INTERFACE.md`, `DATA_CONTRACT.md`, `ORGANISER_RUNBOOK.md`, `INTEGRATION.md`, `FAQ.md`, `PROBLEM_STATEMENT.pdf`).
- **The submission's numbers.** `results/` - the six required result JSONs (`final.json`, `container_check.json`, `greedy.json`, `no_asks.json`, `random.json`, `ac.json`) plus the hard-constraint clarification evidence (`hard_constraint_clarification_summary.json`, `hard_constraint_clarification_notes.md`). `REPORT.md` interprets all of it.
- **The journey.** `docs/journey/` - the team's own records: `round1-research-record.md`, `round1-research-ledger-verbatim.md`, `round2-stage1.5-findings.md`, `round2-solver-handoff.md`, with the original plans in `docs/journey/plans/` and the design spec in `docs/journey/specs/`.
- **The research programme.** `research/` - 24 folders of experiments, audits, notes and results, with [`research/README.md`](research/README.md) as the folder-by-folder index (question, verdict, key numbers, entry point). This is curated, not a raw dump: six large raw dumps (10-85 MB each), regenerable training snapshots and scratch logs are deliberately excluded, and the scripts that rebuild them are kept - `research/README.md` names exactly what is absent.
- **Housekeeping.** `CHANGELOG.md` records corrections to the submission documentation; `.gitattributes` (`* -text`) pins byte-stable checkout so the data checksums survive any cloner's `core.autocrlf`; `.gitignore` anchors `/results/` so the results rule does not swallow research folders that also contain a `results/` directory.

## 8. Outcome and lessons

**Outcome.** The team submitted the frozen build before the deadline - the operative deadline recorded for this team was **17 October 2026, 23:59 IST** (`CHANGELOG.md`), and the frozen commit cited by the submission is `f9796de`, kept unchanged as `round2-final-submission-corrected`. In the end, only eight teams were selected, and MayNerd was not among them.

**What the process taught:**

- **The headline result is a well-audited null.** Across the 24 folders of `research/` and a 30-method tournament over 985 recorded method-episodes, nothing reliably beat the stock greedy baseline on the primary metric. The team's most substantial positive artifacts are engineering ones - the blossom-based exact-k solver and the causal demonstration of the score floor's volume suppression - and they are reported as such, not as performance wins.
- **Pre-registration and self-audit work.** The two claims that initially looked like wins - the "+13 F2" contrast and the "+18.7%" REL estimate - were withdrawn by the team's own integrity checks, published as corrections, and never shipped as results. That is the main reason the record can be trusted.
- **Effects at this scale were mostly beyond resolution.** With 100 paired seed groups, the observed confidence-interval half-width was about 0.053 MSMI/100, so true effects well under about 0.05 could not be settled either way by any run performed here (`REPORT.md` section 10).
- **Reproducibility is a deliverable of its own.** Byte-stable checkout and a clean-checkout validation caught real packaging defects after the fact - fixed without touching policy behaviour and re-validated - and are the reason a stranger can rerun the commands above and get the recorded values.
- **What we would tell the next team:** freeze the protocol before the run, treat every oracle number as an upper bound, and expect nulls. A negative result you can defend is worth more than a positive one you cannot.
