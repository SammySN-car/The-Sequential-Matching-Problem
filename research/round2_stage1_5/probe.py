"""Round 2 Stage 1.5 - READ-ONLY diagnostic probe (measurement only, no tuning).

Re-simulates seed 101 x 6 variants using the FROZEN Round 1 A+C policy in-process
(identical decide() path as policy_ac.py / the container) and instruments every
ask and match decision:

  * feasible non-past candidate counts (pre- and post-floor), floor removal
  * zero-selected-with-candidates categories (measured, not assumed)
  * greedy candidate-set overlap (pre-floor and post-floor definitions)
  * greedy-seed vs final matching (does local search change the seed?)
  * paired counterfactual ask branches on isolated deepcopy clones:
        branch AC-full (real trajectory), AC-constraints-only, AC-soft-only,
        baseline_asks  -- the real simulation is never mutated by a branch
  * clarification cost per newly feasible candidate (gains and net)
  * complete funnel per variant + fidelity vs Round 1 results/ac.json seed-101

Determinism: no timestamps, sort_keys JSON, stable sorted iteration, only the
simulator seed 101. Writes ONLY into research/round2_stage1_5/.
Never modifies policy.py, kit.py, evaluate.py, results/, or any Round 1 artifact.
"""
import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

import kit
import policy
from evaluate import validate_response

VARIANTS = ('development', 'sparse', 'cold_start', 'delayed', 'shift', 'drift')


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
    """Verbatim replica of the greedy-seed stage inside policy.max_score_matching
    (frozen Round 1 source, lines: partner map over above sorted by (-score,a,b),
    then canonical unique list sorted by (a,b)). Measurement replica only."""
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


def instrument_match(state, model):
    """Replicate the ac_match pipeline exactly (same ordering, same functions)
    to expose pre-floor/post-floor candidate counts and both seed matchings."""
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
    above = sorted((e for e in scored if e[2] >= floor),
                   key=lambda e: (-e[2], e[0], e[1]))
    below = len(scored) - len(above)
    all_sorted = sorted(scored, key=lambda e: (-e[2], e[0], e[1]))
    seed_floor = greedy_seed(above)
    seed_nofloor = greedy_seed(all_sorted)
    real_final = policy.max_score_matching(nodes, scored, floor)
    # greedy overlap: what kit.baseline_match (the Round 1 greedy policy) would pick
    # from the SAME state; pure function, no side effects. Post-floor definition:
    # how many greedy picks fall below A+C's floor (i.e. A+C structurally cannot pick them).
    g_sel = kit.baseline_match(state)
    g_k = {tuple(sorted(p)) for p in g_sel}
    smap = {(x, y): s for x, y, s in scored}
    return {
        'greedy_pairs': g_k,
        'greedy_below': sum(1 for p in g_k if smap.get(p, -1.0) < floor),
        'greedy_not_in_cand': len(g_k - set(smap)),
        'n_members_available': len(members),
        'n_cand': len(cand),
        'cand_set': canon(cand),
        'n_above': len(above),
        'n_below': below,
        'cap_hit': cap_hit,
        'seed_floor': seed_floor,
        'seed_nofloor': seed_nofloor,
        'real_final': real_final,
    }


def probe_variant(seed, variant, model):
    world = kit.generate(seed, 200, 'evaluation', variant)
    sim = kit.Simulator(world)
    memory = None
    digest = hashlib.sha256()
    days = []
    for _ in range(60):
        # ---------------- ASK PHASE ----------------
        state = sim.observe()
        req = {'schema_version': state['schema_version'], 'phase': 'ask',
               'state': state, 'memory': memory}
        resp = policy.decide(req, mode='ac')
        validate_response(resp, 'ask')
        memory = resp['memory']
        asks = resp['asks']
        digest.update(json.dumps(['ask', sim.day, asks], sort_keys=True).encode())

        f0 = frontier(state)
        asks_con = [a for a in asks if a['field'] == 'constraints']
        asks_soft = [a for a in asks if a['field'] != 'constraints']
        asks_base = kit.baseline_asks(state)

        def branch(asks_b):
            clone = copy.deepcopy(sim)          # isolated counterfactual
            try:
                clone.resolve_asks(asks_b)
                return frontier(clone.observe()), None
            except Exception as exc:            # measured, not swallowed
                return None, '%s: %s' % (type(exc).__name__, exc)

        f_base, err_base = branch(asks_base)
        f_con, err_con = branch(asks_con)
        f_soft, err_soft = branch(asks_soft)

        sim.resolve_asks(asks)                  # actual trajectory step
        f_full = frontier(sim.observe())

        def gains_lost(fnew):
            if fnew is None:
                return None, None
            return len(fnew - f0), len(f0 - fnew)

        g_ac, l_ac = gains_lost(f_full)
        g_base, l_base = gains_lost(f_base)
        g_con, l_con = gains_lost(f_con)
        g_soft, l_soft = gains_lost(f_soft)

        con_members = {a['member_id'] for a in asks_con}
        base_members = {a['member_id'] for a in asks_base}
        ask_rec = {
            'day': sim.day,
            'ask_con_members': len(con_members),
            'ask_base_members': len(base_members),
            'ask_overlap_members': len(con_members & base_members),
            'budget_before': 12 - (sim.asks_total - ask_cost(asks)) if False else None,
            'n_ac': len(asks), 'n_ac_con': len(asks_con), 'n_ac_soft': len(asks_soft),
            'cost_ac': ask_cost(asks),
            'cost_ac_con': 3 * len(asks_con), 'cost_ac_soft': len(asks_soft),
            'n_base': len(asks_base), 'cost_base': ask_cost(asks_base),
            'f0': len(f0), 'f_full': len(f_full),
            'f_base': len(f_base) if f_base is not None else None,
            'f_con': len(f_con) if f_con is not None else None,
            'f_soft': len(f_soft) if f_soft is not None else None,
            'gains_ac': g_ac, 'lost_ac': l_ac,
            'gains_base': g_base, 'lost_base': l_base,
            'gains_con': g_con, 'lost_con': l_con,
            'gains_soft': g_soft, 'lost_soft': l_soft,
            'err_base': err_base, 'err_con': err_con, 'err_soft': err_soft,
        }

        # ---------------- MATCH PHASE ----------------
        state2 = sim.observe()
        req2 = {'schema_version': state2['schema_version'], 'phase': 'match',
                'state': state2, 'memory': memory}
        fb0 = FALLBACK_COUNT[0]
        resp2 = policy.decide(req2, mode='ac')
        validate_response(resp2, 'match')
        memory = resp2['memory']
        pairs = resp2['pairs']
        fallback_used = FALLBACK_COUNT[0] > fb0
        digest.update(json.dumps(['match', sim.day, pairs], sort_keys=True).encode())

        inst = instrument_match(state2, model)
        assert inst['cand_set'] == canon(pairs) or True   # (sets compared below)
        f_full_recheck = inst['cand_set']
        same_as_ask_frontier = (f_full_recheck ==
                                frontier(state2))         # post-resolve state frontier
        seed_k = canon([e[:2] for e in inst['seed_floor']])
        final_k = canon(pairs)
        changed = (None if fallback_used else seed_k != final_k)
        pairs_changed = (None if fallback_used else len(seed_k ^ final_k))

        if inst['n_cand'] == 0:
            category = 'no_candidates'
        elif len(pairs) == 0:
            if inst['n_above'] == 0:
                category = 'all_below_floor'
            elif fallback_used:
                category = 'fallback_empty'
            else:
                category = 'above_but_zero_or_outer_exception'
        else:
            category = 'selected'

        match_rec = {
            'day': sim.day,
            'n_members_available': inst['n_members_available'],
            'n_cand': inst['n_cand'],
            'n_above': inst['n_above'],
            'n_below': inst['n_below'],
            'cap_hit': inst['cap_hit'],
            'n_selected': len(pairs),
            'n_seed_floor': len(inst['seed_floor']),
            'n_seed_nofloor': len(inst['seed_nofloor']),
            'n_unused_above': inst['n_above'] - len(pairs),
            'fallback_used': fallback_used,
            'seed_changed': changed,
            'pairs_changed': pairs_changed,
            'category': category,
            'greedy_n': len(inst['greedy_pairs']),
            'greedy_overlap_n': len(inst['greedy_pairs'] & final_k),
            'greedy_below_floor_n': inst['greedy_below'],
            'greedy_not_in_cand': inst['greedy_not_in_cand'],
            'frontier_recheck_ok': same_as_ask_frontier,
            'instrument_matches_action':
                canon([e[:2] for e in inst['real_final']]) == final_k or fallback_used,
        }
        days.append({'ask': ask_rec, 'match': match_rec})

        sim.advance(pairs)                       # actual trajectory step

    for _ in range(40):                          # follow-up, exactly like evaluate.episode
        sim.advance([])
    m = sim.metrics()
    return {'days': days, 'metrics': m, 'action_sha256': digest.hexdigest()}


FALLBACK_COUNT = [0]


def ref_seed101(fname):
    data = json.loads((REPO / 'results' / fname).read_text(encoding='utf-8'))
    out = {}
    for ep in data['episodes']:
        if ep['seed'] == 101:
            out[ep['variant']] = {'assignments': ep['assignments'],
                                  'mutual': ep['mutual_acceptances'],
                                  'msmi': ep['mutual_second_meeting_intention'],
                                  'action_sha256': ep['action_sha256'],
                                  'ask_cost': ep['ask_cost']}
    return out


def aggregate(episodes):
    pv, tot = {}, None
    for variant in VARIANTS:
        ep = episodes[variant]
        asks = [d['ask'] for d in ep['days']]
        mats = [d['match'] for d in ep['days']]
        cand = sum(r['n_cand'] for r in mats)
        below = sum(r['n_below'] for r in mats)
        above = sum(r['n_above'] for r in mats)
        zero_cand_days = sum(1 for r in mats if r['n_cand'] == 0)
        zero_sel = [r for r in mats if r['n_cand'] > 0 and r['n_selected'] == 0]
        comparable = [r for r in mats if r['seed_changed'] is not None]
        changed = [r for r in comparable if r['seed_changed']]
        cats = {}
        for r in zero_sel:
            cats[r['category']] = cats.get(r['category'], 0) + 1
        gains_ac = sum(a['gains_ac'] for a in asks)
        gains_base = sum(a['gains_base'] for a in asks if a['gains_base'] is not None)
        gains_con = sum(a['gains_con'] for a in asks if a['gains_con'] is not None)
        gains_soft = sum(a['gains_soft'] for a in asks if a['gains_soft'] is not None)
        lost_ac = sum(a['lost_ac'] for a in asks)
        lost_base = sum(a['lost_base'] for a in asks if a['lost_base'] is not None)
        cost_ac = sum(a['cost_ac'] for a in asks)
        cost_con = sum(a['cost_ac_con'] for a in asks)
        cost_soft = sum(a['cost_ac_soft'] for a in asks)
        cost_base = sum(a['cost_base'] for a in asks)
        ask_con_m = sum(a['ask_con_members'] for a in asks)
        ask_base_m = sum(a['ask_base_members'] for a in asks)
        ask_ov_m = sum(a['ask_overlap_members'] for a in asks)
        err_counts = sum(1 for a in asks for k in ('err_base', 'err_con', 'err_soft')
                         if a[k])
        row = {
            'decisions': len(mats),
            'members_available_mean': sum(r['n_members_available'] for r in mats) / len(mats),
            'cand_total': cand,
            'cand_mean': cand / len(mats),
            'above_total': above,
            'below_total': below,
            'floor_removed_pct': (100.0 * below / cand) if cand else None,
            'zero_candidate_days': zero_cand_days,
            'zero_selected_with_cand': len(zero_sel),
            'zero_selected_categories': cats,
            'seed_comparables': len(comparable),
            'seed_changed_count': len(changed),
            'seed_changed_pct': (100.0 * len(changed) / len(comparable)) if comparable else None,
            'pairs_changed_total': sum(r['pairs_changed'] for r in changed),
            'selected_total': sum(r['n_selected'] for r in mats),
            'seed_nofloor_total': sum(r['n_seed_nofloor'] for r in mats),
            'floor_volume_delta': sum(r['n_seed_nofloor'] for r in mats) - sum(r['n_selected'] for r in mats),
            'unused_above_total': sum(max(0, r['n_unused_above']) for r in mats),
            'cap_hits': sum(1 for r in mats if r['cap_hit']),
            'fallback_used': sum(1 for r in mats if r['fallback_used']),
            'ask_cost_ac': cost_ac,
            'ask_cost_ac_con': cost_con,
            'ask_cost_ac_soft': cost_soft,
            'ask_cost_base_counterfactual': cost_base,
            'ask_con_members': ask_con_m,
            'ask_base_members': ask_base_m,
            'ask_overlap_members': ask_ov_m,
            'greedy_n': sum(r['greedy_n'] for r in mats),
            'greedy_overlap_n': sum(r['greedy_overlap_n'] for r in mats),
            'greedy_below_floor_n': sum(r['greedy_below_floor_n'] for r in mats),
            'greedy_not_in_cand': sum(r['greedy_not_in_cand'] for r in mats),
            'gains_ac': gains_ac,
            'lost_ac': lost_ac,
            'net_ac': gains_ac - lost_ac,
            'gains_base': gains_base,
            'lost_base': lost_base,
            'net_base': gains_base - lost_base,
            'gains_con': gains_con,
            'gains_soft': gains_soft,
            'cost_per_gain_ac': (cost_ac / gains_ac) if gains_ac else None,
            'cost_per_net_ac': (cost_ac / (gains_ac - lost_ac)) if (gains_ac - lost_ac) else None,
            'cost_per_gain_base': (cost_base / gains_base) if gains_base else None,
            'branch_errors': err_counts,
            'frontier_recheck_failures': sum(1 for r in mats if not r['frontier_recheck_ok']),
            'instrument_mismatches': sum(1 for r in mats if not r['instrument_matches_action']),
            'assignments': ep['metrics']['assignments'],
            'mutual': ep['metrics']['mutual_acceptances'],
            'msmi': ep['metrics']['mutual_second_meeting_intention'],
            'ask_cost_metrics': ep['metrics']['ask_cost'],
            'action_sha256': ep['action_sha256'],
        }
        pv[variant] = row
    keys_sum = ['cand_total', 'above_total', 'below_total', 'selected_total',
                'seed_nofloor_total', 'unused_above_total', 'ask_cost_ac',
                'ask_cost_ac_con', 'ask_cost_ac_soft', 'ask_cost_base_counterfactual',
                'gains_ac', 'lost_ac', 'gains_base', 'lost_base', 'gains_con',
                'gains_soft', 'assignments', 'mutual', 'msmi', 'pairs_changed_total',
                'zero_selected_with_cand', 'seed_changed_count', 'seed_comparables',
                'cap_hits', 'fallback_used', 'branch_errors',
                'ask_con_members', 'ask_base_members', 'ask_overlap_members',
                'greedy_n', 'greedy_overlap_n', 'greedy_below_floor_n',
                'greedy_not_in_cand']
    tot = {k: sum(pv[v][k] for v in VARIANTS) for k in keys_sum}
    tot['decisions'] = 60 * len(VARIANTS)
    tot['cand_mean'] = tot['cand_total'] / tot['decisions']
    tot['floor_removed_pct'] = (100.0 * tot['below_total'] / tot['cand_total']) if tot['cand_total'] else None
    tot['seed_changed_pct'] = (100.0 * tot['seed_changed_count'] / tot['seed_comparables']) if tot['seed_comparables'] else None
    tot['net_ac'] = tot['gains_ac'] - tot['lost_ac']
    tot['net_base'] = tot['gains_base'] - tot['lost_base']
    tot['cost_per_gain_ac'] = (tot['ask_cost_ac'] / tot['gains_ac']) if tot['gains_ac'] else None
    tot['cost_per_gain_base'] = (tot['ask_cost_base_counterfactual'] / tot['gains_base']) if tot['gains_base'] else None
    tot['floor_volume_delta'] = tot['seed_nofloor_total'] - tot['selected_total']
    cats_all = {}
    for v in VARIANTS:
        for k, n in pv[v]['zero_selected_categories'].items():
            cats_all[k] = cats_all.get(k, 0) + n
    tot['zero_selected_categories'] = cats_all
    tot['zero_candidate_days'] = sum(pv[v]['zero_candidate_days'] for v in VARIANTS)
    return pv, tot


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seed', type=int, default=101)
    ap.add_argument('--out', default=None)
    args = ap.parse_args()

    # fallback spy: counts _rule_greedy invocations (wraps the frozen function; no behavior change)
    orig = policy._rule_greedy

    def spy(edges):
        FALLBACK_COUNT[0] += 1
        return orig(edges)

    policy._rule_greedy = spy

    model = policy.load_model()
    assert model is not None, 'frozen model blob failed to load'
    floor = float(model['floor'])

    ref_ac = ref_seed101('ac.json')
    ref_greedy = ref_seed101('greedy.json')

    episodes = {}
    for variant in VARIANTS:
        episodes[variant] = probe_variant(args.seed, variant, model)
        ep = episodes[variant]
        r = ref_ac.get(variant, {})
        fidelity = {
            'assignments_match': ep['metrics']['assignments'] == r.get('assignments'),
            'mutual_match': ep['metrics']['mutual_acceptances'] == r.get('mutual'),
            'msmi_match': ep['metrics']['mutual_second_meeting_intention'] == r.get('msmi'),
            'ask_cost_match': ep['metrics']['ask_cost'] == r.get('ask_cost'),
            'digest_match': ep['action_sha256'] == r.get('action_sha256'),
        }
        ep['fidelity_vs_round1_ac'] = fidelity
        ep['fidelity_ok'] = all(fidelity.values())
        print(json.dumps({'variant': variant,
                          'assignments': ep['metrics']['assignments'],
                          'fidelity_ok': ep['fidelity_ok']}, sort_keys=True), flush=True)

    pv, tot = aggregate(episodes)
    artifact = {}
    for line in (REPO / 'results' / 'artifact.sha256').read_text().splitlines():
        h, f = line.split()
        artifact[f] = h

    output = {
        'schema': 'round2_stage1_5_probe_v2',
        'round': 'Round 2 Stage 1.5 (measurement only; Round 1 frozen)',
        'seed': args.seed,
        'variants': list(VARIANTS),
        'floor': floor,
        'round1_artifact_hashes': artifact,
        'reference_round1_seed101': {'ac': ref_ac, 'greedy': ref_greedy},
        'per_variant': pv,
        'overall': tot,
        'episodes': {v: {'metrics': episodes[v]['metrics'],
                         'action_sha256': episodes[v]['action_sha256'],
                         'fidelity_ok': episodes[v]['fidelity_ok'],
                         'fidelity_vs_round1_ac': episodes[v]['fidelity_vs_round1_ac'],
                         'days': episodes[v]['days']} for v in VARIANTS},
    }
    out_path = Path(args.out) if args.out else (
        REPO / 'research' / 'round2_stage1_5' / ('probe_seed%d_run1.json' % args.seed))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2, sort_keys=True, allow_nan=False) + '\n',
                        encoding='utf-8')
    print('WROTE', out_path)
    print('FALLBACK_CALLS', FALLBACK_COUNT[0])
    print('ALL_FIDELITY_OK', all(episodes[v]['fidelity_ok'] for v in VARIANTS))


if __name__ == '__main__':
    main()