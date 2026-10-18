"""Run harness for round2 promotion fresh-seed evaluation.
Phases: official (36 runs), rerun (4 determinism runs), container (1 run).
Idempotent: skips runs whose output already exists. Appends to run_log.txt.
"""
import argparse
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]

SEEDS = list(range(107, 119))
ARMS = {
    'greedy':    (['--policy', 'policy.py', '--baseline', 'greedy'], 'greedy'),
    'original':  (['--policy', 'policy_ac.py'], 'original'),
    'floorhalf': (['--policy',
                   'research/round2_stage3_intermediate_floor/intermediate_policy.py'],
                  'floorhalf'),
}
RERUN_PLAN = [('greedy', 107), ('original', 107), ('floorhalf', 107),
              ('floorhalf', 118)]
LOG = HERE / 'run_log.txt'


def plan(phase, seeds):
    runs = []
    if phase == 'official':
        for arm in ('greedy', 'original', 'floorhalf'):
            for s in seeds:
                runs.append((arm, s, 'arm_%s_seed%d.json' % (ARMS[arm][1], s), False))
    elif phase == 'rerun':
        for arm, s in RERUN_PLAN:
            runs.append((arm, s, 'arm_%s_seed%d_rerun.json' % (ARMS[arm][1], s), False))
    elif phase == 'container':
        runs.append(('greedy', 107, 'arm_greedy_seed107_container.json', True))
    else:
        raise SystemExit('bad phase')
    if phase == 'rerun':
        return [r for r in runs if r[1] in seeds]
    return runs


def one(r):
    arm, s, out_name, use_image = r
    out_path = HERE / out_name
    if out_path.exists():
        return (out_name, 'SKIP_EXISTS', 0.0, '')
    cmd = [sys.executable, 'evaluate.py']
    if use_image:
        cmd += ['--image', 'sequential-policy:1.0']
    else:
        cmd += ARMS[arm][0]
    cmd += ['--seeds', str(s), '--variants', 'all', '--output', str(out_path)]
    t0 = time.time()
    try:
        p = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True,
                           timeout=900)
        dt = time.time() - t0
        status = 'OK' if p.returncode == 0 else 'FAIL rc=%d' % p.returncode
        tail = (p.stderr or p.stdout or '').strip().splitlines()
        note = tail[-1][:200] if status != 'OK' else ''
    except subprocess.TimeoutExpired:
        dt = time.time() - t0
        status, note = 'TIMEOUT', '900s'
    line = '%s | %-7s | %-28s | %6.1fs | %s %s' % (
        time.strftime('%H:%M:%S'), phase_g, out_name, dt, status, note)
    with LOG.open('a', encoding='utf-8') as f:
        f.write(line + '\n')
    return (out_name, status, dt, note)


def main():
    global phase_g
    ap = argparse.ArgumentParser()
    ap.add_argument('--phase', required=True,
                    choices=['official', 'rerun', 'container'])
    ap.add_argument('--seeds', default='')
    ap.add_argument('--workers', type=int, default=6)
    a = ap.parse_args()
    seeds = [int(x) for x in a.seeds.split(',') if x] or list(SEEDS)
    runs = plan(a.phase, seeds)
    phase_g = a.phase
    with LOG.open('a', encoding='utf-8') as f:
        f.write('\n[%s] phase=%s seeds=%s runs=%d workers=%d @ %s\n' % (
            time.strftime('%Y-%m-%d %H:%M:%S'), a.phase, seeds, len(runs),
            a.workers, time.strftime('%H:%M:%S')))
    t0 = time.time()
    results = []
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(one, r): r for r in runs}
        for fu in as_completed(futs):
            results.append(fu.result())
            print(results[-1][0], results[-1][1], '%.0fs' % results[-1][2],
                  flush=True)
    bad = [r for r in results if r[1] not in ('OK', 'SKIP_EXISTS')]
    with LOG.open('a', encoding='utf-8', ) as f:
        f.write('  phase done: %d runs, %d bad, wall %.1fs\n' % (
            len(results), len(bad), time.time() - t0))
    print('DONE %d runs, %d bad, wall %.0fs' % (len(results), len(bad),
                                                time.time() - t0))
    if bad:
        print('BAD:', bad)
        sys.exit(1)


if __name__ == '__main__':
    main()