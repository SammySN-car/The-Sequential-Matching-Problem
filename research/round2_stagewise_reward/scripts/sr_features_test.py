"""Tests for sr_features.py (implementation_plan.md Task 1, gates T-FEA-1..4).

Plain python script, standard library only, no pytest. Prints [PASS]/[FAIL] per
test and exits non-zero on any failure.
"""
import copy
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import kit
from sr_features import build_feasible_edges, extract_pair_features, feature_audit_rows

FORBIDDEN = ('truth', 'bias', 'second_bias', 'response_rate', 'exit_day', 'seed', 'variant')
EXPECTED_NAMES = [
    'age_diff', 'age_slack', 'gender_fit_ab', 'gender_fit_ba', 'zone_common',
    'schedule_overlap', 'arrival_diff', 'soft_equal', 'soft_differ', 'soft_missing',
    'soft_declined', 'goal_agree', 'prev_intros_mean', 'hist_yes', 'current_day',
    'degree_a', 'degree_b',
]
EXPECTED_CLASSES = ['LEGAL OBSERVABLE'] * 15 + ['STRUCTURE-INFORMED'] * 2


def _scrub(node):
    """Recursively delete the forbidden keys wherever present (T-FEA-2)."""
    if isinstance(node, dict):
        for key in FORBIDDEN:
            node.pop(key, None)
        for value in node.values():
            _scrub(value)
    elif isinstance(node, list):
        for value in node:
            _scrub(value)


def _expect_assertion(fn, label):
    try:
        fn()
    except AssertionError:
        return
    raise AssertionError('expected AssertionError: ' + label)


def _fresh_sim():
    world = kit.generate(90210, 200, 'test', 'development')
    return kit.Simulator(world)


def test_audit_classification():
    rows = feature_audit_rows()
    assert len(rows) == 17, 'expected 17 rows, got %d' % len(rows)
    names = [r['name'] for r in rows]
    assert names == EXPECTED_NAMES, 'name/order mismatch: %r' % names
    assert len(set(names)) == 17, 'duplicate feature names'
    for row in rows:
        assert set(row) == {'name', 'source', 'legality', 'class'}, 'bad row keys: %r' % row
        assert row['source'], 'empty source expression for %s' % row['name']
    illegal = [r['name'] for r in rows
               if r['legality'] != 'LEGAL' or r['class'] not in ('LEGAL OBSERVABLE', 'STRUCTURE-INFORMED')]
    assert not illegal, 'illegal/leakage rows: %r' % illegal
    classes = [r['class'] for r in rows]
    assert classes == EXPECTED_CLASSES, 'class mismatch: %r' % classes
    out_path = Path(__file__).resolve().parents[1] / 'results' / 'feature_audit.json'
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({'count': 17, 'illegal_count': 0, 'rows': rows},
                                   indent=2, sort_keys=True) + '\n')


def _advance_until(sim, state, predicate, limit_day):
    """Baseline-roll out from `state` until predicate(state, edges, degree) holds
    or the day limit is reached. Returns (state, edges, degree)."""
    edges, degree = build_feasible_edges(state)
    while not predicate(state, edges, degree) and state['day'] < limit_day:
        sim.resolve_asks(kit.baseline_asks(state))
        sim.advance(kit.baseline_match(state))
        state = sim.observe()
        edges, degree = build_feasible_edges(state)
    return state, edges, degree


def test_scrub_invariance():
    sim = _fresh_sim()
    # The feasible graph is sparse (only hard-complete members are feasible), so
    # roll out to day >= 10 (introductions and feedback then exist) and use the
    # first state whose feasible graph is non-empty.
    state, edges, degree = _advance_until(
        sim, sim.observe(),
        lambda s, e, d: s['day'] >= 10 and len(e) > 0, 40)
    assert edges, 'no feasible edges between day 10 and 40'
    scrubbed = copy.deepcopy(state)
    _scrub(scrubbed)
    edges2, degree2 = build_feasible_edges(scrubbed)
    assert edges == edges2 and degree == degree2, 'scrub changed the feasible graph'
    feats = json.dumps([extract_pair_features(state, degree, a, b) for a, b in edges])
    feats_scrubbed = json.dumps([extract_pair_features(scrubbed, degree2, a, b) for a, b in edges])
    assert feats == feats_scrubbed, 'scrub changed extractor output'


def _find_soft_pair(state, edges):
    """First feasible edge with a member whose relationship_goal is not_asked."""
    members = {m['member_id']: m for m in state['members']}
    for x, y in edges:
        for ask_target, partner in ((x, y), (y, x)):
            if (members[ask_target]['fields'].get('relationship_goal') is None
                    and members[ask_target]['field_status'].get('relationship_goal') == 'not_asked'):
                return ask_target, partner
    return None


def test_late_field_immutable():
    sim = _fresh_sim()
    # Literal day-0 feasible pairs are complete-profile pairs only (feasibility
    # requires every HARD field observed; kit.py L55-56 makes that ~35% complete
    # or ~0.10^11 for the rest), so a day-0 feasible pair always has
    # relationship_goal observed. Roll out baseline days until the feasible
    # graph contains a pair with relationship_goal not_asked, freeze that
    # day's features, then reveal the SOFT field one day later (T-FEA-3).
    state, edges, degree = _advance_until(
        sim, sim.observe(), lambda s, e, d: _find_soft_pair(s, e) is not None, 40)
    chosen = _find_soft_pair(state, edges)
    assert chosen, 'no feasible pair with relationship_goal not_asked by day 40'
    a, b = chosen
    feats0 = extract_pair_features(state, degree, a, b)
    stored = list(feats0)
    stored_json = json.dumps(feats0)
    sim.advance([])  # day d -> d+1: no new introductions, ask budget reset
    sim.resolve_asks([{'member_id': a, 'field': 'relationship_goal'}])
    state1 = sim.observe()
    assert json.dumps(extract_pair_features(state, degree, a, b)) == stored_json, \
        'frozen day-d snapshot extraction changed'
    assert stored == feats0, 'stored day-d feature list mutated'
    edges1, degree1 = build_feasible_edges(state1)
    feats1 = extract_pair_features(state1, degree1, a, b)
    changed = [i + 1 for i in range(7, 13) if feats1[i] != stored[i]]
    assert changed, 'late SOFT reveal changed none of features 8-12'


def test_future_feedback_rejected():
    sim = _fresh_sim()
    state = sim.observe()
    edges, degree = build_feasible_edges(state)
    assert edges, 'no feasible edges'
    a, b = edges[0]
    state['feedback'].append({'introduction_id': 'fake_future', 'member_id': None,
                              'event': 'date_happened', 'value': True, 'missing_reason': None,
                              'occurred_day': state['day'] + 99, 'observed_day': state['day'] + 1})
    _expect_assertion(lambda: extract_pair_features(state, degree, a, b),
                      'feedback with observed_day > day must be rejected')


def main():
    tests = [test_audit_classification, test_scrub_invariance,
             test_late_field_immutable, test_future_feedback_rejected]
    failures = 0
    for test in tests:
        try:
            test()
        except Exception as exc:  # noqa: BLE001 - test harness reports every failure
            failures += 1
            print('[FAIL] %s: %s' % (test.__name__, ascii(str(exc))[:300]))
        else:
            print('[PASS] %s' % test.__name__)
    print('SUMMARY: %d/%d PASS' % (len(tests) - failures, len(tests)))
    sys.exit(1 if failures else 0)


if __name__ == '__main__':
    main()
