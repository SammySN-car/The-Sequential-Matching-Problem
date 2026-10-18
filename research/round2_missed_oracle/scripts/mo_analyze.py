"""Missed-oracle mechanism audit: core per-state diagnostics.

Computes, for every state, the exact-k_t selected sets for all arms (reusing
the validated solver), the rank of every counterfactual-positive edge, and the
additive ranking-versus-conflict decomposition defined in analysis_plan.md 4.

R_t is a DIAGNOSTIC BOUND (positives among the top-k_t scores, overlap
ignored). It is never a realisable selector and is labelled as such everywhere.
"""
import csv, json, sys, time
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
MO = HERE.parent
CEIL = HERE.parent.parent / 'round2_decision_ceiling'
FC_DIR = HERE.parent.parent / 'round2_fixed_cardinality'
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(FC_DIR / 'scripts'))
sys.path.insert(0, str(CEIL / 'scripts'))
import ce_common as c  # noqa: E402
max_matching_size = c.max_matching_size  # validated helper in ce_common

EPS = 1e-12


def canon(e):
    return (e[0], e[1]) if e[0] <= e[1] else (e[1], e[0])


def competition_rank(score, all_scores):
    """1 + count of strictly greater scores."""
    return 1 + sum(1 for s in all_scores if s > score + EPS)


def main():
    t0 = time.time()
    c.log('mo_analyze start')

    sets = {}
    for line in open(MO / 'recomputed_sets.jsonl', encoding='utf-8'):
        r = json.loads(line)
        sets[(r['seed'], r['variant'], r['day'])] = {
            a: tuple(tuple(e) for e in r[a])
            for a in ('GREEDY', 'F1-SCORE', 'F2-SOFT', 'F3-OBSERV', 'F5-ORACLE')}

    labels, score2, score1 = defaultdict(dict), {}, {}
    for line in open(CEIL / 'counterfactual_pairs.jsonl', encoding='utf-8'):
        r = json.loads(line)
        k = (r['seed'], r['variant'], r['day'])
        labels[k][(r['user_a'], r['user_b'])] = int(bool(r['cf_y_msmi']))
    for line in open(CEIL / 'oof_scores.jsonl', encoding='utf-8'):
        r = json.loads(line)
        score2[(r['seed'], r['variant'], r['day'], r['user_a'], r['user_b'])] = \
            float(r['F2_soft_state'])
        score1[(r['seed'], r['variant'], r['day'], r['user_a'], r['user_b'])] = \
            float(r['F1_baseline_count_score'])

    gap_ref = {}
    for line in open(CEIL / 'oracle_by_day.jsonl', encoding='utf-8'):
        r = json.loads(line)
        gap_ref[(r['seed'], r['variant'], r['day'])] = r

    diag_rows, rank_rows = [], []
    tot = defaultdict(int)
    for line in open(CEIL / 'day_edges.jsonl', encoding='utf-8'):
        d = json.loads(line)
        k = (d['seed'], d['variant'], d['day'])
        raw = d['edges']
        edges = [tuple(e[1]) for e in raw]
        kt = len(d['pairs'])
        lab, S = labels[k], sets[k]
        pos = {e for e in edges if lab[e] == 1}
        p_t = len(pos)
        s2 = [score2[(k[0], k[1], k[2], e[0], e[1])] for e in edges]
        s1 = [score1[(k[0], k[1], k[2], e[0], e[1])] for e in edges]

        # top-k_t by F2 score, ties broken canonically (diagnostic only)
        order = sorted(range(len(edges)), key=lambda i: (-s2[i], canon(edges[i])))
        topk_idx = set(order[:kt])
        R_t = sum(1 for i in topk_idx if edges[i] in pos)
        U_t = min(p_t, kt)

        P = {a: sum(lab[e] for e in S[a]) for a in S}
        M2, M5, MG = set(S['F2-SOFT']), set(S['F5-ORACLE']), set(S['GREEDY'])
        gap = P['F5-ORACLE'] - P['F2-SOFT']

        # ---- one row per COUNTERFACTUAL-POSITIVE edge ----------------------
        m2_neg = [e for e in M2 if lab[e] == 0]
        m2_pos = [e for e in M2 if lab[e] == 1]
        s2_rank = {edges[i]: competition_rank(s2[i], s2) for i in range(len(edges))}
        base_rank = {edges[i]: competition_rank(-raw[i][0], [-r[0] for r in raw])
                     for i in range(len(edges))}
        for e in sorted(pos):
            i = edges.index(e)
            sc = s2[i]
            outrank_neg = [f for f in m2_neg if s2[edges.index(f)] > sc + EPS]
            conflicts = [f for f in M2 if set(f) & set(e)]
            conflicts_pos = [f for f in m2_pos if set(f) & set(e)]
            tie_neg = sum(1 for f in m2_neg if abs(s2[edges.index(f)] - sc) <= EPS)
            fA = bool(outrank_neg); fB = bool(conflicts)
            fC = len(outrank_neg);  fD = tie_neg > 0; fE = bool(conflicts_pos)
            resid = [x for x in edges if not (set(x) & set(e))]
            coverable = (kt == 0) or (max_matching_size(resid) >= kt - 1)
            missed = e in (M5 - M2); captured = e in M2
            if missed:
                primary = ('E_blocked_by_positive' if fE else
                           'B_matching_conflict' if fB else
                           'A_ranking_failure' if fA else
                           'D_weak_separation' if fD else 'residual')
            elif captured:
                primary = 'captured_by_F2'
            else:
                primary = 'not_in_F5_optimal_set'
            rank_rows.append(dict(
                seed=k[0], variant=k[1], day=k[2],
                user_a=e[0], user_b=e[1], n_edges=len(edges), k_t=kt,
                f2_score=round(sc, 8), f2_rank=s2_rank[e],
                f2_percentile=round(s2_rank[e] / len(edges), 6),
                f2_tie_size=sum(1 for x in s2 if abs(x - sc) <= EPS),
                baseline_raw=-raw[i][0], baseline_rank=base_rank[e],
                in_F5_optimal_set=int(e in M5), f2_selected=int(captured),
                greedy_selected=int(e in MG), missed_oracle_positive=int(missed),
                coverable_at_kt=int(coverable),
                n_conflicting_with_F2=len(conflicts),
                n_conflicting_positive_in_F2=len(conflicts_pos),
                n_F2_negatives_outranking=len(outrank_neg),
                n_F2_negatives_tied=tie_neg,
                flag_A_ranking_failure=int(fA), flag_B_matching_conflict=int(fB),
                flag_C_false_positive_pull=fC, flag_D_weak_separation=int(fD),
                flag_E_blocked_by_positive=int(fE),
                n_flags=int(fA) + int(fB) + int(fD) + int(fE),
                primary_mechanism=primary,
                state_gap=gap, state_local_gap=gap_ref[k]['local_gap']))
            tot['positive'] += 1
            if missed:
                tot['missed'] += 1
                tot['mech_' + primary] += 1
                for f, nm in ((fA, 'A'), (fB, 'B'), (fC > 0, 'C'),
                              (fD, 'D'), (fE, 'E')):
                    if f:
                        tot['flag_' + nm] += 1
                combo = ''.join(n for f, n in
                                ((fA, 'A'), (fB, 'B'), (fD, 'D'), (fE, 'E')) if f) or 'none'
                tot['combo_' + combo] += 1

        # ---- per-state diagnostics ----------------------------------------
        rank_fail_states = 0
        for e in M5 - M2:
            if lab[e] != 1:
                continue
            i = edges.index(e)
            if any(lab[f] == 0 and s2[edges.index(f)] > s2[i] + EPS for f in M2):
                rank_fail_states += 1
                break

        diag_rows.append(dict(
            seed=k[0], variant=k[1], day=k[2],
            n_edges=len(edges), k_t=kt, p_t=p_t,
            local_gap=gap_ref[k]['local_gap'],
            headroom=int(gap_ref[k]['local_gap'] >= 1),
            P_GREEDY=P['GREEDY'], P_F1=P['F1-SCORE'], P_F2=P['F2-SOFT'],
            P_F3=P['F3-OBSERV'], P_F5=P['F5-ORACLE'],
            R_t=R_t, U_t=U_t,
            gap_F5_F2=gap,
            ranking_component=P['F5-ORACLE'] - R_t,
            conflict_component=R_t - P['F2-SOFT'],
            irreducible_matching_cost=U_t - P['F5-ORACLE'],
            topk_max_matching_size=max_matching_size([edges[i] for i in topk_idx]),
            topk_conflicted=int(max_matching_size([edges[i] for i in topk_idx]) < kt),
            f2_rank_fail_state=rank_fail_states,
            sets_equal_F5_F2=int(M2 == M5),
            sets_equal_F5_GREEDY=int(M5 == MG),
            n_missed_oracle_positives=sum(1 for e in M5 - M2 if lab[e] == 1),
            f2_precision=(round(P['F2-SOFT'] / kt, 6) if kt else ''),
            f2_recall=(round(P['F2-SOFT'] / p_t, 6) if p_t else ''),
            regret_F5_minus_F2=gap))

    c.write_jsonl(MO / 'selection_diagnostics.jsonl', diag_rows)
    with open(MO / 'selection_diagnostics.csv', 'w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=list(diag_rows[0])); w.writeheader(); w.writerows(diag_rows)
    with open(MO / 'positive_edge_ranks.csv', 'w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rank_rows[0])); w.writeheader(); w.writerows(rank_rows)
    c.log('wrote selection_diagnostics (%d rows) and positive_edge_ranks (%d rows)'
          % (len(diag_rows), len(rank_rows)))

    agg = dict(
        n_states=len(diag_rows), n_rank_rows=len(rank_rows),
        n_positive_edges_ranked=tot.get('positive', 0),
        sum_gap_F5_F2=sum(r['gap_F5_F2'] for r in diag_rows),
        sum_ranking_component=sum(r['ranking_component'] for r in diag_rows),
        sum_conflict_component=sum(r['conflict_component'] for r in diag_rows),
        sum_irreducible_matching_cost=sum(r['irreducible_matching_cost'] for r in diag_rows),
        missed_positive_primary={k[5:]: v for k, v in tot.items() if k.startswith('mech_')},
        missed_positive_flag_counts_nonexclusive={k[5:]: v for k, v in tot.items() if k.startswith('flag_')},
        missed_positive_flag_combos={k[6:]: v for k, v in tot.items() if k.startswith('combo_')},
        n_missed=tot['missed'],
        n_captured=tot.get('positive', 0) - tot['missed'],
        states_with_conflicted_topk=sum(r['topk_conflicted'] for r in diag_rows),
        states_with_F2_rank_fail=sum(r['f2_rank_fail_state'] for r in diag_rows))
    (MO / 'decomposition_agg.json').write_text(json.dumps(agg, indent=1, sort_keys=True) + '\n',
                                               encoding='utf-8')
    print(json.dumps(agg, indent=1, sort_keys=True))
    c.log('mo_analyze core done (%.1fs)' % (time.time() - t0))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
