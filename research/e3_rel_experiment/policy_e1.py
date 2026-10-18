"""E1 arm: REL-asks-only. Count scoring/allocation unchanged (kit.baseline_*),
plus VoI-gated REL soft asks (enumeration gate, truth-blind)."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from kit import baseline_match  # noqa: E402
from rel_common import voi_rel_asks  # noqa: E402


def order_key(item):
    member_id, field = item
    return (member_id, field)


def decide(request):
    memory = request.get('memory') or {}
    state = request['state']
    if request['phase'] == 'ask':
        return {'asks': voi_rel_asks(state, 'count', order_key), 'memory': memory}
    return {'pairs': baseline_match(state), 'memory': memory}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline', choices=['greedy', 'no_asks', 'random'], default='greedy')
    parser.parse_args(argv)
    request = json.load(sys.stdin)
    print(json.dumps(decide(request), allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
