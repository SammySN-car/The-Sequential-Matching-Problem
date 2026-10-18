"""Group C: wait / temporal methods (m16-m23). Ask phase = baseline_asks: waiting is
the isolated mechanism, asking stays control-parity."""
from kit import baseline_asks
import common
import alloc


def _ask_or(state, request, pairs_fn):
    memory = request.get('memory')
    if request['phase'] == 'ask':
        return {'asks': baseline_asks(state), 'memory': memory}
    return {'pairs': pairs_fn(), 'memory': memory}


def decide_m16(request):
    state = request['state']

    def go():
        kept = alloc.filter_min_score(common.feasible_edges(state),
                                      common.PATIENT_MIN_SCORE)
        return alloc.greedy_take(kept)
    return _ask_or(state, request, go)


def decide_m17(request):
    state = request['state']

    def go():
        return alloc.quota_half(alloc.greedy_take(common.feasible_edges(state)))
    return _ask_or(state, request, go)


def decide_m18(request):
    state = request['state']

    def go():
        req = max(1, common.TIME_T0 - state['day'] // common.TIME_STEP)
        return alloc.greedy_take(alloc.filter_min_score(common.feasible_edges(state), req))
    return _ask_or(state, request, go)


def decide_m19(request):
    state = request['state']

    def go():
        ctx = common.make_ctx(state)
        day, mfs = ctx['day'], ctx['members']

        def key_fn(e):
            wait_pair = max(common.wait_days(mfs[e[0]], day),
                            common.wait_days(mfs[e[1]], day))
            return (-wait_pair, -e[2], common.pair_key(e[0], e[1]))
        return alloc.take_ordered(ctx['edges'], key_fn)
    return _ask_or(state, request, go)


def decide_m20(request):
    state = request['state']

    def go():
        ctx = common.make_ctx(state)
        return alloc.greedy_take(alloc.protect_filter(ctx['edges'], ctx))
    return _ask_or(state, request, go)


def decide_m21(request):
    state = request['state']

    def go():
        ctx = common.make_ctx(state)
        day, mfs = ctx['day'], ctx['members']
        kept = []
        for a, b, s in ctx['edges']:
            need = max(0, common.DELAY_T0
                       - max(common.wait_days(mfs[a], day),
                             common.wait_days(mfs[b], day)) // common.DELAY_STEP)
            if s >= need:
                kept.append((a, b, s))
        return alloc.greedy_take(kept)
    return _ask_or(state, request, go)


def decide_m22(request):
    state = request['state']

    def go():
        ctx = common.make_ctx(state)
        if alloc.thin_wait(ctx):
            return []
        return alloc.greedy_take(ctx['edges'])
    return _ask_or(state, request, go)


def decide_m23(request):
    state = request['state']

    def go():
        ctx = common.make_ctx(state)
        if not alloc.hybrid_favorable(ctx):
            return []
        return alloc.greedy_take(ctx['edges'])
    return _ask_or(state, request, go)


DECISIONS = {
    'm16_patient_policy': decide_m16,
    'm17_daily_quota': decide_m17,
    'm18_time_threshold': decide_m18,
    'm19_arrival_age': decide_m19,
    'm20_new_arrival_protection': decide_m20,
    'm21_delay_cost_threshold': decide_m21,
    'm22_market_thickness': decide_m22,
    'm23_hybrid_patient_greedy': decide_m23,
}
