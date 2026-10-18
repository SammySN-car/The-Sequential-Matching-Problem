"""Offline ranking diagnostics for the FROZEN stagewise model (Task 9; plan S.9).

Pure offline diagnostic - scores with the frozen artifact only; NO tuning, NO
refitting, NO policy runs, NO final-evaluation seeds (70001-70100 are never
touched). Inputs (read-only):
  results/model_artifact.json (+ .sha256)  - frozen model, sha-verified
  data/feasible_edges_val.jsonl            - all feasible edges, val groups
  data/feasible_edges_val/seed_*.jsonl     - per-seed shards (line-count check)
  data/snapshots/seed_<g>.jsonl            - introduced rows, fit 40002-40400
                                             (fit box) + val 40401-40500
  data/labels/seed_<g>.jsonl               - stage/msmi labels, val groups
  data/states.jsonl                        - per-state introduced lists
                                             (integrity cross-check only)

Output: results/offline_ranking.json (+ run_log.txt append).

Scoring math mirrors scripts/sr_train.py predict_stage exactly:
  p = sigmoid(bias + sum_i w_i * (x_i - mu_i) / sigma_i), sigma_i == 0 -> 1.0,
  eta >= 709 -> 1.0, eta <= -709 -> 0.0; P_hat = p1 * p2 * p3.

IMPORTANT (stated in the JSON 'caveats' field): outcomes exist only for
INTRODUCED pairs; every ranking statistic here is over observed populations.
Counterfactual outcomes of never-introduced feasible pairs are never computed,
imputed or assumed. Nothing in this file speaks to realized sequential MSMIs
or to any policy decision quality.
"""
import argparse
import datetime
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
EXP_ROOT = SCRIPT_DIR.parent
DEFAULT_DATA_DIR = EXP_ROOT / 'data'
DEFAULT_RESULTS_DIR = EXP_ROOT / 'results'

STAGES = ('s1', 's2', 's3')
N_FEATURES = 17
SPREAD_THRESHOLDS = (0.01, 0.02, 0.05)
ROUND_DECIMALS = 9          # exact-vector match grid: 1e-9
PERCENTILES = (1.0, 5.0, 25.0, 50.0, 75.0, 95.0, 99.0)

CAVEATS = [
    'SELECTION BIAS: realized outcomes (s1/s2/s3/msmi) exist ONLY for pairs '
    'the greedy collection policy actually introduced. Every outcome-based '
    'ranking statistic in this file conditions on that introduced subset, '
    'which was chosen by greedy priorities - not at random with respect to '
    'the features the model scores on.',
    'NO COUNTERFACTUAL LABELS: for feasible pairs that were never introduced '
    'in a validation state, no outcome is computed, imputed or assumed '
    'anywhere in this file. "P_hat spread within a state" is a score '
    'statement only; it says nothing about whether the high-scored edge '
    'would have outperformed the low-scored edge.',
    'OBSERVED POPULATIONS ONLY: sections 1-3 are distributions over the '
    'collected validation states (feasible-edge sets produced by the '
    'greedy rollout dynamics of the collection policy); they are not a '
    'sample from any other environment or policy distribution.',
    'PREDICTION-VS-DECISION SEPARATION: this file evaluates the frozen '
    'model as a RANKER on observed outcomes only. It says nothing about '
    'realized sequential MSMIs, about deployability of the exact-k solver, '
    'or about the value of any policy that would rank/sort by P_hat. The '
    'pre-registered final policy evaluation remains stopped per the '
    'solver deployability failure; this diagnostic cannot change that.',
    'The within-state ranking statistic pools pairs across states '
    '(micro) and also reports an unweighted per-state mean (macro); '
    'states contribute comparably only if they have >= 2 introduced pairs '
    'with decided outcomes, so small-k states are underrepresented.',
]


# ---------------------------------------------------------------- scoring ---

def _sigmoid_eta(eta):
    """Vectorised sr_train.predict_stage tail: >=709 -> 1.0, <=-709 -> 0.0."""
    return np.where(eta >= 709.0, 1.0,
                    np.where(eta <= -709.0, 0.0,
                             1.0 / (1.0 + np.exp(-np.clip(eta, -709.0, 709.0)))))


def score_stage(stage, X):
    """p per row, mirroring sr_train.predict_stage (sigma==0 -> 1.0)."""
    w = np.asarray(stage['w'], dtype=np.float64)
    mu = np.asarray(stage['mu'], dtype=np.float64)
    sigma = np.asarray(stage['sigma'], dtype=np.float64)
    sigma = np.where(sigma == 0.0, 1.0, sigma)
    eta = float(stage['bias']) + ((X - mu) / sigma) @ w
    return _sigmoid_eta(eta)


def score_all(artifact, X):
    per_stage = {st: score_stage(artifact['stages'][st], X) for st in STAGES}
    p_hat = per_stage['s1'] * per_stage['s2'] * per_stage['s3']
    return p_hat, per_stage


# ------------------------------------------------------------------ input ---

def _read_jsonl(path):
    with open(path, 'r', encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def _is01(v):
    return type(v) is int and v in (0, 1)


def _dist(arr):
    """Percentile summary (documented: numpy linear interpolation)."""
    a = np.asarray(arr, dtype=np.float64)
    out = {'n': int(a.size), 'min': float(a.min()), 'mean': float(a.mean())}
    for q in PERCENTILES:
        out['p%g' % q] = float(np.percentile(a, q))
    out['max'] = float(a.max())
    return out


def _utc_now_iso():
    return datetime.datetime.now(datetime.timezone.utc).replace(
        microsecond=0).isoformat().replace('+00:00', 'Z')


def _sha256_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


# -------------------------------------------------------------------- main --

def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Offline ranking diagnostics for the frozen stagewise '
                    'model (Task 9, plan S.9). Scores only - never fits.')
    parser.add_argument('--data-dir', default=str(DEFAULT_DATA_DIR))
    parser.add_argument('--results-dir', default=str(DEFAULT_RESULTS_DIR))
    args = parser.parse_args(argv)
    data_dir = Path(args.data_dir)
    results_dir = Path(args.results_dir)
    started = time.time()
    problems = []
    integrity = {'checks': {}, 'problems': problems}

    def check(name, ok, detail):
        integrity['checks'][name] = {'ok': bool(ok), 'detail': detail}
        if not ok:
            problems.append('%s: %s' % (name, detail))
        print('[%s] %s: %s' % ('OK' if ok else 'PROBLEM', name, detail),
              flush=True)

    # --- frozen artifact (read-only, sha-verified) ---------------------------
    artifact_path = results_dir / 'model_artifact.json'
    sha_path = results_dir / 'model_artifact.sha256'
    if not artifact_path.exists() or not sha_path.exists():
        check('artifact_present', False, 'model_artifact.json/.sha256 missing')
        return _finish(None, integrity, results_dir, started)
    digest = _sha256_file(artifact_path)
    expected = sha_path.read_text(encoding='utf-8').split()[0]
    check('artifact_sha256', digest == expected,
          'sha256=%s expected=%s' % (digest, expected))
    artifact = json.loads(artifact_path.read_text(encoding='utf-8'))
    features = artifact['features']
    check('artifact_features_17', len(features) == N_FEATURES,
          'n=%d names=%s' % (len(features), ','.join(features)))
    stages_status = {st: artifact['stages'][st].get('status', 'OK')
                     for st in STAGES}
    check('artifact_stages_frozen', all(v == 'OK' for v in stages_status.values()),
          'statuses=%s' % json.dumps(stages_status, sort_keys=True))

    fit_lo, fit_hi = artifact['split']['fit_range']
    val_lo, val_hi = artifact['split']['val_range']
    val_seeds = set(range(val_lo, val_hi + 1))
    fit_seeds = set(range(fit_lo, fit_hi + 1))
    check('split_disjoint', not (fit_seeds & val_seeds),
          'fit %d-%d val %d-%d' % (fit_lo, fit_hi, val_lo, val_hi))

    # --- feasible val edges (merged) ----------------------------------------
    edge_path = data_dir / 'feasible_edges_val.jsonl'
    if not edge_path.exists():
        check('feasible_edges_present', False, 'missing %s' % edge_path)
        return _finish(artifact, integrity, results_dir, started)
    edge_feats, edge_keys, n_rows, bad_feat, bad_group = [], [], 0, 0, 0
    with open(edge_path, 'r', encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            n_rows += 1
            if len(r['features']) != N_FEATURES:
                bad_feat += 1
                continue
            if int(r['seed_group']) not in val_seeds:
                bad_group += 1
            edge_feats.append(r['features'])
            edge_keys.append((int(r['seed_group']), r['variant'], int(r['day'])))
    X_edges = np.asarray(edge_feats, dtype=np.float64)
    check('merged_rows_wellformed', bad_feat == 0 and bad_group == 0,
          'rows=%d bad_feature_count=%d outside_val_range=%d'
          % (n_rows, bad_feat, bad_group))

    # --- shard line counts (merged must equal sum) --------------------------
    shard_dir = data_dir / 'feasible_edges_val'
    shard_total, shard_seeds = 0, set()
    for path in sorted(shard_dir.glob('seed_*.jsonl')):
        try:
            g = int(path.stem.split('_', 1)[1])
        except ValueError:
            continue
        shard_seeds.add(g)
        with open(path, 'r', encoding='utf-8') as fh:
            shard_total += sum(1 for ln in fh if ln.strip())
    check('shard_seed_coverage', shard_seeds == val_seeds,
          'shard groups=%d range=%s expected val %d-%d'
          % (len(shard_seeds),
             ('%d-%d' % (min(shard_seeds), max(shard_seeds))) if shard_seeds
             else 'none', val_lo, val_hi))
    check('merged_equals_shard_sum', n_rows == shard_total,
          'merged=%d shard_sum=%d' % (n_rows, shard_total))

    # --- score all feasible val edges ---------------------------------------
    p_hat_edges, p_stage_edges = score_all(artifact, X_edges)
    n_edges = X_edges.shape[0]

    score_distributions = {
        'definition': 'P_hat and per-stage p over ALL feasible edges in '
                      'validation groups %d-%d (data/feasible_edges_val.jsonl); '
                      'percentiles by numpy linear interpolation.'
                      % (val_lo, val_hi),
        'n_edges_total': n_edges,
        'p_hat': _dist(p_hat_edges),
        'per_stage': {st: _dist(p_stage_edges[st]) for st in STAGES},
    }

    # --- discrimination frequency (per-state max-min spread) ----------------
    state_ids, inv = np.unique(
        np.array([('%09d|%s|%09d' % k) for k in edge_keys]), return_inverse=True)
    n_states = int(state_ids.size)
    spread = np.full(n_states, np.nan)
    order = np.argsort(inv, kind='mergesort')
    inv_s = inv[order]
    starts = np.flatnonzero(np.r_[True, inv_s[1:] != inv_s[:-1]])
    ends = np.r_[starts[1:], inv_s.size]
    for s, e in zip(starts, ends):
        block = p_hat_edges[order[s:e]]
        spread[inv_s[s]] = block.max() - block.min()
    finite = spread[np.isfinite(spread)]
    discrimination = {
        'definition': 'Per validation state (seed_group, variant, day) with '
                      '>=1 feasible edge: spread = max(P_hat) - min(P_hat) '
                      'over its feasible edges. "share_ge_x" = fraction of '
                      'states whose spread >= x.',
        'n_states': n_states,
        'n_edges_total': n_edges,
        'spread': _dist(finite),
        'share_ge_0.01': float((finite >= 0.01).mean()),
        'share_ge_0.02': float((finite >= 0.02).mean()),
        'share_ge_0.05': float((finite >= 0.05).mean()),
        'threshold_note': '0.02 is the plan threshold; 0.01 and 0.05 are '
                          'context only.',
    }

    # --- fit-split box from introduced fit rows (snapshots 40002-40400) ------
    fit_vecs, fit_rows_n = [], 0
    for g in sorted(fit_seeds):
        path = data_dir / 'snapshots' / ('seed_%d.jsonl' % g)
        if not path.exists():
            continue
        for r in _read_jsonl(path):
            if len(r['features']) != N_FEATURES:
                continue
            fit_vecs.append(r['features'])
            fit_rows_n += 1
    X_fit_intro = np.asarray(fit_vecs, dtype=np.float64)
    box_min = X_fit_intro.min(axis=0)
    box_max = X_fit_intro.max(axis=0)
    check('fit_snapshots_present', fit_rows_n > 0,
          'fit introduced rows=%d (seeds %d-%d)' % (fit_rows_n, fit_lo, fit_hi))

    outside = (X_edges < box_min) | (X_edges > box_max)
    fit_set = set(tuple(v) for v in np.round(X_fit_intro, ROUND_DECIMALS))
    rounded_edges = np.round(X_edges, ROUND_DECIMALS)
    in_fit_set = np.fromiter(
        (tuple(v) in fit_set for v in rounded_edges),
        dtype=np.float64, count=n_edges)
    feature_support = {
        'fit_box_definition': 'Per-feature min/max over INTRODUCED fit-split '
                              'rows (snapshots, seed groups %d-%d, n=%d). An '
                              'edge is outside a feature\'s box iff its value '
                              'is < min or > max (exact float comparison).'
                              % (fit_lo, fit_hi, fit_rows_n),
        'exact_vector_definition': 'A val feasible edge is "represented" iff '
                                   'its 17-vector rounded to %d decimals '
                                   '(1e-%d grid) exactly equals the rounded '
                                   '17-vector of SOME introduced fit row. '
                                   'Distinct from the box test: box '
                                   'membership only needs per-feature bounds, '
                                   'exact-vector membership needs the whole '
                                   'joint vector to have been observed '
                                   'during fitting.'
                                   % (ROUND_DECIMALS, ROUND_DECIMALS),
        'per_feature_outside_box_share': {
            name: float(outside[:, i].mean())
            for i, name in enumerate(features)},
        'all_features_outside_box_share': float(outside.any(axis=1).mean()),
        'n_edges_total': n_edges,
        'n_edges_outside_box_all_features': int(outside.any(axis=1).sum()),
        'exact_vector_in_fit_introduced': {
            'share': float(in_fit_set.mean()),
            'n_edges': int(in_fit_set.sum()),
            'n_fit_unique_rounded_vectors': len(fit_set),
            'n_fit_rows': fit_rows_n},
    }

    # --- val introduced rows + labels (join on (variant, intro_id)) ---------
    val_intro = {}          # (variant, intro_id) -> row dict
    intro_by_state = {}     # (seed_group, variant, day) -> [row dict, ...]
    missing_snap = []
    for g in sorted(val_seeds):
        path = data_dir / 'snapshots' / ('seed_%d.jsonl' % g)
        if not path.exists():
            missing_snap.append(g)
            continue
        for r in _read_jsonl(path):
            r['seed_group'] = g
            val_intro[(r['variant'], r['intro_id'])] = r
            intro_by_state.setdefault(
                (g, r['variant'], int(r['day'])), []).append(r)
    check('val_snapshots_present', not missing_snap,
          'val introduced rows=%d missing_groups=%s'
          % (len(val_intro), missing_snap or 'none'))

    labels = {}
    missing_lab = []
    for g in sorted(val_seeds):
        path = data_dir / 'labels' / ('seed_%d.jsonl' % g)
        if not path.exists():
            missing_lab.append(g)
            continue
        for lab in _read_jsonl(path):
            labels[(lab['variant'], lab['intro_id'])] = lab
    check('val_labels_present', not missing_lab,
          'val labels=%d missing_groups=%s' % (len(labels), missing_lab or 'none'))
    unmatched = [k for k in val_intro if k not in labels]
    check('label_join_complete', not unmatched,
          'introduced rows without label=%d (sample %s)'
          % (len(unmatched), unmatched[:3]))

    # --- integrity cross-check: states.jsonl introduced vs snapshots -------
    states_intro = {}
    if (data_dir / 'states.jsonl').exists():
        for r in _read_jsonl(data_dir / 'states.jsonl'):
            if int(r['seed_group']) not in val_seeds:
                continue
            key = (int(r['seed_group']), r['variant'], int(r['day']))
            states_intro[key] = sorted(
                tuple(sorted(m)) for m in r.get('introduced', []))
    intro_mismatch = 0
    for key, rows in intro_by_state.items():
        a = sorted(tuple(sorted(r['members'])) for r in rows)
        if states_intro.get(key) != a:
            intro_mismatch += 1
    extra_state_keys = set(states_intro) - set(intro_by_state)
    check('states_vs_snapshots_introduced', intro_mismatch == 0,
          'val states=%d introduced-set mismatches=%d extra_states_no_intro=%d'
          % (len(states_intro), intro_mismatch, len(extra_state_keys)))

    # --- within-state ranking on observed outcomes --------------------------
    # Statistic (documented): for each val state with >=2 introduced pairs
    # whose outcome y is decided (in {0,1}), every unordered pair of introduced
    # pairs with y_i != y_j is COMPARABLE. It scores 1.0 if sign(score_i -
    # score_j) == sign(y_i - y_j), 0.5 if score_i == score_j (prediction tie),
    # else 0. micro = total score / total comparable pairs (pairs pooled over
    # states); macro = unweighted mean of per-state micro. A Spearman-style
    # rank correlation is NOT used because outcome ties (common for binary
    # msmi with k up to ~20) make per-state rho degenerate.
    def compute_ranking(score_key, outcome_desc):
        per_state = []
        n_comp_total = 0
        n_rows_total = 0
        n_states_ge2 = 0
        n_states_used = 0
        conc_total = 0.0
        for _key, rows in sorted(intro_by_state.items()):
            if len(rows) < 2:
                continue
            n_states_ge2 += 1
            scored = []
            for r in rows:
                lab = labels.get((r['variant'], r['intro_id']))
                if lab is None or len(r['features']) != N_FEATURES:
                    continue
                stage = 'msmi' if score_key == 'p_hat' else score_key
                y = lab[stage]
                if not _is01(y):
                    continue
                Xr = np.asarray([r['features']], dtype=np.float64)
                if score_key == 'p_hat':
                    s = float(score_all(artifact, Xr)[0][0])
                else:
                    s = float(score_stage(artifact['stages'][score_key], Xr)[0])
                scored.append((s, int(y)))
            if len(scored) < 2:
                continue
            n_states_used += 1
            n_rows_total += len(scored)
            conc = 0.0
            n_comp = 0
            for i in range(len(scored)):
                for j in range(i + 1, len(scored)):
                    si, yi = scored[i]
                    sj, yj = scored[j]
                    if yi == yj:
                        continue
                    n_comp += 1
                    if si == sj:
                        conc += 0.5
                    elif (si - sj) * (yi - yj) > 0:
                        conc += 1.0
            n_comp_total += n_comp
            conc_total += conc
            if n_comp:
                per_state.append(conc / n_comp)
        block = {
            'outcome': outcome_desc,
            'n_states_ge_2_introduced': n_states_ge2,
            'n_states_with_decided_outcomes_ge_2': n_states_used,
            'n_introduced_rows_used': n_rows_total,
            'n_comparable_pairs': n_comp_total,
            'micro_concordant_share': (
                None if n_comp_total == 0 else conc_total / n_comp_total),
            'macro_mean_per_state_concordance': (
                None if not per_state else float(np.mean(per_state))),
            'per_state_concordance': (
                None if not per_state else _dist(per_state)),
        }
        print('rank %s: states_ge2=%d used=%d pairs=%d micro=%s macro=%s'
              % (score_key, n_states_ge2, n_states_used, n_comp_total,
                 ('%.4f' % block['micro_concordant_share'])
                 if block['micro_concordant_share'] is not None else 'n/a',
                 ('%.4f' % block['macro_mean_per_state_concordance'])
                 if block['macro_mean_per_state_concordance'] is not None
                 else 'n/a'), flush=True)
        return block

    within_state = {
        'statistic_definition': (
            'PAIRWISE CONCORDANCE (not Spearman rho; binary outcome ties make '
            'per-state rho degenerate). For each val state with >= 2 '
            'introduced pairs whose outcome y is decided (in {0,1}), every '
            'unordered pair of introduced pairs with y_i != y_j is '
            'COMPARABLE (outcome ties excluded). Each comparable pair scores '
            '1.0 if sign(score_i - score_j) == sign(y_i - y_j) (concordant), '
            '0.5 if score_i == score_j (prediction tie), else 0.0 '
            '(discordant). micro_concordant_share = total score / total '
            'comparable pairs, pooled over all states. '
            'macro_mean_per_state_concordance = unweighted mean over states '
            'of the per-state score share; states with zero comparable '
            'pairs (all outcomes tied) are excluded from the macro mean and '
            'from n_comparable_pairs.'),
        'primary_msmi': compute_ranking(
            'p_hat', 'realized msmi (0/1) on introduced pairs; score = '
                     'P_hat = p1*p2*p3'),
        'secondary_stage_chain': {
            's1': compute_ranking('s1', 'realized s1; score = p1'),
            's2': compute_ranking('s2', 'realized s2 (in-population only); '
                                        'score = p2'),
            's3': compute_ranking('s3', 'realized s3 (in-population only); '
                                        'score = p3'),
        },
        'selection_bias_statement': (
            'Outcomes exist ONLY for introduced pairs; these statistics are '
            'NOT top-k accuracy over all feasible pairs, and counterfactual '
            'outcomes of never-introduced pairs are never computed or '
            'imputed. See caveats.'),
    }

    # --- train-vs-val distribution drift (val-introduced rows) --------------
    val_vecs = [r['features'] for r in val_intro.values()
                if len(r['features']) == N_FEATURES]
    X_val_intro = np.asarray(val_vecs, dtype=np.float64)
    drift_per_feature = {}
    for i, name in enumerate(features):
        fm, fsd = float(X_fit_intro[:, i].mean()), float(X_fit_intro[:, i].std())
        vm, vsd = float(X_val_intro[:, i].mean()), float(X_val_intro[:, i].std())
        drift_per_feature[name] = {
            'fit_mean': fm, 'fit_std': fsd,
            'val_mean': vm, 'val_std': vsd,
            'mean_drift_in_fit_sd': ((vm - fm) / fsd) if fsd else 0.0,
            'std_ratio_val_over_fit': (vsd / fsd) if fsd else None,
            'share_val_outside_fit_box': float(
                ((X_val_intro[:, i] < box_min[i])
                 | (X_val_intro[:, i] > box_max[i])).mean()),
        }
    drift = {
        'definition': 'INTRODUCED rows only: fit = snapshots seed groups '
                      '%d-%d (n=%d), val = snapshots seed groups %d-%d '
                      '(n=%d). mean_drift_in_fit_sd = (val_mean - fit_mean) '
                      '/ fit_std. share_val_outside_fit_box is per feature.'
                      % (fit_lo, fit_hi, X_fit_intro.shape[0],
                         val_lo, val_hi, X_val_intro.shape[0]),
        'per_feature': drift_per_feature,
        'val_rows_any_feature_outside_box_share': float(
            ((X_val_intro < box_min) | (X_val_intro > box_max))
            .any(axis=1).mean()),
    }

    # --- pointer to Task 6 predictive metrics (cited, NOT recomputed) --------
    tm_path = results_dir / 'train_metrics.json'
    tm_sha = _sha256_file(tm_path) if tm_path.exists() else None
    predictive_metrics_source = {
        'note': 'Per-stage and combined predictive metrics (PR-AUC, ROC-AUC, '
                'log loss, calibration, prevalence, constant baseline) are '
                'NOT recomputed in this file; they are produced by Task 6 '
                '(scripts/sr_train.py) and cited here from the frozen '
                'results/train_metrics.json. This Task 9 file covers the '
                'RANKING diagnostics only.',
        'file': 'results/train_metrics.json',
        'sha256': tm_sha,
        'present': tm_sha is not None,
    }

    doc = {
        'schema': 1,
        'task': 'Task 9 offline ranking diagnostics (plan S.9) - scoring '
                'only, frozen artifact, validation groups %d-%d, no policy '
                'runs, no final-eval seeds.' % (val_lo, val_hi),
        'created': _utc_now_iso(),
        'artifact_sha256': digest,
        'artifact_plan_sha256': artifact.get('plan_sha256'),
        'predictive_metrics_source': predictive_metrics_source,
        'split': artifact['split'],
        'feature_order': features,
        'integrity': integrity,
        'score_distributions': score_distributions,
        'discrimination_frequency': discrimination,
        'feature_support_ood': feature_support,
        'within_state_ranking': within_state,
        'distribution_drift': drift,
        'caveats': CAVEATS,
    }

    out_path = results_dir / 'offline_ranking.json'
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(json.dumps(doc, indent=2, sort_keys=True, allow_nan=False)
                 + '\n')
    elapsed = time.time() - started
    log_line = (
        '%s python scripts/sr_offline_rank.py -> EXIT %d (val groups %d-%d; '
        'edges=%d states=%d spread_ge_0.02=%.3f; outside_box=%.4f '
        'exact_vec=%.4f; within-state msmi micro=%s macro=%s over %s pairs) '
        '[CORRECTED: concordance sign inverted in prior run - '
        '(si-sj)*(yj-yi) fixed to (si-sj)*(yi-yj); predictive_metrics_source '
        'pointer added] -> results/offline_ranking.json'
        % (datetime.date.today().isoformat(), 1 if problems else 0,
           val_lo, val_hi, n_edges, n_states,
           discrimination['share_ge_0.02'],
           feature_support['all_features_outside_box_share'],
           feature_support['exact_vector_in_fit_introduced']['share'],
           ('%.4f' % within_state['primary_msmi']['micro_concordant_share'])
           if within_state['primary_msmi']['micro_concordant_share']
           is not None else 'n/a',
           ('%.4f' % within_state['primary_msmi']
            ['macro_mean_per_state_concordance'])
           if within_state['primary_msmi']['macro_mean_per_state_concordance']
           is not None else 'n/a',
           within_state['primary_msmi']['n_comparable_pairs']))
    with open(EXP_ROOT / 'run_log.txt', 'a', encoding='utf-8',
              newline='\n') as fh:
        fh.write(log_line + '\n')
    print(log_line, flush=True)
    print('wrote %s in %.1fs' % (out_path, elapsed), flush=True)
    if problems:
        print('INTEGRITY PROBLEMS: %d -> exiting non-zero' % len(problems),
              file=sys.stderr)
        return 1
    return 0


def _finish(artifact, integrity, results_dir, started):
    doc = {
        'schema': 1,
        'task': 'Task 9 offline ranking diagnostics (plan S.9)',
        'created': _utc_now_iso(),
        'integrity': integrity,
        'caveats': CAVEATS,
    }
    out_path = results_dir / 'offline_ranking.json'
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(json.dumps(doc, indent=2, sort_keys=True, allow_nan=False)
                 + '\n')
    with open(EXP_ROOT / 'run_log.txt', 'a', encoding='utf-8',
              newline='\n') as fh:
        fh.write('%s python scripts/sr_offline_rank.py -> EXIT 1 (input '
                 'missing: %s) -> results/offline_ranking.json\n'
                 % (datetime.date.today().isoformat(),
                    '; '.join(integrity['problems'])))
    return 1


if __name__ == '__main__':
    sys.exit(main())
