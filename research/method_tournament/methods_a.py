"""Group A: score-function methods (m01-m08). Ask phase = kit.baseline_asks (control parity)."""
from kit import baseline_asks, baseline_match, SOFT, OPTIONS
import common
import alloc


def decide_m01(request):
    state = request['state']
    memory = request.get('memory') or {}
    if request['phase'] == 'ask':
        return {'asks': baseline_asks(state), 'memory': memory}
    return {'pairs': baseline_match(state), 'memory': memory}


def _scored_match(score_fn):
    def decide(request):
        state = request['state']
        memory = request.get('memory')
        if request['phase'] == 'ask':
            return {'asks': baseline_asks(state), 'memory': memory}
        ctx = common.make_ctx(state)
        mfs = ctx['members']
        scored = [(a, b, score_fn(mfs[a], mfs[b], ctx)) for a, b, s in ctx['edges']]
        return {'pairs': alloc.greedy_take(scored), 'memory': memory}
    return decide


def score_m02(a, b, ctx):
    return common.directional(a, b) + common.directional(b, a)


def score_m03(a, b, ctx):
    return min(common.directional(a, b), common.directional(b, a))


def score_m04(a, b, ctx):
    return common.directional(a, b) * common.directional(b, a)


def score_m05(a, b, ctx):
    x, y = common.directional(a, b), common.directional(b, a)
    return 0.0 if x + y == 0 else 2.0 * x * y / (x + y)


def score_m06(a, b, ctx):
    """Bottleneck over the 4 REL fields: equal=1, unequal=0, missing=uniform prior."""
    worst = 1.0
    for k in common.REL:
        av, bv = a['fields'].get(k), b['fields'].get(k)
        if av is None or bv is None:
            val = 1.0 / len(OPTIONS[k])
        else:
            val = 1.0 if av == bv else 0.0
        if val < worst:
            worst = val
    return worst


_WEIGHT = {k: 1.0 - 1.0 / len(OPTIONS[k]) for k in SOFT}


def score_m08(a, b, ctx):
    """Structure-only weights from OPTIONS cardinalities; one side observed gets w*p prior."""
    total = 0.0
    for k in SOFT:
        av, bv = a['fields'].get(k), b['fields'].get(k)
        if av is not None and bv is not None:
            if av == bv:
                total += _WEIGHT[k]
        elif av is not None or bv is not None:
            total += _WEIGHT[k] / len(OPTIONS[k])
    return total


def decide_m07(request):
    state = request['state']
    memory = request.get('memory')
    if request['phase'] == 'ask':
        return {'asks': baseline_asks(state), 'memory': memory}
    kept = alloc.filter_min_score(common.feasible_edges(state), common.PRUNE_MIN_SCORE)
    return {'pairs': alloc.greedy_take(kept), 'memory': memory}


DECISIONS = {
    'm01_greedy_baseline': decide_m01,
    'm02_reciprocal_sum': _scored_match(score_m02),
    'm03_reciprocal_min': _scored_match(score_m03),
    'm04_reciprocal_product': _scored_match(score_m04),
    'm05_harmonic_reciprocal': _scored_match(score_m05),
    'm06_bottleneck': _scored_match(score_m06),
    'm07_prune_and_greedy': decide_m07,
    'm08_weighted_compatibility': _scored_match(score_m08),
}
