"""Round 2 PROMOTION copy of Stage 3 diagnose3.py (measurement only, no tuning).

PROVENANCE: copied from research/round2_stage3_intermediate_floor/diagnose3.py
for the fresh-seed promotion experiment (the original is frozen and asserts
outputs stay in its own directory). Only change: one sys.path line so the
frozen intermediate_policy.py shim imports from the frozen Stage 3 directory.
Instrumentation, arms, and fidelity checks are unchanged.

Re-simulates each (seed, variant) in-process with the SAME decide() path as the
official evaluate.py subprocess, for one of three arms:

    frozen:       floor argument = float(model['floor'])            (policy_ac.py)
    intermediate: floor argument = float(model['floor']) / 2.0       (intermediate_policy.py)
    nofloor:      floor argument = -inf                             (stage2 ablation_policy.py)

Records per day (identical instrumentation to Stage 2 diagnose.py):

  * feasible candidate count (pre-floor), counts vs frozen floor and vs
    intermediate floor, candidates after the ARM's floor, selected pairs,
    per-selected-pair model score
  * zero-selection days and their categories (arm-floor-relative)
  * greedy reference picks on the SAME state (kit.baseline_match) + overlap
  * short ask/match digests per day
  * fallback, cap, local-search seed stats, frontier cross-check

Episode end: official metrics verbatim minus inference_seconds, plus a FOUR-WAY
survivorship split of every introduction by model score:

    ge_frozen        s >= floor            (passes BOTH thresholds)
    mid_band         floor/2 <= s < floor  (admitted only by the intermediate arm)
    lt_intermediate  s <  floor/2          (admitted only by the no-floor arm)
    unscored         score unavailable

with per-group mutual acceptance and MSMI computed by the EXACT
per-introduction predicates from kit.Simulator.metrics (kit.py lines 194/197).
Both required classifications follow from this split:
  vs frozen floor:       ge_frozen  vs  (mid_band + lt_intermediate)
  vs intermediate floor: (ge_frozen + mid_band)  vs  lt_intermediate

Fidelity: action_sha256 + official metrics compared against the official
evaluate.py run for the same arm/seed -> the instrument measures the official run.

Writes only into research/round2_promotion_fresh_seeds/ (the HERE of this copy).
Never modifies policy.py, policy_ac.py, kit.py, evaluate.py, results/, any
Round 1 / Stage 1.5 / Stage 2 artifact, or any Stage 3 pre-registered file.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / 'research' / 'round2_stage3_intermediate_floor'))  # frozen Stage 3 shim for 'intermediate' arm

import kit     # noqa: E402
import policy  # noqa: E402
from evaluate import validate_response  # noqa: E402

VARIANTS = ('development', 'sparse', 'cold_start', 'delayed', 'shift', 'drift')
FROZEN_MATCHER = policy.max_score_matching   # captured before any arm patch


def canon(pairs):
    return {tuple(sorted(p)) for p in pairs}


def frontier(state):
    """Feasible non-past candidate pair set - the exact predicate shared by
    policy.ac_match candidates and kit.baseline_match candidates."""
    members = sorted((m for m in state['members'] if m['available']),
                     key=lambda m: m['member_id'])
    past = {tuple(sorted((i['user_a'], i['user_b'])))
            for i in state['introductions']}
    out = set()
    for i, a in enumerate(members):
        for b in members[i + 1:]:
            key = tuple(sorted((a['member_id'], b['member_id'])))
            if key in past:
                continue
            if kit.eligibility(a, b)['status'] != 'feasible':
                continue
            out.add(key)
    return out


def greedy_seed(above):
    """Verbatim replica of the greedy-seed stage inside policy.max_score_matching."""
    partner = {}
    for a, b, s in above:
        if a in partner or b in partner:
            continue
        partner[a] = (b, s)
        partner[b] = (a, s)
    seen, out = set(), []
    for a, (b, s) in partner.items():
        k = (a, b) if a <= b else (b, a)
        if k in seen:
            continue
        seen.add(k)
        out.append((k[0], k[1], s))
    return sorted(out, key=lambda e: (e[0], e[1]))


def ask_cost(asks):
    return sum(3 if a['field'] == 'constraints' else 1 for a in asks)


def short_digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()[:16]


def instrument_match(state, model, arm):
    """Replicate the ac_match pipeline exactly (same ordering, same functions) to
    expose pre-floor counts, frozen-floor counts, intermediate-floor counts,
    per-pair scores, and greedy reference picks. real_final calls
    policy.max_score_matching -> follows the arm patch."""
    members = sorted((m for m in state['members'] if m['available']),
                     key=lambda m: m['member_id'])
    nodes = [m['member_id'] for m in members]
    past = {tuple(sorted((i['user_a'], i['user_b'])))
            for i in state['introductions']}
    cand = []
    for i, a in enumerate(members):
        for b in members[i + 1:]:
            key = tuple(sorted((a['member_id'], b['member_id'])))
            if key in past:
                continue
            if kit.eligibility(a, b)['status'] != 'feasible':
                continue
            cand.append((a['member_id'], b['member_id']))
    cap_hit = len(cand) > 12000
    if cap_hit:
        cand = sorted(cand,
                      key=lambda p: (-policy.rule_score(state, p[0], p[1]), p[0], p[1]))[:12000]
    scored = [(x, y, policy._score_pair(model, state, x, y)) for x, y in cand]
    floor = float(model['floor'])
    inter = floor / 2.0
    above = sorted((e for e in scored if e[2] >= floor),
                   key=lambda e: (-e[2], e[0], e[1]))
    n_ge_inter = sum(1 for e in scored if e[2] >= inter)
    below = len(scored) - len(above)
    all_sorted = sorted(scored, key=lambda e: (-e[2], e[0], e[1]))
    seed_floor = greedy_seed(above)
    seed_nofloor = greedy_seed(all_sorted)
    real_final = policy.max_score_matching(nodes, scored, floor)  # follows the arm patch
    g_sel = kit.baseline_match(state)
    g_k = {tuple(sorted(p)) for p in g_sel}
    smap = {(x, y): s for x, y, s in scored}
    if arm == 'nofloor':
        n_after_arm = len(scored)
    elif arm == 'intermediate':
        n_after_arm = n_ge_inter
    else:
        n_after_arm = len(above)
    return {
        'greedy_pairs': g_k,
        'greedy_below': sum(1 for p in g_k if smap.get(p, -1.0) < floor),
        'greedy_not_in_cand': len(g_k - set(smap)),
        'n_members_available': len(members),
        'n_cand': len(cand),
        'cand_set': canon(cand),
        'n_above': len(above),
        'n_ge_inter': n_ge_inter,
        'n_below': below,
        'n_after_arm': n_after_arm,
        'cap_hit': cap_hit,
        'seed_floor': seed_floor,
        'seed_nofloor': seed_nofloor,
        'real_final': real_final,
        'smap': smap,
    }


FALLBACK_COUNT = [0]


def diag_variant(seed, variant, model, arm, floor):
    world = kit.generate(seed, 200, 'evaluation', variant)
    sim = kit.Simulator(world)
    memory = None
    digest = hashlib.sha256()          # exactly evaluate.episode's digest
    ask_digest = hashlib.sha256()      # ask-only (cross-arm purity/divergence)
    match_digest = hashlib.sha256()    # match-only
    days = []
    for _ in range(60):
        # ---------------- ASK PHASE ----------------
        state = sim.observe()
        req = {'schema_version': state['schema_version'], 'phase': 'ask',
               'state': state, 'memory': memory}
        fb0 = FALLBACK_COUNT[0]
        resp = policy.decide(req, mode='ac')
        validate_response(resp, 'ask')
        memory = resp['memory']
        asks = resp['asks']
        digest.update(json.dumps(['ask', sim.day, asks], sort_keys=True).encode())
        ask_digest.update(json.dumps(['ask', sim.day, asks], sort_keys=True).encode())
        sim.resolve_asks(asks)

        # ---------------- MATCH PHASE ----------------
        state2 = sim.observe()
        req2 = {'schema_version': state2['schema_version'], 'phase': 'match',
                'state': state2, 'memory': memory}
        resp2 = policy.decide(req2, mode='ac')
        validate_response(resp2, 'match')
        memory = resp2['memory']
        pairs = resp2['pairs']
        fallback_used = FALLBACK_COUNT[0] > fb0
        digest.update(json.dumps(['match', sim.day, pairs], sort_keys=True).encode())
        match_digest.update(json.dumps(['match', sim.day, pairs], sort_keys=True).encode())

        inst = instrument_match(state2, model, arm)
        f_recheck = frontier(state2)
        same_as_ask_frontier = (inst['cand_set'] == f_recheck)
        seed_k = canon([e[:2] for e in inst['seed_floor']])
        final_k = canon(pairs)
        changed = (None if fallback_used else seed_k != final_k)

        if inst['n_cand'] == 0:
            category = 'no_candidates'
        elif len(pairs) == 0:
            if inst['n_after_arm'] == 0:
                category = 'all_below_floor'   # arm-floor-relative
            elif fallback_used:
                category = 'fallback_empty'
            else:
                category = 'above_but_zero_or_outer_exception'
        else:
            category = 'selected'

        selected_scored = sorted(
            [[a, b, inst['smap'][(a, b)]] for a, b in final_k if (a, b) in inst['smap']]
            + [[a, b, inst['smap'][(b, a)]] for a, b in final_k
               if (a, b) not in inst['smap'] and (b, a) in inst['smap']])
        match_rec = {
            'day': sim.day,
            'n_members_available': inst['n_members_available'],
            'n_cand': inst['n_cand'],
            'n_above': inst['n_above'],
            'n_ge_inter': inst['n_ge_inter'],
            'n_below': inst['n_below'],
            'n_after_arm': inst['n_after_arm'],
            'n_selected': len(pairs),
            'n_seed_floor': len(inst['seed_floor']),
            'n_seed_nofloor': len(inst['seed_nofloor']),
            'cap_hit': inst['cap_hit'],
            'fallback_used': fallback_used,
            'seed_changed': changed,
            'category': category,
            'greedy_n': len(inst['greedy_pairs']),
            'greedy_overlap_n': len(inst['greedy_pairs'] & final_k),
            'greedy_below_floor_n': inst['greedy_below'],
            'greedy_not_in_cand': inst['greedy_not_in_cand'],
            'frontier_recheck_ok': same_as_ask_frontier,
            'instrument_matches_action':
                canon([e[:2] for e in inst['real_final']]) == final_k or fallback_used,
            'after_floor_equals_feasible': inst['n_after_arm'] == inst['n_cand'],
            'selected_scored': selected_scored,
            'greedy_pairs_day': sorted(list(p) for p in inst['greedy_pairs']),
            'match_digest16': short_digest(['match', sim.day, pairs]),
        }
        ask_rec = {'day': sim.day, 'n_asks': len(asks), 'cost': ask_cost(asks),
                   'ask_digest16': short_digest(['ask', sim.day, asks])}
        days.append({'ask': ask_rec, 'match': match_rec})
        sim.advance(pairs)

    arrived = {m['member_id']: m['arrived_day'] for m in sim.observe()['members']
               if m['arrived_day'] <= 59}
    for _ in range(40):                          # follow-up, exactly like evaluate.episode
        sim.advance([])
    m = sim.metrics()
    first = {}
    for intro in sim.introductions:
        for member in (intro['user_a'], intro['user_b']):
            first.setdefault(member, intro['assigned_day'])
    waits = sorted(first[i] - arrived[i] for i in first)
    m.update(valid=True, arrived_members=len(arrived),
             msmi_per_100_arrived_members=100 * m['mutual_second_meeting_intention'] / max(1, len(arrived)),
             served_members=len(first), unserved_members=len(arrived) - len(first),
             coverage=len(first) / max(1, len(arrived)),
             mutual_acceptances_per_100=100 * m['mutual_acceptances'] / max(1, len(arrived)),
             first_introduction_wait_days=waits,
             action_sha256=digest.hexdigest())

    # -------- survivorship: official per-intro predicates (kit.metrics verbatim) --------
    inter = floor / 2.0
    score_by_mid = {}
    for rec in days:
        day = rec['match']['day']
        for a, b, s in rec['match']['selected_scored']:
            aa, bb = sorted((a, b))
            mid = 'intro_' + hashlib.sha256(('%s|%s|%s' % (aa, bb, day)).encode()).hexdigest()[:24]
            score_by_mid[mid] = s
    events = sim.receive_feedback()
    groups = {k: {'n': 0, 'mutual': 0, 'msmi': 0}
              for k in ('ge_frozen', 'mid_band', 'lt_intermediate', 'unscored')}
    for intro in sim.introductions:
        es = [e for e in events if e['introduction_id'] == intro['introduction_id']]
        rs = [e for e in es if e['event'] == 'introduction_response']
        mutual = len(rs) == 2 and all(e['value'] == 'yes' for e in rs)
        ds = [e for e in es if e['event'] == 'date_happened' and e['value'] is True]
        ss = [e for e in es if e['event'] == 'second_meeting_intention']
        msmi = (bool(ds) and ds[0]['occurred_day'] - intro['assigned_day'] <= 30
                and len(ss) == 2
                and all(e['value'] == 'yes' and e['occurred_day'] - ds[0]['occurred_day'] <= 3 for e in ss))
        s = score_by_mid.get(intro['introduction_id'])
        if s is None:
            cls = 'unscored'
        elif s >= floor:
            cls = 'ge_frozen'
        elif s >= inter:
            cls = 'mid_band'
        else:
            cls = 'lt_intermediate'
        groups[cls]['n'] += 1
        groups[cls]['mutual'] += int(bool(mutual))
        groups[cls]['msmi'] += int(bool(msmi))

    # -------- greedy overlap over the whole episode --------
    S = set()
    G = set()
    for rec in days:
        S |= canon([p[:2] for p in rec['match']['selected_scored']])
        G |= canon(rec['match']['greedy_pairs_day'])
    greedy = {'S': len(S), 'G': len(G), 'S_and_G': len(S & G),
              'S_or_G': len(S | G),
              'jaccard': (len(S & G) / len(S | G)) if (S or G) else None}
    return {'days': days, 'metrics': m, 'action_sha256': digest.hexdigest(),
            'ask_digest_final': ask_digest.hexdigest(),
            'match_digest_final': match_digest.hexdigest(),
            'survivorship': groups, 'greedy': greedy}


def load_ref(path, seed):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    return {e['variant']: e for e in data['episodes'] if e['seed'] == seed}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--arm', choices=['frozen', 'intermediate', 'nofloor'], required=True)
    ap.add_argument('--seed', type=int, required=True)
    ap.add_argument('--ref', required=True, help='official evaluate.py JSON for the same arm+seed')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    if args.arm == 'nofloor':
        sys.path.insert(0, str(REPO / 'research' / 'round2_stage2_floor_ablation'))
        import ablation_policy  # applies the Stage 2 single -inf floor intervention
        assert policy.max_score_matching is not FROZEN_MATCHER, 'nofloor patch missing'
    elif args.arm == 'intermediate':
        import intermediate_policy  # applies the pre-registered floor/2 intervention
        assert policy.max_score_matching is not FROZEN_MATCHER, 'intermediate patch missing'
    else:
        assert policy.max_score_matching is FROZEN_MATCHER, 'frozen arm must stay frozen'

    orig = policy._rule_greedy

    def spy(edges):
        FALLBACK_COUNT[0] += 1
        return orig(edges)

    policy._rule_greedy = spy

    model = policy.load_model()
    assert model is not None, 'frozen model blob failed to load'
    floor = float(model['floor'])
    assert floor == 0.007905174015296758, 'frozen floor drifted: %r' % floor
    ref = load_ref(args.ref, args.seed)

    episodes = {}
    for variant in VARIANTS:
        episodes[variant] = diag_variant(args.seed, variant, model, args.arm, floor)
        ep = episodes[variant]
        r = ref.get(variant, {})
        fidelity = {
            'assignments_match': ep['metrics']['assignments'] == r.get('assignments'),
            'mutual_match': ep['metrics']['mutual_acceptances'] == r.get('mutual_acceptances'),
            'msmi_match': ep['metrics']['mutual_second_meeting_intention'] == r.get('mutual_second_meeting_intention'),
            'msmi_per_100_match': ep['metrics']['msmi_per_100_arrived_members'] == r.get('msmi_per_100_arrived_members'),
            'coverage_match': ep['metrics']['coverage'] == r.get('coverage'),
            'ask_cost_match': ep['metrics']['ask_cost'] == r.get('ask_cost'),
            'digest_match': ep['action_sha256'] == r.get('action_sha256'),
        }
        ep['fidelity_vs_official'] = fidelity
        ep['fidelity_ok'] = all(fidelity.values())
        print(json.dumps({'arm': args.arm, 'seed': args.seed, 'variant': variant,
                          'assignments': ep['metrics']['assignments'],
                          'fidelity_ok': ep['fidelity_ok']}, sort_keys=True), flush=True)

    # -------- per-variant funnel + totals --------
    pv = {}
    for variant in VARIANTS:
        ep = episodes[variant]
        mats = [d['match'] for d in ep['days']]
        asks = [d['ask'] for d in ep['days']]
        zero_sel = [r for r in mats if r['n_cand'] > 0 and r['n_selected'] == 0]
        cats = {}
        for r in zero_sel:
            cats[r['category']] = cats.get(r['category'], 0) + 1
        pv[variant] = {
            'decisions': len(mats),
            'feasible_total': sum(r['n_cand'] for r in mats),
            'after_floor_total': sum(r['n_after_arm'] for r in mats),
            'above_frozen_floor_total': sum(r['n_above'] for r in mats),
            'above_intermediate_floor_total': sum(r['n_ge_inter'] for r in mats),
            'selected_total': sum(r['n_selected'] for r in mats),
            'introduced': ep['metrics']['assignments'],
            'zero_candidate_days': sum(1 for r in mats if r['n_cand'] == 0),
            'zero_selected_with_cand': len(zero_sel),
            'zero_selected_categories': cats,
            'cap_hits': sum(1 for r in mats if r['cap_hit']),
            'fallback_used': sum(1 for r in mats if r['fallback_used']),
            'frontier_recheck_failures': sum(1 for r in mats if not r['frontier_recheck_ok']),
            'instrument_mismatches': sum(1 for r in mats if not r['instrument_matches_action']),
            'after_floor_neq_feasible_days': sum(1 for r in mats if not r['after_floor_equals_feasible']),
            'seed_changed_days': sum(1 for r in mats if r['seed_changed']),
            'ask_cost': sum(a['cost'] for a in asks),
            'greedy_n': sum(r['greedy_n'] for r in mats),
            'greedy_overlap_n': sum(r['greedy_overlap_n'] for r in mats),
            'greedy_below_floor_n': sum(r['greedy_below_floor_n'] for r in mats),
            'greedy': ep['greedy'],
            'survivorship': ep['survivorship'],
            'metrics': {k: ep['metrics'][k] for k in (
                'assignments', 'mutual_acceptances', 'mutual_second_meeting_intention',
                'msmi_per_100_arrived_members', 'coverage', 'ask_cost')},
            'action_sha256': ep['action_sha256'],
            'fidelity_ok': ep['fidelity_ok'],
        }
    keys_sum = ('feasible_total', 'after_floor_total', 'above_frozen_floor_total',
                'above_intermediate_floor_total', 'selected_total', 'introduced',
                'zero_candidate_days', 'zero_selected_with_cand', 'cap_hits',
                'fallback_used', 'frontier_recheck_failures', 'instrument_mismatches',
                'after_floor_neq_feasible_days', 'seed_changed_days', 'ask_cost',
                'greedy_n', 'greedy_overlap_n', 'greedy_below_floor_n')
    tot = {k: sum(pv[v][k] for v in VARIANTS) for k in keys_sum}
    tot['decisions'] = 60 * len(VARIANTS)
    cats_all = {}
    for v in VARIANTS:
        for k, n in pv[v]['zero_selected_categories'].items():
            cats_all[k] = cats_all.get(k, 0) + n
    tot['zero_selected_categories'] = cats_all
    for v in VARIANTS:
        grp = pv[v]['survivorship']
        tot.setdefault('survivorship', {k: {'n': 0, 'mutual': 0, 'msmi': 0}
                                        for k in ('ge_frozen', 'mid_band',
                                                  'lt_intermediate', 'unscored')})
        for cls in grp:
            for k in ('n', 'mutual', 'msmi'):
                tot['survivorship'][cls][k] += grp[cls][k]

    artifact = {}
    for line in (REPO / 'results' / 'artifact.sha256').read_text().splitlines():
        h, f = line.split()
        artifact[f] = h

    output = {
        'schema': 'round2_stage3_intermediate_floor_diag_v1',
        'arm': args.arm, 'seed': args.seed,
        'variants': list(VARIANTS), 'floor': floor,
        'intermediate_floor': floor / 2.0,
        'ref_file': args.ref,
        'round1_artifact_hashes': artifact,
        'per_variant': pv, 'overall': tot,
        'all_fidelity_ok': all(pv[v]['fidelity_ok'] for v in VARIANTS),
        'episodes': {v: {'metrics': episodes[v]['metrics'],
                         'action_sha256': episodes[v]['action_sha256'],
                         'ask_digest_final': episodes[v]['ask_digest_final'],
                         'match_digest_final': episodes[v]['match_digest_final'],
                         'fidelity_ok': episodes[v]['fidelity_ok'],
                         'fidelity_vs_official': episodes[v]['fidelity_vs_official'],
                         'survivorship': episodes[v]['survivorship'],
                         'greedy': episodes[v]['greedy'],
                         'days': episodes[v]['days']} for v in VARIANTS},
    }
    out_path = Path(args.out)
    assert out_path.parent.resolve() == HERE.resolve(), 'output must stay in this directory'
    out_path.write_text(json.dumps(output, indent=2, sort_keys=True, allow_nan=False) + '\n',
                        encoding='utf-8')
    print('WROTE', out_path)
    print('FALLBACK_CALLS', FALLBACK_COUNT[0])
    print('ALL_FIDELITY_OK', output['all_fidelity_ok'])


if __name__ == '__main__':
    main()