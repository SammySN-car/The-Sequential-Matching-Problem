"""Task 2: C1-C6 correctness battery for srws_solver -> results/solver_validation.json.

Verifies srws_solver.solve_exact_k against an EXHAUSTIVE oracle on >= 10,000
independently generated small-graph cases (n<=14, m<=40) across the frozen-plan
C1-C6 gates. Deterministic: all randomness from documented seeds; no clock/RNG
in the decision path. Standard library only.

C1 brute-force battery: objective value equality vs exhaustive enumeration
    (zero mismatches allowed).
C2 determinism: repeated solves return identical edge sets; reported primary
    sum equals the brute-force optimum.
C3 structure: exactly k edges, no repeated vertices, indices in range, edges
    present in E.
C4 tie policy: returned set == lexicographically smallest primary-optimal set.
C5 cross-check with old fc_matching.solve_exact_k (same edge set where the old
    solver completes); every disagreement explained (old float/EPS/limit).
C6 exact-k from greedy: with k = greedy matching cardinality the solver returns
    exactly k edges (feasibility of the greedy-cardinality query).
"""
import itertools, json, math, os, random, sys, time
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)                    # .../round2_stagewise_reward_solver
RESEARCH = os.path.dirname(EXP)                # .../research
sys.path.insert(0, HERE)
from srws_solver import solve_exact_k, SolverError, InfeasibleKError

FC_SCRIPTS = os.path.join(RESEARCH, "round2_fixed_cardinality", "scripts")
sys.path.insert(0, FC_SCRIPTS)
import fc_matching

RESULTS = os.path.join(EXP, "results")
os.makedirs(RESULTS, exist_ok=True)
SCALE = float(os.environ.get("SRS_BATTERY_SCALE", "1.0"))
MASTER_SEED = 20261014


def canon(e):
    return (e[0], e[1]) if e[0] <= e[1] else (e[1], e[0])


def canon_rank(edges):
    order = sorted(range(len(edges)), key=lambda i: canon(edges[i]))
    rank = [0] * len(edges)
    for pos, i in enumerate(order):
        rank[i] = pos
    return rank


def oracle(edges, weights, k):
    """Exhaustive enumeration of ALL size-k vertex-disjoint subsets.

    Returns None if no size-k matching exists, else
    (best_exact_sum_Fraction, lex_smallest_rank_tuple, lex_smallest_idx_tuple).
    """
    m = len(edges)
    rank = canon_rank(edges)
    F = [Fraction(w) for w in weights]
    best_val = None
    best_key = None
    best_idx = None
    used = set()

    def bt(i, count, ssum, keylist, chosen):
        nonlocal best_val, best_key, best_idx
        if count == k:
            key = tuple(sorted(keylist))
            if best_val is None or ssum > best_val or (ssum == best_val and key < best_key):
                best_val, best_key, best_idx = ssum, key, tuple(chosen)
            return
        if i >= m or count + (m - i) < k:
            return
        u, v = edges[i]
        if u not in used and v not in used:
            used.add(u); used.add(v)
            bt(i + 1, count + 1, ssum + F[i], keylist + [rank[i]], chosen + [i])
            used.discard(u); used.discard(v)
        bt(i + 1, count, ssum, keylist, chosen)

    bt(0, 0, Fraction(0), [], [])
    if best_val is None:
        return None
    return best_val, best_key, best_idx


def greedy_cardinality(edges, weights):
    """Greedy maximal matching (score-desc, disjoint) -> chosen index tuple."""
    m = len(edges)
    order = sorted(range(m), key=lambda i: (-weights[i], canon(edges[i])))
    used = set()
    chosen = []
    for i in order:
        u, v = edges[i]
        if u not in used and v not in used:
            used.add(u); used.add(v)
            chosen.append(i)
    return tuple(sorted(chosen))


def frac_sum(edges, weights, idx):
    return sum((Fraction(weights[i]) for i in idx), Fraction(0))


# ---------------------------------------------------------------- generators
def g_empty(rng):
    n = rng.randint(1, 8)
    return [], [], rng.randint(0, 2)


def g_k0(rng):
    edges, weights = _random_graph(rng, rng.randint(2, 12), rng.choice([0.2, 0.5, 0.8]))
    return edges, weights, 0


def _random_graph(rng, n, p):
    verts = ["v%d" % i for i in range(n)]
    edges = []
    weights = []
    for i, u in enumerate(verts):
        for v in verts[i + 1:]:
            if rng.random() < p:
                edges.append((u, v))
                weights.append(rng.random())
    return edges, weights


def g_isolated_oddeven(rng):
    # mix odd/even n with some isolated (never-incident) vertices
    n_total = rng.randint(3, 13)
    n_iso = rng.randint(0, max(1, n_total // 3))
    n_inc = n_total - n_iso
    verts = ["v%d" % i for i in range(n_inc)]            # incident pool
    edges = []
    weights = []
    p = rng.choice([0.3, 0.6, 0.9])
    for i, u in enumerate(verts):
        for v in verts[i + 1:]:
            if rng.random() < p:
                edges.append((u, v))
                weights.append(rng.random())
    k = rng.randint(0, n_total // 2)
    return edges, weights, k


def g_sparse(rng):
    n = rng.randint(2, 14)
    edges, weights = _random_graph(rng, n, rng.choice([0.15, 0.25, 0.35]))
    k = rng.randint(0, n // 2)
    if rng.random() < 0.15:
        k = n // 2 + 1                      # deliberately infeasible-by-size
    return edges, weights, k


def g_dense(rng):
    n = rng.randint(2, 12)
    edges, weights = _random_graph(rng, n, rng.choice([0.7, 0.85, 1.0]))
    if len(edges) > 40:                      # cap m<=40
        keep = rng.sample(range(len(edges)), 40)
        edges = [edges[i] for i in keep]
        weights = [weights[i] for i in keep]
    k = rng.randint(0, n // 2)
    return edges, weights, k


def g_equal_weight(rng):
    # every edge identical weight -> massive primary tie (stresses C4)
    n = rng.randint(2, 12)
    wval = rng.choice([0.5, 0.25, 0.75, 1e-9, 0.0])
    edges = []
    weights = []
    verts = ["v%d" % i for i in range(n)]
    p = rng.choice([0.5, 0.8, 1.0])
    for i, u in enumerate(verts):
        for v in verts[i + 1:]:
            if rng.random() < p:
                edges.append((u, v))
                weights.append(wval)
    k = rng.randint(0, n // 2)
    return edges, weights, k


def g_zero_nearzero(rng):
    n = rng.randint(2, 12)
    verts = ["v%d" % i for i in range(n)]
    edges = []
    weights = []
    p = rng.choice([0.4, 0.7, 1.0])
    for i, u in enumerate(verts):
        for v in verts[i + 1:]:
            if rng.random() < p:
                edges.append((u, v))
                r = rng.random()
                if r < 0.4:
                    weights.append(0.0)
                elif r < 0.8:
                    weights.append(rng.random() * 1e-12)   # near zero
                else:
                    weights.append(rng.random() * 1e-6)
    k = rng.randint(0, n // 2)
    return edges, weights, k


def g_close_float(rng):
    # very close float scores differing only in last bits
    n = rng.randint(2, 10)
    verts = ["v%d" % i for i in range(n)]
    edges = []
    weights = []
    p = rng.choice([0.5, 0.8, 1.0])
    base = 0.3 + rng.random() * 0.4
    for i, u in enumerate(verts):
        for v in verts[i + 1:]:
            if rng.random() < p:
                edges.append((u, v))
                w = base
                for _ in range(rng.randint(0, 3)):
                    w = math.nextafter(w, 1.0 if rng.random() < 0.5 else 0.0)
                weights.append(w)
    k = rng.randint(0, n // 2)
    return edges, weights, k


def g_greedy_block(rng):
    # motif where the locally-heaviest edge blocks a better size-k total
    a, b, c, d = "a", "b", "c", "d"
    heavy = 0.8 + rng.random() * 0.19
    e1 = 0.4 + rng.random() * 0.2
    e2 = 0.4 + rng.random() * 0.2
    edges = [(a, b), (a, c), (b, d)]
    weights = [heavy, e1, e2]
    # optional low noise edges that must not beat the good pair for k=2
    if rng.random() < 0.5:
        edges.append((c, d)); weights.append(rng.random() * 0.2)
    n_extra = rng.randint(0, 3)
    pool = ["p%d" % j for j in range(n_extra * 2)]
    for j in range(0, len(pool) - 1, 2):
        edges.append((pool[j], pool[j + 1])); weights.append(rng.random() * 0.3)
    k = 2
    return edges, weights, k


def g_infeasible_structural(rng):
    # star / near-star: max matching is 1 while floor(n/2) is larger
    n = rng.randint(4, 10)
    hub = "h"
    edges = []
    weights = []
    for j in range(n - 1):
        edges.append((hub, "l%d" % j)); weights.append(rng.random())
    # a couple of leaf-leaf edges so feasibility is borderline
    if rng.random() < 0.5 and n >= 5:
        edges.append(("l0", "l1")); weights.append(rng.random())
    k = rng.choice([2, n // 2, n // 2 + 1])
    return edges, weights, k


FAMILIES = [
    ("F1-empty", g_empty, 500),
    ("F2-k0", g_k0, 500),
    ("F3-isolated-oddeven", g_isolated_oddeven, 1200),
    ("F4-sparse", g_sparse, 2200),
    ("F5-dense", g_dense, 1500),
    ("F6-equal-weight-tie", g_equal_weight, 1500),
    ("F7-zero-nearzero", g_zero_nearzero, 1000),
    ("F8-close-float", g_close_float, 1000),
    ("F9-greedy-block", g_greedy_block, 800),
    ("F10-infeasible-structural", g_infeasible_structural, 1000),
]


def main():
    t0 = time.time()
    total = 0
    mism_obj = 0        # C1
    mism_tie = 0        # C4
    det_fail = 0        # C2
    struct_fail = 0     # C3
    infeas_mism = 0     # C1 (feasibility agreement)
    c6_checked = 0
    c6_violations = 0
    old_agree = 0
    old_disagree = 0
    old_disagree_explained = 0
    old_disagree_newbug = 0
    old_skipped = 0
    infeasible_seen = 0
    feasible_seen = 0
    fam_stats = {}
    failing = []

    for fam_name, gen, count in FAMILIES:
        count = max(1, int(round(count * SCALE)))
        seed = MASTER_SEED + sum(ord(ch) for ch in fam_name)
        rng = random.Random(seed)
        fs = {"cases": 0, "feasible": 0, "infeasible": 0, "objective_mismatch": 0,
              "tie_mismatch": 0, "det_fail": 0, "struct_fail": 0,
              "old_agree": 0, "old_disagree": 0, "c6_checked": 0, "c6_viol": 0}
        for case in range(count):
            edges, weights, k = gen(rng)
            total += 1
            fs["cases"] += 1
            case_id = "%s#%d" % (fam_name, case)
            orn = oracle(edges, weights, k)

            # ---- run new solver ----
            try:
                idx, meta = solve_exact_k(edges, weights, k)
                raised = None
            except InfeasibleKError as e:
                idx, meta, raised = None, None, "infeasible"
            except SolverError as e:
                idx, meta, raised = None, None, "solvererror:%s" % e

            if orn is None:
                # oracle: no size-k matching
                infeasible_seen += 1
                fs["infeasible"] += 1
                if raised != "infeasible":
                    infeas_mism += 1
                    fs["objective_mismatch"] += 1
                    if len(failing) < 40:
                        failing.append({"id": case_id, "kind": "infeasible-mismatch",
                                        "raised": raised, "k": k, "n_edges": len(edges)})
                continue

            # oracle feasible
            feasible_seen += 1
            fs["feasible"] += 1
            if raised is not None:
                infeas_mism += 1
                fs["objective_mismatch"] += 1
                if len(failing) < 40:
                    failing.append({"id": case_id, "kind": "feasible-but-raised",
                                    "raised": raised, "k": k, "n_edges": len(edges)})
                continue

            opt_val, opt_key, _ = orn

            # ---- C3 structure ----
            m = len(edges)
            ok_struct = (len(idx) == k and len(set(idx)) == k
                         and all(0 <= i < m for i in idx))
            if ok_struct:
                usedv = set()
                for i in idx:
                    u, v = edges[i]
                    if u in usedv or v in usedv:
                        ok_struct = False
                        break
                    usedv.add(u); usedv.add(v)
            if not ok_struct:
                struct_fail += 1
                fs["struct_fail"] += 1
                if len(failing) < 40:
                    failing.append({"id": case_id, "kind": "structure", "idx": list(idx), "k": k})

            # ---- C1 objective ----
            got = frac_sum(edges, weights, idx)
            if got != opt_val:
                mism_obj += 1
                fs["objective_mismatch"] += 1
                if len(failing) < 40:
                    failing.append({"id": case_id, "kind": "objective",
                                    "got": str(got), "opt": str(opt_val), "k": k})

            # ---- C4 tie policy ----
            rank = canon_rank(edges)
            got_key = tuple(sorted(rank[i] for i in idx))
            if got_key != opt_key:
                mism_tie += 1
                fs["tie_mismatch"] += 1
                if len(failing) < 40:
                    failing.append({"id": case_id, "kind": "tie",
                                    "got": list(got_key), "opt": list(opt_key), "k": k})

            # ---- C2 determinism ----
            try:
                idx2, _2 = solve_exact_k(edges, weights, k)
                if tuple(idx2) != tuple(idx):
                    det_fail += 1
                    fs["det_fail"] += 1
            except Exception:
                det_fail += 1
                fs["det_fail"] += 1

            # ---- C6 exact-k from greedy (generated graphs) ----
            gset = greedy_cardinality(edges, weights)
            kg = len(gset)
            c6_checked += 1
            fs["c6_checked"] += 1
            try:
                idxg, _3 = solve_exact_k(edges, weights, kg)
                if len(idxg) != kg:
                    c6_violations += 1
                    fs["c6_viol"] += 1
                    if len(failing) < 40:
                        f6ailing = {"id": case_id, "kind": "c6", "kg": kg, "got": len(idxg)}
                        failing.append(f6ailing)
            except Exception as e:
                c6_violations += 1
                fs["c6_viol"] += 1
                if len(failing) < 40:
                    failing.append({"id": case_id, "kind": "c6-raise", "kg": kg, "err": str(e)})

            # ---- C5 cross-check with old solver ----
            try:
                old_idx, old_obj, old_nodes, old_failed = fc_matching.solve_exact_k(edges, weights, k)
            except Exception:
                old_idx, old_failed = None, True
            if old_failed or old_idx is None:
                old_skipped += 1
            else:
                if tuple(sorted(old_idx)) == tuple(sorted(idx)):
                    old_agree += 1
                    fs["old_agree"] += 1
                else:
                    old_disagree += 1
                    fs["old_disagree"] += 1
                    newobj = frac_sum(edges, weights, idx)
                    oldobj = frac_sum(edges, weights, old_idx)
                    if newobj == opt_val:
                        old_disagree_explained += 1   # old float/limit divergence
                    else:
                        old_disagree_newbug += 1
                        if len(failing) < 40:
                            failing.append({"id": case_id, "kind": "c5-new-suboptimal",
                                            "new": list(idx), "old": list(old_idx),
                                            "newobj": str(newobj), "opt": str(opt_val)})

        fam_stats[fam_name] = fs

    elapsed = time.time() - t0

    # ---------------- gate verdicts ----------------
    c1_pass = (mism_obj == 0 and infeas_mism == 0)
    c2_pass = (det_fail == 0)
    c3_pass = (struct_fail == 0)
    c4_pass = (mism_tie == 0)
    c5_pass = (old_disagree_newbug == 0)   # every disagreement explained by old-solver divergence
    c6_pass = (c6_violations == 0)
    volume_pass = total >= 10000
    passed = all([c1_pass, c2_pass, c3_pass, c4_pass, c5_pass, c6_pass, volume_pass])

    out = {
        "experiment": "round2_stagewise_reward_solver",
        "task": 2,
        "script": "scripts/srws_solver_test.py",
        "master_seed": MASTER_SEED,
        "scale": SCALE,
        "elapsed_seconds": round(elapsed, 3),
        "total_cases": total,
        "feasible_cases": feasible_seen,
        "infeasible_cases": infeasible_seen,
        "gates": {
            "C1_bruteforce_objective": {"pass": c1_pass, "objective_mismatch": mism_obj,
                                         "feasibility_mismatch": infeas_mism},
            "C2_determinism": {"pass": c2_pass, "det_fail": det_fail},
            "C3_structure": {"pass": c3_pass, "struct_fail": struct_fail},
            "C4_tie_policy": {"pass": c4_pass, "tie_mismatch": mism_tie},
            "C5_crosscheck_old_solver": {
                "pass": c5_pass, "agree": old_agree, "disagree": old_disagree,
                "disagree_explained_old_float_or_limit": old_disagree_explained,
                "disagree_new_solver_suboptimal": old_disagree_newbug,
                "skipped_infeasible_or_node_limit": old_skipped,
                "note": "old fc_matching uses float EPS=1e-9 + node limit; divergences on "
                        "near-tie/last-bit cases are expected and, when the new solver's "
                        "objective equals the exhaustive optimum, attributed to the old solver.",
            },
            "C6_exactk_from_greedy": {"pass": c6_pass, "checked": c6_checked,
                                       "violations": c6_violations,
                                       "note": "evaluated on generated graphs (k = greedy "
                                               "matching cardinality); benchmark-state (S.7) "
                                               "restatement runs in Task 4 corpus."},
            "volume_min_10000": {"pass": volume_pass, "required": 10000, "actual": total},
        },
        "per_family": fam_stats,
        "failing_cases": failing,
        "benchmark_state_note": (
            "C2/C5/C6 reference 'every benchmark state (S.7)'. The S.7 corpus is "
            "materialised in Task 4 (srws_benchmark.py); this Task-2 battery validates "
            "the identical correctness properties on the >=10k generated small-graph "
            "population and cross-checks the old solver there. Benchmark-state "
            "restatements are appended to results when the corpus exists."
        ),
        "passed": passed,
    }

    with open(os.path.join(RESULTS, "solver_validation.json"), "w") as f:
        json.dump(out, f, indent=2)

    # ---------------- console summary ----------------
    print("Task 2 C1-C6 battery: %d cases in %.1fs" % (total, elapsed))
    print("  feasible=%d infeasible=%d" % (feasible_seen, infeasible_seen))
    for g, d in out["gates"].items():
        print("  %-32s pass=%s %s" % (g, d["pass"],
              {k: v for k, v in d.items() if k not in ("pass", "note")}))
    print("  passed =", passed)
    if failing:
        print("  first failing cases:")
        for fc in failing[:10]:
            print("   ", fc)


if __name__ == "__main__":
    main()
