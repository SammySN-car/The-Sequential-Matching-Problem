"""N01 analysis - seed-grouped, evidence-gated feature x conversion tables.

Pre-registered analysis rules (single fixed pass; no threshold fishing after
results; gate never weakened):

1. Population: mature introductions from n01_introductions.jsonl, worlds whose
   commit row in n01_replay_rows.jsonl passed the fidelity gate (126/126).
2. Primary label: y_msmi (official MSMI). Diagnostic labels: y_mutual,
   y_date, y_second - reported, never sufficient for conclusion A.
3. Features: only the decision-time-legal lists in n01_autopsy.FEATURE_*.
   seed and variant are strata keys, never features.
4. Split rule: booleans -> (False, True); numeric -> threshold = median of the
   DISCOVERY pool, low = value <= threshold, high = value > threshold. The
   discovery threshold transfers unchanged to the replication pool and the
   pooled pool. One split per feature; no alternative thresholds are tried.
5. Pools: discovery = seeds 143-151 (9 seeds), replication = seeds 152-163
   (12 seeds), pooled = all 21 seeds. Uncertainty = seed-grouped t 95% CI on
   the per-seed rate difference (high - low), df = seeds with both halves
   non-empty - 1.
6. Gate (methods.json n01 evidence_needed_to_justify_followons, unchanged):
   G1 discovery pooled conversion ratio >= 2x between halves;
   G2 minority half covers >= 5% of introductions on >= 3 of 6 variants;
   G3 ratio >= 2x on >= 3 of 6 variants (discovery);
   G4 replicates on >= 3 replication seeds (per-seed ratio >= 2x, where a
   zero-event low half with a non-zero high half counts as >= 2x and is
   reported explicitly) AND replication pooled ratio >= 2x.
   A ratio with both halves at zero events is not testable and never counts.
   Gate pass = G1 and G2 and G3 and G4, evaluated on y_msmi only.
7. Selection bias: labels exist only for chosen pairs; associations are
   conditional on greedy's selection. Absolute scores are never compared
   across seed sets. Exploratory/intermediates can never yield conclusion A.

Conclusion A: >=1 feature passes the full gate on y_msmi (report an exact
fresh-seed test). Conclusion B: none passes (any intermediate-only hits are
listed as exploratory, explicitly not success).
"""
import json
import pathlib
import statistics
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import n01_autopsy as h  # noqa: E402

DISCOVERY = (143, 144, 145, 146, 147, 148, 149, 150, 151)
REPLICATION = (152, 153, 154, 155, 156, 157, 158, 159, 160, 161, 162, 163)
VARIANTS = h.VARIANTS
PRIMARY = 'y_msmi'
DIAGNOSTIC = ('y_mutual', 'y_date', 'y_second')

T95 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447,
       7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179,
       13: 2.160, 14: 2.145, 15: 2.131, 16: 2.120, 17: 2.110, 18: 2.101,
       19: 2.093, 20: 2.086, 21: 2.080, 22: 2.074, 23: 2.069, 24: 2.064,
       25: 2.060, 26: 2.056, 27: 2.052, 28: 2.048, 29: 2.045, 30: 2.042}


def read_jsonl(path):
    if not pathlib.Path(path).exists():
        return []
    return [json.loads(l) for l in pathlib.Path(path).read_text(
        encoding='utf-8').splitlines() if l.strip()]


def final_blocks(path, committed):
    """Last consecutive run per world wins; only fidelity-committed worlds.

    A crash between appends can duplicate a world's block (commit row is
    written last); the final complete run is authoritative.
    """
    runs = []
    cur_key, cur = None, []
    for row in read_jsonl(path):
        key = (row['seed'], row['variant'])
        if key != cur_key:
            if cur:
                runs.append((cur_key, cur))
            cur_key, cur = key, [row]
        else:
            cur.append(row)
    if cur:
        runs.append((cur_key, cur))
    out = []
    last = {}
    for key, block in runs:  # last run per world wins
        last[key] = block
    for key, block in last.items():
        if key in committed:
            out.extend(block)
    return out


def load():
    world_rows = {(r['seed'], r['variant']): r for r in read_jsonl(
        h.OUT_ROWS)}
    bad = [k for k, r in world_rows.items() if not r.get('all_match')]
    if bad or len(world_rows) != 126:
        raise SystemExit('fidelity gate failed or incomplete: bad=%r present=%d'
                         % (bad, len(world_rows)))
    committed = set(world_rows)
    intros = final_blocks(h.OUT_INTROS, committed)
    days = final_blocks(h.OUT_DAYS, committed)
    if len(intros) != sum(r['n_intros'] for r in world_rows.values()):
        raise SystemExit('introduction count mismatch: %d vs %d'
                         % (len(intros),
                            sum(r['n_intros'] for r in world_rows.values())))
    if any(not r['mature'] for r in intros):
        raise SystemExit('immature introductions present')
    return world_rows, intros, days


def pool_stats(rows, feature, kind, thr, label):
    """Halves stats for one pool. flag: ok | low_zero | no_events |
    not_testable. ge2 treats low_zero as ratio >= 2 (reported explicitly)."""
    def in_low(v):
        return v == 0 if kind == 'bool' else v <= thr
    low = [r for r in rows if in_low(r[feature])]
    high = [r for r in rows if not in_low(r[feature])]
    n_low, n_high, n_tot = len(low), len(high), len(rows)
    ev_low = sum(r[label] for r in low)
    ev_high = sum(r[label] for r in high)
    if n_low == 0 or n_high == 0:
        flag, ratio = 'not_testable', None
    elif ev_low + ev_high == 0:
        flag, ratio = 'no_events', None
    elif ev_low == 0:
        flag, ratio = 'low_zero', None
    else:
        # rate ratio, not count ratio (halves can differ in size)
        flag, ratio = 'ok', (ev_high / n_high) / (ev_low / n_low)
    rate_low = ev_low / n_low if n_low else None
    rate_high = ev_high / n_high if n_high else None
    return {
        'n_low': n_low, 'n_high': n_high, 'n_total': n_tot,
        'events_low': ev_low, 'events_high': ev_high,
        'rate_low': round(rate_low, 6) if rate_low is not None else None,
        'rate_high': round(rate_high, 6) if rate_high is not None else None,
        'abs_diff': (round(rate_high - rate_low, 6)
                     if rate_low is not None and rate_high is not None
                     else None),
        'ratio': round(ratio, 4) if ratio is not None else None,
        'ratio_flag': flag,
        'ge2': flag == 'low_zero' or (ratio is not None and ratio >= 2.0),
        'minority_share': round(min(n_low, n_high) / n_tot, 4) if n_tot else None,
    }


def seed_ci(per_seed_diffs):
    diffs = [d for d in per_seed_diffs if d is not None]
    n = len(diffs)
    if n < 2:
        return {'n_seeds': n, 'mean_diff': None, 'ci95': None, 'df': n - 1}
    mean = statistics.mean(diffs)
    sd = statistics.stdev(diffs)
    tcrit = T95.get(n - 1, 1.96)
    half = tcrit * sd / (n ** 0.5)
    return {'n_seeds': n, 'mean_diff': round(mean, 6),
            'ci95': [round(mean - half, 6), round(mean + half, 6)],
            'df': n - 1}


def evaluate_feature(feature, kind, thr, intros, label, detail):
    disc = [r for r in intros if r['seed'] in DISCOVERY]
    rep = [r for r in intros if r['seed'] in REPLICATION]
    pools = {name: pool_stats(rows, feature, kind, thr, label)
             for name, rows in (('discovery', disc),
                                ('replication', rep), ('pooled', intros))}
    result = {'pools': pools}
    per_variant = {v: pool_stats([r for r in disc if r['variant'] == v],
                                 feature, kind, thr, label)
                   for v in VARIANTS}
    per_seed = {str(s): pool_stats([r for r in intros if r['seed'] == s],
                                   feature, kind, thr, label)
                for s in DISCOVERY + REPLICATION}
    if detail:
        result['per_variant_discovery'] = per_variant
        result['per_seed_all'] = per_seed
        diffs = []
        for s in DISCOVERY + REPLICATION:
            st = per_seed[str(s)]
            if st['ratio_flag'] == 'not_testable':
                diffs.append(None)
            else:
                diffs.append(st['rate_high'] - st['rate_low'])
        result['seed_grouped_t95_diff'] = seed_ci(diffs)
    g1 = pools['discovery']['ge2']
    g1_rep = pools['replication']['ge2']
    g2 = sum(1 for v in VARIANTS if per_variant[v]['minority_share'] is not None
             and per_variant[v]['minority_share'] >= 0.05) >= 3
    g3 = sum(1 for v in VARIANTS if per_variant[v]['ge2']) >= 3
    rep_seed_ge2 = sum(1 for s in REPLICATION if per_seed[str(s)]['ge2'])
    g4 = rep_seed_ge2 >= 3
    result['gate'] = {
        'G1_discovery_ratio_ge2': bool(g1),
        'G2_minority_ge5pct_on_3_variants': bool(g2),
        'G3_ratio_ge2_on_3_variants': bool(g3),
        'G4_ge2_on_3_replication_seeds': bool(g4),
        'replication_seeds_ge2': rep_seed_ge2,
        'replication_pooled_ge2': bool(g1_rep),
        'variants_ge2_discovery': sum(1 for v in VARIANTS
                                      if per_variant[v]['ge2']),
        'variants_minority_ge5_discovery': sum(
            1 for v in VARIANTS
            if per_variant[v]['minority_share'] is not None
            and per_variant[v]['minority_share'] >= 0.05),
        'pass': bool(g1 and g1_rep and g2 and g3 and g4),
    }
    return result


def day_stats(days):
    out = {'days': len(days),
           'zero_selection_days': sum(r['zero_selection'] for r in days),
           'zero_selection_rate': round(sum(r['zero_selection']
                                            for r in days) / len(days), 4),
           'per_variant': {}}
    for v in VARIANTS:
        rows = [r for r in days if r['variant'] == v]
        with_edges = [r for r in rows if r['edges_total'] > 0]
        out['per_variant'][v] = {
            'days': len(rows),
            'zero_selection_rate': round(sum(r['zero_selection']
                                             for r in rows) / len(rows), 4),
            'mean_edges_when_any': round(statistics.mean(
                r['edges_total'] for r in with_edges), 1) if with_edges else 0.0,
            'mean_unmatched_despite_edges': round(statistics.mean(
                r['unmatched_despite_edges'] for r in with_edges),
                2) if with_edges else 0.0,
            'mean_available': round(statistics.mean(
                r['n_available'] for r in rows), 1),
        }
    return out


def main():
    world_rows, intros, days = load()
    totals = {lab: sum(r[lab] for r in intros) for lab in h.LABELS}
    funnel = {
        'introductions': len(intros),
        'mutual': totals['y_mutual'],
        'dates': totals['y_date'],
        'second_intention': totals['y_second'],
        'msmi': totals['y_msmi'],
        'mutual_per_intro': round(totals['y_mutual'] / len(intros), 4),
        'msmi_per_intro': round(totals['y_msmi'] / len(intros), 5),
        'date_given_mutual': (round(totals['y_date'] / totals['y_mutual'], 4)
                              if totals['y_mutual'] else None),
        'msmi_given_date': (round(totals['y_msmi'] / totals['y_date'], 4)
                            if totals['y_date'] else None),
        'missing_feedback': sum(r['missing'] for r in intros),
    }
    features = ([(f, 'bool') for f in h.FEATURE_BOOLEANS]
                + [(f, 'num') for f in h.FEATURE_NUMBERS])
    out_features = []
    primary_passes = []
    diagnostic_passes = []
    for feature, kind in features:
        values = [r[feature] for r in intros if r['seed'] in DISCOVERY]
        thr = (statistics.median(values) if kind == 'num' else None)
        entry = {'feature': feature, 'kind': kind,
                 'threshold_discovery_median': thr,
                 'threshold_pool': 'discovery seeds 143-151'}
        entry['by_label'] = {}
        for label in (PRIMARY,) + DIAGNOSTIC:
            detail = label == PRIMARY
            stats = evaluate_feature(feature, kind, thr, intros, label, detail)
            entry['by_label'][label] = stats
        entry['gate_pass_primary'] = entry['by_label'][PRIMARY]['gate']['pass']
        if entry['gate_pass_primary']:
            primary_passes.append(feature)
        elif any(entry['by_label'][lab]['gate']['pass'] for lab in DIAGNOSTIC):
            diagnostic_passes.append(
                {'feature': feature,
                 'labels': [lab for lab in DIAGNOSTIC
                            if entry['by_label'][lab]['gate']['pass']]})
        out_features.append(entry)
    conclusion = 'A' if primary_passes else 'B'
    report = {
        'meta': {
            'artifact': 'n01_decision_state_autopsy',
            'status': 'executed',
            'fidelity': {'worlds': 126, 'digest_matches': 126,
                         'label_sums_match': 126, 'immature': 0,
                         'note': 'byte-identical to sealed official control '
                                 'rows before any analysis ran'},
            'funnel': funnel,
            'day_stats': day_stats(days),
            'primary_label': PRIMARY,
            'diagnostic_labels': list(DIAGNOSTIC),
            'selection_bias_caveat': (
                'Labels exist only for pairs greedy chose to introduce. '
                'Outcomes of unchosen pairs are counterfactual and '
                'unobservable, so every feature/conversion association here '
                'is conditional on selection and cannot be read causally or '
                'as counterfactual policy value.'),
            'analysis_rules': (
                'Pre-registered single pass: boolean natural split; numeric '
                'median split on discovery seeds 143-151, threshold '
                'transferred unchanged to replication 152-163; gate = G1 '
                'discovery pooled ratio >= 2, G2 minority half >= 5% of '
                'intros on >= 3 of 6 variants, G3 ratio >= 2 on >= 3 of 6 '
                'variants, G4 ratio >= 2 on >= 3 replication seeds AND '
                'replication pooled >= 2; low-half zero events with '
                'non-zero high half counts as >= 2 and is flagged; '
                'zero/zero = not testable; gate evaluated on y_msmi only.'),
            'deviation_from_methods_json': (
                'methods.json wrote dev-only seeds (90210 family); the '
                'authorising instruction superseded it with deterministic '
                'replay of the existing consumed tournament worlds '
                '(seeds 143-163) and forbade new seeds. No new seed or '
                'confirmation was created.'),
        },
        'features': out_features,
        'gate_pass_features_primary': primary_passes,
        'gate_pass_features_diagnostic_only': diagnostic_passes,
        'conclusion': conclusion,
    }
    h.OUT_SUMMARY  # noqa: B018  (path anchor only)
    out_path = HERE / 'n01_feature_results.json'
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True,
                                   allow_nan=False) + '\n', encoding='utf-8')
    # compact console summary
    print(json.dumps({'funnel': funnel,
                      'conclusion': conclusion,
                      'primary_passes': primary_passes,
                      'diagnostic_only': diagnostic_passes}, indent=2))
    ranked = []
    for entry in out_features:
        st = entry['by_label'][PRIMARY]['pools']['discovery']
        ranked.append((st['ratio'] if st['ratio'] is not None else
                       (999 if st['ratio_flag'] == 'low_zero' else -1),
                       entry['feature'], st))
    ranked.sort(reverse=True, key=lambda x: x[0])
    print('top primary-label discovery ratios:')
    for ratio, feature, st in ranked[:12]:
        print('  %-24s ratio=%s flag=%s ev=(%s,%s) n=(%s,%s)'
              % (feature, st['ratio'], st['ratio_flag'], st['events_low'],
                 st['events_high'], st['n_low'], st['n_high']))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())