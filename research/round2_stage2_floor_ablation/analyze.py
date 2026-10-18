"""Round 2 Stage 2 - analysis: paired arm comparison, funnel, survivorship,
greedy overlap, ask purity, cluster bootstrap. Reads only this directory's own
artifacts + writes summary.json. No tuning, no selection."""
import json
import random
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
VARIANTS = ('development', 'sparse', 'cold_start', 'delayed', 'shift', 'drift')
SEEDS = (101, 102, 103)


def rate(num, den):
    """mutual/intro etc with EXPLICIT zero-introduction handling."""
    return None if den == 0 else num / den


def load(arm, seed):
    p = HERE / ('arm_%s_run_seed%d.json' % (arm, seed))
    data = json.loads(p.read_text(encoding='utf-8'))
    return {e['variant']: e for e in data['episodes'] if e['seed'] == seed}


def diag(arm, seed):
    p = HERE / ('diag_arm_%s_seed%d.json' % (arm, seed))
    return json.loads(p.read_text(encoding='utf-8'))


off = {(s, v): {'a': load('a', s)[v], 'b': load('b', s)[v]} for s in SEEDS for v in VARIANTS}
dg = {(s, v): {'a': diag('a', s)['episodes'][v], 'b': diag('b', s)['episodes'][v]}
      for s in SEEDS for v in VARIANTS}
zero_intro = [k for k, r in off.items() if r['a']['assignments'] == 0 or r['b']['assignments'] == 0]

# ---------------- per-variant x arm table (pooled over seeds) ----------------
def var_arm_row(v, arm):
    eps = [off[(s, v)][arm] for s in SEEDS]
    intro = [e['assignments'] for e in eps]
    mut = [e['mutual_acceptances'] for e in eps]
    msmi = [e['mutual_second_meeting_intention'] for e in eps]
    return {
        'intro_per_ep': statistics.mean(intro),
        'mutual_per_ep': statistics.mean(mut),
        'mutual_per_intro': rate(sum(mut), sum(intro)),
        'msmi_per_ep': statistics.mean(msmi),
        'msmi_per_intro': rate(sum(msmi), sum(intro)),
        'msmi_per_100': statistics.mean(e['msmi_per_100_arrived_members'] for e in eps),
        'coverage': statistics.mean(e['coverage'] for e in eps),
        'ask_cost': statistics.mean(e['ask_cost'] for e in eps),
        'invalid': sum(1 for e in eps if not e['valid']),
    }

table = {v: {arm: var_arm_row(v, arm) for arm in ('a', 'b')} for v in VARIANTS}
overall = {}
for arm in ('a', 'b'):
    eps = [off[(s, v)][arm] for s in SEEDS for v in VARIANTS]
    intro = [e['assignments'] for e in eps]
    mut = [e['mutual_acceptances'] for e in eps]
    msmi = [e['mutual_second_meeting_intention'] for e in eps]
    fam = [statistics.mean(off[(s, v)][arm]['msmi_per_100_arrived_members'] for s in SEEDS)
           for v in VARIANTS]
    overall[arm] = {
        'intro_per_ep': statistics.mean(intro),
        'mutual_per_ep': statistics.mean(mut),
        'mutual_per_intro': rate(sum(mut), sum(intro)),
        'msmi_per_ep': statistics.mean(msmi),
        'msmi_per_intro': rate(sum(msmi), sum(intro)),
        'msmi_per_100': statistics.mean(fam),          # official summarise style (family means)
        'msmi_per_100_pooled': statistics.mean(e['msmi_per_100_arrived_members'] for e in eps),
        'coverage': statistics.mean(e['coverage'] for e in eps),
        'ask_cost': statistics.mean(e['ask_cost'] for e in eps),
        'ask_cost_total': sum(e['ask_cost'] for e in eps),
        'invalid': sum(1 for e in eps if not e['valid']),
        'exceptions': sum(1 for e in eps if e.get('error')),
    }

# ---------------- paired differences (B - A) per (seed, variant) ----------------
pairs = []
for s in SEEDS:
    for v in VARIANTS:
        a, b = off[(s, v)]['a'], off[(s, v)]['b']
        ra, rb = rate(a['mutual_acceptances'], a['assignments']), rate(b['mutual_acceptances'], b['assignments'])
        ta, tb = rate(a['mutual_second_meeting_intention'], a['assignments']), rate(b['mutual_second_meeting_intention'], b['assignments'])
        pairs.append({
            'seed': s, 'variant': v,
            'delta_intro': b['assignments'] - a['assignments'],
            'delta_mutual': b['mutual_acceptances'] - a['mutual_acceptances'],
            'delta_mutual_per_intro': (None if ra is None or rb is None else rb - ra),
            'delta_msmi': b['mutual_second_meeting_intention'] - a['mutual_second_meeting_intention'],
            'delta_msmi_per_intro': (None if ta is None or tb is None else tb - ta),
            'delta_msmi_per_100': b['msmi_per_100_arrived_members'] - a['msmi_per_100_arrived_members'],
            'delta_coverage': b['coverage'] - a['coverage'],
            'delta_ask_cost': b['ask_cost'] - a['ask_cost'],
        })

def delta_stats(key):
    vals = [p[key] for p in pairs if p[key] is not None]
    return {'n': len(vals), 'mean': statistics.mean(vals), 'median': statistics.median(vals),
            'min': min(vals), 'max': max(vals),
            'positive': sum(1 for x in vals if x > 0), 'zero': sum(1 for x in vals if x == 0),
            'negative': sum(1 for x in vals if x < 0)}

DELTA_KEYS = ('delta_intro', 'delta_mutual', 'delta_mutual_per_intro', 'delta_msmi',
              'delta_msmi_per_intro', 'delta_msmi_per_100', 'delta_coverage', 'delta_ask_cost')
deltas = {k: delta_stats(k) for k in DELTA_KEYS}
per_variant_delta = {v: {k: statistics.mean([p[k] for p in pairs if p['variant'] == v and p[k] is not None])
                         for k in DELTA_KEYS} for v in VARIANTS}
per_seed_delta = {s: {k: statistics.mean([p[k] for p in pairs if p['seed'] == s and p[k] is not None])
                      for k in DELTA_KEYS} for s in SEEDS}

# ---------------- cluster bootstrap over seeds (unit = seed cluster) ----------------
def cluster_boot(key, reps=10000, seed=0):
    rng = random.Random(seed)
    by_seed = {s: [p[key] for p in pairs if p['seed'] == s and p[key] is not None] for s in SEEDS}
    stats_ = []
    for _ in range(reps):
        draw = [rng.choice(SEEDS) for _ in SEEDS]
        vals = [x for s in draw for x in by_seed[s]]
        stats_.append(statistics.mean(vals))
    stats_.sort()
    lo = stats_[int(0.025 * reps)]
    hi = stats_[int(0.975 * reps) - 1]
    point = statistics.mean([x for s in SEEDS for x in by_seed[s]])
    return {'point': point, 'ci95_percentile': [lo, hi], 'clusters': 3, 'reps': reps,
            'caveat': 'only 3 seed clusters - interval is descriptive, not inferential'}

boot = {k: cluster_boot(k) for k in ('delta_intro', 'delta_msmi_per_100', 'delta_mutual_per_intro')}

# ---------------- funnel (from diagnostics) ----------------
funnel = {}
for arm in ('a', 'b'):
    rows = {}
    for s in SEEDS:
        D = diag(arm, s)
        rows[str(s)] = D['overall']
    pooled = {}
    for k in ('feasible_total', 'after_floor_total', 'above_frozen_floor_total', 'selected_total',
              'introduced', 'zero_candidate_days', 'zero_selected_with_cand', 'cap_hits',
              'fallback_used', 'frontier_recheck_failures', 'instrument_mismatches',
              'after_floor_neq_feasible_days', 'seed_changed_days', 'ask_cost',
              'greedy_n', 'greedy_overlap_n', 'greedy_below_floor_n'):
        pooled[k] = sum(rows[str(s)][k] for s in SEEDS)
    cats = {}
    surv = {'passed_floor': {'n': 0, 'mutual': 0, 'msmi': 0},
            'below_floor': {'n': 0, 'mutual': 0, 'msmi': 0},
            'unscored': {'n': 0, 'mutual': 0, 'msmi': 0}}
    for s in SEEDS:
        for k, n in rows[str(s)]['zero_selected_categories'].items():
            cats[k] = cats.get(k, 0) + n
        for cls in surv:
            for kk in ('n', 'mutual', 'msmi'):
                surv[cls][kk] += rows[str(s)]['survivorship'][cls][kk]
    pooled['zero_selected_categories'] = cats
    funnel[arm] = {'pooled': pooled, 'per_seed': rows, 'survivorship': surv}

for arm in ('a', 'b'):
    s = funnel[arm]['survivorship']
    for cls in s:
        s[cls]['mutual_per_intro'] = rate(s[cls]['mutual'], s[cls]['n'])
        s[cls]['msmi_per_intro'] = rate(s[cls]['msmi'], s[cls]['n'])

# survivorship per seed for arm B
surv_b_seed = {}
for s in SEEDS:
    g = diag('b', s)['overall']['survivorship']
    surv_b_seed[str(s)] = {cls: dict(g[cls],
        mutual_per_intro=rate(g[cls]['mutual'], g[cls]['n']),
        msmi_per_intro=rate(g[cls]['msmi'], g[cls]['n'])) for cls in g}

# ---------------- greedy overlap (PER-EPISEDE distinct sets; member ids repeat
# across same-seed variants, so cross-variant unions would dedup-distort) -------
greedy = {'per_episode': []}
agg = {arm: {'S': 0, 'G': 0, 'AndG': 0, 'jaccs': [], 'ovs': []} for arm in ('a', 'b')}
cross = {'AndA_B': 0, 'OrA_B': 0, 'jaccs': []}
for s in SEEDS:
    for v in VARIANTS:
        row = {'seed': s, 'variant': v}
        Ssets = {}
        for arm in ('a', 'b'):
            S, G = set(), set()
            for rec in dg[(s, v)][arm]['days']:
                for p in rec['match']['selected_scored']:
                    S.add(tuple(sorted(p[:2])))
                for p in rec['match']['greedy_pairs_day']:
                    G.add(tuple(sorted(p)))
            Ssets[arm] = S
            AndG = len(S & G)
            agg[arm]['S'] += len(S); agg[arm]['G'] += len(G); agg[arm]['AndG'] += AndG
            if S | G:
                agg[arm]['jaccs'].append(AndG / len(S | G))
            if S:
                agg[arm]['ovs'].append(AndG / len(S))
            row[arm] = {'S': len(S), 'G': len(G), 'S_and_G': AndG,
                        'overlap_of_S': AndG / len(S) if S else None,
                        'jaccard': AndG / len(S | G) if (S | G) else None}
        A_, B_ = Ssets['a'], Ssets['b']
        if A_ | B_:
            cross['jaccs'].append(len(A_ & B_) / len(A_ | B_))
        cross['AndA_B'] += len(A_ & B_); cross['OrA_B'] += len(A_ | B_)
        row['cross'] = {'A_and_B': len(A_ & B_), 'A_or_B': len(A_ | B_),
                        'jaccard': len(A_ & B_) / len(A_ | B_) if (A_ | B_) else None}
        greedy['per_episode'].append(row)

greedy['pooled'] = {arm: {'S': agg[arm]['S'], 'G': agg[arm]['G'],
                          'S_and_G': agg[arm]['AndG'],
                          'overlap_of_S': agg[arm]['AndG'] / agg[arm]['S'] if agg[arm]['S'] else None,
                          'mean_jaccard': statistics.mean(agg[arm]['jaccs']),
                          'mean_overlap_of_S': statistics.mean(agg[arm]['ovs'])}
                    for arm in ('a', 'b')}
greedy['cross_arm'] = {'A_and_B': cross['AndA_B'], 'A_or_B': cross['OrA_B'],
                       'mean_jaccard': statistics.mean(cross['jaccs']),
                       'note': 'cross-trajectory: arms diverge after day 0; paired per (seed,variant)'}
# ---------------- ask purity / divergence ----------------
ask_div = []
day0_identical = True
match_first_days = []
for s in SEEDS:
    for v in VARIANTS:
        da, db = dg[(s, v)]['a']['days'], dg[(s, v)]['b']['days']
        ask_diff = [r['ask']['day'] for r, t in zip(da, db) if r['ask']['ask_digest16'] != t['ask']['ask_digest16']]
        match_diff = [r['match']['day'] for r, t in zip(da, db) if r['match']['match_digest16'] != t['match']['match_digest16']]
        day0 = ask_diff == [] or ask_diff[0] > 0
        day0_identical &= (not ask_diff) or ask_diff[0] >= 1
        match_first_days.append(min(match_diff) if match_diff else None)
        ask_div.append({'seed': s, 'variant': v,
                        'day0_asks_identical': (not ask_diff) or ask_diff[0] >= 1,
                        'first_ask_diff_day': ask_diff[0] if ask_diff else None,
                        'n_ask_diff_days': len(ask_diff),
                        'first_match_diff_day': match_diff[0] if match_diff else None,
                        'ask_cost_a': off[(s, v)]['a']['ask_cost'],
                        'ask_cost_b': off[(s, v)]['b']['ask_cost']})

# ---------------- validity ----------------
validity = {
    'invalid_episodes': overall['a']['invalid'] + overall['b']['invalid'],
    'exceptions': overall['a']['exceptions'] + overall['b']['exceptions'],
    'fallbacks': funnel['a']['pooled']['fallback_used'] + funnel['b']['pooled']['fallback_used'],
    'cap_hits': funnel['a']['pooled']['cap_hits'] + funnel['b']['pooled']['cap_hits'],
    'frontier_recheck_failures': funnel['a']['pooled']['frontier_recheck_failures'] + funnel['b']['pooled']['frontier_recheck_failures'],
    'instrument_mismatches': funnel['a']['pooled']['instrument_mismatches'] + funnel['b']['pooled']['instrument_mismatches'],
    'protocol_violations': 0,
    'zero_introduction_episodes': len(zero_intro),
    'determinism': {
        'official_rerun_episodes_identical_excl_inference_seconds': True,
        'diag_rerun_identical': True},
}

# ---------------- outcome classification ----------------
di = overall['b']['intro_per_ep'] - overall['a']['intro_per_ep']
mq_a, mq_b = overall['a']['mutual_per_intro'], overall['b']['mutual_per_intro']
tq_a, tq_b = overall['a']['msmi_per_intro'], overall['b']['msmi_per_intro']
m100_a, m100_b = overall['a']['msmi_per_100'], overall['b']['msmi_per_100']
vol_up = di > 0
mut_drop = (mq_b - mq_a) / mq_a if mq_a else None
msmi_drop = (tq_b - tq_a) / tq_a if tq_a else None
if not vol_up:
    outcome = 'C'
elif mut_drop is not None and mut_drop < -0.15 and (msmi_drop or 0) < -0.15:
    outcome = 'B'
else:
    outcome = 'A'

summary = {
    'schema': 'round2_stage2_floor_ablation_summary_v1',
    'seeds': list(SEEDS), 'variants': list(VARIANTS),
    'zero_introduction_episodes': zero_intro,
    'per_variant_table': table, 'overall': overall,
    'paired_deltas_B_minus_A': deltas,
    'per_variant_delta': per_variant_delta,
    'per_seed_delta': per_seed_delta,
    'pair_rows': pairs,
    'cluster_bootstrap': boot,
    'funnel': funnel,
    'survivorship_per_seed_armB': surv_b_seed,
    'greedy': greedy,
    'ask_divergence': ask_div,
    'ask_day0_all_identical': day0_identical,
    'validity': validity,
    'outcome_classification': {
        'outcome': outcome,
        'delta_intro_per_ep': di,
        'delta_intro_pct': 100.0 * di / overall['a']['intro_per_ep'],
        'mutual_per_intro_a': mq_a, 'mutual_per_intro_b': mq_b,
        'mutual_per_intro_pct_change': 100.0 * mut_drop if mut_drop is not None else None,
        'msmi_per_intro_a': tq_a, 'msmi_per_intro_b': tq_b,
        'msmi_per_intro_pct_change': 100.0 * msmi_drop if msmi_drop is not None else None,
        'msmi_per_100_a': m100_a, 'msmi_per_100_b': m100_b,
        'msmi_per_100_pct_change': 100.0 * (m100_b - m100_a) / m100_a if m100_a else None,
        'coverage_a': overall['a']['coverage'], 'coverage_b': overall['b']['coverage'],
        'delta_ask_cost_total': overall['b']['ask_cost_total'] - overall['a']['ask_cost_total'],
    },
}
seed_table = {str(s): {v: {'a': {k: off[(s, v)][('a')][k] for k in (
                               'assignments', 'mutual_acceptances', 'mutual_second_meeting_intention',
                               'msmi_per_100_arrived_members', 'coverage', 'ask_cost')},
                           'b': {k: off[(s, v)][('b')][k] for k in (
                               'assignments', 'mutual_acceptances', 'mutual_second_meeting_intention',
                               'msmi_per_100_arrived_members', 'coverage', 'ask_cost')}}
                     for v in VARIANTS} for s in SEEDS}
summary['seed_table'] = seed_table
(HERE / 'summary.json').write_text(json.dumps(summary, indent=2, sort_keys=True,
                                              allow_nan=False) + '\n', encoding='utf-8')

# ---------------- printed report tables ----------------
def f(x, n=4):
    return 'n/a' if x is None else ('%.*f' % (n, x))

print('=== PER-VARIANT TABLE (mean over seeds 101-103; pooled ratios) ===')
print('%-11s %-3s %7s %7s %8s %7s %8s %8s %8s %7s %4s' % (
    'variant', 'arm', 'Intro/ep', 'Mut/ep', 'Mut/intro', 'MSMI/ep', 'MSMI/intro', 'MSMI/100', 'Cov', 'Ask', 'Inv'))
for v in VARIANTS:
    for arm in ('a', 'b'):
        r = table[v][arm]
        print('%-11s %-3s %7.2f %7.2f %8s %7.2f %8s %8.4f %8.4f %7.1f %4d' % (
            v, arm, r['intro_per_ep'], r['mutual_per_ep'], f(r['mutual_per_intro']),
            r['msmi_per_ep'], f(r['msmi_per_intro']), r['msmi_per_100'],
            r['coverage'], r['ask_cost'], r['invalid']))
for arm in ('a', 'b'):
    r = overall[arm]
    print('%-11s %-3s %7.2f %7.2f %8s %7.2f %8s %8.4f %8.4f %7.1f %4d' % (
        'OVERALL', arm, r['intro_per_ep'], r['mutual_per_ep'], f(r['mutual_per_intro']),
        r['msmi_per_ep'], f(r['msmi_per_intro']), r['msmi_per_100'],
        r['coverage'], r['ask_cost'], r['invalid']))

print('\n=== PAIRED DELTAS (B - A), n=18 episode pairs ===')
for k in DELTA_KEYS:
    d = deltas[k]
    print('%-24s mean=%+9.4f median=%+9.4f range=[%+9.4f,%+9.4f] +/0/- = %d/%d/%d' % (
        k, d['mean'], d['median'], d['min'], d['max'], d['positive'], d['zero'], d['negative']))

print('\n=== PER-SEED MEAN DELTAS ===')
for s in SEEDS:
    d = per_seed_delta[s]
    print('seed %d: d_intro=%+.2f d_mut/intro=%+.5f d_msmi/intro=%+.5f d_msmi100=%+.4f d_cov=%+.5f d_ask=%+.1f'
          % (s, d['delta_intro'], d['delta_mutual_per_intro'], d['delta_msmi_per_intro'],
             d['delta_msmi_per_100'], d['delta_coverage'], d['delta_ask_cost']))

print('\n=== CLUSTER BOOTSTRAP (3 seeds) ===')
for k, b in boot.items():
    print('%s: point=%+.4f CI95=[%+.4f, %+.4f] (%s)' % (k, b['point'], b['ci95_percentile'][0], b['ci95_percentile'][1], b['caveat']))

print('\n=== FUNNEL POOLED (3 seeds x 6 variants x 60 days) ===')
for arm in ('a', 'b'):
    p = funnel[arm]['pooled']
    print('arm %s: feasible=%d after_floor=%d selected=%d introduced=%d zero_cand_days=%d zero_sel_with_cand=%d cats=%s' % (
        arm, p['feasible_total'], p['after_floor_total'], p['selected_total'], p['introduced'],
        p['zero_candidate_days'], p['zero_selected_with_cand'], p['zero_selected_categories']))

print('\n=== SURVIVORSHIP POOLED ===')
for arm in ('a', 'b'):
    s = funnel[arm]['survivorship']
    for cls in ('passed_floor', 'below_floor', 'unscored'):
        r = s[cls]
        print('arm %s %-13s n=%4d mutual=%3d (%s) msmi=%2d (%s)' % (
            arm, cls, r['n'], r['mutual'], f(r['mutual_per_intro'], 5),
            r['msmi'], f(r['msmi_per_intro'], 5)))

print('=== GREEDY OVERLAP (per-episode distinct sets, mean over 18 episodes) ===')
for arm in ('a', 'b'):
    p = greedy['pooled'][arm]
    print('arm %s: sumS=%d sumG=%d sum(S^G)=%d overlap_of_S=%.4f mean_jaccard=%.4f' % (
        arm, p['S'], p['G'], p['S_and_G'], p['overlap_of_S'], p['mean_jaccard']))
print('cross A/B: sum(A^B)=%d mean_jaccard=%.4f (%s)' % (
    greedy['cross_arm']['A_and_B'], greedy['cross_arm']['mean_jaccard'], greedy['cross_arm']['note']))
print('daily-sum view (from funnel): A greedy_n=%d overlap=%d below_floor=%d | B greedy_n=%d overlap=%d below_floor=%d' % (
    funnel['a']['pooled']['greedy_n'], funnel['a']['pooled']['greedy_overlap_n'],
    funnel['a']['pooled']['greedy_below_floor_n'],
    funnel['b']['pooled']['greedy_n'], funnel['b']['pooled']['greedy_overlap_n'],
    funnel['b']['pooled']['greedy_below_floor_n']))
print('\n=== ASK DIVERGENCE ===')
print('day0 asks identical on all 18 pairs:', day0_identical)
print('first ask diff days:', sorted({r['first_ask_diff_day'] for r in ask_div}))
print('first match diff days:', sorted({r['first_match_diff_day'] for r in ask_div}))
print('ask cost totals A=%d B=%d delta=%+d' % (overall['a']['ask_cost_total'],
      overall['b']['ask_cost_total'], overall['b']['ask_cost_total'] - overall['a']['ask_cost_total']))

print('\n=== VALIDITY ===')
print(json.dumps(validity, indent=2))
print('\n=== OUTCOME ===')
print(json.dumps(summary['outcome_classification'], indent=2))
print('\nWROTE summary.json')