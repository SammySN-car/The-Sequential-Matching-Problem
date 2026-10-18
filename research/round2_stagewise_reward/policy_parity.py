"""Greedy-parity policy: delegates to kit.baseline_asks / kit.baseline_match
through the shared adapter core (Task 4). Behaviour-identical to policy.py's
greedy path - ask L24, match L28, ORDER included - so official evaluate.py
action_sha256 digests must match the default policy exactly on the pilot seed
(scripts/sr_parity_test.py asserts this on seed 40001 x all six variants).
Because the I/O core is shared with the future policy_candidate.py, parity also
proves the candidate's protocol scaffolding (analysis plan S.3 P2/P5).

--baseline accepts greedy|no_asks|random for CLI compatibility with
evaluate.py: 'no_asks' mirrors policy.py L24 (asks = [], matching unchanged);
'random' is NOT supported here - parity evidence only needs greedy/no_asks -
and exits non-zero with a clear message instead of approximating policy.py's
seeded shuffle.

Instrumentation (analysis plan R1.5): SR_INSTRUMENTATION_DIR, when set, receives
one <pid>.jsonl per process; when absent (e.g. parity runs) nothing is written.

Standard library + kit only; never prints besides the protocol response.
"""
import argparse
import itertools
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))          # sr_policy_core
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))     # repo root: kit

import kit
from sr_policy_core import run_adapter


def feasible_edge_count(state):
    """|feasible, not-yet-introduced pairs among available members| - the same
    edge list kit.baseline_match builds internally (kit L211-216), recomputed
    here WITHOUT the SOFT scoring so n_edges is exact and cheap (measured
    ~35 ms per decision state, far below the 10 s invocation limit)."""
    members = [m for m in state['members'] if m['available']]
    past = {tuple(sorted((i['user_a'], i['user_b'])))
            for i in state['introductions']}
    count = 0
    for a, b in itertools.combinations(members, 2):
        key = tuple(sorted((a['member_id'], b['member_id'])))
        if key in past or kit.eligibility(a, b)['status'] != 'feasible':
            continue
        count += 1
    return count


def make_ask(mode):
    """ask_fn: no_asks -> [] (policy.py L24), else kit.baseline_asks verbatim."""
    def ask_fn(state):
        asks = [] if mode == 'no_asks' else kit.baseline_asks(state)
        return asks, None
    return ask_fn


def match_fn(state):
    """match_fn: kit.baseline_match verbatim (never re-sorted - pair ORDER is
    part of action_sha256, evaluate.py L93) plus per-state meta counters."""
    started = time.perf_counter()
    pairs = kit.baseline_match(state)
    elapsed = time.perf_counter() - started   # inference only; n_edges recount is overhead
    meta = {
        'n_available': sum(1 for m in state['members'] if m['available']),
        'n_edges': feasible_edge_count(state),
        'k_greedy': len(pairs),
        'k_chosen': len(pairs),
        'solver_nodes': 0,
        'solver_fallback': 0,
        'seconds': elapsed,
    }
    return pairs, meta


def instrumentation_path():
    directory = os.environ.get('SR_INSTRUMENTATION_DIR')
    if not directory:
        return None
    return os.path.join(directory, '%d.jsonl' % os.getpid())


def build_parser():
    parser = argparse.ArgumentParser(description='greedy-parity policy (Task 4)')
    parser.add_argument('--baseline', choices=['greedy', 'no_asks', 'random'],
                        default='greedy')
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.baseline == 'random':
        raise SystemExit('policy_parity.py: --baseline random is not supported; '
                         'this policy provides greedy/no_asks parity evidence only')
    run_adapter(make_ask(args.baseline), match_fn, instrumentation_path())
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
