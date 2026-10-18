"""Section 5: is there decision-time signal for MSMI inside available choice sets?

Fits the frozen model under seed-group cross-validation on the counterfactual
frame and answers questions B-E. Counterfactual labels of unselected pairs are
UNOBSERVED by the original collector and are used only as diagnostic targets
(GC9); nothing here is trained for deployment.
"""
import csv, hashlib, json, sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ce_common as c  # noqa: E402
from sklearn.ensemble import HistGradientBoostingClassifier  # noqa: E402
from sklearn.metrics import roc_auc_score, average_precision_score  # noqa: E402
from sklearn.model_selection import GroupKFold  # noqa: E402

BANNED_FEATURE_EXACT = c.BANNED_FEATURE_EXACT

# analysis_plan.md sec.5.1. Lists are explicit and closed; assert_legal_features
# rejects anything not named here.
F1 = ['pair_score', 'pair_score_deficit', 'score_is_max', 'edges_total',
      'edges_at_same_score', 'n_available', 'n_intros_so_far']

SOFT_CHANNELS = ['relationship_goal', 'relationship_pace', 'lifestyle',
                 'conversations', 'emotional_availability',
                 'space_for_relationship', 'relocate']
HARD_CHANNELS = ['who_to_meet', 'age', 'geography', 'smoking',
                 'children_present', 'relationship_structure',
                 'children_plans', 'schedule']
HARD_STATES = ['pass', 'fail', 'unknown']
SOFT_STATES = ['match', 'mismatch', 'unknown', 'declined']

GENDER_BUCKETS = 7     # declared constants, not tuned
ZONE_BUCKETS = 97
N_SPLITS = 4
MODEL_KW = dict(max_iter=200, learning_rate=0.06, random_state=40)


def stable_bucket(name, nb):
    """Fixed integer bucket for a categorical.

    CPython's built-in hash() on str is salted per process (PYTHONHASHSEED), so
    it is NOT a "fixed integer bucket". md5-truncated is stable across runs,
    which is what analysis_plan.md 5.1 requires of the declared constants.
    """
    return float(int(hashlib.md5(str(name).encode('utf-8')).hexdigest(), 16) % nb)


def f2_columns():
    cols = []
    for ch in HARD_CHANNELS:
        for d in ('ab', 'ba'):
            for st in HARD_STATES:
                cols.append('hc_%s_%s_%s' % (ch, d, st))
    for k in SOFT_CHANNELS:
        for st in SOFT_STATES:
            cols.append('sc_%s_%s' % (k, st))
    return cols


F2_EXTRA = f2_columns()          # 8*2*3 + 7*4 = 76 columns
F3_EXTRA = ['age_a', 'age_b', 'gender_a', 'gender_b', 'zone_a', 'zone_b',
            'days_since_arrival_a', 'days_since_arrival_b',
            'n_hard_observed_a', 'n_hard_observed_b',
            'n_soft_observed_a', 'n_soft_observed_b', 'has_profile_gap']
F4_EXTRA = ['day', 'ask_budget_match', 'has_history', 'has_prior',
            'prior_intro_max', 'prior_mutual_total', 'prior_date_total',
            'degree_min', 'degree_max', 'degree_excl_min', 'degree_excl_max',
            'new_arrival_today', 'n_mutual_so_far', 'n_dates_so_far',
            'n_feedback_events', 'arrival_age_min', 'arrival_age_max',
            'age_gap', 'same_gender', 'zone_same', 'soft_obs_min', 'soft_obs_max',
            'soft_unequal', 'soft_unknown_max', 'soft_declined_max']
F5 = ['day', 'ask_budget_match', 'n_available', 'edges_total',
      'n_intros_so_far', 'n_mutual_so_far', 'n_dates_so_far', 'has_history',
      'n_feedback_events']

FEATURE_SETS = {
    'F1_baseline_count_score': F1,
    'F2_soft_state': F1 + F2_EXTRA,
    'F3_public_profile': F1 + F2_EXTRA + F3_EXTRA,
    'F4_full_legal_observables': F1 + F2_EXTRA + F3_EXTRA + F4_EXTRA,
    'F5_state_only': F5,
}


def hard_state(a, b, ch, direction):
    """Eligibility channel status for one direction, from public fields only."""
    x, y = (a, b) if direction == 'ab' else (b, a)
    fx, fy = x['fields'], y['fields']
    if ch == 'who_to_meet':
        if fx.get('who_to_meet') is None:
            return 'unknown'
        return 'pass' if y['gender'] in fx['who_to_meet'] else 'fail'
    if ch == 'age':
        if fx.get('age_min') is None or fx.get('age_max') is None:
            return 'unknown'
        return 'pass' if fx['age_min'] <= y['age'] <= fx['age_max'] else 'fail'
    if ch == 'geography':
        if fx.get('acceptable_zones') is None:
            return 'unknown'
        return 'pass' if y['zone'] in fx['acceptable_zones'] else 'fail'
    if ch == 'smoking':
        if fx.get('partner_smoking') is None or fy.get('smoking') is None:
            return 'unknown'
        if fx['partner_smoking'] == 'no_smoking' and \
           fy['smoking'] in ('yes', 'occasionally'):
            return 'fail'
        return 'pass'
    if ch == 'children_present':
        if fx.get('partner_children') is None or fy.get('has_children') is None:
            return 'unknown'
        return 'fail' if (fx['partner_children'] == 'no_children'
                          and fy['has_children'] is True) else 'pass'
    if ch == 'relationship_structure':
        if fx.get('relationship_structure') is None or \
           fy.get('relationship_structure') is None:
            return 'unknown'
        return ('pass' if fx['relationship_structure']
                == fy['relationship_structure'] else 'fail')
    if ch == 'children_plans':
        wc = {fx.get('wants_children'), fy.get('wants_children')}
        if None in wc:
            return 'unknown'
        return 'fail' if wc == {'yes', 'no'} else 'pass'
    if ch == 'schedule':
        if fx.get('schedule') is None or fy.get('schedule') is None:
            return 'unknown'
        return 'pass' if set(fx['schedule']) & set(fy['schedule']) else 'fail'
    raise ValueError(ch)


def derived_features(state, key):
    by = {m['member_id']: m for m in state['members']}
    a, b = by[key[0]], by[key[1]]
    out = {}
    for ch in HARD_CHANNELS:
        for d in ('ab', 'ba'):
            st = hard_state(a, b, ch, d)
            for s in HARD_STATES:
                out['hc_%s_%s_%s' % (ch, d, s)] = int(st == s)
    for k in SOFT_CHANNELS:
        fa, fb = a['fields'].get(k), b['fields'].get(k)
        sa, sb = a['field_status'].get(k), b['field_status'].get(k)
        if sa == 'declined' or sb == 'declined':
            st = 'declined'
        elif fa is None or fb is None:
            st = 'unknown'
        elif fa == fb:
            st = 'match'
        else:
            st = 'mismatch'
        for s in SOFT_STATES:
            out['sc_%s_%s' % (k, s)] = int(st == s)
    out.update(
        age_a=float(a['age']), age_b=float(b['age']),
        gender_a=stable_bucket(a['gender'], GENDER_BUCKETS),
        gender_b=stable_bucket(b['gender'], GENDER_BUCKETS),
        zone_a=stable_bucket(a['zone'], ZONE_BUCKETS),
        zone_b=stable_bucket(b['zone'], ZONE_BUCKETS),
        days_since_arrival_a=float(state['day'] - a['arrived_day']),
        days_since_arrival_b=float(state['day'] - b['arrived_day']),
        n_hard_observed_a=sum(a['fields'].get(k) is not None for k in c.kit.HARD),
        n_hard_observed_b=sum(b['fields'].get(k) is not None for k in c.kit.HARD),
        n_soft_observed_a=sum(a['fields'].get(k) is not None for k in c.kit.SOFT),
        n_soft_observed_b=sum(b['fields'].get(k) is not None for k in c.kit.SOFT),
        has_profile_gap=int(
            any(a['fields'].get(k) is None or b['fields'].get(k) is None
                for k in c.kit.SOFT)))
    return out


def assert_legal_features(cols):
    bad = [k for k in cols
           if k in BANNED_FEATURE_EXACT or k.startswith('cf_')
           or k.startswith('y_') or k in ('seed', 'variant')]
    if bad:
        raise SystemExit('ILLEGAL FEATURE COLUMNS: %r' % bad)
    for name, spec in FEATURE_SETS.items():
        missing = [k for k in spec if k not in cols]
        if missing:
            raise SystemExit('feature set %s missing %r' % (name, missing[:5]))
    return True


STATE_SIDE_KEY = ('seed', 'variant', 'day', 'user_a', 'user_b')


def load_state_side():
    return {tuple(r[k] for k in STATE_SIDE_KEY): r
            for r in c.read_jsonl(c.OUT / 'pair_state.jsonl')}


def derived_features_from_row(r, side):
    s = side[tuple(r[k] for k in STATE_SIDE_KEY)]
    state = dict(day=s['day'],
                 ask_budget_remaining=s['ask_budget_remaining'],
                 members=[s['a'], s['b']])
    return derived_features(state, (r['user_a'], r['user_b']))


def load_frame():
    side = load_state_side()
    X_parts, y, groups, states, sels, seeds, variants, days = \
        [], [], [], [], [], [], [], []
    with open(c.OUT / 'counterfactual_pairs.jsonl', encoding='utf-8') as fh:
        for line in fh:
            r = json.loads(line)
            feat = dict(r['feat'])
            feat.update(derived_features_from_row(r, side))
            X_parts.append(feat)
            y.append(int(r['cf_y_msmi']))
            groups.append(r['seed'])
            states.append((r['seed'], r['variant'], r['day']))
            sels.append(r['selected'])
            seeds.append(r['seed'])
            variants.append(r['variant'])
            days.append(r['day'])
    assert_legal_features(sorted(X_parts[0]))
    return dict(feat=X_parts, y=np.array(y), groups=np.array(groups),
                states=states, selected=np.array(sels),
                seeds=seeds, variants=variants, days=days)


def oof_scores(X, y, groups):
    oof = np.zeros(len(y))
    gkf = GroupKFold(n_splits=N_SPLITS)   # groups = seed; variants stay together
    for tr, te in gkf.split(X, y, groups):
        clf = HistGradientBoostingClassifier(**MODEL_KW)
        clf.fit(X[tr], y[tr])
        oof[te] = clf.predict_proba(X[te])[:, 1]
    return oof


def bootstrap_seed_groups(stat_fn, seeds, n_boot=1000, rng_seed=4242):
    """95% percentile CI resampling whole seed-groups, never rows."""
    rng = np.random.default_rng(rng_seed)
    uniq = sorted(set(seeds))
    idx_of = {s: np.where(np.array(seeds) == s)[0] for s in uniq}
    stats = []
    for _ in range(n_boot):
        pick = rng.choice(len(uniq), size=len(uniq), replace=True)
        idx = np.concatenate([idx_of[uniq[i]] for i in pick])
        v = stat_fn(idx)
        if v is not None and np.isfinite(v):
            stats.append(v)
    if not stats:
        return (float('nan'), float('nan'))
    return (float(np.percentile(stats, 2.5)), float(np.percentile(stats, 97.5)))


def world_within_state_means(scores, y, states, seeds):
    per, wm = defaultdict(list), defaultdict(list)
    for s, yy, k, w in zip(scores, y, states, seeds):
        per[(w, k)].append((s, yy))
    for (w, _k), v in per.items():
        ys = np.array([q[1] for q in v])
        ss = np.array([q[0] for q in v])
        if ys.sum() == 0 or ys.sum() == len(ys):
            continue
        wm[w].append(float(roc_auc_score(ys, ss)))
    return {w: float(np.mean(v)) for w, v in wm.items() if v}


def heterogeneity_permutation(scores, y, states, seeds, n_perm=200,
                              rng_seed=4242):
    """Observed spread of per-seed within-state AUC vs a within-world null.

    A row-level test would be pseudo-replication; labels are shuffled only
    inside each seed-group so per-world class counts are preserved.
    """
    obs = world_within_state_means(scores, y, states, seeds)
    obs_spread = (float(np.std(list(obs.values()))) if len(obs) > 1
                  else float('nan'))
    rng = np.random.default_rng(rng_seed)
    null, y_arr = [], np.asarray(y)
    seeds_arr = np.asarray(seeds)
    for _ in range(n_perm):
        yp = y_arr.copy()
        for w in set(seeds):
            idx = np.where(seeds_arr == w)[0]
            yp[idx] = rng.permutation(yp[idx])
        m = world_within_state_means(scores, yp, states, seeds)
        if len(m) > 1:
            null.append(float(np.std(list(m.values()))))
    p = ((sum(1 for v in null if v >= obs_spread) + 1) / (len(null) + 1)
         if null else float('nan'))
    return dict(observed_spread=obs_spread, n_worlds=len(obs),
                null_mean=(float(np.mean(null)) if null else float('nan')),
                null_p_ge_observed=p, n_permutations=len(null))


def within_state_auc(scores, y, states):
    by = defaultdict(list)
    for s, yy, k in zip(scores, y, states):
        by[k].append((s, yy))
    per_state, pos_w = {}, {}
    for k, v in by.items():
        ys = np.array([p[1] for p in v])
        ss = np.array([p[0] for p in v])
        npos = int(ys.sum())
        if npos == 0 or npos == len(ys):
            continue
        per_state[k] = float(roc_auc_score(ys, ss))
        pos_w[k] = npos
    if not per_state:
        return dict(mean=float('nan'), posweighted=float('nan'),
                    n_states=0, n_states_pos=0, top1_hit=float('nan'))
    vals = np.array(list(per_state.values()))
    wts = np.array([pos_w[k] for k in per_state], dtype=float)
    hits = 0
    for k in per_state:
        v = by[k]
        ys = np.array([p[1] for p in v])
        ss = np.array([p[0] for p in v])
        hits += int(ss[ys.argmax()] == ss.max() and ys[ss.argmax()] == 1)
    return dict(mean=float(vals.mean()),
                posweighted=float((vals * wts).sum() / wts.sum()),
                n_states=len(per_state), n_states_pos=len(per_state),
                top1_hit=hits / len(per_state))


def metric_strata(fr):
    y = fr['y']
    out = [('overall', 'all', np.ones(len(y), dtype=bool))]
    for v in sorted(set(fr['variants'])):
        out.append(('variant', v, np.array([x == v for x in fr['variants']])))
    for s in sorted(set(fr['seeds'])):
        out.append(('world', str(s), np.array([x == s for x in fr['seeds']])))

    def band(d):
        return ('0-9' if d <= 9 else '10-19' if d <= 19
                else '20-39' if d <= 39 else '40-59')
    for b in ('0-9', '10-19', '20-39', '40-59'):
        out.append(('day_band', b, np.array([band(d) == b for d in fr['days']])))
    return out


def main():
    c.log('task5 start: section 5 signal analysis')
    fr = load_frame()
    n_pos = int(fr['y'].sum())
    power = 'ok' if (n_pos >= 100 and
                     len({s for s, yy in zip(fr['seeds'], fr['y']) if yy}) >= 5) \
        else 'underpowered'
    c.log('frame rows=%d positives=%d seeds=%d power=%s'
          % (len(fr['y']), n_pos, len(set(fr['seeds'])), power))
    rows = []
    oof_by_set = {}
    for name, cols in FEATURE_SETS.items():
        X = np.array([[f.get(k, 0.0) for k in cols] for f in fr['feat']],
                     dtype=np.float32)
        oof = oof_scores(X, fr['y'], fr['groups'])
        oof_by_set[name] = oof
        auc = float(roc_auc_score(fr['y'], oof))
        ap = float(average_precision_score(fr['y'], oof))
        prev = float(fr['y'].mean())
        ws = within_state_auc(oof, fr['y'], fr['states'])

        def _auc(idx, _o=oof, _y=fr['y']):
            if len(set(_y[idx])) < 2:
                return None
            return float(roc_auc_score(_y[idx], _o[idx]))
        lo, hi = bootstrap_seed_groups(_auc, fr['seeds'])

        for stype, sval, mask in metric_strata(fr):
            yy, ss = fr['y'][mask], oof[mask]
            if len(set(yy)) < 2:
                auc_s = float('nan'); ap_s = float('nan')
            else:
                auc_s = float(roc_auc_score(yy, ss))
                ap_s = float(average_precision_score(yy, ss))
            prev_s = float(yy.mean())
            ws_s = within_state_auc(ss, yy,
                                    [fr['states'][i] for i in np.where(mask)[0]])
            rows.append(dict(
                feature_set=name, stratum_type=stype, stratum_value=sval,
                n_rows=int(mask.sum()), n_positives=int(yy.sum()),
                prevalence=round(prev_s, 6),
                auc=round(auc_s, 6), pr_auc=round(ap_s, 6),
                lift=round(ap_s / prev_s, 6) if prev_s > 0 else '',
                within_state_auc_mean=round(ws_s['mean'], 6),
                within_state_auc_posweighted=round(ws_s['posweighted'], 6),
                n_states=ws_s['n_states'], n_states_pos=ws_s['n_states_pos'],
                top1_hit_rate=round(ws_s['top1_hit'], 6),
                ci95_low=round(lo, 6), ci95_high=round(hi, 6),
                power_flag=power if stype == 'overall' else ''))
        c.log('%s AUC=%.4f AP=%.4f within_state=%.4f states=%d'
              % (name, auc, ap, ws['mean'], ws['n_states']))

    ablations = [('F2_minus_F1', 'F2_soft_state', 'F1_baseline_count_score'),
                 ('F3_minus_F1', 'F3_public_profile', 'F1_baseline_count_score'),
                 ('F4_minus_F3', 'F4_full_legal_observables', 'F3_public_profile')]
    ab_rows = []
    for label, hi_s, lo_s in ablations:
        def _d(idx, _h=hi_s, _l=lo_s, _y=fr['y'], _o=oof_by_set):
            if len(set(_y[idx])) < 2:
                return None
            return float(roc_auc_score(_y[idx], _o[_h][idx]) -
                         roc_auc_score(_y[idx], _o[_l][idx]))
        lo, hi_ci = bootstrap_seed_groups(_d, fr['seeds'])
        point = float(roc_auc_score(fr['y'], oof_by_set[hi_s]) -
                      roc_auc_score(fr['y'], oof_by_set[lo_s]))
        ab_rows.append(dict(contrast=label, delta_auc=round(point, 6),
                            ci95_low=round(lo, 6), ci95_high=round(hi_ci, 6),
                            excludes_zero=int(lo > 0 or hi_ci < 0)))
        c.log('ablation %s delta=%.4f ci=[%.4f, %.4f]'
              % (label, point, lo, hi_ci))

    sel = fr['selected'].astype(bool)
    d_rows = []
    for name in ('F1_baseline_count_score', 'F4_full_legal_observables'):
        oof = oof_by_set[name]
        all_auc = (float(roc_auc_score(fr['y'], oof))
                   if len(set(fr['y'])) > 1 else float('nan'))
        if sel.sum() and len(set(fr['y'][sel])) > 1:
            sel_auc = float(roc_auc_score(fr['y'][sel], oof[sel]))
        else:
            sel_auc = float('nan')
        diff = float(oof[sel].mean() - oof[~sel].mean())
        lo, hi_ci = bootstrap_seed_groups(
            lambda idx, _o=oof, _m=sel: float(
                _o[idx][_m[idx]].mean() - _o[idx][~_m[idx]].mean())
            if _m[idx].any() and (~_m[idx]).any() else None, fr['seeds'])
        d_rows.append(dict(feature_set=name, auc_all=round(all_auc, 6),
                           auc_selected_only=round(sel_auc, 6),
                           score_gap_selected_minus_not=round(diff, 6),
                           gap_ci95_low=round(lo, 6),
                           gap_ci95_high=round(hi_ci, 6)))
    with open(c.OUT / 'selection_effect.csv', 'w', newline='',
              encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=list(d_rows[0]))
        w.writeheader()
        w.writerows(d_rows)
    c.log('wrote selection_effect.csv')

    het = heterogeneity_permutation(
        oof_by_set['F4_full_legal_observables'], fr['y'], fr['states'],
        fr['seeds'], n_perm=200, rng_seed=4242)
    (c.OUT / 'heterogeneity.json').write_text(
        json.dumps(het, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    c.log('heterogeneity ' + json.dumps(het, sort_keys=True))

    with open(c.OUT / 'within_state_signal.csv', 'w', newline='',
              encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    with open(c.OUT / 'ablation_deltas.csv', 'w', newline='',
              encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=list(ab_rows[0]))
        w.writeheader()
        w.writerows(ab_rows)
    # persist OOF scores for section 5 question E (decision relevance)
    with open(c.OUT / 'oof_scores.jsonl', 'w', encoding='utf-8') as fh:
        for i in range(len(fr['y'])):
            rec = dict(seed=fr['seeds'][i], variant=fr['variants'][i],
                       day=fr['days'][i],
                       user_a=fr['feat'][i]['user_a'],
                       user_b=fr['feat'][i]['user_b'],
                       selected=int(fr['selected'][i]), y=int(fr['y'][i]))
            for name in FEATURE_SETS:
                rec[name] = float(oof_by_set[name][i])
            fh.write(json.dumps(rec, sort_keys=True) + '\n')
    c.log('wrote oof_scores.jsonl (%d rows)' % len(fr['y']))

    c.log('wrote within_state_signal.csv (%d rows), ablation_deltas.csv (%d)'
          % (len(rows), len(ab_rows)))
    c.log('task5 done')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
