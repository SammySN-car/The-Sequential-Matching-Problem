"""Section 6: local (one-day, myopic, hindsight) MSMI oracle headroom.

NEVER a sequential policy oracle and NEVER summed across days (analysis_plan.md
sec.6.1). Every reported figure is per-day. Uses label information the policy
never had at decision time - which is exactly what makes it a ceiling.
"""
import csv, json, random, sys
from collections import defaultdict
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


def oracle_positive_edges(keys, labels):
    """Edges whose counterfactual label says MSMI would have happened."""
    return [k for k, lab in zip(keys, labels) if lab == 1]


def solve_local_oracle(keys, labels):
    """Exact max number of vertex-disjoint counterfactual MSMI positives.

    Returns (local_oracle_positives, enum_failed). cap=10**9 so matchings are
    enumerated rather than truncated; a node_limit breach sets enum_failed and
    the value is then taken from the exact max_matching_size search, with the
    breach reported via the day's enum_failed flag.
    """
    pos = oracle_positive_edges(keys, labels)
    if not pos:
        return 0, False
    matchings, failed = c.enumerate_matchings(pos, cap=10 ** 9,
                                              node_limit=4_000_000)
    if failed:
        return c.max_matching_size(pos), True
    return max(len(m) for m in matchings), False


def brute_force_max(keys):
    """Exhaustive 2^n reference for small edge sets (n <= 16)."""
    n = len(keys)
    best = 0
    for mask in range(1 << n):
        used, ok, cnt = set(), True, 0
        for i in range(n):
            if mask >> i & 1:
                if set(keys[i]) & used:
                    ok = False
                    break
                used |= set(keys[i]); cnt += 1
        if ok:
            best = max(best, cnt)
    return best


def main():
    c.log('task6 start: local oracle')
    if 'V1_selected_pair_agreement' not in open(
            c.OUT / 'counterfactual_validation.csv', encoding='utf-8').read():
        raise SystemExit('counterfactual validation absent - refusing')
    labels = defaultdict(dict)
    with open(c.OUT / 'counterfactual_pairs.jsonl', encoding='utf-8') as fh:
        for line in fh:
            r = json.loads(line)
            labels[(r['seed'], r['variant'], r['day'])][(r['user_a'], r['user_b'])] = \
                int(bool(r['cf_y_msmi']))

    day_rows, solver_checks, n_failed = [], [], 0
    for line in open(c.OUT / 'day_edges.jsonl', encoding='utf-8'):
        d = json.loads(line)
        key = (d['seed'], d['variant'], d['day'])
        lab = labels.get(key, {})
        keys = [tuple(e[1]) for e in d['edges']]
        y = [lab.get(tuple(e[1])) for e in d['edges']]
        if any(v is None for v in y):
            raise SystemExit('missing cf label for %s' % (key,))
        pairs = [tuple(p) for p in d['pairs']]

        local_or, failed = solve_local_oracle(keys, y)
        if failed:
            n_failed += 1
        collector = sum(lab.get(p, 0) for p in pairs)
        full_max = c.max_matching_size(keys)
        # maxcard reference arm: label-free, exact, independent networkx blossom
        maxcard = full_max
        try:
            import networkx as nx
            g = nx.Graph()
            for neg, k in sorted(d['edges']):
                g.add_edge(k[0], k[1], weight=-neg)
            if g.number_of_edges():
                maxcard = len(nx.max_weight_matching(g, maxcardinality=True))
        except ImportError:
            pass
        if maxcard != full_max:
            raise SystemExit('solver disagreement on %s: nx=%d mine=%d'
                             % (key, maxcard, full_max))
        if len(keys) <= 16:
            solver_checks.append(dict(key=str(key),
                                      mine=c.max_matching_size(keys),
                                      brute=brute_force_max(keys)))
        gap = local_or - collector
        if gap < 0:
            raise SystemExit('negative local_gap on %s' % (key,))
        day_rows.append(dict(
            seed=d['seed'], variant=d['variant'], day=d['day'],
            day_band=band(d['day'], DAY_BANDS),
            density_band=band(len(keys), DENSITY),
            n_edges=len(keys), batch_size=len(pairs),
            max_matching_size=full_max,
            collector_positives=collector, maxcard_positives=maxcard,
            local_oracle_positives=local_or, local_gap=gap,
            rel_gap=(round(gap / local_or, 6) if local_or >= 1 else None),
            enum_failed=int(failed)))

    ok = all(s['mine'] == s['brute'] for s in solver_checks)
    (c.OUT / 'oracle_solver_check.json').write_text(json.dumps(dict(
        n_bruteforce_checked=len(solver_checks),
        n_bruteforce_disagree=sum(1 for s in solver_checks
                                  if s['mine'] != s['brute']),
        passed=bool(ok), n_enum_failed=n_failed), indent=1) + '\n',
        encoding='utf-8')
    if not ok:
        raise SystemExit('ORACLE SOLVER DISAGREES WITH BRUTE FORCE')
    c.write_jsonl(c.OUT / 'oracle_by_day.jsonl', day_rows)

    # --- three arms reported separately; daily gaps never summed
    strata = [('overall', 'all', day_rows)]
    for v in sorted({r['variant'] for r in day_rows}):
        strata.append(('variant', v, [r for r in day_rows if r['variant'] == v]))
    for s in sorted({r['seed'] for r in day_rows}):
        strata.append(('world', str(s), [r for r in day_rows if r['seed'] == s]))
    for _, _, name in DAY_BANDS:
        strata.append(('day_band', name,
                       [r for r in day_rows if r['day_band'] == name]))
    for _, _, name in DENSITY:
        strata.append(('density_band', name,
                       [r for r in day_rows if r['density_band'] == name]))

    rows = []
    for stype, sval, sub in strata:
        n = len(sub)
        gaps = sorted(r['local_gap'] for r in sub)
        ge1 = [r for r in sub if r['local_gap'] >= 1]
        oracle_pos = [r for r in sub if r['local_oracle_positives'] >= 1]
        rel = [r['rel_gap'] for r in oracle_pos if r['rel_gap'] is not None]
        rows.append(dict(
            stratum_type=stype, stratum_value=sval, n_days=n,
            n_days_oracle_pos_ge1=len(oracle_pos),
            n_days_gap_ge1=len(ge1),
            share_gap_ge1_among_oracle_pos=(
                round(len(ge1) / len(oracle_pos), 6) if oracle_pos else ''),
            mean_local_gap=round(sum(gaps) / n, 6) if n else '',
            median_local_gap=round(gaps[n // 2], 6) if n else '',
            p90_local_gap=round(gaps[int(0.9 * (n - 1))], 6) if n else '',
            mean_collector_positives=round(
                sum(r['collector_positives'] for r in sub) / n, 6) if n else '',
            mean_oracle_positives=round(
                sum(r['local_oracle_positives'] for r in sub) / n, 6) if n else '',
            mean_maxcard_positives=round(
                sum(r['maxcard_positives'] for r in sub) / n, 6) if n else '',
            rel_gap_mean=(round(sum(rel) / len(rel), 6) if rel else ''),
            n_enum_failed=sum(r['enum_failed'] for r in sub),
            share_days_positive_headroom=round(len(ge1) / n, 6) if n else ''))
    with open(c.OUT / 'local_oracle_headroom.csv', 'w', newline='',
              encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)
    ov = rows[0]
    c.log('oracle overall: %s' % json.dumps(ov, sort_keys=True))
    c.log('wrote local_oracle_headroom.csv (%d strata rows)' % len(rows))
    c.log('task6 done')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
