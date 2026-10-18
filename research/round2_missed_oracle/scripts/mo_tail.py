"""Section 7: tail-signal analysis of soft-channel states (match/mismatch/unknown).

Soft-channel states are recomputed with the ceiling audit's EXACT rule via
s3_signal.derived_features_from_row - never reimplemented. All F2/F1 scores
are the held-out (out-of-fold) scores already recorded in oof_scores.jsonl;
this section performs NO refit.

HONESTY: an observed raw-rate difference between "unknown" and "mismatch" is
reported together with the generation/selection evidence that could explain
it. Unknown is NOT asserted to be intrinsically better than mismatch.
"""
import json, sys, time
from collections import defaultdict
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
MO = HERE.parent
CEIL = HERE.parent.parent / 'round2_decision_ceiling'
sys.path.insert(0, str(CEIL / 'scripts'))
import ce_common as c   # noqa: E402
import s3_signal as s3  # noqa: E402

SOFT = s3.SOFT_CHANNELS      # 7
B, SEED = 2000, 4242


def boot_seed(seed_ids, vals, b=B, seed=SEED):
    """95% percentile CI resampling whole seed groups."""
    uniq = sorted(set(seed_ids))
    by = defaultdict(list)
    for s, v in zip(seed_ids, vals):
        by[s].append(v)
    arr = np.array([np.mean(by[s]) for s in uniq], float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(arr), size=(b, len(arr)))
    bs = arr[idx].mean(axis=1)
    return [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]


def cluster_boot_diff(sa, sb, b=B, seed=SEED):
    """Two-sample cluster bootstrap of (pooled mean of sa) - (pooled mean of sb).

    sa/sb are lists of (seed, value) pairs. Resamples whole seed groups, then
    recomputes each stratum's POOLED (edge-weighted) mean on the resampled
    seeds only. Returns the percentile 95% CI for the same estimand as the
    point estimate mean(sa) - mean(sb).
    """
    uniq = sorted(set(s for s, _ in sa) | set(s for s, _ in sb))
    bya = {s: [v for t, v in sa if t == s] for s in uniq}
    byb = {s: [v for t, v in sb if t == s] for s in uniq}
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(b):
        pick = rng.choice(len(uniq), size=len(uniq), replace=True)
        xa, xb = [], []
        for i in pick:
            xa.extend(bya[uniq[i]]); xb.extend(byb[uniq[i]])
        if xa and xb:
            out.append(float(np.mean(xa)) - float(np.mean(xb)))
    return [float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))]


def main():
    t0 = time.time(); c.log('mo_tail start')
    side = s3.load_state_side()
    oof = {}
    for line in open(CEIL / 'oof_scores.jsonl', encoding='utf-8'):
        r = json.loads(line)
        oof[(r['seed'], r['variant'], r['day'], r['user_a'], r['user_b'])] = (
            float(r['F2_soft_state']), float(r['F1_baseline_count_score']),
            int(bool(r['y'])), r['seed'], r['variant'])

    recs = []
    for line in open(CEIL / 'counterfactual_pairs.jsonl', encoding='utf-8'):
        r = json.loads(line)
        k = (r['seed'], r['variant'], r['day'], r['user_a'], r['user_b'])
        f2, f1, y, seed, variant = oof[k]
        feat = s3.derived_features_from_row(r, side)
        counts = {st: 0 for st in s3.SOFT_STATES}
        per_ch = {}
        for ch in SOFT:
            for st in s3.SOFT_STATES:
                v = feat.get('sc_%s_%s' % (ch, st), 0.0)
                if v:
                    counts[st] += 1
                    per_ch[ch] = st
        recs.append(dict(f2=f2, f1=f1, y=y, seed=seed, variant=variant,
                         counts=counts, per_ch=per_ch,
                         has_unknown=counts['unknown'] > 0,
                         has_mismatch=counts['mismatch'] > 0,
                         has_match=counts['match'] > 0,
                         has_declined=counts['declined'] > 0))

    out = {'n_edges': len(recs), 'soft_channels': SOFT,
           'soft_states': s3.SOFT_STATES, 'notes': []}

    # ---- D1 mean F2 score by soft-state composition -----------------------
    d1 = []
    for nu in (0, 1, 2, 3):
        for nm in (0, 1, 2, 3):
            sub = [r for r in recs if r['counts']['unknown'] == nu
                   and r['counts']['mismatch'] == nm]
            if len(sub) < 20:
                continue
            d1.append(dict(n_unknown=nu, n_mismatch=nm, n_edges=len(sub),
                           mean_f2=round(float(np.mean([r['f2'] for r in sub])), 6),
                           mean_f1=round(float(np.mean([r['f1'] for r in sub])), 6),
                           msmi_rate=round(float(np.mean([r['y'] for r in sub])), 6)))
    out['D1_score_by_composition'] = d1

    # ---- D2 unknown vs mismatch counterfactual MSMI rate -------------------
    # strata chosen to make the comparison as like-for-like as the data allow:
    #   unknown_only  : >=1 unknown, 0 mismatch
    #   mismatch_only : >=1 mismatch, 0 unknown
    #   both          : >=1 of each
    #   neither       : 0 of both
    def stratum(r):
        if r['has_unknown'] and r['has_mismatch']:
            return 'both'
        if r['has_unknown']:
            return 'unknown_only'
        if r['has_mismatch']:
            return 'mismatch_only'
        return 'neither'
    d2 = {}
    for s in ('unknown_only', 'mismatch_only', 'both', 'neither'):
        sub = [r for r in recs if stratum(r) == s]
        if not sub:
            d2[s] = None; continue
        d2[s] = dict(n_edges=len(sub),
                     n_positive=sum(r['y'] for r in sub),
                     n_seeds=len(set(r['seed'] for r in sub)),
                     n_seeds_present_both_strata=None,
                     msmi_rate=round(float(np.mean([r['y'] for r in sub])), 6),
                     mean_f2=round(float(np.mean([r['f2'] for r in sub])), 6),
                     ci95_msmi=boot_seed([r['seed'] for r in sub],
                                         [r['y'] for r in sub]))
    out['D2_unknown_vs_mismatch'] = d2
    if d2['unknown_only'] and d2['mismatch_only']:
        out['D2_raw_rate_difference'] = round(
            d2['unknown_only']['msmi_rate'] - d2['mismatch_only']['msmi_rate'], 6)
        # proper two-sample cluster bootstrap: resample seed groups, then
        # recompute each stratum's pooled rate on the resampled seeds only.
        # The point estimand is the pooled (edge-weighted) rate difference.
        su = [r for r in recs if stratum(r) == 'unknown_only']
        sm = [r for r in recs if stratum(r) == 'mismatch_only']
        uniq = sorted(set(r['seed'] for r in su + sm))
        bu = {s: [r['y'] for r in su if r['seed'] == s] for s in uniq}
        bm = {s: [r['y'] for r in sm if r['seed'] == s] for s in uniq}
        rng = np.random.default_rng(SEED)
        diffs = []
        for _ in range(B):
            pick = rng.choice(len(uniq), size=len(uniq), replace=True)
            au, am = [], []
            for i in pick:
                au.extend(bu[uniq[i]]); am.extend(bm[uniq[i]])
            if au and am:
                diffs.append(float(np.mean(au)) - float(np.mean(am)))
        out['D2_ci95_of_difference'] = [float(np.percentile(diffs, 2.5)),
                                        float(np.percentile(diffs, 97.5))]
        out['notes'].append(
            'D2 raw rate difference is DESCRIPTIVE. unknown_only and '
            'mismatch_only differ in which fields were asked and by whom; the '
            'comparison is NOT a causal effect of ignorance vs mismatch. The '
            'seed-group CI reflects sampling of seeds, not removal of this '
            'generation/selection confound.')

    # ---- D3 per-channel score separation ---------------------------------
    d3 = []
    for ch in SOFT:
        for a, b in (('match', 'mismatch'), ('unknown', 'mismatch'),
                     ('unknown', 'match')):
            sa = [r for r in recs if r['per_ch'].get(ch) == a]
            sb = [r for r in recs if r['per_ch'].get(ch) == b]
            if len(sa) < 15 or len(sb) < 15:
                continue
            d3.append(dict(channel=ch, state_a=a, state_b=b,
                           n_a=len(sa), n_b=len(sb),
                           mean_f2_a=round(float(np.mean([r['f2'] for r in sa])), 6),
                           mean_f2_b=round(float(np.mean([r['f2'] for r in sb])), 6),
                           delta_f2_a_minus_b=round(float(np.mean([r['f2'] for r in sa])
                                                           - np.mean([r['f2'] for r in sb])), 6),
                           ci95_delta=cluster_boot_diff(
                               [(r['seed'], r['f2']) for r in sa],
                               [(r['seed'], r['f2']) for r in sb]),
                           msmi_a=round(float(np.mean([r['y'] for r in sa])), 6),
                           msmi_b=round(float(np.mean([r['y'] for r in sb])), 6),
                           data_sufficient=len(sa) >= 30 and len(sb) >= 30))
    out['D3_per_channel_separation'] = d3

    # ---- D4 does F2-F1 selection difference concentrate in headroom states -
    diag = [json.loads(l) for l in open(MO / 'selection_diagnostics.jsonl',
                                        encoding='utf-8')]
    hr = [d for d in diag if d['headroom']]
    nh = [d for d in diag if not d['headroom']]
    def agg(rows, a, b):
        return sum(r[a] - r[b] for r in rows)
    out['D4_selection_difference_by_headroom'] = dict(
        n_headroom_states=len(hr), n_nonheadroom_states=len(nh),
        F2_minus_GREEDY_headroom=agg(hr, 'P_F2', 'P_GREEDY'),
        F2_minus_GREEDY_nonheadroom=agg(nh, 'P_F2', 'P_GREEDY'),
        F2_minus_F5_headroom=agg(hr, 'P_F2', 'P_F5'),
        F2_minus_F5_nonheadroom=agg(nh, 'P_F2', 'P_F5'),
        ranking_component_headroom=sum(r['ranking_component'] for r in hr),
        ranking_component_nonheadroom=sum(r['ranking_component'] for r in nh),
        conflict_component_headroom=sum(r['conflict_component'] for r in hr),
        conflict_component_nonheadroom=sum(r['conflict_component'] for r in nh),
        note=('A negative conflict_component means R_t < P_F2: the naive '
              'top-k_t-by-score set contained FEWER positives than F2 actually '
              'kept, because the top-scoring edges overlapped one another and '
              'the non-overlap constraint forced F2 onto a more diverse set '
              'that happened to include more positives. On zero-headroom '
              'states the matching constraint therefore partly RECOVERS for '
              "F2's ranking rather than costing it."))

    (MO / 'tail_signal.json').write_text(json.dumps(out, indent=1, sort_keys=True) + '\n',
                                         encoding='utf-8')
    print('D1 strata:', len(d1))
    print('D2:', {k: (v['msmi_rate'] if v else None) for k, v in d2.items()})
    print('D2 raw diff:', out.get('D2_raw_rate_difference'),
          'ci:', out.get('D2_ci95_of_difference'))
    print('D3 rows:', len(d3), '| sufficient:', sum(1 for r in d3 if r['data_sufficient']))
    print('D4:', json.dumps(out['D4_selection_difference_by_headroom'], indent=1))
    c.log('mo_tail done (%.1fs)' % (time.time() - t0))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
