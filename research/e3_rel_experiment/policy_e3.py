"""E3 arm: analytic scorer + VoI-gated REL soft asks (hard asks first, unchanged;
same take-while allocation mechanism as E2). Truth-blind enumeration gate."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from rel_common import W, match_response, voi_rel_asks  # noqa: E402


def order_key(item):
    member_id, field = item
    return (-W[field], member_id, field)


def decide(request):
    memory = request.get('memory') or {}
    state = request['state']
    if request['phase'] == 'ask':
        return {'asks': voi_rel_asks(state, 'analytic', order_key), 'memory': memory}
    return {'pairs': match_response(state, 'analytic'), 'memory': memory}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline', choices=['greedy', 'no_asks', 'random'], default='greedy')
    parser.parse_args(argv)
    request = json.load(sys.stdin)
    print(json.dumps(decide(request), allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
