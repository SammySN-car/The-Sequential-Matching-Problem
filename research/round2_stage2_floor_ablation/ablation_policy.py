"""Round 2 Stage 2 - Arm B: frozen A+C with floor filtering DISABLED.

Causal ablation (measurement only, no tuning). This policy is behaviorally
identical to the frozen Round 1 A+C policy (policy_ac.py -> policy.decide(mode='ac'))
except for the single floor argument passed to the matcher:

    Arm A (frozen):  max_score_matching(nodes, edges, float(model['floor']))
    Arm B (this):    max_score_matching(nodes, edges, -inf)

The frozen code filtered candidate edges with the predicate `e[2] >= floor`
(policy.py:469). Passing -inf makes that predicate tautologically true for every
finite model score (scores are sigmoid outputs strictly in (0, 1)), which is
literally equivalent to removing the filtering operation. No threshold is
substituted; no other line is touched:

    * candidate generation (policy.py:567-584) - untouched, and it runs BEFORE
      the model/floor is even loaded (line 585), so it cannot depend on the floor
    * model scoring (_score_pair / score_row / embedded blob) - untouched
    * greedy seed + local search inside max_score_matching - untouched (the
      frozen function object itself is called)
    * ac_asks clarification policy - untouched (never reads floor)
    * fallback _rule_greedy - untouched (was already floor-free)
    * candidate cap, memory, determinism, CLI protocol - untouched

Invocation matches policy_ac.py exactly: `python ablation_policy.py --baseline
<ignored>` reads one request from stdin, writes one response to stdout.
Read-only with respect to all frozen artifacts; this file writes nothing.
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))   # repo root: import policy/kit

import policy  # noqa: E402  (frozen Round 1 policy - READ-ONLY)

_FROZEN_MAX_SCORE_MATCHING = policy.max_score_matching


def _max_score_matching_floor_disabled(nodes, edges, floor):
    """Sole intervention: neutralize the floor argument (-inf). All other
    behavior is the frozen matcher itself - same ordering, same seed, same search."""
    return _FROZEN_MAX_SCORE_MATCHING(nodes, edges, -math.inf)


policy.max_score_matching = _max_score_matching_floor_disabled


def main(argv=None):          # argv deliberately ignored, exactly like policy_ac.py (R5)
    request = json.load(sys.stdin)
    print(json.dumps(policy.decide(request, mode='ac'), allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())