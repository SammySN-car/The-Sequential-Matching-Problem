"""Runner for the E1/E2/E3 experiment (preregistered in experiment_plan.json).

Phases:
  smoke      - official evaluate.py pass, seed 119 only (24 episodes, pre-flight)
  official   - full 288-episode official pass: 4 arms x seeds 119..130 x 6 variants
  mechanism  - second instrumented pass (evaluate.episode + InstrumentedSim),
               cross-checks action_sha256 against the official pass per episode

Run from the repository root. Writes run_log.txt and per_arm/*.json.
Exit code 0 = all episodes valid (and mechanism digests match, where run).
"""
import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

from evaluate import VARIANTS, episode  # noqa: E402
from kit import generate  # noqa: E402
from instrumented_sim import InstrumentedSim, episode_mechanism  # noqa: E402

PER_ARM = HERE / 'per_arm'
LOG = HERE / 'run_log.txt'
SEEDS_FULL = list(range(119, 131))
SEEDS_STAGE2 = list(range(131, 143))
SEEDS_SMOKE = [119]
ARMS = {
    'C': {'policy': 'policy.py'},
    'E1': {'policy': str(HERE / 'policy_e1.py')},
    'E2': {'policy': str(HERE / 'policy_e2.py')},
    'E3': {'policy': str(HERE / 'policy_e3.py')},
}


def log(msg):
    stamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    line = f'[{stamp}] {msg}'
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(line + '\n')
    print(line, flush=True)


def official_command(arm, seeds, output):
    return [sys.executable, str(ROOT / 'evaluate.py'),
            '--policy', ARMS[arm]['policy'], '--baseline', 'greedy',
            '--seeds', ','.join(str(s) for s in seeds),
            '--variants', 'all', '--output', str(output)]


def run_official(smoke=False, stage2=False):
    seeds = SEEDS_SMOKE if smoke else (SEEDS_STAGE2 if stage2 else SEEDS_FULL)
    tag = 'smoke' if smoke else ('stage2' if stage2 else 'full')
    PER_ARM.mkdir(parents=True, exist_ok=True)
    procs = {}
    for arm in ARMS:
        out = PER_ARM / ('smoke_' + arm + '.json' if smoke
                         else ('s2_' + arm + '.json' if stage2
                               else arm + '.json'))
        cmd = official_command(arm, seeds, out)
        started = time.time()
        log(f'official[{tag}] arm={arm} start cmd={" ".join(cmd)}')
        procs[arm] = (subprocess.Popen(cmd, cwd=str(ROOT),
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT,
                                       text=True), started, out)
    failed = []
    for arm, (proc, started, out) in procs.items():
        stdout, _ = proc.communicate()
        took = time.time() - started
        log(f'official[{tag}] arm={arm} exit={proc.returncode} '
            f'duration={took:.1f}s output={out.name}')
        for ln in (stdout or '').strip().splitlines()[-6:]:
            log(f'  {arm}| {ln}')
        if proc.returncode != 0 or not out.exists():
            failed.append(arm)
    if failed:
        log(f'official[{tag}] FAILED arms={failed}')
        return 1
    log(f'official[{tag}] ALL ARMS OK')
    return 0


def run_mechanism(arm):
    """One arm, 72 episodes: instrumented replay + digest cross-check."""
    seeds = SEEDS_FULL
    PER_ARM.mkdir(parents=True, exist_ok=True)
    official_path = PER_ARM / (arm + '.json')
    if not official_path.exists():
        log(f'mechanism arm={arm} MISSING official file {official_path}')
        return 1
    official = { (r['seed'], r['variant']): r
                 for r in json.loads(official_path.read_text(encoding='utf-8'))['episodes'] }
    command = [sys.executable, ARMS[arm]['policy'], '--baseline', 'greedy']
    rows, digest_mismatch, invalid = [], [], []
    started = time.time()
    for variant in VARIANTS:
        for seed in seeds:
            try:
                result = episode(generate(seed, 200, 'evaluation', variant),
                                 command, simulator_class=InstrumentedSim)
            except (ValueError, TypeError, KeyError, OSError) as error:
                result = {'valid': False, 'error': str(error)}
            result.update(seed=seed, variant=variant)
            off = official.get((seed, variant))
            if result.get('valid') and off and off.get('valid'):
                if result['action_sha256'] != off['action_sha256']:
                    digest_mismatch.append([seed, variant])
            if not result.get('valid'):
                invalid.append([seed, variant, result.get('error')])
                rows.append(result)
                continue
            logrec = InstrumentedSim.last_instance.log
            rows.append({'seed': seed, 'variant': variant,
                         'valid': True,
                         'msmi_per_100_arrived_members':
                             result['msmi_per_100_arrived_members'],
                         'ask_cost': result['ask_cost'],
                         'action_sha256': result['action_sha256'],
                         'mechanism': episode_mechanism(logrec, arm)})
    took = time.time() - started
    out = PER_ARM / (arm + '_mechanism.json')
    payload = {'arm': arm, 'episodes': rows,
               'digest_mismatch': digest_mismatch,
               'invalid': invalid, 'duration_seconds': took}
    out.write_text(json.dumps(payload, indent=2, allow_nan=False) + '\n',
                   encoding='utf-8')
    log(f'mechanism arm={arm} episodes={len(rows)} invalid={len(invalid)} '
        f'digest_mismatch={len(digest_mismatch)} duration={took:.1f}s out={out.name}')
    if invalid or digest_mismatch:
        return 1
    return 0


def run_mechanism_all():
    procs = {}
    for arm in ARMS:
        cmd = [sys.executable, str(Path(__file__).resolve()),
               '--phase', 'mechanism', '--arm', arm]
        log(f'mechanism parent spawning arm={arm}')
        procs[arm] = subprocess.Popen(cmd, cwd=str(ROOT),
                                      stdout=subprocess.PIPE,
                                      stderr=subprocess.STDOUT, text=True)
    failed = []
    for arm, proc in procs.items():
        out, _ = proc.communicate()
        for ln in (out or '').strip().splitlines()[-4:]:
            log(f'  mech| {ln}')
        if proc.returncode != 0:
            failed.append(arm)
    if failed:
        log(f'mechanism FAILED arms={failed}')
        return 1
    log('mechanism ALL ARMS OK')
    return 0


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--phase', choices=['smoke', 'official', 'mechanism'],
                   required=True)
    p.add_argument('--arm', choices=list(ARMS))
    p.add_argument('--stage2', action='store_true',
                   help='official phase: stage-2 seeds 131-142 -> s2_<arm>.json')
    args = p.parse_args()
    if args.phase == 'smoke':
        return run_official(smoke=True)
    if args.phase == 'official':
        return run_official(smoke=False, stage2=args.stage2)
    if args.arm:
        return run_mechanism(args.arm)
    return run_mechanism_all()


if __name__ == '__main__':
    raise SystemExit(main())
