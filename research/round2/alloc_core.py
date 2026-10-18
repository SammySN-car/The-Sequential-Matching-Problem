"""Round 2 core: greedy parity, exact max-weight solver, frozen adoption gate.

PREREGISTERED: research/round2/design.md (frozen 2026-10-12). No tunable constants.
Solver attribution: O(n^3) Hungarian assignment (Vorobyev / e-maxx formulation),
re-implemented here from research/method_tournament/alloc.py:hungarian_max_weight
with ONE intentional change: zero-weight real pairs are RETAINED in the output
(m25's w>0 filter caused the cardinality collapse documented in design section 2).
Stdlib only; deterministic (all node lists sorted; no hash-order dependence).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root: kit
from kit import SOFT, eligibility  # noqa: E402  (frozen kit, READ-ONLY)

HUNGARIAN_NODE_CAP = 180  # frozen: common.HUNGARIAN_NODE_CAP (tournament constant)


def pair_key(a, b):
    return tuple(sorted((a, b)))


def base_score(a, b):
    """Observed equal-SOFT-field count: identical to kit.baseline_match scoring."""
    return sum(a['fields'].get(k) is not None and a['fields'].get(k) == b['fields'].get(k)
               for k in SOFT)


def feasible_edges(state):
    """[(id_a, id_b, score)] for available, feasible, never-introduced pairs.

    Same graph kit.baseline_match enumerates; sorted by member id for determinism."""
    ms = sorted((m for m in state['members'] if m['available']), key=lambda m: m['member_id'])
    past = {pair_key(i['user_a'], i['user_b']) for i in state['introductions']}
    out = []
    for i, a in enumerate(ms):
        for b in ms[i + 1:]:
            if pair_key(a['member_id'], b['member_id']) in past:
                continue
            if eligibility(a, b)['status'] != 'feasible':
                continue
            out.append((a['member_id'], b['member_id'], base_score(a, b)))
    return out


def greedy_matching(edges):
    """Official greedy: sort by (-score, pair_key), take non-overlapping.
    Byte-equal behaviour to kit.baseline_match (verified in tests)."""
    used = set()
    out = []
    for _, pair in sorted(((-s, pair_key(a, b)) for a, b, s in edges)):
        if pair[0] in used or pair[1] in used:
            continue
        out.append(list(pair))
        used.add(pair[0])
        used.add(pair[1])
    return out


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


def hungarian_max_weight(left, right, weight):
    """Exact maximum-weight assignment, e-maxx O(n^3). Pads to square with dummy
    nodes (dummy edges weight 0). Returns sorted list of (u, v) over REAL pairs,
    INCLUDING zero-weight pairs (intentional change vs tournament m25)."""
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
        if (u_id, v_id) in weight:      # existing edges only (zero-weight kept; non-edges excluded)
            pairs.append((u_id, v_id))
    return sorted(pairs)


def edge_sum(pairs, edges):
    w = {pair_key(a, b): s for a, b, s in edges}
    return sum(w.get(pair_key(x, y), 0) for x, y in pairs)


def apply_gate(greedy_pairs, greedy_k, greedy_sum, exact_pairs, exact_sum):
    """FROZEN gate (design.md 3.1): adopt exact iff cardinality >= greedy AND
    score sum strictly greater. Returns (chosen, info)."""
    info = {'greedy_k': greedy_k, 'greedy_sum': greedy_sum,
            'exact_k': None if exact_pairs is None else len(exact_pairs),
            'exact_sum': exact_sum if exact_pairs is not None else None,
            'score_gain': None, 'cardinality_change': None, 'reason': None}
    if exact_pairs is None:
        info['reason'] = 'exact_unavailable'
        return 'greedy', info
    if len(exact_pairs) < greedy_k:
        info['reason'] = 'g1_cardinality_loss'
        return 'greedy', info
    if not exact_sum > greedy_sum:
        info['reason'] = 'g2_no_strict_gain'
        return 'greedy', info
    info['reason'] = 'adopted'
    info['score_gain'] = exact_sum - greedy_sum
    info['cardinality_change'] = len(exact_pairs) - greedy_k
    return 'exact', info


def solve_exact(edges):
    """Exact branch when E1 (bipartite) and E2 (node cap) hold; else (None, reason)."""
    colored = two_color(edges)
    if colored is None:
        return None, 'non_bipartite'
    left, right = colored
    nodes = len(left) + len(right)
    if nodes > HUNGARIAN_NODE_CAP:
        return None, 'over_cap'
    if not edges:
        return [], 'empty_graph'
    wmap = {}
    for a, b, s in edges:
        wmap[(a, b)] = s
        wmap[(b, a)] = s
    return hungarian_max_weight(left, right, wmap), 'exact'


def allocate(state, arm):
    """Match-phase allocation. arm in {'gated', 'ungated'}.

    Returns (pairs, telemetry). Arms differ ONLY in adoption rule (design 3.1).
    Ask phase is handled by the launcher, not here."""
    edges = feasible_edges(state)
    greedy = greedy_matching(edges)
    g_k, g_sum = len(greedy), edge_sum(greedy, edges)
    exact, status = solve_exact(edges)
    telemetry = {'solver_tried': True, 'solver': status,
                 'bipartite': status in ('exact', 'empty_graph'),
                 'nodes': None, 'gate_adopted_exact': False,
                 'reject_reason': None, 'score_gain': None, 'cardinality_change': None,
                 'greedy_k': g_k, 'greedy_sum': g_sum,
                 'exact_k': None if exact is None else len(exact),
                 'exact_sum': None if exact is None else edge_sum(exact, edges)}
    colored = two_color(edges)
    if colored is not None:
        telemetry['nodes'] = len(colored[0]) + len(colored[1])
    if arm == 'ungated':
        if exact is None:
            telemetry['reject_reason'] = status
            return greedy, telemetry
        e_sum = edge_sum(exact, edges)
        telemetry['gate_adopted_exact'] = True
        telemetry['score_gain'] = e_sum - g_sum
        telemetry['cardinality_change'] = len(exact) - g_k
        return [list(p) for p in exact], telemetry
    if arm != 'gated':
        raise ValueError('unknown arm: ' + repr(arm))
    chosen, info = apply_gate(greedy, g_k, g_sum, exact,
                              None if exact is None else edge_sum(exact, edges))
    telemetry['reject_reason'] = info['reason'] if chosen == 'greedy' else None
    telemetry['score_gain'] = info['score_gain']
    telemetry['cardinality_change'] = info['cardinality_change']
    if chosen == 'exact':
        telemetry['gate_adopted_exact'] = True
        return [list(p) for p in exact], telemetry
    return greedy, telemetry