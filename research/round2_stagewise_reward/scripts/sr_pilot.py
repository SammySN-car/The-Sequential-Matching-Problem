"""Plumbing-pilot orchestrator P1-P6 + data-quality pilot / N decision
(implementation_plan.md Task 5, analysis_plan.md S.3/S.4).

The orchestrator IS its own test: every step asserts, any failure marks the
step FAIL in results/pilot_report.json and the process exits non-zero.

Two entry points (documented choice: one script, --quality flag; no separate
sr_pilot_quality.py):

  python scripts/sr_pilot.py
      P1 greedy official reference (results/pilot_greedy_official.json; only
         regenerated via evaluate.py if the file is missing)
      P2 parity vs results/pilot_parity_official.json (action_sha256 equal,
         6/6 episodes, seed 40001 x all six variants)
      P3 randomised collection: sr_collect.collect_group(40001, all variants,
         val_from=None) into data/; T-LAB-1 (variant, intro_id) set equality on
         the WRITTEN files; per-variant deterministic replay -> maturity_report
         (T-MAT-1) + full stage-label cross-check against the written rows;
         stage counts consistent (file-derived == collector stats).
      P4 deterministic replay: collect_group(40001, ...) again into a temp dir,
         sha256 of snapshot/label/state files identical to P3.
      P5 protocol smoke: evaluate.py --policy <abs policy_parity.py> --seeds
         40001 --variants all with SR_INSTRUMENTATION_DIR=<temp>; 6/6 valid,
         instrumentation lines exist and k_chosen == k_greedy on every line.
      P6 measurements: in-process vs subprocess seconds/episode, rows written,
         positives per stage, tracemalloc peak around one in-process episode,
         max per-call inference seconds.
      Output: results/pilot_report.json (per-step PASS/FAIL + measurements).

  python scripts/sr_pilot.py --quality
      Collect seeds 40002-40011 (10 groups x 6 variants = 60 episodes) with
      val_from=None into data/ via collect_in_parallel at
      W = min(8, os.cpu_count()) workers. The quality-pilot groups JOIN the
      training pool (analysis plan S.4 table: no model existed yet). From the
      measured in-pool seconds/episode, choose N = largest value in [300,499]
      whose projected collection wall time <= 4 h (14400 s) at W workers, and
      project stage-3 positives at N by linear extrapolation (caveat recorded).
      Output: data/n_decision.json. Exits non-zero (after writing the file,
      gate_s3_projection: FAIL) if the projection is below the plan's 150
      stage-3-positive quality gate, or if even N=300 misses the 4 h budget.

Seed policy: 40001 (plumbing pilot) and 40002-40011 (quality pilot) ONLY.
Final-evaluation seeds 70001-70100 are never touched.

Standard library + repo kit/sr_* only. ASCII output (PYTHONIOENCODING=utf-8).
run_log.txt gets one appended line per entry point run with its key outcome.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path

EXPERIMENT = Path(__file__).resolve().parents[1]   # research/round2_stagewise_reward
REPO_ROOT = EXPERIMENT.parents[1]                  # repo root
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(EXPERIMENT / 'scripts'))
sys.path.insert(0, str(EXPERIMENT))

import kit  # noqa: E402
import sr_collect  # noqa: E402
from sr_collect import (VARIANTS, collect_group, collect_episode,  # noqa: E402
                        collect_in_parallel, merge_group_files)
from sr_features import build_feasible_edges  # noqa: E402
from sr_label import maturity_report, stage_labels  # noqa: E402

SEED = 40001                             # plumbing-pilot seed (S.3)
QUALITY_SEEDS = list(range(40002, 40012))  # quality-pilot groups 40002-40011
DATA_DIR = EXPERIMENT / 'data'
RESULTS_DIR = EXPERIMENT / 'results'
RUN_LOG = EXPERIMENT / 'run_log.txt'
POLICY_PARITY = EXPERIMENT / 'policy_parity.py'
PILOT_REPORT = RESULTS_DIR / 'pilot_report.json'
GREEDY_OFFICIAL = RESULTS_DIR / 'pilot_greedy_official.json'
PARITY_OFFICIAL = RESULTS_DIR / 'pilot_parity_official.json'
N_DECISION = DATA_DIR / 'n_decision.json'
S3_GATE = 150               # plan S.4 quality gate: projected stage-3 positives
BUDGET_SECONDS = 4 * 3600   # 4 h collection wall-time cap (S.4, R1.2)
N_MIN, N_MAX = 300, 499     # predeclared N range (S.4)
RUN_TIMEOUT = 3600          # subprocess evaluate.py safety net
CALLS_PER_EPISODE = 120     # evaluate.py: 60 days x (ask + match) invocations


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _read_jsonl(path):
    with open(path, encoding='utf-8') as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _sub_env(extra=None):
    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    env.pop('SR_INSTRUMENTATION_DIR', None)
    if extra:
        env.update(extra)
    return env


def _append_log(line):
    with open(RUN_LOG, 'a', encoding='utf-8', newline='\n') as fh:
        fh.write('%s %s\n' % (time.strftime('%Y-%m-%d'), line))


def _check_official(path, detail):
    """Shared P1/P2 sanity: 6 episodes, exact (variant, SEED) key set, all
    valid. Returns {variant: row}."""
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    rows = data['episodes']
    assert len(rows) == 6, '%s: expected 6 episodes, got %d' % (path.name, len(rows))
    got = {(r['variant'], r['seed']) for r in rows}
    expected = {(v, SEED) for v in VARIANTS}
    assert got == expected, '%s: episode keys %r != %r' % (path.name, sorted(got), sorted(expected))
    bad = [r['variant'] for r in rows if not r.get('valid')]
    assert not bad, '%s: invalid episodes: %r' % (path.name, bad)
    detail['episodes'] = 6
    detail['all_valid'] = True
    return {r['variant']: r for r in rows}


def replay_episode(seed, variant):
    """Deterministic mirror of sr_collect.collect_episode's simulator loop
    (same RNG seeding, canonical edge sorts and advance order; sr_collect
    L108-180), returning (intros, events) instead of building rows. P4's
    byte-identical replay proves the collector is deterministic, so these
    intros/events are exactly those underlying P3's written rows."""
    world = kit.generate(seed, sr_collect.N, sr_collect.POOL_ID, variant)
    sim = kit.Simulator(world)
    for _day in range(sr_collect.MATCH_DAYS):
        state = sim.observe()
        sim.resolve_asks(kit.baseline_asks(state))
        state = sim.observe()
        edges, _degree = build_feasible_edges(state)
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
        sim.advance([list(e) for e in sorted(chosen)])
    for _ in range(sr_collect.COOLDOWN_DAYS):
        sim.advance([])
    return sim.introductions, sim.events


# --------------------------------------------------------------------------
# plumbing pilot steps P1-P6
# --------------------------------------------------------------------------
def step_p1(ctx):
    """Official greedy reference: verify the Task-4 artifact (only regenerate
    with evaluate.py if it is missing)."""
    detail = {'file': str(GREEDY_OFFICIAL)}
    if not GREEDY_OFFICIAL.exists():
        cmd = [sys.executable, 'evaluate.py', '--seeds', str(SEED),
               '--variants', 'all', '--output', str(GREEDY_OFFICIAL)]
        started = time.time()
        proc = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True,
                              text=True, encoding='utf-8', errors='replace',
                              env=_sub_env(), timeout=RUN_TIMEOUT)
        detail['regenerated'] = True
        detail['regenerate_wall_seconds'] = round(time.time() - started, 3)
        assert proc.returncode == 0, 'evaluate.py rc=%d: %s' % (
            proc.returncode, ascii((proc.stderr or proc.stdout)[-300:]))
    by_variant = _check_official(GREEDY_OFFICIAL, detail)
    detail['action_sha256'] = {v: by_variant[v]['action_sha256'] for v in VARIANTS}
    detail['inference_seconds'] = {v: by_variant[v]['inference_seconds'] for v in VARIANTS}
    return detail


def step_p2(ctx):
    """Parity: the official parity artifact matches P1 on every episode."""
    detail = {'file': str(PARITY_OFFICIAL)}
    assert PARITY_OFFICIAL.exists(), 'missing %s' % PARITY_OFFICIAL
    by_variant = _check_official(PARITY_OFFICIAL, detail)
    greedy = ctx['P1_greedy_official']['action_sha256']
    equal = sum(1 for v in VARIANTS if by_variant[v]['action_sha256'] == greedy[v])
    detail['digests_equal'] = equal
    detail['action_sha256'] = {v: by_variant[v]['action_sha256'] for v in VARIANTS}
    detail['inference_seconds'] = {v: by_variant[v]['inference_seconds'] for v in VARIANTS}
    assert equal == len(VARIANTS), 'action_sha256 parity %d/%d' % (equal, len(VARIANTS))
    return detail


def step_p3(ctx):
    """Randomised collection on the pilot seed + written-file validation:
    T-LAB-1 set equality, per-variant maturity (replay) + full label
    cross-check, stage counts consistent with the collector stats."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    started = time.time()
    stats = collect_group(SEED, VARIANTS, None, DATA_DIR)
    wall = time.time() - started
    merge_group_files(DATA_DIR, [SEED])   # coherent states.jsonl for the pilot seed
    snap_path = DATA_DIR / 'snapshots' / ('seed_%d.jsonl' % SEED)
    label_path = DATA_DIR / 'labels' / ('seed_%d.jsonl' % SEED)
    snaps = _read_jsonl(snap_path)
    labels = _read_jsonl(label_path)
    # T-LAB-1: exactly one snapshot and one label row per (variant, intro_id).
    skeys = [(r['variant'], r['intro_id']) for r in snaps]
    lkeys = [(r['variant'], r['intro_id']) for r in labels]
    assert len(set(skeys)) == len(skeys), 'duplicate (variant, intro_id) in snapshots'
    assert len(set(lkeys)) == len(lkeys), 'duplicate (variant, intro_id) in labels'
    assert set(skeys) == set(lkeys), 'T-LAB-1: snapshot/label key-set mismatch'
    assert len(labels) == stats['intros'] == stats['rows'], \
        'row counts %d/%d != intros %d' % (len(labels), stats['rows'], stats['intros'])
    # Stage counts: label-file-derived positives must equal collector stats.
    positives = {s: sum(1 for r in labels if r[s] == 1) for s in ('s1', 's2', 's3', 'msmi')}
    unknown = {s: sum(1 for r in labels if r[s] == 'UNKNOWN') for s in ('s1', 's2', 's3', 'msmi')}
    not_in_pop = {s: sum(1 for r in labels if r[s] == 'NOT_IN_POPULATION')
                  for s in ('s1', 's2', 's3', 'msmi')}
    for s in ('s1', 's2', 's3', 'msmi'):
        assert positives[s] == stats[s + '_pos'], \
            '%s positives %d != collector %d' % (s, positives[s], stats[s + '_pos'])
    # Per-variant replay: maturity_report (T-MAT-1) + every written label row
    # reproduced from the replayed intros/events.
    label_by_key = {(r['variant'], r['intro_id']): r for r in labels}
    snap_by_key = {(r['variant'], r['intro_id']): r for r in snaps}
    maturity = {}
    for variant in VARIANTS:
        intros, events = replay_episode(SEED, variant)
        report = maturity_report(intros, events)   # raises on any immature label
        maturity[variant] = report['per_stage_max_observed_day']
        n_variant = sum(1 for r in labels if r['variant'] == variant)
        assert len(intros) == n_variant, \
            '%s: replay %d intros != %d label rows' % (variant, len(intros), n_variant)
        for intro in intros:
            key = (variant, intro['introduction_id'])
            written = label_by_key[key]
            lab = stage_labels(intro, events)
            for s in ('s1', 's2', 's3', 'msmi'):
                assert written[s] == lab[s], \
                    '%s/%s: written %s=%r != replayed %r' % (variant, key[1], s, written[s], lab[s])
            assert written['max_observed_day'] == \
                report['per_intro_max_observed_day'][intro['introduction_id']], \
                '%s/%s: max_observed_day mismatch' % (variant, key[1])
            srow = snap_by_key[key]
            assert srow['day'] == intro['assigned_day'], \
                '%s/%s: snapshot day != assigned_day' % (variant, key[1])
            assert sorted(srow['members']) == sorted([intro['user_a'], intro['user_b']]), \
                '%s/%s: snapshot members != intro pair' % (variant, key[1])
    detail = {
        'wall_seconds': round(wall, 3),
        'seconds_per_episode': round(wall / len(VARIANTS), 4),
        'collector_group_seconds': round(stats['seconds'], 3),
        'intros': stats['intros'], 'rows': stats['rows'], 'states': stats['states'],
        'feasible_edges_total': stats['feasible_edges_total'],
        'positives': positives, 'unknown': unknown, 'not_in_population': not_in_pop,
        'maturity_per_stage_max_observed_day': maturity,
        'label_crosscheck': '6/6 variants, %d rows reproduced from deterministic replay' % len(labels),
        'snapshot_file_bytes': snap_path.stat().st_size,
        'label_file_bytes': label_path.stat().st_size,
    }
    return detail


def step_p4(ctx):
    """Deterministic replay: identical collector output, byte for byte."""
    with tempfile.TemporaryDirectory() as tmp:
        collect_group(SEED, VARIANTS, None, Path(tmp))
        hashes_p3, hashes_p4 = {}, {}
        for sub in ('snapshots', 'labels', 'states'):
            name = 'seed_%d.jsonl' % SEED
            hashes_p3[sub] = _sha256_file(DATA_DIR / sub / name)
            hashes_p4[sub] = _sha256_file(Path(tmp) / sub / name)
        for sub in ('snapshots', 'labels'):
            assert hashes_p4[sub] == hashes_p3[sub], \
                'P4: %s hash %s != P3 %s' % (sub, hashes_p4[sub], hashes_p3[sub])
    assert hashes_p4['states'] == hashes_p3['states'], 'P4: states hash mismatch'
    return {'files_identical': True, 'sha256': hashes_p3,
            'files_compared': ['snapshots/seed_%d.jsonl' % SEED,
                               'labels/seed_%d.jsonl' % SEED,
                               'states/seed_%d.jsonl' % SEED]}


def step_p5(ctx):
    """Protocol smoke through the official harness with instrumentation on:
    6/6 valid episodes and k_chosen == k_greedy on every match line."""
    with tempfile.TemporaryDirectory() as tmp:
        instr = Path(tmp) / 'instr'
        instr.mkdir()
        out = Path(tmp) / 'parity_smoke.json'
        env = _sub_env({'SR_INSTRUMENTATION_DIR': str(instr)})
        cmd = [sys.executable, 'evaluate.py', '--policy', str(POLICY_PARITY),
               '--seeds', str(SEED), '--variants', 'all', '--output', str(out)]
        started = time.time()
        proc = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True,
                              text=True, encoding='utf-8', errors='replace',
                              env=env, timeout=RUN_TIMEOUT)
        wall = time.time() - started
        assert proc.returncode == 0, 'evaluate.py rc=%d: %s' % (
            proc.returncode, ascii((proc.stderr or proc.stdout)[-300:]))
        by_variant = _check_official(out, {})
        files = sorted(instr.glob('*.jsonl'))
        assert files, 'no instrumentation files written under %s' % instr
        n_lines = 0
        mismatches = 0
        max_call = 0.0
        for f in files:
            for line in f.read_text(encoding='utf-8').splitlines():
                if not line.strip():
                    continue
                rec = json.loads(line)
                n_lines += 1
                if rec.get('phase') != 'match' or rec.get('k_chosen') != rec.get('k_greedy'):
                    mismatches += 1
                max_call = max(max_call, rec.get('seconds', 0.0))
        expected_lines = len(VARIANTS) * 60   # one match invocation per day per episode
        assert n_lines == expected_lines, \
            'instrumentation lines %d != %d (60 match calls x 6 episodes)' % (n_lines, expected_lines)
        assert mismatches == 0, '%d instrumentation lines with phase != match or k_chosen != k_greedy' % mismatches
        inference_total = sum(by_variant[v]['inference_seconds'] for v in VARIANTS)
        return {
            'wall_seconds': round(wall, 3),
            'seconds_per_episode_wall': round(wall / len(VARIANTS), 3),
            'inference_seconds_total': round(inference_total, 3),
            'inference_seconds_per_episode': round(inference_total / len(VARIANTS), 3),
            'instrumentation_files': len(files),
            'instrumentation_lines': n_lines,
            'k_chosen_eq_k_greedy_all_lines': True,
            'max_per_call_match_seconds': max_call,
        }


def step_p6(ctx):
    """Measurements: in-process vs subprocess seconds/episode, rows written,
    positives per stage, tracemalloc peak around one in-process episode, max
    per-call inference seconds (instrumentation) and per-episode official
    inference totals."""
    p3 = ctx['P3_collection']
    p5 = ctx['P5_protocol_smoke']
    official_inf = []
    for step in ('P1_greedy_official', 'P2_parity'):
        official_inf.extend(ctx[step]['inference_seconds'].values())
    tracemalloc.start()
    episode = collect_episode(SEED, 'development')
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    detail = {
        'in_process_seconds_per_episode': p3['seconds_per_episode'],
        'in_process_seconds_per_episode_basis': 'P3 collect_group wall %.2fs / 6 episodes' % p3['wall_seconds'],
        'subprocess_seconds_per_episode_inference': p5['inference_seconds_per_episode'],
        'subprocess_seconds_per_episode_wall': p5['seconds_per_episode_wall'],
        'subprocess_basis': 'P5 evaluate.py wall %.1fs / 6; inference = sum(inference_seconds)/6' % p5['wall_seconds'],
        'official_max_episode_inference_seconds': round(max(official_inf), 3),
        'official_mean_per_call_inference_seconds': round(max(official_inf) / CALLS_PER_EPISODE, 4),
        'max_per_call_match_seconds_instrumented': p5['max_per_call_match_seconds'],
        'ten_second_invocation_limit_headroom': round(
            10.0 / max(p5['max_per_call_match_seconds'], 1e-9), 1),
        'rows_written': {'snapshots': p3['rows'], 'labels': p3['intros'], 'states': 60 * len(VARIANTS),
                         'note': 'states = 60 decision days x 6 variants for seed %d' % SEED},
        'positives_per_stage': p3['positives'],
        'unknown_per_stage': p3['unknown'],
        'peak_python_memory_bytes_tracemalloc': peak,
        'peak_memory_episode': 'development (one in-process collect_episode)',
        'tracemalloc_episode_intros': episode['intros'],
    }
    return detail


# --------------------------------------------------------------------------
# entry point 1: plumbing pilot
# --------------------------------------------------------------------------
def run_plumbing():
    steps = [('P1_greedy_official', step_p1), ('P2_parity', step_p2),
             ('P3_collection', step_p3), ('P4_deterministic_replay', step_p4),
             ('P5_protocol_smoke', step_p5), ('P6_measurements', step_p6)]
    report = {'task': 5, 'entry_point': 'plumbing_pilot', 'pilot_seed': SEED,
              'variants': list(VARIANTS), 'steps': {}, 'overall': None}
    ctx = {}
    failed_at = None
    for name, fn in steps:
        if failed_at is not None:
            report['steps'][name] = {'status': 'SKIPPED', 'after_failure_in': failed_at}
            continue
        started = time.time()
        try:
            detail = fn(ctx)
            status = 'PASS'
        except Exception as exc:  # noqa: BLE001 - orchestrator reports every failure
            status = 'FAIL'
            failed_at = name
            detail = {'error': '%s: %s' % (type(exc).__name__, ascii(str(exc))[:400])}
        detail['wall_seconds'] = round(time.time() - started, 3)
        report['steps'][name] = dict(detail, status=status)
        ctx[name] = detail
        print('[%s] %s (%.1fs) %s' % (status, name, detail['wall_seconds'],
                                      detail.get('error', '')), flush=True)
    report['overall'] = 'FAIL' if failed_at else 'PASS'
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    PILOT_REPORT.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n',
                            encoding='utf-8', newline='\n')
    if failed_at:
        _append_log('python scripts/sr_pilot.py -> FAIL at %s: %s'
                    % (failed_at, report['steps'][failed_at]['error']))
        print('PLUMBING PILOT FAIL at %s -> %s' % (failed_at, PILOT_REPORT), flush=True)
        return 1
    p3, p6 = report['steps']['P3_collection'], report['steps']['P6_measurements']
    _append_log('python scripts/sr_pilot.py -> P1-P6 PASS (Task 5 plumbing pilot seed %d: '
                'in-process %.2fs/ep, subprocess %.2fs/ep inference, %d intros, '
                's1/s2/s3/msmi positives %d/%d/%d/%d, parity 6/6, replay hashes equal, '
                'peak %.1f MB) -> results/pilot_report.json'
                % (SEED, p6['in_process_seconds_per_episode'],
                   p6['subprocess_seconds_per_episode_inference'], p3['intros'],
                   p3['positives']['s1'], p3['positives']['s2'], p3['positives']['s3'],
                   p3['positives']['msmi'],
                   p6['peak_python_memory_bytes_tracemalloc'] / 1e6))
    print('PLUMBING PILOT PASS -> %s' % PILOT_REPORT, flush=True)
    return 0


# --------------------------------------------------------------------------
# entry point 2: data-quality pilot + N decision
# --------------------------------------------------------------------------
def _label_pool_stats(seeds):
    """Stage positives / UNKNOWN / NOT_IN_POPULATION counts straight from the
    written label files of the given seed groups."""
    positives = {s: 0 for s in ('s1', 's2', 's3', 'msmi')}
    unknown = {s: 0 for s in ('s1', 's2', 's3', 'msmi')}
    not_in_pop = {s: 0 for s in ('s1', 's2', 's3', 'msmi')}
    rows = 0
    for seed in seeds:
        for r in _read_jsonl(DATA_DIR / 'labels' / ('seed_%d.jsonl' % seed)):
            rows += 1
            for s in ('s1', 's2', 's3', 'msmi'):
                if r[s] == 1:
                    positives[s] += 1
                elif r[s] == 'UNKNOWN':
                    unknown[s] += 1
                elif r[s] == 'NOT_IN_POPULATION':
                    not_in_pop[s] += 1
    return {'rows': rows, 'positives': positives, 'unknown': unknown,
            'not_in_population': not_in_pop}


def run_quality():
    seeds = list(QUALITY_SEEDS)
    workers = max(1, min(8, os.cpu_count() or 1))
    print('quality pilot: %d groups x %d variants, W=%d workers, into %s'
          % (len(seeds), len(VARIANTS), workers, DATA_DIR), flush=True)
    started = time.time()
    results, coverage = collect_in_parallel(seeds, VARIANTS, None, DATA_DIR, workers)
    wall = time.time() - started
    total = coverage['total']
    episodes = total['episodes']
    assert episodes == len(seeds) * len(VARIANTS), \
        'expected %d episodes, got %d' % (len(seeds) * len(VARIANTS), episodes)
    seconds_per_episode = wall / episodes          # in-pool, under full W contention
    group_seconds = sorted(r['seconds'] for r in results)
    # Cross-check the label files against the collector's own aggregates.
    pool = _label_pool_stats(seeds)
    assert pool['rows'] == total['intros'], \
        'label rows %d != collector intros %d' % (pool['rows'], total['intros'])
    for s in ('s1', 's2', 's3', 'msmi'):
        assert pool['positives'][s] == total[s + '_pos'], \
            '%s positives %d != collector %d' % (s, pool['positives'][s], total[s + '_pos'])
    # Predeclared N sizing rule (S.4 / R1.2): largest N in [300, 499] whose
    # projected collection wall time at W workers is <= 4 h, projected linearly
    # from the measured in-pool seconds/episode.
    per_group_seconds = len(VARIANTS) * seconds_per_episode
    n_max_fit = int(BUDGET_SECONDS // per_group_seconds)
    runtime_gate = 'PASS' if n_max_fit >= N_MIN else 'FAIL'
    N = min(N_MAX, n_max_fit) if n_max_fit >= N_MIN else N_MIN
    projected_wall = N * per_group_seconds
    s3_rate = total['s3_pos'] / episodes
    projected_s3 = s3_rate * (N * len(VARIANTS))
    s3_gate = 'PASS' if projected_s3 >= S3_GATE else 'FAIL'
    val_from = 40002 + N - int(round(0.2 * N))
    n_val = (40001 + N) - val_from + 1
    decision = {
        'N': N,
        'val_from': val_from,
        'W': workers,
        'seconds_per_episode_measured': round(seconds_per_episode, 4),
        'projected_wall_seconds': round(projected_wall, 1),
        'projected_s3_positives': round(projected_s3, 1),
        'quality_pilot_stats': {
            'seeds': [seeds[0], seeds[-1]], 'groups': len(seeds), 'episodes': episodes,
            'wall_seconds': round(wall, 1),
            'seconds_per_episode_in_pool': round(seconds_per_episode, 4),
            'workers': workers,
            'per_group_seconds_min': round(group_seconds[0], 2),
            'per_group_seconds_max': round(group_seconds[-1], 2),
            'per_group_seconds_mean': round(sum(group_seconds) / len(group_seconds), 2),
            'intros': total['intros'], 'rows': pool['rows'], 'states': total['states'],
            'feasible_edges_total': total['feasible_edges_total'],
            'positives': pool['positives'], 'unknown': pool['unknown'],
            'not_in_population': pool['not_in_population'],
        },
        'train_seed_bounds': {'first': 40002, 'last': 40001 + N, 'count': N},
        'val_seed_bounds': {'first': val_from, 'last': 40001 + N, 'count': n_val},
        'budget_seconds': BUDGET_SECONDS,
        's3_gate_threshold': S3_GATE,
        'gate_runtime_projection': runtime_gate,
        'gate_s3_projection': s3_gate,
        'linear_projection_caveat':
            'Stage-3 positives at N are a LINEAR extrapolation of the 60-episode '
            'quality-pilot rate (%.4f s3/episode over %d episodes); a 10-group pilot '
            'cannot bound group-to-group variance, so treat the projection as an '
            'order-of-magnitude estimate, not a guarantee.' % (s3_rate, episodes),
        'rationale':
            'N = largest value in [%d, %d] whose projected collection wall time at '
            'W=%d workers is <= %d s (4 h). Measured in-pool throughput: %.4f s/episode '
            '(wall %.1f s / %d episodes, full worker contention, seeds %d-%d x 6 '
            'variants, val_from=None). Per-group cost %.2f s x N groups -> projected '
            'wall %.1f s for N=%d (n_max_fit=%d). Stage-3 projection: %.4f positives/'
            'episode x %d episodes = %.1f. Quality-pilot groups %d-%d join the training '
            'pool (no model existed at collection time). val_from = 40002 + N - '
            'round(0.2*N) = %d makes the last ~20%% of the N groups (%d-%d, %d groups) '
            'validation.'
            % (N_MIN, N_MAX, workers, BUDGET_SECONDS, seconds_per_episode, wall,
               episodes, seeds[0], seeds[-1], per_group_seconds, projected_wall, N,
               n_max_fit, s3_rate, N * len(VARIANTS), projected_s3, seeds[0], seeds[-1],
               val_from, val_from, 40001 + N, n_val),
    }
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    N_DECISION.write_text(json.dumps(decision, indent=2, sort_keys=True) + '\n',
                          encoding='utf-8', newline='\n')
    ok = runtime_gate == 'PASS' and s3_gate == 'PASS'
    _append_log('python scripts/sr_pilot.py --quality -> N=%d (val_from=%d, val seeds %d-%d, '
                'W=%d, %.3fs/ep in-pool, projected wall %.0fs <= %d, projected s3 positives '
                '%.1f, gates runtime=%s s3=%s) -> data/n_decision.json'
                % (N, val_from, val_from, 40001 + N, workers, seconds_per_episode,
                   projected_wall, BUDGET_SECONDS, projected_s3, runtime_gate, s3_gate))
    if not ok:
        print('QUALITY PILOT GATE FAIL (runtime=%s s3=%s, projected s3=%.1f < %d)'
              % (runtime_gate, s3_gate, projected_s3, S3_GATE), file=sys.stderr, flush=True)
        print('N decision still written to %s for the controller.' % N_DECISION,
              file=sys.stderr, flush=True)
        return 1
    print('QUALITY PILOT PASS: N=%d, val_from=%d (%d val groups %d-%d), projected wall '
          '%.0fs, projected s3 positives %.1f -> %s'
          % (N, val_from, n_val, val_from, 40001 + N, projected_wall, projected_s3,
             N_DECISION), flush=True)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Task 5 plumbing pilot (P1-P6) and data-quality pilot / N decision')
    parser.add_argument('--quality', action='store_true',
                        help='run the data-quality pilot (seeds 40002-40011) and write '
                             'data/n_decision.json instead of the plumbing pilot')
    args = parser.parse_args(argv)
    if args.quality:
        return run_quality()
    return run_plumbing()


if __name__ == '__main__':
    sys.exit(main())
