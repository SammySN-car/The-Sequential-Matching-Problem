"""Task 3: P1-P3 policy validity for policy_candidate.py -> results/policy_validity.json.

Plain python script, standard library only (+ repo kit/evaluate). Prints a
[PASS]/[FAIL] per assertion, a summary, and exits non-zero on any failure.

Frozen-plan P-series (analysis_plan S.8):
  P1 greedy parity   candidate asks == kit.baseline_asks on every state; and
                     candidate k == len(kit.baseline_match(state)) on every
                     state (protocol-level C6). Verified in-process on a
                     generated state population AND from the pilot harness
                     instrumentation (k_chosen == k_greedy on every line).
  P2 protocol        every emitted response passes evaluate.py's
                     validate_response (exactly {asks|pairs, memory}; pair
                     arity 2; memory pass-through; < 1 MiB), verified
                     in-process on all generated states PLUS the parent pilot
                     seed group 40001 (6 episodes via the official harness,
                     smoke only, excluded from all claims).
  P3 determinism     repeating an invocation yields byte-identical response
                     JSON: in-process (match_fn twice) AND end-to-end (two
                     full evaluate.py runs on 40001/development ->
                     identical action_sha256).

Also records frozen-artifact + copied-module provenance hashes and the pilot
cardinality/invalid-action audit. Seed policy: 40001 (designated pilot) only;
NEVER a training (40002-40500) or final-evaluation (70001-70100) seed. No tuning.
"""
import hashlib, json, os, statistics, subprocess, sys, tempfile, time
from pathlib import Path

EXPERIMENT = Path(__file__).resolve().parents[1]   # round2_stagewise_reward_solver
REPO_ROOT = EXPERIMENT.parents[1]                  # repo root
PARENT_EXP = EXPERIMENT.parents[0] / 'round2_stagewise_reward'
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(EXPERIMENT))
sys.path.insert(0, str(EXPERIMENT / 'scripts'))

import kit
import evaluate
from kit import generate, Simulator, baseline_asks, baseline_match
import policy_candidate
from sr_features import build_feasible_edges

POLICY = EXPERIMENT / 'policy_candidate.py'
OFFICIAL_OUTPUT = EXPERIMENT / 'results' / 'pilot_candidate_official.json'
SEED = 40001
VARIANTS = ('development', 'sparse', 'cold_start', 'delayed', 'shift', 'drift')
DET_VARIANT = 'development'
EXPECTED_PILOT_LINES = 360          # 6 episodes x 60 match days
FROZEN_MODEL_SHA = '7f1ddfe00211e2603e88c4e8318d3a62980aeb8364f51bc41909e8875fa275f2'
SR_FEATURES_SHA = '76fc12f6a75f45d247cb277fe36a0ddade520891eae7156bea18dc10d080e67e'
SR_POLICY_CORE_SHA = '02af1e6a4b7bf9dbfda9d74de998bbe07b8242d59da42ba1e2d45b108bed046d'
RUN_TIMEOUT = 1800

_fails = 0
_checks = 0
_instr = []
_pilot = {}


def check(label, ok, detail=''):
    global _fails, _checks
    _checks += 1
    if ok:
        print('[PASS] %s' % label, flush=True)
    else:
        _fails += 1
        print('[FAIL] %s%s' % (label, (' :: ' + detail) if detail else ''), flush=True)
    return ok


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _gen_states():
    """Deterministic population: all 6 variants x {day0, day5 greedy replay}
    x a few seeds (incl. the pilot 40001). No evaluation seeds used."""
    seeds = [SEED, 101, 424242, 7]
    states = []
    for seed in seeds:
        for variant in VARIANTS:
            sim = Simulator(generate(seed, 200, 'evaluation', variant))
            states.append(('d0-%s-%s' % (seed, variant), sim.observe()))
            for _ in range(5):
                sim.resolve_asks(baseline_asks(sim.observe()))
                sim.advance(baseline_match(sim.observe()))
            states.append(('d5-%s-%s' % (seed, variant), sim.observe()))
    return states


def test_provenance():
    check('frozen model artifact sha256 matches freeze record',
          _sha(PARENT_EXP / 'results' / 'model_artifact.json') == FROZEN_MODEL_SHA)
    check('sr_features.py copy byte-identical (76fc12f6)',
          _sha(EXPERIMENT / 'scripts' / 'sr_features.py') == SR_FEATURES_SHA)
    check('sr_policy_core.py copy byte-identical (02af1e6a)',
          _sha(EXPERIMENT / 'sr_policy_core.py') == SR_POLICY_CORE_SHA)
    check('policy_candidate loads frozen artifact at import',
          policy_candidate.ARTIFACT is not None and
          len(policy_candidate.ARTIFACT['features']) > 0)


def test_p1_p2_p3_inprocess():
    """P1 parity + feasibility, P2 validate_response, P3 determinism on states."""
    p1_ask_fail = p1_k_fail = p1_feas_fail = p2_fail = p3_fail = 0
    n = 0
    for name, state in _gen_states():
        n += 1
        # P1: asks parity
        asks, _ = policy_candidate.make_ask()(state)
        if asks != baseline_asks(state):
            p1_ask_fail += 1
        # match (in-process; deterministic)
        pairs, meta = policy_candidate.match_fn(state)
        kg = len(baseline_match(state))
        if len(pairs) != kg or meta['k_chosen'] != meta['k_greedy'] or meta['k_greedy'] != kg:
            p1_k_fail += 1
        # P1/C3 feasibility: disjoint, in edge set, exactly k
        edges, _deg = build_feasible_edges(state)
        eset = set(edges)
        used = set()
        okf = (len(pairs) == kg)
        for p in pairs:
            key = tuple(sorted(p))
            if len(p) != 2 or key not in eset or key[0] in used or key[1] in used:
                okf = False
            used.update(key)
        if not okf:
            p1_feas_fail += 1
        # P2: validate_response on emitted responses
        mem = {'probe': 1}
        try:
            evaluate.validate_response({'asks': asks, 'memory': mem}, 'ask')
            evaluate.validate_response({'pairs': pairs, 'memory': mem}, 'match')
        except Exception:
            p2_fail += 1
        # P3: determinism in-process
        pairs2, _ = policy_candidate.match_fn(state)
        if json.dumps(pairs2) != json.dumps(pairs):
            p3_fail += 1
    check('P1 in-process: asks == baseline_asks on %d states' % n, p1_ask_fail == 0,
          '%d mismatches' % p1_ask_fail)
    check('P1 in-process: k == len(baseline_match) on %d states' % n, p1_k_fail == 0,
          '%d mismatches' % p1_k_fail)
    check('P1 in-process: pairs feasible/disjoint/exact-k on %d states' % n,
          p1_feas_fail == 0, '%d violations' % p1_feas_fail)
    check('P2 in-process: validate_response on all states', p2_fail == 0,
          '%d failures' % p2_fail)
    check('P3 in-process: match_fn byte-identical on repeat', p3_fail == 0,
          '%d mismatches' % p3_fail)
    _pilot['inprocess_states'] = n
    _pilot['inprocess_p1_ask_fail'] = p1_ask_fail
    _pilot['inprocess_p1_k_fail'] = p1_k_fail
    _pilot['inprocess_p1_feas_fail'] = p1_feas_fail
    _pilot['inprocess_p2_fail'] = p2_fail
    _pilot['inprocess_p3_fail'] = p3_fail


def _sub_env(extra=None):
    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    env.pop('SRS_INSTRUMENTATION_DIR', None)
    if extra:
        env.update(extra)
    return env


def _evaluate_cmd(output_path, variants='all', seed=SEED):
    return [sys.executable, 'evaluate.py', '--policy', str(POLICY),
            '--seeds', str(seed), '--variants', variants,
            '--output', str(output_path)]


def _run(cmd, env, timeout=RUN_TIMEOUT):
    print('  $ ' + ' '.join(cmd), flush=True)
    t = time.perf_counter()
    p = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True,
                       encoding='utf-8', errors='replace', env=env, timeout=timeout)
    print('    rc=%d %.1fs' % (p.returncode, time.perf_counter() - t), flush=True)
    return p


def _read_instr(directory):
    lines = []
    for path in sorted(Path(directory).glob('*.jsonl')):
        for raw in path.read_text(encoding='utf-8').splitlines():
            if raw.strip():
                lines.append(json.loads(raw))
    return lines


def test_pilot_official():
    """Official 6-episode harness run (seed 40001, all variants) + audit."""
    global _instr
    if OFFICIAL_OUTPUT.exists():
        OFFICIAL_OUTPUT.unlink()
    with tempfile.TemporaryDirectory() as instr:
        p = _run(_evaluate_cmd(OFFICIAL_OUTPUT), _sub_env({'SRS_INSTRUMENTATION_DIR': instr}))
        check('pilot harness exit code 0', p.returncode == 0,
              'rc=%d %s' % (p.returncode, ascii((p.stderr or p.stdout or '')[-300:])))
        rows = []
        if OFFICIAL_OUTPUT.exists():
            rows = json.loads(OFFICIAL_OUTPUT.read_text(encoding='utf-8'))['episodes']
        check('pilot output has 6 episodes', len(rows) == 6, 'got %d' % len(rows))
        bad = [(r.get('variant'), r.get('seed'), r.get('error'))
               for r in rows if r.get('valid') is not True]
        check('P2 pilot: all 6 episodes valid:true (every response passed validate_response)',
              not bad, 'invalid: %r' % (bad,))
        _pilot['pilot_episodes'] = len(rows)
        _pilot['pilot_invalid'] = len(bad)
        _instr = _read_instr(instr)
        check('pilot instrumentation line count == %d' % EXPECTED_PILOT_LINES,
              len(_instr) == EXPECTED_PILOT_LINES, 'got %d' % len(_instr))
        phase_ok = all(r.get('phase') == 'match' for r in _instr)
        check('every pilot line is a match-phase record', phase_ok)
        mismatched = [r for r in _instr if r.get('k_chosen') != r.get('k_greedy')]
        check('P1 pilot: k_chosen == k_greedy on every line (%d lines)' % len(_instr),
              not mismatched, '%d mismatches, first: %r' % (len(mismatched), mismatched[:1]))
        _pilot['pilot_lines'] = len(_instr)
        _pilot['pilot_cardinality_violations'] = len(mismatched)
        if _instr:
            sv = [r['solver_seconds'] for r in _instr if 'solver_seconds' in r]
            iv = [r['invocation_seconds'] for r in _instr if 'invocation_seconds' in r]
            if sv:
                print('    solver_seconds: max=%.4f median=%.4f' %
                      (max(sv), statistics.median(sv)), flush=True)
                print('    invocation_seconds: max=%.4f median=%.4f' %
                      (max(iv), statistics.median(iv)), flush=True)
                _pilot['solver_seconds_max'] = max(sv)
                _pilot['invocation_seconds_max'] = max(iv)


def test_pilot_determinism():
    """Two full evaluate.py runs on 40001/development -> identical action_sha256."""
    env = _sub_env()
    digests, valids = [], []
    with tempfile.TemporaryDirectory() as tmp:
        for run in (1, 2):
            out = Path(tmp) / ('run%d.json' % run)
            p = _run(_evaluate_cmd(out, DET_VARIANT), env)
            check('P3 pilot determinism run %d exit 0' % run, p.returncode == 0,
                  'rc=%d' % p.returncode)
            if out.exists():
                rows = json.loads(out.read_text(encoding='utf-8'))['episodes']
                valids.append(bool(rows) and rows[0].get('valid') is True)
                digests.append(rows[0].get('action_sha256') if rows else None)
            else:
                valids.append(False); digests.append(None)
    check('P3 pilot: episodes valid', all(valids), 'valids=%r' % valids)
    check('P3 pilot: action_sha256 identical across two runs',
          len(digests) == 2 and digests[0] is not None and digests[0] == digests[1],
          'digests=%r' % (digests,))
    _pilot['pilot_determinism_sha'] = digests[0] if digests else None


def main():
    tests = [test_provenance, test_p1_p2_p3_inprocess,
             test_pilot_official, test_pilot_determinism]
    for t in tests:
        try:
            t()
        except Exception as exc:   # noqa: BLE001
            check('%s raised' % t.__name__, False,
                  '%s: %s' % (type(exc).__name__, ascii(str(exc))[:300]))
    passed = _fails == 0
    result = {
        'experiment': 'round2_stagewise_reward_solver', 'task': 3,
        'script': 'scripts/srws_policy_test.py', 'pilot_seed': SEED,
        'gates': {
            'P1_greedy_parity': {'pass': (_pilot.get('inprocess_p1_ask_fail', 1) == 0 and
                                          _pilot.get('inprocess_p1_k_fail', 1) == 0 and
                                          _pilot.get('inprocess_p1_feas_fail', 1) == 0 and
                                          _pilot.get('pilot_cardinality_violations', 1) == 0)},
            'P2_protocol_conformance': {'pass': (_pilot.get('inprocess_p2_fail', 1) == 0 and
                                                 _pilot.get('pilot_invalid', 1) == 0 and
                                                 _pilot.get('pilot_episodes', 0) == 6)},
            'P3_determinism': {'pass': (_pilot.get('inprocess_p3_fail', 1) == 0 and
                                        bool(_pilot.get('pilot_determinism_sha')))},
        },
        'pilot': _pilot,
        'benchmark_state_note': (
            'P1/P2/P3 are validated in-process on a 48-state generated population '
            '(all 6 variants, day0+day5 greedy replay, seeds {40001,101,424242,7}) '
            'and end-to-end on the parent pilot seed group 40001 (6 episodes). The '
            "exhaustive 'every benchmark state (S.7)' restatement is finalised in "
            'Task 4 when the R-A..R-D corpus is materialised; identical properties '
            'are exercised here.'),
        'passed': passed,
    }
    out = EXPERIMENT / 'results' / 'policy_validity.json'
    out.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print('SUMMARY: %d/%d assertions PASS' % (_checks - _fails, _checks))
    print('policy_validity.json passed =', passed)
    sys.exit(1 if _fails else 0)


if __name__ == '__main__':
    main()
