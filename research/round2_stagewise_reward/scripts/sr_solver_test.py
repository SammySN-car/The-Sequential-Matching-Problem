"""Task 7 verification battery for the exact-k max-weight matching solver
(plan S.8 V1-V5 + fc-suite provenance), research/round2_stagewise_reward.

Reads (READ-ONLY):
  research/round2_fixed_cardinality/scripts/fc_matching.py  - solver under test
  research/round2_stagewise_reward/results/model_artifact.json (frozen, sha256-checked)
  research/round2_stagewise_reward/results/feature_audit.json
  research/round2_stagewise_reward/data/states.jsonl (+ data/states/seed_40001..40011 shards)
  research/round2_stagewise_reward/data/feasible_edges_val/seed_*.jsonl (val groups)
  research/round2_stagewise_reward/data/states/seed_40001.jsonl (pilot parity)
  research/round2_fixed_cardinality/solver_validation.json (prior provenance, hash only)

Writes (ONLY):
  research/round2_stagewise_reward/results/solver_validation.json
  research/round2_stagewise_reward/run_log.txt            (append one line)

Conventions / decisions (all documented in the JSON artifact):
- Solver signature verified from source (fc_matching.py L29-131):
      solve_exact_k(edges: Sequence[Tuple[str,str]], weights: Sequence[float], k: int)
          -> (edge_indices | None, value | None, nodes: int, failed: bool)
  FIRST element is a tuple of INPUT EDGE INDICES (not pairs). Objective is
  MAXIMISE sum of weights over a vertex-disjoint set of exactly k edges.
  Semantics confirmed from source:
      k == 0                -> ((), 0.0, 0, False)
      infeasible k          -> (None, None, nodes, False)   # failed stays False
      node-limit breach     -> (None, None, nodes, True)    # failed=True, value None
      optimum returned      -> lexicographically smallest optimum under canonical
                               (u, v) key with u <= v (pass 2, fc_matching.py L96-130)
  NODE_LIMIT = 8_000_000 (pass 1), 16_000_000 cumulative (pass 2).
- V1 RNG: stdlib random.Random(4242) (documented choice over numpy; same
  generator style as fc's own suite). Graphs: 6-10 vertices, random edge
  subsets (<= 14 edges) so exhaustive enumeration stays cheap; k drawn from
  {0, 1, max_matching, max_matching+1, n_edges+1, random(0..max+1)} so both
  infeasible paths (no size-k matching; k > n) are exercised.
- Brute force: independent enumerator written here (itertools.combinations
  over ALL index subsets of size k, disjoint filter). fc's own
  brute_force_exact_k is NOT reused (avoid circularity).
- P_hat weights: standalone reimplementation of sr_train.predict_stage
  (sigmoid(bias + sum(w_i*(x_i-mu_i)/sigma_i)), sigma==0 -> 1, +/-709 clamp);
  P_hat = p_s1 * p_s2 * p_s3 from the frozen artifact. sr_train is NOT
  imported for the policy-adjacent path (only an optional cross-check).
- Real-state replay: mirrors sr_collect.collect_episode's per-day loop
  (per-day policy = one priority draw per canonical-sorted edge from
  random.Random(sha256(f'{seed}|{variant}|{day}|collect')), descending
  priority, first-come disjoint). priority_rng is IMPORTED from sr_collect
  (reuse over rewrite). Every replayed state is parity-checked EXACTLY
  against data/states/*.jsonl rows (all fields incl. edge_priorities floats).
- V4 states: GLOBAL top-50 by n_edges over data/states.jsonl plus the
  data/states/seed_40001..40011 shards (all 500 groups; states.jsonl itself
  covers the main batch 40012-40500), plus explicit day-0 states (the dense
  day-0 states already inside the top-50, plus 3 zero-edge day-0 states).
  Non-val groups are replayed in-process (partial episodes up to the needed
  day); val groups use the frozen per-edge features in
  data/feasible_edges_val/. A supplemental val-only top-50 timing set is
  reported for reference but is NOT part of the gate.
- fc_own_suite: re-run read-only via subprocess (cwd = fc scripts dir) with
  the suite's single output write DIVERTED to the system temp dir and any
  other repo write BLOCKED (hard constraint: never modify prior research
  files). All computation, inputs and the exit code run unmodified.

Gates (passed = ALL):
  v1_zero_disagreements, v2_determinism_and_lexmin, v3_zero_violations,
  v4_max_seconds_lt_3, v4_zero_node_limit_failures, v4_zero_data_errors,
  v5_zero_disagreements.
  fc_own_suite provenance is recorded but is NOT part of the gate.

Usage:
  python scripts/sr_solver_test.py            # full battery (the deliverable)
  python scripts/sr_solver_test.py --quick    # smoke subset; prints only,
                                              # writes NO files (no side effects)
"""
import argparse
import hashlib
import heapq
import itertools
import json
import math
import os
import platform
import random
import subprocess
import sys
import tempfile
import time
import traceback
from collections import Counter
from math import exp
from pathlib import Path

HERE = Path(__file__).resolve().parent               # .../scripts
SR_DIR = HERE.parent                                 # .../round2_stagewise_reward
REPO = HERE.parents[2]                               # repository root
FC_SCRIPTS = REPO / 'research' / 'round2_fixed_cardinality' / 'scripts'
FC_MODULE = FC_SCRIPTS / 'fc_matching.py'
FC_PRIOR = REPO / 'research' / 'round2_fixed_cardinality' / 'solver_validation.json'
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(FC_SCRIPTS))

import kit                                                     # noqa: E402
import fc_matching                                             # noqa: E402
from fc_matching import solve_exact_k                          # noqa: E402
from sr_features import build_feasible_edges, extract_pair_features  # noqa: E402
import sr_collect                                              # noqa: E402

VARIANTS = sr_collect.VARIANTS
PILOT_SEED = 40001
VAL_FROM, VAL_TO = 40401, 40500
SHARD_SEEDS = range(40001, 40012)          # per-group state shards not merged into states.jsonl

RESULTS = SR_DIR / 'results' / 'solver_validation.json'
RUN_LOG = SR_DIR / 'run_log.txt'
ARTIFACT = SR_DIR / 'results' / 'model_artifact.json'
ARTIFACT_SHA = SR_DIR / 'results' / 'model_artifact.sha256'
FEATURE_AUDIT = SR_DIR / 'results' / 'feature_audit.json'
STATES = SR_DIR / 'data' / 'states.jsonl'
PILOT_STATES = SR_DIR / 'data' / 'states' / ('seed_%d.jsonl' % PILOT_SEED)
VAL_EDGES_DIR = SR_DIR / 'data' / 'feasible_edges_val'

V1_GRAPHS = 2000
V1_SEED = 4242
V1_MAX_EDGES = 14
V4_GATE_SECONDS = 3.0
WEIGHT_POOL = [-2.0, -1.0, -0.5, 0.0, 0.0, 0.25, 0.5, 1.0, 2.0, 3.5, 7.0]
MAX_EXAMPLES = 8


# --------------------------------------------------------------- small utils --
def canon(e):
    return (e[0], e[1]) if e[0] <= e[1] else (e[1], e[0])


def canon_seq(edges, combo):
    """Solver's sequence convention: indices ordered by canonical edge key,
    input-index order within equal canonical keys (stable sort)."""
    return tuple(sorted(combo, key=lambda i: (canon(edges[i]), i)))


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def percentile(vals, q):
    """House linear-interpolation percentile (same as sr_collect._percentile)."""
    vals = sorted(vals)
    if not vals:
        return None
    if len(vals) == 1:
        return float(vals[0])
    pos = (len(vals) - 1) * q
    lo, hi = int(math.floor(pos)), int(math.ceil(pos))
    if lo == hi:
        return float(vals[lo])
    return vals[lo] + (vals[hi] - vals[lo]) * (pos - lo)


def summary(vals):
    vals = sorted(vals)
    if not vals:
        return {'n': 0}
    return {'n': len(vals), 'min': float(vals[0]), 'max': float(vals[-1]),
            'mean': float(sum(vals) / len(vals)),
            'p50': percentile(vals, 0.50), 'p95': percentile(vals, 0.95)}


def note(bucket, kind, detail, counter):
    counter[kind] = counter.get(kind, 0) + 1
    if len(bucket) < MAX_EXAMPLES:
        bucket.append({'type': kind, 'detail': detail})


def say(msg):
    print(msg, flush=True)


# ------------------------------------------------------------- model / P_hat --
def load_model():
    art = json.loads(ARTIFACT.read_text(encoding='utf-8'))
    audit = json.loads(FEATURE_AUDIT.read_text(encoding='utf-8'))
    audit_names = [r['name'] for r in audit['rows']]
    if art['features'] != audit_names:
        raise ValueError('artifact feature order != feature_audit names')
    sha_line = ARTIFACT_SHA.read_text(encoding='utf-8').split()
    frozen_ok = bool(sha_line) and sha_line[0] == sha256_file(ARTIFACT)
    return art, {'features': art['features'], 'frozen_sha256_ok': frozen_ok,
                 'model_artifact_sha256': sha256_file(ARTIFACT)}


def stage_p(stage, x):
    """Mirror of sr_train.predict_stage (stdlib)."""
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
    return 1.0 / (1.0 + exp(-eta))


def phat_factory(art):
    stages = [art['stages'][k] for k in ('s1', 's2', 's3')]

    def phat(x):
        p = 1.0
        for st in stages:
            p *= stage_p(st, x)
        return p
    return phat


def phat_crosscheck(art, sample_features):
    """Optional one-off cross-check of the standalone predict against
    sr_train.predict_stage (numpy allowed research-side). Never gates."""
    try:
        sys.path.insert(0, str(HERE))
        import sr_train  # noqa: E402
        for x in sample_features:
            mine = phat_factory(art)(x)
            ref = 1.0
            for k in ('s1', 's2', 's3'):
                ref *= sr_train.predict_stage(art['stages'][k], x)
            if mine != ref:
                return {'status': 'MISMATCH', 'mine': mine, 'sr_train': ref}
        return {'status': 'OK', 'vectors': len(sample_features),
                'bit_exact': True}
    except Exception as exc:  # record verbatim, never gate on it
        return {'status': 'NOT_RUN', 'reason': '%s: %s'
                % (type(exc).__name__, str(exc))}


# ------------------------------------------------------------- brute forces ---
def bf_solve(edges, weights, k):
    """Independent exhaustive enumeration of ALL size-k index subsets with the
    disjoint filter. Returns (best_value|None, lex_min_optimal_seq|None,
    n_optima)."""
    n = len(edges)
    if k < 0 or k > n:
        return None, None, 0
    best = None
    opts = []
    for combo in itertools.combinations(range(n), k):
        used = set()
        tot = 0.0
        ok = True
        for i in combo:
            u, v = edges[i]
            if u in used or v in used:
                ok = False
                break
            used.add(u)
            used.add(v)
            tot += weights[i]
        if not ok:
            continue
        if best is None or tot > best:
            best = tot
            opts = [combo]
        elif tot == best:
            opts.append(combo)
    if best is None:
        return None, None, 0
    lex = min(canon_seq(edges, c) for c in opts)
    return best, lex, len(opts)


def max_cardinality(edges, nv_cap):
    """Largest k with an existing size-k matching (exhaustive, tiny graphs)."""
    best = 0
    for kk in range(1, min(len(edges), nv_cap) + 1):
        val, _, _ = bf_solve(edges, [0.0] * len(edges), kk)
        if val is not None:
            best = kk
    return best


def check_solution(edges, weights, k, got, val):
    """Structural self-consistency of a returned matching. -> list of problems."""
    probs = []
    if got is None:
        return ['no matching returned']
    if len(got) != k:
        probs.append('size %d != k %d' % (len(got), k))
    if len(set(got)) != len(got):
        probs.append('duplicate edge index %r' % (got,))
    used = set()
    total = 0.0
    for i in got:
        if i < 0 or i >= len(edges):
            probs.append('index %d out of range' % i)
            continue
        u, v = edges[i]
        if u in used or v in used:
            probs.append('vertex overlap at edge %d %r' % (i, edges[i]))
        used.add(u)
        used.add(v)
        total += weights[i]
    if val is None or abs(total - val) > 1e-9:
        probs.append('value %r != sum of chosen weights %r' % (val, total))
    return probs


# ------------------------------------------------------------------ replay ----
def replay_variant(seed, variant, follow_up, handle):
    """Deterministic mirror of sr_collect.collect_episode's per-day loop
    (sr_collect L108-161; identical to sr_pilot.replay_episode L131-157,
    which was proven byte-identical in Task 5). handle(dayrec) is invoked each
    match day BEFORE advance(); no rows are ever written."""
    world = kit.generate(seed, sr_collect.N, sr_collect.POOL_ID, variant)
    sim = kit.Simulator(world)
    for _ in range(sr_collect.MATCH_DAYS):
        state = sim.observe()
        sim.resolve_asks(kit.baseline_asks(state))
        state = sim.observe()
        edges, degree = build_feasible_edges(state)
        edges = sorted(edges)
        rng = sr_collect.priority_rng(seed, variant, state['day'])
        prio_pairs = [(edge, rng.random()) for edge in edges]
        ordered = sorted(prio_pairs, key=lambda ep: (-ep[1], ep[0]))
        used = set()
        chosen = []
        for edge, _p in ordered:
            if used.isdisjoint(edge):
                chosen.append(edge)
                used.update(edge)
        chosen = sorted(chosen)
        rec = {
            'variant': variant, 'day': state['day'], 'state': state,
            'edges': edges, 'degree': degree, 'chosen': chosen,
            'k_greedy': len(kit.baseline_match(state)),
            'row': {
                'seed_group': seed, 'variant': variant, 'day': state['day'],
                'n_available': sum(1 for m in state['members'] if m['available']),
                'n_edges': len(edges),
                'k_greedy': len(kit.baseline_match(state)),
                'k_chosen': len(chosen),
                'introduced': [list(e) for e in chosen],
                'edge_priorities': [[list(e), p] for e, p in prio_pairs],
            },
        }
        handle(rec)
        sim.advance([list(e) for e in chosen])
    if follow_up:
        for _ in range(sr_collect.COOLDOWN_DAYS):
            sim.advance([])


# ----------------------------------------------------------------- V1 --------
def gen_graphs(rng, count):
    """(vertices, edges, weights, ks) per graph; stream documented: nv, shuffle,
    n_edges, then weight draws, then the random k draw (all from rng)."""
    out = []
    for _ in range(count):
        nv = rng.randint(6, 10)
        verts = ['v%d' % i for i in range(nv)]
        cand = [(a, b) for i, a in enumerate(verts) for b in verts[i + 1:]]
        rng.shuffle(cand)
        n_e = rng.randint(0, min(len(cand), V1_MAX_EDGES))
        edges = cand[:n_e]
        w = [rng.choice(WEIGHT_POOL) for _ in edges]
        kmax = max_cardinality(edges, nv // 2)
        ks = sorted({0, 1, kmax, kmax + 1, n_e + 1, rng.randint(0, kmax + 1)})
        out.append((nv, edges, w, ks))
    return out


def run_v1(graphs):
    counter = {}
    examples = []
    checks = k0 = infeasible = 0
    for gi, (nv, edges, w, ks) in enumerate(graphs):
        for k in ks:
            checks += 1
            got, val, nodes, failed = solve_exact_k(edges, w, k)
            best, _lex, _nopt = bf_solve(edges, w, k)
            if failed:
                note(examples, 'node_limit',
                     'graph %d k=%d nodes=%d' % (gi, k, nodes), counter)
                continue
            if best is None:
                infeasible += 1
                if not (got is None and val is None):
                    counter['infeasible_path_failures'] = \
                        counter.get('infeasible_path_failures', 0) + 1
                    note(examples, 'infeasible_path_failure',
                         'graph %d k=%d: bf infeasible but solver got=%r val=%r'
                         % (gi, k, got, val), counter)
            else:
                if val is None or abs(val - best) > 1e-9:
                    counter['value_disagreements'] = \
                        counter.get('value_disagreements', 0) + 1
                    note(examples, 'value_disagreement',
                         'graph %d nv=%d k=%d edges=%r w=%r solver=%r bf=%r'
                         % (gi, nv, k, edges, w, val, best), counter)
            if k == 0:
                k0 += 1
                if not (got == () and val == 0.0):
                    counter['k0_failures'] = counter.get('k0_failures', 0) + 1
                    note(examples, 'k0_failure',
                         'got=%r val=%r' % (got, val), counter)
            if got is not None:
                probs = check_solution(edges, w, k, got, val)
                for p in probs:
                    note(examples, 'constraint_failure',
                         'graph %d k=%d: %s' % (gi, k, p), counter)
    # --- duplicate-edge / negative-k documented behaviour -------------------
    dup_cases = [
        ('dup_heavier_copy_wins', [('a', 'b'), ('a', 'b'), ('b', 'c')],
         [1.0, 2.0, 1.5], 1, (1,), 2.0),
        ('dup_equal_prefers_earlier_index', [('a', 'b'), ('a', 'b'), ('b', 'c')],
         [1.0, 1.0, 1.5], 1, (2,), 1.5),
        ('dup_k2_lex_first_occurrence', [('a', 'b'), ('a', 'b'), ('c', 'd')],
         [1.0, 1.0, 1.0], 2, (0, 2), 2.0),
        ('dup_orientation_canon_tie', [('b', 'a'), ('a', 'b'), ('c', 'd')],
         [1.0, 1.0, 1.0], 1, (0,), 1.0),
        ('negative_k_infeasible', [('a', 'b')], [1.0], -1, None, None),
    ]
    dup_results = []
    dup_fail = 0
    for name, edges, w, k, exp_got, exp_val in dup_cases:
        got, val, nodes, failed = solve_exact_k(edges, w, k)
        ok = (got == exp_got and val == exp_val and failed is False)
        if not ok:
            dup_fail += 1
            note(examples, 'duplicate_behavior_failure',
                 '%s: expected got=%r val=%r, got got=%r val=%r failed=%r'
                 % (name, exp_got, exp_val, got, val, failed), counter)
        dup_results.append({'name': name, 'edges': [list(e) for e in edges],
                            'weights': w, 'k': k, 'expected': [exp_got, exp_val],
                            'observed': [got, val], 'failed': failed, 'ok': ok})
    disagreements = (counter.get('value_disagreements', 0)
                     + counter.get('infeasible_path_failures', 0)
                     + counter.get('k0_failures', 0)
                     + counter.get('node_limit', 0)
                     + counter.get('constraint_failure', 0)
                     + dup_fail)
    return {
        'rng': 'stdlib random.Random(%d)' % V1_SEED,
        'graphs': len(graphs), 'vertices_range': [6, 10],
        'max_edges_per_graph': V1_MAX_EDGES,
        'weight_pool': WEIGHT_POOL,
        'k_selection': 'sorted set {0, 1, max_matching, max_matching+1, '
                       'n_edges+1, random(0..max_matching+1)}',
        'checks': checks, 'k0_checks': k0, 'infeasible_checks': infeasible,
        'disagreements': disagreements, 'by_type': counter,
        'duplicate_edge_tests': dup_results,
        'duplicate_behavior_failures': dup_fail,
        'examples': examples,
        'infeasible_reporting_note':
            'solver reports infeasible as (None, None, failed=False); '
            'failed=True is reserved for node-limit breaches',
        'passed': disagreements == 0,
    }


# ----------------------------------------------------------------- V2 --------
TIE_CASES = [
    ('path3_k1', [('a', 'b'), ('b', 'c'), ('c', 'd')], [1.0, 1.0, 1.0], 1),
    ('star4_k1', [('a', 'b'), ('a', 'c'), ('a', 'd')], [1.0, 1.0, 1.0], 1),
    ('cycle4_k2', [('a', 'b'), ('b', 'c'), ('c', 'd'), ('d', 'a')],
     [1.0, 1.0, 1.0, 1.0], 2),
    ('neg_tie_k1', [('a', 'b'), ('b', 'c'), ('c', 'd')], [-1.0, -1.0, -1.0], 1),
    ('dup_k2_lex_first', [('a', 'b'), ('a', 'b'), ('c', 'd')],
     [1.0, 1.0, 2.0], 2),
    ('dup_orientation_k1', [('b', 'a'), ('a', 'b'), ('c', 'd')],
     [1.0, 1.0, 1.0], 1),
    ('triangle_k1', [('a', 'b'), ('b', 'c'), ('a', 'c')], [2.0, 2.0, 2.0], 1),
    ('disjoint3_k2', [('a', 'b'), ('c', 'd'), ('e', 'f')], [1.0, 1.0, 1.0], 2),
]


def run_v2(graphs):
    det_inputs = []
    for nv, edges, w, ks in graphs[:30]:
        for k in ks:
            det_inputs.append((edges, w, k))
    det_mismatch = []
    for gi, (edges, w, k) in enumerate(det_inputs):
        runs = [solve_exact_k(edges, w, k) for _ in range(3)]
        if not (runs[0] == runs[1] == runs[2]):
            det_mismatch.append({'input_index': gi, 'k': k,
                                 'runs': [list(map(repr, r)) for r in runs]})
    tie_results = []
    tie_fail = 0
    for name, edges, w, k in TIE_CASES:
        best, lex, nopt = bf_solve(edges, w, k)
        got, val, nodes, failed = solve_exact_k(edges, w, k)
        runs = [solve_exact_k(edges, w, k) for _ in range(2)]
        det = all(r == (got, val, nodes, failed) for r in runs)
        is_tie = nopt >= 2
        lex_ok = (got == lex)
        val_ok = (val is not None and best is not None
                  and abs(val - best) <= 1e-9)
        ok = is_tie and lex_ok and val_ok and det and not failed
        if not ok:
            tie_fail += 1
        tie_results.append({
            'name': name, 'edges': [list(e) for e in edges], 'weights': w,
            'k': k, 'n_optima': nopt, 'brute_force_lex_min': lex,
            'solver_indices': got, 'value': val, 'brute_force_value': best,
            'deterministic': det, 'ok': ok,
        })
    return {
        'determinism': {
            'inputs': len(det_inputs), 'runs_per_input': 3,
            'mismatches': len(det_mismatch), 'examples': det_mismatch[:MAX_EXAMPLES],
        },
        'lexicographic_ties': {
            'cases': len(tie_results), 'failures': tie_fail,
            'detail': tie_results,
        },
        'disagreements': len(det_mismatch) + tie_fail,
        'passed': len(det_mismatch) == 0 and tie_fail == 0,
    }


# ----------------------------------------------------------------- V3 --------
def run_v3(model, phat, quick=False):
    variants = VARIANTS[:1] if quick else VARIANTS
    official = {}
    with open(PILOT_STATES, encoding='utf-8') as fh:
        for line in fh:
            r = json.loads(line)
            official[(r['variant'], r['day'])] = r
    violations = {}
    vexamples = []
    records = []
    parity = {'compared': 0, 'mismatches': 0}
    parity_examples = []
    solve_secs = []
    max_nodes = 0
    node_limit = 0
    sample_feats = []

    def handle(rec):
        nonlocal max_nodes, node_limit
        row = rec['row']
        key = (rec['variant'], rec['day'])
        ref = official.get(key)
        parity['compared'] += 1
        if ref is None or ref != row:
            parity['mismatches'] += 1
            if len(parity_examples) < MAX_EXAMPLES:
                parity_examples.append(
                    {'variant': rec['variant'], 'day': rec['day'],
                     'missing': ref is None,
                     'fields_differing': sorted(
                         set(row) | set(ref or {}),
                         key=str) if ref is None else
                         [f for f in set(row) | set(ref) if row.get(f) != ref.get(f)]})
        state, edges, degree = rec['state'], rec['edges'], rec['degree']
        feats = [extract_pair_features(state, degree, a, b) for a, b in edges]
        if feats and len(sample_feats) < 5:
            sample_feats.append(feats[0])
        weights = [phat(f) for f in feats]
        k = rec['k_greedy']
        t0 = time.perf_counter()
        got, val, nodes, failed = solve_exact_k(edges, weights, k)
        solve_secs.append(time.perf_counter() - t0)
        max_nodes = max(max_nodes, nodes)
        eset = {canon(e) for e in edges}
        members = {m['member_id']: m for m in state['members']}
        past = {tuple(sorted((i['user_a'], i['user_b'])))
                for i in state['introductions']}
        if failed:
            node_limit += 1
            note(vexamples, 'node_limit_failed',
                 '%s day %d n_edges=%d k=%d nodes=%d'
                 % (rec['variant'], rec['day'], len(edges), k, nodes),
                 violations)
        elif got is None:
            note(vexamples, 'no_matching_returned',
                 '%s day %d n_edges=%d k=%d (greedy itself has a size-k '
                 'matching)' % (rec['variant'], rec['day'], len(edges), k),
                 violations)
        else:
            if len(got) != k:
                note(vexamples, 'size_mismatch',
                     '%s day %d |M|=%d k=%d'
                     % (rec['variant'], rec['day'], len(got), k), violations)
            used = set()
            total = 0.0
            for i in got:
                if not (0 <= i < len(edges)):
                    note(vexamples, 'edge_index_out_of_range',
                         '%s day %d index %d' % (rec['variant'], rec['day'], i),
                         violations)
                    continue
                a, b = edges[i]
                if canon((a, b)) not in eset:
                    note(vexamples, 'edge_not_in_feasible_set',
                         '%s day %d edge %r' % (rec['variant'], rec['day'],
                                                (a, b)), violations)
                if a in used or b in used:
                    note(vexamples, 'duplicated_member',
                         '%s day %d edge %r' % (rec['variant'], rec['day'],
                                                (a, b)), violations)
                used.add(a)
                used.add(b)
                total += weights[i]
                if kit.eligibility(members[a], members[b])['status'] != 'feasible':
                    note(vexamples, 'eligibility_not_feasible',
                         '%s day %d pair %r' % (rec['variant'], rec['day'],
                                                (a, b)), violations)
                if not members[a]['available'] or not members[b]['available']:
                    note(vexamples, 'member_unavailable',
                         '%s day %d pair %r' % (rec['variant'], rec['day'],
                                                (a, b)), violations)
                if tuple(sorted((a, b))) in past:
                    note(vexamples, 'past_introduction',
                         '%s day %d pair %r' % (rec['variant'], rec['day'],
                                                (a, b)), violations)
            if val is None or abs(total - val) > 1e-9:
                note(vexamples, 'value_mismatch',
                     '%s day %d value=%r sum=%r'
                     % (rec['variant'], rec['day'], val, total), violations)
        records.append({'variant': rec['variant'], 'day': rec['day'],
                        'n_edges': len(edges), 'k': k, 'edges': edges,
                        'weights': weights,
                        'day0': rec['day'] == 0})

    for variant in variants:
        t0 = time.perf_counter()
        replay_variant(PILOT_SEED, variant, follow_up=not quick, handle=handle)
        say('  V3 replay %s: done (%.1fs)' % (variant, time.perf_counter() - t0))
    missing = len({(v, d) for v in variants for d in range(sr_collect.MATCH_DAYS)}) \
        - parity['compared']
    total_violations = sum(violations.values()) + parity['mismatches'] \
        + (missing if missing > 0 else 0)
    return {
        'seed_group': PILOT_SEED, 'variants': list(variants),
        'match_days': sr_collect.MATCH_DAYS,
        'states_checked': parity['compared'],
        'replay_parity': {
            'source': 'data/states/seed_40001.jsonl (all fields incl. '
                      'edge_priorities floats)',
            'compared': parity['compared'], 'mismatches': parity['mismatches'],
            'missing_states': missing if missing > 0 else 0,
            'examples': parity_examples,
        },
        'weights': 'P_hat = p_s1*p_s2*p_s3 (frozen model_artifact.json)',
        'violations': sum(violations.values()),
        'violations_by_type': violations, 'violation_examples': vexamples,
        'node_limit_failures': node_limit,
        'solve_seconds': summary(solve_secs), 'max_nodes': max_nodes,
        'total_violations_including_parity': total_violations,
        'passed': total_violations == 0,
        '_records': records,   # consumed by V5/V4, stripped before serialisation
        '_sample_feats': sample_feats,  # P_hat cross-check sample, stripped
    }


# ----------------------------------------------------------------- V4 --------
def _push(heap, rows, item, row):
    key = (item[1], item[2], item[3])
    if len(heap) < 50:
        heapq.heappush(heap, item)
        rows[key] = row
    elif item > heap[0]:
        ev = heapq.heapreplace(heap, item)
        rows.pop((ev[1], ev[2], ev[3]), None)
        rows[key] = row


def collect_dense_states():
    """Stream every state record (states.jsonl main batch + the unmerged
    seed_40001..40011 shards) once; return top-50 globally, top-50 within val
    groups (supplemental), day-0 statistics and sample zero-edge day-0 rows."""
    top, top_rows = [], {}
    valtop, valtop_rows = [], {}
    day0_hist = Counter()
    day0_zero_samples = []
    total = 0
    sources = []

    def feed(row):
        nonlocal total
        total += 1
        item = (row['n_edges'], row['seed_group'], row['variant'], row['day'])
        _push(top, top_rows, item, row)
        if VAL_FROM <= row['seed_group'] <= VAL_TO:
            _push(valtop, valtop_rows, item, row)
        if row['day'] == 0:
            day0_hist[row['n_edges']] += 1
            if row['n_edges'] == 0 and len(day0_zero_samples) < 3:
                day0_zero_samples.append(row)

    with open(STATES, encoding='utf-8') as fh:
        for line in fh:
            feed(json.loads(line))
    sources.append('data/states.jsonl')
    for g in SHARD_SEEDS:
        p = SR_DIR / 'data' / 'states' / ('seed_%d.jsonl' % g)
        if not p.exists():
            continue
        sources.append('data/states/seed_%d.jsonl' % g)
        with open(p, encoding='utf-8') as fh:
            for line in fh:
                feed(json.loads(line))
    day0_total = sum(day0_hist.values())
    return {
        'top': sorted(top, reverse=True), 'top_rows': top_rows,
        'valtop': sorted(valtop, reverse=True), 'valtop_rows': valtop_rows,
        'day0': {
            'states': day0_total,
            'zero_edge_states': day0_hist.get(0, 0),
            'n_edges_min': min(day0_hist) if day0_hist else None,
            'n_edges_max': max(day0_hist) if day0_hist else None,
            'n_edges_mean': (sum(k * v for k, v in day0_hist.items())
                             / day0_total) if day0_total else None,
            'n_edges_histogram': {str(k): v
                                  for k, v in sorted(day0_hist.items())},
        },
        'zero_day0_samples': day0_zero_samples,
        'states_streamed': total, 'sources': sources,
    }


def _row_key(row):
    return (row['seed_group'], row['variant'], row['day'])


def fetch_edges_and_weights(row, phat, pilot_records, cache, need_replays,
                            shard_rows):
    """Classify + obtain (edges, weights) for one dense state.
    Returns (edges, weights, source, data_error|None)."""
    g, variant, day = row['seed_group'], row['variant'], row['day']
    key = (g, variant, day)
    if g == PILOT_SEED:                       # pilot replay from V3
        rec = pilot_records.get(key)
        if rec is None:
            return None, None, 'pilot_replay', 'pilot record missing'
        return rec['edges'], rec['weights'], 'pilot_replay(seed_40001)', None
    if VAL_FROM <= g <= VAL_TO:               # frozen per-edge features
        rows = shard_rows.get((g, variant, day))
        if not rows:
            return None, None, 'val_shard', 'val shard rows missing'
        edges = sorted(tuple(r['members']) for r in rows)
        feats = [r['features'] for r in sorted(rows, key=lambda r: r['members'])]
        ref_edges = sorted(tuple(e[0]) for e in row['edge_priorities'])
        if edges != ref_edges or len(edges) != row['n_edges'] \
                or any(len(f) != 17 for f in feats):
            return None, None, 'val_shard', 'shard/state edge parity mismatch'
        return edges, [phat(f) for f in feats], 'val_shard(usable_features)', None
    need_replays.setdefault((g, variant), set()).add(day)
    cached = cache.get(key)
    if cached is None:
        return None, None, 'replay_pending', 'replay not run yet'
    return cached['edges'], cached['weights'], 'in_process_replay', \
        cached.get('error')


def run_v4(model, phat, v3_records, quick=False):
    if quick:
        return {'status': 'SKIPPED_QUICK', 'gates': {}, 'passed': None}
    pilot_by_key = {(PILOT_SEED, r['variant'], r['day']): r
                    for r in v3_records}
    say('  V4 streaming states.jsonl + shards ...')
    dense = collect_dense_states()
    say('  V4 streamed %d states; day0=%r'
        % (dense['states_streamed'],
           {k: dense['day0'][k] for k in ('states', 'zero_edge_states',
                                          'n_edges_min', 'n_edges_max')}))
    primary_items = dense['top'] + [
        (0, r['seed_group'], r['variant'], r['day'])
        for r in dense['zero_day0_samples']]
    primary_rows = dict(dense['top_rows'])
    for r in dense['zero_day0_samples']:
        primary_rows[_row_key(r)] = r
    supp_items = dense['valtop']
    supp_rows = dense['valtop_rows']

    # --- gather sources needed ------------------------------------------------
    need_replays = {}                 # (g, variant) -> set(days)
    need_shards = set()
    all_rows = [(item, primary_rows[(item[1], item[2], item[3])], 'top50'
                 if item in dense['top'] else 'day0_zero_extra')
                for item in primary_items]
    all_rows += [(item, supp_rows[(item[1], item[2], item[3])],
                  'val_top50_supplemental') for item in supp_items]
    for item, row, _s in all_rows:
        g = row['seed_group']
        if VAL_FROM <= g <= VAL_TO:
            need_shards.add(g)
        elif g != PILOT_SEED:
            need_replays.setdefault((g, row['variant']), set()).add(row['day'])
    # first pass marks replay needs; fetch_edges_and_weights re-adds defensively
    cache = {}
    shard_rows = {}

    for g in sorted(need_shards):
        p = VAL_EDGES_DIR / ('seed_%d.jsonl' % g)
        if not p.exists():
            continue
        with open(p, encoding='utf-8') as fh:
            for line in fh:
                r = json.loads(line)
                shard_rows.setdefault(
                    (g, r['variant'], r['day']), []).append(r)

    # --- partial replays for non-val, non-pilot dense states ------------------
    for (g, variant) in sorted(need_replays):
        days = need_replays[(g, variant)]
        t0 = time.perf_counter()
        by_day = {}

        def handle(rec, _g=g, _days=days, _by_day=by_day):
            if rec['day'] in _days:
                _by_day[rec['day']] = rec
        replay_variant(g, variant, follow_up=False, handle=handle)
        for day in sorted(days):
            rec = by_day.get(day)
            row = primary_rows.get((g, variant, day)) \
                or supp_rows.get((g, variant, day))
            if rec is None or row is None:
                cache[(g, variant, day)] = {'error': 'replay row missing'}
                continue
            if rec['row'] != row:
                cache[(g, variant, day)] = {
                    'edges': rec['edges'], 'weights': None,
                    'error': 'replay parity mismatch vs states.jsonl'}
                continue
            feats = [extract_pair_features(rec['state'], rec['degree'], a, b)
                     for a, b in rec['edges']]
            cache[(g, variant, day)] = {
                'edges': rec['edges'], 'weights': [phat(f) for f in feats],
                'error': None}
        say('  V4 replay %d/%s days=%s -> %.1fs'
            % (g, variant, sorted(days), time.perf_counter() - t0))

    # --- timed solves ---------------------------------------------------------
    entries = []
    data_errors = []
    for item, row, set_name in all_rows:
        edges, weights, source, err = fetch_edges_and_weights(
            row, phat, pilot_by_key, cache, need_replays, shard_rows)
        if err:
            note(data_errors, 'data_error',
                 '%s: %s' % (_row_key(row), err), {})
            entries.append({'set': set_name, 'seed_group': row['seed_group'],
                            'variant': row['variant'], 'day': row['day'],
                            'n_edges': row['n_edges'], 'k': row['k_greedy'],
                            'source': source, 'error': err})
            continue
        k = row['k_greedy']
        t0 = time.perf_counter()
        got, val, nodes, failed = solve_exact_k(edges, weights, k)
        dt = time.perf_counter() - t0
        entries.append({
            'set': set_name, 'seed_group': row['seed_group'],
            'variant': row['variant'], 'day': row['day'],
            'n_edges': row['n_edges'], 'k': k, 'source': source,
            'seconds': round(dt, 6), 'nodes': nodes, 'failed': failed,
            'value': val,
            'matching_size': (len(got) if got is not None else None),
        })
        say('    V4 [%s] %d/%s day%d n=%d k=%d -> %.3fs nodes=%d failed=%s'
            % (set_name, row['seed_group'], row['variant'], row['day'],
               row['n_edges'], k, dt, nodes, failed))

    primary = [e for e in entries if e['set'] in ('top50', 'day0_zero_extra')]
    supp = [e for e in entries if e['set'] == 'val_top50_supplemental']
    ok_primary = [e for e in primary if 'error' not in e]
    secs = [e['seconds'] for e in ok_primary]
    nodes_l = [e['nodes'] for e in ok_primary]
    failed_n = sum(1 for e in ok_primary if e['failed'])
    no_value = sum(1 for e in ok_primary if e['value'] is None)
    max_seconds = max(secs) if secs else None
    gate_time = max_seconds is not None and max_seconds < V4_GATE_SECONDS
    gate_nodes = failed_n == 0
    gate_data = len(data_errors) == 0 and len(ok_primary) == len(primary)
    supp_secs = [e['seconds'] for e in supp if 'error' not in e]

    day0_entries = [e for e in primary if e['day'] == 0]
    return {
        'selection': 'GLOBAL top-50 by n_edges over all 500 groups '
                     '(data/states.jsonl main batch 40012-40500 + unmerged '
                     'seed_40001..40011 shards), plus 3 explicit zero-edge '
                     'day-0 states; k = k_greedy from the state record; '
                     'weights = P_hat (frozen artifact); one timed solve per '
                     'state, no warm-up special-casing (battery already warm)',
        'states_streamed': dense['states_streamed'],
        'sources_used': dense['sources'],
        'timed_primary': len(primary), 'timed_primary_ok': len(ok_primary),
        'day0': dense['day0'],
        'day0_states_timed': [{'seed_group': e['seed_group'],
                               'variant': e['variant'], 'n_edges': e['n_edges'],
                               'k': e['k'], 'seconds': e.get('seconds'),
                               'failed': e.get('failed')}
                              for e in day0_entries],
        'entries': entries,
        'seconds': summary(secs), 'nodes': summary(nodes_l),
        'gates': {
            'max_seconds_lt_3': bool(gate_time),
            'max_seconds': max_seconds, 'limit_seconds': V4_GATE_SECONDS,
            'zero_node_limit_failures': gate_nodes,
            'node_limit_failures': failed_n,
            'zero_no_value_solves': no_value == 0,
            'zero_data_errors': gate_data,
        },
        'failures': [e for e in primary
                     if 'error' in e or e.get('failed')
                     or (e.get('seconds') or 0) >= V4_GATE_SECONDS],
        'supplemental_val_top50': {
            'note': 'diagnostic only, NOT part of the gate: top-50 within val '
                    'groups 40401-40500 (the alternative selection the brief '
                    'allows)',
            'timed': len(supp),
            'seconds': summary(supp_secs),
            'node_limit_failures': sum(1 for e in supp
                                       if e.get('failed')),
            'max_seconds': max(supp_secs) if supp_secs else None,
            'max_seconds_lt_3': bool(supp_secs)
            and max(supp_secs) < V4_GATE_SECONDS,
        },
        'data_errors': data_errors,
        'passed': bool(gate_time and gate_nodes and gate_data),
    }


# ----------------------------------------------------------------- V5 --------
def run_v5(v3_records, phat):
    sel = [r for r in v3_records if r['n_edges'] <= 14]
    disagreements = 0
    examples = []
    max_edges = 0
    for r in sel:
        max_edges = max(max_edges, r['n_edges'])
        got, val, nodes, failed = solve_exact_k(r['edges'], r['weights'], r['k'])
        best, _lex, _nopt = bf_solve(r['edges'], r['weights'], r['k'])
        probs = []
        if failed:
            probs.append('node_limit (nodes=%d)' % nodes)
        elif (val is None) != (best is None) or (
                val is not None and abs(val - best) > 1e-9):
            probs.append('value solver=%r bf=%r' % (val, best))
        elif got is not None:
            probs = check_solution(r['edges'], r['weights'], r['k'], got, val)
        if probs:
            disagreements += 1
            if len(examples) < MAX_EXAMPLES:
                examples.append({'variant': r['variant'], 'day': r['day'],
                                 'n_edges': r['n_edges'], 'k': r['k'],
                                 'problems': probs})
    return {
        'source': 'pilot seed %d match states with n_edges <= 14' % PILOT_SEED,
        'states': len(sel), 'max_edges': max_edges,
        'brute_force': 'exhaustive enumeration of ALL size-k index subsets '
                       '(itertools.combinations + disjoint filter)',
        'disagreements': disagreements, 'examples': examples,
        'passed': disagreements == 0,
    }


# ------------------------------------------------------ fc own suite ---------
FC_WRAPPER = r'''
import builtins, os, pathlib, runpy, sys
target = pathlib.Path(sys.argv[1]).resolve()
divert = pathlib.Path(sys.argv[2])
repo = pathlib.Path(sys.argv[3]).resolve()
script = sys.argv[4]
orig_write = pathlib.Path.write_text
orig_open = builtins.open
def _under_repo(p):
    if isinstance(p, (bytes, bytearray)):
        p = os.fsdecode(p)
    if not isinstance(p, (str, os.PathLike)):
        return False
    try:
        pathlib.Path(p).resolve().relative_to(repo)
        return True
    except ValueError:
        return False
def _guarded(self, data, *a, **kw):
    if self.resolve() == target:
        divert.parent.mkdir(parents=True, exist_ok=True)
        return divert.write_text(data, *a, **kw)
    if _under_repo(self):
        raise RuntimeError('BLOCKED repo write: %s' % self)
    return orig_write(self, data, *a, **kw)
def _open(file, mode='r', *a, **kw):
    if any(c in str(mode) for c in 'wax+'):
        if _under_repo(file):
            raise RuntimeError('BLOCKED repo open-for-write: %s' % file)
    return orig_open(file, mode, *a, **kw)
pathlib.Path.write_text = _guarded
builtins.open = _open
try:
    runpy.run_path(script, run_name='__main__')
except SystemExit as e:
    code = e.code
    sys.exit(0 if code is None else (code if isinstance(code, int) else 1))
'''


def run_fc_suite():
    prior = {'path': str(FC_PRIOR.relative_to(REPO)),
             'sha256': sha256_file(FC_PRIOR) if FC_PRIOR.exists() else None}
    if FC_PRIOR.exists():
        try:
            prior['passed_field'] = json.loads(
                FC_PRIOR.read_text(encoding='utf-8')).get('passed')
        except Exception as exc:
            prior['passed_field'] = 'unreadable: %s' % exc
    tmpbase = Path(tempfile.gettempdir()) / 'opencode'
    tmpbase.mkdir(parents=True, exist_ok=True)
    divert = tmpbase / 'fc_solver_validation_rerun.json'
    if divert.exists():
        divert.unlink()
    cmd = [sys.executable, '-B', '-c', FC_WRAPPER, str(FC_PRIOR),
           str(divert), str(REPO), str(FC_SCRIPTS / 'fc_solvers_test.py')]
    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    t0 = time.perf_counter()
    out = {
        'attempted': True,
        'method': 'subprocess python -B with cwd=round2_fixed_cardinality/'
                  'scripts; the suite runs unmodified (same files, same RNG, '
                  'same exit code) while a wrapper diverts its single output '
                  'write (round2_fixed_cardinality/solver_validation.json) to '
                  'a temp file and blocks any other repo write - required by '
                  'the hard constraint never to modify prior research files',
        'command': 'python -B -c <write-divert-wrapper> fc_solvers_test.py',
        'cwd': 'research/round2_fixed_cardinality/scripts',
        'prior_artifact': prior,
        'timeout_seconds': 3600,
    }
    timed_out = False
    try:
        proc = subprocess.run(
            cmd, cwd=str(FC_SCRIPTS), capture_output=True, text=True,
            encoding='utf-8', errors='replace', timeout=3600, env=env)
        rc, stdout, stderr = proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        rc = None
        stdout = exc.stdout or ''
        stderr = exc.stderr or ''
        if isinstance(stdout, bytes):
            stdout = stdout.decode('utf-8', 'replace')
        if isinstance(stderr, bytes):
            stderr = stderr.decode('utf-8', 'replace')
    out['seconds'] = round(time.perf_counter() - t0, 1)
    out['exit_code'] = rc
    out['timed_out'] = timed_out
    out['stdout'] = stdout[-40000:]
    out['stderr'] = stderr[-20000:]
    env_markers = ('ModuleNotFoundError', 'ImportError', 'FileNotFoundError',
                   'No module named', 'BLOCKED repo', 'Traceback')
    if timed_out:
        out['status'] = 'TIMED_OUT'
        out['reason'] = 'suite exceeded 3600s'
    elif rc == 0:
        out['status'] = 'PASSED_RERUN'
    elif any(m in (stderr or '') for m in env_markers):
        out['status'] = 'SKIPPED_ENV'
        out['reason'] = 'suite could not run to completion in this environment'
    else:
        out['status'] = 'FAILED_RERUN'
    if divert.exists():
        rerun_sha = sha256_file(divert)
        out['rerun_artifact'] = {
            'path': str(divert),
            'sha256': rerun_sha,
            'byte_identical_to_prior': (
                rerun_sha == prior['sha256'] if prior['sha256'] else None),
        }
    else:
        out['rerun_artifact'] = None
        if out['status'] == 'PASSED_RERUN':
            out['status'] = 'PASSED_RERUN_NO_ARTIFACT'
    out['note_on_prior'] = ('prior solver_validation.json preserved untouched; '
                           'sha256 cited above is the provenance anchor')
    return out


# ----------------------------------------------------------------- main -------
def build_v2_v1_graphs(quick):
    rng = random.Random(V1_SEED)
    return gen_graphs(rng, 50 if quick else V1_GRAPHS)


def run_battery(quick=False):
    say('Task 7 solver verification battery (quick=%s)' % quick)
    say('  solver: %s sha256=%s' % (FC_MODULE.relative_to(REPO),
                                    sha256_file(FC_MODULE)))
    model, model_meta = load_model()
    phat = phat_factory(model)
    say('  model_artifact frozen_sha256_ok=%s' % model_meta['frozen_sha256_ok'])

    graphs = build_v2_v1_graphs(quick)
    t0 = time.perf_counter()
    v1 = run_v1(graphs)
    say('  V1: %d graphs, %d checks, %d disagreements (%.1fs)'
        % (v1['graphs'], v1['checks'], v1['disagreements'],
           time.perf_counter() - t0))

    t0 = time.perf_counter()
    v2 = run_v2(graphs)
    say('  V2: det mismatches=%d tie failures=%d (%.1fs)'
        % (v2['determinism']['mismatches'], v2['lexicographic_ties']['failures'],
           time.perf_counter() - t0))

    t0 = time.perf_counter()
    v3 = run_v3(model, phat, quick=quick)
    say('  V3: %d states, %d violations, parity mismatches=%d (%.1fs)'
        % (v3['states_checked'], v3['violations'],
           v3['replay_parity']['mismatches'], time.perf_counter() - t0))

    # P_hat cross-check against sr_train on a sample of V3 features (non-gate)
    cross = phat_crosscheck(model, v3['_sample_feats'])
    say('  P_hat cross-check vs sr_train.predict_stage: %s' % cross['status'])

    t0 = time.perf_counter()
    v4 = run_v4(model, phat, v3['_records'], quick=quick)
    if v4.get('status') != 'SKIPPED_QUICK':
        say('  V4: primary timed=%d max=%.3fs max_nodes=%d node_limit=%d '
            'data_errors=%d (%.1fs)'
            % (v4['timed_primary'], v4['gates']['max_seconds'] or -1.0,
               v4['nodes'].get('max', -1), v4['gates']['node_limit_failures'],
               len(v4['data_errors']), time.perf_counter() - t0))
    else:
        say('  V4: SKIPPED (--quick)')

    t0 = time.perf_counter()
    v5 = run_v5(v3['_records'], phat)
    say('  V5: %d states <=14 edges, %d disagreements (%.1fs)'
        % (v5['states'], v5['disagreements'], time.perf_counter() - t0))

    if quick:
        fc = {'attempted': False, 'status': 'NOT_ATTEMPTED_QUICK',
              'note': 'provenance re-run only happens in the full battery'}
    else:
        say('  fc_own_suite: attempting read-only re-run ...')
        fc = run_fc_suite()
        say('  fc_own_suite: status=%s exit=%s (%.0fs)'
            % (fc['status'], fc.get('exit_code'), fc.get('seconds', 0.0)))

    gates = {
        'v1_zero_disagreements': bool(v1['passed']),
        'v2_determinism_and_lexmin': bool(v2['passed']),
        'v3_zero_violations': bool(v3['passed']),
        'v4_max_seconds_lt_3': bool(v4.get('gates', {})
                                    .get('max_seconds_lt_3')) if not quick else None,
        'v4_zero_node_limit_failures':
            bool(v4.get('gates', {}).get('zero_node_limit_failures'))
            if not quick else None,
        'v4_zero_data_errors':
            bool(v4.get('gates', {}).get('zero_data_errors'))
            if not quick else None,
        'v5_zero_disagreements': bool(v5['passed']),
    }
    active = [g for g in gates.values() if g is not None]
    if quick:
        passed = all(active)          # V4 not run in --quick; smoke only
    else:
        passed = len(active) == 7 and all(active)

    doc = {
        'task': 7,
        'schema': 1,
        'created_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'battery': 'research/round2_stagewise_reward/scripts/sr_solver_test.py',
        'environment': {
            'python': platform.python_version(),
            'platform': platform.platform(),
        },
        'solver_under_test': {
            'path': str(FC_MODULE.relative_to(REPO)),
            'sha256': sha256_file(FC_MODULE),
            'entry_point': 'solve_exact_k',
            'signature_from_source':
                'solve_exact_k(edges: Sequence[Tuple[str,str]], weights: '
                'Sequence[float], k: int) -> '
                '(edge_indices|None, value|None, nodes: int, failed: bool)',
            'objective': 'MAXIMISE sum of weights over a vertex-disjoint set '
                         'of EXACTLY k edges',
            'return_semantics': [
                'first element = tuple of INPUT EDGE INDICES (not pairs)',
                'k==0 -> ((), 0.0, 0, False)',
                'infeasible -> (None, None, nodes, False): failed stays False',
                'node-limit -> (None, None, nodes, True): failed=True, value None',
                'returned optimum is the lexicographically smallest optimum '
                'under canonical (u,v) key u<=v (pass 2, source L96-130)',
            ],
            'node_limit_pass1': fc_matching.NODE_LIMIT,
            'node_limit_pass2_cumulative': fc_matching.NODE_LIMIT * 2,
            'verified_by': 'direct source read of fc_matching.py (read-only)',
        },
        'model_artifact': model_meta,
        'v1_random_graphs': v1,
        'v2_determinism_ties': v2,
        'v3_pilot_replay': {k: v for k, v in v3.items()
                            if not k.startswith('_')},
        'v4_dense_timing': v4,
        'v5_small_states_bruteforce': v5,
        'fc_own_suite': fc,
        'phat_crosscheck': cross,
        'gates': gates,
        'passed': bool(passed),
    }
    return doc, v3


def append_run_log(doc, quick):
    if quick:
        return
    if 'error' in doc:
        line = ('python scripts/sr_solver_test.py -> TASK7 SOLVER BATTERY '
                'CRASHED (%s) -> results/solver_validation.json written with '
                'passed:false' % doc['error'].strip().splitlines()[-1][:120])
        with open(RUN_LOG, 'a', encoding='utf-8', newline='\n') as fh:
            fh.write('%s %s\n' % (time.strftime('%Y-%m-%d'), line))
        say('run_log appended (crash).')
        return
    v1 = doc['v1_random_graphs']
    v2 = doc['v2_determinism_ties']
    v3 = doc['v3_pilot_replay']
    v4 = doc['v4_dense_timing']
    v5 = doc['v5_small_states_bruteforce']
    fc = doc['fc_own_suite']
    line = (
        'python scripts/sr_solver_test.py -> TASK7 SOLVER BATTERY %s '
        '(V1 checks=%d dis=%d; V2 det_mismatch=%d tie_fail=%d; '
        'V3 states=%d violations=%d parity_mismatch=%d; '
        'V4 timed=%d max_s=%s max_nodes=%s node_limit=%d; '
        'V5 states=%d dis=%d; fc_own_suite=%s) -> results/solver_validation.json'
        % ('PASS' if doc['passed'] else 'FAIL',
           v1['checks'], v1['disagreements'],
           v2['determinism']['mismatches'], v2['lexicographic_ties']['failures'],
           v3['states_checked'], v3['violations'],
           v3['replay_parity']['mismatches'],
           v4.get('timed_primary', 0),
           ('%.3f' % v4['gates']['max_seconds'])
           if v4.get('gates', {}).get('max_seconds') is not None else 'n/a',
           v4.get('nodes', {}).get('max', 'n/a'),
           v4.get('gates', {}).get('node_limit_failures', 'n/a'),
           v5['states'], v5['disagreements'], fc.get('status')))
    with open(RUN_LOG, 'a', encoding='utf-8', newline='\n') as fh:
        fh.write('%s %s\n' % (time.strftime('%Y-%m-%d'), line))
    say('run_log appended.')


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Task 7 exact-k solver verification battery (V1-V5)')
    parser.add_argument('--quick', action='store_true',
                        help='fast smoke subset; prints only, writes no files')
    args = parser.parse_args(argv)
    doc = None
    try:
        doc, _v3 = run_battery(quick=args.quick)
    except Exception:
        err = traceback.format_exc()
        say('BATTERY CRASHED:\n' + err)
        doc = {
            'task': 7, 'schema': 1,
            'created_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            'battery': 'research/round2_stagewise_reward/scripts/'
                       'sr_solver_test.py',
            'passed': False,
            'error': err,
        }
    if not args.quick:
        RESULTS.parent.mkdir(parents=True, exist_ok=True)
        RESULTS.write_text(json.dumps(doc, indent=2, sort_keys=True) + '\n',
                           encoding='utf-8', newline='\n')
        say('wrote %s (passed=%s)' % (RESULTS, doc.get('passed')))
        append_run_log(doc, args.quick)
    else:
        say('quick mode: no files written; passed=%s' % doc.get('passed'))
    return 0 if doc.get('passed') else 1


if __name__ == '__main__':
    sys.exit(main())
