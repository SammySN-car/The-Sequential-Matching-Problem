"""S04: clarification (ask) effectiveness from existing logs.

Sources: n01_days.jsonl (ask spend by day, greedy), n01_introductions.jsonl
(soft-unknown/declined features at intro time), promotion diag day records
(ask cost/n_asks), stage-1.5 probe summary (base vs soft ask costs),
e3 mechanism summary (VoI-gated REL asks), population tables (declined rates).
No new episodes.
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eda_common import PLOTS, TABLES, load_n01_days, load_n01_intros, log, write_csv  # noqa: E402

VARIANTS = ('development', 'sparse', 'cold_start', 'delayed', 'shift', 'drift')
ROOT = Path(__file__).resolve().parents[2]


def mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def main():
    log('S04 clarification analysis start')
    days = load_n01_days()
    intros = load_n01_intros()

    # ---- ask spend by day (budget = 12/day; hard bundle = 3; soft = 1) ----
    by_day = defaultdict(list)
    for r in days:
        by_day[r['day']].append(r['ask_spend_today'])
    spend_rows = []
    cum = 0.0
    for d in range(60):
        xs = by_day[d]
        m = mean(xs)
        cum += m
        spend_rows.append({'day': d, 'mean_spend': round(m, 2),
                           'pct_worlds_spend_gt0': round(100 * sum(1 for x in xs if x > 0) / len(xs), 1),
                           'cumulative_mean_spend': round(cum, 1)})
    write_csv(TABLES / 'ask_spend_by_day.csv', spend_rows)

    # ---- soft unknown / declined remaining at introduction time ----
    soft_rows = []
    for v in VARIANTS + ('ALL',):
        rs = intros if v == 'ALL' else [r for r in intros if r['variant'] == v]
        if not rs:
            continue
        soft_rows.append({
            'variant': v, 'intros': len(rs),
            'soft_unknown_max_mean': round(mean([r['soft_unknown_max'] for r in rs]), 3),
            'soft_declined_max_mean': round(mean([r['soft_declined_max'] for r in rs]), 3),
            'soft_obs_min_mean': round(mean([r['soft_obs_min'] for r in rs]), 3),
            'soft_obs_max_mean': round(mean([r['soft_obs_max'] for r in rs]), 3),
            'pct_soft_obs_min_zero': round(100 * sum(1 for r in rs if r['soft_obs_min'] == 0) / len(rs), 2),
        })
    write_csv(TABLES / 'soft_state_at_introduction.csv', soft_rows)

    # ---- hard-missing at intro time (should be 0: feasibility requires observed) ----
    n_missing = sum(1 for r in intros if r.get('soft_unknown_max', 0) is None)
    zero_soft_both = sum(1 for r in intros if r['soft_obs_min'] == 0)
    log(f'  intros with both members at 0 observed soft fields: {zero_soft_both}/{len(intros)} '
        f'({100 * zero_soft_both / len(intros):.1f}%)')

    # ---- promotion diag ask telemetry ----
    diag_dir = ROOT / 'research' / 'round2_promotion_fresh_seeds'
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
            costs = [dayrec['ask']['cost'] for dayrec in ep['days'] if 'ask' in dayrec]
            nasks = [dayrec['ask']['n_asks'] for dayrec in ep['days'] if 'ask' in dayrec]
            promo_rows.append({'seed': seed, 'variant': v,
                               'ask_cost_total': sum(costs),
                               'ask_days_active': sum(1 for c in costs if c > 0),
                               'mean_asks_per_active_day': round(
                                   mean([n for c, n in zip(costs, nasks) if c > 0]), 2)})
    write_csv(TABLES / 'promotion_ask_telemetry.csv', promo_rows)

    # ---- stage-1.5 probe: base (hard-only) vs AC+soft ask costs ----
    probe = json.loads((ROOT / 'research' / 'round2_stage1_5' / 'probe_seed101_run1.json')
                       .read_text(encoding='utf-8'))
    ov = probe['overall']
    probe_rows = [
        {'measure': 'ask_cost_baseline_hard_only', 'value': ov['ask_cost_base_counterfactual'],
         'source': 'probe_seed101 (6 variants, A+C floor policy context)'},
        {'measure': 'ask_cost_ac_total', 'value': ov['ask_cost_ac'], 'source': 'same'},
        {'measure': 'ask_cost_ac_soft_only', 'value': ov['ask_cost_ac_soft'], 'source': 'same'},
        {'measure': 'ask_overlap_members_hard', 'value': ov['ask_overlap_members'], 'source': 'same'},
    ]
    write_csv(TABLES / 'probe_ask_costs.csv', probe_rows)

    # ---- E1/E2/E3 mechanism (REL VoI asks) ----
    e3_dir = ROOT / 'research' / 'e3_rel_experiment' / 'per_arm'
    e3_rows = []
    for arm, fname in (('C', 'C_mechanism.json'), ('E1', 'E1_mechanism.json'),
                       ('E2', 'E2_mechanism.json'), ('E3', 'E3_mechanism.json')):
        p = e3_dir / fname
        if not p.exists():
            continue
        doc = json.loads(p.read_text(encoding='utf-8'))
        # mechanism files store per-episode aggregates; use summary if present
        summary = doc.get('summary', {})
        e3_rows.append({'arm': arm,
                        'scenario_means_present': bool(summary.get('scenario_means')),
                        'source_file': fname})
    # richer numbers are already in report.md; record the headline facts here
    e3_headline = [
        {'arm': 'C/E2', 'rel_asks_per_episode': 0, ' voi_gate_precision': None,
         'note': 'no REL asks (control and scorer-only arms)'},
        {'arm': 'E1', 'rel_asks_per_episode': 42.3,
         'note': 'VoI gate: 76.6% of REL-ask days changed the allocation; '
                 '87.6% of asks on changed days (report.md section 3)'},
        {'arm': 'E3', 'rel_asks_per_episode': 42.8,
         'note': '67.7% allocation-change days; 18.5% edge scores changed'},
    ]
    write_csv(TABLES / 'e3_rel_ask_headline.csv', e3_headline)

    # ---- does more information create more feasible edges? (edges vs cumulative asks) ----
    # Within n01 worlds: correlate day-level edges_total with cumulative ask spend
    # (descriptive association only; arrivals confound, documented in report).
    by_world = defaultdict(list)
    for r in days:
        by_world[(r['seed'], r['variant'])].append(r)
    xs, ys = [], []
    for key, rs in by_world.items():
        rs = sorted(rs, key=lambda r: r['day'])
        cum_ask = 0
        for r in rs:
            cum_ask += r['ask_spend_today']
            if r['day'] >= 1:
                xs.append(cum_ask)
                ys.append(r['edges_total'])
    # simple binned means
    bins = defaultdict(list)
    for x, y in zip(xs, ys):
        bins[min(int(x // 24) * 24, 216)].append(y)
    edge_ask_rows = [{'cum_ask_bin_start': b, 'n_days': len(v),
                      'mean_feasible_edges': round(mean(v), 3)}
                     for b, v in sorted(bins.items())]
    write_csv(TABLES / 'edges_vs_cumulative_ask.csv', edge_ask_rows)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot([r['day'] for r in spend_rows], [r['mean_spend'] for r in spend_rows],
            color='#2b7bba')
    ax.axhline(12, color='#999999', linestyle='--', linewidth=0.8, label='daily budget 12')
    ax.set_xlabel('decision day'); ax.set_ylabel('mean ask units spent')
    ax.set_title('Ask spend by day (greedy baseline, 126 tournament worlds)')
    ax.legend()
    fig.tight_layout(); fig.savefig(PLOTS / 'ask_spend_by_day.png', dpi=130); plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot([r['cum_ask_bin_start'] for r in edge_ask_rows],
            [r['mean_feasible_edges'] for r in edge_ask_rows], marker='o')
    ax.set_xlabel('cumulative ask units spent in world (binned)')
    ax.set_ylabel('mean feasible edges that day')
    ax.set_title('Feasible edges vs cumulative ask spend (descriptive; arrivals confound)')
    fig.tight_layout(); fig.savefig(PLOTS / 'edges_vs_asks.png', dpi=130); plt.close(fig)

    log('S04 done')


if __name__ == '__main__':
    main()
