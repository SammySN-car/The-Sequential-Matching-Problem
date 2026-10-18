"""Round 2 Stage 2 purity child - runs ONE arm on ONE request (stdin JSON) and
dumps the exact matcher internals: pre-floor edge list, the floor argument
ac_match passed, and the floor value the FROZEN matcher actually received.
One process per arm so the Arm B patch can never leak into Arm A measurements."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))        # repo root

import policy  # noqa: E402

REC = {}

arm = sys.argv[1]
if arm == 'nofloor':
    import ablation_policy  # applies the single -inf floor intervention

    _frozen = ablation_policy._FROZEN_MAX_SCORE_MATCHING

    def _frozen_rec(nodes, edges, f):
        REC['floor_to_frozen'] = f            # floor the FROZEN matcher received
        return _frozen(nodes, edges, f)

    ablation_policy._FROZEN_MAX_SCORE_MATCHING = _frozen_rec
elif arm != 'frozen':
    raise SystemExit('unknown arm: ' + arm)

_orig_matcher = policy.max_score_matching     # AFTER the Arm B patch (ablation wrapper or frozen)


def _recording_matcher(nodes, edges, floor):
    REC['nodes'] = list(nodes)
    REC['edges'] = [list(e) for e in edges]
    REC['floor'] = floor                      # argument ac_match passed in
    REC.setdefault('floor_to_frozen', floor)  # frozen arm: same value (no wrapper)
    out = _orig_matcher(nodes, edges, floor)
    REC['result'] = [list(e) for e in out]
    return out


policy.max_score_matching = _recording_matcher

request = json.load(sys.stdin)
response = policy.decide(request, mode='ac')
# allow_nan default: Arm B's floor_to_frozen is -inf (Python emits -Infinity).
print(json.dumps({'arm': arm, 'response': response, 'rec': REC}))