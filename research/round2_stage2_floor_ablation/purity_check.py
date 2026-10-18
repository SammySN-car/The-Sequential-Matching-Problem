"""Round 2 Stage 2 - purity verification for the floor ablation (run BEFORE
trusting any ablation result).

Proves Arm B differs from frozen A+C ONLY in floor filtering, on identical
(day-0) states for seeds 101/102/103 x 6 variants:

  P1  frozen policy.py / policy_ac.py hashes match results/artifact.sha256
      (pre-run and post-run); ablation file lives only in this directory
  P2  identical asks on identical states (ask phase)
  P3  identical memory on identical states
  P4  identical pre-floor candidate edge lists INCLUDING model scores
      (same candidate generation AND same scores, by construction)
  P5  floor observed by matcher: frozen = model floor, Arm B = -inf, and the
      predicate `score >= -inf` is tautologically true over real edges
  P6  each arm's matcher result equals a parent-side recomputation of the
      FROZEN matcher with ONLY the floor argument changed (same matcher code)
  P7  every selected pair (both arms) comes from the shared edge list
  P8  frozen arm selects only score >= floor pairs
  P9  ablation_policy.py overrides exactly one policy attribute
      (policy.max_score_matching) - no other behavioral hook

Trajectories diverge after the first differing match, so cross-arm identity is
claimed only on shared states; structurally, candidate generation runs before
the floor is loaded (policy.py:567-584 < 585) and ac_asks never reads floor.
Writes purity.json into this directory only.
"""
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))

import kit     # noqa: E402
import policy  # noqa: E402

VARIANTS = ('development', 'sparse', 'cold_start', 'delayed', 'shift', 'drift')
SEEDS = (101, 102, 103)

checks = []


def chk(name, ok, detail=''):
    checks.append({'check': name, 'pass': bool(ok), 'detail': detail})
    print(('PASS  ' if ok else 'FAIL  ') + name + ((' | ' + detail) if detail else ''),
          flush=True)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def key2(p):
    return tuple(sorted(p[:2]))


def run_child(arm, request):
    proc = subprocess.run(
        [sys.executable, str(HERE / 'purity_child.py'), arm],
        input=json.dumps(request, allow_nan=False).encode(),
        capture_output=True, timeout=60, cwd=str(REPO))
    if proc.returncode != 0:
        raise RuntimeError('child %s failed rc=%d: %s'
                           % (arm, proc.returncode, proc.stderr[:800].decode(errors='replace')))
    return json.loads(proc.stdout.decode('utf-8'))


def main():
    expected = {}
    for line in (REPO / 'results' / 'artifact.sha256').read_text().splitlines():
        h, f = line.split()
        expected[f] = h
    pre = {f: sha(REPO / f) for f in expected}
    chk('P1a frozen hashes match artifact.sha256 before run',
        all(pre[f] == expected[f] for f in expected),
        ' '.join('%s=%s' % (f, pre[f][:12]) for f in sorted(expected)))

    model = policy.load_model()
    assert model is not None, 'frozen model failed to load'
    floor = float(model['floor'])

    ablation_src = (HERE / 'ablation_policy.py').read_text(encoding='utf-8')
    overrides = re.findall(r'^policy\.\w+\s*=', ablation_src, re.M)
    chk('P9 ablation overrides exactly one attribute (policy.max_score_matching)',
        overrides == ['policy.max_score_matching ='], str(overrides))

    rows = []
    for seed in SEEDS:
        for variant in VARIANTS:
            world = kit.generate(seed, 200, 'evaluation', variant)
            sim = kit.Simulator(world)
            state = sim.observe()

            req_ask = {'schema_version': kit.VERSION, 'phase': 'ask',
                       'state': state, 'memory': None}
            a = run_child('frozen', req_ask)
            b = run_child('nofloor', req_ask)

            req_match = {'schema_version': kit.VERSION, 'phase': 'match',
                         'state': state, 'memory': a['response']['memory']}
            am = run_child('frozen', req_match)
            bm = run_child('nofloor', req_match)

            ra, rb = am['rec'], bm['rec']
            ea = [tuple(e) for e in ra.get('edges', [])]
            eb = [tuple(e) for e in rb.get('edges', [])]

            # P6: parent recomputes with the FROZEN matcher, changing ONLY the floor arg
            nodes = ra.get('nodes', [])
            exp_a = policy.max_score_matching(nodes, ea, floor)
            exp_b = policy.max_score_matching(nodes, ea, float('-inf'))

            sel_a = {key2(p) for p in am['response']['pairs']}
            sel_b = {key2(p) for p in bm['response']['pairs']}
            edge_keys = {key2(e) for e in ea}
            score_of = {key2(e): e[2] for e in ea}
            below_b = sum(1 for p in sel_b if score_of.get(p, 0.0) < floor)

            row = {
                'seed': seed, 'variant': variant,
                'same_asks': a['response']['asks'] == b['response']['asks'],
                'same_memory': a['response']['memory'] == b['response']['memory'],
                'same_edges': ea == eb,
                'n_edges': len(ea),
                'matcher_called': ('floor' in ra) and ('floor' in rb),
                'floor_arg_a': ra.get('floor'),
                'floor_arg_b': rb.get('floor'),
                'floor_to_frozen_a': ra.get('floor_to_frozen'),
                'floor_to_frozen_b': rb.get('floor_to_frozen'),
                'tautology': all(e[2] >= float('-inf') for e in ea),
                'match_reprod_a': {key2(e) for e in exp_a} == {key2(e) for e in ra.get('result', [])},
                'match_reprod_b': {key2(e) for e in exp_b} == {key2(e) for e in rb.get('result', [])},
                'subset_a': sel_a <= edge_keys,
                'subset_b': sel_b <= edge_keys,
                'all_above_floor_a': all(score_of[p] >= floor for p in sel_a if p in score_of),
                'sel_a': len(sel_a), 'sel_b': len(sel_b),
                'below_floor_selected_b': below_b,
            }
            rows.append(row)

    allf = lambda k: all(r[k] for r in rows)
    inf = float('inf')
    chk('P2 asks identical on all %d shared day-0 states' % len(rows), allf('same_asks'))
    chk('P3 memory identical on all shared states', allf('same_memory'))
    chk('P4 pre-floor candidate edges + scores identical on all shared states',
        allf('same_edges'), 'n_edges range %d..%d'
            % (min(r['n_edges'] for r in rows), max(r['n_edges'] for r in rows)))
    called = [r for r in rows if r['matcher_called']]
    chk('P5a ac_match passes the SAME floor argument in both arms (call site untouched)',
        len(called) > 0
        and all(r['floor_arg_a'] == floor for r in called)
        and all(r['floor_arg_b'] == floor for r in called),
        'model floor=%.6g' % floor)
    chk('P5b frozen matcher receives model floor (A) vs -inf (B); tautology holds',
        len(called) > 0
        and all(r['floor_to_frozen_a'] == floor for r in called)
        and all(r['floor_to_frozen_b'] == float('-inf') for r in called)
        and all(r['tautology'] for r in called),
        'matcher called on %d/%d states' % (len(called), len(rows)))
    chk('P6 matcher results reproduced by frozen matcher with only-floor change',
        allf('match_reprod_a') and allf('match_reprod_b'))
    chk('P7 every selected pair comes from the shared edge list',
        allf('subset_a') and allf('subset_b'))
    chk('P8 frozen arm selects only score >= floor pairs', allf('all_above_floor_a'))

    post = {f: sha(REPO / f) for f in expected}
    chk('P1b frozen hashes unchanged after run', post == pre,
        ' '.join('%s=%s' % (f, post[f][:12]) for f in sorted(expected)))

    for r in rows:                      # strict-JSON sanitising AFTER all checks ran
        for k in ('floor_arg_a', 'floor_arg_b', 'floor_to_frozen_a', 'floor_to_frozen_b'):
            if r[k] == float('-inf'):
                r[k] = '-inf'

    n_below = sum(r['below_floor_selected_b'] for r in rows)
    out = {
        'schema': 'round2_stage2_floor_ablation_purity_v1',
        'seeds': list(SEEDS), 'variants': list(VARIANTS),
        'model_floor': floor,
        'ablation_overrides': overrides,
        'ablation_source': ablation_src,
        'frozen_hashes_pre': pre, 'frozen_hashes_post': post,
        'artifact_sha256_expected': expected,
        'states': rows,
        'checks': checks,
        'all_pass': all(c['pass'] for c in checks),
        'arm_b_below_floor_selected_total': n_below,
        'note': 'shared-state purity; trajectories diverge after first differing match '
                '(structural argument: cand built before floor load; ac_asks never reads floor)',
    }
    (HERE / 'purity.json').write_text(json.dumps(out, indent=2, sort_keys=True,
                                                 allow_nan=False) + '\n', encoding='utf-8')
    print('BELOW_FLOOR_SELECTED_BY_ARM_B %d (informational)' % n_below)
    print('ALL_PASS', out['all_pass'])
    return 0 if out['all_pass'] else 1


if __name__ == '__main__':
    raise SystemExit(main())