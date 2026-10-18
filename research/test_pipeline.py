"""Tests for the research/ data-pipeline prototype (TDD: written before implementation)."""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for p in (str(REPO_ROOT), str(REPO_ROOT / 'research')):
    if p not in sys.path:
        sys.path.insert(0, p)


def resp(iid, member, value, observed, occurred=None, missing=None):
    return {'introduction_id': iid, 'member_id': member, 'event': 'introduction_response',
            'value': value, 'missing_reason': missing,
            'occurred_day': occurred, 'observed_day': observed}


def date_ev(iid, value, observed, occurred=None):
    return {'introduction_id': iid, 'member_id': None, 'event': 'date_happened',
            'value': value, 'missing_reason': None, 'occurred_day': occurred,
            'observed_day': observed}


def second(iid, member, value, observed, occurred=None, missing=None):
    return {'introduction_id': iid, 'member_id': member, 'event': 'second_meeting_intention',
            'value': value, 'missing_reason': missing, 'occurred_day': occurred,
            'observed_day': observed}


class TestLabels(unittest.TestCase):
    def test_maturity_is_max_observed_day(self):
        from labels import maturity_day
        evs = [resp('i', 'a', 'yes', 12, 12), resp('i', 'b', 'yes', 13, 13),
               date_ev('i', True, 20, 20), second('i', 'a', 'yes', 21, 21),
               second('i', 'b', 'yes', 22, 22)]
        self.assertEqual(maturity_day(evs), 22)
        self.assertIsNone(maturity_day([]))

    def test_immature_returns_none(self):
        from labels import label_msmi
        evs = [resp('i', 'a', 'yes', 12, 12), resp('i', 'b', 'yes', 13, 13),
               date_ev('i', True, 40, 40), second('i', 'a', 'yes', 41, 41),
               second('i', 'b', 'yes', 42, 42)]
        self.assertIsNone(label_msmi(evs, assigned_day=10, horizon=30))
        self.assertEqual(label_msmi(evs, assigned_day=10, horizon=42), 1)

    def test_positive_label(self):
        from labels import label_msmi
        evs = [resp('i', 'a', 'yes', 12, 12), resp('i', 'b', 'yes', 13, 13),
               date_ev('i', True, 20, 20), second('i', 'a', 'yes', 21, 21),
               second('i', 'b', 'yes', 22, 22)]
        self.assertEqual(label_msmi(evs, assigned_day=10, horizon=100), 1)

    def test_negative_when_any_response_is_no(self):
        from labels import label_msmi
        evs = [resp('i', 'a', 'yes', 12, 12), resp('i', 'b', 'no', 13, 13)]
        self.assertEqual(label_msmi(evs, assigned_day=10, horizon=100), 0)

    def test_negative_when_date_is_late(self):
        from labels import label_msmi
        evs = [resp('i', 'a', 'yes', 12, 12), resp('i', 'b', 'yes', 13, 13),
               date_ev('i', True, 45, 45)]
        self.assertEqual(label_msmi(evs, assigned_day=10, horizon=100), 0)

    def test_negative_when_second_intention_missing_or_late(self):
        from labels import label_msmi
        base = [resp('i', 'a', 'yes', 12, 12), resp('i', 'b', 'yes', 13, 13),
                date_ev('i', True, 20, 20)]
        no_response = list(base) + [second('i', 'a', None, 25, None, 'no_response'),
                                    second('i', 'b', 'yes', 22, 22)]
        self.assertEqual(label_msmi(no_response, assigned_day=10, horizon=100), 0)
        one_no = list(base) + [second('i', 'a', 'no', 21, 21),
                               second('i', 'b', 'yes', 22, 22)]
        self.assertEqual(label_msmi(one_no, assigned_day=10, horizon=100), 0)
        late = list(base) + [second('i', 'a', 'yes', 30, 30),
                             second('i', 'b', 'yes', 31, 31)]
        self.assertEqual(label_msmi(late, assigned_day=10, horizon=100), 0)

    def test_none_iff_immature(self):
        from labels import label_msmi, maturity_day
        cases = [
            [resp('i', 'a', 'yes', 12, 12), resp('i', 'b', 'yes', 13, 13)],
            [resp('i', 'a', 'yes', 12, 12), resp('i', 'b', 'no', 13, 13)],
            [resp('i', 'a', None, 17, None, 'no_response'),
             resp('i', 'b', None, 17, None, 'no_response')],
        ]
        for evs in cases:
            for horizon in (0, 5, 12, 13, 17, 100):
                label = label_msmi(evs, assigned_day=10, horizon=horizon)
                mature = maturity_day(evs) is not None and maturity_day(evs) <= horizon
                self.assertEqual(label is None, not mature,
                                 msg=f'evs={evs} horizon={horizon} label={label}')

    def test_group_events_by_introduction(self):
        from labels import group_events
        evs = [resp('i1', 'a', 'yes', 12, 12), resp('i2', 'b', 'no', 13, 13)]
        grouped = group_events(evs)
        self.assertEqual(sorted(grouped), ['i1', 'i2'])
        self.assertEqual(len(grouped['i1']), 1)

    def test_matches_kit_metrics_on_real_rollout(self):
        import kit
        from labels import label_msmi, group_events
        sim = kit.rollout(kit.generate(20260926, 200), days=60)
        for _ in range(40):
            sim.advance([])
        horizon = sim.day
        grouped = group_events(sim.receive_feedback())
        total = 0
        for intro in sim.introductions:
            label = label_msmi(grouped.get(intro['introduction_id'], []),
                               assigned_day=intro['assigned_day'], horizon=horizon)
            self.assertIsNotNone(label, msg='every label must have matured by horizon')
            total += label
        self.assertEqual(total, sim.metrics()['mutual_second_meeting_intention'])


if __name__ == '__main__':
    unittest.main()

class TestFeatures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import kit
        cls.sim = kit.Simulator(kit.generate(7, 120))
        cls.events = None
        for _ in range(18):
            obs = cls.sim.observe()
            cls.sim.resolve_asks(kit.baseline_asks(obs))
            cls.sim.advance(kit.baseline_match(cls.sim.observe()))
        cls.t = cls.sim.day
        cls.state = cls.sim.observe()
        cls.members = [m['member_id'] for m in cls.state['members'] if m['available']][:4]

    def test_feature_keys_stable_and_audit_clean(self):
        from features import FEATURE_KEYS, audit_feature_keys, pair_features
        self.assertEqual(len(FEATURE_KEYS), len(set(FEATURE_KEYS)))
        self.assertEqual(audit_feature_keys(FEATURE_KEYS), [])
        feats = pair_features(self.state, self.members[0], self.members[1], self.t)
        self.assertEqual(set(feats), set(FEATURE_KEYS))
        self.assertTrue(all(isinstance(v, float) for v in feats.values()))

    def test_unknown_soft_field_is_nan_not_zero(self):
        from features import pair_features, SOFT
        target = None
        for m in self.state['members']:
            if not m['available']:
                continue
            missing = [k for k in SOFT if m['fields'].get(k) is None]
            if missing:
                other = [o for o in self.state['members']
                         if o['member_id'] != m['member_id'] and o['available']][0]
                target = (m['member_id'], other['member_id'], missing[0])
                break
        self.assertIsNotNone(target, 'need a member with an unobserved soft field')
        a, b, key = target
        feats = pair_features(self.state, a, b, self.t)
        self.assertEqual(feats['soft_%s_observed' % key], 0.0)
        match = feats['soft_%s_match' % key]
        self.assertTrue(match != match, 'unknown soft must be NaN, not 0')

    def test_future_feedback_is_ignored(self):
        from features import pair_features
        a, b = self.members[0], self.members[1]
        base = pair_features(self.state, a, b, self.t)
        poisoned = dict(self.state)
        poisoned['feedback'] = list(self.state['feedback']) + [
            {'introduction_id': 'future', 'member_id': a, 'event': 'introduction_response',
             'value': 'yes', 'missing_reason': None, 'occurred_day': self.t + 40,
             'observed_day': self.t + 40}]
        after = pair_features(poisoned, a, b, self.t)
        self.assertEqual({k: 0 if v != v else v for k, v in base.items()},
                         {k: 0 if v != v else v for k, v in after.items()})

    def test_future_field_observation_is_masked(self):
        from features import pair_features, SOFT
        target = None
        a = b = None
        for m in self.state['members']:
            if not m['available'] or target is not None:
                continue
            for key in SOFT:
                if m['fields'].get(key) is None:
                    a, target = m['member_id'], key
                    break
        for m in self.state['members']:
            if m['available'] and m['member_id'] != a:
                b = m['member_id']
                break
        self.assertIsNotNone(target, 'need an available member with an unobserved soft field')
        self.assertIsNotNone(b)
        base = pair_features(self.state, a, b, self.t)
        poisoned = dict(self.state)
        poisoned['members'] = []
        for m in self.state['members']:
            copy_m = dict(m)
            copy_m['fields'] = dict(m['fields'])
            copy_m['field_observed_day'] = dict(m['field_observed_day'])
            if m['member_id'] == a:
                copy_m['fields'][target] = 'exploring'
                copy_m['field_observed_day'][target] = self.t + 30
            poisoned['members'].append(copy_m)
        after = pair_features(poisoned, a, b, self.t)
        norm = lambda d: {k: 0 if v != v else v for k, v in d.items()}
        self.assertEqual(norm(base), norm(after))

    def test_history_is_laplace_smoothed(self):
        from features import member_history, pair_features
        hist = member_history(self.state, self.t, self.members[0])
        n = hist['n_responses']
        if n >= 0:
            self.assertAlmostEqual(hist['yes_rate'], (hist['n_yes'] + 1) / (n + 2))

    def test_symmetry_under_pair_swap(self):
        from features import pair_features
        a, b = self.members[2], self.members[3]
        f1 = pair_features(self.state, a, b, self.t)
        f2 = pair_features(self.state, b, a, self.t)
        norm = lambda d: {k: 0 if v != v else v for k, v in d.items()}
        self.assertEqual(norm(f1), norm(f2))

    def test_structure_informed_features_are_flagged(self):
        from features import STRUCTURE_INFORMED, pair_features, audit_structure_disclosure
        feats = pair_features(self.state, self.members[0], self.members[1], self.t)
        for key in STRUCTURE_INFORMED:
            self.assertIn(key, feats)
        self.assertEqual(audit_structure_disclosure(), [])

class TestCollect(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import kit
        cls.sim = kit.Simulator(kit.generate(11, 150))
        for _ in range(12):
            cls.sim.resolve_asks(kit.baseline_asks(cls.sim.observe()))
            cls.sim.advance(kit.baseline_match(cls.sim.observe()))
        cls.state = cls.sim.observe()

    def test_scan_is_exactly_the_feasible_available_unintroduced_set(self):
        import itertools
        import kit
        from collect import scan
        members = [m for m in self.state['members'] if m['available']]
        past = {tuple(sorted((i['user_a'], i['user_b']))) for i in self.state['introductions']}
        expected = set()
        for a, b in itertools.combinations(members, 2):
            key = tuple(sorted((a['member_id'], b['member_id'])))
            if key in past:
                continue
            if kit.eligibility(a, b)['status'] == 'feasible':
                expected.add(key)
        got = set(map(tuple, map(sorted, scan(self.state))))
        self.assertEqual(got, expected)
        self.assertGreater(len(expected), 0)

    def test_random_match_is_valid_and_maximal(self):
        import kit
        from collect import RandomCollector, scan
        col = RandomCollector(seed=5)
        pairs = col.match(self.state)
        opps = set(tuple(sorted(p)) for p in scan(self.state))
        used = set()
        for pair in pairs:
            self.assertEqual(len(pair), 2)
            key = tuple(sorted(pair))
            self.assertIn(key, opps, 'chosen pair must be an opportunity')
            self.assertFalse(used & set(pair), 'overlap')
            used.update(pair)
        unused = [m for m in self.state['members']
                  if m['available'] and m['member_id'] not in used]
        import itertools
        for a, b in itertools.combinations([m['member_id'] for m in unused], 2):
            self.assertNotIn(tuple(sorted((a, b))), opps,
                             'maximality: no edge may remain among unused members')

    def test_asks_respect_budget_and_validity(self):
        from collect import RandomCollector
        col = RandomCollector(seed=9)
        for _ in range(6):
            state = self.state
            asks = col.asks(state)
            cost = sum(3 if a['field'] == 'constraints' else 1 for a in asks)
            self.assertLessEqual(cost, state['ask_budget_remaining'])
            self.assertEqual(len({(a['member_id'], a['field']) for a in asks}), len(asks))
            available = {m['member_id'] for m in state['members'] if m['available']}
            for a in asks:
                self.assertIn(a['member_id'], available)
                import kit
                self.assertIn(a['field'], ['constraints'] + list(kit.SOFT))

    def test_collect_rows_labels_only_introduced_pairs_and_mature(self):
        from collect import collect_rows
        out = collect_rows(__import__('kit').generate(3, 120), collector_seed=1,
                           days=25, follow_up=40)
        rows = out['rows']
        intros = out['introductions']
        self.assertEqual(len(rows), len(intros))
        self.assertGreater(len(rows), 0)
        for row in rows:
            self.assertIn(row['label'], (0, 1), 'no None labels after follow-up')
            self.assertIn((row['day'], tuple(sorted((row['a'], row['b'])))),
                          {(i['assigned_day'], tuple(sorted((i['user_a'], i['user_b']))))
                           for i in intros})
            from features import FEATURE_KEYS
            self.assertEqual(set(row['features']), set(FEATURE_KEYS))

    def test_determinism_same_seed_same_rows(self):
        import json
        import kit
        from collect import collect_rows
        world = kit.generate(5, 100)
        a = collect_rows(world, collector_seed=42, days=20, follow_up=40)
        b = collect_rows(world, collector_seed=42, days=20, follow_up=40)
        norm = lambda rows: json.dumps(
            [{k: (sorted(v.items()) if isinstance(v, dict) else
                  [0 if x != x else x for x in v] if isinstance(v, list) else v)
              for k, v in r.items()} for r in rows],
            sort_keys=True, default=str)
        self.assertEqual(norm(a['rows']), norm(b['rows']))
        self.assertEqual(a['per_day'], b['per_day'])

    def test_opportunities_cover_chosen_and_random_beats_greedy_on_coverage(self):
        import kit
        from collect import collect_rows
        world = kit.generate(9, 150)
        rnd = collect_rows(world, collector_seed=3, days=30, follow_up=40)
        grd = collect_rows(world, collector_seed=3, days=30, follow_up=40, policy='greedy')
        for out in (rnd, grd):
            total_opp = sum(d['opportunities'] for d in out['per_day'])
            total_chosen = sum(d['chosen'] for d in out['per_day'])
            self.assertGreater(total_opp, 0)
            self.assertLessEqual(total_chosen, total_opp)
            self.assertEqual(out['coverage_fraction'],
                             total_chosen / total_opp)
        self.assertGreater(rnd['coverage_fraction'], grd['coverage_fraction'],
                           'randomized ordering must explore more of the opportunity space')

    def test_collectors_never_read_hidden_world_fields(self):
        import kit
        from collect import RandomCollector
        world = kit.generate(13, 80)
        sim = kit.Simulator(world)
        for _ in range(5):
            state = sim.observe()
            col = RandomCollector(seed=2)
            col.asks(state)
            col.match(state)
            sim.resolve_asks(col.asks(state))
            sim.advance(col.match(sim.observe()))

class TestIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import kit
        from collect import collect_rows
        cls.world = kit.generate(21, 100)
        cls.out = collect_rows(cls.world, collector_seed=8, days=25, follow_up=40)

    def test_clean_run_passes_audit(self):
        from integrity import audit_rows
        self.assertEqual(audit_rows(self.out['rows'], horizon=self.out['horizon']), [])

    def test_forbidden_feature_injection_is_caught(self):
        from integrity import audit_rows
        rows = [dict(r, features=dict(r['features'])) for r in self.out['rows']]
        rows[0]['features']['member_truth_bias'] = 1.0
        rows[1]['features']['seed'] = 3.0
        violations = audit_rows(rows, horizon=self.out['horizon'])
        self.assertTrue(any('forbidden' in v for v in violations), violations)

    def test_temporal_injection_is_caught(self):
        from integrity import audit_rows
        rows = [dict(r, features=dict(r['features'])) for r in self.out['rows']]
        rows[0]['features']['day'] = rows[0]['day'] + 5.0
        violations = audit_rows(rows, horizon=self.out['horizon'])
        self.assertTrue(any('day' in v for v in violations), violations)

    def test_immature_but_labelled_is_caught(self):
        from integrity import audit_rows
        rows = [dict(r) for r in self.out['rows']]
        rows[0]['label'] = None
        rows[0]['maturity_day'] = rows[0]['day']
        violations = audit_rows(rows, horizon=rows[0]['day'])
        self.assertTrue(any('premature' in v for v in violations), violations)
        rows[0]['label'] = 0
        rows[0]['maturity_day'] = rows[0]['day'] + 1
        violations = audit_rows(rows, horizon=rows[0]['day'])
        self.assertTrue(any('unmatured' in v for v in violations), violations)

    def test_world_snapshot_unchanged_by_rollout(self):
        import json
        import kit
        from collect import collect_rows
        world = kit.generate(31, 80)
        before = json.dumps(world, sort_keys=True)
        collect_rows(world, collector_seed=1, days=10, follow_up=40)
        self.assertEqual(json.dumps(world, sort_keys=True), before)

    def test_labels_stable_once_mature(self):
        from labels import group_events, label_msmi
        grouped = group_events(self.out['events'])
        checked = 0
        for row in self.out['rows']:
            evs = grouped[row['introduction_id']]
            recomputed = label_msmi(evs, assigned_day=row['day'],
                                    horizon=row['maturity_day'])
            self.assertEqual(recomputed, row['label'],
                             msg='label must not change once matured')
            checked += 1
        self.assertGreater(checked, 0)

    def test_suite_report_shape_and_ok(self):
        from integrity import run_integrity_suite
        report = run_integrity_suite(n_worlds=1, days=20, follow_up=40, collector_seed=4)
        self.assertIn('ok', report)
        self.assertTrue(report['ok'], report)
        for key in ('forbidden_keys', 'structure_disclosure', 'rows_audit',
                    'snapshot_unchanged', 'label_stability', 'determinism'):
            self.assertTrue(report['checks'][key], (key, report))


def _have_sklearn():
    try:
        import numpy  # noqa: F401
        import sklearn  # noqa: F401
        return True
    except ImportError:
        return False


@unittest.skipUnless(_have_sklearn(), 'numpy+sklearn required')
class TestAnalyze(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import kit
        from collect import collect_rows
        outs = [collect_rows(kit.generate(61, 120), collector_seed=1, days=20, follow_up=40),
                collect_rows(kit.generate(62, 120), collector_seed=2, days=20, follow_up=40),
                collect_rows(kit.generate(63, 120), collector_seed=3, days=20, follow_up=40)]
        cls.rows = [r for out in outs for r in out['rows']]

    def test_build_dataset_shape_order_and_none_labels_dropped(self):
        import numpy as np
        from analyze import build_dataset
        from features import FEATURE_KEYS
        X, y, kept = build_dataset(self.rows)
        self.assertEqual(X.shape[1], len(FEATURE_KEYS))
        self.assertEqual(X.shape[0], len(y))
        self.assertEqual(X.shape[0], len(kept))
        self.assertTrue(set(np.unique(y)) <= {0, 1})
        expected = sum(1 for r in self.rows if r['label'] is not None)
        self.assertEqual(X.shape[0], expected)
        self.assertGreater(X.shape[0], 0)

    def test_rows_are_stamped_with_world_identity(self):
        for r in self.rows:
            for key in ('world_seed', 'variant', 'policy'):
                self.assertIn(key, r)

    def test_world_split_has_no_world_overlap(self):
        from analyze import world_key, world_split
        train, val = world_split(self.rows, val_frac=0.34, split_seed=0)
        train_worlds = {world_key(r) for r in train}
        val_worlds = {world_key(r) for r in val}
        self.assertFalse(train_worlds & val_worlds, (train_worlds, val_worlds))
        self.assertEqual(len(train) + len(val), len(self.rows))
        self.assertGreater(len(train), 0)
        self.assertGreater(len(val), 0)

    def test_split_is_deterministic(self):
        from analyze import world_key, world_split
        a = [world_key(r) for r in world_split(self.rows, 0.34, 7)[1]]
        b = [world_key(r) for r in world_split(self.rows, 0.34, 7)[1]]
        self.assertEqual(a, b)

    def test_constant_baseline_scores_are_constant_and_auc_half(self):
        import numpy as np
        from analyze import ConstantBaseline, evaluate
        y = np.array([0, 0, 1, 1, 0, 1])
        model = ConstantBaseline(0.25)
        scores = model.predict_proba(np.zeros((6, 2)))[:, 1]
        self.assertTrue(all(s == 0.25 for s in scores))
        m = evaluate(y, scores)
        self.assertAlmostEqual(m['roc_auc'], 0.5)
        self.assertAlmostEqual(m['avg_precision'], y.mean())

    def test_evaluate_handles_single_class(self):
        import numpy as np
        from analyze import evaluate
        m = evaluate(np.zeros(5), np.full(5, 0.2))
        self.assertIsNone(m['roc_auc'])
        self.assertEqual(m['n'], 5)

    def test_hist_gb_fits_and_scores_are_deterministic(self):
        import numpy as np
        from analyze import fit_models, predict, evaluate
        rng = np.random.RandomState(0)
        X = rng.randn(200, 6)
        y = (X[:, 0] + X[:, 1] > 0).astype(int)
        rows_fake = None
        models1 = fit_models(X, y)
        models2 = fit_models(X, y)
        names1 = [n for n, _ in models1]
        self.assertIn('constant', names1)
        self.assertIn('hist_gb', names1)
        s1 = dict((n, predict(m, X)) for n, m in models1)
        s2 = dict((n, predict(m, X)) for n, m in models2)
        for n in s1:
            np.testing.assert_allclose(s1[n], s2[n])
        m = evaluate(y, s1['hist_gb'])
        self.assertGreater(m['roc_auc'], 0.9)
        self.assertGreater(m['avg_precision'], 0.9)

    def test_leakage_audit_is_empty_and_catches_bad_names(self):
        from analyze import leakage_audit
        import features
        self.assertEqual(leakage_audit(), [])
        self.assertTrue(features.audit_feature_keys(['truth', 'bias', 'seed']))

@unittest.skipUnless(_have_sklearn(), 'numpy+sklearn required')
class TestStageTargets(unittest.TestCase):
    def test_mutual_and_date_labels(self):
        from labels import label_mutual, label_date
        both_yes = [resp('i', 'a', 'yes', 12, 12), resp('i', 'b', 'yes', 13, 13),
                    date_ev('i', True, 20, 20), second('i', 'a', 'yes', 21, 21),
                    second('i', 'b', 'yes', 22, 22)]
        self.assertEqual(label_mutual(both_yes, 10, 100), 1)
        self.assertEqual(label_date(both_yes, 10, 100), 1)
        one_no = [resp('i', 'a', 'yes', 12, 12), resp('i', 'b', 'no', 13, 13)]
        self.assertEqual(label_mutual(one_no, 10, 100), 0)
        self.assertEqual(label_date(one_no, 10, 100), 0)
        immature = list(both_yes)
        self.assertIsNone(label_mutual(immature, 10, 15))
        self.assertIsNone(label_date(immature, 10, 15))

    def test_stage_labels_match_kit_metrics_on_real_rollout(self):
        import kit
        from labels import group_events, label_mutual, label_date
        sim = kit.rollout(kit.generate(20260926, 200), days=60)
        for _ in range(40):
            sim.advance([])
        horizon = sim.day
        grouped = group_events(sim.receive_feedback())
        mutual = dates = 0
        for intro in sim.introductions:
            evs = grouped[intro['introduction_id']]
            mutual += label_mutual(evs, intro['assigned_day'], horizon)
            dates += label_date(evs, intro['assigned_day'], horizon)
        m = sim.metrics()
        self.assertEqual(mutual, m['mutual_acceptances'])
        self.assertEqual(dates, m['dates'])

    def test_build_dataset_accepts_target_column(self):
        from analyze import build_dataset
        rows = [
            {'label': 1, 'label_mutual': 0, 'features': {'x': 1.0}},
            {'label': 0, 'label_mutual': 1, 'features': {'x': 0.0}},
            {'label': None, 'label_mutual': None, 'features': {'x': 0.5}},
        ]
        X, y, kept = build_dataset(rows, feature_keys=['x'], target='label_mutual')
        self.assertEqual(list(y), [0, 1])
        self.assertEqual(len(kept), 2)
        X2, y2, _ = build_dataset(rows, feature_keys=['x'], target='label')
        self.assertEqual(list(y2), [1, 0])

@unittest.skipUnless(_have_sklearn(), 'numpy+sklearn required')
class TestDriver(unittest.TestCase):
    def test_flatten_row_handles_meta_targets_and_nan(self):
        from run_experiment import flatten_row, META_COLUMNS, FEATURE_COLUMN_PREFIX
        from features import FEATURE_KEYS
        row = {'day': 3, 'a': 'x', 'b': 'y', 'features': dict((k, float('nan')) for k in FEATURE_KEYS),
               'world_seed': 5, 'variant': 'shift', 'policy': 'random', 'collector_seed': 1,
               'introduction_id': 'i', 'maturity_day': 9, 'label': 1, 'label_mutual': 1,
               'label_date': 0}
        flat = flatten_row(row)
        self.assertEqual(flat['day'], 3)
        self.assertEqual(flat['label'], 1)
        self.assertEqual(flat['variant'], 'shift')
        self.assertEqual(flat[FEATURE_COLUMN_PREFIX + 'age_diff'], '')
        self.assertEqual(set(META_COLUMNS) - set(flat), set())
        self.assertEqual(set(k for k in flat if k.startswith(FEATURE_COLUMN_PREFIX)),
                         set(FEATURE_COLUMN_PREFIX + k for k in FEATURE_KEYS))

    def test_decide_gate_integrity_failure_is_stop(self):
        from run_experiment import decide
        sections = {'integrity_clean': False, 'stage_signal': True, 'msmi_signal': True}
        self.assertEqual(decide(sections), 'STOP')

    def test_decide_no_signal_is_stop(self):
        from run_experiment import decide
        sections = {'integrity_clean': True, 'stage_signal': False, 'msmi_signal': False}
        self.assertEqual(decide(sections), 'STOP')

    def test_decide_stage_signal_without_mmsi_is_changes(self):
        from run_experiment import decide
        sections = {'integrity_clean': True, 'stage_signal': True, 'msmi_signal': False}
        self.assertEqual(decide(sections), 'PROCEED WITH CHANGES')

    def test_decide_all_clear_is_proceed(self):
        from run_experiment import decide
        sections = {'integrity_clean': True, 'stage_signal': True, 'msmi_signal': True}
        self.assertEqual(decide(sections), 'PROCEED')

@unittest.skipUnless(_have_sklearn(), 'numpy+sklearn required')
class TestReviewFixes(unittest.TestCase):
    def _row(self, **over):
        from features import FEATURE_KEYS
        row = {'day': 5, 'a': 'p', 'b': 'q', 'world_seed': 1, 'variant': 'development',
               'policy': 'random', 'collector_seed': 0, 'introduction_id': 'i1',
               'maturity_day': 9, 'label': 0, 'label_mutual': 0, 'label_date': 0,
               'horizon': 100,
               'features': dict((k, 0.0) for k in FEATURE_KEYS)}
        row['features'] = dict(row['features'], day=float(row['day']))
        row.update(over)
        if 'features' in over:
            row['features'] = dict(row['features'], day=float(row['day']))
        return row

    def test_insufficient_follow_up_yields_none_labels(self):
        import kit
        from collect import collect_rows
        from labels import group_events, maturity_day, label_msmi
        out = collect_rows(kit.generate(77, 100), collector_seed=6, days=10, follow_up=0)
        grouped = group_events(out['events'])
        exercised = False
        for row in out['rows']:
            evs = grouped[row['introduction_id']]
            true_maturity = maturity_day(evs)
            if true_maturity is None or true_maturity > row['horizon']:
                self.assertIsNone(row['label'],
                                  'censored outcome must be None, never 0')
                exercised = True
            else:
                self.assertEqual(row['label'],
                                 label_msmi(evs, row['day'], row['horizon']))
        self.assertTrue(exercised,
                        'full event record must expose censoring at short follow-up')
        full = collect_rows(kit.generate(77, 100), collector_seed=6, days=10, follow_up=40)
        self.assertTrue(all(r['label'] is not None for r in full['rows']))

    def test_rows_are_stamped_with_horizon(self):
        import kit
        from collect import collect_rows
        out = collect_rows(kit.generate(78, 80), collector_seed=1, days=8, follow_up=40)
        self.assertTrue(all('horizon' in r for r in out['rows']))

    def test_audit_rows_scopes_duplicates_to_one_rollout(self):
        from integrity import audit_rows
        # same (day, pair) in two different rollouts of the same world: legal
        base = self._row(collector_seed=0)
        other = self._row(collector_seed=1, introduction_id='i2')
        self.assertEqual(audit_rows([base, other], horizon=100), [])
        # same key inside ONE rollout: illegal
        self.assertTrue(any('duplicate' in v for v in
                            audit_rows([base, dict(base)], horizon=100)))
        # premature label still detected against the row's own horizon
        bad = self._row(label=None, maturity_day=6, horizon=6)
        self.assertTrue(any('premature' in v for v in audit_rows([bad], horizon=6)))

    def test_static_source_audit_flags_hidden_member_reads(self):
        from integrity import audit_source
        self.assertEqual(audit_source(), [])
        planted = "v = world['members'][0]['truth']\nw = m['response_rate']\n"
        violations = audit_source({'planted.py': planted})
        self.assertEqual(len(violations), 2, violations)

    def test_policy_ignores_injected_hidden_fields(self):
        import copy
        import kit
        from collect import RandomCollector
        sim = kit.Simulator(kit.generate(79, 100))
        for _ in range(6):
            sim.resolve_asks(kit.baseline_asks(sim.observe()))
            sim.advance(kit.baseline_match(sim.observe()))
        state = sim.observe()
        poisoned = copy.deepcopy(state)
        for m in poisoned['members']:
            m['truth'] = {'relationship_goal': 'exploring'}
            m['bias'] = 99.0
            m['response_rate'] = 0.0
            m['exit_day'] = 3
            m['ask_log'] = []
        for seed in (1, 2):
            a = RandomCollector(seed=seed)
            b = RandomCollector(seed=seed)
            self.assertEqual(a.asks(state), b.asks(poisoned))
            self.assertEqual(a.match(state), b.match(poisoned))

    def test_stage_gate_uses_validation_prevalence(self):
        from run_experiment import compute_criteria, AP_LIFT_STAGE
        train_eval = {'targets': {
            'mutual': {'train_n': 100, 'train_pos': 10, 'val_n': 100, 'val_pos': 50,
                       'models': {'hist_gb': {'avg_precision': 0.52, 'roc_auc': 0.6}}},
            'date': {'train_n': 100, 'train_pos': 11, 'val_n': 100, 'val_pos': 50,
                     'models': {'hist_gb': {'avg_precision': 0.30, 'roc_auc': 0.55}}},
            'msmi': {'train_n': 100, 'train_pos': 1, 'val_n': 100, 'val_pos': 2,
                     'models': {'hist_gb': {'avg_precision': 0.03, 'roc_auc': 0.60}}}}}
        report = compute_criteria(train_eval, integrity_clean=True)
        # 0.52 < 1.3 * 0.50 (val prevalence): must NOT pass on train prevalence (0.10)
        self.assertFalse(report['stage_signal'], report)
        # msmi: 0.03 >= 1.1 * 0.02 and AUC 0.60 >= 0.55 -> passes
        self.assertTrue(report['msmi_signal'], report)
        gated = compute_criteria(train_eval, integrity_clean=False)
        self.assertFalse(gated['integrity_clean'], 'integrity flag must be carried through')
        from run_experiment import decide
        self.assertEqual(decide(gated), 'STOP', 'integrity failure overrides any signal')

    def test_sort_rows_makes_report_inputs_reproducible(self):
        import random
        from run_experiment import sort_rows
        rows = [self._row(world_seed=s, day=d, a='a%d' % s, b='b%d' % s)
                for s in (1, 2, 3) for d in (4, 5)]
        shuffled = list(rows)
        random.Random(0).shuffle(shuffled)
        first = [ (r['world_seed'], r['day'], r['a']) for r in sort_rows(list(rows)) ]
        second = [ (r['world_seed'], r['day'], r['a']) for r in sort_rows(shuffled) ]
        self.assertEqual(first, second)
        self.assertEqual(first, [ (r['world_seed'], r['day'], r['a']) for r in rows ])


@unittest.skipUnless(_have_sklearn(), 'numpy+sklearn required')
class TestScaleUpAdditions(unittest.TestCase):
    """Scale-up run additions: AUC confidence intervals + split-overlap proof."""

    def _row(self, **over):
        from features import FEATURE_KEYS
        row = {'day': 5, 'a': 'p', 'b': 'q', 'world_seed': 1, 'variant': 'development',
               'policy': 'random', 'collector_seed': 0, 'introduction_id': 'i1',
               'maturity_day': 9, 'label': 0, 'label_mutual': 0, 'label_date': 0,
               'horizon': 100,
               'features': dict((k, 0.0) for k in FEATURE_KEYS)}
        row.update(over)
        return row

    def test_auc_ci_matches_hand_computed_hanley_mcneil(self):
        from analyze import auc_ci
        auc, n_pos, n_neg = 0.7, 100, 400
        q1 = auc / (2 - auc)
        q2 = 2 * auc * auc / (1 + auc)
        se = ((auc * (1 - auc) + (n_pos - 1) * (q1 - auc * auc)
               + (n_neg - 1) * (q2 - auc * auc)) / (n_pos * n_neg)) ** 0.5
        lo, hi = auc_ci(auc, n_pos, n_neg)
        self.assertAlmostEqual(lo, max(0.0, auc - 1.96 * se), places=12)
        self.assertAlmostEqual(hi, min(1.0, auc + 1.96 * se), places=12)
        self.assertLess(lo, auc)
        self.assertGreater(hi, auc)

    def test_evaluate_attaches_auc_ci_and_none_for_single_class(self):
        from analyze import evaluate
        y = [0] * 40 + [1] * 10
        scores = [i / 100.0 for i in range(40)] + [0.1 + i / 100.0 for i in range(10)]
        metrics = evaluate(y, scores)
        self.assertIn('auc_ci95', metrics)
        lo, hi = metrics['auc_ci95']
        self.assertLess(lo, metrics['roc_auc'])
        self.assertGreater(hi, metrics['roc_auc'])
        self.assertGreaterEqual(lo, 0.0)
        self.assertLessEqual(hi, 1.0)
        single = evaluate([1, 1], [0.4, 0.6])
        self.assertIsNone(single['roc_auc'])
        self.assertIsNone(single['auc_ci95'])

    def test_split_overlap_zero_for_real_split_and_positive_when_poisoned(self):
        from analyze import split_overlap, world_split
        rows = [self._row(world_seed=s, label=s % 2) for s in range(1, 11)]
        train, val = world_split(rows, val_frac=0.2, split_seed=0)
        self.assertEqual(split_overlap(train, val), {'worlds': 0, 'seeds': 0})
        poisoned = split_overlap(rows[:6], rows[4:])
        self.assertGreater(poisoned['worlds'], 0)
        self.assertGreater(poisoned['seeds'], 0)

    def test_train_and_evaluate_reports_zero_split_overlap(self):
        from run_experiment import train_and_evaluate
        rows = [self._row(world_seed=s, label=s % 2, label_mutual=s % 2,
                          label_date=s % 2, a='a%d' % s, b='b%d' % s)
                for s in range(1, 11)]
        out = train_and_evaluate(rows)
        self.assertEqual(out['split_overlap']['worlds'], 0)
        self.assertEqual(out['split_overlap']['seeds'], 0)

    def test_build_report_shows_gates_auc_ci_and_split_overlap(self):
        from run_experiment import build_report
        metrics = {'roc_auc': 0.52, 'avg_precision': 0.011, 'log_loss': 0.06,
                   'brier': 0.011, 'n': 100, 'positives': 7,
                   'auc_ci95': (0.45, 0.59)}
        entry = {'train_n': 80, 'train_pos': 6, 'val_n': 20, 'val_pos': 1,
                 'models': {'constant': dict(metrics), 'hist_gb': dict(metrics)}}
        report = {
            'n_rollouts': 10, 'n_random': 8, 'n_greedy': 2, 'n_worlds': 5,
            'days': 60, 'follow_up': 40, 'n_rows': 100,
            'integrity': {'ok': True, 'checks': {'determinism': True},
                          'violations': []},
            'dataset_audit_violations': 0, 'source_audit': [], 'n_immature': 0,
            'leakage': [],
            'coverage': {'random': {'rollouts': 8, 'opportunities': 100,
                                    'chosen': 60, 'fraction': 0.6},
                         'greedy': {'rollouts': 2, 'opportunities': 20,
                                    'chosen': 12, 'fraction': 0.6}},
            'variant_balance': {'development': {'rows': 100, 'positives': 7}},
            'train_eval': {'train_worlds': 4, 'val_worlds': 1,
                           'split_overlap': {'worlds': 0, 'seeds': 0},
                           'targets': {'msmi': dict(entry)},
                           'top_features_mutual': []},
            'calibration': {'msmi': []},
            'criteria': {'integrity_clean': True, 'stage_signal': True,
                         'msmi_signal': False},
            'decision': 'PROCEED WITH CHANGES', 'decision_notes': []}
        text = build_report(report)
        self.assertIn(
            'MSMI signal (val AUC >= 0.55 and AP >= 1.1x prevalence) ... False',
            text)
        self.assertIn('AUC CI95 [0.4500, 0.5900]', text)
        self.assertIn('split overlap', text)
        self.assertIn('0 worlds / 0 seeds', text)


@unittest.skipUnless(_have_sklearn(), 'numpy+sklearn required')
class TestExportInferenceContract(unittest.TestCase):
    """T13: pure walk matches sklearn (<= threshold + missing branch)."""

    @classmethod
    def setUpClass(cls):
        import numpy as np
        from sklearn.ensemble import HistGradientBoostingClassifier
        # crafted 1-D data: split threshold = midpoint 1.5 between values 1.0 and 2.0
        X = np.array([[v] for v in [0.0, 1.0, 2.0, 3.0, 4.0] * 10], dtype=float)
        y = (X[:, 0] >= 1.5).astype(int)
        cls.m = HistGradientBoostingClassifier(random_state=0, max_iter=1,
                                               learning_rate=1.0,
                                               max_leaf_nodes=2).fit(X, y)
        import policy
        from export_model import sk_model_to_dict
        d = sk_model_to_dict(cls.m, ['f0'], 0.5)
        cls.pure = {'schema': 1, 'n_features': 1, 'feature_keys': ['f0'],
                    'floor': 0.5, 'baseline': d['baseline'], 'trees': d['trees']}

    @staticmethod
    def _sigmoid(raw):
        import math
        return 1.0 / (1.0 + math.exp(-raw)) if raw >= 0 else math.exp(raw) / (1.0 + math.exp(raw))

    def test_t13_parity_on_probes(self):
        import numpy as np
        import policy
        probes = np.array([[0.0], [1.0], [1.5], [2.0], [3.0], [float('nan')]])
        expect = self.m.predict_proba(probes)[:, 1]
        for i, row in enumerate(probes):
            got = policy.score_row(self.pure, [float(row[0])])
            self.assertLessEqual(abs(got - float(expect[i])), 1e-9,
                                 msg='probe %r: pure=%r sklearn=%r'
                                     % (row.tolist(), got, expect[i]))

    def test_t13_sample_exactly_at_threshold_takes_left_branch(self):
        import policy
        root = self.pure['trees'][0][0]
        threshold = root[1]
        left_leaf = self.pure['trees'][0][root[2]][0]
        self.assertAlmostEqual(policy.score_row(self.pure, [threshold]),
                               self._sigmoid(self.pure['baseline'] + left_leaf), places=15)

def _load_scale_rows():
    path = REPO_ROOT / 'research' / 'out_scale800' / 'rows.csv'
    if not path.exists():
        raise unittest.SkipTest('research/out_scale800/rows.csv not present')
    from export_model import rows_from_csv
    return rows_from_csv(path)


@unittest.skipUnless(_have_sklearn(), 'numpy+sklearn required')
class TestExportParityGates(unittest.TestCase):
    """T12 (HARD): per-row parity atol 1e-9 rtol 0. T14: val AUC 0.5937 +/- 0.001."""

    @classmethod
    def setUpClass(cls):
        import numpy as np
        import analyze
        import policy
        rows = _load_scale_rows()
        train_rows, val_rows = analyze.world_split(rows, val_frac=0.2, split_seed=0)
        cls.Xtr, cls.ytr, _ = analyze.build_dataset(train_rows, target='label')
        cls.Xva, cls.yva, _ = analyze.build_dataset(val_rows, target='label')
        cls.sk = dict(analyze.fit_models(cls.Xtr, cls.ytr))['hist_gb']
        cls.pm = policy.load_model()
        if cls.pm is None:
            raise AssertionError('MODEL_B64 empty/invalid - run: python -m research.export_model')
        rng = np.random.RandomState(0)
        cls.sample_idx = rng.choice(len(cls.Xtr), size=500, replace=False)

    def test_t12_row_parity_hard_gate(self):
        import policy
        worst = 0.0
        for i in self.sample_idx:
            x = [float(v) for v in self.Xtr[i]]
            pure = policy.score_row(self.pm, x)
            sk = float(self.sk.predict_proba(self.Xtr[i:i + 1])[0, 1])
            worst = max(worst, abs(pure - sk))
        self.assertLessEqual(worst, 1e-9, 'T12 HARD GATE violated: max abs diff %r' % worst)

    def test_t14_val_auc_reproduction(self):
        import numpy as np
        from sklearn.metrics import roc_auc_score
        auc_sk = float(roc_auc_score(self.yva, self.sk.predict_proba(self.Xva)[:, 1]))
        self.assertLess(abs(auc_sk - 0.5937), 0.001,
                        'refit sklearn val AUC %r drifted from reported 0.5937' % auc_sk)
        import policy
        pure = np.array([policy.score_row(self.pm, [float(v) for v in row])
                         for row in self.Xva])
        auc_pure = float(roc_auc_score(self.yva, pure))
        self.assertLess(abs(auc_pure - 0.5937), 0.001,
                        'pure scorer val AUC %r drifted from 0.5937' % auc_pure)


@unittest.skipUnless(_have_sklearn(), 'numpy+sklearn required')
class TestExportCheckMode(unittest.TestCase):
    """--check verifies the embedded blob read-only: never rewrites policy.py."""

    @classmethod
    def setUpClass(cls):
        rows_path = REPO_ROOT / 'research' / 'out_scale800' / 'rows.csv'
        if not rows_path.exists():
            raise unittest.SkipTest(
                'research/out_scale800/rows.csv not present '
                '(bulk input excluded from the curated branch)')

    def test_check_mode_passes_and_does_not_write_policy(self):
        import subprocess
        import sys
        policy_path = REPO_ROOT / 'policy.py'
        before = policy_path.read_bytes()
        proc = subprocess.run(
            [sys.executable, '-m', 'research.export_model', '--check'],
            cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=900)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn('check OK', proc.stdout)
        self.assertEqual(policy_path.read_bytes(), before,
                         '--check must never rewrite policy.py')