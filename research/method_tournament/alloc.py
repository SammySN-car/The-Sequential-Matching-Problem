"""Allocation primitives: greedy take and temporal gates.

Constants are FROZEN per design.md section 6. Graph algorithms (Kuhn, Hungarian,
one-swap, augmenting) are added by Task 4 in the same file.
"""
from common import (pair_key, wait_days, QUOTA_DIVISOR, PROTECT_DAYS, THIN_AVG_DEG,
                    HYBRID_MIN_SCORE, HYBRID_AVG_DEG)


def _take(ordered):
    used = set()
    out = []
    for a, b in ordered:
        if a in used or b in used:
            continue
        out.append([a, b])
        used.add(a)
        used.add(b)
    return out


def greedy_take(edges):
    """Sort by (-score, pair_key) then take non-overlapping: identical to kit.baseline_match."""
    ordered = [(a, b) for a, b, s in sorted(edges, key=lambda e: (-e[2], pair_key(e[0], e[1])))]
    return _take(ordered)


def take_ordered(edges, key_fn):
    """Same non-overlap scan under a caller-supplied deterministic sort key."""
    ordered = [(a, b) for a, b, s in sorted(edges, key=key_fn)]
    return _take(ordered)


def filter_min_score(edges, minimum):
    return [e for e in edges if e[2] >= minimum]


def quota_half(pairs):
    """Keep ceil(n / QUOTA_DIVISOR) pairs; withheld pairs stay available for later days."""
    n_keep = (len(pairs) + QUOTA_DIVISOR - 1) // QUOTA_DIVISOR
    return pairs[:n_keep]


def protect_filter(edges, ctx):
    day, mfs = ctx['day'], ctx['members']
    return [e for e in edges
            if min(wait_days(mfs[e[0]], day), wait_days(mfs[e[1]], day)) >= PROTECT_DAYS]


def thin_wait(ctx):
    """m22: today's graph is thin -> wait (match nothing)."""
    return ctx['avg_deg'] < THIN_AVG_DEG


def hybrid_favorable(ctx):
    """m23: strong top pair OR dense graph -> greedy now."""
    return ctx['max_base'] >= HYBRID_MIN_SCORE or ctx['avg_deg'] >= HYBRID_AVG_DEG

# --- Graph algorithms -------------------------------------------------------

def _adjacency(edges):
    adj = {}
    for a, b, s in edges:
        adj.setdefault(a, []).append((s, b))
        adj.setdefault(b, []).append((s, a))
    for u in adj:
        adj[u].sort(key=lambda t: (-t[0], t[1]))
    return adj


def two_color(edges):
    """Deterministic BFS 2-coloring. Returns (left, right) sorted, or None on odd cycles."""
    adj = _adjacency(edges)
    color = {}
    for start in sorted(adj):
        if start in color:
            continue
        color[start] = 0
        queue = [start]
        while queue:
            u = queue.pop(0)
            for _, v in adj[u]:
                if v not in color:
                    color[v] = 1 - color[u]
                    queue.append(v)
                elif color[v] == color[u]:
                    return None
    return (sorted(u for u in color if color[u] == 0),
            sorted(u for u in color if color[u] == 1))


def max_cardinality(edges):
    """Exact maximum-cardinality matching on bipartite graphs (Kuhn augmenting paths).
    Adjacency prefers higher base scores as the secondary heuristic. None when not bipartite."""
    colored = two_color(edges)
    if colored is None:
        return None
    left, right = colored
    adj = _adjacency(edges)
    match_r = {}

    def try_k(u, seen):
        for _, v in adj.get(u, ()):
            if v in seen:
                continue
            seen.add(v)
            if v not in match_r or try_k(match_r[v], seen):
                match_r[v] = u
                return True
        return False

    for u in sorted(left):
        try_k(u, set())
    return sorted([[match_r[v], v] for v in sorted(match_r)])


def hungarian_max_weight(left, right, weight):
    """E-maxx O(n^3) assignment maximizing sum of weight[(u, v)] over allowed pairs.
    Pads to square with dummy nodes; disallowed pairs cost MAXW and are filtered out
    afterwards (exact: zero-weight removal cannot change the optimum value).
    weight must map both orientations. Returns sorted list of (u, v) with weight > 0."""
    n0, m0 = len(left), len(right)
    if n0 == 0 or m0 == 0:
        return []
    maxw = max(weight.values()) if weight else 0
    n = max(n0, m0)
    left_p = list(left) + [None] * (n - n0)
    right_p = list(right) + [None] * (n - m0)

    def w_of(i, j):
        u, v = left_p[i], right_p[j]
        if u is None or v is None:
            return 0
        return weight.get((u, v), 0)

    a = [[0.0] * (n + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        row = a[i]
        for j in range(1, n + 1):
            row[j] = float(maxw - w_of(i - 1, j - 1))
    u = [0.0] * (n + 1)
    v = [0.0] * (n + 1)
    p = [0] * (n + 1)
    way = [0] * (n + 1)
    inf = float('inf')
    for i in range(1, n + 1):
        p[0] = i
        j0 = 0
        minv = [inf] * (n + 1)
        used = [False] * (n + 1)
        while True:
            used[j0] = True
            i0 = p[j0]
            delta = inf
            j1 = 0
            for j in range(1, n + 1):
                if used[j]:
                    continue
                cur = a[i0][j] - u[i0] - v[j]
                if cur < minv[j]:
                    minv[j] = cur
                    way[j] = j0
                if minv[j] < delta:
                    delta = minv[j]
                    j1 = j
            for j in range(n + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while j0:
            p[j0] = p[way[j0]]
            j0 = way[j0]
    pairs = []
    for j in range(1, n + 1):
        i = p[j]
        if i == 0:
            continue
        u_id, v_id = left_p[i - 1], right_p[j - 1]
        if u_id is None or v_id is None:
            continue
        if w_of(i - 1, j - 1) > 0:
            pairs.append((u_id, v_id))
    return sorted(pairs)


def one_swap_improve(pairs, edges):
    """Greedy local improvement: swap partner pairs while total base weight strictly grows.
    Integer weights guarantee termination."""
    weight = {pair_key(a, b): s for a, b, s in edges}

    def w(x, y):
        return weight.get(pair_key(x, y), -1)

    pairs = [list(p) for p in pairs]
    improved = True
    while improved:
        improved = False
        for i in range(len(pairs)):
            for j in range(i + 1, len(pairs)):
                a, b = pairs[i]
                c, d = pairs[j]
                for x, y, z, t in ((a, d, c, b), (a, c, b, d)):
                    if w(x, y) < 0 or w(z, t) < 0:
                        continue
                    if w(x, y) + w(z, t) > w(a, b) + w(c, d):
                        pairs[i], pairs[j] = [x, y], [z, t]
                        improved = True
                        break
                if improved:
                    break
            if improved:
                break
    pairs.sort(key=lambda pr: pair_key(pr[0], pr[1]))
    return pairs


def augment3_improve(pairs, edges, rounds_cap):
    """Short augmenting exchanges: unmatch (x, x'), add (x, y) with y free adjacent to x and
    (x', z) with z free adjacent to x'; cardinality grows by 1. Capped by rounds_cap."""
    adj = _adjacency(edges)
    pairs = [list(p) for p in pairs]
    for _ in range(rounds_cap):
        matched = {}
        for idx, (x, y) in enumerate(pairs):
            matched[x] = (idx, y)
            matched[y] = (idx, x)
        free = set(adj) - set(matched)
        grew = False
        for x in sorted(matched):
            idx, xp = matched[x]
            free_x = [v for _, v in adj.get(x, ()) if v in free]
            free_xp = [v for _, v in adj.get(xp, ()) if v in free]
            if not free_x or not free_xp:
                continue
            y = free_x[0]
            z = free_xp[0]
            if y == z:
                continue
            pairs[idx] = [x, y]
            pairs.append([xp, z])
            grew = True
            break
        if not grew:
            break
    pairs.sort(key=lambda pr: pair_key(pr[0], pr[1]))
    return pairs


def brute_max_weight(edges):
    """Exhaustive maximum-weight matching. TEST REFERENCE ONLY (n <= 8 nodes)."""
    weight = {pair_key(a, b): s for a, b, s in edges}
    nodes = sorted({m for a, b, s in edges for m in (a, b)})
    best = ([], 0)

    def rec(i, used, chosen, total):
        nonlocal best
        if i == len(nodes):
            if total > best[1]:
                best = (sorted(chosen), total)
            return
        u = nodes[i]
        if u in used:
            rec(i + 1, used, chosen, total)
            return
        rec(i + 1, used, chosen, total)
        for v in nodes[i + 1:]:
            if v in used or pair_key(u, v) not in weight:
                continue
            chosen.append((u, v))
            rec(i + 1, used | {v, u}, chosen, total + weight[pair_key(u, v)])
            chosen.pop()

    rec(0, set(), [], 0)
    return best
