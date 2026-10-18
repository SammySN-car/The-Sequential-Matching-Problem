"""Pilot gate evaluation - frozen protocol section 8 (G1-G5, G7). Pure functions + CLI.

G8 (unit suite) is run separately via unittest and recorded in PROGRESS.md.
"""
import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]

CONFIRM_COUNTS = {'greedy': 600, 'unlock': 600, 'greedy_official': 6}
METRIC_FIELDS = ('msmi_per_100_arrived_members', 'ask_cost', 'assignments',
                 'mutual_acceptances', 'dates', 'mutual_second_meeting_intention')


def gate_g1(records):
    """Instrumented greedy action digests == official greedy digests (shared keys)."""
    off, ins = {}, {}
    for r in records:
        if r['arm'] == 'greedy_official':
            off[(r['seed'], r['variant'])] = r
        elif r['arm'] == 'greedy':
            ins[(r['seed'], r['variant'])] = r
    bad = set(set(off) ^ set(ins))               # missing counterpart on either side
    for k in set(off) & set(ins):
        if off[k]['row'].get('action_sha256') != ins[k]['row'].get('action_sha256'):
            bad.add(k)
    return (not bad and bool(set(off) & set(ins))), sorted(bad)


def gate_g2(pilot_records, replay_records):
    """Determinism: replayed keys reproduce digest + headline metrics."""
    base = {r['key']: r for r in pilot_records}
    bad = []
    if not replay_records:
        return False, ['no replay records']
    for r in replay_records:
        b = base.get(r['key'])
        if b is None:
            bad.append('%s: not in pilot' % r['key'])
            continue
        if r['row'].get('action_sha256') != b['row'].get('action_sha256'):
            bad.append('%s: digest differs' % r['key'])
            continue
        for f in METRIC_FIELDS:
            if r['row'].get(f) != b['row'].get(f):
                bad.append('%s: %s differs' % (r['key'], f))
                break
    return (not bad), bad


def gate_g3(records):
    bad = [r['key'] for r in records
           if not r.get('valid') or r.get('exit_code') != 0]
    return (not bad and bool(records)), bad


def gate_g4(log_groups):
    """Every logged ask day obeys budget, count and field rules (protocol G4)."""
    bad = []
    for gi, lines in enumerate(log_groups):
        for ln in lines:
            b, n, e = ln.get('budget_remaining'), ln.get('n_asks'), ln.get('n_eligible')
            day = ln.get('day')
            if not isinstance(b, int) or b < 0 or b > 12:
                bad.append((gi, 'budget_range', day))
                continue
            if not isinstance(n, int) or ln.get('spent') != 3 * n or 3 * n > b:
                bad.append((gi, 'over_budget', day))
                continue
            if n != min(b // 3, e if isinstance(e, int) else n):
                bad.append((gi, 'count_mismatch', day))
                continue
            if any(a.get('field') != 'constraints' for a in ln.get('asks', [])):
                bad.append((gi, 'wrong_field', day))
    return (not bad), bad


def gate_g5(unlock_logs, greedy_logs):
    """Intervention active: day-0 ask lists diverge somewhere AND a positive pick exists."""
    def base(k):
        return tuple(k[1:]) if len(k) == 3 else tuple(k)
    u = {base(k): v for k, v in unlock_logs.items()}
    g = {base(k): v for k, v in greedy_logs.items()}
    shared = set(u) & set(g)
    if not shared:
        return False, 'no shared (unlock, greedy) log pairs'
    diverged, has_trace, missing = False, False, []
    for k in shared:
        u0 = next((l for l in u[k] if l.get('day') == 0), None)
        g0 = next((l for l in g[k] if l.get('day') == 0), None)
        if u0 is None or g0 is None:
            missing.append(k)
            continue
        if ([a['member_id'] for a in u0.get('asks', [])]
                != [a['member_id'] for a in g0.get('asks', [])]):
            diverged = True
        if any(l.get('trace') for l in u[k]):
            has_trace = True
    if missing:
        return False, 'missing day-0 logs: %s' % missing
    return (diverged and has_trace), 'day0_diverged=%s positive_trace=%s' % (
        diverged, has_trace)


def gate_g7(mean_times, now=None, cutoff='2026-10-17 18:00', cap_hours=18.0):
    """Projection fits the runtime budget and the pre-deadline cutoff."""
    hours = (sum(CONFIRM_COUNTS[a] * mean_times.get(a, 0.0) for a in CONFIRM_COUNTS)
             / 3600.0)
    fmt = '%Y-%m-%d %H:%M'
    if now is None:
        now = datetime.now().strftime(fmt)
    eta = datetime.strptime(now, fmt) + timedelta(hours=hours)
    ok = hours <= cap_hours and eta <= datetime.strptime(cutoff, fmt)
    return ok, {'projected_hours': round(hours, 2), 'eta': eta.strftime(fmt),
                'cutoff': cutoff, 'cap_hours': cap_hours}


def load_records(exp, phase):
    path = Path(exp) / 'results' / ('progress_%s.jsonl' % phase)
    recs = []
    if not path.exists():
        return recs
    for line in path.read_text(encoding='utf-8').splitlines():
        try:
            recs.append(json.loads(line))
        except ValueError:
            continue
    return recs


def load_logs(exp, arms, seed_filter=None):
    logs = {}
    log_dir = Path(exp) / 'logs'
    for path in sorted(log_dir.glob('asklog__*.jsonl')):
        parts = path.stem.split('__')            # asklog__arm__seed__variant
        if len(parts) != 4:
            continue
        _, arm, seed, variant = parts
        if arm not in arms:
            continue
        try:
            seed = int(seed)
        except ValueError:
            continue
        if seed_filter is not None and seed not in seed_filter:
            continue
        lines = []
        for line in path.read_text(encoding='utf-8').splitlines():
            try:
                lines.append(json.loads(line))
            except ValueError:
                continue
        logs[(arm, seed, variant)] = lines
    return logs


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--exp', default=str(HERE))
    args = p.parse_args(argv)
    exp = Path(args.exp)
    pilot = load_records(exp, 'pilot')
    replay = load_records(exp, 'pilot_replay')
    u_logs = load_logs(exp, ('unlock',))
    g_logs = load_logs(exp, ('greedy',))

    results = []
    ok, detail = gate_g1(pilot)
    results.append(('G1 parity official<->instrumented', ok, detail))
    ok, detail = gate_g2(pilot, replay)
    results.append(('G2 determinism replay', ok, detail))
    ok, detail = gate_g3(pilot)
    results.append(('G3 validity', ok, detail))
    ok, detail = gate_g4(list(u_logs.values()) + list(g_logs.values()))
    results.append(('G4 budget legality', ok, detail))
    ok, detail = gate_g5(u_logs, g_logs)
    results.append(('G5 intervention active', ok, detail))
    means = {}
    for arm in ('greedy', 'unlock', 'greedy_official'):
        arm_rows = [r for r in pilot if r['arm'] == arm and r.get('valid')]
        means[arm] = (sum(r['elapsed_s'] for r in arm_rows) / len(arm_rows)) if arm_rows else 999.0
    ok, detail = gate_g7(means)
    results.append(('G7 runtime projection', ok, detail))

    all_ok = True
    for name, ok, detail in results:
        print('%s %s :: %s' % ('PASS' if ok else 'FAIL', name, detail))
        all_ok = all_ok and ok
    print('MEANS %s' % json.dumps({k: round(v, 2) for k, v in means.items()}))
    print('OVERALL %s' % ('ALL GATES PASS' if all_ok else 'GATE FAILURE'))
    return 0 if all_ok else 1


if __name__ == '__main__':
    raise SystemExit(main())