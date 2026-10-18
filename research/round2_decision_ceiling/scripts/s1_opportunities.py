"""Section 3: how many genuine decision opportunities exist.

Replays the 126 frozen worlds (no new worlds, no new seeds), persists every
per-day candidate graph, computes C1-C5 structural metrics, and reconciles
against the frozen n01 aggregates before writing opportunity_summary.csv.
"""
import csv, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ce_common as c  # noqa: E402

DAY_BANDS = ((0, 9, '0-9'), (10, 19, '10-19'), (20, 39, '20-39'), (40, 59, '40-59'))
DENSITY = ((1, 1, '1'), (2, 4, '2-4'), (5, 9, '5-9'), (10, 10 ** 9, '10+'))


def band(v, table):
    for lo, hi, name in table:
        if lo <= v <= hi:
            return name
    return '0'


METRIC_COLS = [
    'edges_total', 'n_pairs', 'n_available', 'n_arrived',
    'n_members_with_degree_ge1', 'n_members_degree_ge2', 'degree_max',
    'competing_edges_mean', 'selected_with_alt_partner',
    'selected_with_alt_partner_share', 'n_matchings_capped',
    'n_matchings_gt_cap', 'enum_failed', 'batch_size', 'max_matching_size',
    'batch_underfill', 'alt_same_size', 'alt_same_size_same_endpoints',
    'alt_same_size_diff_endpoints', 'alt_same_size_unknown',
    'alt_repair_same_endpoints', 'addition_possible',
    'cardinality_preserving_replacement', 'n_intros_so_far', 'n_feedback',
    'ask_budget']


def main():
    c.log('task3 start: section 3 reconstruction')
    frozen_days = c.read_jsonl(c.FROZEN_DAYS)
    frozen_by_key = {(r['seed'], r['variant'], r['day']): r for r in frozen_days}
    day_rows = []
    for seed, variant in c.world_list():
        def per_day(ctx, _s=seed, _v=variant):
            keys = [tuple(k) for _, k in sorted(ctx['edges'])]
            metrics = c.day_structural_metrics(ctx['edges'], ctx['pairs'], keys)
            metrics.update(
                n_available=sum(1 for m in ctx['state']['members']
                                if m['available']),
                n_arrived=len(ctx['state']['members']),
                n_intros_so_far=ctx['n_intros'],
                n_feedback=ctx['n_feedback'],
                ask_budget=ctx['state']['ask_budget_remaining'])
            day_rows.append(dict(seed=_s, variant=_v, day=ctx['day'],
                                 edges=[[-e[0], list(e[1])] for e in ctx['edges']],
                                 pairs=[list(p) for p in ctx['pairs']],
                                 metrics=metrics, day_ctx=ctx['day_ctx']))
        c.replay_world(seed, variant, per_day=per_day, follow_up=False)
    c.write_jsonl(c.OUT / 'day_edges.jsonl', [
        dict(seed=r['seed'], variant=r['variant'], day=r['day'],
             edges=r['edges'], pairs=r['pairs'], metrics=r['metrics'],
             day_ctx=r['day_ctx']) for r in day_rows])

    rec = dict(
        n_days=len(day_rows), n_days_frozen=len(frozen_days),
        sum_edges_total=sum(r['metrics']['edges_total'] for r in day_rows),
        sum_n_pairs=sum(r['metrics']['n_pairs'] for r in day_rows),
        n_zero=sum(1 for r in day_rows if r['metrics']['n_pairs'] == 0),
        n_pairs_ge2=sum(1 for r in day_rows if r['metrics']['n_pairs'] >= 2),
        sum_edges_frozen=sum(r['edges_total'] for r in frozen_days),
        sum_n_pairs_frozen=sum(r['n_pairs'] for r in frozen_days),
        n_zero_frozen=sum(1 for r in frozen_days if r['n_pairs'] == 0),
        n_pairs_ge2_frozen=sum(1 for r in frozen_days if r['n_pairs'] >= 2),
        per_day_edge_mismatch=0, per_day_pair_mismatch=0,
        max_edges_per_day=max((r['metrics']['edges_total'] for r in day_rows),
                              default=0))
    for r in day_rows:
        f = frozen_by_key.get((r['seed'], r['variant'], r['day']))
        if f is None:
            rec['per_day_edge_mismatch'] += 1
            continue
        if f['edges_total'] != r['metrics']['edges_total']:
            rec['per_day_edge_mismatch'] += 1
        if f['n_pairs'] != r['metrics']['n_pairs']:
            rec['per_day_pair_mismatch'] += 1
    rec['reconciled'] = bool(
        rec['n_days'] == 7560 and rec['sum_edges_total'] == 15304
        and rec['sum_n_pairs'] == 8433 and rec['n_zero'] == 3566
        and rec['n_pairs_ge2'] == 2087
        and rec['per_day_edge_mismatch'] == 0
        and rec['per_day_pair_mismatch'] == 0)
    (c.OUT / 'reconciliation.json').write_text(
        json.dumps(rec, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    c.log('reconciliation ' + json.dumps(rec, sort_keys=True))
    if not rec['reconciled']:
        raise SystemExit('RECONCILIATION FAILED - section 3 output withheld')

    strata = [('overall', 'all', day_rows)]
    for v in sorted({r['variant'] for r in day_rows}):
        strata.append(('variant', v, [r for r in day_rows if r['variant'] == v]))
    for s in sorted({r['seed'] for r in day_rows}):
        strata.append(('world', str(s), [r for r in day_rows if r['seed'] == s]))
    for _, _, name in DAY_BANDS:
        strata.append(('day_band', name,
                       [r for r in day_rows if band(r['day'], DAY_BANDS) == name]))
    for _, _, name in DENSITY:
        strata.append(('density_band', name,
                       [r for r in day_rows
                        if band(r['metrics']['edges_total'], DENSITY) == name]))

    rows = []
    for stype, sval, subset in strata:
        n = len(subset)
        row = dict(stratum_type=stype, stratum_value=sval, n_days=n)
        for col in METRIC_COLS:
            vals = [r['metrics'][col] for r in subset]
            row[col + '_mean'] = round(sum(vals) / n, 6) if n else ''
        row['sum_edges_total'] = sum(r['metrics']['edges_total'] for r in subset)
        row['sum_n_pairs'] = sum(r['metrics']['n_pairs'] for r in subset)
        for lo, hi, name in ((0, 0, '0'), (1, 1, '1'), (2, 4, '2_4'),
                             (5, 9, '5_9'), (10, 10 ** 9, '10p')):
            row['n_days_edges' + name] = sum(
                1 for r in subset if lo <= r['metrics']['edges_total'] <= hi)
        row['n_days_alt_same_size'] = sum(
            1 for r in subset if r['metrics']['alt_same_size'])
        row['n_days_alt_same_size_unknown'] = sum(
            1 for r in subset if r['metrics']['alt_same_size_unknown'])
        rows.append(row)
    cols = sorted({k for r in rows for k in r})
    with open(c.OUT / 'opportunity_summary.csv', 'w', newline='',
              encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    c.log('wrote opportunity_summary.csv (%d strata rows)' % len(rows))
    c.log('task3 done')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
