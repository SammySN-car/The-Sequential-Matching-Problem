"""Local A+C evaluation adapter (spec R5 / section 5).

evaluate.py always invokes local policies as `python <policy> --baseline <greedy|no_asks|random>`
(choices frozen, spec C4). This shim parses NO arguments - the --baseline flag is
deliberately ignored - and forces mode 'ac' on every request. The container path
does not use this file: the Docker image runs `python policy.py` with no args and
policy.py's argparse default ('ac') covers it.
"""
import json
import sys

from policy import decide


def main(argv=None):          # argv accepted but deliberately unused (R5)
    request = json.load(sys.stdin)
    print(json.dumps(decide(request, mode='ac'), allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
