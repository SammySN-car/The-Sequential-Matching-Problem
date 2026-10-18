"""Round 2 candidate launcher: gated / ungated maximum-weight allocation.

Protocol-compatible with policy.py (reads one JSON request on stdin, writes one
JSON response on stdout; accepts and ignores --baseline for evaluate.py CLI use).

Ask phase: exactly kit.baseline_asks (identical to official greedy).
Match phase: alloc_core.allocate(state, arm) - arms differ ONLY in the frozen
adoption gate (research/round2/design.md section 3.1).

Memory protocol: aggregate calibration-band counters + pending intro map +
cumulative gate telemetry (design.md section 7). No member-level outcomes
beyond band aggregates; well under 1 MiB. Deterministic; stdlib only; no
network; no filesystem writes.

Band outcome settlement (diagnostic only; NEVER affects allocation):
pending intro_id -> [band, assigned_day]; settled when both response events
are observed AND either the date outcome is decided or day > assigned+37.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))   # repo root: kit
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # research/round2: alloc_core

from kit import baseline_asks  # noqa: E402  (frozen kit, READ-ONLY)
import alloc_core  # noqa: E402

BANDS = tuple(range(8))  # score = observed equal-SOFT count, 0..7


def intro_id(a, b, day):
    """Replicates kit.Simulator.advance id derivation (public, deterministic)."""
    return 'intro_' + hashlib.sha256(('%s|%s|%s' % (a, b, day)).encode()).hexdigest()[:24]


def empty_memory():
    return {'bands': {str(s): [0, 0, 0, 0] for s in BANDS},  # [intros, mutual, dates, msmi]
            'pending': {},   # intro_id -> [band, assigned_day]
            'solver_tried': 0, 'solver_exact': 0, 'gate_adopted': 0,
            'reject_g1': 0, 'reject_g2': 0, 'reject_other': 0,
            'score_gain_sum': 0, 'card_delta_sum': 0,
            'days': 0, 'zero_days': 0, 'pairs_total': 0}


def sanitize_memory(mem):
    """Defensive: accept only our own aggregate shape; anything else restarts."""
    if not isinstance(mem, dict) or 'bands' not in mem:
        return empty_memory()
    base = empty_memory()
    for k in base:
        if k in mem:
            base[k] = mem[k]
    clean = {}
    for s in BANDS:
        row = base['bands'].get(str(s))
        if not (isinstance(row, list) and len(row) == 4):
            row = [0, 0, 0, 0]
        clean[str(s)] = [int(x) for x in row]
    base['bands'] = clean
    pend = {}
    raw = mem.get('pending') if isinstance(mem.get('pending'), dict) else {}
    for k in list(raw)[:400]:
        v = raw[k]
        if isinstance(k, str) and isinstance(v, list) and len(v) == 2:
            pend[k] = [int(v[0]), int(v[1])]
    base['pending'] = pend
    for k in ('solver_tried', 'solver_exact', 'gate_adopted', 'reject_g1', 'reject_g2',
              'reject_other', 'score_gain_sum', 'card_delta_sum', 'days', 'zero_days',
              'pairs_total'):
        base[k] = int(base.get(k, 0) or 0)
    return base


def update_bands(memory, state, day, proposals):
    """Calibration-band bookkeeping (diagnostic only; never affects pairs).

    Outcomes are read only from state['feedback'] (already-observed events).
    MSMI: both responses yes AND date within 30 days of assignment AND both
    second intentions yes within 3 days of date (mirrors kit.Simulator.metrics
    on observed events)."""
    for a, b, score in proposals:
        band = max(0, min(7, int(score)))
        memory['bands'][str(band)][0] += 1
        memory['pending'][intro_id(a, b, day)] = [band, day]
    events_by_intro = {}
    for e in state.get('feedback', ()):
        events_by_intro.setdefault(e['introduction_id'], []).append(e)
    for mid in list(memory['pending']):
        band, assigned = memory['pending'][mid]
        es = events_by_intro.get(mid) or []
        rs = [e for e in es if e['event'] == 'introduction_response']
        ds = [e for e in es if e['event'] == 'date_happened']
        ss = [e for e in es if e['event'] == 'second_meeting_intention']
        # Settle only when the outcome chain is decided or the horizon passed.
        settle = False
        mutual = happened = False
        if len(rs) >= 2:
            mutual = all(e['value'] == 'yes' for e in rs)
            if not mutual:
                settle = True
            else:
                true_dates = [e for e in ds if e['value'] is True]
                false_dates = [e for e in ds if e['value'] is False]
                if true_dates:
                    happened = True
                    if len(ss) >= 2 or day > true_dates[0]['occurred_day'] + 6:
                        settle = True
                elif false_dates or day > assigned + 45:
                    settle = True
        elif day > assigned + 10:
            settle = True
        if not settle:
            continue
        row = memory['bands'][str(band)]
        if mutual:
            row[1] += 1
        if happened:
            row[2] += 1
        true_dates = [e for e in ds if e['value'] is True]
        if happened and true_dates and true_dates[0]['occurred_day'] - assigned <= 30 and len(ss) == 2 and \
                all(e['value'] == 'yes' and e['occurred_day'] - true_dates[0]['occurred_day'] <= 3
                    for e in ss):
            row[3] += 1
        del memory['pending'][mid]
    return memory


def decide(request, arm):
    state = request['state']
    memory = sanitize_memory(request.get('memory'))
    phase = request['phase']
    if phase == 'ask':
        return {'asks': baseline_asks(state), 'memory': memory}
    pairs, telemetry = alloc_core.allocate(state, arm)
    day = state['day']
    score_by_pair = {alloc_core.pair_key(a, b): s for a, b, s in alloc_core.feasible_edges(state)}
    proposals = [(p[0], p[1], score_by_pair.get(alloc_core.pair_key(p[0], p[1]), 0)) for p in pairs]
    memory = update_bands(memory, state, day, proposals)
    memory['days'] += 1
    if not pairs:
        memory['zero_days'] += 1
    memory['pairs_total'] += len(pairs)
    if telemetry.get('solver_tried'):
        memory['solver_tried'] += 1
    if telemetry.get('solver') in ('exact', 'empty_graph'):
        memory['solver_exact'] += 1
    if telemetry.get('gate_adopted_exact'):
        memory['gate_adopted'] += 1
        memory['score_gain_sum'] += int(telemetry.get('score_gain') or 0)
        memory['card_delta_sum'] += int(telemetry.get('cardinality_change') or 0)
    reason = telemetry.get('reject_reason')
    if reason == 'g1_cardinality_loss':
        memory['reject_g1'] += 1
    elif reason == 'g2_no_strict_gain':
        memory['reject_g2'] += 1
    elif reason is not None and reason != 'adopted':
        memory['reject_other'] += 1
    return {'pairs': pairs, 'memory': memory}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--arm', choices=['gated', 'ungated'], required=True)
    parser.add_argument('--baseline', default=None)  # accepted, ignored (CLI compatibility)
    args = parser.parse_args(argv)
    request = json.loads(sys.stdin.read())
    response = decide(request, args.arm)
    sys.stdout.write(json.dumps(response, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())