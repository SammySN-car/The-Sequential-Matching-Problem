"""Shared visible-state helpers for tournament methods. Stdlib + kit only.

Constants are FROZEN per design.md section 6; FrozenConstantsTests pins their values.
All iteration here is sorted: no PYTHONHASHSEED is set, so order must never depend on
set/dict hashing.
"""
from kit import SOFT, OPTIONS, eligibility

# Frozen constants (design.md section 6) -------------------------------------
REL = ('relationship_goal', 'relationship_pace', 'lifestyle', 'conversations')
PROTECT_DAYS = 3
QUOTA_DIVISOR = 2
PATIENT_MIN_SCORE = 3
TIME_T0, TIME_STEP = 4, 20
DELAY_T0, DELAY_STEP = 4, 15
THIN_AVG_DEG = 2.0
HYBRID_MIN_SCORE = 4
HYBRID_AVG_DEG = 3.0
STRONG_SCORE = 3
PRUNE_MIN_SCORE = 2
HUNGARIAN_NODE_CAP = 180
AUGMENT_ROUNDS_CAP = 50
SOFT_ASK_RESERVE = 3
VOI_EVAL_CAP = 96


def pair_key(a, b):
    return tuple(sorted((a, b)))


def member_map(state):
    return {m['member_id']: m for m in state['members']}


def past_pairs(state):
    return {pair_key(i['user_a'], i['user_b']) for i in state['introductions']}


def base_score(a, b):
    """Observed soft-field agreement count (identical formula to kit.baseline_match)."""
    return sum(a['fields'].get(k) is not None and a['fields'].get(k) == b['fields'].get(k)
               for k in SOFT)


def wait_days(m, day):
    return day - m['arrived_day']


def feasible_edges(state, members=None):
    """[(id_a, id_b, base)] for available, feasible, never-introduced pairs.
    Same graph kit.baseline_match enumerates; sorted by member id for determinism."""
    ms = members if members is not None else [m for m in state['members'] if m['available']]
    ms = sorted(ms, key=lambda m: m['member_id'])
    past = past_pairs(state)
    out = []
    for i, a in enumerate(ms):
        for b in ms[i + 1:]:
            if pair_key(a['member_id'], b['member_id']) in past:
                continue
            if eligibility(a, b)['status'] != 'feasible':
                continue
            out.append((a['member_id'], b['member_id'], base_score(a, b)))
    return out


def directional(a, b):
    """d(a->b): sum over SOFT fields a observed; equal=1, unequal=0,
    missing on b credited the uniform prior 1/|OPTIONS[k]|. Asymmetric by design."""
    total = 0.0
    for k in SOFT:
        av = a['fields'].get(k)
        if av is None:
            continue
        bv = b['fields'].get(k)
        if bv is None:
            total += 1.0 / len(OPTIONS[k])
        elif av == bv:
            total += 1.0
    return total


def make_ctx(state, edges=None):
    """Per-day context shared by every method: edges, degrees, sorted incident lists."""
    if edges is None:
        edges = feasible_edges(state)
    mfs = member_map(state)
    deg = {}
    inc = {}
    for a, b, s in edges:
        deg[a] = deg.get(a, 0) + 1
        deg[b] = deg.get(b, 0) + 1
        inc.setdefault(a, []).append((s, b))
        inc.setdefault(b, []).append((s, a))
    for m in inc:
        inc[m].sort(key=lambda t: (-t[0], t[1]))
    n_avail = sum(1 for m in state['members'] if m['available'])
    return {'state': state, 'day': state['day'], 'members': mfs, 'edges': edges,
            'deg': deg, 'inc': inc, 'n_avail': n_avail,
            'avg_deg': (2.0 * len(edges) / n_avail) if n_avail else 0.0,
            'max_base': max((s for _, _, s in edges), default=0)}


def alt_for(ctx, m, other):
    """Best base score of m's other feasible partners today (0 when none)."""
    for s, o in ctx['inc'].get(m, ()):
        if o != other:
            return s
    return 0
