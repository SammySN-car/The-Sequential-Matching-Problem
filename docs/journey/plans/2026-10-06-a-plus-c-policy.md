# A+C Policy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the approved A+C policy: rule-based clarification asks, embedded HistGB ranking scorer with exact sklearn parity (T12 hard gate), 44-feature research parity, floor-gated approximate max-score matching, deterministic fallback, and the pre-registered evaluation.

**Architecture:** `policy.py` gains self-contained sections (model package, feature copy, ask policy, matching, memory, fallback) behind an `ac` default mode, with baselines byte-preserved; `research/export_model.py` trains the train-split model and injects a base64+zlib JSON blob between markers in `policy.py`; `policy_ac.py` is a thin local-eval shim. Container (stdlib-only, no args) runs `ac` by default.

**Tech Stack:** Python 3.10/3.12 stdlib for `policy.py`; scikit-learn 1.8 + numpy locally for export/parity tests only; Docker for assessed runs; unittest (no pytest).

**Spec:** `docs/superpowers/specs/2026-10-06-a-plus-c-policy-design.md` (read it before starting; every requirement below argues from it).

## Global Constraints

- NEVER modify `kit.py` or `evaluate.py` (read-only; this plan only adds/edits `policy.py`, `research/export_model.py`, `policy_ac.py`, `test_policy.py`, `research/test_pipeline.py`).
- No git commits unless explicitly requested (no commit steps; a passing suite is the task gate).
- `policy.py` imports and runs on stdlib only (no numpy/sklearn in it); Python 3.10 and 3.12 syntax only.
- Feature block is a VERBATIM copy of `research/features.py` EXCLUDING: module docstring, `import kit`, `FORBIDDEN_TOKENS`, `STRUCTURE_INFORMED`, `audit_feature_keys`, `audit_structure_disclosure`. Add `import kit` to policy.py's imports. Never edit a copied line.
- Model: `HistGradientBoostingClassifier(random_state=0, max_iter=200, learning_rate=0.1)` on train fold ONLY: `analyze.world_split(rows, val_frac=0.2, split_seed=0)` + `analyze.build_dataset(train_rows, target='label')`, model = `'hist_gb'` entry of `analyze.fit_models(Xtr, ytr)`. Fitted tree count is the ACTUAL `model.n_iter_` (<= max_iter=200: sklearn early stopping stays at its default and may stop sooner - do NOT disable it): the exporter asserts `len(trees) == model.n_iter_` and serializes `n_iter` into the blob; no test or doc may assume exactly 200 trees.
- Prediction contract: `raw(x) = baseline + sum of walked leaf values over all fitted trees (actual `model.n_iter_`, serialized `n_iter` == `len(trees)`)`; NO inference-time learning-rate scaling; sigmoid(raw); `x <= num_threshold` goes left; NaN follows `missing_go_to_left`.
- T12 HARD GATE: `abs(pure(X) - predict_proba(X)[:,1]) <= 1e-9` (rtol=0) on sampled rows; exporter exits non-zero if its self-check fails.
- Floor = median of the model's train-fold predictions; rank reference only, never a probability (A2/C6).
- Defaults: `decide(request, mode='ac')`; argparse `--baseline {greedy,no_asks,random,ac}` default `ac`. Baseline modes byte-preserved.
- Outputs strict JSON (`allow_nan=False`); memory <= 1 MiB; empty-state responses exactly as spec section 10.
- Test command (repo root): `python -B -m unittest`. Never pip install.
- Match performance: p95 <= 5 s, hard < 9 s (invoke timeout 10 s), validated ONLY by the realistic timing tests (Task 9: real day-50+ states from a simulator replay with accumulated introductions/feedback, real `pair_features`, real embedded model, ask phase included, measured inside Docker via `evaluate.invoke(evaluate.docker_command(image), ...)` under `--cpus=2 --memory=1g --network=none`); local timings are indicative, Docker timings are authoritative. Pre-registered contingency (spec 8, trigger AMENDED per review finding 2): when `len(candidate_pairs) > 12000`, cap candidates to the top 12,000 by `(-rule_score, a, b)` BEFORE model scoring - deterministic, based on state/candidate count, NEVER on measured elapsed time and never random. Allowed optimizations are semantics-preserving ONLY (byte-identical responses, pinned by a characterization test): typed/normalized tree representation at load, local variable binding in hot loops, per-call eligibility cache, per-call `member_history` memoization cleared at each `decide` entry (added OUTSIDE the verbatim feature block - copied feature lines are never edited). No time-dependent or random cutoffs of any kind.
- Evaluation results never change code (C7); evaluation commands are exactly spec section 14.
- Matching is a GENERAL graph over one member pool (a member may be either endpoint of any edge): unified occupancy structure, canonical edge keys `(min(a, b), max(a, b))`; `kit.advance` raises `ValueError('overlapping allocation')` on any within-decision overlap (kit.py line 147) - overlapping pairs must NEVER be emitted (Task 6 property tests + Task 9 T9 loop).
- Frozen artifact: after Task 9 all policy code is final; `policy.py` is SHA-256-hashed; the Docker image is built from that file; evaluation runs against it; the final verification NEVER re-runs the exporter - only read-only `python -m research.export_model --check` (hash before/after must match).
- Seed hygiene: research train/val worlds are seeds 50000-50799 (rows.csv), local eval seeds 101,102,103 - asserted DISJOINT (T3). Private grading seeds are unknown, never accessible to policy code, never used anywhere.
- Pre-eval diagnostics (`research/export_model.py --diagnose`: within-(world, day) model-vs-greedy ranking on validation rows; floor replay statistics) are read-only and DIAGNOSIS-ONLY, run before outcomes are read: they never trigger tuning, retuning, floor/threshold changes, prevalence subtraction (`score - 0.0094`), probability interpretation, or any code change.

## Review Focus

1. Exporter injection corrupting `policy.py` outside markers -> Task 2 Step 4 inject unit tests + Task 2 Step 12 full-suite run after real export.
2. Feature copy drifting from `research/features.py` (including late-episode masking) -> Task 3 T3 parity (3 variants x 4 days incl. day 45, elementwise, NaN-safe) + stored research-row replay parity + research/eval seed-disjointness.
3. Asks that make `resolve_asks` raise (budget/unavailable/declined) -> Task 5 T6 + Task 9 T9 real loop.
4. Pairs that make `advance` raise (dup/past/infeasible/OVERLAPPING): the population is ONE general graph, not two sides - if A-B is chosen, B is occupied for B-C regardless of orientation -> Task 6 T7 non-bipartite test + no-member-twice property test + Task 9 T9 real loop (`advance` raises `overlapping allocation`, kit.py line 147).
5. Latency that looks fine only on optimistic empty-history states -> Task 9 T10 realistic timing (day 50+ replayed state with accumulated history (pinned replay: 200-member world, 174 available, 96 introductions, 208 feedback records), real features/model, BOTH phases, Docker evaluator constraints); contingency = deterministic count-based cap.
6. NaN leaking into JSON responses -> Task 8 T2 `json.dumps(..., allow_nan=False)`.
7. Container/CI without sklearn (blob decode must stay stdlib) -> Task 2 T4 real-blob decode test (runs in CI).
8. Final verification accidentally re-exporting and REWRITING the frozen artifact -> Task 10: hash-freeze before image build, `--check` read-only verification after eval, exporter never runs post-freeze.
9. Toy blobs bypassing the runtime encoding (JSON -> zlib -> base64) so schema tests fail at decode instead of schema validation -> Task 1 encoding-contract roundtrip test + decode-before-schema assertions.
10. Assuming exactly 200 fitted trees when early stopping fits fewer -> Task 2 exporter `n_iter_` assertion; T4 checks `n_iter == len(trees)` within [1, 200].

---

## File Structure

- Create: `test_policy.py` (root; CI-safe T1-T11; shared builders at top)
- Create: `policy_ac.py` (root; ~20-line local-eval shim)
- Create: `research/export_model.py` (CSV read, train, floor, encode, self-check, inject; CLI modes: default = export (writes policy.py), `--check` = read-only parity/schema verification, `--diagnose` = read-only pre-eval ranking + floor report)
- Modify: `policy.py` (model package, feature copy, ask/match/memory/fallback, dispatch, markers)
- Modify: `research/test_pipeline.py` (T12/T13/T14, sklearn-gated)
- Outputs (not code): `results/*.json` (evaluation), `results/pre_eval_diagnostics.json` (diagnose), `results/artifact.sha256` (freeze), `results/run_log.txt` (commands + exit codes)

---

### Task 1: Model package in policy.py (markers, decode, walk, score)

**Files:**
- Modify: `policy.py` (append after imports; marker region at end; `decide` untouched)
- Test: `test_policy.py` (new file)

**Interfaces:**
- Produces: `MODEL_B64` (module str, marker-delimited); `load_model() -> dict | None` (memoized per blob string; validates schema); `_walk(tree, x) -> float`; `score_row(model, x) -> float`; `_sigmoid(raw) -> float`. Model dict keys: `schema, n_features, feature_keys, floor, baseline, n_iter, trees`; node = `[value]` (leaf) or `[feature, threshold, left, right, missing_left]`.

- [ ] **Step 1: Write the failing tests** - create `test_policy.py`:

```python
"""A+C policy tests (CI-safe: stdlib + kit + research.features only)."""
import base64
import json
import math
import zlib
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent
for p in (str(REPO_ROOT), str(REPO_ROOT / 'research')):
    if p not in sys.path:
        sys.path.insert(0, p)

import kit
import policy


def make_member(mid, available=True, age=30, zone='z1', gender='woman',
                arrived=0, hard_complete=True, soft_goal='long_term',
                soft_pace='steady', ask_status='not_asked'):
    fields = {
        'age_min': 21, 'age_max': 46, 'who_to_meet': ['woman', 'man', 'non_binary'],
        'relationship_structure': 'monogamous', 'smoking': 'no',
        'partner_smoking': 'any', 'has_children': False, 'partner_children': 'any',
        'wants_children': 'unsure', 'acceptable_zones': ['z1', 'z2', 'z3'],
        'schedule': ['weekday_evening', 'weekend_day', 'weekend_evening'],
        'relationship_goal': soft_goal, 'relationship_pace': soft_pace,
        'lifestyle': 'mixed', 'conversations': 'ideas',
        'emotional_availability': 'ready', 'space_for_relationship': 'moderate',
        'relocate': 'unsure'}
    status = {k: 'observed' for k in fields}
    observed_day = {k: 0 for k in fields}
    if not hard_complete:
        for k in kit.HARD[:3]:
            fields[k] = None
            status[k] = ask_status
            observed_day[k] = None
    for key, val in (('relationship_goal', soft_goal), ('relationship_pace', soft_pace)):
        if val is None:
            fields[key] = None
            status[key] = 'not_asked'
            observed_day[key] = None
    return {'member_id': mid, 'pool_id': 'p', 'age': age, 'gender': gender,
            'zone': zone, 'arrived_day': arrived, 'available': available,
            'fields': fields, 'field_status': status,
            'field_observed_day': observed_day, 'source': 'synthetic_questionnaire'}


def make_state(members, day=1, budget=12, introductions=None, feedback=None):
    return {'schema_version': '1.0.0', 'synthetic': True, 'day': day,
            'ask_budget_remaining': budget, 'members': members,
            'introductions': introductions or [], 'feedback': feedback or [],
            'ask_log': []}


def encode_blob(obj):
    """The runtime blob contract: JSON -> zlib -> base64 (must match exporter and load_model)."""
    return base64.b64encode(
        zlib.compress(json.dumps(obj, separators=(',',':')).encode('utf-8'), 9)).decode('ascii')


def decode_blob(blob):
    """Inverse of encode_blob; tests use it to build/assert on decoded objects."""
    return json.loads(zlib.decompress(base64.b64decode(blob.encode('ascii'))).decode('utf-8'))


def toy_obj():
    """One split on feature 0 at 0.5; leaves +1/-1; NaN -> left (missing_left=0)."""
    return {
        'schema': 1, 'n_features': 44, 'feature_keys': ['f%d' % i for i in range(44)],
        'floor': 0.5, 'baseline': 0.0, 'n_iter': 1,
        'trees': [[[1, 0.5, 1, 2, 0], [1.0], [-1.0]]]}


def toy_blob():
    """Toy model encoded with the REAL runtime encoding (not plain JSON)."""
    return encode_blob(toy_obj())


class ModelPackageTests(unittest.TestCase):
    def test_load_model_parses_valid_toy_blob(self):
        with mock.patch.object(policy, 'MODEL_B64', toy_blob()):
            model = policy.load_model()
        self.assertIsNotNone(model)
        self.assertEqual(model['schema'], 1)
        self.assertEqual(model['n_features'], 44)
        self.assertEqual(len(model['feature_keys']), 44)
        self.assertEqual(model['floor'], 0.5)
        self.assertEqual(model['n_iter'], 1)
        self.assertEqual(model['n_iter'], len(model['trees']))

    def test_load_model_rejects_garbage_and_empty(self):
        with mock.patch.object(policy, 'MODEL_B64', 'not-zlib-data'):
            self.assertIsNone(policy.load_model())
        with mock.patch.object(policy, 'MODEL_B64', ''):
            self.assertIsNone(policy.load_model())

    def test_load_model_rejects_wrong_schema(self):
        # decode must SUCCEED first: rejection must come from schema validation, not decoding
        good = decode_blob(toy_blob())              # proves the encoding roundtrip
        self.assertEqual(good['n_features'], 44)
        self.assertEqual(good['n_iter'], len(good['trees']))
        bad = decode_blob(toy_blob())
        bad['n_features'] = 43
        with mock.patch.object(policy, 'MODEL_B64', encode_blob(bad)):
            self.assertIsNone(policy.load_model())
        bad = decode_blob(toy_blob())
        bad['floor'] = float('nan')
        with mock.patch.object(policy, 'MODEL_B64', encode_blob(bad)):
            self.assertIsNone(policy.load_model())
        bad = decode_blob(toy_blob())
        bad['n_iter'] = len(bad['trees']) + 1    # n_iter/tree-count mismatch
        with mock.patch.object(policy, 'MODEL_B64', encode_blob(bad)):
            self.assertIsNone(policy.load_model())

    def test_walk_threshold_semantics_and_nan_branch(self):
        tree = [[1, 0.5, 1, 2, 0], [1.0], [-1.0]]
        self.assertEqual(policy._walk(tree, [0.6]), 1.0)
        self.assertEqual(policy._walk(tree, [0.5]), 1.0)   # <= goes left
        self.assertEqual(policy._walk(tree, [0.9]), -1.0)
        self.assertEqual(policy._walk(tree, [float('nan')]), 1.0)
        tree2 = [[1, 0.5, 1, 2, 1], [1.0], [-1.0]]
        self.assertEqual(policy._walk(tree2, [float('nan')]), -1.0)

    def test_score_row_is_sigmoid_of_baseline_plus_sum(self):
        model = {'schema': 1, 'n_features': 44, 'feature_keys': ['f'] * 44,
                 'floor': 0.0, 'baseline': 0.0,
                 'trees': [[[1, 0.5, 1, 2, 0], [1.0], [-1.0]],
                           [[1, 0.5, 1, 2, 0], [1.0], [-1.0]]]}
        x = [0.6] + [0.0] * 43
        self.assertAlmostEqual(policy.score_row(model, x), 1.0 / (1.0 + math.exp(-2.0)), places=15)
        x = [0.9] + [0.0] * 43
        self.assertAlmostEqual(policy.score_row(model, x), 1.0 / (1.0 + math.exp(2.0)), places=15)

    def test_sigmoid_branches_for_extremes(self):
        self.assertEqual(policy._sigmoid(0.0), 0.5)
        self.assertEqual(policy._sigmoid(700.0), 1.0)
        self.assertGreater(policy._sigmoid(-700.0), 0.0)
        self.assertLess(policy._sigmoid(-700.0), 1e-300)

    def test_marker_region_present_in_policy_source(self):
        src = (REPO_ROOT / 'policy.py').read_text(encoding='utf-8')
        self.assertIn('# BEGIN GENERATED MODEL BLOB', src)
        self.assertIn('# END GENERATED MODEL BLOB', src)

    def test_toy_blob_follows_runtime_encoding_contract(self):
        # blob is exactly base64(zlib(JSON)) - the encoding load_model and the exporter both use
        obj = toy_obj()
        blob = toy_blob()
        self.assertEqual(
            json.loads(zlib.decompress(base64.b64decode(blob.encode('ascii'))).decode('utf-8')),
            obj)
        with mock.patch.object(policy, 'MODEL_B64', blob):
            self.assertIsNotNone(policy.load_model())


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -B -m unittest test_policy -v`
Expected: FAIL with `AttributeError: module 'policy' has no attribute 'MODEL_B64'`.

- [ ] **Step 3: Implement the model package in policy.py**

Add `import base64`, `import zlib` to policy.py's imports. Append (before `if __name__ == '__main__':` is fine; do not touch `decide`):

```python
# --- Model package (generated blob + pure-Python HistGB inference) ---

# BEGIN GENERATED MODEL BLOB (regenerate: python -m research.export_model)
MODEL_B64 = ''
# END GENERATED MODEL BLOB

_LOADED = {}


def load_model():
    """Decode+validate MODEL_B64 once per distinct blob; None routes to fallback."""
    blob = MODEL_B64
    if blob in _LOADED:
        return _LOADED[blob]
    model = None
    try:
        raw = zlib.decompress(base64.b64decode(blob.encode('ascii')))
        obj = json.loads(raw.decode('utf-8'))
        ok = (isinstance(obj, dict) and obj.get('schema') == 1
              and obj.get('n_features') == 44
              and isinstance(obj.get('feature_keys'), list)
              and len(obj['feature_keys']) == 44
              and math.isfinite(obj.get('floor'))
              and math.isfinite(obj.get('baseline'))
              and isinstance(obj.get('n_iter'), int) and not isinstance(obj.get('n_iter'), bool)
              and 1 <= obj['n_iter'] <= 200
              and isinstance(obj.get('trees'), list) and bool(obj['trees']))
        if ok:
            if obj['n_iter'] != len(obj['trees']):   # binary HGB: one tree per fitted iteration
                ok = False
            for tree in obj['trees']:
                if not tree:
                    ok = False
                    break
                for node in tree:
                    if len(node) not in (1, 5):
                        ok = False
                        break
            model = obj if ok else None
    except Exception:
        model = None
    _LOADED[blob] = model
    return model


def _walk(tree, x):
    """One tree -> raw contribution. Leaf [value]; internal [feat, thr, left, right, missing_left]."""
    i = 0
    while True:
        node = tree[i]
        if len(node) == 1:
            return float(node[0])
        value = x[int(node[0])]
        if value != value:  # NaN -> missing branch
            i = int(node[3]) if node[4] else int(node[2])
        elif value <= float(node[1]):
            i = int(node[2])
        else:
            i = int(node[3])


def _sigmoid(raw):
    if raw >= 0.0:
        return 1.0 / (1.0 + math.exp(-raw))
    e = math.exp(raw)
    return e / (1.0 + e)


def score_row(model, x):
    """Ranking score in (0,1): sigmoid(baseline + sum of leaf values). No lr scaling (A2/C6)."""
    raw = float(model['baseline'])
    for tree in model['trees']:
        raw += _walk(tree, x)
    return _sigmoid(raw)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -B -m unittest test_policy -v` -> Expected: PASS (8 tests).

- [ ] **Step 5: Run the full suite**

Run: `python -B -m unittest` -> Expected: PASS, 88 tests (80 existing + 8 new).

---

### Task 2: Exporter (train, floor, encode, self-check, inject) + T12/T13/T14

**Files:**
- Create: `research/export_model.py`
- Modify: `policy.py` (only the marker region, by the exporter)
- Test: `test_policy.py` (inject + T4), `research/test_pipeline.py` (T12/T13/T14)

**Interfaces:**
- Consumes: Task 1 `load_model`/`score_row`; `analyze.world_split/build_dataset/fit_models`; `research/out_scale800/rows.csv`.
- Produces: `export_model.inject_blob(source, b64) -> str`; `export_model.rows_from_csv(path) -> list[dict]` (keys: `world_seed, variant, day, collector_seed, policy, features, label`); `export_model.sk_tree_to_nodes(predictor) -> list[node]`; `export_model.sk_model_to_dict(model, feature_keys, floor) -> dict` (includes `n_iter`; hard-asserts flattened tree count == `model.n_iter_`); `export_model.check_only() -> int`; `export_model.diagnose() -> int`; populated `MODEL_B64`. Top of `export_model.py` must stay stdlib+`features` only (no numpy/analyze at module level) so CI can import `inject_blob`.
- Tests import via `from export_model import ...` (research dir on sys.path in both test files).

- [ ] **Step 1: Write the failing inject tests** - append to `test_policy.py`:

```python
class ExportInjectTests(unittest.TestCase):
    def test_inject_replaces_only_marker_region_and_is_idempotent(self):
        from export_model import inject_blob
        src = ('HEAD\n# BEGIN GENERATED MODEL BLOB\n'
               "MODEL_B64 = 'old'\n"
               '# END GENERATED MODEL BLOB\nTAIL\n')
        once = inject_blob(src, 'QUJD')
        self.assertTrue(once.startswith('HEAD\n# BEGIN GENERATED MODEL BLOB'))
        self.assertTrue(once.endswith('# END GENERATED MODEL BLOB\nTAIL\n'))
        self.assertIn("MODEL_B64 = 'QUJD'", once)
        self.assertNotIn("'old'", once)
        self.assertEqual(once, inject_blob(once, 'QUJD'))

    def test_inject_without_markers_raises(self):
        from export_model import inject_blob
        with self.assertRaises(ValueError):
            inject_blob('no markers here', 'QUJD')
```

- [ ] **Step 2: Run to verify failure**

Run: `python -B -m unittest test_policy.ExportInjectTests -v` -> Expected: FAIL `ModuleNotFoundError: No module named 'export_model'`.

- [ ] **Step 3: Implement research/export_model.py** (module top = stdlib + features only; sklearn/numpy/analyze imported lazily inside functions):

```python
"""Export the train-split MSMI HistGB into policy.py's marker region.

Run: python -m research.export_model            export + parity self-check; writes policy.py markers; exit 0 iff PASS
     python -m research.export_model --check    read-only: schema/n_iter/floor vs fresh refit + T12 parity; NEVER writes
     python -m research.export_model --diagnose read-only: pre-eval ranking + floor report -> results/pre_eval_diagnostics.json
"""
import base64
import csv
import json
import sys
import zlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for p in (str(REPO_ROOT), str(REPO_ROOT / 'research')):
    if p not in sys.path:
        sys.path.insert(0, p)

import features

BEGIN = '# BEGIN GENERATED MODEL BLOB'
END = '# END GENERATED MODEL BLOB'


def inject_blob(source, b64):
    if BEGIN not in source or END not in source:
        raise ValueError('model blob markers missing from policy.py')
    head, rest = source.split(BEGIN, 1)
    _, tail = rest.split(END, 1)
    nl = '\r\n' if '\r\n' in rest else '\n'   # preserve the file's own line endings
    return head + BEGIN + nl + "MODEL_B64 = '%s'" % b64 + nl + END + tail


def rows_from_csv(path):
    """rows.csv -> research-shaped rows (world_seed int, label int|None, NaN preserved)."""
    out = []
    with open(path, newline='', encoding='utf-8') as handle:
        for rec in csv.DictReader(handle):
            feats = {}
            for key in features.FEATURE_KEYS:
                text = rec['feat_' + key]
                feats[key] = float(text) if text != '' else float('nan')
            label = rec['label']
            out.append({'world_seed': int(rec['world_seed']),
                        'variant': rec['variant'],
                        'day': int(rec['day']),
                        'collector_seed': int(rec['collector_seed']),
                        'policy': rec['policy'],
                        'features': feats,
                        'label': int(label) if label != '' else None})
    return out


def sk_tree_to_nodes(predictor):
    """TreePredictor -> [value] leaf | [feature, threshold, left, right, missing_left]."""
    nodes = []
    for nd in predictor.nodes:
        if bool(nd['is_leaf']):
            nodes.append([float(nd['value'])])
        else:
            nodes.append([int(nd['feature_idx']), float(nd['num_threshold']),
                          int(nd['left']), int(nd['right']),
                          int(nd['missing_go_to_left'])])
    return nodes


def sk_model_to_dict(model, feature_keys, floor):
    trees = [sk_tree_to_nodes(t) for forest in model._predictors for t in forest]
    n_iter = int(model.n_iter_)
    if len(trees) != n_iter:
        # binary HGB: one tree per fitted iteration - a mismatch means _predictors shape changed
        raise AssertionError('flattened tree count %d != model.n_iter_ %d' % (len(trees), n_iter))
    return {'schema': 1, 'n_features': len(feature_keys),
            'feature_keys': list(feature_keys), 'floor': float(floor),
            'baseline': float(model._baseline_prediction.reshape(-1)[0]),
            'n_iter': n_iter, 'trees': trees}
```

- [ ] **Step 4: Run inject tests to verify they pass**

Run: `python -B -m unittest test_policy.ExportInjectTests -v` -> Expected: PASS.

- [ ] **Step 5: Write T13 (threshold/missing parity vs sklearn)** - append to `research/test_pipeline.py`:

```python
def _have_sklearn():
    try:
        import numpy  # noqa: F401
        import sklearn  # noqa: F401
        return True
    except ImportError:
        return False


@unittest.skipUnless(_have_sklearn(), 'numpy+sklearn required')
class TestExportInferenceContract(unittest.TestCase):
    """T13: pure walk matches sklearn (<= threshold + missing branch)."""

    @classmethod
    def setUpClass(cls):
        import numpy as np
        from sklearn.ensemble import HistGradientBoostingClassifier
        # crafted 1-D data: split threshold = midpoint 1.5 between values 1.0 and 2.0
        X = np.array([[v] for v in [0.0, 1.0, 2.0, 3.0, 4.0] * 10], dtype=float)
        y = (X[:, 0] >= 1.5).astype(int)
        cls.m = HistGradientBoostingClassifier(random_state=0, max_iter=1,
                                               learning_rate=1.0,
                                               max_leaf_nodes=2).fit(X, y)
        import policy
        from export_model import sk_model_to_dict
        d = sk_model_to_dict(cls.m, ['f0'], 0.5)
        cls.pure = {'schema': 1, 'n_features': 1, 'feature_keys': ['f0'],
                    'floor': 0.5, 'baseline': d['baseline'], 'trees': d['trees']}

    @staticmethod
    def _sigmoid(raw):
        import math
        return 1.0 / (1.0 + math.exp(-raw)) if raw >= 0 else math.exp(raw) / (1.0 + math.exp(raw))

    def test_t13_parity_on_probes(self):
        import numpy as np
        import policy
        probes = np.array([[0.0], [1.0], [1.5], [2.0], [3.0], [float('nan')]])
        expect = self.m.predict_proba(probes)[:, 1]
        for i, row in enumerate(probes):
            got = policy.score_row(self.pure, [float(row[0])])
            self.assertLessEqual(abs(got - float(expect[i])), 1e-9,
                                 msg='probe %r: pure=%r sklearn=%r'
                                     % (row.tolist(), got, expect[i]))

    def test_t13_sample_exactly_at_threshold_takes_left_branch(self):
        import policy
        root = self.pure['trees'][0][0]
        threshold = root[1]
        left_leaf = self.pure['trees'][0][root[2]][0]
        self.assertAlmostEqual(policy.score_row(self.pure, [threshold]),
                               self._sigmoid(self.pure['baseline'] + left_leaf), places=15)
```

- [ ] **Step 6: Run T13 (confirms Task 1 walk semantics against sklearn)**

Run: `python -B -m unittest research.test_pipeline.TestExportInferenceContract -v`
Expected: PASS. If FAIL: the Task 1 `_walk` direction/missing logic is wrong - fix `_walk`, do not adjust the test.

- [ ] **Step 7: Write failing T12/T14 (hard gates)** - append to `research/test_pipeline.py`:

```python
def _load_scale_rows():
    path = REPO_ROOT / 'research' / 'out_scale800' / 'rows.csv'
    if not path.exists():
        raise unittest.SkipTest('research/out_scale800/rows.csv not present')
    from export_model import rows_from_csv
    return rows_from_csv(path)


@unittest.skipUnless(_have_sklearn(), 'numpy+sklearn required')
class TestExportParityGates(unittest.TestCase):
    """T12 (HARD): per-row parity atol 1e-9 rtol 0. T14: val AUC 0.5937 +/- 0.001."""

    @classmethod
    def setUpClass(cls):
        import numpy as np
        import policy
        rows = _load_scale_rows()
        train_rows, val_rows = analyze.world_split(rows, val_frac=0.2, split_seed=0)
        cls.Xtr, cls.ytr, _ = analyze.build_dataset(train_rows, target='label')
        cls.Xva, cls.yva, _ = analyze.build_dataset(val_rows, target='label')
        cls.sk = dict(analyze.fit_models(cls.Xtr, cls.ytr))['hist_gb']
        cls.pm = policy.load_model()
        if cls.pm is None:
            raise AssertionError('MODEL_B64 empty/invalid - run: python -m research.export_model')
        rng = np.random.RandomState(0)
        cls.sample_idx = rng.choice(len(cls.Xtr), size=500, replace=False)

    def test_t12_row_parity_hard_gate(self):
        import policy
        worst = 0.0
        for i in self.sample_idx:
            x = [float(v) for v in self.Xtr[i]]
            pure = policy.score_row(self.pm, x)
            sk = float(self.sk.predict_proba(self.Xtr[i:i + 1])[0, 1])
            worst = max(worst, abs(pure - sk))
        self.assertLessEqual(worst, 1e-9, 'T12 HARD GATE violated: max abs diff %r' % worst)

    def test_t14_val_auc_reproduction(self):
        import numpy as np
        from sklearn.metrics import roc_auc_score
        auc_sk = float(roc_auc_score(self.yva, self.sk.predict_proba(self.Xva)[:, 1]))
        self.assertLess(abs(auc_sk - 0.5937), 0.001,
                        'refit sklearn val AUC %r drifted from reported 0.5937' % auc_sk)
        import policy
        pure = np.array([policy.score_row(self.pm, [float(v) for v in row])
                         for row in self.Xva])
        auc_pure = float(roc_auc_score(self.yva, pure))
        self.assertLess(abs(auc_pure - 0.5937), 0.001,
                        'pure scorer val AUC %r drifted from 0.5937' % auc_pure)


@unittest.skipUnless(_have_sklearn(), 'numpy+sklearn required')
class TestExportCheckMode(unittest.TestCase):
    """--check verifies the embedded blob read-only: never rewrites policy.py."""

    def test_check_mode_passes_and_does_not_write_policy(self):
        import subprocess
        import sys
        policy_path = REPO_ROOT / 'policy.py'
        before = policy_path.read_bytes()
        proc = subprocess.run(
            [sys.executable, '-m', 'research.export_model', '--check'],
            cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=900)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn('check OK', proc.stdout)
        self.assertEqual(policy_path.read_bytes(), before,
                         '--check must never rewrite policy.py')
```

Note: `REPO_ROOT` IS module-level in `research/test_pipeline.py` (line 6); `analyze` is NOT imported at module level there - always `import analyze` inside `setUpClass` (or the test method), matching that file's local-import style.

- [ ] **Step 8: Run to verify failure (blob still empty)**

Run: `python -B -m unittest research.test_pipeline.TestExportParityGates research.test_pipeline.TestExportCheckMode -v`
Expected: TestExportParityGates ERROR with `AssertionError: MODEL_B64 empty/invalid - run: python -m research.export_model`; TestExportCheckMode FAIL (`CHECK FAIL: MODEL_B64 empty/invalid`, returncode 1). Both prove the pre-export state fails.

- [ ] **Step 9: Implement exporter main and run it** - append to `research/export_model.py`:

```python
def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if '--check' in argv:
        return check_only()
    if '--diagnose' in argv:
        return diagnose()
    if argv:
        print('usage: python -m research.export_model [--check | --diagnose]',
              file=sys.stderr)
        return 2
    import numpy as np
    import analyze
    from sklearn.metrics import roc_auc_score
    rows_path = REPO_ROOT / 'research' / 'out_scale800' / 'rows.csv'
    policy_path = REPO_ROOT / 'policy.py'
    rows = rows_from_csv(rows_path)
    train_rows, val_rows = analyze.world_split(rows, val_frac=0.2, split_seed=0)
    Xtr, ytr, _ = analyze.build_dataset(train_rows, target='label')
    Xva, yva, _ = analyze.build_dataset(val_rows, target='label')
    models = dict(analyze.fit_models(Xtr, ytr))
    if 'hist_gb' not in models:
        print('FATAL: hist_gb model could not be fit', file=sys.stderr)
        return 1
    model = models['hist_gb']
    floor = float(np.median(analyze.predict(model, Xtr)))
    blob = sk_model_to_dict(model, features.FEATURE_KEYS, floor)

    # T12-style self-check (HARD): never emit a blob that fails parity
    import policy
    rng = np.random.RandomState(0)
    worst = 0.0
    for i in rng.choice(len(Xtr), size=500, replace=False):
        x = [float(v) for v in Xtr[i]]
        pure = policy.score_row(blob, x)
        sk = float(model.predict_proba(Xtr[i:i + 1])[0, 1])
        worst = max(worst, abs(pure - sk))
    if worst > 1e-9:
        print('FATAL: parity self-check failed, max abs diff %r' % worst, file=sys.stderr)
        return 1

    b64 = base64.b64encode(zlib.compress(
        json.dumps(blob, separators=(',', ':')).encode('utf-8'), 9)).decode('ascii')
    source = policy_path.read_bytes().decode('utf-8')   # byte-faithful: no newline translation
    policy_path.write_bytes(inject_blob(source, b64).encode('utf-8'))
    val_auc = float(roc_auc_score(yva, analyze.predict(model, Xva)))
    print('export OK: train_rows=%d val_auc=%.4f floor=%.6g blob_b64=%d bytes trees=%d'
          % (len(Xtr), val_auc, floor, len(b64), len(blob['trees'])))
    print('parity self-check: max abs diff %g <= 1e-9 PASS' % worst)
    return 0


def check_only():
    """Read-only: embedded blob vs fresh refit (schema, n_iter, floor, baseline, parity).
    Never writes policy.py - the frozen artifact stays byte-identical."""
    import numpy as np
    import analyze
    import policy
    rows = rows_from_csv(REPO_ROOT / 'research' / 'out_scale800' / 'rows.csv')
    train_rows, _ = analyze.world_split(rows, val_frac=0.2, split_seed=0)
    Xtr, ytr, _ = analyze.build_dataset(train_rows, target='label')
    pm = policy.load_model()
    if pm is None:
        print('CHECK FAIL: MODEL_B64 empty/invalid', file=sys.stderr)
        return 1
    model = dict(analyze.fit_models(Xtr, ytr))['hist_gb']
    floor = float(np.median(analyze.predict(model, Xtr)))
    blob = sk_model_to_dict(model, features.FEATURE_KEYS, floor)
    for key in ('schema', 'n_features', 'feature_keys', 'floor', 'baseline', 'n_iter'):
        if pm.get(key) != blob.get(key):
            print('CHECK FAIL: %r mismatch vs fresh refit' % key, file=sys.stderr)
            return 1
    rng = np.random.RandomState(0)
    worst = 0.0
    for i in rng.choice(len(Xtr), size=500, replace=False):
        x = [float(v) for v in Xtr[i]]
        worst = max(worst, abs(policy.score_row(pm, x)
                               - float(model.predict_proba(Xtr[i:i + 1])[0, 1])))
    if worst > 1e-9:
        print('CHECK FAIL: parity max abs diff %r > 1e-9' % worst, file=sys.stderr)
        return 1
    print('check OK: schema/n_iter/floor/baseline match fresh refit; parity max abs diff %g <= 1e-9'
          % worst)
    return 0


def diagnose():
    """Read-only pre-eval diagnosis -> results/pre_eval_diagnostics.json.

    (a) within-state ranking on validation rows: AUC(model) vs AUC(greedy proxy =
        soft_match_count) inside each (world_seed, day, collector_seed, policy) state
        group + top-half lift - the operational regime is WITHIN-state ranking.
    (b) floor coverage per state group: fraction of stored feasible candidate pairs
        >= floor; groups with zero above-floor pairs; by variant.
    Stored rows ARE candidate pairs captured in real kit states at that point; full
    mid-run state regeneration would duplicate collect.py's bookkeeping and is out of
    scope for a diagnosis-only step. Never tunes, never changes code, never reads
    evaluation results."""
    import statistics
    import analyze
    import policy
    rows = rows_from_csv(REPO_ROOT / 'research' / 'out_scale800' / 'rows.csv')
    _, val_rows = analyze.world_split(rows, val_frac=0.2, split_seed=0)
    pm = policy.load_model()
    if pm is None:
        print('FATAL: invalid MODEL_B64 - run export first', file=sys.stderr)
        return 1
    floor = float(pm['floor'])

    def auc(y, s):
        pos = [s[i] for i in range(len(y)) if y[i] == 1]
        neg = [s[i] for i in range(len(y)) if y[i] == 0]
        if not pos or not neg:
            return None
        return sum((p > q) + 0.5 * (p == q) for p in pos for q in neg) / (len(pos) * len(neg))

    def xvec(rec):
        return [rec['features'][k] for k in features.FEATURE_KEYS]

    groups = {}
    for rec in val_rows:
        key = (rec['world_seed'], rec['day'], rec['collector_seed'], rec['policy'])
        groups.setdefault(key, []).append(rec)

    aucs_model, aucs_rule, deltas, lifts = [], [], [], []
    single_class = 0
    pairs = above = zero_above = 0
    by_variant = {}
    for key in sorted(groups):
        g = groups[key]
        scores = [policy.score_row(pm, xvec(r)) for r in g]
        st = by_variant.setdefault(g[0]['variant'],
                                   {'groups': 0, 'pairs': 0, 'above': 0,
                                    'zero_above_groups': 0})
        st['groups'] += 1
        n_above = sum(1 for s in scores if s >= floor)
        st['pairs'] += len(g)
        st['above'] += n_above
        pairs += len(g)
        above += n_above
        if n_above == 0:
            st['zero_above_groups'] += 1
            zero_above += 1
        lab = [(r['label'], s) for r, s in zip(g, scores) if r['label'] is not None]
        ys = [t[0] for t in lab]
        ss = [t[1] for t in lab]
        if len(set(ys)) < 2:
            single_class += 1
            continue
        am = auc(ys, ss)
        ar = auc(ys, [r['features']['soft_match_count']
                      for r, s in zip(g, scores) if r['label'] is not None])
        aucs_model.append(am)
        if ar is not None:
            aucs_rule.append(ar)
            deltas.append(am - ar)
        order = sorted(range(len(lab)), key=lambda i: -ss[i])
        half = order[:max(1, len(lab) // 2)]
        lifts.append(sum(ys[i] for i in half) / len(half) - sum(ys) / len(ys))

    def mean(v):
        return statistics.fmean(v) if v else None

    def med(v):
        return statistics.median(v) if v else None
    report = {
        'note': 'pre-eval diagnosis only; no tuning, no calibration, never reads evaluation results',
        'n_val_rows': len(val_rows),
        'ranking': {
            'state_groups': len(groups),
            'scored_groups': len(aucs_model),
            'single_class_groups': single_class,
            'model_auc_mean': mean(aucs_model),
            'model_auc_median': med(aucs_model),
            'rule_auc_mean': mean(aucs_rule),
            'rule_auc_median': med(aucs_rule),
            'model_minus_rule_mean': mean(deltas),
            'model_beats_rule_frac': (sum(1 for d in deltas if d > 0) / len(deltas))
                                     if deltas else None,
            'top_half_lift_mean': mean(lifts)},
        'floor': {
            'floor': floor,
            'state_groups': len(groups),
            'pairs': pairs,
            'above_floor_pairs': above,
            'above_floor_frac': (above / pairs) if pairs else None,
            'zero_above_floor_groups': zero_above,
            'by_variant': by_variant}}
    out = REPO_ROOT / 'results' / 'pre_eval_diagnostics.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False),
                   encoding='utf-8')
    print('diagnose OK: scored_groups=%d model_auc_mean=%s above_floor_frac=%s -> %s'
          % (len(aucs_model), report['ranking']['model_auc_mean'],
             report['floor']['above_floor_frac'], out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
```

- [ ] **Step 10: Run the exporter**

Run: `python -m research.export_model` (1-3 minutes: 86 MB CSV + 209k-row fit + self-check)
Expected: `export OK: train_rows=209238 val_auc=0.5937 ... trees=<n_iter>` + `parity self-check ... PASS`, exit 0 - `<n_iter>` is the ACTUAL fitted count in [1, 200] (early stopping may end sooner; the exporter hard-asserts it equals `model.n_iter_`); `policy.py` now contains a populated `MODEL_B64 = '...'` line. If val_auc deviates from 0.5937 by >= 0.001: STOP - split/params wrong (check `val_frac=0.2, split_seed=0`, target `label`, `random_state=0`); do not proceed until it matches.
Then smoke-run the read-only modes: `python -m research.export_model --check` -> `check OK ...`, exit 0 (fresh refit + parity vs embedded blob, writes nothing); `python -m research.export_model --diagnose` -> `diagnose OK ... -> results/pre_eval_diagnostics.json`, exit 0. READ the diagnose JSON now (ranking + floor coverage) - it is re-run authoritatively in Task 10 before evaluation; it never triggers code changes (C7).

- [ ] **Step 11: Write failing T4 real-blob guard** - append to `test_policy.py`:

```python
class RealBlobGuardTests(unittest.TestCase):
    """T4: real embedded blob well-formed; decodes with stdlib only (CI has no sklearn)."""

    def test_t4_real_blob_well_formed(self):
        src = (REPO_ROOT / 'policy.py').read_text(encoding='utf-8')
        begin = src.index('# BEGIN GENERATED MODEL BLOB')
        end = src.index('# END GENERATED MODEL BLOB')
        region = src[begin:end]
        self.assertIn("MODEL_B64 = '", region)
        model = policy.load_model()
        self.assertIsNotNone(model, 'real blob must decode with stdlib only')
        self.assertEqual(model['schema'], 1)
        self.assertEqual(model['n_features'], 44)
        self.assertEqual(len(model['feature_keys']), 44)
        import features
        self.assertEqual(model['feature_keys'], features.FEATURE_KEYS)
        self.assertTrue(math.isfinite(model['floor']) and model['floor'] > 0.0)
        self.assertTrue(1 <= model['n_iter'] <= 200)
        self.assertEqual(model['n_iter'], len(model['trees']))
        for tree in model['trees']:
            for node in tree:
                self.assertIn(len(node), (1, 5))
```

- [ ] **Step 12: Run T4 and the full suite**

Run: `python -B -m unittest test_policy.RealBlobGuardTests -v`, then `python -B -m unittest`
Expected: PASS everywhere; T12/T14 now PASS (T14 spends ~1-3 min pure-scoring 50k val rows; the refit happens once in `setUpClass`). Full-suite count: 88 + 8 = 96.

---

### Task 3: Feature block copy + T3 parity

**Files:**
- Modify: `policy.py` (append feature block after model package; add `import kit` to top imports)
- Test: `test_policy.py`

**Interfaces:**
- Produces (verbatim from `research/features.py`): constants `WEIGHTS, SOFT, HARD, HIST_METRICS, PROFILE_KEYS, HARD_KEYS, WHO_KEYS, SOFT_MATCH_KEYS, SOFT_OBS_KEYS, SOFT_AGG_KEYS, TEMPORAL_KEYS, HIST_KEYS, COMP_KEYS, FEATURE_KEYS, FEATURE_GROUPS, NAN`; functions `smoothing, _visible, _field, _feedback_upto, member_history, pair_features(state, a_id, b_id, t) -> dict`.
- Consumed by Tasks 5-9: `pair_features`, `FEATURE_KEYS`, `eligibility` (already imported).

- [ ] **Step 1: Write the failing T3 parity test** - append to `test_policy.py`:

```python
class FeatureParityTests(unittest.TestCase):
    """T3: policy feature block == research features.py, elementwise (NaN == NaN)."""

    @staticmethod
    def _capture_states():
        states = []
        for seed, variant in ((7, 'development'), (8, 'cold_start'), (9, 'sparse')):
            sim = kit.Simulator(kit.generate(seed, 60, variant=variant))
            for day in range(46):
                state = sim.observe()
                if day in (0, 5, 11, 45):   # day 45 exercises late-episode masking
                    states.append(state)
                sim.resolve_asks(kit.baseline_asks(state))
                sim.advance(kit.baseline_match(sim.observe()))
        return states

    @staticmethod
    def _same(a, b):
        if isinstance(a, float) and isinstance(b, float) and a != a and b != b:
            return True
        return a == b

    def test_t3_feature_keys_order_identical(self):
        import features
        self.assertEqual(policy.FEATURE_KEYS, features.FEATURE_KEYS)

    def test_t3_pair_features_identical_across_variants_and_days(self):
        import itertools
        import features
        checked = 0
        for state in self._capture_states():
            t = state['day']
            ids = [m['member_id'] for m in state['members']]
            pairs = list(itertools.combinations(ids, 2))
            sample = pairs[:5]
            for a, b in pairs[5:300]:
                ma = next(m for m in state['members'] if m['member_id'] == a)
                mb = next(m for m in state['members'] if m['member_id'] == b)
                if kit.eligibility(ma, mb)['status'] == 'feasible':
                    sample.append((a, b))
                    break
            for a, b in sample:
                mine = policy.pair_features(state, a, b, t)
                theirs = features.pair_features(state, a, b, t)
                self.assertEqual(list(mine), list(theirs))
                for key in policy.FEATURE_KEYS:
                    self.assertTrue(self._same(mine[key], theirs[key]),
                                    'day %s pair %s key %s: %r != %r'
                                    % (t, (a, b), key, mine[key], theirs[key]))
                checked += 1
        self.assertGreaterEqual(checked, 24)  # 3 variants x 4 days (incl. day 45) x >=2 pairs


class ResearchRowParityTests(unittest.TestCase):
    """Stored research rows.csv == policy.pair_features on replayed simulator states."""

    def test_research_stored_rows_match_policy_features_on_replay(self):
        import csv as _csv
        from collect import RandomCollector
        rows_path = REPO_ROOT / 'research' / 'out_scale800' / 'rows.csv'
        if not rows_path.exists():
            raise unittest.SkipTest('research/out_scale800/rows.csv not present')
        # rows.csv is canonically sorted; take the first 3 rollouts' day<=15 rows
        keys, stored = [], {}
        with rows_path.open(newline='', encoding='utf-8') as fh:
            for rec in _csv.DictReader(fh):
                if int(rec['day']) > 15:
                    continue
                key = (int(rec['world_seed']), rec['variant'], rec['policy'],
                       int(rec['collector_seed']))
                if key not in stored:
                    if len(keys) >= 3:
                        break
                    keys.append(key)
                    stored[key] = {}
                stored[key][(int(rec['day']), rec['a'], rec['b'])] = rec
        self.assertTrue(keys, 'rows.csv has no day<=15 rows')
        checked = 0
        for wseed, variant, pol, cseed in keys:
            rollout = (wseed, variant, pol, cseed)
            world = kit.generate(wseed, 200, 'research', variant)
            sim = kit.Simulator(world)
            collector = RandomCollector(seed=cseed) if pol == 'random' else None
            replayed = {}
            for t in range(16):   # exactly collect_rows' per-day mechanics, day 0..15
                state = sim.observe()
                asks = collector.asks(state) if collector else kit.baseline_asks(state)
                sim.resolve_asks(asks)
                state = sim.observe()
                pairs = collector.match(state) if collector else kit.baseline_match(state)
                for pair in pairs:
                    a, b = sorted(pair)
                    replayed[(t, a, b)] = policy.pair_features(state, a, b, t)
                sim.advance(pairs)
            want = stored[rollout]
            self.assertEqual(set(want), set(replayed),
                             'stored vs replayed (day, a, b) mismatch for %r' % (rollout,))
            for rkey, feats in sorted(replayed.items()):
                rec = want[rkey]
                for k in policy.FEATURE_KEYS:
                    text = rec['feat_' + k]
                    stored_v = float(text) if text != '' else float('nan')
                    got = feats[k]
                    same = (got == stored_v) or (got != got and stored_v != stored_v)
                    self.assertTrue(same, 'rollout %r %r key %s: %r != %r'
                                    % (rollout, rkey, k, got, stored_v))
                checked += 1
        self.assertGreaterEqual(checked, 5)


class SeedHygieneTests(unittest.TestCase):
    """Research worlds must never overlap the local eval seeds {101, 102, 103}."""

    def test_research_and_eval_seeds_are_disjoint(self):
        import csv as _csv
        rows_path = REPO_ROOT / 'research' / 'out_scale800' / 'rows.csv'
        if not rows_path.exists():
            raise unittest.SkipTest('research/out_scale800/rows.csv not present')
        seen = set()
        with rows_path.open(newline='', encoding='utf-8') as fh:
            for rec in _csv.DictReader(fh):
                seen.add(int(rec['world_seed']))
        self.assertTrue(seen, 'rows.csv is empty')
        leaked = seen & {101, 102, 103}
        self.assertFalse(leaked,
                         'local eval seeds leaked into research worlds: %r' % sorted(leaked))
        # Private grading seeds are unknown and never accessible to policy code (T11).
```

- [ ] **Step 2: Run to verify failure**

Run: `python -B -m unittest test_policy.FeatureParityTests test_policy.ResearchRowParityTests test_policy.SeedHygieneTests -v` -> Expected: FeatureParityTests + ResearchRowParityTests FAIL with `AttributeError` (`FEATURE_KEYS`/`pair_features` missing); SeedHygieneTests PASS from the start (data guard, policy-independent).

- [ ] **Step 3: Copy the feature block into policy.py**

1. Add `import kit` to policy.py's top imports (keep the existing `from kit import ...` line).
2. In `research/features.py`, copy EVERYTHING from the line `WEIGHTS = {'relationship_goal': ...` through end of file, EXCEPT these four names (skip their definitions entirely): `FORBIDDEN_TOKENS`, `STRUCTURE_INFORMED`, `audit_feature_keys`, `audit_structure_disclosure`. Do not copy the module docstring or `import kit`. Do not modify a single copied line. Paste into `policy.py` after the model package section.
3. Sanity: `python -c "import policy; print(len(policy.FEATURE_KEYS), callable(policy.pair_features))"` -> `44 True`.

- [ ] **Step 4: Run T3 to verify it passes**

Run: `python -B -m unittest test_policy.FeatureParityTests -v` -> Expected: PASS (>=24 pair comparisons across 3 variants x 4 days incl. day 45).

- [ ] **Step 5: Run the full suite**

Run: `python -B -m unittest` -> Expected: PASS (100 tests).

---

### Task 4: Memory summary (T2 part 1)

**Files:**
- Modify: `policy.py` (add `memory_summary` after the model package)
- Test: `test_policy.py`

**Interfaces:**
- Produces: `memory_summary(state) -> dict`: `{}` for empty members, else `{'v': 1, 'm': {member_id: [n_intro, n_dates, n_second_yes, n_second_no]}}`, counting only feedback with `observed_day <= state['day']`.

- [ ] **Step 1: Write the failing tests** - append to `test_policy.py`:

```python
class MemoryTests(unittest.TestCase):
    def test_empty_members_returns_empty_dict(self):
        self.assertEqual(policy.memory_summary(make_state([])), {})

    def test_counts_and_observed_day_cutoff(self):
        members = [make_member('a'), make_member('b'), make_member('c')]
        intros = [{'introduction_id': 'i1', 'user_a': 'a', 'user_b': 'b',
                   'assigned_day': 0, 'response_deadline_day': 5,
                   'logging_policy': 'h', 'propensity': None}]
        feedback = [
            {'introduction_id': 'i1', 'member_id': 'a', 'event': 'introduction_response',
             'value': 'yes', 'missing_reason': None, 'occurred_day': 1, 'observed_day': 1},
            {'introduction_id': 'i1', 'member_id': None, 'event': 'date_happened',
             'value': True, 'missing_reason': None, 'occurred_day': 4, 'observed_day': 4},
            {'introduction_id': 'i1', 'member_id': 'a', 'event': 'second_meeting_intention',
             'value': 'yes', 'missing_reason': None, 'observed_day': 6},
            {'introduction_id': 'i1', 'member_id': 'b', 'event': 'second_meeting_intention',
             'value': 'no', 'missing_reason': None, 'observed_day': 6},
            {'introduction_id': 'i1', 'member_id': None, 'event': 'date_happened',
             'value': True, 'missing_reason': None, 'occurred_day': 9, 'observed_day': 9},
        ]
        mem = policy.memory_summary(make_state(members, day=7,
                                               introductions=intros, feedback=feedback))
        self.assertEqual(mem['v'], 1)
        self.assertEqual(mem['m']['a'], [1, 1, 1, 0])
        self.assertEqual(mem['m']['b'], [1, 1, 0, 1])
        self.assertEqual(mem['m']['c'], [0, 0, 0, 0])

    def test_future_events_excluded(self):
        members = [make_member('a'), make_member('b')]
        intros = [{'introduction_id': 'i1', 'user_a': 'a', 'user_b': 'b',
                   'assigned_day': 0, 'response_deadline_day': 5,
                   'logging_policy': 'h', 'propensity': None}]
        feedback = [{'introduction_id': 'i1', 'member_id': 'a',
                     'event': 'second_meeting_intention', 'value': 'yes',
                     'missing_reason': None, 'observed_day': 8}]
        mem = policy.memory_summary(make_state(members, day=7,
                                               introductions=intros, feedback=feedback))
        self.assertEqual(mem['m']['a'], [1, 0, 0, 0])

    def test_json_safe_and_size_bounded(self):
        members = [make_member('syn_%032x' % i) for i in range(200)]
        mem = policy.memory_summary(make_state(members))
        text = json.dumps(mem, allow_nan=False)
        self.assertLess(len(text.encode('utf-8')), 1024 * 1024)
```

- [ ] **Step 2: Run to verify failure**

Run: `python -B -m unittest test_policy.MemoryTests -v` -> Expected: FAIL `AttributeError: module 'policy' has no attribute 'memory_summary'`.

- [ ] **Step 3: Implement memory_summary** - append to `policy.py`:

```python
def memory_summary(state):
    """Restart-safe per-member counters from observable state only (v1 decisions do not read it)."""
    members = state.get('members') or []
    if not members:
        return {}
    day = state.get('day', 0)
    counts = {m['member_id']: [0, 0, 0, 0] for m in members}
    for intro in state.get('introductions') or []:
        for uid in (intro['user_a'], intro['user_b']):
            if uid in counts:
                counts[uid][0] += 1
    pair_of = {}
    for intro in state.get('introductions') or []:
        pair_of[intro['introduction_id']] = (intro['user_a'], intro['user_b'])
    for ev in state.get('feedback') or []:
        observed = ev.get('observed_day')
        if observed is None or observed > day:
            continue
        if ev.get('event') == 'date_happened' and ev.get('value'):
            for uid in pair_of.get(ev.get('introduction_id'), ()):
                if uid in counts:
                    counts[uid][1] += 1
        elif ev.get('event') == 'second_meeting_intention':
            uid = ev.get('member_id')
            if uid in counts:
                if ev.get('value') == 'yes':
                    counts[uid][2] += 1
                elif ev.get('value') == 'no':
                    counts[uid][3] += 1
    return {'v': 1, 'm': counts}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -B -m unittest test_policy.MemoryTests -v` -> Expected: PASS (4 tests).

- [ ] **Step 5: Run the full suite**

Run: `python -B -m unittest` -> Expected: PASS (104 tests).

---

### Task 5: Ask policy (T6)

**Files:**
- Modify: `policy.py` (add `_past_pairs`, `ac_asks`)
- Test: `test_policy.py`

**Interfaces:**
- Consumes: `kit.HARD`, `eligibility`, `_past_pairs` (added here).
- Produces: `ac_asks(state) -> list[dict]` with asks `{'member_id', 'field'}` where field in `constraints|relationship_goal|relationship_pace`; deterministic; cost <= `ask_budget_remaining`; `[]` on any exception.

- [ ] **Step 1: Write the failing tests** - append to `test_policy.py`:

```python
class AskPolicyTests(unittest.TestCase):
    @staticmethod
    def _cost(asks):
        return sum(3 if a['field'] == 'constraints' else 1 for a in asks)

    @staticmethod
    def _valid(state, asks):
        for a in asks:
            member = next(m for m in state['members'] if m['member_id'] == a['member_id'])
            if not member['available']:
                return False
            if a['field'] == 'constraints':
                if not any(member['field_status'][k] == 'not_asked' for k in kit.HARD):
                    return False
            elif member['field_status'][a['field']] != 'not_asked':
                return False
        return True

    def test_budget_ceiling_and_validity_all_budgets(self):
        members = ([make_member('m%d' % i, hard_complete=False) for i in range(8)]
                   + [make_member('c%d' % i) for i in range(8)])
        for budget in (12, 4, 3, 2, 0):
            state = make_state(members, budget=budget)
            asks = policy.ac_asks(state)
            self.assertLessEqual(self._cost(asks), budget)
            self.assertTrue(self._valid(state, asks), 'invalid ask at budget %d' % budget)

    def test_tier1_asks_member_blocking_most_partners_first(self):
        members = ([make_member('hot', hard_complete=False),
                    make_member('cold', hard_complete=False)]
                   + [make_member('p%d' % i) for i in range(3)])
        asks = policy.ac_asks(make_state(members, budget=12))
        self.assertTrue(asks)
        self.assertEqual(asks[0], {'member_id': 'hot', 'field': 'constraints'})

    def test_declined_hard_field_never_asked(self):
        members = ([make_member('d%d' % i, hard_complete=False, ask_status='declined')
                    for i in range(4)] + [make_member('c%d' % i) for i in range(4)])
        self.assertEqual(policy.ac_asks(make_state(members, budget=12)), [])

    def test_tier1b_fewest_missing_first_when_no_complete_members(self):
        members = [make_member('few%d' % i, hard_complete=False) for i in range(3)]
        for i in range(3):
            m = make_member('many%d' % i, hard_complete=False)
            for k in kit.HARD[3:8]:
                m['fields'][k] = None
                m['field_status'][k] = 'not_asked'
                m['field_observed_day'][k] = None
            members.append(m)
        asks = policy.ac_asks(make_state(members, budget=12))
        self.assertTrue(asks)
        self.assertTrue(all(a['field'] == 'constraints' for a in asks))
        self.assertTrue(all(a['member_id'].startswith('few') for a in asks[:3]),
                        'fewest-missing first: %r' % asks)

    def test_tier2_soft_ask_completes_observed_partner(self):
        a = make_member('a')
        b = make_member('b', soft_goal=None)
        asks = policy.ac_asks(make_state([a, b], budget=12))
        self.assertEqual(asks, [{'member_id': 'b', 'field': 'relationship_goal'}])

    def test_unavailable_member_never_asked(self):
        members = [make_member('x', hard_complete=False, available=False),
                   make_member('y')]
        self.assertEqual(policy.ac_asks(make_state(members, budget=12)), [])

    def test_past_pair_excluded_from_blocking(self):
        m = make_member('m', hard_complete=False)
        o = make_member('o')
        past = [{'introduction_id': 'i1', 'user_a': 'm', 'user_b': 'o',
                 'assigned_day': 0, 'response_deadline_day': 5,
                 'logging_policy': 'h', 'propensity': None}]
        self.assertEqual(policy.ac_asks(make_state([m, o], budget=12, introductions=past)), [])

    def test_determinism(self):
        members = ([make_member('m%d' % i, hard_complete=False) for i in range(5)]
                   + [make_member('c%d' % i) for i in range(5)])
        state = make_state(members, budget=12)
        self.assertEqual(policy.ac_asks(state), policy.ac_asks(state))

    def test_exception_returns_empty(self):
        state = make_state([make_member('m', hard_complete=False), make_member('o')])
        with mock.patch.object(policy, 'eligibility', side_effect=RuntimeError('boom')):
            self.assertEqual(policy.ac_asks(state), [])
```

- [ ] **Step 2: Run to verify failure**

Run: `python -B -m unittest test_policy.AskPolicyTests -v` -> Expected: FAIL `AttributeError: module 'policy' has no attribute 'ac_asks'`.

- [ ] **Step 3: Implement ac_asks** - append to `policy.py`:

```python
def _past_pairs(state):
    return {tuple(sorted((i['user_a'], i['user_b'])))
            for i in state.get('introductions') or []}


def ac_asks(state):
    """Rule-based selective clarification (spec section 7): tier1 blocked flips,
    tier1b progressive completion, tier2 soft completion. Budget-capped, deterministic."""
    try:
        budget = int(state.get('ask_budget_remaining') or 0)
        avail = sorted((m for m in state['members'] if m['available']),
                       key=lambda m: m['member_id'])
        past = _past_pairs(state)
        asks = []
        spent = 0

        def hard_missing(m):
            return any(m['field_status'][k] == 'not_asked' for k in kit.HARD)

        def pair_past(a, b):
            return tuple(sorted((a, b))) in past

        tier1 = []
        for m in avail:
            if not hard_missing(m):
                continue
            blocked = 0
            for o in avail:
                if o['member_id'] == m['member_id'] or pair_past(m['member_id'], o['member_id']):
                    continue
                if not all(o['fields'][k] is not None for k in kit.HARD):
                    continue
                if eligibility(m, o)['status'] == 'needs_clarification':
                    blocked += 1
            if blocked:
                tier1.append((-blocked, m['member_id']))
        for _, mid in sorted(tier1):
            if spent + 3 > budget:
                break
            asks.append({'member_id': mid, 'field': 'constraints'})
            spent += 3

        asked_constraints = {a['member_id'] for a in asks}
        tier1b = []
        for m in avail:
            if m['member_id'] in asked_constraints or not hard_missing(m):
                continue
            has_partner = any(o['member_id'] != m['member_id']
                              and not pair_past(m['member_id'], o['member_id'])
                              for o in avail)
            if not has_partner:
                continue
            n_missing = sum(1 for k in kit.HARD if m['field_status'][k] == 'not_asked')
            tier1b.append((n_missing, m['member_id']))
        for _, mid in sorted(tier1b):
            if spent + 3 > budget:
                break
            asks.append({'member_id': mid, 'field': 'constraints'})
            spent += 3

        for field in ('relationship_goal', 'relationship_pace'):
            tier2 = []
            for m in avail:
                if m['field_status'][field] != 'not_asked':
                    continue
                partners = 0
                for o in avail:
                    if o['member_id'] == m['member_id'] or pair_past(m['member_id'], o['member_id']):
                        continue
                    if eligibility(m, o)['status'] != 'feasible':
                        continue
                    if o['fields'][field] is not None:
                        partners += 1
                if partners:
                    tier2.append((-partners, m['member_id']))
            for _, mid in sorted(tier2):
                if spent + 1 > budget:
                    break
                asks.append({'member_id': mid, 'field': field})
                spent += 1
        return asks
    except Exception:
        return []
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -B -m unittest test_policy.AskPolicyTests -v` -> Expected: PASS (9 tests).

- [ ] **Step 5: Run the full suite**

Run: `python -B -m unittest` -> Expected: PASS (113 tests).

---


### Task 6: Global matching (rule_score + max_score_matching + ac_match, T7)

**Files:**
- Modify: `policy.py` (add `rule_score`, `_rule_greedy`, `max_score_matching`, `_score_pair`, `ac_match`)
- Test: `test_policy.py`

**Interfaces:**
- Consumes: `kit.eligibility`, `_past_pairs` (from Task 5), `pair_features`, `FEATURE_KEYS`, `load_model`, `score_row`.
- Produces:
  - `rule_score(state, a_id, b_id) -> float` (observable heuristic: availability > feasibility > soft agreement; NaN-safe)
  - `_rule_greedy(edges) -> list[(a, b, score)]` (deterministic no-floor greedy, shared by fallback paths)
  - `max_score_matching(nodes, edges, floor) -> list[(a, b, score)]` - greedy seed by `(-score, a, b)` + up to 8 deterministic strictly-improving local moves on a GENERAL graph (one member pool; single `partner` occupancy map; canonical edge keys `_canon(a, b)`); every kept edge `score >= floor`; all-below-floor -> `[]` (conservative wait)
  - `_score_pair(model, state, a_id, b_id) -> float` - **the test seam** (patch this or `load_model`; never patch internals). Pure: no internal try/except - exceptions must propagate so `ac_match` can switch to the rule fallback.
  - `ac_match(state) -> list[[str, str]]` - **CRITICAL CONTRACT: `evaluate.validate_response` (lines 39-41) accepts ONLY two-element arrays of strings.** Scores/reasons stay internal; returning dicts would make every episode invalid. Candidates = available members x feasible x NOT past pairs (`kit.advance` raises `ValueError('repeat pair')` on repeats, kit.py line 150, and `ValueError('overlapping allocation')` if any member appears twice within one decision, kit.py line 147 - the matching output must never do that).

- [ ] **Step 1: Write the failing tests** - append to `test_policy.py`:

```python
class MatchingTests(unittest.TestCase):
    """T7 match rules: feasibility, no past pairs, uniqueness, floor, optimum, determinism, sorted."""

    def test_t7_toy_optimum_reached_not_greedy_trap(self):
        nodes = ['u1', 'u2', 'u3', 'v1', 'v2', 'v3']
        edges = [('u1', 'v1', 10.0), ('u1', 'v2', 9.0), ('u2', 'v1', 9.0),
                 ('u2', 'v2', 1.0), ('u3', 'v3', 8.0)]
        got = policy.max_score_matching(nodes, edges, floor=0.0)
        self.assertEqual(sum(s for _, _, s in got), 26.0)   # local search escapes greedy 19.0
        self.assertEqual(len(got), 3)

    def test_t7_floor_drops_weak_edges(self):
        nodes = ['u1', 'u2', 'v1', 'v2']
        edges = [('u1', 'v1', 0.9), ('u2', 'v2', 0.3)]
        self.assertEqual(policy.max_score_matching(nodes, edges, floor=0.5),
                         [('u1', 'v1', 0.9)])

    def test_t7_all_below_floor_returns_empty_conservative_wait(self):
        self.assertEqual(policy.max_score_matching(['u1', 'v1'], [('u1', 'v1', 0.3)], 0.5),
                         [])

    def test_t7_optimal_swap_across_2x2(self):
        nodes = ['u1', 'u2', 'v1', 'v2']
        edges = [('u1', 'v1', 10.0), ('u1', 'v2', 9.5), ('u2', 'v1', 9.5),
                 ('u2', 'v2', 0.1)]
        got = policy.max_score_matching(nodes, edges, floor=0.0)
        self.assertAlmostEqual(sum(s for _, _, s in got), 19.0, places=9)

    @staticmethod
    def _four_members():
        return [make_member('u1'), make_member('u2'),
                make_member('w1'), make_member('w2')]

    @staticmethod
    def _controlled_model():
        return {'schema': 1, 'n_features': 44, 'feature_keys': ['f'] * 44,
                'floor': 0.5, 'baseline': 0.0, 'trees': [[[0.0]]]}

    def test_t7_ac_match_returns_sorted_two_string_pairs_deterministic(self):
        state = make_state(self._four_members(), budget=12)
        with mock.patch.object(policy, 'load_model', return_value=self._controlled_model()), \
             mock.patch.object(policy, '_score_pair', return_value=0.9):
            out = policy.ac_match(state)
            again = policy.ac_match(state)
        self.assertEqual(out, [['u1', 'u2'], ['w1', 'w2']])  # all-tie 0.9 -> lexicographic greedy + sorted by (a, b)
        self.assertEqual(out, again)
        for pair in out:
            self.assertIsInstance(pair, list)
            self.assertEqual(len(pair), 2)
            self.assertTrue(all(isinstance(x, str) for x in pair))

    def test_t7_ac_match_excludes_past_pairs(self):
        # scorer makes the past pair the GLOBAL best edge: if ac_match did not
        # exclude it, greedy would pick (u1, w1) first and the output would differ.
        past = [{'introduction_id': 'i1', 'user_a': 'u1', 'user_b': 'w1',
                 'assigned_day': 0, 'response_deadline_day': 5,
                 'logging_policy': 'h', 'propensity': None}]
        state = make_state(self._four_members(), budget=12, introductions=past)

        def fake_score(model, st, x, y):
            return 1.0 if tuple(sorted((x, y))) == ('u1', 'w1') else 0.5

        with mock.patch.object(policy, 'load_model', return_value=self._controlled_model()), \
             mock.patch.object(policy, '_score_pair', side_effect=fake_score):
            out = policy.ac_match(state)
        self.assertEqual(out, [['u1', 'u2'], ['w1', 'w2']])  # (u1, w1) excluded, ties fall to (a, b)

    def test_t7_ac_match_skips_unavailable_members(self):
        members = [make_member('u1'), make_member('w1', available=False)]
        with mock.patch.object(policy, 'load_model', return_value=self._controlled_model()):
            self.assertEqual(policy.ac_match(make_state(members)), [])

    def test_t7_ac_match_empty_state(self):
        self.assertEqual(policy.ac_match(make_state([])), [])

    def test_rule_score_prefers_feasible_and_available(self):
        state = make_state([make_member('u1'), make_member('w1')])
        s_ok = policy.rule_score(state, 'u1', 'w1')
        blocked = make_state([make_member('u1'), make_member('w1', available=False)])
        self.assertGreater(s_ok, policy.rule_score(blocked, 'u1', 'w1'))

    def test_t7_general_graph_chain_never_double_books_a_member(self):
        # ONE member pool: two-sided occupancy would pick both edges and double-book
        # 'b' -> kit.advance raises ValueError('overlapping allocation') (kit.py line 147)
        got = policy.max_score_matching(['a', 'b', 'c'],
                                        [('a', 'b', 1.0), ('b', 'c', 2.0)], floor=0.0)
        self.assertEqual(got, [('b', 'c', 2.0)])   # max matching here is a single edge

    def test_t7_no_member_appears_twice_on_general_graph_cases(self):
        cases = [
            (['a', 'b', 'c'], [('a', 'b', 1.0), ('b', 'c', 2.0)]),
            (['a', 'b', 'c'], [('a', 'b', 5.0), ('b', 'c', 4.0), ('a', 'c', 3.0)]),
            (['a', 'b', 'c', 'd'], [('b', 'c', 9.0), ('a', 'b', 8.0), ('c', 'd', 7.0)]),
            (['x', 'y', 'z'], [('y', 'z', 6.0), ('x', 'y', 6.0), ('x', 'z', 1.0)]),
        ]
        for nodes, edges in cases:
            got = policy.max_score_matching(nodes, edges, floor=0.0)
            used = [n for a, b, _ in got for n in (a, b)]
            self.assertEqual(len(used), len(set(used)),
                             'member reused in %r -> %r' % (edges, got))

    def test_t7_eligibility_status_is_orientation_symmetric(self):
        # ac_match scores pairs in sorted-member orientation; the gate itself must not
        # depend on argument order (if this fails: escalate - do NOT patch kit.py)
        checked = 0
        for seed, variant in ((21, 'development'), (22, 'cold_start'), (23, 'sparse')):
            state = kit.Simulator(kit.generate(seed, 60, variant=variant)).observe()
            by_id = {m['member_id']: m for m in state['members']}
            ids = sorted(by_id)[:12]
            for i, a in enumerate(ids):
                for b in ids[i + 1:]:
                    self.assertEqual(
                        kit.eligibility(by_id[a], by_id[b])['status'],
                        kit.eligibility(by_id[b], by_id[a])['status'],
                        'orientation-dependent eligibility for %s/%s' % (a, b))
                    checked += 1
        self.assertGreaterEqual(checked, 66)   # 3 states x C(12, 2)
```

- [ ] **Step 2: Run to verify failure**

Run: `python -B -m unittest test_policy.MatchingTests -v` -> Expected: FAIL `AttributeError: module 'policy' has no attribute 'rule_score'`.

- [ ] **Step 3: Implement** - append to `policy.py`:

```python
def rule_score(state, a_id, b_id):
    """Deterministic observable heuristic (fallback + T1 tie ordering): availability >
    feasibility > soft agreement. Never raises; NaN-guarded."""
    by_id = {m['member_id']: m for m in state['members']}
    a, b = by_id.get(a_id), by_id.get(b_id)
    if a is None or b is None or not a['available'] or not b['available']:
        return -1.0
    status = eligibility(a, b)['status']
    if status == 'infeasible':
        return -1.0
    score = 1.0 if status == 'feasible' else 0.5
    try:
        f = pair_features(state, a_id, b_id, state.get('day', 0))
        v = f.get('soft_match_count')
        if v is not None and v == v:          # NaN guard: nan != nan
            score += 0.01 * float(v)
    except Exception:
        pass
    return score


def _rule_greedy(edges):
    """Deterministic no-floor greedy fallback: sort by (-score, a, b), disjoint pairs.
    ONE member pool: occupancy is a single 'used' set (either endpoint consumes a member)."""
    picked, used = [], set()
    for a, b, s in sorted(edges, key=lambda e: (-e[2], e[0], e[1])):
        if a in used or b in used:
            continue
        picked.append((a, b, s))
        used.add(a)
        used.add(b)
    return picked


def _canon(a, b):
    """Orientation-free edge key: (min, max)."""
    return (a, b) if a <= b else (b, a)


def max_score_matching(nodes, edges, floor):
    """Greedy seed by (-score, a, b) + up to 8 deterministic strictly-improving local moves.

    GENERAL GRAPH: one member pool - a member may be either endpoint of any edge.
    Occupancy is a single partner map (node -> (other, score)); edge lookups use
    canonical keys _canon(a, b) so orientation never matters; a member is never in
    two kept edges (kit.advance raises 'overlapping allocation' otherwise).
    Returns unique (a, b, score), every score >= floor, sorted by (a, b).
    All candidate edges below floor -> [] (conservative wait, spec section 9).
    """
    if not edges:
        return []
    valid = set(nodes)
    above = sorted((e for e in edges
                    if e[0] in valid and e[1] in valid and e[0] != e[1]
                    and e[2] >= floor),
                   key=lambda e: (-e[2], e[0], e[1]))
    if not above:
        return []
    score_of = {}
    for a, b, s in above:                  # canonical key; first in (-score, a, b) wins
        score_of.setdefault(_canon(a, b), s)
    partner = {}                           # node -> (other_node, score): one pool
    for a, b, s in above:                  # greedy seed
        if a in partner or b in partner:
            continue
        partner[a] = (b, s)
        partner[b] = (a, s)

    def as_list():
        seen, out = set(), []
        for a, (b, s) in partner.items():  # each kept edge appears twice in partner
            k = _canon(a, b)
            if k in seen:
                continue
            seen.add(k)
            out.append((k[0], k[1], s))
        return sorted(out, key=lambda e: (e[0], e[1]))

    for _ in range(8):
        improved = False
        # move (a): add a free-free edge
        for a, b, s in above:
            if a not in partner and b not in partner:
                partner[a] = (b, s)
                partner[b] = (a, s)
                improved = True
                break
        if improved:
            continue
        # move (b): one matched endpoint switches onto a free node (strict gain),
        # checked in BOTH edge orientations so either endpoint can be the mover
        for a, b2, s2 in above:
            if a in partner and b2 not in partner and s2 > partner[a][1]:
                b1 = partner[a][0]
                del partner[b1]            # old partner becomes free
                partner[a] = (b2, s2)
                partner[b2] = (a, s2)
                improved = True
                break
            if b2 in partner and a not in partner and s2 > partner[b2][1]:
                a1 = partner[b2][0]
                del partner[a1]
                partner[b2] = (a, s2)
                partner[a] = (b2, s2)
                improved = True
                break
        if improved:
            continue
        # move (c): 2-cycle exchange between two kept edges (strict gain)
        m_pairs = sorted({_canon(a, b) for a, (b, _) in partner.items()})
        found = None
        for i, (a1, b1) in enumerate(m_pairs):
            s1 = partner[a1][1]
            for a2, b2 in m_pairs[i + 1:]:
                s2 = partner[a2][1]
                s12 = score_of.get(_canon(a1, b2))
                s21 = score_of.get(_canon(a2, b1))
                if s12 is not None and s21 is not None and s12 + s21 > s1 + s2:
                    found = (a1, b1, a2, b2, s12, s21)
                    break
            if found:
                break
        if found:
            a1, b1, a2, b2, s12, s21 = found
            for n in (a1, b1, a2, b2):
                partner.pop(n, None)
            partner[a1] = (b2, s12)
            partner[b2] = (a1, s12)
            partner[a2] = (b1, s21)
            partner[b1] = (a2, s21)
            improved = True
        if not improved:
            break
    return as_list()


def _score_pair(model, state, a_id, b_id):
    """Ranking score for one candidate pair. Test seam - patch this, not internals.
    Pure by design: exceptions propagate so ac_match can switch to the rule fallback."""
    f = pair_features(state, a_id, b_id, state.get('day', 0))
    return score_row(model, [f[k] for k in FEATURE_KEYS])


def ac_match(state):
    """Floor-gated approximate max-score global matching (spec sections 5.2, 9).

    Returns sorted [[a, b], ...] - the exact shape evaluate.validate_response accepts.
    Candidate pairs: available members, kit-feasible, never previously introduced.
    Model path: floor-gated max_score_matching. Fallback (blob missing/corrupt or
    scoring exception): deterministic no-floor rule greedy (spec T8).
    """
    try:
        members = sorted((m for m in state['members'] if m['available']),
                         key=lambda m: m['member_id'])
        if not members:
            return []
        past = _past_pairs(state)
        cand = []
        for i, a in enumerate(members):
            for b in members[i + 1:]:
                key = tuple(sorted((a['member_id'], b['member_id'])))
                if key in past:
                    continue
                if eligibility(a, b)['status'] != 'feasible':
                    continue
                cand.append((a['member_id'], b['member_id']))
        if not cand:
            return []
        if len(cand) > 12000:  # C7 count-based cap (spec 8): top 12,000 by (-rule_score, a, b) - never time-based
            cand = sorted(cand, key=lambda p: (-rule_score(state, p[0], p[1]), p[0], p[1]))[:12000]
        model = load_model()
        chosen = None
        if model is not None:
            try:
                edges = [(x, y, _score_pair(model, state, x, y)) for x, y in cand]
                chosen = max_score_matching([m['member_id'] for m in members],
                                            edges, float(model['floor']))
            except Exception:
                chosen = None                # scoring failure -> rule fallback (T8)
        if chosen is None:
            chosen = _rule_greedy([(x, y, rule_score(state, x, y)) for x, y in cand])
        return [[a, b] for a, b, _ in sorted(chosen, key=lambda e: (e[0], e[1]))]
    except Exception:
        return []
```

**Invariants (pinned by T7):** greedy seed by `(-score, a, b)`; every kept edge `score >= floor`; all-below-floor -> `[]`; GENERAL GRAPH - one member pool, a member may be either endpoint of any edge: single `partner` occupancy map (a member is NEVER in two kept edges - `kit.advance` raises `'overlapping allocation'` otherwise), canonical edge keys `_canon(a, b)` (orientation never matters); local search = 3 strictly-improving moves (free-free add; one matched endpoint re-partners onto a free node, checked in both edge orientations; 2-cycle exchange), up to 8 deterministic moves, sorted iteration everywhere (no set/dict-order dependence); output pairs are `[str, str]` sorted by `(a, b)`; past pairs excluded before scoring; eligibility gate is orientation-symmetric (reciprocity test); candidate set capped to the top 12,000 by `(-rule_score, a, b)` when `len(cand) > 12000` (C7 count-based, never time-based).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -B -m unittest test_policy.MatchingTests -v` -> Expected: PASS (12 tests).
If the toy (`26.0`) or 2x2 (`19.0`) totals fail: print `max_score_matching(nodes, edges, 0.0)` on the toy edges, confirm the greedy seed total (19.0 for the toy), then watch move (c) lift it to 26.0. The moves, not the tests, are what you adjust.

- [ ] **Step 5: Run the full suite**

Run: `python -B -m unittest` -> Expected: PASS (125 tests).

---

### Task 7: Fallback path (T8)

**Files:**
- Modify: `policy.py` (ask-branch guard lands in Task 8's `decide`; scoring/blob fallback already lives in Tasks 1/6)
- Test: `test_policy.py`

**Interfaces:**
- Behaviour pinned (spec T8): corrupt/empty `MODEL_B64` -> valid deterministic pairs via rule greedy (no floor); injected scoring exception -> rule-fallback pairs; ask failure -> empty asks (guard added in Task 8 `decide`).

- [ ] **Step 1: Write the failing tests** - append to `test_policy.py`:

```python
def assert_no_overlap(testcase, pairs):
    """Shared guard: no member may appear twice in one decision's output
    (kit.advance raises ValueError('overlapping allocation'), kit.py line 147)."""
    used = [n for pair in pairs for n in pair]
    testcase.assertEqual(len(used), len(set(used)),
                          'member reused across pairs: %r' % (pairs,))


class FallbackTests(unittest.TestCase):
    @staticmethod
    def _req(state, phase='match', memory=None):
        return {'schema_version': '1.0.0', 'phase': phase, 'state': state, 'memory': memory}

    @staticmethod
    def _model():
        return {'schema': 1, 'n_features': 44, 'feature_keys': ['f'] * 44,
                'floor': 0.5, 'baseline': 0.0, 'n_iter': 1, 'trees': [[[0.0]]]}

    def test_t8_corrupt_blob_rule_greedy_pairs_deterministic(self):
        members = [make_member('u1'), make_member('u2'),
                   make_member('w1'), make_member('w2')]
        state = make_state(members, budget=12)
        with mock.patch.object(policy, 'MODEL_B64', 'corrupt-blob!!'), \
             mock.patch.object(policy, '_rule_greedy', wraps=policy._rule_greedy) as spy:
            out = policy.ac_match(state)
            again = policy.ac_match(state)
        self.assertEqual(out, [['u1', 'u2'], ['w1', 'w2']])  # all feasible -> tie -> (a, b) order
        self.assertEqual(out, again)
        self.assertEqual(spy.call_count, 2)   # corrupted blob -> rule path EVERY call
        for pair in out:
            self.assertEqual(len(pair), 2)
            self.assertTrue(all(isinstance(x, str) for x in pair))
        assert_no_overlap(self, out)

    def test_t8_injected_scoring_exception_falls_back_to_rule_pairs(self):
        members = [make_member('u1'), make_member('u2'),
                   make_member('w1'), make_member('w2')]
        state = make_state(members, budget=12)
        with mock.patch.object(policy, '_score_pair', side_effect=RuntimeError('boom')), \
             mock.patch.object(policy, '_rule_greedy', wraps=policy._rule_greedy) as spy:
            out = policy.ac_match(state)
        self.assertEqual(out, [['u1', 'u2'], ['w1', 'w2']])  # rule greedy, no floor, no crash
        spy.assert_called_once()              # the exception path provably used _rule_greedy
        assert_no_overlap(self, out)

    def test_t8_model_path_never_calls_rule_greedy(self):
        members = [make_member('u1'), make_member('u2'),
                   make_member('w1'), make_member('w2')]
        state = make_state(members, budget=12)
        with mock.patch.object(policy, 'load_model', return_value=self._model()), \
             mock.patch.object(policy, '_score_pair', return_value=0.9), \
             mock.patch.object(policy, '_rule_greedy', wraps=policy._rule_greedy) as spy:
            out = policy.ac_match(state)
        self.assertEqual(out, [['u1', 'u2'], ['w1', 'w2']])  # model path: floor 0.5 <= 0.9
        spy.assert_not_called()               # healthy model never touches the fallback
        assert_no_overlap(self, out)

    def test_t8_empty_blob_decide_returns_wellformed_strict_json(self):
        state = make_state([make_member('u1'), make_member('w1')], budget=12)
        with mock.patch.object(policy, 'MODEL_B64', ''):
            match_out = policy.decide(self._req(state, 'match'), mode='ac')
            ask_out = policy.decide(self._req(state, 'ask'), mode='ac')
        self.assertEqual(set(match_out), {'pairs', 'memory'})
        self.assertEqual(set(ask_out), {'asks', 'memory'})
        json.dumps(match_out, allow_nan=False)
        json.dumps(ask_out, allow_nan=False)

    def test_t8_ask_failure_returns_empty_asks(self):
        state = make_state([make_member('m', hard_complete=False), make_member('o')],
                           budget=12)
        with mock.patch.object(policy, 'ac_asks', side_effect=RuntimeError('boom')):
            out = policy.decide(self._req(state, 'ask'), mode='ac')
        self.assertEqual(out['asks'], [])
        self.assertEqual(set(out), {'asks', 'memory'})
```

- [ ] **Step 2: Run to verify failure**

Run: `python -B -m unittest test_policy.FallbackTests -v`
Expected: tests 1-4 may already PASS (blob/scoring fallback from Tasks 1/6 are characterization tests; the `wraps` spies pin WHICH path ran - `_rule_greedy` called on failure paths, NOT called on the healthy model path); test 5 FAILS until the `decide` ask-branch guard lands in Task 8 Step 4. Fix the implementation only, never these tests.

- [ ] **Step 3: Full suite**

Run: `python -B -m unittest` -> Expected: PASS (130 tests) - test 5 turns green with Task 8's `decide` rewrite; if you run this step after Task 8 instead, count is 140. A test that fails here AND after Task 8 means the fallback contract is unimplemented.

---

### Task 8: decide() dispatch, CLI defaults, shim (T1/T2/T11)

**Files:**
- Modify: `policy.py` (`decide` dispatch + `build_parser`/`main`; baseline branch body byte-preserved)
- Create: `policy_ac.py`
- Test: `test_policy.py`

**Interfaces (verified against evaluate.py / test_runner.py / Dockerfile):**
- `decide(request, mode='ac')` where `request = {'schema_version', 'phase', 'state', 'memory'}` (evaluate.py episode lines 87-88). Match response `{'pairs': [[str, str], ...], 'memory': summary}`; ask response `{'asks': [{'member_id','field'}, ...], 'memory': summary}`; response keys EXACT (validate_response rejects extras).
- Baseline modes (`greedy`/`no_asks`/`random`): body byte-identical, including `'memory': memory` echo.
- CLI: keep the `--baseline` flag name (evaluate.py always passes `--baseline <greedy|no_asks|random>` to local policies, line 147); extend choices with `ac`, **default `ac`** (Dockerfile ENTRYPOINT is bare `["python", "policy.py"]` - no args - so the default IS the container policy; test_runner `invoke([sys.executable, 'policy.py'], ...)` also passes no args).
- `policy_ac.py`: stdin adapter that **ignores argv entirely** (R5) and forces `mode='ac'`.

- [ ] **Step 1: Read decide() before touching it**

Run: `python -B -c "import inspect, policy; print(inspect.getsource(policy.decide))"`
The `mode != 'random'` / random-block / final-return lines must survive your edit verbatim.

- [ ] **Step 2: Write the failing tests** - append to `test_policy.py`:

```python
def req(state, phase='match', memory=None):
    """Build a decide() request exactly like evaluate.episode does."""
    return {'schema_version': '1.0.0', 'phase': phase, 'state': state, 'memory': memory}


class DecideDispatchTests(unittest.TestCase):
    def test_t1_default_mode_runs_ac_ask_phase_divergence(self):
        # Deterministic divergence craft: the only partner is a PAST introduction.
        # baseline_asks -> asks constraints for m; ac (default) -> waits ([]).
        m = make_member('m', hard_complete=False)
        o = make_member('o')
        past = [{'introduction_id': 'i1', 'user_a': 'm', 'user_b': 'o',
                 'assigned_day': 0, 'response_deadline_day': 5,
                 'logging_policy': 'h', 'propensity': None}]
        state = make_state([m, o], budget=12, introductions=past)
        default_out = policy.decide(req(state, 'ask'))
        self.assertEqual(default_out, policy.decide(req(state, 'ask'), mode='ac'))
        self.assertEqual(default_out['asks'], [])
        self.assertEqual(policy.decide(req(state, 'ask'), mode='greedy')['asks'],
                         [{'member_id': 'm', 'field': 'constraints'}])

    def test_t1_default_mode_runs_ac_match_phase(self):
        sim = kit.Simulator(kit.generate(42, 40, variant='development'))
        state = sim.observe()
        self.assertEqual(policy.decide(req(state, 'match')),
                         policy.decide(req(state, 'match'), mode='ac'))

    def test_t1_greedy_mode_byte_preserved(self):
        sim = kit.Simulator(kit.generate(42, 60))
        state = sim.observe()
        self.assertEqual(policy.decide(req(state, 'match'), mode='greedy')['pairs'],
                         kit.baseline_match(state))
        self.assertEqual(policy.decide(req(state, 'ask'), mode='greedy')['asks'],
                         kit.baseline_asks(state))

    def test_t1_cli_default_ac_baseline_still_selectable(self):
        import subprocess
        self.assertEqual(policy.build_parser().parse_args([]).baseline, 'ac')
        self.assertEqual(
            policy.build_parser().parse_args(['--baseline', 'greedy']).baseline, 'greedy')
        out = subprocess.run([sys.executable, str(REPO_ROOT / 'policy.py'), '--help'],
                             capture_output=True, text=True, cwd=str(REPO_ROOT))
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn('ac', out.stdout)
        self.assertIn('greedy', out.stdout)

    def test_t2_empty_state_exact_responses(self):
        empty = kit.Simulator(kit.generate(42, 0, variant='development')).observe()
        self.assertEqual(policy.decide(req(empty, 'match'), mode='ac'),
                         {'pairs': [], 'memory': {}})
        self.assertEqual(policy.decide(req(empty, 'ask'), mode='ac'),
                         {'asks': [], 'memory': {}})

    def test_t2_ask_shape_strict_json_budget_and_resolvable(self):
        from evaluate import validate_response
        sim = kit.Simulator(kit.generate(42, 60))
        state = sim.observe()
        decision = policy.decide(req(state, 'ask'), mode='ac')
        validate_response(decision, 'ask')                     # exact harness contract
        json.dumps(decision, allow_nan=False)                  # strict JSON (T2)
        cost = sum(3 if a['field'] == 'constraints' else 1 for a in decision['asks'])
        self.assertLessEqual(cost, state['ask_budget_remaining'])
        sim.resolve_asks(decision['asks'])                     # no KeyError/TypeError
        match_decision = policy.decide(req(sim.observe(), 'match'), mode='ac')
        validate_response(match_decision, 'match')
        sim.advance(match_decision['pairs'])                   # no ValueError

    def test_t2_memory_robustness_none_empty_stale(self):
        state = make_state([make_member('u1'), make_member('w1')], budget=12)
        base = policy.decide(req(state, 'match', memory=None), mode='ac')
        for memory in ({}, {'v': 0, 'm': {'stale': [9, 9, 9, 9]}}, 'garbage-string'):
            self.assertEqual(policy.decide(req(state, 'match', memory=memory), mode='ac'),
                             base)                             # ac ignores request memory (regenerates)

    def test_t11_policy_source_has_no_forbidden_tokens(self):
        src = (REPO_ROOT / 'policy.py').read_text(encoding='utf-8')
        for line in src.splitlines():
            if 'FORBIDDEN_TOKENS' in line or 'STRUCTURE_INFORMED' in line:
                continue       # the token list/auditor definitions themselves
            for token in ('future_', 'hidden_', 'ground_truth', 'label_mutual',
                          'label_date', 'response_rate', 'oracle'):
                self.assertNotIn(token, line,
                                 'forbidden token %r in policy.py: %r' % (token, line))
        self.assertNotIn('audit_feature_keys(', src)   # auditor not imported/called in policy
        self.assertNotIn('audit_structure_disclosure', src)

    def test_t11_feature_keys_have_no_forbidden_tokens(self):
        import features
        for key in features.FEATURE_KEYS:
            for token in ('future_', 'hidden_', 'ground_truth', 'oracle'):
                self.assertNotIn(token, key)


class ShimTests(unittest.TestCase):
    def test_policy_ac_forces_ac_and_ignores_baseline_flag(self):
        # divergence craft from T1: greedy would ask, ac waits - proves which mode ran
        m = make_member('m', hard_complete=False)
        o = make_member('o')
        past = [{'introduction_id': 'i1', 'user_a': 'm', 'user_b': 'o',
                 'assigned_day': 0, 'response_deadline_day': 5,
                 'logging_policy': 'h', 'propensity': None}]
        state = make_state([m, o], budget=12, introductions=past)
        import subprocess
        out = subprocess.run(
            [sys.executable, str(REPO_ROOT / 'policy_ac.py'), '--baseline', 'greedy'],
            input=json.dumps(req(state, 'ask')), capture_output=True, text=True,
            cwd=str(REPO_ROOT))
        self.assertEqual(out.returncode, 0, out.stderr)
        parsed = json.loads(out.stdout)
        self.assertEqual(parsed, policy.decide(req(state, 'ask'), mode='ac'))
        self.assertNotEqual(parsed, policy.decide(req(state, 'ask'), mode='greedy'))
        src = (REPO_ROOT / 'policy_ac.py').read_text(encoding='utf-8')
        self.assertIn("mode='ac'", src)
```

- [ ] **Step 3: Run to verify failure**

Run: `python -B -m unittest test_policy.DecideDispatchTests test_policy.ShimTests test_policy.FallbackTests -v`
Expected: FAIL - no `build_parser`, no `policy_ac.py`, decide default still `greedy`, T8 test 5 failing (the ask-guard test; tests 1-4 are characterization passes).

- [ ] **Step 4: Implement dispatch + CLI + shim**

1. Rewrite `decide` as (existing baseline lines kept verbatim inside the else-path):

```python
def decide(request, mode='ac'):
    state = request['state']
    memory = request.get('memory') or {}
    if request['phase'] == 'ask':
        if mode == 'ac':
            try:
                asks = ac_asks(state)
            except Exception:
                asks = []
            return {'asks': asks, 'memory': memory_summary(state)}
        return {'asks': [] if mode == 'no_asks' else baseline_asks(state), 'memory': memory}
    if mode == 'ac':
        return {'pairs': ac_match(state), 'memory': memory_summary(state)}
    if mode != 'random':
        pairs = baseline_match(state)
    else:
        <existing random body, byte-identical>
    return {'pairs': pairs, 'memory': memory}
```

2. Replace the `__main__` block with:

```python
def build_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline', choices=['greedy', 'no_asks', 'random', 'ac'],
                        default='ac')
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    request = json.load(sys.stdin)
    print(json.dumps(decide(request, args.baseline), allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
```

3. Create `policy_ac.py` (spec R5: ignores evaluate.py's `--baseline`, forces `ac`; NOT copied into the Docker image - `.dockerignore` whitelist excludes it):

```python
"""Local A+C evaluation adapter (spec R5 / section 5).

evaluate.py always invokes local policies as `python <policy> --baseline <greedy|no_asks|random>`
(choices frozen, spec C4). This shim parses NO arguments - the --baseline flag is
deliberately ignored - and forces mode 'ac' on every request. The container path
does not use this file: the Docker image runs `python policy.py` with no args and
policy.py's argparse default ('ac') covers it.
"""
import json
import sys

from policy import decide


def main(argv=None):          # argv accepted but deliberately unused (R5)
    request = json.load(sys.stdin)
    print(json.dumps(decide(request, mode='ac'), allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
```

4. Docker entrypoint sanity (no edit): confirm `ENTRYPOINT ["python", "policy.py"]` in Dockerfile still holds - default `ac` reaches the container.

- [ ] **Step 5: Run the new tests to verify they pass**

Run: `python -B -m unittest test_policy.DecideDispatchTests test_policy.ShimTests test_policy.FallbackTests -v`
Expected: PASS (15 tests: FallbackTests 5 + DecideDispatchTests 9 + ShimTests 1).

- [ ] **Step 6: Full suite + baseline regression**

Run: `python -B -m unittest` -> Expected: PASS (140 tests). Any pre-existing failure means the `decide` refactor disturbed a baseline path - restore it, do not adjust the old test.

---

### Task 9: Integration - real resolver loop (T9) + performance (T10)

**Files:**
- Test: `test_policy.py`

**Interfaces:**
- Consumes: full `decide` pipeline, `kit.Simulator.resolve_asks/advance`, `evaluate.validate_response` (the exact harness validator) and `evaluate.invoke(evaluate.docker_command(image), request, timeout=10)` (returns `(validated_response, elapsed)`; container constraints `--cpus=2 --memory=1g --network=none`), the C7 count-based cap from Task 6, the `assert_no_overlap` helper (Task 7), and `mock.patch.object(policy, '_rule_greedy', wraps=...)` spies that pin the real-model path; image `sequential-policy:1.0` is built in Task 10 (the docker timing test SKIPs until then). Tests only - no code changes in this task.

- [ ] **Step 1: Write the tests** - append to `test_policy.py`:

```python
class IntegrationTests(unittest.TestCase):
    @staticmethod
    def _req(state, phase='match'):
        return {'schema_version': '1.0.0', 'phase': phase, 'state': state, 'memory': None}

    def test_t9_real_resolver_20_day_loop_exact_harness_contract(self):
        from evaluate import validate_response
        self.assertIsNotNone(policy.load_model(), 'T9 must exercise the REAL embedded model')
        sim = kit.Simulator(kit.generate(42, 60, variant='development'))
        with mock.patch.object(policy, '_rule_greedy', wraps=policy._rule_greedy) as spy:
            for _ in range(20):
                ask_decision = policy.decide(self._req(sim.observe(), 'ask'), mode='ac')
                validate_response(ask_decision, 'ask')      # exact evaluate.py contract
                json.dumps(ask_decision, allow_nan=False)
                sim.resolve_asks(ask_decision['asks'])
                match_decision = policy.decide(self._req(sim.observe(), 'match'), mode='ac')
                validate_response(match_decision, 'match')  # pairs = [str, str] arrays
                json.dumps(match_decision, allow_nan=False)
                assert_no_overlap(self, match_decision['pairs'])
                for pair in match_decision['pairs']:
                    self.assertNotIn(tuple(sorted(pair)),
                                     {tuple(sorted((i['user_a'], i['user_b'])))
                                      for i in sim.observe()['introductions']},
                                     'ac returned a past pair - advance would raise')
                sim.advance(match_decision['pairs'])        # never ValueError (kit lines 147/150)
        spy.assert_not_called()  # healthy end-to-end path never drops to the rule fallback
        self.assertTrue(sim.observe()['members'])           # loop survived 20 days

    @staticmethod
    def _replay_state(target_day=50):
        """Real 200-member world replayed to target_day with accumulated history
        (introductions, feedback, field maturation) via collect_rows' exact day
        mechanics: observe -> asks -> re-observe -> match -> advance."""
        sim = kit.Simulator(kit.generate(42, 200, 'dev_replay', variant='development'))
        for _ in range(target_day):
            state = sim.observe()
            sim.resolve_asks(kit.baseline_asks(state))
            state = sim.observe()
            sim.advance(kit.baseline_match(state))
        return sim.observe()

    def test_t10_local_match_latency_on_real_day50_state(self):
        import time
        state = self._replay_state(target_day=50)
        available = [m for m in state['members'] if m['available']]
        # realistic regime (probed: seed 42 day 50 -> 174 available, 96 intros, 208 feedback,
        # request 452783 bytes < 1 MiB evaluate limit, allow_nan=False clean)
        self.assertGreaterEqual(len(available), 150)
        self.assertLessEqual(len(available), 190)
        self.assertGreaterEqual(len(state['introductions']), 50)
        self.assertGreaterEqual(len(state['feedback']), 100)
        with mock.patch.object(policy, '_rule_greedy', wraps=policy._rule_greedy) as spy:
            start = time.perf_counter()
            out = policy.ac_match(state)
            elapsed = time.perf_counter() - start
        spy.assert_not_called()
        assert_no_overlap(self, out)
        print('T10 local match (day50, %d available, %d intros): %.2fs (%d pairs)'
              % (len(available), len(state['introductions']), elapsed, len(out)))
        self.assertLess(elapsed, 9.0,
                        'local ac_match on a day-50 state took %.2fs '
                        '(hard <9s; the Task 10 container run is authoritative)' % elapsed)

    def test_t10_local_ask_latency_on_real_day50_state(self):
        import time
        state = self._replay_state(target_day=50)
        req = self._req(state, 'ask')
        start = time.perf_counter()
        out = policy.decide(req, mode='ac')
        elapsed = time.perf_counter() - start
        json.dumps(out, allow_nan=False)
        self.assertIsInstance(out['asks'], list)
        print('T10 local ask (day50): %.2fs (%d asks)' % (elapsed, len(out['asks'])))
        self.assertLess(elapsed, 9.0, 'local ask phase took %.2fs (hard <9s)' % elapsed)

    def test_t10_docker_latency_within_eval_constraints(self):
        # Authoritative: exact evaluator container constraints (--cpus=2 --memory=1g
        # --network=none, read-only) + evaluate.invoke's 10 s limit, measured inside
        # invoke itself (returns (validated_response, elapsed)).
        # SKIPs until Task 10 builds sequential-policy:1.0; re-run there.
        import subprocess
        import evaluate as ev
        try:
            probe = subprocess.run(['docker', 'version'], capture_output=True, timeout=30)
        except (OSError, subprocess.TimeoutExpired):
            raise unittest.SkipTest('docker not available')
        if probe.returncode != 0:
            raise unittest.SkipTest('docker daemon not available')
        image = 'sequential-policy:1.0'
        if subprocess.run(['docker', 'image', 'inspect', image],
                          capture_output=True).returncode != 0:
            raise unittest.SkipTest('%s not built yet (Task 10 builds it)' % image)
        state = self._replay_state(target_day=50)
        response, elapsed = ev.invoke(ev.docker_command(image),
                                      self._req(state, 'match'), timeout=10)
        self.assertIsInstance(response['pairs'], list)  # validate_response ran inside invoke
        print('T10 docker match (day50): %.2fs (%d pairs)'
              % (elapsed, len(response['pairs'])))
        self.assertLess(elapsed, 9.0,
                        'docker ac_match took %.2fs (hard <9s under evaluator constraints)'
                        % elapsed)
        # ask phase measured too - evaluate.episode invokes BOTH phases every day
        ask_out, ask_elapsed = ev.invoke(ev.docker_command(image),
                                         self._req(state, 'ask'), timeout=10)
        self.assertIsInstance(ask_out['asks'], list)
        print('T10 docker ask (day50): %.2fs (%d asks)'
              % (ask_elapsed, len(ask_out['asks'])))
        self.assertLess(ask_elapsed, 9.0,
                        'docker ask phase took %.2fs (hard <9s under evaluator constraints)'
                        % ask_elapsed)
```

- [ ] **Step 2: Run and record**

Run: `python -B -m unittest test_policy.IntegrationTests -v`
Expected: PASS (4 tests). The docker timing test SKIPs until Task 10 builds `sequential-policy:1.0`, where it re-runs as the authoritative container-constrained measurement (`--cpus=2 --memory=1g --network=none`, 10 s invoke limit). Record the printed LOCAL T10 elapsed values in your working notes. The C7 count-based cap is already part of `ac_match` since Task 6 Step 3 (fires only when `len(cand) > 12000`, per Global Constraints - never on measured time):
- Both local values < 5 s: p95 target met locally; the Task 10 container number is binding.
- Local match >= 5 s and < 9 s: apply ONLY the pre-registered semantics-preserving optimizations from Global Constraints - typed/normalized tree representation at load, local variable binding in hot loops, per-call eligibility cache, per-call `member_history` memoization cleared at each `decide` entry (outside the verbatim feature block). Each must keep every test green (byte-identical responses pinned by the characterization/e2e tests). Re-run T10; note "optimizations applied" in the ledger. This is NOT tuning.
- >= 9 s even with cap + optimizations: STOP and escalate in the ledger (do not touch anything else).

- [ ] **Step 3: Full suite**

Run: `python -B -m unittest` -> Expected: PASS (144 tests).

---

### Task 10: Pre-registered evaluation (spec section 14) + integrity gates G1-G3

**Files:**
- Create: `results/artifact.sha256` (freeze), `results/pre_eval_diagnostics.json` (pre-eval gate), `results/greedy.json`, `results/no_asks.json`, `results/random.json`, `results/ac.json`, `results/ac_rerun.json`, `results/ac_container.json`, `results/run_log.txt`
- Modify: none (evaluate.py, kit.py, Dockerfile untouched; no code changes of ANY kind in this task - C7)

**Interfaces:**
- Consumes: `evaluate.py` verbatim contract - flags `--policy`, `--baseline`, `--seeds` (comma list), `--variants` (comma list or `all`), `--output`, `--image`; worlds are fixed `generate(seed, 200, 'evaluation', variant)` with 60 decision days + 40 follow-up (no `--days`/`--limit` flags exist); local policy command = `python <policy> --baseline <choice>`; container command = `docker run <image>` (no args).
- Produces: 6 result JSONs (5 spec commands + rerun) + `results/pre_eval_diagnostics.json` + `results/artifact.sha256` + run log under `results/`; ledger entries.

- [ ] **Step 1: Freeze the artifact, then build the image (before any A+C numbers are read)**

1. FREEZE (G3 source half): `python -B -c "import hashlib; open('results/artifact.sha256','w').write(''.join('%s  %s\n' % (hashlib.sha256(open(f,'rb').read()).hexdigest(), f) for f in ('policy.py','policy_ac.py')))"` then `type results/artifact.sha256` -> two SHA-256 lines, recorded in the ledger. From this moment policy.py + policy_ac.py are FROZEN (Global Constraints: evaluation runs against this artifact; the final verification NEVER re-runs the exporter).
2. BUILD (G3 build half): `docker build -t sequential-policy:1.0 .` -> exit 0, built FROM the frozen artifact.
3. Sanity: in-container introspection is NOT possible (ENTRYPOINT is `python policy.py`, read-only fs, network none) - instead verify locally that policy.py has no sklearn import: `python -B -c "import policy; assert 'sklearn' not in open('policy.py').read()"`.
4. Authoritative latency gate (the docker timing test no longer skips): `python -B -m unittest test_policy.IntegrationTests.test_t10_docker_latency_within_eval_constraints -v` -> PASS with printed value < 9 s. A skip means the image is missing - fix the build, never the test.

- [ ] **Step 2: Pre-eval diagnostics gate (read-only, before ANY outcome is computed)**

Run: `python -m research.export_model --diagnose` -> exit 0, `diagnose OK ... -> results/pre_eval_diagnostics.json`. READ the JSON now (within-(world, day) model-vs-rule ranking on validation rows; floor coverage per state group and by variant; zero-above-floor groups). ANY zero-above-floor group: STOP and escalate in the ledger BEFORE running evaluation (a floor that never passes on stored rows means the match path silently degenerates - diagnosis only; changing the floor would be tuning, C7). These diagnostics never trigger tuning, floor/threshold changes, prevalence subtraction (`score - 0.0094`), or any code change (Global Constraints). Log PASS in the run log and continue.

- [ ] **Step 3: Run the pre-registered commands EXACTLY as spec section 14** (record each command + exit code + wall time in `results/run_log.txt`; est. 60-120 min total)

```
python evaluate.py --baseline greedy  --seeds 101,102,103 --variants all --output results/greedy.json
python evaluate.py --baseline no_asks  --seeds 101,102,103 --variants all --output results/no_asks.json
python evaluate.py --baseline random   --seeds 101,102,103 --variants all --output results/random.json
python evaluate.py --policy policy_ac.py --baseline greedy --seeds 101,102,103 --variants all --output results/ac.json
python evaluate.py --image sequential-policy:1.0 --seeds 101,102,103 --variants all --output results/ac_container.json
```

(Note: the `--policy policy_ac.py` command still passes `--baseline greedy` because evaluate.py appends it - the shim ignores it, spec R5. Output filenames record identity.)

- [ ] **Step 4: Integrity gate G1 - run BEFORE reading any outcome metric**

For each of the 5 result files: `json.loads` with `evaluate.strict_json` (or plain loads - outputs are written with `allow_nan=False`), assert `summary.eligible is True`, every `episodes[].valid is True`, and `summary.eligible` truthy. Any invalid episode: STOP, read `episodes[].error`, fix the underlying contract bug (this is a correctness fix, allowed), re-run the affected command(s), re-check G1. Log pass/fail per file.

- [ ] **Step 5: Integrity gate G2 - determinism + local/container parity**

1. Rerun: `python evaluate.py --policy policy_ac.py --baseline greedy --seeds 101 --variants all --output results/ac_rerun.json`
2. For seed 101 rows (6 variants) compare `action_sha256` of `results/ac_rerun.json` episodes against the seed-101 episodes of `results/ac.json` - must be IDENTICAL per (seed, variant).
3. For ALL 18 (seed, variant) episodes compare `action_sha256` in `results/ac.json` vs `results/ac_container.json` - must be IDENTICAL (spec section 12: local vs container byte-determinism; image runs the same stdlib code + same blob).
Any mismatch: STOP; suspects are unsorted iteration or non-deterministic fallback; do not read metrics until equal.

- [ ] **Step 6: Read outcomes against the pre-registered questions (no tuning, C7)**

Fill the spec section 14 report table from the 5 files: per-variant + aggregate `msmi_per_100_arrived_members` (primary), `coverage`, `mutual_acceptances_per_100`, `ask_cost`, `inference_seconds` (mean, and p50/p95/p99 per-episode from episodes), invalid counts, ranking vs baselines. Headline: `ac` container vs the three baselines. Honest reporting includes R1 (may not beat greedy) and the C6 calibration caveat. Gates: G1-G3 above; no other gate exists - if `ac` loses to greedy, that is a REPORTED result, not a bug. Power/uncertainty (reporting discipline, NOT a new gate): the design is 3 seeds x 6 variants = 18 episodes per policy and each per-variant cell holds only 3 episodes - report per-episode spread (p50/p95 of the primary) next to means, report the rank count (how many of the 3 seeds `ac` beats each baseline), treat small aggregate deltas as within noise for this design, and claim no significance the pre-registered design cannot support.

- [ ] **Step 7: Ledger + final verification sweep**

Append to the ledger: all commands + exit codes, G1/G2/G3 outcomes, the results table, and the honest one-paragraph conclusion. Then paste outputs of:
- `python -B -m unittest` (expect 144 tests, 0 errors/failures - research + root suites)
- `python -B -m research.export_model --check` (expect exit 0 + `check OK ...` - read-only parity/schema/n_iter verification; the exporter is NEVER re-run in this task, Global Constraints)
- `python -B -c "import hashlib; lines = [l.split() for l in open('results/artifact.sha256')]; ok = all(hashlib.sha256(open(f,'rb').read()).hexdigest() == h for h, f in lines); print('artifact unchanged:', ok); assert ok"` -> `artifact unchanged: True` (hash after == hash frozen in Step 1)
- `python -B -c "import policy; m = policy.load_model(); print(m is not None, len(policy.MODEL_B64))"` -> `True <n>`
- `git status --short` (expect exactly: `policy.py`, `policy_ac.py`, `test_policy.py`, `research/export_model.py`, `research/test_pipeline.py`, `results/*.json`, `results/artifact.sha256`, `results/run_log.txt`, `docs/superpowers/**`; and `git diff --stat kit.py evaluate.py Dockerfile .dockerignore .github` empty)

---

## Task Dependency & Verification Summary

| Task | Depends on | Spec tests covered | New tests | Cumulative |
|------|-----------|--------------------|-----------|------------|
| 1 Model package | - | T5 (walk/sigmoid/score) | 8 | 88 |
| 2 Exporter + inject | 1 | T4, T12, T13, T14 | 8 | 96 |
| 3 Feature copy | 2 (blob guard) | T3 | 4 | 100 |
| 4 Memory summary | - | (T2 memory support) | 4 | 104 |
| 5 Ask policy | 3 (features) | T6 | 9 | 113 |
| 6 Matching | 3, 5 (`_past_pairs`) | T7 | 12 | 125 |
| 7 Fallback | 1, 6 | T8 (part: blob/scoring) | 5 | 130 |
| 8 Dispatch/CLI/shim | 4, 5, 6, 7 | T1, T2, T8 (ask guard), T11 | 10 | 140 |
| 9 Integration/perf | 8 | T9, T10 | 4 | 144 |
| 10 Evaluation | 9 | G1, G2, G3 (spec 14) | - | 144 |

After EVERY task: `python -B -m unittest` green with the cumulative count in the table (count mismatch = a test was not written or was overwritten - investigate before proceeding).

## Per-Task Review Checklist (reviewer: verify each before approving the task)

1. **Protocol**: every response passes `evaluate.validate_response` for its phase; pairs are `[str, str]` arrays (NOT dicts); `json.dumps(..., allow_nan=False)` clean; memory <= 1 MiB.
2. **Baseline preservation**: `git diff policy.py` shows baseline branches (`mode != 'random'`, random body, `baseline_asks`/`baseline_match` calls, memory echo) byte-identical inside; only surrounding `mode == 'ac'` branches are new.
3. **Stdlib-only policy**: `python -B -c "import policy"` works with no numpy/sklearn installed (CI gate); no `research/` import in policy.py (image does not contain it).
4. **No hidden info**: source audit (T11) + no reads of fields beyond `features.py`'s observable set; no `sim.` internals, no `variant`/`seed`/`events` in decisions.
5. **Determinism**: sorted iteration everywhere in new code (no raw `set`/`dict` order in outputs); same request twice -> identical bytes (tested in T5/T6/T7/T8 groups).
6. **T-labels match the spec's T1-T14** (this plan's task numbers != spec test numbers: Task 1=T5, Task 5=T6, Task 6=T7, Task 7=T8).
7. **After Task 2**: blob present (T4), parity <= 1e-9 (T12 HARD), val AUC 0.5937 +/- 0.001 (T14) - the three gates that make every later number meaningful. Never relax `atol`.
8. **After Task 9**: local T10 values measured + recorded (4 green IntegrationTests; the docker timing test SKIPs until Task 10 builds the image and re-runs it); C7 count-based cap present in `ac_match` since Task 6, firing iff `len(cand) > 12000` - NEVER on measured time; the 5-9 s band triggers ONLY the pre-registered semantics-preserving optimizations (byte-identical outputs); >= 9 s after cap + optimizations = escalate, no tuning.
9. **Task 10**: zero code changes; commands verbatim from spec section 14; G1-G3 logged before metrics read.

## If Something Goes Wrong

- T12/T14 fail after a fresh export -> suspect `sk_model_to_dict` (baseline/leaf values) or `_walk` (threshold direction / missing branch) against spec section 4's contract; never loosen `atol=1e-9`.
- T3 fail -> a copied line drifted; re-copy verbatim from `research/features.py`.
- T6 fail -> tier ordering (`(-blocked, id)` then `(n_missing, id)` then `(-partners, id, field order)`), budget arithmetic (3/1/1), declined fields excluded before ranking.
- T7 fail -> print greedy seed vs local search on the toy edges; adjust MOVES (a/b/c), never the floor discipline or sort keys; remember candidate generation excludes past pairs BEFORE scoring.
- `advance` raises `repeat pair` -> past-pair exclusion missing/differently keyed (`tuple(sorted(...))`); raise occurs in T9 or real eval.
- T9 `validate_response` raises -> pair/ask shape drifted (dicts, extra response keys, non-str members).
- T10 >= 9 s -> the C7 count-based cap (already in `ac_match`; fires iff `len(cand) > 12000`, per Global Constraints) plus ONLY the pre-registered semantics-preserving optimizations; still >= 9 s -> stop and escalate; never add time-dependent or random cutoffs.
- G2 mismatch local vs container -> compare that both run the same policy.py (blob length check locally; image built AFTER final export).
- evaluate.py rejects a run (`valid: false`) -> read `episodes[].error`, treat as a contract bug to fix, re-run that command; never edit evaluate.py.
- Anything outside these remedies -> stop, ledger it, report honestly (spec C7: results never change code without a new approved round).