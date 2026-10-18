"""Round 2 Stage 4 - X0: history-lift diagnostic (READ-ONLY on frozen data).

Model A (full 44 features) vs Model B (history group removed -> 34 features)
on the frozen 800-world scale800 dataset, reusing the EXACT original pipeline:

  split    : analyze.world_split(rows, val_frac=0.2, split_seed=0)
             world_key = (world_seed, variant); whole worlds only
  features : features.FEATURE_KEYS  vs  minus features.FEATURE_GROUPS['history']
             (hist_{n_intros,n_mutual,n_dates,yes_rate,n_missing}_{mean,absdiff})
  model    : analyze.fit_models -> HistGradientBoostingClassifier(
             random_state=0, max_iter=200, learning_rate=0.1)
  metrics  : analyze.evaluate (roc_auc, auc_ci95 Hanley-McNeil, avg_precision,
             log_loss, brier)

Stratification on VALIDATION rows only, exact from stored features:
  less-experienced member's prior intro count =
      hist_n_intros_mean - hist_n_intros_absdiff/2   (== min(a,b), exact)
  groups {0, 1-2, 3+} x logging policy {random, greedy}
  (+ marginals). No data reconstruction, no re-collection.

Uncertainty: world-clustered bootstrap over the 160 validation worlds;
cluster = (world_seed, variant); 2000 resamples of 160 clusters with
replacement; multiplicity weights; percentile CI [2.5, 97.5];
per-target seed 9099 + target index (NOT an episode seed).

Output: research/round2_stage4_history_coldstart_audit/x0_results.json
"""
import csv
import hashlib
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
for _p in (str(REPO), str(REPO / 'research')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np
from sklearn.metrics import roc_auc_score, average_precision_score

import analyze
import features

ROWS_CSV = REPO / 'research' / 'out_scale800' / 'rows.csv'
REPORT_JSON = REPO / 'research' / 'out_scale800' / 'report.json'
OUT_JSON = HERE / 'x0_results.json'

TARGETS = (('label_mutual', 'mutual'), ('label', 'msmi'))
HISTORY_KEYS = list(features.FEATURE_GROUPS['history'])
KEYS_A = list(features.FEATURE_KEYS)
KEYS_B = [k for k in features.FEATURE_KEYS if k not in HISTORY_KEYS]
BOOT_SEED_BASE = 9099
BOOT_N = 2000
VAL_FRAC, SPLIT_SEED = 0.2, 0
HYPER = {'random_state': 0, 'max_iter': 200, 'learning_rate': 0.1}


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def load_rows():
    """rows.csv -> row dicts in ORIGINAL (sorted) file order; '' -> NaN/None."""
    rows = []
    with open(ROWS_CSV, newline='', encoding='utf-8') as fh:
        for r in csv.DictReader(fh):
            feats = {}
            for k in KEYS_A:
                v = r['feat_' + k]
                feats[k] = float('nan') if v == '' else float(v)

            def maybe_int(x):
                return None if x == '' else int(x)
            rows.append({'world_seed': int(r['world_seed']),
                         'variant': r['variant'],
                         'policy': r['policy'],
                         'collector_seed': int(r['collector_seed']),
                         'day': int(r['day']),
                         'a': r['a'], 'b': r['b'],
                         'introduction_id': r['introduction_id'],
                         'maturity_day': maybe_int(r['maturity_day']),
                         'label': maybe_int(r['label']),
                         'label_mutual': maybe_int(r['label_mutual']),
                         'label_date': maybe_int(r['label_date']),
                         'features': feats})
    return rows


def min_prior_intros(row):
    """Exact less-experienced member's prior intro count at decision time."""
    f = row['features']
    return f['hist_n_intros_mean'] - f['hist_n_intros_absdiff'] / 2.0


def exp_group(m):
    if m < 0.5:
        return '0'
    if m < 2.5:
        return '1-2'
    return '3+'


def slim(m):
    return {'roc_auc': m['roc_auc'], 'auc_ci95_rowlevel': m['auc_ci95'],
            'avg_precision': m['avg_precision'], 'log_loss': m['log_loss'],
            'brier': m['brier'], 'n': m['n'], 'positives': m['positives'],
            'prevalence': m['prevalence']}


def stratatum(y, sA, sB):
    out = {'n': int(len(y)), 'positives': int(np.sum(y)),
           'prevalence': float(np.mean(y)) if len(y) else None}
    mA, mB = analyze.evaluate(y, sA), analyze.evaluate(y, sB)
    for tag, m in (('A', mA), ('B', mB)):
        e = slim(m)
        e['ap_lift'] = (m['avg_precision'] / out['prevalence']
                        if out['prevalence'] else None)
        out[tag] = e
    if mA['roc_auc'] is not None and mB['roc_auc'] is not None:
        out['delta_auc'] = mA['roc_auc'] - mB['roc_auc']
        out['delta_ap'] = mA['avg_precision'] - mB['avg_precision']
    else:
        out['delta_auc'] = None
        out['delta_ap'] = None
    return out


def cluster_bootstrap(y, sA, sB, codes, n_worlds, seed):
    """World-clustered bootstrap of delta(A-B) on validation rows."""
    rng = np.random.default_rng(seed)
    d_auc, d_ap, skipped = [], [], 0
    w = np.empty(len(y), dtype=float)
    for _ in range(BOOT_N):
        draw = rng.integers(0, n_worlds, size=n_worlds)
        mult = np.bincount(draw, minlength=n_worlds)
        w[:] = mult[codes]
        pos = float(np.dot(y, w))
        tot = float(w.sum())
        if pos <= 0.0 or pos >= tot:
            skipped += 1
            continue
        a_auc = roc_auc_score(y, sA, sample_weight=w)
        b_auc = roc_auc_score(y, sB, sample_weight=w)
        d_auc.append(a_auc - b_auc)
        d_ap.append(average_precision_score(y, sA, sample_weight=w)
                    - average_precision_score(y, sB, sample_weight=w))

    def summarize(v):
        arr = np.asarray(v, dtype=float)
        return {'n_valid': int(arr.size),
                'mean': float(arr.mean()),
                'ci95_percentile': [float(np.percentile(arr, 2.5)),
                                    float(np.percentile(arr, 97.5))],
                'frac_lt_zero': float(np.mean(arr < 0.0)),
                'frac_gt_zero': float(np.mean(arr > 0.0))}
    return {'procedure': 'resample 160 validation world clusters with '
                         'replacement; row weight = cluster multiplicity; '
                         'recompute metric on weighted rows',
            'cluster': '(world_seed, variant)',
            'n_clusters': int(n_worlds), 'resamples': int(BOOT_N),
            'seed': int(seed), 'ci_definition': 'percentile [2.5, 97.5]',
            'skipped_single_class': int(skipped),
            'delta_auc': summarize(d_auc), 'delta_ap': summarize(d_ap)}


def main():
    t0 = time.time()
    log = []

    def say(msg):
        line = '[X0] ' + msg
        print(line, flush=True)
        log.append(line)

    report = json.loads(REPORT_JSON.read_text(encoding='utf-8'))
    say('rows.csv sha256=%s' % sha256_file(ROWS_CSV))
    rows = load_rows()
    say('loaded %d rows' % len(rows))

    train, val = analyze.world_split(rows, val_frac=VAL_FRAC,
                                     split_seed=SPLIT_SEED)
    split_info = {
        'val_frac': VAL_FRAC, 'split_seed': SPLIT_SEED,
        'train_rows': len(train), 'val_rows': len(val),
        'train_worlds': len({analyze.world_key(r) for r in train}),
        'val_worlds': len({analyze.world_key(r) for r in val}),
        'split_overlap': analyze.split_overlap(train, val),
        'row_order': 'rows.csv original (canonical sorted) order preserved',
    }
    say('split: train %d / val %d, worlds %d / %d, overlap %s' % (
        split_info['train_rows'], split_info['val_rows'],
        split_info['train_worlds'], split_info['val_worlds'],
        split_info['split_overlap']))
    rep_te = report['train_eval']
    assert split_info['train_rows'] == rep_te['n_train_rows'], 'train n mismatch'
    assert split_info['val_rows'] == rep_te['n_val_rows'], 'val n mismatch'
    assert split_info['split_overlap'] == {'worlds': 0, 'seeds': 0}, 'overlap!'

    # validation-world codes for the bootstrap (val row order)
    val_worlds = sorted({analyze.world_key(r) for r in val})
    wcode = {wk: i for i, wk in enumerate(val_worlds)}
    codes = np.array([wcode[analyze.world_key(r)] for r in val], dtype=int)

    # strata membership for validation rows
    pol = [r['policy'] for r in val]
    expg = [exp_group(min_prior_intros(r)) for r in val]
    exp_levels = ['0', '1-2', '3+']
    pol_levels = ['random', 'greedy']

    out = {'schema': 'round2_stage4_x0_v1',
           'generated': time.strftime('%Y-%m-%d %H:%M:%S'),
           'input': {'rows_csv': str(ROWS_CSV.relative_to(REPO)).replace('\\', '/'),
                     'rows_csv_sha256': sha256_file(ROWS_CSV),
                     'n_rows': len(rows)},
           'config': {
               'split': 'analyze.world_split(val_frac=0.2, split_seed=0), '
                        'world_key=(world_seed, variant), whole worlds',
               'model': 'sklearn HistGradientBoostingClassifier via '
                        'analyze.fit_models, ' + json.dumps(HYPER),
               'model_a_features': len(KEYS_A),
               'model_b_features': len(KEYS_B),
               'removed_feature_keys': HISTORY_KEYS,
               'removed_group': 'features.FEATURE_GROUPS["history"] '
                                '(5 groups x {mean, absdiff} = 10 keys); '
                                'TEMPORAL keys are NOT in this group',
               'targets': [t for _, t in TARGETS],
               'bootstrap': {'clusters': 'validation worlds',
                             'n_clusters': len(val_worlds),
                             'resamples': BOOT_N,
                             'seeds': {'mutual': BOOT_SEED_BASE,
                                       'msmi': BOOT_SEED_BASE + 1},
                             'ci': 'percentile [2.5, 97.5]'},
               'stratification': {
                   'experience': 'min_prior = hist_n_intros_mean - '
                                 'hist_n_intros_absdiff/2 (exact min(a,b) at '
                                 'decision time); groups 0 / 1-2 / 3+',
                   'policy': "rows.csv 'policy' column (random|greedy)",
                   'scope': 'validation rows only'},
               'sklearn_version': __import__('sklearn').__version__,
               'python_version': sys.version.split()[0]},
           'split': split_info,
           'reproduction_check_vs_scale800_report_json': {},
           'targets': {}}

    for ti, (field, name) in enumerate(TARGETS):
        tt = time.time()
        XtrA, ytr, kept_tr = analyze.build_dataset(train, target=field)
        XvaA, yva, kept_va = analyze.build_dataset(val, target=field)
        XtrB, ytrB, _ = analyze.build_dataset(train, feature_keys=KEYS_B,
                                              target=field)
        XvaB, yvaB, _ = analyze.build_dataset(val, feature_keys=KEYS_B,
                                              target=field)
        assert np.array_equal(ytr, ytrB) and np.array_equal(yva, yvaB), \
            'label mismatch between A/B builds'
        rep = report['train_eval']['targets'][name]
        say('%s: train %d (pos %d) / val %d (pos %d)' % (
            name, len(ytr), int(ytr.sum()), len(yva), int(yva.sum())))
        assert len(ytr) == rep['train_n'] and int(ytr.sum()) == rep['train_pos'], \
            '%s train counts != report.json' % name
        assert len(yva) == rep['val_n'] and int(yva.sum()) == rep['val_pos'], \
            '%s val counts != report.json' % name

        modelsA = dict(analyze.fit_models(XtrA, ytr))
        modelsB = dict(analyze.fit_models(XtrB, ytr))
        mA, mB = modelsA['hist_gb'], modelsB['hist_gb']
        sA = analyze.predict(mA, XvaA)
        sB = analyze.predict(mB, XvaB)
        evA, evB = analyze.evaluate(yva, sA), analyze.evaluate(yva, sB)

        rep_m = rep['models']['hist_gb']
        repro = {}
        for k in ('roc_auc', 'avg_precision', 'log_loss', 'brier'):
            repro[k] = {'model_a_ours': evA[k], 'report_json': rep_m[k],
                        'diff': (None if evA[k] is None or rep_m[k] is None
                                 else evA[k] - rep_m[k])}
        out['reproduction_check_vs_scale800_report_json'][name] = repro
        say('%s Model A vs report.json: %s' % (name, {
            k: v['diff'] for k, v in repro.items()}))

        overall = {
            'n_val': int(len(yva)), 'positives': int(yva.sum()),
            'prevalence': float(yva.mean()),
            'model_a': slim(evA), 'model_b': slim(evB),
            'ap_lift_a': evA['avg_precision'] / float(yva.mean()),
            'ap_lift_b': evB['avg_precision'] / float(yva.mean()),
            'delta_auc_a_minus_b': (None if evA['roc_auc'] is None
                                    else evA['roc_auc'] - evB['roc_auc']),
            'delta_ap_a_minus_b': (None if evA['avg_precision'] is None
                                   else evA['avg_precision'] - evB['avg_precision']),
            'delta_logloss_a_minus_b': (None if evA['log_loss'] is None
                                        else evA['log_loss'] - evB['log_loss']),
            'delta_brier_a_minus_b': (None if evA['brier'] is None
                                      else evA['brier'] - evB['brier']),
        }

        boot = cluster_bootstrap(yva, sA, sB, codes, len(val_worlds),
                                 BOOT_SEED_BASE + ti)

        strata = {'joint': {}, 'experience': {}, 'policy': {}}
        def add(cell_store, key, mask):
            yy = yva[mask]
            if len(yy) == 0:
                cell_store[key] = {'n': 0}
                return
            cell_store[key] = stratatum(yy, sA[mask], sB[mask])
        idx = np.arange(len(yva))
        for e in exp_levels:
            for p in pol_levels:
                m = (np.array(expg) == e) & (np.array(pol) == p)
                add(strata['joint'], '%s|%s' % (e, p), m)
            add(strata['experience'], e, np.array(expg) == e)
        for p in pol_levels:
            add(strata['policy'], p, np.array(pol) == p)

        out['targets'][name] = {
            'overall': overall,
            'world_cluster_bootstrap': boot,
            'strata_validation_only': strata,
            'experience_group_counts_val': {
                e: int(sum(1 for g in expg if g == e)) for e in exp_levels},
            'policy_counts_val': {
                p: int(sum(1 for q in pol if q == p)) for p in pol_levels},
            'elapsed_seconds': round(time.time() - tt, 1)}
        say('%s: delta_auc=%.6f boot CI=%s | elapsed %.1fs' % (
            name, overall['delta_auc_a_minus_b'],
            boot['delta_auc']['ci95_percentile'],
            out['targets'][name]['elapsed_seconds']))

    out['total_elapsed_seconds'] = round(time.time() - t0, 1)
    OUT_JSON.write_text(json.dumps(out, indent=2), encoding='utf-8')
    say('wrote %s (%d bytes)' % (OUT_JSON.name, OUT_JSON.stat().st_size))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())