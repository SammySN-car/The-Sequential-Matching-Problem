"""Section 4: predictive signal at each stage (frozen model, OOF by seed).

Feature sets A/B/C (frozen). Model: HistGradientBoostingClassifier(200,
0.06, rs=40), GroupKFold(4) by seed. Final-MSMI row reuses the frozen OOF
scores (bit-exactly reproduced in ss0 V5). Conditional diagnostics use the
UNCONDITIONAL OOF score restricted to an outcome-defined subset and are
labelled as non-deployable.
"""
import csv, json, sys, time
from pathlib import Path
import numpy as np
from sklearn.metrics import roc_auc_score, average_precision_score

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ss_common as s   # noqa: E402
import s3_signal as s3  # noqa: E402

COND = [
    ('mutual_given_responded', 'both_responded', 'mutual'),
    ('date_given_mutual', 'mutual', 'date'),
    ('timely_second_given_date', 'date', 'timely_second'),
    ('msmi_given_deadline', 'date_within_deadline', 'final_msmi'),
]
SET_TO_OOF = {'A_baseline_count': 'oof_f1', 'B_soft_state': 'oof_f2',
              'C_full_legal': 'oof_f4'}


def main():
    t0 = time.time()
    s.log('ss2_models start')
    fr = s.build_frame(include_feat=True)
    seeds = fr['seeds']
    groups = np.array(fr['groups'])
    rows, per_seed_rows = [], []

    oof_by = {set_name: fr[arr] for set_name, arr in SET_TO_OOF.items()}
    fitted = {}

    for set_name, cols in s.FEATURE_SETS.items():
        X = np.array([[f.get(k, 0.0) for k in cols] for f in fr['feat']],
                     dtype=np.float32)
        for stage in s.STAGES:
            y = fr['stages'][stage]
            if stage == 'final_msmi':
                oof = oof_by[set_name]          # reuse frozen OOF (bit-exact)
                src = 'frozen_oof'
            else:
                oof = s3.oof_scores(X, y, groups)
                src = 'refit_oof'
            fitted[(set_name, stage)] = oof
            auc = float(roc_auc_score(y, oof))
            ap = float(average_precision_score(y, oof))
            prev = float(y.mean())
            ci = s.seed_boot_auc(oof, y, seeds)
            rows.append(dict(
                feature_set=set_name, target=stage, scope='unconditional',
                source=src, n_rows=len(y), n_pos=int(y.sum()),
                prevalence=round(prev, 6), auc=round(auc, 6),
                pr_auc=round(ap, 6),
                lift=round(ap / prev, 6) if prev > 0 else '',
                ci95_low=round(ci[0], 6), ci95_high=round(ci[1], 6),
                power_flag=s.power_flag(y, seeds)))
            s.log('%s/%s auc=%.4f ap=%.4f lift=%.2f %s'
                  % (set_name, stage, auc, ap,
                     ap / prev if prev else float('nan'), src))

            # conditional diagnostic on outcome-defined subset (no refit)
            for clabel, dstage, tstage in COND:
                if tstage != stage:
                    continue
                mask = fr['stages'][dstage] == 1
                ys, ss_ = y[mask], oof[mask]
                if len(ys) == 0 or len(set(ys)) < 2:
                    continue
                auc_c = float(roc_auc_score(ys, ss_))
                ap_c = float(average_precision_score(ys, ss_))
                prev_c = float(ys.mean())
                seeds_c = [x for x, m in zip(seeds, mask) if m]
                ci_c = s.seed_boot_auc(ss_, ys, seeds_c)
                rows.append(dict(
                    feature_set=set_name, target=stage,
                    scope='cond_' + clabel, source=src + '_subset_no_refit',
                    n_rows=int(mask.sum()), n_pos=int(ys.sum()),
                    prevalence=round(prev_c, 6), auc=round(auc_c, 6),
                    pr_auc=round(ap_c, 6),
                    lift=round(ap_c / prev_c, 6) if prev_c > 0 else '',
                    ci95_low=round(ci_c[0], 6), ci95_high=round(ci_c[1], 6),
                    power_flag='outcome_defined_subset'))

    with open(s.OUT / 'stage_model_metrics.csv', 'w', newline='',
              encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)
    s.log('wrote stage_model_metrics.csv (%d rows)' % len(rows))

    # ---- per-seed metrics (inference unit) --------------------------------
    for seed in sorted(set(seeds)):
        m = np.array([x == seed for x in seeds])
        rec = dict(seed=seed, n_edges=int(m.sum()))
        for stage in s.STAGES:
            y = fr['stages'][stage][m]
            rec['n_' + stage] = int(y.sum())
            rec['rate_' + stage] = round(float(y.mean()), 6)
            for set_name in s.FEATURE_SETS:
                oof = fitted[(set_name, stage)][m]
                rec['auc_%s_%s' % (set_name, stage)] = (
                    round(float(roc_auc_score(y, oof)), 6)
                    if len(set(y)) > 1 else '')
        per_seed_rows.append(rec)
    with open(s.OUT / 'seed_group_metrics.csv', 'w', newline='',
              encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=list(per_seed_rows[0]))
        w.writeheader(); w.writerows(per_seed_rows)
    s.log('wrote seed_group_metrics.csv (%d rows)' % len(per_seed_rows))

    # persist fitted unconditional OOF for ss3/ss4 (scores only)
    persist = {k: [float(x) for x in v] for k, v in fitted.items()}
    (s.OUT / 'stage_oof_scores.json').write_text(
        json.dumps({'%s|%s' % k: v for k, v in persist.items()},
                   separators=(',', ':')) + '\n', encoding='utf-8')
    s.log('wrote stage_oof_scores.json')
    s.log('ss2_models done (%.1fs)' % (time.time() - t0))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
