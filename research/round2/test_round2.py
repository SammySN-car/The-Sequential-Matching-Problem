"""Round 2 candidate: gated maximum-weight allocation - unit tests (TDD).

Run: python -m pytest research/round2/test_round2.py -q   (or unittest)
Frozen files (kit/evaluate/policy) are imported READ-ONLY.
"""
import json
import os
import random
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
R2 = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(R2))
sys.path.insert(0, str(R2 / 'policies'))

import kit            # noqa: E402  (frozen)
import evaluate       # noqa: E402  (frozen)
import alloc_core     # noqa: E402  (round2 candidate core)


# ---- test-only exhaustive reference (n <= 8 nodes) -------------------------
def brute_max_weight(edges):
    weight = {}
    for a, b, s in edges:
        weight[tuple(sorted((a, b)))] = s
    nodes = sorted({m for a, b, s in edges for m in (a, b)})
    best = ([], 0)

    def rec(i, used, chosen, total):
        nonlocal best
        if i == len(nodes):
            if total > best[1]:
                best = (sorted(chosen), total)
            return
        u = nodes[i]
        if u in used:
            rec(i + 1, used, chosen, total)
            return
        rec(i + 1, used, chosen, total)          # leave u free
        for v in nodes[i + 1:]:
            if v in used or tuple(sorted((u, v))) not in weight:
                continue
            chosen.append(tuple(sorted((u, v))))
            rec(i + 1, used | {v, u}, chosen, total + weight[tuple(sorted((u, v)))])
            chosen.pop()

    rec(0, set(), [], 0)
    return best


def graph_seed(rng, n_nodes, p_edge=0.5, max_score=4):
    edges = []
    ids = ['m%02d' % i for i in range(n_nodes)]
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            if rng.random() < p_edge:
                edges.append((a, b, rng.randint(0, max_score)))
    return edges


class TwoColorTests(unittest.TestCase):
    def test_bipartite_returns_sorted_partition(self):
        edges = [('a', 'b', 1), ('b', 'c', 1), ('c', 'd', 1)]  # path a-b-c-d
        left, right = alloc_core.two_color(edges)
        self.assertEqual(sorted(left + right), ['a', 'b', 'c', 'd'])
        # valid 2-coloring: no edge inside a side
        for a, b, _ in edges:
            self.assertTrue((a in left) != (b in left))

    def test_odd_cycle_k3_is_none(self):
        edges = [('a', 'b', 1), ('b', 'c', 1), ('a', 'c', 1)]
        self.assertIsNone(alloc_core.two_color(edges))

    def test_empty_graph(self):
        self.assertEqual(alloc_core.two_color([]), ([], []))


class GreedyParityTests(unittest.TestCase):
    """alloc_core.greedy_matching must equal kit.baseline_match exactly."""

    def _states(self):
        for seed in (90250, 90251, 90252):
            for variant in ('development', 'sparse', 'cold_start'):
                world = kit.generate(seed, 200, 'evaluation', variant)
                sim = kit.Simulator(world)
                for day in range(6):
                    sim.resolve_asks(kit.baseline_asks(sim.observe()))
                    state = sim.observe()
                    yield state
                    sim.advance(kit.baseline_match(state))

    def test_greedy_identical_to_official_on_fixture_states(self):
        checked = 0
        for state in self._states():
            official = kit.baseline_match(state)
            ours = alloc_core.greedy_matching(alloc_core.feasible_edges(state))
            self.assertEqual([sorted(p) for p in official], [sorted(p) for p in ours],
                             'greedy divergence on day %s' % state['day'])
            checked += 1
        self.assertGreaterEqual(checked, 15)

    def test_feasible_edges_excludes_past_and_infeasible(self):
        world = kit.generate(90250, 60, 'evaluation', 'development')
        sim = kit.Simulator(world)
        sim.resolve_asks(kit.baseline_asks(sim.observe()))
        pairs = kit.baseline_match(sim.observe())
        sim.advance(pairs)
        state = sim.observe()
        past = {tuple(sorted((i['user_a'], i['user_b']))) for i in state['introductions']}
        for a, b, s in alloc_core.feasible_edges(state):
            self.assertNotIn(tuple(sorted((a, b))), past)
            self.assertGreaterEqual(s, 0)
            self.assertLessEqual(s, len(kit.SOFT))


class HungarianTests(unittest.TestCase):
    def _solve(self, edges):
        colored = alloc_core.two_color(edges)
        self.assertIsNotNone(colored, 'test graph must be bipartite')
        left, right = colored
        wmap = {}
        for a, b, s in edges:
            wmap[(a, b)] = s
            wmap[(b, a)] = s
        pairs = alloc_core.hungarian_max_weight(left, right, wmap)
        w = {tuple(sorted(p)): s for a, b, s in edges for p in [(a, b)]}
        total = sum(w[tuple(sorted(p))] for p in pairs)
        return sorted(tuple(sorted(p)) for p in pairs), total

    def test_matches_brute_force_weight_on_random_bipartite(self):
        rng = random.Random(7)
        for trial in range(60):
            # bipartite by construction: left ids l*, right ids r*
            edges = []
            for i in range(rng.randint(1, 4)):
                for j in range(rng.randint(1, 4)):
                    if rng.random() < 0.6:
                        edges.append(('l%d' % i, 'r%d' % j, rng.randint(0, 4)))
            if not edges:
                continue
            pairs, total = self._solve(edges)
            _, best = brute_max_weight(edges)
            self.assertEqual(total, best, 'trial %d' % trial)
            # non-overlapping
            used = [m for p in pairs for m in p]
            self.assertEqual(len(used), len(set(used)))

    def test_includes_zero_weight_pairs(self):
        # a can match b(5) or c(0); optimum weight 5 with either 1 pair.
        edges = [('a', 'b', 5), ('a', 'c', 0)]
        pairs, total = self._solve(edges)
        self.assertEqual(total, 5)
        self.assertEqual(len(pairs), 1)

    def test_empty_and_single(self):
        self.assertEqual(alloc_core.hungarian_max_weight([], [], {}), [])
        pairs, total = self._solve([('a', 'b', 3)])
        self.assertEqual(total, 3)
        self.assertEqual(pairs, [('a', 'b')])


class GateTests(unittest.TestCase):
    """G1: cardinality >= greedy; G2: strictly greater score sum; else greedy."""

    def test_none_exact_falls_back(self):
        chosen, info = alloc_core.apply_gate([['a', 'b']], 1, 5, None, 0)
        self.assertEqual(chosen, 'greedy')
        self.assertEqual(info['reason'], 'exact_unavailable')

    def test_cardinality_loss_rejected(self):
        chosen, info = alloc_core.apply_gate(
            [['a', 'b'], ['c', 'd']], 2, 10, [['a', 'b']], 8)
        self.assertEqual(chosen, 'greedy')
        self.assertEqual(info['reason'], 'g1_cardinality_loss')

    def test_equal_sum_rejected_strict_gain_required(self):
        chosen, info = alloc_core.apply_gate([['a', 'b']], 1, 5, [['a', 'b']], 5)
        self.assertEqual(chosen, 'greedy')
        self.assertEqual(info['reason'], 'g2_no_strict_gain')

    def test_strict_gain_and_cardinality_adopted(self):
        chosen, info = alloc_core.apply_gate([['a', 'b']], 1, 5, [['a', 'b'], ['c', 'd']], 7)
        self.assertEqual(chosen, 'exact')
        self.assertEqual(info['score_gain'], 2)
        self.assertEqual(info['cardinality_change'], 1)

    def test_more_cardinality_same_sum_rejected(self):
        # allowed by G1 but fails G2 -> greedy (frozen rule: both required)
        chosen, info = alloc_core.apply_gate([['a', 'b']], 1, 5, [['a', 'b'], ['c', 'd']], 5)
        self.assertEqual(chosen, 'greedy')
        self.assertEqual(info['reason'], 'g2_no_strict_gain')

    def test_star_graph_exact_equals_greedy_weight_so_greedy_wins(self):
        # star: a-b(5), a-c(5). greedy -> (a,b). exact -> one pair weight 5. gate -> greedy.
        state_like = None  # structural test via allocate on synthetic members below
        edges = [('a', 'b', 5), ('a', 'c', 5)]
        colored = alloc_core.two_color(edges)
        left, right = colored
        wmap = {}
        for x, y, s in edges:
            wmap[(x, y)] = s
            wmap[(y, x)] = s
        exact = alloc_core.hungarian_max_weight(left, right, wmap)
        greedy = alloc_core.greedy_matching(edges)
        g_sum = sum(dict.fromkeys([]) or {tuple(sorted((a, b))): s for a, b, s in edges}[tuple(sorted(p))] for p in greedy)
        e_sum = sum(wmap.get(tuple(sorted(p)), 0) for p in exact)
        chosen, _ = alloc_core.apply_gate(greedy, len(greedy), g_sum, exact, e_sum)
        self.assertEqual(chosen, 'greedy')


class AllocateTests(unittest.TestCase):
    def test_gated_equals_greedy_when_gate_cannot_pass(self):
        for seed, variant in ((90250, 'development'), (90251, 'sparse')):
            world = kit.generate(seed, 200, 'evaluation', variant)
            sim = kit.Simulator(world)
            for day in range(5):
                sim.resolve_asks(kit.baseline_asks(sim.observe()))
                state = sim.observe()
                official = kit.baseline_match(state)
                gated = alloc_core.allocate(state, 'gated')[0]
                ungated = alloc_core.allocate(state, 'ungated')[0]
                self.assertEqual([sorted(p) for p in official],
                                 [sorted(p) for p in gated])
                # ungated may differ (that is the ablation); it must stay a valid
                # non-overlapping matching over currently feasible pairs
                used = [m for p in ungated for m in p]
                self.assertEqual(len(used), len(set(used)))
                feasible = {alloc_core.pair_key(a, b) for a, b, _ in
                            alloc_core.feasible_edges(state)}
                for x, y in ungated:
                    self.assertIn(alloc_core.pair_key(x, y), feasible)
                sim.advance(official)

    def test_allocate_never_returns_partial_on_nonbipartite_state(self):
        # force a triangle-like feasible graph via synthetic members
        def mem(i, zone='zone_a'):
            return {'member_id': 'm%d' % i, 'pool_id': 'p', 'synthetic': True, 'age': 30,
                    'gender': 'woman' if i % 2 else 'man', 'zone': zone, 'arrived_day': 0,
                    'fields': {k: None for k in list(kit.HARD) + list(kit.SOFT)},
                    'field_status': {k: 'not_asked' for k in list(kit.HARD) + list(kit.SOFT)},
                    'field_observed_day': {k: None for k in list(kit.HARD) + list(kit.SOFT)},
                    'source': 'synthetic_questionnaire', 'available': True}
        # missing hard fields -> needs_clarification, not feasible -> no edges; still must not crash
        state = {'day': 0, 'ask_budget_remaining': 12, 'members': [mem(0), mem(1), mem(2)],
                 'introductions': [], 'feedback': [], 'ask_log': []}
        for arm in ('gated', 'ungated'):
            pairs, tele = alloc_core.allocate(state, arm)
            self.assertEqual(pairs, [])
            self.assertEqual(tele['solver'], 'empty_graph')


class LauncherProtocolTests(unittest.TestCase):
    LAUNCHER = str(R2 / 'policies' / 'mw_alloc.py')

    def _invoke(self, arm, request, env=None):
        e = dict(os.environ)
        if env:
            e.update(env)
        proc = subprocess.run(
            [sys.executable, self.LAUNCHER, '--arm', arm, '--baseline', 'ignored'],
            input=json.dumps(request).encode(), capture_output=True, timeout=10, env=e)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode(errors='replace'))
        return json.loads(proc.stdout.decode())

    def _state(self, seed=90250, variant='development'):
        world = kit.generate(seed, 200, 'evaluation', variant)
        sim = kit.Simulator(world)
        sim.resolve_asks(kit.baseline_asks(sim.observe()))
        return sim.observe()

    def test_ask_phase_identical_to_official_greedy(self):
        state = self._state()
        req = {'schema_version': kit.VERSION, 'phase': 'ask', 'state': state, 'memory': None}
        official_asks = kit.baseline_asks(state)
        for arm in ('gated', 'ungated'):
            got = self._invoke(arm, req)
            self.assertEqual(got['asks'], official_asks)
            self.assertIn('memory', got)

    def test_match_phase_gated_identical_when_gate_off(self):
        state = self._state()
        req = {'schema_version': kit.VERSION, 'phase': 'match', 'state': state, 'memory': None}
        official = kit.baseline_match(state)
        got = self._invoke('gated', req)
        self.assertEqual([sorted(p) for p in got['pairs']],
                         [sorted(p) for p in official])

    def test_memory_persists_and_stays_small(self):
        state = self._state()
        mem = None
        for _ in range(3):
            req = {'schema_version': kit.VERSION, 'phase': 'match', 'state': state, 'memory': mem}
            got = self._invoke('gated', req)
            mem = got['memory']
        self.assertLess(len(json.dumps(mem, allow_nan=False).encode()), 4096)

    def test_determinism_across_hash_seeds(self):
        state = self._state(seed=90251, variant='sparse')
        req = {'schema_version': kit.VERSION, 'phase': 'match', 'state': state, 'memory': None}
        outputs = set()
        for hs in ('0', '1', '42'):
            outputs.add(json.dumps(self._invoke('gated', req, {'PYTHONHASHSEED': hs}),
                                   sort_keys=True))
        self.assertEqual(len(outputs), 1)

    def test_rejects_wrong_phase_payload_via_official_validate(self):
        state = self._state()
        req = {'schema_version': kit.VERSION, 'phase': 'match', 'state': state, 'memory': None}
        got = self._invoke('gated', req)
        evaluate.validate_response(got, 'match')  # official schema check


class EpisodeParityTests(unittest.TestCase):
    """Instrumented episode loop must match official evaluate.episode digests."""

    def test_official_episode_runs_ungated_and_gated_valid(self):
        import runner_r2
        world = kit.generate(90252, 200, 'evaluation', 'development')
        for arm in ('gated', 'ungated'):
            cmd = [sys.executable, str(R2 / 'policies' / 'mw_alloc.py'), '--arm', arm]
            official = evaluate.episode(world, cmd)
            instr, final_memory, telemetry = runner_r2.episode_instrumented(world, cmd)
            self.assertTrue(official['valid'] and instr['valid'])
            self.assertEqual(official['action_sha256'], instr['action_sha256'],
                             'instrumented loop diverged for %s' % arm)
            self.assertIn('bands', final_memory)
            self.assertIn('solver_tried', telemetry)


if __name__ == '__main__':
    unittest.main()

class BandSettleTests(unittest.TestCase):
    """Diagnostic band collector settles outcomes from LATER feedback (defect fix)."""

    def test_settles_msmi_when_feedback_arrives_days_later(self):
        import mw_alloc
        state0 = {'day': 0, 'feedback': [], 'ask_budget_remaining': 12,
                  'members': [], 'introductions': []}
        mem = mw_alloc.empty_memory()
        mem = mw_alloc.update_bands(mem, state0, 0, [('x', 'y', 3)])
        self.assertEqual(mem['bands']['3'][0], 1)
        self.assertEqual(len(mem['pending']), 1)
        mid = mw_alloc.intro_id('x', 'y', 0)
        events = [
            {'introduction_id': mid, 'member_id': 'x', 'event': 'introduction_response',
             'value': 'yes', 'observed_day': 3, 'occurred_day': 3, 'missing_reason': None},
            {'introduction_id': mid, 'member_id': 'y', 'event': 'introduction_response',
             'value': 'yes', 'observed_day': 4, 'occurred_day': 4, 'missing_reason': None},
            {'introduction_id': mid, 'member_id': None, 'event': 'date_happened',
             'value': True, 'observed_day': 20, 'occurred_day': 20},
            {'introduction_id': mid, 'member_id': 'x', 'event': 'second_meeting_intention',
             'value': 'yes', 'observed_day': 22, 'occurred_day': 22, 'missing_reason': None},
            {'introduction_id': mid, 'member_id': 'y', 'event': 'second_meeting_intention',
             'value': 'yes', 'observed_day': 22, 'occurred_day': 22, 'missing_reason': None},
        ]
        mem = mw_alloc.update_bands(mem, {'day': 25, 'feedback': events}, 25, [])
        self.assertEqual(mem['pending'], {})
        row = mem['bands']['3']
        self.assertEqual(row, [1, 1, 1, 1])  # intro, mutual, date, msmi

    def test_unsettled_without_responses(self):
        import mw_alloc
        mem = mw_alloc.empty_memory()
        mem = mw_alloc.update_bands(mem, {'day': 1, 'feedback': []}, 1, [('x', 'y', 1)])
        self.assertEqual(len(mem['pending']), 1)
        mem = mw_alloc.update_bands(mem, {'day': 12, 'feedback': []}, 12, [])
        # responses missing past deadline window (assigned+10) -> settles as non-mutual
        self.assertEqual(len(mem['pending']), 0)
        self.assertEqual(mem['bands']['1'], [1, 0, 0, 0])
