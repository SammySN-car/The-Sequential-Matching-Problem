"""Exact-cardinality (EXACT-k) maximum-weight matching on general graphs.

Formulation (analysis_plan.md S.4 / S.4.1): the exact-k problem is
reduced to a minimum-weight PERFECT matching of the NEGATED combined
weights on an augmented graph (the frozen plan's min-on-negated form;
negation is exact).

  1. V is exactly the set of vertices incident to >= 1 edge; n = |V|.
  2. Preconditions (asserted, not assumed): E non-empty implies n >= 2,
     0 <= k <= floor(n/2); k = 0 or E empty short-circuits to the empty
     matching without invoking the solver core.
  3. D = n - 2k dummy vertices are added; every dummy is joined to EVERY
     original vertex with combined weight 0 (no tie weight).
  4. A minimum-weight perfect matching of the augmented graph with all
     edge weights negated (N = n + D = 2n - 2k vertices, always even) is
     computed by the min-form primal-dual core.
  5. Original-original edges are extracted; the result has exactly k edges.

Reduction correctness: in any perfect matching of the augmented graph each
dummy is matched with an original (there are no dummy-dummy edges), so
exactly D = n - 2k originals are consumed and exactly 2k remain paired
among themselves: exactly k original edges. Conversely any k-matching of G
extends to a perfect matching of the augmented graph. On the negated
weights the objective is minus the original combined-weight sum, so the
argmin the core computes is the argmax S.4 requires.

Forcing perfection: the core below computes a PLAIN minimum-weight
matching on the negated weights (it does not assume perfection). Every
negated augmented edge weight is -(BIG + C) for originals and -BIG for
dummies, with BIG = 1 + sum(C over all augmented edges). For any matching
of size s its integer weight is -s*BIG - sum(C over its original edges),
so a larger matching has a strictly smaller (more negative) sum than any
smaller one (the BIG surplus exceeds the entire C budget): a
minimum-weight matching is maximum-cardinality first, maximum-sum-C
second. When a perfect matching exists, max cardinality is N/2 and the
result IS perfect and maximises sum C among perfect matchings; when none
exists the returned matching has size < N/2 and InfeasibleKError is
raised. Perfection is checked explicitly, never assumed.

Numerical policy (S.4.1): no rounding or quantisation. Each float weight
is converted EXACTLY via float.as_integer_ratio(); all weights of a state
are scaled to integers with a common power-of-two denominator
(N_i = num_i << (Q - q_i), Q = max q_i). Ties are broken WITHOUT touching
the primary objective: the E original edges are ranked in canonical
(u<v) order, tie weight t_i = 2^(E-1-i), B = 2^E, combined weight
C_i = N_i * B + t_i. Since sum(t over any edge set) < B, maximising sum C
first maximises the exact primary sum, then among primary optima
maximises sum t. Binary tie weights make sum t unique per edge SET, so
the optimal set is unique and equals the lexicographically smallest
primary-optimal k-matching under the canonical edge order (the same
documented tie policy as round2_fixed_cardinality/scripts/fc_matching.py).
No floating-point perturbation is used anywhere.

Algorithm: own-implementation primal-dual (Edmonds/Galil) blossom for
minimum-weight matching on general graphs (min-form dual: margin(e) =
w - p_u - p_v + z >= 0; vertex duals ascend on S, descend on T; the dual
objective increases by delta each step and is bounded by the optimum, so
the algorithm terminates), pure standard library, exact integer
arithmetic (global power-of-two scaling, exact comparisons).
Complexity of the formulation is polynomial; that fact is NOT evidence
about this implementation's runtime - the measured gates in analysis_plan
S.7 decide deployability.

Determinism: no RNG and no clock in the decision path; fixed edge scan
order; the first tight same-tree blossom edge in scan order is processed,
so identical input yields identical output.
"""
import math

__all__ = ["solve_exact_k", "SolverError", "InfeasibleKError"]


class SolverError(Exception):
    """Precondition violation or structural failure inside the solver."""


class InfeasibleKError(SolverError):
    """No vertex-disjoint edge set of exactly k edges exists."""


def _canon(e):
    u, v = e
    return (u, v) if u <= v else (v, u)


def solve_exact_k(edges, weights, k):
    """Max-weight vertex-disjoint set of EXACTLY k edges (see module doc).

    edges:   sequence of (u, v) string pairs, u != v, no duplicate pairs.
    weights: sequence of floats, same length, each in [0, 1).
    k:       int >= 0.

    Returns (indices, meta):
      indices - tuple of input-edge indices, ascending, exactly k of them
                (k = 0 -> ()), maximising the exact sum of weights; among
                primary optima the unique set maximising binary tie
                weights == lexicographically smallest under canonical
                (u<v) sorted edge order.
      meta    - {'n_vertices', 'n_aug_edges', 'aug_N', 'value_int',
                 'value_float'}; value_int is the exact decimal string of
                 the combined integer weight sum of the selected original
                 edges; value_float is math.fsum of the selected floats.

    Raises InfeasibleKError if no size-k matching exists (including
    k > floor(n/2)); SolverError on precondition violation. Never returns
    a partial matching.
    """
    # ---- preconditions -------------------------------------------------
    if len(edges) != len(weights):
        raise SolverError("edges/weights length mismatch: %d vs %d"
                          % (len(edges), len(weights)))
    if not isinstance(k, int) or isinstance(k, bool):
        raise SolverError("k must be an int, got %r" % (k,))
    if k < 0:
        raise SolverError("k must be >= 0, got %d" % k)

    m = len(edges)
    seen = set()
    ws = []
    for i, e in enumerate(edges):
        try:
            u, v = e
        except Exception:
            raise SolverError("edge %d is not a pair: %r" % (i, e))
        if not isinstance(u, str) or not isinstance(v, str):
            raise SolverError("edge %d endpoints must be str: %r" % (i, e))
        if u == v:
            raise SolverError("edge %d is a self-loop: %r" % (i, e))
        c = _canon(e)
        if c in seen:
            raise SolverError("duplicate edge %r (canonical %r)" % (e, c))
        seen.add(c)
        w = weights[i]
        try:
            ratio = w.as_integer_ratio()
        except Exception:
            raise SolverError("weight %d is not a real number: %r" % (i, w))
        if w != w:  # NaN
            raise SolverError("weight %d is NaN" % i)
        if not (0 <= w < 1):
            raise SolverError("weight %d out of [0,1): %r" % (i, w))
        # as_integer_ratio returns (num, 2**exp); S.4.1's q is the
        # EXPONENT, recover it from the power-of-two denominator (the
        # previous code stored the denominator value itself, which makes
        # num << (Q - q) astronomically large for e.g. 0.1 -> MemoryError)
        ws.append((ratio[0], ratio[1].bit_length() - 1))

    # vertex set = incident endpoints only (isolated members excluded)
    verts = sorted({x for e in edges for x in e})
    n = len(verts)

    # ---- short-circuits ------------------------------------------------
    if m == 0 or k == 0:
        if k > n // 2:
            raise InfeasibleKError("k=%d > floor(n/2)=0" % k)
        return (), {"n_vertices": n, "n_aug_edges": 0, "aug_N": 0,
                    "value_int": "0", "value_float": 0.0}
    if k > n // 2:
        raise InfeasibleKError("k=%d > floor(n/2)=%d" % (k, n // 2))
    if n < 2:
        raise InfeasibleKError("fewer than 2 incident vertices with k=%d" % k)

    # ---- exact integer scaling (common power-of-two denominator) ------
    Q = 0
    for _, q in ws:
        if q > Q:
            Q = q
    N = [num << (Q - q) for (num, q) in ws]      # exact integers, N_i >= 0

    # ---- canonical order, tie weights, combined integer weights --------
    order = sorted(range(m), key=lambda i: _canon(edges[i]))  # canon ranks
    rank = [0] * m
    for pos, i in enumerate(order):
        rank[i] = pos
    E = m
    B = 1 << E
    C = [N[i] * B + (1 << (E - 1 - rank[i])) for i in range(m)]
    BIG = 1 + sum(C)

    # ---- augmented graph: originals 0..n-1, dummies n..n+D-1 ----------
    D = n - 2 * k
    Nv = n + D
    vidx = {v: i for i, v in enumerate(verts)}
    aedges = []
    for i in range(m):
        u, v = edges[i]
        # S.4.1: the solver minimises the NEGATED combined weights
        aedges.append((vidx[u], vidx[v], -(BIG + C[i])))
    for d in range(n, Nv):
        for a in range(n):
            aedges.append((d, a, -BIG))          # C = 0 for dummy edges

    mate = _max_weight_matching(Nv, aedges)

    # ---- perfection check + extraction ---------------------------------
    size = sum(1 for x in mate if x >= 0) // 2
    if size * 2 != Nv:
        raise InfeasibleKError(
            "augmented graph has no perfect matching (max cardinality "
            "%d < %d): no size-%d matching exists" % (size, Nv, k))
    chosen = tuple(i for i in range(m)
                   if mate[vidx[edges[i][0]]] == vidx[edges[i][1]])
    if len(chosen) != k:
        raise SolverError("structural: perfect matching yielded %d original "
                          "edges, expected %d" % (len(chosen), k))
    used = set()
    for i in chosen:
        u, v = edges[i]
        if u in used or v in used:
            raise SolverError("structural: vertex reuse in result")
        used.add(u); used.add(v)

    value_int = str(sum(C[i] for i in chosen))
    value_float = math.fsum(weights[i] for i in chosen)
    return tuple(sorted(chosen)), {
        "n_vertices": n,
        "n_aug_edges": len(aedges),
        "aug_N": Nv,
        "value_int": value_int,
        "value_float": value_float,
    }


# ======================================================================
# Primal-dual blossom (Edmonds/Galil; van Rantwijk / networkx core).
#
# MINIMUM-weight matching for the negated combined weights of S.4.1:
# internally W(e) = -w(e) and the algorithm runs in the MAX-form dual,
#   dualvar[v] = 2*u(v) >= 0   (u(v) = maxW/2 initially),
#   bdual[b]   = z(b) >= 0 in doubled units,
#   slack(u,v) = dualvar[u] + dualvar[v] - 2*W(u,v),
# measuring tightness of 2u(u)+2u(v) <= 2W(u,v) for edges whose
# endpoints sit in different top-level containers (a container's z
# constrains only edges INSIDE it).  Maximising sum(W) == minimising
# sum(w), so the returned mate is a minimum-weight matching for the w
# the caller passed in.  All quantities are exact integers in doubled
# units (initial slacks are 2*(maxW - W) >= 0 and every dual step
# shifts a slack by 0 or +-2*delta, so parities never drift).
#
# Laminar blossoms persist across phases with their duals, exactly as
# in van Rantwijk's implementation (networkx algorithms/matching.py):
#   blossompar[c]  laminar parent of child c (vertex or blossom);
#                  None == top-level (all vertices start as None)
#   base[c]        base vertex of container c
#   childs[b]      ring of sub-blossoms, base child at index 0
#   redge[b][j]    ring edge (v, w) with v in childs[j-1], w in childs[j]
#   inb[v]         TOP-level container of v
#   members[c]     flat vertex list of c (leaf traversal)
#   label[c]       1 = S, 2 = T (also per reached vertex inside a
#                  T-blossom); scan_blossom uses 5 as a breadcrumb
#   labeledge[c]   edge (v, w) through which c (or vertex w) was labelled
#   bestedge[c]    least-slack edge out of c (or to unreached vertex w)
#   allowedge      edges known tight for the rest of the stage
#   queue          S-vertices whose neighbours must be scanned
# Only zero-dual blossoms are ever expanded: at stage end (endstage;
# labels die with the stage anyway) or mid-phase via delta4 when a
# T-blossom's dual hits zero - the mid-phase expansion relabels the
# ring path from the entry child to the base child (T/S alternating),
# clearing stale labels before each relabel.  Formation gives the new
# container z = 0 and never rewrites member duals, so NO edge margin
# changes at formation; dissolving a zero-dual container needs no dual
# compensation at all.  The dual objective increases by delta >= 1 per
# dual step and is bounded by the optimum, so the algorithm terminates.
# ======================================================================

def _max_weight_matching(nv, edges):
    """Return mate list for a MINIMUM-weight matching.

    edges: list of (u, v, w) with w a Python int (in this reduction the
    negated combined weights of analysis_plan S.4.1, hence negative).
    Internally the weights are negated and the max-form dual of
    Galil / van Rantwijk (networkx) is applied; maximizing sum(-w)
    yields a minimum-weight matching for the given w.
    """
    if not edges:
        return [-1] * nv

    def _chk(cond, msg):
        if not cond:
            raise SolverError("internal: " + msg)

    # ---- deterministic edge order, max-form weights, adjacency --------
    elist = sorted((min(u, v), max(u, v), w) for (u, v, w) in edges)
    adj = [dict() for _ in range(nv)]
    maxw = 0
    for (u, v, w) in elist:
        _chk(u != v, "self-loop in augmented graph")
        wi = -w
        if wi > maxw:
            maxw = wi
        adj[u][v] = wi
        adj[v][u] = wi

    # ---- primal-dual state -------------------------------------------
    dualvar = [maxw] * nv           # 2*u(v); u = maxw/2 >= 0
    mate = [-1] * nv
    label = {}                      # vertex/container -> 1 (S) / 2 (T)
    labeledge = {}
    bestedge = {}
    allowedge = set()
    queue = []
    blossompar = dict.fromkeys(range(nv), None)  # None == top-level
    base = {v: v for v in range(nv)}
    members = {v: [v] for v in range(nv)}
    childs = {}                     # blossom -> ring children
    redge = {}                      # blossom -> ring edges
    bdual = {}                      # blossom -> z (doubled units, >= 0)
    inb = list(range(nv))           # top-level container of each vertex
    nid = [nv]                      # fresh blossom ids (>= nv)

    def slack(a, b):
        return dualvar[a] + dualvar[b] - 2 * adj[a][b]

    def assign_label(w, t, v):
        # Label the top-level container of w with t (1=S, 2=T), coming
        # through edge (v, w) (v is None for a root S).
        b = inb[w]
        _chk(label.get(w) is None and label.get(b) is None,
             "assign_label on already-labelled container")
        label[w] = label[b] = t
        labeledge[w] = labeledge[b] = None if v is None else (v, w)
        bestedge[w] = bestedge[b] = None
        if t == 1:
            # b became S: all its vertices must be scanned.
            queue.extend(members[b])
        else:
            # b became T (R12): the mate of its base becomes S.
            assign_label(mate[base[b]], 1, base[b])

    def scan_blossom(v, w):
        # Trace the two S-paths from v and w with breadcrumbs; return
        # the base vertex of the blossom they close, or -1 if they form
        # an augmenting path.
        path = []
        found = -1
        while v >= 0:
            b = inb[v]
            lb = label.get(b)
            if lb is not None and lb & 4:
                found = base[b]
                break
            _chk(lb == 1, "scan_blossom hit unlabelled/non-S container")
            path.append(b)
            label[b] = 5
            le = labeledge[b]
            if le is None:
                _chk(mate[base[b]] < 0, "scan_blossom: rooted S is matched")
                v = -1
            else:
                _chk(le[0] == mate[base[b]],
                     "scan_blossom: tree edge not from base's mate")
                v = le[0]
                b = inb[v]
                _chk(label.get(b) == 2, "scan_blossom: step back not T")
                v = labeledge[b][0]
            if w >= 0:
                v, w = w, v
        for b in path:
            label[b] = 1
        return found

    def add_blossom(base_v, v, w):
        # Close the blossom with base base_v through S-vertices v, w.
        bb = inb[base_v]
        bv = inb[v]
        bw = inb[w]
        b = nid[0]
        nid[0] += 1
        base[b] = base_v
        blossompar[b] = None
        blossompar[bb] = b
        path = []
        edgs = [(v, w)]
        while bv != bb:
            blossompar[bv] = b
            path.append(bv)
            edgs.append(labeledge[bv])
            _chk(label.get(bv) == 2 or (
                label.get(bv) == 1 and
                labeledge[bv][0] == mate[base[bv]]),
                "add_blossom: bad v-side child label")
            v = labeledge[bv][0]
            bv = inb[v]
        path.append(bb)
        path.reverse()
        edgs.reverse()
        while bw != bb:
            blossompar[bw] = b
            path.append(bw)
            edgs.append((labeledge[bw][1], labeledge[bw][0]))
            _chk(label.get(bw) == 2 or (
                label.get(bw) == 1 and
                labeledge[bw][0] == mate[base[bw]]),
                "add_blossom: bad w-side child label")
            w = labeledge[bw][0]
            bw = inb[w]
        childs[b] = path
        redge[b] = edgs
        # Ring invariant: edgs[j] joins path[j-1] (at its base) to
        # path[j]; edgs[0] joins the two blossom-forming endpoints.
        _chk(label.get(bb) == 1, "add_blossom: base child not S")
        label[b] = 1
        labeledge[b] = labeledge[bb]
        bdual[b] = 0
        # The T vertices inside turn S (their container is now S);
        # queue them and repoint them at the new container.
        flat = []
        for c in path:
            flat.extend(members[c])
        members[b] = flat
        for x in flat:
            if label.get(inb[x]) == 2:
                queue.append(x)
            inb[x] = b
        # Least-slack edges from b to the other S containers.
        bestedgeto = {}
        for c in path:
            for xc in members[c]:
                for yc in adj[xc]:
                    i2, j2 = xc, yc
                    if inb[j2] == b:
                        i2, j2 = j2, i2
                    bj2 = inb[j2]
                    if (bj2 != b and label.get(bj2) == 1 and
                            ((bj2 not in bestedgeto) or
                             slack(i2, j2) < slack(*bestedgeto[bj2]))):
                        bestedgeto[bj2] = (i2, j2)
            bestedge[c] = None
        mybest = None
        mybestslack = None
        bestedge[b] = None
        for k in bestedgeto.values():
            ks = slack(*k)
            if mybest is None or ks < mybestslack:
                mybest = k
                mybestslack = ks
        bestedge[b] = mybest

    def expand_blossom(b, endstage):
        # Dissolve b into top-level sub-blossoms.  Endstage expansions
        # only need the structural split; a mid-phase T expansion must
        # also relabel the ring path from the entry child to the base.
        def _recurse(b, endstage):
            for s in childs[b]:
                blossompar[s] = None
                if s >= nv:
                    if endstage and bdual[s] == 0:
                        yield s            # recurse into sub-blossom
                    else:
                        for v in members[s]:
                            inb[v] = s
                else:
                    inb[s] = s
            if (not endstage) and label.get(b) == 2:
                # Relabel sub-blossoms along the even ring path from
                # the entry child round to the base child.
                entrychild = inb[labeledge[b][1]]
                j = childs[b].index(entrychild)
                if j & 1:
                    j -= len(childs[b])
                    jstep = 1
                else:
                    jstep = -1
                v, w = labeledge[b]
                while j != 0:
                    if jstep == 1:
                        p, q = redge[b][j]
                    else:
                        q, p = redge[b][j - 1]
                    label[w] = None
                    label[q] = None
                    assign_label(w, 2, v)
                    allowedge.add((p, q))
                    allowedge.add((q, p))
                    j += jstep
                    if jstep == 1:
                        v, w = redge[b][j]
                    else:
                        w, v = redge[b][j - 1]
                    allowedge.add((v, w))
                    allowedge.add((w, v))
                    j += jstep
                # The base child turns T WITHOUT stepping to its mate
                # (the augmenting trace handles the base's own edge).
                bw = childs[b][j]
                label[w] = label[bw] = 2
                labeledge[w] = labeledge[bw] = (v, w)
                bestedge[bw] = None
                # The rest of the ring: a sub-blossom containing a
                # vertex reached from outside turns S through it.
                j += jstep
                while childs[b][j] != entrychild:
                    bc = childs[b][j]
                    if label.get(bc) == 1:
                        j += jstep
                        continue
                    if bc >= nv:
                        hit = None
                        for x in members[bc]:
                            if label.get(x):
                                hit = x
                                break
                    else:
                        hit = bc
                    if hit is not None and label.get(hit):
                        _chk(label[hit] == 2 and inb[hit] == bc,
                             "expand: reached vertex in wrong sub-blossom")
                        label[hit] = None
                        label[mate[base[bc]]] = None
                        assign_label(hit, 2, labeledge[hit][0])
                    j += jstep
            # Remove b entirely.
            label.pop(b, None)
            labeledge.pop(b, None)
            bestedge.pop(b, None)
            del blossompar[b]
            del base[b]
            del bdual[b]
            del childs[b]
            del redge[b]
            del members[b]

        # Generator trampoline keeps the call stack flat (as in
        # networkx): each recursive expansion is one generator.
        gens = [_recurse(b, endstage)]
        while gens:
            g = gens[-1]
            for s in g:
                gens.append(_recurse(s, endstage))
                break
            else:
                gens.pop()

    def augment_blossom(b, v):
        # Flip matched/unmatched along the ring path from vertex v to
        # the base of b; v becomes the new base of b.
        def _recurse(b, v):
            # Climb the laminar chain to the immediate child of b
            # that contains v.
            t = v
            while blossompar[t] != b:
                t = blossompar[t]
            if t >= nv:
                yield (t, v)
            i = j = childs[b].index(t)
            if i & 1:
                j -= len(childs[b])
                jstep = 1
            else:
                jstep = -1
            while j != 0:
                j += jstep
                t = childs[b][j]
                if jstep == 1:
                    w, x = redge[b][j]
                else:
                    x, w = redge[b][j - 1]
                if t >= nv:
                    yield (t, w)
                j += jstep
                t = childs[b][j]
                if t >= nv:
                    yield (t, x)
                mate[w] = x
                mate[x] = w
            # Rotate the ring so the new base child sits at the front.
            c = childs[b]
            r = redge[b]
            childs[b] = c[i:] + c[:i]
            redge[b] = r[i:] + r[:i]
            base[b] = base[childs[b][0]]
            _chk(base[b] == v, "augment_blossom: rotation lost the base")

        gens = [_recurse(b, v)]
        while gens:
            g = gens[-1]
            for args in g:
                gens.append(_recurse(*args))
                break
            else:
                gens.pop()

    def augment_matching(v, w):
        # Augment along the S-alternating path between v and w.
        for s, j in ((v, w), (w, v)):
            while True:
                bs = inb[s]
                _chk(label.get(bs) == 1, "augment: trace not in S")
                _chk((labeledge[bs] is None and mate[base[bs]] < 0) or
                     (labeledge[bs][0] == mate[base[bs]]),
                     "augment: S-container not entered at base's mate")
                if bs >= nv:
                    augment_blossom(bs, s)
                mate[s] = j
                if labeledge[bs] is None:
                    break                   # reached a single vertex
                t = labeledge[bs][0]
                bt = inb[t]
                _chk(label.get(bt) == 2, "augment: back-link not T")
                s, j = labeledge[bt]
                _chk(base[bt] == t,
                     "augment: T-container not entered at its base")
                if bt >= nv:
                    augment_blossom(bt, j)
                mate[j] = s

    # ---- main loop: one stage per augmenting path ---------------------
    while True:
        label.clear()
        labeledge.clear()
        bestedge.clear()
        allowedge.clear()
        del queue[:]
        # Every free vertex's container becomes a root S.
        for v in range(nv):
            if mate[v] < 0 and label.get(inb[v]) is None:
                assign_label(v, 1, None)

        augmented = 0
        while True:
            # Grow the alternating forest by scanning queued S-vertices.
            while queue and not augmented:
                v = queue.pop()
                _chk(label.get(inb[v]) == 1, "queue: vertex not in S")
                for w in adj[v]:
                    if w == v:
                        continue
                    bv = inb[v]
                    bw = inb[w]
                    if bv == bw:
                        continue            # edge internal to a blossom
                    kslack = None
                    if (v, w) not in allowedge:
                        kslack = slack(v, w)
                        if kslack <= 0:
                            allowedge.add((v, w))
                            allowedge.add((w, v))
                    if (v, w) in allowedge:
                        if label.get(bw) is None:
                            # (C1) reach w: its container becomes T,
                            # the mate of its base becomes S.
                            assign_label(w, 2, v)
                        elif label.get(bw) == 1:
                            # (C2) two S containers: augmenting path or
                            # a new blossom closing the tree.
                            found = scan_blossom(v, w)
                            if found >= 0:
                                add_blossom(found, v, w)
                            else:
                                augment_matching(v, w)
                                augmented = 1
                                break
                        elif label.get(w) is None:
                            # Reached w inside a T-blossom; mark it so
                            # a later T-expansion can relabel through it.
                            _chk(label.get(bw) == 2,
                                 "reached vertex not in T")
                            label[w] = 2
                            labeledge[w] = (v, w)
                    elif label.get(bw) == 1:
                        # Non-allowable S-S edge: track the least one.
                        if (bestedge.get(bv) is None or
                                kslack < slack(*bestedge[bv])):
                            bestedge[bv] = (v, w)
                    elif label.get(w) is None:
                        # Edge to an unreached free vertex: track the
                        # least-slack one for delta2.
                        if (bestedge.get(w) is None or
                                kslack < slack(*bestedge[w])):
                            bestedge[w] = (v, w)
            if augmented:
                break

            # No augmenting path under these constraints: pump the duals.
            # delta1: raise the smallest vertex dual.
            deltatype = 1
            delta = min(dualvar)
            deltaedge = None
            deltablossom = None
            # delta2: least slack S -> unreached-free.
            for v in range(nv):
                if label.get(inb[v]) is None and bestedge.get(v) is not None:
                    d = slack(*bestedge[v])
                    if d < delta:
                        delta = d
                        deltatype = 2
                        deltaedge = bestedge[v]
            # delta3: half the least slack between two S containers.
            for b in blossompar:
                if (blossompar[b] is None and label.get(b) == 1 and
                        bestedge.get(b) is not None):
                    kslack = slack(*bestedge[b])
                    _chk((kslack & 1) == 0, "delta3: odd slack")
                    d = kslack >> 1
                    if d < delta:
                        delta = d
                        deltatype = 3
                        deltaedge = bestedge[b]
            # delta4: smallest dual of a T-blossom.
            for b in bdual:
                if (blossompar[b] is None and label.get(b) == 2 and
                        bdual[b] < delta):
                    delta = bdual[b]
                    deltatype = 4
                    deltablossom = b

            if deltatype == 1:
                break                       # optimum reached

            # Dual update: S-vertices descend, T-vertices rise; a
            # top-level S-blossom gains 2*delta, a T-blossom loses it.
            for v in range(nv):
                lb = label.get(inb[v])
                if lb == 1:
                    dualvar[v] -= delta
                elif lb == 2:
                    dualvar[v] += delta
            for b in bdual:
                if blossompar[b] is None:
                    lb = label.get(b)
                    if lb == 1:
                        bdual[b] += delta
                    elif lb == 2:
                        bdual[b] -= delta
            if deltatype == 2 or deltatype == 3:
                a2, b2 = deltaedge
                _chk(label.get(inb[a2]) == 1, "delta edge not from S")
                allowedge.add((a2, b2))
                allowedge.add((b2, a2))
                queue.append(a2)
            else:
                # delta4: the T-blossom's dual hit zero; expand it and
                # relabel its ring path mid-phase.
                expand_blossom(deltablossom, False)

        # Paranoia: the mate list stays symmetric.
        for x in mate:
            if x >= 0:
                _chk(mate[x] >= 0 and mate[mate[x]] == x,
                     "mate list not symmetric")
        if not augmented:
            break
        # Stage end: dissolve every zero-dual top-level S-blossom.
        for b in list(bdual):
            if b not in bdual:
                continue                    # already dissolved
            if (blossompar[b] is None and label.get(b) == 1 and
                    bdual[b] == 0):
                expand_blossom(b, True)

    return mate
