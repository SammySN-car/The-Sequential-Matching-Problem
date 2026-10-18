"""G0: counterfactual replay validity tests (analysis_plan.md sec. 2.2).

T1 pair-orientation invariance; T2 batch independence; T2L snapshot leak check;
T3 isolated replay of every selected introduction; T4 label sums vs official;
T5 determinism. Writes g0_results.json and g0_replay_validation.md only.

Snapshots are consumed inside the replay callback and discarded, so only one
simulator snapshot exists in memory at a time.
"""
import json, random, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ce_common as c  # noqa: E402

LABEL_KEYS = ('mature', 'y_msmi', 'y_mutual', 'y_date', 'y_second', 'missing')
N_SAMPLE = 50          # first-N-by-iteration-order, so sampling is deterministic


def run_structure_tests(worlds, n_sample=N_SAMPLE):
    """T1, T2 and T2L in a single streaming replay pass."""
    st = dict(t1_tested=0, t1_bad=0, t2_tested=0, t2_bad=0,
              t2l_tested=0, t2l_bad=0)
    for seed, variant in worlds:
        def per_day(ctx, _st=st):
            snap = ctx['snap']
            fp = c.snapshot_fingerprint(snap)
            edges = [list(k) for _, k in sorted(ctx['edges'])]
            if not edges:
                return
            # T2L: run_pair_isolated raises if the snapshot leaks; a raise here
            # would abort the pass, so we also re-fingerprint explicitly.
            if _st['t1_tested'] < n_sample:
                pair = edges[_st['t1_tested'] % len(edges)]
                try:
                    s1, mid1 = c.run_pair_isolated(snap, [pair[0], pair[1]])
                    s2, mid2 = c.run_pair_isolated(snap, [pair[1], pair[0]])
                    e1 = [e for e in s1.events if e['introduction_id'] == mid1]
                    e2 = [e for e in s2.events if e['introduction_id'] == mid2]
                    _st['t1_tested'] += 1
                    if mid1 != mid2 or e1 != e2:
                        _st['t1_bad'] += 1
                except AssertionError:
                    _st['t1_bad'] += 1
                    _st['t1_tested'] += 1
            if ctx['pairs'] and _st['t2_tested'] < n_sample:
                try:
                    batch = c.clone_from(snap)
                    batch.advance([list(p) for p in ctx['pairs']])
                    ok = True
                    for pair in ctx['pairs']:
                        s, mid = c.run_pair_isolated(snap, list(pair))
                        solo = [e for e in s.events
                                if e['introduction_id'] == mid]
                        got = [e for e in batch.events
                               if e['introduction_id'] == mid]
                        if solo != got:
                            ok = False
                    _st['t2_tested'] += 1
                    if not ok:
                        _st['t2_bad'] += 1
                except AssertionError:
                    _st['t2_bad'] += 1
                    _st['t2_tested'] += 1
            if _st['t2l_tested'] < n_sample:
                _st['t2l_tested'] += 1
                if c.snapshot_fingerprint(snap) != fp:
                    _st['t2l_bad'] += 1
        c.replay_world(seed, variant, per_day=per_day, follow_up=False)
    return [
        dict(test='T1_pair_orientation', tested=st['t1_tested'],
             mismatched=st['t1_bad'], passed=bool(st['t1_bad'] == 0)),
        dict(test='T2_batch_independence', tested=st['t2_tested'],
             mismatched=st['t2_bad'], passed=bool(st['t2_bad'] == 0)),
        dict(test='T2L_snapshot_leak', tested=st['t2l_tested'],
             mismatched=st['t2l_bad'], passed=bool(st['t2l_bad'] == 0)),
    ]


def run_full_pass():
    """T3 + T4: isolate-replay every selected introduction in all 126 worlds."""
    frozen = c.frozen_intro_index()
    world_rows = c.frozen_world_rows()
    out = {}
    for seed, variant in c.world_list():
        iso = {}

        def per_day(ctx, _iso=iso):
            for pair in ctx['pairs']:
                sim_after, mid = c.run_pair_isolated(ctx['snap'], list(pair))
                _iso[mid] = c.labels_from_events(mid, sim_after.events,
                                                 c.HORIZON, ctx['day'])

        digest, _ = c.replay_world(seed, variant, per_day=per_day,
                                   follow_up=False)
        off = world_rows[(seed, variant)]
        compared = mismatched = missing = 0
        bad_ids = []
        for mid, lab in iso.items():
            ref = frozen.get((seed, variant, mid))
            if ref is None:
                missing += 1
                continue
            compared += 1
            if any(lab.get(k) != ref.get(k) for k in LABEL_KEYS):
                mismatched += 1
                if len(bad_ids) < 5:
                    bad_ids.append(mid)
        seen = {k[2] for k in frozen if k[0] == seed and k[1] == variant}
        mature = [v for v in iso.values() if v['mature']]
        sums = dict(assignments=len(iso),
                    mutual=sum(v['y_mutual'] for v in mature),
                    dates=sum(v['y_date'] for v in mature),
                    msmi=sum(v['y_msmi'] for v in mature),
                    missing=sum(v['missing'] for v in mature))
        out['%d|%s' % (seed, variant)] = dict(
            seed=seed, variant=variant,
            digest_ok=(digest == off['replay_digest']),
            n_selected=len(iso), n_compared=compared,
            n_label_mismatch=mismatched, n_mid_missing=missing,
            n_unreplayed=len(seen - set(iso)), sums=sums,
            sums_ok=(sums == off['sums']),
            n_immature=sum(1 for v in iso.values() if not v['mature']),
            final_day=c.HORIZON, mismatched_ids=bad_ids)
        c.log('T3 %d/%s selected=%d compared=%d mismatch=%d sums_ok=%s'
              % (seed, variant, len(iso), compared, mismatched,
                 sums == off['sums']))
    return out


def aggregate(res):
    return dict(
        worlds=len(res),
        digest_ok=sum(1 for r in res.values() if r['digest_ok']),
        sums_ok=sum(1 for r in res.values() if r['sums_ok']),
        n_selected=sum(r['n_selected'] for r in res.values()),
        n_compared=sum(r['n_compared'] for r in res.values()),
        n_label_mismatch=sum(r['n_label_mismatch'] for r in res.values()),
        n_mid_missing=sum(r['n_mid_missing'] for r in res.values()),
        n_unreplayed=sum(r['n_unreplayed'] for r in res.values()),
        n_immature=sum(r['n_immature'] for r in res.values()),
        msmi_total=sum(r['sums']['msmi'] for r in res.values()),
        mutual_total=sum(r['sums']['mutual'] for r in res.values()),
        dates_total=sum(r['sums']['dates'] for r in res.values()),
        missing_total=sum(r['sums']['missing'] for r in res.values()))


def write_validation_md():
    r = json.loads((c.OUT / 'g0_results.json').read_text(encoding='utf-8'))
    t3 = r.get('T3_isolated_replay', {})
    checks = [
        ('T1 pair-orientation invariance',
         r.get('T1_pair_orientation', {}).get('passed'),
         '%d runs, 0 mismatches' % r.get('T1_pair_orientation', {}).get('tested', 0)),
        ('T2 batch independence',
         r.get('T2_batch_independence', {}).get('passed'),
         '%d days, 0 mismatches' % r.get('T2_batch_independence', {}).get('tested', 0)),
        ('T2L snapshot leak', r.get('T2L_snapshot_leak', {}).get('passed'),
         '%d snapshots unchanged' % r.get('T2L_snapshot_leak', {}).get('tested', 0)),
        ('T3 isolated replay exact match',
         t3.get('n_label_mismatch') == 0 and t3.get('n_mid_missing') == 0
         and t3.get('n_unreplayed') == 0 and t3.get('n_compared') == 8433,
         '8433/8433 exact on mature, y_msmi, y_mutual, y_date, y_second, missing'),
        ('T3b action digest reproduction', t3.get('digest_ok') == 126,
         '126/126 digests equal n01_replay_rows'),
        ('T4 label sums vs official',
         t3.get('sums_ok') == 126 and t3.get('n_immature') == 0,
         '126/126 per-world sums equal; 0 immature at horizon 100'),
        ('T5 determinism', r.get('T5_determinism', {}).get('passed'),
         'two full passes bit-identical'),
    ]
    go = all(bool(ok) for _, ok, _ in checks)
    lines = ['# G0 - Counterfactual Replay Validation', '',
             '**Status: %s**' % ('GO - proceed to sections 3-7' if go
                                 else 'NO-GO - section 4 and beyond must not run'),
             '',
             'Protocol horizon %d = 60 decision days + 40 follow-up days '
             '(`evaluate.episode`, `evaluate.py` L80-115).' % c.HORIZON, '',
             '| Test | Result | Criterion |', '|---|---|---|']
    for name, ok, crit in checks:
        lines.append('| %s | %s | %s |' % (name, 'PASS' if ok else 'FAIL', crit))
    lines += ['', '## Method', '',
              'Each counterfactual run starts from `copy.deepcopy(Simulator)` '
              'taken after `resolve_asks` and before `advance` on the decision '
              'day, giving the copy its own `introductions`, `events`, `past` '
              'and `busy` (the only containers `kit.Simulator.advance` writes, '
              'verified against kit.py L141-189). The pair is run alone with '
              '`advance([[a,b]])` under the sorted orientation produced at '
              'kit.py L152, then followed with `advance([])` to day %d so labels '
              'use the same maturity rules as the official rollout. A '
              'fingerprint of the four mutated containers is taken before and '
              'after every isolated run; any change aborts the pass.' % c.HORIZON,
              '',
              '## Per-world detail', '',
              '| seed | variant | selected | compared | mismatch | digest | sums |',
              '|---|---|---|---|---|---|---|']
    for key in sorted(r.get('T3_per_world', {}),
                      key=lambda s: (int(s.split('|')[0]), s)):
        w = r['T3_per_world'][key]
        lines.append('| %d | %s | %d | %d | %d | %s | %s |' % (
            w['seed'], w['variant'], w['n_selected'], w['n_compared'],
            w['n_label_mismatch'], 'ok' if w['digest_ok'] else 'FAIL',
            'ok' if w['sums_ok'] else 'FAIL'))
    (c.OUT / 'g0_replay_validation.md').write_text(
        '\n'.join(lines) + '\n', encoding='utf-8')
    c.log('g0_replay_validation.md written; verdict=%s' % ('GO' if go else 'NO-GO'))
    return go
