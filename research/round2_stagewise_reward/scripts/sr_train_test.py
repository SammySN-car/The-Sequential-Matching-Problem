"""Tests for sr_train.py (implementation_plan.md Task 6; analysis_plan.md S.7).

Plain python script, standard library only (numpy reaches sr_train only), no
pytest. Prints [PASS]/[FAIL] per test and exits non-zero on any failure.

Fixture-based by design: synthetic feature/label data in a temp dir, NEVER the
full collected training run (that happens once, outside the tests).
"""
import contextlib
import hashlib
import io
import json
import random
import shutil
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sr_train import (N_FEATURES, fit_stage, predict_stage, split_seeds,
                      stage_gate, main as train_main)

EXP_ROOT = Path(__file__).resolve().parents[1]
FIX_SEEDS = tuple(range(40002, 40013))  # 11 groups; val = last round(20%) = 2
VARIANT = 'development'


def test_artifact_deterministic():
    """Same synthetic data twice -> bitwise-identical fit_stage dicts."""
    rng = random.Random(4242)
    n_feat = N_FEATURES + 1  # one extra constant column -> sigma must become 1.0
    X = [[rng.uniform(-2.0, 2.0) for _ in range(n_feat - 1)] + [7.5]
         for _ in range(150)]
    y = [1 if row[0] + row[1] > 0 else 0 for row in X]
    assert set(y) == {0, 1}, 'fixture must contain both classes'
    a = fit_stage(X, y, lam=1.0)
    b = fit_stage(X, y, lam=1.0)
    assert set(a) == {'w', 'bias', 'mu', 'sigma'}, sorted(a)
    assert len(a['w']) == len(a['mu']) == len(a['sigma']) == n_feat, \
        (len(a['w']), len(a['mu']), len(a['sigma']), n_feat)
    # Bitwise determinism, compared as serialized bytes (the artifact path).
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True), \
        'fit_stage is not deterministic'
    assert a['mu'][-1] == 7.5 and a['sigma'][-1] == 1.0, \
        ('constant column must standardise with sigma=1.0', a['mu'][-1], a['sigma'][-1])
    p = predict_stage(a, X[0])
    assert 0.0 < p < 1.0, p
    # Constant predictor sanity: sigma=1, mu=0, w=0 -> sigmoid(bias).
    stage = {'w': [0.0], 'bias': 0.0, 'mu': [0.0], 'sigma': [1.0]}
    assert predict_stage(stage, [123.0]) == 0.5, predict_stage(stage, [123.0])


def test_split_disjoint():
    """Binding split rule: 40001 excluded, fit=40002..40400, val=40401..40500."""
    seeds = list(range(40001, 40501))
    fit, val = split_seeds(seeds)
    assert not (set(fit) & set(val)), 'seed groups in both fit and val'
    assert set(fit) | set(val) == set(range(40002, 40501)), 'union != 40002..40500'
    assert 40001 not in fit and 40001 not in val, 'plumbing pilot 40001 must be excluded'
    assert fit == list(range(40002, 40401)), (fit[0], fit[-1], len(fit))
    assert val == list(range(40401, 40501)), (val[0], val[-1], len(val))
    # Input order is irrelevant (whole groups, sorted seeds).
    assert split_seeds(seeds[::-1]) == (fit, val), 'split depends on input order'
    # Smaller fixture: val = last round(20%) of the collected groups.
    f2, v2 = split_seeds(FIX_SEEDS)
    assert f2 == list(FIX_SEEDS[:-2]) and v2 == list(FIX_SEEDS[-2:]), (f2, v2)


def test_gate_enforced():
    """Plan S.7 gates: 3 positives -> FAILED; entry point returns non-zero."""
    ok, reasons = stage_gate(3, 500, N_FEATURES)
    assert not ok and any('positive' in r for r in reasons), (ok, reasons)
    ok, reasons = stage_gate(100, 100, N_FEATURES)
    assert ok, reasons  # 100/17 = 5.88 EPV >= 5
    ok, reasons = stage_gate(84, 5000, N_FEATURES)
    assert not ok and any('events-per-variable' in r for r in reasons), (ok, reasons)
    ok, reasons = stage_gate(5000, 40, N_FEATURES)
    assert not ok and any('negative' in r for r in reasons), (ok, reasons)

    # CLI path on a tiny 3-positive fixture: non-zero, FAILED artifact, no freeze.
    tmp = Path(tempfile.mkdtemp(prefix='sr_train_gate_'))
    try:
        _write_gate_fixture(tmp)
        results_dir = tmp / 'results'
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            rc = train_main(['--data-dir', str(tmp / 'data'),
                             '--results-dir', str(results_dir),
                             '--plan', str(EXP_ROOT / 'analysis_plan.md'),
                             '--audit', str(EXP_ROOT / 'results' / 'feature_audit.json')])
        assert rc != 0, 'gate failure must exit non-zero'
        assert 'FAILED' in err.getvalue(), err.getvalue()
        art = json.loads((results_dir / 'model_artifact.json').read_text(encoding='utf-8'))
        assert art['stages']['s1']['status'] == 'FAILED', art['stages']['s1']
        assert art['stages']['s1']['n_pos'] == 3, art['stages']['s1']
        assert not (results_dir / 'model_artifact.sha256').exists(), \
            'failed gate must NOT freeze an artifact'
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_pipeline_freeze():
    """Passing tiny fixture: full pipeline -> artifact frozen + metrics written."""
    tmp = Path(tempfile.mkdtemp(prefix='sr_train_pass_'))
    try:
        _write_pass_fixture(tmp)
        results_dir = tmp / 'results'
        rc = train_main(['--data-dir', str(tmp / 'data'),
                         '--results-dir', str(results_dir),
                         '--plan', str(EXP_ROOT / 'analysis_plan.md'),
                         '--audit', str(EXP_ROOT / 'results' / 'feature_audit.json')])
        assert rc == 0, 'passing fixture must return 0, got %r' % rc
        art_path = results_dir / 'model_artifact.json'
        raw = art_path.read_bytes()
        art = json.loads(raw.decode('utf-8'))
        assert art['schema'] == 1
        assert art['features'] and len(art['features']) == N_FEATURES, len(art['features'])
        for st in ('s1', 's2', 's3'):
            entry = art['stages'][st]
            assert entry['status'] == 'OK', (st, entry)
            assert len(entry['w']) == len(entry['mu']) == len(entry['sigma']) == N_FEATURES
            assert isinstance(entry['bias'], float), (st, entry['bias'])
            assert all(isinstance(v, float) for v in entry['w'] + entry['mu']
                       + entry['sigma']), st
        assert art['split']['excluded'] == [40001], art['split']
        # Freeze format: "<sha256>  model_artifact.json" and hash over exact bytes.
        sha_line = (results_dir / 'model_artifact.sha256').read_text(encoding='utf-8').strip()
        expect = hashlib.sha256(raw).hexdigest()
        assert sha_line == '%s  model_artifact.json' % expect, (sha_line, expect)
        met = json.loads((results_dir / 'train_metrics.json').read_text(encoding='utf-8'))
        for st in ('s1', 's2', 's3'):
            assert met['gates'][st]['passed'] is True, met['gates'][st]
            for split in ('fit', 'val'):
                m = met['stages'][st][split]
                assert m['n'] > 0 and 0.0 < m['prevalence'] < 1.0, (st, split, m)
                assert 0.0 <= m['pr_auc'] <= 1.0 and 0.0 <= m['roc_auc'] <= 1.0, (st, split, m)
                assert len(m['calibration_bins']) == 10, (st, split, len(m['calibration_bins']))
        comb = met['combined_pmsmi']['val']
        assert comb['mean_predicted'] > 0.0 and comb['mean_observed'] > 0.0, comb
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------- fixtures ---

def _snap_row(iid, day, feats):
    return {'intro_id': iid, 'seed_group': None, 'variant': VARIANT, 'day': day,
            'members': ['mem_a', 'mem_b'], 'features': [float(v) for v in feats],
            'degree_a': 3, 'degree_b': 4, 'n_edges': 10, 'k_greedy': 3,
            'k_chosen': 3, 'priority': 0.5}


def _write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + '\n')


def _feats(i):
    return [float((i + j) % 7) for j in range(N_FEATURES)]


def _write_gate_fixture(tmp):
    """11 groups, exactly 3 stage-1 positives in the fit split -> gate FAILED."""
    data = tmp / 'data'
    for g in FIX_SEEDS:
        snaps, labs = [], []
        for k in range(3):
            iid = 'gate_%d_%d' % (g, k)
            s1 = 1 if (g == 40002 and k == 0) else 0
            row = _snap_row(iid, 0, _feats(1000 * g + k))
            row['seed_group'] = g
            snaps.append(row)
            labs.append({'intro_id': iid, 'variant': VARIANT, 's1': s1,
                         's2': 1 if s1 else 'NOT_IN_POPULATION',
                         's3': 1 if s1 else 'NOT_IN_POPULATION',
                         'msmi': s1, 'max_observed_day': 40})
        _write_jsonl(data / 'snapshots' / ('seed_%d.jsonl' % g), snaps)
        _write_jsonl(data / 'labels' / ('seed_%d.jsonl' % g), labs)
    # Top up to exactly 3 positives in fit: 40002 has 1; add 2 more in 40003.
    extra_snaps, extra_labs = [], []
    for k in range(2):
        iid = 'gate_extra_%d' % k
        row = _snap_row(iid, 1, _feats(70000 + k))
        row['seed_group'] = 40003
        extra_snaps.append(row)
        extra_labs.append({'intro_id': iid, 'variant': VARIANT, 's1': 1,
                           's2': 'NOT_IN_POPULATION', 's3': 'NOT_IN_POPULATION',
                           'msmi': 0, 'max_observed_day': 40})
    snap_path = data / 'snapshots' / 'seed_40003.jsonl'
    with open(snap_path, 'a', encoding='utf-8', newline='\n') as fh:
        for row in extra_snaps:
            fh.write(json.dumps(row, sort_keys=True) + '\n')
    with open(data / 'labels' / 'seed_40003.jsonl', 'a', encoding='utf-8', newline='\n') as fh:
        for row in extra_labs:
            fh.write(json.dumps(row, sort_keys=True) + '\n')


def _write_pass_fixture(tmp):
    """Every gate passes (fit: s1 400/400, s2 250/150, s3 150/100)."""
    data = tmp / 'data'
    fit_groups = list(FIX_SEEDS[:-2])
    val_groups = list(FIX_SEEDS[-2:])

    def emit(group, rows_spec):
        snaps, labs = [], []
        for k, (s1, s2, s3, msmi) in enumerate(rows_spec):
            iid = 'pass_%d_%04d' % (group, k)
            row = _snap_row(iid, k % 60, _feats(group * 10000 + k))
            row['seed_group'] = group
            snaps.append(row)
            labs.append({'intro_id': iid, 'variant': VARIANT, 's1': s1, 's2': s2,
                         's3': s3, 'msmi': msmi, 'max_observed_day': 60})
        _write_jsonl(data / 'snapshots' / ('seed_%d.jsonl' % group), snaps)
        _write_jsonl(data / 'labels' / ('seed_%d.jsonl' % group), labs)

    # Fit rows: 800 rows -> s1 400 pos / 400 neg; s2 pop 400 (250/150);
    # s3 pop 250 (150/100).
    fit_rows = []
    for i in range(800):
        s1 = 1 if i % 2 == 0 else 0
        if not s1:
            fit_rows.append((0, 'NOT_IN_POPULATION', 'NOT_IN_POPULATION', 0))
            continue
        j = i // 2  # 0..399 among s1 positives
        s2 = 1 if j < 250 else 0
        if not s2:
            fit_rows.append((1, 0, 'NOT_IN_POPULATION', 0))
            continue
        s3 = 1 if j < 150 else 0
        fit_rows.append((1, 1, s3, s3))
    for idx, group in enumerate(fit_groups):
        emit(group, fit_rows[idx::len(fit_groups)])
    # Val rows: 300 -> s1 150/150; s2 pop 150 (80/70); s3 pop 80 (40/40).
    val_rows = []
    for i in range(300):
        s1 = 1 if i % 2 == 0 else 0
        if not s1:
            val_rows.append((0, 'NOT_IN_POPULATION', 'NOT_IN_POPULATION', 0))
            continue
        j = i // 2  # 0..149
        s2 = 1 if j < 80 else 0
        if not s2:
            val_rows.append((1, 0, 'NOT_IN_POPULATION', 0))
            continue
        s3 = 1 if j < 40 else 0
        val_rows.append((1, 1, s3, s3))
    for idx, group in enumerate(val_groups):
        emit(group, val_rows[idx::len(val_groups)])


def test_metrics_sanity():
    """PR-AUC / ROC-AUC / log loss against hand-checkable cases."""
    import numpy as np
    from sr_train import average_precision, log_loss, roc_auc
    y = [1, 1, 1, 0, 0, 0]
    # Perfect ranking.
    assert average_precision(y, [0.9, 0.8, 0.7, 0.6, 0.5, 0.4]) == 1.0
    assert roc_auc(y, [0.9, 0.8, 0.7, 0.6, 0.5, 0.4]) == 1.0
    # Inverted ranking.
    assert roc_auc(y, [0.4, 0.5, 0.6, 0.7, 0.8, 0.9]) == 0.0
    # Constant scores: AP = prevalence (tie grouping), AUC = 0.5, not luck.
    assert average_precision(y, [0.5] * 6) == 0.5
    assert roc_auc(y, [0.5] * 6) == 0.5
    # Balanced tie blocks with labels in the WORST possible tie order
    # (grouped AP like precision_recall_curve: 0.5, not tie-order luck).
    assert average_precision([1, 0, 1, 0], [0.9, 0.9, 0.1, 0.1]) == 0.5
    # pairwise: 0.9/0.9 tie .5 + 0.9>0.1 win 1 + 0.1<0.9 loss 0 + 0.1/0.1 tie .5
    assert roc_auc([1, 0, 1, 0], [0.9, 0.9, 0.1, 0.1]) == 0.5
    # Random continuous scores: AP ~ prevalence, AUC ~ 0.5 (fixed seed).
    rng = np.random.default_rng(4242)
    ys = (rng.random(50000) < 0.14).astype(float)
    ps = rng.random(50000)
    ap, auc = average_precision(ys, ps), roc_auc(ys, ps)
    assert abs(ap - ys.mean()) < 0.01, (ap, ys.mean())
    assert abs(auc - 0.5) < 0.02, auc
    # Log loss of the truth itself beats any constant.
    assert log_loss([1, 0], [1.0 - 1e-12, 1e-12]) < 1e-10


def main():
    tests = [test_artifact_deterministic, test_split_disjoint,
             test_gate_enforced, test_pipeline_freeze, test_metrics_sanity]
    failures = 0
    for test in tests:
        try:
            test()
        except Exception as exc:  # noqa: BLE001 - harness reports every failure
            failures += 1
            print('[FAIL] %s: %s' % (test.__name__, ascii(str(exc))[:400]))
        else:
            print('[PASS] %s' % test.__name__)
    print('SUMMARY: %d/%d PASS' % (len(tests) - failures, len(tests)))
    sys.exit(1 if failures else 0)


if __name__ == '__main__':
    main()
