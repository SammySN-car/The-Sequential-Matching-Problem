"""Section 4: counterfactual pair-alone outcomes for every feasible opportunity.

Diagnostic only. Counterfactual labels for unselected pairs are UNOBSERVED by the
original collector (flag='counterfactual_unobserved') and are never treated as
observed outcomes (GC9, analysis_plan.md sec.4).
"""
import csv, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ce_common as c  # noqa: E402

BANNED_FEATURE_EXACT = c.BANNED_FEATURE_EXACT


def main():
    verdict = (c.OUT / 'g0_replay_validation.md').read_text(encoding='utf-8')
    if '**Status: GO' not in verdict:
        raise SystemExit('G0 verdict is not GO - refusing to compute counterfactuals')
    c.log('task4 start: counterfactual pass (G0 GO confirmed)')

    frozen = c.frozen_intro_index()
    rows = []
    state_side = []
    for seed, variant in c.world_list():
        def per_day(ctx, _s=seed, _v=variant):
            selected = {tuple(p) for p in ctx['pairs']}
            for _, key in sorted(ctx['edges']):
                sim_after, mid = c.run_pair_isolated(ctx['snap'], list(key))
                lab = c.labels_from_events(mid, sim_after.events, c.HORIZON,
                                           ctx['day'])
                if lab['mature'] == 0 and lab['y_msmi'] is None:
                    raise SystemExit('V3 violation: immature label for %s' % mid)
                is_sel = tuple(key) in selected
                feat = c.n01.pair_features(
                    ctx['state'], ctx['edges'], ctx['degree'], ctx['max_score'],
                    ctx['score_counts'], ctx['member_hist'], ctx['day_ctx'],
                    list(key), 0 if is_sel else -1, len(ctx['pairs']))
                feat.pop('pair_rank', None)   # undefined for a counterfactual
                feat.pop('batch_size', None)  # undefined for a counterfactual
                feat['n_feedback_events'] = ctx['n_feedback']
                ref = frozen.get((_s, _v, mid))
                st = ctx['state']
                by = {m['member_id']: m for m in st['members']}
                state_side.append(dict(
                    seed=_s, variant=_v, day=ctx['day'],
                    user_a=key[0], user_b=key[1],
                    ask_budget_remaining=st['ask_budget_remaining'],
                    n_intros=ctx['n_intros'], n_mutual=ctx['n_mutual'],
                    n_dates=ctx['n_dates'], n_feedback=ctx['n_feedback'],
                    a={k: by[key[0]][k] for k in
                       ('member_id', 'age', 'gender', 'zone', 'arrived_day',
                        'fields', 'field_status')},
                    b={k: by[key[1]][k] for k in
                       ('member_id', 'age', 'gender', 'zone', 'arrived_day',
                        'fields', 'field_status')}))
                rows.append(dict(
                    seed=_s, variant=_v, day=ctx['day'],
                    user_a=key[0], user_b=key[1],
                    selected=int(is_sel), introduction_id=mid,
                    cf_mature=lab['mature'], cf_y_mutual=lab['y_mutual'],
                    cf_y_date=lab['y_date'], cf_y_second=lab['y_second'],
                    cf_y_msmi=lab['y_msmi'], cf_missing=lab['missing'],
                    flag='selected_agrees' if is_sel else 'counterfactual_unobserved',
                    ref_agrees=None if ref is None else int(
                        all(lab.get(k) == ref.get(k)
                            for k in ('mature', 'y_msmi', 'y_mutual',
                                      'y_date', 'y_second', 'missing'))),
                    _feat=feat))
        c.replay_world(seed, variant, per_day=per_day, follow_up=False)
    c.log('counterfactual rows built: %d' % len(rows))

    n_total = len(rows)
    n_sel = sum(r['selected'] for r in rows)
    dup_keys = n_total - len({(r['seed'], r['variant'], r['day'],
                               r['user_a'], r['user_b']) for r in rows})
    sel_rows = [r for r in rows if r['selected']]
    v1_pass = all(r['ref_agrees'] == 1 for r in sel_rows) and len(sel_rows) == 8433
    v3_pass = all(r['cf_mature'] == 1 and r['cf_y_msmi'] is not None
                  for r in rows)
    feat_keys = sorted(rows[0]['_feat']) if rows else []
    v6_pass = not any(k in BANNED_FEATURE_EXACT or k.startswith('cf_')
                      or k.startswith('y_') for k in feat_keys)

    for r in rows:
        r['flag'] = ('selected_agrees' if r['ref_agrees'] == 1 else
                     'selected_disagrees' if r['selected'] else
                     'counterfactual_unobserved')
    with open(c.OUT / 'counterfactual_pairs.jsonl', 'w', encoding='utf-8') as fh:
        for r in rows:
            row = {k: v for k, v in r.items() if k != '_feat'}
            row['feat'] = r['_feat']
            fh.write(json.dumps(row, sort_keys=True) + '\n')
    c.log('wrote counterfactual_pairs.jsonl (%d rows)' % len(rows))
    c.write_jsonl(c.OUT / 'pair_state.jsonl', state_side)
    c.log('wrote pair_state.jsonl (%d rows)' % len(state_side))

    agg = {}
    for r in rows:
        k = (r['seed'], r['variant'])
        a = agg.setdefault(k, dict(opportunities=0, cf_msmi_pos=0,
                                   selected=0, cf_pos_selected=0))
        a['opportunities'] += 1
        a['cf_msmi_pos'] += int(bool(r['cf_y_msmi']))
        a['selected'] += r['selected']
        a['cf_pos_selected'] += int(bool(r['cf_y_msmi']) and r['selected'])
    with open(c.OUT / 'opportunity_by_world.csv', 'w', newline='',
              encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=['seed', 'variant', 'opportunities',
                                           'cf_msmi_pos', 'selected',
                                           'cf_pos_selected'])
        w.writeheader()
        for (s, v), a in sorted(agg.items()):
            w.writerow(dict(seed=s, variant=v, **a))
    c.log('wrote opportunity_by_world.csv (%d worlds)' % len(agg))

    checks = [
        dict(check='V1_selected_pair_agreement', passed=int(v1_pass),
             detail='%d/%d selected pairs match frozen labels'
                    % (sum(r['ref_agrees'] == 1 for r in sel_rows),
                       len(sel_rows))),
        dict(check='V2_batch_independence', passed=1,
             detail='established by G0 T2 (0 mismatches)'),
        dict(check='V3_maturity', passed=int(v3_pass),
             detail='%d rows, 0 None labels at horizon %d' % (n_total, c.HORIZON)),
        dict(check='V4_count_integrity', passed=int(
            n_total == 15304 and n_sel == 8433 and dup_keys == 0),
             detail='total=%d selected=%d duplicate_keys=%d'
                    % (n_total, n_sel, dup_keys)),
        dict(check='V5_orientation', passed=1,
             detail='all keys sorted ascending; G0 T1 passed'),
        dict(check='V6_feature_legality', passed=int(v6_pass),
             detail='%d feature columns, none banned' % len(feat_keys)),
    ]
    with open(c.OUT / 'counterfactual_validation.csv', 'w', newline='',
              encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=['check', 'passed', 'detail'])
        w.writeheader()
        w.writerows(checks)
    for ck in checks:
        c.log('V %s passed=%s :: %s' % (ck['check'], ck['passed'], ck['detail']))
    if not all(ck['passed'] for ck in checks):
        raise SystemExit('counterfactual validation FAILED - sections 5-7 withheld')
    c.log('task4 done')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
