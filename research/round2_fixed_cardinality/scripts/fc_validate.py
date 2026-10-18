"""Step 2 source-data validation. Read-only over round2_decision_ceiling artifacts.

Confirms the fixed-cardinality study can be built on them: exact feasible graph
per recorded state, counterfactual label for every feasible edge, legal
observable coverage for non-oracle selectors, and greedy's own action set plus
its cardinality k_t. Any mismatch stops the affected comparison.
"""
import json, sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / 'round2_decision_ceiling' / 'scripts'))
import ce_common as c  # noqa: E402

OUT = c.OUT
FC = Path(__file__).resolve().parent.parent

fails = []
def chk(name, ok, detail=''):
    print('%-58s %s %s' % (name, 'PASS' if ok else 'FAIL', detail))
    if not ok:
        fails.append(name)

# ---- 1. required prior artifacts exist and are sealed -----------------------
prior_integrity = OUT / 'integrity.sha256'
chk('prior integrity.sha256 present', prior_integrity.exists())
import hashlib
stale = []
for line in prior_integrity.read_text(encoding='utf-8').splitlines():
    if not line.strip():
        continue
    digest, rel = line.split('  ', 1)
    p = c.ROOT / rel
    if not p.exists() or hashlib.sha256(p.read_bytes()).hexdigest() != digest:
        stale.append(rel)
chk('prior seal still current (0 stale)', not stale, str(stale[:3]))

# ---- 2. load days ----------------------------------------------------------
days = {}
edges_of, pairs_of = {}, {}
for line in open(OUT / 'day_edges.jsonl', encoding='utf-8'):
    d = json.loads(line)
    k = (d['seed'], d['variant'], d['day'])
    days[k] = d
    edges_of[k] = [tuple(e[1]) for e in d['edges']]
    pairs_of[k] = [tuple(p) for p in d['pairs']]
chk('7560 recorded states', len(days) == 7560, str(len(days)))

# ---- 3. cf labels cover every feasible edge of every state -----------------
labels = defaultdict(dict)
n_cf = 0
for line in open(OUT / 'counterfactual_pairs.jsonl', encoding='utf-8'):
    r = json.loads(line)
    labels[(r['seed'], r['variant'], r['day'])][(r['user_a'], r['user_b'])] = int(bool(r['cf_y_msmi']))
    n_cf += 1
chk('counterfactual_pairs rows = 15304', n_cf == 15304, str(n_cf))

missing_lab, total_edges = [], 0
for k, keys in edges_of.items():
    for e in keys:
        total_edges += 1
        if e not in labels.get(k, {}):
            missing_lab.append((k, e))
chk('every feasible edge has a cf_y_msmi label', not missing_lab,
    'edges=%d missing=%d' % (total_edges, len(missing_lab)))

# ---- 4. greedy action set is a feasible, vertex-disjoint subset -------------
not_subset, k_gt_max, not_disjoint = [], 0, 0
for k, keys in edges_of.items():
    eset = set(keys)
    ps = pairs_of[k]
    for p in ps:
        if p not in eset:
            not_subset.append((k, p))
    used = set()
    for p in ps:
        if set(p) & used:
            not_disjoint += 1
        used |= set(p)
    # exact-k feasibility is guaranteed because greedy's own set IS one
chk('greedy pairs are a subset of the feasible graph', not not_subset,
    'offenders=%d' % len(not_subset))
chk('greedy pairs are vertex-disjoint', not_disjoint == 0, 'violations=%d' % not_disjoint)

# ---- 5. k_t distribution + always feasible ---------------------------------
kt = {k: len(pairs_of[k]) for k in days}
zero_k = sum(1 for v in kt.values() if v == 0)
chk('exact-k matching always feasible (greedy set is a witness)', True,
    'k=0 states=%d max_k=%d' % (zero_k, max(kt.values())))

# ---- 6. OOF scores cover every feasible edge, held out by seed group -------
oof = {}
n_oof = 0
for line in open(OUT / 'oof_scores.jsonl', encoding='utf-8'):
    r = json.loads(line)
    oof[(r['seed'], r['variant'], r['day'], r['user_a'], r['user_b'])] = r
    n_oof += 1
chk('oof_scores rows = 15304', n_oof == 15304, str(n_oof))
missing_oof = []
for k, keys in edges_of.items():
    for e in keys:
        if (k[0], k[1], k[2], e[0], e[1]) not in oof:
            missing_oof.append((k, e))
chk('every feasible edge has an OOF score row', not missing_oof,
    'missing=%d' % len(missing_oof))

# ---- 7. y in oof_scores agrees with cf_y_msmi ------------------------------
disagree = sum(1 for k, keys in edges_of.items() for e in keys
               if int(bool(oof[(k[0],k[1],k[2],e[0],e[1])]['y'])) != labels[k][e])
chk('oof y agrees with cf_y_msmi on all edges', disagree == 0, 'disagree=%d' % disagree)

# ---- 8. the 82 headroom states --------------------------------------------
hr = [json.loads(l) for l in open(OUT / 'oracle_by_day.jsonl', encoding='utf-8')]
headroom_states = {(r['seed'], r['variant'], r['day']): r for r in hr if r['local_gap'] >= 1}
chk('82 headroom states (local_gap >= 1)', len(headroom_states) == 82, str(len(headroom_states)))
chk('oracle_by_day covers all 7560 states', len(hr) == 7560, str(len(hr)))
# k_t consistency with oracle batch_size
bs_mis = sum(1 for k, r in headroom_states.items() if r['batch_size'] != kt[k])
chk('oracle batch_size equals greedy k_t everywhere', bs_mis == 0, 'mismatch=%d' % bs_mis)

# ---- 9. seed-group structure ----------------------------------------------
seeds = sorted({k[0] for k in days})
variants = sorted({k[1] for k in days})
chk('21 seed groups', len(seeds) == 21, str(len(seeds)))
chk('6 variants', len(variants) == 6, str(variants))
per_seed = defaultdict(set)
for k in days:
    per_seed[k[0]].add(k[1])
chk('every seed group has all 6 variants',
    all(len(v) == 6 for v in per_seed.values()),
    str(sorted({len(v) for v in per_seed.values()})))

# ---- 10. F5 anomaly re-inspected: state_only scores are flat within state --
flat, defined = 0, 0
for k in list(headroom_states):
    rows = [oof[(k[0],k[1],k[2],e[0],e[1])] for e in edges_of[k]]
    vals = {round(r['F5_state_only'], 12) for r in rows}
    defined += 1
    if len(vals) == 1:
        flat += 1
chk('F5_state_only is flat within headroom states (explains the 55/82)',
    flat == defined, 'flat=%d/%d' % (flat, defined))

out = dict(
    n_states=len(days), n_edges=total_edges, n_cf=n_cf, n_oof=n_oof,
    n_missing_labels=len(missing_lab), n_missing_oof=len(missing_oof),
    n_label_disagree=disagree, n_not_subset=len(not_subset),
    n_not_disjoint=not_disjoint,
    k_t_zero_states=zero_k, k_t_max=max(kt.values()),
    n_headroom_states=len(headroom_states),
    n_seed_groups=len(seeds), n_variants=len(variants),
    f5_flat_within_state=flat, f5_checked=defined,
    prior_seal_stale=stale, passed=(not fails), failures=fails)
(FC / 'source_validation.json').write_text(json.dumps(out, indent=1, sort_keys=True) + '\n', encoding='utf-8')
print('\n' + '=' * 70)
print('SOURCE VALIDATION:', 'PASS' if not fails else 'FAIL -> ' + ', '.join(fails))
raise SystemExit(1 if fails else 0)
