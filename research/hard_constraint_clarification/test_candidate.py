"""TDD suite for the hard-constraint clarification allocation candidate (RED first).

Run from repo root:  python -m unittest research.hard_constraint_clarification.test_candidate -v
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import kit
from research.hard_constraint_clarification import candidate_policy as cp


def field_values(zone='zone_a'):
    """Fully observed, mutually compatible default values for every HARD and SOFT field."""
    return {
        'age_min': 25, 'age_max': 40,
        'who_to_meet': ['woman', 'man', 'non_binary'],
        'relationship_structure': 'monogamous',
        'smoking': 'no',
        'partner_smoking': 'any',
        'has_children': False,
        'partner_children': 'any',
        'wants_children': 'unsure',
        'acceptable_zones': [zone],
        'schedule': ['weekday_evening', 'weekend_day', 'weekend_evening'],
        'relationship_goal': 'long_term',
        'relationship_pace': 'steady',
        'lifestyle': 'mixed',
        'conversations': 'ideas',
        'emotional_availability': 'ready',
        'space_for_relationship': 'ample',
        'relocate': 'no',
    }


def mk(mid, *, zone='zone_a', holes=(), declined=(), unavailable=False, gender='woman', age=30, zones=None):
    fields = field_values(zone)
    if zones is not None:
        fields['acceptable_zones'] = list(zones)
    status = {k: 'observed' for k in list(kit.HARD) + list(kit.SOFT)}
    for k in holes:
        fields[k] = None
        status[k] = 'not_asked'
    for k in declined:
        fields[k] = None
        status[k] = 'declined'
    return {'member_id': mid, 'pool_id': 'evaluation', 'synthetic': True, 'age': age,
            'gender': gender, 'zone': zone, 'arrived_day': 0,
            'fields': fields, 'field_status': status,
            'field_observed_day': {k: 0 for k in status},
            'source': 'synthetic_questionnaire', 'available': not unavailable}


def st(members, budget=12, day=0, introductions=None):
    return {'schema_version': '1.0.0', 'day': day, 'ask_budget_remaining': budget,
            'members': members, 'introductions': introductions or [],
            'feedback': [], 'ask_log': []}


def ask_ids(asks):
    return [a['member_id'] for a in asks]


class BudgetAndEligibility(unittest.TestCase):
    def test_budget_cap_never_exceeded(self):
        s = st([mk('mA', holes=('schedule',)), mk('mB', holes=('schedule',))], budget=5)
        self.assertLessEqual(len(cp.hcc_asks(s)), 1)
        s2 = st([mk('mA', holes=('schedule',))], budget=2)
        self.assertEqual(cp.hcc_asks(s2), [])
        s3 = st([mk('mA', holes=('schedule',))], budget=0)
        self.assertEqual(cp.hcc_asks(s3), [])
        s4 = st([mk('m%d' % i, holes=('schedule',)) for i in range(9)], budget=12)
        self.assertLessEqual(len(cp.hcc_asks(s4)), 4)

    def test_all_asks_are_constraints_and_cost_three(self):
        s = st([mk('mA', holes=('schedule',)), mk('mB', holes=('schedule',))])
        asks = cp.hcc_asks(s)
        self.assertTrue(all(a['field'] == 'constraints' for a in asks))
        self.assertLessEqual(3 * len(asks), s['ask_budget_remaining'])

    def test_selected_members_come_from_greedy_eligible_set(self):
        members = [mk('c1', holes=('schedule',)), mk('mA', holes=('age_min',)),
                   mk('dec', holes=('smoking',), declined=('who_to_meet',)),
                   mk('gone', holes=('schedule',), unavailable=True),
                   mk('done')]
        s = st(members, budget=12)
        eligible_ids = set(ask_ids(kit.baseline_asks(s)))
        selected_ids = set(ask_ids(cp.hcc_asks(s)))
        self.assertTrue(selected_ids <= eligible_ids)
        self.assertNotIn('dec', selected_ids)
        self.assertNotIn('gone', selected_ids)
        self.assertNotIn('done', selected_ids)

    def test_never_asks_unavailable_or_declined(self):
        members = [mk('dec', holes=('schedule',), declined=('acceptable_zones',)),
                   mk('gone', holes=('schedule',), unavailable=True)]
        self.assertEqual(cp.hcc_asks(st(members)), [])


class PriorityRule(unittest.TestCase):
    """c1 sits first in list order (greedy would ask it first) but unlocks nothing."""

    def fixture(self, budget=12):
        members = [
            mk('c1', holes=('schedule',), zone='zone_c', zones=['zone_c']),  # zero potential
            mk('mA', holes=('schedule',)),                                   # unlocks p1,p2 (zone_a)
            mk('mB', holes=('smoking',), zone='zone_b', zones=['zone_b']),   # unlocks p3 (zone_b)
            mk('p1'), mk('p2'),                                              # complete, zone_a
            mk('p3', zone='zone_b'),                                         # complete, zone_b
        ]
        return st(members, budget=budget)

    def test_priority_orders_by_unlock_not_list_order(self):
        s = self.fixture()
        self.assertEqual(ask_ids(kit.baseline_asks(s)), ['c1', 'mA', 'mB'])   # greedy = state order
        got = ask_ids(cp.hcc_asks(s))
        self.assertEqual(got, ['mA', 'mB', 'c1'])                             # same members+count, new order

    def test_budget_5_selects_single_best(self):
        s = self.fixture(budget=5)
        self.assertEqual(ask_ids(cp.hcc_asks(s)), ['mA'])
        self.assertEqual(ask_ids(kit.baseline_asks(s)), ['c1'])   # intervention differs from greedy

    def test_zero_scores_fall_back_to_greedy_order_and_count(self):
        members = [mk('z2', holes=('schedule',), zone='zone_c', zones=['zone_c']),
                   mk('z1', holes=('age_min',), zone='zone_q', zones=['zone_q']),
                   mk('z3', holes=('smoking',), zone='zone_r', zones=['zone_r']),
                   mk('p1')]
        s = st(members, budget=12)
        self.assertEqual(cp.hcc_asks(s), kit.baseline_asks(s))

    def test_priority_false_is_exactly_greedy(self):
        s = self.fixture()
        self.assertEqual(cp.hcc_asks(s, priority=False), kit.baseline_asks(s))


class MarginalAccounting(unittest.TestCase):
    def fixture(self, budget=6):
        members = [mk('m1', holes=('schedule',)), mk('m2', holes=('smoking',)), mk('p1')]
        return st(members, budget=budget)

    def test_second_selection_does_not_recount_shared_pair(self):
        s = self.fixture()
        trace = cp.selection_trace(s)
        # shared pair {m1,m2}: inform(m1)=2 ({m1,p1},{m1,m2}); after m1 picked, m2 marginal inform=1
        self.assertEqual(trace[0]['member_id'], 'm1')
        self.assertEqual(trace[0]['inform_marginal'], 2)
        self.assertEqual(trace[1]['member_id'], 'm2')
        self.assertEqual(trace[1]['inform_marginal'], 1)
        self.assertEqual(trace[1]['unlock_marginal'], 1)      # {m2,p1} untouched by m1

    def test_unlock_sets_are_disjoint_across_members(self):
        s = self.fixture()
        trace = cp.selection_trace(s)
        keys = [frozenset(tuple(t['pair_keys_unlocked']) for t in [t]) for t in trace]
        flat = [set(tuple(p) for p in t['pair_keys_unlocked']) for t in trace]
        for i in range(len(flat)):
            for j in range(i + 1, len(flat)):
                self.assertFalse(flat[i] & flat[j])
        self.assertTrue(keys)  # trace non-empty sanity


class UnknownAndDeclinedHandling(unittest.TestCase):
    def test_unknown_partner_counted_as_potential_not_incompatible(self):
        # pU has not-asked hard info: pair is needs_clarification -> potential (inform), not unlock
        members = [mk('mA', holes=('schedule',)), mk('pU', holes=('age_min',))]
        s = st(members, budget=12)
        trace = cp.selection_trace(s)
        self.assertEqual(trace[0]['member_id'], 'mA')
        self.assertEqual(trace[0]['inform_marginal'], 1)       # {mA,pU} counted
        self.assertEqual(trace[0]['unlock_marginal'], 0)       # pU incomplete -> not resolved-by-ask

    def test_declined_partner_pair_not_counted_as_potential(self):
        members = [mk('mA', holes=('schedule',)), mk('pD', declined=('has_children',))]
        s = st(members, budget=12)
        self.assertEqual(cp.selection_trace(s), [])            # permanently unresolvable -> zero potential
        self.assertEqual(cp.hcc_asks(s), kit.baseline_asks(s))  # leftover slots filled in greedy order

    def test_known_incompatible_pairs_excluded(self):
        members = [mk('mI', holes=('schedule',), zone='zone_z', zones=['zone_z']),
                   mk('p1', zone='zone_a'), mk('p2', zone='zone_a')]
        s = st(members, budget=12)
        self.assertEqual(cp.selection_trace(s), [])            # geography failures -> no potential
        self.assertEqual(cp.hcc_asks(s), kit.baseline_asks(s))


class ProtocolSurface(unittest.TestCase):
    def test_match_phase_identical_to_baseline_match(self):
        s = st([mk('a', holes=('schedule',)), mk('b')])
        for mode in ('greedy', 'unlock'):
            req = {'schema_version': '1.0.0', 'phase': 'match', 'state': s, 'memory': {'x': 1}}
            out = cp.decide(req, mode=mode)
            self.assertEqual(out['pairs'], kit.baseline_match(s))
            self.assertEqual(out['memory'], {'x': 1})

    def test_greedy_mode_asks_identical_to_kit(self):
        s = st([mk('c1', holes=('schedule',)), mk('mA', holes=('age_min',))])
        req = {'schema_version': '1.0.0', 'phase': 'ask', 'state': s, 'memory': None}
        self.assertEqual(cp.decide(req, mode='greedy')['asks'], kit.baseline_asks(s))

    def test_deterministic(self):
        s = st([mk('mA', holes=('schedule',)), mk('mB', holes=('smoking',)), mk('p1')])
        self.assertEqual(cp.hcc_asks(s), cp.hcc_asks(s))
        self.assertEqual(cp.selection_trace(s), cp.selection_trace(s))

    def test_source_has_no_truth_or_model_access(self):
        src = Path(cp.__file__).read_text(encoding='utf-8')
        for token in ("'truth'", '"truth"', 'response_rate', 'second_bias',
                      'exit_day', 'propensity', 'MODEL_B64', 'load_model', 'world['):
            self.assertNotIn(token, src, 'forbidden token %r in candidate source' % token)


if __name__ == '__main__':
    unittest.main()