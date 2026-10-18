"""Group E: active asking (m29-m30). The ask phase selects soft fields within the
daily budget (hard asks first, capped to keep SOFT_ASK_RESERVE units for soft);
the match phase is control-parity baseline_match, so ask selection is the isolated
mechanism. Truth-blind: only kit.OPTIONS enumerations, never hidden state."""
from kit import baseline_asks, baseline_match, OPTIONS, SOFT
import common
import alloc


def _hard_asks_capped(state):
    """Control's hard-constraint asks, truncated so soft budget units remain."""
    cap = max(0, state['ask_budget_remaining'] - common.SOFT_ASK_RESERVE) // 3
    return baseline_asks(state)[:cap]


def _soft_candidates(state):
    """(member, field) eligible for a soft ask, sorted by (member_id, field)."""
    out = []
    for m in sorted(state['members'], key=lambda x: x['member_id']):
        if m['available']:
            for k in sorted(SOFT):
                if m['field_status'].get(k) == 'not_asked':
                    out.append((m, k))
    return out


def _alloc_key(pairs):
    return {common.pair_key(p[0], p[1]) for p in pairs}


def decide_m29(request):
    state = request['state']
    memory = request.get('memory')
    if request['phase'] == 'ask':
        budget = state['ask_budget_remaining']
        asks = _hard_asks_capped(state)
        spent = 3 * len(asks)
        ctx = common.make_ctx(state)
        mfs = {m['member_id']: m for m in state['members']}
        ranked = []
        for m, k in _soft_candidates(state):
            mid = m['member_id']
            value = sum(1 for _s, nb in ctx['inc'].get(mid, ())
                        if mfs[nb]['fields'].get(k) is not None)
            if value > 0:   # only immediately resolvable comparisons
                ranked.append((-value, mid, k))
        ranked.sort()
        for neg_value, mid, k in ranked:
            if spent + 1 > budget:
                break
            asks.append({'member_id': mid, 'field': k})
            spent += 1
        return {'asks': asks, 'memory': memory}
    return {'pairs': baseline_match(state), 'memory': memory}


def decide_m30(request):
    state = request['state']
    memory = request.get('memory')
    if request['phase'] == 'ask':
        budget = state['ask_budget_remaining']
        asks = _hard_asks_capped(state)
        spent = 3 * len(asks)
        edges = common.feasible_edges(state)
        mfs = {m['member_id']: m for m in state['members']}
        ctx = common.make_ctx(state, edges)
        base_alloc = _alloc_key(alloc.greedy_take(edges))
        recomputations = 1   # VOI_EVAL_CAP greedy passes (design section 6 table)
        edge_idx = {}
        for i, (a, b, _s) in enumerate(edges):
            edge_idx.setdefault(a, []).append(i)
            edge_idx.setdefault(b, []).append(i)
        for m, k in _soft_candidates(state):
            if recomputations >= common.VOI_EVAL_CAP:
                break   # preregistered cap in fixed (member, field) order
            if spent + 1 > budget:
                break
            mid = m['member_id']
            # Exact skip: if no feasible partner has observed k, no option can
            # change any incident score, so the allocation is provably unchanged.
            if not any(mfs[nb]['fields'].get(k) is not None
                       for _s, nb in ctx['inc'].get(mid, ())):
                continue
            touched = edge_idx.get(mid, [])
            orig_scores = [edges[i][2] for i in touched]
            original = m['fields'].get(k)
            changed = False
            try:
                for opt in OPTIONS[k]:   # truth-blind enumeration
                    if recomputations >= common.VOI_EVAL_CAP:
                        break
                    recomputations += 1
                    m['fields'][k] = opt
                    for i in touched:
                        a, b, _s = edges[i]
                        edges[i] = (a, b, common.base_score(mfs[a], mfs[b]))
                    if _alloc_key(alloc.greedy_take(edges)) != base_alloc:
                        changed = True
                        break
            finally:
                m['fields'][k] = original
                for i, sc in zip(touched, orig_scores):
                    a, b, _s = edges[i]
                    edges[i] = (a, b, sc)
            if changed:
                asks.append({'member_id': mid, 'field': k})
                spent += 1
        return {'asks': asks, 'memory': memory}
    return {'pairs': baseline_match(state), 'memory': memory}


DECISIONS = {
    'm29_uncertainty_aware': decide_m29,
    'm30_targeted_info': decide_m30,
}
