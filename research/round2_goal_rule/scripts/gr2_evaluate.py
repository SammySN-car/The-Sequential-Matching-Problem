"""Step 2: evaluate G0..G5+G1m on the 7,560 recorded states (identical k_t).

Writes per_state_results.csv, per_seed_results.csv, per_variant_results.csv,
selector_summary.csv, tie_analysis.json, evaluation.json.

Deltas are reported against G0 (greedy), G1f (frozen reproduction) and G1m
(spec maximizer baseline). Hard reconciliation asserts (Amendment 1):
G0=90, G1f=81, G1m=88, G4=94, G5=161.
Exact point totals preserved; inference = paired seed-group bootstrap
(B=2000, rng 4242) with positive/tied/negative seed counts.
"""
import csv, json, sys, time
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gr_common as g  # noqa: E402

EXPECTED_TOTALS = {'G0': 90, 'G1f': 81, 'G1m': 88, 'G4': 94, 'G5': 161}


def write_csv(path, rows, fields=None):
    keys = list(rows[0].keys())
    for r in rows[1:]:
        for k in r:
            if k not in keys:
                keys.append(k)
    fields = fields or keys
    with open(path, 'w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=fields, restval='')
        w.writeheader()
        w.writerows(rows)
    g.log('wrote %s (%d rows, %d cols)' % (Path(path).name, len(rows),
                                           len(fields)))


def fmt_ci(ci):
    return '%.4f;%.4f' % (ci[0], ci[1])


def fmt_ptn(d):
    return '%d/%d/%d' % (d['positive'], d['tied'], d['negative'])


def main():
    t0 = time.time()
    g.log('gr2_evaluate start (7 arms)')
    sel = g.read_jsonl(g.OUT / 'selector_sets.jsonl')
    labels = g.load_labels()
    diag = g.load_diag()
    assert len(sel) == 7560

    REFS = ['G0', 'G1f', 'G1m']          # delta/bootstrap references
    per_state = []
    per_seed = defaultdict(lambda: defaultdict(int))
    per_variant = defaultdict(lambda: defaultdict(int))
    seed_k, var_k = Counter(), Counter()
    score_hist = {a: Counter() for a in g.SCORED_ARMS}
    hr_tot = {a: 0 for a in g.ARMS}
    zhr_tot = {a: 0 for a in g.ARMS}
    changed_states = {a: 0 for a in g.ARMS}
    improve = {a: [0, 0, 0] for a in g.ARMS}   # improved, tied, worsened vs G0

    # ---- per-state positives + accumulators -------------------------------
    for r in sel:
        key = (r['seed'], r['variant'], r['day'])
        lab, d, kt = labels[key], diag[key], r['k_t']
        pos = {a: sum(lab[tuple(e)] for e in r['sets'][a]) for a in g.ARMS}
        sets = {a: set(map(tuple, r['sets'][a])) for a in g.ARMS}
        row = dict(seed=r['seed'], variant=r['variant'], day=r['day'],
                   n_edges=r['n_edges'], k_t=kt,
                   headroom=int(bool(d['headroom'])),
                   local_gap=d['local_gap'])
        for a in g.ARMS:
            row['%s_positives' % a] = pos[a]
            row['%s_changed_vs_G0' % a] = int(a != 'G0' and sets[a] != sets['G0'])
            for ref in REFS:
                row['%s_delta_vs_%s' % (a, ref)] = pos[a] - pos[ref]
        for a in g.SCORED_ARMS:
            row['%s_n_at_max' % a] = r['tie'][a]['n_at_max']
            row['%s_n_distinct' % a] = r['tie'][a]['n_distinct']
        per_state.append(row)

        for a in g.ARMS:
            ps, pv = per_seed[r['seed']], per_variant[r['variant']]
            ps['%s_pos' % a] += pos[a]
            pv['%s_pos' % a] += pos[a]
            for ref in REFS:
                ps['%s_d%s' % (a, ref)] += pos[a] - pos[ref]
                pv['%s_d%s' % (a, ref)] += pos[a] - pos[ref]
            if d['headroom']:
                hr_tot[a] += pos[a]
                ps['hr_%s' % a] += pos[a]
                pv['hr_%s' % a] += pos[a]
            else:
                zhr_tot[a] += pos[a]
                ps['zhr_%s' % a] += pos[a]
                pv['zhr_%s' % a] += pos[a]
            if row['%s_changed_vs_G0' % a]:
                changed_states[a] += 1
            if a != 'G0':
                dv = pos[a] - pos['G0']
                improve[a][0 if dv > 0 else (1 if dv == 0 else 2)] += 1
        seed_k[r['seed']] += kt
        var_k[r['variant']] += kt

    write_csv(g.OUT / 'per_state_results.csv', per_state)

    # ---- hard reconciliation (Amendment 1 + sec.7) -------------------------
    totals = {a: sum(per_seed[sd]['%s_pos' % a] for sd in per_seed)
              for a in g.ARMS}
    bad = {a: (totals[a], EXPECTED_TOTALS[a]) for a in EXPECTED_TOTALS
           if totals[a] != EXPECTED_TOTALS[a]}
    total_k = sum(seed_k.values())
    if bad or total_k != 8433:
        raise SystemExit('RECONCILIATION FAILED: totals=%s expected_mismatch=%s'
                         ' sum_k=%d' % (totals, bad, total_k))
    g.log('reconciliation OK: %s sum_k=%d' % (totals, total_k))

    # ---- score-value histograms -------------------------------------------
    chan = g.load_channel_states(g.OUT / 'channel_states.json')
    for s in g.load_day_edges():
        key = s['key']
        channels = [chan[(key[0], key[1], key[2], e[0], e[1])]
                    for e in s['edges']]
        score_hist['G1f'].update(int(round(w)) for w in g.weight_g1f(s['neg_scores']))
        score_hist['G1m'].update(int(round(w)) for w in g.weight_g1m(s['neg_scores']))
        score_hist['G2'].update(g.weight_g2(channels))
        score_hist['G3'].update(round(w, 6) for w in g.weight_g3(channels))

    # ---- per-seed / per-variant tables ------------------------------------
    seeds = sorted(per_seed)
    assert len(seeds) == 21
    srows = []
    for sd in seeds:
        rec = dict(seed=sd, sum_k_t=seed_k[sd])
        for a in g.ARMS:
            rec['%s_positives' % a] = per_seed[sd]['%s_pos' % a]
            for ref in ('G0', 'G1f', 'G1m'):
                if a == ref:
                    continue
                rec['%s_delta_vs_%s' % (a, ref)] = \
                    per_seed[sd]['%s_d%s' % (a, ref)]
        for ref in REFS:
            rec['headroom_positives_%s' % ref] = per_seed[sd]['hr_%s' % ref]
        rec['zero_headroom_delta_G2_vs_G1m'] = \
            per_seed[sd]['zhr_G2'] - per_seed[sd]['zhr_G1m']
        srows.append(rec)
    write_csv(g.OUT / 'per_seed_results.csv', srows)

    vrows = []
    for v in sorted(per_variant):
        rec = dict(variant=v)
        for a in g.ARMS:
            rec['%s_positives' % a] = per_variant[v]['%s_pos' % a]
            for ref in ('G0', 'G1f', 'G1m'):
                if a == ref:
                    continue
                rec['%s_delta_vs_%s' % (a, ref)] = \
                    per_variant[v]['%s_d%s' % (a, ref)]
        for ref in REFS:
            rec['headroom_positives_%s' % ref] = per_variant[v]['hr_%s' % ref]
        rec['zero_headroom_delta_G2_vs_G1m'] = \
            per_variant[v]['zhr_G2'] - per_variant[v]['zhr_G1m']
        vrows.append(rec)
    write_csv(g.OUT / 'per_variant_results.csv', vrows)

    # ---- tie / discrimination analysis (sec.5) ----------------------------
    tie_json = {}
    for a in g.SCORED_ARMS:
        n_at = [r['tie'][a]['n_at_max'] for r in sel]
        n_di = [r['tie'][a]['n_distinct'] for r in sel]
        changed = [r for r in sel
                   if set(map(tuple, r['sets'][a])) !=
                   set(map(tuple, r['sets']['G0']))]
        ch_tie_only = sum(1 for r in changed
                          if r['tie'][a]['n_distinct'] <= 1)
        ch_top_tied = sum(1 for r in changed if r['tie'][a]['n_at_max'] > 1)
        tie_json[a] = dict(
            name=g.ARM_NAMES[a],
            mean_candidates=round(float(np.mean([r['n_edges'] for r in sel])), 4),
            mean_n_distinct_scores=round(float(np.mean(n_di)), 4),
            share_states_no_discrimination=round(
                float(np.mean([x <= 1 for x in n_di])), 4),
            share_states_top_score_tied=round(
                float(np.mean([x > 1 for x in n_at])), 4),
            mean_n_at_max=round(float(np.mean(n_at)), 4),
            n_states_changed_vs_G0=len(changed),
            changed_states_tie_only=ch_tie_only,
            changed_states_top_score_tied=ch_top_tied,
            changed_states_top_unique=len(changed) - ch_top_tied,
            score_value_histogram=({str(k): int(v) for k, v in
                                    sorted(score_hist[a].items())}
                                   if a in ('G1f', 'G1m', 'G2', 'G3')
                                   else 'continuous (see n_at_max/n_distinct)'))
    (g.OUT / 'tie_analysis.json').write_text(
        json.dumps(tie_json, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    g.log('wrote tie_analysis.json')

    # ---- selector summary --------------------------------------------------
    ssum = []
    for a in g.ARMS:
        row = dict(
            arm=a, name=g.ARM_NAMES[a],
            total_positives=totals[a],
            positives_per_selected_pair=round(totals[a] / total_k, 6),
            n_states_changed_vs_G0=changed_states[a],
            n_improved_vs_G0=improve[a][0], n_tied_vs_G0=improve[a][1],
            n_worsened_vs_G0=improve[a][2],
            headroom_positives=hr_tot[a],
            zero_headroom_positives=zhr_tot[a])
        for ref in REFS:
            if a == ref:
                row['delta_vs_%s' % ref] = 0
                row['ci95_delta_vs_%s' % ref] = '0.0000;0.0000'
                row['seed_pos_tie_neg_vs_%s' % ref] = '0/21/0'
                row['ci95_vs_%s_excludes_zero' % ref] = 0
                continue
            dv = [per_seed[sd]['%s_d%s' % (a, ref)] for sd in seeds]
            ci = g.boot_mean(dv)
            row['delta_vs_%s' % ref] = totals[a] - totals[ref]
            row['ci95_delta_vs_%s' % ref] = fmt_ci(ci)
            row['seed_pos_tie_neg_vs_%s' % ref] = fmt_ptn(g.pos_tie_neg(dv))
            row['ci95_vs_%s_excludes_zero' % ref] = int(ci[0] > 0 or ci[1] < 0)
        row['headroom_delta_vs_G0'] = hr_tot[a] - hr_tot['G0']
        row['headroom_delta_vs_G1m'] = hr_tot[a] - hr_tot['G1m']
        row['zero_headroom_delta_vs_G0'] = zhr_tot[a] - zhr_tot['G0']
        row['zero_headroom_delta_vs_G1m'] = zhr_tot[a] - zhr_tot['G1m']
        row['label'] = 'exploratory_local_counterfactual'
        if a in tie_json:
            row['share_states_no_discrimination'] = \
                tie_json[a]['share_states_no_discrimination']
            row['share_states_top_score_tied'] = \
                tie_json[a]['share_states_top_score_tied']
            row['changed_states_tie_only'] = tie_json[a]['changed_states_tie_only']
        ssum.append(row)
    write_csv(g.OUT / 'selector_summary.csv', ssum)

    # ---- evaluation.json ---------------------------------------------------
    ev = dict(
        n_states=7560, sum_k_t=int(total_k),
        totals=totals,
        reconciliation=dict(expected=EXPECTED_TOTALS, passed=True,
                            sign_chain='s1_opportunities.py:54 stores +count; '
                                       'fc_selectors.py:123 / mo_validate.py:172 '
                                       'apply -count; see plan Amendment 1'),
        deltas={a: {ref: totals[a] - totals[ref] for ref in REFS}
                for a in g.ARMS},
        positives_per_selected_pair={a: round(totals[a] / total_k, 6)
                                     for a in g.ARMS},
        bootstrap=dict(B=g.B, rng_seed=g.SEED,
                       unit='seed group (21, six variants kept together)',
                       paired={a: {
                           'vs_%s' % ref: dict(
                               ci95=fmt_ci(g.boot_mean(
                                   [per_seed[sd]['%s_d%s' % (a, ref)]
                                    for sd in seeds])),
                               pos_tie_neg=fmt_ptn(g.pos_tie_neg(
                                   [per_seed[sd]['%s_d%s' % (a, ref)]
                                    for sd in seeds])))
                           for ref in REFS if a != ref}
                           for a in g.ARMS}),
        headroom=dict(n_states=82, totals={a: hr_tot[a] for a in g.ARMS},
                      delta_vs_G0={a: hr_tot[a] - hr_tot['G0']
                                   for a in g.ARMS if a != 'G0'}),
        zero_headroom=dict(n_states=7478,
                           totals={a: zhr_tot[a] for a in g.ARMS},
                           delta_vs_G0={a: zhr_tot[a] - zhr_tot['G0']
                                        for a in g.ARMS if a != 'G0'}),
        improved_tied_worsened_vs_G0={a: dict(improved=improve[a][0],
                                              tied=improve[a][1],
                                              worsened=improve[a][2])
                                      for a in g.ARMS if a != 'G0'},
        n_states_changed_vs_G0={a: changed_states[a] for a in g.ARMS})
    (g.OUT / 'evaluation.json').write_text(
        json.dumps(ev, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    g.log('wrote evaluation.json: totals=%s' % totals)
    g.log('gr2_evaluate done (%.1fs)' % (time.time() - t0))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
