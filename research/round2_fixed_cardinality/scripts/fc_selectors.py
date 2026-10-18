"""Fixed-cardinality selector comparison.

Every arm selects EXACTLY k_t pairs on the same recorded state, so all
differences are pure pair-selection effects with zero volume component.

Arms (see analysis_plan.md 5 for the full mapping to audit feature sets):
  GREEDY      recorded original action set (reference)
  F1-SCORE    exact-k max of baseline soft-match count
  F2-SOFT     exact-k max of OOF F2_soft_state score
  F3-OBSERV   exact-k max of OOF F4_full_legal_observables score
  F4-RANDOM   zero-discrimination control, R=100 replicates, fixed seed
  F5-ORACLE   exact-k max of counterfactual MSMI labels (not deployable)
"""
import csv, hashlib, json, random, statistics, sys, time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent /
                        'round2_decision_ceiling' / 'scripts'))
import ce_common as c  # noqa: E402
from fc_matching import check_matching, solve_exact_k  # noqa: E402

FC = Path(__file__).resolve().parent.parent
BASE_SEED = 4242
R_REPLICATES = 100
DAY_BANDS = ((0, 9, '0-9'), (10, 19, '10-19'), (20, 39, '20-39'), (40, 59, '40-59'))
ARMS = ['GREEDY', 'F1-SCORE', 'F2-SOFT', 'F3-OBSERV', 'F4-RANDOM', 'F5-ORACLE']


def band(v, table):
    for lo, hi, name in table:
        if lo <= v <= hi:
            return name
    return 'other'


def stable_rng(key):
    """PYTHONHASHSEED-independent per-state rng (hash() on str is salted)."""
    h = hashlib.md5(('%d|%s|%s|%d' % (BASE_SEED, key[0], key[1], key[2]))
                    .encode('utf-8')).digest()
    return random.Random(int.from_bytes(h[:8], 'big'))


def random_exact_k(edges, k, rng, max_tries=200):
    """Uniform-permutation greedy acceptance to size exactly k.

    Zero pair-outcome information is consulted. Reshuffles until k edges are
    accepted; the number of reshuffles is reported so failures are visible
    rather than silently reducing cardinality.
    """
    if k == 0:
        return (), 0
    for attempt in range(max_tries):
        perm = edges[:]
        rng.shuffle(perm)
        used, chosen = set(), []
        for e in perm:
            if len(chosen) == k:
                break
            if e[0] not in used and e[1] not in used:
                chosen.append(e)
                used.add(e[0]); used.add(e[1])
        if len(chosen) == k:
            return tuple(sorted(chosen)), attempt
    raise RuntimeError('F4-RANDOM failed to reach k=%d after %d tries'
                       % (k, max_tries))


def main():
    c.log('fc_selectors start (base_seed=%d, R=%d)' % (BASE_SEED, R_REPLICATES))
    t0 = time.time()

    labels = defaultdict(dict)
    for line in open(c.OUT / 'counterfactual_pairs.jsonl', encoding='utf-8'):
        r = json.loads(line)
        labels[(r['seed'], r['variant'], r['day'])][(r['user_a'], r['user_b'])] = \
            int(bool(r['cf_y_msmi']))

    oof = {}
    for line in open(c.OUT / 'oof_scores.jsonl', encoding='utf-8'):
        r = json.loads(line)
        oof[(r['seed'], r['variant'], r['day'], r['user_a'], r['user_b'])] = r

    headroom = {}
    for line in open(c.OUT / 'oracle_by_day.jsonl', encoding='utf-8'):
        r = json.loads(line)
        headroom[(r['seed'], r['variant'], r['day'])] = r

    rows = []
    fails = []
    n_retry_reps = 0
    n_total_reps = 0
    max_reshuffle = 0
    for i, line in enumerate(open(c.OUT / 'day_edges.jsonl', encoding='utf-8')):
        d = json.loads(line)
        key = (d['seed'], d['variant'], d['day'])
        raw = d['edges']
        edges = [tuple(e[1]) for e in raw]
        pairs = [tuple(p) for p in d['pairs']]
        kt = len(pairs)
        hr = headroom[key]
        lab = labels[key]
        idx = {e: j for j, e in enumerate(edges)}
        day_band = band(d['day'], DAY_BANDS)

        def positives(sel):
            return sum(lab[e] for e in sel)

        row = dict(seed=key[0], variant=key[1], day=key[2], day_band=day_band,
                   n_edges=len(edges), k_t=kt,
                   local_gap=hr['local_gap'], headroom=int(hr['local_gap'] >= 1),
                   max_matching_size=hr['max_matching_size'],
                   maxcard_positives=hr['maxcard_positives'])

        # ---- reference arm -------------------------------------------------
        gsel = pairs
        row['GREEDY_positives'] = positives(gsel)
        row['GREEDY_selected'] = kt

        # ---- exact-k arms --------------------------------------------------
        weightings = {
            'F1-SCORE':  [-e[0] for e in raw],
            'F2-SOFT':   [oof[(key[0], key[1], key[2], e[0], e[1])]['F2_soft_state']
                          for e in edges],
            'F3-OBSERV': [oof[(key[0], key[1], key[2], e[0], e[1])]['F4_full_legal_observables']
                          for e in edges],
            'F5-ORACLE': [lab[e] for e in edges],
        }
        selected = {}
        for arm in ('F1-SCORE', 'F2-SOFT', 'F3-OBSERV', 'F5-ORACLE'):
            if kt == 0:
                sel_i, obj, nodes, failed = (), 0.0, 0, False
            else:
                sel_i, obj, nodes, failed = solve_exact_k(edges, weightings[arm], kt)
            if failed or sel_i is None:
                fails.append('%s %s' % (arm, key))
                continue
            ok, why = check_matching(edges, sel_i, kt)
            if not ok:
                fails.append('%s %s: %s' % (arm, key, why))
            sel = tuple(edges[j] for j in sel_i)
            selected[arm] = sel
            row[arm + '_selected'] = len(sel)
            row[arm + '_positives'] = positives(sel)
            row[arm + '_changed_set'] = int(set(sel) != set(gsel))
            row[arm + '_changed_count'] = int(positives(sel) != row['GREEDY_positives'])

        # ---- F4-RANDOM control --------------------------------------------
        rng = stable_rng(key)
        draws, retries = [], 0
        for _ in range(R_REPLICATES):
            sel, att = random_exact_k(edges, kt, rng)
            draws.append(positives(sel))
            retries += att
            n_total_reps += 1
            if att:
                n_retry_reps += 1
                max_reshuffle = max(max_reshuffle, att)
        row['F4-RANDOM_selected'] = kt
        row['F4-RANDOM_positives'] = round(statistics.fmean(draws), 6)
        row['F4-RANDOM_min'] = min(draws)
        row['F4-RANDOM_median'] = statistics.median(draws)
        row['F4-RANDOM_max'] = max(draws)
        row['F4-RANDOM_std'] = round(statistics.pstdev(draws), 6)
        row['F4-RANDOM_retries_mean'] = round(retries / R_REPLICATES, 6)
        row['F4-RANDOM_changed_set'] = 1   # a random draw essentially never equals greedy
        row['F4-RANDOM_changed_count'] = int(
            abs(row['F4-RANDOM_positives'] - row['GREEDY_positives']) > 1e-12)
        row['F4-RANDOM_beats_greedy_replicates'] = sum(1 for x in draws
                                                       if x > row['GREEDY_positives'])
        row['F4-RANDOM_ties_greedy_replicates'] = sum(1 for x in draws
                                                      if x == row['GREEDY_positives'])

        rows.append(row)
        if (i + 1) % 1500 == 0:
            c.log('  %d/%d states  (%.1fs)' % (i + 1, 7560, time.time() - t0))

    c.log('fc_selectors: %d states, solver/constraint failures=%d'
          % (len(rows), len(fails)))
    if fails:
        for f in fails[:10]:
            c.log('  FAIL %s' % f)
        raise SystemExit('%d selector failures' % len(fails))

    c.write_jsonl(FC / 'per_state_results.jsonl', rows)
    fields = list(rows[0].keys())
    with open(FC / 'per_state_results.csv', 'w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader(); w.writerows(rows)
    c.log('wrote per_state_results.csv (%d rows, %d cols)' % (len(rows), len(fields)))

    (FC / 'random_control.json').write_text(json.dumps(dict(
        base_seed=BASE_SEED, replicates_per_state=R_REPLICATES,
        n_replicates_total=n_total_reps,
        n_replicates_needing_reshuffle=n_retry_reps,
        max_reshuffles= max_reshuffle), indent=1, sort_keys=True) + '\n',
        encoding='utf-8')
    c.log('task selectors done (%.1fs)' % (time.time() - t0))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
