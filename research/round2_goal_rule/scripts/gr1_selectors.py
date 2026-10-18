"""Step 1: compute the fixed-scoring selectors with the validated exact-k
solver; reuse validated G0/G5; reconcile against frozen arms (V3);
validate every output with check_matching (V4); verify the G1m maximizer
direction (V6). See analysis_plan.md Amendment 1 for the G1f/G1m split.

Writes selector_sets.jsonl (7,560 states x 7 arms) and appends V3/V4/V6 to
validation.json. Channel states come from the frozen s3_signal definitions
(cached to channel_states.json). Weights are computed WITHOUT consulting any
counterfactual outcome.
"""
import json, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gr_common as g  # noqa: E402

FROZEN_ARM = {'G1f': 'F1-SCORE', 'G4': 'F2-SOFT'}


def n_at_max(w):
    if not w:
        return 0
    mx = max(w)
    return sum(1 for x in w if abs(x - mx) < 1e-12)


def main():
    t0 = time.time()
    g.log('gr1_selectors start (7 arms, Amendment 1)')
    states = g.load_day_edges()
    rec = g.load_recomputed_sets()
    oof = g.load_oof_f2()
    chan = g.load_channel_states(g.OUT / 'channel_states.json')
    g.log('channel states loaded (%d edges)' % len(chan))

    rows, failures = [], []
    v3_mismatch = {a: 0 for a in FROZEN_ARM}
    g1m_diff_frozen = 0
    cnt = {'G0': 0, 'G1f': 0, 'G1m': 0}   # match-count sums (direction proof)

    for s in states:
        key, edges, sc, greedy, kt = (s['key'], s['edges'], s['neg_scores'],
                                      s['greedy'], len(s['greedy']))
        channels = [chan[(key[0], key[1], key[2], e[0], e[1])] for e in edges]
        weights = {
            'G1f': g.weight_g1f(sc),
            'G1m': g.weight_g1m(sc),
            'G2': g.weight_g2(channels),
            'G3': g.weight_g3(channels),
            'G4': [oof[(key[0], key[1], key[2], e[0], e[1])] for e in edges],
        }
        sel = {'G0': list(greedy),
               'G5': [tuple(e) for e in sorted(rec[key]['F5-ORACLE'])]}
        tie = {}
        for arm in g.SCORED_ARMS:
            w = weights[arm]
            sel[arm] = g.solve_arm(edges, w, kt, arm, key, failures)
            tie[arm] = dict(n_edges=len(edges),
                            n_distinct=len({round(x, 12) for x in w}),
                            n_at_max=n_at_max(w))
            if sel[arm] is None:
                continue
            if arm in FROZEN_ARM and frozenset(sel[arm]) != rec[key][FROZEN_ARM[arm]]:
                v3_mismatch[arm] += 1
            if arm == 'G1m' and frozenset(sel[arm]) != rec[key]['F1-SCORE']:
                g1m_diff_frozen += 1
        if any(sel[a] is None for a in g.ARMS):
            continue
        # V4: exact cardinality + no member repeated for the reused arms too
        for arm in ('G0', 'G5'):
            if len(sel[arm]) != kt or len(set(map(tuple, sel[arm]))) != kt:
                failures.append('%s %s cardinality/dup' % (arm, key))
        # V6 direction proof on match-count sums (day_edges score = count)
        idx = {e: i for i, e in enumerate(edges)}
        for arm in ('G0', 'G1f', 'G1m'):
            cnt[arm] += sum(sc[idx[e]] for e in sel[arm])
        rows.append(dict(
            seed=key[0], variant=key[1], day=key[2],
            n_edges=len(edges), k_t=kt,
            sets={a: [list(e) for e in sorted(sel[a])] for a in g.ARMS},
            tie={a: tie[a] for a in g.SCORED_ARMS}))

    if len(rows) != 7560 or failures:
        g.log('failures: %s' % failures[:5])
        raise SystemExit('selector computation failed (%d rows, %d fails)'
                         % (len(rows), len(failures)))

    g.write_jsonl(g.OUT / 'selector_sets.jsonl', rows)

    # ---- append V3/V4/V6 to validation.json -------------------------------
    vpath = g.OUT / 'validation.json'
    v = json.loads(vpath.read_text(encoding='utf-8'))
    new = []

    def chk(name, ok, detail=''):
        new.append(dict(check=name, passed=int(bool(ok)), detail=detail))
        print('%-4s %-58s %s' % ('PASS' if ok else 'FAIL', name, detail),
              flush=True)

    chk('V3 G1f reproduces frozen F1-SCORE set on every state',
        v3_mismatch['G1f'] == 0, 'mismatch=%d' % v3_mismatch['G1f'])
    chk('V3 G4 reproduces frozen F2-SOFT set on every state',
        v3_mismatch['G4'] == 0, 'mismatch=%d' % v3_mismatch['G4'])
    chk('V6 G1m match-count >= greedy (maximizer direction)',
        cnt['G1m'] >= cnt['G0'],
        'G1m=%d G0=%d G1f=%d' % (cnt['G1m'], cnt['G0'], cnt['G1f']))
    chk('V4 every arm has exactly k_t non-overlapping feasible pairs',
        not failures and len(rows) == 7560,
        'states=%d failures=%d' % (len(rows), len(failures)))
    v['checks'] += new
    v['n_checks'] = len(v['checks'])
    v['failures'] = [c for c in v['checks'] if not c['passed']]
    v['passed'] = not v['failures']
    v['info']['v3_mismatch'] = v3_mismatch
    v['info']['g1m_states_differing_from_frozen_F1'] = g1m_diff_frozen
    v['info']['match_count_sums'] = cnt
    vpath.write_text(json.dumps(v, indent=1, sort_keys=True) + '\n',
                     encoding='utf-8')
    g.log('gr1 done: G1m differs from frozen F1 on %d states; count sums %s'
          % (g1m_diff_frozen, cnt))
    g.log('gr1_selectors done (%.1fs, %d checks total)'
          % (time.time() - t0, v['n_checks']))
    if not v['passed']:
        raise SystemExit('V3/V4/V6 FAILED')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
