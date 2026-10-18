"""Frozen-protocol analysis - sections 6 and 10 of PROTOCOL.md.

Every formula here implements the frozen definitions (primary endpoint, bootstrap CI,
verdicts). Written and unit-tested BEFORE any confirmatory outcome was examined.
"""
import argparse
import json
import random
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from research.hard_constraint_clarification import pilot_gates as pg  # noqa: E402

VARIANTS = ('development', 'sparse', 'cold_start', 'delayed', 'shift', 'drift')
BOOT_SEED = 20261016
BOOT_B = 10000
BUDGET_PER_DAY = 12
DECISION_DAYS = 60


def mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def group_scores(records, arm, require_all=False):
    """seed -> group primary P_X(g) (mean over the six variants).

    A seed is scored only when all six variants are present and valid; otherwise the
    missing (seed, variant) pairs are reported (never silently dropped).
    """
    by = {}
    for r in records:
        if r['arm'] != arm:
            continue
        if not r.get('valid') or r.get('exit_code', 0) != 0:
            continue
        by.setdefault(r['seed'], {})[r['variant']] = \
            r['row'].get('msmi_per_100_arrived_members')
    scores, missing = {}, []
    for s in sorted(by):
        vm = by[s]
        miss = [v for v in VARIANTS if v not in vm]
        missing.extend((s, v) for v in miss)
        if not miss:
            scores[s] = mean([vm[v] for v in VARIANTS])
    missing.sort()
    if require_all:
        return scores, missing
    return scores


def paired_deltas(g_scores, u_scores):
    return {s: u_scores[s] - g_scores[s]
            for s in sorted(set(g_scores) & set(u_scores))}


def bootstrap_ci(deltas, B=BOOT_B, seed=BOOT_SEED):
    """Percentile bootstrap of the mean over paired seed groups (frozen section 6)."""
    if not deltas:
        return (None, None)
    rng = random.Random(seed)
    n = len(deltas)
    means = []
    for _ in range(B):
        means.append(sum(deltas[rng.randrange(n)] for _ in range(n)) / n)
    means.sort()
    lo = means[int(round(0.025 * (B - 1)))]
    hi = means[int(round(0.975 * (B - 1)))]
    return (lo, hi)


def variant_stats(greedy_records, unlock_records, seeds=None):
    """Per-variant paired means + descriptive bootstrap CIs (diagnostics only)."""
    def by_key(recs):
        out = {}
        for r in recs:
            if not r.get('valid') or r.get('exit_code', 0) != 0:
                continue
            out[(r['seed'], r['variant'])] = r['row'].get('msmi_per_100_arrived_members')
        return out
    gm, um = by_key(greedy_records), by_key(unlock_records)
    if seeds is None:
        seeds = sorted({s for s, _ in set(gm) & set(um)})
    stats = {}
    for idx, v in enumerate(VARIANTS):
        pairs = [(gm[(s, v)], um[(s, v)]) for s in seeds
                 if (s, v) in gm and (s, v) in um]
        if not pairs:
            stats[v] = {'greedy': None, 'unlock': None, 'delta': None,
                        'ci95': (None, None), 'n_pairs': 0}
            continue
        deltas = [u - g for g, u in pairs]
        stats[v] = {'greedy': mean([g for g, _ in pairs]),
                    'unlock': mean([u for _, u in pairs]),
                    'delta': mean(deltas),
                    'ci95': bootstrap_ci(deltas, seed=BOOT_SEED + 100 + idx),
                    'n_pairs': len(pairs)}
    return stats


def verdict(*, complete_groups, planned_groups, invalid_count, spot_ok,
            mean_delta, ci, variant_deltas):
    """Frozen section 10 decision rules - only three verdicts, STOP checked first."""
    reasons = []
    if not spot_ok:
        reasons.append('confirmatory spot-check parity failure (seed 120001)')
    if invalid_count:
        reasons.append('%d invalid episode(s) in confirmatory' % invalid_count)
    if reasons:
        return 'STOP', reasons
    if complete_groups < planned_groups:
        reasons.append('coverage %d/%d complete paired groups' % (complete_groups,
                                                                  planned_groups))
        return 'INCONCLUSIVE', reasons
    n_nonneg = sum(1 for v in VARIANTS if (variant_deltas.get(v) is not None
                                           and variant_deltas[v] >= 0))
    if mean_delta > 0 and ci[0] is not None and ci[0] > 0 and n_nonneg >= 4:
        reasons.append('mean delta %+.5f, ci95 [%+.5f, %+.5f], %d/6 variants >= 0'
                       % (mean_delta, ci[0], ci[1], n_nonneg))
        return 'PROMISING — REVIEW REQUIRED', reasons
    if mean_delta <= 0:
        reasons.append('point estimate %+.5f not positive' % mean_delta)
    elif ci[0] is None or ci[0] <= 0:
        reasons.append('ci95 [%s, %s] spans or touches zero' % (ci[0], ci[1]))
    if n_nonneg < 4:
        reasons.append('only %d/6 variants >= 0' % n_nonneg)
    return 'INCONCLUSIVE', reasons


def episode_diagnostics(records):
    valid = [r for r in records if r.get('valid') and r.get('exit_code', 0) == 0]
    rows = [r['row'] for r in valid]
    def f(key):
        return mean([r.get(key, 0) for r in rows])
    return {'episodes': len(records), 'valid': len(valid),
            'ask_cost_mean': f('ask_cost'),
            'msmi_count_mean': f('mutual_second_meeting_intention'),
            'msmi_per_100_mean': f('msmi_per_100_arrived_members'),
            'assignments_mean': f('assignments'),
            'mutual_acceptances_mean': f('mutual_acceptances'),
            'dates_mean': f('dates'),
            'coverage_mean': f('coverage'),
            'inference_s_total': sum(r.get('inference_seconds', 0) for r in rows),
            'runtime_s_total': sum(r.get('elapsed_s', 0) for r in records)}


def ask_summary(logs):
    episodes = len(logs)
    total_asks = total_spent = total_days = unlock = inform = 0
    recipients = set()
    for lines in logs.values():
        for ln in lines:
            total_days += 1
            total_asks += ln.get('n_asks', 0) or 0
            total_spent += ln.get('spent', 0) or 0
            for a in ln.get('asks', []):
                recipients.add(a.get('member_id'))
            for t in (ln.get('trace') or []):
                unlock += t.get('unlock_marginal', 0) or 0
                inform += t.get('inform_marginal', 0) or 0
    budget_total = float(BUDGET_PER_DAY * DECISION_DAYS * episodes)
    return {'episodes': episodes, 'total_days': total_days,
            'total_asks': total_asks, 'total_spent': total_spent,
            'budget_fraction': (total_spent / budget_total) if episodes else 0.0,
            'mean_asks_per_day': (total_asks / total_days) if total_days else 0.0,
            'distinct_recipients': len(recipients),
            'potential_unlock_sum': unlock, 'potential_inform_sum': inform}


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--exp', default=str(HERE))
    p.add_argument('--phase', default='confirmatory')
    args = p.parse_args(argv)
    exp = Path(args.exp)

    records = pg.load_records(exp, args.phase)
    arms = {'greedy': [r for r in records if r['arm'] == 'greedy'],
            'unlock': [r for r in records if r['arm'] == 'unlock'],
            'greedy_official': [r for r in records if r['arm'] == 'greedy_official']}
    all_arms = records

    g_scores, g_missing = group_scores(arms['greedy'], 'greedy', require_all=True)
    u_scores, u_missing = group_scores(arms['unlock'], 'unlock', require_all=True)
    deltas = paired_deltas(g_scores, u_scores)
    delta_values = list(deltas.values())
    mean_delta = mean(delta_values)
    ci = bootstrap_ci(delta_values)

    paired_seeds = sorted(deltas)
    vstats = variant_stats(arms['greedy'], arms['unlock'], seeds=paired_seeds)
    variant_deltas = {v: vstats[v]['delta'] for v in VARIANTS}

    invalid = [r['key'] for r in all_arms
               if r['arm'] in ('greedy', 'unlock')
               and (not r.get('valid') or r.get('exit_code', 0) != 0)]
    spot = [r for r in all_arms if r['seed'] == 120001]
    spot_ok, spot_bad = pg.gate_g1(spot)

    planned = 100
    complete = len(deltas)
    v, reasons = verdict(complete_groups=complete, planned_groups=planned,
                         invalid_count=len(invalid), spot_ok=spot_ok,
                         mean_delta=mean_delta, ci=ci, variant_deltas=variant_deltas)

    u_logs = pg.load_logs(exp, ('unlock',))
    g_logs = pg.load_logs(exp, ('greedy',))

    analysis = {
        'protocol': 'PROTOCOL.md frozen 2026-10-16 16:35 IST',
        'generated': datetime.now().astimezone().isoformat(timespec='seconds'),
        'coverage': {'planned_groups': planned, 'complete_paired_groups': complete,
                     'greedy_missing': g_missing, 'unlock_missing': u_missing,
                     'per_arm': {a: episode_diagnostics(rs) for a, rs in arms.items()}},
        'invalid_episodes': invalid,
        'spot_check': {'ok': spot_ok, 'mismatches': spot_bad, 'n_keys': len(spot)},
        'primary': {'endpoint': 'mean over 100 seed groups of the equally weighted '
                                'six-variant mean of msmi_per_100_arrived_members',
                    'greedy_score': mean([g_scores[s] for s in paired_seeds]),
                    'unlock_score': mean([u_scores[s] for s in paired_seeds]),
                    'delta': mean_delta, 'ci95': list(ci), 'B': BOOT_B,
                    'boot_seed': BOOT_SEED, 'n_groups': complete,
                    'group_deltas': {str(s): deltas[s] for s in paired_seeds}},
        'per_variant': {vv: {**st, 'ci95': list(st['ci95'])}
                        for vv, st in vstats.items()},
        'msmi': {a: {'total': sum(r['row'].get('mutual_second_meeting_intention', 0)
                                  for r in rs if r.get('valid')),
                     'count_mean': episode_diagnostics(rs)['msmi_count_mean'],
                     'rate_per_100': episode_diagnostics(rs)['msmi_per_100_mean']}
                 for a, rs in arms.items()},
        'asks': {'greedy': ask_summary(g_logs), 'unlock': ask_summary(u_logs)},
        'verdict': v, 'verdict_reasons': reasons,
    }
    out_path = exp / 'results' / 'analysis_confirm.json'
    out_path.write_text(json.dumps(analysis, indent=2, sort_keys=True) + '\n',
                        encoding='utf-8')

    print('=== HCC confirmatory analysis (frozen protocol section 6) ===')
    print('coverage      : %d/%d paired groups | invalid=%d | spot_check=%s'
          % (complete, planned, len(invalid), 'PASS' if spot_ok else 'FAIL'))
    print('greedy score  : %.5f' % analysis['primary']['greedy_score'])
    print('unlock score  : %.5f' % analysis['primary']['unlock_score'])
    print('delta         : %+.5f   95%% CI [%+.5f, %+.5f]  (B=%d, seed=%d)'
          % (mean_delta, ci[0], ci[1], BOOT_B, BOOT_SEED))
    for vv in VARIANTS:
        st = vstats[vv]
        print('  %-12s greedy %.4f unlock %.4f delta %+.4f ci [%+.4f, %+.4f] n=%d'
              % (vv, st['greedy'], st['unlock'], st['delta'],
                 st['ci95'][0], st['ci95'][1], st['n_pairs']))
    print('asks budget   : greedy %.4f unlock %.4f | recipients g=%d u=%d'
          % (analysis['asks']['greedy']['budget_fraction'],
             analysis['asks']['unlock']['budget_fraction'],
             analysis['asks']['greedy']['distinct_recipients'],
             analysis['asks']['unlock']['distinct_recipients']))
    print('VERDICT       : %s' % v)
    for r in reasons:
        print('                - %s' % r)
    print('written: %s' % out_path)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())