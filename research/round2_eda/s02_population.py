"""S02: data-generating population and missingness structure.

Regenerates the deterministic member populations for every world seed set
used by prior experiments (kit.generate is a pure function of the seed; this
is reconstruction of existing data, not a new simulation). Outputs tables and
plots under research/round2_eda/. Diagnostic-only fields (truth, exit_day) are
clearly marked in the output schemas.
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import kit  # noqa: E402
from eda_common import PLOTS, TABLES, log, sha256_file, write_csv  # noqa: E402

VARIANTS = ('development', 'sparse', 'cold_start', 'delayed', 'shift', 'drift')
HARD = kit.HARD
SOFT = kit.SOFT
ALL_FIELDS = HARD + SOFT


def world_keys_from_scale800():
    import csv
    keys = set()
    with open(Path(__file__).resolve().parents[2] / 'research' / 'out_scale800' / 'worlds.csv',
              encoding='utf-8') as f:
        for row in csv.DictReader(f):
            keys.add((int(row['world_seed']), row['variant']))
    return sorted(keys)


def tournament_keys():
    return [(s, v) for s in range(143, 164) for v in VARIANTS]


def promotion_keys():
    return [(s, v) for s in range(107, 119) for v in VARIANTS]


def iter_members(keys, tag):
    for seed, variant in keys:
        world = kit.generate(seed, 200, f'eda_{tag}', variant)
        for m in world['members']:
            yield seed, variant, m


def main():
    log('S02 population analysis start')
    log(f'kit.py sha256 {sha256_file(Path(kit.__file__))}')

    sets = {
        'tournament_126': tournament_keys(),
        'scale800_800': world_keys_from_scale800(),
        'promotion_72': promotion_keys(),
    }
    for tag, keys in sets.items():
        log(f'  world set {tag}: {len(keys)} worlds')

    # ---- demographics by variant (scale800 = largest set) ----
    demo_rows = []
    hard_missing_per_member = []              # (tag, variant, n_missing_hard, n_declined_hard)
    member_rows_sample = []
    soft_coverage = defaultdict(list)         # variant -> list of n soft observed
    exit_diag = defaultdict(list)             # variant -> exit_days (diagnostic-only)

    for tag in ('tournament_126', 'scale800_800'):
        keys = sets[tag]
        by_variant = defaultdict(lambda: {'members': 0, 'age': [], 'arrived': 0,
                                          'gender': Counter(), 'zone': Counter()})
        for seed, variant, m in iter_members(keys, tag):
            b = by_variant[variant]
            b['members'] += 1
            b['age'].append(m['age'])
            b['arrived'] += int(m['arrived_day'] > 0)
            b['gender'][m['gender']] += 1
            b['zone'][m['zone']] += 1
            n_missing_hard = sum(1 for k in HARD if m['field_status'][k] != 'observed')
            n_declined_hard = sum(1 for k in HARD if m['field_status'][k] == 'declined')
            hard_missing_per_member.append((tag, variant, n_missing_hard, n_declined_hard))
            soft_coverage[variant].append(sum(1 for k in SOFT if m['field_status'][k] == 'observed'))
            exit_diag[variant].append(m['exit_day'])
        for variant in VARIANTS:
            b = by_variant[variant]
            ages = b['age']
            demo_rows.append({
                'dataset': tag, 'variant': variant, 'members': b['members'],
                'age_mean': sum(ages) / len(ages),
                'age_min': min(ages), 'age_max': max(ages),
                'pct_arrived_after_day0': 100 * b['arrived'] / b['members'],
                'pct_woman': 100 * b['gender']['woman'] / b['members'],
                'pct_man': 100 * b['gender']['man'] / b['members'],
                'pct_non_binary': 100 * b['gender']['non_binary'] / b['members'],
                'pct_zone_a': 100 * b['zone']['zone_a'] / b['members'],
                'pct_zone_b': 100 * b['zone']['zone_b'] / b['members'],
                'pct_zone_c': 100 * b['zone']['zone_c'] / b['members'],
                'pct_zone_d': 100 * b['zone']['zone_d'] / b['members'],
            })
        log(f'  demographics done for {tag}')
    write_csv(TABLES / 'population_demographics.csv', demo_rows)

    # ---- per-field status rates by variant (scale800, single tidy pass) ----
    status_rows = []
    members_with_declined_hard = Counter()
    members_total = Counter()
    for seed, variant, m in iter_members(sets['scale800_800'], 'scale800_800'):
        members_total[variant] += 1
        if any(m['field_status'][k] == 'declined' for k in HARD):
            members_with_declined_hard[variant] += 1
    fields_all = {k: Counter() for k in ALL_FIELDS}
    per_variant_fields = defaultdict(lambda: {k: Counter() for k in ALL_FIELDS})
    for seed, variant, m in iter_members(sets['scale800_800'], 'scale800_800'):
        for k in ALL_FIELDS:
            st = m['field_status'][k]
            fields_all[k][st] += 1
            per_variant_fields[variant][k][st] += 1
    for scope, src in [('ALL', fields_all)] + [(v, per_variant_fields[v]) for v in VARIANTS]:
        for k in ALL_FIELDS:
            c = src[k]
            n = sum(c.values())
            status_rows.append({
                'scope': scope, 'field': k, 'field_class': 'hard' if k in HARD else 'soft',
                'n': n, 'observed': c['observed'], 'declined': c['declined'],
                'not_asked': c['not_asked'],
                'pct_observed': round(100 * c['observed'] / n, 3),
                'pct_declined': round(100 * c['declined'] / n, 3),
                'pct_not_asked': round(100 * c['not_asked'] / n, 3),
            })
    write_csv(TABLES / 'field_status_by_variant.csv', status_rows)

    # ---- hard-field missingness per member (scale800) ----
    hist_missing = Counter()
    hist_declined = Counter()
    for tag, variant, n_miss, n_decl in hard_missing_per_member:
        if tag != 'scale800_800':
            continue
        hist_missing[n_miss] += 1
        hist_declined[n_decl] += 1
    total_members = sum(hist_missing.values())
    miss_rows = [{'n_hard_not_observed': k, 'members': v,
                  'pct': round(100 * v / total_members, 3)}
                 for k, v in sorted(hist_missing.items())]
    write_csv(TABLES / 'hard_missing_per_member.csv', miss_rows)
    decl_rows = [{'n_hard_declined': k, 'members': v,
                  'pct': round(100 * v / total_members, 3)}
                 for k, v in sorted(hist_declined.items())]
    write_csv(TABLES / 'hard_declined_per_member.csv', decl_rows)

    decl_by_variant = []
    for v in VARIANTS:
        n = members_total[v]
        d = members_with_declined_hard[v]
        decl_by_variant.append({'variant': v, 'members': n,
                                'members_with_declined_hard': d,
                                'pct': round(100 * d / n, 3)})
    write_csv(TABLES / 'declined_hard_members_by_variant.csv', decl_by_variant)

    # ---- co-occurrence of declined hard fields (scale800) ----
    pair_co = Counter()
    for seed, variant, m in iter_members(sets['scale800_800'], 'scale800_800'):
        decl = tuple(sorted(k for k in HARD if m['field_status'][k] == 'declined'))
        if decl:
            pair_co[decl] += 1
    co_rows = [{'declined_set': '+'.join(k), 'members': n}
               for k, n in pair_co.most_common(25)]
    write_csv(TABLES / 'declined_hard_cooccurrence_top25.csv', co_rows)

    # ---- soft coverage per member (scale800) ----
    cov_rows = []
    for v in VARIANTS:
        xs = sorted(soft_coverage[v])
        n = len(xs)
        cov_rows.append({'variant': v, 'members': n,
                         'soft_observed_mean': round(sum(xs) / n, 3),
                         'soft_observed_p10': xs[n // 10],
                         'soft_observed_p50': xs[n // 2],
                         'soft_observed_p90': xs[9 * n // 10],
                         'pct_zero_soft': round(100 * sum(1 for x in xs if x == 0) / n, 3),
                         'pct_full_soft': round(100 * sum(1 for x in xs if x == 7) / n, 3)})
    write_csv(TABLES / 'soft_coverage_per_member.csv', cov_rows)

    # ---- variant differences: arrival + exit (exit = diagnostic-only) ----
    arr_rows = []
    for v in VARIANTS:
        arr = Counter()
        ex = [x for x in exit_diag[v]]
        for seed, variant, m in iter_members(sets['scale800_800'], 'x'):
            if variant != v:
                continue
            arr['after0'] += int(m['arrived_day'] > 0)
            arr['total'] += 1
        arr_rows.append({'variant': v, 'pct_arrived_after_day0': round(100 * arr['after0'] / arr['total'], 3),
                         'pct_early_exit_le60_diag': round(100 * sum(1 for x in ex if x <= 60) / len(ex), 3)})
    write_csv(TABLES / 'arrival_exit_by_variant.csv', arr_rows)

    # ---- plots ----
    # 1) field status stacked bars (ALL scope, hard vs soft)
    fields_plot = [r for r in status_rows if r['scope'] == 'ALL']
    fig, ax = plt.subplots(figsize=(12, 5))
    xs = range(len(fields_plot))
    obs = [r['pct_observed'] for r in fields_plot]
    dec = [r['pct_declined'] for r in fields_plot]
    na = [r['pct_not_asked'] for r in fields_plot]
    ax.bar(xs, obs, label='observed', color='#4c9f70')
    ax.bar(xs, dec, bottom=obs, label='declined', color='#c0504d')
    ax.bar(xs, na, bottom=[o + d for o, d in zip(obs, dec)], label='not_asked', color='#999999')
    ax.set_xticks(list(xs))
    ax.set_xticklabels([r['field'].replace('_', '\n', 1) for r in fields_plot], fontsize=7)
    ax.set_ylabel('% of member-fields (scale800, 160k members)')
    ax.set_title('Field status at generation (before any asks): observed / declined / not_asked')
    ax.legend()
    fig.tight_layout()
    fig.savefig(PLOTS / 'field_status_stacked.png', dpi=130)
    plt.close(fig)

    # 2) hard-declined per member histogram
    fig, ax = plt.subplots(figsize=(7, 4))
    ks = [r['n_hard_declined'] for r in decl_rows]
    vs = [r['members'] for r in decl_rows]
    ax.bar(ks, vs, color='#c0504d')
    ax.set_xlabel('number of HARD fields declined at generation')
    ax.set_ylabel('members')
    ax.set_title('Members with declined hard fields (scale800: 160,000 members)')
    fig.tight_layout()
    fig.savefig(PLOTS / 'hard_declined_hist.png', dpi=130)
    plt.close(fig)

    # 3) soft coverage by variant
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(VARIANTS, [r['soft_observed_mean'] for r in cov_rows], color='#4c9f70')
    ax.set_ylabel('mean SOFT fields observed at generation (of 7)')
    ax.set_title('Baseline soft coverage by variant (pre-ask)')
    plt.setp(ax.get_xticklabels(), rotation=20)
    fig.tight_layout()
    fig.savefig(PLOTS / 'soft_coverage_by_variant.png', dpi=130)
    plt.close(fig)

    summary = {
        'members_examined_scale800': sum(members_total.values()),
        'members_with_any_declined_hard_pct': round(
            100 * sum(members_with_declined_hard.values()) / sum(members_total.values()), 3),
        'note': 'truth/exit_day used only where marked diagnostic; populations regenerated '
                'deterministically from recorded seeds via kit.generate (no rollouts).',
    }
    (TABLES / 's02_summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    log(f'S02 done: {summary}')


if __name__ == '__main__':
    main()
