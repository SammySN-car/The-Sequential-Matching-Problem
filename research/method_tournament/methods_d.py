"""Group D: allocation / graph methods (m24-m28). Ask phase = baseline_asks."""
from kit import baseline_asks
import common
import alloc


def _ask_or(state, request, pairs_fn):
    memory = request.get('memory')
    if request['phase'] == 'ask':
        return {'asks': baseline_asks(state), 'memory': memory}
    return {'pairs': pairs_fn(), 'memory': memory}


def decide_m24(request):
    state = request['state']

    def go():
        edges = common.feasible_edges(state)
        got = alloc.max_cardinality(edges)
        if got is None:   # non-bipartite: documented approximation
            got = alloc.augment3_improve(alloc.greedy_take(edges), edges,
                                         common.AUGMENT_ROUNDS_CAP)
        return got
    return _ask_or(state, request, go)


def decide_m25(request):
    state = request['state']

    def go():
        edges = [e for e in common.feasible_edges(state) if e[2] > 0]  # exact for value
        colored = alloc.two_color(edges)
        if colored is not None and len(colored[0]) + len(colored[1]) <= common.HUNGARIAN_NODE_CAP:
            wmap = {}
            for a, b, s in edges:
                wmap[(a, b)] = s
                wmap[(b, a)] = s
            return [list(p) for p in alloc.hungarian_max_weight(colored[0], colored[1], wmap)]
        return alloc.one_swap_improve(alloc.greedy_take(edges), edges)  # documented fallback
    return _ask_or(state, request, go)


def decide_m26(request):
    state = request['state']

    def go():
        edges = common.feasible_edges(state)
        return alloc.one_swap_improve(alloc.greedy_take(edges), edges)
    return _ask_or(state, request, go)


def decide_m27(request):
    state = request['state']

    def go():
        edges = common.feasible_edges(state)
        return alloc.augment3_improve(alloc.greedy_take(edges), edges,
                                      common.AUGMENT_ROUNDS_CAP)
    return _ask_or(state, request, go)


def decide_m28(request):
    state = request['state']

    def go():
        edges = common.feasible_edges(state)
        pools = {}
        for a, b, s in edges:          # pool includes the candidate pair itself
            pools[a] = pools.get(a, 0) + s
            pools[b] = pools.get(b, 0) + s

        def key_fn(e):
            a, b, s = e
            return (-(3 * s - pools.get(a, 0) - pools.get(b, 0)),
                    common.pair_key(a, b))
        return alloc.take_ordered(edges, key_fn)
    return _ask_or(state, request, go)


DECISIONS = {
    'm24_max_cardinality': decide_m24,
    'm25_max_weight': decide_m25,
    'm26_greedy_one_swap': decide_m26,
    'm27_greedy_augmenting': decide_m27,
    'm28_conflict_aware': decide_m28,
}
