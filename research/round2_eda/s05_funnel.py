"""S05: outcome funnel - where do introduced pairs die?

Primary source: actual recorded labels (coarse, no model):
  n01_introductions.jsonl (8,433 greedy intros; has missing/no-response counts)
  out_scale800/rows.csv (259,696 intros; label/label_mutual/label_date)
Fine respond-vs-decline split is NOT persisted in either artifact - recorded
as a data gap rather than reconstructed via new simulation.
"""
import csv
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eda_common import PLOTS, TABLES, load_n01_intros, wilson, log, write_csv  # noqa: E402

VARIANTS = ('development', 'sparse', 'cold_start', 'delayed', 'shift', 'drift')
ROOT = Path(__file__).resolve().parents[2]


def mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def funnel_row(stage, n, denom, denom_stage):
    p = n / denom if denom else 0.0
    lo, hi = wilson(n, denom) if denom else (0.0, 0.0)
    return {'stage': stage, 'n': n, 'denominator': denom,
            'denominator_stage': denom_stage,
            'rate_pct': round(100 * p, 3),
            'wilson95_lo_pct': round(100 * lo, 3),
            'wilson95_hi_pct': round(100 * hi, 3)}


def n01_funnel(intros):
    rows = []
    n_assign = len(intros)
    responded = [r for r in intros if r['missing'] == 0]
    n_resp = len(responded)
    mutual = [r for r in intros if r['y_mutual'] == 1]
    dated = [r for r in intros if r['y_date'] == 1]
    second = [r for r in intros if r['y_second'] == 1]
    msmi = [r for r in intros if r['y_msmi'] == 1]
    rows.append(funnel_row('assigned', n_assign, n_assign, '-'))
    rows.append(funnel_row('both_responded', n_resp, n_assign, 'assigned'))
    rows.append(funnel_row('both_accepted_(mutual)', len(mutual), n_resp, 'both_responded'))
    rows.append(funnel_row('date_happened', len(dated), len(mutual), 'mutual'))
    rows.append(funnel_row('second_yes_within_3d', len(second), len(dated), 'date'))
    rows.append(funnel_row('msmi_(date_le_30d)', len(msmi), len(second), 'second'))
    # one-step-from-assigned rates
    rows.append(funnel_row('msmi_from_assigned', len(msmi), n_assign, 'assigned'))
    # no-response structure
    miss1 = sum(1 for r in intros if r['missing'] == 1)
    miss2 = sum(1 for r in intros if r['missing'] >= 2)
    rows.append(funnel_row('exactly_one_no_response', miss1, n_assign, 'assigned'))
    rows.append(funnel_row('both_no_response', miss2, n_assign, 'assigned'))
    # responded but not mutual = declined
    declined = n_resp - len(mutual)
    rows.append(funnel_row('declined_among_responded', declined, n_resp, 'both_responded'))
    return rows


def scale800_funnel():
    path = ROOT / 'research' / 'out_scale800' / 'rows.csv'
    n = mut = dat = msm = 0
    by_variant = defaultdict(lambda: [0, 0, 0, 0])  # n, mutual, date, msmi
    with open(path, newline='', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            n += 1
            m = int(r['label_mutual']); d = int(r['label_date']); y = int(r['label'])
            mut += m; dat += d; msm += y
            v = by_variant[r['variant']]
            v[0] += 1; v[1] += m; v[2] += d; v[3] += y
    rows = [funnel_row('assigned', n, n, '-'),
            funnel_row('mutual', mut, n, 'assigned'),
            funnel_row('date_happened', dat, mut, 'mutual'),
            funnel_row('msmi', msm, dat, 'date'),
            funnel_row('msmi_from_assigned', msm, n, 'assigned')]
    var_rows = []
    for v in VARIANTS:
        n_, m_, d_, y_ = by_variant[v]
        var_rows.append({'variant': v, 'n_intros': n_, 'mutual': m_, 'date': d_, 'msmi': y_,
                         'mutual_pct': round(100 * m_ / n_, 3),
                         'date_given_mutual_pct': round(100 * d_ / m_, 3) if m_ else 0.0,
                         'msmi_given_date_pct': round(100 * y_ / d_, 3) if d_ else 0.0,
                         'msmi_per_100': round(100 * y_ / n_, 3)})
    return rows, var_rows


def main():
    log('S05 funnel start')

    intros = load_n01_intros()
    rows1 = n01_funnel(intros)
    write_csv(TABLES / 'funnel_n01_greedy.csv', rows1)
    log('  n01: ' + ' -> '.join(f"{r['stage']}={r['n']}" for r in rows1[:6]))

    rows2, var_rows = scale800_funnel()
    write_csv(TABLES / 'funnel_scale800.csv', rows2)
    write_csv(TABLES / 'funnel_scale800_by_variant.csv', var_rows)

    # ---- n01 funnel by variant ----
    var_n01 = []
    for v in VARIANTS:
        rs = [r for r in intros if r['variant'] == v]
        n = len(rs)
        resp = sum(1 for r in rs if r['missing'] == 0)
        mut = sum(r['y_mutual'] for r in rs)
        dat = sum(r['y_date'] for r in rs)
        sec = sum(r['y_second'] for r in rs)
        ms = sum(r['y_msmi'] for r in rs)
        var_n01.append({'variant': v, 'n': n,
                        'both_responded_pct': round(100 * resp / n, 2),
                        'mutual_given_responded_pct': round(100 * mut / resp, 2) if resp else 0.0,
                        'date_given_mutual_pct': round(100 * dat / mut, 2) if mut else 0.0,
                        'second_given_date_pct': round(100 * sec / dat, 2) if dat else 0.0,
                        'msmi_given_second_pct': round(100 * ms / sec, 2) if sec else 0.0,
                        'msmi': ms, 'second': sec})
    write_csv(TABLES / 'funnel_n01_by_variant.csv', var_n01)

    # ---- conversion by day band (n01) ----
    def day_band(d):
        return '0-9' if d < 10 else '10-19' if d < 20 else '20-39' if d < 40 else '40+'
    bands = defaultdict(list)
    for r in intros:
        bands[day_band(r['day'])].append(r)
    day_rows = []
    for b in ('0-9', '10-19', '20-39', '40+'):
        rs = bands[b]
        if not rs:
            continue
        n = len(rs)
        mut = sum(r['y_mutual'] for r in rs)
        ms = sum(r['y_msmi'] for r in rs)
        lo, hi = wilson(ms, n)
        day_rows.append({'day_band': b, 'n': n, 'mutual': mut, 'msmi': ms,
                         'mutual_pct': round(100 * mut / n, 3),
                         'msmi_pct': round(100 * ms / n, 4),
                         'msmi_wilson95_pct': f'[{100 * lo:.3f},{100 * hi:.3f}]'})
    write_csv(TABLES / 'funnel_n01_by_day_band.csv', day_rows)

    # ---- conversion by observed soft-field count (n01; soft_match_count not
    # persisted in n01 intros - using soft_obs_min as conservative proxy) ----
    def soft_band(c):
        return '0' if c == 0 else '1-2' if c <= 2 else '3-4' if c <= 4 else '5-6' if c <= 6 else '7'
    sband = defaultdict(list)
    for r in intros:
        sband[soft_band(r['soft_obs_min'])].append(r)
    soft_rows = []
    for b in ('0', '1-2', '3-4', '5+'):
        rs = sband[b]
        if not rs:
            continue
        n = len(rs)
        mut = sum(r['y_mutual'] for r in rs)
        ms = sum(r['y_msmi'] for r in rs)
        lo, hi = wilson(ms, n)
        soft_rows.append({'soft_band': b, 'n': n, 'mutual_pct': round(100 * mut / n, 3),
                          'msmi_pct': round(100 * ms / n, 4),
                          'msmi_wilson95_pct': f'[{100 * lo:.3f},{100 * hi:.3f}]'})
    write_csv(TABLES / 'funnel_n01_by_soft_match.csv', soft_rows)

    # ---- tie structure at chosen score (n01: score_is_max / edges_at_same_score) ----
    ties = sum(1 for r in intros if r['edges_at_same_score'] > 1)
    log(f'  n01 intros chosen at a tied score: {ties}/{len(intros)} '
        f'({100 * ties / len(intros):.1f}%)')
    tie_rows = []
    for flag, label in ((0, 'unique_best'), (1, 'at_tied_score')):
        rs = [r for r in intros if (r['edges_at_same_score'] > 1) == bool(flag)]
        n = len(rs)
        mut = sum(r['y_mutual'] for r in rs)
        ms = sum(r['y_msmi'] for r in rs)
        lo, hi = wilson(ms, n) if n else (0.0, 0.0)
        tie_rows.append({'tie_status': label, 'n': n,
                         'mutual_pct': round(100 * mut / n, 3) if n else 0.0,
                         'msmi_pct': round(100 * ms / n, 4) if n else 0.0,
                         'msmi_wilson95_pct': f'[{100 * lo:.3f},{100 * hi:.3f}]'})
    write_csv(TABLES / 'funnel_n01_by_tie_status.csv', tie_rows)

    # ---- plot: funnel comparison n01 vs scale800 ----
    stages = ['assigned', 'mutual', 'date', 'msmi']
    n01_vals = [8433, 1279, 965, 90]
    s8_vals = [int(r['n']) for r in rows2 if r['stage'] in
               ('assigned', 'mutual', 'date_happened', 'msmi')]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.5))
    for ax, vals, title in ((axes[0], n01_vals, 'n01 greedy (126 worlds)'),
                            (axes[1], s8_vals, 'scale800 (800 worlds, mixed collectors)')):
        xs = range(4)
        ax.bar(xs, [max(v, 0.5) for v in vals], color=['#4c78a8', '#f58518', '#54a24b', '#e45756'])
        ax.set_yscale('log')
        ax.set_xticks(list(xs)); ax.set_xticklabels(stages, rotation=20)
        ax.set_title(f'{title}\nassigned={vals[0]:,} msmi={vals[3]}', fontsize=9)
        ax.set_ylabel('pairs (log)')
        for x, v in zip(xs, vals):
            ax.text(x, max(v, 0.5) * 1.15, f'{v:,}', ha='center', fontsize=8)
    fig.suptitle('Outcome funnel of introduced pairs (actual labels)')
    fig.tight_layout(); fig.savefig(PLOTS / 'funnel_comparison.png', dpi=130); plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4.5))
    names = [r['soft_band'] for r in soft_rows]
    vals = [r['mutual_pct'] for r in soft_rows]
    ax.bar(names, vals, color='#4c78a8')
    ax.set_xlabel('min observed soft fields across the pair (soft_obs_min)')
    ax.set_ylabel('mutual acceptance %')
    ax.set_title('Mutual acceptance by soft-match count (n01, n='
                 + ','.join(str(r['n']) for r in soft_rows) + ')')
    fig.tight_layout(); fig.savefig(PLOTS / 'mutual_by_soft_match.png', dpi=130); plt.close(fig)

    log('S05 done')


if __name__ == '__main__':
    main()
