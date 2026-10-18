"""Tests for sr_label.py (implementation_plan.md Task 2, gate T-MAT-1).

Plain python script, standard library only, no pytest. Prints [PASS]/[FAIL] per
test and exits non-zero on any failure.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import kit
from sr_label import (NOT_IN_POPULATION, S1_WINDOW, S2_WINDOW, S3_WINDOW,
                      maturity_report, stage_labels)

UNKNOWN = 'UNKNOWN'
HORIZON_DAY = 100
SEED = 90210
N = 200
POOL_ID = 'test'
# Official six variants, verbatim from evaluate.py L16.
VARIANTS = ('development', 'sparse', 'cold_start', 'delayed', 'shift', 'drift')


def _observed(events, day):
    """Feedback view: only events observed by `day` (receive_feedback, kit.py L110-111)."""
    return [e for e in events if e['observed_day'] <= day]


def _official(intro, es):
    """Independent per-intro recomputation of the kit.metrics() logic (kit.py L192-198).

    `es` must already be this introduction's events. Returns
    (mutual_acceptance, timely_date, official_msmi, late_true_date):
    - mutual: len(rs)==2 and all values 'yes' (kit L194);
    - timely: a date_happened with value True and date_day - assigned <= 30 (kit L197);
    - msmi: timely and exactly two second-yes each within <= 3 days (kit L197);
    - late: a True date beyond the 30-day window (counted by metrics['dates'] at
      kit L195 but excluded by the official MSMI window at kit L197).
    """
    rs = [e for e in es if e['event'] == 'introduction_response']
    mutual = len(rs) == 2 and all(e['value'] == 'yes' for e in rs)
    ds = [e for e in es if e['event'] == 'date_happened' and e['value'] is True]
    timely = bool(ds) and ds[0]['occurred_day'] - intro['assigned_day'] <= 30
    late = bool(ds) and ds[0]['occurred_day'] - intro['assigned_day'] > 30
    ss = [e for e in es if e['event'] == 'second_meeting_intention']
    msmi = (timely and len(ss) == 2
            and all(e['value'] == 'yes'
                    and e['occurred_day'] - ds[0]['occurred_day'] <= 3 for e in ss))
    return mutual, timely, msmi, late


def _rollout(variant):
    """Official episode: 60 baseline ask/match days + 40 empty advances
    (kit.rollout L224-229; kit.py __main__ L236)."""
    world = kit.generate(SEED, N, POOL_ID, variant)
    sim = kit.rollout(world, days=60)
    for _ in range(40):
        sim.advance([])
    return sim


def _expect_raise(fn, exc_type, label):
    try:
        fn()
    except exc_type as exc:
        return exc
    raise AssertionError('expected %s: %s' % (exc_type.__name__, label))


def test_matches_metrics():
    # Derived maturity windows (analysis_plan.md S.2), pinned here as constants.
    assert (S1_WINDOW, S2_WINDOW, S3_WINDOW) == (7, 33, 35), \
        'derived maturity windows changed: %r' % ((S1_WINDOW, S2_WINDOW, S3_WINDOW),)
    for variant in VARIANTS:
        sim = _rollout(variant)
        events = _observed(sim.events, sim.day)
        metrics = sim.metrics()
        by_intro = {}
        for e in events:
            by_intro.setdefault(e['introduction_id'], []).append(e)
        s1_pos = s2_pos = msmi_pos = timely_pos = late_pos = 0
        for intro in sim.introductions:
            iid = intro['introduction_id']
            es = by_intro.get(iid, [])
            # Full event list per call: the documented API consumption pattern
            # (implementation_plan.md Task 2: consumes sim.introductions + sim.events).
            lab = stage_labels(intro, events)
            assert set(lab) == {'s1', 's2', 's3', 'msmi'}, (variant, iid, lab)
            mutual, timely, off_msmi, late = _official(intro, es)
            # T-MAT-1: after the official 60+40 episode no label may be UNKNOWN
            # (maturity proof: every event is observed by day <= 97 < 100).
            assert lab['s1'] in (0, 1), (variant, iid, lab)
            assert lab['s2'] in (0, 1, NOT_IN_POPULATION), (variant, iid, lab)
            assert lab['s3'] in (0, 1, NOT_IN_POPULATION), (variant, iid, lab)
            assert lab['msmi'] in (0, 1), (variant, iid, lab)
            # Per-intro agreement with the independent kit.metrics() recomputation.
            assert lab['s1'] == (1 if mutual else 0), (variant, iid, lab, mutual)
            if mutual:
                assert lab['s2'] in (0, 1) and (lab['s2'] == 1) == timely, \
                    (variant, iid, lab, timely)
            else:
                assert lab['s2'] == NOT_IN_POPULATION, (variant, iid, lab)
            if lab['s2'] == 1:
                assert lab['s3'] in (0, 1) and (lab['s3'] == 1) == off_msmi, \
                    (variant, iid, lab, off_msmi)
            else:
                assert lab['s3'] == NOT_IN_POPULATION, (variant, iid, lab)
            assert lab['msmi'] == (1 if off_msmi else 0), (variant, iid, lab, off_msmi)
            s1_pos += lab['s1'] == 1
            s2_pos += lab['s2'] == 1
            msmi_pos += lab['msmi'] == 1
            timely_pos += timely
            late_pos += late
        # Totals vs official metrics() (kit.py L190-203).
        assert s1_pos == metrics['mutual_acceptances'], \
            (variant, s1_pos, metrics['mutual_acceptances'])
        # metrics['dates'] counts every date_happened with value True (kit L195),
        # while our s2 applies the official <=30 day window (kit L197). Therefore:
        #   metrics['dates'] == timely + late (recompute validated against kit), and
        #   s2_pos == metrics['dates'] EXACTLY when late_pos == 0, otherwise s2_pos
        #   is smaller by exactly the number of late True dates (asserted below).
        assert metrics['dates'] == timely_pos + late_pos, \
            (variant, metrics['dates'], timely_pos, late_pos)
        assert s2_pos == timely_pos, (variant, s2_pos, timely_pos)
        assert s2_pos <= metrics['dates'], (variant, s2_pos, metrics['dates'])
        assert (s2_pos == metrics['dates']) == (late_pos == 0), \
            (variant, s2_pos, metrics['dates'], late_pos)
        # MSMI must match the official metric EXACTLY (brief; plan S.2 / T-MAT-1).
        assert msmi_pos == metrics['mutual_second_meeting_intention'], \
            (variant, msmi_pos, metrics['mutual_second_meeting_intention'])
        # Maturity gate: no raise at horizon 100, everything strictly below it.
        rep = maturity_report(sim.introductions, events)
        assert rep['max_observed_day'] is not None \
            and rep['max_observed_day'] <= HORIZON_DAY - 1, (variant, rep)


def test_unknown_excluded():
    # Synthetic intro with assigned_day 10 and no events at all -> every key
    # UNKNOWN (brief: test_unknown_excluded).
    intro = {'introduction_id': 'syn_empty', 'user_a': 'mem_a', 'user_b': 'mem_b',
             'assigned_day': 10, 'response_deadline_day': 17,
             'logging_policy': 'test', 'propensity': None}
    lab = stage_labels(intro, [])
    assert lab == {'s1': UNKNOWN, 's2': UNKNOWN, 's3': UNKNOWN, 'msmi': UNKNOWN}, lab
    # A partially present stage-1 pair is equally undecidable at the horizon:
    # both response events are required before s1 leaves UNKNOWN (kit L162-166
    # always appends exactly two per introduction).
    partial = [{'introduction_id': 'syn_empty', 'member_id': 'mem_a',
                'event': 'introduction_response', 'value': 'yes',
                'missing_reason': None, 'occurred_day': 11, 'observed_day': 11}]
    lab2 = stage_labels(intro, partial)
    assert lab2 == {'s1': UNKNOWN, 's2': UNKNOWN, 's3': UNKNOWN, 'msmi': UNKNOWN}, lab2
    # Events belonging to a different introduction must not leak into the labels.
    other = [{'introduction_id': 'someone_else', 'member_id': 'mem_z',
              'event': 'introduction_response', 'value': 'no',
              'missing_reason': None, 'occurred_day': 11, 'observed_day': 11}]
    lab3 = stage_labels(intro, other)
    assert lab3 == {'s1': UNKNOWN, 's2': UNKNOWN, 's3': UNKNOWN, 'msmi': UNKNOWN}, lab3
    # Maturity report on an event-free intro: no raise, no maxima recorded.
    rep = maturity_report([intro], [])
    assert rep['n_intros'] == 1 and rep['max_observed_day'] is None, rep
    assert rep['per_intro_max_observed_day'] == {}, rep


def _syn_events(iid, assigned, date_day, second_day):
    """Synthetic mutually-accepted intro mirroring kit event shapes exactly:
    two yes responses (kit L162-166), one date event with value True
    (kit L172-173, no missing_reason key), and two second-yes events
    (kit L181-183) on `second_day`."""
    evs = []
    for i, day in enumerate((assigned + 1, assigned + 2)):
        evs.append({'introduction_id': iid, 'member_id': 'mem_%d' % i,
                    'event': 'introduction_response', 'value': 'yes',
                    'missing_reason': None, 'occurred_day': day, 'observed_day': day})
    evs.append({'introduction_id': iid, 'member_id': None, 'event': 'date_happened',
                'value': True, 'occurred_day': date_day, 'observed_day': date_day})
    for i, day in enumerate((second_day, second_day)):
        evs.append({'introduction_id': iid, 'member_id': 'mem_%d' % i,
                    'event': 'second_meeting_intention', 'value': 'yes',
                    'missing_reason': None, 'occurred_day': day, 'observed_day': day})
    return evs


def test_boundaries():
    assigned = 10
    intro = {'introduction_id': 'syn_boundary', 'user_a': 'mem_0', 'user_b': 'mem_1',
             'assigned_day': assigned, 'response_deadline_day': assigned + 7,
             'logging_policy': 'test', 'propensity': None}
    # (a) Inclusive lower bounds: date exactly at assigned+30, both seconds exactly
    # at date+3 -> all stages 1, msmi 1 (kit L197: <=30 and <=3 are inclusive).
    lab = stage_labels(intro, _syn_events('syn_boundary', assigned,
                                          assigned + 30, assigned + 30 + 3))
    assert lab == {'s1': 1, 's2': 1, 's3': 1, 'msmi': 1}, lab
    # (b) Date one day late (assigned+31): s2 fails, s3 population excluded,
    # msmi 0.
    lab = stage_labels(intro, _syn_events('syn_boundary', assigned,
                                          assigned + 31, assigned + 31 + 3))
    assert lab == {'s1': 1, 's2': 0, 's3': NOT_IN_POPULATION, 'msmi': 0}, lab
    # (c) Second yes one day late (date+4): s3 fails, msmi 0.
    lab = stage_labels(intro, _syn_events('syn_boundary', assigned,
                                          assigned + 30, assigned + 30 + 4))
    assert lab == {'s1': 1, 's2': 1, 's3': 0, 'msmi': 0}, lab
    # (d) Horizon boundary: a response observed at exactly horizon_day is not yet
    # mature -> stage 1 (and everything downstream) UNKNOWN.
    ev_d = _syn_events('syn_boundary', assigned, assigned + 30, assigned + 33)
    ev_d[1] = dict(ev_d[1], occurred_day=HORIZON_DAY, observed_day=HORIZON_DAY)
    lab = stage_labels(intro, ev_d)
    assert lab == {'s1': UNKNOWN, 's2': UNKNOWN, 's3': UNKNOWN, 'msmi': UNKNOWN}, lab
    # (e) Maturity report horizon boundary: observed_day 99 accepted, 100 raises.
    late_intro = {'introduction_id': 'syn_late', 'user_a': 'mem_0', 'user_b': 'mem_1',
                  'assigned_day': 92, 'response_deadline_day': 99,
                  'logging_policy': 'test', 'propensity': None}
    ok_events = [
        {'introduction_id': 'syn_late', 'member_id': 'mem_0',
         'event': 'introduction_response', 'value': 'no', 'missing_reason': None,
         'occurred_day': 93, 'observed_day': 93},
        {'introduction_id': 'syn_late', 'member_id': 'mem_1',
         'event': 'introduction_response', 'value': None,
         'missing_reason': 'no_response', 'occurred_day': None, 'observed_day': 99},
    ]
    rep = maturity_report([late_intro], ok_events)
    assert rep['max_observed_day'] == 99, rep
    assert rep['per_stage_max_observed_day']['s1'] == 99, rep
    bad_events = [dict(ok_events[0]), dict(ok_events[1], observed_day=100)]
    exc = _expect_raise(lambda: maturity_report([late_intro], bad_events),
                        ValueError, 'observed_day == horizon_day must raise')
    assert 'horizon' in str(exc), str(exc)


def main():
    tests = [test_matches_metrics, test_unknown_excluded, test_boundaries]
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
