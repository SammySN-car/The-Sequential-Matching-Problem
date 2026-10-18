"""Crash-safe paired experiment runner (frozen protocol sections 5, 7, 9).

One evaluate.py invocation per (arm, seed, variant) key - the official evaluator is never
modified; the instrumented arms are selected via its --policy flag. Mode and ask logging
reach the candidate through inherited environment variables (HCC_MODE / HCC_LOG). Progress
is an append-only JSONL per phase; resume skips completed keys; the first invalid episode
halts the phase (protocol section 10) unless --keep-going is passed.
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]

# Mirror of evaluate.py:16 VARIANTS (verified by grep 2026-10-16). A wrong name would make
# evaluate.py raise -> invalid episode -> gates fail, so this is self-validating.
VARIANTS = ('development', 'sparse', 'cold_start', 'delayed', 'shift', 'drift')

CANDIDATE = 'research/hard_constraint_clarification/candidate_policy.py'
ARMS = ('greedy_official', 'greedy', 'unlock')
PILOT_SEEDS = (119001, 119002, 119003)
CONF_SEEDS = tuple(range(120001, 120101))


def phase_keys(phase):
    """Ordered (arm, seed, variant) work items for a phase (protocol section 7)."""
    if phase == 'pilot':
        return [(a, s, v) for s in PILOT_SEEDS for v in VARIANTS for a in ARMS]
    if phase == 'pilot_replay':
        return [('unlock', 119001, 'development'), ('greedy_official', 119003, 'sparse')]
    if phase in ('confirmatory', 'confirmatory_rerun'):
        keys = []
        for s in CONF_SEEDS:                      # interleaved: both arms before next seed
            for v in VARIANTS:
                keys.append(('greedy', s, v))
                keys.append(('unlock', s, v))
        keys += [('greedy_official', 120001, v) for v in VARIANTS]   # spot-check parity
        return keys
    raise KeyError('unknown phase %r' % phase)


def key_str(arm, seed, variant):
    return '%s__%s__%s' % (arm, seed, variant)


def progress_path(exp, phase):
    return Path(exp) / 'results' / ('progress_%s.jsonl' % phase)


def load_done(path):
    """key -> record for every well-formed progress line (last wins; garbage tolerated)."""
    done = {}
    path = Path(path)
    if not path.exists():
        return done
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if isinstance(rec, dict) and 'key' in rec:
            done[rec['key']] = rec
    return done


def build_cmd(arm, seed, variant, out_path):
    cmd = [sys.executable, 'evaluate.py']
    if arm != 'greedy_official':
        cmd += ['--policy', CANDIDATE]
    cmd += ['--baseline', 'greedy', '--seeds', str(seed),
            '--variants', variant, '--output', str(out_path)]
    return cmd


def build_env(arm, seed, variant, exp):
    env = dict(os.environ)
    if arm == 'greedy_official':
        return env
    env['HCC_MODE'] = 'greedy' if arm == 'greedy' else 'unlock'
    env['HCC_LOG'] = str((Path(exp) / 'logs' /
                          ('asklog__%s.jsonl' % key_str(arm, seed, variant))).resolve())
    return env


def record_from_output(arm, seed, variant, exit_code, elapsed, output):
    rows = (output or {}).get('episodes') or []
    row = rows[0] if rows else {'valid': False,
                                'error': 'no episodes in evaluate output'}
    return {'key': key_str(arm, seed, variant), 'phase': None, 'arm': arm, 'seed': seed,
            'variant': variant, 'exit_code': exit_code, 'elapsed_s': elapsed,
            'valid': bool(row.get('valid')), 'row': row}


def execute_key(arm, seed, variant, phase, exp):
    exp = Path(exp)
    out_path = exp / 'tmp' / ('%s.json' % key_str(arm, seed, variant))
    log_path = exp / 'logs' / ('asklog__%s.jsonl' % key_str(arm, seed, variant))
    for stale in (out_path, log_path):
        if stale.exists():
            stale.unlink()
    env = build_env(arm, seed, variant, exp)
    cmd = build_cmd(arm, seed, variant, out_path)
    started = time.time()
    proc = subprocess.run(cmd, cwd=str(REPO_ROOT), env=env,
                          capture_output=True, text=True, timeout=900)
    elapsed = time.time() - started
    try:
        output = json.loads(out_path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as err:
        output = {'rows': [{'valid': False, 'error':
                            'unreadable evaluate output (%s); stderr tail: %s'
                            % (err, (proc.stderr or '')[-400:])}]}
    rec = record_from_output(arm, seed, variant, proc.returncode, elapsed, output)
    rec['stderr_tail'] = (proc.stderr or '')[-400:]
    return rec


def run_phase(phase, exp=None, resume=True, stop_on_invalid=True, limit=None,
              execute=None, out=print):
    exp = Path(exp) if exp else HERE
    keys = phase_keys(phase)
    if limit is not None:
        keys = keys[:limit]
    done = load_done(progress_path(exp, phase)) if resume else {}
    if execute is None:
        execute = lambda k, ph, ex: execute_key(k[0], k[1], k[2], ph, ex)
    summary = {'phase': phase, 'planned': len(keys), 'executed': 0, 'skipped': 0,
               'invalid': 0, 'stopped': False}
    for k in keys:
        ks = key_str(*k)
        if ks in done:
            summary['skipped'] += 1
            continue
        rec = execute(k, phase, exp)
        rec['phase'] = phase
        rec['key'] = ks
        with open(progress_path(exp, phase), 'a', encoding='utf-8') as fh:
            fh.write(json.dumps(rec, sort_keys=True) + '\n')
        summary['executed'] += 1
        if not rec['valid']:
            summary['invalid'] += 1
            out('INVALID %s exit=%s error=%s'
                % (ks, rec['exit_code'], rec['row'].get('error', '')))
            if stop_on_invalid:
                summary['stopped'] = True
                break
        else:
            out('ok %s %.1fs' % (ks, rec['elapsed_s']))
    return summary


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--phase', required=True,
                   choices=('pilot', 'pilot_replay', 'confirmatory', 'confirmatory_rerun'))
    p.add_argument('--limit', type=int, default=None)
    p.add_argument('--no-resume', action='store_true')
    p.add_argument('--keep-going', action='store_true',
                   help='continue past an invalid episode (protocol default: STOP)')
    args = p.parse_args(argv)
    summ = run_phase(args.phase, resume=not args.no_resume,
                     stop_on_invalid=not args.keep_going, limit=args.limit)
    print(json.dumps(summ, sort_keys=True))
    return 3 if summ['stopped'] else 0


if __name__ == '__main__':
    raise SystemExit(main())