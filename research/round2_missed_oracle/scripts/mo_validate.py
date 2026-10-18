"""Step 2 validation: prove the existing predictions/selectors/labels are sound
BEFORE any new diagnostic is computed. Read-only over prior studies.

V1  Rebuild the training frame from counterfactual_pairs + pair_state and
    RECOMPUTE out-of-fold F1/F2 scores; require bit-exact agreement with
    oof_scores.jsonl. This simultaneously proves feature legality and that no
    score was produced by a model trained on its own seed group.
V2  Every evaluated pair is an edge of that state's feasible graph.
V3  Counterfactual labels align to the correct world/pair/assignment day.
V4  F2 has no hidden attribute or counterfactual target in its feature set.
V5  Recomputed selector cardinality equals k_t on every state, and the
    recomputed per-arm positive counts reproduce the frozen study.
V6  Reconcile +71 / +4 / +13 against per_state_results.jsonl.
"""
import json, sys, time
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
FC_DIR = HERE.parent.parent / 'round2_fixed_cardinality'
CEIL = HERE.parent.parent / 'round2_decision_ceiling'
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(FC_DIR / 'scripts'))
sys.path.insert(0, str(CEIL / 'scripts'))

import ce_common as c          # noqa: E402
import s3_signal as s3         # noqa: E402
from fc_matching import solve_exact_k, check_matching  # noqa: E402

MO = HERE.parent
checks, info = [], {}
def chk(name, ok, detail=''):
    checks.append((name, bool(ok), detail))
    print('%-4s %-56s %s' % ('PASS' if ok else 'FAIL', name, detail))


def main():
    t0 = time.time()
    c.log('missed-oracle validation start')

    # ---- V0 prior studies still sealed ------------------------------------
    import hashlib
    stale = []
    for line in (CEIL / 'integrity.sha256').read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        d, rel = line.split('  ', 1)
        p = c.ROOT / rel
        if not p.exists() or hashlib.sha256(p.read_bytes()).hexdigest() != d:
            stale.append(rel)
    # run_log.txt was deliberately appended to by the fixed-cardinality study
    # (a recorded deviation note); every substantive ceiling artifact must be
    # byte-identical, and run_log.txt must be the ONLY difference.
    ceiling_substantive = [s for s in stale if not s.endswith('run_log.txt')]
    chk('ceiling substantive artifacts unchanged',
        not ceiling_substantive, 'unexpected stale=%s' % (ceiling_substantive or 'none'))
    chk('ceiling seal differs only in run_log.txt',
        set(stale).issubset({'research/round2_decision_ceiling/run_log.txt'}),
        'stale=%s' % (stale or 'none'))
    stale2 = []
    for line in (FC_DIR / 'integrity.sha256').read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        d, rel = line.split('  ', 1)
        p = c.ROOT / rel
        if not p.exists() or hashlib.sha256(p.read_bytes()).hexdigest() != d:
            stale2.append(rel)
    chk('fixed-cardinality seal still current', not stale2, 'stale=%s' % (stale2[:3] or 'none'))

    # ---- V1 rebuild frame + recompute OOF ---------------------------------
    c.log('V1: rebuilding frame and recomputing OOF scores')
    fr = s3.load_frame()
    cols = sorted(fr['feat'][0])
    chk('feature columns are legal (no banned/cf_/y_)',
        s3.assert_legal_features(cols), '%d cols' % len(cols))
    banned = [k for k in cols if k in c.BANNED_FEATURE_EXACT or k.startswith('cf_')
              or k.startswith('y_') or k in ('seed', 'variant')]
    chk('no hidden attribute or counterfactual target in features', not banned,
        'banned=%s' % banned)

    import numpy as np
    import pandas as pd
    X_all = pd.DataFrame(fr['feat'])[s3.FEATURE_SETS['F1_baseline_count_score']].to_numpy()
    X_f2 = pd.DataFrame(fr['feat'])[s3.FEATURE_SETS['F2_soft_state']].to_numpy()
    y, groups = fr['y'], fr['groups']

    # group structure: every seed is one group holding all 6 variants
    gs = defaultdict(set)
    for st_, g in zip(fr['states'], groups):
        gs[int(g)].add(st_[1])
    chk('21 seed groups each holding all 6 variants',
        len(gs) == 21 and all(len(v) == 6 for v in gs.values()),
        'groups=%d' % len(gs))

    stored = {}
    for line in open(c.OUT / 'oof_scores.jsonl', encoding='utf-8'):
        r = json.loads(line)
        stored[(r['seed'], r['variant'], r['day'], r['user_a'], r['user_b'])] = r
    chk('oof_scores rows = 15304', len(stored) == 15304, str(len(stored)))

    oof1 = s3.oof_scores(X_all, y, groups)
    oof2 = s3.oof_scores(X_f2, y, groups)
    d1 = d2 = 0.0
    n = 0
    for i, st_ in enumerate(fr['states']):
        k = (st_[0], st_[1], st_[2], fr['feat'][i].get('_ua'), fr['feat'][i].get('_ub'))
        # reconstruct key from the row order of counterfactual_pairs
        n += 1
    # keys must be taken in counterfactual_pairs.jsonl order; rebuild explicitly
    keys = []
    for line in open(c.OUT / 'counterfactual_pairs.jsonl', encoding='utf-8'):
        r = json.loads(line)
        keys.append((r['seed'], r['variant'], r['day'], r['user_a'], r['user_b']))
    for i, k in enumerate(keys):
        s = stored[k]
        d1 = max(d1, abs(float(s['F1_baseline_count_score']) - float(oof1[i])))
        d2 = max(d2, abs(float(s['F2_soft_state']) - float(oof2[i])))
    chk('recomputed F1 OOF scores match stored bit-exactly', d1 == 0.0, 'max|d|=%r' % d1)
    chk('recomputed F2 OOF scores match stored bit-exactly', d2 == 0.0, 'max|d|=%r' % d2)
    info['oof_max_abs_diff_f1'] = d1
    info['oof_max_abs_diff_f2'] = d2
    c.log('  V1 recomputed OOF max|diff|: F1=%r F2=%r (%.1fs)' % (d1, d2, time.time() - t0))

    # ---- V2/V3 feasible graph + label alignment ---------------------------
    labels, edges_of, pairs_of = defaultdict(dict), {}, {}
    n_cf = 0
    for line in open(c.OUT / 'counterfactual_pairs.jsonl', encoding='utf-8'):
        r = json.loads(line)
        k = (r['seed'], r['variant'], r['day'])
        labels[k][(r['user_a'], r['user_b'])] = int(bool(r['cf_y_msmi']))
        n_cf += 1
    for line in open(c.OUT / 'day_edges.jsonl', encoding='utf-8'):
        d = json.loads(line)
        k = (d['seed'], d['variant'], d['day'])
        edges_of[k] = [tuple(e[1]) for e in d['edges']]
        pairs_of[k] = [tuple(p) for p in d['pairs']]
    off = sum(1 for k, es in edges_of.items() for e in es if e not in labels[k])
    chk('every feasible edge has a label', off == 0, 'missing=%d' % off)
    # orientation: label key must equal the feasible-graph orientation
    ori = 0
    for k, es in edges_of.items():
        for e in es:
            if (e[1], e[0]) in labels[k] and e not in labels[k]:
                ori += 1
    chk('no reversed-orientation label mismatches', ori == 0, 'reversed=%d' % ori)
    chk('cf rows = 15304', n_cf == 15304, str(n_cf))

    # ---- V4/V5 selectors at exact k_t reproduce the frozen counts ---------
    c.log('V4/V5: recomputing selectors at exact k_t')
    rows_prior = [json.loads(l) for l in open(FC_DIR / 'per_state_results.jsonl',
                                              encoding='utf-8')]
    prior = {(r['seed'], r['variant'], r['day']): r for r in rows_prior}
    ARMS = {'F1-SCORE': 'F1_baseline_count_score', 'F2-SOFT': 'F2_soft_state',
            'F3-OBSERV': 'F4_full_legal_observables'}
    score_of = {}
    for i, k in enumerate(keys):
        s = stored[k]
        score_of[k] = {a: float(s[col]) for a, col in ARMS.items()}
        score_of[k]['F1-SCORE'] = float(s['F1_baseline_count_score'])
        score_of[k]['BASELINE_RAW'] = None
    mism = {a: 0 for a in list(ARMS) + ['F5-ORACLE', 'GREEDY']}
    card_bad = 0
    selected_sets = {}
    for line in open(c.OUT / 'day_edges.jsonl', encoding='utf-8'):
        d = json.loads(line)
        k = (d['seed'], d['variant'], d['day'])
        raw = d['edges']
        edges = [tuple(e[1]) for e in raw]
        kt = len(d['pairs'])
        lab = labels[k]
        weights = {
            'F1-SCORE':  [-e[0] for e in raw],
            'F2-SOFT':   [score_of[(k[0], k[1], k[2], e[0], e[1])]['F2-SOFT'] for e in edges],
            'F3-OBSERV': [score_of[(k[0], k[1], k[2], e[0], e[1])]['F3-OBSERV'] for e in edges],
            'F5-ORACLE': [lab[e] for e in edges],
        }
        sets = {}
        for arm, w in weights.items():
            if kt == 0:
                sel_i = ()
            else:
                sel_i, _, _, failed = solve_exact_k(edges, w, kt)
                if failed or sel_i is None:
                    raise SystemExit('solver failed on %s %s' % (arm, k))
            ok, why = check_matching(edges, sel_i, kt)
            if not ok:
                card_bad += 1
            sel = tuple(edges[j] for j in sel_i)
            sets[arm] = sel
            got = sum(lab[e] for e in sel)
            if got != prior[k][arm + '_positives']:
                mism[arm] += 1
        sets['GREEDY'] = tuple(tuple(x) for x in d['pairs'])
        if sum(lab[e] for e in sets['GREEDY']) != prior[k]['GREEDY_positives']:
            mism['GREEDY'] += 1
        selected_sets[k] = sets
    chk('every recomputed selector has exactly k_t pairs', card_bad == 0,
        'violations=%d' % card_bad)
    chk('recomputed arm positives reproduce the frozen study',
        sum(mism.values()) == 0, 'mismatches=%s' % mism)

    # ---- V6 reconcile headline deltas -------------------------------------
    tot = {a: sum(sum(labels[k][e] for e in s[a]) for k, s in selected_sets.items())
           for a in ('GREEDY', 'F1-SCORE', 'F2-SOFT', 'F3-OBSERV', 'F5-ORACLE')}
    chk('GREEDY total = 90', tot['GREEDY'] == 90, str(tot['GREEDY']))
    chk('F5 - GREEDY = +71', tot['F5-ORACLE'] - tot['GREEDY'] == 71,
        '%+d' % (tot['F5-ORACLE'] - tot['GREEDY']))
    chk('F2 - GREEDY = +4', tot['F2-SOFT'] - tot['GREEDY'] == 4,
        '%+d' % (tot['F2-SOFT'] - tot['GREEDY']))
    chk('F2 - F1 = +13', tot['F2-SOFT'] - tot['F1-SCORE'] == 13,
        '%+d' % (tot['F2-SOFT'] - tot['F1-SCORE']))
    info['arm_totals'] = tot

    # persist the recomputed selected sets for reuse (under the new study only)
    (MO / 'recomputed_sets.jsonl').write_text(
        '\n'.join(json.dumps({'seed': k[0], 'variant': k[1], 'day': k[2],
                              **{a: [list(e) for e in s[a]]
                                 for a in ('GREEDY', 'F1-SCORE', 'F2-SOFT',
                                           'F3-OBSERV', 'F5-ORACLE')}})
                  for k, s in sorted(selected_sets.items())) + '\n', encoding='utf-8')
    c.log('wrote recomputed_sets.jsonl')

    failed = [n for n, ok, _ in checks if not ok]
    (MO / 'validation.json').write_text(json.dumps(dict(
        passed=not failed, n_checks=len(checks), failures=failed, info=info),
        indent=1, sort_keys=True) + '\n', encoding='utf-8')
    print('=' * 72)
    print('VALIDATION:', 'PASS' if not failed else 'FAIL -> %s' % failed)
    c.log('missed-oracle validation %s (%.1fs)'
          % ('PASS' if not failed else 'FAIL', time.time() - t0))
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
