"""E2 arm: analytic scorer only. Ask behavior byte-identical to control
(kit.baseline_asks); match uses the analytic score with kit's take-while algorithm."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from kit import baseline_asks  # noqa: E402
from rel_common import match_response  # noqa: E402


def decide(request):
    memory = request.get('memory') or {}
    state = request['state']
    if request['phase'] == 'ask':
        return {'asks': baseline_asks(state), 'memory': memory}
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
