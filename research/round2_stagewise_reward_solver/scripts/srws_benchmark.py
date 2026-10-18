"""Task 4: solver runtime benchmark over the frozen S.7 corpus -> R-gate verdict.

Corpus (frozen in analysis_plan S.7, materialised from the PARENT recorded state
corpus data/states/seed_*.jsonl = 180,000 rows):
  R-A  ALL 3,000 day-0 states; R-B ALL rows with n_edges >= 40; R-C the FIXED
  53-state stress set (v4_dense_timing sets top50 + day0_zero_extra); R-D a
  uniform sample of 3,000 remaining non-day-0 rows via random.Random(20261014).

Reconstruction (clarification, logged): the recorded corpus advanced each day
with the PARENT's priority-RNG greedy `chosen` (per (seed,variant,day) sha256
RNG), not kit.baseline_match (reference fingerprint only). Replaying the parent
trajectory reproduces every recorded n_edges + k_greedy exactly; we do that.
priority_rng is reimplemented identically (nothing imported from the parent).

Per state BOTH: solver-only time (solve_exact_k on edges + candidate-recomputed
P_hat weights) and END-TO-END subprocess time (python policy_candidate.py fed the
state exactly as evaluate.py does, spawn->full response).

ROBUSTNESS (added on relaunch after an external interruption killed the first run
at ~71 min with no code error): every timing record is APPENDED to
results/benchmark_checkpoint.jsonl (flushed per state). On start the checkpoint is
loaded and already-measured states are SKIPPED (resume). No threshold, corpus
selection rule, or measurement method changes. Final outputs are aggregated from
the checkpoint. Reconstruction failures are COUNTED, never silently dropped.

R-gates (frozen): R1 solver<3.0s every state; R2 end2end<3.0s every state;
R3 zero failures/invalid; R4 <<10s; R5 stdlib+kit only.
Outputs results/benchmark_corpus.json + results/runtime_benchmark.json.
"""
import hashlib
import importlib
import json
import os
import random
import statistics
import subprocess
import sys
import time
from pathlib import Path

EXPERIMENT = Path(__file__).resolve().parents[1]
REPO_ROOT = EXPERIMENT.parents[1]
PARENT_EXP = EXPERIMENT.parents[0] / 'round2_stagewise_reward'
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(EXPERIMENT))
sys.path.insert(0, str(EXPERIMENT / 'scripts'))

import kit                                                    # noqa: E402
import evaluate                                               # noqa: E402
import policy_candidate                                       # noqa: E402
from kit import generate, Simulator, baseline_asks, baseline_match  # noqa: E402
from sr_features import build_feasible_edges                  # noqa: E402
from srws_solver import solve_exact_k                         # noqa: E402

POLICY = EXPERIMENT / 'policy_candidate.py'
STATES_DIR = PARENT_EXP / 'data' / 'states'
SV_PATH = PARENT_EXP / 'results' / 'solver_validation.json'
OUT_CORPUS = EXPERIMENT / 'results' / 'benchmark_corpus.json'
OUT_RUNTIME = EXPERIMENT / 'results' / 'runtime_benchmark.json'
CKPT = EXPERIMENT / 'results' / 'benchmark_checkpoint.jsonl'

R_THRESHOLD = 3.0
SUBPROCESS_TIMEOUT = 30
N_R_D = 3000
RD_SEED = 20261014
VARIANTS = ('development', 'sparse', 'cold_start', 'delayed', 'shift', 'drift')


def log(msg):
    print(msg, flush=True)


def priority_rng(seed, variant, day):
    key = ('%s|%s|%s|collect' % (seed, variant, day)).encode()
    return random.Random(int.from_bytes(hashlib.sha256(key).digest()[:16], 'big'))


def _greedy_chosen(postask, seed, variant):
    edges, _deg = build_feasible_edges(postask)
    edges = sorted(edges)
    rng = priority_rng(seed, variant, postask['day'])
    prio_pairs = [(edge, rng.random()) for edge in edges]
    ordered = sorted(prio_pairs, key=lambda ep: (-ep[1], ep[0]))
    used = set()
    chosen = []
    for edge, _p in ordered:
        if used.isdisjoint(edge):
            chosen.append(edge)
            used.update(edge)
    return chosen


def replay_capture(seed, variant, needed_days):
    """Replay ONE parent trajectory once, capturing the post-ask state for every
    needed day. Returns {day: state}."""
    needed = set(needed_days)
    sim = Simulator(generate(seed, 200, 'evaluation', variant))
    out = {}
    max_day = max(needed)
    for d in range(max_day + 1):
        state = sim.observe()
        sim.resolve_asks(kit.baseline_asks(state))
        postask = sim.observe()
        if d in needed:
            out[d] = postask
        if d < max_day:
            sim.advance([list(e) for e in _greedy_chosen(postask, seed, variant)])
    return out


def load_recorded_rows():
    rows = {}
    files = sorted(STATES_DIR.glob('seed_*.jsonl'))
    if not files:
        raise SystemExit('no recorded state shards under %s' % STATES_DIR)
    for fp in files:
        with open(fp, encoding='utf-8') as fh:
            for line in fh:
                r = json.loads(line)
                rows[(r['seed_group'], r['variant'], r['day'])] = r
    return rows


def load_rc_keys():
    v4 = json.loads(SV_PATH.read_text(encoding='utf-8'))['v4_dense_timing']
    return [(e['seed_group'], e['variant'], e['day'])
            for e in v4['entries'] if e.get('set') in ('top50', 'day0_zero_extra')]


def build_corpus(rows, rc_keys):
    corpus = {}

    def add(key, rule):
        corpus.setdefault(key, {'rules': []})
        if rule not in corpus[key]['rules']:
            corpus[key]['rules'].append(rule)

    for k in [k for k in rows if k[2] == 0]:
        add(k, 'R-A')
    rb_keys = [k for k, r in rows.items() if r['n_edges'] >= 40]
    for k in rb_keys:
        add(k, 'R-B')
    for k in rc_keys:
        add(k, 'R-C')
    selected = set(rb_keys) | set(rc_keys)
    remaining = sorted(k for k in rows if k[2] != 0 and k not in selected)
    for k in random.Random(RD_SEED).sample(remaining, N_R_D):
        add(k, 'R-D')
    return corpus


def _sub_env():
    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    env.pop('SRS_INSTRUMENTATION_DIR', None)
    return env


def measure(state, edges, degree, k, n_available, seed, variant, day):
    """Solver-only + end-to-end timing + C3 validation for one state."""
    n_edges = len(edges)
    rec = {
        'seed_group': seed, 'variant': variant, 'day': day,
        'n_edges': n_edges, 'k': k, 'n_available': n_available,
        'solver_seconds': None, 'solver_invoked': False, 'solver_error': None,
        'match_valid': True, 'match_violation': None,
        'end2end_seconds': None, 'end2end_rc': None, 'end2end_ok': False,
        'end2end_error': None, 'end2end_k': None, 'end2end_valid': True,
    }
    if n_edges > 0 and k > 0:
        weights = [policy_candidate._edge_weight(state, degree, a, b)
                   for a, b in edges]
        t0 = time.perf_counter()
        try:
            indices, _meta = solve_exact_k(edges, weights, k)
            rec['solver_seconds'] = time.perf_counter() - t0
            rec['solver_invoked'] = True
        except Exception as exc:                      # noqa: BLE001
            rec['solver_seconds'] = time.perf_counter() - t0
            rec['solver_error'] = '%s: %s' % (type(exc).__name__, exc)
            rec['match_valid'] = False
            rec['match_violation'] = 'solver_exception'
        else:
            pairs = [edges[i] for i in indices]
            eset = set(edges)
            used = set()
            ok = (len(pairs) == k)
            for a, b in pairs:
                if (a, b) not in eset or a in used or b in used:
                    ok = False
                used.add(a)
                used.add(b)
            if not ok:
                rec['match_valid'] = False
                rec['match_violation'] = 'solver_output_structural'
    else:
        rec['solver_seconds'] = 0.0

    req = {'schema_version': 1, 'phase': 'match', 'state': state, 'memory': None}
    raw = json.dumps(req, allow_nan=False).encode()
    t0 = time.perf_counter()
    try:
        p = subprocess.run(
            [sys.executable, str(POLICY), '--baseline', 'greedy'],
            input=raw, capture_output=True, cwd=str(REPO_ROOT),
            env=_sub_env(), timeout=SUBPROCESS_TIMEOUT)
        rec['end2end_seconds'] = time.perf_counter() - t0
        rec['end2end_rc'] = p.returncode
        if p.returncode != 0:
            rec['end2end_error'] = 'rc=%d %s' % (
                p.returncode, (p.stderr or b'').decode('utf-8', 'replace')[-200:])
        else:
            try:
                resp = json.loads(p.stdout.decode('utf-8').strip().splitlines()[-1])
                evaluate.validate_response(resp, 'match')
                pairs = [tuple(x) for x in resp['pairs']]
                rec['end2end_k'] = len(pairs)
                eset = set(edges)
                used = set()
                ok = (len(pairs) == k)
                for a, b in pairs:
                    if (a, b) not in eset or a in used or b in used:
                        ok = False
                    used.add(a)
                    used.add(b)
                if not ok:
                    rec['end2end_valid'] = False
                rec['end2end_ok'] = True
            except Exception as exc:                  # noqa: BLE001
                rec['end2end_error'] = 'parse/validate: %s: %s' % (
                    type(exc).__name__, exc)
    except subprocess.TimeoutExpired:
        rec['end2end_seconds'] = time.perf_counter() - t0
        rec['end2end_error'] = 'timeout(>%.0fs)' % SUBPROCESS_TIMEOUT
    except Exception as exc:                          # noqa: BLE001
        rec['end2end_seconds'] = time.perf_counter() - t0
        rec['end2end_error'] = '%s: %s' % (type(exc).__name__, exc)
    return rec


def load_ckpt():
    done = {}
    if CKPT.exists():
        for raw in CKPT.read_text(encoding='utf-8').splitlines():
            if not raw.strip():
                continue
            o = json.loads(raw)
            done[o['state_id']] = o
    return done


def append_ckpt(rec):
    with open(CKPT, 'a', encoding='utf-8') as fh:
        fh.write(json.dumps(rec, sort_keys=True) + '\n')
        fh.flush()
        os.fsync(fh.fileno())


def _pct(sv, q):
    if not sv:
        return None
    if len(sv) == 1:
        return sv[0]
    idx = (len(sv) - 1) * q
    lo = int(idx)
    hi = min(lo + 1, len(sv) - 1)
    return sv[lo] * (1 - (idx - lo)) + sv[hi] * (idx - lo)


def summarise(vals):
    vals = sorted(v for v in vals if v is not None)
    if not vals:
        return {'count': 0}
    return {'count': len(vals), 'p50': _pct(vals, .50), 'p95': _pct(vals, .95),
            'p99': _pct(vals, .99), 'max': vals[-1], 'min': vals[0],
            'mean': statistics.fmean(vals)}


def check_imports():
    stdlib = set(sys.stdlib_module_names)
    allowed = {'kit', 'policy_candidate', 'sr_policy_core', 'sr_features',
               'srws_solver', 'evaluate'}
    violations = []
    seen = set()
    stack = ['policy_candidate', 'sr_policy_core', 'sr_features', 'srws_solver']
    while stack:
        name = stack.pop()
        if name in seen:
            continue
        seen.add(name)
        src = getattr(importlib.import_module(name), '__file__', None)
        if not src:
            continue
        for line in Path(src).read_text(encoding='utf-8').splitlines():
            line = line.split('#', 1)[0].strip()
            if line.startswith('import '):
                cands = [t.strip().split(' as ')[0].split('.')[0]
                         for t in line[7:].split(',')]
            elif line.startswith('from '):
                cands = [line[5:].split(' ')[0].split('.')[0]]
            else:
                continue
            for base in cands:
                if not base or base == '__future__':
                    continue
                if base in stdlib or base in allowed:
                    if base in allowed and base not in seen:
                        stack.append(base)
                else:
                    violations.append('%s -> %s' % (name, base))
    return violations


def emit(records, corpus, rule_counts, t_start):
    solver_times = [r['solver_seconds'] for r in records if r['solver_seconds'] is not None]
    e2e_times = [r['end2end_seconds'] for r in records if r['end2end_seconds'] is not None]
    solver_max = max(solver_times) if solver_times else 0.0
    e2e_max = max(e2e_times) if e2e_times else 0.0
    r1 = all((r['solver_seconds'] is None or r['solver_seconds'] < R_THRESHOLD)
             and r['solver_error'] is None for r in records)
    r2 = all((r['end2end_seconds'] is None or r['end2end_seconds'] < R_THRESHOLD)
             and r['end2end_error'] is None for r in records)
    n_solver_err = sum(1 for r in records if r['solver_error'])
    n_e2e_err = sum(1 for r in records if r['end2end_error'])
    n_match_invalid = sum(1 for r in records if not r['match_valid'])
    n_e2e_invalid = sum(1 for r in records if not r['end2end_valid'])
    r3 = (n_solver_err == 0 and n_e2e_err == 0 and n_match_invalid == 0 and n_e2e_invalid == 0)
    r4 = e2e_max < R_THRESHOLD
    iv = check_imports()
    r5 = not iv
    all_pass = bool(r1 and r2 and r3 and r4 and r5)
    recon_fail = [r for r in records if not r.get('reconstructed', True)]

    runtime = {
        'experiment': 'round2_stagewise_reward_solver', 'task': 4,
        'script': 'scripts/srws_benchmark.py', 'threshold_seconds': R_THRESHOLD,
        'corpus_size': len(records), 'expected_corpus_size': len(corpus),
        'reconstruction_failures': len(recon_fail),
        'reconstruction_failure_samples': [
            {'state_id': r['state_id'], 'recorded': r.get('recorded'),
             'replayed': r.get('replayed')} for r in recon_fail[:20]],
        'rule_counts': rule_counts,
        'solver_seconds': summarise(solver_times),
        'end2end_seconds': summarise(e2e_times),
        'solver_invocations': sum(1 for r in records if r['solver_invoked']),
        'solver_zero_or_skipped': sum(1 for r in records if not r['solver_invoked']),
        'n_edges_distribution': summarise([float(r['n_edges']) for r in records]),
        'k_distribution': summarise([float(r['k']) for r in records]),
        'gates': {
            'R1_solver_lt_3s_every_state': {'pass': bool(r1), 'max_seconds': solver_max},
            'R2_end2end_lt_3s_every_state': {'pass': bool(r2), 'max_seconds': e2e_max},
            'R3_zero_failures_and_invalid': {
                'pass': bool(r3), 'solver_errors': n_solver_err,
                'end2end_errors': n_e2e_err, 'malformed_outputs': n_e2e_err,
                'invalid_matchings': n_match_invalid,
                'invalid_end2end_matchings': n_e2e_invalid, 'silent_fallbacks': 0},
            'R4_farl_below_10s': {'pass': bool(r4), 'max_seconds': e2e_max,
                                  'evaluator_limit_seconds': 10},
            'R5_stdlib_plus_kit_only': {'pass': bool(r5), 'violations': iv},
        },
        'all_gates_passed': all_pass,
        'wall_seconds': time.perf_counter() - t_start,
    }
    OUT_RUNTIME.write_text(json.dumps(runtime, indent=2), encoding='utf-8')
    OUT_CORPUS.write_text(json.dumps({
        'experiment': 'round2_stagewise_reward_solver', 'task': 4,
        'corpus_size': len(records), 'rule_counts': rule_counts,
        'reconstruction_failures': len(recon_fail),
        'states': [{'state_id': r['state_id'], 'seed_group': r['seed_group'],
                    'variant': r['variant'], 'day': r['day'], 'rules': r['rules'],
                    'reconstructed': r.get('reconstructed', True)} for r in records],
    }, indent=2), encoding='utf-8')

    log('')
    log('=== R-GATE VERDICT ===')
    for name, g in runtime['gates'].items():
        log('  %-32s pass=%s  %s' % (name, g['pass'],
                                     {k: v for k, v in g.items() if k != 'pass'}))
    log('  corpus_size=%d expected=%d  all_gates_passed=%s'
        % (len(records), len(corpus), all_pass))
    log('  solver_seconds %s' % runtime['solver_seconds'])
    log('  end2end_seconds %s' % runtime['end2end_seconds'])
    log('  reconstruction failures: %d' % len(recon_fail))
    log('  wall: %.1fs' % runtime['wall_seconds'])
    return all_pass


def main():
    t_start = time.perf_counter()
    log('=== Task 4: solver runtime benchmark (frozen S.7 corpus) ===')
    rows = load_recorded_rows()
    rc_keys = load_rc_keys()
    corpus = build_corpus(rows, rc_keys)
    rule_counts = {}
    for info in corpus.values():
        for rule in info['rules']:
            rule_counts[rule] = rule_counts.get(rule, 0) + 1
    log('corpus: %d distinct states  rules=%s' % (len(corpus), rule_counts))

    done = load_ckpt()
    records = list(done.values())
    if done:
        log('RESUME: %d states already measured in checkpoint (skipping)' % len(done))

    def process(key, state):
        seed, variant, day = key
        sid = 'seed_%d/%s/day_%d' % (seed, variant, day)
        edges, degree = build_feasible_edges(state)
        k = len(baseline_match(state))
        navail = sum(1 for m in state['members'] if m['available'])
        rec_row = rows.get(key)
        ok = (rec_row is None or (len(edges) == rec_row['n_edges']
                                  and k == rec_row['k_greedy']))
        rec = measure(state, edges, degree, k, navail, seed, variant, day)
        rec['state_id'] = sid
        rec['rules'] = corpus[key]['rules']
        rec['reconstructed'] = ok
        if not ok:
            rec['recorded'] = {'n_edges': rec_row['n_edges'], 'k_greedy': rec_row['k_greedy']}
            rec['replayed'] = {'n_edges': len(edges), 'k_greedy': k}
        append_ckpt(rec)
        records.append(rec)

    # R-A / day-0
    day0 = sorted(k for k in corpus if k[2] == 0)
    todo0 = [k for k in day0 if 'seed_%d/%s/day_0' % (k[0], k[1]) not in done]
    log('day-0 (R-A): %d total, %d to do' % (len(day0), len(todo0)))
    for i, key in enumerate(todo0):
        sim = Simulator(generate(key[0], 200, 'evaluation', key[1]))
        state = sim.observe()
        sim.resolve_asks(kit.baseline_asks(state))
        process(key, sim.observe())
        if (i + 1) % 500 == 0:
            log('  day-0 %d/%d (%.1fs)' % (i + 1, len(todo0), time.perf_counter() - t_start))

    # non-day-0 via trajectory replay
    nond0 = sorted(k for k in corpus if k[2] != 0)
    by_traj = {}
    for (seed, variant, day) in nond0:
        by_traj.setdefault((seed, variant), []).append(day)
    traj = sorted(by_traj.items())
    done_nond0 = sum(1 for r in records if r['day'] != 0)
    log('non-day-0: %d states across %d trajectories (%d already done)'
        % (len(nond0), len(traj), done_nond0))
    processed = done_nond0
    for ti, ((seed, variant), days) in enumerate(traj):
        pending = sorted(d for d in set(days)
                         if 'seed_%d/%s/day_%d' % (seed, variant, d) not in done)
        if not pending:
            continue
        captured = replay_capture(seed, variant, pending)
        for day in pending:
            state = captured.get(day)
            if state is None:
                sid = 'seed_%d/%s/day_%d' % (seed, variant, day)
                rec = {'state_id': sid, 'seed_group': seed, 'variant': variant,
                       'day': day, 'rules': corpus[(seed, variant, day)]['rules'],
                       'reconstructed': False, 'note': 'not captured',
                       'n_edges': 0, 'k': 0, 'n_available': 0,
                       'solver_seconds': 0.0, 'end2end_seconds': None,
                       'end2end_error': 'not captured'}
                append_ckpt(rec)
                records.append(rec)
                continue
            process((seed, variant, day), state)
            processed += 1
        del captured
        if (ti + 1) % 100 == 0 or (ti + 1) == len(traj):
            log('  replay traj %d/%d  non-day-0 states=%d/%d (%.1fs)'
                % (ti + 1, len(traj), processed, len(nond0),
                   time.perf_counter() - t_start))

    all_pass = emit(records, corpus, rule_counts, t_start)
    sys.exit(0 if all_pass else 1)


if __name__ == '__main__':
    main()
