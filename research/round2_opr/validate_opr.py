"""Phase 3b OPR validation driver. Research-only; never imported by policy.

Stages (see validation_plan.md, frozen preregistration):
  d1  diagnostics D-A..D-E on the 126 sealed control worlds -> validation_d1.json
  d2  digest-verified C/E1 replay + G4 variance-reduction   -> validation_d2.json
  all run both stages, apply the preregistered gate         -> validation_results.json

Run from the repository root:  python research/round2_opr/validate_opr.py --stage d1
"""

import argparse
import hashlib
import itertools
import json
import math
import statistics
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

import kit  # noqa: E402
import evaluate as evaluate_harness  # noqa: E402
from opr_core import members_index, p_msmi, simulate_outcome  # noqa: E402

N01 = ROOT / 'research' / 'next_method_search' / 'n01_introductions.jsonl'
C_JSON = ROOT / 'research' / 'e3_rel_experiment' / 'per_arm' / 'C.json'
E1_JSON = ROOT / 'research' / 'e3_rel_experiment' / 'per_arm' / 'E1.json'
OUT_D1 = HERE / 'validation_d1.json'
OUT_D2 = HERE / 'validation_d2.json'
OUT_ALL = HERE / 'validation_results.json'
LOG = HERE / 'opr_run_log.txt'

EXPECTED_SHA = {
    str(N01): '25c018c29f9c6bb26578eb692fb41998d2ca7a923369e7450c6b2a1aa5f2b91a',
    str(C_JSON): 'a245c22f5350f6146b5ae05e877dddb40b6415b68eaed999784a12309dc12951',
    str(E1_JSON): '89296ba543caeffcdac939a0b1a76b4361e19f9959449010c4c06d42410414d0',
}


def log(msg):
    stamp = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    line = f'[{stamp}] {msg}'
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(line + '\n')
    print(line, flush=True)


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_inputs():
    for path, expect in EXPECTED_SHA.items():
        got = sha256_file(path)
        if got != expect:
            raise SystemExit(f'SEALED INPUT DRIFT: {path} sha256 {got} != {expect}')
    log('sealed input hashes verified (3/3)')


def load_n01():
    rows = []
    with open(N01, encoding='utf-8') as f:
        for line in f:
            rows.append(json.loads(line))
    return rows


def rankdata_avg(vals):
    order = sorted(range(len(vals)), key=lambda i: vals[i])
    ranks = [0.0] * len(vals)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and vals[order[j + 1]] == vals[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def pearson(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if sx == 0 or sy == 0:
        return 0.0
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy)


def spearman_rho(x, y):
    return pearson(rankdata_avg(x), rankdata_avg(y))


def spearman_exact_one_sided_p(x, y):
    """Exact permutation p for rho(x, y): fraction of the 10! rank permutations
    of y whose rho with x is >= observed. n is len(x) (small, e.g. 10)."""
    obs = spearman_rho(x, y)
    rx = rankdata_avg(x)
    ry = rankdata_avg(y)
    n = len(x)
    mx = sum(rx) / n
    sy2 = sum((v - sum(ry) / n) ** 2 for v in ry)
    sx2 = sum((v - mx) ** 2 for v in rx)
    if sx2 == 0 or sy2 == 0:
        return 1.0
    denom = math.sqrt(sx2 * sy2)
    ge = total = 0
    for perm in itertools.permutations(ry):
        rho = sum((a - mx) * (b - sum(ry) / n) for a, b in zip(rx, perm)) / denom
        total += 1
        if rho >= obs - 1e-15:
            ge += 1
    return ge / total, obs


def binomial_ge_p(k, n):
    """P(X >= k) for X ~ Binomial(n, 0.5), exact."""
    return sum(math.comb(n, i) for i in range(k, n + 1)) / (2 ** n)


def stage_d1():
    log('stage d1 start: stream re-derivation + calibration on D1')
    rows = load_n01()
    worlds = {}
    mismatches = []
    ps, ys = [], []
    per_intro = []
    for idx, r in enumerate(rows):
        key = (r['seed'], r['variant'])
        if key not in worlds:
            w = kit.generate(r['seed'], 200, 'evaluation', r['variant'])
            worlds[key] = (w, members_index(w))
        world, members = worlds[key]
        got = simulate_outcome(r['seed'], r['user_a'], r['user_b'],
                               r['assigned_day'], r['variant'], members)
        y = int(r['y_msmi'])
        if int(got['msmi']) != y and len(mismatches) < 20:
            mismatches.append({'row': idx, 'seed': r['seed'], 'variant': r['variant'],
                               'day': r['assigned_day'], 'user_a': r['user_a'],
                               'user_b': r['user_b'], 'expected': y,
                               'got': int(got['msmi'])})
        p = p_msmi(members[r['user_a']], members[r['user_b']],
                   r['variant'], r['assigned_day'])
        ps.append(p)
        ys.append(y)
        per_intro.append({'p': p, 'y': y, 'variant': r['variant'], 'seed': r['seed']})
        if (idx + 1) % 1000 == 0:
            log(f'  d1 rows processed {idx + 1}/{len(rows)}')
    n = len(rows)
    # Mismatch list above is capped at 20 samples; recount exact matches fully.
    exact = 0
    worlds2 = {}
    for r in rows:
        key = (r['seed'], r['variant'])
        if key not in worlds2:
            w = kit.generate(r['seed'], 200, 'evaluation', r['variant'])
            worlds2[key] = members_index(w)
        got = simulate_outcome(r['seed'], r['user_a'], r['user_b'],
                               r['assigned_day'], r['variant'], worlds2[key])
        if int(got['msmi']) == int(r['y_msmi']):
            exact += 1
    match_rate = exact / n
    da_pass = exact == n
    log(f'D-A stream re-derivation: {exact}/{n} exact (rate {match_rate:.6f}) '
        f'PASS={da_pass}')
    if not da_pass:
        result = {'D_A': {'exact': exact, 'total': n, 'match_rate': match_rate,
                          'sample_mismatches': mismatches, 'pass': False},
                  'gate': 'INVALID'}
        OUT_D1.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
        log('D-A FAILED -> OPR INVALID; stop per preregistration')
        return result
    O, E = sum(ys), sum(ps)
    var = sum(p * (1 - p) for p in ps)
    R = (O - E) / math.sqrt(var) if var > 0 else 0.0
    db_pass = abs(R) <= 3 and (E > 0 and 0.85 <= O / E <= 1.15)
    log(f'D-B global calibration: O={O} E={E:.4f} O/E={O / E:.4f} R={R:.4f} PASS={db_pass}')
    order = sorted(range(n), key=lambda i: ps[i])
    bins = [order[i * n // 10:(i + 1) * n // 10] for i in range(10)]
    deciles = []
    dc_bin_pass = True
    for b in bins:
        bp = sum(ps[i] for i in b) / len(b)
        emp = sum(ys[i] for i in b) / len(b)
        sig = math.sqrt(sum(ps[i] * (1 - ps[i]) for i in b))
        ok = None
        if len(b) >= 30:
            ok = abs(emp - bp) <= 4 * sig if sig > 0 else abs(emp - bp) == 0
            dc_bin_pass = dc_bin_pass and ok
        deciles.append({'n': len(b), 'mean_p': bp, 'empirical': emp,
                        'sigma': sig, 'gated': len(b) >= 30, 'pass': ok})
    mean_ps = [d['mean_p'] for d in deciles]
    emps = [d['empirical'] for d in deciles]
    rho_p, rho = spearman_exact_one_sided_p(mean_ps, emps)
    dc_pass = dc_bin_pass and rho >= 0.8 and rho_p < 0.01
    log(f'D-C deciles: bins gated ok={dc_bin_pass} rho={rho:.4f} '
        f'exact_p={rho_p:.6f} PASS={dc_pass}')
    per_variant = {}
    for v in sorted({r['variant'] for r in rows}):
        vv = [i for i in range(n) if per_intro[i]['variant'] == v]
        ov = sum(ys[i] for i in vv)
        ev = sum(ps[i] for i in vv)
        rv = (ov - ev) / math.sqrt(sum(ps[i] * (1 - ps[i]) for i in vv))
        per_variant[v] = {'n': len(vv), 'O': ov, 'E': ev, 'R': rv,
                          'flag_abs_R_gt_4': abs(rv) > 4}
    sps = sorted(ps)
    def pct(q):
        return sps[min(n - 1, int(q * n))]
    result = {
        'D_A': {'exact': exact, 'total': n, 'match_rate': match_rate, 'pass': da_pass},
        'D_B': {'O': O, 'E': E, 'O_over_E': O / E, 'R': R, 'pass': db_pass,
                'variance_note': 'exact: independent per-intro streams given world state'},
        'D_C': {'deciles': deciles, 'spearman_rho': rho,
                'spearman_exact_one_sided_p': rho_p, 'pass': dc_pass},
        'D_D': {'per_variant': per_variant},
        'D_E': {'p50': pct(0.50), 'p90': pct(0.90), 'p99': pct(0.99), 'max': sps[-1],
                'min': sps[0]},
        'worlds': len(worlds), 'intros': n,
    }
    OUT_D1.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    log(f'stage d1 done -> {OUT_D1.name}')
    return result


class CaptureSim(kit.Simulator):
    last_introductions = None

    def __init__(self, world):
        super().__init__(world)
        CaptureSim.last_introductions = self.introductions


def _replay_one(args):
    arm, seed, variant = args
    policy = (ROOT / 'policy.py') if arm == 'C' else (ROOT / 'research' / 'e3_rel_experiment' / 'policy_e1.py')
    cmd = [sys.executable, str(policy), '--baseline', 'greedy']
    world = kit.generate(seed, 200, 'evaluation', variant)
    result = evaluate_harness.episode(world, cmd, simulator_class=CaptureSim)
    intros = [{'user_a': i['user_a'], 'user_b': i['user_b'],
               'assigned_day': i['assigned_day']}
              for i in CaptureSim.last_introductions]
    return {'arm': arm, 'seed': seed, 'variant': variant,
            'msmi': result['mutual_second_meeting_intention'],
            'action_sha256': result['action_sha256'], 'intros': intros,
            'valid': result.get('valid', True)}


def stage_d2(workers=4):
    log(f'stage d2 start: digest-verified replay of C and E1 ({workers} workers)')
    c_json = json.loads(C_JSON.read_text(encoding='utf-8'))
    e1_json = json.loads(E1_JSON.read_text(encoding='utf-8'))
    archived = {}
    for arm, doc in (('C', c_json), ('E1', e1_json)):
        for ep in doc['episodes']:
            archived[(arm, ep['seed'], ep['variant'])] = ep
    tasks = [(arm, ep['seed'], ep['variant'])
             for arm, doc in (('C', c_json), ('E1', e1_json))
             for ep in doc['episodes']]
    replays = {}
    accepted = 0
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for i, got in enumerate(pool.map(_replay_one, tasks)):
            key = (got['arm'], got['seed'], got['variant'])
            arch = archived[key]
            ok = (got['action_sha256'] == arch['action_sha256']
                  and got['msmi'] == arch['mutual_second_meeting_intention']
                  and got['valid'] and arch.get('valid', True))
            got['accepted'] = bool(ok)
            replays[key] = got
            accepted += int(ok)
            if (i + 1) % 12 == 0:
                log(f'  replays {i + 1}/{len(tasks)} accepted={accepted}')
    acc_rate = accepted / len(tasks)
    reliable = acc_rate >= 0.9
    log(f'D2 replay acceptance {accepted}/{len(tasks)} = {acc_rate:.4f} '
        f'reliable={reliable}')
    worlds_meta = sorted({(ep['seed'], ep['variant'])
                          for ep in c_json['episodes']})
    preds, reals = [], []
    g4_rows = []
    world_members = {}
    for seed, variant in worlds_meta:
        key_c = ('C', seed, variant)
        key_e = ('E1', seed, variant)
        if not (replays[key_c]['accepted'] and replays[key_e]['accepted']):
            continue
        wkey = (seed, variant)
        if wkey not in world_members:
            w = kit.generate(seed, 200, 'evaluation', variant)
            world_members[wkey] = members_index(w)
        members = world_members[wkey]
        def p_sum(intros):
            return sum(p_msmi(members[i['user_a']], members[i['user_b']],
                              variant, i['assigned_day'], n=2001)
                       for i in intros)
        pred = p_sum(replays[key_e]['intros']) - p_sum(replays[key_c]['intros'])
        real = (replays[key_e]['msmi'] - replays[key_c]['msmi'])
        preds.append(pred)
        reals.append(real)
        g4_rows.append({'seed': seed, 'variant': variant,
                        'predicted_delta': pred, 'realized_delta': real})
    n_eff_rows = [r for r in g4_rows if r['predicted_delta'] != 0.0]
    n_eff = len(n_eff_rows)
    S = sum(1 for r in n_eff_rows
            if (r['predicted_delta'] > 0) == (r['realized_delta'] > 0))
    g4_p = binomial_ge_p(S, n_eff) if n_eff else 1.0
    g4_pass = bool(reliable and n_eff > 0 and g4_p < 0.05)
    log(f'G4 sign agreement {S}/{n_eff} exact_p={g4_p:.6f} PASS={g4_pass}')
    pear = pearson(preds, reals) if len(preds) > 2 else None
    result = {
        'D2': {'replay_accepted': accepted, 'replay_total': len(tasks),
               'acceptance_rate': acc_rate, 'reliable': reliable},
        'G4': {'S': S, 'n_eff': n_eff, 'ties_excluded': len(g4_rows) - n_eff,
               'binomial_one_sided_p': g4_p, 'pass': g4_pass,
               'pearson_r': pear,
               'mean_predicted_delta': statistics.mean(preds) if preds else None,
               'mean_realized_delta': statistics.mean(reals) if reals else None,
               'rows': g4_rows},
    }
    OUT_D2.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    log(f'stage d2 done -> {OUT_D2.name}')
    return result


def apply_gate(d1, d2):
    da = d1.get('D_A', {}).get('pass', False)
    db = d1.get('D_B', {}).get('pass', False)
    dc = d1.get('D_C', {}).get('pass', False)
    reliable = d2.get('D2', {}).get('reliable', False)
    g4 = d2.get('G4', {}).get('pass', False)
    if not da:
        gate = 'INVALID'
    elif not reliable:
        gate = 'INCONCLUSIVE'
    elif da and db and dc and g4:
        gate = 'OPR_VALIDATED'
    else:
        gate = 'OPR_NOT_VALIDATED'
    log(f'GATE: {gate} (D-A={da} D-B={db} D-C={dc} D2_reliable={reliable} G4={g4})')
    return gate


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--stage', choices=['d1', 'd2', 'all'], default='all')
    ap.add_argument('--workers', type=int, default=4)
    args = ap.parse_args()
    verify_inputs()
    d1 = json.loads(OUT_D1.read_text(encoding='utf-8')) if OUT_D1.exists() else None
    d2 = json.loads(OUT_D2.read_text(encoding='utf-8')) if OUT_D2.exists() else None
    if args.stage in ('d1', 'all'):
        d1 = stage_d1()
    if args.stage in ('d2', 'all') and (d1 is None or d1.get('D_A', {}).get('pass')):
        d2 = stage_d2(workers=args.workers)
    elif args.stage == 'd2' and d1 and not d1.get('D_A', {}).get('pass'):
        log('D-A previously failed; refusing to run stage d2')
    if d1 is not None and d2 is not None:
        gate = apply_gate(d1, d2)
        combined = {'preregistration': 'validation_plan.md', 'gate': gate,
                    'D_A': d1.get('D_A'), 'D_B': d1.get('D_B'), 'D_C': d1.get('D_C'),
                    'D_D': d1.get('D_D'), 'D_E': d1.get('D_E'),
                    'D2': d2.get('D2'), 'G4': d2.get('G4')}
        OUT_ALL.write_text(json.dumps(combined, indent=2) + '\n', encoding='utf-8')
        log(f'combined results -> {OUT_ALL.name}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
