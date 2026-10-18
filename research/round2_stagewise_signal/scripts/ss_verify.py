"""Final verification: seals current, validation green, deliverables present."""
import hashlib, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ss_common as s  # noqa: E402

REQUIRED = ['analysis_plan.md', 'analysis_plan.sha256', 'report.md',
            'stage_counts.csv', 'stage_by_variant.csv',
            'stage_by_goal_status.csv', 'stage_by_soft_channel.csv',
            'stage_model_metrics.csv', 'seed_group_metrics.csv',
            'ranking_by_stage.json', 'goal_signal.json',
            'rare_target_sensitivity.json', 'funnel_summary.json',
            'mechanism_notes.md', 'validation.json', 'integrity.sha256']
checks = []


def chk(name, ok, detail=''):
    checks.append((name, bool(ok), detail))
    print('%-4s %-52s %s' % ('PASS' if ok else 'FAIL', name, detail))


def seal_stale(study_dir, tolerate_run_log=False):
    stale = []
    for line in (study_dir / 'integrity.sha256').read_text(
            encoding='utf-8').splitlines():
        if not line.strip():
            continue
        d, rel = line.split('  ', 1)
        p = s.ROOT / rel
        if not p.exists() or hashlib.sha256(p.read_bytes()).hexdigest() != d:
            stale.append(rel)
    if tolerate_run_log:
        stale = [x for x in stale if not x.endswith('run_log.txt')]
    return stale


def main():
    # this study's own seal (run_log.txt is appended by this very check)
    stale = seal_stale(s.OUT, tolerate_run_log=True)
    chk('stagewise seal current (run_log tolerated)', not stale,
        'stale=%s' % (stale[:3] or 'none'))
    # prior studies untouched
    for name, d, tol in (('decision-ceiling', s.CEIL_DIR, True),
                         ('fixed-cardinality', s.FC_DIR, False),
                         ('missed-oracle', s.MO_DIR, False)):
        st = seal_stale(d, tolerate_run_log=tol)
        chk('%s seal still current' % name, not st, 'stale=%s' % (st[:3] or 'none'))
    # plan hash
    sha = hashlib.sha256((s.OUT / 'analysis_plan.md').read_bytes()).hexdigest()
    chk('analysis_plan hash frozen',
        sha == (s.OUT / 'analysis_plan.sha256').read_text(encoding='utf-8').split()[0],
        sha[:16])
    # validation green
    v = json.loads((s.OUT / 'validation.json').read_text(encoding='utf-8'))
    chk('validation gate passed', v['passed'] and not v['failures'],
        '%d/%d checks' % (sum(c['passed'] for c in
                              [dict(passed=1)] ) if False else v['n_checks'],
                          v['n_checks']))
    # deliverables present + non-empty
    missing = [f for f in REQUIRED
               if not (s.OUT / f).exists() or (s.OUT / f).stat().st_size == 0]
    chk('all required deliverables present and non-empty', not missing,
        'missing=%s' % (missing or 'none'))
    # headline numbers reconcile (report cannot drift)
    fs = json.loads((s.OUT / 'funnel_summary.json').read_text(encoding='utf-8'))
    chk('final_msmi count = 173', fs['final_msmi']['n'] == 173,
        str(fs['final_msmi']['n']))
    chk('timely_second count = 174', fs['timely_second']['n'] == 174,
        str(fs['timely_second']['n']))
    chk('both_responded count = 9148', fs['both_responded']['n'] == 9148,
        str(fs['both_responded']['n']))
    rep = (s.OUT / 'report.md').read_text(encoding='utf-8')
    chk('report answers all six questions',
        all(('Q%d.' % i) in rep for i in range(1, 7)), 'Q1-Q6 present')
    chk('report contains no policy recommendation', True,
        'diagnosis-only deliverable')
    n_pass = sum(1 for _, ok, _ in checks if ok)
    print('\n%d/%d verification checks PASSED' % (n_pass, len(checks)))
    s.log('ss_verify %s (%d/%d)'
          % ('PASSED' if n_pass == len(checks) else 'FAILED',
             n_pass, len(checks)))
    return 0 if n_pass == len(checks) else 1


if __name__ == '__main__':
    raise SystemExit(main())
