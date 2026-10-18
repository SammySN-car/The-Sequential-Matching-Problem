"""Paired analysis, retention, selection, and verdicts for the method tournament.

design.md: section 5 (metrics), 7 (retention), 9 (selection and verdict).
Ranking uses ONLY paired same-world deltas of msmi_per_100_arrived_members versus
the shared greedy control. Never AUC, offline expected value, mutual acceptances,
introduction counts, or ask efficiency. Absolute numbers are never compared across
seed sets (the 0.4931 incumbent is a different seed set).
"""
import argparse
import json
import math
import pathlib
import statistics
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_tournament as rt  # noqa: E402

T95 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365,
       8: 2.306, 9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179, 13: 2.160,
       14: 2.145, 15: 2.131, 16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093,
       20: 2.086, 24: 2.064, 29: 2.045, 35: 2.030, 40: 2.021, 49: 2.010,
       59: 2.001, 71: 1.994, 89: 1.987, 119: 1.980}
T99 = {1: 63.657, 2: 9.925, 3: 5.841, 4: 4.604, 5: 4.032, 6: 3.707, 7: 3.499,
       8: 3.355, 9: 3.250, 10: 3.169, 11: 3.106, 12: 3.055, 13: 3.012,
       14: 2.977, 15: 2.947, 16: 2.921, 17: 2.898, 18: 2.878, 19: 2.861,
       20: 2.845, 24: 2.797, 29: 2.756, 35: 2.724, 40: 2.704, 49: 2.680,
       59: 2.660, 71: 2.640, 89: 2.620, 119: 2.601}

NOT_RANKED_NOTE = ('Ranking metric: mean paired delta of MSMI/100 vs control. '
                   'Never AUC, offline expected value, mutual acceptances, '
                   'introduction counts, or ask efficiency. Absolute numbers are '
                   'never compared across seed sets.')


# design section 7 latency gate is PER INVOCATION ('all invocations valid, i.e.
# under 10 s each'); evaluate.episode enforces timeout=10 on each of the 120
# invokes (60 decision days x ask+match) and rows carry the episode TOTAL.
INVOKES_PER_EPISODE = 120


def t_critical(df, level=95):
    """Conservative tabulated two-sided t critical (largest tabulated df <= df).

    level=95 for screening/secondary intervals; level=99 for the Phase-3
    Bonferroni gate when k=2 candidates are tested (design.md section 9:
    k=1 -> 95%, t=2.201; k=2 -> 99%, t=3.106; both at df=11).
    """
    if df <= 0:
        return float('inf')
    table = T99 if level == 99 else T95
    return table[max(k for k in table if k <= df)]


def load_phase_rows(phase):
    return rt.dedupe(rt.load_rows(HERE / 'per_phase' / (phase + '_rows.jsonl')))


def control_map(rows):
    return {(r['seed'], r['variant']): r for r in rows
            if r['method'] == rt.CONTROL}


def paired_deltas(rows, method, ctrl):
    """[(seed, variant, delta)] sorted; delta is None where either side is invalid."""
    out = []
    for r in rows:
        if r['method'] != method:
            continue
        key = (r['seed'], r['variant'])
        c = ctrl.get(key)
        if c is None or not r.get('valid') or not c.get('valid'):
            out.append((r['seed'], r['variant'], None))
        else:
            out.append((r['seed'], r['variant'],
                        r['msmi_per_100_arrived_members']
                        - c['msmi_per_100_arrived_members']))
    return sorted(out)


def _eligibility(s):
    """design.md section 7: every gate is required for retention.

    m01 never reaches this function - it is excluded upstream (parity control).
    """
    reasons = []
    if s['invalid_episodes']:
        reasons.append('%d invalid episode(s)' % s['invalid_episodes'])
    max_inf = (s.get('secondary') or {}).get('max_inference_seconds')
    if max_inf is None:
        reasons.append('no latency evidence (max_inference_seconds missing)')
    elif max_inf / INVOKES_PER_EPISODE > 10.0:
        reasons.append('latency gate: per-invocation inference %.3f s exceeds '
                       '10 s' % (max_inf / INVOKES_PER_EPISODE))
    if s['n_units'] == 0:
        reasons.append('zero paired units')
    if s['mean_delta'] is None:
        reasons.append('no valid paired units')
    else:
        if s['mean_delta'] < -0.05:
            reasons.append('mean delta %.4f below -0.05' % s['mean_delta'])
        bad = sorted(v for v, m in s['per_variant_mean_delta'].items()
                     if m is not None and m < -0.15)
        if bad:
            reasons.append('catastrophic family: ' + ', '.join(bad))
    return (not reasons), reasons


def seed_level_deltas(pairs):
    """[(seed, mean delta)] - the 6 variants are averaged within seed first.

    Variants share one seeded world per seed (design.md section 9), so
    inference runs on the seed-level means (df = n_seeds - 1); per-variant
    means stay in the summary as mandatory stratification.
    """
    by_seed = {}
    for s, _v, d in pairs:
        if d is not None:
            by_seed.setdefault(s, []).append(d)
    return sorted((s, statistics.mean(ds))
                  for s, ds in by_seed.items() if ds)


def method_summary(rows, method, ctrl):
    mrows = [r for r in rows if r['method'] == method]
    invalid = sum(1 for r in mrows if not r.get('valid'))
    pairs = paired_deltas(rows, method, ctrl)
    per_variant = {}
    for variant in rt.VARIANTS:
        vd = [d for _s, v, d in pairs if v == variant and d is not None]
        per_variant[variant] = statistics.mean(vd) if vd else None
    cluster = seed_level_deltas(pairs)
    cluster_vals = [m for _s, m in cluster]
    n_seeds = len(cluster_vals)
    if n_seeds:
        mean = statistics.mean(cluster_vals)
        if n_seeds >= 2:
            se = statistics.stdev(cluster_vals) / math.sqrt(n_seeds)
            dof = n_seeds - 1
            ci95 = [round(mean - t_critical(dof, 95) * se, 6),
                    round(mean + t_critical(dof, 95) * se, 6)]
            ci99 = [round(mean - t_critical(dof, 99) * se, 6),
                    round(mean + t_critical(dof, 99) * se, 6)]
        else:
            ci95, ci99 = [None, None], [None, None]
    else:
        mean, ci95, ci99 = None, [None, None], [None, None]
    valid = [r for r in mrows if r.get('valid')]
    # within-seed cross-variant dispersion of deltas (design.md section 5)
    dispersions = []
    for s in sorted({s for s, _v, d in pairs if d is not None}):
        sv = [d for s2, _v, d in pairs if s2 == s and d is not None]
        if len(sv) >= 2:
            dispersions.append(statistics.stdev(sv))
    # behavioral distinctness (honesty reporting; never a ranking input)
    distinct = len({r['action_sha256'] for r in valid})
    differing = 0
    for r in valid:
        c = ctrl.get((r['seed'], r['variant']))
        if c is not None and c.get('valid') and r['action_sha256'] != c['action_sha256']:
            differing += 1
    summary = {
        'n_units': len([d for _s, _v, d in pairs if d is not None]),
        'n_seeds': n_seeds,
        'invalid_episodes': invalid,
        'mean_delta': mean,
        'ci95': ci95,
        'ci99': ci99,
        'per_variant_mean_delta': per_variant,
        'cross_variant_dispersion_mean': (round(statistics.mean(dispersions), 6)
                                          if dispersions else None),
        'behavioral': {'distinct_digests': distinct,
                       'worlds_differing_from_control': differing},
        'secondary': {
            'coverage_mean': round(statistics.mean(
                r['coverage'] for r in valid), 4) if valid else None,
            'ask_cost_mean': round(statistics.mean(
                r['ask_cost'] for r in valid), 1) if valid else None,
            'intros_per_100_mean': round(statistics.mean(
                100.0 * r['assignments'] / max(1, r['arrived_members'])
                for r in valid), 3) if valid else None,
            'max_inference_seconds': round(max(
                r['inference_seconds'] for r in valid), 1) if valid else None,
        },
    }
    summary['eligible'], summary['ineligibility_reasons'] = _eligibility(summary)
    return summary


def check_control_parity(rows, method='m01_greedy_baseline'):
    ctrl = control_map(rows)
    mismatched, checked = [], 0
    for r in sorted(rows, key=lambda x: (x['method'], x['seed'], x['variant'])):
        if r['method'] != method:
            continue
        checked += 1
        c = ctrl.get((r['seed'], r['variant']))
        if (c is None or not r.get('valid') or not c.get('valid')
                or r['action_sha256'] != c['action_sha256']):
            mismatched.append({'seed': r['seed'], 'variant': r['variant']})
    return {'worlds_checked': checked, 'mismatched_worlds': mismatched}


def select_top(per, k=2):
    """design.md section 9: top-k by FULL-precision mean delta.

    Sign-independent; zero-invalid only (an invalid method can never satisfy
    section 9 credibility); m01_greedy_baseline excluded (parity control);
    ties broken by (round(mean, 6), method_id) - never display-rounded values.
    """
    pool = [m for m in per
            if m != 'm01_greedy_baseline'
            and per[m]['invalid_episodes'] == 0
            and per[m]['mean_delta'] is not None]
    return sorted(pool, key=lambda m: (-per[m]['mean_delta'],
                                       round(per[m]['mean_delta'], 6), m))[:k]


def credible(s, level=95):
    """design.md section 9 Phase-3 credibility: ALL conditions required.

    The cluster CI must clear zero at the Bonferroni level for the number of
    candidates tested (k=1 -> 95%, k=2 -> 99%; design.md section 9).
    """
    ci = s['ci99'] if level == 99 else s['ci95']
    return (s['invalid_episodes'] == 0
            and s['mean_delta'] is not None and s['mean_delta'] > 0
            and ci[0] is not None and ci[0] > 0
            and all(m is not None and m >= -0.15
                    for m in s['per_variant_mean_delta'].values()))


def retention(per, eligible):
    """design.md section 7: first min(5, E) core + next up to 3 diagnostics.

    eligible arrives ranked (full precision, ties by (round(mean, 6), id));
    returns (top5, diagnostics, retained). E = 0 -> ([], [], []), which
    triggers the Phase-2/3 skip branch (design.md section 7).
    """
    top5 = eligible[:5]
    diagnostics = []
    for m in eligible[5:8]:
        pv = per[m]['per_variant_mean_delta']
        valued = [(v, x) for v, x in pv.items() if x is not None]
        if valued:
            best_v, best_x = max(valued, key=lambda t: t[1])
            reason = ('next-ranked eligible (mean %+.4f); strongest family '
                      'signal %+.4f on %s' % (per[m]['mean_delta'], best_x, best_v))
        else:
            reason = ('next-ranked eligible (mean %+.4f); no family signal'
                      % per[m]['mean_delta'])
        diagnostics.append({'method': m, 'reason': reason})
    retained = top5 + [d['method'] for d in diagnostics]
    return top5, diagnostics, retained


def assert_code_fingerprint(rows, phase, pre=None):
    """design.md section 8: every row must carry the pre-screening fingerprint."""
    pre = (pathlib.Path(pre) if pre else
           HERE / 'hashes' / ('pre_%s_fingerprint.txt' % phase))
    if not pre.exists():
        raise SystemExit('phase-start fingerprint missing: ' + str(pre))
    want = pre.read_text(encoding='utf-8').strip()
    bad = [r for r in rows if r.get('code_sha256') != want]
    if bad:
        raise SystemExit('%d %s rows carry a foreign code_sha256 (want %s...)'
                         % (len(bad), phase, want[:16]))
    return want[:16]


def _guard_delta(rows, method, ctrl, key):
    vals = []
    for r in rows:
        if r['method'] != method:
            continue
        c = ctrl.get((r['seed'], r['variant']))
        if c is not None and r.get('valid') and c.get('valid'):
            vals.append(r[key] - c[key])
    return round(statistics.mean(vals), 4) if vals else None


def _fmt_ci(ci):
    return '[n/a]' if ci[0] is None else '[%+.4f, %+.4f]' % (ci[0], ci[1])


def _write(name, text):
    path = HERE / name
    path.write_text(text, encoding='utf-8')
    print('wrote ' + name)


def analyse_screening():
    rows = load_phase_rows('screening')
    fp16 = assert_code_fingerprint(rows, 'screening')
    ctrl = control_map(rows)
    methods = sorted({r['method'] for r in rows} - {rt.CONTROL})
    per = {m: method_summary(rows, m, ctrl) for m in methods}
    parity = check_control_parity(rows)
    if parity['mismatched_worlds'] or parity['worlds_checked'] != 18:
        print(json.dumps(parity, indent=2))
        raise SystemExit('m01 control parity FAILED (expected 18/18 identical)')
    # m01 is excluded from eligibility, ranking, and retention (design section 7)
    rank_pool = [m for m in methods if m != 'm01_greedy_baseline']
    eligible = sorted((m for m in rank_pool if per[m]['eligible']),
                      key=lambda m: (-per[m]['mean_delta'],
                                     round(per[m]['mean_delta'], 6), m))
    top5, diagnostics, retained = retention(per, eligible)
    results = {
        'phase': 'screening', 'worlds': 18,
        'seeds': [143, 144, 145], 'variants': list(rt.VARIANTS),
        'code_fingerprint': fp16,
        'control_parity': parity, 'per_method': per,
        'eligible_ranking': eligible, 'top5': top5,
        'diagnostic_candidates': diagnostics, 'retained': retained,
        'behavioral_diversity': {m: per[m]['behavioral'] for m in sorted(per)},
        'dispersion': {m: per[m]['cross_variant_dispersion_mean']
                       for m in sorted(per)},
        'm01_excluded_note': ('m01_greedy_baseline is excluded from eligibility, '
                              'ranking, and retention (parity/diagnostic only; '
                              'design section 7).'),
        'not_ranked_note': NOT_RANKED_NOTE,
        'no_winner_note': ('Phase 1 has 18 paired worlds: no method may be '
                           'called a winner from screening alone.'),
        'cluster_note': ('Inference clusters on seed: 6 per-variant deltas are '
                         'averaged per seed -> 12 seed-level means (df = 11); '
                         'screening is gate-only (design section 9).'),
    }
    _write('screening_results.json',
           json.dumps(results, indent=2, sort_keys=True, allow_nan=False) + '\n')
    _write('screening_report.md', _screening_md(results))
    print(json.dumps({'retained': retained, 'eligible': len(eligible),
                      'ineligible': len(rank_pool) - len(eligible),
                      'code_fingerprint': fp16}, indent=2))
    return 0


def _screening_md(res):
    per = res['per_method']
    parity = res['control_parity']
    lines = ['# Method Tournament - Phase 1 Screening Report', '',
             '- Worlds: %d (seeds 143-145 x 6 variants), paired vs shared '
             'greedy control.' % res['worlds'],
             '- Control parity: m01 digests identical to policy.py --baseline '
             'greedy on %d/%d worlds.' % (parity['worlds_checked'], res['worlds']),
             '- ' + res['no_winner_note'],
             '- ' + res['m01_excluded_note'],
             '- ' + res['cluster_note'],
             '- Screening code fingerprint: ' + res['code_fingerprint'] +
             ' (verified on every row).',
             '- ' + res['not_ranked_note'], '',
             '## Leaderboard (eligible, ranked by mean paired delta)', '',
             '| rank | method | mean delta | cluster 95% CI | invalid | worst variant '
             '| retained |',
             '|---|---|---|---|---|---|---|']
    retained = set(res['retained'])
    for i, m in enumerate(res['eligible_ranking'], 1):
        s = per[m]
        pv = [x for x in s['per_variant_mean_delta'].values() if x is not None]
        worst = min(pv) if pv else None
        lines.append('| %d | %s | %+.4f | %s | %d | %s | %s |' % (
            i, m, s['mean_delta'], _fmt_ci(s['ci95']), s['invalid_episodes'],
            ('%+.4f' % worst) if worst is not None else 'n/a',
            'YES' if m in retained else ''))
    lines += ['', '## Ineligible methods', '']
    ineligible = [m for m in sorted(per) if not per[m]['eligible']]
    if ineligible:
        for m in ineligible:
            lines.append('- **%s**: %s' % (m, '; '.join(
                per[m]['ineligibility_reasons'])))
    else:
        lines.append('- (none)')
    lines += ['', '## Retention decisions (design section 7)', '',
              '- Retained top-5: ' + ', '.join(res['top5'])]
    if res['diagnostic_candidates']:
        lines.append('- Diagnostic candidates (slots 6-8, human gate confirms):')
        for d in res['diagnostic_candidates']:
            lines.append('  - %s: %s' % (d['method'], d['reason']))
    else:
        lines.append('- Diagnostic candidates: none beyond top-5.')
    lines += ['', '## Behavioral distinctness (honesty check, never ranking)', '',
              '| method | distinct action digests | worlds differing from control |',
              '|---|---|---|']
    for m in sorted(res['behavioral_diversity']):
        b = res['behavioral_diversity'][m]
        lines.append('| %s | %d | %d |' % (
            m, b['distinct_digests'], b['worlds_differing_from_control']))
    lines += ['', '## Cross-variant dispersion (within-seed, diagnostic)', '']
    for m in sorted(res['dispersion']):
        d = res['dispersion'][m]
        lines.append('- %s: %s' % (
            m, 'n/a' if d is None else '%.4f' % d))
    lines += ['', '## Secondary diagnostics (never ranking inputs)', '',
              '| method | coverage | ask cost | intros/100 | max inference s |',
              '|---|---|---|---|---|']
    for m in sorted(per):
        sec = per[m]['secondary']
        lines.append('| %s | %s | %s | %s | %s |' % (
            m, sec['coverage_mean'], sec['ask_cost_mean'],
            sec['intros_per_100_mean'], sec['max_inference_seconds']))
    lines.append('')
    return '\n'.join(lines)


def analyse_confirm1():
    rows = load_phase_rows('confirm1')
    fp16 = assert_code_fingerprint(rows, 'confirm1')
    ctrl = control_map(rows)
    screening = json.loads((HERE / 'screening_results.json')
                           .read_text(encoding='utf-8'))
    methods = screening['retained']
    per = {m: method_summary(rows, m, ctrl) for m in methods}
    selected = select_top(per, 2)
    results = {
        'phase': 'confirm1', 'worlds': 36, 'arms': methods,
        'code_fingerprint': fp16,
        'per_method': per, 'selected': selected,
        'selection_rule': ('Top 2 by FULL-precision mean paired delta '
                           '(sign-independent); zero-invalid only; m01 excluded; '
                           'ties by (round(mean, 6), method_id) (design section 9).'),
        'not_ranked_note': NOT_RANKED_NOTE,
        'cluster_note': ('Inference clusters on seed: 6 per-variant deltas are '
                         'averaged per seed -> 12 seed-level means (df = 11) '
                         '(design section 9).'),
    }
    _write('confirmation_results.json',
           json.dumps(results, indent=2, sort_keys=True, allow_nan=False) + '\n')
    _write('confirmation_report.md', _confirm_md(results, 'Phase 2 Confirmation'))
    print(json.dumps({'selected': selected}, indent=2))
    return 0


def _confirm_md(res, title):
    per = res['per_method']
    lines = ['# Method Tournament - %s Report' % title, '',
             '- Worlds: %d, arms: %s + shared control.' % (res['worlds'],
                                                           ', '.join(res['arms']) or '(none)'),
             '- ' + res.get('selection_rule', ''),
             '- ' + res.get('cluster_note', '')]
    if res.get('code_fingerprint'):
        lines.append('- Code fingerprint: ' + res['code_fingerprint'] +
                     ' (verified on every row).')
    lines += ['- ' + res.get('not_ranked_note', ''), '',
              '| method | mean delta | cluster 95% CI | invalid | worst variant | '
              'coverage | ask cost |',
              '|---|---|---|---|---|---|---|']
    for m in sorted(per):
        s = per[m]
        pv = [x for x in s['per_variant_mean_delta'].values() if x is not None]
        worst = min(pv) if pv else None
        lines.append('| %s | %s | %s | %d | %s | %s | %s |' % (
            m, ('%+.4f' % s['mean_delta']) if s['mean_delta'] is not None else 'n/a',
            _fmt_ci(s['ci95']), s['invalid_episodes'],
            ('%+.4f' % worst) if worst is not None else 'n/a',
            s['secondary']['coverage_mean'], s['secondary']['ask_cost_mean']))
    lines += ['', 'Selected for Phase 3: ' + (', '.join(res['selected'])
                                              if res['selected'] else '(none)'), '']
    return '\n'.join(lines)


def analyse_confirm2():
    rows = load_phase_rows('confirm2')
    fp16 = assert_code_fingerprint(rows, 'confirm2')
    ctrl = control_map(rows)
    confirmation = json.loads((HERE / 'confirmation_results.json')
                              .read_text(encoding='utf-8'))
    candidates = confirmation['selected']
    per = {m: method_summary(rows, m, ctrl) for m in candidates}
    # Bonferroni over tested candidates (design section 9): k=1 -> 95%, k=2 -> 99%
    level = 95 if len(candidates) <= 1 else 99
    cred = sorted((m for m in candidates if credible(per[m], level)),
                  key=lambda m: (-per[m]['mean_delta'], m))
    winner = cred[0] if cred else None
    verdict = ('%s is credible on Phase 3 (72 paired units).' % winner
               if winner else
               'Greedy remains the best empirically supported policy among the evaluated candidates.')
    screen = json.loads((HERE / 'screening_results.json')
                        .read_text(encoding='utf-8'))
    retained = screen.get('retained', [])
    if winner:
        keep_reason = None
    elif not candidates and not retained:
        keep_reason = 'no eligible candidates at screening'
    elif not candidates:
        keep_reason = 'no Phase-3 arms (selection empty after Phase 2)'
    else:
        keep_reason = 'no credible candidate on Phase 3'
    results = {
        'phase': 'confirm2', 'worlds': 72, 'candidates': candidates,
        'code_fingerprint': fp16,
        'bonferroni_level': level,
        'n_seed_clusters': 12,
        'per_method': per, 'credible': cred, 'winner': winner,
        'verdict': verdict,
        'keep_greedy_reason': keep_reason,
        'coverage_delta': {m: _guard_delta(rows, m, ctrl, 'coverage')
                           for m in candidates},
        'ask_cost_mean': {m: per[m]['secondary']['ask_cost_mean']
                          for m in candidates},
        'guardrail_note': ('Coverage delta >= -0.05 and ask cost are guardrails, '
                           'reported not binding (design section 9).'),
        'not_ranked_note': NOT_RANKED_NOTE,
        'incumbent_note': ('Incumbent 0.4931 MSMI/100 is a different seed set '
                           'and is never compared to these numbers.'),
        'cluster_note': ('Inference clusters on seed: 72 worlds -> 12 seed-level '
                         'means (df = 11); per-variant gates mandatory '
                         '(design section 9).'),
    }
    _write('final_results.json',
           json.dumps(results, indent=2, sort_keys=True, allow_nan=False) + '\n')
    _write('final_report.md', _final_md(results))
    print(json.dumps({'winner': winner, 'credible': cred, 'verdict': verdict,
                      'bonferroni_level': level}, indent=2))
    return 0


def _final_md(res):
    per = res['per_method']
    level = res.get('bonferroni_level', 95)
    ci_key = 'ci99' if level == 99 else 'ci95'
    ci_label = 'cluster %d%% CI' % level
    lines = ['# Method Tournament - Phase 3 Final Report', '',
             '- Worlds: %d (seeds 152-163 x 6 variants), candidates: %s.' % (
                 res['worlds'], ', '.join(res['candidates']) or '(none)'),
             '- ' + res['not_ranked_note'],
             '- ' + res['incumbent_note'],
             '- ' + res['guardrail_note'],
             '- ' + res.get('cluster_note', ''),
             '- Bonferroni: %d candidate(s) tested -> %d%% significance level '
             '(design section 9).' % (len(res['candidates']), level)]
    if res.get('code_fingerprint'):
        lines.append('- Code fingerprint: ' + res['code_fingerprint'] +
                     ' (verified on every row).')
    lines += ['',
              '| method | mean delta | ' + ci_label + ' | invalid | worst variant | '
              'credible | coverage delta | ask cost |',
              '|---|---|---|---|---|---|---|---|']
    for m in res['candidates']:
        s = per[m]
        pv = [x for x in s['per_variant_mean_delta'].values() if x is not None]
        worst = min(pv) if pv else None
        lines.append('| %s | %s | %s | %d | %s | %s | %s | %s |' % (
            m, ('%+.4f' % s['mean_delta']) if s['mean_delta'] is not None else 'n/a',
            _fmt_ci(s[ci_key]), s['invalid_episodes'],
            ('%+.4f' % worst) if worst is not None else 'n/a',
            'YES' if m in res['credible'] else 'no',
            res['coverage_delta'][m], res['ask_cost_mean'][m]))
    lines += ['', '## Verdict', '', res['verdict'], '']
    if res.get('keep_greedy_reason'):
        lines += ['',
                  'Keep-greedy reason: %s.' % res['keep_greedy_reason']]
    lines.append('')
    return '\n'.join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', required=True,
                        choices=['screening', 'confirm1', 'confirm2'])
    args = parser.parse_args(argv)
    if args.phase == 'screening':
        return analyse_screening()
    if args.phase == 'confirm1':
        return analyse_confirm1()
    return analyse_confirm2()


if __name__ == '__main__':
    raise SystemExit(main())
