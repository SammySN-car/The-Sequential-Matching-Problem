"""Diagnostic driver: arms frozen(B) + intermediate(C) x seeds 107-118."""
import argparse
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
LOG = HERE / 'run_log.txt'
SEEDS = list(range(107, 119))
ARMS = {'frozen': 'arm_original', 'intermediate': 'arm_floorhalf'}


def one(job):
    arm, seed = job
    out = HERE / ('diag_%s_seed%d.json' % (arm, seed))
    ref = HERE / ('%s_seed%d.json' % (ARMS[arm], seed))
    if out.exists():
        return (out.name, 'SKIP_EXISTS', 0.0)
    cmd = [sys.executable, str(HERE / 'diag_promo.py'), '--arm', arm,
           '--seed', str(seed), '--ref', str(ref), '--out', str(out)]
    t0 = time.time()
    try:
        p = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True,
                           timeout=600)
        dt = time.time() - t0
        ok = p.returncode == 0 and 'ALL_FIDELITY_OK True' in p.stdout
        status = 'OK' if ok else ('FAIL rc=%d' % p.returncode)
        note = '' if ok else ((p.stderr or '') + (p.stdout or ''))[-300:]
    except subprocess.TimeoutExpired:
        dt, status, note = time.time() - t0, 'TIMEOUT', '600s'
    with LOG.open('a', encoding='utf-8') as f:
        f.write('%s | diag   | %-30s | %6.1fs | %s %s\n' % (
            time.strftime('%H:%M:%S'), out.name, dt, status, note))
    return (out.name, status, dt, note)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--workers', type=int, default=6)
    ap.add_argument('--seeds', default='')
    a = ap.parse_args()
    seeds = [int(x) for x in a.seeds.split(',') if x] or SEEDS
    jobs = [(arm, s) for arm in ARMS for s in seeds]
    with LOG.open('a', encoding='utf-8') as f:
        f.write('\n[%s] phase=diag jobs=%d workers=%d\n' % (
            time.strftime('%Y-%m-%d %H:%M:%S'), len(jobs), a.workers))
    res = []
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        for fu in as_completed([ex.submit(one, j) for j in jobs]):
            res.append(fu.result())
            print(res[-1][0], res[-1][1], '%.0fs' % res[-1][2], flush=True)
    bad = [r for r in res if r[1] != 'OK' and r[1] != 'SKIP_EXISTS']
    print('DONE %d jobs, %d bad, wall %.0fs' % (len(res), len(bad),
                                                time.time() - t0))
    if bad:
        print('BAD:', bad)
        sys.exit(1)


if __name__ == '__main__':
    main()