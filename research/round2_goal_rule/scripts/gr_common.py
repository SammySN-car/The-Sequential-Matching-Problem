"""Shared helpers for the Relationship-Goal Rule diagnostic study.

Read-only over every prior artifact. All outputs land under
research/round2_goal_rule/. Reuses the validated solver (fc_matching), the
frozen soft-channel definitions (s3_signal), and frozen OOF predictions.
"""
import hashlib, json, sys, time
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent                 # .../round2_goal_rule/scripts
OUT = HERE.parent                                      # .../round2_goal_rule
ROOT = HERE.parent.parent.parent                       # repository root
CEIL_DIR = ROOT / 'research' / 'round2_decision_ceiling'
FC_DIR = ROOT / 'research' / 'round2_fixed_cardinality'
MO_DIR = ROOT / 'research' / 'round2_missed_oracle'
SS_DIR = ROOT / 'research' / 'round2_stagewise_signal'
sys.path.insert(0, str(FC_DIR / 'scripts'))
sys.path.insert(0, str(CEIL_DIR / 'scripts'))

import ce_common as c          # noqa: E402
import s3_signal as s3         # noqa: E402
from fc_matching import solve_exact_k, check_matching  # noqa: E402

B, SEED = 2000, 4242           # seed-group bootstrap, frozen in analysis_plan.md
ARMS = ['G0', 'G1f', 'G1m', 'G2', 'G3', 'G4', 'G5']
ARM_NAMES = {'G0': 'original_greedy',
             'G1f': 'frozen_F1_reproduction_minimizes_count',
             'G1m': 'baseline_count_score_maximizing',
             'G2': 'relationship_goal_score',
             'G3': 'goal_plus_conversations',
             'G4': 'F2_SOFT_oof', 'G5': 'F5_oracle_reference'}
SCORED_ARMS = ['G1f', 'G1m', 'G2', 'G3', 'G4']
# reference arms for paired deltas (Amendment 1): both baselines
BASELINES = ['G1f', 'G1m']


def log(msg):
    line = '[%s] %s' % (time.strftime('%Y-%m-%dT%H:%M:%S'), msg)
    print(line, flush=True)
    with open(OUT / 'run_log.txt', 'a', encoding='utf-8') as fh:
        fh.write(line + '\n')


def read_jsonl(path):
    with open(path, encoding='utf-8') as fh:
        return [json.loads(l) for l in fh if l.strip()]


def write_jsonl(path, rows):
    with open(path, 'w', encoding='utf-8') as fh:
        for r in rows:
            fh.write(json.dumps(r, sort_keys=True) + '\n')
    log('wrote %s (%d rows)' % (Path(path).name, len(rows)))


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def seal_stale(study_dir, tolerate_run_log=False):
    """Files in a study's integrity.sha256 whose content no longer matches."""
    stale = []
    for line in (Path(study_dir) / 'integrity.sha256').read_text(
            encoding='utf-8').splitlines():
        if not line.strip():
            continue
        d, rel = line.split('  ', 1)
        p = ROOT / rel
        if not p.exists() or sha256(p) != d:
            stale.append(rel)
    if tolerate_run_log:
        stale = [x for x in stale if not x.endswith('run_log.txt')]
    return stale


# ---------------------------------------------------------------------------
# Frozen input loaders
# ---------------------------------------------------------------------------

def load_day_edges():
    """7,560 states: key, edges (canonical tuples), neg_scores, greedy pairs."""
    out = []
    for r in read_jsonl(CEIL_DIR / 'day_edges.jsonl'):
        edges = [tuple(e[1]) for e in r['edges']]
        out.append(dict(key=(r['seed'], r['variant'], r['day']),
                        edges=edges,
                        neg_scores=[e[0] for e in r['edges']],
                        greedy=[tuple(p) for p in r['pairs']]))
    return out


def load_labels():
    """(seed,variant,day) -> {(ua,ub): 0/1} counterfactual MSMI labels."""
    out = defaultdict(dict)
    for r in read_jsonl(CEIL_DIR / 'counterfactual_pairs.jsonl'):
        out[(r['seed'], r['variant'], r['day'])][(r['user_a'], r['user_b'])] = \
            int(bool(r['cf_y_msmi']))
    return out


def load_oof_f2():
    """(seed,variant,day,ua,ub) -> frozen OOF F2_soft_state score."""
    out = {}
    for r in read_jsonl(CEIL_DIR / 'oof_scores.jsonl'):
        out[(r['seed'], r['variant'], r['day'], r['user_a'], r['user_b'])] = \
            float(r['F2_soft_state'])
    return out


def load_diag():
    """(seed,variant,day) -> selection_diagnostics record (k_t, headroom...)."""
    return {(r['seed'], r['variant'], r['day']): r
            for r in read_jsonl(MO_DIR / 'selection_diagnostics.jsonl')}


def load_recomputed_sets():
    """(seed,variant,day) -> {arm: frozenset of canonical edge tuples}."""
    out = {}
    for r in read_jsonl(MO_DIR / 'recomputed_sets.jsonl'):
        out[(r['seed'], r['variant'], r['day'])] = {
            a: frozenset(tuple(e) for e in r[a])
            for a in ('GREEDY', 'F1-SCORE', 'F2-SOFT', 'F3-OBSERV',
                      'F5-ORACLE')}
    return out


def load_channel_states(cache_path=None):
    """(seed,variant,day,ua,ub) -> {'relationship_goal', 'conversations'} state.

    Uses the FROZEN s3_signal soft-state definitions (never reimplemented).
    Results are cached to `cache_path` so later scripts skip the pair_state
    reload; the cache is a derived copy of the frozen definitions.
    """
    if cache_path and Path(cache_path).exists():
        out = {}
        for r in read_jsonl(cache_path):
            k = (r['seed'], r['variant'], r['day'], r['user_a'], r['user_b'])
            out[k] = r['channels']
        return out
    side = s3.load_state_side()
    out = {}
    for r in read_jsonl(CEIL_DIR / 'counterfactual_pairs.jsonl'):
        feat = s3.derived_features_from_row(r, side)
        k = (r['seed'], r['variant'], r['day'], r['user_a'], r['user_b'])
        out[k] = {ch: next(st for st in s3.SOFT_STATES
                           if feat.get('sc_%s_%s' % (ch, st), 0.0))
                  for ch in ('relationship_goal', 'conversations')}
    if cache_path:
        rows = [dict(seed=k[0], variant=k[1], day=k[2], user_a=k[3],
                     user_b=k[4], channels=v) for k, v in out.items()]
        write_jsonl(cache_path, rows)
    return out


# ---------------------------------------------------------------------------
# Fixed scoring rules (analysis_plan.md sec.3). Deterministic, never tuned.
# ---------------------------------------------------------------------------

def goal_category_score(state):
    """+1 match, -0.5 observed mismatch, 0 unknown/declined (frozen rule)."""
    if state == 'match':
        return 1.0
    if state == 'mismatch':
        return -0.5
    return 0.0


def weight_g1f(neg_scores):
    """Bit-exact frozen F1-SCORE weight (fc_selectors.py:123,
    mo_validate.py:172). day_edges stores POSITIVE counts
    (s1_opportunities.py:54), so this weight MINIMIZES total match
    count - the Amendment 1 discrepancy."""
    return [-float(x) for x in neg_scores]


def weight_g1m(neg_scores):
    """Spec-faithful baseline (Amendment 1): MAXIMIZE the total number
    of matching observed soft fields."""
    return [float(x) for x in neg_scores]


def weight_g2(channels):
    return [goal_category_score(c['relationship_goal']) for c in channels]


def weight_g3(channels):
    # 0.7 / 0.2 are the published NON-SHIFT simulator weights; structure-
    # informed, applied uniformly to every variant (never adapted).
    return [0.7 * goal_category_score(c['relationship_goal'])
            + 0.2 * goal_category_score(c['conversations']) for c in channels]


def solve_arm(edges, weights, k, arm, key, failures):
    """Exact-k solve + check_matching. Returns list of canonical edge tuples."""
    if k == 0:
        return []
    sel_i, obj, nodes, failed = solve_exact_k(edges, weights, k)
    if failed or sel_i is None:
        failures.append('%s %s (failed=%s sel=%s)' % (arm, key, failed, sel_i))
        return None
    ok, why = check_matching(edges, sel_i, k)
    if not ok:
        failures.append('%s %s: %s' % (arm, key, why))
        return None
    return [tuple(edges[i]) for i in sel_i]


# ---------------------------------------------------------------------------
# Seed-group inference (B=2000, rng 4242). Per-seed values -> paired CI.
# ---------------------------------------------------------------------------

def boot_mean(values, b=B, seed=SEED):
    """95% percentile CI of the mean of per-seed values (whole-group resample)."""
    arr = np.array(values, dtype=float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(arr), size=(b, len(arr)))
    bs = arr[idx].mean(axis=1)
    return [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]


def pos_tie_neg(values):
    return dict(positive=sum(1 for v in values if v > 0),
                tied=sum(1 for v in values if v == 0),
                negative=sum(1 for v in values if v < 0))


def seed_boot_rate(y, seeds, b=B, seed=SEED):
    """95% CI of a pooled (edge-weighted) rate, resampling whole seed groups."""
    uniq = sorted(set(seeds))
    by = defaultdict(list)
    for v, s in zip(y, seeds):
        by[s].append(float(v))
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(b):
        pick = rng.choice(len(uniq), size=len(uniq), replace=True)
        vals = []
        for i in pick:
            vals.extend(by[uniq[i]])
        out.append(float(np.mean(vals)))
    if not out:
        return [float('nan'), float('nan')]
    return [float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))]
