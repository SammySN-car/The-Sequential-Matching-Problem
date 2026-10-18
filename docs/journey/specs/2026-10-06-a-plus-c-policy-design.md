# A+C Policy Design Spec — 2026-10-06

Status: for human review (brainstorming, architectural path).
Context: decisions 1-8 approved 2026-10-06 with amendments A1 and A2; this document is the written spec required before planning.

## 1. Purpose and success criteria

Build the first working A+C (ask + match) policy: observable state -> selective clarification asks -> 44-feature scoring with a trained HistGB value model -> global non-overlapping matching, correct, runnable, deterministic, measurable, evaluated by the real `evaluate.py` harness.

- S1: `python -m unittest` fully green locally (existing 80 + new tests). Non-sklearn tests must also pass in CI (zero pip installs, Python 3.10 and 3.12).
- S2: `docker build` succeeds; container-mode evaluation runs the A+C policy with no CLI args, all episodes valid, no crashes.
- S3: Determinism: identical per-episode action digests across repeated runs and across local/container modes for the same seed.
- S4: Evaluation executed exactly as section 14; results reported honestly (win or lose); no design changes driven by results without a new approved round.
- S5: No edits to `kit.py` or `evaluate.py`; no hidden or future simulator information anywhere in policy decisions.

## 2. Constraints

- C1 Files: forbidden = `kit.py`, `evaluate.py` (read-only). New/edited files limited to: `policy.py`, `research/export_model.py`, `policy_ac.py`, tests, this spec, and evaluation outputs under `results/`. No commits unless explicitly requested.
- C2 Deployment: image = `kit.py` + `policy.py` + stdlib only (`.dockerignore` whitelist). No numpy/sklearn in container or CI.
- C3 Protocol: engine calls the policy twice per day (ask phase, then match phase after refreshing observations). Response must be exactly `asks` or `pairs` plus a `memory` dict <= 1 MiB, strict JSON (no NaN), within the 10 s invoke timeout. Memory resets between calls (container is `--read-only`, no persistent FS).
- C4 `evaluate.py` local mode always invokes `policy.py --baseline {greedy,no_asks,random}` (choices frozen, cannot add `ac`); container mode passes no args at all.
- C5 (A1) Model trained only on the research train split (209,238 rows of `research/out_scale800/rows.csv` via the existing `world_split`). Validation worlds untouched. Full-data refit deferred until design and evaluation are finalized.
- C6 (A2) HistGB output is a ranking score, not a calibrated probability. Scores and floors must never be presented as probabilities or expected MSMI; `score - 0.0094`-style thresholds are prohibited. Known caveat: our proper scores were slightly worse than the constant baseline.
- C7 No tuning: model spec, floor, algorithms, and evaluation protocol are pre-registered here. Evaluation results do not trigger parameter changes (any change = new approved round).

## 3. Architecture: files and data flow

    evaluate.py --baseline {greedy,no_asks,random}  ->  python policy.py --baseline X   (baselines, byte-preserved)
    evaluate.py --policy policy_ac.py ...           ->  python policy_ac.py ...         (local A+C, trusted mode)
    evaluate.py --image sequential-policy:1.0       ->  docker run image                (A+C = container default)

    request -> phase dispatch
      ask   -> rule-based ask policy (section 7) -> asks + memory
      match -> feasible edges -> feature block -> HistGB score -> floor -> local search -> pairs + memory
    any exception in ac path -> deterministic fallback (section 8) or empty asks (section 7)

- `policy.py` sections: adapter + CLI (starter parser retained, extended), mode dispatch, self-contained feature block, ask policy, scoring (embedded blob), matching, memory, fallback.
- `research/export_model.py` (new, local development only): trains, encodes, injects the blob between markers in `policy.py`.
- `policy_ac.py` (new, ~20 lines, local evaluation only): thin stdin/stdout adapter that forces mode `ac` and ignores the `--baseline` flag that evaluate.py always passes. Not part of the Docker image (whitelist excludes it) and not used by the container path.

## 4. Model training and export

- Data: `research/out_scale800/rows.csv` -> `analyze.build_dataset` -> `analyze.world_split` (same functions and parameters as `run_experiment`) -> fit on the train fold ONLY (209,238 rows).
- Fit: `HistGradientBoostingClassifier(random_state=0, max_iter=200, learning_rate=0.1)`, sklearn defaults otherwise, 44 features, native NaN handling. This is the exact model class from `research/analyze.py:68-76`; deterministic given the data.
- Blob schema: JSON -> `zlib.compress` -> base64 -> `MODEL_B64` string literal inside `policy.py`, delimited by `# BEGIN GENERATED MODEL BLOB` / `# END GENERATED MODEL BLOB` markers. Exporter replaces only the region between markers, idempotently.
  - `{schema: 1, n_features: 44, feature_keys: [44 keys in research FEATURE_KEYS order], floor: float, baseline: float, trees: [[node, ...], ...]}`
  - node = `[value]` (leaf, length 1) or `[feature, threshold, left, right, missing_left]` (internal, length 5).
  - Export sources on the fitted sklearn object: `baseline = float(model._baseline_prediction.ravel()[0])`; trees from `model._predictors` (200 TreePredictors), per node: `feature_idx -> feature`, `num_threshold -> threshold`, `left`, `right`, `missing_go_to_left`, and for `is_leaf` nodes `value -> leaf value`.
- Prediction-equivalence contract (exact): `raw(x) = baseline + sum over all 200 trees of walk(tree, x)`, where `walk` returns the stored leaf value of the terminal node. No additional learning-rate or per-tree scaling is applied at inference - `learning_rate=0.1` shrinkage is already baked into stored leaf values at fit time (verified empirically 2026-10-06: identical-seed models at lr=1.0 vs lr=0.1 yield tree-0 leaf values in an exact 10:1 ratio; manual `baseline + sum(trees)` reproduced `predict_proba` to max abs diff 3.5e-18 on a 500-row probe). The exporter must run this parity self-check on sampled train rows and exit non-zero unless `abs(pure_python(X) - model.predict_proba(X)[:, 1]) <= 1e-9` holds for every sampled row - so the export cannot succeed while omitting any boosting or learning-rate contribution.
- `floor`: the model's own predicted score at the median of its predictions on the train fold. A rank reference only ("at least mid-pack among pairs the model was trained on") - never a probability. Computed once at export, stored in the blob, never re-derived at runtime.
- Exporter prints size, floor, and a validation-AUC sanity number. Reproducibility: same rows.csv -> byte-identical blob.
- Guard tests (CI-safe, stdlib only): markers present, blob decodes, schema fields present, n_features == 44, feature_keys order matches research, floor is a finite float, trees well-formed.

## 5. Pure-Python inference

- Lazy module-level cache: decode `MODEL_B64` -> `zlib.decompress` -> `base64.b64decode` -> `json.loads`, once per process. Any failure caches `None` and routes to fallback.
- Tree walk per row: start at the root node; `is_leaf` -> return its stored `value`; missing (NaN) feature follows `missing_go_to_left`; otherwise sklearn's `x <= num_threshold` convention goes left (pinned by T13; matches sklearn's predictor exactly).
- Complete additive prediction: `raw(x) = baseline + sum of walked leaf values over all trees` (the section 4 contract - no learning-rate or per-tree scaling at inference, float64, baseline first then trees in stored order). Ranking score = overflow-safe sigmoid of raw (branch on sign).
- Hard correctness gate (T12): for sampled rows, `pure_python_score(X)` must equal `sklearn_model.predict_proba(X)[:, 1]` within `atol=1e-9, rtol=0`. An export that fails this is invalid and must not be committed; T14 (val AUC reproduction) is a secondary sanity check only.
- Input: 44 Python floats in blob `feature_keys` order. No numpy, no sklearn at runtime.

## 6. Feature parity

- Copy the `research/features.py` logic required for `pair_features(state, a_id, b_id, t)` and `member_history(state, t, member_id)` into a self-contained block in `policy.py` (no `research/` import - it is not in the image; `kit` import is allowed and already used).
- `member_history` results cached per member per call, so cost is O(members x events), not O(pairs x events).
- Parity tests (local): for captured live states across at least 3 variants and several days, `policy.pair_features` equals `research.features.pair_features` elementwise (including NaN equality), and the key order equals `research.features.FEATURE_KEYS` exactly (the model was trained on that order).

## 7. Ask phase (rule-based; approved decision 4)

Deterministic. Hard rules: total cost <= `state['ask_budget_remaining']` (12/day, resets daily); only members with `available == True`; only fields with status `not_asked` (never observed, never declined); field values limited to `constraints` (cost 3), `relationship_goal` (cost 1), `relationship_pace` (cost 1). No day gating (budget resets daily, so unspent capacity is simply lost - unlike `baseline_asks`, which waits until day 35).

- Tier 1 - constraints: for member m (available, at least one not_asked hard field) compute `blocked_count(m)` = number of available members o such that pair (m,o) is not a past introduction, o has ALL hard fields observed, and `kit.eligibility(m,o)['status'] == 'needs_clarification'` (with o complete, the obstacle is provably m's missing fields - asking m can flip the pair to feasible). Ask `constraints` for candidates ordered by `(-blocked_count, member_id)` while budget >= 3.
- Tier 1b - progressive completion (refinement presented for review): if budget remains after Tier 1, ask `constraints` for available members having at least one available non-past partner, ordered by `(number of not_asked hard fields ascending, member_id)`. Rationale: daily budget reset makes unused capacity worthless; partial hard knowledge enables future Tier-1 flips. Strikes a balance between "ask only when provably useful" and cold-start starvation (where no member yet has complete hard fields, Tier 1 finds nothing).
- Tier 2 - soft: for `relationship_goal` then `relationship_pace`: ask member m (available, field not_asked) when m has at least one feasible non-past partner o with that same field already observed (the ask completes the pair's soft knowledge). Ordered by `(-partner_count, member_id, field order)`.
- Any exception in the ask path -> return `asks: []` (never crash, never emit an invalid ask that would make `resolve_asks` raise).

## 8. Match phase (amendments A2 applied)

1. Candidates: available members; pairs never previously introduced (`state['introductions']`); `kit.eligibility(a,b)['status'] == 'feasible'` (kit's function, no re-implementation).
2. Score every candidate: `pair_features` -> HistGB -> raw ranking score `s`.
3. Wait rule (rank guard, not a probability): keep edge only if `s >= floor` from the blob. If no edge survives, or no feasible pairs exist, return `pairs: []` (conservative wait). Prohibited interpretations: `s` or `s - floor` as probability or expected MSMI; the floor is a rank reference only (A2, C6).
4. Matching: approximate maximum-total-score non-overlapping matching on the surviving edges:
   - deterministic seed: edges sorted by `(-s, id_a, id_b)`, greedy take-while-both-free;
   - local-search sweeps (max 8, stop at first sweep with no gain) over the same sorted order, applying strictly improving moves: (a) take edge (u,v) when both u and v are free; (a') augment: u matched to p, v free, edge (u,v) with `s(u,v) > s(u,p)` -> match (u,v), leaving p free; (b) partner exchange: current matched pairs (u,v) and (u',v') -> alternative (u,v') and (u',v), applied only when `s(u,v') + s(u',v) > s(u,v) + s(u',v')`.
   - output: sorted list of `[id_a, id_b]`, one introduction per member.
5. Whole match path wrapped in try/except -> deterministic fallback on any error: rule-score greedy over the same feasible candidates, rule score = count of matching observed soft fields (observed only), sorted by `(-rule, id_a, id_b)`, take-while-both-free. No model, no floor (floor is meaningless without model scores).
- Performance: target p95 <= 5 s per match call, hard bound < 9 s (invoke timeout 10 s). Worst case to measure in T10: 200 available members with all hard fields observed -> ~19.9k candidate pairs. Pre-registered contingency if measurement exceeds 5 s: keep the top 12,000 edges by rule score before model scoring (step 2), deterministic, covered by a test. No other performance tuning.

## 9. Memory

- Output: `{}` when the state has no members (the protocol test requires exactly this for an empty request), else `{"v": 1, "m": {member_id: [n_intro, n_dates, n_second_yes, n_second_no]}}`, derived fresh from `state` each call (introductions + observed feedback up to `state['day']`).
- Incoming memory (`None`, empty, garbage, from a previous phase) is never trusted and never crashes processing.
- v1 decisions do not read memory: the observable state is Markov-sufficient and is what feature parity requires. Memory is a validated, restart-safe protocol summary, ~20 KB worst case (well under 1 MiB).

## 10. CLI and protocol compatibility

- `policy.py` argparse: `--baseline {greedy,no_asks,random,ac}`, default `ac` (container passes no args). `decide(request, mode='ac')` default `ac` (test_runner calls `decide` without a mode argument).
- Baseline modes byte-preserved: `greedy`/`no_asks`/`random` behave exactly as the starter code does today (reviewed by existing tests).
- Empty request (0 members, `memory: null`) -> exactly `{'pairs': [], 'memory': {}}` in the match phase and `{'asks': [], 'memory': {}}` in the ask phase (the protocol test exercises the match phase).
- Local A+C evaluation: `python evaluate.py --policy policy_ac.py --baseline greedy --seeds 101,102,103 --variants all --output results/ac.json`. The shim ignores the baseline flag (evaluate.py cannot pass `ac`, C4); the output filename records the policy identity. Documented in the shim docstring and here (R5).

## 11. Error handling

- Model decode/score failure -> fallback matching (section 8.5). Ask-path failure -> empty asks. `decide` never raises in `ac` mode.
- Outputs are always strict-JSON-safe (`allow_nan=False`): NaN may exist inside internal feature computation but never in the response.

## 12. Determinism

- No RNG anywhere in the `ac` path. No direct iteration of `set`/`dict` into ordered outputs (explicit sorts everywhere) with `member_id` tie-breaks. Identical request -> byte-identical response (tested).
- Cross-mode: same seed -> identical per-episode `action_sha256` for local (`policy_ac.py`) and container runs (checked in section 14).

## 13. Testing (TDD: red/green per behavior; all discovered by `python -m unittest`)

Root `test_policy.py` (CI-safe: stdlib + repo only):
- T1 dispatch and defaults: `decide()` default runs `ac` (differs from baseline output on a non-trivial state); CLI default is `ac`; baseline modes unchanged.
- T2 protocol: empty-state exact response; ask/match response shapes; memory robustness (`None`, `{}`, stale version).
- T3 feature parity with research (multi-variant captured states, NaN-safe) and `FEATURE_KEYS` order equality.
- T4 blob guard: markers present, blob decodes, schema fields, `n_features == 44`, `feature_keys` order, finite float floor, tree well-formedness.
- T5 scorer: toy trees -> hand-computed sigmoid values; NaN branch in both directions; `<=` threshold semantics.
- T6 ask rules: budget ceiling never exceeded; only available members; only `not_asked` fields; tier ordering; past-pair exclusion; determinism (same state twice -> identical asks).
- T7 match rules: feasibility only; no past pairs; unique members; floor applied (every matched edge `s >= floor`); empty-wait case; local-search toy graph reaches known optimum; determinism; sorted output.
- T8 fallback: corrupted `MODEL_B64` -> valid deterministic output via fallback; injected scoring exception -> fallback pairs; ask failure -> empty asks.
- T9 integration: pairs from `ac` passed to a real `kit.Simulator.advance` never raise `ValueError`; 20-day loop (ask then match, refresh in between) stays valid - same style as `test_runner.test_observed_policy_never_receives_world_fields`, which now exercises the default `ac` path.
- T10 perf smoke: worst-case all-hard-observed 200-member state -> match call completes < 9 s.
- T11 forbidden-token audit: the scoring/decision path reads only observable state keys (no `truth`, no `sim.` internals, no `variant`/`seed`/`response_rate`/`events` bypass; source-level audit in the style of `audit_feature_keys`).

`research/test_pipeline.py` additions (skipUnless numpy + sklearn, matching existing import style):
- T12 export roundtrip parity (HARD GATE): `predict_proba(X)[:, 1]` of the refit model equals the exported-blob pure-Python score on sampled rows with `atol=1e-9, rtol=0`, exercising the complete additive prediction (baseline + all 200 tree contributions; learning-rate shrinkage already inside stored leaf values; no inference-time scaling). This is the primary export/inference correctness requirement; T14 is secondary.
- T13 threshold direction and missing-branch: constructed single-tree model with known split -> pure-Python walk must match sklearn (catches `<=`/`<` and `missing_left` errors).
- T14 validation sanity: exported scorer reproduces val AUC 0.5937 within 0.001 on the scale-up split.

Existing suites (`test_kit`, `test_runner`, `test_release`, remainder of `test_pipeline`) must remain green. Pre-existing note: some research tests import numpy unguarded (CI has no pip installs) - unchanged by this work; all tests added by this design are either CI-safe or explicitly guarded.

## 14. Evaluation plan (pre-registered)

- Policies: `greedy`, `no_asks`, `random` (trusted local, via `--baseline`); `ac` (trusted local via `--policy policy_ac.py`, and assessed container mode via `--image`).
- Seeds 101,102,103 x `--variants all` for every policy.

Commands:

    python evaluate.py --baseline greedy  --seeds 101,102,103 --variants all --output results/greedy.json
    python evaluate.py --baseline no_asks  --seeds 101,102,103 --variants all --output results/no_asks.json
    python evaluate.py --baseline random   --seeds 101,102,103 --variants all --output results/random.json
    python evaluate.py --policy policy_ac.py --baseline greedy --seeds 101,102,103 --variants all --output results/ac.json
    docker build -t sequential-policy:1.0 .
    python evaluate.py --image sequential-policy:1.0 --seeds 101,102,103 --variants all --output results/ac_container.json

Integrity checks, executed before reading outcome metrics:
- G1: zero invalid/failed episodes; every summary `eligible: true`.
- G2: determinism - rerun `ac` (seed 101) -> identical per-episode `action_sha256`; local `ac` vs container `ac` -> identical per-episode digests for matching seeds/variants.
- G3: container build and container eval succeed (no sklearn in image).

Report (per the 15-section evaluation brief): per-variant and aggregate primary_score (MSMI/100), coverage, mutual acceptances/100, ask_cost, inference_seconds, invalid-episode counts, ranking vs the three baselines, digest checks, and the calibration caveat (C6). Headline comparison: `ac` (container) vs baselines (trusted local - same mode as official `examples/baseline_results/`).

Pre-registration: results do not alter model, floor, asks, or matching (C7). Any post-evaluation change is a new round requiring approval.

## 15. Risks and known limitations

- R1: modest, uncalibrated discrimination (AUC 0.59, CI [0.567, 0.621]) may not beat greedy's 0.50 MSMI per 100 - reported honestly, no post-hoc tuning (C7).
- R2: CI lacks numpy/sklearn - sklearn-dependent tests skip; blob/parity/protocol tests still run in CI.
- R3: blob ~0.8-1.1 MB raw -> ~250-350 KB embedded; decode+load ~0.1-0.3 s once per process (measured in T10).
- R4: worst-case inference close to the 10 s timeout -> pre-registered pre-cap contingency (section 8), measured in T10.
- R5: `policy_ac.py` ignores the `--baseline` flag evaluate.py passes - documented; output filenames record identity.
- R6: CI container eval runs `ac` on seed 101 with no sklearn in the image - guaranteed by design (pure-Python scorer, embedded blob).
- R7: export reproducibility depends on `research/out_scale800/rows.csv` being present locally.

## 16. Out of scope

Full-data refit (A1), hyperparameter tuning, calibration, RL or learned ask policies, edits to `kit.py`/`evaluate.py`/CI/Dockerfile/`.dockerignore`, Round-1 report, second-generation architecture.
