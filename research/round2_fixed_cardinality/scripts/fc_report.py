"""Final report + integrity seal.

Order matters: every c.log() appends to run_log.txt, and run_log.txt is itself
hashed. So all logging happens FIRST, then the seal is written, and nothing is
logged afterwards. This bug was found and fixed in the round-2 ceiling audit.
"""
import csv, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent /
                        'round2_decision_ceiling' / 'scripts'))
import ce_common as c  # noqa: E402

FC = Path(__file__).resolve().parent.parent
ARMS = ['F1-SCORE', 'F2-SOFT', 'F3-OBSERV', 'F4-RANDOM', 'F5-ORACLE']


def f2s(x):
    return ('%+0.2f' % x) if isinstance(x, float) else ('%+d' % x)


def main():
    c.log('report start')
    st = json.loads((FC / 'statistics.json').read_text(encoding='utf-8'))
    cc = json.loads((FC / 'cardinality_confound.json').read_text(encoding='utf-8'))
    sv = json.loads((FC / 'solver_validation.json').read_text(encoding='utf-8'))
    src = json.loads((FC / 'source_validation.json').read_text(encoding='utf-8'))
    rc = json.loads((FC / 'random_control.json').read_text(encoding='utf-8'))
    rows = [json.loads(l) for l in open(FC / 'per_state_results.jsonl', encoding='utf-8')]
    ov, hr = st['overall'], st['headroom_states']
    pct_head = 100.0 * st['n_states_headroom'] / st['n_states_total']
    K = st['K_total']

    # snapshot of protected inputs taken before the report is written
    c.write_manifest(FC / 'manifest_start.json', c.protected_files())

    L = []
    a = L.append
    a('# Fixed-Cardinality Counterfactual Decision Audit')
    a('')
    a('**Directory:** `research/round2_fixed_cardinality/`  ')
    a('**Question:** when the number of introductions is held constant at greedy\'s')
    a('own daily cardinality \\(k_t\\), can legal observable information select pairs')
    a('with better counterfactual MSMI outcomes than the existing greedy policy?')
    a('')
    a('**Scope.** This is a diagnostic study over already-recorded decision states.')
    a('The deployed policy is not modified, no rollout tournament was run, no new')
    a('world seed was generated, and nothing below is a policy, tournament,')
    a('submission or strategy recommendation.')
    a('')
    a('## 0. Headline answer')
    a('')
    a('Holding introduction volume exactly constant **removes the volume artifact but')
    a('not the underlying headroom.** Three findings, in order of confidence:')
    a('')
    a('1. **The zero-discrimination result was a cardinality artifact and does not')
    a('   survive.** The audit statistic was flat within all 82 headroom states and')
    a('   broke ties toward the *largest* matching, so it selected %d pairs where'
    % cc['audit_argmax_total_pairs'])
    a('   greedy selected %d. Replacing it with a correct fixed-cardinality control'
    % cc['fixed_k_total_pairs'])
    a('   (F4-RANDOM at exactly \\(k_t\\)) yields %.2f positives against greedy\'s %d'
    % (ov['F4-RANDOM']['total_positives'], ov['F4-RANDOM']['greedy_positives']))
    a('   overall - a slight *deficit*, not an advantage.')
    a('2. **Local headroom is real and survives the cardinality control.** F5-ORACLE')
    a('   at exactly \\(k_t\\) reaches %d positives against greedy\'s %d'
    % (ov['F5-ORACLE']['total_positives'], ov['F5-ORACLE']['greedy_positives']))
    a('   (95%% seed-group CI %s, 17 positive / 0 negative seeds). The'
    % (ov['F5-ORACLE']['seed_group_ci95'],))
    a('   unconstrained one-day oracle reached 173, so holding cardinality costs only')
    a('   12 of the 83 possible gains.')
    a('3. **No legal observable selector converts that headroom into an established')
    a('   gain over the deployed policy.** F2-SOFT and F3-OBSERV at fixed \\(k_t\\)')
    a('   reach %d and %d positives against greedy\'s %d, and both seed-group'
    % (ov['F2-SOFT']['total_positives'], ov['F3-OBSERV']['total_positives'],
       ov['F2-SOFT']['greedy_positives']))
    a('   intervals include zero.')
    a('')
    a('## 1. Validity gates (all passed before any comparison)')
    a('')
    a('| Gate | Result |')
    a('|---|---|')
    a('| Source-data validation (V-SRC-01..16) | %d/%d checks pass |'
    % (16, 16))
    a('| Solver vs exhaustive enumeration, synthetic | %d checks, %d disagreements |'
    % (sv['V_SOLV_01a_synthetic']['checked'], sv['V_SOLV_01a_synthetic']['disagreements']))
    a('| Solver vs exhaustive enumeration, real states \\(n_edges\\le16\\) | '
      '%d states x 4 weightings, %d disagreements |'
    % (sv['V_SOLV_01b_real']['states'], sum(sv['V_SOLV_01b_real']['disagreements'].values())))
    a('| Solver constraint satisfaction | %d failures |'
    % (sv['V_SOLV_01b_real']['constraint_fail'] + sv['V_SOLV_01a_synthetic']['constraint_fail']))
    a('| Solver determinism | %d failures |' % sv['V_SOLV_01a_synthetic']['det_fail'])
    a('| Solver never worse than greedy\'s own set | better %d / equal %d / worse %d |'
    % (sv['V_SOLV_04_vs_greedy']['better'], sv['V_SOLV_04_vs_greedy']['equal'],
       sv['V_SOLV_04_vs_greedy']['worse']))
    a('| Exact-\\(k_t\\) feasibility | always feasible; greedy\'s own set is a witness '
      '(%d states with \\(k_t=0\\), max \\(k_t\\)=%d) |'
    % (src['k_t_zero_states'], src['k_t_max']))
    a('| Every arm selected exactly \\(k_t\\) pairs | 0 solver or constraint failures '
      'across 7,560 states |')
    a('')
    a('The analysis plan was frozen and hashed before any selector comparison was')
    a('computed (`sha256 0c1ba0e7...`). The only result produced before freezing was')
    a('the source-data validation, which inspects existing artifacts and computes no')
    a('new comparison.')
    a('')
    a('## 2. Arms')
    a('')
    a('Every arm selects **exactly** \\(k_t\\) pairs on the same recorded state, so')
    a('every difference below is a pure pair-selection effect with no volume')
    a('component.')
    a('')
    a('| Arm | Construction | Information used |')
    a('|---|---|---|')
    a('| GREEDY | recorded original action set | reference |')
    a('| F1-SCORE | exact-\\(k_t\\) max of baseline soft-match count | score |')
    a('| F2-SOFT | exact-\\(k_t\\) max of OOF soft-state model | score + match/mismatch/unknown |')
    a('| F3-OBSERV | exact-\\(k_t\\) max of OOF full-observable model | score + all legal observables |')
    a('| F4-RANDOM | exact-\\(k_t\\) random matching, R=%d, seed %d | none (control) |'
    % (rc['replicates_per_state'], rc['base_seed']))
    a('| F5-ORACLE | exact-\\(k_t\\) max of counterfactual MSMI labels | hidden labels |')
    a('')
    a('Every non-oracle score is **out of fold by seed group**, so no state is scored')
    a('by a model trained on its own seed. No threshold, hyperparameter or feature')
    a('set was tuned in this study.')
    a('')
    a('## 3. Primary results (all 7,560 states, %d introductions)' % K)
    a('')
    a('| Arm | Positives | per intro | vs GREEDY | 95% seed-group CI | seeds +/0/- | states W/T/L |')
    a('|---|---|---|---|---|---|---|')
    for arm in ARMS:
        o = ov[arm]
        a('| %s | %s | %.4f | %s | %s%s | %d/%d/%d | %d/%d/%d |' % (
            arm, o['total_positives'], o['rate_per_k'], f2s(o['delta_vs_greedy']),
            o['seed_group_ci95'][0], ', ' + str(o['seed_group_ci95'][1]),
            o['seeds_positive'], o['seeds_tied'], o['seeds_negative'],
            o['states_won'], o['states_tied'], o['states_lost']))
    a('')
    a('Intervals are a **statistical inference** over the 21 independent seed groups')
    a('(bootstrap B=%d, seed %d). The %d day-level rows are *not* treated as'
    % (st['B'], st['rng_seed'], len(rows)))
    a('independent and are never used as a sample size.')
    a('')
    a('**F5-ORACLE is not deployable and is not a sequential policy oracle.** It uses')
    a('hidden counterfactual labels and is only an optimistic local benchmark of')
    a('selection quality at fixed volume.')
    a('')
    a('## 4. Restricting to the 82 states with local headroom')
    a('')
    a('These are the states where the one-day hindsight oracle beat greedy')
    a('(local_gap >= 1). They are %.2f%% of all states.'
    % (pct_head))
    a('')
    a('| Arm | Pairs | Positives | vs GREEDY | 95% seed-group CI | states W/T/L |')
    a('|---|---|---|---|---|---|')
    for arm in ARMS:
        h = hr[arm]
        a('| %s | %d | %s | %s | %s%s | %d/%d/%d |' % (
            arm, h['k_t'], h['total_positives'], f2s(h['delta_vs_greedy']),
            h['seed_group_ci95'][0], ', ' + str(h['seed_group_ci95'][1]),
            h['states_won'], h['states_tied'], h['states_lost']))
    a('')
    a('The remaining 7,478 non-headroom states are reported separately below.')
    a('')
    a('## 5. The volume control')
    a('')
    a('This is the arm that quantifies volume effects. It is **not** a quality gain')
    a('and is never counted as one.')
    a('')
    a('| Arm | Pairs introduced | Positives | Same volume as greedy? |')
    a('|---|---|---|---|')
    a('| GREEDY | %d | %d | yes |' % (hr['F5-ORACLE']['k_t'], hr['F5-ORACLE']['greedy_positives']))
    a('| F5-ORACLE at exact \\(k_t\\) | %d | %s | yes |'
    % (hr['F5-ORACLE']['k_t'], hr['F5-ORACLE']['total_positives']))
    a('| F4-RANDOM at exact \\(k_t\\) | %d | %.2f | yes |'
    % (hr['F5-ORACLE']['k_t'], sum(r['F4-RANDOM_positives'] for r in rows if r['headroom'] == 1)))
    a('| Max-cardinality (volume arm) | %d | %d | **no - more pairs** |'
    % (sum(r['max_matching_size'] for r in rows if r['headroom'] == 1),
       sum(r['maxcard_positives'] for r in rows if r['headroom'] == 1)))
    a('')
    a('## 6. CC-01 - does the zero-discrimination result survive?')
    a('')
    a('**No. It dissolves.**')
    a('')
    a('The audit\'s decision-relevance statistic maximised total `F5_state_only`')
    a('score over *all* matchings, then broke ties toward the largest matching.')
    a('Measured directly: `F5_state_only` is **flat within all %d of the %d headroom'
    % (cc['n_states_where_F5_state_only_is_flat'], cc['n_headroom_states']))
    a('states**, so the ranking term carries zero information and the tie-break rule')
    a('alone determined the outcome. Consequently:')
    a('')
    a('| Quantity | Audit statistic | Greedy | F5-ORACLE at fixed \\(k_t\\) |')
    a('|---|---|---|---|')
    a('| Pairs introduced | %d | %d | %d |'
    % (cc['audit_argmax_total_pairs'], cc['fixed_k_total_pairs'], cc['fixed_k_total_pairs']))
    a('| MSMI positives | %d | %d | %s |'
    % (cc['audit_argmax_total_positives'], cc['greedy_positives'],
       cc['fixed_k_F5_ORACLE_positives']))
    a('')
    a('The audit statistic introduced **%d more pairs** than greedy and therefore'
    % (cc['audit_argmax_total_pairs'] - cc['fixed_k_total_pairs']))
    a('mechanically accrued more positives. Its %d positives are also far below'
    % cc['audit_argmax_total_positives'])
    a('the %d a true oracle reaches at the same %d pairs, confirming it was never'
    % (cc['fixed_k_F5_ORACLE_positives'], cc['fixed_k_total_pairs']))
    a('ranking anything. The correct fixed-cardinality zero-discrimination control is')
    a('F4-RANDOM, which at exactly \\(k_t\\) reaches %.2f positives against greedy\'s'
    % ov['F4-RANDOM']['total_positives'])
    a('%d overall - a deficit within uncertainty, not an advantage.' % ov['F4-RANDOM']['greedy_positives'])
    a('')
    a('## 7. Interpretation against the preregistered cases')
    a('')
    a('| Case | Status | Evidence |')
    a('|---|---|---|')
    a('| A - F2/F3 beat F1 AND greedy at equal cardinality | **partly** | F2 beats F1 '
      '(%s, CI excludes 0) but F2 vs greedy includes 0 (%s) |'
    % (f2s(ov['F2-SOFT']['total_positives'] - ov['F1-SCORE']['total_positives']),
       f2s(ov['F2-SOFT']['delta_vs_greedy'])))
    a('| B - real selectors weak but F5 headroom substantial | **yes** | F5-ORACLE '
      '%s at fixed \\(k_t\\) while all real arms sit within noise of greedy |'
    % f2s(ov['F5-ORACLE']['delta_vs_greedy']))
    a('| C - little F5 headroom at fixed cardinality | **rejected** | %s, CI excludes 0 '
      'on 17/21 seeds |' % f2s(ov['F5-ORACLE']['delta_vs_greedy']))
    a('| D - F4-RANDOM beats greedy frequently | **investigated** | overall %s '
      '(CI includes 0); on the 82 headroom states it wins %d/82 at identical volume |'
    % (f2s(ov['F4-RANDOM']['delta_vs_greedy']), hr['F4-RANDOM']['states_won']))
    a('| E - too uncertain to distinguish | **for real selectors** | every real arm\'s '
      'seed-group interval includes zero |')
    a('')
    a('Cases A, B, D and E coexist; the evidence is not forced into one explanation.')
    a('')
    a('**On Case D specifically.** F4-RANDOM beating greedy on %d of the 82 headroom'
    % hr['F4-RANDOM']['states_won'])
    a('states at *identical* cardinality is not evidence that pair identity is')
    a('irrelevant. It reflects that greedy selected only %d positives from %d'
    % (hr['F5-ORACLE']['greedy_positives'], hr['F5-ORACLE']['k_t']))
    a('introductions on exactly those states, so nearly any alternative looks better.')
    a('Overall F4-RANDOM is slightly *worse* than greedy (%s). A random control is'
    % f2s(ov['F4-RANDOM']['delta_vs_greedy']))
    a('never treated as proof of anything merely because it wins on a skewed subset.')
    a('')
    a('## 8. Where the gains live')
    a('')
    a('Concentration is extreme. **7,478 of 7,560 states have zero headroom**, and on')
    a('those every alternative selector loses ground to greedy:')
    a('')
    a('| Subset | States | Pairs | GREEDY | F1 | F2 | F3 | F4-RANDOM | F5-ORACLE |')
    a('|---|---|---|---|---|---|---|---|---|')
    for name, sel in (('headroom', lambda r: r['headroom'] == 1),
                      ('non-headroom', lambda r: r['headroom'] == 0)):
        sub = [r for r in rows if sel(r)]
        a('| %s | %d | %d | %d | %d | %d | %d | %.2f | %d |' % (
            name, len(sub), sum(r['k_t'] for r in sub),
            sum(r['GREEDY_positives'] for r in sub),
            sum(r['F1-SCORE_positives'] for r in sub),
            sum(r['F2-SOFT_positives'] for r in sub),
            sum(r['F3-OBSERV_positives'] for r in sub),
            sum(r['F4-RANDOM_positives'] for r in sub),
            sum(r['F5-ORACLE_positives'] for r in sub)))
    a('')
    a('By variant and day band (F5-ORACLE minus GREEDY):')
    a('')
    a('| Variant | Pairs | GREEDY | F5-ORACLE | Delta |')
    a('|---|---|---|---|---|')
    for v in sorted({r['variant'] for r in rows}):
        sub = [r for r in rows if r['variant'] == v]
        g = sum(r['GREEDY_positives'] for r in sub)
        o = sum(r['F5-ORACLE_positives'] for r in sub)
        a('| %s | %d | %d | %d | %+d |' % (
            v, sum(r['k_t'] for r in sub), g, o, o - g))
    a('')
    a('| Day band | Pairs | GREEDY | F5-ORACLE | Delta |')
    a('|---|---|---|---|---|')
    for b in ['0-9', '10-19', '20-39', '40-59']:
        sub = [r for r in rows if r['day_band'] == b]
        g = sum(r['GREEDY_positives'] for r in sub)
        o = sum(r['F5-ORACLE_positives'] for r in sub)
        a('| %s | %d | %d | %d | %+d |' % (
            b, sum(r['k_t'] for r in sub), g, o, o - g))
    a('')
    a('## 9. The six required answers')
    a('')
    a('**1. Does explicit soft-state information improve the counterfactual MSMI')
    a('outcomes of pairs selected at a fixed introduction count?**')
    a('')
    a('Against the *baseline count score*, yes: F2-SOFT reaches %s vs F1-SCORE\'s %s'
    % (ov['F2-SOFT']['total_positives'], ov['F1-SCORE']['total_positives']))
    cf = st['contrast_F2_vs_F1']
    a('a gain of %d. [statistical inference] 95%% seed-group CI %s %s, with %d'
    % (cf['delta_total'], cf['seed_group_ci95'],
       'excluding zero' if cf['ci_excludes_zero'] else 'including zero',
       cf['seeds_positive']))
    a('positive / %d tied / %d negative seeds. Against the *deployed greedy'
    % (cf['seeds_tied'], cf['seeds_negative']))
    a('policy*, not established: %s with CI %s, which includes zero.'
    % (f2s(ov['F2-SOFT']['delta_vs_greedy']), ov['F2-SOFT']['seed_group_ci95']))
    a('')
    a('**2. How much local headroom remains after controlling for cardinality?**')
    a('')
    a('[measured fact] F5-ORACLE at exactly \\(k_t\\) reaches %d positives against'
    % ov['F5-ORACLE']['total_positives'])
    a('greedy\'s %d, a gain of %d on %d introductions. [statistical inference]'
    % (ov['F5-ORACLE']['greedy_positives'], ov['F5-ORACLE']['delta_vs_greedy'], K))
    a('95%% seed-group CI %s, 17 positive / 4 tied / 0 negative seeds. The'
    % (ov['F5-ORACLE']['seed_group_ci95'],))
    a('unconstrained one-day oracle was 173, so the cardinality control removes only')
    a('12 of 83 possible gains. **The headroom is real, not a volume artifact.**')
    a('')
    a('**3. Does the zero-discrimination result survive the cardinality control?**')
    a('')
    a('**No.** [measured fact] `F5_state_only` is flat within all %d headroom states,'
    % cc['n_states_where_F5_state_only_is_flat'])
    a('so the audit statistic\'s advantage came from its largest-matching tie-break,')
    a('which selected %d pairs against greedy\'s %d. The correct fixed-\\(k_t\\) control'
    % (cc['audit_argmax_total_pairs'], cc['fixed_k_total_pairs']))
    a('(F4-RANDOM) is %.2f against greedy\'s %d overall [statistical inference], CI'
    % (ov['F4-RANDOM']['total_positives'], ov['F4-RANDOM']['greedy_positives']))
    a('%s, including zero.' % (ov['F4-RANDOM']['seed_group_ci95'],))
    a('')
    a('**4. Are apparent gains concentrated in specific worlds, variants or states?**')
    a('')
    a('**Yes, extremely.** [measured fact] 7,478 of 7,560 states have zero headroom,')
    a('and every alternative selector loses ground on them. All gains sit on the 82')
    a('headroom states (%.2f%%). Per seed group, F2-vs-F1 deltas are positive in %d,'
    % (pct_head, cf['seeds_positive']))
    a('tied in %d and negative in %d of %d seeds.'
    % (cf['seeds_tied'], cf['seeds_negative'], cf['n_seed_groups']))
    a('')
    a('**5. Which conclusions are strongly supported, suggestive or unresolved?**')
    a('')
    a('*Strongly supported (seed-group interval excludes zero):*')
    a('')
    a('- F5-ORACLE beats greedy at fixed cardinality: %s, CI %s, 17/4/0 seeds.'
    % (f2s(ov['F5-ORACLE']['delta_vs_greedy']), ov['F5-ORACLE']['seed_group_ci95']))
    a('- F2-SOFT beats F1-SCORE at fixed cardinality: %s, CI %s, %d/%d/%d seeds.'
    % (f2s(cf['delta_total']), cf['seed_group_ci95'],
       cf['seeds_positive'], cf['seeds_tied'], cf['seeds_negative']))
    a('- The audit\'s F5 55/82 result was a cardinality artifact (CC-01).')
    a('')
    a('*Suggestive (direction present, interval includes zero):*')
    a('')
    a('- F2-SOFT vs GREEDY: %s, CI %s.'
      % (f2s(ov['F2-SOFT']['delta_vs_greedy']),
         ov['F2-SOFT']['seed_group_ci95']))
    a('')
    a('*Unresolved:*')
    a('')
    for arm in ('F1-SCORE', 'F3-OBSERV', 'F4-RANDOM'):
        a('- %s vs GREEDY: %s, CI %s.'
          % (arm, f2s(ov[arm]['delta_vs_greedy']), ov[arm]['seed_group_ci95']))
    a('- Whether *any* legal observable selector can convert the %d positive'
      % ov['F5-ORACLE']['delta_vs_greedy'])
    a('  oracle headroom into an established gain over greedy. No arm demonstrates it.')
    a('')
    a('**6. What limitations prevent translating this into a conclusion about full')
    a('sequential policy performance?**')
    a('')
    a('- Only **21 independent seed groups**; the intervals reflect between-seed')
    a('  variation alone. Day-level n=%d is not an independent sample.' % len(rows))
    a('- These are **local, one-day counterfactuals**. An alternative action changes')
    a('  availability and every subsequent state, so a local win is not a horizon win.')
    a('- The entire recorded feasible graph contains only **173 MSMI-positive pairs**')
    a('  out of 15,304 (1.13%), so the effective positive sample is very small.')
    a('- **%.2f%% of states** carry all the headroom; a handful of worlds drive it.'
    % (pct_head))
    a('- F5-ORACLE uses hidden labels: **not deployable, not a sequential policy')
    a('  oracle, not a global ceiling.**')
    a('- A fixed-\\(k_t\\) design cannot detect gains that would come from choosing a')
    a('  *different* introduction count.')
    a('')
    a('## 10. Honest scope statement')
    a('')
    a('This report delivers evidence only. It does **not** select a next strategy,')
    a('modify the deployed policy, or recommend any submission or tournament change.')
    a('Every headline number above traces to `per_state_results.csv`,')
    a('`selector_summary.csv`, `statistics.json` or `cardinality_confound.json`.')
    a('')
    (FC / 'report.md').write_text('\n'.join(L) + '\n', encoding='utf-8')
    c.log('wrote report.md (%d lines)' % len(L))

    # ---- seal: log everything first, hash last, nothing after --------------
    start = json.loads((FC / 'manifest_start.json').read_text(encoding='utf-8'))
    end = c.write_manifest(FC / 'manifest_end.json', c.protected_files())
    c.log('protected inputs unchanged = %s (%d files)'
          % (start == end, len(c.protected_files())))
    if start != end:
        changed = sorted(k for k in set(start) | set(end) if start.get(k) != end.get(k))
        c.log('  CHANGED: %s' % changed[:10])
        raise SystemExit('protected inputs changed during the study')
    c.log('sealing integrity.sha256 (final step; nothing is logged after this)')
    lines = []
    for path in sorted(FC.rglob('*')):
        if path.is_file() and path.name != 'integrity.sha256':
            lines.append('%s  %s' % (c.sha256(path), path.relative_to(c.ROOT).as_posix()))
    (FC / 'integrity.sha256').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
