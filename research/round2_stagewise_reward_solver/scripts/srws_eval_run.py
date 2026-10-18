"""Task 5: run the final paired sequential evaluation (E-series) via the
UNMODIFIED evaluator, both arms, seeds 70001-70100 x all six variants.

GATED: may only run if results/solver_validation.json passed=true AND
results/runtime_benchmark.json all_gates_passed=true AND
results/policy_validity.json passed=true. This script re-checks those gates
before launching and aborts if any fail.

Arms (S.9):
  greedy    --policy policy.py            (the untouched official greedy default)
  candidate --policy .../policy_candidate.py
Identical seed/variant cells in both arms. SRS_INSTRUMENTATION_DIR is set for
the CANDIDATE arm only; instrumentation files are evidence, never protocol
output. Each arm appends per-episode JSONL progress (results/eval_<arm>_progress.jsonl)
as it runs so a crash leaves partial evidence; the full result is written by
evaluate.py to results/eval_<arm>.json.

Standard library only. Never mutates git, the frozen model, or any protected
file. Seeds consumed here are the evaluation seeds 70001-70100 (designated).
"""
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

EXPERIMENT = Path(__file__).resolve().parents[1]
REPO_ROOT = EXPERIMENT.parents[1]
RESULTS = EXPERIMENT / 'results'
INSTR_DIR = RESULTS / 'eval_instrumentation'

SEEDS = list(range(70001, 70101))       # 100 evaluation seed groups (S.9)
SEEDS_SPEC = ','.join(str(s) for s in SEEDS)
VARIANTS = 'all'
POLICY_CANDIDATE = EXPERIMENT / 'policy_candidate.py'
POLICY_GREEDY = REPO_ROOT / 'policy.py'

ARMS = [
    ('greedy', POLICY_GREEDY, False),
    ('candidate', POLICY_CANDIDATE, True),
]


def now():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def check_gates():
    """Enforce the S.9 pre-conditions before consuming evaluation seeds."""
    sv = json.loads((RESULTS / 'solver_validation.json').read_text(encoding='utf-8'))
    rb = json.loads((RESULTS / 'runtime_benchmark.json').read_text(encoding='utf-8'))
    pv = json.loads((RESULTS / 'policy_validity.json').read_text(encoding='utf-8'))
    ok = bool(sv.get('passed')) and bool(rb.get('all_gates_passed')) and bool(pv.get('passed'))
    print('[gates] solver_validation.passed=%s runtime_benchmark.all_gates_passed=%s '
          'policy_validity.passed=%s -> %s'
          % (sv.get('passed'), rb.get('all_gates_passed'), pv.get('passed'),
             'PROCEED' if ok else 'ABORT'), flush=True)
    return ok


def run_arm(name, policy, instrument):
    out_json = RESULTS / ('eval_%s.json' % name)
    progress = RESULTS / ('eval_%s_progress.jsonl' % name)
    runrec = RESULTS / ('eval_%s_run.json' % name)
    cmd = [sys.executable, 'evaluate.py', '--policy', str(policy),
           '--baseline', 'greedy', '--seeds', SEEDS_SPEC,
           '--variants', VARIANTS, '--output', str(out_json)]
    env = dict(__import__('os').environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    env.pop('SRS_INSTRUMENTATION_DIR', None)
    if instrument:
        INSTR_DIR.mkdir(parents=True, exist_ok=True)
        env['SRS_INSTRUMENTATION_DIR'] = str(INSTR_DIR)
    # fresh progress file for this run (crash-safe append follows)
    progress.write_text('', encoding='utf-8')
    print('[%s] $ %s' % (name, ' '.join(cmd)), flush=True)
    t0 = time.perf_counter()
    started = now()
    rc = None
    # stream stdout; append each per-episode JSON line to progress (crash-safe)
    proc = subprocess.Popen(cmd, cwd=str(REPO_ROOT), env=env, bufsize=1,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, encoding='utf-8', errors='replace')
    n_lines = 0
    with open(progress, 'a', encoding='utf-8') as pf:
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            # evaluate.py prints one compact JSON object per finished episode
            if line.startswith('{') and '"seed"' in line:
                try:
                    obj = json.loads(line)
                    pf.write(json.dumps(obj, sort_keys=True) + '\n')
                    pf.flush()
                    n_lines += 1
                    if n_lines % 50 == 0:
                        print('[%s] %d episodes (%.0fs)' % (name, n_lines,
                                                            time.perf_counter() - t0),
                              flush=True)
                except json.JSONDecodeError:
                    pass
    stderr_tail = proc.stderr.read()[-2000:] if proc.stderr else ''
    proc.wait()
    rc = proc.returncode
    wall = time.perf_counter() - t0
    runrec.write_text(json.dumps({
        'arm': name, 'command': cmd, 'policy': str(policy),
        'seeds_spec': SEEDS_SPEC, 'variants': VARIANTS,
        'instrumented': instrument, 'started_utc': started,
        'finished_utc': now(), 'returncode': rc, 'wall_seconds': wall,
        'progress_lines': n_lines, 'stderr_tail': stderr_tail,
    }, indent=2), encoding='utf-8')
    print('[%s] rc=%d wall=%.0fs progress_lines=%d' % (name, rc, wall, n_lines),
          flush=True)
    if stderr_tail:
        print('[%s] stderr tail: %s' % (name, stderr_tail[-500:]), flush=True)
    return rc


def main():
    print('=== Task 5: final paired sequential evaluation (E-series) ===', flush=True)
    print('start %s' % now(), flush=True)
    if not check_gates():
        print('ABORT: a required C/R/P gate has not passed; evaluation seeds '
              'remain untouched.', flush=True)
        return 2
    rcs = {}
    for name, policy, instrument in ARMS:
        rcs[name] = run_arm(name, policy, instrument)
    print('=== eval run complete: rcs=%s ===' % rcs, flush=True)
    print('end %s' % now(), flush=True)
    # evaluate.py returns 0 only if every episode in that arm was valid.
    return 0 if all(rc == 0 for rc in rcs.values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
