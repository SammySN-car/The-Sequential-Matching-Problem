"""Tests for sr_policy_core.py + policy_parity.py (implementation_plan.md Task 4).

Plain python script, standard library only (+ repo kit/evaluate), no pytest.
Prints [PASS]/[FAIL] per test and per pilot episode and exits non-zero on any
failure.

test_digest_parity (the core deliverable) runs the OFFICIAL harness twice on
seed 40001 x all six variants - P1 default policy.py, P2 policy_parity.py -
and asserts action_sha256 equality per episode (evaluate.py L93 covers
[phase, day, action] IN ORDER, so this also pins pair/ask ordering), plus
validity and the mutual_second_meeting_intention / assignments /
arrived_members metrics.

Seed policy: 40001 ONLY - the designated plumbing-pilot seed (analysis plan
S.3). Never a training seed (40002-40500) or a final-evaluation seed
(70001-70100).

Output locations: --output uses ABSOLUTE paths into this experiment's
results/ directory (house convention, cf. round2_promotion_fresh_seeds/
run_promo.py L52-57: cwd=repo root so evaluate.py's default relative
--policy policy.py resolves; absolute --output keeps every byte inside
research/round2_stagewise_reward/).
"""
import io
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

EXPERIMENT = Path(__file__).resolve().parents[1]   # research/round2_stagewise_reward
REPO_ROOT = EXPERIMENT.parents[1]                  # repo root (== parents[3] of this file)
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(EXPERIMENT))

import kit
from evaluate import validate_response

SEED = 40001
VARIANTS = ('development', 'sparse', 'cold_start', 'delayed', 'shift', 'drift')
METRIC_FIELDS = ('mutual_second_meeting_intention', 'assignments', 'arrived_members')
PARITY_POLICY = EXPERIMENT / 'policy_parity.py'
RUN_TIMEOUT = 3600


def _sub_env(extra=None):
    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    env.pop('SR_INSTRUMENTATION_DIR', None)
    if extra:
        env.update(extra)
    return env


def _policy_request(phase, state, memory):
    return {'schema_version': kit.VERSION, 'phase': phase,
            'state': state, 'memory': memory}


def _run_policy(mode, request, instrumentation_dir=None):
    """Spawn policy_parity.py exactly like evaluate.invoke() (one JSON request
    line on stdin, one response line expected). Returns the CompletedProcess."""
    env = _sub_env({'SR_INSTRUMENTATION_DIR': instrumentation_dir}
                   if instrumentation_dir else None)
    return subprocess.run(
        [sys.executable, str(PARITY_POLICY), '--baseline', mode],
        input=json.dumps(request, allow_nan=False),
        capture_output=True, text=True, encoding='utf-8', errors='replace',
        env=env, timeout=120)


def _pilot_state():
    """Real day-5 observe() dict on seed 40001 (plumbing-pilot seed), after a
    few baseline days so introductions/feedback exist in the state."""
    sim = kit.Simulator(kit.generate(SEED, 200, 'evaluation', 'development'))
    state = sim.observe()
    for _ in range(5):
        sim.resolve_asks(kit.baseline_asks(state))
        sim.advance(kit.baseline_match(state))
        state = sim.observe()
    return state


def test_adapter_protocol():
    """run_adapter contract (in-process, fake fns) + real policy_parity CLI:
    exact response key sets, memory pass-through, one instrumentation line per
    MATCH invocation only, exact ask/pair equality with kit baselines (order
    included), no_asks support, random rejection."""
    import sr_policy_core as core

    # --- Part 1: in-process core contract --------------------------------
    state = {'day': 3, 'members': []}
    ask_request = _policy_request('ask', state, {'keep': 1})
    match_request = _policy_request('match', {'day': 4, 'members': []}, {'keep': 1})
    calls = []

    def ask_fn(s):
        calls.append(('ask', s['day']))
        return [{'member_id': 'm1', 'field': 'constraints'}], None

    def match_fn(s):
        calls.append(('match', s['day']))
        return [['m1', 'm2']], {'n_available': 2, 'n_edges': 1, 'k_greedy': 1,
                                'k_chosen': 1, 'solver_nodes': 0,
                                'solver_fallback': 0, 'seconds': 0.01}

    with tempfile.TemporaryDirectory() as tmp:
        instr = os.path.join(tmp, 'instr.jsonl')
        stdin = io.StringIO(json.dumps(ask_request) + '\n' + json.dumps(match_request) + '\n')
        stdout = io.StringIO()
        saved = sys.stdin, sys.stdout
        sys.stdin, sys.stdout = stdin, stdout
        try:
            core.run_adapter(ask_fn, match_fn, instr)
        finally:
            sys.stdin, sys.stdout = saved
        lines = stdout.getvalue().splitlines()
        assert len(lines) == 2, 'expected exactly 2 response lines, got %r' % len(lines)
        resp_ask, resp_match = json.loads(lines[0]), json.loads(lines[1])
        assert set(resp_ask) == {'asks', 'memory'}, 'bad ask keys: %r' % set(resp_ask)
        assert set(resp_match) == {'pairs', 'memory'}, 'bad match keys: %r' % set(resp_match)
        validate_response(resp_ask, 'ask')
        validate_response(resp_match, 'match')
        assert resp_ask['asks'] == [{'member_id': 'm1', 'field': 'constraints'}]
        assert resp_match['pairs'] == [['m1', 'm2']]
        assert resp_ask['memory'] == {'keep': 1}, 'ask memory not passed through'
        assert resp_match['memory'] == {'keep': 1}, 'match memory not passed through'
        assert calls == [('ask', 3), ('match', 4)], 'dispatch order/args wrong: %r' % calls
        with open(instr, encoding='utf-8') as fh:
            records = [json.loads(x) for x in fh if x.strip()]
        assert len(records) == 1, 'ask must not instrument; expected 1 line, got %d' % len(records)
        rec = records[0]
        assert rec['day'] == 4 and rec['phase'] == 'match', 'bad day/phase: %r' % rec
        assert rec['pid'] == os.getpid(), 'instrumentation pid mismatch'
        assert rec['k_greedy'] == rec['k_chosen'] == 1 and rec['solver_nodes'] == 0 \
            and rec['solver_fallback'] == 0 and rec['n_available'] == 2 and rec['n_edges'] == 1, \
            'meta fields missing from instrumentation line: %r' % rec

    # list-returning ask_fn (brief interface: ask_fn(state) -> list) also works
    stdout = io.StringIO()
    saved = sys.stdin, sys.stdout
    sys.stdin, sys.stdout = io.StringIO(json.dumps(ask_request) + '\n'), stdout
    try:
        core.run_adapter(lambda s: [{'member_id': 'm9', 'field': 'constraints'}],
                         lambda s: ([], None), None)
    finally:
        sys.stdin, sys.stdout = saved
    assert json.loads(stdout.getvalue())['asks'] == [{'member_id': 'm9', 'field': 'constraints'}]

    # unknown phase fails loudly (no response, propagates)
    sys.stdin, sys.stdout = io.StringIO(json.dumps(_policy_request('nope', state, None)) + '\n'), io.StringIO()
    try:
        try:
            core.run_adapter(ask_fn, match_fn, None)
        except ValueError:
            pass
        else:
            raise AssertionError('unknown phase must raise ValueError')
    finally:
        sys.stdin, sys.stdout = saved

    # --- Part 2: real policy_parity.py CLI + env var ----------------------
    state = _pilot_state()
    with tempfile.TemporaryDirectory() as tmp:
        p = _run_policy('greedy', _policy_request('match', state, None), instrumentation_dir=tmp)
        assert p.returncode == 0, 'match invocation failed: %s' % ascii((p.stderr or p.stdout)[-400:])
        assert p.stdout.strip() and '\n' not in p.stdout.strip(), \
            'expected exactly one response line, got %r' % p.stdout[:200]
        resp = json.loads(p.stdout)
        validate_response(resp, 'match')
        expected = kit.baseline_match(state)
        assert resp['pairs'] == expected, 'pairs differ from kit.baseline_match (ORDER matters)'
        assert resp['memory'] is None, 'null memory must pass through as null'
        files = sorted(os.listdir(tmp))
        assert len(files) == 1 and files[0].endswith('.jsonl'), 'instrumentation files: %r' % files
        rec = json.loads(Path(tmp, files[0]).read_text(encoding='utf-8').strip().splitlines()[0])
        assert rec['pid'] == int(files[0][: -len('.jsonl')]), 'file name pid mismatch: %r' % files[0]
        assert rec['day'] == state['day'] and rec['phase'] == 'match', 'bad day/phase: %r' % rec
        assert rec['k_greedy'] == rec['k_chosen'] == len(expected), \
            'k fields disagree with pairs: %r' % rec
        assert rec['n_available'] == sum(1 for m in state['members'] if m['available']), \
            'n_available wrong: %r' % rec
        assert rec['n_edges'] >= rec['k_greedy'], 'n_edges < k_greedy: %r' % rec
        assert isinstance(rec['seconds'], float) and rec['seconds'] >= 0.0, \
            'seconds wrong: %r' % rec

    p = _run_policy('greedy', _policy_request('ask', state, None))
    assert p.returncode == 0, 'ask invocation failed: %s' % ascii((p.stderr or p.stdout)[-400:])
    resp = json.loads(p.stdout)
    validate_response(resp, 'ask')
    assert resp['asks'] == kit.baseline_asks(state), 'asks differ from kit.baseline_asks (ORDER matters)'
    assert resp['memory'] is None

    p = _run_policy('no_asks', _policy_request('ask', state, None))
    assert p.returncode == 0, 'no_asks invocation failed: %s' % ascii((p.stderr or p.stdout)[-400:])
    assert json.loads(p.stdout)['asks'] == [], 'no_asks must return empty asks (policy.py L24)'

    p = _run_policy('random', _policy_request('ask', state, None))
    assert p.returncode != 0, 'random must be rejected, got rc=0'
    assert 'random' in p.stderr.lower(), 'rejection message must name the mode: %r' % p.stderr[:200]


def _evaluate_command(policy, output_name):
    """Official harness command. cwd must be REPO_ROOT: evaluate.py's default
    --policy policy.py is relative to cwd (evaluate.py L136/L147)."""
    out_path = EXPERIMENT / 'results' / output_name
    cmd = [sys.executable, 'evaluate.py']
    if policy is not None:
        cmd += ['--policy', str(policy)]
    cmd += ['--seeds', str(SEED), '--variants', 'all', '--output', str(out_path)]
    return cmd, out_path


def test_digest_parity():
    """P1 vs P2 on seed 40001 x 6 variants: identical action_sha256, valid
    episodes, identical official metrics (analysis plan S.3 P1/P2)."""
    cmd_a, out_a = _evaluate_command(None, 'pilot_greedy_official.json')                       # default policy.py
    cmd_b, out_b = _evaluate_command(PARITY_POLICY, 'pilot_parity_official.json')              # policy_parity.py
    for stale in (out_a, out_b):
        if stale.exists():
            stale.unlink()   # a stale file must never mask a crashed run
    env = _sub_env()
    procs = []
    started = time.perf_counter()
    for cmd in (cmd_a, cmd_b):
        print('  $ ' + ' '.join(cmd), flush=True)
        p = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True,
                           text=True, encoding='utf-8', errors='replace',
                           env=env, timeout=RUN_TIMEOUT)
        procs.append(p)
        print('    rc=%d %.1fs' % (p.returncode, time.perf_counter() - started), flush=True)
    failures = 0
    for label, p in zip(('policy.py', 'policy_parity.py'), procs):
        if p.returncode != 0:
            failures += 1
            print('[FAIL] %s evaluate run exited rc=%d: %s'
                  % (label, p.returncode, ascii((p.stderr or p.stdout or '')[-300:])), flush=True)
    episodes = {}
    for label, path in (('policy.py', out_a), ('policy_parity.py', out_b)):
        if not path.exists():
            episodes[label] = {}
            continue
        rows = json.loads(path.read_text(encoding='utf-8'))['episodes']
        episodes[label] = {(r.get('variant'), r.get('seed')): r for r in rows}
    for variant in VARIANTS:
        key = (variant, SEED)
        problems = []
        a = episodes['policy.py'].get(key)
        b = episodes['policy_parity.py'].get(key)
        if a is None or b is None:
            problems.append('episode missing (policy.py=%s parity=%s)' % (a is not None, b is not None))
        else:
            if not (a.get('valid') is True and b.get('valid') is True):
                problems.append('invalid episode (policy.py valid=%r parity valid=%r)'
                                % (a.get('valid'), b.get('valid')))
            if a.get('action_sha256') != b.get('action_sha256'):
                problems.append('action_sha256 %s != %s'
                                % (a.get('action_sha256'), b.get('action_sha256')))
            for field in METRIC_FIELDS:
                if a.get(field) != b.get(field):
                    problems.append('%s %r != %r' % (field, a.get(field), b.get(field)))
        if problems:
            failures += 1
            print('[FAIL] %s/seed%d: %s' % (variant, SEED, '; '.join(problems)), flush=True)
        else:
            print('[PASS] %s/seed%d digest=%s' % (variant, SEED, a['action_sha256'][:16]), flush=True)
    print('EPISODE SUMMARY: %d/%d PASS (%.1fs total)'
          % (len(VARIANTS) - (failures - sum(1 for p in procs if p.returncode != 0)),
             len(VARIANTS), time.perf_counter() - started), flush=True)
    assert failures == 0, 'parity failures: %d' % failures


def main():
    tests = [test_adapter_protocol, test_digest_parity]
    failures = 0
    for test in tests:
        try:
            test()
        except Exception as exc:  # noqa: BLE001 - test harness reports every failure
            failures += 1
            print('[FAIL] %s: %s' % (test.__name__, ascii(str(exc))[:300]), flush=True)
        else:
            print('[PASS] %s' % test.__name__, flush=True)
    print('SUMMARY: %d/%d PASS' % (len(tests) - failures, len(tests)))
    sys.exit(1 if failures else 0)


if __name__ == '__main__':
    main()
