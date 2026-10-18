"""Decision-time pair features. Only what Simulator.observe() shows at day t.

Legality rules enforced here and audited in integrity.py:
- never read world['members'][*]['truth'|'bias'|'second_bias'|'response_rate'|'exit_day']
- never read world['seed'] / world['variant'] / raw sim.events / ask_log
- feedback counted only when observed_day <= t
- field values masked when field_observed_day > t (future observation)
- unknowns are NaN, never 0
- every feature is symmetric in (a, b): the label is symmetric, so scoring a pair
  must not depend on argument order.

STRUCTURE_INFORMED features are legal but disclosed: they reuse the published soft
weights from kit.Simulator._prob (development-only, not a real-world estimate).
"""
import kit

WEIGHTS = {'relationship_goal': .7, 'relationship_pace': .4,
           'lifestyle': .25, 'conversations': .2}
SOFT = list(kit.SOFT)
HARD = list(kit.HARD)

FORBIDDEN_TOKENS = ('truth', 'bias', 'second_bias', 'response_rate', 'exit_day',
                    'seed', 'variant', 'events', 'ask_log', 'member_id',
                    'introduction_id', 'pool_id', 'observed_day', 'future')
STRUCTURE_INFORMED = ('weighted_soft_score', 'weighted_soft_covered')

HIST_METRICS = ('n_intros', 'n_mutual', 'n_dates', 'yes_rate', 'n_missing')

PROFILE_KEYS = ('age_diff', 'age_mean', 'same_zone', 'same_gender', 'arrived_gap')
HARD_KEYS = ('hard_feasible', 'n_hard_missing', 'n_hard_reasons')
WHO_KEYS = ('who_meets_min', 'who_meets_max')
SOFT_MATCH_KEYS = tuple('soft_%s_match' % k for k in SOFT)
SOFT_OBS_KEYS = tuple('soft_%s_observed' % k for k in SOFT)
SOFT_AGG_KEYS = ('soft_match_count', 'soft_observed_pairs',
                 'weighted_soft_score', 'weighted_soft_covered')
TEMPORAL_KEYS = ('day', 'days_since_arrival_mean', 'days_since_arrival_absdiff',
                 'ask_budget')
HIST_KEYS = tuple('hist_%s_%s' % (m, agg) for m in HIST_METRICS for agg in ('mean', 'absdiff'))
COMP_KEYS = ('comp_available', 'comp_available_excl')

FEATURE_KEYS = list(PROFILE_KEYS + HARD_KEYS + WHO_KEYS + SOFT_MATCH_KEYS + SOFT_OBS_KEYS
                    + SOFT_AGG_KEYS + TEMPORAL_KEYS + HIST_KEYS + COMP_KEYS)
FEATURE_GROUPS = {
    'profile': list(PROFILE_KEYS),
    'hard': list(HARD_KEYS),
    'who_to_meet': list(WHO_KEYS),
    'soft': list(SOFT_MATCH_KEYS + SOFT_OBS_KEYS),
    'soft_aggregate': list(SOFT_AGG_KEYS),
    'temporal': list(TEMPORAL_KEYS),
    'history': list(HIST_KEYS),
    'competition': list(COMP_KEYS),
}

NAN = float('nan')


def audit_feature_keys(keys=None):
    """Names that would leak hidden information (empty list == clean)."""
    keys = FEATURE_KEYS if keys is None else keys
    return [k for k in keys if any(tok in k for tok in FORBIDDEN_TOKENS)]


def audit_structure_disclosure():
    """Structure-informed features must be declared (and only declared ones exist)."""
    out = []
    for k in STRUCTURE_INFORMED:
        if k not in FEATURE_KEYS:
            out.append(k + ':declared_but_absent')
    for k in FEATURE_KEYS:
        if k.startswith('weighted_') and k not in STRUCTURE_INFORMED:
            out.append(k + ':undeclared')
    return out


def smoothing(x, n):
    """Laplace-smoothed rate (x+1)/(n+2); never collapses to 0 or 1."""
    return (x + 1.0) / (n + 2.0)


def _visible(state, mid):
    for m in state['members']:
        if m['member_id'] == mid:
            return m
    raise ValueError('member not visible in state: ' + str(mid))


def _field(member, key, t):
    """Observed-at-t value of a field, else None (future observations masked)."""
    value = member['fields'].get(key)
    if value is None:
        return None
    observed = member['field_observed_day'].get(key)
    if observed is None or observed > t:
        return None
    return value


def _feedback_upto(state, t):
    return [e for e in state['feedback'] if e.get('observed_day') is not None
            and e['observed_day'] <= t]


def member_history(state, t, member_id):
    """Per-member statistics from feedback observed at or before t."""
    events = _feedback_upto(state, t)
    by_intro = {}
    for e in events:
        by_intro.setdefault(e['introduction_id'], []).append(e)
    members_of = {i['introduction_id']: (i['user_a'], i['user_b'])
                  for i in state['introductions'] if i['assigned_day'] <= t}
    out = dict(n_intros=0, n_mutual=0, n_dates=0, n_missing=0,
               n_responses=0, n_yes=0, n_second_yes=0)
    for iid, pair in members_of.items():
        if member_id not in pair:
            continue
        out['n_intros'] += 1
        evs = by_intro.get(iid, [])
        rs = [e for e in evs if e['event'] == 'introduction_response']
        if len(rs) == 2 and all(e['value'] == 'yes' for e in rs):
            out['n_mutual'] += 1
        if any(e['event'] == 'date_happened' and e['value'] is True for e in evs):
            out['n_dates'] += 1
    for e in events:
        if e.get('member_id') != member_id:
            continue
        if e['event'] == 'introduction_response':
            out['n_responses'] += 1
            out['n_yes'] += e['value'] == 'yes'
            out['n_missing'] += e.get('missing_reason') == 'no_response'
        elif e['event'] == 'second_meeting_intention':
            out['n_second_yes'] += e['value'] == 'yes'
    out['yes_rate'] = smoothing(out['n_yes'], out['n_responses'])
    return out


def pair_features(state, a_id, b_id, t):
    """Feature vector for pair (a_id, b_id) as known at day t. Symmetric in a/b."""
    a = _visible(state, a_id)
    b = _visible(state, b_id)
    f = {}

    f['age_diff'] = float(abs(a['age'] - b['age']))
    f['age_mean'] = float((a['age'] + b['age']) / 2.0)
    f['same_zone'] = float(a['zone'] == b['zone'])
    f['same_gender'] = float(a['gender'] == b['gender'])
    f['arrived_gap'] = float(abs(a['arrived_day'] - b['arrived_day']))

    elig = kit.eligibility(a, b)
    f['hard_feasible'] = float(elig['status'] == 'feasible')
    f['n_hard_missing'] = float(len(elig['missing']))
    f['n_hard_reasons'] = float(len(elig['reasons']))

    wa = _field(a, 'who_to_meet', t)
    wb = _field(b, 'who_to_meet', t)
    if wa is None or wb is None:
        f['who_meets_min'] = NAN
        f['who_meets_max'] = NAN
    else:
        flags = sorted((float(b['gender'] in wa), float(a['gender'] in wb)))
        f['who_meets_min'], f['who_meets_max'] = flags

    matches = 0
    observed_pairs = 0
    for key in SOFT:
        va = _field(a, key, t)
        vb = _field(b, key, t)
        seen = va is not None and vb is not None
        f['soft_%s_observed' % key] = float(seen)
        f['soft_%s_match' % key] = (float(va == vb) if seen else NAN)
        if seen:
            observed_pairs += 1
            matches += va == vb
    f['soft_match_count'] = float(matches)
    f['soft_observed_pairs'] = float(observed_pairs)

    weighted = 0.0
    covered = 0
    for key, w in WEIGHTS.items():
        va = _field(a, key, t)
        vb = _field(b, key, t)
        if va is not None and vb is not None:
            weighted += w * (1.0 if va == vb else -0.5)
            covered += 1
    f['weighted_soft_score'] = float(weighted)
    f['weighted_soft_covered'] = float(covered)

    since_a = float(t - a['arrived_day'])
    since_b = float(t - b['arrived_day'])
    f['day'] = float(t)
    f['days_since_arrival_mean'] = (since_a + since_b) / 2.0
    f['days_since_arrival_absdiff'] = abs(since_a - since_b)
    f['ask_budget'] = float(state['ask_budget_remaining'])

    ha = member_history(state, t, a_id)
    hb = member_history(state, t, b_id)
    for metric in HIST_METRICS:
        va, vb = float(ha[metric]), float(hb[metric])
        f['hist_%s_mean' % metric] = (va + vb) / 2.0
        f['hist_%s_absdiff' % metric] = abs(va - vb)

    available = sum(1 for m in state['members'] if m.get('available'))
    f['comp_available'] = float(available)
    f['comp_available_excl'] = float(max(0, available - 2))

    if set(f) != set(FEATURE_KEYS):
        raise AssertionError('feature set drift: %s' % sorted(set(f) ^ set(FEATURE_KEYS)))
    return {k: float(f[k]) for k in FEATURE_KEYS}
