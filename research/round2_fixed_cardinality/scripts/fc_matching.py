"""Exact-cardinality (EXACT-k) maximum-weight matching.

Problem: given edges E with weights w and integer k, find a vertex-disjoint
M subset of E with |M| = k maximising sum of w over M.

This is NOT the same as a max-weight matching (which is free to choose its own
size) and NOT the same as a max-cardinality matching. Cardinality is a hard
constraint; if it cannot be met the solver reports failure rather than silently
returning a smaller matching.

Determinism: the returned matching is the lexicographically smallest optimal
size-k matching under the canonical edge ordering (u,v) with u < v.
"""
from typing import Iterable, List, Optional, Sequence, Tuple

NODE_LIMIT = 8_000_000
EPS = 1e-9


def _canon(e):
    return (e[0], e[1]) if e[0] <= e[1] else (e[1], e[0])


def _canonical_order(edges):
    """Return index order sorted by canonical (u, v) key."""
    return sorted(range(len(edges)), key=lambda i: _canon(edges[i]))


def solve_exact_k(edges: Sequence[Tuple[str, str]],
                  weights: Sequence[float],
                  k: int,
                  ) -> Tuple[Optional[Tuple[int, ...]], Optional[float], int, bool]:
    """Max-weight vertex-disjoint set of EXACTLY k edges.

    Returns (edge_indices, objective, nodes_visited, failed).
    edge_indices are indices into the input `edges` sequence.
    failed=True means the node limit was breached, in which case the objective
    is None and the caller MUST report the failure.
    """
    n = len(edges)
    if k == 0:
        return (), 0.0, 0, False
    if k < 0 or n == 0 or k > n:
        return None, None, 0, False          # infeasible

    # ---- pass 1: find the optimal objective by branch and bound -------------
    order = sorted(range(n), key=lambda i: (-weights[i], _canon(edges[i])))
    E1 = [edges[i] for i in order]
    W1 = [weights[i] for i in order]
    prefix = [0.0] * (n + 1)                 # prefix[j] = sum of j largest
    for i in range(n):
        prefix[i + 1] = prefix[i] + W1[i]

    best_val = [float('-inf')]
    nodes = [0]
    failed = [False]

    def dfs(idx, size, wsum):
        if failed[0]:
            return
        nodes[0] += 1
        if nodes[0] > NODE_LIMIT:
            failed[0] = True
            return
        if size == k:
            if wsum > best_val[0]:
                best_val[0] = wsum
            return
        if idx >= n:
            return
        if size + (n - idx) < k:             # cannot reach k edges
            return
        need = k - size
        if idx + need <= n:
            if wsum + (prefix[idx + need] - prefix[idx]) <= best_val[0] and \
                    best_val[0] > float('-inf'):
                return                        # cannot improve the objective
        # include edge idx if free
        u, v = E1[idx]
        if u not in used and v not in used:
            used.add(u); used.add(v)
            dfs(idx + 1, size + 1, wsum + W1[idx])
            used.discard(u); used.discard(v)
        # exclude edge idx
        dfs(idx + 1, size, wsum)

    used = set()
    dfs(0, 0, 0.0)
    if failed[0]:
        return None, None, nodes[0], True
    if best_val[0] == float('-inf'):
        return None, None, nodes[0], False   # no size-k matching exists

    opt = best_val[0]

    # ---- pass 2: lex-smallest size-k matching achieving exactly opt ---------
    # Search in canonical (u,v) order, include-first, so the first complete
    # solution found is the lexicographically smallest index set.
    canon = _canonical_order(edges)
    E2 = [edges[i] for i in canon]
    W2 = [weights[i] for i in canon]
    solution = [None]

    def dfs2(idx, size, wsum, chosen):
        if solution[0] is not None:
            return
        nodes[0] += 1
        if nodes[0] > NODE_LIMIT * 2:
            failed[0] = True
            return
        if size == k:
            if abs(wsum - opt) <= EPS:
                solution[0] = tuple(chosen)
            return
        if idx >= n or size + (n - idx) < k:
            return
        u, v = E2[idx]
        if u not in used and v not in used:
            used.add(u); used.add(v)
            dfs2(idx + 1, size + 1, wsum + W2[idx], chosen + [canon[idx]])
            used.discard(u); used.discard(v)
        if solution[0] is None:
            dfs2(idx + 1, size, wsum, chosen)

    used = set()
    dfs2(0, 0, 0.0, [])
    if failed[0]:
        return None, None, nodes[0], True
    if solution[0] is None:
        return None, None, nodes[0], False
    return solution[0], float(sum(weights[i] for i in solution[0])), nodes[0], False


def brute_force_exact_k(edges, weights, k):
    """Exhaustive reference for small n. Returns best value or None."""
    n = len(edges)
    if k == 0:
        return 0.0
    best = None
    for mask in range(1 << n):
        used, ok, tot, cnt = set(), True, 0.0, 0
        for i in range(n):
            if mask >> i & 1:
                u, v = edges[i]
                if u in used or v in used:
                    ok = False
                    break
                used.add(u); used.add(v); tot += weights[i]; cnt += 1
        if ok and cnt == k and (best is None or tot > best):
            best = tot
    return best


def check_matching(edges, chosen, k):
    """Return (ok, reason). Enforces exactly k, feasible edges, no repeats."""
    if len(chosen) != k:
        return False, 'size %d != k %d' % (len(chosen), k)
    eset = {_canon(e) for e in edges}
    used = set()
    for i in chosen:
        if i < 0 or i >= len(edges):
            return False, 'index %d out of range' % i
        if _canon(edges[i]) not in eset:
            return False, 'infeasible edge %r' % (edges[i],)
        u, v = edges[i]
        if u in used or v in used:
            return False, 'repeated member in %r' % (edges[i],)
        used.add(u); used.add(v)
    return True, ''
