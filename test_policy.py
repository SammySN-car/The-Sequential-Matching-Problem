"""A+C policy tests (CI-safe: stdlib + kit + research.features only)."""
import base64
import json
import math
import zlib
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent
for p in (str(REPO_ROOT), str(REPO_ROOT / 'research')):
    if p not in sys.path:
        sys.path.insert(0, p)

import kit
import policy


def make_member(mid, available=True, age=30, zone='z1', gender='woman',
                arrived=0, hard_complete=True, soft_goal='long_term',
                soft_pace='steady', ask_status='not_asked'):
    fields = {
        'age_min': 21, 'age_max': 46, 'who_to_meet': ['woman', 'man', 'non_binary'],
        'relationship_structure': 'monogamous', 'smoking': 'no',
        'partner_smoking': 'any', 'has_children': False, 'partner_children': 'any',
        'wants_children': 'unsure', 'acceptable_zones': ['z1', 'z2', 'z3'],
        'schedule': ['weekday_evening', 'weekend_day', 'weekend_evening'],
        'relationship_goal': soft_goal, 'relationship_pace': soft_pace,
        'lifestyle': 'mixed', 'conversations': 'ideas',
        'emotional_availability': 'ready', 'space_for_relationship': 'moderate',
        'relocate': 'unsure'}
    status = {k: 'observed' for k in fields}
    observed_day = {k: 0 for k in fields}
    if not hard_complete:
        for k in kit.HARD[:3]:
            fields[k] = None
            status[k] = ask_status
            observed_day[k] = None
    for key, val in (('relationship_goal', soft_goal), ('relationship_pace', soft_pace)):
        if val is None:
            fields[key] = None
            status[key] = 'not_asked'
            observed_day[key] = None
    return {'member_id': mid, 'pool_id': 'p', 'age': age, 'gender': gender,
            'zone': zone, 'arrived_day': arrived, 'available': available,
            'fields': fields, 'field_status': status,
            'field_observed_day': observed_day, 'source': 'synthetic_questionnaire'}


def make_state(members, day=1, budget=12, introductions=None, feedback=None):
    return {'schema_version': '1.0.0', 'synthetic': True, 'day': day,
            'ask_budget_remaining': budget, 'members': members,
            'introductions': introductions or [], 'feedback': feedback or [],
            'ask_log': []}


def encode_blob(obj):
    """The runtime blob contract: JSON -> zlib -> base64 (must match exporter and load_model)."""
    return base64.b64encode(
        zlib.compress(json.dumps(obj, separators=(',',':')).encode('utf-8'), 9)).decode('ascii')


def decode_blob(blob):
    """Inverse of encode_blob; tests use it to build/assert on decoded objects."""
    return json.loads(zlib.decompress(base64.b64decode(blob.encode('ascii'))).decode('utf-8'))


def toy_obj():
    """One split on feature 0 at 0.5; leaves +1/-1; NaN -> left (missing_left=1)."""
    return {
        'schema': 1, 'n_features': 44, 'feature_keys': ['f%d' % i for i in range(44)],
        'floor': 0.5, 'baseline': 0.0, 'n_iter': 1,
        'trees': [[[0, 0.5, 1, 2, 1], [1.0], [-1.0]]]}


def toy_blob():
    """Toy model encoded with the REAL runtime encoding (not plain JSON)."""
    return encode_blob(toy_obj())


class ModelPackageTests(unittest.TestCase):
    def test_load_model_parses_valid_toy_blob(self):
        with mock.patch.object(policy, 'MODEL_B64', toy_blob()):
            model = policy.load_model()
        self.assertIsNotNone(model)
        self.assertEqual(model['schema'], 1)
        self.assertEqual(model['n_features'], 44)
        self.assertEqual(len(model['feature_keys']), 44)
        self.assertEqual(model['floor'], 0.5)
        self.assertEqual(model['n_iter'], 1)
        self.assertEqual(model['n_iter'], len(model['trees']))

    def test_load_model_rejects_garbage_and_empty(self):
        with mock.patch.object(policy, 'MODEL_B64', 'not-zlib-data'):
            self.assertIsNone(policy.load_model())
        with mock.patch.object(policy, 'MODEL_B64', ''):
            self.assertIsNone(policy.load_model())

    def test_load_model_rejects_wrong_schema(self):
        # decode must SUCCEED first: rejection must come from schema validation, not decoding
        good = decode_blob(toy_blob())              # proves the encoding roundtrip
        self.assertEqual(good['n_features'], 44)
        self.assertEqual(good['n_iter'], len(good['trees']))
        bad = decode_blob(toy_blob())
        bad['n_features'] = 43
        with mock.patch.object(policy, 'MODEL_B64', encode_blob(bad)):
            self.assertIsNone(policy.load_model())
        bad = decode_blob(toy_blob())
        bad['floor'] = float('nan')
        with mock.patch.object(policy, 'MODEL_B64', encode_blob(bad)):
            self.assertIsNone(policy.load_model())
        bad = decode_blob(toy_blob())
        bad['n_iter'] = len(bad['trees']) + 1    # n_iter/tree-count mismatch
        with mock.patch.object(policy, 'MODEL_B64', encode_blob(bad)):
            self.assertIsNone(policy.load_model())

    def test_walk_threshold_semantics_and_nan_branch(self):
        tree = [[0, 0.5, 1, 2, 1], [1.0], [-1.0]]
        self.assertEqual(policy._walk(tree, [0.4]), 1.0)
        self.assertEqual(policy._walk(tree, [0.5]), 1.0)   # <= goes left
        self.assertEqual(policy._walk(tree, [0.9]), -1.0)
        self.assertEqual(policy._walk(tree, [float('nan')]), 1.0)
        tree2 = [[0, 0.5, 1, 2, 0], [1.0], [-1.0]]
        self.assertEqual(policy._walk(tree2, [float('nan')]), -1.0)

    def test_score_row_is_sigmoid_of_baseline_plus_sum(self):
        model = {'schema': 1, 'n_features': 44, 'feature_keys': ['f'] * 44,
                 'floor': 0.0, 'baseline': 0.0,
                 'trees': [[[0, 0.5, 1, 2, 0], [1.0], [-1.0]],
                           [[0, 0.5, 1, 2, 0], [1.0], [-1.0]]]}
        x = [0.4] + [0.0] * 43
        self.assertAlmostEqual(policy.score_row(model, x), 1.0 / (1.0 + math.exp(-2.0)), places=15)
        x = [0.9] + [0.0] * 43
        self.assertAlmostEqual(policy.score_row(model, x), 1.0 / (1.0 + math.exp(2.0)), places=15)

    def test_sigmoid_branches_for_extremes(self):
        self.assertEqual(policy._sigmoid(0.0), 0.5)
        self.assertEqual(policy._sigmoid(700.0), 1.0)
        self.assertGreater(policy._sigmoid(-700.0), 0.0)
        self.assertLess(policy._sigmoid(-700.0), 1e-300)

    def test_marker_region_present_in_policy_source(self):
        src = (REPO_ROOT / 'policy.py').read_text(encoding='utf-8')
        self.assertIn('# BEGIN GENERATED MODEL BLOB', src)
        self.assertIn('# END GENERATED MODEL BLOB', src)

    def test_toy_blob_follows_runtime_encoding_contract(self):
        # blob is exactly base64(zlib(JSON)) - the encoding load_model and the exporter both use
        obj = toy_obj()
        blob = toy_blob()
        self.assertEqual(
            json.loads(zlib.decompress(base64.b64decode(blob.encode('ascii'))).decode('utf-8')),
            obj)
        with mock.patch.object(policy, 'MODEL_B64', blob):
            self.assertIsNotNone(policy.load_model())


if __name__ == '__main__':
    unittest.main()

class ExportInjectTests(unittest.TestCase):
    def test_inject_replaces_only_marker_region_and_is_idempotent(self):
        from export_model import inject_blob
        src = ('HEAD\n# BEGIN GENERATED MODEL BLOB\n'
               "MODEL_B64 = 'old'\n"
               '# END GENERATED MODEL BLOB\nTAIL\n')
        once = inject_blob(src, 'QUJD')
        self.assertTrue(once.startswith('HEAD\n# BEGIN GENERATED MODEL BLOB'))
        self.assertTrue(once.endswith('# END GENERATED MODEL BLOB\nTAIL\n'))
        self.assertIn("MODEL_B64 = 'QUJD'", once)
        self.assertNotIn("'old'", once)
        self.assertEqual(once, inject_blob(once, 'QUJD'))

    def test_inject_without_markers_raises(self):
        from export_model import inject_blob
        with self.assertRaises(ValueError):
            inject_blob('no markers here', 'QUJD')

class RealBlobGuardTests(unittest.TestCase):
    """T4: real embedded blob well-formed; decodes with stdlib only (CI has no sklearn)."""

    def test_t4_real_blob_well_formed(self):
        src = (REPO_ROOT / 'policy.py').read_text(encoding='utf-8')
        begin = src.index('# BEGIN GENERATED MODEL BLOB')
        end = src.index('# END GENERATED MODEL BLOB')
        region = src[begin:end]
        self.assertIn("MODEL_B64 = '", region)
        model = policy.load_model()
        self.assertIsNotNone(model, 'real blob must decode with stdlib only')
        self.assertEqual(model['schema'], 1)
        self.assertEqual(model['n_features'], 44)
        self.assertEqual(len(model['feature_keys']), 44)
        import features
        self.assertEqual(model['feature_keys'], features.FEATURE_KEYS)
        self.assertTrue(math.isfinite(model['floor']) and model['floor'] > 0.0)
        self.assertTrue(1 <= model['n_iter'] <= 200)

        self.assertEqual(model['n_iter'], len(model['trees']))
        for tree in model['trees']:
            for node in tree:
                self.assertIn(len(node), (1, 5))

class FeatureParityTests(unittest.TestCase):
    """T3: policy feature block == research features.py, elementwise (NaN == NaN)."""

    @staticmethod
    def _capture_states():
        states = []
        for seed, variant in ((7, 'development'), (8, 'cold_start'), (9, 'sparse')):
            sim = kit.Simulator(kit.generate(seed, 60, variant=variant))
            for day in range(46):
                state = sim.observe()
                if day in (0, 5, 11, 45):   # day 45 exercises late-episode masking
                    states.append(state)
                sim.resolve_asks(kit.baseline_asks(state))
                sim.advance(kit.baseline_match(sim.observe()))
        return states

    @staticmethod
    def _same(a, b):
        if isinstance(a, float) and isinstance(b, float) and a != a and b != b:
            return True
        return a == b

    def test_t3_feature_keys_order_identical(self):
        import features
        self.assertEqual(policy.FEATURE_KEYS, features.FEATURE_KEYS)

    def test_t3_pair_features_identical_across_variants_and_days(self):
        import itertools
        import features
        checked = 0
        for state in self._capture_states():
            t = state['day']
            ids = [m['member_id'] for m in state['members']]
            pairs = list(itertools.combinations(ids, 2))
            sample = pairs[:5]
            for a, b in pairs[5:300]:
                ma = next(m for m in state['members'] if m['member_id'] == a)
                mb = next(m for m in state['members'] if m['member_id'] == b)
                if kit.eligibility(ma, mb)['status'] == 'feasible':
                    sample.append((a, b))
                    break
            for a, b in sample:
                mine = policy.pair_features(state, a, b, t)
                theirs = features.pair_features(state, a, b, t)
                self.assertEqual(list(mine), list(theirs))
                for key in policy.FEATURE_KEYS:
                    self.assertTrue(self._same(mine[key], theirs[key]),
                                    'day %s pair %s key %s: %r != %r'
                                    % (t, (a, b), key, mine[key], theirs[key]))
                checked += 1
        self.assertGreaterEqual(checked, 24)  # 3 variants x 4 days (incl. day 45) x >=2 pairs


class ResearchRowParityTests(unittest.TestCase):
    """Stored research rows.csv == policy.pair_features on replayed simulator states."""

    def test_research_stored_rows_match_policy_features_on_replay(self):
        import csv as _csv
        from collect import RandomCollector
        rows_path = REPO_ROOT / 'research' / 'out_scale800' / 'rows.csv'
        if not rows_path.exists():
            raise unittest.SkipTest('research/out_scale800/rows.csv not present')
        # rows.csv is canonically sorted; take the first 3 rollouts' day<=15 rows
        keys, stored = [], {}
        with rows_path.open(newline='', encoding='utf-8') as fh:
            for rec in _csv.DictReader(fh):
                if int(rec['day']) > 15:
                    continue
                key = (int(rec['world_seed']), rec['variant'], rec['policy'],
                       int(rec['collector_seed']))
                if key not in stored:
                    if len(keys) >= 3:
                        break
                    keys.append(key)
                    stored[key] = {}
                stored[key][(int(rec['day']), rec['a'], rec['b'])] = rec
        self.assertTrue(keys, 'rows.csv has no day<=15 rows')
        checked = 0
        for wseed, variant, pol, cseed in keys:
            rollout = (wseed, variant, pol, cseed)
            world = kit.generate(wseed, 200, 'research', variant)
            sim = kit.Simulator(world)
            collector = RandomCollector(seed=cseed) if pol == 'random' else None
            replayed = {}
            for t in range(16):   # exactly collect_rows' per-day mechanics, day 0..15
                state = sim.observe()
                asks = collector.asks(state) if collector else kit.baseline_asks(state)
                sim.resolve_asks(asks)
                state = sim.observe()
                pairs = collector.match(state) if collector else kit.baseline_match(state)
                for pair in pairs:
                    a, b = sorted(pair)
                    replayed[(t, a, b)] = policy.pair_features(state, a, b, t)
                sim.advance(pairs)
            want = stored[rollout]
            self.assertEqual(set(want), set(replayed),
                             'stored vs replayed (day, a, b) mismatch for %r' % (rollout,))
            for rkey, feats in sorted(replayed.items()):
                rec = want[rkey]
                for k in policy.FEATURE_KEYS:
                    text = rec['feat_' + k]
                    stored_v = float(text) if text != '' else float('nan')
                    got = feats[k]
                    same = (got == stored_v) or (got != got and stored_v != stored_v)
                    self.assertTrue(same, 'rollout %r %r key %s: %r != %r'
                                    % (rollout, rkey, k, got, stored_v))
                checked += 1
        self.assertGreaterEqual(checked, 5)


class SeedHygieneTests(unittest.TestCase):
    """Research worlds must never overlap the local eval seeds {101, 102, 103}."""

    def test_research_and_eval_seeds_are_disjoint(self):
        import csv as _csv
        rows_path = REPO_ROOT / 'research' / 'out_scale800' / 'rows.csv'
        if not rows_path.exists():
            raise unittest.SkipTest('research/out_scale800/rows.csv not present')
        seen = set()
        with rows_path.open(newline='', encoding='utf-8') as fh:
            for rec in _csv.DictReader(fh):
                seen.add(int(rec['world_seed']))
        self.assertTrue(seen, 'rows.csv is empty')
        leaked = seen & {101, 102, 103}
        self.assertFalse(leaked,
                         'local eval seeds leaked into research worlds: %r' % sorted(leaked))
        # Private grading seeds are unknown and never accessible to policy code (T11).

class MemoryTests(unittest.TestCase):
    def test_empty_members_returns_empty_dict(self):
        self.assertEqual(policy.memory_summary(make_state([])), {})

    def test_counts_and_observed_day_cutoff(self):
        members = [make_member('a'), make_member('b'), make_member('c')]
        intros = [{'introduction_id': 'i1', 'user_a': 'a', 'user_b': 'b',
                   'assigned_day': 0, 'response_deadline_day': 5,
                   'logging_policy': 'h', 'propensity': None}]
        feedback = [
            {'introduction_id': 'i1', 'member_id': 'a', 'event': 'introduction_response',
             'value': 'yes', 'missing_reason': None, 'occurred_day': 1, 'observed_day': 1},
            {'introduction_id': 'i1', 'member_id': None, 'event': 'date_happened',
             'value': True, 'missing_reason': None, 'occurred_day': 4, 'observed_day': 4},
            {'introduction_id': 'i1', 'member_id': 'a', 'event': 'second_meeting_intention',
             'value': 'yes', 'missing_reason': None, 'observed_day': 6},
            {'introduction_id': 'i1', 'member_id': 'b', 'event': 'second_meeting_intention',
             'value': 'no', 'missing_reason': None, 'observed_day': 6},
            {'introduction_id': 'i1', 'member_id': None, 'event': 'date_happened',
             'value': True, 'missing_reason': None, 'occurred_day': 9, 'observed_day': 9},
        ]
        mem = policy.memory_summary(make_state(members, day=7,
                                               introductions=intros, feedback=feedback))
        self.assertEqual(mem['v'], 1)
        self.assertEqual(mem['m']['a'], [1, 1, 1, 0])
        self.assertEqual(mem['m']['b'], [1, 1, 0, 1])
        self.assertEqual(mem['m']['c'], [0, 0, 0, 0])

    def test_future_events_excluded(self):
        members = [make_member('a'), make_member('b')]
        intros = [{'introduction_id': 'i1', 'user_a': 'a', 'user_b': 'b',
                   'assigned_day': 0, 'response_deadline_day': 5,
                   'logging_policy': 'h', 'propensity': None}]
        feedback = [{'introduction_id': 'i1', 'member_id': 'a',
                     'event': 'second_meeting_intention', 'value': 'yes',
                     'missing_reason': None, 'observed_day': 8}]
        mem = policy.memory_summary(make_state(members, day=7,
                                               introductions=intros, feedback=feedback))
        self.assertEqual(mem['m']['a'], [1, 0, 0, 0])

    def test_json_safe_and_size_bounded(self):
        members = [make_member('syn_%032x' % i) for i in range(200)]
        mem = policy.memory_summary(make_state(members))
        text = json.dumps(mem, allow_nan=False)
        self.assertLess(len(text.encode('utf-8')), 1024 * 1024)

class AskPolicyTests(unittest.TestCase):
    @staticmethod
    def _cost(asks):
        return sum(3 if a['field'] == 'constraints' else 1 for a in asks)

    @staticmethod
    def _valid(state, asks):
        for a in asks:
            member = next(m for m in state['members'] if m['member_id'] == a['member_id'])
            if not member['available']:
                return False
            if a['field'] == 'constraints':
                if not any(member['field_status'][k] == 'not_asked' for k in kit.HARD):
                    return False
            elif member['field_status'][a['field']] != 'not_asked':
                return False
        return True

    def test_budget_ceiling_and_validity_all_budgets(self):
        members = ([make_member('m%d' % i, hard_complete=False) for i in range(8)]
                   + [make_member('c%d' % i) for i in range(8)])
        for budget in (12, 4, 3, 2, 0):
            state = make_state(members, budget=budget)
            asks = policy.ac_asks(state)
            self.assertLessEqual(self._cost(asks), budget)
            self.assertTrue(self._valid(state, asks), 'invalid ask at budget %d' % budget)

    def test_tier1_asks_member_blocking_most_partners_first(self):
        members = ([make_member('hot', hard_complete=False),
                    make_member('cold', hard_complete=False)]
                   + [make_member('p%d' % i) for i in range(3)])
        past = [{'introduction_id': 'i0', 'user_a': 'cold', 'user_b': 'p2',
                 'assigned_day': 0, 'response_deadline_day': 5,
                 'logging_policy': 'h', 'propensity': None}]
        asks = policy.ac_asks(make_state(members, budget=12, introductions=past))
        self.assertTrue(asks)
        self.assertEqual(asks[0], {'member_id': 'hot', 'field': 'constraints'})

    def test_declined_hard_field_never_asked(self):
        members = ([make_member('d%d' % i, hard_complete=False, ask_status='declined')
                    for i in range(4)] + [make_member('c%d' % i) for i in range(4)])
        self.assertEqual(policy.ac_asks(make_state(members, budget=12)), [])

    def test_tier1b_fewest_missing_first_when_no_complete_members(self):
        members = [make_member('few%d' % i, hard_complete=False) for i in range(3)]
        for i in range(3):
            m = make_member('many%d' % i, hard_complete=False)
            for k in kit.HARD[3:8]:
                m['fields'][k] = None
                m['field_status'][k] = 'not_asked'
                m['field_observed_day'][k] = None
            members.append(m)
        asks = policy.ac_asks(make_state(members, budget=12))
        self.assertTrue(asks)
        self.assertTrue(all(a['field'] == 'constraints' for a in asks))
        self.assertTrue(all(a['member_id'].startswith('few') for a in asks[:3]),
                        'fewest-missing first: %r' % asks)

    def test_tier2_soft_ask_completes_observed_partner(self):
        a = make_member('a')
        b = make_member('b', soft_goal=None)
        asks = policy.ac_asks(make_state([a, b], budget=12))
        self.assertEqual(asks, [{'member_id': 'b', 'field': 'relationship_goal'}])

    def test_unavailable_member_never_asked(self):
        members = [make_member('x', hard_complete=False, available=False),
                   make_member('y')]
        self.assertEqual(policy.ac_asks(make_state(members, budget=12)), [])

    def test_past_pair_excluded_from_blocking(self):
        m = make_member('m', hard_complete=False)
        o = make_member('o')
        past = [{'introduction_id': 'i1', 'user_a': 'm', 'user_b': 'o',
                 'assigned_day': 0, 'response_deadline_day': 5,
                 'logging_policy': 'h', 'propensity': None}]
        self.assertEqual(policy.ac_asks(make_state([m, o], budget=12, introductions=past)), [])

    def test_determinism(self):
        members = ([make_member('m%d' % i, hard_complete=False) for i in range(5)]
                   + [make_member('c%d' % i) for i in range(5)])
        state = make_state(members, budget=12)
        self.assertEqual(policy.ac_asks(state), policy.ac_asks(state))

    def test_exception_returns_empty(self):
        state = make_state([make_member('m', hard_complete=False), make_member('o')])
        with mock.patch.object(policy, 'eligibility', side_effect=RuntimeError('boom')):
            self.assertEqual(policy.ac_asks(state), [])

class MatchingTests(unittest.TestCase):
    """T7 match rules: feasibility, no past pairs, uniqueness, floor, optimum, determinism, sorted."""

    def test_t7_toy_optimum_reached_not_greedy_trap(self):
        nodes = ['u1', 'u2', 'u3', 'v1', 'v2', 'v3']
        edges = [('u1', 'v1', 10.0), ('u1', 'v2', 9.0), ('u2', 'v1', 9.0),
                 ('u2', 'v2', 1.0), ('u3', 'v3', 8.0)]
        got = policy.max_score_matching(nodes, edges, floor=0.0)
        self.assertEqual(sum(s for _, _, s in got), 26.0)   # local search escapes greedy 19.0
        self.assertEqual(len(got), 3)

    def test_t7_floor_drops_weak_edges(self):
        nodes = ['u1', 'u2', 'v1', 'v2']
        edges = [('u1', 'v1', 0.9), ('u2', 'v2', 0.3)]
        self.assertEqual(policy.max_score_matching(nodes, edges, floor=0.5),
                         [('u1', 'v1', 0.9)])

    def test_t7_all_below_floor_returns_empty_conservative_wait(self):
        self.assertEqual(policy.max_score_matching(['u1', 'v1'], [('u1', 'v1', 0.3)], 0.5),
                         [])

    def test_t7_optimal_swap_across_2x2(self):
        nodes = ['u1', 'u2', 'v1', 'v2']
        edges = [('u1', 'v1', 10.0), ('u1', 'v2', 9.5), ('u2', 'v1', 9.5),
                 ('u2', 'v2', 0.1)]
        got = policy.max_score_matching(nodes, edges, floor=0.0)
        self.assertAlmostEqual(sum(s for _, _, s in got), 19.0, places=9)

    @staticmethod
    def _four_members():
        return [make_member('u1'), make_member('u2'),
                make_member('w1'), make_member('w2')]

    @staticmethod
    def _controlled_model():
        return {'schema': 1, 'n_features': 44, 'feature_keys': ['f'] * 44,
                'floor': 0.5, 'baseline': 0.0, 'trees': [[[0.0]]]}

    def test_t7_ac_match_returns_sorted_two_string_pairs_deterministic(self):
        state = make_state(self._four_members(), budget=12)
        with mock.patch.object(policy, 'load_model', return_value=self._controlled_model()), \
             mock.patch.object(policy, '_score_pair', return_value=0.9):
            out = policy.ac_match(state)
            again = policy.ac_match(state)
        self.assertEqual(out, [['u1', 'u2'], ['w1', 'w2']])  # all-tie 0.9 -> lexicographic greedy + sorted by (a, b)
        self.assertEqual(out, again)
        for pair in out:
            self.assertIsInstance(pair, list)
            self.assertEqual(len(pair), 2)
            self.assertTrue(all(isinstance(x, str) for x in pair))

    def test_t7_ac_match_excludes_past_pairs(self):
        # scorer makes the past pair the GLOBAL best edge: if ac_match did not
        # exclude it, greedy would pick (u1, w1) first and the output would differ.
        past = [{'introduction_id': 'i1', 'user_a': 'u1', 'user_b': 'w1',
                 'assigned_day': 0, 'response_deadline_day': 5,
                 'logging_policy': 'h', 'propensity': None}]
        state = make_state(self._four_members(), budget=12, introductions=past)

        def fake_score(model, st, x, y):
            return 1.0 if tuple(sorted((x, y))) == ('u1', 'w1') else 0.5

        with mock.patch.object(policy, 'load_model', return_value=self._controlled_model()), \
             mock.patch.object(policy, '_score_pair', side_effect=fake_score):
            out = policy.ac_match(state)
        self.assertEqual(out, [['u1', 'u2'], ['w1', 'w2']])  # (u1, w1) excluded, ties fall to (a, b)

    def test_t7_ac_match_skips_unavailable_members(self):
        members = [make_member('u1'), make_member('w1', available=False)]
        with mock.patch.object(policy, 'load_model', return_value=self._controlled_model()):
            self.assertEqual(policy.ac_match(make_state(members)), [])

    def test_t7_ac_match_empty_state(self):
        self.assertEqual(policy.ac_match(make_state([])), [])

    def test_rule_score_prefers_feasible_and_available(self):
        state = make_state([make_member('u1'), make_member('w1')])
        s_ok = policy.rule_score(state, 'u1', 'w1')
        blocked = make_state([make_member('u1'), make_member('w1', available=False)])
        self.assertGreater(s_ok, policy.rule_score(blocked, 'u1', 'w1'))

    def test_t7_general_graph_chain_never_double_books_a_member(self):
        # ONE member pool: two-sided occupancy would pick both edges and double-book
        # 'b' -> kit.advance raises ValueError('overlapping allocation') (kit.py line 147)
        got = policy.max_score_matching(['a', 'b', 'c'],
                                        [('a', 'b', 1.0), ('b', 'c', 2.0)], floor=0.0)
        self.assertEqual(got, [('b', 'c', 2.0)])   # max matching here is a single edge

    def test_t7_no_member_appears_twice_on_general_graph_cases(self):
        cases = [
            (['a', 'b', 'c'], [('a', 'b', 1.0), ('b', 'c', 2.0)]),
            (['a', 'b', 'c'], [('a', 'b', 5.0), ('b', 'c', 4.0), ('a', 'c', 3.0)]),
            (['a', 'b', 'c', 'd'], [('b', 'c', 9.0), ('a', 'b', 8.0), ('c', 'd', 7.0)]),
            (['x', 'y', 'z'], [('y', 'z', 6.0), ('x', 'y', 6.0), ('x', 'z', 1.0)]),
        ]
        for nodes, edges in cases:
            got = policy.max_score_matching(nodes, edges, floor=0.0)
            used = [n for a, b, _ in got for n in (a, b)]
            self.assertEqual(len(used), len(set(used)),
                             'member reused in %r -> %r' % (edges, got))

    def test_t7_eligibility_status_is_orientation_symmetric(self):
        # ac_match scores pairs in sorted-member orientation; the gate itself must not
        # depend on argument order (if this fails: escalate - do NOT patch kit.py)
        checked = 0
        for seed, variant in ((21, 'development'), (22, 'cold_start'), (23, 'sparse')):
            state = kit.Simulator(kit.generate(seed, 60, variant=variant)).observe()
            by_id = {m['member_id']: m for m in state['members']}
            ids = sorted(by_id)[:12]
            for i, a in enumerate(ids):
                for b in ids[i + 1:]:
                    self.assertEqual(
                        kit.eligibility(by_id[a], by_id[b])['status'],
                        kit.eligibility(by_id[b], by_id[a])['status'],
                        'orientation-dependent eligibility for %s/%s' % (a, b))
                    checked += 1
        self.assertGreaterEqual(checked, 66)   # 3 states x C(12, 2)

def assert_no_overlap(testcase, pairs):
    """Shared guard: no member may appear twice in one decision's output
    (kit.advance raises ValueError('overlapping allocation'), kit.py line 147)."""
    used = [n for pair in pairs for n in pair]
    testcase.assertEqual(len(used), len(set(used)),
                          'member reused across pairs: %r' % (pairs,))


class FallbackTests(unittest.TestCase):
    @staticmethod
    def _req(state, phase='match', memory=None):
        return {'schema_version': '1.0.0', 'phase': phase, 'state': state, 'memory': memory}

    @staticmethod
    def _model():
        return {'schema': 1, 'n_features': 44, 'feature_keys': ['f'] * 44,
                'floor': 0.5, 'baseline': 0.0, 'n_iter': 1, 'trees': [[[0.0]]]}

    def test_t8_corrupt_blob_rule_greedy_pairs_deterministic(self):
        members = [make_member('u1'), make_member('u2'),
                   make_member('w1'), make_member('w2')]
        state = make_state(members, budget=12)
        with mock.patch.object(policy, 'MODEL_B64', 'corrupt-blob!!'), \
             mock.patch.object(policy, '_rule_greedy', wraps=policy._rule_greedy) as spy:
            out = policy.ac_match(state)
            again = policy.ac_match(state)
        self.assertEqual(out, [['u1', 'u2'], ['w1', 'w2']])  # all feasible -> tie -> (a, b) order
        self.assertEqual(out, again)
        self.assertEqual(spy.call_count, 2)   # corrupted blob -> rule path EVERY call
        for pair in out:
            self.assertEqual(len(pair), 2)
            self.assertTrue(all(isinstance(x, str) for x in pair))
        assert_no_overlap(self, out)

    def test_t8_injected_scoring_exception_falls_back_to_rule_pairs(self):
        members = [make_member('u1'), make_member('u2'),
                   make_member('w1'), make_member('w2')]
        state = make_state(members, budget=12)
        with mock.patch.object(policy, '_score_pair', side_effect=RuntimeError('boom')), \
             mock.patch.object(policy, '_rule_greedy', wraps=policy._rule_greedy) as spy:
            out = policy.ac_match(state)
        self.assertEqual(out, [['u1', 'u2'], ['w1', 'w2']])  # rule greedy, no floor, no crash
        spy.assert_called_once()              # the exception path provably used _rule_greedy
        assert_no_overlap(self, out)

    def test_t8_model_path_never_calls_rule_greedy(self):
        members = [make_member('u1'), make_member('u2'),
                   make_member('w1'), make_member('w2')]
        state = make_state(members, budget=12)
        with mock.patch.object(policy, 'load_model', return_value=self._model()), \
             mock.patch.object(policy, '_score_pair', return_value=0.9), \
             mock.patch.object(policy, '_rule_greedy', wraps=policy._rule_greedy) as spy:
            out = policy.ac_match(state)
        self.assertEqual(out, [['u1', 'u2'], ['w1', 'w2']])  # model path: floor 0.5 <= 0.9
        spy.assert_not_called()               # healthy model never touches the fallback
        assert_no_overlap(self, out)

    def test_t8_empty_blob_decide_returns_wellformed_strict_json(self):
        state = make_state([make_member('u1'), make_member('w1')], budget=12)
        with mock.patch.object(policy, 'MODEL_B64', ''):
            match_out = policy.decide(self._req(state, 'match'), mode='ac')
            ask_out = policy.decide(self._req(state, 'ask'), mode='ac')
        self.assertEqual(set(match_out), {'pairs', 'memory'})
        self.assertEqual(set(ask_out), {'asks', 'memory'})
        json.dumps(match_out, allow_nan=False)
        json.dumps(ask_out, allow_nan=False)

    def test_t8_ask_failure_returns_empty_asks(self):
        state = make_state([make_member('m', hard_complete=False), make_member('o')],
                           budget=12)
        with mock.patch.object(policy, 'ac_asks', side_effect=RuntimeError('boom')):
            out = policy.decide(self._req(state, 'ask'), mode='ac')
        self.assertEqual(out['asks'], [])
        self.assertEqual(set(out), {'asks', 'memory'})

def req(state, phase='match', memory=None):
    """Build a decide() request exactly like evaluate.episode does."""
    return {'schema_version': '1.0.0', 'phase': phase, 'state': state, 'memory': memory}


class DecideDispatchTests(unittest.TestCase):
    def test_t1_default_mode_runs_greedy_ask_phase(self):
        # ROUND 2 FLIP (design section 8): default is now greedy (official baseline).
        # Deterministic craft: the only partner is a PAST introduction.
        # greedy (default) -> asks constraints for m; ac (still selectable) -> waits ([]).
        m = make_member('m', hard_complete=False)
        o = make_member('o')
        past = [{'introduction_id': 'i1', 'user_a': 'm', 'user_b': 'o',
                 'assigned_day': 0, 'response_deadline_day': 5,
                 'logging_policy': 'h', 'propensity': None}]
        state = make_state([m, o], budget=12, introductions=past)
        default_out = policy.decide(req(state, 'ask'))
        self.assertEqual(default_out, policy.decide(req(state, 'ask'), mode='greedy'))
        self.assertEqual(default_out['asks'],
                         [{'member_id': 'm', 'field': 'constraints'}])
        self.assertEqual(policy.decide(req(state, 'ask'), mode='ac')['asks'], [])

    def test_t1_default_mode_runs_greedy_match_phase(self):
        sim = kit.Simulator(kit.generate(42, 40, variant='development'))
        state = sim.observe()
        self.assertEqual(policy.decide(req(state, 'match')),
                         policy.decide(req(state, 'match'), mode='greedy'))
        # ac remains selectable but is NOT the default
        self.assertNotEqual(policy.decide(req(state, 'match')),
                            policy.decide(req(state, 'match'), mode='ac'))

    def test_t1_greedy_mode_byte_preserved(self):
        sim = kit.Simulator(kit.generate(42, 60))
        state = sim.observe()
        self.assertEqual(policy.decide(req(state, 'match'), mode='greedy')['pairs'],
                         kit.baseline_match(state))
        self.assertEqual(policy.decide(req(state, 'ask'), mode='greedy')['asks'],
                         kit.baseline_asks(state))

    def test_t1_cli_default_greedy_ac_still_selectable(self):
        import subprocess
        self.assertEqual(policy.build_parser().parse_args([]).baseline, 'greedy')
        self.assertEqual(
            policy.build_parser().parse_args(['--baseline', 'greedy']).baseline, 'greedy')
        out = subprocess.run([sys.executable, str(REPO_ROOT / 'policy.py'), '--help'],
                             capture_output=True, text=True, cwd=str(REPO_ROOT))
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn('ac', out.stdout)
        self.assertIn('greedy', out.stdout)

    def test_t2_empty_state_exact_responses(self):
        empty = kit.Simulator(kit.generate(42, 0, variant='development')).observe()
        self.assertEqual(policy.decide(req(empty, 'match'), mode='ac'),
                         {'pairs': [], 'memory': {}})
        self.assertEqual(policy.decide(req(empty, 'ask'), mode='ac'),
                         {'asks': [], 'memory': {}})

    def test_t2_ask_shape_strict_json_budget_and_resolvable(self):
        from evaluate import validate_response
        sim = kit.Simulator(kit.generate(42, 60))
        state = sim.observe()
        decision = policy.decide(req(state, 'ask'), mode='ac')
        validate_response(decision, 'ask')                     # exact harness contract
        json.dumps(decision, allow_nan=False)                  # strict JSON (T2)
        cost = sum(3 if a['field'] == 'constraints' else 1 for a in decision['asks'])
        self.assertLessEqual(cost, state['ask_budget_remaining'])
        sim.resolve_asks(decision['asks'])                     # no KeyError/TypeError
        match_decision = policy.decide(req(sim.observe(), 'match'), mode='ac')
        validate_response(match_decision, 'match')
        sim.advance(match_decision['pairs'])                   # no ValueError

    def test_t2_memory_robustness_none_empty_stale(self):
        state = make_state([make_member('u1'), make_member('w1')], budget=12)
        base = policy.decide(req(state, 'match', memory=None), mode='ac')
        for memory in ({}, {'v': 0, 'm': {'stale': [9, 9, 9, 9]}}, 'garbage-string'):
            self.assertEqual(policy.decide(req(state, 'match', memory=memory), mode='ac'),
                             base)                             # ac ignores request memory (regenerates)

    def test_t11_policy_source_has_no_forbidden_tokens(self):
        src = (REPO_ROOT / 'policy.py').read_text(encoding='utf-8')
        for line in src.splitlines():
            if 'FORBIDDEN_TOKENS' in line or 'STRUCTURE_INFORMED' in line:
                continue       # the token list/auditor definitions themselves
            for token in ('future_', 'hidden_', 'ground_truth', 'label_mutual',
                          'label_date', 'response_rate', 'oracle'):
                self.assertNotIn(token, line,
                                 'forbidden token %r in policy.py: %r' % (token, line))
        self.assertNotIn('audit_feature_keys(', src)   # auditor not imported/called in policy
        self.assertNotIn('audit_structure_disclosure', src)

    def test_t11_feature_keys_have_no_forbidden_tokens(self):
        import features
        for key in features.FEATURE_KEYS:
            for token in ('future_', 'hidden_', 'ground_truth', 'oracle'):
                self.assertNotIn(token, key)


class ShimTests(unittest.TestCase):
    def test_policy_ac_forces_ac_and_ignores_baseline_flag(self):
        # divergence craft from T1: greedy would ask, ac waits - proves which mode ran
        m = make_member('m', hard_complete=False)
        o = make_member('o')
        past = [{'introduction_id': 'i1', 'user_a': 'm', 'user_b': 'o',
                 'assigned_day': 0, 'response_deadline_day': 5,
                 'logging_policy': 'h', 'propensity': None}]
        state = make_state([m, o], budget=12, introductions=past)
        import subprocess
        out = subprocess.run(
            [sys.executable, str(REPO_ROOT / 'policy_ac.py'), '--baseline', 'greedy'],
            input=json.dumps(req(state, 'ask')), capture_output=True, text=True,
            cwd=str(REPO_ROOT))
        self.assertEqual(out.returncode, 0, out.stderr)
        parsed = json.loads(out.stdout)
        self.assertEqual(parsed, policy.decide(req(state, 'ask'), mode='ac'))
        self.assertNotEqual(parsed, policy.decide(req(state, 'ask'), mode='greedy'))
        src = (REPO_ROOT / 'policy_ac.py').read_text(encoding='utf-8')
        self.assertIn("mode='ac'", src)

class IntegrationTests(unittest.TestCase):
    @staticmethod
    def _req(state, phase='match'):
        return {'schema_version': '1.0.0', 'phase': phase, 'state': state, 'memory': None}

    def test_t9_real_resolver_20_day_loop_exact_harness_contract(self):
        from evaluate import validate_response
        self.assertIsNotNone(policy.load_model(), 'T9 must exercise the REAL embedded model')
        sim = kit.Simulator(kit.generate(42, 60, variant='development'))
        with mock.patch.object(policy, '_rule_greedy', wraps=policy._rule_greedy) as spy:
            for _ in range(20):
                ask_decision = policy.decide(self._req(sim.observe(), 'ask'), mode='ac')
                validate_response(ask_decision, 'ask')      # exact evaluate.py contract
                json.dumps(ask_decision, allow_nan=False)
                sim.resolve_asks(ask_decision['asks'])
                match_decision = policy.decide(self._req(sim.observe(), 'match'), mode='ac')
                validate_response(match_decision, 'match')  # pairs = [str, str] arrays
                json.dumps(match_decision, allow_nan=False)
                assert_no_overlap(self, match_decision['pairs'])
                for pair in match_decision['pairs']:
                    self.assertNotIn(tuple(sorted(pair)),
                                     {tuple(sorted((i['user_a'], i['user_b'])))
                                      for i in sim.observe()['introductions']},
                                     'ac returned a past pair - advance would raise')
                sim.advance(match_decision['pairs'])        # never ValueError (kit lines 147/150)
        spy.assert_not_called()  # healthy end-to-end path never drops to the rule fallback
        self.assertTrue(sim.observe()['members'])           # loop survived 20 days

    @staticmethod
    def _replay_state(target_day=50):
        """Real 200-member world replayed to target_day with accumulated history
        (introductions, feedback, field maturation) via collect_rows' exact day
        mechanics: observe -> asks -> re-observe -> match -> advance."""
        sim = kit.Simulator(kit.generate(42, 200, 'dev_replay', variant='development'))
        for _ in range(target_day):
            state = sim.observe()
            sim.resolve_asks(kit.baseline_asks(state))
            state = sim.observe()
            sim.advance(kit.baseline_match(state))
        return sim.observe()

    def test_t10_local_match_latency_on_real_day50_state(self):
        import time
        state = self._replay_state(target_day=50)
        available = [m for m in state['members'] if m['available']]
        # realistic regime (probed: seed 42 day 50 -> 174 available, 96 intros, 208 feedback,
        # request 452783 bytes < 1 MiB evaluate limit, allow_nan=False clean)
        self.assertGreaterEqual(len(available), 150)
        self.assertLessEqual(len(available), 190)
        self.assertGreaterEqual(len(state['introductions']), 50)
        self.assertGreaterEqual(len(state['feedback']), 100)
        with mock.patch.object(policy, '_rule_greedy', wraps=policy._rule_greedy) as spy:
            start = time.perf_counter()
            out = policy.ac_match(state)
            elapsed = time.perf_counter() - start
        spy.assert_not_called()
        assert_no_overlap(self, out)
        print('T10 local match (day50, %d available, %d intros): %.2fs (%d pairs)'
              % (len(available), len(state['introductions']), elapsed, len(out)))
        self.assertLess(elapsed, 9.0,
                        'local ac_match on a day-50 state took %.2fs '
                        '(hard <9s; the Task 10 container run is authoritative)' % elapsed)

    def test_t10_local_ask_latency_on_real_day50_state(self):
        import time
        state = self._replay_state(target_day=50)
        req = self._req(state, 'ask')
        start = time.perf_counter()
        out = policy.decide(req, mode='ac')
        elapsed = time.perf_counter() - start
        json.dumps(out, allow_nan=False)
        self.assertIsInstance(out['asks'], list)
        print('T10 local ask (day50): %.2fs (%d asks)' % (elapsed, len(out['asks'])))
        self.assertLess(elapsed, 9.0, 'local ask phase took %.2fs (hard <9s)' % elapsed)

    def test_t10_docker_latency_within_eval_constraints(self):
        # Authoritative: exact evaluator container constraints (--cpus=2 --memory=1g
        # --network=none, read-only) + evaluate.invoke's 10 s limit, measured inside
        # invoke itself (returns (validated_response, elapsed)).
        # SKIPs until Task 10 builds sequential-policy:1.0; re-run there.
        import subprocess
        import evaluate as ev
        try:
            probe = subprocess.run(['docker', 'version'], capture_output=True, timeout=30)
        except (OSError, subprocess.TimeoutExpired):
            raise unittest.SkipTest('docker not available')
        if probe.returncode != 0:
            raise unittest.SkipTest('docker daemon not available')
        image = 'sequential-policy:1.0'
        if subprocess.run(['docker', 'image', 'inspect', image],
                          capture_output=True).returncode != 0:
            raise unittest.SkipTest('%s not built yet (Task 10 builds it)' % image)
        state = self._replay_state(target_day=50)
        response, elapsed = ev.invoke(ev.docker_command(image),
                                      self._req(state, 'match'), timeout=10)
        self.assertIsInstance(response['pairs'], list)  # validate_response ran inside invoke
        print('T10 docker match (day50): %.2fs (%d pairs)'
              % (elapsed, len(response['pairs'])))
        self.assertLess(elapsed, 9.0,
                        'docker ac_match took %.2fs (hard <9s under evaluator constraints)'
                        % elapsed)
        # ask phase measured too - evaluate.episode invokes BOTH phases every day
        ask_out, ask_elapsed = ev.invoke(ev.docker_command(image),
                                         self._req(state, 'ask'), timeout=10)
        self.assertIsInstance(ask_out['asks'], list)
        print('T10 docker ask (day50): %.2fs (%d asks)'
              % (ask_elapsed, len(ask_out['asks'])))
        self.assertLess(ask_elapsed, 9.0,
                        'docker ask phase took %.2fs (hard <9s under evaluator constraints)'
                        % ask_elapsed)