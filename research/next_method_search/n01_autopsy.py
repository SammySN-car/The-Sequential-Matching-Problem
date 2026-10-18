"""N01 decision-state autopsy - replay harness (diagnostic only, not a policy).

Reconstructs the official greedy control trajectories on the EXISTING tournament
worlds (seeds 143-163 x 6 variants = 126 worlds), verifies byte-fidelity
against the sealed per-phase rows, and extracts decision-time-legal features
plus mature outcome labels for every introduction.

Protocol (identical to evaluate.episode, evaluate.py L80-115): 60 decision days
of (ask phase, match phase) with a fresh sim.observe() per phase, digest over
json.dumps([phase, day, action], sort_keys=True), arrived snapshot at day<=59,
40 follow-up days of advance([]), then sim.metrics().

Actions come from kit.baseline_asks and a line-for-line copy of the
kit.baseline_match allocation (policy.py --baseline greedy routes to exactly
these functions: policy.py L11/L24/L28). Fidelity gate: action_sha256 must
equal the official row AND every aggregate field in COMPARE_FIELDS must match
AND per-introduction label sums must equal the official aggregates, for every
world. Analysis must not run unless all requested worlds match.

Labels (kit.metrics L190-203 + DATA_CONTRACT "Feedback and censoring"):
  mature   every event of the introduction has observed_day <= sim.day at the
           end of follow-up (theoretical max = assigned(<=59)+38 = 97 < 100);
           immature introductions are excluded as right-censored and counted.
  y_mutual exactly 2 introduction_response events, both value == 'yes'.
  y_date   a date_happened event with value True.
  y_second y_date and exactly 2 second_meeting_intention events, both 'yes'
           and both occurred_day - date_day <= 3.
  y_ms...  y_second and date_day - assigned_day <= 30.

Selection bias: labels exist ONLY for pairs greedy chose to introduce;
outcomes of unchosen pairs are counterfactual and unobservable, so every
feature/conversion association below is conditional on selection.

Frozen files are imported read-only. No new seeds are created. All writes go
under research/next_method_search/. Resume semantics: a world is done once its
commit row lands in n01_replay_rows.jsonl (appended last per world).
"""
import argparse
import hashlib
import itertools
import json
import pathlib
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from kit import (SOFT, Simulator, baseline_asks, baseline_match,  # noqa: E402
                 eligibility, generate)

TOURNAMENT = ROOT / 'research' / 'method_tournament' / 'per_phase'
CONTROL = '__control__'
PHASES = {
    'screening': (143, 144, 145),
    'confirm1': (146, 147, 148, 149, 150, 151),
    'confirm2': (152, 153, 154, 155, 156, 157, 158, 159, 160, 161, 162, 163),
}
VARIANTS = ('development', 'sparse', 'cold_start', 'delayed', 'shift', 'drift')

# Aggregate fields compared byte-for-byte against the official control row.
# (inference_seconds is timing-only and excluded; action_sha256 is compared
# separately and is the primary fidelity gate.)
COMPARE_FIELDS = (
    'assignments', 'mutual_acceptances', 'dates',
    'mutual_second_meeting_intention', 'missing_feedback', 'ask_cost',
    'arrived_members', 'served_members', 'unserved_members', 'coverage',
    'mutual_acceptances_per_100', 'msmi_per_100_arrived_members',
    'first_introduction_wait_days',
)

# Gate-candidate features. ALL are computed from the match-phase state the
# policy saw (decision-time legal). Seed/variant are strata keys only and are
# deliberately NOT features.
FEATURE_BOOLEANS = ('score_is_max', 'same_gender', 'zone_same',
                    'new_arrival_today', 'has_prior', 'has_history')
FEATURE_NUMBERS = (
    'pair_score', 'pair_score_deficit', 'pair_rank', 'batch_size',
    'edges_total', 'edges_at_same_score', 'age_gap', 'soft_obs_min',
    'soft_obs_max', 'soft_unequal', 'soft_unknown_max', 'soft_declined_max',
    'arrival_age_min', 'arrival_age_max', 'degree_min', 'degree_max',
    'degree_excl_min', 'degree_excl_max', 'prior_intro_max',
    'prior_mutual_total', 'prior_date_total', 'day', 'ask_budget_match',
    'n_available', 'n_intros_so_far', 'n_mutual_so_far', 'n_dates_so_far',
)
LABELS = ('y_msmi', 'y_mutual', 'y_date', 'y_second')

OUT_ROWS = HERE / 'n01_replay_rows.jsonl'
OUT_DAYS = HERE / 'n01_days.jsonl'
OUT_INTROS = HERE / 'n01_introductions.jsonl'
OUT_SUMMARY = HERE / 'n01_replay_summary.json'


def phase_of(seed):
    for name, seeds in PHASES.items():
        if seed in seeds:
            return name
    raise ValueError('seed not in any phase: %r' % seed)


def load_official():
    """Official control rows per (seed, variant), last-write-wins dedupe."""
    official = {}
    for name in ('screening_rows.jsonl', 'confirm1_rows.jsonl',
                 'confirm2_rows.jsonl'):
        path = TOURNAMENT / name
        for line in path.read_text(encoding='utf-8').splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if row['method'] == CONTROL and row.get('valid'):
                official[(row['seed'], row['variant'])] = row
    return official


def episode_result(sim, arrived, digest_hex):
    """evaluate.episode post-processing copied from evaluate.py L98-114."""
    result = sim.metrics()
    first = {}
    for intro in sim.introductions:
        for member in (intro['user_a'], intro['user_b']):
            first.setdefault(member, intro['assigned_day'])
    waits = sorted(first[i] - arrived[i] for i in first)
    result.update(valid=True, arrived_members=len(arrived),
                  msmi_per_100_arrived_members=100 * result['mutual_second_meeting_intention'] / max(1, len(arrived)),
                  served_members=len(first), unserved_members=len(arrived) - len(first),
                  coverage=len(first) / max(1, len(arrived)),
                  mutual_acceptances_per_100=100 * result['mutual_acceptances'] / max(1, len(arrived)),
                  first_introduction_wait_days=waits,
                  inference_seconds=0.0, action_sha256=digest_hex)
    return result


def allocate(state):
    """kit.baseline_match line-for-line (kit.py L210-222) plus edge metadata.

    Returns (pairs, edges, degree, used): pairs identical to the control
    action, edges as (-score, key), endpoint degree counter, used endpoints.
    """
    members = [m for m in state['members'] if m['available']]
    past = {tuple(sorted((i['user_a'], i['user_b'])))
            for i in state['introductions']}
    edges = []
    for a, b in itertools.combinations(members, 2):
        key = tuple(sorted((a['member_id'], b['member_id'])))
        if key in past or eligibility(a, b)['status'] != 'feasible':
            continue
        score = sum(a['fields'].get(k) is not None
                    and a['fields'].get(k) == b['fields'].get(k) for k in SOFT)
        edges.append((-score, key))
    degree = Counter()
    for _, key in edges:
        degree.update(key)
    used = set()
    pairs = []
    for _, key in sorted(edges):
        if not used.intersection(key):
            pairs.append(list(key))
            used.update(key)
    return pairs, edges, degree, used


def day_history(state):
    """Decision-time history from state['introductions'] + state['feedback'].

    feedback contains only events with observed_day <= day, so outcomes are
    'so far as observed today'. Returns (member_hist, n_intros, n_mutual,
    n_dates, n_feedback_events); member_hist maps member_id ->
    (intros_so_far, mutual_so_far, dates_so_far).
    """
    by_intro = defaultdict(list)
    for e in state['feedback']:
        by_intro[e['introduction_id']].append(e)
    member_hist = {}
    n_intros = n_mutual = n_dates = 0
    for intro in state['introductions']:
        n_intros += 1
        es = by_intro.get(intro['introduction_id'], [])
        rs = [e for e in es if e['event'] == 'introduction_response']
        mutual = int(len(rs) == 2 and all(e['value'] == 'yes' for e in rs))
        dated = int(any(e['event'] == 'date_happened' and e['value'] is True
                        for e in es))
        n_mutual += mutual
        n_dates += dated
        for mid in (intro['user_a'], intro['user_b']):
            acc = member_hist.get(mid, (0, 0, 0))
            member_hist[mid] = (acc[0] + 1, acc[1] + mutual, acc[2] + dated)
    return member_hist, n_intros, n_mutual, n_dates, len(state['feedback'])


def pair_features(state, edges, degree, max_score, score_counts, member_hist,
                  day_ctx, pair, rank, batch):
    """Decision-time-legal features for one chosen pair, from match state."""
    by_id = {m['member_id']: m for m in state['members']}
    a, b = by_id[pair[0]], by_id[pair[1]]
    key = tuple(pair)
    score = -next(e[0] for e in edges if e[1] == key)
    obs_a = sum(a['fields'].get(k) is not None for k in SOFT)
    obs_b = sum(b['fields'].get(k) is not None for k in SOFT)
    unequal = sum(a['fields'].get(k) is not None and b['fields'].get(k) is not None
                  and a['fields'].get(k) != b['fields'].get(k) for k in SOFT)
    declined_a = sum(a['field_status'][k] == 'declined' for k in SOFT)
    declined_b = sum(b['field_status'][k] == 'declined' for k in SOFT)
    ha = member_hist.get(a['member_id'], (0, 0, 0))
    hb = member_hist.get(b['member_id'], (0, 0, 0))
    deg_a, deg_b = degree[a['member_id']], degree[b['member_id']]
    age_a = state['day'] - a['arrived_day']
    age_b = state['day'] - b['arrived_day']
    row = {
        'day': state['day'],
        'user_a': pair[0], 'user_b': pair[1],
        'pair_rank': rank, 'batch_size': batch,
        'pair_score': score,
        'pair_score_deficit': score - max_score,
        'score_is_max': int(score == max_score),
        'edges_total': len(edges),
        'edges_at_same_score': score_counts.get(-score, 0),
        'age_gap': abs(a['age'] - b['age']),
        'same_gender': int(a['gender'] == b['gender']),
        'zone_same': int(a['zone'] == b['zone']),
        'soft_obs_min': min(obs_a, obs_b),
        'soft_obs_max': max(obs_a, obs_b),
        'soft_unequal': unequal,
        'soft_unknown_max': max(len(SOFT) - obs_a, len(SOFT) - obs_b),
        'soft_declined_max': max(declined_a, declined_b),
        'arrival_age_min': min(age_a, age_b),
        'arrival_age_max': max(age_a, age_b),
        'new_arrival_today': int(min(age_a, age_b) == 0),
        'degree_min': min(deg_a, deg_b),
        'degree_max': max(deg_a, deg_b),
        'degree_excl_min': min(deg_a, deg_b) - 1,
        'degree_excl_max': max(deg_a, deg_b) - 1,
        'prior_intro_max': max(ha[0], hb[0]),
        'prior_mutual_total': ha[1] + hb[1],
        'prior_date_total': ha[2] + hb[2],
        'has_prior': int(ha[0] > 0 or hb[0] > 0),
        'ask_budget_match': state['ask_budget_remaining'],
        'has_history': day_ctx['has_history'],
        'n_available': day_ctx['n_available'],
        'n_intros_so_far': day_ctx['n_intros'],
        'n_mutual_so_far': day_ctx['n_mutual'],
        'n_dates_so_far': day_ctx['n_dates'],
    }
    return row

def replay_world(seed, variant, official):
    """Replay one control world; return world/day/introduction rows."""
    started = time.time()
    world = generate(seed, 200, 'evaluation', variant)
    sim = Simulator(world)
    digest = hashlib.sha256()
    day_rows, intro_rows = [], []
    for _ in range(60):
        state_ask = sim.observe()
        asks = baseline_asks(state_ask)
        digest.update(json.dumps(['ask', sim.day, asks], sort_keys=True).encode())
        sim.resolve_asks(asks)
        state = sim.observe()
        pairs, edges, degree, used = allocate(state)
        if sim.day == 0:
            assert pairs == baseline_match(state), \
                'day-0 allocation diverges from kit.baseline_match'
        digest.update(json.dumps(['match', sim.day, pairs], sort_keys=True).encode())
        member_hist, n_intros, n_mutual, n_dates, n_fb = day_history(state)
        day_ctx = {
            'has_history': int(n_intros > 0),
            'n_available': sum(1 for m in state['members'] if m['available']),
            'n_intros': n_intros, 'n_mutual': n_mutual, 'n_dates': n_dates,
        }
        max_score = -min((e[0] for e in edges), default=0)
        score_counts = Counter(e[0] for e in edges)
        edge_members = set()
        for _, key in edges:
            edge_members.update(key)
        day_rows.append({
            'phase': phase_of(seed), 'seed': seed, 'variant': variant,
            'day': sim.day,
            'n_arrived': len(state['members']),
            'n_available': day_ctx['n_available'],
            'edges_total': len(edges), 'n_pairs': len(pairs),
            'zero_selection': int(not pairs),
            'unmatched_despite_edges': len(edge_members - used),
            'ask_spend_today': 12 - state['ask_budget_remaining'],
            'n_intros_so_far': n_intros, 'n_mutual_so_far': n_mutual,
            'n_dates_so_far': n_dates, 'n_feedback_events': n_fb,
            'has_history': int(n_intros > 0),
        })
        before = len(sim.introductions)
        sim.advance(pairs)
        new_intros = sim.introductions[before:]
        by_pair = {tuple(sorted((i['user_a'], i['user_b']))): i
                   for i in new_intros}
        assert len(by_pair) == len(pairs), 'introduction mapping mismatch'
        batch = len(pairs)
        for rank, pair in enumerate(pairs):
            intro = by_pair[tuple(pair)]
            row = pair_features(state, edges, degree, max_score, score_counts,
                                member_hist, day_ctx, pair, rank, batch)
            row.update(phase=phase_of(seed), seed=seed, variant=variant,
                       introduction_id=intro['introduction_id'],
                       assigned_day=intro['assigned_day'])
            intro_rows.append(row)
    arrived = {m['member_id']: m['arrived_day']
               for m in sim.observe()['members'] if m['arrived_day'] <= 59}
    for _ in range(40):
        sim.advance([])
    result = episode_result(sim, arrived, digest.hexdigest())
    final_day = sim.day
    events_by = defaultdict(list)
    for e in sim.events:
        events_by[e['introduction_id']].append(e)
    n_immature = 0
    for row in intro_rows:
        es = events_by.get(row['introduction_id'], [])
        mature = int(bool(es) and all(e['observed_day'] <= final_day
                                      for e in es))
        row['mature'] = mature
        if not mature:
            n_immature += 1
            row.update(y_msmi=None, y_mutual=None, y_date=None, y_second=None,
                       missing=None)
            continue
        rs = [e for e in es if e['event'] == 'introduction_response']
        y_mutual = int(len(rs) == 2 and all(e['value'] == 'yes' for e in rs))
        ds = [e for e in es
              if e['event'] == 'date_happened' and e['value'] is True]
        y_date = int(bool(ds))
        ss = [e for e in es if e['event'] == 'second_meeting_intention']
        second_ok = bool(ds) and len(ss) == 2 and all(
            e['value'] == 'yes'
            and e['occurred_day'] - ds[0]['occurred_day'] <= 3 for e in ss)
        y_second = int(second_ok)
        y_msmi = int(second_ok
                     and ds[0]['occurred_day'] - row['assigned_day'] <= 30)
        row.update(y_msmi=y_msmi, y_mutual=y_mutual, y_date=y_date,
                   y_second=y_second,
                   missing=sum(e.get('missing_reason') == 'no_response'
                               for e in es))
    aggregates_match = {f: result[f] == official[f] for f in COMPARE_FIELDS}
    digest_match = result['action_sha256'] == official['action_sha256']
    mature_rows = [r for r in intro_rows if r['mature']]
    sums = {
        'assignments': len(intro_rows),
        'mutual': sum(r['y_mutual'] for r in mature_rows),
        'dates': sum(r['y_date'] for r in mature_rows),
        'msmi': sum(r['y_msmi'] for r in mature_rows),
        'missing': sum(r['missing'] for r in mature_rows),
    }
    label_sums_match = (
        sums['assignments'] == official['assignments']
        and sums['mutual'] == official['mutual_acceptances']
        and sums['dates'] == official['dates']
        and sums['msmi'] == official['mutual_second_meeting_intention']
        and sums['missing'] == official['missing_feedback'])
    world_row = {
        'phase': phase_of(seed), 'seed': seed, 'variant': variant,
        'digest_match': digest_match,
        'official_digest': official['action_sha256'],
        'replay_digest': result['action_sha256'],
        'aggregates_match': aggregates_match,
        'label_sums_match': label_sums_match,
        'all_match': bool(digest_match and all(aggregates_match.values())
                          and label_sums_match),
        'n_intros': len(intro_rows), 'n_immature': n_immature,
        'max_observed_day': max((e['observed_day'] for e in sim.events),
                                default=0),
        'final_day': final_day,
        'zero_selection_days': sum(r['zero_selection'] for r in day_rows),
        'ask_cost': result['ask_cost'],
        'sums': sums,
        'wall_seconds': round(time.time() - started, 1),
    }
    return {'world': world_row, 'days': day_rows, 'intros': intro_rows}


def dump_rows(path, rows):
    with path.open('a', encoding='utf-8') as fh:
        for r in rows:
            fh.write(json.dumps(r, sort_keys=True, allow_nan=False) + '\n')


def read_rows(path):
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding='utf-8').splitlines()
            if l.strip()]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--phase', default='all', choices=sorted(PHASES) + ['all'])
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--limit', type=int, default=0,
                    help='pilot mode: replay only the first N pending worlds')
    ap.add_argument('--fresh', action='store_true',
                    help='delete prior N01 outputs before running')
    args = ap.parse_args(argv)
    if args.fresh:
        for path in (OUT_ROWS, OUT_DAYS, OUT_INTROS, OUT_SUMMARY):
            path.unlink(missing_ok=True)
    official = load_official()
    wanted_phases = sorted(PHASES) if args.phase == 'all' else [args.phase]
    worlds = [(s, v) for ph in wanted_phases for s in PHASES[ph]
              for v in VARIANTS]
    done_rows = read_rows(OUT_ROWS)
    done = {(r['seed'], r['variant']) for r in done_rows}
    todo = [(s, v) for (s, v) in worlds if (s, v) not in done]
    if args.limit:
        todo = todo[:args.limit]
    print('worlds requested=%d done=%d to_replay=%d'
          % (len(worlds), len(done & set(worlds)), len(todo)), flush=True)
    if todo:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(replay_world, s, v, official[(s, v)]): (s, v)
                       for s, v in todo}
            for fut in as_completed(futures):
                sv = futures[fut]
                try:
                    res = fut.result()
                except Exception as exc:  # record, never lose the run
                    res = {'world': {'phase': phase_of(sv[0]), 'seed': sv[0],
                                     'variant': sv[1], 'digest_match': False,
                                     'label_sums_match': False,
                                     'all_match': False,
                                     'error': repr(exc),
                                     'n_intros': 0, 'n_immature': 0},
                           'days': [], 'intros': []}
                    print('ERROR %r %r' % (sv, exc), flush=True)
                w = res['world']
                # commit order: days, intros, then the world row as marker
                dump_rows(OUT_DAYS, res['days'])
                dump_rows(OUT_INTROS, res['intros'])
                dump_rows(OUT_ROWS, [w])
                print('world %r digest=%s all=%s intros=%s'
                      % (sv, w.get('digest_match'), w.get('all_match'),
                         w.get('n_intros')), flush=True)
    keyset = set(worlds)
    rows = {(r['seed'], r['variant']): r for r in read_rows(OUT_ROWS)}
    rows = [r for k, r in rows.items() if k in keyset]
    n_ok = sum(1 for r in rows if r.get('all_match'))
    summary = {
        'worlds_requested': len(worlds), 'worlds_present': len(rows),
        'worlds_fidelity_ok': n_ok,
        'digest_matches': sum(1 for r in rows if r.get('digest_match')),
        'label_sums_match': sum(1 for r in rows if r.get('label_sums_match')),
        'errors': ['%s/%s' % (r.get('seed'), r.get('variant')) for r in rows
                   if r.get('error')],
        'total_introductions': sum(r.get('n_intros', 0) for r in rows),
        'total_immature': sum(r.get('n_immature', 0) for r in rows),
        'max_observed_day_overall': max((r.get('max_observed_day', 0)
                                         for r in rows), default=0),
        'all_fidelity_match': bool(len(rows) == len(worlds)
                                   and n_ok == len(worlds)),
        'feature_booleans': list(FEATURE_BOOLEANS),
        'feature_numbers': list(FEATURE_NUMBERS),
        'labels': list(LABELS),
    }
    OUT_SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + '\n',
                           encoding='utf-8')
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary['all_fidelity_match'] else 2


if __name__ == '__main__':
    raise SystemExit(main())