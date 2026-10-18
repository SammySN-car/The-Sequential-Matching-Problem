"""Task 1 smoke tests for srws_solver (TDD: written BEFORE the solver exists)."""
import itertools, random, sys, time
from fractions import Fraction

sys.path.insert(0, __file__.rsplit("\\", 1)[0])
from srws_solver import solve_exact_k, SolverError, InfeasibleKError

FAILURES = []

def check(name, cond, detail=""):
    if cond:
        print("PASS", name)
    else:
        print("FAIL", name, detail)
        FAILURES.append(name)

def canon_rank(edges):
    order = sorted(range(len(edges)),
                   key=lambda i: (edges[i][0], edges[i][1]) if edges[i][0] <= edges[i][1]
                   else (edges[i][1], edges[i][0]))
    rank = [0] * len(edges)
    for pos, i in enumerate(order):
        rank[i] = pos
    return rank

def brute_exact(edges, weights, k):
    """Best (exact Fraction value, canon-rank tuple) over size-k disjoint sets, or None."""
    m = len(edges)
    rank = canon_rank(edges)
    F = [Fraction(w) for w in weights]
    best = None
    for combo in itertools.combinations(range(m), k):
        used = set()
        ok = True
        for i in combo:
            u, v = edges[i]
            if u in used or v in used:
                ok = False
                break
            used.add(u); used.add(v)
        if not ok:
            continue
        val = sum((F[i] for i in combo), Fraction(0))
        key = tuple(sorted(rank[i] for i in combo))
        if best is None or val > best[0] or (val == best[0] and key < best[1]):
            best = (val, key)
    return best

# 1. empty graph
idx, meta = solve_exact_k([], [], 0)
check("empty-k0", idx == () and set(meta) >= {"n_vertices", "n_aug_edges", "aug_N", "value_int", "value_float"})
try:
    solve_exact_k([], [], 1)
    check("empty-k1-infeasible", False)
except InfeasibleKError:
    check("empty-k1-infeasible", True)

# 2. k=0 short circuit
idx, meta = solve_exact_k([("a", "b")], [0.5], 0)
check("k0", idx == ())

# 3. triangle equal weights k=1 -> canon-first edge
idx, _ = solve_exact_k([("a", "b"), ("b", "c"), ("a", "c")], [0.5] * 3, 1)
check("triangle-lex", idx == (0,), "got %r" % (idx,))

# 4. trap: locally-best edge blocks better total
edges = [("0", "1"), ("0", "2"), ("1", "3"), ("2", "3")]
w = [0.9, 0.6, 0.6, 0.1]
idx, _ = solve_exact_k(edges, w, 2)
check("trap", idx == (1, 2), "got %r" % (idx,))
b = brute_exact(edges, w, 2)
check("trap-brute", b is not None and tuple(sorted(canon_rank(edges)[i] for i in idx)) == b[1])

# 5. K4 equal k=2 -> max tie weight == lex-smallest rank set
edges = [("a", "b"), ("a", "c"), ("a", "d"), ("b", "c"), ("b", "d"), ("c", "d")]
idx, _ = solve_exact_k(edges, [0.5] * 6, 2)
check("k4-lex", idx == (0, 5), "got %r" % (idx,))

# 6. infeasible: star k=2; k > floor(n/2)
for nm, ee, kk in [("star-k2", [("c", "a"), ("c", "b"), ("c", "d")], 2),
                   ("k-over-half", [("a", "b"), ("b", "c"), ("c", "d")], 3)]:
    try:
        solve_exact_k(ee, [0.5] * len(ee), kk)
        check(nm, False, "no exception")
    except InfeasibleKError:
        check(nm, True)

# 7. determinism: 5x identical
base_e = [("a", "b"), ("a", "c"), ("b", "c"), ("b", "d"), ("c", "d"), ("a", "d")]
outs = {solve_exact_k(base_e, [0.7, 0.1, 0.9, 0.2, 0.6, 0.3], 2)[0] for _ in range(5)}
check("determinism", len(outs) == 1, repr(outs))

# 8. preconditions -> SolverError
for nm, fn in [
    ("len-mismatch", lambda: solve_exact_k([("a", "b")], [0.5, 0.5], 1)),
    ("self-loop", lambda: solve_exact_k([("a", "a")], [0.5], 1)),
    ("duplicate", lambda: solve_exact_k([("a", "b"), ("b", "a")], [0.5, 0.5], 1)),
    ("k-negative", lambda: solve_exact_k([("a", "b")], [0.5], -1)),
    ("weight-one", lambda: solve_exact_k([("a", "b")], [1.0], 1)),
]:
    try:
        fn()
        check(nm, False, "no exception")
    except SolverError:
        check(nm, True)
    except Exception as e:
        check(nm, False, "wrong type %r" % e)

# 9. near-equal floats: exact arithmetic must beat float-sum tie
#    0.1 + 0.2 (exact) > 0.30000000000000004 (exact), but float sums are equal.
edges = [("a", "b"), ("a", "c"), ("b", "d"), ("c", "d")]
w = [0.1, 0.30000000000000004, 3e-17, 0.2]
idx, _ = solve_exact_k(edges, w, 2)
b = brute_exact(edges, w, 2)
got_key = tuple(sorted(canon_rank(edges)[i] for i in idx))
check("exact-float-tie", b is not None and got_key == b[1] and got_key == (1, 2),
      "got key %r expect %r" % (got_key, (1, 2)))

# 10. randomized mini-battery: 200 cases vs exact brute (value AND tie set)
rng = random.Random(987654321)
bad = 0
for case in range(200):
    nv = rng.randint(2, 6)
    verts = ["v%d" % i for i in range(nv)]
    p = rng.choice([0.3, 0.5, 0.8])
    ee = [(u, v) for i, u in enumerate(verts) for v in verts[i + 1:] if rng.random() < p]
    fam = rng.randint(0, 3)
    if fam == 0:
        ww = [rng.random() for _ in ee]
    elif fam == 1:
        ww = [0.5] * len(ee)
    elif fam == 2:
        ww = [0.0 if rng.random() < 0.3 else rng.random() * 1e-6 for _ in ee]
    else:
        ww = [min(max(0.5 + rng.choice([-1, 0, 1]) * 2 ** -rng.randint(40, 53), 0.0), 1.0) for _ in ee]
    order = list(range(len(ee)))
    rng.shuffle(order)
    ee2 = [ee[i] for i in order]
    ww2 = [ww[i] for i in order]
    k = rng.randint(0, nv // 2 + 1)
    b = brute_exact(ee2, ww2, k)
    try:
        idx, meta = solve_exact_k(ee2, ww2, k)
        if b is None:
            bad += 1
            print("  case %d: solver returned %r but brute says infeasible" % (case, idx))
            continue
        got_key = tuple(sorted(canon_rank(ee2)[i] for i in idx))
        val = sum((Fraction(ww2[i]) for i in idx), Fraction(0))
        if len(idx) != k or val != b[0] or got_key != b[1]:
            bad += 1
            print("  case %d MISMATCH k=%d val_ok=%s key_ok=%s got=%r expect=%r"
                  % (case, k, val == b[0], got_key == b[1], got_key, b[1]))
    except InfeasibleKError:
        if b is not None:
            bad += 1
            print("  case %d: solver infeasible but brute optimum %s" % (case, b[0]))
check("mini-battery-200", bad == 0, "%d bad" % bad)

# 11. timing: 60 vertices, 65 edges, k=17
rng2 = random.Random(555)
verts = ["v%d" % i for i in range(60)]
ee = [("v%d" % i, "v%d" % (i + 17)) for i in range(17)]
seen = set(tuple(sorted(e)) for e in ee)
while len(ee) < 65:
    a, b2 = rng2.sample(verts, 2)
    key = tuple(sorted((a, b2)))
    if key in seen:
        continue
    seen.add(key)
    ee.append(key)
rng2.shuffle(ee)
ww = [rng2.random() for _ in ee]
t0 = time.perf_counter()
idx, meta = solve_exact_k(ee, ww, 17)
dt = time.perf_counter() - t0
used = set()
ok = len(idx) == 17
for i in idx:
    u, v = ee[i]
    if u in used or v in used:
        ok = False
    used.add(u); used.add(v)
check("timing-n60", ok and dt < 3.0, "len=%d time=%.3fs" % (len(idx), dt))
print("timing-n60: %.3fs" % dt)

# 12. regressions for the four root-cause defects fixed 2026-10-14:
#  (a) non-convergence: the exact input that previously spun through the
#      phase loop until "SolverError: internal: no convergence after
#      1201 steps" (dead-phase break never reached the return);
#  (b) sign: a min-form core fed POSITIVE weights returned the MINIMUM
#      perfect matching - covered by trap/trap-brute above (minimum would
#      pick {e0,e3} = 1.0, the test requires {e1,e2} = 1.2);
#  (c) exponent scaling: as_integer_ratio() denominators are 2**exp as
#      VALUES; storing them raw made num << (Q - q) MemoryError on 0.1;
#  (d) augment flip: in-order mate[] mutation left stale asymmetric
#      entries on depth>0 augmenting paths - covered by the dense brute
#      battery below.

# (a) explicit non-convergence regression
try:
    for _ in range(5):
        idx, _ = solve_exact_k([("a", "b"), ("b", "c"), ("a", "c")], [0.5] * 3, 1)
    check("regress-nonconvergence", idx == (0,), "got %r" % (idx,))
except SolverError as e:
    check("regress-nonconvergence", False, "raised %r" % (e,))

# (c) exponent-scaling regression: weights with wildly different
#     binary exponents (2**-40 vs 0.5) checked against brute force
edges = [("a", "b"), ("a", "c"), ("b", "d"), ("c", "d")]
w = [2.0 ** -40, 0.5, 0.1, 0.75]
idx, _ = solve_exact_k(edges, w, 2)
b = brute_exact(edges, w, 2)
got = tuple(sorted(canon_rank(edges)[i] for i in idx))
check("regress-exponent-scaling", b is not None and got == b[1],
      "got %r expect %r" % (got, b[1] if b else None))

# (d) dense deep-augment battery: 300 cases, n in 4..8, p in {0.6, 0.9},
#     three weight families incl. zero / near-zero / last-bit-close
rng = random.Random(2026101414)
bad = 0
for case in range(300):
    nv = rng.randint(4, 8)
    verts = ["d%d" % i for i in range(nv)]
    p = rng.choice([0.6, 0.9])
    ee = [(u, v) for i, u in enumerate(verts) for v in verts[i + 1:] if rng.random() < p]
    if not ee:
        continue
    fam = rng.randint(0, 2)
    if fam == 0:
        ww = [rng.random() for _ in ee]
    elif fam == 1:
        ww = [0.5] * len(ee)
    else:
        ww = [rng.choice([0.0, 1e-9, 0.5, 0.5 + 2 ** -40, 0.999999]) for _ in ee]
    k = rng.randint(1, nv // 2)
    b = brute_exact(ee, ww, k)
    try:
        idx, meta = solve_exact_k(ee, ww, k)
        if b is None:
            bad += 1
            print("  dense case %d: solver feasible but brute infeasible" % case)
            continue
        got = tuple(sorted(canon_rank(ee)[i] for i in idx))
        val = sum((Fraction(ww[i]) for i in idx), Fraction(0))
        if len(idx) != k or val != b[0] or got != b[1]:
            bad += 1
            print("  dense case %d MISMATCH k=%d val_ok=%s key_ok=%s got=%r expect=%r"
                  % (case, k, val == b[0], got == b[1], got, b[1]))
    except InfeasibleKError:
        if b is not None:
            bad += 1
            print("  dense case %d: solver infeasible but brute optimum %s" % (case, b[0]))
check("regress-deep-augment-battery-300", bad == 0, "%d bad" % bad)

print("----")
print("FAILURES: %d %r" % (len(FAILURES), FAILURES))
sys.exit(1 if FAILURES else 0)
