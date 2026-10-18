"""Candidate policy: greedy asks + exact-k max-sum-P_hat match (Task 3).

CLI shape mirrors the evaluator (evaluate.py L147 always appends
`--baseline <mode>`): --baseline accepts greedy|no_asks|random, default
greedy, and is ACCEPTED BUT IGNORED - this file's identity selects the
candidate behaviour (frozen plan S.5/S.8): asks are ALWAYS kit.baseline_asks;
the match phase always runs the NEW exact-k solver over P_hat weights.

Match phase (analysis_plan S.4/S.5; implementation_plan policy contract):
  1. edges, degree = sr_features.build_feasible_edges(state)   (same feasible
     graph as the baseline; past pairs already excluded -> repeat-pair
     restrictions preserved by construction).
  2. k = len(kit.baseline_match(state))                        (exact greedy
     cardinality; feasibility is guaranteed because greedy's own k-pair set
     achieves this cardinality on the same graph).
  3. k == 0 or not edges -> pairs = [], solver never called.
  4. P_hat per edge via the FROZEN parent artifact
     (research/round2_stagewise_reward/results/model_artifact.json, sha256
     verified at import) in pure-stdlib arithmetic; then
     srws_solver.solve_exact_k(edges, P_hat, k) -> (indices, meta). The new
     solver returns indices SORTED ASCENDING, so pairs are emitted in
     ascending input-edge index order (plan: "pairs = selected edges in
     ascending input-edge index order").
  5. NO FALLBACK: SolverError / InfeasibleKError / any exception in the match
     phase writes a diagnostic to STDERR and exits 2 (episode fails loudly).
     There is no greedy substitution and no partial matching is ever emitted.

Instrumentation (analysis_plan S.5): env SRS_INSTRUMENTATION_DIR, when set,
receives one <pid>.jsonl per match process; each match line carries
{day, n_edges, k_greedy, k_chosen, solver_seconds, invocation_seconds, pid}
(day/phase/pid added by sr_policy_core). Absent -> no writes.

Standard library + kit/sr_features/srws_solver only (no numpy - Docker/offline
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

EXPERIMENT = Path(__file__).resolve().parent                    # round2_stagewise_reward_solver
REPO_ROOT = EXPERIMENT.parents[1]                               # repo root: kit
PARENT_EXP = EXPERIMENT.parents[0] / 'round2_stagewise_reward'  # frozen parent experiment
sys.path.insert(0, str(EXPERIMENT))                             # sr_policy_core (experiment root)
sys.path.insert(0, str(REPO_ROOT))                              # kit
sys.path.insert(0, str(EXPERIMENT / 'scripts'))                 # sr_features, srws_solver

import kit                                                       # noqa: E402
from sr_policy_core import run_adapter                           # noqa: E402
from sr_features import build_feasible_edges, extract_pair_features  # noqa: E402
from srws_solver import solve_exact_k                            # noqa: E402

ARTIFACT_PATH = PARENT_EXP / 'results' / 'model_artifact.json'
ARTIFACT_SHA_PATH = PARENT_EXP / 'results' / 'model_artifact.sha256'
STAGE_KEYS = ('s1', 's2', 's3')          # P_hat = p1 * p2 * p3 (sr_train L506-508)


def _load_artifact():
    """Load + sha256-verify the FROZEN model artifact (read-only reference to
    the parent experiment). Any defect -> message on STDERR and non-zero exit;
    stdout is the protocol channel and must stay clean."""
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
    """Mirror of sr_train.predict_stage in pure stdlib: sigmoid of the
    standardised dot product, sigma == 0 treated as 1.0, eta clamped."""
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
    """P_hat(edge) = p1 * p2 * p3 over the 17 frozen S.6 features (in [0,1))."""
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
    """(pairs, meta): exact-k max-sum-P_hat matching, NO fallback.

    pairs is the solver's own ASCENDING-INDEX order (evaluate.py L93 folds the
    order into action_sha256). meta carries the S.5 instrumentation counters;
    sr_policy_core adds day/phase/pid when appending the line.
    """
    started = time.perf_counter()
    edges, degree = build_feasible_edges(state)                 # step 1
    k = len(kit.baseline_match(state))                          # step 2
    n_edges = len(edges)
    if k == 0 or not edges:                                     # step 3
        pairs = []
        solver_seconds = 0.0
    else:
        weights = [_edge_weight(state, degree, a, b) for a, b in edges]   # step 4
        t0 = time.perf_counter()
        try:
            indices, _smeta = solve_exact_k(edges, weights, k)
        except Exception as exc:                                # step 5: NO fallback
            sys.stderr.write('policy_candidate.py: solver failure '
                             '(n_edges=%d k=%d): %s: %s\n'
                             % (n_edges, k, type(exc).__name__, exc))
            raise SystemExit(2)
        solver_seconds = time.perf_counter() - t0
        pairs = [list(edges[i]) for i in indices]               # ascending order kept
        if len(pairs) != k:                                     # defensive: exact-k
            sys.stderr.write('policy_candidate.py: solver returned %d pairs, '
                             'expected k=%d\n' % (len(pairs), k))
            raise SystemExit(2)
    invocation_seconds = time.perf_counter() - started
    meta = {
        'n_edges': n_edges,
        'k_greedy': k,
        'k_chosen': len(pairs),
        'solver_seconds': solver_seconds,
        'invocation_seconds': invocation_seconds,
    }
    return pairs, meta


def instrumentation_path():
    directory = os.environ.get('SRS_INSTRUMENTATION_DIR')
    if not directory:
        return None
    return os.path.join(directory, '%d.jsonl' % os.getpid())


def build_parser():
    parser = argparse.ArgumentParser(
        description='candidate policy: greedy asks + exact-k max-sum-P_hat '
                    'match (new polynomial solver)')
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
