"""Tests for sr_collect.py (implementation_plan.md Task 3).

Plain python script, standard library only, no pytest. Prints [PASS]/[FAIL] per
test and exits non-zero on any failure. Uses seeds 90210/90211 ONLY (never a
production seed 40001-40500 or 70001-70100).

Controller-ledger amendments to the derived implementation plan (Task 3):
- snapshot rows carry a SINGLE 'priority' field (the introduced edge's own
  priority draw), not priority_a/priority_b;
- per-state records gain 'edge_priorities' ([[pair, priority], ...] for EVERY
  feasible edge of that state, lexicographic by pair) so the selection rule is
  exactly reconstructible offline;
- label rows carry 'variant' because intro_id = sha256(a|b|day) (kit L155)
  collides ACROSS variants within one seed group (the 4 world-identical
  variants share all member ids); join key = (variant, intro_id), and the
  canonical intro_id stays verbatim in both files.
"""
import hashlib
import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import kit
import sr_collect

SEED = 90210
SEED2 = 90211
VARIANTS = ('development', 'sparse', 'cold_start', 'delayed', 'shift', 'drift')

SNAPSHOT_KEYS = {'intro_id', 'seed_group', 'variant', 'day', 'members', 'features',
                 'degree_a', 'degree_b', 'n_edges', 'k_greedy', 'k_chosen', 'priority'}
LABEL_KEYS = {'intro_id', 'variant', 's1', 's2', 's3', 'msmi', 'max_observed_day'}
STATE_KEYS = {'seed_group', 'variant', 'day', 'n_available', 'n_edges', 'k_greedy',
              'k_chosen', 'introduced', 'edge_priorities'}
VAL_EDGE_KEYS = {'intro_id', 'seed_group', 'variant', 'day', 'members', 'features',
                 'n_edges'}


def _read_jsonl(path):
    with open(path, encoding='utf-8') as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _collect(tmp, seed, variants, val_from=None):
    stats = sr_collect.collect_group(seed, variants, val_from, Path(tmp))
    sr_collect.merge_group_files(Path(tmp), [seed])
    return stats


def test_rows_equal_intros():
    """T-LAB-1: exactly one snapshot row and one label row per actual
    introduction, joined on (variant, intro_id), both directions."""
    with tempfile.TemporaryDirectory() as tmp:
        stats = _collect(tmp, SEED, VARIANTS)
        snaps = _read_jsonl(Path(tmp) / 'snapshots' / ('seed_%d.jsonl' % SEED))
        labs = _read_jsonl(Path(tmp) / 'labels' / ('seed_%d.jsonl' % SEED))
        # Row counts equal the introduction counts actually created by the sim.
        assert stats['rows'] == stats['intros'], (stats['rows'], stats['intros'])
        assert len(snaps) == len(labs) == stats['intros'], \
            (len(snaps), len(labs), stats['intros'])
        assert stats['intros'] > 0, 'collection produced no introductions'
        # (variant, intro_id) is the join key and must be unique in BOTH files.
        spairs = [(r['variant'], r['intro_id']) for r in snaps]
        lpairs = [(r['variant'], r['intro_id']) for r in labs]
        assert len(set(spairs)) == len(spairs), 'duplicate (variant, intro_id) in snapshots'
        assert len(set(lpairs)) == len(lpairs), 'duplicate (variant, intro_id) in labels'
        # Exact set equality, both directions (T-LAB-1).
        assert set(spairs) == set(lpairs), \
            ('join mismatch', sorted(set(spairs) ^ set(lpairs))[:5])
        # Canonical intro_id stays verbatim (auditable against kit's identifiers):
        # the kit id scheme is 'intro_' + 24 hex chars (kit L155).
        assert all(r['intro_id'].startswith('intro_') and len(r['intro_id']) == 30
                   for r in snaps), 'intro_id not in kit format'
        # Every label matured after the 60+40 episode (no UNKNOWN, inside horizon).
        for r in labs:
            assert r['s1'] in (0, 1), r
            assert r['s2'] in (0, 1, 'NOT_IN_POPULATION'), r
            assert r['s3'] in (0, 1, 'NOT_IN_POPULATION'), r
            assert r['msmi'] in (0, 1), r
            assert isinstance(r['max_observed_day'], int) and 0 <= r['max_observed_day'] <= 99, r
        # Per-variant state accounting: 60 match states per episode.
        assert stats['states'] == 60 * len(VARIANTS), stats['states']
        for variant in VARIANTS:
            pv = stats['per_variant'][variant]
            assert pv['states'] == 60, (variant, pv['states'])
            assert pv['intros'] == pv['rows'], (variant, pv)
        # Merged states.jsonl exists and has one record per match state.
        merged = _read_jsonl(Path(tmp) / 'states.jsonl')
        assert len(merged) == stats['states'], (len(merged), stats['states'])
        for r in merged:
            assert set(r) == STATE_KEYS, sorted(set(r) ^ STATE_KEYS)


def test_deterministic_replay():
    """Collect 90210 twice into two temp dirs -> byte-identical files."""
    with tempfile.TemporaryDirectory() as t1, tempfile.TemporaryDirectory() as t2:
        _collect(t1, SEED, VARIANTS, val_from=SEED)
        _collect(t2, SEED, VARIANTS, val_from=SEED)
        rels = ['snapshots/seed_%d.jsonl' % SEED,
                'labels/seed_%d.jsonl' % SEED,
                'states/seed_%d.jsonl' % SEED,
                'states.jsonl',
                'feasible_edges_val/seed_%d.jsonl' % SEED,
                'feasible_edges_val.jsonl']
        for rel in rels:
            h1, h2 = _sha(Path(t1) / rel), _sha(Path(t2) / rel)
            assert h1 == h2, ('non-deterministic file', rel, h1, h2)
            assert Path(t1, rel).stat().st_size > 0, ('empty file', rel)


def test_no_infeasible_pairs():
    """(a) a deliberately infeasible pair DOES raise in advance();
    (b) the pipeline PROPAGATES an advance() failure instead of swallowing it;
    (c) the real collection completes with zero failures."""
    # (a) Direct: at day 0 most members lack observed constraints, so almost any
    # available pair is not 'feasible' and advance() must raise.
    world = kit.generate(SEED, 200, 'evaluation', 'development')
    sim = kit.Simulator(world)
    state = sim.observe()
    avail = [m['member_id'] for m in state['members'] if m['available']]
    bad = None
    members = {m['member_id']: m for m in state['members']}
    for i, a in enumerate(avail):
        for b in avail[i + 1:]:
            if kit.eligibility(members[a], members[b])['status'] != 'feasible':
                bad = (a, b)
                break
        if bad:
            break
    assert bad is not None, 'expected at least one infeasible pair at day 0'
    raised = False
    try:
        sim.advance([list(bad)])
    except ValueError:
        raised = True
    assert raised, 'advance() accepted an infeasible pair'
    # (b) Propagation: inject an infeasible edge into the collector; the
    # advance() failure must surface out of collect_episode, not be swallowed.
    original = sr_collect.build_feasible_edges

    def poisoned(state):
        edges, degree = original(state)
        return edges + [('zzz_injected_a', 'zzz_injected_b')], degree

    sr_collect.build_feasible_edges = poisoned
    try:
        with tempfile.TemporaryDirectory() as tmp:
            raised = False
            try:
                sr_collect.collect_group(SEED, ('development',), None, Path(tmp))
            except ValueError as exc:
                raised = True
                assert 'unknown member' in str(exc), str(exc)
            assert raised, 'collect_group swallowed an advance() failure'
    finally:
        sr_collect.build_feasible_edges = original
    # (c) The real collection on a small variant subset completes with zero
    # failures and consistent counts.
    with tempfile.TemporaryDirectory() as tmp:
        stats = sr_collect.collect_group(SEED, ('development', 'sparse'), None, Path(tmp))
        assert stats['rows'] == stats['intros'] > 0, stats
        assert stats['states'] == 120, stats['states']


def test_priorities_recorded():
    """Every snapshot row carries its edge's priority float in [0,1); every
    state record carries edge_priorities for ALL feasible edges; snapshot
    priority == the introduced pair's entry in edge_priorities."""
    with tempfile.TemporaryDirectory() as tmp:
        # val_from=SEED makes 90210 a val group -> feasible_edges_val exercised.
        stats = _collect(tmp, SEED, VARIANTS, val_from=SEED)
        snaps = _read_jsonl(Path(tmp) / 'snapshots' / ('seed_%d.jsonl' % SEED))
        states = _read_jsonl(Path(tmp) / 'states' / ('seed_%d.jsonl' % SEED))
        assert snaps and states
        # State records: edge_priorities covers every feasible edge, sorted.
        priority_of = {}
        introduced_of = {}
        for s in states:
            assert set(s) == STATE_KEYS, sorted(set(s) ^ STATE_KEYS)
            assert len(s['edge_priorities']) == s['n_edges'], s
            pairs = [tuple(entry[0]) for entry in s['edge_priorities']]
            assert pairs == sorted(pairs), 'edge_priorities not lexicographic'
            assert len(set(pairs)) == len(pairs), 'duplicate pair in edge_priorities'
            for entry in s['edge_priorities']:
                pr = entry[1]
                assert isinstance(pr, float) and 0.0 <= pr < 1.0, entry
                priority_of[(s['variant'], s['day'], tuple(entry[0]))] = pr
            intro = [tuple(p) for p in s['introduced']]
            assert intro == sorted(intro), 'introduced not sorted'
            assert len(intro) == s['k_chosen'], s
            assert s['n_edges'] >= s['k_chosen'], s
            introduced_of[(s['variant'], s['day'])] = set(intro)
        # Snapshot rows: schema, priority range, feature count, k-consistency.
        seen_day_pairs = {}
        for r in snaps:
            assert set(r) == SNAPSHOT_KEYS, sorted(set(r) ^ SNAPSHOT_KEYS)
            assert isinstance(r['priority'], float) and 0.0 <= r['priority'] < 1.0, r
            assert len(r['features']) == 17 and all(isinstance(f, float) for f in r['features']), r
            assert len(r['members']) == 2 and r['members'][0] < r['members'][1], r
            assert r['n_edges'] >= r['k_chosen'] >= 1, r
            key = (r['variant'], r['day'], tuple(r['members']))
            # Ruling: snapshot priority == the pair's edge_priorities entry.
            assert r['priority'] == priority_of[key], (key, r['priority'], priority_of[key])
            assert tuple(r['members']) in introduced_of[(r['variant'], r['day'])], r
            seen_day_pairs[(r['variant'], r['day'])] = \
                seen_day_pairs.get((r['variant'], r['day']), 0) + 1
        # Every day's snapshot count equals that state's k_chosen.
        for (variant, day), n in seen_day_pairs.items():
            state_rows = [s for s in states if s['variant'] == variant and s['day'] == day]
            assert len(state_rows) == 1
            assert n == state_rows[0]['k_chosen'], (variant, day, n)
        # Val-edge file: one line per feasible edge of every match state.
        vals = _read_jsonl(Path(tmp) / 'feasible_edges_val' / ('seed_%d.jsonl' % SEED))
        merged_vals = _read_jsonl(Path(tmp) / 'feasible_edges_val.jsonl')
        assert len(vals) == len(merged_vals) == sum(s['n_edges'] for s in states), \
            (len(vals), len(merged_vals))
        by_state = {}
        for r in vals:
            assert set(r) == VAL_EDGE_KEYS, sorted(set(r) ^ VAL_EDGE_KEYS)
            assert r['intro_id'] is None, r
            assert len(r['features']) == 17, r
            by_state.setdefault((r['variant'], r['day']), []).append(tuple(r['members']))
        for s in states:
            got = sorted(by_state.get((s['variant'], s['day']), []))
            assert got == sorted(tuple(p) for p, _ in s['edge_priorities']), (s['variant'], s['day'])
        # Coverage stats from the same run stay internally consistent.
        assert stats['feasible_edges_total'] == sum(s['n_edges'] for s in states)


def test_pool_smoke():
    """The production path: multiprocessing pool over seed groups writes the
    same bytes as a direct sequential collect."""
    with tempfile.TemporaryDirectory() as tmp_pool, tempfile.TemporaryDirectory() as tmp_seq:
        results, coverage = sr_collect.collect_in_parallel(
            [SEED, SEED2], ('development',), None, Path(tmp_pool), workers=2)
        assert sorted(r['seed_group'] for r in results) == [SEED, SEED2]
        for g in (SEED, SEED2):
            for sub in ('snapshots', 'labels', 'states'):
                assert (Path(tmp_pool) / sub / ('seed_%d.jsonl' % g)).exists(), (sub, g)
        assert (Path(tmp_pool) / 'states.jsonl').exists()
        assert (Path(tmp_pool) / 'coverage_stats.json').exists()
        cov = json.loads((Path(tmp_pool) / 'coverage_stats.json').read_text(encoding='utf-8'))
        assert set(cov['per_variant']) == {'development'}
        assert cov['per_variant']['development']['episodes'] == 2
        assert cov['total']['episodes'] == 2
        # Percentiles must be monotone non-decreasing (guards the sorted-input
        # assumption of _percentile).
        pct = cov['per_variant']['development']['edges_per_state_percentiles']
        seq = [pct['p25'], pct['p50'], pct['p75'], pct['p90'], pct['p95'], pct['max']]
        assert all(a <= b for a, b in zip(seq, seq[1:])), seq
        mem = cov['per_variant']['development']['per_member_intro_counts']
        assert mem['min'] <= mem['p50'] <= mem['p90'] <= mem['max'], mem
        # Pool output == sequential output, byte for byte.
        sr_collect.collect_group(SEED, ('development',), None, Path(tmp_seq))
        for sub in ('snapshots', 'labels', 'states'):
            rel = '%s/seed_%d.jsonl' % (sub, SEED)
            assert _sha(Path(tmp_pool) / rel) == _sha(Path(tmp_seq) / rel), rel


def main():
    tests = [test_rows_equal_intros, test_deterministic_replay,
             test_no_infeasible_pairs, test_priorities_recorded, test_pool_smoke]
    failures = 0
    for test in tests:
        try:
            test()
        except Exception as exc:  # noqa: BLE001 - test harness reports every failure
            failures += 1
            print('[FAIL] %s: %s' % (test.__name__, ascii(str(exc))[:300]))
        else:
            print('[PASS] %s' % test.__name__)
    print('SUMMARY: %d/%d PASS' % (len(tests) - failures, len(tests)))
    sys.exit(1 if failures else 0)


if __name__ == '__main__':
    main()
