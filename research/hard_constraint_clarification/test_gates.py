"""TDD suite for pilot_gates.py (frozen protocol section 8). Run from repo root:
python -m unittest research.hard_constraint_clarification.test_gates -v
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from research.hard_constraint_clarification import pilot_gates as pg


def rx_key(arm, seed, variant):
    return '%s__%s__%s' % (arm, seed, variant)


def rec(arm, seed, variant, sha, valid=True, elapsed=1.0):
    return {'key': rx_key(arm, seed, variant), 'phase': 'pilot', 'arm': arm, 'seed': seed,
            'variant': variant, 'exit_code': 0, 'elapsed_s': elapsed, 'valid': valid,
            'row': {'seed': seed, 'variant': variant, 'valid': valid,
                    'action_sha256': sha, 'msmi_per_100_arrived_members': 0.4,
                    'ask_cost': 200, 'assignments': 30, 'mutual_acceptances': 10,
                    'dates': 8, 'mutual_second_meeting_intention': 5}}


def ask_line(day, budget, n_eligible, n_asks, mode='unlock', trace=None, ids=None):
    if ids is None:
        ids = ['m%d' % i for i in range(n_asks)]
    return {'day': day, 'mode': mode, 'budget_remaining': budget, 'n_eligible': n_eligible,
            'n_asks': n_asks, 'spent': 3 * n_asks,
            'asks': [{'member_id': i, 'field': 'constraints'} for i in ids],
            'trace': trace or []}


class GateG1Parity(unittest.TestCase):
    def test_all_matching_passes(self):
        recs = [rec('greedy_official', 119001, 'development', 'aaa'),
                rec('greedy', 119001, 'development', 'aaa'),
                rec('greedy_official', 119001, 'drift', 'bbb'),
                rec('greedy', 119001, 'drift', 'bbb')]
        ok, bad = pg.gate_g1(recs)
        self.assertTrue(ok)
        self.assertEqual(bad, [])

    def test_single_mismatch_fails_and_is_named(self):
        recs = [rec('greedy_official', 119001, 'development', 'aaa'),
                rec('greedy', 119001, 'development', 'zzz')]
        ok, bad = pg.gate_g1(recs)
        self.assertFalse(ok)
        self.assertEqual(bad, [(119001, 'development')])

    def test_missing_counterpart_fails(self):
        recs = [rec('greedy_official', 119001, 'development', 'aaa')]
        ok, bad = pg.gate_g1(recs)
        self.assertFalse(ok)


class GateG2Determinism(unittest.TestCase):
    def test_identical_replay_passes(self):
        self.assertTrue(pg.gate_g2([rec('unlock', 119001, 'development', 'aaa')],
                                   [rec('unlock', 119001, 'development', 'aaa')])[0])

    def test_different_sha_fails(self):
        ok, bad = pg.gate_g2([rec('unlock', 119001, 'development', 'aaa')],
                             [rec('unlock', 119001, 'development', 'bbb')])
        self.assertFalse(ok)

    def test_different_metric_fails(self):
        a = rec('unlock', 119001, 'development', 'aaa')
        b = rec('unlock', 119001, 'development', 'aaa')
        b['row']['ask_cost'] = 999
        self.assertFalse(pg.gate_g2([a], [b])[0])

    def test_missing_replay_fails(self):
        self.assertFalse(pg.gate_g2([rec('unlock', 119001, 'development', 'aaa')], [])[0])


class GateG3Validity(unittest.TestCase):
    def test_all_valid_passes(self):
        self.assertTrue(pg.gate_g3([rec('unlock', 1, 'development', 'a')])[0])

    def test_invalid_fails(self):
        r = rec('unlock', 1, 'development', 'a', valid=False)
        ok, bad = pg.gate_g3([r])
        self.assertFalse(ok)
        self.assertEqual(bad, [r['key']])

    def test_empty_fails(self):
        self.assertFalse(pg.gate_g3([])[0])


class GateG4Budget(unittest.TestCase):
    def test_legal_days_pass(self):
        lines = [ask_line(0, 12, 6, 4), ask_line(1, 12, 2, 2), ask_line(2, 5, 9, 1),
                 ask_line(3, 3, 0, 0)]
        ok, bad = pg.gate_g4([lines])
        self.assertTrue(ok, bad)

    def test_over_budget_fails(self):
        ok, bad = pg.gate_g4([[ask_line(0, 12, 6, 5)]])
        self.assertFalse(ok)
        self.assertEqual(bad[0][1], 'over_budget')

    def test_wrong_count_vs_eligible_fails(self):
        ok, bad = pg.gate_g4([[ask_line(0, 12, 3, 4)]])
        self.assertFalse(ok)
        self.assertEqual(bad[0][1], 'count_mismatch')

    def test_budget_out_of_range_fails(self):
        ok, bad = pg.gate_g4([[ask_line(0, 13, 6, 4)]])
        self.assertFalse(ok)
        self.assertEqual(bad[0][1], 'budget_range')


class GateG5Intervention(unittest.TestCase):
    def test_day0_divergence_plus_positive_trace_passes(self):
        uline = ask_line(0, 12, 6, 2, mode='unlock',
                         trace=[{'member_id': 'm9', 'unlock_marginal': 3,
                                 'inform_marginal': 5,
                                 'pair_keys_unlocked': [['m9', 'p1']]}],
                         ids=['m9', 'm0'])
        u = {('unlock', 119001, 'development'): [uline]}
        g = {('greedy', 119001, 'development'): [ask_line(0, 12, 6, 2, mode='greedy')]}
        ok, why = pg.gate_g5(u, g)
        self.assertTrue(ok, why)

    def test_identical_day0_fails(self):
        u = {('unlock', 119001, 'development'): [ask_line(0, 12, 6, 2)]}
        g = {('greedy', 119001, 'development'): [ask_line(0, 12, 6, 2)]}
        self.assertFalse(pg.gate_g5(u, g)[0])

    def test_divergence_without_positive_trace_fails(self):
        uline = ask_line(0, 12, 6, 2, ids=['mZ', 'mY'])
        u = {('unlock', 119001, 'development'): [uline]}
        g = {('greedy', 119001, 'development'): [ask_line(0, 12, 6, 2)]}
        self.assertFalse(pg.gate_g5(u, g)[0])

    def test_no_shared_pairs_fails(self):
        u = {('unlock', 119001, 'development'): [ask_line(0, 12, 6, 2)]}
        self.assertFalse(pg.gate_g5(u, {})[0])


class GateG7Runtime(unittest.TestCase):
    def test_projection_within_budget_passes(self):
        ok, info = pg.gate_g7({'greedy': 20.0, 'unlock': 20.0, 'greedy_official': 20.0},
                              now='2026-10-16 18:00', cutoff='2026-10-17 18:00')
        self.assertTrue(ok, info)

    def test_projection_over_cap_fails(self):
        ok, info = pg.gate_g7({'greedy': 60.0, 'unlock': 60.0, 'greedy_official': 60.0},
                              now='2026-10-16 18:00', cutoff='2026-10-17 18:00')
        self.assertFalse(ok)


if __name__ == '__main__':
    unittest.main()