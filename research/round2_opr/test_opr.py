"""Unit tests for research/round2_opr/opr_core.py.

Two layers:
  1. Pure formula tests (weights, drift, deadline enumeration, bounds,
     monotonicity, quadrature convergence).
  2. Equivalence tests: simulate_outcome must reproduce kit.Simulator's
     realized events exactly for randomized worlds and variants.
"""

import math
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import kit
from opr_core import (BASE_WEIGHTS, SHIFT_WEIGHTS, HAPPENED_P, SHARED_SIGMA,
                      SECOND_ON_TIME_P, ACCEPT_BASE, SECOND_BASE, GOAL_MATCH_TERM,
                      DRIFT_THRESHOLD_DAY, DRIFT_TERM, DATE_WINDOW,
                      date_deadline_prob, drift_term, fit_score, members_index,
                      p_msmi, p_msmi_conditional_g, q_second, rand_for, sigmoid,
                      simulate_outcome, z_accept)

VARIANTS = ['development', 'shift', 'drift', 'delayed', 'cold_start', 'sparse']


def adaptive_simpson(f, lo, hi, tol=1e-14, depth=60):
    def simpson(a, b, fa, fm, fb):
        return (b - a) / 6.0 * (fa + 4.0 * fm + fb)

    def rec(a, b, fa, fm, fb, whole, tol, depth):
        m = 0.5 * (a + b)
        lm, rm = 0.5 * (a + m), 0.5 * (m + b)
        flm, frm = f(lm), f(rm)
        left = simpson(a, m, fa, flm, fm)
        right = simpson(m, b, fm, frm, fb)
        delta = left + right - whole
        if depth <= 0 or abs(delta) <= 15.0 * tol:
            return left + right + delta / 15.0
        return (rec(a, m, fa, flm, fm, left, tol / 2, depth - 1)
                + rec(m, b, fm, frm, fb, right, tol / 2, depth - 1))

    fa, fb = f(lo), f(hi)
    fm = f(0.5 * (lo + hi))
    return rec(lo, hi, fa, fm, fb, simpson(lo, hi, fa, fm, fb), tol, depth)


def p_msmi_simpson(m_a, m_b, variant, day):
    sigma = SHARED_SIGMA

    def integrand(z):
        g = sigma * z
        dens = math.exp(-0.5 * z * z) / math.sqrt(2.0 * math.pi)
        return p_msmi_conditional_g(m_a, m_b, variant, day, g) * dens

    return adaptive_simpson(integrand, -7.0, 7.0)


def random_member(rng, ident):
    truth = {k: rng.choice(v) for k, v in kit.OPTIONS.items()}
    return {'member_id': ident, 'pool_id': 't', 'age': rng.randint(21, 46),
            'gender': rng.choice(kit.GENDERS),
            'zone': rng.choice(['zone_a', 'zone_b', 'zone_c', 'zone_d']),
            'arrived_day': 0, 'exit_day': 10000, 'truth': truth,
            'bias': rng.gauss(0, .7), 'response_rate': rng.uniform(.55, .98),
            'second_bias': rng.gauss(0, .5)}


def permissive_fields(member):
    return {'age_min': 18, 'age_max': 65, 'who_to_meet': list(kit.GENDERS),
            'relationship_structure': 'monogamous', 'smoking': 'no',
            'partner_smoking': 'any', 'has_children': False,
            'partner_children': 'any', 'wants_children': 'unsure',
            'acceptable_zones': ['zone_a', 'zone_b', 'zone_c', 'zone_d'],
            'schedule': ['weekday_evening', 'weekend_day', 'weekend_evening']}


class TestSigmoidAndTerms(unittest.TestCase):
    def test_sigmoid_bounds_and_symmetry(self):
        self.assertAlmostEqual(sigmoid(0.0), 0.5, places=15)
        for x in (-3.0, -0.5, 0.25, 2.0):
            self.assertGreater(sigmoid(x), 0.0)
            self.assertLess(sigmoid(x), 1.0)
            self.assertAlmostEqual(sigmoid(x) + sigmoid(-x), 1.0, places=14)

    def test_z_accept_formula(self):
        self.assertEqual(z_accept(0.1, 0.2, 0.3, 0.0), -0.25 + 0.1 + 0.2 + 0.3)
        self.assertEqual(z_accept(0.1, 0.2, 0.3, DRIFT_TERM),
                         -0.25 + 0.1 + 0.2 + 0.3 - 0.5)

    def test_q_second_formula(self):
        self.assertEqual(q_second(0.2, 0.1, True), SECOND_BASE + 0.2 + 0.1 + GOAL_MATCH_TERM)
        self.assertEqual(q_second(0.2, 0.1, False), SECOND_BASE + 0.2 + 0.1)


class TestFitAndDrift(unittest.TestCase):
    def _truth(self, vals):
        return dict(vals)

    def test_fit_default_weights_all_match(self):
        t = {k: 'x' for k in BASE_WEIGHTS}
        self.assertAlmostEqual(fit_score(t, dict(t), 'development'),
                               sum(BASE_WEIGHTS.values()), places=14)

    def test_fit_default_weights_all_mismatch(self):
        a = {k: 'x' for k in BASE_WEIGHTS}
        b = {k: 'y' for k in BASE_WEIGHTS}
        self.assertAlmostEqual(fit_score(a, b, 'development'),
                               -0.5 * sum(BASE_WEIGHTS.values()), places=14)

    def test_fit_shift_weights(self):
        t = {k: 'x' for k in SHIFT_WEIGHTS}
        self.assertAlmostEqual(fit_score(t, dict(t), 'shift'),
                               sum(SHIFT_WEIGHTS.values()), places=14)
        self.assertAlmostEqual(fit_score(t, dict(t), 'development'),
                               sum(BASE_WEIGHTS.values()), places=14)

    def test_fit_partial_match(self):
        a = {'relationship_goal': 'x', 'relationship_pace': 'x',
             'lifestyle': 'x', 'conversations': 'x'}
        b = {'relationship_goal': 'x', 'relationship_pace': 'y',
             'lifestyle': 'x', 'conversations': 'y'}
        expect = .7 * 1 + .4 * -0.5 + .25 * 1 + .2 * -0.5
        self.assertAlmostEqual(fit_score(a, b, 'development'), expect, places=14)

    def test_drift_before_and_after_threshold(self):
        self.assertEqual(drift_term('drift', DRIFT_THRESHOLD_DAY - 1), 0.0)
        self.assertEqual(drift_term('drift', DRIFT_THRESHOLD_DAY), DRIFT_TERM)
        self.assertEqual(drift_term('drift', 100), DRIFT_TERM)
        self.assertEqual(drift_term('development', 100), 0.0)
        self.assertEqual(drift_term('delayed', 100), 0.0)


class TestDeadline(unittest.TestCase):
    def test_nondelayed_is_exactly_one(self):
        for v in ('development', 'shift', 'drift', 'cold_start', 'sparse'):
            self.assertEqual(date_deadline_prob(v), 1.0)

    def test_delayed_bruteforce_independent_enumeration(self):
        hits = total = 0
        for d1 in range(1, 8):
            for d2 in range(1, 8):
                for u in range(1, 15):
                    for v in range(5, 13):
                        total += 1
                        if max(d1, d2) + u + v <= 30:
                            hits += 1
        self.assertAlmostEqual(date_deadline_prob('delayed'), hits / total, places=15)

    def test_delayed_between_zero_and_one_and_strictly_below_one(self):
        d = date_deadline_prob('delayed')
        self.assertGreater(d, 0.5)
        self.assertLess(d, 1.0)   # max offset 33 > 30, so tail exists


class TestPmsmi(unittest.TestCase):
    def setUp(self):
        self.rng = random.Random(7)
        self.a = random_member(self.rng, 'mem_aaaaaaaaaaaaaaaaaaaaaaaaaaa')
        self.b = random_member(self.rng, 'mem_bbbbbbbbbbbbbbbbbbbbbbbbbbb')

    def test_bounds(self):
        for variant in VARIANTS:
            for day in (0, 20, 34, 35, 50):
                p = p_msmi(self.a, self.b, variant, day)
                self.assertGreaterEqual(p, 0.0)
                self.assertLessEqual(p, 1.0)

    def test_positive_for_realistic_attrs(self):
        p = p_msmi(self.a, self.b, 'development', 0)
        self.assertGreater(p, 1e-5)
        self.assertLess(p, 0.2)

    def test_day_only_enters_via_drift(self):
        p_dev_0 = p_msmi(self.a, self.b, 'development', 0)
        p_dev_35 = p_msmi(self.a, self.b, 'development', 35)
        self.assertEqual(p_dev_0, p_dev_35)
        p_drift_34 = p_msmi(self.a, self.b, 'drift', 34)
        p_drift_35 = p_msmi(self.a, self.b, 'drift', 35)
        self.assertAlmostEqual(p_drift_34, p_dev_0, places=12)
        self.assertLess(p_drift_35, p_drift_34)

    def test_monotone_in_bias(self):
        p_lo = p_msmi(self.a, self.b, 'development', 0)
        a2 = dict(self.a, bias=self.a['bias'] + 1.0)
        b2 = dict(self.b, bias=self.b['bias'] + 1.0)
        p_hi = p_msmi(a2, b2, 'development', 0)
        self.assertGreater(p_hi, p_lo)

    def test_monotone_in_response_rate(self):
        p_lo = p_msmi(self.a, self.b, 'development', 0)
        a2 = dict(self.a, response_rate=min(0.999, self.a['response_rate'] + 0.2))
        p_hi = p_msmi(a2, self.b, 'development', 0)
        self.assertGreater(p_hi, p_lo)

    def test_quadrature_convergence_and_independent_simpson(self):
        for variant in ('development', 'delayed', 'shift'):
            p4 = p_msmi(self.a, self.b, variant, 0, n=4001)
            p8 = p_msmi(self.a, self.b, variant, 0, n=8001)
            ps = p_msmi_simpson(self.a, self.b, variant, 0)
            self.assertLess(abs(p8 - p4), 1e-10)
            self.assertLess(abs(p8 - ps), 1e-10)

    def test_conditional_g_direct_formula(self):
        m_a, m_b, variant, day, g = self.a, self.b, 'development', 0, 0.3
        fit = fit_score(m_a['truth'], m_b['truth'], variant)
        goal_match = (m_a['truth']['relationship_goal']
                      == m_b['truth']['relationship_goal'])
        za = -0.25 + m_a['bias'] + fit + g
        zb = -0.25 + m_b['bias'] + fit + g
        qa = 0.15 + m_a['second_bias'] + g + (0.4 if goal_match else 0.0)
        qb = 0.15 + m_b['second_bias'] + g + (0.4 if goal_match else 0.0)
        expect = (m_a['response_rate'] * sigmoid(za)
                  * m_b['response_rate'] * sigmoid(zb)
                  * HAPPENED_P
                  * m_a['response_rate'] * SECOND_ON_TIME_P * sigmoid(qa)
                  * m_b['response_rate'] * SECOND_ON_TIME_P * sigmoid(qb))
        got = p_msmi_conditional_g(m_a, m_b, variant, day, g)
        self.assertAlmostEqual(got, expect, places=15)

    def test_drift_rejects_before_day_35_in_conditional(self):
        g = 0.2
        p34 = p_msmi_conditional_g(self.a, self.b, 'drift', 34, g)
        p35 = p_msmi_conditional_g(self.a, self.b, 'drift', 35, g)
        self.assertLess(p35, p34)


class TestSimulateMatchesKit(unittest.TestCase):
    def _run_one(self, rng):
        seed = rng.randint(1, 10**6)
        variant = rng.choice(VARIANTS)
        day = rng.choice([0, 10, 34, 35, 44])
        ma = random_member(rng, 'mem_' + 'a' * 27)
        mb = random_member(rng, 'mem_' + 'b' * 27)
        for m in (ma, mb):
            m['fields'] = permissive_fields(m)
            m['field_status'] = {k: 'observed' for k in permissive_fields(m)}
            m['field_observed_day'] = {k: 0 for k in permissive_fields(m)}
            m['pool_id'] = 't'
            m['synthetic'] = True
            m['source'] = 'synthetic_questionnaire'
        world = {'schema_version': kit.VERSION, 'synthetic': True, 'seed': seed,
                 'variant': variant, 'pool_id': 't', 'members': [ma, mb]}
        sim = kit.Simulator(world)
        sim.day = day
        a, b = sorted([ma['member_id'], mb['member_id']])
        sim.advance([[a, b]])
        mine = simulate_outcome(seed, a, b, day, variant, members_index(world))
        # metrics() only counts feedback observed by the current day; flush the
        # calendar so future-dated date/second events become observable.
        for _ in range(50):
            sim.advance([])
        events = sim.events
        # intro responses
        resp = sorted([e for e in events if e['event'] == 'introduction_response'],
                      key=lambda e: e['member_id'])
        for idx, e in enumerate(resp):
            responded, accepted = mine['responded'][idx], mine['accepted'][idx]
            if not responded:
                self.assertIsNone(e['value'])
                self.assertEqual(e['missing_reason'], 'no_response')
            else:
                self.assertEqual(e['value'], 'yes' if accepted else 'no')
                self.assertEqual(e['occurred_day'],
                                 day + mine['response_delays'][idx])
        dates = [e for e in events if e['event'] == 'date_happened']
        if mine['date_day'] is None:
            self.assertEqual(dates, [])
        else:
            self.assertEqual(len(dates), 1)
            self.assertEqual(dates[0]['occurred_day'], mine['date_day'])
            self.assertEqual(dates[0]['value'], mine['happened'])
        seconds = sorted([e for e in events if e['event'] == 'second_meeting_intention'],
                         key=lambda e: e['member_id'])
        if mine['second'] is None:
            self.assertEqual(seconds, [])
        else:
            self.assertEqual(len(seconds), 2)
            for idx, e in enumerate(seconds):
                answered, yes, delay = mine['second'][idx]
                if not answered:
                    self.assertIsNone(e['value'])
                    self.assertEqual(e['missing_reason'], 'no_response')
                    self.assertIsNone(e['occurred_day'])
                else:
                    self.assertEqual(e['value'], 'yes' if yes else 'no')
                    self.assertEqual(e['occurred_day'], mine['date_day'] + delay)
        # metric-level agreement
        self.assertEqual(sim.metrics()['mutual_second_meeting_intention'],
                         1 if mine['msmi'] else 0)

    def test_randomized_trials_match(self):
        rng = random.Random(20261012)
        for _ in range(250):
            self._run_one(rng)

    def test_seed_sensitivity_of_stream(self):
        rng = random.Random(99)
        ma = random_member(rng, 'mem_' + 'a' * 27)
        mb = random_member(rng, 'mem_' + 'b' * 27)
        world_members = members_index({'members': [ma, mb]})
        outcomes = {simulate_outcome(s, ma['member_id'], mb['member_id'], 0,
                                     'development', world_members)['msmi']
                    for s in range(1, 40)}
        self.assertLessEqual(len(outcomes), 2)
        # not all seeds identical: stream varies with seed
        raw = [simulate_outcome(s, ma['member_id'], mb['member_id'], 0,
                                'development', world_members)
               for s in range(1, 15)]
        self.assertGreater(len({r['date_day'] for r in raw}), 1)

    def test_rand_for_matches_kit(self):
        for parts in [(1, 'a', 'b', 0), (42, 'x', 'y', 35)]:
            mine = rand_for(*parts)
            theirs = kit.rand_for(*parts)
            self.assertEqual(mine.random(), theirs.random())


if __name__ == '__main__':
    unittest.main()
