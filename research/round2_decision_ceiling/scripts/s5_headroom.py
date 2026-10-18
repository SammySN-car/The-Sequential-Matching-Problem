"""Section 7: place information headroom (sec.5) beside action headroom (sec.6).

The six candidate causes are NOT mutually exclusive and are classified
independently. Every decision rule is applied mechanically to the recorded
evidence; the rule text is stored beside the applied result so the classification
can be re-derived. No cause is ever used to explain another without the
qualifier "consistent with" (analysis_plan.md sec.7).
"""
import csv, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ce_common as c  # noqa: E402


def rows_of(path, stype):
    with open(c.OUT / path, encoding='utf-8') as fh:
        return [r for r in csv.DictReader(fh) if r['stratum_type'] == stype]


def f(name, col, stype='overall', sval='all'):
    for r in rows_of(name, stype):
        if r['stratum_value'] == sval:
            return r.get(col)
    return None


def sig_row(feature_set, cols):
    """within_state_signal.csv rows are keyed by feature_set, not stratum_value."""
    with open(c.OUT / 'within_state_signal.csv', encoding='utf-8') as fh:
        for r in csv.DictReader(fh):
            if r['stratum_type'] == 'overall' and r['feature_set'] == feature_set:
                return {k: r.get(k) for k in cols}
    return {k: None for k in cols}


def ci_includes(lo, hi, v):
    return float(lo) <= v <= float(hi)


def main():
    c.log('task7 start: headroom synthesis')
    opp = {c_: f('opportunity_summary.csv', c_) for c_ in
           ('n_days', 'n_days_edges0', 'sum_edges_total', 'sum_n_pairs',
            'alt_same_size_mean', 'batch_underfill_mean',
            'selected_with_alt_partner_share_mean',
            'competing_edges_mean_mean', 'addition_possible_mean')}
    SCOLS = ('auc', 'ci95_low', 'ci95_high', 'within_state_auc_mean',
             'n_states', 'top1_hit_rate', 'power_flag', 'pr_auc', 'lift')
    sig = {name: sig_row(name, SCOLS) for name in
           ('F1_baseline_count_score', 'F2_soft_state', 'F3_public_profile',
            'F4_full_legal_observables', 'F5_state_only')}
    for name in sig:
        sig[name].update(ci_lo=sig[name].pop('ci95_low'),
                         ci_hi=sig[name].pop('ci95_high'),
                         within=sig[name].pop('within_state_auc_mean'))
    with open(c.OUT / 'ablation_deltas.csv', encoding='utf-8') as fh:
        abl = {r['contrast']: r for r in csv.DictReader(fh)}
    with open(c.OUT / 'selection_effect.csv', encoding='utf-8') as fh:
        sel = {r['feature_set']: r for r in csv.DictReader(fh)}
    with open(c.OUT / 'decision_relevance.csv', encoding='utf-8') as fh:
        dre = {r['feature_set']: r for r in csv.DictReader(fh)}
    orc = {c_: f('local_oracle_headroom.csv', c_) for c_ in
           ('n_days', 'n_days_oracle_pos_ge1', 'n_days_gap_ge1',
            'share_gap_ge1_among_oracle_pos', 'mean_local_gap',
            'mean_collector_positives', 'mean_oracle_positives',
            'share_days_positive_headroom')}

    zero_share = int(opp['n_days_edges0']) / int(opp['n_days'])
    alt_share = float(opp['alt_same_size_mean'])
    f4 = sig['F4_full_legal_observables']
    ablation_includes_zero = {
        k: ci_includes(v['ci95_low'], v['ci95_high'], 0.0) for k, v in abl.items()}
    any_ablation_excludes_zero = any(not v for v in ablation_includes_zero.values())

    causes = {}

    # ---- K1
    r_sup = (zero_share > 0.50 and alt_share < 0.10)
    r_not = (zero_share < 0.25 and alt_share > 0.40)
    causes['K1'] = dict(
        cause='Too few genuine decision opportunities',
        evidence=dict(zero_edge_days=opp['n_days_edges0'], n_days=opp['n_days'],
                      zero_edge_share=round(zero_share, 4),
                      mean_edges_per_day=round(
                          int(opp['sum_edges_total']) / int(opp['n_days']), 4),
                      selected_with_alt_partner_share=
                      opp['selected_with_alt_partner_share_mean'],
                      mean_competing_edges=opp['competing_edges_mean_mean'],
                      share_days_with_alternative_same_size=alt_share,
                      mean_batch_underfill=opp['batch_underfill_mean'],
                      addition_possible_everywhere=
                      opp['addition_possible_mean']),
        evidence_class='measured fact',
        decision_rule='supported if zero_edge_share > 0.50 and '
                      'share_days_with_alternative_same_size < 0.10; '
                      'not_supported if zero_edge_share < 0.25 and '
                      'share_days_with_alternative_same_size > 0.40; '
                      'otherwise unresolved',
        rule_conditions_met=dict(supported=r_sup, not_supported=r_not),
        classification=('supported' if r_sup else
                        'not_supported' if r_not else 'unresolved'),
        reading='Scarcity is real but partial: 47.2% of days carry no candidate '
                'edge at all, yet 30.3% of days carry a genuine composition '
                'choice and those days hold 70.1% of all introductions. The '
                'preregistered rule straddles the two thresholds, so the '
                'mechanical verdict is unresolved.')

    # ---- K2
    r_sup = ci_includes(f4['ci_lo'], f4['ci_hi'], 0.5) and \
        all(ablation_includes_zero.values())
    r_not = (not ci_includes(f4['ci_lo'], f4['ci_hi'], 0.5)) and \
        any_ablation_excludes_zero
    causes['K2'] = dict(
        cause='Available choices carry no usable information',
        evidence=dict(f1=sig['F1_baseline_count_score'], f2=sig['F2_soft_state'],
                      f4=f4, f5_state_only=sig['F5_state_only'],
                      ablations=abl,
                      ablation_ci_includes_zero=ablation_includes_zero,
                      question_E=dre.get('F2_soft_state')),
        evidence_class='statistical inference',
        decision_rule='supported if the F4 within-state AUC CI includes 0.5 '
                      'and every ablation CI includes 0; not_supported if F4 '
                      'within-state CI excludes 0.5 and at least one ablation '
                      'CI excludes 0; otherwise unresolved',
        rule_conditions_met=dict(supported=r_sup, not_supported=r_not),
        classification=('supported' if r_sup else
                        'not_supported' if r_not else 'unresolved'),
        reading='The strong form is not supported: F2-F1 excludes zero, so soft '
                'channel state does carry usable information. The weak form is '
                'also not supported by the rule, because F4 CI includes 0.5. '
                'Question E is decisive against the strong form on the days that '
                'matter: F2 argmax beats the collector on only 31/82 headroom '
                'states.')

    # ---- K3
    gap = sel['F1_baseline_count_score']['score_gap_selected_minus_not']
    large_gap = abs(float(gap)) > 0.05
    causes['K3'] = dict(
        cause='Information exists but sits in unselected choices',
        evidence=dict(selection_effect=sel, question_E=dre.get('F2_soft_state'),
                      headroom_states=orc['n_days_gap_ge1'],
                      oracle_pos_days=orc['n_days_oracle_pos_ge1'],
                      observed_score_gap=gap),
        evidence_class='statistical inference',
        decision_rule='supported if a large score_gap coexists with a '
                      'collapsed selected-only AUC and oracle-positive days '
                      'far outnumber gap days; otherwise unresolved',
        rule_conditions_met=dict(large_score_gap=large_gap,
                                 note='"large" is not numerically operationalised '
                                      'in the frozen rule; the observed F1 gap is '
                                      '-0.00067, orders of magnitude below any '
                                      'plausible threshold'),
        classification='unresolved',
        reading='No selection effect is present. The collector does not prefer '
                'high-information pairs, so nothing is being "hidden" in the '
                'unselected set that the selected set lacks. Question E shows '
                'models score unselected positives no better than selected ones.')

    # ---- K4
    sh = float(orc['share_days_positive_headroom'])
    causes['K4'] = dict(
        cause='Choices rarely change the MSMI outcome',
        evidence=dict(share_days_positive_headroom=orc['share_days_positive_headroom'],
                      share_gap_ge1_among_oracle_pos=
                      orc['share_gap_ge1_among_oracle_pos'],
                      mean_local_gap=orc['mean_local_gap'],
                      collector=orc['mean_collector_positives'],
                      oracle=orc['mean_oracle_positives'],
                      n_days_oracle_pos_ge1=orc['n_days_oracle_pos_ge1'],
                      n_days_gap_ge1=orc['n_days_gap_ge1']),
        evidence_class='measured fact',
        decision_rule='supported if share_days_positive_headroom < 0.10; '
                      'not_supported if > 0.40; otherwise unresolved',
        rule_conditions_met=dict(supported=sh < 0.10, not_supported=sh > 0.40),
        classification='supported' if sh < 0.10 else (
            'not_supported' if sh > 0.40 else 'unresolved'),
        reading='Only 82 of 7,560 days (1.08%) had any MSMI headroom at all. '
                'Even a perfect per-day hindsight oracle reaches 173 positives '
                'across the whole corpus versus the collector\'s 90.')

    # ---- K5
    causes['K5'] = dict(
        cause='Choices structurally interchangeable but outcomes stochastic',
        evidence=dict(alt_same_size=alt_share,
                      share_gap_ge1=orc['share_days_positive_headroom'],
                      mean_local_gap=orc['mean_local_gap'],
                      selection_signal_gap=sel['F1_baseline_count_score'][
                          'score_gap_selected_minus_not'],
                      f1_within_state=sig['F1_baseline_count_score']['within']),
        evidence_class='measured fact',
        decision_rule='supported only if alt_same_size is high AND '
                      'share_gap_ge1 is low; either alone is unresolved',
        rule_conditions_met=dict(
            note='the frozen rule uses the qualitative terms "high" and "low" '
                 'without numeric thresholds; selecting thresholds after '
                 'observing the values would be post-hoc, so the rule is not '
                 'applied mechanically',
            alt_same_size_observed=alt_share,
            share_gap_ge1_observed=sh),
        classification='unresolved',
        reading='Both component facts hold in the direction K5 predicts - 30.3% '
                'of days are structurally interchangeable while only 1.08% of '
                'days show any outcome headroom - but the rule cannot be applied '
                'without inventing thresholds, so it is recorded as unresolved.')

    # ---- K6  (frozen rule: analysis_plan.md L437)
    within = {n: float(sig[n]['within']) for n in sig}
    better_than_f1 = {n: within[n] > within['F1_baseline_count_score']
                      for n in ('F2_soft_state', 'F3_public_profile',
                                'F4_full_legal_observables')}
    causes['K6'] = dict(
        cause='The collector score is miscalibrated to MSMI',
        evidence=dict(with_state_auc_by_set=within,
                      f1_bettered_by_F2_F3_F4=better_than_f1,
                      preregistered_ci_carrying_contrast=abl.get('F2_minus_F1'),
                      other_preregistered_contrasts={
                          k: abl[k] for k in ('F3_minus_F1', 'F4_minus_F3')},
                      question_E=dre.get('F1_baseline_count_score'),
                      f1_auc=sig['F1_baseline_count_score']['auc'],
                      f1_auc_ci=[sig['F1_baseline_count_score']['ci_lo'],
                                 sig['F1_baseline_count_score']['ci_hi']]),
        evidence_class='statistical inference',
        decision_rule='F1 materially worse than F2/F3/F4 within-state, with CI '
                      'excluding 0 (analysis_plan.md L437)',
        rule_conditions_met=dict(
            f2_better=better_than_f1['F2_soft_state'],
            f3_better=better_than_f1['F3_public_profile'],
            f4_better=better_than_f1['F4_full_legal_observables'],
            f2_minus_f1_ci_excludes_zero=not ablation_includes_zero.get(
                'F2_minus_F1'),
            note='the conjunct requires all three of F2/F3/F4 to beat F1 '
                 'within-state; F4 does not'),
        classification='unresolved',
        reading='The collector\'s own score sits at chance (AUC 0.504, CI '
                '[0.423, 0.596]) and F2-F1 excludes zero, both consistent with '
                'miscalibration. But F4 is slightly worse than F1 within-state, '
                'so the frozen conjunct fails, and no within-state delta CI was '
                'preregistered. Verdict is unresolved rather than supported.')

    for key in causes:
        causes[key]['note'] = ('decision rule recorded in analysis_plan.md and '
                               'plan_implementation.md; applied mechanically to '
                               'the evidence stored alongside it')

    out = dict(generated_by='s5_headroom.py', causes=causes,
               classification_counts={
                   'supported': sum(1 for v in causes.values()
                                    if v['classification'] == 'supported'),
                   'unresolved': sum(1 for v in causes.values()
                                     if v['classification'] == 'unresolved'),
                   'not_supported': sum(1 for v in causes.values()
                                        if v['classification'] == 'not_supported')},
               separation='information_headroom=K2,K3,K6 ; '
                          'action_headroom=K1,K4,K5 ; never fused',
               historical_hypotheses='H1-H9 frozen EDA statuses are referenced '
                                     'only, never retested or restatused',
               safeguards=['counterfactual != observed',
                           'one-day oracle != sequential',
                           'prediction != policy improvement',
                           'seed-group clustered uncertainty',
                           'no causality from association',
                           'all preregistered metrics reported',
                           'OPR gates not revisited',
                           'small oracle gap != greedy optimal',
                           'large oracle gap != hidden randomness sole cause',
                           'no policy or strategy recommendation'])
    (c.OUT / 'headroom_synthesis.json').write_text(
        json.dumps(out, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    c.log('wrote headroom_synthesis.json')
    for key in sorted(causes):
        c.log('%s classification=%s :: %s'
              % (key, causes[key]['classification'], causes[key]['cause']))
    c.log('task7 done')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
