"""Shared helpers for the Stagewise Counterfactual Signal Audit.

Read-only over every prior artifact (round2_eda, round2_decision_ceiling,
round2_fixed_cardinality, round2_missed_oracle). All outputs land under
research/round2_stagewise_signal/. Reuses the validated ceiling replay and
feature extraction rather than reimplementing them.
"""
import csv, json, sys, time
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent                 # .../round2_stagewise_signal/scripts
OUT = HERE.parent                                      # .../round2_stagewise_signal
ROOT = HERE.parent.parent.parent                       # repository root
CEIL_DIR = ROOT / 'research' / 'round2_decision_ceiling'
FC_DIR = ROOT / 'research' / 'round2_fixed_cardinality'
MO_DIR = ROOT / 'research' / 'round2_missed_oracle'
sys.path.insert(0, str(CEIL_DIR / 'scripts'))
sys.path.insert(0, str(FC_DIR / 'scripts'))

import ce_common as c          # noqa: E402
import s3_signal as s3         # noqa: E402

B, SEED = 2000, 4242           # seed-group bootstrap, frozen in analysis_plan.md
STAGES = ['both_responded', 'mutual', 'date', 'date_within_deadline',
          'timely_second', 'final_msmi']
SOFT = s3.SOFT_CHANNELS        # 7 frozen soft channels
SOFT_STATES = s3.SOFT_STATES   # match / mismatch / unknown / declined
FEATURE_SETS = {
    'A_baseline_count': s3.FEATURE_SETS['F1_baseline_count_score'],
    'B_soft_state': s3.FEATURE_SETS['F2_soft_state'],
    'C_full_legal': s3.FEATURE_SETS['F4_full_legal_observables'],
}


def log(msg):
    line = '[%s] %s' % (time.strftime('%Y-%m-%dT%H:%M:%S'), msg)
    print(line, flush=True)
    with open(OUT / 'run_log.txt', 'a', encoding='utf-8') as fh:
        fh.write(line + '\n')


def write_jsonl(path, rows):
    with open(path, 'w', encoding='utf-8') as fh:
        for r in rows:
            fh.write(json.dumps(r, sort_keys=True) + '\n')
    log('wrote %s (%d rows)' % (Path(path).name, len(rows)))


def read_jsonl(path):
    with open(path, encoding='utf-8') as fh:
        return [json.loads(l) for l in fh if l.strip()]


def read_csv_dict(path):
    with open(path, encoding='utf-8') as fh:
        return [dict(r) for r in csv.DictReader(fh)]


# ---------------------------------------------------------------------------
# Stage extraction from the simulator's actual event records.
# Mirrors kit.Simulator.advance() event semantics and the official
# metrics() definition of MSMI (kit.py L190-203); see analysis_plan.md sec.2.
# ---------------------------------------------------------------------------

def stages_from_events(mid, events, assigned_day):
    """Full outcome funnel for one introduction, from real event records."""
    es = [e for e in events if e['introduction_id'] == mid]
    rs = [e for e in es if e['event'] == 'introduction_response']
    n_resp = len(rs)
    n_no_response = sum(1 for e in rs if e['value'] is None)
    n_explicit_no = sum(1 for e in rs if e['value'] == 'no')
    n_yes_intro = sum(1 for e in rs if e['value'] == 'yes')
    both_responded = int(n_resp == 2 and n_no_response == 0)
    mutual = int(n_resp == 2 and all(e['value'] == 'yes' for e in rs))

    ds = [e for e in es if e['event'] == 'date_happened' and e['value'] is True]
    any_dh = [e for e in es if e['event'] == 'date_happened']
    date = int(bool(ds))
    date_day = ds[0]['occurred_day'] if ds else None
    date_within_deadline = int(bool(ds) and date_day - assigned_day <= 30)

    ss = [e for e in es if e['event'] == 'second_meeting_intention']
    n_second_yes = sum(1 for e in ss if e['value'] == 'yes')
    n_second_no = sum(1 for e in ss if e['value'] == 'no')
    n_second_missing = sum(1 for e in ss if e['value'] is None)
    n_second_late = (sum(1 for e in ss if e['value'] == 'yes'
                         and date_day is not None
                         and e['occurred_day'] - date_day > 3) if ss else 0)
    timely_second = int(bool(ds) and len(ss) == 2 and all(
        e['value'] == 'yes' and e['occurred_day'] - date_day <= 3 for e in ss))
    final_msmi = int(timely_second and date_within_deadline)

    return dict(
        both_responded=both_responded, mutual=mutual, date=date,
        date_within_deadline=date_within_deadline,
        timely_second=timely_second, final_msmi=final_msmi,
        n_intro_no_response=n_no_response, n_intro_explicit_no=n_explicit_no,
        n_intro_yes=n_yes_intro,
        date_happened_flag=(True if ds else (False if any_dh else None)),
        date_delay_days=(date_day - assigned_day if ds else None),
        n_second_yes=n_second_yes, n_second_no=n_second_no,
        n_second_missing=n_second_missing, n_second_late=n_second_late)


# ---------------------------------------------------------------------------
# Loaders for frozen side data.
# ---------------------------------------------------------------------------

def load_existing_oof():
    """(seed, variant, day, ua, ub) -> frozen OOF record (ceiling study)."""
    out = {}
    for r in read_jsonl(CEIL_DIR / 'oof_scores.jsonl'):
        out[(r['seed'], r['variant'], r['day'], r['user_a'], r['user_b'])] = r
    return out


def load_recomputed_sets():
    """(seed, variant, day) -> {arm: frozenset of canonical edge tuples}."""
    out = {}
    for r in read_jsonl(MO_DIR / 'recomputed_sets.jsonl'):
        out[(r['seed'], r['variant'], r['day'])] = {
            a: frozenset(tuple(sorted(e)) for e in r[a])
            for a in ('GREEDY', 'F1-SCORE', 'F2-SOFT', 'F3-OBSERV', 'F5-ORACLE')}
    return out


def load_headroom_states():
    """Set of (seed, variant, day) local-headroom states (82)."""
    out = set()
    for r in read_jsonl(MO_DIR / 'selection_diagnostics.jsonl'):
        if r['headroom']:
            out.add((r['seed'], r['variant'], r['day']))
    return out


def load_positive_ranks():
    return read_csv_dict(MO_DIR / 'positive_edge_ranks.csv')


# ---------------------------------------------------------------------------
# Seed-group inference (frozen: B=2000, rng 4242, whole seed groups).
# ---------------------------------------------------------------------------

def seed_boot_auc(scores, y, seeds, b=B, seed=SEED):
    """95% percentile CI for ROC-AUC resampling whole seed groups."""
    from sklearn.metrics import roc_auc_score
    uniq = sorted(set(seeds))
    by = defaultdict(list)
    for i, s in enumerate(seeds):
        by[s].append(i)
    rng = np.random.default_rng(seed)
    vals = []
    y = np.asarray(y); scores = np.asarray(scores)
    for _ in range(b):
        pick = rng.choice(len(uniq), size=len(uniq), replace=True)
        idx = np.concatenate([np.array(by[uniq[i]]) for i in pick])
        yy, ss = y[idx], scores[idx]
        if len(set(yy)) < 2:
            continue
        vals.append(float(roc_auc_score(yy, ss)))
    if not vals:
        return [float('nan'), float('nan')]
    return [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))]


def seed_boot_mean(values, seeds, b=B, seed=SEED):
    """95% percentile CI for a pooled per-seed mean (values aligned to rows)."""
    uniq = sorted(set(seeds))
    by = defaultdict(list)
    for v, s in zip(values, seeds):
        by[s].append(float(v))
    arr = np.array([np.mean(by[s]) for s in uniq], float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(arr), size=(b, len(arr)))
    bs = arr[idx].mean(axis=1)
    return [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]


def cluster_boot_diff(sa, sb, b=B, seed=SEED):
    """Two-sample seed-group cluster bootstrap of pooled-mean(sa)-pooled-mean(sb).

    sa/sb are lists of (seed, value). Resamples whole seed groups, then
    recomputes each stratum's pooled (edge-weighted) mean on the resampled
    seeds only. Same estimand as mo_tail.cluster_boot_diff.
    """
    uniq = sorted(set(s for s, _ in sa) | set(s for s, _ in sb))
    bya = {s: [v for t, v in sa if t == s] for s in uniq}
    byb = {s: [v for t, v in sb if t == s] for s in uniq}
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(b):
        pick = rng.choice(len(uniq), size=len(uniq), replace=True)
        xa, xb = [], []
        for i in pick:
            xa.extend(bya[uniq[i]]); xb.extend(byb[uniq[i]])
        if xa and xb:
            out.append(float(np.mean(xa)) - float(np.mean(xb)))
    if not out:
        return [float('nan'), float('nan')]
    return [float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))]


def day_band(d):
    return ('0-9' if d <= 9 else '10-19' if d <= 19
            else '20-39' if d <= 39 else '40-59')


def power_flag(y, seeds):
    n_pos = int(np.sum(y))
    n_seed_pos = len({s for s, yy in zip(seeds, y) if yy})
    return 'ok' if (n_pos >= 100 and n_seed_pos >= 5) else 'inconclusive'

# ---------------------------------------------------------------------------
# Central aligned frame (counterfactual_pairs.jsonl row order).
# ---------------------------------------------------------------------------

def build_frame(include_feat=False):
    """Aligned per-row scalars (+ optional full feature lists).

    Every array/list is in counterfactual_pairs.jsonl row order; stage labels
    come from the validated isolated-replay funnel (stage_funnel.jsonl).
    """
    fr = s3.load_frame()                                   # feat/y/groups/...
    cf_rows = read_jsonl(CEIL_DIR / 'counterfactual_pairs.jsonl')
    stage_rows = read_jsonl(OUT / 'stage_funnel.jsonl')
    keys = [(r['seed'], r['variant'], r['day'], r['user_a'], r['user_b'])
            for r in cf_rows]
    keys_st = [(r['seed'], r['variant'], r['day'], r['user_a'], r['user_b'])
               for r in stage_rows]
    assert keys == keys_st, 'stage_funnel order mismatch'
    assert len(fr['y']) == len(keys)

    oof = load_existing_oof()
    sets = load_recomputed_sets()
    hr = load_headroom_states()

    channel_states, goal, n_soft_obs, pair_score = [], [], [], []
    f2_sel, greedy_sel, headroom = [], [], []
    oof_f1, oof_f2, oof_f4, day_band_list = [], [], [], []
    for f, k in zip(fr['feat'], keys):
        cs = {}
        for ch in SOFT:
            for st in SOFT_STATES:
                if f.get('sc_%s_%s' % (ch, st), 0.0):
                    cs[ch] = st
        channel_states.append(cs)
        goal.append(cs.get('relationship_goal', 'unknown'))
        n_soft_obs.append(sum(1 for ch in SOFT
                              if cs.get(ch) in ('match', 'mismatch')))
        pair_score.append(f.get('pair_score', 0.0))
        state_key = (k[0], k[1], k[2])
        edge = (k[3], k[4])
        f2_sel.append(int(edge in sets[state_key]['F2-SOFT']))
        greedy_sel.append(int(edge in sets[state_key]['GREEDY']))
        headroom.append(int(state_key in hr))
        rec = oof[k]
        oof_f1.append(float(rec['F1_baseline_count_score']))
        oof_f2.append(float(rec['F2_soft_state']))
        oof_f4.append(float(rec['F4_full_legal_observables']))
        day_band_list.append(day_band(k[2]))

    stages = {st: np.array([r[st] for r in stage_rows], dtype=int)
              for st in STAGES}
    out = dict(
        keys=keys, seeds=list(fr['seeds']), variants=list(fr['variants']),
        days=list(fr['days']), day_band=day_band_list,
        states=list(fr['states']),
        selected=np.array(fr['selected'], dtype=int),
        greedy_selected=np.array(greedy_sel, dtype=int),
        f2_selected=np.array(f2_sel, dtype=int),
        headroom=np.array(headroom, dtype=int),
        pair_score=np.array(pair_score, dtype=float),
        n_soft_observed=np.array(n_soft_obs, dtype=int),
        goal=goal, channel_states=channel_states,
        stages=stages,
        oof_f1=np.array(oof_f1), oof_f2=np.array(oof_f2),
        oof_f4=np.array(oof_f4),
        event_detail=stage_rows)
    # greedy flag must match the recorded counterfactual selected flag
    assert (out['greedy_selected'] == out['selected']).all(), \
        'recomputed GREEDY set != counterfactual selected flag'
    if include_feat:
        out['feat'] = fr['feat']
        out['groups'] = fr['groups']
    return out

def seed_boot_rate(y, seeds, b=B, seed=SEED):
    """95% percentile CI for a POOLED (edge-weighted) rate, resampling seeds.

    Point estimate this interval targets is np.mean(y) (pooled). Resampling is
    over whole seed groups; within a resample the pooled rate is recomputed.
    """
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
