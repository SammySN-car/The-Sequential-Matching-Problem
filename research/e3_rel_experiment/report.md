# E1/E2/E3 Experiment Report — REL value-of-information asks × analytic scoring

Preregistered in `experiment_plan.json` (Stage A approved before any run).
Frozen sources untouched (6/6 hashes verified before and after).
Final verdict (preregistered stopping rules): **INCONCLUSIVE — keep greedy.**

## 1. Question and arms

Stage A (`leakage_audit.md`) established that the static "+18.7%" figure is an
*oracle full REL reveal upper bound* (offline pair-value arithmetic using
`truth`, hidden parameters, whole-pool static allocation) — not a live MSMI
forecast. The live test:

| Arm | Ask phase | Match phase |
|-----|-----------|-------------|
| C (control) | `kit.baseline_asks` (`policy.py`) | `kit.baseline_match` (count score, take-while-free) |
| E1 | hard asks first + VoI-gated REL soft asks (count scoring) | byte-identical to C |
| E2 | byte-identical to C (`baseline_asks`, zero REL asks) | analytic scorer, same take-while algorithm |
| E3 | hard asks first + VoI-gated REL asks (analytic scoring) | analytic scorer, same take-while algorithm |

The VoI gate (`rel_common.voil_asks`) enumerates the *public* answer space
(`kit.OPTIONS[field]`), recomputes today's allocation for each legal answer,
and asks only if at least one legal answer would change the allocation. It
never reads truth, hidden parameters, outcomes, or future state (static token
scan + unit tests, `test_rel_experiment.py`). No tunable parameters; no MWM,
local search, thresholds, RL, retraining, history, or hard-ask redesign.

## 2. Protocol

- Engine: frozen `evaluate.py` (`--policy` local subprocess, `--baseline greedy`,
  seeds/variants as CLI args), official CLI for primary runs; instrumented
  second pass via `evaluate.episode(..., simulator_class=InstrumentedSim)`.
- Pairing: same (seed, variant) unit across all 4 arms; equal-weight mean of
  the 6 variant family means = primary `msmi_per_100_arrived_members`.
- Stage 1: seeds 119–130 × 6 variants × 4 arms = **288 episodes**.
- Stage 2 (preregistered single extension, rule triggered): seeds 131–142 ×
  6 × 4 = **288 episodes**. Total **576**.
- Guardrails: 0 invalid episodes, per-invocation latency ≪ 10 s (episode totals
  19–22 s = sum of 120 invokes), ask budget protocol-enforced, deterministic
  reruns byte-identical, no hidden-input reads.

## 3. Results

### Stage 1 (seeds 119–130, 72 paired units/arm)

| Arm | MSMI/100 | vs C | seed-level 95% CI | W/T/L |
|-----|----------|------|-------------------|-------|
| C | 0.3958 | — | — | — |
| E1 | 0.4583 | **+15.8%** | [−0.039, +0.164] | 16/49/7 |
| E2 | 0.3681 | −7.0% | [−0.166, +0.110] | 8/52/12 |
| E3 | 0.4306 | +8.8% | [−0.124, +0.194] | 16/44/12 |

Stage-1 rule: E3 point > 0 with CI overlapping 0 → **extend exactly once**
(performed).

### Stage 1 + 2 pooled (seeds 119–142, 144 paired units/arm) — FINAL

| Arm | MSMI/100 | vs C | seed-level 95% CI | W/T/L |
|-----|----------|------|-------------------|-------|
| C | 0.3854 | — | — | — |
| E1 | 0.4167 | +8.1% | **[−0.031, +0.093]** | 22/109/13 |
| E2 | 0.4062 | +5.4% | [−0.060, +0.101] | 22/103/19 |
| E3 | 0.3889 | +0.9% | **[−0.084, +0.091]** | 27/90/27 |

Bootstrap (10k, seed-level, fixed RNG) agrees with the t-intervals (see
`summary.json`). Stage-2 alone reversed the stage-1 ordering (E3−C ≈ −0.028,
E1−C ≈ 0.000, E2−C ≈ +0.069) — the arm effects are not stable across seed
blocks of 12 seeds.

**Stopping rule (verbatim from the plan):** "after extension CI still overlaps
0 → verdict 'inconclusive' → keep greedy." Both E3 and the best point estimate
(E1) overlap 0 after the single permitted extension. Final decision rule:
replace greedy ONLY on credible realized MSMI improvement — **not met. Keep
greedy.**

### Stage-1 mechanism (InstrumentedSim pass; 288/288 digests byte-identical)

| | E1 | E3 | C / E2 |
|---|----|----|--------|
| REL asks/episode | 42.3 | 42.8 | 0 |
| REL-ask days where allocation actually changed | **76.6%** | 67.7% | — |
| REL asks issued on changed days | 87.6% | 75.6% | — |
| Days with changed edge ranking | 12.6% | 15.5% | 0% |
| Edge scores changed | 9.9% | 18.5% | 0% |
| Zero-selection days | 0.435 | 0.441 | 0.435 / 0.441 |

- The gate is high-precision (most asks were decision-relevant) and did not
  collapse volume: zero-selection days match C exactly (E1) / +0.6 pp (E3).
- E2's byte-identical ask isolation is confirmed by 0 REL asks and unchanged
  mechanism fields — so E2's variance comes from the matcher alone.
- Counterfactual check: for C and E2 the mask-and-recompute identity holds on
  every day (REL reveals never happen → allocation cannot change).

## 4. What this says about the static findings

- The static +5.2% (analytic scorer) did **not** transfer: live E2 ranges from
  −7.0% (stage 1) to +5.4% (pooled) — the static whole-pool snapshot advantage
  does not survive daily-sequential operation (ask timing, availability,
  busy/pause dynamics). This is the sequential-transfer gap `leakage_audit.md`
  flagged as untested.
- REL ask headroom exists (statically: 517 free units/ep) and the gate spends
  it efficiently (42/ep, 76.6% decision-relevant), but the realized MSMI gain
  is within seed noise (seed-level SD ≈ 0.24 on a scale where observed effects
  are ≈ 0.03–0.06).
- The combined arm E3 was never better than E1 (pooled −2.8 pp vs E1), i.e.
  the analytic scorer did not add value on top of asks.

## 5. Guardrails and integrity

- Invalid episodes: **0 / 576** (stage 1 and stage 2, all arms).
- Determinism: 48-episode slice rerun byte-identical (action_sha256 + all
  metrics, timing excluded) — `determinism_rerun.json` PASS.
- Independent replay: instrumented pass vs official CLI pass —
  **288/288 action_sha256 identical** (`*_mechanism.json`, digest_mismatch=0).
- Container parity: **PASS (5/5)** — `container_fidelity.json`. Slice
  (seeds 119,130 x 6 variants = 12 episodes per check): E1/E2/E3
  local-vs-container byte-identical (0/36 mismatches); control-greedy in a
  derived image (`Dockerfile.control`, frozen Dockerfile untouched)
  byte-identical (0/12); and — because the frozen image's entrypoint runs
  `policy.py` with no args, whose argparse default is `ac` (A+C), not greedy
  (`docs/POLICY_INTERFACE.md`) — the official image's A+C mode was verified
  separately local-vs-container (0/12). A day-by-day request/response diff
  over all 60 days (seed 119, development) showed no greedy divergence; one
  cold-start 10-second invocation timeout in the verification slice was
  diagnosed as transient and passed after a warm-up invoke.
- Existing suite green at start: `test_kit test_runner test_release test_policy`
  (63) + `research.test_pipeline` OK; 20 new component tests OK (alloc
  equivalence to `baseline_match`, hand-computed scorer values, gate invariants
  incl. single-sided/no-flip/budget fixtures, isolation, protocol validation,
  static leak scan).
- Frozen 6-file SHA-256: unchanged before vs after (`integrity_before/`,
  `integrity_after/`, `hashes_manifest.txt`); 0 commits.
- `.dockerignore` temporarily extended to build derived images, restored
  byte-exact from git (verified clean in `git status`).

## 6. Reproduce

```
python -m unittest research.e3_rel_experiment.test_rel_experiment   # from repo root:
python research/e3_rel_experiment/test_rel_experiment.py
python research/e3_rel_experiment/run_experiment.py --phase official            # stage 1 (seeds 119-130)
python research/e3_rel_experiment/run_experiment.py --phase official --stage2   # stage 2 (seeds 131-142)
python research/e3_rel_experiment/run_experiment.py --phase mechanism
python research/e3_rel_experiment/analyse.py --stage2
python research/e3_rel_experiment/verify_reruns.py --phase determinism
python research/e3_rel_experiment/verify_reruns.py --phase container
```

## 7. Files

`design.md`, `leakage_audit.md`, `experiment_plan.json`, `summary.json`,
`run_log.txt`, `per_arm/` (official, stage-2, rerun, mechanism, container),
`determinism_rerun.json`, `container_fidelity.json`, `integrity_before/`,
`integrity_after/`, `hashes_manifest.txt`, plus code: `rel_common.py`,
`policy_e1.py`, `policy_e2.py`, `policy_e3.py`, `instrumented_sim.py`,
`run_experiment.py`, `analyse.py`, `verify_reruns.py`, `test_rel_experiment.py`,
`Dockerfile.e3`.
