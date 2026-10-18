"""Existing-data analysis: counterfactual label structure, diag dynamics, ask headroom.

RESEARCH ONLY: reads existing artifacts, runs no episodes, modifies nothing.
Outputs data_analysis.json next to this file.
"""
import csv, json, statistics, zipfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).parent

# ---------------------------------------------------------------- 1. rows.csv
def rows_analysis():
    path = ROOT / 'research' / 'out_scale800' / 'rows.csv'
    per_world = defaultdict(lambda: {'G': set(), 'R': set()})
    labels = defaultdict(dict)          # (world, pair) -> {policy: (day, label, mutual)}
    n = 0
    by_policy = defaultdict(int)
    by_policy_pos = defaultdict(lambda: defaultdict(int))
    with open(path, newline='', encoding='utf-8') as f:
        rd = csv.DictReader(f)
        for row in rd:
            n += 1
            pol = row['policy']
            by_policy[pol] += 1
            ws = int(row['world_seed']); var = row['variant']
            a, b = row['a'], row['b']
            pair = (a, b) if a < b else (b, a)
            key = (ws, var)
            (per_world[key]['G'] if pol == 'greedy' else per_world[key]['R']).add(pair)
            lab = row['label']
            labels[(ws, var, pair)][pol] = (
                int(row['day']),
                int(lab) if lab not in ('', 'None') else None,
                int(row['label_mutual']) if row['label_mutual'] not in ('', 'None') else None)
            if lab not in ('', 'None'):
                by_policy_pos[pol]['msmi'] += int(lab)
                if row['label_mutual'] not in ('', 'None'):
                    by_policy_pos[pol]['mutual'] += int(row['label_mutual'])

    worlds_both = [k for k, v in per_world.items() if v['G'] and v['R']]
    g_total = sum(len(v['G']) for v in per_world.values())
    r_total = sum(len(v['R']) for v in per_world.values())
    inter = sum(len(v['G'] & v['R']) for v in per_world.values())
    union = sum(len(v['G'] | v['R']) for v in per_world.values())
    # counterfactual label availability: fraction of greedy pairs also labeled by random
    g_cov = []
    same_day = 0; both_day = 0
    agree_m = [0, 0]; agree_u = [0, 0]
    for key, v in per_world.items():
        if not v['G']:
            continue
        cov = len(v['G'] & v['R'])
        g_cov.append(cov / len(v['G']))
        for pair in v['G'] & v['R']:
            lg = labels[key + (pair,)].get('greedy')
            lr = labels[key + (pair,)].get('random')
            if lg and lr:
                both_day += 1
                same_day += (lg[0] == lr[0])
                if lg[1] is not None and lr[1] is not None:
                    agree_u[0] += 1
                    agree_u[1] += (lg[1] == lr[1])
                    agree_m[0] += (lg[1] == 1 and lr[1] == 1)
    # determinism check: same world+pair+same day -> same label?
    det_ok = det_n = 0
    for key, polmap in labels.items():
        if 'greedy' in polmap and 'random' in polmap:
            if polmap['greedy'][0] == polmap['random'][0]:
                det_n += 1
                det_ok += (polmap['greedy'][1] == polmap['random'][1])
    return {
        'rows_total': n,
        'rows_by_policy': dict(by_policy),
        'positives_by_policy': {p: dict(v) for p, v in by_policy_pos.items()},
        'worlds_with_both_policies': len(worlds_both),
        'distinct_pairs_greedy': g_total,
        'distinct_pairs_random': r_total,
        'pair_overlap_g_and_r': inter,
        'pair_union': union,
        'overlap_share_of_greedy': inter / max(1, g_total),
        'greedy_pairs_with_random_counterfactual_label_share_mean': statistics.fmean(g_cov),
        'same_day_among_overlap_pairs': [same_day, both_day],
        'label_agreement_same_pair_any_day': [agree_u[1], agree_u[0]],
        'determinism_same_world_pair_day': [det_ok, det_n],
    }

# ---------------------------------------------------------------- 2. diags
def diag_analysis():
    ddir = ROOT / 'research' / 'round2_promotion_fresh_seeds'
    curves = defaultdict(lambda: defaultdict(list))
    jaccard = []
    for arm in ('frozen', 'intermediate'):
        for seed in range(107, 119):
            p = ddir / f'diag_{arm}_seed{seed}.json'
            if not p.exists():
                continue
            d = json.loads(p.read_text(encoding='utf-8'))
            for variant, ep in d['episodes'].items():
                if 'greedy' in ep and isinstance(ep['greedy'], dict):
                    jaccard.append(ep['greedy'].get('jaccard'))
                for idx, rec in enumerate(ep['days']):
                    m = rec.get('match') or {}; a = rec.get('ask') or {}
                    day = m.get('day', a.get('day', idx))
                    curves['n_members_available'][day].append(m.get('n_members_available'))
                    curves['n_cand'][day].append(m.get('n_cand'))
                    curves['n_selected'][day].append(m.get('n_selected'))
                    curves['greedy_n'][day].append(m.get('greedy_n'))
                    curves['ask_cost'][day].append(a.get('cost'))
                    curves['greedy_overlap_n'][day].append(m.get('greedy_overlap_n'))
    out_curves = {}
    for metric, byday in curves.items():
        out_curves[metric] = {str(day): round(statistics.fmean(v), 3)
                              for day, v in sorted(byday.items())}
    return {'per_day_mean_curves': out_curves,
            'ac_vs_greedy_counterfactual_jaccard_mean':
                round(statistics.fmean([j for j in jaccard if j is not None]), 4),
            'n_episode_day_records': len(jaccard)}

# ---------------------------------------------------------------- 3. ask headroom
def ask_headroom():
    z = zipfile.ZipFile(ROOT / 'research' / 'ask_coverage_audit_package.zip')
    replay = json.loads(z.read('audit_derived/replay_digest.json'))
    mcbd = replay['mean_cost_by_day']
    free = [12 - c for c in mcbd]
    buckets = {
        'days_0_10_free': round(sum(free[0:11]), 1),
        'days_11_21_free': round(sum(free[11:22]), 1),
        'days_22_59_free': round(sum(free[22:60]), 1),
        'total_free_per_episode': round(sum(free), 1),
        'total_spent': round(sum(mcbd), 1),
    }
    return {'mean_cost_by_day': [round(c, 3) for c in mcbd],
            'free_budget_buckets': buckets,
            'exhaust_days_mean': round(statistics.fmean(replay['exhaust_days']), 2)}

def main():
    out = {'rows_counterfactual': rows_analysis(),
           'diag_dynamics': diag_analysis(),
           'ask_headroom': ask_headroom()}
    (HERE / 'data_analysis.json').write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))

if __name__ == '__main__':
    main()
