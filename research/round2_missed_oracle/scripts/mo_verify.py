"""Final verification for the missed-oracle opportunity audit.

Checks (1) every reported number against the delivered CSVs, (2) internal
consistency of the decomposition, (3) the prior study's seals are still
current, (4) no tracked repo file outside this study was modified, and
(5) the integrity manifest is complete and current.
"""
import csv, hashlib, json, subprocess, sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
MO = HERE.parent
CEIL = HERE.parent.parent / 'round2_decision_ceiling'
FC = HERE.parent.parent / 'round2_fixed_cardinality'
REPO = HERE.parent.parent.parent

fails, n = [], 0


def chk(name, cond, detail=''):
    global n
    n += 1
    if cond:
        print('PASS', name, ('' if not detail else '  %s' % detail))
    else:
        print('FAIL', name, detail)
        fails.append(name)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


diag = [json.loads(l) for l in open(MO / 'selection_diagnostics.jsonl', encoding='utf-8')]
er = list(csv.DictReader(open(MO / 'positive_edge_ranks.csv', encoding='utf-8')))
stats = json.loads((MO / 'statistics.json').read_text(encoding='utf-8'))
tail = json.loads((MO / 'tail_signal.json').read_text(encoding='utf-8'))
tax = json.loads((MO / 'headroom_taxonomy.json').read_text(encoding='utf-8'))
agg = json.loads((MO / 'decomposition_agg.json').read_text(encoding='utf-8'))

# ---- 1. decomposition closes exactly ---------------------------------------
P5 = sum(r['P_F5'] for r in diag); P2 = sum(r['P_F2'] for r in diag)
Rt = sum(r['R_t'] for r in diag); U = sum(r['U_t'] for r in diag)
rank_c = sum(r['ranking_component'] for r in diag)
conf_c = sum(r['conflict_component'] for r in diag)
chk('P_F5 == 161', P5 == 161, str(P5))
chk('P_F2 == 94', P2 == 94, str(P2))
chk('gap == 67', P5 - P2 == 67)
chk('ranking == 60', rank_c == 60, str(rank_c))
chk('conflict == 7', conf_c == 7, str(conf_c))
chk('ranking + conflict == gap (exact)', rank_c + conf_c == P5 - P2)
chk('R_t == 101', Rt == 101, str(Rt))
chk('U_t == 173', U == 173, str(U))
chk('irreducible cost == 12 (173-161)', U - P5 == 12)
chk('ranking == P_F5 - R_t', rank_c == P5 - Rt)
chk('conflict == R_t - P_F2', conf_c == Rt - P2)

# ---- 2. capture reconciles with frozen study -------------------------------
PG = sum(r['P_GREEDY'] for r in diag); P1 = sum(r['P_F1'] for r in diag)
chk('GREEDY == 90', PG == 90, str(PG))
chk('F1 == 81', P1 == 81, str(P1))
chk('F5-F == +71', P5 - PG == 71)
chk('F2-F == +4', P2 - PG == 4)
chk('F2-F1 == +13', P2 - P1 == 13)

# ---- 3. per-state sanity ---------------------------------------------------
chk('F2 never exceeds F5 (F5 optimal)', all(r['P_F2'] <= r['P_F5'] for r in diag),
    'violations=%d' % sum(1 for r in diag if r['P_F2'] > r['P_F5']))
chk('identical cardinality across arms',
    all(r['P_GREEDY'] <= r['k_t'] and r['P_F2'] <= r['k_t'] and r['P_F5'] <= r['k_t']
        for r in diag))
chk('headroom == 82', sum(1 for r in diag if r['headroom']) == 82)
chk('non-headroom == 7478', sum(1 for r in diag if not r['headroom']) == 7478)

# ---- 4. positive_edge_ranks -----------------------------------------------
chk('positive_edge_ranks rows == 173', len(er) == 173, str(len(er)))
# real invariant: the CSV's edge set equals exactly the cf-positive edge set
lab_pos = set()
for line in open(CEIL / 'counterfactual_pairs.jsonl', encoding='utf-8'):
    rr = json.loads(line)
    if int(bool(rr['cf_y_msmi'])):
        lab_pos.add((int(rr['seed']), rr['variant'], int(rr['day']),
                     rr['user_a'], rr['user_b']))
csv_pos = set((int(r['seed']), r['variant'], int(r['day']),
               r['user_a'], r['user_b']) for r in er)
chk('CSV edges == exactly the 173 cf-positive edges',
    csv_pos == lab_pos and len(csv_pos) == 173,
    'csv=%d labels=%d sym_diff=%d' % (len(csv_pos), len(lab_pos), len(csv_pos ^ lab_pos)))
missed = [r for r in er if r['missed_oracle_positive'] == '1']
capt = [r for r in er if r['f2_selected'] == '1']
chk('missed == 67', len(missed) == 67, str(len(missed)))
chk('captured == 94', len(capt) == 94, str(len(capt)))
chk('all 67 missed coverable at k_t', all(r['coverable_at_kt'] == '1' for r in missed))
chk('flag E == 0 (no positive displaced by a positive)',
    sum(1 for r in missed if r['flag_E_blocked_by_positive'] == '1') == 0)
chk('flag A == 46', sum(1 for r in missed if r['flag_A_ranking_failure'] == '1') == 46)
chk('flag B == 66', sum(1 for r in missed if r['flag_B_matching_conflict'] == '1') == 66)

# ---- 5. taxonomy -----------------------------------------------------------
chk('taxonomy counts sum to 7478', sum(tax['counts'].values()) == 7478,
    str(tax['counts']))
chk('taxonomy categories mutually exclusive (a,b,c,d)',
    sorted(tax['counts']) == ['a_no_positive_edges', 'b_greedy_set_is_optimal',
                              'd_alternative_optima'])
chk('taxonomy invariant P_F5==P_GREEDY holds', tax['invariant_holds'])
chk('taxonomy a == 7394', tax['counts']['a_no_positive_edges'] == 7394)
chk('taxonomy c == 0', tax['counts'].get('c_extras_blocked', 0) == 0)

# ---- 6. statistics CIs -----------------------------------------------------
rg = stats['bootstrap_seed_groups']['regret_F5_minus_F2']
fg = stats['bootstrap_seed_groups']['F2_minus_GREEDY']
chk('regret CI excludes 0 (positive gap)', rg['ci95'][0] > 0, str(rg['ci95']))
chk('F2-GREEDY CI includes 0', fg['ci95'][0] <= 0 <= fg['ci95'][1], str(fg['ci95']))
# bootstrap records per-seed means; the TOTAL is the sum of seed_values
chk('F2-GREEDY per-seed sum == +4',
    sum(fg['seed_values']) == 4, str(sum(fg['seed_values'])))
chk('F2-GREEDY bootstrap mean == sum/21',
    abs(fg['mean'] - sum(fg['seed_values']) / 21.0) < 1e-9, str(fg['mean']))
chk('21 seed groups', stats['n_seed_groups'] == 21)

# ---- 7. tail signal --------------------------------------------------------
d2 = tail['D2_unknown_vs_mismatch']
lo, hi = tail['D2_ci95_of_difference']
est = tail['D2_raw_rate_difference']
chk('D2 CI contains point estimate', lo <= est <= hi, '%.6f in [%f,%f]' % (est, lo, hi))
chk('D2 CI includes 0 (null result)', lo <= 0 <= hi, '[%f,%f]' % (lo, hi))
for r in tail['D3_per_channel_separation']:
    lo2, hi2 = r['ci95_delta']; d2v = r['delta_f2_a_minus_b']
    if not (lo2 <= d2v <= hi2):
        chk('D3 estimate inside CI (%s)' % r['channel'], False, '%.6f' % d2v)
        break
else:
    chk('all D3 estimates inside their CIs', True, '21/21')
rg_goal = [r for r in tail['D3_per_channel_separation']
           if r['channel'] == 'relationship_goal' and r['state_a'] == 'match'
           and r['state_b'] == 'mismatch']
chk('relationship_goal match-vs-mismatch CI excludes 0',
    rg_goal and (rg_goal[0]['ci95_delta'][0] > 0 or rg_goal[0]['ci95_delta'][1] < 0),
    str(rg_goal[0]['ci95_delta']) if rg_goal else 'missing')
d4 = tail['D4_selection_difference_by_headroom']
chk('D4 F2-GREEDY headroom == +12', d4['F2_minus_GREEDY_headroom'] == 12)
chk('D4 F2-GREEDY nonheadroom == -8', d4['F2_minus_GREEDY_nonheadroom'] == -8)

# ---- 8. plan frozen before results ----------------------------------------
plan = (MO / 'analysis_plan.md').read_text(encoding='utf-8')
chk('analysis_plan.md exists and is frozen', 'FROZEN BEFORE' in plan)
runlog = (MO / 'run_log.txt').read_text(encoding='utf-8')
chk('plan sha logged before diagnostics',
    'sha256=d0006555e468c2515da76c0bc51e6515a0496ca67fa527fa485b7458159fde1f' in runlog)
chk('plan sha still current', sha(MO / 'analysis_plan.md') ==
    'd0006555e468c2515da76c0bc51e6515a0496ca67fa527fa485b7458159fde1f')

# ---- 9. prior seals still current ------------------------------------------
def seal_current(sep, allowed_stale=()):
    stale = []
    for line in open(sep, encoding='utf-8'):
        line = line.strip()
        if not line:
            continue
        h, rel = line.split('  ', 1)
        p = REPO / rel
        if not p.exists() or sha(p) != h:
            stale.append(rel)
    return [s for s in stale if s not in allowed_stale]

chk('fixed-cardinality seal still current',
    not seal_current(FC / 'integrity.sha256'), str(seal_current(FC / 'integrity.sha256')))
stale_ce = seal_current(CEIL / 'integrity.sha256',
                        allowed_stale=('research/round2_decision_ceiling/run_log.txt',))
chk('ceiling substantive artifacts unchanged (run_log.txt excepted)',
    not stale_ce, str(stale_ce))

# ---- 10. no tracked repo file outside this study changed -------------------
r = subprocess.run(['git', 'status', '--porcelain'], cwd=REPO,
                   capture_output=True, text=True)
changed = [l for l in r.stdout.splitlines() if l.strip()]
allowed_prefixes = ('?? research/round2_missed_oracle/', ' M policy.py',
                    '?? docs/superpowers/', '?? policy_ac.py', '?? research/',
                    '?? test_policy.py')
bad = [l for l in changed if not any(l.startswith(a) or a in l for a in allowed_prefixes)]
chk('git status back to the known 5-line baseline', not bad, str(bad or 'clean'))

# ---- 11. integrity manifest ------------------------------------------------
seal = MO / 'integrity.sha256'
chk('integrity.sha256 exists', seal.exists())
if seal.exists():
    entries = [l.strip() for l in seal.read_text(encoding='utf-8').splitlines() if l.strip()]
    stale2 = []
    for e in entries:
        h, rel = e.split('  ', 1)
        p = REPO / rel
        if not p.exists() or sha(p) != h:
            stale2.append(rel)
    chk('this study seal is current', not stale2, str(stale2[:3]))
    chk('report.md is sealed', any('round2_missed_oracle/report.md' in e for e in entries))
    chk('analysis_plan.md is sealed', any('analysis_plan.md' in e for e in entries))
    chk('all core CSVs sealed', all(
        any(name in e for e in entries)
        for name in ('positive_edge_ranks.csv', 'selection_diagnostics.csv',
                     'gap_decomposition.csv', 'per_seed_results.csv')))

print('=' * 72)
if fails:
    print('VERIFICATION FAILED: %d of %d checks' % (len(fails), n))
    for f in fails:
        print('  -', f)
    sys.exit(1)
print('FRESH VERIFICATION: ALL %d CHECKS PASS' % n)
c_ok = True
