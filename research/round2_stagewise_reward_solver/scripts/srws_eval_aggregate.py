"""Task 5: aggregate the final paired sequential evaluation -> results/paired_stats.json.

Statistics (fixed before evaluation, S.9):
  - per seed group per arm: unweighted mean over the 6 variants of
    msmi_per_100_arrived_members;
  - primary quantity d_g = candidate_g - greedy_g for each of the 100 seed
    groups; point estimate = mean(d_g);
  - 95% CI: paired bootstrap over seed groups (resample the 100 d_g with
    replacement; B = 10,000; RNG random.Random(71001); percentile 2.5/97.5).
    Seed groups are the sampling units;
  - win/tie/loss over d_g (tie = |d_g| < 1e-12); per-variant paired means;
    actual MSMIs + arrived members + introductions per arm; runtime
    distributions; invalid episodes; instrumentation cardinality audit
    (k_chosen == k_greedy on every candidate match line).

Decision signal emitted here is E-series only (mean>0, CI excludes 0, zero
invalid candidate episodes); the FINAL single decision (considering all C/R/P
gates) is emitted in report.md (Task 6). Standard library only.
"""
import json
import random
import statistics
import sys
from pathlib import Path

EXPERIMENT = Path(__file__).resolve().parents[1]
RESULTS = EXPERIMENT / 'results'
INSTR_DIR = RESULTS / 'eval_instrumentation'

SEEDS = list(range(70001, 70101))
VARIANTS = ('development', 'sparse', 'cold_start', 'delayed', 'shift', 'drift')
B = 10000
BOOT_SEED = 71001
TIE_EPS = 1e-12
PRIMARY = 'msmi_per_100_arrived_members'


def load_arm(name):
    data = json.loads((RESULTS / ('eval_%s.json' % name)).read_text(encoding='utf-8'))
    rows = data['episodes']
    by = {}
    invalid = []
    for r in rows:
        if r.get('valid') is True and r.get(PRIMARY) is not None:
            by[(r['seed'], r['variant'])] = r
        else:
            invalid.append({'seed': r.get('seed'), 'variant': r.get('variant'),
                            'error': r.get('error')})
    return by, invalid, data


def group_mean(by, seed):
    vals = [by[(seed, v)][PRIMARY] for v in VARIANTS if (seed, v) in by]
    if len(vals) != len(VARIANTS):
        return None
    return statistics.fmean(vals)


def percentile(sorted_vals, q):
    idx = int(q * len(sorted_vals))
    idx = min(idx, len(sorted_vals) - 1)
    return sorted_vals[idx]


def audit_cardinality():
    lines = 0
    mismatch = 0
    if INSTR_DIR.exists():
        for fp in sorted(INSTR_DIR.glob('*.jsonl')):
            for raw in fp.read_text(encoding='utf-8').splitlines():
                if not raw.strip():
                    continue
                lines += 1
                try:
                    o = json.loads(raw)
                except json.JSONDecodeError:
                    mismatch += 1
                    continue
                if o.get('k_chosen') != o.get('k_greedy'):
                    mismatch += 1
    return lines, mismatch


def main():
    greedy, greedy_invalid, gdata = load_arm('greedy')
    cand, cand_invalid, cdata = load_arm('candidate')

    d_g = {}
    missing = []
    for s in SEEDS:
        g = group_mean(greedy, s)
        c = group_mean(cand, s)
        if g is None or c is None:
            missing.append({'seed': s, 'greedy': g, 'candidate': c})
            continue
        d_g[s] = c - g

    vals = [d_g[s] for s in sorted(d_g)]
    mean_d = statistics.fmean(vals) if vals else None

    # paired bootstrap over seed groups
    ci_lo = ci_hi = None
    if vals:
        rng = random.Random(BOOT_SEED)
        n = len(vals)
        boots = []
        for _ in range(B):
            sample = [vals[rng.randrange(n)] for _ in range(n)]
            boots.append(statistics.fmean(sample))
        boots.sort()
        ci_lo = percentile(boots, 0.025)
        ci_hi = percentile(boots, 0.975)

    wins = sum(1 for v in vals if v > TIE_EPS)
    losses = sum(1 for v in vals if v < -TIE_EPS)
    ties = sum(1 for v in vals if abs(v) <= TIE_EPS)

    # per-variant paired means
    per_variant = {}
    for v in VARIANTS:
        diffs = []
        for s in SEEDS:
            if (s, v) in greedy and (s, v) in cand:
                diffs.append(cand[(s, v)][PRIMARY] - greedy[(s, v)][PRIMARY])
        per_variant[v] = {'n': len(diffs),
                          'mean_diff': statistics.fmean(diffs) if diffs else None}

    def totals(by):
        keys = ('mutual_second_meeting_intention', 'arrived_members', 'assignments',
                'mutual_acceptances', PRIMARY, 'coverage', 'inference_seconds', 'ask_cost')
        out = {}
        for k in keys:
            vs = [r[k] for r in by.values() if k in r and r[k] is not None]
            out[k + '_sum'] = sum(vs) if vs else None
            out[k + '_mean'] = statistics.fmean(vs) if vs else None
        inf = [r['inference_seconds'] for r in by.values()
               if r.get('inference_seconds') is not None]
        out['inference_seconds_max'] = max(inf) if inf else None
        return out

    instr_lines, instr_mismatch = audit_cardinality()

    eval_ok = (not missing and not cand_invalid and mean_d is not None
               and ci_lo is not None)
    excludes_zero = (ci_lo is not None and (ci_lo > 0 or ci_hi < 0))
    improves = (mean_d is not None and mean_d > 0)
    e_decision = 'PROCEED' if (improves and excludes_zero and eval_ok) else (
        'PROCEED_WITH_CHANGES' if eval_ok else 'STOP')

    result = {
        'experiment': 'round2_stagewise_reward_solver', 'task': 5,
        'script': 'scripts/srws_eval_aggregate.py',
        'seeds': [SEEDS[0], SEEDS[-1]], 'n_seed_groups': len(SEEDS),
        'variants': list(VARIANTS), 'bootstrap': {'B': B, 'seed': BOOT_SEED,
                                                  'unit': 'seed_group'},
        'greedy_episodes': len(greedy), 'candidate_episodes': len(cand),
        'greedy_invalid': greedy_invalid, 'candidate_invalid': cand_invalid,
        'missing_seed_groups': missing,
        'd_g': {str(s): d_g[s] for s in sorted(d_g)},
        'mean_paired_diff': mean_d,
        'ci95': {'lo': ci_lo, 'hi': ci_hi},
        'win_tie_loss': {'win': wins, 'tie': ties, 'loss': losses},
        'per_variant': per_variant,
        'totals': {'greedy': totals(greedy), 'candidate': totals(cand)},
        'cardinality_audit': {'instrumentation_lines': instr_lines,
                              'k_mismatches': instr_mismatch,
                              'pass': instr_mismatch == 0},
        'e_series_decision_signal': e_decision,
        'final_decision_note': 'Final single decision emitted in report.md (Task 6).',
    }
    (RESULTS / 'paired_stats.json').write_text(json.dumps(result, indent=2),
                                               encoding='utf-8')
    print('mean_paired_diff = %r' % mean_d)
    print('ci95 = [%r, %r]' % (ci_lo, ci_hi))
    print('win/tie/loss = %d/%d/%d' % (wins, ties, losses))
    print('candidate_invalid = %d  cardinality_mismatches = %d'
          % (len(cand_invalid), instr_mismatch))
    print('e_series_decision_signal = %s' % e_decision)
    print('wrote results/paired_stats.json')
    return 0


if __name__ == '__main__':
    sys.exit(main())
