"""bi2: POST HOC corrective recomputation from saved artifacts (plan sec.7).

C1 totals | C2 paired seed-group CIs (gr convention, bit-for-bit vs
evaluation.json) | C3 set structure + count sums | C4 headroom |
C5 baseline-rank direction check | C6 decomposition | C7 frozen-number
reproduction (fc shared-rng / fresh-rng / contrast algorithms, gr pairs,
mo sums, ss published values). Read-only over inputs; writes only corrected_*
outputs under this study dir. Nothing is adjusted to fit expectations: every
mismatch is reported and fails the run.
"""
import csv
import json
import random
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
ROOT = HERE.parents[2]
GR = ROOT / 'research/round2_goal_rule'
FC = ROOT / 'research/round2_fixed_cardinality'
MO = ROOT / 'research/round2_missed_oracle'
CEIL = ROOT / 'research/round2_decision_ceiling'
SS = ROOT / 'research/round2_stagewise_signal'

ARMS = ['G0', 'G1f', 'G1m', 'G2', 'G3', 'G4', 'G5']
REFS = ['G0', 'G1f', 'G1m']
PAIRS = [('G2', 'G0'), ('G2', 'G1m'), ('G2', 'G1f'),
         ('G3', 'G0'), ('G3', 'G1m'), ('G3', 'G1f'),
         ('G4', 'G0'), ('G4', 'G1m'), ('G4', 'G1f'),
         ('G1m', 'G0'), ('G1f', 'G0'),
         ('G5', 'G0'), ('G5', 'G1m'), ('G5', 'G1f')]
B, SEEDN = 2000, 4242
EXPECTED_GR = {'G0': 90, 'G1f': 81, 'G1m': 88, 'G2': 92, 'G3': 92,
               'G4': 94, 'G5': 161}
EXPECTED_SUM_KT = 8433
FC_ARMS = ['F1-SCORE', 'F2-SOFT', 'F3-OBSERV', 'F4-RANDOM', 'F5-ORACLE']


def log(msg):
    line = '[%s] bi2: %s' % (time.strftime('%Y-%m-%d %H:%M:%S'), msg)
    print(line)
    with open(OUT / 'run_log.txt', 'a', encoding='utf-8') as fh:
        fh.write(line + '\n')


def write_csv(name, rows):
    with open(OUT / name, 'w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    log('wrote %s (%d rows)' % (name, len(rows)))


# ---------------- faithful bootstrap implementations ----------------------
def gr_boot_mean(values):
    """gr_common.boot_mean verbatim: np default_rng(SEEDN) fresh per call."""
    arr = np.array(values, dtype=float)
    rng = np.random.default_rng(SEEDN)
    idx = rng.integers(0, len(arr), size=(B, len(arr)))
    bs = arr[idx].mean(axis=1)
    return [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]


def fc_boot_shared(deltas_by_arm, arms):
    """fc_stats main loop verbatim: ONE random.Random(SEEDN) consumed
    sequentially across `arms` in order. Returns {arm: (lo, hi)} rounded 4dp."""
    rng = random.Random(SEEDN)
    out = {}
    for a in arms:
        d = deltas_by_arm[a]
        draws = []
        for _ in range(B):
            pick = [rng.randrange(21) for _ in range(21)]
            draws.append(sum(d[i] for i in pick) / 21.0)
        draws.sort()
        out[a] = (round(draws[int(0.025 * B)], 4),
                  round(draws[int(0.975 * B) - 1], 4))
    return out


def fc_boot_fresh(deltas):
    """fc_stats headroom/contrast verbatim: FRESH random.Random(SEEDN)."""
    rng = random.Random(SEEDN)
    draws = []
    for _ in range(B):
        pick = [rng.randrange(21) for _ in range(21)]
        draws.append(sum(deltas[i] for i in pick) / 21.0)
    draws.sort()
    return (round(draws[int(0.025 * B)], 4),
            round(draws[int(0.975 * B) - 1], 4))


def ptn(values):
    return (sum(1 for v in values if v > 0), sum(1 for v in values if v == 0),
            sum(1 for v in values if v < 0))


def competition_rank(score, all_scores):
    return 1 + sum(1 for s in all_scores if s > score)   # EPS-free: ints


def main():
    t0 = time.time()
    log('start (POST HOC integrity checks, plan sec.7)')
    fail = []

    # ================= load goal_rule per_state ===========================
    gr_rows = []
    with open(GR / 'per_state_results.csv', newline='',
              encoding='utf-8-sig') as fh:
        for r in csv.DictReader(fh):
            rec = dict(seed=int(r['seed']), variant=r['variant'],
                       day=int(r['day']), k_t=int(r['k_t']),
                       headroom=int(r['headroom']))
            for a in ARMS:
                rec[a] = int(r['%s_positives' % a])
            gr_rows.append(rec)
    n_states = len(gr_rows)
    seeds = sorted({r['seed'] for r in gr_rows})
    log('loaded gr per_state: %d rows, %d seeds' % (n_states, len(seeds)))

    # ---------------- C1 totals ------------------------------------------
    totals = {a: sum(r[a] for r in gr_rows) for a in ARMS}
    sum_kt = sum(r['k_t'] for r in gr_rows)
    hr_rows = [r for r in gr_rows if r['headroom'] == 1]
    c1 = dict(n_states=n_states, n_seeds=len(seeds), sum_k_t=sum_kt,
              n_headroom=len(hr_rows), totals=totals,
              expected_totals=EXPECTED_GR,
              totals_match=all(totals[a] == EXPECTED_GR[a] for a in EXPECTED_GR),
              sum_kt_match=(sum_kt == EXPECTED_SUM_KT),
              headroom_match=(len(hr_rows) == 82))
    for k, ok in [('totals', c1['totals_match']), ('sum_k_t', c1['sum_kt_match']),
                  ('headroom', c1['headroom_match'])]:
        if not ok:
            fail.append('C1 %s mismatch: %r' % (k, totals if k == 'totals' else sum_kt))
    log('C1 totals=%s sum_k_t=%d headroom=%d match=%s'
        % (totals, sum_kt, len(hr_rows), c1['totals_match'] and c1['sum_kt_match']))

    # ---------------- C2 paired CIs (gr convention) ----------------------
    per_seed_pos = {sd: {a: 0 for a in ARMS} for sd in seeds}
    for r in gr_rows:
        for a in ARMS:
            per_seed_pos[r['seed']][a] += r[a]
    ev = json.loads((GR / 'evaluation.json').read_text(encoding='utf-8'))
    ci_rows, ci_fail = [], []
    for a, ref in PAIRS:
        d = [per_seed_pos[sd][a] - per_seed_pos[sd][ref] for sd in seeds]
        lo, hi = gr_boot_mean(d)
        p, t, n = ptn(d)
        st_w = sum(1 for r in gr_rows if r[a] > r[ref])
        st_t = sum(1 for r in gr_rows if r[a] == r[ref])
        st_l = sum(1 for r in gr_rows if r[a] < r[ref])
        pub = ev['bootstrap']['paired'].get(a, {}).get('vs_%s' % ref)
        mine = '%.4f;%.4f' % (lo, hi)
        mine_ptn = '%d/%d/%d' % (p, t, n)
        match = (pub is not None and pub['ci95'] == mine
                 and pub['pos_tie_neg'] == mine_ptn)
        if pub is not None and not match:
            ci_fail.append('%s vs %s: mine=%s/%s pub=%s/%s'
                           % (a, ref, mine, mine_ptn, pub['ci95'],
                              pub['pos_tie_neg']))
        ci_rows.append(dict(
            pair='%s-%s' % (a, ref),
            delta_total=totals[a] - totals[ref],
            mean_per_seed=round(float(np.mean(d)), 6),
            ci_lo=round(lo, 4), ci_hi=round(hi, 4),
            seeds_positive=p, seeds_tied=t, seeds_negative=n,
            states_won=st_w, states_tied=st_t, states_lost=st_l,
            ci_excludes_zero=bool(lo > 0 or hi < 0),
            matches_evaluation_json=str(bool(match))))
    if ci_fail:
        fail.append('C2 exact-match failures: %r' % ci_fail)
    write_csv('corrected_paired_ci.csv', ci_rows)
    log('C2: %d pairs, exact evaluation.json matches=%d/%d'
        % (len(ci_rows), sum(1 for r in ci_rows
                             if r['matches_evaluation_json'] == 'True'),
           len(ci_rows)))

    # ---------------- C3 set structure ------------------------------------
    counts_by_state, edges_by_state = {}, {}
    with open(CEIL / 'day_edges.jsonl', encoding='utf-8') as fh:
        for line in fh:
            d = json.loads(line)
            k = (d['seed'], d['variant'], d['day'])
            counts_by_state[k] = {tuple(sorted(e[1])): int(e[0])
                                  for e in d['edges']}
            edges_by_state[k] = tuple(tuple(sorted(e[1])) for e in d['edges'])
    sets_by_state = {}
    card_bad = []
    with open(GR / 'selector_sets.jsonl', encoding='utf-8') as fh:
        for line in fh:
            d = json.loads(line)
            k = (d['seed'], d['variant'], d['day'])
            s = {a: frozenset(tuple(sorted(e)) for e in d['sets'][a])
                 for a in ARMS}
            sets_by_state[k] = s
            for a in ARMS:
                if len(s[a]) != d['k_t']:
                    card_bad.append('%s %s: |%s|=%d k_t=%d'
                                    % (k, a, len(s[a]), d['k_t']))
    if card_bad:
        fail.append('C3 cardinality violations: %r' % card_bad[:5])
    diff_states = {}
    for x, y in [('G0', 'G1f'), ('G0', 'G1m'), ('G1f', 'G1m')]:
        diff_states['states_differing_%s_vs_%s' % (x, y)] = sum(
            1 for k, s in sets_by_state.items() if s[x] != s[y])
    count_sums = {}
    for a in ARMS:
        tot = 0
        for k, s in sets_by_state.items():
            cm = counts_by_state[k]
            tot += sum(cm[e] for e in s[a])
        count_sums[a] = tot
    # cross-check: changed_vs_G0 columns
    chg = {}
    with open(GR / 'per_state_results.csv', newline='',
              encoding='utf-8-sig') as fh:
        for r in csv.DictReader(fh):
            pass  # columns already consumed above; recompute from sets instead
    c3_rows = ([dict(metric=m, value=v) for m, v in sorted(diff_states.items())]
               + [dict(metric='soft_match_count_sum_%s' % a, value=count_sums[a])
                  for a in ARMS]
               + [dict(metric='cardinality_violations', value=len(card_bad))])
    write_csv('corrected_set_diffs.csv', c3_rows)
    log('C3 diffs=%s count_sums=%s' % (diff_states, count_sums))

    # ---------------- C4 headroom -----------------------------------------
    hr_gr = {a: sum(r[a] for r in hr_rows) for a in ARMS}
    hr_mo = defaultdict(int)
    hr_states_mo = 0
    with open(MO / 'selection_diagnostics.jsonl', encoding='utf-8') as fh:
        for line in fh:
            d = json.loads(line)
            if int(d['headroom']) == 1:
                hr_states_mo += 1
                for col in ('P_GREEDY', 'P_F1', 'P_F2', 'P_F3', 'P_F5'):
                    hr_mo[col] += int(d[col])
    c4 = dict(headroom_states_from_gr=len(hr_rows),
              headroom_states_from_mo=hr_states_mo,
              gr=hr_gr,
              mo=dict(hr_mo),
               cross_checks=dict(
                  G0_eq_P_GREEDY=hr_gr['G0'] == hr_mo['P_GREEDY'],
                  G1f_eq_P_F1=hr_gr['G1f'] == hr_mo['P_F1'],
                  G4_eq_P_F2=hr_gr['G4'] == hr_mo['P_F2'],
                  G5_eq_P_F5=hr_gr['G5'] == hr_mo['P_F5']))
    if hr_states_mo != 82 or not all(c4['cross_checks'].values()):
        fail.append('C4 cross-check failed: %r' % c4)
    log('C4 gr=%s mo=%s' % (hr_gr, dict(hr_mo)))

    # ---------------- C5 baseline-rank direction --------------------------
    pub_rows = list(csv.DictReader(
        open(MO / 'positive_edge_ranks.csv', newline='', encoding='utf-8-sig')))
    n_pub = len(pub_rows)
    # published reproduction from the CSV itself
    f2_pct = [float(r['f2_percentile']) for r in pub_rows]
    bpct = [int(r['baseline_rank']) / int(r['n_edges']) for r in pub_rows]
    published = dict(
        n_positive_edges=n_pub,
        mean_f2_percentile=round(float(np.mean(f2_pct)), 6),
        median_f2_percentile=round(float(np.median(f2_pct)), 6),
        mean_baseline_percentile=round(float(np.mean(bpct)), 6),
        f2_better_than_baseline_share=round(float(np.mean(
            [fp < bp for fp, bp in zip(f2_pct, bpct)])), 6),
        n_f2_selected=sum(int(r['f2_selected']) for r in pub_rows),
        n_missed=sum(int(r['missed_oracle_positive']) for r in pub_rows),
        n_in_F5=sum(int(r['in_F5_optimal_set']) for r in pub_rows),
        baseline_rank_missed_mean=round(float(np.mean(
            [int(r['baseline_rank']) for r in pub_rows
             if int(r['missed_oracle_positive'])])), 6),
        baseline_rank_captured_mean=round(float(np.mean(
            [int(r['baseline_rank']) for r in pub_rows
             if int(r['f2_selected'])])), 6))
    # corrected: competition_rank on the STORED COUNT (rank 1 = highest count)
    sign_bad, corrected_vals, miss_true, cap_true = [], [], [], []
    for r in pub_rows:
        k = (int(r['seed']), r['variant'], int(r['day']))
        cm = counts_by_state[k]
        e = tuple(sorted((r['user_a'], r['user_b'])))
        c = cm[e]
        if int(r['baseline_raw']) != -c:
            sign_bad.append('%s %s raw=%s count=%d' % (k, e,
                                                       r['baseline_raw'], c))
        allc = list(cm.values())
        true_rank = competition_rank(c, allc)
        n = len(allc)
        true_pct = true_rank / n
        f2p = float(r['f2_percentile'])
        corrected_vals.append((f2p, true_pct, true_rank, int(r['n_edges'])))
        if int(r['missed_oracle_positive']):
            miss_true.append(true_rank)
        if int(r['f2_selected']):
            cap_true.append(true_rank)
    if sign_bad:
        fail.append('C5 sign-chain assertion failed: %r' % sign_bad[:3])
    # n_edges must equal len(counts) for each row
    nedge_bad = [r for (f2p, tr, rr, ne), r in zip(corrected_vals, pub_rows)
                 if ne != len(counts_by_state[(int(r['seed']), r['variant'],
                                               int(r['day']))])]
    if nedge_bad:
        fail.append('C5 n_edges mismatch on %d rows' % len(nedge_bad))
    true_pcts = [x[1] for x in corrected_vals]
    f2ps = [x[0] for x in corrected_vals]
    corrected = dict(
        mean_true_baseline_percentile=round(float(np.mean(true_pcts)), 6),
        median_true_baseline_percentile=round(float(np.median(true_pcts)), 6),
        f2_better_than_true_baseline_share=round(float(np.mean(
            [f < b for f, b in zip(f2ps, true_pcts)])), 6),
        true_baseline_rank_missed_mean=round(float(np.mean(miss_true)), 6),
        true_baseline_rank_captured_mean=round(float(np.mean(cap_true)), 6),
        sign_chain_rows_verified=n_pub,
        sign_chain_all_match=(len(sign_bad) == 0))
    c5_rows = [dict(metric='published.' + k, value=v)
               for k, v in sorted(published.items())]
    c5_rows += [dict(metric='corrected.' + k, value=v)
                for k, v in sorted(corrected.items())]
    # ss published values cross-read
    ss_pos = json.loads((SS / 'ranking_by_stage.json').read_text(
        encoding='utf-8'))['positive_edge_rank_summary']
    for k in ('mean_baseline_percentile', 'mean_f2_percentile',
              'median_f2_percentile', 'f2_better_than_baseline_share'):
        c5_rows.append(dict(metric='ss_published.%s' % k, value=ss_pos[k]))
    ss_match = all(abs(float(ss_pos[k]) - float(published[k if k != 'f2_better_than_baseline_share' else 'f2_better_than_baseline_share'])) < 1e-9
                   for k in ('mean_baseline_percentile', 'mean_f2_percentile',
                             'median_f2_percentile',
                             'f2_better_than_baseline_share'))
    if not ss_match:
        fail.append('C5 ss published mismatch: %r' % ss_pos)
    write_csv('corrected_rank_direction.csv', c5_rows)
    log('C5 published mean_base_pct=%.6f corrected=%.6f | share pub=%.6f corrected=%.6f'
        % (published['mean_baseline_percentile'],
           corrected['mean_true_baseline_percentile'],
           published['f2_better_than_baseline_share'],
           corrected['f2_better_than_true_baseline_share']))

    # ---------------- C6 decomposition ------------------------------------
    comp = dict(rank=0, conflict=0, p1=0, p2=0, p5=0, pg=0, rt=0, n_hr=0)
    with open(MO / 'selection_diagnostics.jsonl', encoding='utf-8') as fh:
        for line in fh:
            d = json.loads(line)
            comp['rank'] += int(d['ranking_component'])
            comp['conflict'] += int(d['conflict_component'])
            comp['p1'] += int(d['P_F1'])
            comp['p2'] += int(d['P_F2'])
            comp['p5'] += int(d['P_F5'])
            comp['pg'] += int(d['P_GREEDY'])
            comp['rt'] += int(d['R_t'])
    agg = json.loads((MO / 'decomposition_agg.json').read_text(encoding='utf-8'))
    c6 = dict(sums=comp,
              agg=dict(rank=agg['sum_ranking_component'],
                       conflict=agg['sum_conflict_component'],
                       gap=agg['sum_gap_F5_F2'], n_captured=agg['n_captured'],
                       n_missed=agg['n_missed']),
              checks=dict(
                  rank_60=comp['rank'] == 60,
                  conflict_7=comp['conflict'] == 7,
                  closure=(comp['rank'] + comp['conflict']
                           == comp['p5'] - comp['p2'] == 67),
                  rt_101=comp['rt'] == 101,
                  p1_81=comp['p1'] == 81,
                  p2_94=comp['p2'] == 94,
                  pg_90=comp['pg'] == 90,
                  p5_161=comp['p5'] == 161,
                  f2_minus_f1_13=(comp['p2'] - comp['p1'] == 13),
                  agg_agrees=(agg['sum_ranking_component'] == comp['rank']
                              and agg['sum_conflict_component'] == comp['conflict'])))
    if not all(c6['checks'].values()):
        fail.append('C6 check failed: %r' % c6['checks'])
    # n_captured mislabel (pre-existing, recorded not fixed)
    c6['n_captured_field'] = dict(value=agg['n_captured'],
                                  f2_selected_sum=published['n_f2_selected'],
                                  note='known label issue: n_captured=106 is '
                                       '"positives not in F5-F2"; F2 actually '
                                       'selected 94 positives')
    log('C6 rank=%d conflict=%d rt=%d p1=%d p2=%d pg=%d p5=%d checks=%s'
        % (comp['rank'], comp['conflict'], comp['rt'], comp['p1'], comp['p2'],
           comp['pg'], comp['p5'],
           all(c6['checks'].values())))

    # ---------------- C7 frozen fc reproduction ---------------------------
    fc_rows = [json.loads(l) for l in
               open(FC / 'per_state_results.jsonl', encoding='utf-8')]
    fc_seeds = sorted({r['seed'] for r in fc_rows})
    assert len(fc_seeds) == 21
    per_seed_fc = []
    for s in fc_seeds:
        sub = [r for r in fc_rows if r['seed'] == s]
        rec = dict(seed=s)
        for a in FC_ARMS:
            rec[a] = sum(r['%s_positives' % a] for r in sub)
        rec['GREEDY'] = sum(r['GREEDY_positives'] for r in sub)
        per_seed_fc.append(rec)
    deltas_main = {a: [rec[a] - rec['GREEDY'] for rec in per_seed_fc]
                   for a in FC_ARMS}
    main_ci = fc_boot_shared(deltas_main, FC_ARMS)
    fcs = json.loads((FC / 'statistics.json').read_text(encoding='utf-8'))
    c7 = dict(fc_main={}, fc_headroom={}, fc_contrast={})
    for a in FC_ARMS:
        pub = fcs['overall'][a]
        tot = sum(r['%s_positives' % a] for r in fc_rows)
        d = deltas_main[a]
        p, t, n = ptn(d)
        ok = (list(main_ci[a]) == [float(x) for x in pub['seed_group_ci95']]
              and round(tot, 4) == pub['total_positives']
              and p == pub['seeds_positive'] and t == pub['seeds_tied']
              and n == pub['seeds_negative'])
        c7['fc_main'][a] = dict(mine=list(main_ci[a]),
                                published=pub['seed_group_ci95'],
                                total=round(tot, 4),
                                published_total=pub['total_positives'],
                                match=bool(ok))
        if not ok:
            fail.append('C7 fc main mismatch %s: %r' % (a, c7['fc_main'][a]))
    # fc headroom: fresh rng per arm
    hr_fc = [r for r in fc_rows if r['headroom'] == 1]
    for a in FC_ARMS:
        d = []
        for rec in per_seed_fc:
            sub = [r for r in fc_rows
                   if r['seed'] == rec['seed'] and r['headroom'] == 1]
            d.append(sum(r['%s_positives' % a] - r['GREEDY_positives']
                         for r in sub))
        lo, hi = fc_boot_fresh(d)
        pub = fcs['headroom_states'][a]
        tot = sum(r['%s_positives' % a] for r in hr_fc)
        ok = ([lo, hi] == [float(x) for x in pub['seed_group_ci95']]
              and round(tot, 4) == pub['total_positives'])
        c7['fc_headroom'][a] = dict(mine=[lo, hi],
                                    published=pub['seed_group_ci95'],
                                    total=round(tot, 4),
                                    published_total=pub['total_positives'],
                                    match=bool(ok))
        if not ok:
            fail.append('C7 fc headroom mismatch %s: %r'
                        % (a, c7['fc_headroom'][a]))
    # fc contrast F2-F1: fresh rng3
    d21 = [rec['F2-SOFT'] - rec['F1-SCORE'] for rec in per_seed_fc]
    clo, chi = fc_boot_fresh(d21)
    pub = fcs['contrast_F2_vs_F1']
    p, t, n = ptn(d21)
    ok = ([clo, chi] == [float(x) for x in pub['seed_group_ci95']]
          and sum(d21) == pub['delta_total']
          and p == pub['seeds_positive'] and t == pub['seeds_tied']
          and n == pub['seeds_negative'])
    c7['fc_contrast'] = dict(mine=[clo, chi],
                             published=pub['seed_group_ci95'],
                             delta=sum(d21), published_delta=pub['delta_total'],
                             match=bool(ok))
    if not ok:
        fail.append('C7 fc contrast mismatch: %r' % c7['fc_contrast'])
    # gr pairs already checked in C2; record count
    c7['gr_pairs_exact'] = sum(1 for r in ci_rows
                               if r['matches_evaluation_json'] == 'True')
    c7['gr_pairs_total'] = len(ci_rows)
    log('C7 fc main=%d/5 fc headroom=%d/5 contrast=%s gr_pairs=%d/%d'
        % (sum(1 for v in c7['fc_main'].values() if v['match']),
           sum(1 for v in c7['fc_headroom'].values() if v['match']),
           c7['fc_contrast']['match'], c7['gr_pairs_exact'],
           c7['gr_pairs_total']))

    # ---------------- corrected_totals.csv --------------------------------
    zhr = [r for r in gr_rows if r['headroom'] == 0]
    tot_rows = []
    for a in ARMS:
        pos_h = sum(r[a] for r in hr_rows)
        pos_z = sum(r[a] for r in zhr)
        tot_rows.append(dict(
            arm=a, positives=totals[a], delta_vs_G0=totals[a] - totals['G0'],
            per_intro_rate=round(totals[a] / sum_kt, 6),
            headroom_positives=pos_h, zero_headroom_positives=pos_z,
            soft_match_count_sum=count_sums[a],
            states_changed_vs_G0=sum(
                1 for k, s in sets_by_state.items()
                if s[a] != s['G0'])))
    write_csv('corrected_totals.csv', tot_rows)

    summary = dict(
        generated=time.strftime('%Y-%m-%d %H:%M:%S'),
        label='POST HOC integrity checks (analysis_plan.md sec.7); no prior '
              'result altered; local fixed-cardinality counterfactuals on '
              'saved artifacts only',
        c1=c1, c2=dict(pairs=len(ci_rows),
                       exact_matches=c7['gr_pairs_exact'],
                       failures=ci_fail),
        c3=dict(diff_states=diff_states, count_sums=count_sums,
                cardinality_violations=len(card_bad)),
        c4=c4, c5=dict(published=published, corrected=corrected,
                       ss_published_mean_f2=ss_pos['mean_f2_percentile']),
        c6=c6, c7=c7,
        failures=fail)
    (OUT / 'corrected_summary.json').write_text(
        json.dumps(summary, indent=1, sort_keys=True), encoding='utf-8')
    log('wrote corrected_summary.json; failures=%d' % len(fail))
    for x in fail:
        print('BI2 FAILURE: %s' % x)
    log('done in %.1fs' % (time.time() - t0))
    return 1 if fail else 0


if __name__ == '__main__':
    sys.exit(main())
