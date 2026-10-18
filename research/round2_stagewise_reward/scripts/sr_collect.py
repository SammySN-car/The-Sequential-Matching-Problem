"""Randomised data-collection pipeline over the synthetic sequential-matching
simulator (implementation_plan.md Task 3; policy from analysis_plan.md S.4,
val persistence from R1.3, parallelism from R1.2).

Controller-ledger amendments to the derived implementation plan (recorded in
task-3-report.md): snapshot rows carry a SINGLE 'priority' field (the introduced
edge's own draw), state records carry 'edge_priorities' for every feasible edge
(offline selection-rule reconstructibility), and label rows carry 'variant'
because intro_id = sha256(a|b|day) (kit L155) collides across the four
world-identical variants within one seed group; join key = (variant, intro_id).

Collection policy (analysis_plan.md S.4):
- asks  = kit.baseline_asks(state) - identical budget and order to greedy.
- edges = sr_features.build_feasible_edges(state): available members,
  kit.eligibility == 'feasible', not in past (mirrors kit.baseline_match L213-216).
- One priority draw per edge from
  random.Random(int.from_bytes(sha256(f'{seed}|{variant}|{day}|collect')
  .digest()[:16], 'big')) - byte-identical to kit.rand_for(seed, variant, day,
  'collect') (kit L24-25) - drawn ONE per edge in explicitly sorted canonical
  edge order. The RNG is seeded per (seed, variant, day) ONLY; no dict/set
  iteration order may leak into any output.
- Sort edges by descending priority (ties broken by pair for determinism) and
  greedily take edges whose members are all unused (first-come disjoint) ->
  randomised maximal matching with the baseline's maximal-greedy structure.
- sim.advance(chosen): any raise is an episode failure and PROPAGATES (never
  caught-and-continued).

Episode = 60 days of (resolve_asks then advance) + 40 empty advance([]) calls
(kit L224-229, L236); labels mature only after the full episode, and
sr_label.maturity_report raises on any observed_day >= 100 before labels are
written.

Snapshot rows are frozen from the PRE-advance observe() state (observe()
deep-copies, kit L101-109, so later simulator activity cannot mutate them) and
carry the simulator's own introduction_id verbatim (kit L155).

Outputs (data dir):
- snapshots/seed_<g>.jsonl, labels/seed_<g>.jsonl - one file per seed group,
  all 6 variants, rows sorted by (variant index, day, pair).
- states/seed_<g>.jsonl - per-group per-state records (shards); the parent
  merges them into states.jsonl in sorted seed order after the pool completes
  (no cross-worker file sharing).
- feasible_edges_val/seed_<g>.jsonl - val groups only (seed >= val_from); one
  line per feasible edge of every match state; merged by the parent into
  feasible_edges_val.jsonl.
- coverage_stats.json - per variant + total aggregates (parent process only).

JSON convention: one object per line, sort_keys=True, UTF-8 (ASCII-safe:
json.dumps ensure_ascii). Standard library only.
"""
import argparse
import hashlib
import json
import math
import multiprocessing
import os
import random
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import kit
from sr_features import build_feasible_edges, extract_pair_features
from sr_label import maturity_report, stage_labels

# Official six variants, verbatim from evaluate.py L16 (kit.VARIANTS is not
# exported).
VARIANTS = ('development', 'sparse', 'cold_start', 'delayed', 'shift', 'drift')
N = 200
POOL_ID = 'evaluation'          # identical to evaluate.py L152
MATCH_DAYS = 60
COOLDOWN_DAYS = 40              # -> sim.day 100; every label matures (S.2)
DEFAULT_DATA_DIR = REPO_ROOT / 'research' / 'round2_stagewise_reward' / 'data'


def priority_rng(seed, variant, day):
    """The collection priority RNG for one match state. Seeded per
    (seed, variant, day) ONLY; identical to kit.rand_for(seed, variant, day,
    'collect') (kit L24-25)."""
    key = ('%s|%s|%s|collect' % (seed, variant, day)).encode()
    return random.Random(int.from_bytes(hashlib.sha256(key).digest()[:16], 'big'))


def _write_jsonl(path, rows):
    """One JSON object per line, sort_keys=True, UTF-8, '\\n' endings."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + '\n')


def collect_episode(seed, variant, with_val_edges=False):
    """Run one full 60+40 episode with the randomised collection policy.

    Returns a dict with rows plus per-variant aggregates:
      snapshots, labels, states, val_edges (lists of row dicts),
      intros, s1_pos, s2_pos, s3_pos, msmi_pos, feasible_edges_total,
      member_counts (ALL world members, default 0), pairs (list of (a, b)),
      edges_per_state (list of int).
    Any advance() or maturity failure raises: an episode failure is never
    swallowed.
    """
    world = kit.generate(seed, N, POOL_ID, variant)
    sim = kit.Simulator(world)
    snapshots, states, val_edges = [], [], []
    member_counts = {m['member_id']: 0 for m in world['members']}
    pairs = []
    edges_per_state = []
    for _day in range(MATCH_DAYS):
        state = sim.observe()
        sim.resolve_asks(kit.baseline_asks(state))
        # Match-phase state: the SAME post-ask observe() dict feeds the edge
        # graph, the features, the greedy reference and the priorities.
        state = sim.observe()
        edges, degree = build_feasible_edges(state)
        # Explicit canonical sort: build_feasible_edges iterates state member
        # order; sorting makes draw order independent of any dict ordering.
        edges = sorted(edges)
        rng = priority_rng(seed, variant, state['day'])
        # One draw per edge, in canonical edge order (determinism contract).
        prio_pairs = [(edge, rng.random()) for edge in edges]
        prio = dict(prio_pairs)
        ordered = sorted(prio_pairs, key=lambda ep: (-ep[1], ep[0]))
        used = set()
        chosen = []
        for edge, _p in ordered:
            if used.isdisjoint(edge):
                chosen.append(edge)
                used.update(edge)
        chosen = sorted(chosen)
        n_edges = len(edges)
        edges_per_state.append(n_edges)
        # Reference-only greedy count on the same state (no side effects).
        k_greedy = len(kit.baseline_match(state))
        n_available = sum(1 for m in state['members'] if m['available'])
        states.append({
            'seed_group': seed, 'variant': variant, 'day': state['day'],
            'n_available': n_available, 'n_edges': n_edges,
            'k_greedy': k_greedy, 'k_chosen': len(chosen),
            'introduced': [list(e) for e in chosen],
            # Every feasible edge's draw, lexicographic by pair: the selection
            # rule is exactly reconstructible offline (S.4, R1.3).
            'edge_priorities': [[list(e), p] for e, p in prio_pairs],
        })
        if with_val_edges:
            for a, b in edges:
                val_edges.append({
                    'intro_id': None, 'seed_group': seed, 'variant': variant,
                    'day': state['day'], 'members': [a, b],
                    'features': extract_pair_features(state, degree, a, b),
                    'n_edges': n_edges,
                })
        # advance BEFORE serialising rows: a policy error (infeasible pair)
        # fails the episode before any row is emitted. Features still come
        # from the held pre-advance observe() dict, frozen at decision time.
        sim.advance([list(e) for e in chosen])
        new_intros = sim.introductions[-len(chosen):] if chosen else []
        # advance() appends one introduction per pair in sorted-pair order
        # (kit L152-156); zip against the same sorted order.
        assert [tuple(sorted((i['user_a'], i['user_b']))) for i in new_intros] == chosen, \
            'advance() introduction order diverged from chosen pairs'
        for (a, b), intro in zip(chosen, new_intros):
            snapshots.append({
                'intro_id': intro['introduction_id'], 'seed_group': seed,
                'variant': variant, 'day': state['day'], 'members': [a, b],
                'features': extract_pair_features(state, degree, a, b),
                'degree_a': degree.get(a, 0), 'degree_b': degree.get(b, 0),
                'n_edges': n_edges, 'k_greedy': k_greedy,
                'k_chosen': len(chosen), 'priority': prio[(a, b)],
            })
            member_counts[a] += 1
            member_counts[b] += 1
            pairs.append((a, b))
    for _ in range(COOLDOWN_DAYS):
        sim.advance([])
    # Any immature event raises here, before a single label row is produced.
    report = maturity_report(sim.introductions, sim.events)
    labels = []
    for intro in sim.introductions:
        lab = stage_labels(intro, sim.events)
        labels.append({
            'intro_id': intro['introduction_id'], 'variant': variant,
            's1': lab['s1'], 's2': lab['s2'], 's3': lab['s3'], 'msmi': lab['msmi'],
            'max_observed_day': report['per_intro_max_observed_day'][intro['introduction_id']],
        })
    return {
        'snapshots': snapshots, 'labels': labels, 'states': states,
        'val_edges': val_edges,
        'intros': len(sim.introductions),
        's1_pos': sum(1 for r in labels if r['s1'] == 1),
        's2_pos': sum(1 for r in labels if r['s2'] == 1),
        's3_pos': sum(1 for r in labels if r['s3'] == 1),
        'msmi_pos': sum(1 for r in labels if r['msmi'] == 1),
        'feasible_edges_total': sum(edges_per_state),
        'member_counts': member_counts, 'pairs': pairs,
        'edges_per_state': edges_per_state,
    }


def collect_group(seed, variants, val_from, out_dir):
    """Collect one whole seed group (all `variants`) and write its per-group
    files under `out_dir`. Val groups (seed >= val_from) additionally write the
    feasible-edge shard. Returns stats {intros, rows, s1_pos, s2_pos, s3_pos,
    msmi_pos, states, feasible_edges_total, seconds, per_variant}."""
    started = time.time()
    out_dir = Path(out_dir)
    with_val = val_from is not None and seed >= val_from
    snapshots, labels, states, val_edges = [], [], [], []
    per_variant = {}
    totals = {'intros': 0, 'rows': 0, 's1_pos': 0, 's2_pos': 0, 's3_pos': 0,
              'msmi_pos': 0, 'states': 0, 'feasible_edges_total': 0}
    for variant in variants:
        ep = collect_episode(seed, variant, with_val_edges=with_val)
        snapshots.extend(ep['snapshots'])
        labels.extend(ep['labels'])
        states.extend(ep['states'])
        val_edges.extend(ep['val_edges'])
        per_variant[variant] = {
            'intros': ep['intros'], 'rows': len(ep['snapshots']),
            'states': len(ep['states']),
            'feasible_edges_total': ep['feasible_edges_total'],
            's1_pos': ep['s1_pos'], 's2_pos': ep['s2_pos'],
            's3_pos': ep['s3_pos'], 'msmi_pos': ep['msmi_pos'],
            'pairs': ep['pairs'], 'member_counts': ep['member_counts'],
            'edges_per_state': ep['edges_per_state'],
        }
        totals['intros'] += ep['intros']
        totals['rows'] += len(ep['snapshots'])
        totals['states'] += len(ep['states'])
        totals['feasible_edges_total'] += ep['feasible_edges_total']
        for key in ('s1_pos', 's2_pos', 's3_pos', 'msmi_pos'):
            totals[key] += ep[key]
    # T-LAB-1 self-check: the pipeline must never emit misaligned data.
    if totals['rows'] != totals['intros']:
        raise AssertionError('T-LAB-1 violated: %d snapshot rows vs %d introductions'
                             % (totals['rows'], totals['intros']))
    if len(labels) != totals['intros']:
        raise AssertionError('T-LAB-1 violated: %d label rows vs %d introductions'
                             % (len(labels), totals['intros']))
    keys = [(r['variant'], r['intro_id']) for r in snapshots]
    if len(set(keys)) != len(keys):
        raise AssertionError('duplicate (variant, intro_id) in snapshots')
    if set(keys) != {(r['variant'], r['intro_id']) for r in labels}:
        raise AssertionError('snapshot/label join mismatch within group %d' % seed)
    # Deterministic sorted writes: (variant index, day, pair).
    vindex = {v: i for i, v in enumerate(variants)}
    snapshots.sort(key=lambda r: (vindex[r['variant']], r['day'], r['members']))
    labels.sort(key=lambda r: (vindex[r['variant']], r['intro_id']))
    states.sort(key=lambda r: (vindex[r['variant']], r['day']))
    val_edges.sort(key=lambda r: (vindex[r['variant']], r['day'], r['members']))
    _write_jsonl(out_dir / 'snapshots' / ('seed_%d.jsonl' % seed), snapshots)
    _write_jsonl(out_dir / 'labels' / ('seed_%d.jsonl' % seed), labels)
    _write_jsonl(out_dir / 'states' / ('seed_%d.jsonl' % seed), states)
    if with_val:
        _write_jsonl(out_dir / 'feasible_edges_val' / ('seed_%d.jsonl' % seed), val_edges)
    return {'seed_group': seed, 'seconds': time.time() - started,
            'per_variant': per_variant, **totals}


def merge_group_files(data_dir, seeds):
    """Parent-side merge (never in workers): concatenate per-group state shards
    into states.jsonl and val-edge shards into feasible_edges_val.jsonl, in
    sorted seed order. Shards are already internally sorted, so the merge is a
    pure byte concatenation and fully deterministic."""
    data_dir = Path(data_dir)
    for sub, merged in (('states', 'states.jsonl'),
                        ('feasible_edges_val', 'feasible_edges_val.jsonl')):
        parts = []
        for g in sorted(seeds):
            shard = data_dir / sub / ('seed_%d.jsonl' % g)
            if shard.exists():
                parts.append(shard.read_text(encoding='utf-8'))
        path = data_dir / merged
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(''.join(parts), encoding='utf-8', newline='\n')


def _percentile(sorted_vals, q):
    """Linear-interpolation percentile (house convention: gr/fc)."""
    if not sorted_vals:
        return None
    if len(sorted_vals) == 1:
        return float(sorted_vals[0])
    pos = (len(sorted_vals) - 1) * q
    lo, hi = int(math.floor(pos)), int(math.ceil(pos))
    if lo == hi:
        return float(sorted_vals[lo])
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo)


def _summary(values):
    vals = sorted(values)
    return {'n': len(vals), 'min': vals[0] if vals else None,
            'max': vals[-1] if vals else None,
            'mean': (sum(vals) / len(vals)) if vals else None,
            'p50': _percentile(vals, 0.50), 'p90': _percentile(vals, 0.90)}


def aggregate_coverage(group_stats, seeds, variants, val_from, workers):
    """Merge per-group stats into coverage_stats.json content: per variant and
    total - episodes, states, feasible_edges_total, distinct_pairs_introduced,
    share_introduced (= distinct pairs / feasible (state, edge) opportunities),
    intros, per-member intro counts summary (zeros included), and
    edges-per-state percentiles. Deterministic (no timing values here)."""
    def block(selector):
        episodes = 0
        states = feasible = intros = 0
        pairs = set()
        member_counts = {}
        edges_per_state = []
        pos = {'s1_pos': 0, 's2_pos': 0, 's3_pos': 0, 'msmi_pos': 0}
        for g in group_stats:
            for variant, pv in sorted(g['per_variant'].items()):
                if not selector(variant):
                    continue
                episodes += 1
                states += pv['states']
                feasible += pv['feasible_edges_total']
                intros += pv['intros']
                pairs.update(pv['pairs'])
                edges_per_state.extend(pv['edges_per_state'])
                for key in pos:
                    pos[key] += pv[key]
                for member, count in pv['member_counts'].items():
                    member_counts[member] = member_counts.get(member, 0) + count
        # _percentile assumes sorted input (house linear-percentile convention).
        edges_sorted = sorted(edges_per_state)
        return {
            'episodes': episodes, 'states': states,
            'feasible_edges_total': feasible,
            'distinct_pairs_introduced': len(pairs),
            'share_introduced': (len(pairs) / feasible) if feasible else None,
            'intros': intros, **pos,
            'per_member_intro_counts': _summary(list(member_counts.values())),
            'edges_per_state_percentiles': {
                'p25': _percentile(edges_sorted, 0.25),
                'p50': _percentile(edges_sorted, 0.50),
                'p75': _percentile(edges_sorted, 0.75),
                'p90': _percentile(edges_sorted, 0.90),
                'p95': _percentile(edges_sorted, 0.95),
                'max': float(edges_sorted[-1]) if edges_sorted else None,
            },
        }
    return {
        'per_variant': {v: block(lambda var, v=v: var == v) for v in variants},
        'total': block(lambda var: True),
        'config': {
            'seeds_from': min(seeds), 'seeds_to': max(seeds),
            'n_seed_groups': len(seeds), 'variants': list(variants),
            'val_from': val_from, 'workers': workers,
            'share_introduced_definition':
                'distinct pairs introduced / total feasible (state, edge) opportunities',
        },
    }


def _collect_group_worker(args):
    seed, variants, val_from, out_dir = args
    return collect_group(seed, variants, val_from, out_dir)


def collect_in_parallel(seeds, variants, val_from, data_dir, workers):
    """multiprocessing.Pool over seed groups (one whole group per worker, no
    cross-worker file sharing); parent merges shards and writes
    coverage_stats.json. Exceptions propagate to the caller (episode failure =
    run failure)."""
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    workers = max(1, min(int(workers), len(seeds)))
    tasks = [(s, tuple(variants), val_from, str(data_dir)) for s in seeds]
    results = []
    with multiprocessing.Pool(processes=workers) as pool:
        for stats in pool.imap_unordered(_collect_group_worker, tasks):
            results.append(stats)
            print('group %d done: intros=%d rows=%d states=%d (%.1fs)'
                  % (stats['seed_group'], stats['intros'], stats['rows'],
                     stats['states'], stats['seconds']), flush=True)
    results.sort(key=lambda r: r['seed_group'])
    merge_group_files(data_dir, seeds)
    coverage = aggregate_coverage(results, seeds, variants, val_from, workers)
    coverage_path = data_dir / 'coverage_stats.json'
    coverage_path.write_text(json.dumps(coverage, indent=2, sort_keys=True) + '\n',
                             encoding='utf-8', newline='\n')
    return results, coverage


def parse_seeds(spec):
    """'40012-40451' (inclusive range) and/or '90210,90211' (explicit list)."""
    seeds = set()
    for token in spec.split(','):
        token = token.strip()
        if not token:
            continue
        if '-' in token:
            lo, hi = token.split('-', 1)
            seeds.update(range(int(lo), int(hi) + 1))
        else:
            seeds.add(int(token))
    if not seeds:
        raise SystemExit('empty --seeds specification')
    return sorted(seeds)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Randomised stage-wise reward data collection (Task 3)')
    parser.add_argument('--seeds', required=True,
                        help='range A-B and/or explicit comma list A,B,C')
    parser.add_argument('--val-from', type=int, default=None,
                        help='seed groups >= this seed also write feasible edges')
    parser.add_argument('--workers', type=int, default=None,
                        help='pool size; default min(8, os.cpu_count())')
    parser.add_argument('--data-dir', default=None,
                        help='output data dir (default: experiment data/)')
    args = parser.parse_args(argv)
    seeds = parse_seeds(args.seeds)
    workers = args.workers if args.workers else min(8, os.cpu_count() or 1)
    workers = max(1, workers)
    data_dir = Path(args.data_dir) if args.data_dir else DEFAULT_DATA_DIR
    print('collecting %d seed groups x %d variants with %d workers into %s'
          % (len(seeds), len(VARIANTS), workers, data_dir), flush=True)
    try:
        results, coverage = collect_in_parallel(
            seeds, VARIANTS, args.val_from, data_dir, workers)
    except Exception as exc:  # episode failure: never continue silently
        print('COLLECTION FAILURE: %s: %s' % (type(exc).__name__, ascii(str(exc))[:400]),
              file=sys.stderr)
        return 1
    total = coverage['total']
    print('done: %d episodes, %d introductions, %d states, '
          '%d feasible (state, edge) opportunities in %.1fs'
          % (total['episodes'], total['intros'], total['states'],
             total['feasible_edges_total'],
             sum(r['seconds'] for r in results)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
