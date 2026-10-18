"""Preregistered paired analysis for the E1/E2/E3 experiment.

Reads per_arm/{C,E1,E2,E3}.json + per_arm/*_mechanism.json, computes the
comparisons and guardrails fixed in experiment_plan.json, writes summary.json.
No tuning, no optional analyses beyond the preregistered ones.
"""
import json
import math
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PER_ARM = HERE / 'per_arm'
ARMS = ('C', 'E1', 'E2', 'E3')
COMPARISONS = (('E1', 'C'), ('E2', 'C'), ('E3', 'C'), ('E3', 'E1'), ('E3', 'E2'))
T_CRIT_11 = 2.200985   # two-sided 95%, df = 11 (12 seed-level pairs, fixed)
T_CRIT_71 = 1.993943   # two-sided 95%, df = 71 (72 episode pairs, reported as note)
T_CRIT_23 = 2.068658   # two-sided 95%, df = 23 (24 seed-level pairs, stage 1+2)
T_CRIT_143 = 1.976424  # two-sided 95%, df = 143 (144 episode pairs, stage 1+2)
BOOT_N = 10000
BOOT_SEED = 20261007


def load(name):
    return json.loads((PER_ARM / name).read_text(encoding='utf-8'))


def paired_stats(diffs):
    """diffs: list of per-unit differences (72 episode-level or 12 seed-level)."""
    n = len(diffs)
    m = statistics.mean(diffs)
    sd = statistics.stdev(diffs) if n > 1 else 0.0
    se = sd / math.sqrt(n) if n else 0.0
    return n, m, sd, se


def bootstrap_seed_ci(seed_diffs, rng):
    import random
    means = []
    n = len(seed_diffs)
    for _ in range(BOOT_N):
        means.append(statistics.mean(seed_diffs[rng.randrange(n)]
                                     for _ in range(n)))
    means.sort()
    lo = means[int(0.025 * BOOT_N)]
    hi = means[min(BOOT_N - 1, int(0.975 * BOOT_N))]
    return lo, hi


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--stage2', action='store_true',
                    help='pool stage-1 (119-130) + stage-2 (131-142), n=24 seeds; '
                         'writes the FINAL summary.json per stopping rules')
    args = ap.parse_args(argv)

    def load_arm(a):
        r1 = load(a + '.json')
        if not args.stage2:
            return r1
        s2 = json.loads((PER_ARM / ('s2_' + a + '.json')).read_text(encoding='utf-8'))
        merged = dict(r1)
        merged['episodes'] = r1['episodes'] + s2['episodes']
        merged['summary_stage1'] = r1['summary']
        return merged

    rows = {a: load_arm(a) for a in ARMS}
    guard = {'invalid_episodes': {}, 'digest_mismatch': {},
             'mechanism_invalid': {}}
    for a in ARMS:
        eps = rows[a]['episodes']
        guard['invalid_episodes'][a] = sum(1 for e in eps if not e.get('valid'))
        guard['digest_mismatch'][a] = 'n/a (official pass)'
        if not rows[a]['summary'].get('eligible'):
            print(f'INELIGIBLE arm {a}: {rows[a]["summary"].get("reason")}')
            return 2

    by = {}
    for a in ARMS:
        by[a] = {(e['seed'], e['variant']): e for e in rows[a]['episodes']}

    keys = sorted(by['C'])
    assert all(k in by[a] for a in ARMS for k in keys), 'episode key mismatch'

    def metric(e, name):
        if name == 'msmi':
            return e['msmi_per_100_arrived_members']
        if name == 'coverage':
            return e['coverage']
        if name == 'mutual100':
            return e['mutual_acceptances_per_100']
        if name == 'ask_cost':
            return e['ask_cost']
        if name == 'inference':
            return e['inference_seconds']
        if name == 'intros100':
            return 100.0 * e['assignments'] / max(1, e['arrived_members'])
        if name == 'mutual_per_intro':
            return e['mutual_acceptances'] / max(1, e['assignments'])
        if name == 'msmi_per_intro':
            return e['mutual_second_meeting_intention'] / max(1, e['assignments'])
        raise KeyError(name)

    # ---- guardrails ------------------------------------------------------
    guard['max_inference_seconds'] = {a: max(by[a][k]['inference_seconds']
                                             for k in keys) for a in ARMS}
    guard['ask_cost_means'] = {
        a: statistics.mean(metric(by[a][k], 'ask_cost') for k in keys)
        for a in ARMS}
    for a in ('E1', 'E2', 'E3'):
        mp = PER_ARM / (a + '_mechanism.json')
        if mp.exists():
            mech = json.loads(mp.read_text(encoding='utf-8'))
            guard['digest_mismatch'][a] = len(mech['digest_mismatch'])
            guard['mechanism_invalid'][a] = len(mech['invalid'])

    # ---- primary + secondary per-arm means --------------------------------
    secondary = ('coverage', 'mutual100', 'intros100', 'mutual_per_intro',
                 'msmi_per_intro', 'ask_cost', 'inference')
    arm_means = {}
    for a in ARMS:
        arm_means[a] = {'msmi': statistics.mean(
            metric(by[a][k], 'msmi') for k in keys)}
        for s in secondary:
            arm_means[a][s] = statistics.mean(metric(by[a][k], s) for k in keys)

    # ---- comparisons ------------------------------------------------------
    comparisons = {}
    import random
    for t, c in COMPARISONS:
        diffs72 = [metric(by[t][k], 'msmi') - metric(by[c][k], 'msmi')
                   for k in keys]
        seeds = sorted({k[0] for k in keys})
        seed_diffs = [statistics.mean(
            metric(by[t][(s, v)], 'msmi') - metric(by[c][(s, v)], 'msmi')
            for (ss, v) in keys if ss == s) for s in seeds]
        n, m, sd, se = paired_stats(seed_diffs)
        t_seed = T_CRIT_23 if n == 24 else T_CRIT_11
        ci = (m - t_seed * se, m + t_seed * se)
        n72, m72, _, se72 = paired_stats(diffs72)
        t_unit = T_CRIT_143 if n72 == 144 else T_CRIT_71
        ci72 = (m72 - t_unit * se72, m72 + t_unit * se72)
        w = sum(1 for d in diffs72 if d > 0)
        l = sum(1 for d in diffs72 if d < 0)
        ties = n72 - w - l
        rng = random.Random(BOOT_SEED)
        blo, bhi = bootstrap_seed_ci(seed_diffs, rng)
        base = arm_means[c]['msmi']
        comparisons[f'{t}_vs_{c}'] = {
            'mean_diff_seed_level': m,
            'sd_seed_level': sd,
            't95_ci_seed_level': list(ci),
            'bootstrap95_ci_seed_level': [blo, bhi],
            'percent_vs_control': 100.0 * m / base if base else None,
            'win_tie_loss_units': {'win': w, 'tie': ties, 'loss': l,
                                   'n_units': n72},
            'episode_level_note_ci95': list(ci72),
            'seed_level_diffs': seed_diffs,
        }

    # ---- per-variant primary table ----------------------------------------
    variants = sorted({k[1] for k in keys})
    per_variant = {a: {v: statistics.mean(
        metric(by[a][k], 'msmi') for k in keys if k[1] == v)
        for v in variants} for a in ARMS}

    # ---- mechanism aggregates ---------------------------------------------
    mechanism = {}
    for a in ARMS:
        mp = PER_ARM / (a + '_mechanism.json')
        if not mp.exists():
            mechanism[a] = 'missing'
            continue
        mech = json.loads(mp.read_text(encoding='utf-8'))
        days, rel_ask_days, changed_rel_days, rel_asks_total = [], 0, 0, 0
        zero_days = 0
        rank_changed_days, edges_changed_sum, edges_total_sum = 0, 0, 0
        n_eps = 0
        for ep in mech['episodes']:
            if not ep.get('valid'):
                continue
            n_eps += 1
            mrows = ep['mechanism']
            days.extend(mrows)
            rel_asks_total += sum(r['rel_asks'] for r in mrows)
            rel_ask_days += sum(1 for r in mrows if r['rel_asks'] > 0)
            changed_rel_days += sum(1 for r in mrows
                                    if r['rel_asks'] > 0 and r['alloc_changed_by_rel'])
            zero_days += sum(1 for r in mrows if r['zero_selection'])
            rank_changed_days += sum(1 for r in mrows if r['ranking_changed'])
            edges_changed_sum += sum(r['edges_changed'] for r in mrows)
            edges_total_sum += sum(r['edges_total'] for r in mrows)
        ndays = len(days)
        mechanism[a] = {
            'episodes': n_eps,
            'rel_asks_total': rel_asks_total,
            'rel_asks_per_day': rel_asks_total / max(1, ndays),
            'rel_ask_days': rel_ask_days,
            'rel_ask_days_where_alloc_changed': changed_rel_days,
            'frac_rel_ask_days_changed_alloc':
                changed_rel_days / max(1, rel_ask_days),
            'frac_rel_asks_on_changed_days':
                (sum(r['rel_asks_on_changed_day'] for r in days)
                 / max(1, rel_asks_total)),
            'zero_selection_days': zero_days,
            'frac_zero_selection_days': zero_days / max(1, ndays),
            'frac_days_ranking_changed': rank_changed_days / max(1, ndays),
            'frac_edges_score_changed': edges_changed_sum / max(1, edges_total_sum),
        }

    # ---- stopping-rule verdict (E3 vs C first, as preregistered) ----------
    e3 = comparisons['E3_vs_C']
    if args.stage2:
        if e3['t95_ci_seed_level'][0] > 0:
            verdict = ('FINAL: stage-2 pooled CI entirely > 0 -> winner arm is '
                       'the candidate replacement, subject to all guardrails '
                       'and the final decision rule.')
        else:
            verdict = ('FINAL: after the single extension the CI still overlaps '
                       '0 -> verdict INCONCLUSIVE -> keep greedy.')
    elif e3['mean_diff_seed_level'] <= 0:
        verdict = 'STOP: E3 point <= 0 vs C; keep greedy (no extension).'
    elif e3['t95_ci_seed_level'][0] > 0:
        verdict = 'E3 clearly positive: CI excludes 0; candidate for promotion (subject to all guardrails).'
    else:
        verdict = ('EXTEND once (seeds 131-142) permitted: point > 0 but CI '
                   'overlaps 0; if still overlapping after extension -> '
                   'inconclusive -> keep greedy.')

    out = {
        'plan': 'experiment_plan.json',
        'stage': 2 if args.stage2 else 1,
        'seeds': sorted({k[0] for k in keys}),
        'variants': variants,
        'episodes_per_arm': len(keys),
        'guardrails': guard,
        'arm_means': arm_means,
        'comparisons': comparisons,
        'per_variant_primary': per_variant,
        'mechanism': mechanism,
        'stopping_rule_verdict': verdict,
    }
    (HERE / 'summary.json').write_text(
        json.dumps(out, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print(json.dumps({'guardrails': guard,
                      'arm_means_msmi': {a: round(arm_means[a]['msmi'], 4) for a in ARMS},
                      'comparisons': {k: {
                          'mean': round(v['mean_diff_seed_level'], 4),
                          'ci': [round(x, 4) for x in v['t95_ci_seed_level']],
                          'pct': round(v['percent_vs_control'], 1),
                          'wtl': [v['win_tie_loss_units']['win'],
                                  v['win_tie_loss_units']['tie'],
                                  v['win_tie_loss_units']['loss']]}
                          for k, v in comparisons.items()},
                      'verdict': verdict}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
