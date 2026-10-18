"""Test suite for the method tournament. Run from repo root:
python -m unittest research.method_tournament.test_tournament -v"""
import json
import pathlib
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

METHODS_JSON = HERE / 'methods.json'
DESIGN_MD = HERE / 'design.md'
REQUIRED = ('method_id', 'name', 'mechanism', 'required_inputs', 'asking', 'waiting',
            'matching_optimization', 'computational_complexity', 'implementation_status',
            'known_risks', 'literature_inspiration')


class RegistrySchemaTests(unittest.TestCase):
    def setUp(self):
        self.methods = json.loads(METHODS_JSON.read_text(encoding='utf-8'))['methods']

    def test_thirty_entries_numbered_m01_to_m30(self):
        prefixes = [m['method_id'].split('_')[0] for m in self.methods]
        self.assertEqual(prefixes, ['m%02d' % i for i in range(1, 31)])

    def test_required_fields_and_types(self):
        for m in self.methods:
            for key in REQUIRED:
                self.assertIn(key, m, '%s missing %s' % (m.get('method_id'), key))
            self.assertIn(m['asking'], ('active', 'baseline'))
            self.assertIsInstance(m['waiting'], bool)
            self.assertIsInstance(m['matching_optimization'], bool)
            self.assertTrue(m['file'].startswith('methods_') or m['file'] == 'kit.baseline')

    def test_group_counts(self):
        counts = {}
        for m in self.methods:
            counts[m['group']] = counts.get(m['group'], 0) + 1
        self.assertEqual(counts, {'A': 8, 'B': 7, 'C': 8, 'D': 5, 'E': 2})

    def test_substitutions_documented(self):
        by_id = {m['method_id']: m for m in self.methods}
        self.assertIn('control', by_id['m07_prune_and_greedy'].get('substituted_from', ''))
        self.assertIn('exit_day', by_id['m21_delay_cost_threshold'].get('substituted_from', ''))

    def test_design_lists_every_method(self):
        text = DESIGN_MD.read_text(encoding='utf-8')
        for m in self.methods:
            self.assertIn(m['method_id'], text, m['method_id'])


class CommonHelperTests(unittest.TestCase):
    @staticmethod
    def _state(seed=90210, variant='development', day=30):
        from kit import Simulator, generate, baseline_asks, baseline_match
        sim = Simulator(generate(seed, 200, 'evaluation', variant))
        for _ in range(day):
            sim.resolve_asks(baseline_asks(sim.observe()))
            sim.advance(baseline_match(sim.observe()))
        return sim.observe()

    def test_feasible_edges_covers_every_baseline_pair(self):
        import common
        from kit import baseline_match
        state = self._state(day=38)
        edge_keys = {common.pair_key(a, b) for a, b, s in common.feasible_edges(state)}
        for pair in baseline_match(state):
            self.assertIn(common.pair_key(*pair), edge_keys)

    def test_base_score_matches_kit_formula(self):
        import common
        from kit import SOFT
        state = self._state()
        avail = [m for m in state['members'] if m['available']]
        a, b = avail[0], avail[1]
        expected = sum(a['fields'].get(k) is not None and a['fields'].get(k) == b['fields'].get(k)
                       for k in SOFT)
        self.assertEqual(common.base_score(a, b), expected)

    def test_directional_is_asymmetric_on_missingness(self):
        import common
        from kit import SOFT
        full_a = {'fields': {k: None for k in SOFT}}
        full_b = {'fields': {k: None for k in SOFT}}
        full_a['fields']['relationship_goal'] = 'long_term'
        full_a['fields']['relationship_pace'] = 'slow'
        full_b['fields']['relationship_goal'] = 'long_term'
        self.assertGreater(common.directional(full_a, full_b), common.directional(full_b, full_a))

    def test_ctx_degrees_and_avg(self):
        import common
        state = self._state(day=0)
        ctx = common.make_ctx(state)
        total_deg = sum(ctx['deg'].values())
        self.assertEqual(total_deg, 2 * len(ctx['edges']))
        n_avail = sum(1 for m in state['members'] if m['available'])
        self.assertEqual(ctx['n_avail'], n_avail)
        self.assertAlmostEqual(ctx['avg_deg'], 2.0 * len(ctx['edges']) / max(1, n_avail))

    def test_alt_for_excludes_current_partner(self):
        import common
        state = self._state(day=38)
        ctx = common.make_ctx(state)
        a, b, s = ctx['edges'][0]
        alt = common.alt_for(ctx, a, b)
        others = [sc for sc, o in ctx['inc'][a] if o != b]
        self.assertEqual(alt, max(others) if others else 0)

    def test_wait_days(self):
        import common
        self.assertEqual(common.wait_days({'arrived_day': 7}, 10), 3)


class FrozenConstantsTests(unittest.TestCase):
    def test_design_constants_frozen_common(self):
        import common
        self.assertEqual(common.REL, ('relationship_goal', 'relationship_pace',
                                      'lifestyle', 'conversations'))
        self.assertEqual(common.PROTECT_DAYS, 3)
        self.assertEqual(common.QUOTA_DIVISOR, 2)
        self.assertEqual(common.PATIENT_MIN_SCORE, 3)
        self.assertEqual((common.TIME_T0, common.TIME_STEP), (4, 20))
        self.assertEqual((common.DELAY_T0, common.DELAY_STEP), (4, 15))
        self.assertEqual(common.THIN_AVG_DEG, 2.0)
        self.assertEqual(common.HYBRID_MIN_SCORE, 4)
        self.assertEqual(common.HYBRID_AVG_DEG, 3.0)
        self.assertEqual(common.STRONG_SCORE, 3)
        self.assertEqual(common.PRUNE_MIN_SCORE, 2)
        self.assertEqual(common.HUNGARIAN_NODE_CAP, 180)
        self.assertEqual(common.AUGMENT_ROUNDS_CAP, 50)
        self.assertEqual(common.SOFT_ASK_RESERVE, 3)
        self.assertEqual(common.VOI_EVAL_CAP, 96)


class AllocGreedyTests(unittest.TestCase):
    @staticmethod
    def _state(seed=90210, variant='development', day=30):
        from kit import Simulator, generate, baseline_asks, baseline_match
        sim = Simulator(generate(seed, 200, 'evaluation', variant))
        for _ in range(day):
            sim.resolve_asks(baseline_asks(sim.observe()))
            sim.advance(baseline_match(sim.observe()))
        return sim.observe()

    def test_greedy_take_identical_to_kit_baseline_match(self):
        import common, alloc
        from kit import baseline_match
        state = self._state()
        self.assertEqual(alloc.greedy_take(common.feasible_edges(state)),
                         baseline_match(state))

    def test_greedy_take_matches_kit_across_fixture_matrix(self):
        # F-05: seeds {90210, 90211} x 6 variants x days {0,1,5,15,30,45,59}
        import common, alloc
        from kit import Simulator, generate, baseline_asks, baseline_match
        checked = 0
        for seed in (90210, 90211):
            for variant in ('development', 'sparse', 'cold_start',
                            'delayed', 'shift', 'drift'):
                sim = Simulator(generate(seed, 200, 'evaluation', variant))
                for day in range(60):
                    if day in (0, 1, 5, 15, 30, 45, 59):
                        state = sim.observe()
                        self.assertEqual(
                            alloc.greedy_take(common.feasible_edges(state)),
                            baseline_match(state), (seed, variant, day))
                        checked += 1
                    sim.resolve_asks(baseline_asks(sim.observe()))
                    sim.advance(baseline_match(sim.observe()))
        self.assertEqual(checked, 2 * 6 * 7)

    def test_greedy_take_is_order_invariant(self):
        import common, alloc
        state = self._state(day=38)
        reversed_state = dict(state)
        reversed_state['members'] = list(reversed(state['members']))
        self.assertEqual(alloc.greedy_take(common.feasible_edges(state)),
                         alloc.greedy_take(common.feasible_edges(reversed_state)))

    def test_take_ordered_respects_primary_key(self):
        import alloc
        edges = [('a', 'b', 5), ('c', 'd', 1)]
        key_fn = lambda e: (-(9 if e[0] == 'c' else 1), -e[2])
        self.assertEqual(alloc.take_ordered(edges, key_fn), [['c', 'd'], ['a', 'b']])

    def test_filter_min_score(self):
        import alloc
        edges = [('a', 'b', 5), ('c', 'd', 2)]
        self.assertEqual(alloc.filter_min_score(edges, 3), [('a', 'b', 5)])

    def test_quota_half_ceiling(self):
        import alloc
        five = [[str(i), 'x'] for i in range(5)]
        four = [[str(i), 'x'] for i in range(4)]
        self.assertEqual(alloc.quota_half(five), five[:3])
        self.assertEqual(alloc.quota_half(four), four[:2])
        self.assertEqual(alloc.quota_half([]), [])

    def test_protect_filter_drops_new_arrivals(self):
        import alloc
        ctx = {'day': 10, 'members': {
            'a': {'arrived_day': 9}, 'b': {'arrived_day': 0},
            'c': {'arrived_day': 8}, 'd': {'arrived_day': 1}}}
        self.assertEqual(alloc.protect_filter([('a', 'b', 5), ('c', 'd', 5)], ctx), [])
        self.assertEqual(alloc.protect_filter([('b', 'd', 5)], ctx), [('b', 'd', 5)])

    def test_thin_and_hybrid_gates(self):
        import alloc
        self.assertTrue(alloc.thin_wait({'avg_deg': 1.9}))
        self.assertFalse(alloc.thin_wait({'avg_deg': 2.0}))
        self.assertTrue(alloc.hybrid_favorable({'max_base': 4, 'avg_deg': 0.0}))
        self.assertTrue(alloc.hybrid_favorable({'max_base': 1, 'avg_deg': 3.0}))
        self.assertFalse(alloc.hybrid_favorable({'max_base': 3, 'avg_deg': 2.9}))


class AllocGraphTests(unittest.TestCase):
    @staticmethod
    def _random_edges(rng, n_nodes=6, p=0.6):
        import string
        nodes = [string.ascii_lowercase[i] for i in range(n_nodes)]
        return [(nodes[i], nodes[j], rng.randint(0, 7))
                for i in range(n_nodes) for j in range(i + 1, n_nodes)
                if rng.random() < p]

    @staticmethod
    def _weight_total(pairs, edges):
        import common
        w = {common.pair_key(a, b): s for a, b, s in edges}
        return sum(w[common.pair_key(x, y)] for x, y in pairs)

    def test_two_color_bipartite_and_odd_cycle(self):
        import alloc
        self.assertIsNotNone(alloc.two_color([('a', 'b', 1), ('b', 'c', 1), ('c', 'd', 1)]))
        self.assertIsNone(alloc.two_color([('a', 'b', 1), ('b', 'c', 1), ('c', 'a', 1)]))
        self.assertEqual(alloc.two_color([]), ([], []))

    def test_max_cardinality_equals_brute_on_random_bipartite(self):
        import alloc, random
        rng = random.Random(7)
        for _ in range(25):
            left = ['l%d' % i for i in range(3)]
            right = ['r%d' % i for i in range(3)]
            edges = [(u, v, rng.randint(0, 7)) for u in left for v in right
                     if rng.random() < 0.5]
            got = alloc.max_cardinality(edges)
            self.assertIsNotNone(got)
            want = alloc.brute_max_weight([(a, b, 1) for a, b, s in edges])
            self.assertEqual(len(got), want[1])
            ids = [m for p in got for m in p]
            self.assertEqual(len(ids), len(set(ids)))

    def test_hungarian_equals_brute_on_random_bipartite(self):
        import alloc, random
        rng = random.Random(11)
        for _ in range(25):
            left = ['l%d' % i for i in range(4)]
            right = ['r%d' % i for i in range(4)]
            weight = {}
            for u in left:
                for v in right:
                    if rng.random() < 0.5:
                        w = rng.randint(1, 7)
                        weight[(u, v)] = w
                        weight[(v, u)] = w
            pairs = alloc.hungarian_max_weight(left, right, weight)
            total = sum(weight[p] for p in pairs)
            edges = [(u, v, w) for (u, v), w in weight.items() if u < v]
            self.assertEqual(total, alloc.brute_max_weight(edges)[1])

    def test_max_cardinality_none_on_odd_cycle(self):
        import alloc
        self.assertIsNone(alloc.max_cardinality([('a', 'b', 1), ('b', 'c', 1), ('c', 'a', 1)]))

    def test_one_swap_improves_or_holds_and_idempotent(self):
        import alloc, random
        rng = random.Random(3)
        edges = self._random_edges(rng, 6, 0.6)
        base = alloc.greedy_take(edges)
        once = alloc.one_swap_improve(base, edges)
        twice = alloc.one_swap_improve(once, edges)
        self.assertGreaterEqual(self._weight_total(once, edges), self._weight_total(base, edges))
        self.assertEqual(twice, once)

    def test_augment3_grows_cardinality_without_overlap(self):
        import alloc, random
        rng = random.Random(5)
        edges = self._random_edges(rng, 6, 0.6)
        base = alloc.greedy_take(edges)
        grown = alloc.augment3_improve(base, edges, 50)
        self.assertGreaterEqual(len(grown), len(base))
        ids = [m for p in grown for m in p]
        self.assertEqual(len(ids), len(set(ids)))

    def test_hungarian_latency_on_dense_day59(self):
        import alloc, common, time
        from kit import Simulator, generate, baseline_asks, baseline_match
        sim = Simulator(generate(90215, 200, 'evaluation', 'development'))
        for _ in range(59):
            sim.resolve_asks(baseline_asks(sim.observe()))
            sim.advance(baseline_match(sim.observe()))
        ctx = common.make_ctx(sim.observe())
        edges = ctx['edges']
        wmap = {}
        for a, b, s in edges:
            wmap[(a, b)] = s
            wmap[(b, a)] = s
        started = time.perf_counter()
        colored = alloc.two_color(edges)
        if colored is not None:
            alloc.hungarian_max_weight(colored[0], colored[1], wmap)
        else:
            # F-08: never silently skip - exercise the non-bipartite fallback too
            alloc.one_swap_improve(alloc.greedy_take(edges), edges)
            alloc.augment3_improve(alloc.greedy_take(edges), edges, 50)
        self.assertLess(time.perf_counter() - started, 5.0)

    def test_hungarian_latency_forced_bipartite_n176(self):
        # F-06/F-08: forced branch (always bipartite), n = 176 <= HUNGARIAN_NODE_CAP
        import alloc, common, time
        left = ['l%03d' % i for i in range(88)]
        right = ['r%03d' % i for i in range(88)]
        weight = {}
        for i, u in enumerate(left):
            for j, v in enumerate(right):
                w = 1 + ((i * 17 + j * 13) % 7)
                weight[(u, v)] = w
                weight[(v, u)] = w
        edges = [(u, v, weight[(u, v)]) for u in left for v in right]
        started = time.perf_counter()
        colored = alloc.two_color(edges)
        self.assertIsNotNone(colored)
        pairs = alloc.hungarian_max_weight(colored[0], colored[1], weight)
        self.assertLess(time.perf_counter() - started, 5.0)
        self.assertTrue(pairs)

    def test_fallback_primitives_forced_odd_cycle(self):
        # F-08: forced non-bipartite branch - fallbacks must actually run
        import alloc, time
        odd = [('a', 'b', 1), ('b', 'c', 1), ('c', 'a', 1)]
        self.assertIsNone(alloc.two_color(odd))
        base = alloc.greedy_take(odd)
        started = time.perf_counter()
        fb1 = alloc.augment3_improve(base, odd, 50)
        fb2 = alloc.one_swap_improve(base, odd)
        self.assertLess(time.perf_counter() - started, 5.0)
        self.assertTrue(fb1)
        self.assertTrue(fb2)

    def test_augment3_shared_free_neighbor_skipped_safely(self):
        # F-18: single free node adjacent to both matched endpoints -> y == z skip
        import alloc
        edges = [('a', 'b', 5), ('a', 'c', 4), ('b', 'c', 4)]
        base = alloc.greedy_take(edges)
        grown = alloc.augment3_improve(base, edges, 50)
        ids = [m for p in grown for m in p]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(grown), 1)
        self.assertEqual(grown, alloc.augment3_improve(grown, edges, 50))


BANNED_NAMES = {'truth', 'bias', 'response_rate', 'second_bias', 'exit_day',
                'seed', 'variant', 'events'}
BANNED_CALLS = {'eval', 'exec', 'compile', '__import__', 'getattr', 'setattr',
                'delattr', 'globals', 'locals', 'vars', 'open'}
BANNED_DUNDERS = {'__subclasses__', '__globals__', '__builtins__', '__code__',
                  '__class__', '__bases__', '__mro__', '__dict__', '__bases__',
                  '__mro__', '__qualname__', '__module__'}
BANNED_MODULES_METHODS = {'os', 'sys', 'subprocess', 'importlib', 'inspect',
                          'builtins', 'socket', 'ssl', 'urllib', 'http',
                          'pickle', 'ctypes', 'multiprocessing', 'threading',
                          'tempfile', 'shutil', 'pathlib', 'platform'}
LAUNCHER_ALLOWED_IMPORTS = {'pathlib', 'sys', '_cli', 'registry'}
GENPOLICIES_ALLOWED_IMPORTS = {'pathlib', 'sys', 'registry'}
CLI_ALLOWED_IMPORTS = {'json', 'sys'}


def run_inprocess(fn, world, days=60):
    """Mirror evaluate.episode exactly, but call fn directly (no subprocess).
    Used by unit tests for semantics validation on small worlds; official-size (n=200)
    validation happens in the smoke phase."""
    from kit import Simulator, VERSION
    sim = Simulator(world)
    memory = None
    for _ in range(days):
        for phase in ('ask', 'match'):
            response = fn({'schema_version': VERSION, 'phase': phase,
                           'state': sim.observe(), 'memory': memory})
            memory = response['memory']
            if phase == 'ask':
                sim.resolve_asks(response['asks'])
            else:
                sim.advance(response['pairs'])
    for _ in range(40):
        sim.advance([])
    return sim.metrics()


class LeakScanTests(unittest.TestCase):
    @staticmethod
    def _imported_modules(tree):
        import ast
        mods = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                mods.update((alias.name.split('.')[0]) for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                mods.add(node.module.split('.')[0])
        return mods

    def test_no_hidden_state_access(self):
        import ast
        targets = [HERE / n for n in ('common.py', 'alloc.py', '_cli.py',
                                      'registry.py', 'gen_policies.py')]
        targets += sorted(HERE.glob('methods_*.py'))
        policies_dir = HERE / 'policies'
        if policies_dir.exists():
            targets += sorted(policies_dir.glob('*.py'))
        scanned = 0
        for path in targets:
            if not path.exists():
                continue
            scanned += 1
            tree = ast.parse(path.read_text(encoding='utf-8'))
            # F-16: import rules per file class
            mods = self._imported_modules(tree)
            if path.name.startswith('m') and path.name.endswith('.py') \
                    and path.parent.name == 'policies':
                bad_mods = mods - LAUNCHER_ALLOWED_IMPORTS
            elif path.name == 'gen_policies.py':
                bad_mods = mods - GENPOLICIES_ALLOWED_IMPORTS
            elif path.name == '_cli.py':
                bad_mods = mods - CLI_ALLOWED_IMPORTS
            elif path.name.startswith('methods_'):
                bad_mods = mods & BANNED_MODULES_METHODS
            else:
                bad_mods = mods & BANNED_MODULES_METHODS
            if bad_mods:
                self.fail('%s imports banned module(s) %r'
                          % (path.name, sorted(bad_mods)))
            for node in ast.walk(tree):
                bad = None
                if isinstance(node, ast.Name) and node.id in BANNED_NAMES:
                    bad = node.id
                elif isinstance(node, ast.Name) and node.id in BANNED_CALLS:
                    bad = node.id + ' (banned call)'
                elif isinstance(node, ast.Attribute) and node.attr in BANNED_NAMES:
                    bad = node.attr
                elif isinstance(node, ast.Attribute) and node.attr in BANNED_CALLS:
                    bad = node.attr + ' (banned call)'
                elif isinstance(node, ast.Attribute) and node.attr in BANNED_DUNDERS:
                    bad = node.attr + ' (banned dunder)'
                elif isinstance(node, ast.Constant) and isinstance(node.value, str) \
                        and node.value in BANNED_NAMES:
                    bad = node.value
                elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                        and node.func.id in BANNED_CALLS:
                    bad = node.func.id + ' (banned call)'
                if bad:
                    self.fail('%s references banned name %r at line %d'
                              % (path.name, bad, node.lineno))
        self.assertGreaterEqual(scanned, 6)

    def test_state_protocol_carries_no_banned_keys(self):
        # F-16 runtime: the observe() state itself never exposes banned inputs
        import json
        state = CommonHelperTests._state(day=30)
        blob = json.dumps(state, sort_keys=True)
        for key in ('truth', 'bias', 'response_rate', 'second_bias',
                    'exit_day', 'seed', 'variant'):
            self.assertNotIn('"%s"' % key, blob, key)

    def test_methods_never_touch_trusted_generators(self):
        # F-16 runtime negative: patch kit entry points to raise; decide fns must not notice
        import kit
        from kit import VERSION
        from registry import REGISTRY
        import evaluate
        state = CommonHelperTests._state(day=30)
        names = ('generate', 'Simulator', 'rollout', 'rand_for')
        saved = {n: getattr(kit, n) for n in names}

        def boom(*_a, **_k):
            raise AssertionError('decide fn touched a banned kit entry point')

        try:
            for n in names:
                setattr(kit, n, boom)
            for mid in sorted(REGISTRY):
                for phase in ('ask', 'match'):
                    resp = REGISTRY[mid]({'schema_version': VERSION,
                                          'phase': phase, 'state': state,
                                          'memory': None})
                    evaluate.validate_response(resp, phase)
        finally:
            for n, fn in saved.items():
                setattr(kit, n, fn)


class HashSeedTests(unittest.TestCase):
    def test_method_digests_stable_across_hash_seeds(self):
        # F-13: same actions under PYTHONHASHSEED = 0 / 1 / random
        import hashlib
        import os
        import subprocess
        import sys
        code = (
            "import json,sys;sys.path.insert(0,%r);"
            "from test_tournament import CommonHelperTests;"
            "from registry import REGISTRY;from kit import VERSION;"
            "state=CommonHelperTests._state(day=38);res={}\n"
            "for mid in sorted(REGISTRY):"
            " r=REGISTRY[mid]({'schema_version':VERSION,'phase':'match',"
            "'state':state,'memory':None});"
            " res[mid]=sorted(tuple(p) for p in r['pairs']);"
            "print(json.dumps(res,sort_keys=True))" % (str(HERE),))
        digests = {}
        for value in ('0', '1', 'random'):
            env = dict(os.environ, PYTHONHASHSEED=value)
            proc = subprocess.run([sys.executable, '-c', code],
                                  capture_output=True, text=True, env=env,
                                  timeout=600, cwd=str(ROOT))
            self.assertEqual(proc.returncode, 0, proc.stderr[-400:])
            digests[value] = hashlib.sha256(
                proc.stdout.strip().encode()).hexdigest()
        self.assertEqual(len(set(digests.values())), 1, digests)


class GroupATests(unittest.TestCase):
    EXPECTED = {'m01_greedy_baseline', 'm02_reciprocal_sum', 'm03_reciprocal_min',
                'm04_reciprocal_product', 'm05_harmonic_reciprocal', 'm06_bottleneck',
                'm07_prune_and_greedy', 'm08_weighted_compatibility'}

    def test_registry_contains_group_a(self):
        from registry import REGISTRY
        self.assertTrue(self.EXPECTED.issubset(set(REGISTRY)))

    def test_launchers_exist_for_registry(self):
        from registry import REGISTRY
        for mid in sorted(REGISTRY):
            self.assertTrue((HERE / 'policies' / (mid + '.py')).exists(), mid)

    def test_protocol_roundtrip_every_launcher(self):
        import evaluate
        import sys
        from kit import VERSION
        from registry import REGISTRY
        state0 = CommonHelperTests._state(day=0)
        state59 = CommonHelperTests._state(day=59)
        for mid in sorted(REGISTRY):
            cmd = [sys.executable, str(HERE / 'policies' / (mid + '.py')),
                   '--baseline', 'greedy']
            for phase, state in (('ask', state0), ('match', state59)):
                request = {'schema_version': VERSION, 'phase': phase,
                           'state': state, 'memory': None}
                response, _elapsed = evaluate.invoke(cmd, request)
                evaluate.validate_response(response, phase)

    def test_m01_matches_control_greedy(self):
        import evaluate
        import sys
        from kit import VERSION
        control = [sys.executable, str(ROOT / 'policy.py'), '--baseline', 'greedy']
        ours = [sys.executable,
                str(HERE / 'policies' / 'm01_greedy_baseline.py'), '--baseline', 'greedy']
        for phase, day in (('ask', 0), ('match', 30), ('match', 59)):
            request = {'schema_version': VERSION, 'phase': phase,
                       'state': CommonHelperTests._state(day=day), 'memory': None}
            expected, _ = evaluate.invoke(control, request)
            got, _ = evaluate.invoke(ours, request)
            self.assertEqual(got, expected, '%s@day%d' % (phase, day))

    def test_equal_float_ties_break_deterministically_by_pair_key(self):
        # F-13/m02/m08: float scores can tie exactly; pair_key must decide
        import alloc
        s1 = 1.0 / 3.0 + 1.0
        s2 = 1.0 + 2.0 / 6.0
        self.assertEqual(s1, s2)
        edges = [('b', 'c', s1), ('a', 'd', s2)]
        self.assertEqual(alloc.greedy_take(edges), [['a', 'd'], ['b', 'c']])
        self.assertEqual(alloc.greedy_take(list(reversed(edges))),
                         [['a', 'd'], ['b', 'c']])

    def test_deterministic_and_order_invariant_match_phase(self):
        import json
        from kit import VERSION
        from registry import REGISTRY
        state = CommonHelperTests._state(day=38)
        reversed_state = dict(state)
        reversed_state['members'] = list(reversed(state['members']))
        for mid in sorted(REGISTRY):
            fn = REGISTRY[mid]
            req = {'schema_version': VERSION, 'phase': 'match',
                   'state': state, 'memory': None}
            r1 = fn(dict(req))
            r2 = fn(dict(req))
            self.assertEqual(json.dumps(r1, sort_keys=True),
                             json.dumps(r2, sort_keys=True), mid)
            req2 = dict(req)
            req2['state'] = reversed_state
            r3 = fn(req2)
            self.assertEqual(sorted(tuple(p) for p in r1['pairs']),
                             sorted(tuple(p) for p in r3['pairs']), mid)

    def test_full_episode_groupA(self):
        from kit import generate
        from registry import REGISTRY
        for mid in sorted(REGISTRY):
            metrics = run_inprocess(REGISTRY[mid],
                                    generate(90210, 50, 'evaluation', 'development'))
            self.assertIn('msmi_per_100_arrived_members', metrics, mid)


class GroupBTests(unittest.TestCase):
    EXPECTED = {'m09_partner_scarcity', 'm10_degree_balanced', 'm11_scarcity_x_compat',
                'm12_regret_score', 'm13_opportunity_cost', 'm14_mutual_regret',
                'm15_reserve_high_option'}

    def test_registry_contains_group_b(self):
        from registry import REGISTRY
        self.assertTrue(self.EXPECTED.issubset(set(REGISTRY)))

    def test_full_episode_groupB(self):
        from kit import generate
        from registry import REGISTRY
        for mid in sorted(self.EXPECTED):
            metrics = run_inprocess(REGISTRY[mid],
                                    generate(90211, 50, 'evaluation', 'cold_start'))
            self.assertIn('msmi_per_100_arrived_members', metrics, mid)


class GroupCTests(unittest.TestCase):
    EXPECTED = {'m16_patient_policy', 'm17_daily_quota', 'm18_time_threshold',
                'm19_arrival_age', 'm20_new_arrival_protection',
                'm21_delay_cost_threshold', 'm22_market_thickness',
                'm23_hybrid_patient_greedy'}

    @staticmethod
    def _pair_state(base_target, day=12, wait_a=5, wait_b=5):
        """Two mutually feasible members sharing exactly base_target SOFT fields."""
        import common
        from kit import SOFT, OPTIONS
        state = dict(CommonHelperTests._state(day=day))
        edges = common.feasible_edges(state)
        if not edges:
            raise AssertionError('fixture world has no feasible pair at day=%d; fixture days must have edges' % day)
        a, b, _ = edges[0]
        mfs = {m['member_id']: m for m in state['members']}
        for i, k in enumerate(SOFT):
            mfs[a]['fields'][k] = OPTIONS[k][0]
            mfs[b]['fields'][k] = OPTIONS[k][0] if i < base_target else OPTIONS[k][1]
        mfs[a]['arrived_day'] = day - wait_a
        mfs[b]['arrived_day'] = day - wait_b
        state['members'] = [mfs[a], mfs[b]]
        return state, (a, b)

    @staticmethod
    def _match(mid, state):
        from registry import REGISTRY
        from kit import VERSION
        return REGISTRY[mid]({'schema_version': VERSION, 'phase': 'match',
                              'state': state, 'memory': None})

    @staticmethod
    def _keys(pairs):
        import common
        return [common.pair_key(p[0], p[1]) for p in pairs]

    def test_registry_contains_group_c(self):
        from registry import REGISTRY
        self.assertTrue(self.EXPECTED.issubset(set(REGISTRY)))

    def test_m16_patient_gate(self):
        import common
        state, pair = self._pair_state(1, day=12)
        self.assertEqual(self._match('m16_patient_policy', state)['pairs'], [])
        state5, _ = self._pair_state(5, day=12)
        resp = self._match('m16_patient_policy', state5)
        self.assertEqual(self._keys(resp['pairs']), [common.pair_key(*pair)])

    def test_m17_quota_property(self):
        import common, alloc
        state = CommonHelperTests._state(day=38)
        full = alloc.greedy_take(common.feasible_edges(state))
        resp = self._match('m17_daily_quota', state)
        self.assertEqual(len(resp['pairs']), (len(full) + 1) // 2)

    def test_m18_time_threshold_by_phase(self):
        state3, _ = self._pair_state(3, day=12)   # day<20 -> need 4
        self.assertEqual(self._match('m18_time_threshold', state3)['pairs'], [])
        state5, pair = self._pair_state(5, day=12)
        self.assertEqual(self._keys(self._match('m18_time_threshold', state5)['pairs']),
                         [__import__('common').pair_key(*pair)])
        state2, _ = self._pair_state(2, day=59)   # day>=40 -> need 2
        self.assertNotEqual(self._match('m18_time_threshold', state2)['pairs'], [])
        state1, _ = self._pair_state(1, day=59)
        self.assertEqual(self._match('m18_time_threshold', state1)['pairs'], [])

    def test_m19_first_pair_has_longest_wait(self):
        import common
        day = 38
        state = CommonHelperTests._state(day=day)
        ctx = common.make_ctx(state)
        resp = self._match('m19_arrival_age', state)
        if not ctx['edges']:
            self.fail('fixture day has no edges; fixture days must have edges')
        waits = {m['member_id']: common.wait_days(m, day) for m in state['members']}
        want = max(max(waits[a], waits[b]) for a, b, s in ctx['edges'])
        got = max(waits[x] for x in resp['pairs'][0])
        self.assertEqual(got, want)

    def test_m20_protection_window(self):
        import common
        fresh, pair = self._pair_state(5, day=12, wait_a=0, wait_b=5)
        self.assertEqual(self._match('m20_new_arrival_protection', fresh)['pairs'], [])
        aged, _ = self._pair_state(5, day=12, wait_a=5, wait_b=5)
        resp = self._match('m20_new_arrival_protection', aged)
        self.assertEqual(self._keys(resp['pairs']), [common.pair_key(*pair)])

    def test_m21_delay_cost_threshold(self):
        import common
        # wait 45 -> required score 1 (max(0, 4 - 45//15)); wait 0 -> required 4
        late, pair = self._pair_state(1, day=59, wait_a=45, wait_b=45)
        resp = self._match('m21_delay_cost_threshold', late)
        self.assertEqual(self._keys(resp['pairs']), [common.pair_key(*pair)])
        early, _ = self._pair_state(1, day=59, wait_a=0, wait_b=0)
        self.assertEqual(self._match('m21_delay_cost_threshold', early)['pairs'], [])
        early_strong, _ = self._pair_state(4, day=59, wait_a=0, wait_b=0)
        self.assertNotEqual(self._match('m21_delay_cost_threshold', early_strong)['pairs'], [])

    def test_m22_thin_branch_and_wiring(self):
        import common, alloc
        thin, _ = self._pair_state(5, day=12)   # 2 members, 1 edge -> avg_deg 1.0 < 2.0
        self.assertEqual(self._match('m22_market_thickness', thin)['pairs'], [])
        state = CommonHelperTests._state(day=38)
        ctx = common.make_ctx(state)
        resp = self._match('m22_market_thickness', state)
        if alloc.thin_wait(ctx):
            self.assertEqual(resp['pairs'], [])
        else:
            self.assertEqual(resp['pairs'], alloc.greedy_take(ctx['edges']))

    def test_m23_hybrid_both_branches(self):
        import common, alloc
        weak, _ = self._pair_state(3, day=12)   # max_base 3 < 4 and avg_deg 1.0 < 3.0
        self.assertEqual(self._match('m23_hybrid_patient_greedy', weak)['pairs'], [])
        strong, pair = self._pair_state(5, day=12)
        resp = self._match('m23_hybrid_patient_greedy', strong)
        self.assertEqual(self._keys(resp['pairs']), [common.pair_key(*pair)])

    def test_full_episode_groupC(self):
        from kit import generate
        from registry import REGISTRY
        for mid in sorted(self.EXPECTED):
            metrics = run_inprocess(REGISTRY[mid],
                                    generate(90212, 50, 'evaluation', 'sparse'))
            self.assertIn('msmi_per_100_arrived_members', metrics, mid)


class GroupDTests(unittest.TestCase):
    EXPECTED = {'m24_max_cardinality', 'm25_max_weight', 'm26_greedy_one_swap',
                'm27_greedy_augmenting', 'm28_conflict_aware'}

    @staticmethod
    def _match(mid, state):
        from registry import REGISTRY
        from kit import VERSION
        return REGISTRY[mid]({'schema_version': VERSION, 'phase': 'match',
                              'state': state, 'memory': None})

    @staticmethod
    def _keys(pairs):
        import common
        return [common.pair_key(p[0], p[1]) for p in pairs]

    def _assert_valid(self, resp, edges):
        import common
        ekeys = {common.pair_key(a, b) for a, b, s in edges}
        ids = [m for p in resp['pairs'] for m in p]
        self.assertEqual(len(ids), len(set(ids)))
        for p in resp['pairs']:
            self.assertIn(common.pair_key(p[0], p[1]), ekeys)

    def test_registry_contains_group_d(self):
        from registry import REGISTRY
        self.assertTrue(self.EXPECTED.issubset(set(REGISTRY)))

    def test_all_methods_pick_the_only_edge(self):
        import common
        state, pair = GroupCTests._pair_state(5, day=12)
        for mid in sorted(self.EXPECTED):
            resp = self._match(mid, state)
            self.assertEqual(self._keys(resp['pairs']), [common.pair_key(*pair)], mid)

    def test_m25_zero_prune_returns_empty(self):
        state, _ = GroupCTests._pair_state(0, day=12)   # all SOFT differ -> base 0
        self.assertEqual(self._match('m25_max_weight', state)['pairs'], [])

    def test_m24_matches_reference_branches(self):
        import common, alloc
        state = CommonHelperTests._state(day=38)
        edges = common.feasible_edges(state)
        expected = alloc.max_cardinality(edges)
        if expected is None:
            expected = alloc.augment3_improve(alloc.greedy_take(edges), edges,
                                              common.AUGMENT_ROUNDS_CAP)
        resp = self._match('m24_max_cardinality', state)
        self.assertEqual(resp['pairs'], expected)
        self._assert_valid(resp, edges)

    def test_m25_matches_reference_and_value_ge_greedy(self):
        import common, alloc
        state = CommonHelperTests._state(day=38)
        all_edges = common.feasible_edges(state)
        edges = [e for e in all_edges if e[2] > 0]
        colored = alloc.two_color(edges)
        if colored is not None and len(colored[0]) + len(colored[1]) <= common.HUNGARIAN_NODE_CAP:
            wmap = {}
            for a, b, s in edges:
                wmap[(a, b)] = s
                wmap[(b, a)] = s
            expected = [list(p) for p in alloc.hungarian_max_weight(colored[0], colored[1], wmap)]
        else:
            expected = alloc.one_swap_improve(alloc.greedy_take(edges), edges)
        resp = self._match('m25_max_weight', state)
        self.assertEqual(resp['pairs'], expected)
        self._assert_valid(resp, all_edges)
        w = AllocGraphTests._weight_total
        self.assertGreaterEqual(w(resp['pairs'], all_edges),
                                w(alloc.greedy_take(all_edges), all_edges))
    def test_m24_forced_fallback_when_max_cardinality_unavailable(self):
        import alloc, common
        state = CommonHelperTests._state(day=38)
        real = alloc.max_cardinality
        alloc.max_cardinality = lambda edges: None   # force the odd-cycle branch
        try:
            resp = self._match('m24_max_cardinality', state)
        finally:
            alloc.max_cardinality = real
        edges = common.feasible_edges(state)
        expected = alloc.augment3_improve(alloc.greedy_take(edges), edges,
                                          common.AUGMENT_ROUNDS_CAP)
        self.assertEqual(resp['pairs'], expected)
        self._assert_valid(resp, edges)

    def test_m25_forced_fallback_when_coloring_unavailable(self):
        import alloc, common
        state = CommonHelperTests._state(day=38)
        real = alloc.two_color
        alloc.two_color = lambda edges: None   # force the non-bipartite guard
        try:
            resp = self._match('m25_max_weight', state)
        finally:
            alloc.two_color = real
        all_edges = common.feasible_edges(state)
        edges = [e for e in all_edges if e[2] > 0]
        expected = alloc.one_swap_improve(alloc.greedy_take(edges), edges)
        self.assertEqual(resp['pairs'], expected)
        self._assert_valid(resp, all_edges)

    def test_m25_forced_fallback_on_node_cap(self):
        import alloc, common
        state = CommonHelperTests._state(day=38)
        real_cap = common.HUNGARIAN_NODE_CAP
        common.HUNGARIAN_NODE_CAP = 0   # force the over-cap guard
        try:
            resp = self._match('m25_max_weight', state)
        finally:
            common.HUNGARIAN_NODE_CAP = real_cap
        all_edges = common.feasible_edges(state)
        edges = [e for e in all_edges if e[2] > 0]
        expected = alloc.one_swap_improve(alloc.greedy_take(edges), edges)
        self.assertEqual(resp['pairs'], expected)
        self._assert_valid(resp, all_edges)

    def test_heavy_decide_latency_m24_m25_under_5s(self):
        import time
        state = CommonHelperTests._state(day=38)   # worst fixture: over-cap + non-bipartite
        for mid in ('m24_max_cardinality', 'm25_max_weight'):
            started = time.perf_counter()
            self._match(mid, state)
            self.assertLess(time.perf_counter() - started, 5.0, mid)

    def test_m26_matches_reference(self):
        import common, alloc
        state = CommonHelperTests._state(day=38)
        edges = common.feasible_edges(state)
        resp = self._match('m26_greedy_one_swap', state)
        self.assertEqual(resp['pairs'],
                         alloc.one_swap_improve(alloc.greedy_take(edges), edges))
        self._assert_valid(resp, edges)

    def test_m27_matches_reference(self):
        import common, alloc
        state = CommonHelperTests._state(day=38)
        edges = common.feasible_edges(state)
        resp = self._match('m27_greedy_augmenting', state)
        self.assertEqual(resp['pairs'],
                         alloc.augment3_improve(alloc.greedy_take(edges), edges,
                                                common.AUGMENT_ROUNDS_CAP))
        self._assert_valid(resp, edges)

    def test_m28_conflict_ranking_matches_reference(self):
        import common, alloc
        state = CommonHelperTests._state(day=38)
        edges = common.feasible_edges(state)
        pools = {}
        for a, b, s in edges:
            pools[a] = pools.get(a, 0) + s
            pools[b] = pools.get(b, 0) + s
        expected = alloc.take_ordered(
            edges, lambda e: (-(3 * e[2] - pools.get(e[0], 0) - pools.get(e[1], 0)),
                              common.pair_key(e[0], e[1])))
        resp = self._match('m28_conflict_aware', state)
        self.assertEqual(resp['pairs'], expected)
        self._assert_valid(resp, edges)

    def test_full_episode_groupD(self):
        from kit import generate
        from registry import REGISTRY
        for mid in sorted(self.EXPECTED):
            metrics = run_inprocess(REGISTRY[mid],
                                    generate(90213, 50, 'evaluation', 'development'))
            self.assertIn('msmi_per_100_arrived_members', metrics, mid)


class GroupETests(unittest.TestCase):
    EXPECTED = {'m29_uncertainty_aware', 'm30_targeted_info'}

    @staticmethod
    def _ask(mid, state):
        from registry import REGISTRY
        from kit import VERSION
        return REGISTRY[mid]({'schema_version': VERSION, 'phase': 'ask',
                              'state': state, 'memory': None})

    def test_registry_contains_group_e(self):
        from registry import REGISTRY
        self.assertTrue(self.EXPECTED.issubset(set(REGISTRY)))

    def test_asks_respect_budget_validity_and_reserve(self):
        for day in (0, 59):
            state = CommonHelperTests._state(day=day)
            mfs = {m['member_id']: m for m in state['members']}
            for mid in sorted(self.EXPECTED):
                resp = self._ask(mid, state)
                cost = sum(3 if a['field'] == 'constraints' else 1
                           for a in resp['asks'])
                self.assertLessEqual(cost, state['ask_budget_remaining'],
                                     (mid, day))
                seen = set()
                for a in resp['asks']:
                    key = (a['member_id'], a['field'])
                    self.assertNotIn(key, seen, (mid, day))
                    seen.add(key)
                    m = mfs[a['member_id']]
                    self.assertTrue(m['available'], (mid, day))
                    if a['field'] != 'constraints':
                        self.assertEqual(m['field_status'][a['field']],
                                         'not_asked', (mid, day))
                # SOFT_ASK_RESERVE=3: hard asks capped at (12-3)//3 = 3
                hard = [a for a in resp['asks'] if a['field'] == 'constraints']
                self.assertLessEqual(len(hard), 3, (mid, day))

    def test_m29_ranks_soft_asks_by_information_value(self):
        import common
        from kit import SOFT
        state = CommonHelperTests._state(day=59)
        mfs = {m['member_id']: m for m in state['members']}
        ctx = common.make_ctx(state)
        resp = self._ask('m29_uncertainty_aware', state)
        got = []
        for a in resp['asks']:
            if a['field'] == 'constraints':
                continue
            v = sum(1 for _s, nb in ctx['inc'].get(a['member_id'], ())
                    if mfs[nb]['fields'].get(a['field']) is not None)
            self.assertGreater(v, 0, a)
            got.append((-v, a['member_id'], a['field']))
        want = []
        for m in sorted(state['members'], key=lambda x: x['member_id']):
            if not m['available']:
                continue
            for k in sorted(SOFT):
                if m['field_status'].get(k) == 'not_asked':
                    v = sum(1 for _s, nb in ctx['inc'].get(m['member_id'], ())
                            if mfs[nb]['fields'].get(k) is not None)
                    if v > 0:
                        want.append((-v, m['member_id'], k))
        want.sort()
        self.assertEqual(got, want[:len(got)])

    def test_full_episode_group_e_parity_and_aliveness(self):
        from kit import generate, baseline_match
        from registry import REGISTRY
        for mid in sorted(self.EXPECTED):
            soft_asks = []

            def fn(request, _mid=mid, _sink=soft_asks):
                resp = REGISTRY[_mid](request)
                if request['phase'] == 'ask':
                    _sink.extend(a for a in resp['asks']
                                 if a['field'] != 'constraints')
                else:
                    self.assertEqual(resp['pairs'],
                                     baseline_match(request['state']), _mid)
                return resp

            metrics = run_inprocess(fn,
                                    generate(90214, 50, 'evaluation', 'cold_start'))
            self.assertIn('msmi_per_100_arrived_members', metrics, mid)
            self.assertGreater(len(soft_asks), 0, 'gate never fired: ' + mid)

    def test_m30_ask_latency_on_dense_day59_under_5s(self):
        import time
        state = CommonHelperTests._state(day=59)
        started = time.perf_counter()
        self._ask('m30_targeted_info', state)
        self.assertLess(time.perf_counter() - started, 5.0)

    def test_m30_voi_recomputations_bounded_by_cap(self):
        import alloc, common
        state = CommonHelperTests._state(day=59)
        real = alloc.greedy_take
        calls = []

        def counting(edges, _real=real):
            calls.append(1)
            return _real(edges)

        alloc.greedy_take = counting
        try:
            resp = self._ask('m30_targeted_info', state)
        finally:
            alloc.greedy_take = real
        self.assertIn('asks', resp)
        self.assertGreaterEqual(len(calls), 1)
        self.assertLessEqual(len(calls), common.VOI_EVAL_CAP)

    def test_m30_voi_cap_forces_truncation(self):
        import alloc, common
        state = CommonHelperTests._state(day=59)
        real_take, real_cap = alloc.greedy_take, common.VOI_EVAL_CAP

        def run_with_cap(cap):
            calls = []

            def counting(edges, _real=real_take):
                calls.append(1)
                return _real(edges)

            alloc.greedy_take = counting
            common.VOI_EVAL_CAP = cap
            try:
                self._ask('m30_targeted_info', state)
            finally:
                alloc.greedy_take = real_take
                common.VOI_EVAL_CAP = real_cap
            return len(calls)

        # cap=1: the base allocation consumes the only recomputation, so the
        # candidate loop must be skipped entirely (forced truncation branch).
        self.assertEqual(run_with_cap(1), 1)
        # cap=2: at most one option evaluation may follow the base pass.
        self.assertLessEqual(run_with_cap(2), 2)


class RegistryCompletenessTests(unittest.TestCase):
    def test_methods_json_all_implemented(self):
        data = json.loads(METHODS_JSON.read_text(encoding='utf-8'))
        self.assertEqual(len(data['methods']), 30)
        pending = [m['method_id'] for m in data['methods']
                   if m['implementation_status'] != 'implemented']
        self.assertEqual(pending, [], pending)

    def test_registry_matches_methods_json(self):
        from registry import REGISTRY
        data = json.loads(METHODS_JSON.read_text(encoding='utf-8'))
        ids = {m['method_id'] for m in data['methods']}
        self.assertEqual(set(REGISTRY), ids)
        for mid, fn in REGISTRY.items():
            self.assertTrue(callable(fn), mid)

    def test_policies_dir_exactly_matches_registry(self):
        from registry import REGISTRY
        files = sorted(p.stem for p in (HERE / 'policies').glob('*.py'))
        self.assertEqual(files, sorted(REGISTRY))
        self.assertEqual(len(files), 30)

    def test_group_counts_match_design(self):
        from collections import Counter
        data = json.loads(METHODS_JSON.read_text(encoding='utf-8'))
        counts = Counter(m['group'] for m in data['methods'])
        self.assertEqual(dict(counts), {'A': 8, 'B': 7, 'C': 8, 'D': 5, 'E': 2})


class RunnerTests(unittest.TestCase):
    def test_phase_configs_preregistered(self):
        import run_tournament as rt
        self.assertEqual(rt.PHASES['smoke'],
                         {'seeds': (90290,), 'variants': ('development',)})
        self.assertEqual(rt.PHASES['screening']['seeds'], (143, 144, 145))
        self.assertEqual(rt.PHASES['confirm1']['seeds'], tuple(range(146, 152)))
        self.assertEqual(rt.PHASES['confirm2']['seeds'], tuple(range(152, 164)))
        self.assertEqual(tuple(rt.PHASES['screening']['variants']),
                         ('development', 'sparse', 'cold_start',
                          'delayed', 'shift', 'drift'))
        self.assertEqual(len(rt.worlds('smoke')), 1)
        self.assertEqual(len(rt.worlds('screening')), 18)
        self.assertEqual(len(rt.worlds('confirm1')), 36)
        self.assertEqual(len(rt.worlds('confirm2')), 72)

    def test_expected_episode_counts(self):
        import run_tournament as rt
        all30 = ['m%02d_dummy' % i for i in range(1, 31)]
        self.assertEqual(len(rt.expected_keys('smoke', all30 + [rt.CONTROL])), 31)
        self.assertEqual(len(rt.expected_keys('screening', all30 + [rt.CONTROL])), 558)
        self.assertEqual(len(rt.expected_keys('confirm1', all30[:5] + [rt.CONTROL])), 216)
        self.assertEqual(len(rt.expected_keys('confirm2', all30[:2] + [rt.CONTROL])), 216)

    def test_load_methods_smoke_and_screening(self):
        import run_tournament as rt
        self.assertEqual(len(rt.load_methods('smoke')), 30)
        self.assertEqual(rt.load_methods('screening'), sorted(rt.load_methods('smoke')))

    def test_resume_last_wins_and_only_valid_counts_done(self):
        import run_tournament as rt
        import tempfile
        import pathlib as pl
        with tempfile.TemporaryDirectory() as td:
            path = pl.Path(td) / 'rows.jsonl'
            rows = [
                {'method': 'mA', 'seed': 1, 'variant': 'development',
                 'valid': False, 'error': 'timeout'},
                {'method': 'mA', 'seed': 1, 'variant': 'development',
                 'valid': True, 'msmi_per_100_arrived_members': 0.5},
                {'method': 'mB', 'seed': 1, 'variant': 'development', 'valid': True},
            ]
            path.write_text(''.join(json.dumps(r) + chr(10) for r in rows),
                            encoding='utf-8')
            prior = rt.dedupe(rt.load_rows(path))
            self.assertEqual(len(prior), 2)
            done = {rt.row_key(r) for r in prior if r.get('valid')}
            self.assertEqual(done, {('mA', 1, 'development'),
                                    ('mB', 1, 'development')})
            self.assertTrue(all(r.get('valid') for r in prior))

    def test_freeze_verification_passes_then_fails_on_change(self):
        import run_tournament as rt
        import tempfile
        import hashlib
        import pathlib as pl
        with tempfile.TemporaryDirectory() as td:
            base = pl.Path(td)
            target = base / 'methods_a.py'
            target.write_text('x = 1\n', encoding='utf-8')
            manifest = base / 'freeze.txt'
            digest = hashlib.sha256(target.read_bytes()).hexdigest()
            manifest.write_text(digest + '  methods_a.py' + chr(10),
                                encoding='utf-8')
            rt.verify_freeze(manifest, base=base)
            target.write_text('x = 2\n', encoding='utf-8')
            with self.assertRaises(SystemExit):
                rt.verify_freeze(manifest, base=base)

    def test_commands_point_at_real_files(self):
        import run_tournament as rt
        ctrl = rt.control_command()
        self.assertEqual(ctrl[-3:], [str(rt.ROOT / 'policy.py'),
                                     '--baseline', 'greedy'])
        self.assertTrue(pathlib.Path(ctrl[1]).exists())
        cmd = rt.method_command('m01_greedy_baseline')
        self.assertTrue(pathlib.Path(cmd[1]).exists())

    def test_code_fingerprint_is_total_and_deterministic(self):
        import run_tournament as rt
        self.assertEqual(rt.code_fingerprint(), rt.code_fingerprint())
        fp = rt.code_fingerprint()
        self.assertEqual(len(fp), 64)
        for rel in rt.CODE_FILES:
            p = (rt.ROOT / rel) if rel in rt.ROOT_FILES else (rt.HERE / rel)
            self.assertTrue(p.exists(), 'fingerprint input missing: ' + rel)
        self.assertTrue(list((rt.HERE / 'policies').glob('*.py')))

    def test_purge_stale_archives_foreign_fingerprint_only(self):
        import run_tournament as rt
        import tempfile
        import pathlib as pl
        with tempfile.TemporaryDirectory() as td:
            path = pl.Path(td) / 'screening_rows.jsonl'
            self.assertIsNone(rt.purge_stale(path, 'f' * 64))
            path.write_text(json.dumps(
                {'method': 'm', 'seed': 1, 'variant': 'development',
                 'valid': True, 'code_sha256': 'a' * 64}) + chr(10),
                encoding='utf-8')
            self.assertIsNone(rt.purge_stale(path, 'a' * 64))
            self.assertTrue(path.exists())
            archive = rt.purge_stale(path, 'b' * 64)
            self.assertIsNotNone(archive)
            self.assertFalse(path.exists())
            self.assertTrue(archive.exists())
            self.assertTrue(archive.name.startswith('screening_rows_v'))
            self.assertEqual(
                len(list(pl.Path(td).glob('screening_rows_v*.jsonl'))), 1)

    def test_attempt_log_appends_full_record_shape(self):
        import run_tournament as rt
        import tempfile
        import pathlib as pl
        with tempfile.TemporaryDirectory() as td:
            path = pl.Path(td) / 'smoke_attempts.jsonl'
            self.assertEqual(
                rt.append_attempt(path, 'smoke', 'f' * 64, 3, 3, 0, None, 0), 0)
            recs = [json.loads(l) for l in
                    path.read_text(encoding='utf-8').splitlines() if l]
            self.assertEqual(len(recs), 1)
            self.assertEqual(set(recs[0]), {'ts', 'phase', 'fingerprint',
                                            'episodes_planned',
                                            'episodes_written', 'invalid',
                                            'purged', 'exit'})
            rt.append_attempt(path, 'smoke', 'e' * 64, 5, 2, 1,
                              'screening_rows_vdeadbeef.jsonl', 2)
            self.assertEqual(len(path.read_text(
                encoding='utf-8').splitlines()), 2)


class AllRegistrySweepTests(unittest.TestCase):
    def test_file_inventory_is_exactly_40(self):
        targets = [HERE / n for n in ('common.py', 'alloc.py', '_cli.py',
                                      'registry.py', 'gen_policies.py')]
        targets += sorted(HERE.glob('methods_*.py'))
        targets += sorted((HERE / 'policies').glob('*.py'))
        existing = [p for p in targets if p.exists()]
        # 5 shared + 5 group modules + 30 launchers; LeakScanTests scans all of them.
        self.assertEqual(len(existing), 40)

    def test_all_methods_ask_and_match_latency_day59_under_5s(self):
        import time
        from registry import REGISTRY
        from kit import VERSION
        state = CommonHelperTests._state(day=59)
        for mid in sorted(REGISTRY):
            for phase in ('ask', 'match'):
                req = {'schema_version': VERSION, 'phase': phase,
                       'state': state, 'memory': None}
                started = time.perf_counter()
                REGISTRY[mid](dict(req))
                self.assertLess(time.perf_counter() - started, 5.0, (mid, phase))

    def test_all_methods_deterministic_on_ask_and_match(self):
        from registry import REGISTRY
        from kit import VERSION
        state = CommonHelperTests._state(day=38)
        for mid in sorted(REGISTRY):
            for phase in ('ask', 'match'):
                req = {'schema_version': VERSION, 'phase': phase,
                       'state': state, 'memory': None}
                r1 = REGISTRY[mid](dict(req))
                r2 = REGISTRY[mid](dict(req))
                self.assertEqual(json.dumps(r1, sort_keys=True),
                                 json.dumps(r2, sort_keys=True), (mid, phase))


class InstrumentTests(unittest.TestCase):
    def test_episode_replica_digest_parity_and_bounds(self):
        import evaluate
        import instrument
        import run_tournament as rt
        from kit import generate
        world = generate(90217, 200, 'evaluation', 'development')
        row = instrument.instrument_episode(world, rt.control_command())
        ref = evaluate.episode(world, rt.control_command())
        self.assertEqual(row['action_sha256'], ref['action_sha256'])
        self.assertEqual(len(row['action_sha256']), 64)
        self.assertTrue(row['valid'])
        self.assertTrue(0 <= row['zero_selection_days'] <= 60)
        self.assertGreaterEqual(row['intros_per_100'], 0.0)

    def test_arms_for_both_phases(self):
        import instrument
        self.assertEqual(instrument.arms_for({}, 'selected'), [])
        self.assertEqual(instrument.arms_for({'selected': []}, 'selected'), [])
        self.assertEqual(instrument.arms_for({'selected': ['m02_x']},
                                             'selected'), ['m02_x'])
        self.assertEqual(instrument.arms_for({'retained': ['m05_z']},
                                             'retained'), ['m05_z'])
        self.assertEqual(instrument.arms_for({}, 'retained'), [])

    def test_phase_config_covers_screening_and_final(self):
        import instrument
        self.assertEqual(set(instrument.PHASE_CFG), {'screening', 'confirm2'})
        self.assertEqual(instrument.PHASE_CFG['screening']['seed'], 143)
        self.assertEqual(instrument.PHASE_CFG['confirm2']['seed'], 152)
        self.assertEqual(instrument.PHASE_CFG['screening']['key'], 'retained')
        self.assertEqual(instrument.PHASE_CFG['confirm2']['key'], 'selected')


class AnalyseTests(unittest.TestCase):
    @staticmethod
    def _rows():
        worlds = [(143, 'development'), (143, 'sparse'),
                  (144, 'development'), (144, 'sparse')]
        rows = []
        base = {'coverage': 0.5, 'ask_cost': 200, 'assignments': 100,
                'arrived_members': 200, 'inference_seconds': 10.0, 'valid': True}
        for seed, variant in worlds:
            rows.append(dict(base, method='__control__', seed=seed, variant=variant,
                             msmi_per_100_arrived_members=0.5,
                             action_sha256='h' + str(seed) + variant))
            rows.append(dict(base, method='m02_x', seed=seed, variant=variant,
                             msmi_per_100_arrived_members=0.55, action_sha256='a'))
            rows.append(dict(base, method='m03_y', seed=seed, variant=variant,
                             msmi_per_100_arrived_members=0.40, action_sha256='b'))
        return rows

    def test_paired_deltas_and_mean(self):
        import analyse_tournament as an
        import statistics
        rows = self._rows()
        ctrl = an.control_map(rows)
        pairs = an.paired_deltas(rows, 'm02_x', ctrl)
        self.assertEqual([(s, v) for s, v, _d in pairs],
                         [(143, 'development'), (143, 'sparse'),
                          (144, 'development'), (144, 'sparse')])
        self.assertAlmostEqual(statistics.mean(d for _s, _v, d in pairs), 0.05,
                               places=10)

    def test_seed_level_clustering_and_cluster_ci(self):
        import analyse_tournament as an
        rows = self._rows()
        ctrl = an.control_map(rows)
        s = an.method_summary(rows, 'm02_x', ctrl)
        self.assertEqual(s['n_units'], 4)
        self.assertEqual(s['n_seeds'], 2)
        self.assertAlmostEqual(s['mean_delta'], 0.05, places=10)
        # identical seed means -> zero-width cluster CI (df = 1, se = 0)
        self.assertAlmostEqual(s['ci95'][0], 0.05, places=10)
        self.assertAlmostEqual(s['ci95'][1], 0.05, places=10)
        self.assertAlmostEqual(s['ci99'][0], 0.05, places=10)
        # per-variant stratification preserved at full precision
        self.assertAlmostEqual(s['per_variant_mean_delta']['development'],
                               0.05, places=10)
        self.assertTrue(s['eligible'], s['ineligibility_reasons'])
        # m03 mean -0.10 fails the -0.05 retention gate
        s3 = an.method_summary(rows, 'm03_y', ctrl)
        self.assertFalse(s3['eligible'])
        self.assertAlmostEqual(s3['mean_delta'], -0.10, places=10)

    def test_t_critical_tables_conservative(self):
        import analyse_tournament as an
        self.assertEqual(an.t_critical(17), 2.110)
        self.assertEqual(an.t_critical(71), 1.994)
        self.assertEqual(an.t_critical(22), 2.086)   # falls back to df 20
        self.assertEqual(an.t_critical(0), float('inf'))
        # 99% table for the Bonferroni Phase-3 gate (design section 9)
        self.assertEqual(an.t_critical(11, 99), 3.106)
        self.assertEqual(an.t_critical(1, 99), 63.657)
        self.assertEqual(an.t_critical(22, 99), 2.845)  # falls back to df 20
        self.assertEqual(an.t_critical(11, 95), 2.201)

    def test_eligibility_gates_including_latency(self):
        import analyse_tournament as an
        good = {'invalid_episodes': 0, 'mean_delta': -0.04, 'n_units': 18,
                'per_variant_mean_delta': {'development': -0.14, 'sparse': 0.0},
                'secondary': {'max_inference_seconds': 9.4}}
        ok, reasons = an._eligibility(good)
        self.assertTrue(ok, reasons)
        self.assertFalse(an._eligibility(dict(good, invalid_episodes=1))[0])
        self.assertFalse(an._eligibility(dict(good, mean_delta=-0.06))[0])
        self.assertFalse(an._eligibility(dict(
            good, per_variant_mean_delta={'shift': -0.16}))[0])
        # design section 7 gates PER INVOCATION ("all invocations valid, i.e.
        # under 10 s each"); rows carry the 120-invocation episode total, so the
        # gate fires above 1200 s, and a realistic control-scale total passes.
        realistic = dict(good, secondary={'max_inference_seconds': 21.4})
        self.assertTrue(an._eligibility(realistic)[0],
                        an._eligibility(realistic)[1])
        slow = dict(good, secondary={'max_inference_seconds': 1205.0})
        self.assertFalse(an._eligibility(slow)[0])
        no_latency = dict(good, secondary={})
        self.assertFalse(an._eligibility(no_latency)[0])

    def test_control_parity_check(self):
        import analyse_tournament as an
        rows = self._rows()
        rows.append(dict(rows[0], method='m01_greedy_baseline', action_sha256='h143development'))
        parity = an.check_control_parity(rows)
        self.assertEqual(parity['worlds_checked'], 1)
        self.assertEqual(parity['mismatched_worlds'], [])
        rows[-1]['action_sha256'] = 'DIFFERENT'
        parity = an.check_control_parity(rows)
        self.assertEqual(len(parity['mismatched_worlds']), 1)

    def test_selection_is_sign_independent_top_two(self):
        import analyse_tournament as an
        per = {'a': {'invalid_episodes': 0, 'mean_delta': -0.01},
               'b': {'invalid_episodes': 0, 'mean_delta': -0.03},
               'c': {'invalid_episodes': 2, 'mean_delta': 0.9}}
        self.assertEqual(an.select_top(per, 2), ['a', 'b'])

    def test_selection_excludes_m01_and_uses_full_precision(self):
        import analyse_tournament as an
        per = {'m01_greedy_baseline': {'invalid_episodes': 0, 'mean_delta': 0.9},
               'a': {'invalid_episodes': 0, 'mean_delta': 0.5000006},
               'b': {'invalid_episodes': 0, 'mean_delta': 0.5000004},
               'c': {'invalid_episodes': 3, 'mean_delta': 0.99}}
        # a and b both display as 0.5000; full precision (then id) decides;
        # m01 is never selected despite the highest mean (parity control).
        self.assertEqual(an.select_top(per, 2), ['a', 'b'])

    def test_credibility_gate_cluster_and_bonferroni(self):
        import analyse_tournament as an
        base = {'invalid_episodes': 0, 'mean_delta': 0.05,
                'ci95': [0.01, 0.09], 'ci99': [0.005, 0.095],
                'per_variant_mean_delta': {'drift': -0.1}}
        self.assertTrue(an.credible(base))
        self.assertTrue(an.credible(base, 99))
        self.assertFalse(an.credible(dict(base, ci95=[-0.01, 0.11])))
        # clears 95% but not the Bonferroni 99% level -> not credible at k=2
        self.assertFalse(an.credible(dict(base, ci99=[-0.01, 0.11]), 99))
        self.assertFalse(an.credible(dict(
            base, per_variant_mean_delta={'drift': -0.16})))
        self.assertFalse(an.credible(dict(base, invalid_episodes=1)))

    def test_retention_zero_through_eight(self):
        import analyse_tournament as an

        def per_for(n):
            return {'m%02d_x' % i: {'invalid_episodes': 0,
                                    'mean_delta': 1.0 - i * 0.01,
                                    'per_variant_mean_delta': {'development': 0.1}}
                    for i in range(n)}

        def ranked(per):
            return sorted(per, key=lambda m: (-per[m]['mean_delta'],
                                              round(per[m]['mean_delta'], 6), m))
        # E = 0
        self.assertEqual(an.retention({}, []), ([], [], []))
        # E = 3 -> all core, no diagnostics
        per3 = per_for(3)
        t3, d3, r3 = an.retention(per3, ranked(per3))
        self.assertEqual((len(t3), len(d3), len(r3)), (3, 0, 3))
        self.assertEqual(r3, t3)
        # E = 7 -> 5 core + 2 diagnostics with reasons
        per7 = per_for(7)
        t7, d7, r7 = an.retention(per7, ranked(per7))
        self.assertEqual((len(t7), len(d7), len(r7)), (5, 2, 7))
        self.assertEqual(r7, t7 + [d['method'] for d in d7])
        self.assertTrue(all(d['reason'] for d in d7))
        # E = 10 -> capped at 8 retained (5 + 3 diagnostics)
        per10 = per_for(10)
        t10, d10, r10 = an.retention(per10, ranked(per10))
        self.assertEqual((len(t10), len(d10), len(r10)), (5, 3, 8))

    def test_code_fingerprint_assert(self):
        import analyse_tournament as an
        import tempfile
        import pathlib as pl
        rows = [{'code_sha256': 'a' * 64}, {'code_sha256': 'a' * 64}]
        with tempfile.TemporaryDirectory() as td:
            pre = pl.Path(td) / 'pre.txt'
            pre.write_text('a' * 64 + chr(10), encoding='utf-8')
            got = an.assert_code_fingerprint(rows, 'screening', pre=pre)
            self.assertEqual(got, 'a' * 16)
            rows.append({'code_sha256': 'b' * 64})
            with self.assertRaises(SystemExit):
                an.assert_code_fingerprint(rows, 'screening', pre=pre)


if __name__ == '__main__':
    unittest.main()
