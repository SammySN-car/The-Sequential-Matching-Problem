"""Final verification gate for round2_goal_rule.

Re-derives headline numbers from per_state_results.csv (V5), re-checks
selector cardinality from selector_sets.jsonl (V4 recheck), the frozen
reconciliation targets, this study's integrity manifest, the plan hash,
the seals of all four prior studies, and deliverable presence.
Run AFTER gr_seal.py. Exits non-zero on any failure.
"""
import csv, json, sys, time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gr_common as g  # noqa: E402

EXPECTED = {'G0': 90, 'G1f': 81, 'G1m': 88, 'G2': 92, 'G3': 92,
            'G4': 94, 'G5': 161}
DELIVERABLES = ['analysis_plan.md', 'analysis_plan.sha256', 'report.md',
                'selector_summary.csv', 'per_state_results.csv',
                'per_seed_results.csv', 'per_variant_results.csv',
                'run_log.txt', 'integrity.sha256', 'validation.json',
                'evaluation.json', 'scripts/gr_common.py',
                'scripts/gr0_validate.py', 'scripts/gr1_selectors.py',
                'scripts/gr2_evaluate.py', 'scripts/gr3_goal.py',
                'scripts/gr4_report.py', 'scripts/gr_seal.py',
                'scripts/gr_verify.py']

checks = []


def chk(name, ok, detail=''):
    checks.append(dict(check=name, passed=int(bool(ok)), detail=detail))
    print('%-4s %-64s %s' % ('PASS' if ok else 'FAIL', name, detail), flush=True)


def main():
    t0 = time.time()
    g.log('gr_verify start')
    bad = []

    # ---- plan hash --------------------------------------------------------
    sha = g.sha256(g.OUT / 'analysis_plan.md')
    frozen = (g.OUT / 'analysis_plan.sha256').read_text(encoding='utf-8').split()[0]
    chk('analysis_plan hash matches frozen sha256', sha == frozen, sha[:16])

    # ---- prior seals ------------------------------------------------------
    for name, d, tol in (('decision-ceiling', g.CEIL_DIR, True),
                         ('fixed-cardinality', g.FC_DIR, False),
                         ('missed-oracle', g.MO_DIR, False),
                         ('stagewise-signal', g.SS_DIR, True)):
        stale = g.seal_stale(d, tolerate_run_log=tol)
        chk('%s seal still current' % name, not stale, 'stale=%s' % (stale[:3] or 'none'))

    # ---- validation gate --------------------------------------------------
    v = json.loads((g.OUT / 'validation.json').read_text(encoding='utf-8'))
    chk('validation.json all checks passed', v['passed'] and not v['failures'],
        '%d/%d' % (v['n_checks'] - len(v['failures']), v['n_checks']))

    # ---- V5: re-derive headlines from per_state_results.csv ---------------
    rows = list(csv.DictReader(open(g.OUT / 'per_state_results.csv',
                                    encoding='utf-8')))
    chk('per_state_results has 7,560 rows', len(rows) == 7560, str(len(rows)))
    tot = {a: sum(int(r['%s_positives' % a]) for r in rows)
           for a in g.ARMS}
    chk('re-derived totals == expected (90/81/88/92/92/94/161)',
        tot == EXPECTED, str(tot))
    ksum = sum(int(r['k_t']) for r in rows)
    chk('sum k_t == 8,433 (identical volume for every arm)', ksum == 8433,
        str(ksum))
    ev = json.loads((g.OUT / 'evaluation.json').read_text(encoding='utf-8'))
    chk('evaluation.json totals == re-derived', ev['totals'] == tot, '')
    summ = {r['arm']: r for r in csv.DictReader(
        open(g.OUT / 'selector_summary.csv', encoding='utf-8'))}
    chk('selector_summary totals == re-derived',
        all(int(summ[a]['total_positives']) == tot[a] for a in g.ARMS), '')
    itw_ok, itw_bad = 0, []
    for a in g.ARMS:
        if a == 'G0':
            continue
        i, ti, w = (int(summ[a]['n_improved_vs_G0']),
                    int(summ[a]['n_tied_vs_G0']),
                    int(summ[a]['n_worsened_vs_G0']))
        if i + ti + w == 7560 and i + w <= int(summ[a]['n_states_changed_vs_G0']):
            itw_ok += 1
        else:
            itw_bad.append(a)
    chk('improved+tied+worsened == 7,560 and <= changed (per arm)',
        itw_ok == 6 and not itw_bad, 'bad=%s' % itw_bad)
    ps = list(csv.DictReader(open(g.OUT / 'per_seed_results.csv',
                                  encoding='utf-8')))
    chk('21 seed rows; per-seed sums == totals',
        len(ps) == 21 and all(
            sum(int(r['%s_positives' % a]) for r in ps) == tot[a]
            for a in g.ARMS), '%d rows' % len(ps))
    pv = list(csv.DictReader(open(g.OUT / 'per_variant_results.csv',
                                  encoding='utf-8')))
    chk('6 variant rows; per-variant sums == totals',
        len(pv) == 6 and all(
            sum(int(r['%s_positives' % a]) for r in pv) == tot[a]
            for a in g.ARMS), '%d rows' % len(pv))

    # ---- V4 recheck: cardinality straight from selector_sets --------------
    srows = g.read_jsonl(g.OUT / 'selector_sets.jsonl')
    bad_card = sum(1 for r in srows
                   if any(len(r['sets'][a]) != r['k_t'] or
                          len({tuple(e) for e in r['sets'][a]}) != r['k_t']
                          for a in g.ARMS))
    chk('V4 recheck: every arm exactly k_t unique pairs on every state',
        len(srows) == 7560 and bad_card == 0,
        'states=%d bad=%d' % (len(srows), bad_card))

    # ---- deliverables -----------------------------------------------------
    missing = [f for f in DELIVERABLES if not (g.OUT / f).exists()]
    chk('all deliverables present', not missing, 'missing=%s' % missing)

    # ---- this study's integrity manifest (run_log tolerated) --------------
    stale = g.seal_stale(g.OUT, tolerate_run_log=True)
    chk('integrity.sha256 current (run_log append tolerated)', not stale,
        'stale=%s' % (stale[:3] or 'none'))

    n_pass = sum(c['passed'] for c in checks)
    ok = n_pass == len(checks)
    g.log('gr_verify %s (%d/%d checks, %.1fs)'
          % ('PASSED' if ok else 'FAILED', n_pass, len(checks),
             time.time() - t0))
    if not ok:
        for c in checks:
            if not c['passed']:
                print('FAILED: %s %s' % (c['check'], c['detail']))
        raise SystemExit(1)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
