"""Shared scorer/allocation/VoI-gate library for the E1/E2/E3 experiment.

RESEARCH ONLY. Decision-time inputs policy state + memory only.
Public DATA_CONTRACT usage: kit.OPTIONS, kit.SOFT, kit.eligibility,
kit.baseline_asks, kit.baseline_match. Never reads hidden simulator state.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import kit
from kit import baseline_asks, baseline_match, eligibility

REL = ('relationship_goal', 'relationship_pace', 'lifestyle', 'conversations')
W = {'relationship_goal': .7, 'relationship_pace': .4,
     'lifestyle': .25, 'conversations': .2}
PRIOR_EQ = {k: 1.0 / len(v) for k, v in kit.OPTIONS.items()}
STAGE2_W = 0.02


def s_count(fa, fb):
    """Incumbent score: count of observed-equal SOFT fields (kit.py:217)."""
    return sum(1 for k in kit.SOFT
               if fa.get(k) is not None and fa.get(k) == fb.get(k))


def s_analytic(fa, fb):
    """Analytic expected-fit score on observed fields; missing -> uniform prior."""
    total = 0.0
    for k, w in W.items():
        va, vb = fa.get(k), fb.get(k)
        if va is None or vb is None:
            total += w * (1.5 * PRIOR_EQ[k] - 0.5)
        else:
            total += w * (1.0 if va == vb else -0.5)
    ga, gb = fa.get('relationship_goal'), fb.get('relationship_goal')
    goal_eq = PRIOR_EQ['relationship_goal'] if (ga is None or gb is None) else float(ga == gb)
    return total + STAGE2_W * (1.5 * goal_eq - 0.5)


def fields_by_id(state):
    return {m['member_id']: m['fields'] for m in state['members']}


def candidate_edges(state):
    """Canonical (a, b), a < b: available members, feasible, not previously introduced."""
    members = sorted((m for m in state['members'] if m['available']),
                     key=lambda m: m['member_id'])
    past = {tuple(sorted((i['user_a'], i['user_b'])))
            for i in (state.get('introductions') or [])}
    edges = []
    for i, a in enumerate(members):
        for b in members[i + 1:]:
            ka = (a['member_id'], b['member_id'])   # sorted: members sorted by id
            if ka in past:
                continue
            if eligibility(a, b)['status'] != 'feasible':
                continue
            edges.append(ka)
    return edges


def take_free_alloc(edges, score_pair):
    """kit take-while-free allocation (kit.py:219-221) over explicit scores."""
    ranked = sorted(((-score_pair(a, b), a, b) for a, b in edges))
    used, out = set(), []
    for _, a, b in ranked:
        if a in used or b in used:
            continue
        out.append((a, b))
        used.add(a)
        used.add(b)
    return out


def alloc_count(state):
    """E1/test allocation: identical algorithm + score to kit.baseline_match."""
    fields = fields_by_id(state)
    return take_free_alloc(candidate_edges(state),
                           lambda a, b: s_count(fields[a], fields[b]))


def alloc_analytic(state):
    """E2/E3 allocation: kit's take-while-free algorithm, analytic scores."""
    fields = fields_by_id(state)
    return take_free_alloc(candidate_edges(state),
                           lambda a, b: s_analytic(fields[a], fields[b]))


def match_response(state, kind):
    """Match-phase output in evaluate protocol shape."""
    alloc = alloc_count(state) if kind == 'count' else alloc_analytic(state)
    return [list(p) for p in alloc]


def voi_rel_asks(state, score_kind, order_key, collect_stats=None):
    """Enumeration-based decision-change gate over the public answer space.

    score_kind: 'count' (E1) or 'analytic' (E3).
    order_key:   deterministic candidate order; E1 uses (member_id, field),
                 E3 uses (-W[field], member_id, field).
    Returns the full ask list (hard asks first, then REL asks that pass the
    gate). Truth-blind: enumerates kit.OPTIONS[field] only.
    """
    asks = baseline_asks(state)
    spent = 3 * len(asks)
    budget = int(state.get('ask_budget_remaining') or 0) - spent
    stats = {'hard_asks': len(asks), 'candidates': 0, 'tested_answers': 0,
             'passed': 0, 'budget_left': budget}
    if collect_stats is not None:
        collect_stats.append(stats)
    if budget <= 0:
        return asks

    fields = fields_by_id(state)
    edges = candidate_edges(state)
    if not edges:
        return asks
    scorer = s_count if score_kind == 'count' else s_analytic
    base_scores = {e: scorer(fields[e[0]], fields[e[1]]) for e in edges}
    base_alloc = take_free_alloc(
        edges, lambda a, b: base_scores[(a, b)])
    nodes_in_edges = set()
    for e in edges:
        nodes_in_edges.add(e[0])
        nodes_in_edges.add(e[1])

    cands = []
    for m in state['members']:
        if not m['available']:
            continue
        mid = m['member_id']
        if mid not in nodes_in_edges:
            continue
        for k in REL:
            if m['field_status'].get(k) == 'not_asked':
                cands.append((mid, k))
    cands.sort(key=order_key)
    stats['candidates'] = len(cands)

    for mid, k in cands:
        if spent + 1 > budget:
            break
        incident = [e for e in edges if mid in e]
        flip = False
        for v in kit.OPTIONS[k]:                     # legal public answer space
            stats['tested_answers'] += 1
            fm = dict(fields[mid])
            fm[k] = v
            modified = {}
            for e in incident:
                a, b = e
                fa = fm if a == mid else fields[a]
                fb = fm if b == mid else fields[b]
                modified[e] = scorer(fa, fb)

            def hyp(a, b, _mod=modified):
                return _mod[(a, b)] if (a, b) in _mod else base_scores[(a, b)]
            if take_free_alloc(edges, hyp) != base_alloc:
                flip = True
                break
        if flip:
            asks.append({'member_id': mid, 'field': k})
            spent += 1
            stats['passed'] += 1
    return asks
