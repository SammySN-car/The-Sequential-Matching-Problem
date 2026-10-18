"""Post-run verification: deterministic rerun slice + container parity.

Slice (fixed, preregistered): seeds 119 and 130 x all 6 variants = 12 episodes
per arm.

Phase determinism : rerun the slice locally (official evaluate.py CLI) and
                    require byte-identical action_sha256 + metrics vs the main
                    per_arm/<arm>.json run.  -> determinism_rerun.json
Phase container   : run the slice in Docker (control = frozen image, E-arms =
                    derived Dockerfile.e3 images) and require action_sha256 +
                    metrics parity vs local. -> container_fidelity.json

inference_seconds (wall clock) is excluded from equality; everything else in
the episode row must match exactly.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

from evaluate import VARIANTS, docker_command, episode  # noqa: E402
from kit import generate  # noqa: E402
from run_experiment import ARMS, log, official_command  # noqa: E402

SLICE_SEEDS = [119, 130]
IMAGES = {'C': 'e3-control', 'E1': 'e3-arm-e1', 'E2': 'e3-arm-e2',
          'E3': 'e3-arm-e3'}


def slice_keys():
    return [(s, v) for v in VARIANTS for s in SLICE_SEEDS]


def row_equal(a, b, ignore=('inference_seconds',)):
    ka = {k: v for k, v in a.items() if k not in ignore}
    kb = {k: v for k, v in b.items() if k not in ignore}
    return ka == kb


def load_main(arm):
    j = json.loads((HERE / 'per_arm' / (arm + '.json')).read_text(encoding='utf-8'))
    return {(r['seed'], r['variant']): r for r in j['episodes']}


def run_determinism():
    main = {a: load_main(a) for a in ARMS}
    procs, started = {}, time.time()
    for arm in ARMS:
        out = HERE / 'per_arm' / ('rerun_' + arm + '.json')
        cmd = official_command(arm, SLICE_SEEDS, out)
        log(f'determinism slice start arm={arm}')
        procs[arm] = subprocess.Popen(cmd, cwd=str(ROOT),
                                      stdout=subprocess.PIPE,
                                      stderr=subprocess.STDOUT, text=True)
    failed = []
    for arm, proc in procs.items():
        proc.communicate()
        if proc.returncode != 0:
            failed.append(arm)
    mismatches = {}
    for arm in ARMS:
        if arm in failed:
            mismatches[arm] = 'rerun process failed'
            continue
        rr = json.loads((HERE / 'per_arm' / ('rerun_' + arm + '.json')
                         ).read_text(encoding='utf-8'))
        bad = []
        for r in rr['episodes']:
            key = (r['seed'], r['variant'])
            base = main[arm].get(key)
            if base is None:
                bad.append([list(key), 'missing in main run'])
            elif r.get('action_sha256') != base.get('action_sha256'):
                bad.append([list(key), 'digest mismatch'])
            elif not row_equal(r, base):
                bad.append([list(key), 'metrics mismatch'])
        mismatches[arm] = bad
    payload = {'slice_seeds': SLICE_SEEDS,
               'episodes_per_arm': len(slice_keys()),
               'mismatches': mismatches,
               'pass': all(v == [] for v in mismatches.values()),
               'duration_seconds': time.time() - started}
    (HERE / 'determinism_rerun.json').write_text(
        json.dumps(payload, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    log(f'determinism DONE pass={payload["pass"]} '
        f'duration={payload["duration_seconds"]:.0f}s')
    return 0 if payload['pass'] else 1


def run_container_arm(arm):
    """12 slice episodes in Docker for one arm -> per_arm/container_<arm>.json"""
    command = docker_command(IMAGES[arm])
    rows, invalid = [], []
    started = time.time()
    for v in VARIANTS:
        for s in SLICE_SEEDS:
            try:
                r = episode(generate(s, 200, 'evaluation', v), command)
            except (ValueError, TypeError, KeyError, OSError) as error:
                r = {'valid': False, 'error': str(error)}
            r.update(seed=s, variant=v)
            if not r.get('valid'):
                invalid.append([s, v, r.get('error')])
            rows.append(r)
            log(f'container[{arm}] seed={s} variant={v} valid={r.get("valid")}')
    out = HERE / 'per_arm' / ('container_' + arm + '.json')
    out.write_text(json.dumps({'arm': arm, 'episodes': rows,
                               'invalid': invalid,
                               'duration_seconds': time.time() - started},
                              indent=2, allow_nan=False) + '\n', encoding='utf-8')
    log(f'container[{arm}] DONE invalid={len(invalid)} '
        f'duration={time.time() - started:.0f}s')
    return 1 if invalid else 0


def run_container_compare():
    procs = {}
    for arm in ARMS:
        cmd = [sys.executable, str(Path(__file__).resolve()),
               '--phase', 'container', '--arm', arm]
        log(f'container parent spawning arm={arm}')
        procs[arm] = subprocess.Popen(cmd, cwd=str(ROOT),
                                      stdout=subprocess.PIPE,
                                      stderr=subprocess.STDOUT, text=True)
    failed = []
    for arm, proc in procs.items():
        proc.communicate()
        if proc.returncode != 0:
            failed.append(arm)
    mismatches = {}
    for arm in ARMS:
        path = HERE / 'per_arm' / ('container_' + arm + '.json')
        if arm in failed or not path.exists():
            mismatches[arm] = 'container run failed'
            continue
        main = load_main(arm)
        data = json.loads(path.read_text(encoding='utf-8'))
        bad = []
        for r in data['episodes']:
            key = (r['seed'], r['variant'])
            base = main.get(key)
            if not r.get('valid'):
                bad.append([list(key), 'invalid: ' + str(r.get('error'))])
            elif base is None or r.get('action_sha256') != base.get('action_sha256'):
                bad.append([list(key), 'digest mismatch local-vs-container'])
            elif not row_equal(r, base):
                bad.append([list(key), 'metrics mismatch local-vs-container'])
        mismatches[arm] = bad
    payload = {'images': IMAGES, 'slice_seeds': SLICE_SEEDS,
               'episodes_per_arm': len(slice_keys()),
               'mismatches': mismatches,
               'pass': all(v == [] for v in mismatches.values())}
    (HERE / 'container_fidelity.json').write_text(
        json.dumps(payload, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    log(f'container DONE pass={payload["pass"]}')
    return 0 if payload['pass'] else 1


def run_control_parity():
    """Two extra control comparisons the plain image cannot provide:

    1. control-greedy: the frozen image's entrypoint runs `python policy.py`
       with NO args, and policy.py's argparse default is 'ac' -> the official
       image executes A+C mode, not greedy (by design, docs/POLICY_INTERFACE).
       Greedy-in-container therefore uses the derived Dockerfile.control image
       and is compared against the local official greedy rows.
    2. official-image (A+C) mode: local `python policy.py` (no args, default
       ac) vs the frozen e3-control image -> pure environment parity
       (py3.12 vs 3.13, docker isolation, hash seed) on the A+C path.
    """
    main_c = load_main('C')
    path = HERE / 'container_fidelity.json'
    payload = json.loads(path.read_text(encoding='utf-8'))
    prev = payload.get('control_extra') or {}
    rows_out = {}
    # --- 1. control-greedy in derived image --------------------------------
    command = docker_command('e3-control-greedy')
    bad = []
    started = time.time()
    for v in VARIANTS:
        for s in SLICE_SEEDS:
            try:
                r = episode(generate(s, 200, 'evaluation', v), command)
            except (ValueError, TypeError, KeyError, OSError) as error:
                r = {'valid': False, 'error': str(error), 'seed': s,
                     'variant': v}
            base = main_c[(s, v)]
            r.update(seed=s, variant=v)   # official rows carry these keys
            if not r.get('valid'):
                bad.append([[s, v], 'invalid: ' + str(r.get('error'))])
            elif r.get('action_sha256') != base.get('action_sha256'):
                bad.append([[s, v], 'digest mismatch greedy local-vs-container'])
            elif not row_equal(r, base):
                bad.append([[s, v], 'metrics mismatch greedy local-vs-container'])
            log(f'ctrl-greedy[{v}/{s}] valid={r.get("valid")}')
    rows_out['C_greedy_derived_image'] = bad
    log(f'ctrl-greedy DONE mismatches={len(bad)} '
        f'duration={time.time() - started:.0f}s')
    # --- 2. official image A+C mode, local vs container -------------------
    if isinstance(prev.get('C_ac_official_image'), list) \
            and prev.get('C_ac_invalid') == []:
        rows_out['C_ac_official_image'] = prev['C_ac_official_image']
        rows_out['C_ac_invalid'] = prev['C_ac_invalid']
        log('ctrl-ac reused from previous run')
        local_cmd = None
    else:
        local_cmd = [sys.executable, str(ROOT / 'policy.py')]
    if local_cmd is not None:
        bad_ac, invalid = [], []
        started = time.time()
        for v in VARIANTS:
            for s in SLICE_SEEDS:
                try:
                    rl = episode(generate(s, 200, 'evaluation', v), local_cmd)
                except (ValueError, TypeError, KeyError, OSError) as error:
                    rl = {'valid': False, 'error': str(error)}
                try:
                    rc = episode(generate(s, 200, 'evaluation', v),
                                 docker_command('e3-control'))
                except (ValueError, TypeError, KeyError, OSError) as error:
                    rc = {'valid': False, 'error': str(error)}
                if not rl.get('valid') or not rc.get('valid'):
                    invalid.append([s, v, str(rl.get('error')),
                                    str(rc.get('error'))])
                    bad_ac.append([[s, v], 'invalid'])
                elif rl.get('action_sha256') != rc.get('action_sha256'):
                    bad_ac.append([[s, v], 'digest mismatch ac local-vs-container'])
                elif not row_equal(rl, rc):
                    bad_ac.append([[s, v], 'metrics mismatch ac local-vs-container'])
                log(f'ctrl-ac[{v}/{s}] local={rl.get("valid")} '
                    f'container={rc.get("valid")}')
        rows_out['C_ac_official_image'] = bad_ac
        rows_out['C_ac_invalid'] = invalid
        log(f'ctrl-ac DONE mismatches={len(bad_ac)} invalid={len(invalid)} '
            f'duration={time.time() - started:.0f}s')
    # --- merge into container_fidelity.json --------------------------------
    payload['control_extra'] = rows_out
    payload['pass'] = (payload.get('pass')
                       and all(v == [] for v in rows_out.values()
                               if isinstance(v, list)))
    path.write_text(json.dumps(payload, indent=2, allow_nan=False) + '\n',
                    encoding='utf-8')
    log(f'control parity merged pass={payload["pass"]}')
    return 0 if payload['pass'] else 1


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--phase', choices=['determinism', 'container',
                                       'container_arm', 'control_parity'],
                   required=True)
    p.add_argument('--arm', choices=list(ARMS))
    args = p.parse_args()
    if args.phase == 'determinism':
        return run_determinism()
    if args.phase == 'control_parity':
        return run_control_parity()
    if args.phase == 'container':
        if args.arm:
            return run_container_arm(args.arm)
        return run_container_compare()
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
