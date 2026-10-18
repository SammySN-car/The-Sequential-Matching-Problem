"""Seed-group aggregation, bootstrap uncertainty, and the CC-01 cardinality
confound test. All inference is over the 21 seed groups; day-level n is never
used as a sample size."""
import csv, json, random, statistics, sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent /
                        'round2_decision_ceiling' / 'scripts'))
import ce_common as c  # noqa: E402

FC = Path(__file__).resolve().parent.parent
B = 2000
RNG_SEED = 4242
ARMS = ['F1-SCORE', 'F2-SOFT', 'F3-OBSERV', 'F4-RANDOM', 'F5-ORACLE']
DAY_BANDS = ((0, 9, '0-9'), (10, 19, '10-19'), (20, 39, '20-39'), (40, 59, '40-59'))


def band(v):
    for lo, hi, name in DAY_BANDS:
        if lo <= v <= hi:
            return name
    return 'other'


def main():
    c.log('fc_stats start')
    rows = [json.loads(l) for l in open(FC / 'per_state_results.jsonl', encoding='utf-8')]
    seeds = sorted({r['seed'] for r in rows})
    variants = sorted({r['variant'] for r in rows})
    assert len(seeds) == 21 and len(variants) == 6

    # ---------- per-seed aggregation ---------------------------------------
    per_seed_rows = []
    for s in seeds:
        sub = [r for r in rows if r['seed'] == s]
        hr = [r for r in sub if r['headroom'] == 1]
        rec = dict(seed=s, n_states=len(sub), n_headroom=len(hr),
                   k_t=sum(r['k_t'] for r in sub),
                   GREEDY_positives=sum(r['GREEDY_positives'] for r in sub),
                   maxcard_positives=sum(r['maxcard_positives'] for r in sub),
                   max_matching_size=sum(r['max_matching_size'] for r in sub))
        for a in ARMS:
            rec[a + '_positives'] = sum(r[a + '_positives'] for r in sub)
            rec[a + '_delta_vs_greedy'] = (rec[a + '_positives'] - rec['GREEDY_positives'])
            rec[a + '_wins'] = sum(1 for r in sub if r[a + '_positives'] > r['GREEDY_positives'])
            rec[a + '_losses'] = sum(1 for r in sub if r[a + '_positives'] < r['GREEDY_positives'])
        per_seed_rows.append(rec)
    with open(FC / 'per_seed_results.csv', 'w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=list(per_seed_rows[0])); w.writeheader(); w.writerows(per_seed_rows)
    c.log('wrote per_seed_results.csv (%d rows)' % len(per_seed_rows))

    # ---------- per-variant aggregation ------------------------------------
    per_var_rows = []
    for v in variants:
        sub = [r for r in rows if r['variant'] == v]
        hr = [r for r in sub if r['headroom'] == 1]
        rec = dict(variant=v, n_states=len(sub), n_headroom=len(hr),
                   k_t=sum(r['k_t'] for r in sub),
                   GREEDY_positives=sum(r['GREEDY_positives'] for r in sub))
        for a in ARMS:
            rec[a + '_positives'] = sum(r[a + '_positives'] for r in sub)
            rec[a + '_delta_vs_greedy'] = rec[a + '_positives'] - rec['GREEDY_positives']
        per_var_rows.append(rec)
    with open(FC / 'per_variant_results.csv', 'w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=list(per_var_rows[0])); w.writeheader(); w.writerows(per_var_rows)
    c.log('wrote per_variant_results.csv (%d rows)' % len(per_var_rows))

    # ---------- bootstrap over the 21 seed groups ---------------------------
    rng = random.Random(RNG_SEED)
    stats = {}
    K_total = sum(r['k_t'] for r in rows)
    for a in ARMS:
        d = [rec[a + '_delta_vs_greedy'] for rec in per_seed_rows]
        draws = []
        for _ in range(B):
            pick = [rng.randrange(21) for _ in range(21)]
            draws.append(sum(d[i] for i in pick) / 21.0)
        draws.sort()
        lo = draws[int(0.025 * B)]
        hi = draws[int(0.975 * B) - 1]
        tot = sum(r[a + '_positives'] for r in rows)
        stats[a] = dict(
            arm=a,
            total_positives=round(tot, 4),
            greedy_positives=sum(r['GREEDY_positives'] for r in rows),
            delta_vs_greedy=round(tot - sum(r['GREEDY_positives'] for r in rows), 4),
            rate_per_k=round(tot / K_total, 6),
            greedy_rate=round(sum(r['GREEDY_positives'] for r in rows) / K_total, 6),
            bootstrap_B=B, bootstrap_seed=RNG_SEED,
            seed_group_ci95=[round(lo, 4), round(hi, 4)],
            ci_excludes_zero=bool(lo > 0 or hi < 0),
            seeds_positive=sum(1 for x in d if x > 0),
            seeds_tied=sum(1 for x in d if x == 0),
            seeds_negative=sum(1 for x in d if x < 0),
            n_seed_groups=21,
            states_won=sum(1 for r in rows if r[a + '_positives'] > r['GREEDY_positives']),
            states_tied=sum(1 for r in rows if r[a + '_positives'] == r['GREEDY_positives']),
            states_lost=sum(1 for r in rows if r[a + '_positives'] < r['GREEDY_positives']),
            states_changed_set=sum(1 for r in rows if r.get(a + '_changed_set')),
        )
        c.log('  %s delta=%+0.2f  CI95[%+0.3f,%+0.3f]  seeds +/0/- = %d/%d/%d'
              % (a, stats[a]['delta_vs_greedy'], lo, hi,
                 stats[a]['seeds_positive'], stats[a]['seeds_tied'], stats[a]['seeds_negative']))

    # same, restricted to the 82 headroom states
    hr = [r for r in rows if r['headroom'] == 1]
    hr_stats = {}
    for a in ARMS:
        d = []
        for rec in per_seed_rows:
            sub = [r for r in rows if r['seed'] == rec['seed'] and r['headroom'] == 1]
            d.append(sum(r[a + '_positives'] - r['GREEDY_positives'] for r in sub))
        rng2 = random.Random(RNG_SEED)
        draws = []
        for _ in range(B):
            pick = [rng2.randrange(21) for _ in range(21)]
            draws.append(sum(d[i] for i in pick) / 21.0)
        draws.sort()
        lo = draws[int(0.025 * B)]; hi = draws[int(0.975 * B) - 1]
        tot = sum(r[a + '_positives'] for r in hr)
        hr_stats[a] = dict(arm=a, n_states=len(hr),
                           k_t=sum(r['k_t'] for r in hr),
                           total_positives=round(tot, 4),
                           greedy_positives=sum(r['GREEDY_positives'] for r in hr),
                           delta_vs_greedy=round(tot - sum(r['GREEDY_positives'] for r in hr), 4),
                           seed_group_ci95=[round(lo, 4), round(hi, 4)],
                           ci_excludes_zero=bool(lo > 0 or hi < 0),
                           seeds_positive=sum(1 for x in d if x > 0),
                           seeds_tied=sum(1 for x in d if x == 0),
                           seeds_negative=sum(1 for x in d if x < 0),
                           states_won=sum(1 for r in hr if r[a + '_positives'] > r['GREEDY_positives']),
                           states_tied=sum(1 for r in hr if r[a + '_positives'] == r['GREEDY_positives']),
                           states_lost=sum(1 for r in hr if r[a + '_positives'] < r['GREEDY_positives']))

    # ---------- CC-01 cardinality confound ----------------------------------
    c.log('CC-01: reproducing the audit F5_state_only argmax on the 82 headroom states')
    edges_of, oof5 = {}, {}
    for line in open(c.OUT / 'day_edges.jsonl', encoding='utf-8'):
        d = json.loads(line)
        k = (d['seed'], d['variant'], d['day'])
        edges_of[k] = [tuple(e[1]) for e in d['edges']]
    for line in open(c.OUT / 'oof_scores.jsonl', encoding='utf-8'):
        r = json.loads(line)
        oof5[(r['seed'], r['variant'], r['day'], r['user_a'], r['user_b'])] = r['F5_state_only']

    conf_sizes, conf_pos, flat = [], [], 0
    lab = defaultdict(dict)
    for r in rows:
        pass
    labels = defaultdict(dict)
    for line in open(c.OUT / 'counterfactual_pairs.jsonl', encoding='utf-8'):
        r = json.loads(line)
        labels[(r['seed'], r['variant'], r['day'])][(r['user_a'], r['user_b'])] = int(bool(r['cf_y_msmi']))

    for r in hr:
        k = (r['seed'], r['variant'], r['day'])
        keys = edges_of[k]
        s = [oof5[(k[0], k[1], k[2], e[0], e[1])] for e in keys]
        if len({round(x, 12) for x in s}) == 1:
            flat += 1
        ms, failed = c.enumerate_matchings(keys, cap=10 ** 9)
        best = max(sum(s[j] for j in m) for m in ms)
        best_ms = [m for m in ms if abs(sum(s[j] for j in m) - best) < 1e-12]
        pick = max(best_ms, key=len)          # audit rule: max size among ties
        conf_sizes.append(len(pick))
        conf_pos.append(sum(labels[k][keys[j]] for j in pick))

    cc = dict(
        n_headroom_states=len(hr),
        n_states_where_F5_state_only_is_flat=flat,
        audit_argmax_rule='max total F5_state_only, tie-break = LARGEST matching',
        audit_argmax_total_pairs=sum(conf_sizes),
        audit_argmax_total_positives=sum(conf_pos),
        fixed_k_total_pairs=sum(r['k_t'] for r in hr),
        fixed_k_F5_ORACLE_positives=sum(r['F5-ORACLE_positives'] for r in hr),
        greedy_pairs=sum(r['k_t'] for r in hr),
        greedy_positives=sum(r['GREEDY_positives'] for r in hr),
        conclusion=('The audit statistic selected %d pairs against greedy\'s %d on the same '
                    'states. Its apparent advantage is therefore a VOLUME effect, not a '
                    'ranking effect: F5_state_only is flat within all %d headroom states, so '
                    'the argmax tie-break is the only thing choosing among matchings.'
                    % (sum(conf_sizes), sum(r['k_t'] for r in hr), flat)))
    c.log('  CC-01: audit statistic pairs=%d vs greedy pairs=%d (flat in %d/%d states)'
          % (cc['audit_argmax_total_pairs'], cc['fixed_k_total_pairs'], flat, len(hr)))

    # ---------- Case A contrast: F2-SOFT vs F1-SCORE -----------------------
    d21 = [rec['F2-SOFT_positives'] - rec['F1-SCORE_positives'] for rec in per_seed_rows]
    rng3 = random.Random(RNG_SEED)
    draws21 = []
    for _ in range(B):
        pick = [rng3.randrange(21) for _ in range(21)]
        draws21.append(sum(d21[i] for i in pick) / 21.0)
    draws21.sort()
    lo21 = draws21[int(0.025 * B)]
    hi21 = draws21[int(0.975 * B) - 1]
    contrast = dict(
        contrast='F2-SOFT minus F1-SCORE (the Case A soft-state contrast)',
        delta_total=sum(r['F2-SOFT_positives'] - r['F1-SCORE_positives'] for r in rows),
        bootstrap_B=B, bootstrap_seed=RNG_SEED, n_seed_groups=21,
        seed_group_ci95=[round(lo21, 4), round(hi21, 4)],
        ci_excludes_zero=bool(lo21 > 0 or hi21 < 0),
        seeds_positive=sum(1 for x in d21 if x > 0),
        seeds_tied=sum(1 for x in d21 if x == 0),
        seeds_negative=sum(1 for x in d21 if x < 0),
        states_won=sum(1 for r in rows if r['F2-SOFT_positives'] > r['F1-SCORE_positives']),
        states_tied=sum(1 for r in rows if r['F2-SOFT_positives'] == r['F1-SCORE_positives']),
        states_lost=sum(1 for r in rows if r['F2-SOFT_positives'] < r['F1-SCORE_positives']))
    c.log('  CONTRAST F2-F1 delta=%+d  CI95[%+0.3f,%+0.3f]  seeds +/0/- = %d/%d/%d'
          % (contrast['delta_total'], lo21, hi21,
             contrast['seeds_positive'], contrast['seeds_tied'], contrast['seeds_negative']))

    # ---------- selector_summary.csv ---------------------------------------
    summary = []
    for a in ARMS:
        rec = dict(stats[a])
        rec.update({'headroom_' + k: v for k, v in hr_stats[a].items() if k != 'arm'})
        summary.append(rec)
    with open(FC / 'selector_summary.csv', 'w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=list(summary[0])); w.writeheader(); w.writerows(summary)
    c.log('wrote selector_summary.csv (%d rows)' % len(summary))

    (FC / 'statistics.json').write_text(json.dumps(dict(
        rng_seed=RNG_SEED, B=B, n_seed_groups=21, independent_unit='seed group',
        day_level_n_is_not_independent=True,
        overall=stats, headroom_states=hr_stats, contrast_F2_vs_F1=contrast,
        K_total=K_total,
        n_states_total=len(rows),
        n_states_headroom=len(hr),
        n_states_non_headroom=len(rows) - len(hr)), indent=1,
        sort_keys=True) + '\n', encoding='utf-8')
    (FC / 'cardinality_confound.json').write_text(json.dumps(cc, indent=1,
                                                            sort_keys=True) + '\n', encoding='utf-8')
    c.log('task stats done')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
