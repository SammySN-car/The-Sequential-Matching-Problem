"""bi1: source-fact extraction for the score-direction audit.

For every implementation in analysis_plan.md sec.4, assert the exact executable
lines still exist (hard fail if a pattern is missing), extract them with line
numbers, and record the seven required verdicts. Output: source_facts.md +
source_facts.json. Read-only over the repository.
"""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
ROOT = HERE.parents[2]

FACTS = [
    dict(
        id='kit.baseline_match',
        file='kit.py', ranges=[(210, 222)],
        must=['def baseline_match(state):',
              "eligibility(a,b)['status']!='feasible'",
              'score=sum(a[\'fields\'].get(k) is not None and a[\'fields\'].get(k)==b[\'fields\'].get(k) for k in SOFT)',
              'edges.append((-score,key))',
              'for _,pair in sorted(edges):'],
        verdicts=dict(
            direction='Higher raw score = better (score = count of SOFT fields '
                      'observed non-None on both sides and equal).',
            objective='No global objective: greedy take-while-free in descending '
                      'score order over the whole day edge list.',
            negation='(-score, key) is only an ASCENDING sort key; the value is '
                     'never handed to a maximizer. Direction correct.',
            unknowns='None on either side contributes 0 - neither match nor '
                     'penalty. Observed mismatch 0, observed match 1.',
            ties='sorted() on the canonical tuple key (u, v) ascending.',
            mode='SEQUENTIAL greedy, unconstrained cardinality (not fixed-k).',
            report_agreement='Matches its use as the official control everywhere '
                             '(tests, evaluate.py, tournament, e3, round2).'),
        classification='CORRECT'),
    dict(
        id='n01.allocate',
        file='research/next_method_search/n01_autopsy.py', ranges=[(137, 163)],
        must=['def allocate(state):',
              'kit.baseline_match line-for-line',
              'edges as (-score, key)',
              'edges.append((-score, key))',
              'for _, key in sorted(edges):'],
        verdicts=dict(
            direction='Same as kit: higher count = better; pairs identical to '
                      'the control (docstring + sorted-edge take loop).',
            objective='Sequential greedy for pairs; edges metadata in the '
                      '(-score, key) sort-key convention.',
            negation='Negation present but consumed ONLY by sorted() inside '
                     'allocate; the defect appears when a later writer '
                     'un-negates and a further consumer re-negates (see s1/fc).',
            unknowns='Identical to kit (both-non-None and equal).',
            ties='Canonical key ascending, identical to kit.',
            mode='Sequential greedy replica.',
            report_agreement='Report claims pairs identical to control; code '
                             'supports it.'),
        classification='CORRECT'),
    dict(
        id='s1_opportunities day_edges writer',
        file='research/round2_decision_ceiling/scripts/s1_opportunities.py',
        ranges=[(50, 58)],
        must=["edges=[[-e[0], list(e[1])] for e in ctx['edges']]"],
        verdicts=dict(
            direction='Writes day_edges entries as [-(-score), key] = '
                      '[+count, key]: the stored first element is a POSITIVE '
                      'count (previously verified against feat.pair_score).',
            objective='Serialization only.',
            negation='This line UN-negates n01\'s sort key. Any consumer that '
                     'applies -e[0] believing it still sees a negated score '
                     'therefore NEGATES the count.',
            unknowns='n/a (writes counts produced by the kit-equivalent formula).',
            ties='n/a.',
            mode='n/a.',
            report_agreement='ce_common.py L335 docstring still says '
                             '"(neg_score, key) from n01.allocate" - STALE, '
                             'contradicts this executable line; this stale doc '
                             'is the root cause of the downstream defect.'),
        classification='CORRECT_BUT_STALE_DOCUMENTATION'),
    dict(
        id='fc_selectors F1-SCORE + solve_exact_k',
        file='research/round2_fixed_cardinality/scripts/fc_selectors.py',
        ranges=[(121, 135)],
        must=["'F1-SCORE':  [-e[0] for e in raw],",
              'sel_i, obj, nodes, failed = solve_exact_k(edges, weightings[arm], kt)'],
        extra_files=[('research/round2_fixed_cardinality/scripts/fc_matching.py',
                      [(29, 47)],
                      ['def solve_exact_k(',
                       '"""Max-weight vertex-disjoint set of EXACTLY k edges.',
                       'order = sorted(range(n), key=lambda i: (-weights[i], _canon(edges[i])))',
                       'best_val = [float(\'-inf\')]',
                       'if wsum > best_val[0]:'])],
        verdicts=dict(
            direction='Intended: higher baseline count = better (the report '
                      'describes F1-SCORE as "exact-k max of baseline '
                      'soft-match count").',
            objective='solve_exact_k MAXIMIZES the sum of the weights it is '
                      'given (best_val updated on wsum >).',
            negation='raw stores POSITIVE counts (s1 writer), yet weights = '
                     '-e[0]: the maximizer therefore MAXIMIZES -count = '
                     'MINIMIZES the count. Double-negation defect at '
                     'fc_selectors.py L123.',
            unknowns='Count semantics inherited from the kit formula: unknown -> 0.',
            ties='Lexicographically smallest optimal matching (deterministic); '
                 'branch-and-bound order (-weight, canonical edge).',
            mode='GLOBAL fixed-cardinality exact-k optimization (by design).',
            report_agreement='FAILS Q7: report says "max of baseline soft-match '
                             'count"; actual output minimizes it (81 < greedy 90 '
                             '< maximizer 88 is the measured fingerprint).'),
        classification='DIRECTION_BUG'),
    dict(
        id='mo_validate F1-SCORE reproduction',
        file='research/round2_missed_oracle/scripts/mo_validate.py',
        ranges=[(168, 176)],
        must=["'F1-SCORE':  [-e[0] for e in raw],",
              'solve_exact_k'],
        verdicts=dict(
            direction='Intended same as fc F1-SCORE (frozen reproduction).',
            objective='Exact-k maximizer (imported from fc_matching).',
            negation='Same -e[0] on positive counts: reproduces the defective '
                     'arm faithfully (P_F1 = 81 matches fc).',
            unknowns='Same as fc.',
            ties='Same solver, lex-smallest.',
            mode='Global fixed-cardinality exact-k.',
            report_agreement='Reproduces the frozen (defective) arm as registered; the reproduction is correct even though the arm itself is direction-defective.'),
        classification='DIRECTION_BUG (faithful reproduction)'),
    dict(
        id='gr_common weight_g1f / weight_g1m',
        file='research/round2_goal_rule/scripts/gr_common.py',
        ranges=[(168, 184)],
        must=['def weight_g1f(neg_scores):',
              'return [-float(x) for x in neg_scores]',
              'def weight_g1m(neg_scores):',
              'return [float(x) for x in neg_scores]'],
        verdicts=dict(
            direction='day_edges values are positive counts (parameter name '
                      '"neg_scores" is stale but the values are positive).',
            objective='Both weights feed solve_exact_k (maximizer): g1f = '
                      '-count MINIMIZES (frozen reproduction, 81); g1m = '
                      '+count MAXIMIZES (spec-faithful, 88).',
            negation='g1f keeps the historical defect on purpose; g1m removes '
                     'it. Both series are published side by side (Amendment 1).',
            unknowns='Same count semantics for both.',
            ties='Same solver.',
            mode='Global fixed-cardinality exact-k.',
            report_agreement='Matches the report: G1f labelled frozen '
                             'reproduction, G1m labelled corrected maximizer.'),
        classification='CORRECT (defect reproduced only as a labelled series)'),
    dict(
        id='policy.py A+C scoring, floor, candidates',
        file='policy.py',
        ranges=[(415, 440), (454, 474), (558, 596)],
        must=['def rule_score(state, a_id, b_id):',
              'def max_score_matching(nodes, edges, floor):',
              'Greedy seed by (-score, a, b)',
              'key=lambda e: (-e[2], e[0], e[1])',
              'def ac_match(state):',
              'Floor-gated approximate max-score global matching',
              '(-rule_score(state, p[0], p[1]), p[0], p[1])'],
        verdicts=dict(
            direction='Higher is better: model score = sigmoid(baseline + tree '
                      'sum) in (0,1); rule_score feasible 1.0 > needs_'
                      'clarification 0.5 > infeasible -1, +0.01 per soft match.',
            objective='Per-day approximate MAX-score matching (greedy seed + up '
                      'to 8 strictly-improving moves), floor-gated; fallback '
                      'rule-greedy.',
            negation='-score / -rule_score appear only as descending sort keys; '
                     'never passed as maximization weights. Direction correct.',
            unknowns='Rule branch: unknown/declined fields do not count as soft '
                     'matches (0 contribution); model branch uses observed '
                     'soft-state features.',
            ties='(-score, a, b) then canonical (a, b) output order; deterministic.',
            mode='Full-sequential per-day policy (not fixed-k, not a replica of '
                 'per-pair sequential greedy - a documented design difference).',
            report_agreement='policy_ac.py forces mode=ac; container default '
                             'covers it. Matches spec R5 description.'),
        classification='CORRECT'),
    dict(
        id='method_tournament greedy_take + retained methods',
        file='research/method_tournament/alloc.py', ranges=[(10, 25)],
        must=['def greedy_take(edges):',
              'Sort by (-score, pair_key) then take non-overlapping: identical to kit.baseline_match',
              "key=lambda e: (-e[2], pair_key(e[0], e[1]))"],
        verdicts=dict(
            direction='e[2] is the POSITIVE count; (-e[2], pair_key) sorts '
                      'descending on count - same as kit.',
            objective='Sequential take-while-free (same as kit); retained '
                      'methods build on take_ordered/Hungarian with their own '
                      'positive scores, none weights a maximizer with -count.',
            negation='Sort-key only, consumed by sorted(); direction correct.',
            unknowns='Counts from the kit-equivalent score (unknown -> 0).',
            ties='pair_key canonical order, matching kit.',
            mode='Sequential greedy control; candidates = full-sequential '
                 'episodes run through evaluate.py on identical seeds.',
            report_agreement='"identical to kit.baseline_match" supported by '
                             'code; every tournament row is paired against '
                             'this control with seed-cluster inference.'),
        classification='CORRECT'),
    dict(
        id='mo_analyze baseline rank (suspected second inversion)',
        file='research/round2_missed_oracle/scripts/mo_analyze.py',
        ranges=[(31, 33), (88, 93), (115, 122)],
        must=['def competition_rank(score, all_scores):',
              '1 + count of strictly greater scores',
              'base_rank = {edges[i]: competition_rank(-raw[i][0], [-r[0] for r in raw])',
              'baseline_raw=-raw[i][0], baseline_rank=base_rank[e],'],
        verdicts=dict(
            direction='rank 1 = greatest score passed in. For F2 that is the '
                      'highest F2 score (correct). For baseline the score '
                      'passed is -raw with raw a POSITIVE count, so rank 1 = '
                      'LOWEST count - inverted relative to count quality.',
            objective='Descriptive ranking only (no selection).',
            negation='-raw[i][0] applies the stale neg_score convention a '
                     'second time; same root cause as the F1 selector defect.',
            unknowns='n/a.',
            ties='Competition ranking (1 + count strictly greater) - tied '
                 'scores share a rank, identically in both frames.',
            mode='n/a (descriptive).',
            report_agreement='Downstream claims ("baseline already puts most '
                             'positives near the top", "count ranks them '
                             'BETTER (0.388)", "F2 outranks baseline on only '
                             '32.4%") read lower rank as better under this '
                             'inverted frame. Whether they stand or invert is '
                             'decided by computation C5, not by this reading.'),
        classification='SUSPECTED_DIRECTION_BUG (impact decided by C5)'),
    dict(
        id='mo decomposition formulas (claim C)',
        file='research/round2_missed_oracle/scripts/mo_analyze.py',
        ranges=[(164, 168)],
        must=["ranking_component=P['F5-ORACLE'] - R_t",
              "conflict_component=R_t - P['F2-SOFT']",
              'R_t = sum(1 for i in topk_idx if edges[i] in pos)'],
        verdicts=dict(
            direction='Components are differences of positive counts of '
                      'positives captured; R_t = positives among top-k_t by F2.',
            objective='Additive decomposition identity: (P5 - R_t) + (R_t - P2) '
                      '= P5 - P2 = 67.',
            negation='None: no F1 term appears in either component (P_F1 exists '
                     'only as an aggregate context column in mo_decomp L22).',
            unknowns='Labels are counterfactual MSMI flags; no score semantics.',
            ties='R_t ties broken canonically by (-s2, canon) at L79.',
            mode='Diagnostic identity over saved sets.',
            report_agreement='Formulas match the report/plan decomposition '
                             'definition verbatim.'),
        classification='CORRECT (independent of the F1 defect)'),
]


def extract(path, ranges):
    lines = path.read_text(encoding='utf-8-sig').splitlines()
    out = []
    for a, b in ranges:
        for i in range(a, min(b, len(lines)) + 1):
            out.append('%4d| %s' % (i, lines[i - 1]))
    return out


def main():
    t0 = time.time()
    print('[bi1] start')
    facts, failures = [], []
    for f in FACTS:
        p = ROOT / f['file']
        if not p.exists():
            failures.append('%s: file missing %s' % (f['id'], f['file']))
            continue
        text = p.read_text(encoding='utf-8-sig')
        missing = [m for m in f['must'] if m not in text]
        if missing:
            failures.append('%s: missing patterns %r' % (f['id'], missing))
        excerpts = {f['file']: extract(p, f['ranges'])}
        for ef, er, em in f.get('extra_files', []):
            ep = ROOT / ef
            et = ep.read_text(encoding='utf-8-sig')
            m2 = [m for m in em if m not in et]
            if m2:
                failures.append('%s: missing patterns in %s %r'
                                % (f['id'], ef, m2))
            excerpts[ef] = extract(ep, er)
        facts.append(dict(id=f['id'], file=f['file'],
                          classification=f['classification'],
                          verdicts=f['verdicts'], excerpts=excerpts))
        print('[bi1] %-48s %s' % (f['id'], 'OK' if not missing else 'FAIL'))

    # ---- repo-wide absence scan: -e[0] weighting outside sanctioned dirs --
    sanctioned = ('round2_fixed_cardinality', 'round2_missed_oracle',
                  'round2_goal_rule', 'round2_baseline_integrity')
    # Expected, documented -e[0] site: the s1 writer that UN-negates n01's
    # sort key into day_edges (plan sec.4 item 3 / sec.8 item 2). It writes
    # data; it does not weight a maximizer.
    expected = {'research/round2_decision_ceiling/scripts/s1_opportunities.py'}
    hits = []
    for p in ROOT.rglob('*.py'):
        if '__pycache__' in str(p):
            continue
        rel = str(p.relative_to(ROOT)).replace('\\', '/')
        if any(s in rel for s in sanctioned) or rel in expected:
            continue
        try:
            txt = p.read_text(encoding='utf-8-sig', errors='replace')
        except OSError:
            continue
        for i, line in enumerate(txt.splitlines(), 1):
            if '-e[0]' in line.replace(' ', ''):
                hits.append('%s:%d: %s' % (rel, i, line.strip()[:120]))
    if hits:
        failures.append('-e[0] weighting outside sanctioned dirs: %r' % hits)
    print('[bi1] repo-wide -e[0] scan outside fc/mo/gr: %d hits'
          % len(hits))

    # ---- markdown output -------------------------------------------------
    md = ['# Score-Direction Source Facts (bi1)', '',
          'Generated %s by scripts/bi1_source_facts.py. Every excerpt is the'
          % time.strftime('%Y-%m-%d %H:%M:%S'),
          'executable text at the cited lines; pattern assertions fail the run',
          'if the code moves. Verdict questions follow analysis_plan.md sec.4.', '']
    for f in facts:
        md.append('## %s' % f['id'])
        md.append('')
        md.append('- File: `%s`' % f['file'])
        md.append('- Classification: **%s**' % f['classification'])
        md.append('')
        md.append('| Verdict question | Answer |')
        md.append('|---|---|')
        order = [('direction', '1. Higher or lower raw score is better?'),
                 ('objective', '2. Maximize or minimize the intended score?'),
                 ('negation', '3. Score negated into a maximizing solver?'),
                 ('unknowns', '4. Unknown / mismatch / match scoring?'),
                 ('ties', '5. Tie resolution?'),
                 ('mode', '6. Sequential greedy or fixed-k global?'),
                 ('report_agreement', '7. Output matches the report?')]
        for k, q in order:
            v = f['verdicts'].get(k, '')
            md.append('| %s | %s |' % (q, v.replace('|', '\\|')))
        md.append('')
        md.append('Excerpts:')
        md.append('')
        for ef, ex in f['excerpts'].items():
            md.append('`%s`' % ef)
            md.append('')
            md.append('```')
            md.extend(ex)
            md.append('```')
            md.append('')
    md.append('## Repo-wide negation scan')
    md.append('')
    md.append('`-e[0]` weight construction outside fc/mo/goal_rule: **%d hits**'
              % len(hits))
    if hits:
        md.extend('- `%s`' % h for h in hits)
    else:
        md.append('- none (no other study negates edge scores into a '
                  'maximizer).')
    md.append('')
    (OUT / 'source_facts.md').write_text('\n'.join(md), encoding='utf-8')
    (OUT / 'source_facts.json').write_text(
        json.dumps(dict(generated=time.strftime('%Y-%m-%d %H:%M:%S'),
                        n_facts=len(facts), failures=failures,
                        negation_scan_hits=hits,
                        facts=[dict(id=f['id'], file=f['file'],
                                    classification=f['classification'])
                               for f in facts]),
                   indent=1, sort_keys=True), encoding='utf-8')
    print('[bi1] facts=%d failures=%d' % (len(facts), len(failures)))
    for x in failures:
        print('[bi1] FAILURE: %s' % x)
    print('[bi1] done in %.1fs' % (time.time() - t0))
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
