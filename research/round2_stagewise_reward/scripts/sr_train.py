"""Stage-wise L2-logistic training, prediction diagnostics and model freeze
(implementation_plan.md Task 6; analysis_plan.md S.7 / S.13).

Consumes ONLY the collected data (read-only):
  data/snapshots/seed_<g>.jsonl  - one row per introduction: 17 frozen features
  data/labels/seed_<g>.jsonl     - stage labels, joined on (variant, intro_id)
                                   (intro_id alone collides across variants)

Produces:
  results/train_metrics.json        - per-stage fit/val diagnostics + gates
  results/model_artifact.json       - {schema, features, stages, split, plan hash}
  results/model_artifact.sha256     - freeze, written ONLY if every fit gate passes

Model (plan S.7): three logistic regressions, numpy IRLS, features standardised
with FIT-split statistics only, lambda = 1.0 fixed on non-bias terms, bias
unpenalised, deterministic zero init, tol 1e-9 / max 100 iterations. No
hyperparameter search, no resampling, no class weighting (natural prevalence).
This file is research-side (numpy allowed); the POLICY re-infers in pure stdlib
from the frozen JSON numbers (json default float repr, never rounded).

Split rule (binding, brief + plan S.13): seed 40001 (plumbing pilot) excluded
from fit AND val; fit = first 80% of sorted collected groups = 40002..40400;
val = last 20% = 40401..40500; whole groups together; asserted disjoint.
"""
import argparse
import datetime
import hashlib
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
EXP_ROOT = SCRIPT_DIR.parent
DEFAULT_DATA_DIR = EXP_ROOT / 'data'
DEFAULT_RESULTS_DIR = EXP_ROOT / 'results'
DEFAULT_PLAN = EXP_ROOT / 'analysis_plan.md'
DEFAULT_AUDIT = EXP_ROOT / 'results' / 'feature_audit.json'

STAGES = ('s1', 's2', 's3')
STAGE_DESC = {'s1': 'mutual acceptance', 's2': 'timely first date',
              's3': 'timely mutual second yes'}
N_FEATURES = 17
EXCLUDED_SEEDS = (40001,)

# Plan S.7 fit gates, decided on the FIT split only.
GATE_MIN_POS = 100
GATE_MIN_NEG = 100
GATE_MIN_EPV = 5.0          # events-per-variable = positives / 17

LAM = 1.0                  # fixed; no search
IRLS_TOL = 1e-9
IRLS_MAX_ITERS = 100
METRIC_EPS = 1e-15          # log-loss clipping only (never on stored weights)


# ------------------------------------------------------------------ fitting --

def fit_stage(X, y, lam=LAM):
    """L2-regularised logistic regression by IRLS on standardised features.

    Standardisation (mu, sigma) comes from X ONLY; sigma == 0 features become
    sigma = 1.0. Deterministic: zero init, fixed iteration order. Non-bias terms
    are penalised by `lam`; the bias is unpenalised. Converges when the largest
    absolute parameter update drops below IRLS_TOL, else stops after
    IRLS_MAX_ITERS iterations (deterministic either way).

    Returns {'w': [floats], 'bias': float, 'mu': [floats], 'sigma': [floats]}.
    """
    Xa = np.asarray(X, dtype=np.float64)
    ya = np.asarray(y, dtype=np.float64)
    if Xa.ndim != 2:
        raise ValueError('X must be 2-D, got shape %r' % (Xa.shape,))
    if Xa.shape[0] != ya.shape[0] or ya.shape[0] == 0:
        raise ValueError('row mismatch: X %r vs y %r' % (Xa.shape, ya.shape))
    n, d = Xa.shape

    mu = Xa.mean(axis=0)
    sigma = Xa.std(axis=0)                 # population std (ddof=0), from X only
    sigma = np.where(sigma == 0.0, 1.0, sigma)
    Z = (Xa - mu) / sigma
    A = np.empty((n, d + 1), dtype=np.float64)
    A[:, 0] = 1.0                          # unpenalised bias column
    A[:, 1:] = Z

    beta = np.zeros(d + 1, dtype=np.float64)           # deterministic init
    pen = np.zeros(d + 1, dtype=np.float64)
    pen[1:] = lam                          # bias (index 0) unpenalised
    P = np.diag(pen)

    for _ in range(IRLS_MAX_ITERS):
        eta = A @ beta
        # Overflow-safe sigmoid.
        p = np.where(eta >= 0.0, 1.0 / (1.0 + np.exp(-np.minimum(eta, 700.0))),
                     np.exp(np.maximum(eta, -700.0)) / (1.0 + np.exp(np.maximum(eta, -700.0))))
        wgt = np.maximum(p * (1.0 - p), 1e-12)
        grad = A.T @ (ya - p) - pen * beta             # penalised gradient
        hess = A.T @ (A * wgt[:, None]) + P            # penalised Hessian
        delta = np.linalg.solve(hess, grad)
        beta = beta + delta
        if np.max(np.abs(delta)) < IRLS_TOL:
            break
    if not np.all(np.isfinite(beta)):
        raise ValueError('IRLS produced non-finite parameters')
    return {'w': [float(v) for v in beta[1:]],
            'bias': float(beta[0]),
            'mu': [float(v) for v in mu],
            'sigma': [float(v) for v in sigma]}


def predict_stage(stage, x):
    """sigmoid(bias + ((x - mu) / sigma) . w) in pure stdlib arithmetic."""
    w, mu, sigma = stage['w'], stage['mu'], stage['sigma']
    eta = float(stage['bias'])
    for i, wi in enumerate(w):
        eta += wi * (float(x[i]) - mu[i]) / sigma[i]
    if eta >= 709.0:
        return 1.0
    if eta <= -709.0:
        return 0.0
    return 1.0 / (1.0 + math.exp(-eta))


# -------------------------------------------------------------------- split --

def split_seeds(seeds):
    """(fit_seeds, val_seeds) for whole seed groups.

    Binding rule (brief; plan S.13): EXCLUDED_SEEDS (plumbing pilot 40001) never
    enters either partition; remaining sorted groups -> fit = first 80%,
    val = last round(20%). On the collected range this is exactly
    fit 40002..40400 / val 40401..40500. Order-independent; asserted disjoint.
    """
    uniq = sorted({int(s) for s in seeds} - set(EXCLUDED_SEEDS))
    if len(uniq) < 2:
        raise ValueError('need >= 2 trainable seed groups, got %d' % len(uniq))
    n_val = max(1, int(round(0.2 * len(uniq))))
    fit, val = uniq[:-n_val], uniq[-n_val:]
    if set(fit) & set(val):
        raise ValueError('seed groups in both partitions')
    return fit, val


def stage_gate(n_pos, n_neg, n_features=N_FEATURES):
    """Plan S.7 gate on the FIT split. Returns (passed, failure reasons)."""
    fails = []
    if n_pos < GATE_MIN_POS:
        fails.append('positives %d < %d' % (n_pos, GATE_MIN_POS))
    if n_neg < GATE_MIN_NEG:
        fails.append('negatives %d < %d' % (n_neg, GATE_MIN_NEG))
    epv = n_pos / float(n_features)
    if epv < GATE_MIN_EPV:
        fails.append('events-per-variable %.2f < %.1f (positives / %d)'
                     % (epv, GATE_MIN_EPV, n_features))
    return (not fails), fails


# ------------------------------------------------------------------- input ---

def _read_jsonl(path):
    with open(path, 'r', encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def _is01(v):
    """True iff a label value is an in-population 0/1 (never a status string)."""
    return type(v) is int and v in (0, 1)


def collected_seeds(data_dir):
    """Sorted seed groups present in data/snapshots (seed_<g>.jsonl)."""
    seeds = []
    for path in sorted((data_dir / 'snapshots').glob('seed_*.jsonl')):
        try:
            seeds.append(int(path.stem.split('_', 1)[1]))
        except ValueError:
            continue
    if not seeds:
        raise SystemExit('no data/snapshots/seed_*.jsonl under %s' % data_dir)
    return sorted(seeds)


def load_rows(data_dir, seeds, n_features):
    """Snapshot rows joined to labels on (variant, intro_id) within each group.

    Returns [(seed_group, features[17], label_dict), ...]. Raises if any snapshot
    row lacks a label (join key collision would otherwise hide as a silent drop).
    """
    rows = []
    for g in seeds:
        labels = {}
        for lab in _read_jsonl(data_dir / 'labels' / ('seed_%d.jsonl' % g)):
            labels[(lab['variant'], lab['intro_id'])] = lab
        if not labels:
            raise SystemExit('missing labels for seed group %d' % g)
        for snap in _read_jsonl(data_dir / 'snapshots' / ('seed_%d.jsonl' % g)):
            lab = labels.get((snap['variant'], snap['intro_id']))
            if lab is None:
                raise ValueError('label join failed on (variant, intro_id)=%r '
                                 'in seed group %d'
                                 % ((snap['variant'], snap['intro_id']), g))
            feats = snap['features']
            if len(feats) != n_features:
                raise ValueError('feature count %d != %d (seed %d, %s)'
                                 % (len(feats), n_features, g, snap['intro_id']))
            rows.append((g, [float(v) for v in feats], lab))
    return rows


def stage_population(rows, stage):
    """(X, y, excluded_counts) for one stage's in-population labels (plan S.5)."""
    X, y = [], []
    excl = {'NOT_IN_POPULATION': 0, 'UNKNOWN': 0, 'other': 0}
    for _g, feats, lab in rows:
        v = lab[stage]
        if _is01(v):
            X.append(feats)
            y.append(int(v))
        elif v == 'NOT_IN_POPULATION':
            excl['NOT_IN_POPULATION'] += 1
        elif v == 'UNKNOWN':
            excl['UNKNOWN'] += 1
        else:
            excl['other'] += 1
    return X, y, excl


def combined_population(rows):
    """(X, y, excluded_counts) where ALL THREE stage labels are in-population and
    msmi is decided; P_MSMI = p1*p2*p3 is evaluated against msmi on exactly these
    rows."""
    X, y = [], []
    excl = {'NOT_IN_POPULATION': 0, 'UNKNOWN': 0, 'other': 0}
    for _g, feats, lab in rows:
        vals = [lab[s] for s in STAGES]
        m = lab['msmi']
        if not all(_is01(v) for v in vals) or not _is01(m):
            if any(v == 'UNKNOWN' for v in vals) or m == 'UNKNOWN':
                excl['UNKNOWN'] += 1
            elif any(v == 'NOT_IN_POPULATION' for v in vals) \
                    or m == 'NOT_IN_POPULATION':
                excl['NOT_IN_POPULATION'] += 1
            else:
                excl['other'] += 1
            continue
        X.append(feats)
        y.append(int(m))
    return X, y, excl


# ------------------------------------------------------------------ metrics --

def _arrays(y, p):
    return (np.asarray(y, dtype=np.float64), np.asarray(p, dtype=np.float64))


def average_precision(y, p):
    """PR-AUC as average precision, grouping tied scores (constant predictor ->
    AP = prevalence, never tie-order luck). Ties by stable score order."""
    y, p = _arrays(y, p)
    n_pos = float(y.sum())
    if y.size == 0 or n_pos == 0:
        return float('nan')
    order = np.argsort(-p, kind='mergesort')      # descending score
    ys, ps = y[order], p[order]
    tp = np.cumsum(ys)
    # End of each distinct-score group: last index of every tie block.
    end = np.flatnonzero(np.r_[ps[:-1] != ps[1:], True])
    group_tp = tp[end]
    group_pos = np.diff(np.r_[0.0, group_tp])     # positives per score group
    precision = group_tp / (end + 1.0)            # precision after each group
    return float((group_pos * precision).sum() / n_pos)


def roc_auc(y, p):
    """Mann-Whitney U with average ranks for tied scores."""
    y, p = _arrays(y, p)
    n_pos = float(y.sum())
    n_neg = float(y.size - n_pos)
    if n_pos == 0 or n_neg == 0:
        return float('nan')
    order = np.argsort(p, kind='mergesort')
    sp = p[order]
    ranks = np.empty(sp.size, dtype=np.float64)
    i = 0
    while i < sp.size:                      # tie-block average ranks (1-based)
        j = i
        while j + 1 < sp.size and sp[j + 1] == sp[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2.0 + 1.0
        i = j + 1
    rank_sum_pos = ranks[y == 1].sum()       # ranks are in ORIGINAL row order
    return float((rank_sum_pos - n_pos * (n_pos + 1.0) / 2.0) / (n_pos * n_neg))


def log_loss(y, p):
    y, p = _arrays(y, p)
    pc = np.clip(p, METRIC_EPS, 1.0 - METRIC_EPS)
    return float(-(y * np.log(pc) + (1.0 - y) * np.log(1.0 - pc)).mean())


def calibration_bins(y, p, n_bins=10):
    """10-bin equal-count reliability table (bin means + counts)."""
    y, p = _arrays(y, p)
    if y.size == 0:
        return []
    order = np.argsort(p, kind='mergesort')
    out = []
    for idx, chunk in enumerate(np.array_split(order, n_bins), start=1):
        if chunk.size == 0:
            continue
        out.append({'bin': idx, 'count': int(chunk.size),
                    'predicted': float(p[chunk].mean()),
                    'observed': float(y[chunk].mean())})
    return out


def evaluate_predictions(y, p, baseline_p):
    """Full honest diagnostic block for one split (plan S.7 metrics)."""
    y, p = _arrays(y, p)
    prev = float(y.mean()) if y.size else float('nan')
    return {
        'n': int(y.size),
        'n_pos': int(y.sum()),
        'n_neg': int(y.size - y.sum()),
        'prevalence': prev,
        'pr_auc': average_precision(y, p),
        'roc_auc': roc_auc(y, p),
        'log_loss': log_loss(y, p),
        # Constant-prevalence baseline: p = FIT-split prevalence (the deployable
        # no-signal constant); its PR-AUC on any split equals that split's own
        # prevalence (AP of a constant predictor).
        'baseline_p': float(baseline_p),
        'baseline_log_loss': log_loss(y, np.full(y.size, float(baseline_p))),
        'baseline_pr_auc': prev,
        'calibration_bins': calibration_bins(y, p),
    }


# ------------------------------------------------------------------- output --

def _utc_now_iso():
    return datetime.datetime.now(datetime.timezone.utc).replace(
        microsecond=0).isoformat().replace('+00:00', 'Z')


def _write_json(path, obj):
    text = json.dumps(obj, indent=2, sort_keys=True) + '\n'
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(text)
    return text


def _sha256_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _pop_block(X, y, excl):
    return {'n_rows': len(y), 'n_pos': int(sum(y)), 'n_neg': int(len(y) - sum(y)),
            'excluded_not_in_population': excl['NOT_IN_POPULATION'],
            'excluded_unknown': excl['UNKNOWN'],
            'excluded_other': excl['other']}


# --------------------------------------------------------------------- main --

def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Stage-model training + freeze (Task 6, plan S.7)')
    parser.add_argument('--data-dir', default=str(DEFAULT_DATA_DIR),
                        help='collected data dir (default: experiment data/)')
    parser.add_argument('--results-dir', default=str(DEFAULT_RESULTS_DIR),
                        help='output results dir (default: experiment results/)')
    parser.add_argument('--plan', default=str(DEFAULT_PLAN),
                        help='frozen analysis_plan.md to hash into the artifact')
    parser.add_argument('--audit', default=str(DEFAULT_AUDIT),
                        help='feature_audit.json (frozen 17-feature order)')
    args = parser.parse_args(argv)

    data_dir = Path(args.data_dir)
    results_dir = Path(args.results_dir)
    started = time.time()

    audit = json.loads(Path(args.audit).read_text(encoding='utf-8'))
    features = [row['name'] for row in audit['rows']]
    if len(features) != N_FEATURES:
        print('feature audit has %d names, expected %d' % (len(features), N_FEATURES),
              file=sys.stderr)
        return 1

    # --- split (binding) -----------------------------------------------------
    collected = collected_seeds(data_dir)
    fit_seeds, val_seeds = split_seeds(collected)
    if set(fit_seeds) & set(val_seeds):
        print('SPLIT BREACH: seed groups in both fit and val', file=sys.stderr)
        return 1
    if set(fit_seeds) | set(val_seeds) != set(collected) - set(EXCLUDED_SEEDS):
        print('SPLIT BREACH: fit+val union != collected minus %r' % (EXCLUDED_SEEDS,),
              file=sys.stderr)
        return 1
    n_decision_path = data_dir / 'n_decision.json'
    if n_decision_path.exists():
        val_from = json.loads(n_decision_path.read_text(encoding='utf-8'))['val_from']
        if val_seeds[0] != val_from:
            print('SPLIT BREACH: val starts at %d, n_decision val_from=%d'
                  % (val_seeds[0], val_from), file=sys.stderr)
            return 1

    print('split: fit groups %d (%d..%d), val groups %d (%d..%d), excluded %r'
          % (len(fit_seeds), fit_seeds[0], fit_seeds[-1], len(val_seeds),
             val_seeds[0], val_seeds[-1], EXCLUDED_SEEDS), flush=True)

    # --- load + populations --------------------------------------------------
    fit_rows = load_rows(data_dir, fit_seeds, len(features))
    val_rows = load_rows(data_dir, val_seeds, len(features))
    print('rows: fit %d, val %d' % (len(fit_rows), len(val_rows)), flush=True)

    pops = {st: {'fit': stage_population(fit_rows, st),
                 'val': stage_population(val_rows, st)} for st in STAGES}
    comb = {'fit': combined_population(fit_rows), 'val': combined_population(val_rows)}

    populations = {st: {'fit': _pop_block(*pops[st]['fit']),
                        'val': _pop_block(*pops[st]['val'])} for st in STAGES}
    populations['combined_pmsmi'] = {'fit': _pop_block(*comb['fit']),
                                     'val': _pop_block(*comb['val'])}

    # --- gates (fit split only) ---------------------------------------------
    gates, failures = {}, []
    for st in STAGES:
        n_pos = populations[st]['fit']['n_pos']
        n_neg = populations[st]['fit']['n_neg']
        passed, reasons = stage_gate(n_pos, n_neg, len(features))
        gates[st] = {'passed': passed, 'n_pos': n_pos, 'n_neg': n_neg,
                     'epv': n_pos / float(len(features)), 'failures': reasons}
        print('gate %s (%s): %s (pos=%d neg=%d epv=%.1f)%s'
              % (st, STAGE_DESC[st], 'PASS' if passed else 'FAILED', n_pos, n_neg,
                 gates[st]['epv'], '' if passed else ' -> ' + '; '.join(reasons)),
              flush=True)
        if not passed:
            failures.append(st)

    # --- fit passing stages --------------------------------------------------
    stages = {}
    models = {}
    for st in STAGES:
        if gates[st]['passed']:
            X, y, _ = pops[st]['fit']
            model = fit_stage(X, y, lam=LAM)
            models[st] = model
            stages[st] = {'status': 'OK', 'w': model['w'], 'bias': model['bias'],
                          'mu': model['mu'], 'sigma': model['sigma'],
                          'n_pos': gates[st]['n_pos'], 'n_neg': gates[st]['n_neg']}
        else:
            stages[st] = {'status': 'FAILED',
                          'n_pos': gates[st]['n_pos'],
                          'n_neg': gates[st]['n_neg'],
                          'n_rows': populations[st]['fit']['n_rows'],
                          'gate_failures': gates[st]['failures']}

    # --- metrics (fit + val separately, per stage) ---------------------------
    metrics_doc = {
        'schema': 1,
        'split': {'fit_range': [fit_seeds[0], fit_seeds[-1]],
                  'val_range': [val_seeds[0], val_seeds[-1]],
                  'excluded': list(EXCLUDED_SEEDS),
                  'n_fit_groups': len(fit_seeds), 'n_val_groups': len(val_seeds),
                  'fit_seeds': fit_seeds, 'val_seeds': val_seeds},
        'populations': populations,
        'gates': gates,
        'stages': {},
        'combined_pmsmi': {},
    }
    for st in STAGES:
        if not gates[st]['passed']:
            continue
        baseline_p = populations[st]['fit']['n_pos'] / float(
            populations[st]['fit']['n_rows'])
        block = {}
        for split_name, rows in (('fit', fit_rows), ('val', val_rows)):
            X, y, _ = stage_population(rows, st)
            p = [predict_stage(models[st], feats) for feats in X]
            block[split_name] = evaluate_predictions(y, p, baseline_p)
            m = block[split_name]
            print('%s %s: n=%d prev=%.4f pr_auc=%.4f (baseline %.4f) '
                  'roc_auc=%.4f log_loss=%.4f'
                  % (st, split_name, m['n'], m['prevalence'], m['pr_auc'],
                     m['baseline_pr_auc'], m['roc_auc'], m['log_loss']), flush=True)
        metrics_doc['stages'][st] = block

    # --- combined P_MSMI = p1*p2*p3 vs observed msmi -------------------------
    if not failures and len(models) == len(STAGES):
        fit_comb_y = comb['fit'][1]
        comb_baseline = (sum(fit_comb_y) / float(len(fit_comb_y))
                         if fit_comb_y else 0.0)
        for split_name, rows in (('fit', comb['fit']), ('val', comb['val'])):
            X, y, _ = rows
            if not X:
                continue
            p = [predict_stage(models['s1'], feats)
                 * predict_stage(models['s2'], feats)
                 * predict_stage(models['s3'], feats) for feats in X]
            block = evaluate_predictions(y, p, comb_baseline)
            block['mean_predicted'] = float(np.mean(p))
            block['mean_observed'] = float(np.mean(y))
            if split_name == 'val':
                metrics_doc['combined_pmsmi']['val'] = block
                print('combined val: n=%d prev=%.4f pr_auc=%.4f (baseline %.4f) '
                      'roc_auc=%.4f log_loss=%.4f mean_pred=%.4f mean_obs=%.4f'
                      % (block['n'], block['prevalence'], block['pr_auc'],
                         block['baseline_pr_auc'], block['roc_auc'],
                         block['log_loss'], block['mean_predicted'],
                         block['mean_observed']), flush=True)
            else:
                metrics_doc['combined_pmsmi']['fit_baseline_prevalence'] = comb_baseline

    _write_json(results_dir / 'train_metrics.json', metrics_doc)

    # --- artifact (+ freeze only when every gate passed) ---------------------
    artifact = {
        'schema': 1,
        'features': features,
        'stages': stages,
        'split': {'fit_range': [fit_seeds[0], fit_seeds[-1]],
                  'val_range': [val_seeds[0], val_seeds[-1]],
                  'excluded': list(EXCLUDED_SEEDS)},
        'plan_sha256': _sha256_file(Path(args.plan)),
        'created': _utc_now_iso(),
    }
    _write_json(results_dir / 'model_artifact.json', artifact)

    if failures:
        print('FIT GATE FAILED for stage(s): %s - model_artifact.json written '
              'with FAILED status but NOT frozen (no .sha256); do not proceed.'
              % ', '.join(failures), file=sys.stderr)
        return 1

    raw = (results_dir / 'model_artifact.json').read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    with open(results_dir / 'model_artifact.sha256', 'w', encoding='utf-8',
              newline='\n') as fh:
        fh.write('%s  model_artifact.json\n' % digest)
    print('frozen model_artifact.json sha256=%s (all three stage gates PASS) '
          'in %.1fs' % (digest, time.time() - started), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
