"""Shared helpers for the Decision Opportunity and Counterfactual Ceiling Audit.

Read-only with respect to every protected artifact (GC1). All outputs land in
research/round2_decision_ceiling/ (GC2). stdlib only at import time so that
importing this module can never fail on a missing optional dependency.
"""
import copy, hashlib, json, sys, time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent          # .../round2_decision_ceiling/scripts
OUT = HERE.parent                               # .../round2_decision_ceiling
ROOT = OUT.parents[1]                           # repository root
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'research' / 'next_method_search'))

import kit                                        # noqa: E402
import n01_autopsy as n01                          # noqa: E402

N01 = ROOT / 'research' / 'next_method_search'
FROZEN_INTROS = N01 / 'n01_introductions.jsonl'
FROZEN_DAYS = N01 / 'n01_days.jsonl'
FROZEN_ROWS = N01 / 'n01_replay_rows.jsonl'
FROZEN_SUMMARY = N01 / 'n01_replay_summary.json'
HORIZON = 100          # evaluate.episode: 60 decision days + 40 follow-up days
DECISION_DAYS = 60

BANNED_FEATURE_EXACT = {'seed', 'variant', 'exit_day', 'truth', 'bias',
                        'response_rate', 'second_bias'}
BANNED_FEATURE_PREFIXES = ('cf_', 'y_', 'label')


def log(msg):
    line = '[%s] %s' % (time.strftime('%Y-%m-%dT%H:%M:%S'), msg)
    print(line, flush=True)
    with open(OUT / 'run_log.txt', 'a', encoding='utf-8') as fh:
        fh.write(line + '\n')


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def protected_files():
    files = [ROOT / 'kit.py', ROOT / 'policy.py', ROOT / 'policy_ac.py',
             ROOT / 'evaluate.py', ROOT / 'Dockerfile']
    files += sorted(ROOT.glob('tests/**/*.py'))
    for d in ('round2_eda', 'round2_opr', 'method_tournament',
              'round2_promotion_fresh_seeds', 'next_method_search'):
        p = ROOT / 'research' / d
        if p.is_dir():
            files += [x for x in p.rglob('*') if x.is_file()]
    files += sorted(x for x in (ROOT / 'research').glob('out*/*') if x.is_file())
    return sorted({f for f in files if f.is_file()})


def write_manifest(path, files):
    """sha256 of every protected file, keyed by repo-relative POSIX path."""
    man = {f.relative_to(ROOT).as_posix(): sha256(f) for f in files}
    Path(path).write_text(json.dumps(man, indent=1, sort_keys=True) + '\n',
                          encoding='utf-8')
    return man


def world_list():
    """126 frozen control worlds as (seed, variant), in n01 file order."""
    seen, out = set(), []
    for line in FROZEN_ROWS.read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        key = (int(row['seed']), row['variant'])
        if key not in seen:
            seen.add(key)
            out.append(key)
    return out


def read_jsonl(path):
    with open(path, encoding='utf-8') as fh:
        return [json.loads(l) for l in fh if l.strip()]


def write_jsonl(path, rows):
    with open(path, 'w', encoding='utf-8') as fh:
        for r in rows:
            fh.write(json.dumps(r, sort_keys=True) + '\n')
    log('wrote %s (%d rows)' % (Path(path).name, len(rows)))


def frozen_intro_index():
    """(seed, variant, introduction_id) -> frozen row from n01_introductions."""
    return {(r['seed'], r['variant'], r['introduction_id']): r
            for r in read_jsonl(FROZEN_INTROS)}


def frozen_world_rows():
    return {(r['seed'], r['variant']): r for r in read_jsonl(FROZEN_ROWS)}


def save_g0(results, path=None):
    path = Path(path or (OUT / 'g0_results.json'))
    prev = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    prev.update(results)
    path.write_text(json.dumps(prev, indent=1, sort_keys=True) + '\n',
                    encoding='utf-8')
    log('g0_results.json updated: ' + ', '.join(sorted(results)))
    return prev


# --- G0 primitives (plan Task 1) -------------------------------------------

MUTABLE = ('introductions', 'events', 'past', 'busy')
# kit.Simulator.advance() (kit.py L141-189) writes ONLY these four containers,
# plus rebinding self.day and self.ask_spent. members and world are read-only
# inside advance; retired and ask_log are untouched. Source-verified (GC5).


def clone_from(snap):
    """Exact decision-time state for one isolated advance([pair]) run.

    Shallow-copies the simulator, then gives the copy its own instances of the
    four containers advance() mutates, so a pair-alone run cannot leak back into
    the snapshot later pairs are replayed from.
    """
    s = copy.copy(snap)
    # Shallow container copies are exact: advance() appends to introductions and
    # events, adds to past, and reassigns busy entries - it never mutates an
    # existing element in place (kit.py L141-189). Verified by G0 T3, which
    # requires 8433/8433 exact agreement with the frozen rollout.
    s.introductions = list(snap.introductions)
    s.events = list(snap.events)
    s.past = set(snap.past)
    s.busy = dict(snap.busy)
    return s


def snapshot_fingerprint(snap):
    """Leak assertion digest for the four containers advance() mutates.

    introductions, events and past are append-only inside advance(), so their
    lengths detect any write; busy is updated in place, so its (key, value)
    contents are digested. Equivalent detection power to hashing every element,
    without the quadratic cost of serialising the full event log.
    """
    h = hashlib.sha256()
    h.update(b'%d,%d,%d' % (len(snap.introductions), len(snap.events),
                            len(snap.past)))
    h.update(repr(sorted(snap.busy.items())).encode())
    return h.hexdigest()


def intro_mid(a, b, day):
    return 'intro_' + hashlib.sha256(
        '%s|%s|%s' % (min(a, b), max(a, b), day).encode()).hexdigest()[:24]


def labels_from_events(mid, events, final_day, assigned_day):
    """research/labels.py semantics, copied from n01_autopsy.py L316-341.

    Returns None-valued labels when not mature; callers MUST propagate None and
    never coerce it to 0 (analysis_plan.md V3).
    """
    es = [e for e in events if e['introduction_id'] == mid]
    if not (es and all(e['observed_day'] <= final_day for e in es)):
        return dict(mature=0, y_msmi=None, y_mutual=None, y_date=None,
                    y_second=None, missing=None)
    rs = [e for e in es if e['event'] == 'introduction_response']
    y_mutual = int(len(rs) == 2 and all(e['value'] == 'yes' for e in rs))
    ds = [e for e in es if e['event'] == 'date_happened' and e['value'] is True]
    y_date = int(bool(ds))
    ss = [e for e in es if e['event'] == 'second_meeting_intention']
    second_ok = bool(ds) and len(ss) == 2 and all(
        e['value'] == 'yes'
        and e['occurred_day'] - ds[0]['occurred_day'] <= 3 for e in ss)
    y_second = int(second_ok)
    y_msmi = int(second_ok and ds[0]['occurred_day'] - assigned_day <= 30)
    return dict(mature=1, y_msmi=y_msmi, y_mutual=y_mutual, y_date=y_date,
                y_second=y_second,
                missing=sum(e.get('missing_reason') == 'no_response'
                            for e in es))


def run_pair_isolated(snap, pair, final_day=HORIZON):
    """Run `pair` alone from `snap`, then follow the protocol to `final_day`.

    Returns (sim_after, new_mid). Raises if the run leaked into the snapshot.
    """
    fp_before = snapshot_fingerprint(snap)
    s = clone_from(snap)
    s.advance([list(pair)])
    while s.day < final_day:
        s.advance([])
    if snapshot_fingerprint(snap) != fp_before:
        raise AssertionError('snapshot leaked during isolated run %r' % (pair,))
    new = [i for i in s.introductions if i['assigned_day'] == snap.day]
    if len(new) != 1:
        raise AssertionError('expected exactly 1 new introduction, got %d'
                             % len(new))
    return s, new[0]['introduction_id']


def replay_world(seed, variant, per_day=None, follow_up=True):
    """Replay one frozen control world, exactly as n01_autopsy.replay_world.

    per_day(ctx) runs AFTER resolve_asks/allocate and BEFORE sim.advance(pairs).
    Returns (digest_hex, sim).
    """
    world = kit.generate(seed, 200, 'evaluation', variant)
    sim = kit.Simulator(world)
    digest = hashlib.sha256()
    for _ in range(DECISION_DAYS):
        asks = kit.baseline_asks(sim.observe())
        digest.update(json.dumps(['ask', sim.day, asks],
                                 sort_keys=True).encode())
        sim.resolve_asks(asks)
        state = sim.observe()
        pairs, edges, degree, used = n01.allocate(state)
        digest.update(json.dumps(['match', sim.day, pairs],
                                 sort_keys=True).encode())
        if per_day is not None:
            member_hist, n_intros, n_mutual, n_dates, n_fb = \
                n01.day_history(state)
            per_day(dict(
                seed=seed, variant=variant, day=sim.day, state=state,
                snap=copy.deepcopy(sim), pairs=[list(p) for p in pairs],
                edges=edges, degree=degree, used=used,
                max_score=-min((e[0] for e in edges), default=0),
                score_counts=Counter(e[0] for e in edges),
                member_hist=member_hist,
                day_ctx={'has_history': int(n_intros > 0),
                         'n_available': sum(1 for m in state['members']
                                            if m['available']),
                         'n_intros': n_intros, 'n_mutual': n_mutual,
                         'n_dates': n_dates, 'n_feedback': n_fb},
                n_intros=n_intros, n_mutual=n_mutual, n_dates=n_dates,
                n_feedback=n_fb))
        sim.advance(pairs)
    if follow_up:
        for _ in range(HORIZON - DECISION_DAYS):
            sim.advance([])
    return digest.hexdigest(), sim


# --- matching enumeration (plan Task 3) ------------------------------------

def enumerate_matchings(keys, cap=51, node_limit=2_000_000):
    """All vertex-disjoint subsets of `keys`, capped. Returns (matchings, failed)."""
    out, nodes, stop = [], [0], [False]

    def rec(i, used, cur):
        if stop[0]:
            return
        nodes[0] += 1
        if nodes[0] > node_limit:
            stop[0] = True
            return
        if i == len(keys):
            out.append(frozenset(cur))
            return
        rec(i + 1, used, cur)
        if stop[0]:
            return
        ka, kb = keys[i]
        if ka not in used and kb not in used:
            rec(i + 1, used | {ka, kb}, cur + [i])
            if len(out) > cap:
                stop[0] = True
    rec(0, set(), [])
    return out, stop[0]


def max_matching_size(keys):
    """Exact maximum cardinality of a vertex-disjoint edge set (branch + bound)."""
    best = [0]

    def rec(i, used, taken):
        if i == len(keys):
            best[0] = max(best[0], taken)
            return
        free = sum(1 for e in keys[i:] for x in e if x not in used)
        if taken + free // 2 <= best[0]:
            return
        rec(i + 1, used, taken)
        ka, kb = keys[i]
        if ka not in used and kb not in used:
            rec(i + 1, used | {ka, kb}, taken + 1)
    rec(0, set(), 0)
    return best[0]


def alt_same_size_flags(keys, m_idx, node_limit=2_000_000):
    """Amendment 1 terms: does a different matching of the same batch size exist?

    `m_idx` is the frozenset of edge indices the collector chose. Returns
    dict(alt_same_size, same_endpoints, diff_endpoints, unknown). `unknown` is 1
    when the exact search hit its node limit - never silently reported as 0.
    """
    flags = dict(alt_same_size=0, same_endpoints=0, diff_endpoints=0, unknown=0)
    size = len(m_idx)
    if size == 0:
        return flags            # only the empty matching has size 0
    m_ends = frozenset().union(*[set(keys[i]) for i in m_idx])
    nodes = [0]

    def rec(i, used, cur):
        if nodes[0] > node_limit:
            flags['unknown'] = 1
            return
        if len(cur) == size:
            if frozenset(cur) != m_idx:
                ends = frozenset().union(*[set(keys[j]) for j in cur])
                flags['alt_same_size'] = 1
                if ends == m_ends:
                    flags['same_endpoints'] = 1
                else:
                    flags['diff_endpoints'] = 1
            return
        n = len(keys)
        for j in range(i, n):
            if nodes[0] > node_limit:
                return
            nodes[0] += 1
            kj = set(keys[j])
            if kj & used:
                continue
            rec(j + 1, used | kj, cur + [j])
    rec(0, set(), [])
    return flags


def day_structural_metrics(edges, pairs, keys):
    """C1-C5 metrics for one decision day (analysis_plan.md 3.1 + Amendment 1).

    edges: list of (neg_score, key) from n01.allocate; pairs: the greedy
    selection; keys: the same edges as sorted tuples. Returns a flat dict.
    """
    m = [tuple(p) for p in pairs]
    mset = set(m)
    n_edges = len(keys)
    degree = {}
    for k in keys:
        for x in k:
            degree[x] = degree.get(x, 0) + 1

    out = dict(edges_total=n_edges, n_pairs=len(m))
    out['n_members_with_degree_ge1'] = len(degree)
    out['n_members_degree_ge2'] = sum(1 for v in degree.values() if v >= 2)
    out['degree_max'] = max(degree.values(), default=0)

    # C3 - competition faced by the selected pairs
    m_endpoints = set()
    for p in m:
        m_endpoints.update(p)
    competing_total = selected_with_alt = 0
    for p in m:
        ps = set(p)
        competing_total += sum(1 for k in keys
                               if set(k) & ps and set(k) != ps)
        if any(degree.get(x, 0) > 1 for x in p):
            selected_with_alt += 1
    out['competing_edges_mean'] = (competing_total / len(m)) if m else 0.0
    out['selected_with_alt_partner'] = selected_with_alt
    out['selected_with_alt_partner_share'] = (
        selected_with_alt / len(m)) if m else 0.0

    # C4 - matching structure
    matchings, enum_failed = enumerate_matchings(keys)
    m_idx = frozenset(i for i, k in enumerate(keys) if k in mset)
    out['n_matchings_capped'] = len(matchings)
    out['n_matchings_gt_cap'] = int(enum_failed or len(matchings) > 50)
    out['enum_failed'] = int(enum_failed)
    out['batch_size'] = len(m)
    out['max_matching_size'] = max_matching_size(keys)
    out['batch_underfill'] = out['max_matching_size'] - len(m)

    flags = alt_same_size_flags(keys, m_idx)
    out['alt_same_size'] = flags['alt_same_size']
    out['alt_same_size_same_endpoints'] = flags['same_endpoints']
    out['alt_same_size_diff_endpoints'] = flags['diff_endpoints']
    out['alt_same_size_unknown'] = flags['unknown']

    # alt_repair_same_endpoints at any size (>=2 only; a singleton has no
    # re-pairing of the same two members)
    alt_repair = 0
    if len(m) >= 2:
        for mt in matchings:
            if mt == m_idx:
                continue
            ends = (frozenset().union(*[set(keys[i]) for i in mt])
                    if mt else frozenset())
            if ends == frozenset().union(*[set(p) for p in m]):
                alt_repair = 1
                break
    out['alt_repair_same_endpoints'] = alt_repair

    # greedy is maximal: no feasible edge may be disjoint from every selected
    # endpoint. On unselected days the question is vacuous, so we record
    # n_edges>0 instead of claiming a violation.
    if m_endpoints:
        out['addition_possible'] = int(
            any(not (set(k) & m_endpoints) for k in keys))
    else:
        out['addition_possible'] = int(n_edges > 0)

    # cardinality-preserving replacement (analysis_plan.md 3.1 C5)
    rep = 0
    for k in keys:
        if k in mset:
            continue
        ks = set(k)
        for j, p in enumerate(m):
            others = set()
            for q, pp in enumerate(m):
                if q != j:
                    others.update(pp)
            if not (ks & others) and (ks & set(p)):
                rep = 1
                break
        if rep:
            break
    out['cardinality_preserving_replacement'] = rep
    return out
