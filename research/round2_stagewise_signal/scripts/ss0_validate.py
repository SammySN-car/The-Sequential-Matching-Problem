"""Step 0: validation gate + isolated-replay stage funnel.

V0  Prior seals (decision-ceiling, fixed-cardinality) still current.
V1  Selected-pair replay labels still match the frozen n01 outcomes.
V2  Recomputed y_mutual/y_date/y_second/y_msmi/missing equal the stored
    cf_* columns bit-exactly (the replay reproduces the ceiling labels).
V3  Counts: 15304 rows / 8433 selected / 173 final-MSMI / 90 selected MSMI.
V5  Refitting A/B/C for final_msmi reproduces oof_scores.jsonl bit-exactly.

Writes stage_funnel.jsonl (full event-detail funnel, same row order as
counterfactual_pairs.jsonl) and validation.json.
"""
import hashlib, json, sys, time
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ss_common as s   # noqa: E402
import ce_common as c   # noqa: E402
import s3_signal as s3  # noqa: E402

checks, info = [], {}


def chk(name, ok, detail=''):
    checks.append(dict(check=name, passed=int(bool(ok)), detail=detail))
    print('%-4s %-58s %s' % ('PASS' if ok else 'FAIL', name, detail), flush=True)


def verify_seal(study_dir, tolerate=()):
    stale = []
    for line in (study_dir / 'integrity.sha256').read_text(
            encoding='utf-8').splitlines():
        if not line.strip():
            continue
        d, rel = line.split('  ', 1)
        p = s.ROOT / rel
        if not p.exists() or hashlib.sha256(p.read_bytes()).hexdigest() != d:
            stale.append(rel)
    unexpected = [x for x in stale if not any(x.endswith(t) for t in tolerate)]
    return unexpected, stale


def main():
    t0 = time.time()
    s.log('ss0_validate start')

    # ---- V0 prior seals ---------------------------------------------------
    unf, stale = verify_seal(s.CEIL_DIR, tolerate=('run_log.txt',))
    chk('ceiling substantive artifacts unchanged', not unf,
        'unexpected=%s' % (unf[:3] or 'none'))
    chk('ceiling seal differs only in run_log.txt',
        set(stale).issubset({'research/round2_decision_ceiling/run_log.txt'}),
        'stale=%s' % (stale or 'none'))
    unf2, _ = verify_seal(s.FC_DIR)
    chk('fixed-cardinality seal still current', not unf2,
        'unexpected=%s' % (unf2[:3] or 'none'))

    # ---- plan hash frozen -------------------------------------------------
    plan_sha = hashlib.sha256(
        (s.OUT / 'analysis_plan.md').read_bytes()).hexdigest()
    frozen_sha = (s.OUT / 'analysis_plan.sha256').read_text(
        encoding='utf-8').split()[0]
    chk('analysis_plan hash matches frozen record', plan_sha == frozen_sha,
        plan_sha[:16])

    # ---- replay all 126 worlds, extract the full funnel -------------------
    frozen = c.frozen_intro_index()
    rows = []
    for seed, variant in c.world_list():
        def per_day(ctx, _s=seed, _v=variant):
            selected = {tuple(p) for p in ctx['pairs']}
            for _, key in sorted(ctx['edges']):
                sim_after, mid = c.run_pair_isolated(ctx['snap'], list(key))
                lab = c.labels_from_events(mid, sim_after.events, c.HORIZON,
                                           ctx['day'])
                stg = s.stages_from_events(mid, sim_after.events, ctx['day'])
                if lab['mature'] == 0 and lab['y_msmi'] is None:
                    raise SystemExit('V3 immature label for %s' % mid)
                # internal consistency: stages_from_events == labels_from_events
                assert (stg['mutual'], stg['date'], stg['timely_second'],
                        stg['final_msmi']) == \
                       (lab['y_mutual'], lab['y_date'], lab['y_second'],
                        lab['y_msmi']), mid
                is_sel = tuple(key) in selected
                ref = frozen.get((_s, _v, mid))
                ref_agrees = None if ref is None else int(all(
                    lab.get(k) == ref.get(k)
                    for k in ('mature', 'y_msmi', 'y_mutual', 'y_date',
                              'y_second', 'missing')))
                rows.append(dict(
                    seed=_s, variant=_v, day=ctx['day'],
                    user_a=key[0], user_b=key[1],
                    selected=int(is_sel), introduction_id=mid,
                    ref_agrees=ref_agrees,
                    missing_recomputed=lab['missing'],
                    **stg))
        c.replay_world(seed, variant, per_day=per_day, follow_up=False)
    s.log('replay done: %d stage rows' % len(rows))

    # ---- alignment with counterfactual_pairs.jsonl (row order) -----------
    stored = c.read_jsonl(s.CEIL_DIR / 'counterfactual_pairs.jsonl')
    keys_new = [(r['seed'], r['variant'], r['day'], r['user_a'], r['user_b'])
                for r in rows]
    keys_old = [(r['seed'], r['variant'], r['day'], r['user_a'], r['user_b'])
                for r in stored]
    chk('stage rows align 1:1 with counterfactual_pairs.jsonl',
        keys_new == keys_old, '%d vs %d' % (len(keys_new), len(keys_old)))
    old_by_key = {k: r for k, r in zip(keys_old, stored)}

    # ---- V1 selected-pair agreement with frozen n01 outcomes -------------
    sel = [r for r in rows if r['selected']]
    v1_pass = (len(sel) == 8433 and all(r['ref_agrees'] == 1 for r in sel))
    chk('V1 selected pairs match frozen n01 labels',
        v1_pass, '%d/%d agree, n_selected=%d'
        % (sum(r['ref_agrees'] == 1 for r in sel), len(sel), len(sel)))

    # ---- V2 recomputed stage labels == stored cf_* -----------------------
    maxdiff = {'y_mutual': 0, 'y_date': 0, 'y_second': 0, 'y_msmi': 0,
               'missing': 0}
    for r in rows:
        o = old_by_key[(r['seed'], r['variant'], r['day'], r['user_a'],
                        r['user_b'])]
        maxdiff['y_mutual'] = max(maxdiff['y_mutual'],
                                  abs(r['mutual'] - int(bool(o['cf_y_mutual']))))
        maxdiff['y_date'] = max(maxdiff['y_date'],
                                abs(r['date'] - int(bool(o['cf_y_date']))))
        maxdiff['y_second'] = max(maxdiff['y_second'],
                                  abs(r['timely_second'] - int(bool(o['cf_y_second']))))
        maxdiff['y_msmi'] = max(maxdiff['y_msmi'],
                                abs(r['final_msmi'] - int(bool(o['cf_y_msmi']))))
        maxdiff['missing'] = max(maxdiff['missing'],
                                 abs(r['missing_recomputed'] - o['cf_missing']))
    chk('V2 recomputed labels equal stored cf_* bit-exactly',
        all(v == 0 for v in maxdiff.values()), 'maxdiff=%s' % maxdiff)
    info['v2_max_abs_diff'] = maxdiff

    # ---- V3 counts -------------------------------------------------------
    n_total = len(rows)
    n_sel = sum(r['selected'] for r in rows)
    n_pos = sum(r['final_msmi'] for r in rows)
    n_pos_sel = sum(r['final_msmi'] for r in rows if r['selected'])
    dup = n_total - len(set(keys_new))
    chk('V3 counts 15304/8433/173/90, no duplicate keys',
        (n_total, n_sel, n_pos, n_pos_sel, dup) == (15304, 8433, 173, 90, 0),
        'total=%d selected=%d pos=%d pos_selected=%d dup=%d'
        % (n_total, n_sel, n_pos, n_pos_sel, dup))
    info['counts'] = dict(rows=n_total, selected=n_sel, msmi_pos=n_pos,
                          msmi_pos_selected=n_pos_sel, duplicate_keys=dup)

    # ---- V5 refit A/B/C for final_msmi, require bit-exact OOF ------------
    fr = s3.load_frame()
    chk('V5 frame rows = 15304', len(fr['y']) == 15304, str(len(fr['y'])))
    chk('V5 frame target equals stage final_msmi',
        [int(x) for x in fr['y']] == [r['final_msmi'] for r in rows],
        'target aligned to replayed funnel')
    stored_oof = s.load_existing_oof()
    for set_name, cols in s.FEATURE_SETS.items():
        X = np.array([[f.get(k, 0.0) for k in cols] for f in fr['feat']],
                     dtype=np.float32)
        oof = s3.oof_scores(X, fr['y'], fr['groups'])
        dmax = 0.0
        for i in range(len(oof)):
            k = keys_old[i]
            dmax = max(dmax, abs(float(stored_oof[k][
                'F1_baseline_count_score' if set_name == 'A_baseline_count'
                else 'F2_soft_state' if set_name == 'B_soft_state'
                else 'F4_full_legal_observables']) - float(oof[i])))
        chk('V5 refit %s reproduces stored OOF bit-exactly' % set_name,
            dmax == 0.0, 'max|d|=%r' % dmax)
        info['v5_max_abs_diff_' + set_name] = dmax

    s.write_jsonl(s.OUT / 'stage_funnel.jsonl', rows)

    n_pass = sum(ck['passed'] for ck in checks)
    result = dict(passed=n_pass == len(checks), n_checks=len(checks),
                  failures=[ck for ck in checks if not ck['passed']],
                  info=info)
    (s.OUT / 'validation.json').write_text(
        json.dumps(result, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    s.log('ss0_validate %s (%d/%d checks, %.1fs)'
          % ('PASSED' if result['passed'] else 'FAILED',
             n_pass, len(checks), time.time() - t0))
    if not result['passed']:
        raise SystemExit('VALIDATION FAILED - downstream sections withheld')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
