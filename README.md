# The Sequential Matching Problem

**Final participant release 1.0.0 | Vouchsafe | Round 2 final build submission**

Build a policy that decides who to introduce, when to wait and what to clarify, using incomplete reciprocal preferences and delayed feedback. Every person, conversation and outcome in this kit is synthetic.

**Submitted policy:** the stock greedy baseline (`kit.baseline_match` / `kit.baseline_asks`), kept as the default entrypoint of `policy.py`, exactly as required by Round 2 spec section 8. See [REPORT.md](REPORT.md) for the technical report, evidence and research history.

## Start here

1. Read the [final problem statement](PROBLEM_STATEMENT.md) or [download the PDF](docs/PROBLEM_STATEMENT.pdf).
2. Download this repository with **Code -> Download ZIP**, or clone it. The full dataset is already in `data/`; no Supabase account, API key or separate download is required.
3. Install Python 3.10 or later. Open a terminal in the extracted repository folder and run:

```bash
python -m unittest -v
python verify_data.py
python evaluate.py --seeds 101 --output results/first_run.json
```

On Windows, use `py` instead of `python` if needed. On macOS/Linux, use `python3` if your Python executable has that name. The starter has no external Python dependencies. Results are written to the requested JSON file; scores measure this invented simulator only.

## Environment and versions (verified)

| Component | Version used for this submission | Where it is pinned |
|---|---|---|
| Python (host, used for all five official validation commands) | 3.13.5 (64-bit, CPython, Windows) | Recorded here; any 3.10+ works |
| Python (assessed container) | `python:3.12.7-slim` base image | `Dockerfile` |
| Runtime dependencies of `policy.py` / `evaluate.py` / `kit.py` | **None - Python standard library only** | `requirements.txt` states this explicitly |
| Development/test-only dependency | `scikit-learn 1.8.0` (BSD-3-Clause), only imported by the optional `research/test_pipeline.py` unit tests | Not required by the policy, container, or starter test suites |
| Docker | Docker 29.8.0 (Docker Desktop, Linux engine) | Host tool, not bundled |

`requirements.txt` is intentionally empty of packages: the submitted inference path imports only the standard library, so the container build requires no package installation and no credentials.

## Official validation commands and recorded results (2026-10-16, IST)

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

## Submitted result files

`results/` is git-ignored by default (`.gitignore` line 4); the six required JSON files below were staged explicitly with `git add -f` per docs/SUBMISSION.md L42.

| File | What it is | Generated by | SHA-256 |
|---|---|---|---|
| `results/final.json` | **Official final evaluation.** Greedy policy, seeds 101,102,103 x all 6 scenario variants, 18 full episodes, 40-day follow-up. | Command C on 2026-10-16 | `5c9c50afb1f5d6e6ea56f5f2b4248832cbe4c39283031d9a2e32fab180e3c8cd` |
| `results/container_check.json` | **Container evaluation.** Same policy inside the assessed Docker image, seed 101. | Command E on 2026-10-16 | `7128c5e52042c12c09409fcfb2f5fa30b0d1a92e4e1680eeb7c562b67f885202` |
| `results/greedy.json` | Four-arm same-seed comparison: greedy arm, 18 episodes. | 2026-10-07, see provenance below | `b1f0178d289b9e73a3a6f58e8b8072f72ea6178daac037b0791e31f6017ffa2a` |
| `results/no_asks.json` | Four-arm comparison: no-clarification arm, 18 episodes. | 2026-10-07 | `7fedd9c2ff918e6239e04ae1132256e4f3a19452b86927514db3c8c56c6d39d9` |
| `results/random.json` | Four-arm comparison: random-feasible arm, 18 episodes. | 2026-10-07 | `27b52bb17a98337d420727f683e82c419a62bed1e5b81009de45bfc604010313` |
| `results/ac.json` | Four-arm comparison: research arm A+C (the team's non-baseline method), 18 episodes. | 2026-10-07, `policy_ac.py` shim | `57e0dfb382393839d897f53c8880cb54fccd6b34c34d4163c7892ea39d0710ac` |

All six files have the official evaluator schema: `release`, `mode`, per-episode outcome fields (MSMI, coverage, waiting days, ask cost, missing feedback, served/unserved, `action_sha256`, `valid`) and a `summary` with `primary_score`, `scenario_means` and the official ranking key. The four comparison files use identical seeds (101-103) and identical scenario variants (all six) - verified programmatically.

**Provenance of the four-arm files (disclosure):** they were generated on 2026-10-07 with `policy.py` SHA-256 `379cc2d9...` and `policy_ac.py` SHA-256 `90fb9ad3...` (recorded in `results/run_log.txt`, not part of the submission). The only documented change to `policy.py` since then is the Round-2-required entrypoint default flip (`decide()` and `--baseline` defaults changed from `ac` to `greedy`; see `research/round2/results/summary.json` `decision.entrypoint_flip`); no scoring, matching or ask logic changed. This is re-verified, not assumed: the greedy re-run in `results/final.json` (current policy, SHA `c2ea0ffc...`) reproduces all 18 historical greedy `action_sha256` digests exactly (18/18). The submitted policy SHA-256 is `c2ea0ffc95387c3e92ee214419a0bbde3c747e053eb4f35c5477337de5178d50`.

Historical files that are **not** part of the submission but remain in the local `results/` directory: `artifact.sha256` (a 2026-10-06 checksum pin that documents the historical `379cc2d9...` policy - deliberately left unmodified), `run_log.txt`, `pre_eval_diagnostics.json`, `_timing.json`, `ac_container.json`, `ac_rerun.json`.

## What is included

| File / folder | Purpose |
|---|---|
| [PROBLEM_STATEMENT.md](PROBLEM_STATEMENT.md) | Final challenge, ranking, resources, schedule and ownership rules |
| [REPORT.md](REPORT.md) | **Technical report for this submission** (hypotheses, method, results, ablations, limitations) |
| [data/](data/) | 2,000 synthetic adults, ten disjoint pools and day-30 observable histories |
| [data_manifest.json](data_manifest.json) | Pool counts, source seeds and train/validation/development-test split |
| [docs/DATA_CONTRACT.md](docs/DATA_CONTRACT.md) | Every field, constraint and feedback rule |
| [docs/POLICY_INTERFACE.md](docs/POLICY_INTERFACE.md) | Executable JSON request/response protocol |
| [policy.py](policy.py) | Submitted policy entrypoint: greedy (default), no-clarification, random-feasible; also contains the optional research A+C mode, which is not the submitted default |
| [policy_ac.py](policy_ac.py) | Small shim that forces the research A+C mode; staged so the test suite and the historical `ac.json` provenance stay reproducible |
| [evaluate.py](evaluate.py) | 60-day episodes, 40-day follow-up, metrics and scenario-level score |
| [build_public_data.py](build_public_data.py) | Rebuild public synthetic tables in a new folder |
| [kit.py](kit.py) | Reproducible public simulator and reciprocal eligibility checks |
| [organise.py](organise.py) | Prepare and grade 120 private episodes outside the public repo (never executed in this workspace; no private output exists) |
| [docs/ORGANISER_RUNBOOK.md](docs/ORGANISER_RUNBOOK.md) | Complete assessment commands and ranking procedure |
| [Dockerfile](Dockerfile) | Offline container packaging for assessed inference |
| [docs/SUBMISSION.md](docs/SUBMISSION.md) | Complete research and build submission instructions |
| [docs/INTEGRATION.md](docs/INTEGRATION.md) | Reusable adapter boundary for later Vouchsafe evaluation |
| [docs/FAQ.md](docs/FAQ.md) | Common questions and communication policy |
| [test_kit.py](test_kit.py), [test_policy.py](test_policy.py), [test_release.py](test_release.py), [test_runner.py](test_runner.py) | Test suites: simulator invariants, policy/model contract, release metrics, runner/container contract |
| [examples/baseline_results/](examples/baseline_results/) | Checked starter reference runs for all three baselines (smoke-scale) |
| [examples/REPORT_GUIDE.md](examples/REPORT_GUIDE.md) | What a complete participant technical report must cover |

## Seeds and randomness

**Official evaluation seeds (declared):** `101,102,103` for `results/final.json`; `101` for `results/container_check.json`. These are the public seeds fixed by docs/SUBMISSION.md L37/L39. The four-arm historical comparison uses the same seeds 101-103 across all four arms.

**Training seeds (declared):** the submitted default (greedy) path performs **no training** and uses **no learned asset**. The optional A+C research mode carries a pre-trained model blob inside `policy.py` (44 features, gradient-boosted trees, trained offline on CPU); its training rows came from research-only rollouts over world seeds **50000-50799** (800 rollouts recorded in `research/out_scale800/rows.csv`). `test_policy.SeedHygieneTests.test_research_and_eval_seeds_are_disjoint` verifies these research seeds never overlap evaluation seeds. Data pool source seeds are declared in `data_manifest.json`. No private/holdout seed was ever generated or consumed in this workspace.

**Inference random-seed policy:** the submitted greedy policy is fully deterministic - it consumes no randomness for a given input state. Evidence: all 18 `action_sha256` digests in `results/final.json` are byte-identical to the independently produced historical run, and the container run reproduces the local run digest-for-digest (1/1). The optional `random` baseline uses a fixed per-day seed (`random.Random(17 + state["day"])`), so it is also repeatable. No `PYTHONHASHSEED` pinning is required by the submitted path.

## Model, data and tool provenance

- **Model:** one embedded, compressed model blob inside `policy.py` (zlib+base64 JSON, schema-checked at load). Used only by the optional research A+C mode; never executed in the submitted greedy default. Trained offline in research; no fine-tuning or calibration happens at inference.
- **Data:** fully synthetic dataset v1.0.0 shipped in `data/` (2,000 adults, 613 introductions, 1,270 feedback events, 1,129 conversation records - verified by `verify_data.py`). No real-member data, no external datasets, no network access at evaluation time.
- **Tools:** CPython 3.13.5 / 3.12.7, Docker 29.8.0, scikit-learn 1.8.0 (research tests only). Development used AI coding assistants for implementation, experiment execution and analysis (disclosed per examples/REPORT_GUIDE.md item 3); experiment protocols were frozen in pre-registration files inside `research/` before the corresponding runs.
- **Licences:** participant/starter code - MIT (`LICENSE`); supplied synthetic data - `DATA_LICENSE.md` (permissive, preserve synthetic provenance); Python - PSF licence; scikit-learn - BSD-3-Clause; Docker base image `python:3.12.7-slim` - standard Debian/PSF upstream licences.
- **Training compute:** CPU-only, single machine, no GPU and no paid cloud compute. Exact historical training wall-time was not recorded (unknown); inference at assessment time is CPU-only inside the offline container.

## Develop and compare

Edit `policy.py`, keeping the JSON interface. Observe only the input state. Refreshing observations after clarification is handled by the evaluator. Policy memory is passed explicitly between calls and reset between episodes.

```bash
python evaluate.py --baseline greedy --seeds 101,102,103 --variants all --output results/greedy.json
python evaluate.py --baseline no_asks --seeds 101,102,103 --variants all --output results/no_asks.json
python evaluate.py --baseline random --seeds 101,102,103 --variants all --output results/random.json
```

The full commands take longer than the one-episode quick start. Public variants are `development`, `sparse`, `cold_start`, `delayed`, `shift`, and `drift`. Use your own declared training seeds. Keep the supplied six training pools, two validation pools and two development-test pools disjoint. Day-30 snapshots are not observations from earlier decisions.

To check container execution after installing Docker:

```bash
docker build -t sequential-policy:submission .
python evaluate.py --image sequential-policy:submission --seeds 101 --output results/container_check.json
```

Local subprocess mode is only for trusted development code. Assessed submissions use offline containers with no host evaluation files mounted. Private organiser worlds are intentionally absent from this public repository.

To regenerate the public tables without changing the supplied data:

```bash
python build_public_data.py --output ../rebuilt-public-data
```

The new folder must not already exist. The generator uses only invented data and public seeds. Do not use seed reconstruction inside an evaluated policy.

## What this project researched (summary)

Roughly 25 experiments, a 30-method tournament (985 recorded method-episodes) and a 100-seed-group paired evaluation were run during research. Headline: **no tested alternative established a statistically reliable improvement over greedy**, so the submission keeps greedy. Notable engineering results (an exact-cardinality blossom solver, a causal score-floor ablation) and two withdrawn claims are documented honestly in [REPORT.md](REPORT.md).

## Submit and ask questions

Teams: **1-4 participants**.

| Milestone | Date and time (IST) |
|---|---|
| Round 1 research submission closes | 9 October 2026, 23:59 |
| Round 1 results announced by | 11 October 2026, 22:00 |
| Round 2 build starts | 12 October 2026 |
| Final build submission closes | 18 October 2026, 23:59 |

**Round 1:** submitted through a Google Form (closed).

**Round 2:** use the [Final submission](https://github.com/RomeoJulietLove/The-Sequential-Matching-Problem/issues/new?template=final_submission.yml) issue form by the final deadline. Provide the immutable submitted version and required report/results. Use [Question](https://github.com/RomeoJulietLove/The-Sequential-Matching-Problem/issues/new?template=question.yml) for technical questions. Never post personal data, access codes or credentials in public issues.

This repository and public Issues are the shared technical communication hub. Event announcements and reminders are shared through [the IITM Discord server](https://discord.gg/GwZdY54Gq). Questions answered here are visible to every team. See [CHANGELOG.md](CHANGELOG.md) for release corrections.

The [starter-code permission](LICENSE) and [synthetic-data permission](DATA_LICENSE.md) permit reuse of the supplied kit. Students retain ownership of their own work; participation does not grant Vouchsafe a commercial licence to submissions. Later use requires a separate agreement.