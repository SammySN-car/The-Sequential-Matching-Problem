"""S06: scoring diagnostics - global vs within-day concordance.

Re-fits the exact out_scale800 pipeline (44 features, HistGB, 4-fold group CV
by world_seed) on the EXISTING rows.csv, solely to compute concordance
diagnostics the frozen report did not separate. Diagnostic instrument only:
no policy trained for deployment, model weights discarded after AUC computation.
"""
import csv
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eda_common import TABLES, log, write_csv  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]

SOFT_PREFIX = 'feat_soft_'
STATE_FEATS = ('feat_day', 'feat_days_since_arrival_mean', 'feat_days_since_arrival_absdiff',
               'feat_ask_budget', 'feat_comp_available', 'feat_comp_available_excl')


def load_xy():
    path = ROOT / 'research' / 'out_scale800' / 'rows.csv'
    X, y, groups, day_keys = [], [], [], []
    n_imputed = 0
    with open(path, newline='', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            if not hasattr(load_xy, '_names'):
                load_xy._names = [k for k in r if k.startswith('feat_')]
            row = []
            for k in load_xy._names:
                v = r[k]
                if v == '':
                    v = '0.0'
                    n_imputed += 1
                row.append(float(v))
            X.append(row)
            y.append(int(r['label']))
            groups.append(r['world_seed'])
            day_keys.append((r['world_seed'], r['variant'], r['policy'],
                             r['collector_seed'], r['day']))
    log(f'  imputed {n_imputed} empty feature cells as 0.0')
    return (np.array(X, dtype=np.float32), np.array(y),
            np.array(groups), day_keys)  # list of tuples (hashable)


def cross_val_scores(X, y, groups, feature_idx, seed=40):
    oof = np.zeros(len(y), dtype=np.float64)
    gkf = GroupKFold(n_splits=4)
    for tr, te in gkf.split(X, y, groups):
        clf = HistGradientBoostingClassifier(
            max_iter=200, learning_rate=0.06, random_state=seed)
        clf.fit(X[tr][:, feature_idx], y[tr])
        oof[te] = clf.predict_proba(X[te][:, feature_idx])[:, 1]
    return oof


def within_day_auc(scores, y, day_keys):
    """Mean per-day AUC over days containing both classes; world-level summary."""
    by_day = defaultdict(list)
    for s, yy, k in zip(scores, y, day_keys):
        by_day[k].append((s, yy))
    day_aucs, day_worlds = [], []
    for k, pairs in by_day.items():
        ys = [p[1] for p in pairs]
        if sum(ys) == 0 or sum(ys) == len(ys):
            continue
        ss = [p[0] for p in pairs]
        day_aucs.append(roc_auc_score(ys, ss))
        day_worlds.append(k[0])
    # world-level aggregation: average day AUCs within world, then across worlds
    by_w = defaultdict(list)
    for w, a in zip(day_worlds, day_aucs):
        by_w[w].append(a)
    world_means = [float(np.mean(v)) for v in by_w.values()]
    return (float(np.mean(day_aucs)), len(day_aucs),
            float(np.mean(world_means)), float(np.std(world_means)))


def main():
    log('S06 scoring diagnostics start')
    X, y, groups, day_keys = load_xy()
    names = load_xy._names
    log(f'  loaded {len(y)} rows, {X.shape[1]} features, '
        f'{int(y.sum())} positives, {len(set(map(str, groups)))} worlds')

    all_idx = list(range(X.shape[1]))
    soft_idx = [i for i, n in enumerate(names) if n.startswith(SOFT_PREFIX)]
    no_soft_idx = [i for i in all_idx if i not in soft_idx]
    state_idx = [i for i, n in enumerate(names) if n in STATE_FEATS]

    log('  fitting full feature set...')
    scores_full = cross_val_scores(X, y, groups, all_idx)
    global_auc = roc_auc_score(y, scores_full)
    wd, n_days, wmean, wstd = within_day_auc(scores_full, y, day_keys)
    log(f'  full: global AUC {global_auc:.4f}; within-day mean AUC {wd:.4f} '
        f'({n_days} two-class days); world-mean within-day {wmean:.4f} ± {wstd:.4f}')

    log('  fitting without soft features...')
    scores_nosoft = cross_val_scores(X, y, groups, no_soft_idx)
    auc_nosoft = roc_auc_score(y, scores_nosoft)

    log('  fitting state-only features (day/budget/competition/history)...')
    scores_state = cross_val_scores(X, y, groups, state_idx)
    auc_state = roc_auc_score(y, scores_state)

    # score variance decomposition (full model)
    grand = float(np.mean(scores_full))
    day_means = defaultdict(list)
    for s, k in zip(scores_full, day_keys):
        day_means[k].append(s)
    day_mean_arr = np.array([float(np.mean(v)) for v in day_means.values()])
    between = float(np.var(day_mean_arr))
    within = float(np.mean([float(np.var(v)) for v in day_means.values()]))
    total = between + within

    # between-day AUC: day-mean score vs day-mean label
    day_labels = defaultdict(list)
    for s, yy, k in zip(scores_full, y, day_keys):
        day_labels[k].append(yy)
    keys = list(day_means.keys())
    dms = [float(np.mean(day_means[k])) for k in keys]
    dlb = [float(np.mean(day_labels[k])) for k in keys]
    auc_betweenday = roc_auc_score([1 if x > 0.5 else 0 for x in dlb], dms) if len(set(dlb)) > 1 else float('nan')

    summary = [
        {'measure': 'global_auc_full_44feat', 'value': round(global_auc, 4),
         'note': 'reproduction; frozen report: 0.5937 [0.5667,0.6208]'},
        {'measure': 'global_auc_no_soft_features', 'value': round(auc_nosoft, 4),
         'note': f'delta vs full: {auc_nosoft - global_auc:+.4f}'},
        {'measure': 'global_auc_state_only', 'value': round(auc_state, 4),
         'note': 'day/budget/competition/history features only'},
        {'measure': 'within_day_mean_auc', 'value': round(wd, 4),
         'note': f'{n_days} two-class days; pairs ranked only inside a day'},
        {'measure': 'within_day_world_mean_auc', 'value': round(wmean, 4),
         'note': f'± {wstd:.4f} across worlds (world is unit)'},
        {'measure': 'between_day_auc', 'value': round(float(auc_betweenday), 4),
         'note': 'day-mean score vs day-mean label; days as unit'},
        {'measure': 'score_var_between_days_share', 'value': round(between / total, 4),
         'note': f'between={between:.6g} within={within:.6g}'},
        {'measure': 'n_positive', 'value': int(y.sum()), 'note': 'scale800 all rows'},
    ]
    write_csv(TABLES / 'scoring_concordance_summary.csv', summary)
    log('  between-day score variance share: '
        f'{100 * between / total:.1f}%')

    # per-world global AUC distribution
    by_w = defaultdict(lambda: ([], []))
    for s, yy, w in zip(scores_full, y, groups):
        by_w[int(w)][0].append(s)
        by_w[int(w)][1].append(yy)
    world_rows = []
    for w in sorted(by_w):
        ss, yy = by_w[w]
        if sum(yy) == 0 or sum(yy) == len(yy):
            continue
        world_rows.append({'world_seed': w, 'n': len(yy), 'positives': int(sum(yy)),
                           'auc': round(roc_auc_score(yy, ss), 4)})
    write_csv(TABLES / 'scoring_world_auc_distribution.csv', world_rows)
    aucs = [r['auc'] for r in world_rows]
    log(f'  per-world AUC: n={len(aucs)} mean={np.mean(aucs):.4f} '
        f'med={np.median(aucs):.4f} [{min(aucs):.3f},{max(aucs):.3f}]')
    log('S06 done')


if __name__ == '__main__':
    main()
