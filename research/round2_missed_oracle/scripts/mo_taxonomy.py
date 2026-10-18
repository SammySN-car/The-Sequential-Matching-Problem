"""Section 8: zero-headroom taxonomy over the 7,478 states with local_gap = 0.

On those states the fixed-k oracle equals greedy by construction. Each is
assigned to exactly one mutually exclusive category (a)-(d) from analysis_plan
sec.8. Zero additional oracle gain is NEVER equated with zero predictive
signal or zero decision alternatives.
"""
import json, sys, time
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
MO = HERE.parent
CEIL = HERE.parent.parent / 'round2_decision_ceiling'
sys.path.insert(0, str(CEIL / 'scripts'))
import ce_common as c  # noqa: E402


def main():
    t0 = time.time(); c.log('mo_taxonomy start')
    sets = {}
    for line in open(MO / 'recomputed_sets.jsonl', encoding='utf-8'):
        r = json.loads(line)
        sets[(r['seed'], r['variant'], r['day'])] = {
            a: frozenset(tuple(e) for e in r[a])
            for a in ('GREEDY', 'F2-SOFT', 'F5-ORACLE')}
    lab = defaultdict(dict)
    for line in open(CEIL / 'counterfactual_pairs.jsonl', encoding='utf-8'):
        r = json.loads(line)
        lab[(r['seed'], r['variant'], r['day'])][(r['user_a'], r['user_b'])] = \
            int(bool(r['cf_y_msmi']))
    lref = {}
    for line in open(CEIL / 'oracle_by_day.jsonl', encoding='utf-8'):
        r = json.loads(line)
        lref[(r['seed'], r['variant'], r['day'])] = r

    counts = defaultdict(int)
    by_variant = defaultdict(lambda: defaultdict(int))
    per_state = []
    n_zero = 0
    for line in open(CEIL / 'day_edges.jsonl', encoding='utf-8'):
        d = json.loads(line)
        k = (d['seed'], d['variant'], d['day'])
        if lref[k]['local_gap'] != 0:
            continue
        n_zero += 1
        L = lab[k]; S = sets[k]
        p_t = sum(L[e] for e in L)
        PG = sum(L[e] for e in S['GREEDY'])
        M5, MG = S['F5-ORACLE'], S['GREEDY']
        if p_t == 0:
            cat = 'a_no_positive_edges'
        elif M5 == MG:
            cat = 'b_greedy_set_is_optimal'
        elif p_t > PG:
            cat = 'c_extras_blocked'
        else:
            cat = 'd_alternative_optima'
        counts[cat] += 1
        by_variant[d['variant']][cat] += 1
        per_state.append(dict(seed=k[0], variant=k[1], day=k[2], category=cat,
                              p_t=p_t, P_GREEDY=PG, P_F5=sum(L[e] for e in M5),
                              P_F2=sum(L[e] for e in S['F2-SOFT'])))

    # F2's behaviour on these states must be reported SEPARATELY from the
    # "no oracle gain" fact, so the two are never conflated.
    f2_by_cat = defaultdict(lambda: defaultdict(int))
    for r in per_state:
        f2_by_cat[r['category']]['n'] += 1
        f2_by_cat[r['category']]['P_F2'] += r['P_F2']
        f2_by_cat[r['category']]['P_GREEDY'] += r['P_GREEDY']
        f2_by_cat[r['category']]['P_F5'] += r['P_F5']

    total_f2 = sum(r['P_F2'] for r in per_state)
    total_g = sum(r['P_GREEDY'] for r in per_state)
    out = dict(
        n_zero_headroom_states=n_zero,
        mutually_exclusive_categories=sorted(counts),
        counts=dict(counts),
        fractions={k: round(v / n_zero, 6) for k, v in sorted(counts.items())},
        by_variant={v: dict(c2) for v, c2 in sorted(by_variant.items())},
        F2_behaviour_on_zero_headroom={k: dict(v) for k, v in sorted(f2_by_cat.items())},
        F2_total_on_zero_headroom=total_f2,
        GREEDY_total_on_zero_headroom=total_g,
        F2_minus_GREEDY_on_zero_headroom=total_f2 - total_g,
        invariant='P_F5 == P_GREEDY on every zero-headroom state',
        invariant_holds=all(r['P_F5'] == r['P_GREEDY'] for r in per_state),
        caveat=('A zero-headroom state means the local counterfactual oracle '
                'gains nothing over greedy at this day and this cardinality. '
                'It does NOT mean F2 has no predictive signal there, nor that '
                'no alternative decisions exist. Both are reported separately '
                'above.'))
    assert sum(counts.values()) == n_zero
    (MO / 'headroom_taxonomy.json').write_text(json.dumps(out, indent=1, sort_keys=True) + '\n',
                                               encoding='utf-8')
    c.write_jsonl(MO / 'headroom_taxonomy_per_state.jsonl', per_state)
    print('zero-headroom states:', n_zero)
    print('counts:', json.dumps(dict(counts), indent=1))
    print('fractions:', json.dumps(out['fractions'], indent=1))
    print('invariant P_F5==P_GREEDY holds:', out['invariant_holds'])
    print('F2 on zero-headroom: F2=%d GREEDY=%d diff=%d'
          % (total_f2, total_g, total_f2 - total_g))
    c.log('mo_taxonomy done (%.1fs)' % (time.time() - t0))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
