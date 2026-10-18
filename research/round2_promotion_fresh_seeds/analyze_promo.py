"""Analysis for round2 promotion fresh-seed evaluation -> summary.json.

Deterministic; cluster bootstrap unit = seed (12 clusters), 10000 reps,
percentile CI (same methodology family as Stage 2/3 analyze scripts).
"""
import json
import random
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))
import evaluate  # noqa: E402

SEEDS = list(range(107, 119))
VARIANTS = ('development', 'sparse', 'cold_start', 'delayed', 'shift', 'drift')
ARMS = ('greedy', 'original', 'floorhalf')
ARM_FILE = {'greedy': 'arm_greedy', 'original': 'arm_original',
            'floorhalf': 'arm_floorhalf'}
DIAG_FILE = {'original': 'diag_frozen', 'floorhalf': 'diag_intermediate'}
LABEL = {'floorhalf': 'C floor/2 (candidate)', 'original': 'B original floor',
         'greedy': 'A greedy (reference)'}
REPS = 10000

KEYS = ['msmi_per_100_arrived_members', 'assignments',
        'mutual_acceptances_per_100', 'mutual_per_intro', 'coverage',
        'ask_cost', 'intro_per_100_arrived', 'msmi_per_100_intro',
        'date_rate_per_100_intro']


def derive(ep):
    a = max(1, ep['assignments'])
    return {
        'msmi_per_100_arrived_members': ep['msmi_per_100_arrived_members'],
        'assignments': ep['assignments'],
        'mutual_acceptances_per_100': ep['mutual_acceptances_per_100'],
        'mutual_per_intro': ep['mutual_acceptances'] / a,
        'coverage': ep['coverage'],
        'ask_cost': ep['ask_cost'],
        'intro_per_100_arrived': 100.0 * ep['assignments'] / max(1, ep['arrived_members']),
        'msmi_per_100_intro': 100.0 * ep['mutual_second_meeting_intention'] / a,
        'date_rate_per_100_intro': 100.0 * ep['dates'] / a,
    }


def cluster_ci(per_seed, rng_seed):
    """per_seed: {seed: [world deltas]} -> percentile CI of pooled mean."""
    seeds = sorted(per_seed)
    rng = random.Random(rng_seed)
    vals = []
    for _ in range(REPS):
        draw = [rng.choice(seeds) for _ in seeds]
        flat = [v for s in draw for v in per_seed[s]]
        vals.append(statistics.mean(flat))
    vals.sort()
    return [round(vals[int(0.025 * REPS)], 6), round(vals[int(0.975 * REPS) - 1], 6)]


def simple_ci(vals, rng_seed):
    rng = random.Random(rng_seed)
    n = len(vals)
    means = []
    for _ in range(REPS):
        means.append(statistics.mean(vals[rng.randrange(n)] for _ in range(n)))
    means.sort()
    return [round(means[int(0.025 * REPS)], 6), round(means[int(0.975 * REPS) - 1], 6)]


def ratio_ci(pairs, rng_seed):
    """pairs: {seed: [(num, den), ...]} -> CI of ratio of pooled means."""
    seeds = sorted(pairs)
    rng = random.Random(rng_seed)
    out = []
    for _ in range(REPS):
        draw = [rng.choice(seeds) for _ in seeds]
        flat = [p for s in draw for p in pairs[s]]
        nb = statistics.mean(p[0] for p in flat)
        db = statistics.mean(p[1] for p in flat)
        out.append((nb / db - 1.0) * 100.0 if db else 0.0)
    out.sort()
    return [round(out[int(0.025 * REPS)], 4), round(out[int(0.975 * REPS) - 1], 4)]


def wt_l(deltas):
    w = sum(1 for d in deltas if d > 1e-12)
    l = sum(1 for d in deltas if d < -1e-12)
    return {'wins': w, 'ties': len(deltas) - w - l, 'losses': l}


def load_worlds():
    """worlds[(arm, seed, variant)] = derived metrics dict."""
    worlds = {}
    for arm in ARMS:
        for s in SEEDS:
            d = json.loads((HERE / ('%s_seed%d.json' % (ARM_FILE[arm], s))).read_text(encoding='utf-8'))
            assert len(d['episodes']) == 6, (arm, s)
            for ep in d['episodes']:
                assert ep['valid'], (arm, s, ep['variant'])
                worlds[(arm, s, ep['variant'])] = derive(ep)
    return worlds


def main():
    out = {'schema': 'round2_promotion_summary_v1',
           'generated': time.strftime('%Y-%m-%d %H:%M:%S'),
           'design': {
               'seeds': SEEDS, 'variants': list(VARIANTS), 'arms': list(ARMS),
               'worlds_per_arm': len(SEEDS) * len(VARIANTS),
               'official_episodes': len(SEEDS) * len(VARIANTS) * len(ARMS),
               'primary_metric': 'msmi_per_100_arrived_members via evaluate.summarise',
               'bootstrap': {'unit': 'seed cluster', 'reps': REPS,
                             'ci': 'percentile 95%', 'method_family':
                             'same as Stage 2/3 analyze scripts'},
               'metric_definitions': {
                   'mutual_per_intro': 'mutual_acceptances / assignments',
                   'intro_per_100_arrived': '100 * assignments / arrived_members',
                   'msmi_per_100_intro': '100 * msmi / assignments',
                   'date_rate_per_100_intro': '100 * dates / assignments'}},
           'round1_reference': {
               'greedy_primary_seeds_101_103': 0.389,
               'note': 'Round 1 greedy on DIFFERENT seeds; only within-fresh-'
                       'seed arm comparisons are inferentially comparable'}}

    worlds = load_worlds()

    # ---------- official per-arm summaries (evaluate.summarise) ----------
    per_arm = {}
    for arm in ARMS:
        rows = []
        for s in SEEDS:
            d = json.loads((HERE / ('%s_seed%d.json' % (ARM_FILE[arm], s))).read_text(encoding='utf-8'))
            rows.extend(d['episodes'])
        summ = evaluate.summarise(rows)
        pool = [worlds[(arm, s, v)] for s in SEEDS for v in VARIANTS]
        per_arm[arm] = {
            'label': LABEL[arm],
            'primary_score_official': summ['primary_score'],
            'official_overall': summ['overall'],
            'scenario_means': summ['scenario_means'],
            'pooled_72': {k: round(statistics.mean(p[k] for p in pool), 6)
                          for k in KEYS},
            'pooled_72_median': {k: round(statistics.median(p[k] for p in pool), 6)
                                 for k in KEYS},
            'inference_seconds_mean': round(summ['overall']['inference_seconds'], 3),
        }
    out['official_per_arm'] = per_arm

    # ---------- paired contrasts ----------
    contrast_defs = [('floorhalf_minus_original', 'floorhalf', 'original'),
                     ('floorhalf_minus_greedy', 'floorhalf', 'greedy'),
                     ('original_minus_greedy', 'original', 'greedy')]
    contrasts = {}
    rng_i = 0
    for name, hi, lo in contrast_defs:
        c = {}
        for k in KEYS:
            per_seed = defaultdict(list)
            all_d = []
            for s in SEEDS:
                for v in VARIANTS:
                    d = worlds[(hi, s, v)][k] - worlds[(lo, s, v)][k]
                    per_seed[s].append(d)
                    all_d.append(d)
            rng_i += 1
            seed_deltas = {s: statistics.mean(per_seed[s]) for s in SEEDS}
            c[k] = {
                'mean': round(statistics.mean(all_d), 6),
                'median': round(statistics.median(all_d), 6),
                'min': round(min(all_d), 6), 'max': round(max(all_d), 6),
                'ci95_cluster': cluster_ci(per_seed, 5000 + rng_i),
                'worlds': wt_l(all_d),
                'seed_level': {
                    'mean': round(statistics.mean(seed_deltas.values()), 6),
                    'median': round(statistics.median(seed_deltas.values()), 6),
                    'ci95': simple_ci(list(seed_deltas.values()), 9000 + rng_i),
                    'wt_l': wt_l(list(seed_deltas.values())),
                    'per_seed': {str(s): round(seed_deltas[s], 6) for s in SEEDS},
                },
            }
        contrasts[name] = c
    out['paired_contrasts'] = contrasts

    # ---------- 9. volume confirmation (C vs B, introductions) ----------
    vkey = 'assignments'
    per_seed_v = defaultdict(list)
    vd = []
    for s in SEEDS:
        for v in VARIANTS:
            d = worlds[('floorhalf', s, v)][vkey] - worlds[('original', s, v)][vkey]
            per_seed_v[s].append(d)
            vd.append(d)
    seed_v = {s: statistics.mean(per_seed_v[s]) for s in SEEDS}
    out['volume_confirmation'] = {
        'criterion_from_prior_research': 'C > B introductions in >= 80% of 72 paired worlds',
        'worlds': wt_l(vd), 'n_worlds': 72,
        'pct_wins': round(100.0 * wt_l(vd)['wins'] / 72, 2),
        'meets_80pct': wt_l(vd)['wins'] / 72 >= 0.80,
        'mean_delta': round(statistics.mean(vd), 4),
        'median_delta': round(statistics.median(vd), 4),
        'ci95_cluster': cluster_ci(per_seed_v, 21),
        'seed_level_wt_l': wt_l(list(seed_v.values())),
        'per_seed_mean_delta': {str(s): round(seed_v[s], 4) for s in SEEDS},
        'totals_per_arm': {a: int(sum(worlds[(a, s, v)]['assignments']
                                      for s in SEEDS for v in VARIANTS))
                           for a in ARMS},
    }

    # ---------- 10. mutual no-harm (C vs B, mutual/100) ----------
    mkey = 'mutual_acceptances_per_100'
    per_seed_m = defaultdict(list)
    md = []
    ratio_pairs = defaultdict(list)
    for s in SEEDS:
        for v in VARIANTS:
            c_m = worlds[('floorhalf', s, v)][mkey]
            b_m = worlds[('original', s, v)][mkey]
            per_seed_m[s].append(c_m - b_m)
            md.append(c_m - b_m)
            ratio_pairs[s].append((c_m, b_m))
    c_mean = per_arm['floorhalf']['pooled_72'][mkey]
    b_mean = per_arm['original']['pooled_72'][mkey]
    out['mutual_no_harm'] = {
        'warning_threshold_from_prior_research': '-8% relative degradation (reference)',
        'floorhalf_mean_per_100': c_mean, 'original_mean_per_100': b_mean,
        'relative_change_pct': round((c_mean / b_mean - 1.0) * 100.0, 3),
        'relative_change_ci95': ratio_ci(ratio_pairs, 42),
        'paired_diff_mean': round(statistics.mean(md), 6),
        'paired_diff_ci95_cluster': cluster_ci(per_seed_m, 43),
        'worlds': wt_l(md),
        'seed_level_wt_l': wt_l([statistics.mean(per_seed_m[s]) for s in SEEDS]),
        'exceeds_warning_threshold': (c_mean / b_mean - 1.0) * 100.0 < -8.0,
    }

    # ---------- per-variant breakdown (section 16) ----------
    pv = {}
    for v in VARIANTS:
        e = {}
        for arm in ARMS:
            rows = [worlds[(arm, s, v)] for s in SEEDS]
            e[arm] = {k: round(statistics.mean(r[k] for r in rows), 6)
                      for k in ('msmi_per_100_arrived_members', 'assignments',
                                'mutual_acceptances_per_100', 'mutual_per_intro',
                                'coverage', 'ask_cost')}
        for cname, hi, lo in contrast_defs[:2]:
            deltas = [worlds[(hi, s, v)]['msmi_per_100_arrived_members']
                      - worlds[(lo, s, v)]['msmi_per_100_arrived_members']
                      for s in SEEDS]
            ad = [worlds[(hi, s, v)]['assignments'] - worlds[(lo, s, v)]['assignments']
                  for s in SEEDS]
            e[cname] = {
                'msmi_delta_mean': round(statistics.mean(deltas), 6),
                'msmi_wt_l': wt_l(deltas),
                'msmi_ci95': simple_ci(deltas, 77 + len(pv) * 7 + len(cname)),
                'assign_delta_mean': round(statistics.mean(ad), 4),
                'assign_wt_l': wt_l(ad),
            }
        pv[v] = e
    out['per_variant'] = pv

    # ---------- validity / gates ----------
    n_off = len(ARMS) * len(SEEDS) * len(VARIANTS)
    rerun_files = ['arm_greedy_seed107_rerun.json', 'arm_original_seed107_rerun.json',
                   'arm_floorhalf_seed107_rerun.json', 'arm_floorhalf_seed118_rerun.json']
    n_rer = 0
    n_inv = 0
    for f in rerun_files + ['arm_original_seed107_container.json']:
        d = json.loads((HERE / f).read_text(encoding='utf-8'))
        n_rer += len(d['episodes'])
        n_inv += sum(1 for e in d['episodes'] if not e['valid'])
    gates = json.loads((HERE / 'gates_g2_g3.json').read_text(encoding='utf-8'))
    out['integrity'] = {
        'g1': {'official_episodes': n_off, 'rerun_and_container_episodes': n_rer,
               'invalid': n_inv, 'pass': n_inv == 0},
        'g2': {'all_equal': all(p['equal_excl_inference'] for p in gates['G2_determinism']),
               'pairs': gates['G2_determinism']},
        'g3': {'pass': gates['G3_container']['equal_excl_inference_and_mode'],
               'detail': gates['G3_container']},
        'g5': {'note': 'only public seeds 107-118 used; organise.py never '
                       'executed; no organiser/holdout artifacts exist in repo; '
                       'git head unchanged (see integrity_after.json)'},
    }

    # ---------- diagnostics aggregation (section 11) ----------
    diag_out = {}
    pool_keys = ('decisions', 'feasible_total', 'after_floor_total',
                 'above_frozen_floor_total', 'above_intermediate_floor_total',
                 'selected_total', 'introduced', 'zero_candidate_days',
                 'zero_selected_with_cand', 'cap_hits', 'fallback_used',
                 'frontier_recheck_failures', 'instrument_mismatches',
                 'after_floor_neq_feasible_days', 'seed_changed_days',
                 'ask_cost', 'greedy_n', 'greedy_overlap_n', 'greedy_below_floor_n')
    for arm, dfile in DIAG_FILE.items():
        tot = defaultdict(int)
        surv = defaultdict(lambda: {'n': 0, 'mutual': 0, 'msmi': 0})
        cats = defaultdict(int)
        n_asks = 0
        fid = 0
        per_seed_rows = {}
        for s in SEEDS:
            d = json.loads((HERE / ('%s_seed%d.json' % (dfile, s))).read_text(encoding='utf-8'))
            fid += 1 if d['all_fidelity_ok'] else 0
            o = d['overall']
            for k in pool_keys:
                tot[k] += o[k]
            for cls, g in o['survivorship'].items():
                for kk in ('n', 'mutual', 'msmi'):
                    surv[cls][kk] += g[kk]
            for k, n in o['zero_selected_categories'].items():
                cats[k] += n
            for v in VARIANTS:
                for day in d['episodes'][v]['days']:
                    n_asks += day['ask']['n_asks']
            per_seed_rows[str(s)] = {
                'feasible': o['feasible_total'],
                'after_arm_floor': o['after_floor_total'],
                'removed_by_floor': o['feasible_total'] - o['after_floor_total'],
                'zero_sel_with_cand': o['zero_selected_with_cand'],
                'introduced': o['introduced'],
                'fidelity_ok': d['all_fidelity_ok']}
        arm_floor = 'floor_half' if arm == 'floorhalf' else 'floor_original'
        tot = dict(tot)
        tot['removed_by_floor'] = tot['feasible_total'] - tot['after_floor_total']
        diag_out[arm] = {
            'diagnostic_arm_threshold': arm_floor,
            'fidelity_pass_seeds': '%d/12' % fid,
            'pooled': tot,
            'asks_n_total': n_asks,
            'asks_n_per_episode': round(n_asks / 72.0, 3),
            'zero_selected_categories': dict(cats),
            'survivorship_pooled': dict(surv),
            'per_seed': per_seed_rows,
        }
    diag_out['greedy'] = {
        'note': 'zero-selection diagnostics are defined relative to the A+C '
                'floor-filtered matcher; greedy arm has no floor filter - not '
                'instrumented (same scope as Stage 3)',
        'asks_n_per_episode': None,
        'asks_count_note': 'ask COUNT for greedy is not recorded by the '
                           'official harness (only cost); B/C counts from diagnostics',
    }
    out['diagnostics'] = diag_out

    # ---------- runtime ----------
    runs = defaultdict(list)
    for line in (HERE / 'run_log.txt').read_text(encoding='utf-8').splitlines():
        parts = [p.strip() for p in line.split('|')]
        if len(parts) >= 5 and parts[3].endswith('s') and parts[4].startswith('OK'):
            try:
                dt = float(parts[3][:-1])
            except ValueError:
                continue
            name = parts[2]
            if name.startswith('arm_') and 'seed' in name:
                runs[name.rsplit('_seed', 1)[0] + '_rerun' if name.endswith('_rerun.json')
                     else (name.replace('.json', '') if 'container' not in name else 'container')].append(dt)
    last = {}
    for line in (HERE / 'run_log.txt').read_text(encoding='utf-8').splitlines():
        parts = [p.strip() for p in line.split('|')]
        if len(parts) >= 5 and parts[3].endswith('s'):
            try:
                dt = float(parts[3][:-1])
            except ValueError:
                continue
            nm = parts[2]
            if nm.startswith('arm_') and nm.endswith('.json'):
                last[nm] = dt  # last occurrence = post-incident full run
    wall = defaultdict(list)
    for nm, dt in last.items():
        wall[nm.replace('_seed%d' % 0, '')].append(dt)
    arm_wall = {}
    for arm in ARMS:
        dts = [dt for nm, dt in last.items()
               if nm.startswith('arm_%s_seed' % arm) and nm.endswith('.json')
               and 'rerun' not in nm and 'container' not in nm]
        arm_wall[arm] = {'n_runs': len(dts), 'mean_s': round(statistics.mean(dts), 1),
                         'min_s': round(min(dts), 1), 'max_s': round(max(dts), 1)}
    out['runtime'] = {
        'per_seed_run_wall_seconds_6_episodes': arm_wall,
        'inference_seconds_per_episode_mean': {a: per_arm[a]['inference_seconds_mean'] for a in ARMS},
        'note': 'wall = full evaluate.py subprocess (6 episodes); inference '
                'seconds nondeterministic (excluded from G2/G3 comparisons)',
    }

    (HERE / 'summary.json').write_text(json.dumps(out, indent=2, sort_keys=True) + '\n',
                                       encoding='utf-8')
    # console digest
    print('=== PRIMARY (official summarise) ===')
    for a in ARMS:
        print('  %-10s %.4f' % (a, per_arm[a]['primary_score_official']))
    print('=== CONTRAST floorhalf-original (primary) ===')
    cc = contrasts['floorhalf_minus_original']['msmi_per_100_arrived_members']
    print('  mean %.4f ci %s worlds %s seed %s' % (
        cc['mean'], cc['ci95_cluster'], cc['worlds'], cc['seed_level']['wt_l']))
    print('=== CONTRAST floorhalf-greedy (primary) ===')
    cc = contrasts['floorhalf_minus_greedy']['msmi_per_100_arrived_members']
    print('  mean %.4f ci %s worlds %s' % (cc['mean'], cc['ci95_cluster'], cc['worlds']))
    print('=== CONTRAST original-greedy (primary) ===')
    cc = contrasts['original_minus_greedy']['msmi_per_100_arrived_members']
    print('  mean %.4f ci %s worlds %s' % (cc['mean'], cc['ci95_cluster'], cc['worlds']))
    print('=== VOLUME C>B ===', out['volume_confirmation']['worlds'],
          'pct', out['volume_confirmation']['pct_wins'],
          'meets80', out['volume_confirmation']['meets_80pct'],
          'mean', out['volume_confirmation']['mean_delta'])
    print('=== MUTUAL C vs B ===', 'rel%', out['mutual_no_harm']['relative_change_pct'],
          'ci', out['mutual_no_harm']['relative_change_ci95'],
          'wtl', out['mutual_no_harm']['worlds'])
    print('=== INTRO totals ===', out['volume_confirmation']['totals_per_arm'])
    print('WROTE summary.json')


if __name__ == '__main__':
    main()