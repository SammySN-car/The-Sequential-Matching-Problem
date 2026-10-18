"""Step 0: input validation against the sealed prior artifacts (V0-V2).

Read-only over prior studies. Stops if any reconciliation fails; prior
results are never silently changed (analysis_plan.md sec.2).
"""
import json, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gr_common as g  # noqa: E402

checks, info = [], {}


def chk(name, ok, detail=''):
    checks.append(dict(check=name, passed=int(bool(ok)), detail=detail))
    print('%-4s %-58s %s' % ('PASS' if ok else 'FAIL', name, detail), flush=True)


def main():
    t0 = time.time()
    g.log('gr0_validate start')

    # ---- V0 seals + plan hash --------------------------------------------
    for name, d, tol in (('decision-ceiling', g.CEIL_DIR, True),
                         ('fixed-cardinality', g.FC_DIR, False),
                         ('missed-oracle', g.MO_DIR, False),
                         ('stagewise-signal', g.SS_DIR, True)):
        stale = g.seal_stale(d, tolerate_run_log=tol)
        chk('%s seal current' % name, not stale, 'stale=%s' % (stale[:3] or 'none'))
    sha = g.sha256(g.OUT / 'analysis_plan.md')
    frozen = (g.OUT / 'analysis_plan.sha256').read_text(encoding='utf-8').split()[0]
    chk('analysis_plan hash frozen', sha == frozen, sha[:16])

    # ---- V1 input alignment ----------------------------------------------
    states = g.load_day_edges()
    diag = g.load_diag()
    labels = g.load_labels()
    oof = g.load_oof_f2()
    rec = g.load_recomputed_sets()
    chk('7,560 states', len(states) == 7560, str(len(states)))
    chk('selection_diagnostics covers same states',
        {s['key'] for s in states} == set(diag), '%d diag' % len(diag))

    sum_k = sum(len(s['greedy']) for s in states)
    sorted_ok = all(all(e[0] < e[1] for e in s['edges']) for s in states)
    n_edges = sum(len(s['edges']) for s in states)
    missing_lab = sum(1 for s in states for e in s['edges']
                      if e not in labels[s['key']])
    missing_oof = sum(1 for s in states for e in s['edges']
                      if (s['key'][0], s['key'][1], s['key'][2],
                          e[0], e[1]) not in oof)
    kt_ok = all(len(s['greedy']) == diag[s['key']]['k_t'] for s in states)
    greedy_eq = sum(1 for s in states
                    if rec[s['key']]['GREEDY'] == frozenset(s['greedy']))
    arm_card = all(len(rec[s['key']][a]) == diag[s['key']]['k_t']
                   for s in states
                   for a in ('F1-SCORE', 'F2-SOFT', 'F5-ORACLE'))
    sum_p = sum(sum(labels[s['key']][e] for e in s['edges']) for s in states)
    chk('sum k_t = 8,433', sum_k == 8433, str(sum_k))
    chk('sum feasible edges = 15,304', n_edges == 15304, str(n_edges))
    chk('sum p_t = 173', sum_p == 173, str(sum_p))
    chk('edge keys sorted ascending (orientation)', sorted_ok, '')
    chk('every edge has a counterfactual label', missing_lab == 0,
        'missing=%d' % missing_lab)
    chk('every edge has a frozen OOF F2 score', missing_oof == 0,
        'missing=%d' % missing_oof)
    chk('k_t = len(recorded greedy pairs) on every state', kt_ok, '')
    chk('recomputed GREEDY set == recorded action set',
        greedy_eq == 7560, '%d/7560' % greedy_eq)
    chk('frozen arm cardinality == k_t on every state', arm_card, '')

    # ---- V2 frozen arm totals + headroom split ---------------------------
    def total(arm):
        return sum(sum(labels[s['key']][e] for e in rec[s['key']][arm])
                   for s in states)
    tG, tF1, tF2, tF5 = total('GREEDY'), total('F1-SCORE'), \
        total('F2-SOFT'), total('F5-ORACLE')
    chk('frozen totals GREEDY=90 F1=81 F2=94 F5=161',
        (tG, tF1, tF2, tF5) == (90, 81, 94, 161),
        'G=%d F1=%d F2=%d F5=%d' % (tG, tF1, tF2, tF5))
    info['frozen_totals'] = dict(GREEDY=tG, F1=tF1, F2=tF2, F5=tF5)
    n_hr = sum(1 for k in diag if diag[k]['headroom'])
    chk('82 headroom / 7,478 zero-headroom states',
        (n_hr, len(diag) - n_hr) == (82, 7478), '%d/%d' % (n_hr, len(diag) - n_hr))
    info['headroom_states'] = n_hr
    info['n_edges'] = n_edges
    info['sum_k_t'] = sum_k
    info['sum_p_t'] = sum_p

    n_pass = sum(c['passed'] for c in checks)
    result = dict(passed=n_pass == len(checks), n_checks=len(checks),
                  checks=checks,
                  failures=[c for c in checks if not c['passed']], info=info)
    (g.OUT / 'validation.json').write_text(
        json.dumps(result, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    g.log('gr0_validate %s (%d/%d checks, %.1fs)'
          % ('PASSED' if result['passed'] else 'FAILED',
             n_pass, len(checks), time.time() - t0))
    if not result['passed']:
        raise SystemExit('INPUT VALIDATION FAILED - selector computation withheld')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
