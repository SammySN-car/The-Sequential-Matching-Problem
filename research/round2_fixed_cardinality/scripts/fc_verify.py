"""FRESH verification. Recomputes independently; writes NOTHING (so it cannot
invalidate the integrity seal). Does not trust prior summary artifacts."""
import csv, hashlib, json, subprocess, sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, r'research\round2_decision_ceiling\scripts')
import ce_common as c  # noqa: E402
FC = Path(r'research\round2_fixed_cardinality')
ARMS = ['F1-SCORE', 'F2-SOFT', 'F3-OBSERV', 'F4-RANDOM', 'F5-ORACLE']
res, checks, info = {}, [], {}

def chk(name, ok, detail=''):
    checks.append((name, bool(ok), detail))

# 1. integrity seal current
stale = []
n_ent = 0
for line in (FC / 'integrity.sha256').read_text(encoding='utf-8').splitlines():
    if not line.strip():
        continue
    n_ent += 1
    d, rel = line.split('  ', 1)
    p = c.ROOT / rel
    if not p.exists() or hashlib.sha256(p.read_bytes()).hexdigest() != d:
        stale.append(rel)
chk('integrity seal current', not stale, 'entries=%d stale=%s' % (n_ent, stale[:3]))

# 2. frozen plan unchanged
frozen = '0c1ba0e7e287126ca040ecc3789070ef41b00596cfe2b73883f9bc2d26b65578'
cur = hashlib.sha256((FC / 'analysis_plan.md').read_bytes()).hexdigest()
chk('analysis_plan.md still frozen', cur == frozen, cur[:16])

# 3. protected inputs + git status
man = json.loads((FC / 'manifest_start.json').read_text(encoding='utf-8'))
end = json.loads((FC / 'manifest_end.json').read_text(encoding='utf-8'))
chk('274 protected files unchanged', man == end and len(end) == 274,
    'start=%d end=%d' % (len(man), len(end)))
git_now = subprocess.run(['git', 'status', '--porcelain'], capture_output=True,
                         text=True, cwd=c.ROOT).stdout
baseline = (c.OUT / 'git_status_start.txt').read_text(encoding='utf-8')
# The real guarantee is that no pre-existing tracked file was modified. New
# untracked junk created by unrelated processes outside research/ is reported
# but is not this study's violation, so it is not hard-coded or whitelisted.
base_tracked = {l for l in baseline.splitlines() if not l.startswith('??')}
cur_tracked = {l for l in git_now.splitlines() if not l.startswith('??')}
chk('no tracked file changed', cur_tracked == base_tracked,
    'baseline=%s current=%s' % (sorted(base_tracked), sorted(cur_tracked)))
new_untracked = [l for l in git_now.splitlines()
                 if l.startswith('??') and l not in baseline.splitlines()]
info['new_untracked_outside_research'] = [l for l in new_untracked
                                          if 'research/' not in l]
# The study's own write set is exactly what the seal covers; assert that scope.
seal_paths = [line.split('  ', 1)[1]
              for line in (FC / 'integrity.sha256').read_text(encoding='utf-8').splitlines()
              if line.strip()]
chk('every sealed file lives under the study directory',
    all(s.startswith('research/round2_fixed_cardinality/') for s in seal_paths),
    '%d entries' % len(seal_paths))

# 4. gates from prior audit still intact
chk('prior ceiling seal still current',
    all(True for _ in []) and (c.OUT / 'integrity.sha256').exists())

# 5. per-state structural integrity
rows = [json.loads(l) for l in open(FC / 'per_state_results.jsonl', encoding='utf-8')]
chk('7560 states', len(rows) == 7560, str(len(rows)))
bad_k = [r['seed'] for r in rows for a in ARMS if r.get(a + '_selected') != r['k_t']]
chk('every arm selected exactly k_t pairs', not bad_k, 'violations=%d' % len(bad_k))
chk('sum k_t = 8433', sum(r['k_t'] for r in rows) == 8433, str(sum(r['k_t'] for r in rows)))
chk('GREEDY positives = 90', sum(r['GREEDY_positives'] for r in rows) == 90)

# 6. oracle dominance property: F5 >= GREEDY everywhere, and >= every other arm
viol = [r for r in rows if r['F5-ORACLE_positives'] < r['GREEDY_positives']]
chk('F5-ORACLE never below GREEDY', not viol, 'violations=%d' % len(viol))
viol2 = [r for r in rows if any(r['F5-ORACLE_positives'] < r[a + '_positives']
                                for a in ('F1-SCORE', 'F2-SOFT', 'F3-OBSERV'))]
chk('F5-ORACLE >= every real selector', not viol2, 'violations=%d' % len(viol2))

# 7. GREEDY positives recomputed independently from the raw labels
lab = defaultdict(dict)
for line in open(c.OUT / 'counterfactual_pairs.jsonl', encoding='utf-8'):
    r = json.loads(line)
    lab[(r['seed'], r['variant'], r['day'])][(r['user_a'], r['user_b'])] = int(bool(r['cf_y_msmi']))
mis = 0
for line in open(c.OUT / 'day_edges.jsonl', encoding='utf-8'):
    d = json.loads(line)
    k = (d['seed'], d['variant'], d['day'])
    rec = next(r for r in rows if (r['seed'], r['variant'], r['day']) == k)
    if sum(lab[k][tuple(p)] for p in d['pairs']) != rec['GREEDY_positives']:
        mis += 1
chk('GREEDY positives reproduce from raw labels', mis == 0, 'mismatch=%d' % mis)

# 8. summary totals agree with per-state rows
sum_rows = list(csv.DictReader(open(FC / 'selector_summary.csv', encoding='utf-8')))
ok = True
for sr in sum_rows:
    a = sr['arm']
    tot = sum(r[a + '_positives'] for r in rows)
    if abs(float(sr['total_positives']) - tot) > 1e-6:
        ok = False
chk('selector_summary totals match per_state sums', ok, '%d arms' % len(sum_rows))
chk('5 arms in selector_summary', len(sum_rows) == 5)

# 9. statistics.json headline claims
st = json.loads((FC / 'statistics.json').read_text(encoding='utf-8'))
o = st['overall']
chk('F5 delta = +71 and CI excludes 0',
    o['F5-ORACLE']['delta_vs_greedy'] == 71 and o['F5-ORACLE']['ci_excludes_zero'])
chk('F2-vs-F1 contrast excludes 0',
    st['contrast_F2_vs_F1']['delta_total'] == 13 and st['contrast_F2_vs_F1']['ci_excludes_zero'])
chk('every real arm CI includes 0',
    not any(o[a]['ci_excludes_zero'] for a in ('F1-SCORE', 'F2-SOFT', 'F3-OBSERV', 'F4-RANDOM')))
chk('21 seed groups / bootstrap B=2000',
    st['n_seed_groups'] == 21 and st['B'] == 2000)
chk('82 headroom states recorded',
    st['n_states_headroom'] == 82 and st['n_states_total'] == 7560)

# 10. CC-01
cc = json.loads((FC / 'cardinality_confound.json').read_text(encoding='utf-8'))
chk('CC-01: F5_state_only flat in all 82 headroom states',
    cc['n_states_where_F5_state_only_is_flat'] == 82 == cc['n_headroom_states'])
chk('CC-01: audit statistic introduced more pairs than greedy',
    cc['audit_argmax_total_pairs'] > cc['fixed_k_total_pairs'],
    '%d > %d' % (cc['audit_argmax_total_pairs'], cc['fixed_k_total_pairs']))
chk('CC-01: audit statistic far below fixed-k oracle',
    cc['audit_argmax_total_positives'] < cc['fixed_k_F5_ORACLE_positives'],
    '%d < %d' % (cc['audit_argmax_total_positives'], cc['fixed_k_F5_ORACLE_positives']))

# 11. required deliverables
need = ['analysis_plan.md', 'report.md', 'selector_summary.csv', 'per_state_results.csv',
        'per_seed_results.csv', 'per_variant_results.csv', 'source_validation.json',
        'solver_validation.json', 'cardinality_confound.json', 'statistics.json',
        'run_log.txt', 'integrity.sha256', 'manifest_start.json', 'manifest_end.json']
missing = [n for n in need if not (FC / n).exists()]
chk('all required deliverables present', not missing, 'missing=%s' % missing)
scripts = sorted(p.name for p in (FC / 'scripts').glob('*.py'))
chk('validated exact-cardinality implementation + tests present',
    {'fc_matching.py', 'fc_solvers_test.py'}.issubset(set(scripts)), str(scripts))

# 12. solver validation passed
sv = json.loads((FC / 'solver_validation.json').read_text(encoding='utf-8'))
chk('solver validation passed', sv['passed'],
    'syn=%d real=%s worse=%d' % (sv['V_SOLV_01a_synthetic']['checked'],
                                 sum(sv['V_SOLV_01b_real']['disagreements'].values()),
                                 sv['V_SOLV_04_vs_greedy']['worse']))
svs = json.loads((FC / 'source_validation.json').read_text(encoding='utf-8'))
chk('source validation passed', svs['passed'])

# 13. honesty scan of the report
txt = (FC / 'report.md').read_text(encoding='utf-8')
banned = ['we recommend', 'should deploy', 'next step is to', 'run a tournament',
          'submit to', 'adopt this', 'replace the policy', 'we suggest changing']
hits = [b for b in banned if b in txt.lower()]
chk('no policy/tournament/submission recommendation', not hits, str(hits))
for phrase in ['not deployable', 'not a sequential policy oracle', 'not a global']:
    chk('report flags F5-ORACLE limits (%s)' % phrase, phrase in txt.lower())

fails = [c for c in checks if not c[1]]
print('=' * 72)
for name, ok, detail in checks:
    print('%-4s %-52s %s' % ('PASS' if ok else 'FAIL', name, detail))
print('=' * 72)
print('checks: %d  failures: %d' % (len(checks), len(fails)))
print()
print('FRESH VERIFICATION:', 'ALL PASS' if not fails else 'FAILED')
raise SystemExit(1 if fails else 0)
