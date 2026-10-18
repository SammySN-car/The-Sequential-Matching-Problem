"""Produce gap_decomposition.csv: mechanism counts, overall and by stratum."""
import csv, json, sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
MO = HERE.parent
sys.path.insert(0, str(HERE.parent.parent / 'round2_decision_ceiling' / 'scripts'))
import ce_common as c  # noqa: E402

rows = [json.loads(l) for l in open(MO / 'selection_diagnostics.jsonl', encoding='utf-8')]
er = list(csv.DictReader(open(MO / 'positive_edge_ranks.csv', encoding='utf-8')))


def agg(sub, label):
    return dict(
        stratum=label,
        n_states=len(sub),
        sum_k_t=sum(r['k_t'] for r in sub),
        sum_p_t=sum(r['p_t'] for r in sub),
        P_GREEDY=sum(r['P_GREEDY'] for r in sub),
        P_F1=sum(r['P_F1'] for r in sub),
        P_F2=sum(r['P_F2'] for r in sub),
        P_F5=sum(r['P_F5'] for r in sub),
        R_t=sum(r['R_t'] for r in sub),
        U_t=sum(r['U_t'] for r in sub),
        gap_F5_F2=sum(r['gap_F5_F2'] for r in sub),
        ranking_component=sum(r['ranking_component'] for r in sub),
        conflict_component=sum(r['conflict_component'] for r in sub),
        irreducible_matching_cost=sum(r['irreducible_matching_cost'] for r in sub),
        n_states_ranking_pos=sum(1 for r in sub if r['ranking_component'] > 0),
        n_states_conflict_pos=sum(1 for r in sub if r['conflict_component'] > 0),
        n_states_conflict_neg=sum(1 for r in sub if r['conflict_component'] < 0),
        n_F2_gt_GREEDY=sum(1 for r in sub if r['P_F2'] > r['P_GREEDY']),
        n_F2_eq_GREEDY=sum(1 for r in sub if r['P_F2'] == r['P_GREEDY']),
        n_F2_lt_GREEDY=sum(1 for r in sub if r['P_F2'] < r['P_GREEDY']),
        n_F2_gt_F5=sum(1 for r in sub if r['P_F2'] > r['P_F5']),
        positive_edges=len([r for r in er if True]),
    )


out = [agg(rows, 'ALL'),
       agg([r for r in rows if r['headroom']], 'HEADROOM_local_gap_ge_1'),
       agg([r for r in rows if not r['headroom']], 'NONHEADROOM_local_gap_0')]

# per-variant
for v in sorted(set(r['variant'] for r in rows)):
    out.append(agg([r for r in rows if r['variant'] == v], 'VARIANT_' + v))

# mechanism flag counts per stratum from positive_edge_ranks.csv
def flag_block(sub, label):
    d = dict(stratum=label, n_positive_edges=len(sub),
             n_captured_F2=sum(1 for r in sub if r['f2_selected'] == '1'),
             n_missed=sum(1 for r in sub if r['missed_oracle_positive'] == '1'),
             n_coverable=sum(1 for r in sub if r['coverable_at_kt'] == '1'))
    for f, nm in (('flag_A_ranking_failure', 'A'), ('flag_B_matching_conflict', 'B'),
                  ('flag_D_weak_separation', 'D'), ('flag_E_blocked_by_positive', 'E')):
        d['missed_flag_' + nm] = sum(1 for r in sub if r['missed_oracle_positive'] == '1'
                                     and r[f] == '1')
    d['missed_with_neg_outranking'] = sum(
        1 for r in sub if r['missed_oracle_positive'] == '1'
        and int(r['n_F2_negatives_outranking']) > 0)
    d['missed_with_vertex_conflict'] = sum(
        1 for r in sub if r['missed_oracle_positive'] == '1'
        and int(r['n_conflicting_with_F2']) > 0)
    return d

mech = [flag_block(er, 'ALL'),
        flag_block([r for r in er if int(float(r['state_local_gap'])) >= 1], 'HEADROOM'),
        flag_block([r for r in er if int(float(r['state_local_gap'])) == 0], 'NONHEADROOM')]

with open(MO / 'gap_decomposition.csv', 'w', newline='', encoding='utf-8') as fh:
    w = csv.DictWriter(fh, fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
with open(MO / 'mechanism_flags.csv', 'w', newline='', encoding='utf-8') as fh:
    w = csv.DictWriter(fh, fieldnames=list(mech[0])); w.writeheader(); w.writerows(mech)
c.log('wrote gap_decomposition.csv (%d rows) and mechanism_flags.csv (%d rows)'
      % (len(out), len(mech)))
for r in out[:3]:
    print(r['stratum'], 'gap=', r['gap_F5_F2'], 'rank=', r['ranking_component'],
          'conf=', r['conflict_component'])
