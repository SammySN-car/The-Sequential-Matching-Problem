"""Rollout collection: opportunity scanning, randomized policy, row building.

Policies observe ONLY Simulator.observe() output. The randomized collector exists
to produce diverse, positive-propensity data: bundle constraints asks, prioritize
relationship_goal, jittered/eps-random ordering, random valid maximal matching.
Every row is an INTRODUCED pair; un-introduced pairs are never labelled.
"""
import random

import kit

import features as feat
import labels as lab


def scan(state):
    """Every (a, b) that could lawfully be introduced today: available + feasible + not past.
    This is the coverage denominator."""
    members = [m for m in state['members'] if m['available']]
    past = {tuple(sorted((i['user_a'], i['user_b']))) for i in state['introductions']}
    edges = []
    for i in range(len(members)):
        for j in range(i + 1, len(members)):
            a, b = members[i], members[j]
            key = tuple(sorted((a['member_id'], b['member_id'])))
            if key in past or kit.eligibility(a, b)['status'] != 'feasible':
                continue
            edges.append(key)
    return edges


def soft_score(a, b):
    """Observed soft-field agreement only (legal: reads observe() fields, not truth)."""
    n = 0
    for key in feat.SOFT:
        va, vb = a['fields'].get(key), b['fields'].get(key)
        if va is not None and vb is not None and va == vb:
            n += 1
    return n


class RandomCollector:
    """Randomized ask + match policy. Pure function of (state, seed): no hidden state."""

    def __init__(self, seed=0, eps=0.30, jitter=1.0, bundle=(0, 2, 3, 3, 4),
                 soft_priority=None):
        self.rng = random.Random(seed)
        self.eps = eps
        self.jitter = jitter
        self.bundle = tuple(bundle)
        self.soft_priority = tuple(soft_priority or feat.SOFT)

    def asks(self, state):
        budget = state['ask_budget_remaining']
        if budget < 1:
            return []
        out = []
        cost = 0
        seen = set()
        eligible = [m for m in state['members'] if m['available']
                    and any(m['fields'].get(k) is None for k in feat.HARD)
                    and not any(m['field_status'].get(k) == 'declined' for k in feat.HARD)]
        self.rng.shuffle(eligible)          # jittered ordering
        want = self.rng.choice(self.bundle) # bundle asks
        bundles = 0
        for m in eligible:
            if bundles >= want or cost + 3 > budget:
                break
            out.append({'member_id': m['member_id'], 'field': 'constraints'})
            seen.add((m['member_id'], 'constraints'))
            cost += 3
            bundles += 1
        for m in eligible:
            if cost >= budget:
                break
            for key in self.soft_priority:
                if cost >= budget:
                    break
                if (m['member_id'], key) in seen:
                    continue
                if m['fields'].get(key) is not None:
                    continue
                if m['field_status'].get(key) == 'declined':
                    continue
                out.append({'member_id': m['member_id'], 'field': key})
                seen.add((m['member_id'], key))
                cost += 1
        return out

    def match(self, state):
        """Random valid maximal matching over ALL opportunities (eps-random or jittered)."""
        edges = scan(state)
        if not edges:
            return []
        members = {m['member_id']: m for m in state['members']}
        if self.rng.random() < self.eps:
            order = list(edges)
            self.rng.shuffle(order)
        else:
            scored = [(soft_score(members[a], members[b])
                       + self.jitter * self.rng.gauss(0, 1), a, b) for a, b in edges]
            scored.sort(key=lambda x: -x[0])
            order = [(a, b) for _, a, b in scored]
        used = set()
        out = []
        for a, b in order:
            if a in used or b in used:
                continue
            used.update((a, b))
            out.append([a, b])
        return out


def collect_rows(world, collector_seed=0, days=60, follow_up=40, policy='random'):
    """Run one rollout, return decision-time features for each introduced pair + labels.

    Features come from the state at day t BEFORE advance (decision time).
    Labels come after `days + follow_up` so every introduction has matured.
    """
    if policy not in ('random', 'greedy'):
        raise ValueError('unknown policy: ' + policy)
    sim = kit.Simulator(world)
    collector = RandomCollector(seed=collector_seed) if policy == 'random' else None
    rows = []
    per_day = []
    for t in range(days):
        state = sim.observe()
        asks = collector.asks(state) if collector else kit.baseline_asks(state)
        sim.resolve_asks(asks)
        state = sim.observe()
        opps = scan(state)
        pairs = collector.match(state) if collector else kit.baseline_match(state)
        available = sum(1 for m in state['members'] if m['available'])
        for pair in pairs:
            a, b = sorted(pair)
            rows.append({'day': t, 'a': a, 'b': b,
                         'features': feat.pair_features(state, a, b, t),
                         'world_seed': world['seed'], 'variant': world['variant'],
                         'policy': policy, 'collector_seed': collector_seed})
        per_day.append({'day': t, 'opportunities': len(opps),
                        'chosen': len(pairs), 'available': available})
        sim.advance(pairs)
    for _ in range(follow_up):
        sim.advance([])

    horizon = sim.day
    # Labels are constructed post-episode from the COMPLETE event record so that
    # immature outcomes become None instead of being coerced to 0. Policies never
    # see events: features still come from Simulator.observe() snapshots only.
    grouped = lab.group_events(sim.events)
    index = {(i['assigned_day'], tuple(sorted((i['user_a'], i['user_b'])))): i
             for i in sim.introductions}
    for row in rows:
        intro = index.get((row['day'], tuple(sorted((row['a'], row['b'])))))
        if intro is None:
            raise AssertionError('chosen pair missing from introductions')
        evs = grouped.get(intro['introduction_id'], [])
        row['introduction_id'] = intro['introduction_id']
        row['horizon'] = horizon
        row['maturity_day'] = lab.maturity_day(evs)
        row['label'] = lab.label_msmi(evs, intro['assigned_day'], horizon)
        row['label_mutual'] = lab.label_mutual(evs, intro['assigned_day'], horizon)
        row['label_date'] = lab.label_date(evs, intro['assigned_day'], horizon)
    if len(rows) != len(sim.introductions):
        raise AssertionError('every introduction must yield exactly one row')
    total_opp = sum(d['opportunities'] for d in per_day)
    total_chosen = sum(d['chosen'] for d in per_day)
    return {'rows': rows, 'per_day': per_day, 'introductions': sim.introductions,
            'events': sim.events,
            'metrics': sim.metrics(), 'variant': world['variant'],
            'world_seed': world['seed'], 'policy': policy,
            'collector_seed': collector_seed, 'horizon': horizon,
            'opportunities_total': total_opp, 'chosen_total': total_chosen,
            'coverage_fraction': (total_chosen / total_opp) if total_opp else 0.0}
