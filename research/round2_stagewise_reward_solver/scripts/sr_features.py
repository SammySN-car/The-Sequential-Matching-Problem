"""Stage-wise reward pair-feature extractor (analysis_plan.md S.6, Task 1).

Consumes only kit.Simulator.observe() dicts: state['members'/'day'/'introductions'/
'feedback']. The 17 features follow the predeclared S.6 table order exactly;
rows 16-17 are STRUCTURE-INFORMED (feasible-graph degree), the rest LEGAL
OBSERVABLE. Rejected sources (truth/bias/second_bias/response_rate/exit_day/
seed/variant) are never read. Standard library plus kit constants only.
"""
import itertools

import kit

# kit.py L9-13: HARD and SOFT field name lists.
HARD = kit.HARD
SOFT = kit.SOFT

# HARD keys needed by features 2-6. On a feasible pair eligibility (kit.py L76/L87)
# guarantees every HARD field of both members is observed, so any None here means
# the caller passed a non-feasible pair.
_FEATURE_HARD = ('age_min', 'age_max', 'who_to_meet', 'acceptable_zones', 'schedule')

# S.6 table rows: (name, source expression, class), in fixed feature order.
_AUDIT_TABLE = (
    ('age_diff', 'abs(a.age - b.age)', 'LEGAL OBSERVABLE'),
    ('age_slack', 'min over both directions of min(partner.age - age_min, age_max - partner.age), from observed fields', 'LEGAL OBSERVABLE'),
    ('gender_fit_ab', "1 if b.gender in a.fields['who_to_meet']", 'LEGAL OBSERVABLE'),
    ('gender_fit_ba', "1 if a.gender in b.fields['who_to_meet']", 'LEGAL OBSERVABLE'),
    ('zone_common', 'len(set(a.acceptable_zones) & set(b.acceptable_zones))', 'LEGAL OBSERVABLE'),
    ('schedule_overlap', 'len(set(a.schedule) & set(b.schedule))', 'LEGAL OBSERVABLE'),
    ('arrival_diff', 'abs(a.arrived_day - b.arrived_day)', 'LEGAL OBSERVABLE'),
    ('soft_equal', 'count of SOFT fields both observed and equal (greedy\'s own score)', 'LEGAL OBSERVABLE'),
    ('soft_differ', 'count of SOFT fields both observed and unequal', 'LEGAL OBSERVABLE'),
    ('soft_missing', 'count of SOFT fields unobserved for either member', 'LEGAL OBSERVABLE'),
    ('soft_declined', "count of SOFT fields with field_status=='declined' for either member", 'LEGAL OBSERVABLE'),
    ('goal_agree', '1 if both relationship_goal observed and equal, else 0', 'LEGAL OBSERVABLE'),
    ('prev_intros_mean', "mean over the two members of past introduction counts (state['introductions'])", 'LEGAL OBSERVABLE'),
    ('hist_yes', "count of feedback events (state['feedback'], observed_day <= day) with positive value involving a or b: response 'yes' / date True / second 'yes'", 'LEGAL OBSERVABLE'),
    ('current_day', "state['day']", 'LEGAL OBSERVABLE'),
    ('degree_a', 'number of feasible candidate partners member a has in the current state graph', 'STRUCTURE-INFORMED'),
    ('degree_b', 'same for member b', 'STRUCTURE-INFORMED'),
)


def build_feasible_edges(state):
    """Canonical sorted-id feasible pairs among available members, excluding past
    pairs (mirrors kit.baseline_match L213-216), plus per-member feasible degree
    (0 for members with no feasible edge, including unavailable members)."""
    members = [m for m in state['members'] if m['available']]
    past = {tuple(sorted((i['user_a'], i['user_b']))) for i in state['introductions']}
    degree = {m['member_id']: 0 for m in state['members']}
    edges = []
    for a, b in itertools.combinations(members, 2):
        key = tuple(sorted((a['member_id'], b['member_id'])))
        if key in past or kit.eligibility(a, b)['status'] != 'feasible':
            continue
        edges.append(key)
        degree[key[0]] += 1
        degree[key[1]] += 1
    return edges, degree


def extract_pair_features(state, degree, a, b):
    """The 17 S.6 features for pair (a, b) in the predeclared table order."""
    day = state['day']
    for event in state['feedback']:
        assert event['observed_day'] <= day, 'feedback observed_day beyond decision day'
    members = {m['member_id']: m for m in state['members']}
    assert a in members and b in members, 'pair member not visible in state'
    ma, mb = members[a], members[b]
    fa, fb = ma['fields'], mb['fields']
    for fields in (fa, fb):
        for key in _FEATURE_HARD:
            assert fields.get(key) is not None, 'hard field missing on non-feasible pair'

    age_slack = min(min(mb['age'] - fa['age_min'], fa['age_max'] - mb['age']),
                    min(ma['age'] - fb['age_min'], fb['age_max'] - ma['age']))

    soft_equal = soft_differ = soft_missing = 0
    for key in SOFT:
        va, vb = fa.get(key), fb.get(key)
        if va is None or vb is None:
            soft_missing += 1
        elif va == vb:
            soft_equal += 1
        else:
            soft_differ += 1
    soft_declined = sum(1 for key in SOFT
                        if ma['field_status'].get(key) == 'declined'
                        or mb['field_status'].get(key) == 'declined')
    goal_agree = 1.0 if (fa.get('relationship_goal') is not None
                         and fa.get('relationship_goal') == fb.get('relationship_goal')) else 0.0

    intros_a = sum(1 for i in state['introductions'] if a in (i['user_a'], i['user_b']))
    intros_b = sum(1 for i in state['introductions'] if b in (i['user_a'], i['user_b']))

    intro_pairs = {i['introduction_id']: (i['user_a'], i['user_b'])
                   for i in state['introductions']}
    hist_yes = 0
    for event in state['feedback']:
        if event['event'] in ('introduction_response', 'second_meeting_intention'):
            if event['value'] == 'yes' and event['member_id'] in (a, b):
                hist_yes += 1
        elif event['event'] == 'date_happened' and event['value'] is True:
            pair = intro_pairs.get(event['introduction_id'])
            if pair is not None and (a in pair or b in pair):
                hist_yes += 1

    return [
        float(abs(ma['age'] - mb['age'])),                              # 1 age_diff
        float(age_slack),                                               # 2 age_slack
        1.0 if mb['gender'] in fa['who_to_meet'] else 0.0,              # 3 gender_fit_ab
        1.0 if ma['gender'] in fb['who_to_meet'] else 0.0,              # 4 gender_fit_ba
        float(len(set(fa['acceptable_zones']) & set(fb['acceptable_zones']))),  # 5 zone_common
        float(len(set(fa['schedule']) & set(fb['schedule']))),          # 6 schedule_overlap
        float(abs(ma['arrived_day'] - mb['arrived_day'])),              # 7 arrival_diff
        float(soft_equal),                                              # 8 soft_equal
        float(soft_differ),                                             # 9 soft_differ
        float(soft_missing),                                            # 10 soft_missing
        float(soft_declined),                                           # 11 soft_declined
        goal_agree,                                                     # 12 goal_agree
        (intros_a + intros_b) / 2.0,                                    # 13 prev_intros_mean
        float(hist_yes),                                                # 14 hist_yes
        float(day),                                                     # 15 current_day
        float(degree.get(a, 0)),                                        # 16 degree_a
        float(degree.get(b, 0)),                                        # 17 degree_b
    ]


def feature_audit_rows():
    """Machine-readable T-FEA-1 table: one row per feature, all LEGAL."""
    return [{'name': name, 'source': source, 'legality': 'LEGAL', 'class': cls}
            for name, source, cls in _AUDIT_TABLE]
