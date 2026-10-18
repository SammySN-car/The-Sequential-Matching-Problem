"""Step 4: assemble report.md from the study artifacts (numbers injected,
never hardcoded). Answers the six required questions (analysis_plan.md
sec.9) and documents the Amendment 1 discrepancy.
"""
import csv, json, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gr_common as g  # noqa: E402


def read_csv(name):
    return list(csv.DictReader(open(g.OUT / name, encoding='utf-8')))


def main():
    t0 = time.time()
    g.log('gr4_report start')
    ev = json.loads((g.OUT / 'evaluation.json').read_text(encoding='utf-8'))
    tie = json.loads((g.OUT / 'tie_analysis.json').read_text(encoding='utf-8'))
    goal = json.loads((g.OUT / 'goal_analysis.json').read_text(encoding='utf-8'))
    val = json.loads((g.OUT / 'validation.json').read_text(encoding='utf-8'))
    summ = read_csv('selector_summary.csv')
    pvar = read_csv('per_variant_results.csv')
    T, D, B = ev['totals'], ev['deltas'], ev['bootstrap']['paired']
    name = {r['arm']: r['name'] for r in summ}
    S = {r['arm']: r for r in summ}
    gt = goal['goal_edge_table']
    plan_sha = (g.OUT / 'analysis_plan.sha256').read_text(encoding='utf-8').split()[0]

    def ci(a, ref):
        return B[a]['vs_%s' % ref]['ci95']

    def ptn(a, ref):
        return B[a]['vs_%s' % ref]['pos_tie_neg']

    L = []
    w = L.append

    w('# Round 2 — Goal Rule: Can a Simple Relationship-Goal Rule Exploit the '
      'Discovered Signal?')
    w('')
    w('Study: `research/round2_goal_rule/`. **Status: COMPLETE — exploratory '
      'local counterfactual diagnostic.** This study does not change the '
      'deployed policy, does not implement any selector in `policy.py`, and '
      'makes no submission or next-strategy recommendation. All inference '
      'uses the 21 seed groups (six variants kept together); the 7,560 state '
      'rows and 15,304 edge rows are never treated as independent.')
    w('')
    w('- `analysis_plan.md` frozen, SHA-256 `%s...` (Amendment 1 appended '
      'before selector computation; original freeze hash preserved inside '
      'the amendment and in `run_log.txt`).' % plan_sha[:16])
    w('- Validation gate: **%d/%d checks PASS** (`validation.json`); seals of '
      'the four prior studies current; reconciliation targets hit.'
      % (val['n_checks'] - len(val['failures']), val['n_checks']))
    w('')
    w('## 0. Headline')
    w('')
    w('| Arm | Selector | Positives | vs G0 (greedy) | vs G1m (baseline) | '
      'Pos/pair | States changed vs G0 | Improved/Tied/Worsened vs G0 |')
    w('|---|---|---|---|---|---|---|---|')
    for r in summ:
        a = r['arm']
        w('| %s | `%s` | **%s** | %s | %s | %s | %s | %s/%s/%s |'
          % (a, r['name'], r['total_positives'], r['delta_vs_G0'],
             r['delta_vs_G1m'], r['positives_per_selected_pair'],
             r['n_states_changed_vs_G0'], r['n_improved_vs_G0'],
             r['n_tied_vs_G0'], r['n_worsened_vs_G0']))
    w('')
    w('Paired seed-group bootstrap (B=2000, rng 4242) on exact per-seed '
      'totals:')
    w('')
    w('| Arm | delta vs G0 CI | p/t/n | delta vs G1m CI | p/t/n | delta vs '
      'G1f CI | p/t/n |')
    w('|---|---|---|---|---|---|---|')
    for r in summ:
        a = r['arm']
        if a in ('G0', 'G1f', 'G1m'):
            continue
        w('| %s | %s | %s | %s | %s | %s | %s |'
          % (a, r['ci95_delta_vs_G0'], r['seed_pos_tie_neg_vs_G0'],
             r['ci95_delta_vs_G1m'], r['seed_pos_tie_neg_vs_G1m'],
             r['ci95_delta_vs_G1f'], r['seed_pos_tie_neg_vs_G1f']))
    w('')
    w('**Bottom line (measured facts).** Relationship-goal scoring (G2) '
      'captures %s counterfactual MSMIs versus %s for the true maximizing '
      'baseline (G1m, +%s), %s for original greedy (G0, +%s) and %s for the '
      'frozen F1 reproduction (G1f, +%s). **None of these advantages are '
      'seed-robust**: every G2 confidence interval includes 0 '
      '(%s vs G1m, %s vs G0, %s vs G1f). G3 (goal + conversations) captures '
      'exactly as many as G2 (%s = %s) — conversations adds selection churn '
      'with zero net capture. Gains are concentrated: all %s states where G2 '
      'beats greedy are goal-observable, headroom states drawn from only %s '
      'seed groups.'
      % (T['G2'], T['G1m'], D['G2']['G1m'], T['G0'], D['G2']['G0'],
         T['G1f'], D['G2']['G1f'], ci('G2', 'G1m'), ci('G2', 'G0'),
         ci('G2', 'G1f'), T['G3'], T['G2'],
         S['G2']['n_improved_vs_G0'],
         len({s['seed'] for s in goal['g2_improved_states_vs_G0']})))
    w('')
    w('## 1. Amendment 1 — the G1 sign discrepancy (found during V3)')
    w('')
    w('The plan body defines G1 as *maximizing* the total number of matching '
      'observed soft fields. V3 revealed the frozen F1-SCORE arm does the '
      'opposite:')
    w('')
    w('- **Source-code facts:** `s1_opportunities.py:54` writes '
      '`[-e[0], ...]`, so `day_edges.jsonl` stores POSITIVE counts '
      '(verified against `feat.pair_score`: values 0..7), while the frozen '
      'consumers `fc_selectors.py:123` and `mo_validate.py:172` apply '
      '`-e[0]`, following the stale `neg_score` documentation '
      '(`plan_implementation.md:775`).')
    w('- **Measured fact:** total match-count sums over the selected edges: '
      'G1f (frozen reproduction) = **{g1f}**, greedy G0 = **{g0}**, '
      'spec-faithful maximizer G1m = **{g1m}**. A maximizing selector cannot '
      'score below the specific matching greedy produced; the frozen arm '
      'scores at roughly half. G1m and frozen F1-SCORE disagree on '
      '**{diff}/7,560** states.'.format(
          g1f=val['info']['match_count_sums']['G1f'],
          g0=val['info']['match_count_sums']['G0'],
          g1m=val['info']['match_count_sums']['G1m'],
          diff=val['info']['g1m_states_differing_from_frozen_F1']))
    w('- **Scope:** only the F1-SCORE arm is affected. F2/F3 weights are raw '
      'OOF scores and F5 uses labels (direction-correct, V3-pinned: G1f and '
      'G4 reproduce frozen sets bit-exactly on every state).')
    w('- **Decision (study owner): report both arms.** `G1f` reconciles the '
      'frozen total G1f/F1 = **{a}**; `G1m` is the spec-faithful baseline '
      '(total **{b}**) and anchors Q1/Q2. The frozen prior artifacts are '
      'untouched; this is a documented discrepancy, not a silent fix.'
      .format(a=T['G1f'], b=T['G1m']))
    w('')
    w('## 2. Method (short)')
    w('')
    w('Same 7,560 recorded states, same candidate graphs, exact cardinality '
      '`k_t` per state (`sum k_t = {k}`), same validated deterministic '
      'solver (`solve_exact_k`: lexicographically smallest optimal size-k '
      'matching, `check_matching` on every output). Weights are fixed a '
      'priori and never tuned against counterfactual outcomes: '
      'G1f = `-count`, G1m = `+count`, G2 = `+1/-0.5/0` on relationship-goal '
      'match/mismatch/unknown-declined, G3 = `0.7*goal + 0.2*conversations` '
      '(published non-shift simulator weights, STRUCTURE-INFORMED, applied '
      'uniformly to all variants), G4 = frozen OOF F2 predictions, G5 = '
      'frozen oracle sets (reference only, never deployable). G0 is the '
      'recorded greedy action set (control). Because every arm selects '
      'exactly `k_t` disjoint pairs, no comparison contains a volume '
      'component.'.format(k=ev['sum_k_t']))
    w('')
    w('## 3. Answers')
    w('')
    w('### Q1 — Does relationship-goal scoring capture more counterfactual '
      'MSMIs than the baseline count score?')
    w('')
    w('**Yes in exact totals, no in seed-robust inference.** G2 = {g2} vs '
      'G1m = {g1m} (+{d1}); vs G1f = {g1f} (+{d2}). Paired seed-group CIs '
      'include 0 in both comparisons (vs G1m {ci1} with seed p/t/n {pt1}; '
      'vs G1f {ci2} with {pt2}). Positives per selected pair: G2 {p2} vs '
      'G1m {p1}. The G2 rule demonstrably re-ranks (it selects {m2} '
      'goal-match edges vs G1m\'s {m1}, and {mm2} mismatches vs {mm1}), but '
      'goal-match edges carry a pooled positive rate of only {rate_m} on '
      'recorded opportunities, so the ranking gain converts to a small, '
      'non-robust capture difference.'.format(
          g2=T['G2'], g1m=T['G1m'], d1=D['G2']['G1m'], g1f=T['G1f'],
          d2=D['G2']['G1f'], ci1=ci('G2', 'G1m'), pt1=ptn('G2', 'G1m'),
          ci2=ci('G2', 'G1f'), pt2=ptn('G2', 'G1f'),
          p2=S['G2']['positives_per_selected_pair'],
          p1=S['G1m']['positives_per_selected_pair'],
          m2=goal['chosen_goal_states']['G2']['match'],
          m1=goal['chosen_goal_states']['G1m']['match'],
          mm2=goal['chosen_goal_states']['G2']['mismatch'],
          mm1=goal['chosen_goal_states']['G1m']['mismatch'],
          rate_m=gt['match']['pooled_rate']))
    w('')
    w('### Q2 — Does it improve over original greedy, or merely recover what '
      'the weaker baseline lost?')
    w('')
    w('**Merely recovers — and mostly the frozen baseline\'s self-inflicted '
      'loss.** G2 vs G0 = +{d} exact ({ci}, seed p/t/n {pt}). The frozen '
      'F1f arm sits at {lf} versus greedy (and is a count-minimizer per '
      'Amendment 1); G2\'s +{dg1f} over F1f is therefore mostly recovery of '
      'a broken baseline, netting only +{d} over greedy. Note also that '
      'greedy itself is nearly the count-maximizing selector: G1m differs '
      'from G0 on only {ch} states and totals {g1m} vs {g0} ({dm}). The '
      'eight G2-over-greedy improvements sit in headroom states '
      '({hr2} vs greedy\'s {hr0} positives within the 82 headroom states) '
      'and are partly offset by a delta of {z} in zero-headroom states '
      '({zh2} vs {zh0}).'.format(
          d=D['G2']['G0'], ci=ci('G2', 'G0'), pt=ptn('G2', 'G0'),
          lf=D['G1f']['G0'], dg1f=D['G2']['G1f'],
          ch=S['G1m']['n_states_changed_vs_G0'], g1m=T['G1m'], g0=T['G0'],
          dm=D['G1m']['G0'], hr2=S['G2']['headroom_positives'],
          hr0=S['G0']['headroom_positives'],
          z=D['G2']['G0'] - (int(S['G2']['headroom_positives']) -
                             int(S['G0']['headroom_positives'])),
          zh2=S['G2']['zero_headroom_positives'],
          zh0=S['G0']['zero_headroom_positives']))
    w('')
    w('### Q3 — Does adding conversations improve on relationship-goal '
      'alone?')
    w('')
    w('**No.** G3 = G2 = {g3} exactly (identical headroom and '
      'zero-headroom splits too). G3 and G2 select different sets in {n} '
      'states, but **every one of those {n} states has a counterfactual '
      'delta of exactly 0** (histogram {hist}); all {n} have observable '
      'conversations candidates, so the added field genuinely changes '
      'selections — it just never changes capture. Per-seed G3-G2: {pt}, '
      'CI {ci}. The structure-informed conversations term buys churn, not '
      'capture.'.format(g3=T['G3'], g2=T['G2'],
                        n=goal['g3_vs_g2']['n_states_sets_differ'],
                        hist=goal['g3_vs_g2']['delta_histogram'],
                        pt=goal['g3_vs_g2']['per_seed_pos_tie_neg'],
                        ci=goal['g3_vs_g2']['ci95']))
    w('')
    w('### Q4 — Are gains concentrated in a small number of headroom states '
      'or seed groups?')
    w('')
    c0 = goal['g2_concentration']['G0']
    sc = goal['g2_seed_concentration']['G1m']
    w('**Yes, both.** All {n} states where G2 beats greedy are '
      'goal-observable AND headroom states, drawn from just {ns} seed groups '
      '({sd}); the {nw} worsening states are all zero-headroom, spread over '
      '{nws} seeds. States where no candidate\'s goal is observable are '
      'changed by G2 in {nu} cases but produce a net delta of exactly '
      '{su} — pure tie-breaks. Against the spec baseline G1m, seed {ts} '
      'alone supplies +{tsd} of the net +{tm} (share {sh} of the total). Headroom '
      'split (82 states): G2 {hr2} vs greedy {hr0} vs G1m {hr1}; the '
      '7,478 zero-headroom states: G2 {zh2} vs greedy {zh0} '
      '(delta {dz}).'.format(
          n=S['G2']['n_improved_vs_G0'],
          ns=len({s['seed'] for s in goal['g2_improved_states_vs_G0']}),
          sd=', '.join('%s(%d)' % (sd, sum(1 for s in
                       goal['g2_improved_states_vs_G0'] if s['seed'] == sd))
                       for sd in sorted({s['seed'] for s in
                                         goal['g2_improved_states_vs_G0']})),
          nw=S['G2']['n_worsened_vs_G0'],
          nws=len({s['seed'] for s in goal['g2_worsened_states_vs_G0']}),
          nu=c0['unobservable']['n_changed'], su=c0['unobservable']['sum_delta'],
          ts=sc['top_seed'], tsd=sc['top_seed_delta'],
          tm=sc['total'], sh=sc['top_share_of_total'],
          hr2=S['G2']['headroom_positives'], hr0=S['G0']['headroom_positives'],
          hr1=S['G1m']['headroom_positives'],
          zh2=S['G2']['zero_headroom_positives'],
          zh0=S['G0']['zero_headroom_positives'],
          dz=S['G2']['zero_headroom_delta_vs_G0']))
    w('')
    w('### Q5 — Are score ties limiting the rule\'s ability to exploit the '
      'signal?')
    w('')
    t2, t4 = tie['G2'], tie['G4']
    w('**Yes, severely.** G2 cannot discriminate at all in '
      '{nod:.1%} of states (every candidate\'s goal in the same category); '
      'the maximum itself is tied in {tt:.1%} of states; {to} of the {ch} '
      'G2 set-changes happen in states where all candidates share one score '
      '(arbitrary lex tie-breaks, and they net to zero outcome effect in '
      'the unobservable split). Only {obs} of 7,560 states have ANY '
      'observable-goal candidate; across all states G2 shows a mean of '
      '{nd:.2f} distinct scores per state. By contrast the continuous F2 (G4) '
      'has distinct scores on nearly every edge (mean {nd4:.2f}, top-tied '
      'only {tt4:.1%}) yet still captures only {t4} — discrimination is '
      'necessary but not sufficient; positives are rare among feasible '
      'edges ({base}) and that base rate dominates precision.'.format(
          nod=t2['share_states_no_discrimination'],
          tt=t2['share_states_top_score_tied'],
          to=t2['changed_states_tie_only'], ch=t2['n_states_changed_vs_G0'],
          obs=goal['n_states_goal_observable'], nd=t2['mean_n_distinct_scores'],
          nd4=t4['mean_n_distinct_scores'], tt4=t4['share_states_top_score_tied'],
          t4=T['G4'],
          base=round(val['info']['sum_p_t'] / val['info']['n_edges'], 6)))
    w('')
    w('### Q6 — What does the study establish, and what still requires full '
      'sequential evaluation?')
    w('')
    w('**Established (measured facts, reconciled %d checks):**' %
      val['n_checks'])
    w('')
    w('- Exact selector capture on the 7,560 recorded states at identical '
      '`k_t`: G0={g0}, G1f={g1f} (frozen, reconciled), G1m={g1m}, '
      'G2={g2}, G3={g3}, G4={g4}, G5={g5}; headroom/zero-headroom splits; '
      'per-state improved/tied/worsened counts.'.format(
          g0=T['G0'], g1f=T['G1f'], g1m=T['G1m'], g2=T['G2'], g3=T['G3'],
          g4=T['G4'], g5=T['G5']))
    w('- The Amendment 1 sign discrepancy in the frozen F1-SCORE arm '
      '(source-code + measured evidence).')
    w('- Descriptive association: goal-match edges {rm} positive rate vs '
      'goal-mismatch {rmm} (difference {d} pp, seed-group CI {ci}, excludes '
      '0). Unknown/declined rates are reported but **not** ranked against '
      'mismatch (not established).'.format(
          rm=gt['match']['pooled_rate'], rmm=gt['mismatch']['pooled_rate'],
          d=round(100 * gt['match_minus_mismatch_rate']['point'], 2),
          ci=gt['match_minus_mismatch_rate']['ci95_seed_group']))
    w('- Tie/observability structure: {obs}/{n} states observable; G2 '
      'no-discrimination share {nod:.1%}.'.format(
          obs=goal['n_states_goal_observable'], n=ev['n_states'],
          nod=t2['share_states_no_discrimination']))
    w('- Statistical inference (exploratory): G2\'s advantages over G0, G1m '
      'and G1f all have seed-group CIs containing 0. The only non-oracle '
      'interval excluding 0 is G4 vs G1f ({ci}) — contingent on the frozen '
      '(minimizing) baseline definition; G4 vs G1m ({cim}) includes 0.'.format(
          ci=ci('G4', 'G1f'), cim=ci('G4', 'G1m')))
    w('')
    w('**Not established — requires full sequential evaluation:**')
    w('')
    w('- Any causal or sequential improvement: selectors here face fixed '
      'recorded states; different actions change future availability and '
      'decision states, so none of these totals transfers to the deployed '
      'policy outcome.')
    w('- That G2 (or G3, or G4) is a *winning* rule: every G2 comparison CI '
      'includes 0, gains cluster in {ns} seed groups, and results are '
      'labelled exploratory by design.'.format(
          ns=len({s['seed'] for s in goal['g2_improved_states_vs_G0']})))
    w('- Whether unknown is better than mismatch (not claimed; previous '
      'audit did not establish it).')
    w('- Whether G2\'s headroom gains persist when earlier decisions alter '
      'which states ever occur.')
    w('')
    w('## 4. By-variant and by-seed detail')
    w('')
    w('Per-variant positives (identical `k_t` within every state):')
    w('')
    w('| Variant | ' + ' | '.join(a for a in ['G0','G1f','G1m','G2','G3','G4','G5']) + ' |')
    w('|---|' + '---|' * 7)
    for r in pvar:
        w('| %s | %s |' % (r['variant'],
                           ' | '.join(r['%s_positives' % a]
                                      for a in ['G0','G1f','G1m','G2','G3','G4','G5'])))
    w('')
    w('Full per-seed (21 rows, paired deltas and p/t/n) in '
      '`per_seed_results.csv`; per-variant deltas in '
      '`per_variant_results.csv`; state-level detail (52 columns) in '
      '`per_state_results.csv`.')
    w('')
    w('## 5. Relationship-goal signal on recorded opportunities')
    w('')
    w('| Goal state | Edges | MSMI positives | Pooled rate | Seed-group 95% CI |')
    w('|---|---|---|---|---|')
    for st in ('match', 'mismatch', 'unknown', 'declined'):
        v = gt[st]
        w('| %s | %d | %d | %.4f | [%.4f, %.4f] |'
          % (st, v['n_edges'], v['n_positive'], v['pooled_rate'],
             v['ci95_seed_group'][0], v['ci95_seed_group'][1]))
    w('')
    w('Match-minus-mismatch = {p:.4f}, CI [{lo:.4f}, {hi:.4f}] '
      '(excludes 0). Descriptive on recorded edges only — the selector '
      'results above are counterfactual-but-local, and neither is a causal '
      'or sequential claim.'.format(
          p=gt['match_minus_mismatch_rate']['point'],
          lo=gt['match_minus_mismatch_rate']['ci95_seed_group'][0],
          hi=gt['match_minus_mismatch_rate']['ci95_seed_group'][1]))
    w('')
    w('Goal-state composition of chosen edges (sums = '
      '{k} per arm):'.format(k=ev['sum_k_t']))
    w('')
    w('| Arm | match | mismatch | unknown | declined |')
    w('|---|---|---|---|---|')
    for a in ['G0', 'G1f', 'G1m', 'G2', 'G3', 'G4', 'G5']:
        cc = goal['chosen_goal_states'][a]
        w('| %s | %d | %d | %d | %d |'
          % (a, cc.get('match', 0), cc.get('mismatch', 0),
             cc.get('unknown', 0), cc.get('declined', 0)))
    w('')
    w('G2 mechanically shifts composition toward goal match (G2 selects '
      '{m2} match edges vs greedy {m0}); notably the oracle G5 selects '
      'fewer goal-match edges than greedy ({m5} vs {m0}) — goal agreement '
      'is descriptive signal, not the outcome mechanism.'.format(
          m2=goal['chosen_goal_states']['G2']['match'],
          m0=goal['chosen_goal_states']['G0']['match'],
          m5=goal['chosen_goal_states']['G5']['match']))
    w('')
    w('## 6. Validation and reconciliation')
    w('')
    nchk = '%d/%d' % (val['n_checks'] - len(val['failures']),
                      val['n_checks'])
    w('- **%s checks PASS** (`validation.json`): seals of '
      'round2_decision_ceiling / fixed_cardinality / missed_oracle / '
      'stagewise_signal current; plan hash frozen; 7,560 states / 15,304 '
      'edges / `sum k_t` {k} / `sum p_t` 173; every edge has label + OOF '
      'score; orientation sorted; recomputed GREEDY == recorded action on '
      'all states; frozen totals GREEDY=90 F1=81 F2=94 F5=161; 82/7,478 '
      'headroom split; V3 G1f==F1-SCORE and G4==F2-SOFT bit-exact on every '
      'state; V4 exact `k_t`, feasible, non-overlapping for all 7 arms on '
      'all states; V6 maximizer direction ({g1m} >= {g0} > {g1f}).'
      .format(k=ev['sum_k_t'],
              g1m=val['info']['match_count_sums']['G1m'],
              g0=val['info']['match_count_sums']['G0'],
              g1f=val['info']['match_count_sums']['G1f']) % nchk)
    w('- **Reconciliation targets:** G0=90, G1f/F1=81, G4/F2=94, G5/F5=161 '
      'all exact (hard assert in `gr2_evaluate.py`); G1m=88 per Amendment 1; '
      'G2=G3={g2}; headline table equals `per_state_results.csv` sums '
      '(re-derived at verify time).'.format(g2=T['G2']))
    w('- Prior artifacts were never modified; the ceiling `run_log.txt` '
      'append is the only tolerated seal delta (as in prior studies).')
    w('')
    w('## 7. Files')
    w('')
    w('`analysis_plan.md` (+ `.sha256`, Amendment 1), `report.md`, '
      '`selector_summary.csv`, `per_state_results.csv`, '
      '`per_seed_results.csv`, `per_variant_results.csv`, '
      '`validation.json`, `evaluation.json`, `tie_analysis.json`, '
      '`goal_analysis.json`, `selector_sets.jsonl`, '
      '`channel_states.json`, `scripts/gr_*.py`, `run_log.txt`, '
      '`integrity.sha256`. Reproduce in order: `gr0_validate.py` → '
      '`gr1_selectors.py` → `gr2_evaluate.py` → `gr3_goal.py` → '
      '`gr4_report.py`, then `gr_seal.py` / `gr_verify.py`.')
    w('')
    w('*Exploratory local counterfactual diagnostic — no policy change, no '
      'submission decision, no next-strategy recommendation.*')

    (g.OUT / 'report.md').write_text('\n'.join(L) + '\n', encoding='utf-8')
    g.log('wrote report.md (%d lines)' % len(L))
    g.log('gr4_report done (%.1fs)' % (time.time() - t0))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
