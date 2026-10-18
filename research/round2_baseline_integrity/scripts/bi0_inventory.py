"""bi0: inventory, protected-code hashes, read-only prior-seal verification,
input-artifact hashes, counterfactual seed groups, and the A4 policy-run scan.

Read-only over the whole repository; writes only under this study directory.
"""
import csv
import hashlib
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
ROOT = HERE.parents[2]

DIRS = ['out', 'out_scale800', 'next_method_search', 'next_strategy_research',
        'e3_rel_experiment', 'method_tournament', 'round1_submission', 'round2',
        'round2_stage1_5', 'round2_stage2_floor_ablation',
        'round2_stage3_intermediate_floor', 'round2_promotion_fresh_seeds',
        'round2_stage4_history_coldstart_audit', 'round2_opr', 'round2_eda',
        'round2_decision_ceiling', 'round2_fixed_cardinality',
        'round2_missed_oracle', 'round2_stagewise_signal', 'round2_goal_rule',
        'round2_baseline_integrity']

PROTECTED = ['policy.py', 'policy_ac.py', 'kit.py', 'evaluate.py', 'Dockerfile',
             'test_policy.py', 'test_kit.py', 'research/test_pipeline.py',
             'research/features.py']

# (study, tolerate run_log append) - tolerance mirrors each study's own
# verify convention where known (gr_verify: ceiling/stagewise True, fc/mo
# False); eda/opr/goal_rule manifests were not covered by a prior verify, so
# they are reported strictly and only run_log entries may differ.
SEALS = [('round2_decision_ceiling', True), ('round2_eda', True),
         ('round2_fixed_cardinality', False), ('round2_goal_rule', True),
         ('round2_missed_oracle', False), ('round2_opr', True),
         ('round2_stagewise_signal', True)]

INPUTS = [
    'research/round2_goal_rule/analysis_plan.md',
    'research/round2_goal_rule/analysis_plan.sha256',
    'research/round2_goal_rule/per_state_results.csv',
    'research/round2_goal_rule/selector_sets.jsonl',
    'research/round2_goal_rule/evaluation.json',
    'research/round2_goal_rule/selector_summary.csv',
    'research/round2_goal_rule/report.md',
    'research/round2_decision_ceiling/day_edges.jsonl',
    'research/round2_decision_ceiling/oof_scores.jsonl',
    'research/round2_decision_ceiling/counterfactual_pairs.jsonl',
    'research/round2_missed_oracle/selection_diagnostics.jsonl',
    'research/round2_missed_oracle/recomputed_sets.jsonl',
    'research/round2_missed_oracle/positive_edge_ranks.csv',
    'research/round2_missed_oracle/decomposition_agg.json',
    'research/round2_missed_oracle/gap_decomposition.csv',
    'research/round2_missed_oracle/report.md',
    'research/round2_fixed_cardinality/selector_summary.csv',
    'research/round2_fixed_cardinality/statistics.json',
    'research/round2_fixed_cardinality/report.md',
    'research/round2_stagewise_signal/ranking_by_stage.json',
    'research/round2_stagewise_signal/report.md',
    'research/round2_stagewise_signal/seed_group_metrics.csv',
    'research/e3_rel_experiment/summary.json',
    'research/e3_rel_experiment/report.md',
    'research/method_tournament/final_results.json',
    'research/method_tournament/confirmation_results.json',
    'research/method_tournament/final_report.md',
    'research/round2_promotion_fresh_seeds/summary.json',
    'research/round2_promotion_fresh_seeds/report.md',
    'research/round2/report.md',
    'research/round2_eda/report.md',
    'research/out/report.txt',
    'research/out_scale800/report.txt',
    'research/next_method_search/report.md',
    'kit.py', 'policy.py', 'policy_ac.py', 'evaluate.py', 'Dockerfile',
]


def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def log(msg):
    line = '[%s] %s' % (time.strftime('%Y-%m-%d %H:%M:%S'), msg)
    print(line)
    with open(OUT / 'run_log.txt', 'a', encoding='utf-8') as fh:
        fh.write(line + '\n')


def main():
    t0 = time.time()
    log('bi0_inventory start')

    # ---- 1. directory inventory ------------------------------------------
    inv = {}
    for d in DIRS:
        p = ROOT / 'research' / d
        if p.exists():
            n = sum(1 for x in p.rglob('*')
                    if x.is_file() and '__pycache__' not in str(x))
            inv[d] = dict(exists=True, files=n)
        else:
            inv[d] = dict(exists=False, files=0)
    missing = [d for d, v in inv.items() if not v['exists']]
    log('inventory: %d/%d directories exist; missing=%s'
        % (len(DIRS) - len(missing), len(DIRS), missing or 'none'))

    # ---- 2. protected code hashes ----------------------------------------
    prot, prot_missing = {}, []
    for rel in PROTECTED:
        p = ROOT / rel
        if p.exists():
            prot[rel] = sha256(p)
        else:
            prot_missing.append(rel)
    log('protected: %d hashed, missing=%s' % (len(prot), prot_missing or 'none'))

    # ---- 3. prior seals (read-only verification) -------------------------
    seals, seal_fail = {}, []
    for name, tol in SEALS:
        m = ROOT / 'research' / name / 'integrity.sha256'
        if not m.exists():
            seals[name] = dict(manifest=False)
            continue
        # Path base differs by study: root-relative (research/<d>/...) for
        # ceiling/fc/goal_rule/mo/ss, study-dir-relative for eda/opr.
        strict, non_runlog, entries = [], [], 0
        base_used = 'root'
        for line in m.read_text(encoding='utf-8').splitlines():
            if not line.strip():
                continue
            d, rel = line.split('  ', 1)
            entries += 1
            p = ROOT / rel
            if not p.exists() and not rel.startswith('research/'):
                p = m.parent / rel
                base_used = 'study_dir'
            if not p.exists() or sha256(p) != d:
                strict.append(rel)
                if not rel.endswith('run_log.txt'):
                    non_runlog.append(rel)
        tolerated = sorted(set(strict) - set(non_runlog))
        seals[name] = dict(manifest=True, entries=entries,
                           path_base=base_used,
                           stale_strict=sorted(strict),
                           stale_non_runlog=sorted(non_runlog),
                           run_log_tolerated_by_convention=tol,
                           stale_run_log=tolerated)
        if non_runlog:
            seal_fail.append(name)
        log('seal %-32s entries=%d stale(non-runlog)=%s run_log_stale=%s'
            % (name, entries, non_runlog or 'none', tolerated or 'none'))

    # ---- 4. A4 scan: any full-sequential F2 policy run? ------------------
    f2_files = []
    for p in ROOT.rglob('*.py'):
        if '__pycache__' in str(p) or str(p).startswith(str(OUT)):
            continue
        try:
            txt = p.read_text(encoding='utf-8-sig', errors='replace')
        except OSError:
            continue
        if 'F2_soft_state' in txt or 'F2-SOFT' in txt:
            f2_files.append(str(p.relative_to(ROOT)).replace('\\', '/'))
    policy_like = [f for f in f2_files
                   if Path(f).name.startswith('policy')
                   or 'evaluate' in Path(f).name
                   or 'runner' in Path(f).name]
    log('A4 scan: %d files reference F2; policy/runner/evaluate files=%s'
        % (len(f2_files), policy_like or 'none'))

    # ---- 5. counterfactual seed groups ----------------------------------
    seeds, seed_err = [], None
    ps = ROOT / 'research/round2_goal_rule/per_state_results.csv'
    try:
        with open(ps, newline='', encoding='utf-8-sig') as fh:
            seeds = sorted({int(r['seed']) for r in csv.DictReader(fh)})
    except Exception as e:  # documented, not silently dropped
        seed_err = repr(e)
    log('counterfactual seed groups: n=%d %s%s'
        % (len(seeds), seeds, (' ERR=' + seed_err) if seed_err else ''))

    # ---- 6. input artifact hashes ---------------------------------------
    inputs, inputs_missing = {}, []
    for rel in INPUTS:
        p = ROOT / rel
        if p.exists():
            inputs[rel] = sha256(p)
        else:
            inputs_missing.append(rel)
    for name, _ in SEALS:
        p = ROOT / 'research' / name / 'integrity.sha256'
        if p.exists():
            inputs['research/%s/integrity.sha256' % name] = sha256(p)
    log('input hashes: %d recorded, missing=%s'
        % (len(inputs), inputs_missing or 'none'))

    out = dict(
        generated=time.strftime('%Y-%m-%d %H:%M:%S'),
        study='round2_baseline_integrity',
        plan_sha256=(OUT / 'analysis_plan.sha256').read_text(
            encoding='utf-8').split()[0],
        inventory=inv,
        protected=prot,
        protected_missing=prot_missing,
        seals=seals,
        seal_fail_non_runlog=seal_fail,
        f2_reference_files=sorted(f2_files),
        f2_policy_like_files=policy_like,
        counterfactual_seed_groups=seeds,
        counterfactual_seed_error=seed_err,
        inputs=inputs,
        inputs_missing=inputs_missing)
    (OUT / 'input_hashes.json').write_text(
        json.dumps(out, indent=1, sort_keys=True), encoding='utf-8')

    ok = not missing and not prot_missing and not seal_fail and not seed_err
    log('bi0 done in %.1fs -> input_hashes.json (ok=%s)' % (time.time() - t0, ok))
    if not ok:
        print('BI0 FAILURE: missing_dirs=%s missing_protected=%s seal_fail=%s'
              % (missing, prot_missing, seal_fail))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
