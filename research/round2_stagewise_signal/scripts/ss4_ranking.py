"""Section 6: explain the ranking failure through stagewise results.

Per-stage signal (A/B/C AUCs + paired B-vs-A delta with seed bootstrap),
the 173 positive-edge F2 rank distribution, per-seed consistency, and the
rare-target sensitivity caveat. Separates intermediate-outcome findings from
final-MSMI findings; makes no policy claim.
"""
import csv, json, sys, time
from pathlib import Path
import numpy as np
from sklearn.metrics import roc_auc_score

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ss_common as s  # noqa: E402

ORDER = s.STAGES


def paired_delta_boot(oof_a, oof_b, y, seeds, b=s.B, seed=s.SEED):
    """Seed-group bootstrap CI for AUC(B) - AUC(A), paired on rows."""
    uniq = sorted(set(seeds))
    by = defaultdict = {}
    from collections import defaultdict as dd
    by = dd(list)
    for i, g in enumerate(seeds):
        by[g].append(i)
    rng = np.random.default_rng(seed)
    y = np.asarray(y)
    out = []
    for _ in range(b):
        pick = rng.choice(len(uniq), size=len(uniq), replace=True)
        idx = np.concatenate([np.array(by[uniq[i]]) for i in pick])
        yy = y[idx]
        if len(set(yy)) < 2:
            continue
        out.append(float(roc_auc_score(yy, oof_b[idx]) -
                         roc_auc_score(yy, oof_a[idx])))
    if not out:
        return [float('nan'), float('nan')]
    return [float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))]


def main():
    t0 = time.time()
    s.log('ss4_ranking start')
    fr = s.build_frame()
    seeds = fr['seeds']

    # metrics table (AUCs + CIs) from ss2
    mm = list(csv.DictReader(open(s.OUT / 'stage_model_metrics.csv',
                                  encoding='utf-8')))
    def get_auc(fs, st):
        r = next((x for x in mm if x['feature_set'] == fs
                  and x['target'] == st and x['scope'] == 'unconditional'),
                 None)
        return r

    sb_all = json.loads((s.OUT / 'stage_oof_scores.json').read_text(
        encoding='utf-8'))
    oof_f1 = np.array(sb_all['A_baseline_count|final_msmi']) \
        if False else fr['oof_f1']
    # per-stage A/B arrays for the paired delta (refit ones for non-msmi)
    stage_oof = {k: np.array(v) for k, v in sb_all.items()}

    per_stage = []
    for st in ORDER:
        ra, rb, rc = get_auc('A_baseline_count', st), \
            get_auc('B_soft_state', st), get_auc('C_full_legal', st)
        oa = stage_oof['A_baseline_count|%s' % st]
        ob = stage_oof['B_soft_state|%s' % st]
        y = fr['stages'][st]
        d = float(roc_auc_score(y, ob) - roc_auc_score(y, oa))
        dci = paired_delta_boot(oa, ob, y, seeds)
        per_stage.append(dict(
            stage=st, n_pos=int(y.sum()),
            prevalence=round(float(y.mean()), 6),
            auc_A=float(ra['auc']), auc_B=float(rb['auc']),
            auc_C=float(rc['auc']),
            auc_B_ci=[float(rb['ci95_low']), float(rb['ci95_high'])],
            lift_B=float(rb['lift']),
            delta_B_minus_A=round(d, 6),
            delta_B_minus_A_ci=[round(dci[0], 6), round(dci[1], 6)],
            delta_excludes_zero=bool(dci[0] > 0 or dci[1] < 0),
            power_flag=rb['power_flag']))
        s.log('%s delta(B-A)=%.4f ci=[%.4f,%.4f]' % (st, d, dci[0], dci[1]))

    # ---- 173 positive-edge F2 rank distribution --------------------------
    per = s.load_positive_ranks()
    pct = [float(r['f2_percentile']) for r in per]
    bpct = [int(r['baseline_rank']) / int(r['n_edges']) for r in per]
    pos = dict(
        n_positive_edges=len(per),
        mean_f2_percentile=round(float(np.mean(pct)), 6),
        median_f2_percentile=round(float(np.median(pct)), 6),
        mean_baseline_percentile=round(float(np.mean(bpct)), 6),
        n_f2_selected=sum(int(r['f2_selected']) for r in per),
        n_missed_by_F2=sum(int(r['missed_oracle_positive']) for r in per),
        n_ranked_in_F5=sum(int(r['in_F5_optimal_set']) for r in per),
        # does F2 rank msmi-positives better than the baseline count score?
        f2_better_than_baseline_share=round(float(np.mean(
            [fp < bp for fp, bp in zip(pct, bpct)])), 6),
        note=('f2_percentile = competition rank / n_edges within the state, '
              'using the frozen selector F2 score (positive_edge_ranks.csv). '
              'Lower percentile = better rank.'))

    # ---- per-seed consistency --------------------------------------------
    sg = list(csv.DictReader(open(s.OUT / 'seed_group_metrics.csv',
                                  encoding='utf-8')))
    consist = {}
    for st in ORDER:
        vals = [float(r['auc_B_soft_state_%s' % st]) for r in sg
                if r.get('auc_B_soft_state_%s' % st) not in ('', None)]
        consist[st] = dict(
            n_seeds_with_auc=len(vals),
            n_seeds_auc_gt_0_5=sum(1 for v in vals if v > 0.5),
            auc_min=round(float(np.min(vals)), 6) if vals else None,
            auc_max=round(float(np.max(vals)), 6) if vals else None,
            auc_median=round(float(np.median(vals)), 6) if vals else None)

    out = dict(
        per_stage_signal=per_stage,
        positive_edge_rank_summary=pos,
        per_seed_consistency=consist,
        rare_target_sensitivity=json.loads(
            (s.OUT / 'rare_target_sensitivity.json').read_text(
                encoding='utf-8')),
        goal_ranking=json.loads((s.OUT / 'goal_signal.json').read_text(
            encoding='utf-8')),
        interpretation_rules=[
            'delta_B_minus_A isolates the soft-state representation '
            '(incl. relationship_goal) marginal ranking contribution, both '
            'feature sets frozen; CI is a paired seed-group bootstrap.',
            'The timely_second-vs-final_msmi AUC gap is within model-fit '
            'instability (see rare_target_sensitivity); it is NOT read as '
            'signal attenuation.',
            'Findings about intermediate outcomes are separate from final '
            'MSMI; better prediction of mutual/date is not claimed to raise '
            'final MSMI.'])
    (s.OUT / 'ranking_by_stage.json').write_text(
        json.dumps(out, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    s.log('wrote ranking_by_stage.json')
    s.log('ss4_ranking done (%.1fs)' % (time.time() - t0))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
