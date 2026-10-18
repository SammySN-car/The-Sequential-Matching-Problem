"""S03: feasible-pair graph over time from existing rollout records.

Sources (all pre-existing; no new rollouts):
  - n01_days.jsonl: 7,560 greedy decision days (tournament worlds 143-163)
  - n01_introductions.jsonl: 8,433 assigned intros with decision-state features
  - diag_frozen_seed{107-118}.json: day-level candidate/available counts for
    the frozen promotion arm (72 worlds)
Unique pairs vs (pair, day) opportunities are kept strictly separate.
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eda_common import (PLOTS, TABLES, load_n01_days, load_n01_intros,  # noqa: E402
                        log, write_csv)

VARIANTS = ('development', 'sparse', 'cold_start', 'delayed', 'shift', 'drift')


def main():
    log('S03 graph-over-time analysis start')
    days = load_n01_days()
    intros = load_n01_intros()
    log(f'  n01_days {len(days)} rows; n01_intros {len(intros)} rows')

    # ---- per (variant, day) aggregates ----
    agg = defaultdict(lambda: {'n': 0, 'n_available': [], 'edges': [], 'zero': 0,
                               'unmatched': 0, 'n_pairs': [], 'ask': []})
    for r in days:
        a = agg[(r['variant'], r['day'])]
        a['n'] += 1
        a['n_available'].append(r['n_available'])
        a['edges'].append(r['edges_total'])
        a['zero'] += r['zero_selection']
        a['unmatched'] += r['unmatched_despite_edges']
        a['n_pairs'].append(r['n_pairs'])
        a['ask'].append(r['ask_spend_today'])

    def mean(xs):
        return sum(xs) / len(xs) if xs else 0.0

    graph_rows = []
    for (v, d), a in sorted(agg.items()):
        graph_rows.append({
            'variant': v, 'day': d, 'n_worlds': a['n'],
            'mean_available': round(mean(a['n_available']), 2),
            'mean_feasible_edges': round(mean(a['edges']), 3),
            'pct_zero_selection': round(100 * a['zero'] / a['n'], 2),
            'pct_unmatched_despite_edges': round(100 * a['unmatched'] / a['n'], 2),
            'mean_selected_pairs': round(mean(a['n_pairs']), 3),
            'mean_ask_spend': round(mean(a['ask']), 2),
        })
    write_csv(TABLES / 'graph_by_variant_day.csv', graph_rows)

    # ---- variant-level summary over days 0-59 ----
    var_rows = []
    for v in VARIANTS:
        rs = [r for r in graph_rows if r['variant'] == v]
        zero_days = [r for r in agg_rows_zero(agg, v)]
        var_rows.append({
            'variant': v,
            'mean_available_all_days': round(mean([r['mean_available'] for r in rs]), 1),
            'mean_feasible_edges_all_days': round(mean([r['mean_feasible_edges'] for r in rs]), 3),
            'mean_feasible_edges_when_any': round(mean_edges_when_any(agg, v), 3),
            'pct_days_zero_selection': round(mean([r['pct_zero_selection'] for r in rs]), 2),
            'pct_days_unmatched_despite_edges': round(
                mean([r['pct_unmatched_despite_edges'] for r in rs]), 2),
            'mean_selected_per_day': round(mean([r['mean_selected_pairs'] for r in rs]), 3),
        })
    write_csv(TABLES / 'graph_variant_summary.csv', var_rows)

    # ---- unique pairs vs (pair,day) opportunities ----
    intro_pairs = {(r['seed'], r['variant'], tuple(sorted((r['user_a'], r['user_b']))))
                   for r in intros}
    pair_day = {(r['seed'], r['variant'], r['assigned_day'],
                 tuple(sorted((r['user_a'], r['user_b'])))) for r in intros}
    total_edge_days = sum(r['edges_total'] for r in days)
    total_selected_days = sum(r['n_pairs'] for r in days)
    uniq_rows = [{
        'measure': 'unique_feasible_pairs_assigned',
        'value': len(intro_pairs),
        'note': 'distinct (world, unordered pair) ever introduced'},
        {'measure': 'pair_day_opportunities_assigned',
         'value': len(pair_day), 'note': 'distinct (world, day, pair) introductions'},
        {'measure': 'sum_daily_feasible_edges',
         'value': total_edge_days,
         'note': 'sum of edges_total over decision days: (day, edge) opportunities, '
                 'NOT unique pairs'},
        {'measure': 'sum_daily_selected_pairs',
         'value': total_selected_days, 'note': 'equals intro rows'},
    ]
    write_csv(TABLES / 'unique_pairs_vs_pairdays.csv', uniq_rows)

    # ---- degree / isolation at introduction time (n01 features) ----
    deg_rows = []
    for v in VARIANTS:
        rs = [r for r in intros if r['variant'] == v]
        if not rs:
            continue
        deg_max = sorted(r['degree_max'] for r in rs)
        deg_min = sorted(r['degree_min'] for r in rs)
        n = len(rs)
        deg_rows.append({
            'variant': v, 'intros': n,
            'degree_max_p50': deg_max[n // 2], 'degree_max_p90': deg_max[9 * n // 10],
            'degree_min_p50': deg_min[n // 2], 'degree_min_p90': deg_min[9 * n // 10],
            'pct_degree_min_le1': round(100 * sum(1 for x in deg_min if x <= 1) / n, 2),
            'pct_degree_max_le2': round(100 * sum(1 for x in deg_max if x <= 2) / n, 2),
            'edges_total_p50': sorted(r['edges_total'] for r in rs)[n // 2],
            'edges_total_mean': round(sum(r['edges_total'] for r in rs) / n, 3),
        })
    write_csv(TABLES / 'degree_at_introduction.csv', deg_rows)

    # ---- promotion diag: candidate counts (frozen arm, seeds 107-118) ----
    diag_dir = Path(__file__).resolve().parents[2] / 'research' / 'round2_promotion_fresh_seeds'
    promo_rows = []
    for seed in range(107, 119):
        p = diag_dir / f'diag_frozen_seed{seed}.json'
        if not p.exists():
            continue
        d = json.loads(p.read_text(encoding='utf-8'))
        for v in VARIANTS:
            ep = d['episodes'].get(v)
            if not ep:
                continue
            avail, cand, zeros = [], [], 0
            for dayrec in ep['days']:
                m = dayrec.get('match', {})
                if 'n_members_available' in m:
                    avail.append(m['n_members_available'])
                if 'n_cand' in m:
                    cand.append(m['n_cand'])
                if m.get('category') == 'zero_selection':
                    zeros += 1
            promo_rows.append({
                'seed': seed, 'variant': v, 'days': len(ep['days']),
                'mean_available': round(sum(avail) / len(avail), 1) if avail else None,
                'mean_candidates': round(sum(cand) / len(cand), 2) if cand else None,
                'zero_selection_days': zeros,
            })
    write_csv(TABLES / 'promotion_day_candidate_counts.csv', promo_rows)

    # ---- plots ----
    fig, axes = plt.subplots(2, 3, figsize=(13, 7), sharex=True)
    for ax, v in zip(axes.flat, VARIANTS):
        rs = [r for r in graph_rows if r['variant'] == v]
        ax.plot([r['day'] for r in rs], [r['mean_feasible_edges'] for r in rs],
                label='feasible edges', color='#2b7bba')
        ax.plot([r['day'] for r in rs], [r['mean_selected_pairs'] for r in rs],
                label='selected pairs', color='#c0504d')
        ax2 = ax.twinx()
        ax2.plot([r['day'] for r in rs], [r['pct_zero_selection'] for r in rs],
                 color='#999999', linewidth=0.8, label='% zero-select')
        ax2.set_ylim(0, 100)
        ax.set_title(v)
        ax.set_xlabel('decision day')
    axes.flat[0].legend(fontsize=8)
    axes.flat[1].legend(fontsize=8)
    fig.suptitle('Feasible edges vs selections vs zero-selection days (greedy, 126 tournament worlds)')
    fig.tight_layout()
    fig.savefig(PLOTS / 'graph_edges_by_day.png', dpi=130)
    plt.close(fig)

    log('S03 done')


def agg_rows_zero(agg, v):
    out = []
    for (vv, d), a in sorted(agg.items()):
        if vv == v:
            out.append(100 * a['zero'] / a['n'])
    return out


def mean_edges_when_any(agg, v):
    vals = []
    for (vv, d), a in agg.items():
        if vv != v:
            continue
        # reconstruct conditional mean: edges list has one entry per world-day
        vals.extend(a['edges'])
    nonzero = [x for x in vals if x > 0]
    return sum(nonzero) / len(nonzero) if nonzero else 0.0


if __name__ == '__main__':
    main()
