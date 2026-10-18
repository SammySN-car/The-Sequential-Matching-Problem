"""Official-protocol stdin/stdout runner shared by every generated launcher."""
import json
import sys


def run(fn):
    try:
        request = json.load(sys.stdin)
        response = fn(request)
        json.dump(response, sys.stdout, allow_nan=False, sort_keys=True)
        sys.stdout.write('\n')
        return 0
    except Exception as exc:  # policy errors must surface as nonzero exit (evaluate.invoke)
        sys.stderr.write(str(exc)[:2000])
        return 1
