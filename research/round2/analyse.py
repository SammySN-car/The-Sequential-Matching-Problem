"""Round 2 analysis: frozen statistical protocol (research/round2/design.md 5.4-5.5)."""
import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path

R2 = Path(__file__).resolve().parent
RESULTS = R2 / 'results'

T95, T99 = 2.201, 3.106          # df=11 two-sided
FAMILY_FLOOR = -0.20             # P4 catastrophic degradation floor (msmi/100 abs)


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - r) / d, (c + r) / d)


def load_jsonl(path):
    return [json.loads(l) for l in path.read_text(encoding='utf-8').splitlines() if l.strip()]


def cluster_ci(per_seed_diffs):
    n = len(per_seed_diffs)
    m = statistics.mean(per_seed_diffs)
    if n < 2:
        return m, None, None, n
    sd = statistics.stdev(per_seed_diffs)
    half95 = T95 * sd / math.sqrt(n)
    half99 = T99 * sd / math.sqrt(n)
    return m, m - half95, m + half95, n, m - half99, m + half99


def main():
    rows = load_jsonl(RESULTS / 'eval_rows.jsonl')
    diag = load_jsonl(RESULTS / 'diagnostic_rows.jsonl')
    assert len(rows) == 360 and all(r['valid'] for r in rows), 'grid incomplete or invalid'

    by = {(r['arm'], r['seed'], r['variant']): r for r in rows}
    seeds = sorted({r['seed'] for r in rows})
    variants = sorted({r['variant'] for r in rows})
    arms = sorted({r['arm'] for r in rows})

    def arm_mean(arm, key):
        fam = {v: statistics.mean(by[(arm, s, v)][key] for s in seeds) for v in variants}
        return statistics.mean(fam.values()), fam

    # ---- primary: paired gated vs greedy, clustered by seed ----------------
    def paired(candidate, control, key='msmi_per_100_arrived_members'):
        world_diffs = {}
        seed_diffs = []
        for s in seeds:
            ds = []
            for v in variants:
                d = by[(candidate, s, v)][key] - by[(control, s, v)][key]
                world_diffs[(s, v)] = d
                ds.append(d)
            seed_diffs.append(statistics.mean(ds))
        res = cluster_ci(seed_diffs)
        w = sum(1 for d in world_diffs.values() if d > 0)
        t_ = sum(1 for d in world_diffs.values() if d == 0)
        l = sum(1 for d in world_diffs.values() if d < 0)
        fam = {v: statistics.mean(d for (ss, vv), d in world_diffs.items() if vv == v)
               for v in variants}
        return {'mean': res[0], 'ci95': (res[1], res[2]), 'ci99': (res[4], res[5]),
                'clusters': res[3] if isinstance(res[3], int) else res[3],
                'wtl': {'w': w, 't': t_, 'l': l}, 'per_family': fam,
                'n_worlds': len(world_diffs)}

    primary = paired('gated', 'greedy')
    ablation = paired('ungated', 'greedy')
    cov = paired('gated', 'greedy', key='coverage')

    # ---- arm summaries ------------------------------------------------------
    summaries = {}
    for arm in arms:
        overall = {}
        for key in ('msmi_per_100_arrived_members', 'coverage', 'mutual_acceptances_per_100',
                    'ask_cost', 'inference_seconds'):
            overall[key] = arm_mean(arm, key)[0]
        fam_msmi = arm_mean(arm, 'msmi_per_100_arrived_members')[1]
        summaries[arm] = {'overall': overall, 'family_msmi': fam_msmi,
                          'primary_score': overall['msmi_per_100_arrived_members'],
                          'valid_all': all(by[(arm, s, v)]['valid'] for s in seeds for v in variants)}

    # ---- gate telemetry (diagnostics rows, gated + ungated) ----------------
    tele = {}
    for arm in ('gated', 'ungated'):
        agg = defaultdict(float)
        zero_days = days = pairs_total = 0
        for r in diag:
            if r['arm'] != arm:
                continue
            t = r.get('telemetry') or {}
            m = r.get('final_memory') or {}
            for k in ('solver_tried', 'solver_exact', 'gate_adopted', 'reject_g1',
                      'reject_g2', 'reject_other', 'score_gain_sum', 'card_delta_sum'):
                agg[k] += t.get(k, m.get(k, 0)) or 0
            zero_days += m.get('zero_days', 0)
            days += m.get('days', 0)
            pairs_total += m.get('pairs_total', 0)
        tele[arm] = {k: int(v) for k, v in agg.items()}
        tele[arm]['solver_activation_freq'] = (agg['solver_tried'] / days) if days else None
        tele[arm]['exact_available_freq'] = (agg['solver_exact'] / days) if days else None
        tele[arm]['gate_adopt_freq'] = (agg['gate_adopted'] / days) if days else None
        tele[arm]['zero_selection_days'] = (zero_days / days) if days else None
        tele[arm]['days'] = int(days)
        tele[arm]['pairs_total'] = int(pairs_total)

    # ---- calibration bands (gated diagnostics, Wilson CIs) ------------------
    bands = {str(s): [0, 0, 0, 0] for s in range(8)}
    for r in diag:
        if r['arm'] != 'gated':
            continue
        mem = r.get('final_memory') or {}
        for s, row in (mem.get('bands') or {}).items():
            for i in range(4):
                bands[str(s)][i] += row[i]
    calib = {}
    for s, (n, mutual, dates, msmi) in sorted(bands.items()):
        calib[s] = {'intros': n, 'mutual': mutual, 'dates': dates, 'msmi': msmi,
                    'msmi_rate': msmi / n if n else None,
                    'msmi_wilson95': wilson(msmi, n),
                    'mutual_rate': mutual / n if n else None}

    # ---- waiting / secondary ----------------------------------------------
    waiting = {}
    for arm in ('greedy', 'gated', 'ungated'):
        waits = []
        for s in seeds:
            for v in variants:
                waits.extend(by[(arm, s, v)].get('first_introduction_wait_days') or [])
        waiting[arm] = {'mean_wait_days': statistics.mean(waits) if waits else None,
                        'median_wait_days': statistics.median(waits) if waits else None,
                        'zero_selection_days_overall': tele.get(arm, {}).get('zero_selection_days'),
                        'unserved_mean': statistics.mean(
                            by[(arm, s, v)]['unserved_members'] for s in seeds for v in variants)}

    # ---- promotion decision (P1-P5) ----------------------------------------
    p1 = primary['mean'] > 0
    p2 = primary['ci95'][0] is not None and primary['ci95'][0] > 0
    p3 = all(r['valid'] for r in rows)
    p4 = all(d >= FAMILY_FLOOR for d in primary['per_family'].values())
    max_inf = max(r['inference_seconds'] for r in rows)
    mean_inf = statistics.mean(r['inference_seconds'] for r in rows) / 120.0
    p5_latency = max_inf < 120 and mean_inf < 2.0   # per-episode total < 120s hard; mean invoke < 2s
    # determinism/container checks recorded separately; flagged pending here
    decision = {'P1_mean_gt_0': p1, 'P2_ci95_lower_gt_0': p2, 'P3_zero_invalid': p3,
                'P4_no_family_catastrophe': p4,
                'P4_min_family_diff': min(primary['per_family'].values()),
                'P5_latency_ok_local': p5_latency,
                'mean_invoke_seconds': mean_inf, 'max_episode_inference_seconds': max_inf,
                'P5_determinism_container': 'pending_separate_checks'}

    summary = {'primary_gated_vs_greedy': primary,
               'ablation_ungated_vs_greedy': ablation,
               'coverage_gated_vs_greedy': cov,
               'arm_summaries': summaries,
               'gate_telemetry': tele,
               'calibration_bands_gated': calib,
               'waiting': waiting,
               'promotion_checks': decision}
    (RESULTS / 'summary.json').write_text(
        json.dumps(summary, indent=2, allow_nan=False) + '\n', encoding='utf-8')

    # ---- console report ------------------------------------------------------
    print('PRIMARY gated - greedy: mean=%.4f  ci95=[%.4f, %.4f]  ci99=[%.4f, %.4f]  W/T/L=%d/%d/%d' %
          (primary['mean'], primary['ci95'][0], primary['ci95'][1], primary['ci99'][0],
           primary['ci99'][1], primary['wtl']['w'], primary['wtl']['t'], primary['wtl']['l']))
    print('per-family:', {k: round(v, 4) for k, v in primary['per_family'].items()})
    print('ABLATION ungated - greedy: mean=%.4f ci95=[%.4f, %.4f] W/T/L=%d/%d/%d' %
          (ablation['mean'], ablation['ci95'][0], ablation['ci95'][1],
           ablation['wtl']['w'], ablation['wtl']['t'], ablation['wtl']['l']))
    for arm in arms:
        s = summaries[arm]
        print('ARM %-8s primary=%.4f coverage=%.4f mutual/100=%.2f ask=%.1f inv=%.2fs' %
              (arm, s['primary_score'], s['overall']['coverage'],
               s['overall']['mutual_acceptances_per_100'], s['overall']['ask_cost'],
               s['overall']['inference_seconds'] / 72.0))
    print('GATE gated telemetry:', tele['gated'])
    print('GATE ungated telemetry:', tele['ungated'])
    print('CALIB bands (intros, msmi, rate, wilson):',
          {s: (c['intros'], c['msmi'], round(c['msmi_rate'], 4) if c['msmi_rate'] is not None else None,
               [round(x, 4) for x in c['msmi_wilson95']])
           for s, c in calib.items() if c['intros']})
    print('DECISION CHECKS:', json.dumps(decision, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())