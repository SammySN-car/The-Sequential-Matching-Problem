"""Round 2 Stage 4 - build summary.json from the Stage 4 result artifacts."""
import hashlib
import json
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def load(name):
    return json.loads((HERE / name).read_text(encoding='utf-8'))


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


x0, x1, q3 = load('x0_results.json'), load('x1_results.json'), load('q3_noise_results.json')
integ = load('integrity_after.json')

mu, ms = x0['targets']['mutual'], x0['targets']['msmi']
summary = {
    'schema': 'round2_stage4_summary_v1',
    'generated': time.strftime('%Y-%m-%d %H:%M:%S'),
    'stage': 'round2_stage4_history_coldstart_audit',
    'decision_memo': {
        'Q1_history_signal': {
            'answer': 'YES-small for mutual; NO/inconclusive for MSMI',
            'mutual_delta_auc': mu['overall']['delta_auc_a_minus_b'],
            'mutual_ci95': mu['world_cluster_bootstrap']['delta_auc']['ci95_percentile'],
            'mutual_strata_all_positive': all(
                v.get('delta_auc') is not None and v['delta_auc'] > 0
                for v in mu['strata_validation_only']['joint'].values()),
            'msmi_delta_auc': ms['overall']['delta_auc_a_minus_b'],
            'msmi_ci95': ms['world_cluster_bootstrap']['delta_auc']['ci95_percentile'],
            'vs_heuristics': 'mutual between <0.01 weak and >=0.02 meaningful; '
                             'MSMI CI includes 0',
            'confidence': 'moderate (exact pipeline reproduction, world-clustered)'},
        'Q2_newcomer_penalty': {
            'answer': 'not observed at variant level; candidate-level '
                      'experience = UNKNOWN (STOP rule applied)',
            'cold_start_above_others_count': x1['coldstart_vs_others']
                ['cold_start_gt_others_count'],
            'cold_start_settings': x1['coldstart_vs_others']['n_settings'],
            'stage15_cold_start_exclusion': x1['variant_tables']
                ['stage1.5_seed101_original_floor']['cold_start']['excl_frozen'],
            'day_proxy_pooled_exclusion': {
                k: v['excl_frozen'] for k, v in
                x1['day_proxy_curves']['stage1.5_seed101_pooled'].items()},
            'stop_reason': x1['limitations'][0]['claim'],
            'dominant_driver_observed': 'profile sparsity (sparse variant '
                                        '94.2% excluded, 47/60 all-below-floor '
                                        'days), not newcomer status'},
        'Q3_promotion_noise': {
            'paired_sd_intermediate_minus_frozen': q3['noise_estimate']
                ['paired_sd'],
            'paired_diffs': {k: {'mean': v['mean'], 'sd': v['sd_across_seeds']}
                             for k, v in q3['paired_differences'].items()},
            'normal_approx_seeds': q3['noise_estimate']
                ['normal_approx_guidance'],
            'crn': 'kit.py outcomes are content-addressed per '
                   '(world_seed, pair, day): exact world-level CRN + exact '
                   'shared-(pair,day) outcome coupling; floor-induced '
                   'selection divergence breaks most shared keys; rare MSMI '
                   'events (9-13/arm) dominate residual noise',
            'recommendation': 'retain same-seed paired comparisons; ~12 paired '
                              'seeds for 0.2-scale effects, ~46 for 0.1-scale'},
        'Q4_promotion': {
            'decision': 'PROCEED',
            'grounds': 'X0 no blocker (history lift small/additive); X1 no '
                       'cold-start penalty to exacerbate; Stage 3 option 2 '
                       'unchanged; exploration/cold-start work optional '
                       'follow-up (low-moderate priority), not promotion-blocking',
            'would_change_it': 'candidate-level experience analysis (needs new '
                               'runs, separate approval) or inability to fund '
                               '>= ~12 paired seeds in the promotion protocol'},
    },
    'x0': {
        'dataset': x0['input'],
        'split': {k: x0['split'][k] for k in
                  ('train_rows', 'val_rows', 'train_worlds', 'val_worlds',
                   'split_overlap')},
        'models': {'a_features': x0['config']['model_a_features'],
                   'b_features': x0['config']['model_b_features'],
                   'removed': x0['config']['removed_feature_keys'],
                   'hyperparameters': x0['config']['model']},
        'fidelity_check': x0['reproduction_check_vs_scale800_report_json'],
        'mutual': {
            'model_a': mu['overall']['model_a'],
            'model_b': mu['overall']['model_b'],
            'delta_auc': mu['overall']['delta_auc_a_minus_b'],
            'delta_auc_ci95': mu['world_cluster_bootstrap']['delta_auc'],
            'delta_ap': mu['overall']['delta_ap_a_minus_b'],
            'delta_ap_ci95': mu['world_cluster_bootstrap']['delta_ap'],
            'delta_logloss': mu['overall']['delta_logloss_a_minus_b'],
            'delta_brier': mu['overall']['delta_brier_a_minus_b'],
            'experience_marginal_dauc': {
                k: v['delta_auc'] for k, v in
                mu['strata_validation_only']['experience'].items()},
            'policy_marginal_dauc': {
                k: v['delta_auc'] for k, v in
                mu['strata_validation_only']['policy'].items()},
        },
        'msmi': {
            'model_a': ms['overall']['model_a'],
            'model_b': ms['overall']['model_b'],
            'delta_auc': ms['overall']['delta_auc_a_minus_b'],
            'delta_auc_ci95': ms['world_cluster_bootstrap']['delta_auc'],
            'delta_ap': ms['overall']['delta_ap_a_minus_b'],
            'delta_ap_ci95': ms['world_cluster_bootstrap']['delta_ap'],
            'delta_logloss': ms['overall']['delta_logloss_a_minus_b'],
            'delta_brier': ms['overall']['delta_brier_a_minus_b'],
            'stability_warning': 'joint-cell positives 1-16; cell-level '
                                 'deltas unreliable; rely on clustered CI',
        },
        'bootstrap': x0['config']['bootstrap'],
        'stratification': x0['config']['stratification'],
    },
    'x1': {
        'determinism_probe_run1_eq_run2': x1['determinism']
            ['probe_run1_equals_run2'],
        'stage15_exclusion_by_variant': {
            v: b['excl_frozen'] for v, b in
            x1['variant_tables']['stage1.5_seed101_original_floor'].items()},
        'stage15_zero_selection_days': {
            v: b['zero_selected_categories'] for v, b in
            x1['variant_tables']['stage1.5_seed101_original_floor'].items()},
        'day_proxy_pooled': {k: v['excl_frozen'] for k, v in
                             x1['day_proxy_curves']
                             ['stage1.5_seed101_pooled'].items()},
        'coldstart_vs_others': {
            'n_settings': x1['coldstart_vs_others']['n_settings'],
            'cold_start_gt_others': x1['coldstart_vs_others']
                ['cold_start_gt_others_count'],
        },
        'limitations': x1['limitations'],
    },
    'rng_audit': {
        'file': 'kit.py (read-only, sha16 0D2CB3D3B46CA2A6)',
        'keyed_rng': 'kit.rand_for = Random(SHA256(parts)[:16]) - stateless, '
                     'content-addressed, no global stream',
        'outcome_key': '(world_seed, member_a, member_b, introduction_day)',
        'world_level_crn': 'exact (generate(seed) identical for all policies)',
        'pair_day_crn': 'exact on shared (pair, day) keys; conditional draw '
                        'paths deterministic within key',
        'asks_random': False,
        'coupling_limits': ['floor changes selection -> keys diverge',
                            'day in key -> timing shifts decouple',
                            'drift variant probability depends on day>=35',
                            'rare MSMI funnel dominates residual variance'],
    },
    'integrity': {'checked': integ['checked'],
                  'all_match': integ['all_match']},
    'prohibitions': {
        'new_policy_or_model_tuning': False,
        'promotion_experiment': False, 'holdout_access': False,
        'threshold_sweeps': False, 'episode_seeds_107_118_used': False,
        'thompson_or_rl': False, 'frozen_files_modified': False,
        'simulator_episodes_run': False},
    'evidence_tags': ['OBSERVED', 'INTERPRETATION', 'HYPOTHESIS',
                      'UNKNOWN', 'RECOMMENDATION'],
}

files = ['report.md', 'run_log.txt', 'x0_history_lift.py', 'x0_results.json',
         'x1_coldstart_penalty.py', 'x1_results.json',
         'q3_noise_from_stage3.py', 'q3_noise_results.json',
         'verify_integrity.py', 'integrity_after.json', 'build_summary.py']
summary['artifacts'] = [
    {'name': n, 'bytes': (HERE / n).stat().st_size, 'sha256': sha(HERE / n)}
    for n in files if (HERE / n).exists()]

(HERE / 'summary.json').write_text(json.dumps(summary, indent=2),
                                   encoding='utf-8')
print('summary.json written:', (HERE / 'summary.json').stat().st_size, 'bytes')
print('decision:', summary['decision_memo']['Q4_promotion']['decision'])