"""Section 5: predictive-to-decision gap metrics with seed-group inference.

21 seed groups; all six variants of a seed stay together. Nonparametric
bootstrap over seed groups, B=2000, rng seed 4242, percentile 95% interval,
plus positive/tied/negative seed counts. The 7,560 day rows are NEVER treated
as independent observations.
"""
import json, sys, time
from collections import defaultdict
from pathlib import Path
import numpy as np
from sklearn.metrics import roc_auc_score

HERE = Path(__file__).resolve().parent
MO = HERE.parent
CEIL = HERE.parent.parent / 'round2_decision_ceiling'
sys.path.insert(0, str(CEIL / 'scripts'))
import ce_common as c  # noqa: E402

B, SEED = 2000, 4242


def main():
    t0 = time.time(); c.log('mo_stats start')
    diag = [json.loads(l) for l in open(MO / 'selection_diagnostics.jsonl', encoding='utf-8')]
    score2, y, grp, st = [], [], [], []
    for line in open(CEIL / 'oof_scores.jsonl', encoding='utf-8'):
        r = json.loads(line)
        score2.append(float(r['F2_soft_state'])); y.append(int(bool(r['y'])))
        grp.append(r['seed']); st.append((r['seed'], r['variant'], r['day']))

    global_auc = float(roc_auc_score(y, score2))
    # within-state AUC: states whose edge set has both classes
    by_st = defaultdict(list)
    for s, yy, ss in zip(score2, y, st):
        by_st[ss].append((s, yy))
    ws, n_ws = [], 0
    for ss, pairs in by_st.items():
        lab = [p[1] for p in pairs]
        if 0 in lab and 1 in lab:
            ws.append(float(roc_auc_score(lab, [p[0] for p in pairs]))); n_ws += 1
    within_auc = float(np.mean(ws))

    sum_k = sum(d['k_t'] for d in diag)
    sum_p = sum(d['p_t'] for d in diag)
    sum_P2 = sum(d['P_F2'] for d in diag)
    sum_P5 = sum(d['P_F5'] for d in diag)
    sum_PG = sum(d['P_GREEDY'] for d in diag)
    sum_P1 = sum(d['P_F1'] for d in diag)

    # ---- per-seed aggregates (the unit of inference) ---------------------
    per = defaultdict(lambda: defaultdict(int))
    for d in diag:
        s = d['seed']
        for key in ('k_t', 'p_t', 'P_GREEDY', 'P_F1', 'P_F2', 'P_F5',
                    'R_t', 'U_t', 'gap_F5_F2', 'ranking_component',
                    'conflict_component', 'irreducible_matching_cost'):
            per[s][key] += d[key]
    seeds = sorted(per)
    print('seeds:', len(seeds))

    def boot(key):
        v = np.array([per[s][key] for s in seeds], dtype=float)
        rng = np.random.default_rng(SEED)
        idx = rng.integers(0, len(v), size=(B, len(v)))
        bs = v[idx].mean(axis=1)
        return dict(mean=float(v.mean()),
                    ci95=[float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))],
                    seed_values=[int(x) for x in v])

    stats = dict(
        n_states=len(diag), n_seed_groups=len(seeds),
        denominators=dict(sum_k_t=sum_k, sum_p_t=sum_p,
                          sum_positives_in_F2=sum_P2, sum_positives_in_F5=sum_P5),
        global_auc_F2=global_auc,
        within_state_auc=dict(mean=within_auc, n_states=n_ws),
        pooled_recall_at_kt=sum_P2 / sum_p,
        pooled_precision_of_F2=sum_P2 / sum_k,
        capture=dict(GREEDY=sum_PG, F1=sum_P1, F2=sum_P2, F5=sum_P5),
        F2_minus_GREEDY_total=sum_P2 - sum_PG,
        regret_F5_minus_F2_total=sum_P5 - sum_P2,
        decomposition=dict(
            ranking_component_total=sum(d['ranking_component'] for d in diag),
            conflict_component_total=sum(d['conflict_component'] for d in diag),
            irreducible_matching_cost_total=sum(d['irreducible_matching_cost'] for d in diag),
            ranking_share_of_gap=None, conflict_share_of_gap=None),
        bootstrap_seed_groups=dict(
            B=B, rng_seed=SEED, unit='seed group (all 6 variants kept together)',
            regret_F5_minus_F2=boot('gap_F5_F2'),
            ranking_component=boot('ranking_component'),
            conflict_component=boot('conflict_component'),
            F2_minus_GREEDY=boot('P_F2') if False else None))
    # F2-GREEDY needs its own series
    per2 = defaultdict(int)
    for d in diag:
        per2[d['seed']] += d['P_F2'] - d['P_GREEDY']
    v = np.array([per2[s] for s in seeds], dtype=float)
    rng = np.random.default_rng(SEED)
    bs = v[rng.integers(0, len(v), size=(B, len(v)))].mean(axis=1)
    stats['bootstrap_seed_groups']['F2_minus_GREEDY'] = dict(
        mean=float(v.mean()), ci95=[float(np.percentile(bs, 2.5)),
                                     float(np.percentile(bs, 97.5))],
        seed_values=[int(x) for x in v])

    rc = stats['decomposition']
    rc['ranking_share_of_gap'] = rc['ranking_component_total'] / (sum_P5 - sum_P2)
    rc['conflict_share_of_gap'] = rc['conflict_component_total'] / (sum_P5 - sum_P2)

    # per-seed CSV
    rows = []
    for s in seeds:
        r = dict(seed=s); r.update({k: int(v) for k, v in per[s].items()})
        r['F2_minus_GREEDY'] = int(per2[s])
        rows.append(r)
    c.write_jsonl(MO / 'per_seed_results.jsonl', rows)
    import csv as _csv
    with open(MO / 'per_seed_results.csv', 'w', newline='', encoding='utf-8') as fh:
        w = _csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

    (MO / 'statistics.json').write_text(json.dumps(stats, indent=1, sort_keys=True) + '\n',
                                        encoding='utf-8')
    print(json.dumps({k: v for k, v in stats.items()
                      if k not in ('bootstrap_seed_groups',)}, indent=1, sort_keys=True))
    print('bootstrap regret:', stats['bootstrap_seed_groups']['regret_F5_minus_F2']['ci95'])
    print('bootstrap F2-GREEDY:', stats['bootstrap_seed_groups']['F2_minus_GREEDY']['ci95'])
    c.log('mo_stats done (%.1fs)' % (time.time() - t0))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
