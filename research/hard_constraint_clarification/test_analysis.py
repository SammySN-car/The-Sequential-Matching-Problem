"""TDD suite for analyze_results.py - implements frozen protocol section 6 and 10.

Run from repo root:  python -m unittest research.hard_constraint_clarification.test_analysis -v
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from research.hard_constraint_clarification import analyze_results as ar

VARIANTS = ('development', 'sparse', 'cold_start', 'delayed', 'shift', 'drift')


def ep(arm, seed, variant, msmi100, ask=200, valid=True, sha='x'):
    return {'key': '%s__%s__%s' % (arm, seed, variant), 'phase': 'confirmatory',
            'arm': arm, 'seed': seed, 'variant': variant, 'exit_code': 0,
            'elapsed_s': 16.0, 'valid': valid,
            'row': {'seed': seed, 'variant': variant, 'valid': valid,
                    'action_sha256': sha, 'msmi_per_100_arrived_members': msmi100,
                    'ask_cost': ask, 'assignments': 100, 'mutual_acceptances': 9,
                    'dates': 6, 'mutual_second_meeting_intention': 3, 'coverage': 0.35,
                    'inference_seconds': 12.0, 'arrived_members': 200}}


def arm_grid(arm, seeds, fn):
    return [ep(arm, s, v, fn(s, v)) for s in seeds for v in VARIANTS]


class GroupScores(unittest.TestCase):
    def test_mean_over_six_variants_and_arm_filter(self):
        recs = arm_grid('unlock', [1], lambda s, v: 1.0)
        recs += arm_grid('greedy', [1], lambda s, v: 3.0)
        recs += [ep('greedy_official', 1, 'development', 99.0)]
        u = ar.group_scores(recs, 'unlock')
        g = ar.group_scores(recs, 'greedy')
        self.assertEqual(u[1], 1.0)
        self.assertEqual(g[1], 3.0)
        self.assertNotIn(1, ar.group_scores(recs, 'greedy_official'))

    def test_incomplete_seed_excluded_and_reported(self):
        recs = arm_grid('unlock', [1, 2], lambda s, v: 1.0)
        recs = [r for r in recs if not (r['seed'] == 2 and r['variant'] == 'drift')]
        scores, missing = ar.group_scores(recs, 'unlock', require_all=True)
        self.assertIn(1, scores)
        self.assertNotIn(2, scores)
        self.assertEqual(missing, [(2, 'drift')])

    def test_invalid_episode_not_counted(self):
        recs = arm_grid('unlock', [1], lambda s, v: 1.0)
        recs[0]['valid'] = False
        scores, missing = ar.group_scores(recs, 'unlock', require_all=True)
        self.assertNotIn(1, scores)
        self.assertEqual(missing[0][0], 1)


class PairedDeltas(unittest.TestCase):
    def test_delta_only_over_joint_complete_groups(self):
        g = {1: 1.0, 2: 5.0}
        u = {1: 1.5, 3: 9.0}
        deltas = ar.paired_deltas(g, u)
        self.assertEqual(deltas, {1: 0.5})


class Bootstrap(unittest.TestCase):
    def test_constant_deltas_degenerate_ci(self):
        lo, hi = ar.bootstrap_ci([2.0] * 10, B=500, seed=20261016)
        self.assertEqual(lo, 2.0)
        self.assertEqual(hi, 2.0)

    def test_ci_brackets_mean_and_ordered(self):
        deltas = [-1.0, 0.0, 1.0, 2.0, 3.0, 0.5]
        m = sum(deltas) / len(deltas)
        lo, hi = ar.bootstrap_ci(deltas, B=1000, seed=7)
        self.assertLessEqual(lo, m)
        self.assertLessEqual(m, hi)
        self.assertLessEqual(lo, hi)

    def test_reproducible_given_seed(self):
        deltas = [0.1, -0.2, 0.4, 0.0, -0.05]
        self.assertEqual(ar.bootstrap_ci(deltas, B=500, seed=5),
                         ar.bootstrap_ci(deltas, B=500, seed=5))

    def test_empty_is_none(self):
        self.assertEqual(ar.bootstrap_ci([], B=100, seed=1), (None, None))


class VariantStats(unittest.TestCase):
    def test_per_variant_means_and_delta(self):
        g = arm_grid('greedy', [1, 2], lambda s, v: 1.0)
        u = arm_grid('unlock', [1, 2], lambda s, v: 1.0)
        for r in u:
            if r['variant'] == 'development':
                r['row']['msmi_per_100_arrived_members'] = 2.0
        stats = ar.variant_stats(g, u, seeds=[1, 2])
        self.assertAlmostEqual(stats['development']['greedy'], 1.0)
        self.assertAlmostEqual(stats['development']['unlock'], 2.0)
        self.assertAlmostEqual(stats['development']['delta'], 1.0)
        self.assertAlmostEqual(stats['sparse']['delta'], 0.0)
        self.assertEqual(set(stats), set(VARIANTS))


class Verdict(unittest.TestCase):
    def base(self, **kw):
        args = dict(complete_groups=100, planned_groups=100, invalid_count=0,
                    spot_ok=True, mean_delta=0.05, ci=(0.01, 0.09),
                    variant_deltas={v: 0.01 for v in VARIANTS})
        args.update(kw)
        return ar.verdict(**args)

    def test_promising_when_all_conditions_hold(self):
        v, reasons = self.base()
        self.assertEqual(v, 'PROMISING — REVIEW REQUIRED')

    def test_inconclusive_when_ci_spans_zero(self):
        self.assertEqual(self.base(ci=(-0.02, 0.11))[0], 'INCONCLUSIVE')

    def test_inconclusive_when_incomplete_coverage(self):
        self.assertEqual(self.base(complete_groups=97)[0], 'INCONCLUSIVE')

    def test_stop_on_invalid(self):
        self.assertEqual(self.base(invalid_count=1)[0], 'STOP')

    def test_stop_on_spot_mismatch(self):
        self.assertEqual(self.base(spot_ok=False)[0], 'STOP')

    def test_inconclusive_negative_mean(self):
        self.assertEqual(self.base(mean_delta=-0.02, ci=(-0.1, 0.05))[0], 'INCONCLUSIVE')

    def test_inconclusive_when_variant_regression_too_wide(self):
        vd = {v: 0.01 for v in VARIANTS}
        vd['drift'] = -0.5
        vd['delayed'] = -0.4
        vd['shift'] = -0.3
        self.assertEqual(self.base(variant_deltas=vd)[0], 'INCONCLUSIVE')

    def test_inconclusive_when_ci_touches_zero(self):
        self.assertEqual(self.base(ci=(0.0, 0.1))[0], 'INCONCLUSIVE')

    def test_stop_reasons_recorded(self):
        v, reasons = self.base(invalid_count=2)
        self.assertTrue(any('invalid' in r for r in reasons))


class Diagnostics(unittest.TestCase):
    def test_episode_diagnostics_aggregates(self):
        recs = [ep('unlock', 1, 'development', 2.0, ask=300),
                ep('unlock', 1, 'sparse', 4.0, ask=100)]
        d = ar.episode_diagnostics(recs)
        self.assertEqual(d['episodes'], 2)
        self.assertEqual(d['valid'], 2)
        self.assertEqual(d['ask_cost_mean'], 200.0)
        self.assertEqual(d['msmi_count_mean'], 3.0)
        self.assertEqual(d['assignments_mean'], 100.0)

    def test_ask_summary_fractions_and_recipients(self):
        lines = [{'day': 0, 'budget_remaining': 12, 'n_eligible': 6, 'n_asks': 4,
                  'spent': 12,
                  'asks': [{'member_id': 'm1', 'field': 'constraints'},
                           {'member_id': 'm2', 'field': 'constraints'},
                           {'member_id': 'm3', 'field': 'constraints'},
                           {'member_id': 'm4', 'field': 'constraints'}],
                  'trace': [{'member_id': 'm1', 'unlock_marginal': 3,
                             'inform_marginal': 5, 'pair_keys_unlocked': [['m1', 'p1']]}]},
                 {'day': 1, 'budget_remaining': 12, 'n_eligible': 2, 'n_asks': 2,
                  'spent': 6,
                  'asks': [{'member_id': 'm2', 'field': 'constraints'},
                           {'member_id': 'm5', 'field': 'constraints'}],
                  'trace': []}]
        lines_b = [{'day': 0, 'budget_remaining': 12, 'n_eligible': 1, 'n_asks': 0,
                    'spent': 0, 'asks': [], 'trace': []}]
        s = ar.ask_summary({('unlock', 1, 'development'): lines,
                            ('unlock', 1, 'sparse'): lines_b})
        self.assertEqual(s['episodes'], 2)
        self.assertEqual(s['total_asks'], 6)
        self.assertEqual(s['budget_fraction'], 18.0 / (720.0 * 2))
        self.assertEqual(s['distinct_recipients'], 5)
        self.assertEqual(s['potential_unlock_sum'], 3)
        self.assertEqual(s['potential_inform_sum'], 5)
        self.assertEqual(s['mean_asks_per_day'], 2.0)

    def test_ask_summary_empty(self):
        s = ar.ask_summary({})
        self.assertEqual(s['total_asks'], 0)
        self.assertEqual(s['budget_fraction'], 0.0)


if __name__ == '__main__':
    unittest.main()