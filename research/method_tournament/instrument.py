"""Instrument pass (design.md section 5): secondary diagnostics that official
episode rows do not carry - zero-selection days, mutual per introduction, MSMI
per introduction - computed by re-running a bounded official sample and
digest-verifying every re-run against the sealed phase rows. Two passes:

  --phase screening   seed 143 x 6 variants x (retained + control), <= 54
                      episodes; run after the retention gate and before the
                      freeze (Task 12); appends to screening_report.md.
  --phase confirm2    seed 152 x 6 variants x (selected + control), <= 18
                      episodes; run after the final verdict (Task 15); appends
                      to final_report.md; records a skipped summary when
                      Phase 3 was skipped.

Diagnostic only: instrument output is NEVER a ranking or selection input.
"""
import argparse
import hashlib
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))
import evaluate  # noqa: E402
import run_tournament as rt  # noqa: E402
from kit import VERSION, Simulator, generate  # noqa: E402

PHASE_CFG = {
    'screening': {'seed': 143, 'rows': 'screening_rows.jsonl',
                  'results': 'screening_results.json', 'key': 'retained',
                  'report': 'screening_report.md',
                  'summary': 'instrument_screening.json',
                  'rows_out': 'instrument_rows_screening.jsonl'},
    'confirm2': {'seed': 152, 'rows': 'confirm2_rows.jsonl',
                 'results': 'confirmation_results.json', 'key': 'selected',
                 'report': 'final_report.md',
                 'summary': 'instrument_summary.json',
                 'rows_out': 'instrument_rows.jsonl'},
}


def arms_for(results, key):
    """Arm list for an analysis-results file; [] when the key is absent/empty."""
    return list(results.get(key) or [])


def instrument_episode(world, command, timeout=10):
    """evaluate.episode replica that also counts zero-selection days.

    Byte-identical action_sha256 digests for the same world and command are
    required: design.md section 5 says the instrument pass is digest-verified
    against official rows.
    """
    sim = Simulator(world)
    memory = None
    digest = hashlib.sha256()
    zero_selection_days = 0
    for _ in range(60):
        made_a_match = False
        for phase in ('ask', 'match'):
            request = {'schema_version': VERSION, 'phase': phase,
                       'state': sim.observe(), 'memory': memory}
            response, _elapsed = evaluate.invoke(command, request, timeout)
            memory = response['memory']
            action = response['asks' if phase == 'ask' else 'pairs']
            digest.update(json.dumps([phase, sim.day, action],
                                     sort_keys=True).encode())
            if phase == 'ask':
                sim.resolve_asks(action)
            else:
                if action:
                    made_a_match = True
                sim.advance(action)
        if not made_a_match:
            zero_selection_days += 1
    arrived = {m['member_id']: m['arrived_day']
               for m in sim.observe()['members'] if m['arrived_day'] <= 59}
    for _ in range(40):
        sim.advance([])
    result = sim.metrics()
    first = {}
    for intro in sim.introductions:
        for member in (intro['user_a'], intro['user_b']):
            first.setdefault(member, intro['assigned_day'])
    assignments = max(1, result['assignments'])
    result.update(
        valid=True,
        zero_selection_days=zero_selection_days,
        action_sha256=digest.hexdigest(),
        arrived_members=len(arrived),
        served_members=len(first),
        coverage=len(first) / max(1, len(arrived)),
        intros_per_100=100.0 * result['assignments'] / max(1, len(arrived)),
        mutual_per_introduction=result['mutual_acceptances'] / assignments,
        msmi_per_introduction=result['mutual_second_meeting_intention'] / assignments,
    )
    return result


def _append_report(report, summary, methods, per_arm, phase):
    with report.open('a', encoding='utf-8') as fh:
        fh.write('\n## Instrument pass - %s (diagnostic only)\n\n' % phase)
        if summary.get('skipped'):
            fh.write('- Skipped: %s\n' % summary['reason'])
            return
        fh.write('- Sample: seed %d x 6 variants; digests verified against '
                 'official %s rows: %d/%d match.\n'
                 % (summary['sample_seed'], phase, summary['digest_matches'],
                    summary['episodes']))
        fh.write('- Never a ranking input (design section 5).\n\n')
        fh.write('| arm | zero-selection days | intros/100 | mutual/intro | '
                 'MSMI/intro | coverage | ask cost |\n')
        fh.write('|---|---|---|---|---|---|---|\n')
        for method in methods:
            s = per_arm[method]
            fh.write('| %s | %s | %s | %s | %s | %s | %s |\n' % (
                method, s['zero_selection_days_mean'], s['intros_per_100_mean'],
                s['mutual_per_introduction_mean'],
                s['msmi_per_introduction_mean'], s['coverage_mean'],
                s['ask_cost_mean']))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', required=True, choices=sorted(PHASE_CFG))
    args = parser.parse_args(argv)
    cfg = PHASE_CFG[args.phase]
    checks = HERE / 'deterministic_checks'
    checks.mkdir(exist_ok=True)
    res_path = HERE / cfg['results']
    results = (json.loads(res_path.read_text(encoding='utf-8'))
               if res_path.exists() else {})
    arms = arms_for(results, cfg['key'])
    report = HERE / cfg['report']
    if args.phase == 'confirm2' and not arms:
        summary = {'skipped': True, 'episodes': 0,
                   'reason': 'no Phase-3 arms '
                             '(confirmation_results.selected empty)'}
        (checks / cfg['summary']).write_text(
            json.dumps(summary, indent=2, sort_keys=True) + '\n',
            encoding='utf-8')
        if report.exists():
            _append_report(report, summary, [], {}, args.phase)
        print(json.dumps(summary, indent=2))
        return 0
    official = {}
    for r in rt.dedupe(rt.load_rows(HERE / 'per_phase' / cfg['rows'])):
        official[(r['method'], r['seed'], r['variant'])] = r
    methods = list(arms) + [rt.CONTROL]
    rows = []
    for method in methods:
        cmd = (rt.control_command() if method == rt.CONTROL
               else rt.method_command(method))
        for variant in rt.VARIANTS:
            row = instrument_episode(
                generate(cfg['seed'], 200, 'evaluation', variant), cmd)
            row.update(method=method, seed=cfg['seed'], variant=variant)
            off = official.get((method, cfg['seed'], variant))
            row['official_action_sha256'] = (off['action_sha256']
                                             if off else None)
            row['digest_match'] = bool(off and off.get('valid')) and (
                row['action_sha256'] == off['action_sha256'])
            rows.append(row)
    with (checks / cfg['rows_out']).open('w', encoding='utf-8') as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True, allow_nan=False) + '\n')
    per_arm = {}
    for method in methods:
        mrows = [r for r in rows if r['method'] == method]
        n = max(1, len(mrows))
        per_arm[method] = {
            'episodes': len(mrows),
            'zero_selection_days_mean': round(
                sum(r['zero_selection_days'] for r in mrows) / n, 2),
            'intros_per_100_mean': round(
                sum(r['intros_per_100'] for r in mrows) / n, 3),
            'mutual_per_introduction_mean': round(
                sum(r['mutual_per_introduction'] for r in mrows) / n, 4),
            'msmi_per_introduction_mean': round(
                sum(r['msmi_per_introduction'] for r in mrows) / n, 4),
            'coverage_mean': round(
                sum(r['coverage'] for r in mrows) / n, 4),
            'ask_cost_mean': round(
                sum(r['ask_cost'] for r in mrows) / n, 1),
        }
    summary = {'skipped': False, 'phase': args.phase,
               'sample_seed': cfg['seed'],
               'variants': list(rt.VARIANTS), 'episodes': len(rows),
               'digest_matches': sum(1 for r in rows if r['digest_match']),
               'all_digest_match': all(r['digest_match'] for r in rows),
               'per_arm': per_arm}
    (checks / cfg['summary']).write_text(
        json.dumps(summary, indent=2, sort_keys=True) + '\n',
        encoding='utf-8')
    if report.exists():
        _append_report(report, summary, methods, per_arm, args.phase)
    print(json.dumps({'all_digest_match': summary['all_digest_match'],
                      'episodes': len(rows)}, indent=2))
    return 0 if summary['all_digest_match'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
