"""Tests for policy_candidate.py (implementation_plan.md Task 8, gate V6).

Plain python script, standard library only (+ repo kit/evaluate), no pytest.
Prints [PASS]/[FAIL] PER ASSERTION, a summary, and exits non-zero on any
failure.

  test_exact_cardinality  OFFICIAL harness run: evaluate.py --policy
      policy_candidate.py --seeds 40001 --variants all --output
      results/pilot_candidate_official.json with SR_INSTRUMENTATION_DIR set to
      a temp dir (cwd=repo root, PYTHONIOENCODING=utf-8). Asserts 6/6 episodes
      valid:true, exactly 360 instrumentation lines (6 episodes x 60 match
      days), and on EVERY line k_chosen == k_greedy with solver_fallback == 0
      (pilot states are small - Task 7 V3 measured max solve 21.6 ms).
  test_deterministic      the SAME episode (seed 40001, variant development)
      run twice through evaluate.py; action_sha256 must be byte-identical.
  test_inference_budget   from the instrumentation lines of the official run:
      max seconds < 2.0 (plan S.8 budget).

Seed policy: 40001 ONLY (designated plumbing-pilot seed). Never a training
seed (40002-40500) and NEVER a final-evaluation seed (70001-70100). No tuning
of any kind.

Outputs: results/pilot_candidate_official.json (harness) only; determinism
runs write into temp dirs so nothing else lands in the repo.
"""
import json
import os
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

EXPERIMENT = Path(__file__).resolve().parents[1]   # research/round2_stagewise_reward
REPO_ROOT = EXPERIMENT.parents[1]                  # repo root
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(EXPERIMENT))

POLICY = EXPERIMENT / 'policy_candidate.py'
OFFICIAL_OUTPUT = EXPERIMENT / 'results' / 'pilot_candidate_official.json'
SEED = 40001
VARIANTS = ('development', 'sparse', 'cold_start', 'delayed', 'shift', 'drift')
DETERMINISM_VARIANT = 'development'
EXPECTED_LINES = 360                 # 6 episodes x 60 match days
SECONDS_BUDGET = 2.0                 # plan S.8 per-call inference budget
RUN_TIMEOUT = 3600

_failures = 0
_checks = 0
_instr_lines = []                    # filled by test_exact_cardinality


def check(label, ok, detail=''):
    """Single [PASS]/[FAIL] assertion line."""
    global _failures, _checks
    _checks += 1
    if ok:
        print('[PASS] %s' % label, flush=True)
    else:
        _failures += 1
        print('[FAIL] %s%s' % (label, (' :: ' + detail) if detail else ''),
              flush=True)
    return ok


def _sub_env(extra=None):
    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    env.pop('SR_INSTRUMENTATION_DIR', None)
    if extra:
        env.update(extra)
    return env


def _evaluate_cmd(policy, output_path, variants='all'):
    """Official harness command; cwd MUST be REPO_ROOT (evaluate.py's relative
    defaults + kit import layout)."""
    return [sys.executable, 'evaluate.py',
            '--policy', str(policy),
            '--seeds', str(SEED),
            '--variants', variants,
            '--output', str(output_path)]


def _run(cmd, env, timeout=RUN_TIMEOUT):
    print('  $ ' + ' '.join(cmd), flush=True)
    started = time.perf_counter()
    p = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True,
                       text=True, encoding='utf-8', errors='replace',
                       env=env, timeout=timeout)
    print('    rc=%d %.1fs' % (p.returncode, time.perf_counter() - started),
          flush=True)
    return p


def _read_instrumentation(directory):
    """All JSON lines from every <pid>.jsonl in directory (the harness spawns
    one process per invocation, but pid reuse can append to one file)."""
    lines = []
    for path in sorted(Path(directory).glob('*.jsonl')):
        for raw in path.read_text(encoding='utf-8').splitlines():
            if raw.strip():
                lines.append(json.loads(raw))
    return lines


def test_exact_cardinality():
    """Official 6-episode run + full instrumentation audit."""
    global _instr_lines
    if OFFICIAL_OUTPUT.exists():
        OFFICIAL_OUTPUT.unlink()          # a stale file must never mask a crash
    with tempfile.TemporaryDirectory() as instr:
        p = _run(_evaluate_cmd(POLICY, OFFICIAL_OUTPUT),
                 _sub_env({'SR_INSTRUMENTATION_DIR': instr}))
        check('official harness exit code 0', p.returncode == 0,
              'rc=%d %s' % (p.returncode, ascii((p.stderr or p.stdout or '')[-300:])))

        rows = []
        if OFFICIAL_OUTPUT.exists():
            rows = json.loads(OFFICIAL_OUTPUT.read_text(encoding='utf-8'))['episodes']
        check('output written with 6 episodes', len(rows) == 6,
              'got %d episodes' % len(rows))
        bad = [(r.get('variant'), r.get('seed'), r.get('error'))
               for r in rows if r.get('valid') is not True]
        check('all 6 episodes valid:true', not bad, 'invalid: %r' % (bad,))

        lines = _read_instrumentation(instr)
        _instr_lines = lines
        check('instrumentation line count == %d' % EXPECTED_LINES,
              len(lines) == EXPECTED_LINES, 'got %d lines' % len(lines))

        phase_ok = all(rec.get('phase') == 'match' for rec in lines)
        check('every line is a match-phase record', phase_ok,
              'non-match lines: %d' % sum(1 for r in lines if r.get('phase') != 'match'))

        mismatched = [rec for rec in lines if rec.get('k_chosen') != rec.get('k_greedy')]
        check('k_chosen == k_greedy on every line (%d lines)' % len(lines),
              not mismatched, '%d mismatches, first: %r'
              % (len(mismatched), mismatched[:1]))

        fallbacks = [rec for rec in lines if rec.get('solver_fallback') != 0]
        check('solver_fallback == 0 on every line', not fallbacks,
              '%d fallbacks, first: %r' % (len(fallbacks), fallbacks[:1]))


def test_deterministic():
    """Same episode twice -> byte-identical action_sha256."""
    env = _sub_env()
    digests, valids = [], []
    with tempfile.TemporaryDirectory() as tmp:
        for run in (1, 2):
            out = Path(tmp) / ('run%d.json' % run)
            p = _run(_evaluate_cmd(POLICY, out, DETERMINISM_VARIANT), env)
            check('determinism run %d exit code 0' % run, p.returncode == 0,
                  'rc=%d %s' % (p.returncode, ascii((p.stderr or p.stdout or '')[-300:])))
            if out.exists():
                rows = json.loads(out.read_text(encoding='utf-8'))['episodes']
                valids.append(bool(rows) and rows[0].get('valid') is True)
                digests.append(rows[0].get('action_sha256') if rows else None)
            else:
                valids.append(False)
                digests.append(None)
    check('determinism episodes valid', all(valids), 'valids=%r' % valids)
    check('action_sha256 identical across the two runs',
          len(digests) == 2 and digests[0] is not None and digests[0] == digests[1],
          'digests=%r' % (digests,))
    if len(digests) == 2 and digests[0]:
        print('    action_sha256 = %s' % digests[0], flush=True)


def test_inference_budget():
    """max per-call seconds < 2.0 from the official run's instrumentation."""
    check('instrumentation lines available for budget check', bool(_instr_lines),
          'run test_exact_cardinality first')
    if not _instr_lines:
        return
    seconds = [rec['seconds'] for rec in _instr_lines if 'seconds' in rec]
    check('every line carries a seconds counter', len(seconds) == len(_instr_lines),
          '%d/%d lines have seconds' % (len(seconds), len(_instr_lines)))
    if not seconds:
        return
    worst = max(seconds)
    med = statistics.median(seconds)
    print('    seconds: max=%.4f median=%.4f mean=%.4f (n=%d)'
          % (worst, med, statistics.mean(seconds), len(seconds)), flush=True)
    check('max seconds < %.1f' % SECONDS_BUDGET, worst < SECONDS_BUDGET,
          'max=%.4f' % worst)


def main():
    tests = [test_exact_cardinality, test_deterministic, test_inference_budget]
    for test in tests:
        try:
            test()
        except Exception as exc:   # noqa: BLE001 - harness reports every failure
            check('%s raised' % test.__name__, False,
                  '%s: %s' % (type(exc).__name__, ascii(str(exc))[:300]))
    if _instr_lines:
        seconds = [rec['seconds'] for rec in _instr_lines if 'seconds' in rec]
        print('INSTRUMENTATION SUMMARY: lines=%d fallbacks=%d '
              'max_seconds=%s median_seconds=%s'
              % (len(_instr_lines),
                 sum(1 for r in _instr_lines if r.get('solver_fallback') != 0),
                 ('%.4f' % max(seconds)) if seconds else 'n/a',
                 ('%.4f' % statistics.median(seconds)) if seconds else 'n/a'),
              flush=True)
    print('SUMMARY: %d/%d assertions PASS' % (_checks - _failures, _checks))
    sys.exit(1 if _failures else 0)


if __name__ == '__main__':
    main()
