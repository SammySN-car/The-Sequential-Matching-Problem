"""Step 3: relationship-goal signal examination (analysis_plan.md sec.6).

1. Goal-state edge table: match/mismatch/unknown/declined counts, MSMI
   positives, pooled rates with seed-group bootstrap CIs, and the
   match-minus-mismatch rate difference (descriptive, never causal;
   unknown is never claimed better than mismatch).
2. G2 gain concentration: observable-goal vs all-unknown states, headroom
   split, seed distribution.
3. G3 beyond G2: set differences, net delta, per-seed churn.
4. Goal-state distribution of each selector's chosen edges.

Writes goal_analysis.json. Read-only over frozen inputs.
"""
import json, sys, time
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gr_common as g  # noqa: E402

GOAL_STATES = ['match', 'mismatch', 'unknown', 'declined']


def rate_ci(rows, b=g.B, seed=g.SEED):
    """95% CI of pooled rate, resampling whole seed groups."""
    by = defaultdict(list)
    for sd, y in rows:
        by[sd].append(y)
    uniq = sorted(by)
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(b):
        pick = rng.integers(0, len(uniq), size=len(uniq))
        vals = []
        for i in pick:
            vals.extend(by[uniq[i]])
        out.append(float(np.mean(vals)) if vals else 0.0)
    return [float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))]


def diff_ci(rows_a, rows_b, b=g.B, seed=g.SEED):
    """95% CI of pooled rate(A) - pooled rate(B), resampling seed groups."""
    by = {'a': defaultdict(list), 'b': defaultdict(list)}
    for sd, y in rows_a:
        by['a'][sd].append(y)
    for sd, y in rows_b:
        by['b'][sd].append(y)
    uniq = sorted(set(by['a']) | set(by['b']))
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(b):
        pick = rng.integers(0, len(uniq), size=len(uniq))
        pa, pb = [], []
        for i in pick:
            pa.extend(by['a'].get(uniq[i], []))
            pb.extend(by['b'].get(uniq[i], []))
        if pa and pb:
            out.append(float(np.mean(pa)) - float(np.mean(pb)))
    return [float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))]


def main():
    t0 = time.time()
    g.log('gr3_goal start')
    chan = g.load_channel_states(g.OUT / 'channel_states.json')
    labels = g.load_labels()
    sel = g.read_jsonl(g.OUT / 'selector_sets.jsonl')
    diag = g.load_diag()
    per_seed = defaultdict(lambda: defaultdict(int))

    # ---- 1. goal-state edge table ----------------------------------------
    buckets = {st: [] for st in GOAL_STATES}          # (seed, label)
    for k, ch in chan.items():
        buckets[ch['relationship_goal']].append((k[0],
                                                 labels[(k[0], k[1], k[2])]
                                                 [(k[3], k[4])]))
    goal_table = {}
    for st in GOAL_STATES:
        rows = buckets[st]
        n, npos = len(rows), sum(y for _, y in rows)
        goal_table[st] = dict(n_edges=n, n_positive=npos,
                              pooled_rate=round(npos / n, 6),
                              ci95_seed_group=[round(x, 6) for x in
                                               rate_ci(rows)])
    rows_m = buckets['match']
    rows_mm = buckets['mismatch']
    diff = [round(x, 6) for x in diff_ci(rows_m, rows_mm)]
    goal_table['match_minus_mismatch_rate'] = {
        'point': round(np.mean([y for _, y in rows_m]) -
                       np.mean([y for _, y in rows_mm]), 6),
        'ci95_seed_group': diff,
        'ci_excludes_zero': int(diff[0] > 0 or diff[1] < 0),
        'reading': 'descriptive association on recorded opportunities; '
                   'no causal or sequential claim; unknown NOT compared '
                   'as better/worse than mismatch'}

    # ---- state observability + G2 concentration ---------------------------
    obs, all_und = 0, 0
    conc = {ref: {o: dict(n_changed=0, sum_delta=0, improved=0, worsened=0,
                          hr_improved=0, hr_sum_delta=0)
                  for o in ('observable', 'unobservable')}
            for ref in ('G0', 'G1m')}
    improved_states, worsened_states = [], []
    # observability uses the state's FULL candidate list (day_edges):
    states = {s['key']: s for s in g.load_day_edges()}
    for r in sel:
        key = (r['seed'], r['variant'], r['day'])
        st = states[key]
        d = diag[key]
        cand_ch = [chan[(key[0], key[1], key[2], e[0], e[1])]
                   for e in st['edges']]
        observable = any(c['relationship_goal'] in ('match', 'mismatch')
                         for c in cand_ch)
        obs += observable
        all_und += (not observable)
        pos = {a: sum(labels[key][tuple(e)] for e in r['sets'][a])
               for a in g.ARMS}
        for ref in ('G0', 'G1m'):
            if set(map(tuple, r['sets']['G2'])) == \
               set(map(tuple, r['sets'][ref])):
                continue
            o = 'observable' if observable else 'unobservable'
            dv = pos['G2'] - pos[ref]
            c = conc[ref][o]
            c['n_changed'] += 1
            c['sum_delta'] += dv
            c['improved'] += int(dv > 0)
            c['worsened'] += int(dv < 0)
            if d['headroom']:
                c['hr_improved'] += int(dv > 0)
                c['hr_sum_delta'] += dv
            if ref == 'G0':
                (improved_states if dv > 0 else
                 worsened_states if dv < 0 else []).append(
                    dict(seed=key[0], variant=key[1], day=key[2],
                         delta=dv, observable=int(observable),
                         headroom=int(bool(d['headroom']))))
        for a in g.ARMS:
            per_seed[key[0]]['%s_pos' % a] += pos[a]
            for ref in ('G0', 'G1f', 'G1m'):
                per_seed[key[0]]['%s_d%s' % (a, ref)] += pos[a] - pos[ref]

    seeds = sorted(per_seed)
    seed_conc = {}
    for ref in ('G0', 'G1m'):
        vals = {sd: per_seed[sd]['G2_d%s' % ref] for sd in seeds}
        tot = sum(vals.values())
        top = max(vals, key=lambda sd: vals[sd]) if vals else None
        seed_conc[ref] = dict(per_seed_delta=vals,
                               total=tot,
                               top_seed=top, top_seed_delta=vals[top],
                               top_share_of_total=(round(vals[top] / tot, 4)
                                                   if tot else None),
                               pos_tie_neg=g.pos_tie_neg(list(vals.values())),
                               ci95=g.boot_mean(list(vals.values())))

    # ---- 3. G3 beyond G2 ---------------------------------------------------
    n_g32 = net = 0
    g32_states = []
    g32_conv_observable = 0
    for r in sel:
        key = (r['seed'], r['variant'], r['day'])
        s2, s3 = set(map(tuple, r['sets']['G2'])), \
            set(map(tuple, r['sets']['G3']))
        if s2 == s3:
            continue
        n_g32 += 1
        dv = sum(labels[key][e] for e in s3) - sum(labels[key][e] for e in s2)
        net += dv
        g32_states.append(dict(seed=key[0], variant=key[1], day=key[2],
                               delta=dv))
    # conversations-observable among differing states:
    for s in g32_states:
        key = (s['seed'], s['variant'], s['day'])
        st = states[key]
        cand_ch = [chan[(key[0], key[1], key[2], e[0], e[1])]
                   for e in st['edges']]
        if any(c['conversations'] in ('match', 'mismatch') for c in cand_ch):
            s['conv_observable'] = 1
    g32_conv = sum(s.get('conv_observable', 0) for s in g32_states)
    g32_deltas = [s['delta'] for s in g32_states]
    g32_per_seed = Counter()
    for s in g32_states:
        g32_per_seed[s['seed']] += s['delta']
    # per-seed G3-G2 including zeros
    g32_seed_vec = [g32_per_seed.get(sd, 0) for sd in seeds]

    # ---- 4. goal-state distribution of chosen edges -----------------------
    chosen = {a: Counter() for a in g.ARMS}
    for r in sel:
        key = (r['seed'], r['variant'], r['day'])
        for a in g.ARMS:
            for e in r['sets'][a]:
                chosen[a][chan[(key[0], key[1], key[2], e[0], e[1])]
                          ['relationship_goal']] += 1

    out = dict(
        goal_edge_table=goal_table,
        n_states_goal_observable=obs,
        n_states_all_undecided_or_unknown=all_und,
        g2_concentration={ref: conc[ref] for ref in ('G0', 'G1m')},
        g2_improved_states_vs_G0=improved_states,
        g2_worsened_states_vs_G0=worsened_states,
        g2_seed_concentration=seed_conc,
        g3_vs_g2=dict(
            n_states_sets_differ=n_g32, net_delta=net,
            n_states_conv_observable=g32_conv,
            per_seed_pos_tie_neg=g.pos_tie_neg(g32_seed_vec),
            ci95=g.boot_mean(g32_seed_vec),
            delta_histogram=dict(Counter(g32_deltas))),
        chosen_goal_states={a: dict(chosen[a]) for a in g.ARMS},
        conventions=dict(
            independent_unit='seed group (21, six variants together)',
            bootstrap='B=2000, rng 4242, percentile 95%',
            label='exploratory; counterfactual on recorded states only; '
                  'no causal or sequential claim'))
    (g.OUT / 'goal_analysis.json').write_text(
        json.dumps(out, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    g.log('wrote goal_analysis.json (observable=%d/%d states, g3!=g2 on %d)'
          % (obs, len(sel), n_g32))
    g.log('gr3_goal done (%.1fs)' % (time.time() - t0))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
