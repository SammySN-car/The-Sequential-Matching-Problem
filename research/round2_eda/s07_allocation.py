"""S07: allocation effectiveness - opportunity volume vs conversion.

Sources: round2 eval_rows (paired worlds, greedy + 4 ablation arms),
tournament confirm1_rows (30 methods + greedy baseline), n01 intros
(optimal-structure: is greedy's chosen pair the score-max? tie structure).
Paired by (seed, variant). Decomposition: msmi = assignments * p_conv;
Delta_msmi = conv_bar * Delta_n + n_bar * Delta_conv (Kitagawa two-factor).
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eda_common import PLOTS, TABLES, load_n01_intros, mean, log, write_csv  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
VARIANTS = ('development', 'sparse', 'cold_start', 'delayed', 'shift', 'drift')


def load_eval_rows(path):
    rows = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            rows.append(json.loads(line))
    return rows


def paired_decomposition(rows, arm_key, baseline):
    """Per (seed,variant): Delta msmi = volume + conversion effects."""
    idx = {(r['seed'], r['variant'], r[arm_key]): r for r in rows if r.get('valid')}
    keys = sorted({(r['seed'], r['variant']) for r in rows if r.get('valid')})
    arms = sorted({r[arm_key] for r in rows if r.get('valid')})
    out = []
    for arm in arms:
        if arm == baseline:
            continue
        vol, conv, tot = [], [], []
        for k in keys:
            a = idx.get((k[0], k[1], arm)); b = idx.get((k[0], k[1], baseline))
            if not a or not b:
                continue
            na, ma = a['assignments'], a['mutual_second_meeting_intention']
            nb, mb = b['assignments'], b['mutual_second_meeting_intention']
            ca = ma / na if na else 0.0
            cb = mb / nb if nb else 0.0
            nbar = (na + nb) / 2.0
            cbar = (ca + cb) / 2.0
            vol.append(cbar * (na - nb))
            conv.append(nbar * (ca - cb))
            tot.append(ma - mb)
        out.append({
            'arm': arm, 'baseline': baseline, 'n_paired_worlds': len(tot),
            'mean_delta_msmi': round(mean(tot), 5),
            'mean_volume_effect': round(mean(vol), 5),
            'mean_conversion_effect': round(mean(conv), 5),
            'volume_share_of_total': (round(mean(vol) / mean(tot), 3)
                                      if abs(mean(tot)) > 1e-9 else None),
        })
    return out


def arm_summary(rows, arm_key, name):
    """Per-arm aggregate: volume (assignments), conversion (msmi/assign), rate."""
    by_arm = defaultdict(list)
    for r in rows:
        if r.get('valid'):
            by_arm[r[arm_key]].append(r)
    out = []
    for arm, rs in sorted(by_arm.items()):
        n = len(rs)
        asg = sum(r['assignments'] for r in rs)
        msmi = sum(r['mutual_second_meeting_intention'] for r in rs)
        mut = sum(r['mutual_acceptances'] for r in rs)
        arr = sum(r['arrived_members'] for r in rs)
        out.append({'source': name, 'arm': arm, 'n_worlds': n,
                    'assignments_total': asg,
                    'assignments_per_world': round(asg / n, 2),
                    'conversion_pct': round(100 * msmi / asg, 4) if asg else 0.0,
                    'mutual_pct': round(100 * mut / asg, 4) if asg else 0.0,
                    'msmi_per_100_arrived': round(100 * msmi / arr, 4) if arr else 0.0})
    return out


def main():
    log('S07 allocation start')

    # ---- round2 arms (paired seeds 107-118) ----
    r2 = load_eval_rows(ROOT / 'research' / 'round2' / 'results' / 'eval_rows.jsonl')
    write_csv(TABLES / 'alloc_round2_arm_summary.csv', arm_summary(r2, 'arm', 'round2'))
    decomp = paired_decomposition(r2, 'arm', 'greedy')
    write_csv(TABLES / 'alloc_round2_volume_vs_conversion.csv', decomp)
    for d in decomp:
        log(f"  round2 {d['arm']}: dMSMI={d['mean_delta_msmi']:+.4f} "
            f"vol={d['mean_volume_effect']:+.4f} conv={d['mean_conversion_effect']:+.4f}")

    # ---- tournament arms (confirm1) ----
    t1 = load_eval_rows(ROOT / 'research' / 'method_tournament'
                        / 'per_phase' / 'confirm1_rows.jsonl')
    methods = sorted({r['method'] for r in t1})
    log(f'  tournament confirm1 methods: {len(methods)}')
    write_csv(TABLES / 'alloc_tournament_arm_summary.csv',
              arm_summary(t1, 'method', 'tournament_confirm1'))
    # baseline: greedy if present, else best-eligible from final report = m12?
    baseline = 'greedy' if 'greedy' in methods else methods[0]
    if baseline in methods:
        decomp_t = paired_decomposition(t1, 'method', baseline)
        # keep only top methods by |delta| to bound table size
        decomp_t = sorted(decomp_t, key=lambda d: -abs(d['mean_delta_msmi']))[:20]
        write_csv(TABLES / 'alloc_tournament_volume_vs_conversion.csv', decomp_t)

    # ---- optimal-structure of greedy choices (n01) ----
    intros = load_n01_intros()
    n = len(intros)
    always_max = sum(1 for r in intros if r['score_is_max'] == 1)
    deficit_pos = sum(1 for r in intros if r['pair_score_deficit'] > 1e-12)
    tied = sum(1 for r in intros if r['edges_at_same_score'] > 1)
    ranks = defaultdict(int)
    for r in intros:
        ranks[r['pair_rank']] += 1
    struct = [
        {'measure': 'intros_total', 'value': n, 'note': 'n01 greedy'},
        {'measure': 'score_is_max_fraction', 'value': round(always_max / n, 4),
         'note': 'chosen pair attains day max score'},
        {'measure': 'deficit_positive_count', 'value': deficit_pos,
         'note': 'chosen score < day max (expect 0 for greedy)'},
        {'measure': 'tied_at_chosen_score_fraction', 'value': round(tied / n, 4),
         'note': 'edges_at_same_score > 1'},
        {'measure': 'mean_edges_at_chosen_score',
         'value': round(mean([r['edges_at_same_score'] for r in intros]), 3),
         'note': 'competition among co-max-score edges'},
        {'measure': 'pair_rank_modes', 'value': str(dict(sorted(ranks.items())[:5])),
         'note': 'rank of chosen pair within day ordering'},
    ]
    write_csv(TABLES / 'alloc_greedy_optimality_structure.csv', struct)
    log(f"  greedy score_is_max: {always_max}/{n}; tied: {tied}/{n}")

    # ---- coverage vs conversion scatter (round2 arms) ----
    summ = arm_summary(r2, 'arm', 'round2')
    fig, ax = plt.subplots(figsize=(7.5, 5))
    for s in summ:
        ax.scatter(s['assignments_per_world'], s['conversion_pct'], s=80)
        ax.annotate(s['arm'], (s['assignments_per_world'], s['conversion_pct']),
                    textcoords='offset points', xytext=(6, 4), fontsize=9)
    ax.set_xlabel('assignments per world (volume)')
    ax.set_ylabel('MSMI conversion % (per assignment)')
    ax.set_title('Allocation arms: volume vs conversion (round2, 72 worlds/arm)')
    fig.tight_layout(); fig.savefig(PLOTS / 'volume_vs_conversion.png', dpi=130)
    plt.close(fig)

    log('S07 done')


if __name__ == '__main__':
    main()
