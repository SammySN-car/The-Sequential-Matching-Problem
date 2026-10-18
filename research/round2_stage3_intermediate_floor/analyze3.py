"""Round 2 Stage 3 - analysis: three-arm paired comparison, funnel, four-way
survivorship, greedy overlap, ask divergence, cluster bootstrap, determinism.
Reads only this directory's own artifacts + writes summary.json.
No tuning, no selection - all arms reported regardless of outcome
(preregistration.md section 8)."""
import json
import random
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
VARIANTS = ('development', 'sparse', 'cold_start', 'delayed', 'shift', 'drift')
SEEDS = (104, 105, 106)
ARMS = ('frozen', 'intermediate', 'nofloor')
CONTRASTS = (('intermediate', 'frozen'), ('intermediate', 'nofloor'),
             ('nofloor', 'frozen'))
CKEYS = ('if', 'in', 'nf')          # intermediate-frozen, intermediate-nofloor, nofloor-frozen


def rate(num, den):
    return None if den == 0 else num / den


def load(arm, seed):
    p = HERE / ('arm_%s_seed%d.json' % (arm, seed))
    data = json.loads(p.read_text(encoding='utf-8'))
    return {e['variant']: e for e in data['episodes'] if e['seed'] == seed}


def diag(arm, seed):
    p = HERE / ('diag_arm_%s_seed%d.json' % (arm, seed))
    return json.loads(p.read_text(encoding='utf-8'))


off = {(s, v): {a: load(a, s)[v] for a in ARMS} for s in SEEDS for v in VARIANTS}
dg = {(s, v): {a: diag(a, s)['episodes'][v] for a in ARMS} for s in SEEDS for v in VARIANTS}
zero_intro = [k for k, r in off.items() if any(r[a]['assignments'] == 0 for a in ARMS)]

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

table = {v: {arm: var_arm_row(v, arm) for arm in ARMS} for v in VARIANTS}
overall = {}
for arm in ARMS:
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

# ---------------- paired differences, three contrasts, per (seed, variant) ----------------
pairs = []
for s in SEEDS:
    for v in VARIANTS:
        row = {'seed': s, 'variant': v}
        for ck, (x, y) in zip(CKEYS, CONTRASTS):        # delta = x - y
            a, b = off[(s, v)][x], off[(s, v)][y]
            ra, rb = rate(a['mutual_acceptances'], a['assignments']), rate(b['mutual_acceptances'], b['assignments'])
            ta, tb = rate(a['mutual_second_meeting_intention'], a['assignments']), rate(b['mutual_second_meeting_intention'], b['assignments'])
            row['delta_intro_' + ck] = a['assignments'] - b['assignments']
            row['delta_mutual_' + ck] = a['mutual_acceptances'] - b['mutual_acceptances']
            row['delta_mutual_per_intro_' + ck] = (None if ra is None or rb is None else ra - rb)
            row['delta_msmi_' + ck] = a['mutual_second_meeting_intention'] - b['mutual_second_meeting_intention']
            row['delta_msmi_per_intro_' + ck] = (None if ta is None or tb is None else ta - tb)
            row['delta_msmi_per_100_' + ck] = a['msmi_per_100_arrived_members'] - b['msmi_per_100_arrived_members']
            row['delta_coverage_' + ck] = a['coverage'] - b['coverage']
            row['delta_ask_cost_' + ck] = a['ask_cost'] - b['ask_cost']
        pairs.append(row)

BASE_KEYS = ('delta_intro', 'delta_mutual', 'delta_mutual_per_intro', 'delta_msmi',
             'delta_msmi_per_intro', 'delta_msmi_per_100', 'delta_coverage', 'delta_ask_cost')


def delta_stats(key):
    vals = [p[key] for p in pairs if p.get(key) is not None]
    return {'n': len(vals), 'mean': statistics.mean(vals), 'median': statistics.median(vals),
            'min': min(vals), 'max': max(vals),
            'positive': sum(1 for x in vals if x > 0), 'zero': sum(1 for x in vals if x == 0),
            'negative': sum(1 for x in vals if x < 0)}


deltas = {ck: {k + '_' + ck: delta_stats(k + '_' + ck) for k in BASE_KEYS} for ck in CKEYS}
per_variant_delta = {ck: {v: {k: statistics.mean([p[k + '_' + ck] for p in pairs
                                                  if p['variant'] == v and p.get(k + '_' + ck) is not None])
                              for k in BASE_KEYS} for v in VARIANTS} for ck in CKEYS}
per_seed_delta = {ck: {s: {k: statistics.mean([p[k + '_' + ck] for p in pairs
                                               if p['seed'] == s and p.get(k + '_' + ck) is not None])
                           for k in BASE_KEYS} for s in SEEDS} for ck in CKEYS}

# ---------------- cluster bootstrap over seeds (unit = seed cluster) ----------------
def cluster_boot(key, reps=10000, seed=0):
    rng = random.Random(seed)
    by_seed = {s: [p[key] for p in pairs if p['seed'] == s and p.get(key) is not None] for s in SEEDS}
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


boot = {ck: {k: cluster_boot(k + '_' + ck)
             for k in ('delta_intro', 'delta_msmi_per_100', 'delta_mutual_per_intro')}
        for ck in CKEYS}

# ---------------- funnel (from diagnostics) ----------------
funnel = {}
for arm in ARMS:
    rows = {str(s): diag(arm, s)['overall'] for s in SEEDS}
    pooled = {}
    for k in ('feasible_total', 'after_floor_total', 'above_frozen_floor_total',
              'above_intermediate_floor_total', 'selected_total', 'introduced',
              'zero_candidate_days', 'zero_selected_with_cand', 'cap_hits',
              'fallback_used', 'frontier_recheck_failures', 'instrument_mismatches',
              'after_floor_neq_feasible_days', 'seed_changed_days', 'ask_cost',
              'greedy_n', 'greedy_overlap_n', 'greedy_below_floor_n'):
        pooled[k] = sum(rows[str(s)][k] for s in SEEDS)
    cats = {}
    surv = {cls: {'n': 0, 'mutual': 0, 'msmi': 0}
            for cls in ('ge_frozen', 'mid_band', 'lt_intermediate', 'unscored')}
    for s in SEEDS:
        for k, n in rows[str(s)]['zero_selected_categories'].items():
            cats[k] = cats.get(k, 0) + n
        for cls in surv:
            for kk in ('n', 'mutual', 'msmi'):
                surv[cls][kk] += rows[str(s)]['survivorship'][cls][kk]
    pooled['zero_selected_categories'] = cats
    for cls in surv:
        surv[cls]['mutual_per_intro'] = rate(surv[cls]['mutual'], surv[cls]['n'])
        surv[cls]['msmi_per_intro'] = rate(surv[cls]['msmi'], surv[cls]['n'])
    funnel[arm] = {'pooled': pooled, 'per_seed': rows, 'survivorship': surv}

# survivorship per seed (all arms)
surv_seed = {str(s): {arm: {cls: dict(diag(arm, s)['overall']['survivorship'][cls],
                                      mutual_per_intro=rate(diag(arm, s)['overall']['survivorship'][cls]['mutual'],
                                                            diag(arm, s)['overall']['survivorship'][cls]['n']),
                                      msmi_per_intro=rate(diag(arm, s)['overall']['survivorship'][cls]['msmi'],
                                                          diag(arm, s)['overall']['survivorship'][cls]['n']))
                            for cls in ('ge_frozen', 'mid_band', 'lt_intermediate', 'unscored')}
                     for arm in ARMS} for s in SEEDS}

# ---------------- greedy overlap (PER-EPISODE distinct sets) ----------------
greedy = {'per_episode': []}
agg = {arm: {'S': 0, 'G': 0, 'AndG': 0, 'jaccs': [], 'ovs': []} for arm in ARMS}
cross = {ck: {'And': 0, 'Or': 0, 'jaccs': []} for ck in CKEYS}
for s in SEEDS:
    for v in VARIANTS:
        row = {'seed': s, 'variant': v}
        Ssets = {}
        for arm in ARMS:
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
        for ck, (x, y) in zip(CKEYS, CONTRASTS):
            X, Y = Ssets[x], Ssets[y]
            if X | Y:
                cross[ck]['jaccs'].append(len(X & Y) / len(X | Y))
            cross[ck]['And'] += len(X & Y); cross[ck]['Or'] += len(X | Y)
            row['cross_' + ck] = {'and': len(X & Y), 'or': len(X | Y),
                                  'jaccard': len(X & Y) / len(X | Y) if (X | Y) else None}
        greedy['per_episode'].append(row)

greedy['pooled'] = {arm: {'S': agg[arm]['S'], 'G': agg[arm]['G'],
                          'S_and_G': agg[arm]['AndG'],
                          'overlap_of_S': agg[arm]['AndG'] / agg[arm]['S'] if agg[arm]['S'] else None,
                          'mean_jaccard': statistics.mean(agg[arm]['jaccs']),
                          'mean_overlap_of_S': statistics.mean(agg[arm]['ovs'])}
                    for arm in ARMS}
greedy['cross_contrasts'] = {ck: {'and': cross[ck]['And'], 'or': cross[ck]['Or'],
                                  'mean_jaccard': statistics.mean(cross[ck]['jaccs']),
                                  'note': 'cross-trajectory: arms diverge once floors differ; paired per (seed,variant)'}
                             for ck in CKEYS}

# ---------------- ask divergence (pairwise, three contrasts) ----------------
ask_div = []
day0_all = {ck: True for ck in CKEYS}
for s in SEEDS:
    for v in VARIANTS:
        for ck, (x, y) in zip(CKEYS, CONTRASTS):
            dx, dy = dg[(s, v)][x]['days'], dg[(s, v)][y]['days']
            ask_diff = [r['ask']['day'] for r, t in zip(dx, dy) if r['ask']['ask_digest16'] != t['ask']['ask_digest16']]
            match_diff = [r['match']['day'] for r, t in zip(dx, dy) if r['match']['match_digest16'] != t['match']['match_digest16']]
            day0_ok = (not ask_diff) or ask_diff[0] >= 1
            day0_all[ck] &= day0_ok
            ask_div.append({'seed': s, 'variant': v, 'contrast': ck,
                            'day0_asks_identical': day0_ok,
                            'first_ask_diff_day': ask_diff[0] if ask_diff else None,
                            'n_ask_diff_days': len(ask_diff),
                            'first_match_diff_day': match_diff[0] if match_diff else None,
                            'ask_cost_x': off[(s, v)][x]['ask_cost'],
                            'ask_cost_y': off[(s, v)][y]['ask_cost']})

# ---------------- determinism: official rerun (intermediate seed 104) ----------------
rer_path = HERE / 'arm_intermediate_seed104_rerun.json'
det = {'rerun_file_present': rer_path.exists()}
if rer_path.exists():
    orig = json.loads((HERE / 'arm_intermediate_seed104.json').read_text(encoding='utf-8'))
    rer = json.loads(rer_path.read_text(encoding='utf-8'))
    keyf = lambda e: (e['seed'], e['variant'])
    ro = {keyf(e): e for e in orig['episodes']}
    fields = ('assignments', 'mutual_acceptances', 'mutual_second_meeting_intention',
              'msmi_per_100_arrived_members', 'coverage', 'ask_cost', 'action_sha256', 'valid')
    bad = [keyf(e) for e in rer['episodes']
           if any(ro[keyf(e)][f] != e[f] for f in fields)]
    det['episodes_compared'] = len(rer['episodes'])
    det['mismatched_episodes_excl_inference_seconds'] = bad
    det['identical_excl_inference_seconds'] = not bad
    det['primary_score_match'] = (orig['summary']['primary_score'] == rer['summary']['primary_score'])

# ---------------- validity ----------------
validity = {
    'invalid_episodes': sum(overall[a]['invalid'] for a in ARMS),
    'exceptions': sum(overall[a]['exceptions'] for a in ARMS),
    'fallbacks': sum(funnel[a]['pooled']['fallback_used'] for a in ARMS),
    'cap_hits': sum(funnel[a]['pooled']['cap_hits'] for a in ARMS),
    'frontier_recheck_failures': sum(funnel[a]['pooled']['frontier_recheck_failures'] for a in ARMS),
    'instrument_mismatches': sum(funnel[a]['pooled']['instrument_mismatches'] for a in ARMS),
    'all_fidelity_ok': all(diag(a, s)['all_fidelity_ok'] for a in ARMS for s in SEEDS),
    'protocol_violations': 0,
    'zero_introduction_episodes': len(zero_intro),
    'determinism': det,
}

# ---------------- point-estimate dominance signals (DESCRIPTIVE ONLY) ----------------
prim = {a: overall[a]['msmi_per_100'] for a in ARMS}
vol = {a: overall[a]['intro_per_ep'] for a in ARMS}
flags = {
    'primary_intermediate_ge_frozen': prim['intermediate'] >= prim['frozen'],
    'primary_intermediate_ge_nofloor': prim['intermediate'] >= prim['nofloor'],
    'intro_intermediate_ge_frozen': vol['intermediate'] >= vol['frozen'],
    'intro_intermediate_le_nofloor': vol['intermediate'] <= vol['nofloor'],
}
flags['favorable_signal_all'] = (flags['primary_intermediate_ge_frozen']
                                 and flags['primary_intermediate_ge_nofloor']
                                 and flags['intro_intermediate_ge_frozen'])
dominance = {'point_estimates': flags,
             'primary': prim, 'intro_per_ep': vol,
             'discipline': 'DESCRIPTIVE signal only; per preregistration.md section 8 threshold '
                           'exploration ENDS after this experiment under any outcome; this flag '
                           'never triggers another threshold iteration.'}

summary = {
    'schema': 'round2_stage3_intermediate_floor_summary_v1',
    'seeds': list(SEEDS), 'variants': list(VARIANTS), 'arms': list(ARMS),
    'floor': 0.007905174015296758, 'intermediate_floor': 0.003952587007648379,
    'zero_introduction_episodes': zero_intro,
    'per_variant_table': table, 'overall': overall,
    'paired_deltas': deltas,
    'per_variant_delta': per_variant_delta,
    'per_seed_delta': per_seed_delta,
    'pair_rows': pairs,
    'cluster_bootstrap': boot,
    'funnel': funnel,
    'survivorship_per_seed': surv_seed,
    'greedy': greedy,
    'ask_divergence': ask_div,
    'ask_day0_all_identical_by_contrast': day0_all,
    'validity': validity,
    'dominance_signals': dominance,
}
seed_table = {str(s): {v: {a: {k: off[(s, v)][a][k] for k in (
                           'assignments', 'mutual_acceptances', 'mutual_second_meeting_intention',
                           'msmi_per_100_arrived_members', 'coverage', 'ask_cost')}
                       for a in ARMS}
                  for v in VARIANTS} for s in SEEDS}
summary['seed_table'] = seed_table
(HERE / 'summary.json').write_text(json.dumps(summary, indent=2, sort_keys=True,
                                              allow_nan=False) + '\n', encoding='utf-8')

# ---------------- printed report tables ----------------
def f(x, n=4):
    return 'n/a' if x is None else ('%.*f' % (n, x))


print('=== PER-VARIANT TABLE (mean over seeds 104-106; pooled ratios) ===')
print('%-11s %-12s %8s %7s %8s %7s %8s %8s %7s %7s %4s' % (
    'variant', 'arm', 'Intro/ep', 'Mut/ep', 'Mut/intro', 'MSMI/ep', 'MSMI/intro', 'MSMI/100', 'Cov', 'Ask', 'Inv'))
for v in VARIANTS:
    for arm in ARMS:
        r = table[v][arm]
        print('%-11s %-12s %8.2f %7.2f %8s %7.2f %8s %8.4f %7.4f %7.1f %4d' % (
            v, arm, r['intro_per_ep'], r['mutual_per_ep'], f(r['mutual_per_intro']),
            r['msmi_per_ep'], f(r['msmi_per_intro']), r['msmi_per_100'],
            r['coverage'], r['ask_cost'], r['invalid']))
for arm in ARMS:
    r = overall[arm]
    print('%-11s %-12s %8.2f %7.2f %8s %7.2f %8s %8.4f %7.4f %7.1f %4d' % (
        'OVERALL', arm, r['intro_per_ep'], r['mutual_per_ep'], f(r['mutual_per_intro']),
        r['msmi_per_ep'], f(r['msmi_per_intro']), r['msmi_per_100'],
        r['coverage'], r['ask_cost'], r['invalid']))

print('\n=== PAIRED DELTAS (first - second), n=18 pairs each ===')
for ck, (x, y) in zip(CKEYS, CONTRASTS):
    print('--- %s - %s ---' % (x, y))
    for k in BASE_KEYS:
        d = deltas[ck][k + '_' + ck]
        print('%-24s mean=%+9.4f median=%+9.4f range=[%+9.4f,%+9.4f] +/0/- = %d/%d/%d' % (
            k, d['mean'], d['median'], d['min'], d['max'], d['positive'], d['zero'], d['negative']))

print('\n=== PER-SEED MEAN DELTAS ===')
for ck in CKEYS:
    for s in SEEDS:
        d = per_seed_delta[ck][s]
        print('%s seed %d: d_intro=%+.2f d_mut/intro=%+.5f d_msmi/intro=%+.5f d_msmi100=%+.4f d_cov=%+.5f d_ask=%+.1f'
              % (ck, s, d['delta_intro'], d['delta_mutual_per_intro'], d['delta_msmi_per_intro'],
                 d['delta_msmi_per_100'], d['delta_coverage'], d['delta_ask_cost']))

print('\n=== CLUSTER BOOTSTRAP (3 seeds; DESCRIPTIVE ONLY) ===')
for ck in CKEYS:
    for k, b in boot[ck].items():
        print('%s %s: point=%+.4f CI95=[%+.4f, %+.4f]' % (ck, k, b['point'],
              b['ci95_percentile'][0], b['ci95_percentile'][1]))

print('\n=== FUNNEL POOLED (3 seeds x 6 variants x 60 days) ===')
for arm in ARMS:
    p = funnel[arm]['pooled']
    print('arm %-12s feasible=%d after_arm_floor=%d >=frozen=%d >=intermediate=%d selected=%d introduced=%d zero_cand=%d zero_sel=%d cats=%s' % (
        arm, p['feasible_total'], p['after_floor_total'], p['above_frozen_floor_total'],
        p['above_intermediate_floor_total'], p['selected_total'], p['introduced'],
        p['zero_candidate_days'], p['zero_selected_with_cand'], p['zero_selected_categories']))

print('\n=== SURVIVORSHIP POOLED (4-way by score band) ===')
for arm in ARMS:
    s = funnel[arm]['survivorship']
    for cls in ('ge_frozen', 'mid_band', 'lt_intermediate', 'unscored'):
        r = s[cls]
        print('arm %-12s %-15s n=%4d mutual=%3d (%s) msmi=%2d (%s)' % (
            arm, cls, r['n'], r['mutual'], f(r['mutual_per_intro'], 5),
            r['msmi'], f(r['msmi_per_intro'], 5)))

print('\n=== GREEDY OVERLAP (per-episode distinct sets, mean over 18 episodes) ===')
for arm in ARMS:
    p = greedy['pooled'][arm]
    print('arm %-12s sumS=%d sumG=%d sum(S^G)=%d overlap_of_S=%.4f mean_jaccard=%.4f' % (
        arm, p['S'], p['G'], p['S_and_G'], p['overlap_of_S'], p['mean_jaccard']))

print('\n=== ASK DIVERGENCE ===')
for ck in CKEYS:
    rows = [r for r in ask_div if r['contrast'] == ck]
    print('contrast %s: day0_identical_all=%s first_ask_diff_days=%s first_match_diff_days=%s' % (
        ck, day0_all[ck], sorted({r['first_ask_diff_day'] for r in rows}),
        sorted({r['first_match_diff_day'] for r in rows})))
for arm in ARMS:
    print('ask cost total %s = %d' % (arm, overall[arm]['ask_cost_total']))

print('\n=== VALIDITY ===')
print(json.dumps(validity, indent=2))
print('\n=== DOMINANCE SIGNALS (descriptive) ===')
print(json.dumps(dominance, indent=2))
print('\nWROTE summary.json')