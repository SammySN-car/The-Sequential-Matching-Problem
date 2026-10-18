"""Group B: scarcity / opportunity-cost methods (m09-m15). Ask phase = baseline_asks."""
from kit import baseline_asks
import common
import alloc


def _scored_match(score_fn):
    def decide(request):
        state = request['state']
        memory = request.get('memory')
        if request['phase'] == 'ask':
            return {'asks': baseline_asks(state), 'memory': memory}
        ctx = common.make_ctx(state)
        scored = [(a, b, score_fn(ctx, a, b, s)) for a, b, s in ctx['edges']]
        return {'pairs': alloc.greedy_take(scored), 'memory': memory}
    return decide


def score_m09(ctx, a, b, base):
    return base / max(1, min(ctx['deg'].get(a, 1), ctx['deg'].get(b, 1)))


def score_m10(ctx, a, b, base):
    return base / max(1, max(ctx['deg'].get(a, 1), ctx['deg'].get(b, 1)))


def score_m11(ctx, a, b, base):
    return base * 2.0 / (ctx['deg'].get(a, 1) + ctx['deg'].get(b, 1))


def _gaps(ctx, a, b, base):
    gap_a = max(0, common.alt_for(ctx, a, b) - base)
    gap_b = max(0, common.alt_for(ctx, b, a) - base)
    return gap_a, gap_b


def score_m12(ctx, a, b, base):
    gap_a, gap_b = _gaps(ctx, a, b, base)
    return base - gap_a - gap_b


def score_m13(ctx, a, b, base):
    gap_a, gap_b = _gaps(ctx, a, b, base)
    return base - max(gap_a, gap_b)


def score_m14(ctx, a, b, base):
    gap_a, gap_b = _gaps(ctx, a, b, base)
    return base - min(gap_a, gap_b)


def score_m15(ctx, a, b, base):
    cnt_a = sum(1 for s, o in ctx['inc'].get(a, ()) if o != b and s >= common.STRONG_SCORE)
    cnt_b = sum(1 for s, o in ctx['inc'].get(b, ()) if o != a and s >= common.STRONG_SCORE)
    return base - cnt_a - cnt_b


DECISIONS = {
    'm09_partner_scarcity': _scored_match(score_m09),
    'm10_degree_balanced': _scored_match(score_m10),
    'm11_scarcity_x_compat': _scored_match(score_m11),
    'm12_regret_score': _scored_match(score_m12),
    'm13_opportunity_cost': _scored_match(score_m13),
    'm14_mutual_regret': _scored_match(score_m14),
    'm15_reserve_high_option': _scored_match(score_m15),
}
