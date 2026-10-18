"""Round 2 Stage 3 - Arm 2: frozen A+C with the PRE-REGISTERED intermediate floor.

Pre-registration: research/round2_stage3_intermediate_floor/preregistration.md
(SHA256 FA11A2FB4DF53D507AA8C4D1A905025FD6392F5B656CC997CEE83FED4BF2D491).

The three Stage 3 arms differ ONLY in the floor argument passed to the matcher:

    Arm 1 (frozen):       max_score_matching(nodes, edges, float(model['floor']))
    Arm 2 (intermediate): max_score_matching(nodes, edges, float(model['floor']) / 2.0)   <- this file
    Arm 3 (no floor):     max_score_matching(nodes, edges, -inf)   # Stage 2 ablation_policy.py

Frozen floor = 0.007905174015296758 (embedded model blob, read-only);
registered intermediate value = 0.003952587007648379 = floor / 2.0.

Mechanism: ac_match (policy.py:591) passes float(model['floor']) as the floor
argument to policy.max_score_matching. This wrapper receives exactly that
argument, verifies it equals the registered frozen value (fail-fast integrity
guard; never fires under correct operation), and halves it before delegating to
the FROZEN matcher function object. The predicate e[2] >= floor
(policy.py:469) therefore evaluates as e[2] >= model_floor / 2.0. No other
line differs from the frozen policy:

    * candidate generation (policy.py:567-584) - untouched (runs before model load)
    * model scoring / embedded blob - untouched (read-only)
    * greedy seed + local search inside max_score_matching - untouched (frozen object called)
    * ac_asks clarification - untouched (never reads floor)
    * fallback _rule_greedy - untouched
    * candidate cap, memory, determinism, CLI protocol - untouched

Invocation matches policy_ac.py exactly: python intermediate_policy.py
--baseline <ignored> reads one request from stdin, writes one response to
stdout. Read-only with respect to all frozen artifacts; this file writes
nothing.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))   # repo root: import policy/kit

import policy  # noqa: E402  (frozen Round 1 policy - READ-ONLY)

_FROZEN_MAX_SCORE_MATCHING = policy.max_score_matching

_EXPECTED_FLOOR = 0.007905174015296758          # frozen model floor (registered)
_EXPECTED_INTERMEDIATE = 0.003952587007648379    # registered rule: floor / 2.0


def _max_score_matching_intermediate(nodes, edges, floor):
    """Sole intervention: pass floor / 2.0 to the frozen matcher (the
    pre-registered rule). Everything else is the frozen matcher itself -
    same ordering, same seed, same search."""
    if floor != _EXPECTED_FLOOR:
        raise RuntimeError(
            'unexpected floor argument %r (registered frozen floor %r)' % (floor, _EXPECTED_FLOOR))
    return _FROZEN_MAX_SCORE_MATCHING(nodes, edges, floor / 2.0)


policy.max_score_matching = _max_score_matching_intermediate


def main(argv=None):          # argv deliberately ignored, exactly like policy_ac.py (R5)
    request = json.load(sys.stdin)
    print(json.dumps(policy.decide(request, mode='ac'), allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())