"""Candidate policy: greedy asks + exact-k max-sum-P_hat match (Task 8).

CLI shape mirrors policy_parity.py (evaluate.py L147 always appends
`--baseline <mode>`): --baseline accepts greedy|no_asks|random, default
greedy, and is ACCEPTED BUT IGNORED - this file's identity selects the
candidate behaviour (frozen plan S.8): asks are ALWAYS kit.baseline_asks;
the match phase always runs the exact-k solver over P_hat weights.

match phase (implementation_plan.md Task 8):
  1. edges, degree = sr_features.build_feasible_edges(state)
  2. k = len(kit.baseline_match(state))            (exact greedy cardinality;
     the greedy pair list is also the fallback set)
  3. k == 0 or not edges -> pairs = [], solver never called
  4. P_hat per edge via the FROZEN artifact (results/model_artifact.json,
     sha256 verified at load) in pure-stdlib arithmetic; then
     fc_matching.solve_exact_k(edges, P_hat, k) -> (indices, value, nodes,
     failed). The returned index tuple is the solution ORDER and is NOT
     re-sorted (pair order is part of action_sha256).
  5. failed (node limit) or matching None (infeasible k - impossible since k
     comes from greedy) -> FALL BACK to kit.baseline_match's own k-pair set,
     solver_fallback=1 (+ meta['fallback_reason']); never raises, never emits
     a partial matching.

Instrumentation (plan R1.5): SR_INSTRUMENTATION_DIR, when set, receives one
<pid>.jsonl per match process; absent -> no writes.

Standard library + kit/sr_features/fc_matching only (no numpy - Docker/offline
safe). Never prints besides the protocol response; artifact/contract defects go
to STDERR and exit non-zero so stdout stays a clean protocol channel.
"""
import argparse
import hashlib
import json
import math
import os
import sys
import time
from pathlib import Path

EXPERIMENT = Path(__file__).resolve().parent                    # round2_stagewise_reward
sys.path.insert(0, str(EXPERIMENT))                             # sr_policy_core
sys.path.insert(0, str(EXPERIMENT.parents[1]))                  # repo root: kit
sys.path.insert(0, str(EXPERIMENT / 'scripts'))                 # sr_features
# READ-ONLY solver under test (Task 7); never modified here.
sys.path.insert(0, str(EXPERIMENT.parents[0] / 'round2_fixed_cardinality' / 'scripts'))

import kit                                                       # noqa: E402
from sr_policy_core import run_adapter                           # noqa: E402
from sr_features import build_feasible_edges, extract_pair_features  # noqa: E402
from fc_matching import solve_exact_k                            # noqa: E402

ARTIFACT_PATH = EXPERIMENT / 'results' / 'model_artifact.json'
ARTIFACT_SHA_PATH = EXPERIMENT / 'results' / 'model_artifact.sha256'
STAGE_KEYS = ('s1', 's2', 's3')          # P_hat = p1 * p2 * p3 (sr_train L506-508)


def _load_artifact():
    """Load + sha256-verify the frozen model artifact (path relative to
    __file__). Any defect -> message on STDERR and non-zero exit; stdout is
    the protocol channel and must stay clean."""
    try:
        raw = ARTIFACT_PATH.read_bytes()
        sha_line = ARTIFACT_SHA_PATH.read_text(encoding='ascii').split()
        digest = hashlib.sha256(raw).hexdigest()
        if not sha_line or sha_line[0] != digest:
            raise ValueError('model artifact sha256 mismatch: expected %r, got %s'
                             % (sha_line[0] if sha_line else None, digest))
        art = json.loads(raw.decode('utf-8'))
        n = len(art['features'])
        if n == 0:
            raise ValueError('model artifact has no features')
        for key in STAGE_KEYS:
            stage = art['stages'][key]
            if not (len(stage['w']) == len(stage['mu']) == len(stage['sigma']) == n):
                raise ValueError('stage %s parameter lengths do not match the '
                                 '%d features' % (key, n))
        return art
    except SystemExit:
        raise
    except Exception as exc:                                   # noqa: BLE001
        sys.stderr.write('policy_candidate.py: failed to load model artifact: %s\n'
                         % (exc,))
        raise SystemExit(2)


ARTIFACT = _load_artifact()
_STAGES = [ARTIFACT['stages'][key] for key in STAGE_KEYS]


def _stage_p(stage, x):
    """Mirror of sr_train.predict_stage (L114-124) in pure stdlib: sigmoid of
    the standardised dot product, sigma == 0 treated as 1.0, eta clamped."""
    w, mu, sigma = stage['w'], stage['mu'], stage['sigma']
    eta = float(stage['bias'])
    for i, wi in enumerate(w):
        s = float(sigma[i])
        if s == 0.0:
            s = 1.0
        eta += float(wi) * (float(x[i]) - float(mu[i])) / s
    if eta >= 709.0:
        return 1.0
    if eta <= -709.0:
        return 0.0
    return 1.0 / (1.0 + math.exp(-eta))


def _edge_weight(state, degree, a, b):
    """P_hat(edge) = p1 * p2 * p3 over the 17 frozen S.6 features."""
    x = extract_pair_features(state, degree, a, b)
    p = 1.0
    for stage in _STAGES:
        p *= _stage_p(stage, x)
    return p


def make_ask(mode=None):
    """ask_fn: kit.baseline_asks verbatim regardless of --baseline (frozen
    plan: candidate asks are identical to greedy)."""
    def ask_fn(state):
        return kit.baseline_asks(state), None
    return ask_fn


def match_fn(state):
    """(pairs, meta): exact-k max-sum-P_hat matching with greedy fallback.

    pairs is the solver's own index ORDER (never re-evaluated or re-sorted;
    evaluate.py L93 folds the order into action_sha256). meta carries the
    R1.5 counters; the core adds day/pid when appending instrumentation.
    """
    edges, degree = build_feasible_edges(state)                 # step 1
    started = time.perf_counter()
    greedy = kit.baseline_match(state)                          # step 2 (also fallback)
    k = len(greedy)
    n_edges = len(edges)
    nodes = 0
    fallback = 0
    reason = None
    if k == 0 or not edges:                                     # step 3: no solver call
        pairs = []
    else:
        weights = [_edge_weight(state, degree, a, b) for a, b in edges]   # step 4
        matching, _value, nodes, failed = solve_exact_k(edges, weights, k)
        if failed:                                              # step 5: node limit
            pairs = greedy
            fallback = 1
            reason = 'node_limit'
        elif matching is None:                                  # step 5: infeasible k
            pairs = greedy
            fallback = 1
            reason = 'infeasible_k'
        else:
            pairs = [list(edges[i]) for i in matching]          # solver ORDER kept
    elapsed = time.perf_counter() - started                     # steps 2-5 wall time
    meta = {
        'n_available': sum(1 for m in state['members'] if m['available']),
        'n_edges': n_edges,
        'k_greedy': k,
        'k_chosen': len(pairs),
        'solver_nodes': nodes,
        'solver_fallback': fallback,
        'seconds': elapsed,
    }
    if reason is not None:
        meta['fallback_reason'] = reason
    return pairs, meta


def instrumentation_path():
    directory = os.environ.get('SR_INSTRUMENTATION_DIR')
    if not directory:
        return None
    return os.path.join(directory, '%d.jsonl' % os.getpid())


def build_parser():
    parser = argparse.ArgumentParser(
        description='candidate policy: greedy asks + exact-k max-sum-P_hat '
                    'match (Task 8)')
    parser.add_argument('--baseline', choices=['greedy', 'no_asks', 'random'],
                        default='greedy',
                        help='accepted for evaluate.py CLI compatibility; '
                             'IGNORED - this file\'s identity selects the '
                             'candidate behaviour (asks always greedy)')
    return parser


def main(argv=None):
    build_parser().parse_args(argv)   # --baseline value intentionally unused
    run_adapter(make_ask(), match_fn, instrumentation_path())
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
