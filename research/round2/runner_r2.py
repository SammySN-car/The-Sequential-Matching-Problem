"""Round 2 evaluation runner.

- episode_instrumented: byte-faithful copy of evaluate.episode (official loop)
  that ALSO returns final policy memory (gate telemetry + calibration bands).
  Validity: EpisodeParityTests asserts identical action_sha256 vs evaluate.episode.
- run_grid: official evaluate.episode for all arms; JSONL rows with resume support.
  Worlds: kit.generate(seed, 200, 'evaluation', variant); same worlds across arms.

Usage:
  python research/round2/runner_r2.py --phase fixture      # seeds 90250-90252, 1 arm
  python research/round2/runner_r2.py --phase eval         # seeds 301-312, all arms
  python research/round2/runner_r2.py --phase diagnostics  # instrumented, gated+ungated
"""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
R2 = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(R2))

import kit          # noqa: E402  (frozen)
import evaluate     # noqa: E402  (frozen)

VARIANTS = evaluate.VARIANTS
LAUNCHER = str(R2 / 'policies' / 'mw_alloc.py')

ARMS = {
    'greedy':   [sys.executable, str(ROOT / 'policy.py'), '--baseline', 'greedy'],
    'no_asks':  [sys.executable, str(ROOT / 'policy.py'), '--baseline', 'no_asks'],
    'random':   [sys.executable, str(ROOT / 'policy.py'), '--baseline', 'random'],
    'ungated':  [sys.executable, LAUNCHER, '--arm', 'ungated'],
    'gated':    [sys.executable, LAUNCHER, '--arm', 'gated'],
}


def episode_instrumented(world, command, timeout=10):
    """Official evaluate.episode semantics + final memory + last-match telemetry."""
    sim = kit.Simulator(world)
    memory = None
    inference_seconds = 0
    digest = hashlib.sha256()
    telemetry = {}
    for _ in range(60):
        for phase in ('ask', 'match'):
            request = {'schema_version': kit.VERSION, 'phase': phase,
                       'state': sim.observe(), 'memory': memory}
            response, elapsed = evaluate.invoke(command, request, timeout)
            inference_seconds += elapsed
            memory = response['memory']
            action = response['asks' if phase == 'ask' else 'pairs']
            digest.update(json.dumps([phase, sim.day, action], sort_keys=True).encode())
            if phase == 'ask':
                sim.resolve_asks(action)
            else:
                sim.advance(action)
                if isinstance(memory, dict) and 'solver_tried' in memory:
                    telemetry = {k: memory.get(k) for k in
                                 ('solver_tried', 'solver_exact', 'gate_adopted',
                                  'reject_g1', 'reject_g2', 'reject_other',
                                  'score_gain_sum', 'card_delta_sum', 'days',
                                  'zero_days', 'pairs_total')}
    arrived = {m['member_id']: m['arrived_day'] for m in sim.observe()['members']
               if m['arrived_day'] <= 59}
    for _ in range(40):
        sim.advance([])
    result = sim.metrics()
    first = {}
    for intro in sim.introductions:
        for member in (intro['user_a'], intro['user_b']):
            first.setdefault(member, intro['assigned_day'])
    waits = sorted(first[i] - arrived[i] for i in first)
    result.update(valid=True, arrived_members=len(arrived),
                  msmi_per_100_arrived_members=100 * result['mutual_second_meeting_intention'] / max(1, len(arrived)),
                  served_members=len(first), unserved_members=len(arrived) - len(first),
                  coverage=len(first) / max(1, len(arrived)),
                  mutual_acceptances_per_100=100 * result['mutual_acceptances'] / max(1, len(arrived)),
                  first_introduction_wait_days=waits,
                  inference_seconds=inference_seconds, action_sha256=digest.hexdigest())
    return result, memory, telemetry


def row_key(phase, arm, seed, variant):
    return '%s|%s|%s|%s' % (phase, arm, seed, variant)


def load_done(path):
    done = set()
    if path.exists():
        for line in path.read_text(encoding='utf-8').splitlines():
            if line.strip():
                done.add(json.loads(line)['key'])
    return done


def run_grid(phase, arms, seeds, variants, out_path, instrumented=False):
    done = load_done(out_path)
    total = len(arms) * len(seeds) * len(variants)
    n_done = 0
    for arm in arms:
        command = ARMS[arm]
        for variant in variants:
            for seed in seeds:
                key = row_key(phase, arm, seed, variant)
                n_done += 1
                if key in done:
                    continue
                started = time.time()
                world = kit.generate(seed, 200, 'evaluation', variant)
                try:
                    if instrumented:
                        result, memory, telemetry = episode_instrumented(world, command)
                        row = dict(result)
                        row['telemetry'] = telemetry
                        row['final_memory'] = memory
                    else:
                        row = dict(evaluate.episode(world, command))
                    row['valid'] = bool(row.get('valid'))
                except (ValueError, TypeError, KeyError, OSError) as error:
                    row = {'valid': False, 'error': str(error)}
                row.update(key=key, phase=phase, arm=arm, seed=seed, variant=variant,
                           wall_seconds=round(time.time() - started, 3))
                with out_path.open('a', encoding='utf-8') as fh:
                    fh.write(json.dumps(row, allow_nan=False, sort_keys=True) + '\n')
                print(json.dumps({'key': key, 'valid': row['valid'],
                                  'msmi': row.get('mutual_second_meeting_intention'),
                                  'cov': row.get('coverage'),
                                  'done': '%d/%d' % (n_done, total)}), flush=True)
                if not row['valid']:
                    print('INVALID EPISODE - see design.md 5.6 stopping rule', flush=True)
                    return 2
    return 0


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--phase', choices=['fixture', 'eval', 'diagnostics'], required=True)
    p.add_argument('--arms', default=None, help='comma subset')
    args = p.parse_args(argv)
    results = R2 / 'results'
    results.mkdir(exist_ok=True)
    if args.phase == 'fixture':
        arms = ['gated']
        seeds, variants = [90250, 90251, 90252], list(VARIANTS)
        out = results / 'fixture_rows.jsonl'
    elif args.phase == 'eval':
        arms = ['greedy', 'ungated', 'gated', 'no_asks', 'random']
        seeds = list(range(301, 313))
        variants = list(VARIANTS)
        out = results / 'eval_rows.jsonl'
    else:  # diagnostics
        arms = ['gated', 'ungated']
        seeds = list(range(301, 313))
        variants = list(VARIANTS)
        out = results / 'diagnostic_rows.jsonl'
    if args.arms:
        arms = [a for a in args.arms.split(',') if a in ARMS]
    return run_grid(args.phase, arms, seeds, variants, out,
                    instrumented=(args.phase == 'diagnostics'))


if __name__ == '__main__':
    raise SystemExit(main())