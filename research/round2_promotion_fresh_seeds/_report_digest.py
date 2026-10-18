import json, statistics, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
d = json.loads((HERE / 'summary.json').read_text(encoding='utf-8'))
print('--- per arm pooled ---')
for a, e in d['official_per_arm'].items():
    p = e['pooled_72']
    print(a, 'primary', e['primary_score_official'],
          'intro/100arr %.2f' % p['intro_per_100_arrived'],
          'mutual/100 %.3f' % p['mutual_acceptances_per_100'],
          'mut/inter %.4f' % p['mutual_per_intro'],
          'msmi/100intro %.3f' % p['msmi_per_100_intro'],
          'cov %.4f' % p['coverage'], 'ask', p['ask_cost'],
          'infr %.1fs' % e['inference_seconds_mean'])
print('--- contrasts C-B all keys ---')
for k, v in d['paired_contrasts']['floorhalf_minus_original'].items():
    print(' %-32s mean %+.4f ci [%+.4f,%+.4f] w%s seedw%s' % (
        k, v['mean'], v['ci95_cluster'][0], v['ci95_cluster'][1],
        v['worlds'], v['seed_level']['wt_l']))
print('--- contrasts C-A all keys ---')
for k, v in d['paired_contrasts']['floorhalf_minus_greedy'].items():
    print(' %-32s mean %+.4f ci [%+.4f,%+.4f] w%s' % (
        k, v['mean'], v['ci95_cluster'][0], v['ci95_cluster'][1], v['worlds']))
print('--- per seed C-B primary ---')
print(d['paired_contrasts']['floorhalf_minus_original']['msmi_per_100_arrived_members']['seed_level']['per_seed'])
print('--- volume ---')
v = d['volume_confirmation']
print(v['worlds'], 'ci', v['ci95_cluster'], 'seed', v['seed_level_wt_l'], 'median', v['median_delta'])
print('--- mutual ---')
m = d['mutual_no_harm']
print('rel%', m['relative_change_pct'], 'ci', m['relative_change_ci95'], 'diffci', m['paired_diff_ci95_cluster'], 'seedwtl', m['seed_level_wt_l'])
print('--- diagnostics B (frozen/original) ---')
b = d['diagnostics']['original']['pooled']
print('fid', d['diagnostics']['original']['fidelity_pass_seeds'], b)
print('asks/ep', d['diagnostics']['original']['asks_n_per_episode'], 'cats', d['diagnostics']['original']['zero_selected_categories'])
print('surv', d['diagnostics']['original']['survivorship_pooled'])
print('--- diagnostics C (intermediate/floorhalf) ---')
c = d['diagnostics']['floorhalf']['pooled']
print('fid', d['diagnostics']['floorhalf']['fidelity_pass_seeds'], c)
print('asks/ep', d['diagnostics']['floorhalf']['asks_n_per_episode'], 'cats', d['diagnostics']['floorhalf']['zero_selected_categories'])
print('surv', d['diagnostics']['floorhalf']['survivorship_pooled'])
print('--- per variant primary ---')
for v, e in d['per_variant'].items():
    print(' %-12s A %.3f B %.3f C %.3f | C-B d%+.3f %s ci%s | C-A d%+.3f %s | assign C-B %+0.1f %s' % (
        v, e['greedy']['msmi_per_100_arrived_members'],
        e['original']['msmi_per_100_arrived_members'],
        e['floorhalf']['msmi_per_100_arrived_members'],
        e['floorhalf_minus_original']['msmi_delta_mean'],
        e['floorhalf_minus_original']['msmi_wt_l'],
        e['floorhalf_minus_original']['msmi_ci95'],
        e['floorhalf_minus_greedy']['msmi_delta_mean'],
        e['floorhalf_minus_greedy']['msmi_wt_l'],
        e['floorhalf_minus_original']['assign_delta_mean'],
        e['floorhalf_minus_original']['assign_wt_l']))
print('--- runtime ---')
print(d['runtime']['per_seed_run_wall_seconds_6_episodes'])
print('--- integrity ---')
print('g1', d['integrity']['g1'])
print('g2 all', d['integrity']['g2']['all_equal'], 'g3', d['integrity']['g3']['pass'])