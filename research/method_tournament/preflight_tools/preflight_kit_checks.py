"""Repair-pass preflight measurements (evidence for audit_review/preflight_report).

Fixture seeds >= 90210 ONLY. Never reads or runs tournament seeds (143-163).
Uses only kit.py (frozen repo code). Writes preflight_kit_checks.json beside this file.
"""
import json
import math
import os
import statistics
import subprocess
import sys
import time
from itertools import combinations
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

from kit import (HARD, SOFT, Simulator, baseline_asks, baseline_match,  # noqa: E402
                 eligibility, generate)

FIXTURE_SEEDS = (90210, 90211, 90212)
VARIANTS = ('development', 'sparse', 'cold_start', 'delayed', 'shift', 'drift')
IDENTICAL_GROUP = ('development', 'delayed', 'shift', 'drift')
CHECK_DAYS = (0, 15, 30, 45, 59)
HUNGARIAN_NODE_CAP = 180

out = {'fixture_seeds': list(FIXTURE_SEEDS), 'checks': {}, 'msmi_table': {}}


def record(name, passed, evidence):
    out['checks'][name] = {'passed': bool(passed), 'evidence': evidence}
    print(('PASS ' if passed else 'FAIL ') + name)
    return bool(passed)


def graph_snapshot(sim, seed, variant, day):
    st = sim.observe()
    avail = [m for m in st['members'] if m['available']]
    past = {tuple(sorted((i['user_a'], i['user_b'])))
            for i in st['introductions']}
    nodes = [m['member_id'] for m in avail]
    adj = {nid: [] for nid in nodes}
    n_edges = 0
    for i in range(len(avail)):
        for j in range(i + 1, len(avail)):
            a, b = avail[i], avail[j]
            key = tuple(sorted((a['member_id'], b['member_id'])))
            if key in past:
                continue
            if eligibility(a, b)['status'] != 'feasible':
                continue
            n_edges += 1
            adj[a['member_id']].append(b['member_id'])
            adj[b['member_id']].append(a['member_id'])
    color = {}
    bipartite = True
    odd_cycle_seen = False
    for root in nodes:
        if root in color:
            continue
        color[root] = 0
        stack = [root]
        while stack:
            u = stack.pop()
            for w in adj[u]:
                if w not in color:
                    color[w] = 1 - color[u]
                    stack.append(w)
                elif color[w] == color[u]:
                    bipartite = False
                    odd_cycle_seen = True
    return {
        'seed': seed, 'variant': variant, 'day': day,
        'nodes': len(nodes), 'edges': n_edges, 'bipartite': bipartite,
        'odd_cycle': odd_cycle_seen,
        'nodes_over_hungarian_cap': len(nodes) > HUNGARIAN_NODE_CAP,
        'soft_unknown_members': sum(
            1 for m in avail
            if any(m['field_status'][k] == 'not_asked' for k in SOFT)),
        'soft_notasked_pairs': sum(
            1 for m in avail for k in SOFT
            if m['field_status'][k] == 'not_asked'),
    }


# --- Check 1: F-01 variant roster identity --------------------------------
roster = {}
for seed in FIXTURE_SEEDS[:2]:
    worlds = {v: generate(seed, 200, 'evaluation', v) for v in VARIANTS}
    base = worlds['development']['members']
    for v in VARIANTS:
        roster['%d/%s' % (seed, v)] = (worlds[v]['members'] == base)
    roster['%d/id_aligned_all6' % seed] = all(
        [m['member_id'] for m in worlds[v]['members']]
        == [m['member_id'] for m in base] for v in VARIANTS)
ident_ok = all(roster['%d/%s' % (seed, v)]
               for seed in FIXTURE_SEEDS[:2] for v in IDENTICAL_GROUP)
record('f01_variant_roster_identity', ident_ok, roster)

# --- Check 2: F-07 asking semantics ---------------------------------------
ask_ev = {}
sim = Simulator(generate(90210, 200, 'evaluation', 'development'))
st = sim.observe()
asks = baseline_asks(st)
eligible_raw = [m for m in st['members'] if m['available']
                and any(m['fields'][k] is None for k in HARD)
                and not any(m['field_status'][k] == 'declined' for k in HARD)]
ask_ev['day0_budget'] = st['ask_budget_remaining']
ask_ev['baseline_ask_count'] = len(asks)
ask_ev['expected_ask_count'] = min(len(eligible_raw), 12 // 3)
ask_ev['baseline_ask_fields'] = sorted({a['field'] for a in asks})
# hand-crafted constraints ask on a declined-HARD member
target = None
for m in st['members']:
    if (m['available']
            and any(m['field_status'][k] == 'declined' for k in HARD)
            and any(m['fields'][k] is None for k in HARD)):
        target = m
        break
if target is not None:
    tid = target['member_id']
    declined_keys = [k for k in HARD
                     if sim.members[tid]['field_status'][k] == 'declined']
    before_budget = sim.observe()['ask_budget_remaining']
    sim.resolve_asks([{'member_id': tid, 'field': 'constraints'}])
    after = sim.observe()
    tm = next(m for m in after['members'] if m['member_id'] == tid)
    ask_ev['declined_member_test'] = {
        'declined_keys': declined_keys,
        'declined_still_none': all(tm['fields'][k] is None
                                   for k in declined_keys),
        'cost_charged': before_budget - after['ask_budget_remaining'],
        'same_day_filled_hard_fields': sum(
            1 for k in HARD if tm['field_status'][k] == 'observed'),
    }
else:
    ask_ev['declined_member_test'] = None
# soft fields never block feasibility: mid-episode state (after asking progressed)
sim2 = Simulator(generate(90210, 200, 'evaluation', 'development'))
for _ in range(10):
    sim2.resolve_asks(baseline_asks(sim2.observe()))
    sim2.advance(baseline_match(sim2.observe()))
avail = [m for m in sim2.observe()['members'] if m['available']]
soft_unknown_feasible = 0
for i in range(len(avail)):
    for j in range(i + 1, len(avail)):
        a, b = avail[i], avail[j]
        if eligibility(a, b)['status'] != 'feasible':
            continue
        if any(a['fields'][k] is None or b['fields'][k] is None for k in SOFT):
            soft_unknown_feasible += 1
ask_ev['feasible_pairs_with_unknown_soft_after_10d'] = soft_unknown_feasible
# same-day visibility into match + day budget reset after advance
if target is not None:
    st2 = sim.observe()
    sim.resolve_asks(baseline_asks(st2))
    sim.advance(baseline_match(sim.observe()))
    ask_ev['budget_after_advance'] = sim.observe()['ask_budget_remaining']
else:
    ask_ev['budget_after_advance'] = None
dmt = ask_ev['declined_member_test'] or {}
f07_ok = (
    ask_ev['day0_budget'] == 12
    and ask_ev['baseline_ask_count'] == ask_ev['expected_ask_count']
    and ask_ev['baseline_ask_fields'] == ['constraints']
    and ask_ev['feasible_pairs_with_unknown_soft_after_10d'] > 0
    and dmt.get('cost_charged') == 3
    and dmt.get('declined_still_none') is True
    and (dmt.get('same_day_filled_hard_fields') or 0) > 0
    and ask_ev['budget_after_advance'] == 12)
record('f07_asking_semantics', f07_ok, ask_ev)

# --- Checks 3+4: control rollouts, graph branch stats, seed clustering ----
graph_rows = []
for seed in FIXTURE_SEEDS:
    for variant in VARIANTS:
        t0 = time.time()
        world = generate(seed, 200, 'evaluation', variant)
        sim = Simulator(world)
        for day in range(60):
            if day in CHECK_DAYS:
                graph_rows.append(graph_snapshot(sim, seed, variant, day))
            asks = baseline_asks(sim.observe())
            sim.resolve_asks(asks)
            sim.advance(baseline_match(sim.observe()))
        msmi = sim.metrics()['msmi_per_100_arrived_members']
        out['msmi_table']['%d/%s' % (seed, variant)] = round(msmi, 6)
        print('world %d/%s msmi=%.4f secs=%.1f'
              % (seed, variant, msmi, time.time() - t0))

def icc_two_way_random(rows):
    """ICC(1) on seed x variant table: rows = dict seed -> list of values."""
    k = len(next(iter(rows.values())))
    grand = statistics.mean(x for v in rows.values() for x in v)
    ss_between = sum(k * (statistics.mean(v) - grand) ** 2
                     for v in rows.values())
    ss_within = sum((x - statistics.mean(v)) ** 2
                    for v in rows.values() for x in v)
    df_b = len(rows) - 1
    df_w = len(rows) * (k - 1)
    ms_b = ss_between / df_b if df_b else 0.0
    ms_w = ss_within / df_w if df_w else 0.0
    denom = ms_w + (k - 1) * ms_b / len(rows) if (ms_w or ms_b) else 1.0
    return (ms_b - ms_w) / denom if denom else 0.0

table = {str(seed): [out['msmi_table']['%d/%s' % (seed, v)]
                     for v in VARIANTS] for seed in FIXTURE_SEEDS}
icc = icc_two_way_random(table)
non_bip = [r for r in graph_rows if not r['bipartite']]
d59 = [r for r in graph_rows if r['day'] == 59]
graph_ev = {
    'snapshots': len(graph_rows),
    'non_bipartite_snapshots': len(non_bip),
    'non_bipartite_fraction': round(len(non_bip) / len(graph_rows), 4),
    'max_nodes': max(r['nodes'] for r in graph_rows),
    'nodes_over_cap_snapshots': sum(1 for r in graph_rows
                                    if r['nodes_over_hungarian_cap']),
    'max_edges_day59': max(r['edges'] for r in d59),
    'soft_notasked_pairs_day59_max': max(r['soft_notasked_pairs']
                                         for r in d59),
    'soft_notasked_pairs_day59_mean': round(statistics.mean(
        r['soft_notasked_pairs'] for r in d59), 1),
}
graph_ev['max_edges_all_days'] = max(r['edges'] for r in graph_rows)
graph_ev['max_workload_snapshot'] = max(
    graph_rows, key=lambda r: r['edges'] * r['soft_notasked_pairs'])
record('f08_fixture_graph_stats', True, graph_ev)
out['checks']['f08_fixture_graph_stats']['graph_rows'] = graph_rows
cluster_ev = {'icc_seed_by_variant': round(icc, 4),
              'table': table,
              'note': ('development/delayed/shift/drift share identical worlds '
                       'per seed (check 1); inference must cluster on seed.')}
record('f01_seed_clustering', True, cluster_ev)

# --- Check 5: PYTHONHASHSEED independence ---------------------------------
digests = {}
for value in ('0', '1', 'random'):
    env = dict(os.environ, PYTHONHASHSEED=value)
    proc = subprocess.run([sys.executable, str(HERE / 'hashseed_probe.py')],
                          capture_output=True, text=True, env=env,
                          timeout=600, cwd=str(ROOT))
    digests[value] = proc.stdout.strip() or ('ERR:' + proc.stderr[-200:])
record('f13_hashseed_independence', len(set(digests.values())) == 1, digests)

ok = all(c['passed'] for c in out['checks'].values())
out['all_passed'] = ok
(HERE / 'preflight_kit_checks.json').write_text(
    json.dumps(out, indent=2, sort_keys=True) + '\n', encoding='utf-8')
print('ALL_PASSED' if ok else 'SOME_FAILED')
sys.exit(0 if ok else 1)