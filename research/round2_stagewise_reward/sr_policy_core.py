"""Shared stdin/stdout adapter core for stagewise-reward policies (Task 4).

Protocol (evaluate.py invoke(), L45-69): the harness spawns the policy as
`python <policy> --baseline <mode>`, writes exactly ONE JSON request line
({schema_version, phase, state, memory}) to stdin, closes stdin, and expects
exactly ONE JSON response line ({asks|pairs, memory}) on stdout; a fresh
process handles each (phase, day) invocation (120 per episode). Memory is
passed through verbatim - nothing is accumulated - so serialized memory stays
far below the 1 MiB limit (evaluate.py L32).

If instrumentation_path is set (SR_INSTRUMENTATION_DIR env var, analysis plan
R1.5), each 'match' invocation appends ONE JSON line
{meta..., day, phase, pid} (json.dumps, sort_keys=True) for the offline
cardinality audit: the harness spawns one process per invocation and chunks
run in separate processes, so the per-pid file name plus the in-line pid field
attribute every line. 'ask' invocations write nothing.

Standard library only (no numpy) - Docker/offline safe. Never prints besides
the protocol response; any protocol defect (unknown phase, non-finite number)
raises so the episode fails loudly instead of corrupting evidence.
"""
import json
import os
import sys


def _append_instrumentation(path, meta, state):
    row = dict(meta or {})          # meta may be None -> counters-free line
    row['day'] = state['day']
    row['phase'] = 'match'          # R1.5 line schema {day, phase, n_*...}
    row['pid'] = os.getpid()
    if os.path.dirname(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'a', encoding='utf-8') as fh:
        fh.write(json.dumps(row, sort_keys=True, allow_nan=False) + '\n')


def run_adapter(ask_fn, match_fn, instrumentation_path=None):
    """Blocking one-request-one-response loop over stdin/stdout until EOF.

    ask_fn(state) -> asks list (a (asks, meta) tuple is also accepted, so the
    same call shape works for both phases); match_fn(state) -> (pairs, meta)
    with meta a dict or None. Response keys are EXACTLY {asks|pairs, memory}
    (evaluate.py L26-42 rejects anything else); memory is the request's own
    memory, unchanged.
    """
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        request = json.loads(line)
        phase = request['phase']
        state = request['state']
        memory = request.get('memory')
        if phase == 'ask':
            outcome = ask_fn(state)
            asks = outcome[0] if isinstance(outcome, tuple) else outcome
            response = {'asks': asks, 'memory': memory}
        elif phase == 'match':
            pairs, meta = match_fn(state)
            if instrumentation_path is not None:
                _append_instrumentation(instrumentation_path, meta, state)
            response = {'pairs': pairs, 'memory': memory}
        else:
            raise ValueError('unknown request phase: %r' % (phase,))
        sys.stdout.write(json.dumps(response, allow_nan=False) + '\n')
        sys.stdout.flush()
