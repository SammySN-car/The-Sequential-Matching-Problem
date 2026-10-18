"""V-SOLV-01..05: validate the exact-k solver against brute force and self."""
import json, random, sys, time
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / 'round2_decision_ceiling' / 'scripts'))
import ce_common as c  # noqa: E402
from fc_matching import (brute_force_exact_k, check_matching,  # noqa: E402
                         solve_exact_k)

rng = random.Random(4242)
FC = Path(__file__).resolve().parent.parent
log = []
def say(s):
    print(s); log.append(s)

# ---------- (a) synthetic random graphs -------------------------------------
say('--- V-SOLV-01a: synthetic random graphs vs exhaustive enumeration ---')
syn_checked = syn_dis = cons_fail = det_fail = 0
t0 = time.time()
for trial in range(4000):
    nv = rng.randint(2, 10)
    verts = ['v%d' % i for i in range(nv)]
    cand = [(a, b) for i, a in enumerate(verts) for b in verts[i + 1:]]
    rng.shuffle(cand)
    edges = cand[:rng.randint(0, min(len(cand), 16))]
    w = [rng.choice([0, 0, 1, 2, -1, 3.5, 0.25]) for _ in edges]
    kmax = len(edges)
    for k in sorted({0, 1, rng.randint(0, kmax), kmax}):
        got, val, _, failed = solve_exact_k(edges, w, k)
        ref = brute_force_exact_k(edges, w, k)
        syn_checked += 1
        if failed:
            say('  NODE LIMIT on trial %d k=%d' % (trial, k)); syn_dis += 1; continue
        if got is not None:
            ok, why = check_matching(edges, got, k)
            if not ok:
                cons_fail += 1
                say('  CONSTRAINT %s trial=%d k=%d' % (why, trial, k))
        if (val is None) != (ref is None) or (val is not None and abs(val - ref) > 1e-9):
            syn_dis += 1
            if syn_dis < 5:
                say('  DISAGREE trial=%d k=%d got=%r ref=%r' % (trial, k, val, ref))
        # V-SOLV-03 determinism
        got2, val2, _, _ = solve_exact_k(edges, w, k)
        if got != got2:
            det_fail += 1
say('  synthetic checks=%d  disagreements=%d  constraint_fail=%d  det_fail=%d  (%.1fs)'
    % (syn_checked, syn_dis, cons_fail, det_fail, time.time() - t0))

# ---------- (b) real study graphs -------------------------------------------
say('--- V-SOLV-01b: every real state with n_edges <= 16, all four weightings ---')
REQUIRED = ('counterfactual_pairs.jsonl', 'oof_scores.jsonl', 'day_edges.jsonl')
missing = [n for n in REQUIRED if not (c.OUT / n).exists()]
if missing:
    say('SKIP: %s not present (excluded from the curated branch; see '
        'research/README.md)' % ', '.join(missing))
    sys.exit(0)
labels = defaultdict(dict)
for line in open(c.OUT / 'counterfactual_pairs.jsonl', encoding='utf-8'):
    r = json.loads(line)
    labels[(r['seed'], r['variant'], r['day'])][(r['user_a'], r['user_b'])] = int(bool(r['cf_y_msmi']))
oof = {}
for line in open(c.OUT / 'oof_scores.jsonl', encoding='utf-8'):
    r = json.loads(line)
    oof[(r['seed'], r['variant'], r['day'], r['user_a'], r['user_b'])] = r

# weight functions take (state_key, raw_day_edges_row)
WEIGHTS = {
    'F1-SCORE':   lambda k, raw: -raw[0],
    'F2-SOFT':    lambda k, raw: oof[(k[0],k[1],k[2],raw[1][0],raw[1][1])]['F2_soft_state'],
    'F3-OBSERV':  lambda k, raw: oof[(k[0],k[1],k[2],raw[1][0],raw[1][1])]['F4_full_legal_observables'],
    'F5-ORACLE':  lambda k, raw: labels[k][tuple(raw[1])],
}
real_checked = {a: 0 for a in WEIGHTS}
real_dis = {a: 0 for a in WEIGHTS}
real_cons = 0
hard_max_nodes = 0
hard_states = 0
t0 = time.time()
for line in open(c.OUT / 'day_edges.jsonl', encoding='utf-8'):
    d = json.loads(line)
    kkey = (d['seed'], d['variant'], d['day'])
    raw = d['edges']
    edges = [tuple(e[1]) for e in raw]
    if len(edges) > 16:
        continue
    kt = len(d['pairs'])
    hard_states += 1
    for arm, fn in WEIGHTS.items():
        w = [fn(kkey, r) for r in raw]
        got, val, nodes, failed = solve_exact_k(edges, w, kt)
        hard_max_nodes = max(hard_max_nodes, nodes)
        ref = brute_force_exact_k(edges, w, kt)
        real_checked[arm] += 1
        if failed:
            real_dis[arm] += 1
            say('  NODE LIMIT %s %s' % (arm, kkey)); continue
        if got is not None:
            ok, why = check_matching(edges, got, kt)
            if not ok:
                real_cons += 1
                say('  CONSTRAINT %s %s: %s' % (arm, kkey, why))
        elif ref is not None:
            real_cons += 1
            say('  INFEASIBLE-BUT-REF-OK %s %s' % (arm, kkey))
        if (val is None) != (ref is None) or (val is not None and abs(val - ref) > 1e-9):
            real_dis[arm] += 1
            if real_dis[arm] < 4:
                say('  DISAGREE %s %s got=%r ref=%r' % (arm, kkey, val, ref))
say('  real states with n_edges<=16: %d   checks/arm=%s' % (hard_states, real_checked))
say('  disagreements=%s  constraint_fail=%d  max_nodes=%d  (%.1fs)'
    % (real_dis, real_cons, hard_max_nodes, time.time() - t0))

# ---------- (c) V-SOLV-04: never worse than greedy's own set ----------------
say('--- V-SOLV-04: solver objective >= greedy objective (F1-SCORE weighting) ---')
worse = 0; equal = 0; better = 0; skipped = 0
t0 = time.time()
for line in open(c.OUT / 'day_edges.jsonl', encoding='utf-8'):
    d = json.loads(line)
    kkey = (d['seed'], d['variant'], d['day'])
    edges = [tuple(e[1]) for e in d['edges']]
    w = [-e[0] for e in d['edges']]
    kt = len(d['pairs'])
    idx = {e: i for i, e in enumerate(edges)}
    gscore = sum(w[idx[p]] for p in (tuple(x) for x in d['pairs']))
    got, val, nodes, failed = solve_exact_k(edges, w, kt)
    if failed:
        skipped += 1; continue
    if val < gscore - 1e-9:
        worse += 1; say('  WORSE THAN GREEDY on %s (%r < %r)' % (kkey, val, gscore))
    elif val > gscore + 1e-9:
        better += 1
    else:
        equal += 1
say('  better=%d equal=%d worse=%d node_limit=%d (%.1fs)'
    % (better, equal, worse, skipped, time.time() - t0))

passed = (syn_dis == 0 and cons_fail == 0 and det_fail == 0
          and sum(real_dis.values()) == 0 and real_cons == 0 and worse == 0
          and skipped == 0)
res = dict(V_SOLV_01a_synthetic=dict(checked=syn_checked, disagreements=syn_dis,
                                     constraint_fail=cons_fail, det_fail=det_fail),
           V_SOLV_01b_real=dict(states=hard_states, checked=real_checked,
                                disagreements=real_dis, constraint_fail=real_cons,
                                max_nodes=hard_max_nodes),
           V_SOLV_04_vs_greedy=dict(better=better, equal=equal, worse=worse,
                                    node_limit=skipped),
           passed=bool(passed))
(FC / 'solver_validation.json').write_text(json.dumps(res, indent=1, sort_keys=True) + '\n',
                                           encoding='utf-8')
say('')
say('SOLVER VALIDATION: ' + ('PASS' if passed else 'FAIL'))
raise SystemExit(0 if passed else 1)
