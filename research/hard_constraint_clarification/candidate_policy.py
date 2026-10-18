"""Candidate policy: prioritized hard-constraint clarification allocation (isolated research).

Invoked through the UNMODIFIED official evaluator, from the repository root:

    python evaluate.py --policy research/hard_constraint_clarification/candidate_policy.py `
        --baseline greedy --seeds <seed> --variants <variant> --output <path>

evaluate.py always appends "--baseline <name>"; that flag is accepted and ignored here
(the same pattern as policy_ac.py). The active mode comes from the environment variable
HCC_MODE:  'greedy'  -> kit.baseline_asks + kit.baseline_match (action-identical to
policy.py --baseline greedy; proven by the pilot digest gate),  anything else  ->
unlock-priority clarification allocation with greedy-order fill of leftover slots.
Matching, memory handling, budget, costs and eligibility are identical across modes.

Observable-information-only: reads nothing beyond the public request state. Never reads
hidden simulation values, never loads any learned model.
"""
import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import kit  # noqa: E402  (repository root on sys.path)

_LAST_DIAG = {'trace': [], 'n_eligible': 0}


def _eligible_members(state):
    """Exactly the kit.baseline_asks eligibility filter (kit.py L205-L207)."""
    return [m for m in state['members']
            if m['available']
            and any(m['fields'].get(k) is None for k in kit.HARD)
            and not any(m['field_status'].get(k) == 'declined' for k in kit.HARD)]


def _flags(state):
    """Per-member observable constants: any declined hard field, all hard fields observed."""
    declined, complete = {}, {}
    for m in state['members']:
        mid = m['member_id']
        declined[mid] = any(m['field_status'].get(k) == 'declined' for k in kit.HARD)
        complete[mid] = all(m['fields'].get(k) is not None for k in kit.HARD)
    return declined, complete


def _score_members(state, eligible):
    """Return (unlock, inform) pair-key sets per eligible member.

    unlock[m]: pairs {m,n} whose only unresolved side is m's own hard info - asking m
               fully resolves the pair's missing information (n hard-observed, no observed
               hard failure, not previously introduced).
    inform[m]: pairs {m,n] still missing hard information (needs_clarification) with no
               observed hard failure - asking m informs one side of the pair.

    Excluded from both: pairs with any observed hard failure (known incompatibility
    respected) and pairs where either side has a declined hard field (declined answers are
    never revealed, kit.py L114/L127, so those pairs are permanently unresolvable and must
    not be counted as potential opportunities).
    """
    avail = [m for m in state['members'] if m['available']]
    past = {tuple(sorted((i['user_a'], i['user_b']))) for i in state['introductions']}
    declined, complete = _flags(state)
    elig_ids = {m['member_id'] for m in eligible}
    unlock = {m['member_id']: set() for m in eligible}
    inform = {m['member_id']: set() for m in eligible}
    for i, a in enumerate(avail):
        ka = a['member_id']
        ea = ka in elig_ids
        for b in avail[i + 1:]:
            kb = b['member_id']
            eb = kb in elig_ids
            if not (ea or eb):
                continue
            if declined[ka] or declined[kb]:
                continue
            key = (ka, kb) if ka < kb else (kb, ka)
            if key in past:
                continue
            status = kit.eligibility(a, b)['status']
            if status != 'needs_clarification':
                continue
            if ea:
                inform[ka].add(key)
                if complete[kb]:
                    unlock[ka].add(key)
            if eb:
                inform[kb].add(key)
                if complete[ka]:
                    unlock[kb].add(key)
    return unlock, inform


def selection_trace(state, max_asks=None):
    """Deterministic marginal-coverage selection; returns one record per priority pick.

    Each step picks the eligible member with the lexicographic maximum
    (marginal unlock, marginal inform, -state_index). Pair keys already covered by an
    earlier pick are removed (no double counting); pairs are reciprocal, so a pair whose
    both sides are unknown appears in both members' inform sets and is counted once.
    Stops when no remaining member has positive potential (the caller then fills leftover
    slots in greedy state order, keeping the daily ask count identical to greedy).
    """
    if max_asks is None:
        max_asks = int(state.get('ask_budget_remaining') or 0) // 3
    if max_asks <= 0:
        return []
    eligible = _eligible_members(state)
    if not eligible:
        return []
    unlock, inform = _score_members(state, eligible)
    trace, covered, selected = [], set(), set()
    order = [(m['member_id'], i) for i, m in enumerate(eligible)]
    while len(trace) < max_asks:
        best_key, best_mid = None, None
        for mid, idx in order:
            if mid in selected:
                continue
            key = (len(unlock[mid] - covered), len(inform[mid] - covered), -idx)
            if best_key is None or key > best_key:
                best_key, best_mid = key, mid
        if best_mid is None or (best_key[0] == 0 and best_key[1] == 0):
            break
        trace.append({'member_id': best_mid,
                      'unlock_marginal': best_key[0],
                      'inform_marginal': best_key[1],
                      'pair_keys_unlocked': sorted(unlock[best_mid] - covered)})
        selected.add(best_mid)
        covered |= unlock[best_mid] | inform[best_mid]
    return trace


def hcc_asks(state, priority=True):
    """Constraint clarification asks (cost 3 each, capped by ask_budget_remaining // 3).

    priority=True: unlock-priority rule first, then leftover slots filled in greedy state
    order - so the number of asks per day always equals greedy's, only recipients differ.
    priority=False: the official kit.baseline_asks verbatim (isolation reference).
    """
    global _LAST_DIAG
    if not priority:
        asks = list(kit.baseline_asks(state))
        _LAST_DIAG = {'trace': [], 'n_eligible': len(_eligible_members(state))}
        return asks
    max_asks = int(state.get('ask_budget_remaining') or 0) // 3
    trace = selection_trace(state, max_asks=max_asks)
    eligible = _eligible_members(state)
    chosen = {t['member_id'] for t in trace}
    asks = [{'member_id': t['member_id'], 'field': 'constraints'} for t in trace]
    for m in eligible:
        if len(asks) >= max_asks:
            break
        if m['member_id'] in chosen:
            continue
        asks.append({'member_id': m['member_id'], 'field': 'constraints'})
    _LAST_DIAG = {'trace': trace, 'n_eligible': len(eligible)}
    return asks


def decide(request, mode='unlock'):
    state = request['state']
    memory = request.get('memory') or {}
    if request['phase'] == 'ask':
        return {'asks': hcc_asks(state, priority=(mode != 'greedy')), 'memory': memory}
    return {'pairs': kit.baseline_match(state), 'memory': memory}


def _log(request, mode, out):
    path = os.environ.get('HCC_LOG')
    if not path or request.get('phase') != 'ask':
        return
    state = request['state']
    rec = {'day': state.get('day'), 'mode': mode,
           'budget_remaining': state.get('ask_budget_remaining'),
           'n_eligible': _LAST_DIAG.get('n_eligible'),
           'asks': list(out['asks']), 'n_asks': len(out['asks']),
           'spent': 3 * len(out['asks']), 'trace': _LAST_DIAG.get('trace')}
    with open(path, 'a', encoding='utf-8') as fh:
        fh.write(json.dumps(rec, sort_keys=True) + '\n')


def build_parser():
    p = argparse.ArgumentParser()
    p.add_argument('--baseline')   # appended by evaluate.py; accepted and ignored
    return p


def main(argv=None):
    build_parser().parse_args(argv)
    request = json.load(sys.stdin)
    mode = os.environ.get('HCC_MODE') or 'unlock'
    out = decide(request, mode=mode)
    _log(request, mode, out)
    print(json.dumps(out, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())