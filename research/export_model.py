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