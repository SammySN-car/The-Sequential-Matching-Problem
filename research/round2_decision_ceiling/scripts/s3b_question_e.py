"""Section 5 question E (decision relevance) - preregistered in analysis_plan.md
5.3 but omitted from the implementation plan transcription.

On day-states with positive local headroom (section 6) AND a genuine composition
choice, does the model rank the positive edges above the ones it did not take?

Choice condition uses Amendment 1's alt_same_size. The literal frozen wording
">=2 distinct valid matchings" counts the empty set and is therefore satisfied by
every day with an edge (the same degeneracy Amendment 1 fixed for
matching_unique); the non-degenerate reading is >=2 distinct matchings of the
collector's own batch size.
"""
import csv, json, sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ce_common as c  # noqa: E402
from sklearn.metrics import roc_auc_score  # noqa: E402

FEATURE_SETS = ['F1_baseline_count_score', 'F2_soft_state', 'F3_public_profile',
                'F4_full_legal_observables', 'F5_state_only']


def main():
    c.log('task5e start: decision relevance (question E)')
    headroom, choice, edges_of = {}, {}, {}
    for line in open(c.OUT / 'oracle_by_day.jsonl', encoding='utf-8'):
        r = json.loads(line)
        headroom[(r['seed'], r['variant'], r['day'])] = r['local_gap']
    for line in open(c.OUT / 'day_edges.jsonl', encoding='utf-8'):
        d = json.loads(line)
        k = (d['seed'], d['variant'], d['day'])
        choice[k] = d['metrics']['alt_same_size']
        edges_of[k] = [tuple(e[1]) for e in d['edges']]

    by_state = defaultdict(list)
    for line in open(c.OUT / 'oof_scores.jsonl', encoding='utf-8'):
        r = json.loads(line)
        by_state[(r['seed'], r['variant'], r['day'])].append(r)

    states = [k for k in headroom if headroom[k] >= 1 and choice.get(k)]
    c.log('headroom states=%d, of which with a composition choice=%d'
          % (sum(1 for v in headroom.values() if v >= 1), len(states)))

    rows = []
    for name in FEATURE_SETS:
        aucs, hits, n_beat, n_state_undef = [], 0, 0, 0
        for k in states:
            recs = by_state[k]
            y = np.array([r['y'] for r in recs])
            s = np.array([r[name] for r in recs])
            if len(set(y)) > 1:
                aucs.append(float(roc_auc_score(y, s)))
            else:
                n_state_undef += 1
            keys = edges_of[k]
            key2i = {(recs[i]['user_a'], recs[i]['user_b']): i
                     for i in range(len(recs))}
            best, best_n = float('-inf'), 0
            for mt in c.enumerate_matchings(keys)[0]:
                v = sum(s[key2i[keys[j]]] for j in mt)
                if v > best:
                    best, best_n = v, len(mt)
            if best is None:
                best_n = 0
            picked_pos = 0
            for mt in c.enumerate_matchings(keys)[0]:
                v = sum(s[key2i[keys[j]]] for j in mt)
                if abs(v - best) < 1e-12:
                    n = sum(y[key2i[keys[j]]] for j in mt)
                    picked_pos = max(picked_pos, n)
            coll = sum(int(r['selected'] and r['y']) for r in recs)
            hits += int(picked_pos > coll)
            n_beat += 1
        rows.append(dict(
            feature_set=name, n_headroom_choice_states=len(states),
            n_states_auc_defined=len(aucs), n_states_single_class=n_state_undef,
            within_state_auc_mean=(round(float(np.mean(aucs)), 6) if aucs else ''),
            within_state_auc_posweighted='',
            n_states_argmax_compared=n_beat,
            n_states_argmax_beats_collector=hits,
            argmax_beats_collector_rate=round(hits / n_beat, 6) if n_beat else '',
            collector_positive_states=sum(
                1 for k in states if any(r['selected'] and r['y']
                                         for r in by_state[k]))))
        c.log('E %s states=%d auc_defined=%d within_auc=%s argmax_beats=%d/%d'
              % (name, len(states), len(aucs),
                 rows[-1]['within_state_auc_mean'], hits, n_beat))
    with open(c.OUT / 'decision_relevance.csv', 'w', newline='',
              encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)
    c.log('wrote decision_relevance.csv')
    c.log('task5e done')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
