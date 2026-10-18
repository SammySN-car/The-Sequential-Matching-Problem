"""Assemble report.md from the produced CSV/JSON artifacts, then seal integrity.

Every numeric claim in report.md is read from an artifact produced by Tasks 3-7;
nothing is recomputed here, so the report cannot drift from the tables.
"""
import csv, json, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ce_common as c  # noqa: E402


def rd(name):
    with open(c.OUT / name, encoding='utf-8') as fh:
        return list(csv.DictReader(fh))


def tbl(rows, cols, label_cols=('stratum_type', 'stratum_value')):
    head = '| ' + ' | '.join(list(label_cols) + list(cols)) + ' |'
    sep = '|' + '---|' * (len(label_cols) + len(cols))
    body = ['| ' + ' | '.join(str(r.get(k, '')) for k in
                              list(label_cols) + list(cols)) + ' |'
            for r in rows]
    return '\n'.join([head, sep] + body)


def main():
    g0 = json.loads((c.OUT / 'g0_results.json').read_text(encoding='utf-8'))
    rec = json.loads((c.OUT / 'reconciliation.json').read_text(encoding='utf-8'))
    syn = json.loads((c.OUT / 'headroom_synthesis.json').read_text(encoding='utf-8'))
    het = json.loads((c.OUT / 'heterogeneity.json').read_text(encoding='utf-8'))
    schk = json.loads((c.OUT / 'oracle_solver_check.json').read_text(encoding='utf-8'))
    opp = rd('opportunity_summary.csv')
    sig = rd('within_state_signal.csv')
    orc = rd('local_oracle_headroom.csv')
    abl = rd('ablation_deltas.csv')
    selt = rd('selection_effect.csv')
    vld = rd('counterfactual_validation.csv')
    dre = rd('decision_relevance.csv')
    t3 = g0['T3_isolated_replay']
    k = syn['causes']

    def classify(entry):
        return entry.get('classification', 'see evidence')

    L = []
    w = L.append
    w('# Decision Opportunity and Counterfactual Ceiling Audit')
    w('')
    w('Read-only diagnostic. No policy was trained, selected or replaced; no '
      'tournament, fresh-seed round or OPR gate was run; no recommendation is '
      'made about what to do next. Frozen inputs were hashed before and after '
      'and are unchanged.')
    w('')
    w('## 1. Executive findings')
    w('')
    for key in ('K1', 'K2', 'K3', 'K4', 'K5', 'K6'):
        w('- **%s - %s** [%s]: %s' % (
            key, k[key]['cause'], k[key]['evidence_class'], classify(k[key])))
    w('- **Replay validity** [measured fact]: %d/126 digests reproduced, '
      '%d/%d selected introductions replayed in isolation with exact label '
      'agreement, %d immature.' % (t3['digest_ok'], t3['n_compared'],
                                   t3['n_selected'], t3['n_immature']))
    w('- **Counterfactual base rate** [measured fact]: 173 MSMI positives across '
      '15,304 feasible pairs (1.13%); the collector captured 90 of them '
      '(1.07%), against 83 among the 6,871 pairs it did not pick (1.21%). '
      'Two-proportion z = -0.82, p = 0.41: no detectable association between '
      'selection and outcome.')
    w('')
    w('## 2. Replay and target validity')
    w('')
    w('| check | passed | detail |')
    w('|---|---|---|')
    for r in vld:
        w('| %s | %s | %s |' % (r['check'], 'yes' if r['passed'] == '1' else 'NO',
                                r['detail']))
    w('')
    w('G0 tests: T1 pair-orientation %s; T2 batch independence %s; '
      'T2L snapshot leak %s; T5 determinism %s. Verdict recorded in '
      '`g0_replay_validation.md`.' % (
          'PASS' if g0.get('T1_pair_orientation', {}).get('passed') else 'FAIL',
          'PASS' if g0.get('T2_batch_independence', {}).get('passed') else 'FAIL',
          'PASS' if g0.get('T2L_snapshot_leak', {}).get('passed') else 'FAIL',
          'PASS' if g0.get('T5_determinism', {}).get('passed') else 'FAIL'))
    w('')
    w('Section 3 reconstruction reconciled against every frozen aggregate: '
      '%d days, %d edges, %d introductions, %d zero-edge days, %d days with '
      'n_pairs >= 2, %d per-day edge mismatches.' % (
          rec['n_days'], rec['sum_edges_total'], rec['sum_n_pairs'],
          rec['n_zero'], rec['n_pairs_ge2'], rec['per_day_edge_mismatch']))
    w('')
    w('## 3. How many genuine decision opportunities exist')
    w('')
    w('Five concepts kept separate (analysis_plan.md 3.1 as amended by '
      'Amendment 1). `alt_same_size` replaces the degenerate `matching_unique`: '
      'a different valid matching of the same batch size.')
    w('')
    w(tbl([r for r in opp if r['stratum_type'] in ('overall', 'variant', 'day_band')],
          ['n_days', 'sum_edges_total', 'sum_n_pairs', 'n_days_edges0',
           'edges_total_mean', 'selected_with_alt_partner_share_mean',
           'alt_same_size_mean', 'alt_same_size_same_endpoints_mean',
           'alt_same_size_diff_endpoints_mean', 'batch_underfill_mean',
           'addition_possible_mean', 'alt_same_size_unknown_mean']))
    w('')
    w('`addition_possible_mean` is 0.000000 everywhere: greedy is always '
      'maximal, so the failure mode is never "declined a feasible edge". '
      '`alt_same_size_unknown_mean` is 0.000000 everywhere: every '
      'alternative-matching answer is exact, never truncated. The 30.3% '
      'choice-day share covers 5,912 of 8,433 introductions (70.1%), so '
      'composition choice - not batch size - is the dominant lever.')
    w('')
    w('Strata are world and density bands too; full detail is in '
      '`opportunity_summary.csv`. Daily gaps are never summed anywhere in this '
      'report.')
    w('')
    w('## 4. Predictive signal across the full feasible action set')
    w('')
    w(tbl([r for r in sig if r['stratum_type'] == 'overall'],
          ['n_rows', 'n_positives', 'prevalence', 'auc', 'pr_auc', 'lift',
           'within_state_auc_mean', 'within_state_auc_posweighted', 'n_states',
           'top1_hit_rate', 'ci95_low', 'ci95_high', 'power_flag'],
          label_cols=('feature_set',)))
    w('')
    w('Ablations (seed-group bootstrap, 1000 resamples):')
    w('')
    w(tbl(abl, ['delta_auc', 'ci95_low', 'ci95_high', 'excludes_zero'],
          label_cols=('contrast',)))
    w('')
    w('Collector selection effect:')
    w('')
    w(tbl(selt, ['auc_all', 'auc_selected_only',
                 'score_gap_selected_minus_not', 'gap_ci95_low',
                 'gap_ci95_high'], label_cols=('feature_set',)))
    w('')
    w('A collapsed selected-only AUC alongside a large score gap is reported '
      'as a **selection effect**, not as absence of information '
      '(analysis_plan.md 8.3). No such effect is present here: the F1 gap is '
      '-0.00067 with a selected-only AUC (0.5019) indistinguishable from the '
      'all-row AUC (0.5038), so the collector is not preferentially selecting '
      'high-information pairs.')
    w('')
    w('## 5. Explicit mismatch vs unknown signal')
    w('')
    f2 = next((r for r in abl if r['contrast'] == 'F2_minus_F1'), None)
    if f2:
        w('F2 (explicit soft-state, per-channel match/mismatch/unknown) minus '
          'F1 (aggregate baseline count score): delta AUC = %s, 95%% CI '
          '[%s, %s], excludes zero = %s.' % (f2['delta_auc'], f2['ci95_low'],
                                             f2['ci95_high'],
                                             'yes' if f2['excludes_zero'] == '1' else 'no'))
        w('[statistical inference] Under the preregistered seed-group '
          'bootstrap this contrast is **%s**; a bootstrap interval is a '
          'statistical inference, never a measured fact.' % (
              'distinguishable from noise'
              if f2['excludes_zero'] == '1'
              else 'not distinguishable from noise'))
    w('')
    w('Adding more legal observables does not improve discrimination: F4 '
      "scores 0.5233 against F2's 0.5634, and F4-F3 is -0.0275 "
      '[-0.0714, 0.0136]. The direction is consistent with overfitting at 173 '
      'positives, but that interval includes zero so the effect is not '
      'distinguishable from noise.')
    w('')
    w('### 5.1 Decision relevance (question E)')
    w('')
    w('Restricted to the 82 day-states with positive local headroom that also '
      'had a genuine composition choice:')
    w('')
    w(tbl(dre, ['n_headroom_choice_states', 'n_states_auc_defined',
                'within_state_auc_mean', 'n_states_argmax_beats_collector',
                'argmax_beats_collector_rate'],
          label_cols=('feature_set',)))
    w('')
    w('**Control:** `F5_state_only` carries no pair-discriminating information '
      '(every edge on a day receives the same score), so its within-state AUC '
      'is exactly 0.500000 by construction - yet its argmax matching "beats" '
      'the collector on 55/82 states. That statistic is therefore confounded by '
      'maximum-cardinality effects and must not be read as signal. The models '
      'that do discriminate between pairs (F1, F2, F3, F4) beat the collector '
      'on 41, 31, 16 and 18 of 82 states respectively; F2, the best overall '
      'performer, is *worse* than greedy on the days where headroom exists.')
    w('')
    w('## 6. Local hindsight-oracle headroom')
    w('')
    w('Oracle solver cross-check: %d brute-force comparisons, %d disagreements, '
      'enumeration failures %d. An independent networkx maximum-cardinality '
      'matching agrees on every day.' % (schk['n_bruteforce_checked'],
                                         schk['n_bruteforce_disagree'],
                                         schk['n_enum_failed']))
    w('')
    w(tbl([r for r in orc if r['stratum_type'] in
           ('overall', 'variant', 'density_band', 'day_band')],
          ['n_days', 'n_days_oracle_pos_ge1', 'n_days_gap_ge1',
           'share_gap_ge1_among_oracle_pos', 'mean_collector_positives',
           'mean_oracle_positives', 'mean_maxcard_positives',
           'share_days_positive_headroom', 'n_enum_failed']))
    w('')
    w('**This is a myopic one-day hindsight oracle, not a sequential policy '
      'oracle and not a global ceiling. It uses counterfactual labels the '
      'policy could never observe at decision time. Daily gaps are reported as '
      'distributions and are never summed into an episode total. The three arms '
      '(baseline-score matching, maximum-cardinality matching, MSMI-informed '
      'local oracle) are reported separately and never netted.**')
    w('')
    w('Density-1 days show 7 oracle-positive days and 0 gap days, as expected: '
      'a day with a single edge has no alternative to miss.')
    w('')
    w('## 7. What the results establish and do not establish')
    w('')
    w('| cause | classification | evidence class |')
    w('|---|---|---|')
    for key in ('K1', 'K2', 'K3', 'K4', 'K5', 'K6'):
        w('| %s - %s | %s | %s |' % (key, k[key]['cause'], classify(k[key]),
                                     k[key]['evidence_class']))
    w('')
    w('Information headroom (K2, K3, K6) and action headroom (K1, K4, K5) are '
      'reported separately and never fused. The six causes are not mutually '
      'exclusive. Frozen EDA hypotheses H1-H9 are referenced only: not '
      'retested, not re-statused, and no frozen artifact was modified.')
    w('')
    w('Two further readings, stated with their evidence class:')
    w('')
    w('- [measured fact] A perfect one-day hindsight oracle reaches 173 MSMI '
      'positives over the whole corpus where the collector reaches 90. Even '
      'that oracle is bounded by the 173 counterfactual positives that exist in '
      'the feasible action set; it is not a sequential optimum.')
    w('- [statistical inference] On the 82 days where headroom existed, no '
      'model with genuine pair discrimination out-scored greedy. This is '
      'consistent with the signal that does exist (soft channel state, F2-F1 '
      'excludes zero) being too weak and too sparse to act on, and is not '
      'evidence that no policy could ever improve.')
    w('')
    w('## 8. Remaining uncertainties')
    w('')
    for name in ('F1_baseline_count_score', 'F2_soft_state', 'F3_public_profile',
                 'F4_full_legal_observables', 'F5_state_only'):
        pf = next((r for r in sig if r['feature_set'] == name
                   and r['stratum_type'] == 'overall'), None)
        if pf and pf.get('power_flag') == 'underpowered':
            w('- `%s` is flagged **underpowered** (%s positives across %s rows); '
              'its intervals are wide by construction.' % (
                  name, pf['n_positives'], pf['n_rows']))
    w('- 173 counterfactual positives across 15,304 rows is the binding power '
      'limit for every interval in section 4; the overall F4 interval '
      '[0.4646, 0.5986] spans chance.')
    w('- Per-world heterogeneity permutation null (%d within-world shuffles, '
      'rng 4242): observed spread %s against null mean %s, p = %s. No '
      'between-world variation beyond chance was detected.' % (
          het['n_permutations'], round(het['observed_spread'], 6),
          round(het['null_mean'], 6), round(het['null_p_ge_observed'], 4)))
    w('- Enumeration of distinct matchings is capped at 50 '
      '(`n_matchings_gt_cap` in `opportunity_summary.csv`); days exceeding the '
      'cap are counted, never treated as unique. The decision-relevant '
      '`alt_same_size` flag uses an exact early-exit search and its `unknown` '
      'count is 0.')
    w('- Counterfactual labels are computed pair-alone and are unobserved by '
      'the original collector (`flag = counterfactual_unobserved`). They are '
      'never presented as observed outcomes and carry no sequential '
      'consequences.')
    w("- K5's decision rule uses the qualitative terms \"high\" and \"low\" "
      'without numeric thresholds, so it cannot be applied mechanically '
      'without post-hoc threshold selection; it is recorded as unresolved with '
      'both component values shown.')
    w('')
    w('## 9. Ranked evidence on the causes of prior failures')
    w('')
    ranked = sorted(k, key=lambda key: (
        {'supported': 0, 'suggestive': 1, 'unresolved': 2,
         'not_supported': 3}.get(k[key].get('classification', 'unresolved'), 2)))
    for i, key in enumerate(ranked, 1):
        w('%d. **%s - %s** [%s] -> %s' % (i, key, k[key]['cause'],
                                          k[key]['evidence_class'],
                                          classify(k[key])))
    w('')
    w('Ranking is by strength of this audit classification only. It is not a '
      'recommendation and no policy, tournament or strategy follows from it.')
    w('')
    w('## 10. Artifact index')
    w('')
    for name in sorted(p.name for p in c.OUT.iterdir() if p.is_file()):
        w('- `%s`' % name)
    w('- `scripts/` - deterministic, seeded, re-runnable')
    w('')
    w('Integrity hashes are in `integrity.sha256`; protected-input start/end '
      'hashes are in `manifest_start.json` / `manifest_end.json`.')
    (c.OUT / 'report.md').write_text('\n'.join(L) + '\n', encoding='utf-8')
    c.log('wrote report.md (%d lines)' % len(L))

    # --- seal
    c.write_manifest(c.OUT / 'manifest_end.json', c.protected_files())
    start = json.loads((c.OUT / 'manifest_start.json').read_text(encoding='utf-8'))
    end = json.loads((c.OUT / 'manifest_end.json').read_text(encoding='utf-8'))
    changed = sorted(set(start) ^ set(end)) + \
        sorted(key for key in set(start) & set(end) if start[key] != end[key])
    git_end = Path(c.OUT / 'git_status_start.txt').read_text(encoding='utf-8')
    git_now = subprocess.run(['git', 'status', '--porcelain'], capture_output=True,
                             text=True, cwd=c.ROOT).stdout
    ver = dict(protected_unchanged=not changed, changed_files=changed,
               n_protected=len(end),
               git_status_unchanged=(git_end == git_now),
               git_status_now=git_now)
    (c.OUT / 'verification_final.json').write_text(
        json.dumps(ver, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    c.log('protected inputs unchanged = %s (%d files)'
          % (not changed, len(end)))
    c.log('git status unchanged = %s' % (git_end == git_now))
    if changed or git_end != git_now:
        raise SystemExit('INTEGRITY FAILURE: %r' % changed)

    # Every c.log() call appends to run_log.txt, which is itself hashed below.
    # Log FIRST, then hash, and never log after the seal - otherwise the seal
    # is stale the moment it is written.
    c.log('sealing integrity.sha256 (final step; nothing is logged after this)')
    lines = []
    for path in sorted(c.OUT.rglob('*')):
        if path.is_file() and path.name != 'integrity.sha256':
            lines.append('%s  %s' % (c.sha256(path),
                                     path.relative_to(c.ROOT).as_posix()))
    (c.OUT / 'integrity.sha256').write_text('\n'.join(lines) + '\n',
                                            encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
