"""Outcome-Probability Replay (OPR) core estimator — RESEARCH ONLY.

Implements the exact P(MSMI | introduction of pair (a, b) on day `day`)
implied by kit.py outcome mechanics; derivation frozen in g0_findings.md.

Hard prohibitions (task spec):
  - Nothing in research/round2_opr/ may be imported by a deployed policy.
  - kit.py, policy.py, evaluate.py, Dockerfile are read-only inputs.
  - Hidden world fields (truth, bias, response_rate, second_bias, variant)
    are consumed here at ANALYSIS time only, never as inference features.

Stdlib only. p_msmi is deterministic (fixed quadrature, no wall clock).
"""

from functools import lru_cache
import hashlib
import math
import random

# Mirrored kit.py constants (not imported, so any drift fails loudly in tests).
BASE_WEIGHTS = {'relationship_goal': .7, 'relationship_pace': .4,
                'lifestyle': .25, 'conversations': .2}
SHIFT_WEIGHTS = {'relationship_goal': .25, 'relationship_pace': .8,
                 'lifestyle': -.25, 'conversations': .5}
HAPPENED_P = 0.78
SHARED_SIGMA = 0.45
SECOND_DELAY_MAX = 5           # kit: delay = r.randint(1, 5)
SECOND_ON_TIME_BOUND = 3       # kit metrics: occurred_day - date_day <= 3
SECOND_ON_TIME_P = SECOND_ON_TIME_BOUND / SECOND_DELAY_MAX  # 3/5
ACCEPT_BASE = -0.25
SECOND_BASE = 0.15
GOAL_MATCH_TERM = 0.4
DRIFT_THRESHOLD_DAY = 35
DRIFT_TERM = -0.5
DATE_WINDOW = 30


def rand_for(*parts):
    """Mirror of kit.rand_for: one deterministic stream per (seed, a, b, day)."""
    return random.Random(int.from_bytes(
        hashlib.sha256('|'.join(map(str, parts)).encode()).digest()[:16], 'big'))


def sigmoid(x):
    if x >= 0.0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


def fit_score(truth_a, truth_b, variant):
    """kit._prob fit term: +1 on equal weighted SOFT key, -0.5 otherwise."""
    weights = SHIFT_WEIGHTS if variant == 'shift' else BASE_WEIGHTS
    return sum(w * (1.0 if truth_a[k] == truth_b[k] else -0.5)
               for k, w in weights.items())


def drift_term(variant, day):
    return DRIFT_TERM if variant == 'drift' and day >= DRIFT_THRESHOLD_DAY else 0.0


def z_accept(bias, fit, shared, drift):
    return ACCEPT_BASE + bias + fit + shared + drift


def q_second(second_bias, shared, goal_match):
    return (SECOND_BASE + second_bias + shared
            + (GOAL_MATCH_TERM if goal_match else 0.0))


@lru_cache(maxsize=8)
def date_deadline_prob(variant):
    """Exact P(date_day - assigned_day <= 30) given both members accepted.

    Non-'delayed' variants: date offset = max(d1,d2)+u <= 7+14 = 21 <= 30 -> 1.
    'delayed': extra v ~ U{5..12}; exact finite enumeration, no sampling.
    """
    if variant != 'delayed':
        return 1.0
    hits = 0
    for d1 in range(1, 8):
        for d2 in range(1, 8):
            for u in range(1, 15):
                for v in range(5, 13):
                    if max(d1, d2) + u + v <= DATE_WINDOW:
                        hits += 1
    return hits / (7 * 7 * 14 * 8)


def p_msmi_conditional_g(m_a, m_b, variant, day, g):
    """Full chain probability given shared latent g (see g0_findings.md sec.2)."""
    fit = fit_score(m_a['truth'], m_b['truth'], variant)
    drift = drift_term(variant, day)
    goal_match = (m_a['truth']['relationship_goal']
                  == m_b['truth']['relationship_goal'])
    za = z_accept(m_a['bias'], fit, g, drift)
    zb = z_accept(m_b['bias'], fit, g, drift)
    qa = q_second(m_a['second_bias'], g, goal_match)
    qb = q_second(m_b['second_bias'], g, goal_match)
    return (m_a['response_rate'] * sigmoid(za)
            * m_b['response_rate'] * sigmoid(zb)
            * date_deadline_prob(variant)
            * HAPPENED_P
            * m_a['response_rate'] * SECOND_ON_TIME_P * sigmoid(qa)
            * m_b['response_rate'] * SECOND_ON_TIME_P * sigmoid(qb))


def _midpoint(f, lo, hi, n):
    h = (hi - lo) / n
    total = 0.0
    for i in range(n):
        total += f(lo + (i + 0.5) * h)
    return total * h


def p_msmi(m_a, m_b, variant, day, n=8001):
    """E_g[p_msmi_conditional_g] under g ~ N(0, SHARED_SIGMA^2).

    Midpoint rule on standard-normal z in [-7, 7], Richardson-extrapolated
    (O(h^4)); tail mass beyond 7 sigma is < 1.3e-12 with integrand <= 1.
    Deterministic; n only affects quadrature error, never randomness.
    Invariants are hoisted out of the quadrature loop (same arithmetic as
    p_msmi_conditional_g, evaluated once per call).
    """
    sigma = SHARED_SIGMA
    fit = fit_score(m_a['truth'], m_b['truth'], variant)
    drift = drift_term(variant, day)
    goal_match = (m_a['truth']['relationship_goal']
                  == m_b['truth']['relationship_goal'])
    const = (m_a['response_rate'] * m_b['response_rate']
             * date_deadline_prob(variant) * HAPPENED_P
             * m_a['response_rate'] * SECOND_ON_TIME_P
             * m_b['response_rate'] * SECOND_ON_TIME_P)
    za0 = ACCEPT_BASE + m_a['bias'] + fit + drift
    zb0 = ACCEPT_BASE + m_b['bias'] + fit + drift
    qa0 = SECOND_BASE + m_a['second_bias'] + (GOAL_MATCH_TERM if goal_match else 0.0)
    qb0 = SECOND_BASE + m_b['second_bias'] + (GOAL_MATCH_TERM if goal_match else 0.0)

    def integrand(z):
        g = sigma * z
        dens = math.exp(-0.5 * z * z) / math.sqrt(2.0 * math.pi)
        return (sigmoid(za0 + g) * sigmoid(zb0 + g)
                * sigmoid(qa0 + g) * sigmoid(qb0 + g)) * dens * const

    lo, hi = -7.0, 7.0
    coarse = _midpoint(integrand, lo, hi, n)
    fine = _midpoint(integrand, lo, hi, 2 * n)
    return fine + (fine - coarse) / 3.0


def simulate_outcome(seed, user_a, user_b, day, variant, members_by_id):
    """Re-derive one introduction's realized outcome from kit's exact draw order.

    Mirrors kit.Simulator.advance for a single pair (no eligibility checks:
    replay callers only pass introductions that actually happened).
    Returns dict: responded, accepted, response_delays, date_day, happened,
    second (tuple of (answered, yes, delay) or None), msmi.
    """
    a, b = sorted([user_a, user_b])
    ma, mb = members_by_id[a], members_by_id[b]
    r = rand_for(seed, a, b, day)
    shared = r.gauss(0.0, SHARED_SIGMA)
    fit = fit_score(ma['truth'], mb['truth'], variant)
    drift = drift_term(variant, day)
    responded, accepted, response_delays = [], [], []
    for actor, other in ((ma, mb), (mb, ma)):
        responded.append(r.random() < actor['response_rate'])
        accepted.append(r.random() < sigmoid(
            z_accept(actor['bias'], fit, shared, drift)))
        response_delays.append(r.randint(1, 7))
    if not (all(responded) and all(accepted)):
        return {'responded': tuple(responded), 'accepted': tuple(accepted),
                'response_delays': tuple(response_delays), 'date_day': None,
                'happened': None, 'second': None, 'msmi': False}
    date_day = day + max(response_delays) + r.randint(1, 14)
    if variant == 'delayed':
        date_day += r.randint(5, 12)
    happened = r.random() < HAPPENED_P
    second = None
    if happened:
        second = []
        for actor, other in ((ma, mb), (mb, ma)):
            answer = r.random() < actor['response_rate']
            delay = r.randint(1, SECOND_DELAY_MAX)
            goal_match = (actor['truth']['relationship_goal']
                          == other['truth']['relationship_goal'])
            p = sigmoid(q_second(actor['second_bias'], shared, goal_match))
            yes = r.random() < p
            second.append((answer, yes, delay))
    within = date_day - day <= DATE_WINDOW
    counts = second is not None and all(
        answered and yes and delay <= SECOND_ON_TIME_BOUND
        for answered, yes, delay in second)
    msmi = bool(happened and within and counts)
    return {'responded': tuple(responded), 'accepted': tuple(accepted),
            'response_delays': tuple(response_delays), 'date_day': date_day,
            'happened': bool(happened) if happened is not None else None,
            'second': tuple(second) if second is not None else None,
            'within': within, 'msmi': msmi}


def members_index(world):
    """{member_id: member} over the RAW generated world (hidden fields intact)."""
    return {m['member_id']: m for m in world['members']}
