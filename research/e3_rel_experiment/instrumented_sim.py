"""Instrumentation for the E2 mechanism pass.

Subclass of kit.Simulator used via evaluate.episode(world, command,
simulator_class=InstrumentedSim). All policy invocations stay in evaluate's
official subprocess path, so results (incl. action_sha256) must be byte-identical
to the official run; instrumentation only records what already happened.
"""
import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kit import Simulator  # noqa: E402
from rel_common import REL, alloc_count, alloc_analytic, candidate_edges, s_count, s_analytic  # noqa: E402


class InstrumentedSim(Simulator):
    last_instance = None

    def __init__(self, world):
        super().__init__(world)
        self.log = {'observes': [], 'asks': [], 'advances': []}
        InstrumentedSim.last_instance = self

    def observe(self):
        st = super().observe()
        self.log['observes'].append(st)
        return st

    def resolve_asks(self, asks):
        out = super().resolve_asks(asks)
        self.log['asks'].append({'day': self.day, 'asks': copy.deepcopy(asks),
                                 'revealed': copy.deepcopy(out)})
        return out

    def advance(self, pairs):
        n = len(self.events)
        day = self.day
        super().advance(pairs)
        self.log['advances'].append({'day': day,
                                     'pairs': [list(p) for p in pairs],
                                     'new_events': copy.deepcopy(self.events[n:])})


def mask_rel_reveals(match_state, ask_state):
    """match_state with today's REL reveals undone (hard reveals kept).

    Returns a copy of match_state where every REL field whose status differs
    from the pre-ask state is restored to its pre-ask value/status.
    """
    masked = copy.deepcopy(match_state)
    pre = {m['member_id']: m for m in ask_state['members']}
    for m in masked['members']:
        pm = pre[m['member_id']]
        for k in REL:
            if m['field_status'][k] != pm['field_status'][k]:
                m['fields'][k] = copy.deepcopy(pm['fields'][k])
                m['field_status'][k] = pm['field_status'][k]
                m['field_observed_day'][k] = pm['field_observed_day'][k]
    return masked


def episode_mechanism(log, arm):
    """Per-day mechanism rows for one episode.

    arm: 'C' | 'E1' | 'E2' | 'E3'  (selects the allocation/scorer to replay).
    Only observes[0..119] (the 60 decision days) and advances[0..59] are used.
    """
    scorer = s_count if arm in ('C', 'E1') else s_analytic
    alloc = alloc_count if arm in ('C', 'E1') else alloc_analytic
    rows = []
    for d in range(60):
        ask_state = log['observes'][2 * d]
        match_state = log['observes'][2 * d + 1]
        ask_rec = log['asks'][d] if d < len(log['asks']) else None
        rel_asks = [] if ask_rec is None else [a for a in ask_rec['asks']
                                               if a['field'] in REL]
        hard_asks = [] if ask_rec is None else [a for a in ask_rec['asks']
                                                if a['field'] not in REL]
        actual = [list(p) for p in log['advances'][d]['pairs']]
        masked = mask_rel_reveals(match_state, ask_state)
        cf = [list(p) for p in alloc(masked)]
        # edge-score ranking effect of today's REL reveals
        edges = candidate_edges(masked)     # feasibility is REL-invariant
        pre = _fields(masked)
        post = _fields(match_state)
        pre_scores = {e: scorer(pre[e[0]], pre[e[1]]) for e in edges}
        post_scores = {e: scorer(post[e[0]], post[e[1]]) for e in edges}
        changed_edges = sum(1 for e in edges if pre_scores[e] != post_scores[e])
        rank_pre = sorted((-pre_scores[e], e[0], e[1]) for e in edges)
        rank_post = sorted((-post_scores[e], e[0], e[1]) for e in edges)
        rows.append({
            'day': d,
            'rel_asks': len(rel_asks),
            'rel_ask_cost': len(rel_asks),
            'hard_asks': len(hard_asks),
            'intros': len(actual),
            'zero_selection': len(actual) == 0,
            'alloc_changed_by_rel': cf != actual,
            'rel_asks_on_changed_day': len(rel_asks) if cf != actual else 0,
            'edges_changed': changed_edges,
            'edges_total': len(edges),
            'ranking_changed': rank_pre != rank_post,
        })
    return rows


def _fields(state):
    return {m['member_id']: m['fields'] for m in state['members']}
