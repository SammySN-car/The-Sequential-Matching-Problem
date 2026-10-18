"""Validation experiment driver: parallel rollouts -> CSVs -> sections A-F report.

Usage (from repo root):
    python -m research.run_experiment --smoke
    python -m research.run_experiment --random-rollouts 400 --greedy-rollouts 40 --workers 12
Outputs research/out/{rows.csv, worlds.csv, report.txt}
"""
import argparse
import csv
import math
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(REPO_ROOT), str(REPO_ROOT / 'research')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import kit

import analyze
import features
import integrity
from collect import collect_rows

VARIANTS = ('development', 'sparse', 'cold_start', 'delayed', 'shift', 'drift')
META_COLUMNS = ('world_seed', 'variant', 'policy', 'collector_seed', 'day', 'a', 'b',
                'introduction_id', 'maturity_day', 'label', 'label_mutual', 'label_date')
FEATURE_COLUMN_PREFIX = 'feat_'
TARGETS = (('label', 'msmi'), ('label_mutual', 'mutual'), ('label_date', 'date'))
# Pre-registered engineering thresholds (not statistical claims about the real world).
AP_LIFT_STAGE = 1.3     # stage target: val average precision must beat prevalence by 30%
AP_LIFT_MSMI = 1.1      # MSMI target: minimum AP lift (base rate ~1%)
MSMI_AUC_MIN = 0.55     # MSMI target: minimum val ROC-AUC


def sort_rows(rows):
    """Canonical row order: report numbers must not depend on task completion order."""
    return sorted(rows, key=lambda r: (r.get('world_seed', 0), r.get('variant', ''),
                                       r.get('policy', ''), r.get('collector_seed', 0),
                                       r.get('day', 0), r.get('a', ''), r.get('b', '')))


def flatten_row(row):
    """Row dict -> flat CSV dict: meta/targets as-is, features as feat_* ('' for NaN)."""
    flat = {}
    for key in META_COLUMNS:
        value = row.get(key, '')
        if value is None:
            value = ''
        flat[key] = value
    for key, value in row['features'].items():
        if isinstance(value, float) and math.isnan(value):
            flat[FEATURE_COLUMN_PREFIX + key] = ''
        else:
            flat[FEATURE_COLUMN_PREFIX + key] = value
    return flat


def write_rows_csv(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(META_COLUMNS) + [FEATURE_COLUMN_PREFIX + k
                                       for k in features.FEATURE_KEYS]
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(flatten_row(row))


def write_worlds_csv(path, results):
    fieldnames = ('world_seed', 'variant', 'policy', 'collector_seed', 'days',
                  'follow_up', 'assignments', 'mutual', 'dates', 'msmi', 'ask_cost',
                  'opportunities_total', 'chosen_total', 'coverage_fraction',
                  'msmi_per_100_arrived_members', 'elapsed_seconds')
    with Path(path).open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for item in results:
            out, elapsed = item['out'], item['elapsed']
            metrics = out['metrics']
            writer.writerow({
                'world_seed': out['world_seed'], 'variant': out['variant'],
                'policy': out['policy'], 'collector_seed': out['collector_seed'],
                'days': out['per_day'][-1]['day'] + 1 if out['per_day'] else 0,
                'follow_up': out['horizon'] - (out['per_day'][-1]['day'] + 1
                                               if out['per_day'] else 0),
                'assignments': metrics['assignments'],
                'mutual': metrics['mutual_acceptances'], 'dates': metrics['dates'],
                'msmi': metrics['mutual_second_meeting_intention'],
                'ask_cost': metrics['ask_cost'],
                'opportunities_total': out['opportunities_total'],
                'chosen_total': out['chosen_total'],
                'coverage_fraction': round(out['coverage_fraction'], 6),
                'msmi_per_100_arrived_members': metrics['msmi_per_100_arrived_members'],
                'elapsed_seconds': round(elapsed, 3)})


def _run_spec(spec):
    """Worker: build the world, run one rollout, return its output."""
    world = kit.generate(spec['world_seed'], 200, 'research', spec['variant'])
    started = time.perf_counter()
    out = collect_rows(world, collector_seed=spec['collector_seed'],
                       days=spec['days'], follow_up=spec['follow_up'],
                       policy=spec['policy'])
    return {'out': out, 'elapsed': time.perf_counter() - started}


def build_specs(random_rollouts, greedy_rollouts, worlds, days, follow_up,
                seed_base=50000):
    specs = []
    per_world = max(1, -(-random_rollouts // worlds))
    for w in range(worlds):
        for c in range(per_world):
            if len(specs) >= random_rollouts:
                break
            specs.append({'world_seed': seed_base + w,
                          'variant': VARIANTS[w % len(VARIANTS)],
                          'policy': 'random', 'collector_seed': c,
                          'days': days, 'follow_up': follow_up})
    for w in range(min(greedy_rollouts, worlds)):
        specs.append({'world_seed': seed_base + w,
                      'variant': VARIANTS[w % len(VARIANTS)],
                      'policy': 'greedy', 'collector_seed': 0,
                      'days': days, 'follow_up': follow_up})
    return specs


def coverage_block(results):
    """Random vs greedy coverage, restricted to worlds that ran both."""
    greedy_worlds = {r['out']['world_seed'] for r in results
                     if r['out']['policy'] == 'greedy'}
    block = {}
    for policy in ('random', 'greedy'):
        sel = [r['out'] for r in results if r['out']['policy'] == policy
               and r['out']['world_seed'] in greedy_worlds]
        opp = sum(o['opportunities_total'] for o in sel)
        chosen = sum(o['chosen_total'] for o in sel)
        block[policy] = {'rollouts': len(sel), 'opportunities': opp,
                         'chosen': chosen,
                         'fraction': (chosen / opp) if opp else 0.0}
    return block


def train_and_evaluate(rows):
    """World-split model comparison for every target. Returns metrics + diagnostics."""
    train_rows, val_rows = analyze.world_split(rows, val_frac=0.2, split_seed=0)
    report = {'n_train_rows': len(train_rows), 'n_val_rows': len(val_rows),
              'train_worlds': len({analyze.world_key(r) for r in train_rows}),
              'val_worlds': len({analyze.world_key(r) for r in val_rows}),
              'split_overlap': analyze.split_overlap(train_rows, val_rows),
              'targets': {}}
    top_features = []
    for target, name in TARGETS:
        Xtr, ytr, _ = analyze.build_dataset(train_rows, target=target)
        Xva, yva, _ = analyze.build_dataset(val_rows, target=target)
        entry = {'train_n': int(len(ytr)), 'val_n': int(len(yva)),
                 'train_pos': int(ytr.sum()), 'val_pos': int(yva.sum())}
        if len(ytr) == 0 or len(yva) == 0:
            entry['models'] = None
            report['targets'][name] = entry
            continue
        models = analyze.fit_models(Xtr, ytr)
        entry['models'] = {n: analyze.evaluate(yva, analyze.predict(m, Xva))
                           for n, m in models}
        report['targets'][name] = entry
        if name == 'mutual':
            top_features = top_correlations(Xtr, ytr, top=10)
    report['top_features_mutual'] = top_features
    report['split'] = (train_rows, val_rows)
    return report


def top_correlations(X, y, top=10):
    """Point-biserial correlation per feature (NaN masked); largest |corr| first."""
    scored = []
    y = y.astype(float)
    for i, key in enumerate(features.FEATURE_KEYS):
        col = X[:, i]
        mask = ~numpy_isnan(col)
        if mask.sum() < 10:
            continue
        xs, ys = col[mask], y[mask]
        if xs.std() == 0 or ys.std() == 0:
            continue
        corr = float(((xs - xs.mean()) * (ys - ys.mean())).mean() / (xs.std() * ys.std()))
        scored.append((abs(corr), key, round(corr, 4)))
    scored.sort(reverse=True)
    return [{'feature': k, 'corr': c} for _, k, c in scored[:top]]


def numpy_isnan(col):
    import numpy as np
    return np.isnan(col)


def calibration_bins(y, scores, bins=5):
    """Quantile bins: mean predicted vs observed (empty bins dropped)."""
    import numpy as np
    if len(y) == 0:
        return []
    order = np.argsort(scores)
    chunks = np.array_split(order, bins)
    out = []
    for chunk in chunks:
        if len(chunk) == 0:
            continue
        out.append({'n': int(len(chunk)),
                    'mean_predicted': round(float(scores[chunk].mean()), 5),
                    'observed_rate': round(float(np.asarray(y)[chunk].mean()), 5)})
    return out


def signal_flags(report):
    """Pre-registered gates: integrity, stage signal, MSMI signal."""
    sections = report['criteria']
    return sections


def compute_criteria(train_eval, integrity_clean):
    """Pre-registered gates. Lifts are measured against VALIDATION prevalence
    (the base rate a reader sees in section D for the held-out worlds)."""
    def stats(name):
        entry = train_eval['targets'].get(name) or {}
        models = entry.get('models') or {}
        hist = models.get('hist_gb') or {}
        val_n = entry.get('val_n') or 0
        val_prev = (entry.get('val_pos') or 0) / val_n if val_n else 0.0
        return hist.get('avg_precision'), hist.get('roc_auc'), val_prev

    stage = False
    for name in ('mutual', 'date'):
        ap, _, val_prev = stats(name)
        if ap is not None and val_prev > 0 and ap >= AP_LIFT_STAGE * val_prev:
            stage = True
    ap, auc, val_prev = stats('msmi')
    msmi = bool(auc is not None and auc >= MSMI_AUC_MIN and ap is not None
                and val_prev > 0 and ap >= AP_LIFT_MSMI * val_prev)
    return {'integrity_clean': bool(integrity_clean),
            'stage_signal': bool(stage), 'msmi_signal': msmi}


def decide(sections):
    if not sections.get('integrity_clean'):
        return 'STOP'
    if sections.get('msmi_signal'):
        return 'PROCEED'
    if sections.get('stage_signal'):
        return 'PROCEED WITH CHANGES'
    return 'STOP'


def build_report(report):
    lines = []
    add = lines.append
    add('SEQUENTIAL MATCHING - DATA PIPELINE VALIDATION REPORT (Round 1 research note)')
    add('generated: %s | kit %s | python %s' % (
        time.strftime('%Y-%m-%d %H:%M:%S'), kit.VERSION, sys.version.split()[0]))
    add('')
    add('A. SCALE AND INTEGRITY')
    add('  rollouts: %d (random %d / greedy %d), worlds: %d, days %d + %d follow-up' % (
        report['n_rollouts'], report['n_random'], report['n_greedy'],
        report['n_worlds'], report['days'], report['follow_up']))
    add('  rows (introduced pairs with matured labels): %d' % report['n_rows'])
    add('  integrity suite: %s' % ('ALL CHECKS PASS' if report['integrity']['ok'] else 'FAILURES'))
    for name, ok in sorted(report['integrity']['checks'].items()):
        add('    - %-22s %s' % (name, 'pass' if ok else 'FAIL'))
    add('  rows audit violations: %d' % len(report['integrity']['violations']))
    add('  dataset audit (%d collected rows, per-row horizon): %d violations' % (
        report['n_rows'], report['dataset_audit_violations']))
    add('  static source audit (hidden member reads): %s' % (report['source_audit'] or 'clean'))
    add('  rows dropped as immature (label None, never 0): %d' % report['n_immature'])
    add('  feature-name leakage audit: %s' % (report['leakage'] or 'clean'))
    add('  structure-informed features disclosed: %s' % (
        ', '.join(features.STRUCTURE_INFORMED) or 'none'))
    add('')
    add('B. COVERAGE (opportunity exploration; same worlds for both policies)')
    for policy in ('random', 'greedy'):
        c = report['coverage'][policy]
        add('  %-7s rollouts %3d | opportunities %6d | introduced %4d | coverage %.4f' % (
            policy, c['rollouts'], c['opportunities'], c['chosen'], c['fraction']))
    ratio = (report['coverage']['random']['fraction']
             / report['coverage']['greedy']['fraction']
             if report['coverage']['greedy']['fraction'] else float('inf'))
    add('  random/greedy coverage ratio: %.2fx' % ratio)
    add('')
    add('C. CLASS BALANCE')
    for name, entry in report['train_eval']['targets'].items():
        add('  %-7s train %5d rows / %4d positives (%.4f) | val %5d / %3d (%.4f)' % (
            name, entry['train_n'], entry['train_pos'],
            entry['train_pos'] / entry['train_n'] if entry['train_n'] else 0,
            entry['val_n'], entry['val_pos'],
            entry['val_pos'] / entry['val_n'] if entry['val_n'] else 0))
    add('  by variant (rows / positives for msmi):')
    for variant, counts in sorted(report['variant_balance'].items()):
        add('    %-12s rows %5d positives %3d prevalence %.4f' % (
            variant, counts['rows'], counts['positives'],
            counts['positives'] / counts['rows'] if counts['rows'] else 0))
    add('')
    add('D. SIGNAL (train/val split by whole worlds: %d train worlds / %d val worlds)' % (
        report['train_eval']['train_worlds'], report['train_eval']['val_worlds']))
    _ov = report['train_eval'].get('split_overlap', {'worlds': -1, 'seeds': -1})
    add('  split overlap (must be 0): %d worlds / %d seeds' % (
        _ov['worlds'], _ov['seeds']))
    for name, entry in report['train_eval']['targets'].items():
        if not entry.get('models'):
            add('  %-7s: no models (empty side)' % name)
            continue
        prev = entry['val_pos'] / entry['val_n'] if entry['val_n'] else 0.0
        for model_name, metrics in entry['models'].items():
            auc = metrics['roc_auc']
            ap = metrics['avg_precision']
            lift = (ap / prev) if (ap is not None and prev > 0) else None
            _ci = metrics.get('auc_ci95')
            add('  %-7s %-9s AUC %s | AP %s (lift %s) | logloss %s | brier %s | '
                'AUC CI95 %s | val n %d pos %d' % (
                name, model_name,
                ('%.4f' % auc) if auc is not None else 'n/a',
                ('%.4f' % ap) if ap is not None else 'n/a',
                ('%.2fx' % lift) if lift else 'n/a',
                ('%.4f' % metrics['log_loss']) if metrics['log_loss'] is not None else 'n/a',
                ('%.4f' % metrics['brier']) if metrics['brier'] is not None else 'n/a',
                ('[%.4f, %.4f]' % _ci) if _ci else 'n/a',
                metrics['n'], metrics['positives']))
        add('    calibration (hist_gb val, quantile bins): %s' % report['calibration'].get(name))
    add('  top features by |point-biserial| with mutual: %s' % [
        (f['feature'], f['corr']) for f in report['train_eval'].get('top_features_mutual', [])])
    add('')
    add('E. LEAKAGE AND LEGALITY')
    add('  - every feature is computed from Simulator.observe() at the introduction day t')
    add('  - feedback with observed_day > t is dropped; fields with field_observed_day > t masked')
    add('  - forbidden names (truth/bias/response_rate/exit_day/seed/variant/ids/events): audit clean = %s'
        % (report['leakage'] == []))
    add('  - rows with immature labels are dropped, never stored as 0 (maturity audit pass = %s)'
        % report['integrity']['checks'].get('rows_audit'))
    add('  - splits are by whole world; no row-level split is possible')
    add('  - labels are built post-episode from the complete event record; a short follow-up')
    add('    would yield None labels (audited), never coerced zeros; policies never see events')
    add('  - static source scan of research modules for hidden member reads: %s'
        % (report['source_audit'] or 'clean'))
    add('  - structure-informed features (%s) reuse published kit weights and are disclosed'
        % ', '.join(features.STRUCTURE_INFORMED))
    add('')
    add('F. DECISION (pre-registered criteria)')
    add('  integrity clean ............... %s' % report['criteria']['integrity_clean'])
    add('  stage signal (AP >= %.1fx prevalence on val) ... %s'
        % (AP_LIFT_STAGE, report['criteria']['stage_signal']))
    add('  MSMI signal (val AUC >= %.2f and AP >= %.1fx prevalence) ... %s'
        % (MSMI_AUC_MIN, AP_LIFT_MSMI, report['criteria']['msmi_signal']))
    add('  DECISION: %s' % report['decision'])
    for note in report['decision_notes']:
        add('    - %s' % note)
    add('')
    add('This run validated the DATA PIPELINE only. No final policy, RL, or tuning here.')
    return '\n'.join(lines) + '\n'


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--smoke', action='store_true', help='tiny end-to-end run')
    p.add_argument('--random-rollouts', type=int, default=400)
    p.add_argument('--greedy-rollouts', type=int, default=40)
    p.add_argument('--worlds', type=int, default=100)
    p.add_argument('--days', type=int, default=60)
    p.add_argument('--follow-up', type=int, default=40)
    p.add_argument('--workers', type=int, default=6)
    p.add_argument('--out', default=str(REPO_ROOT / 'research' / 'out'))
    args = p.parse_args(argv)
    if args.smoke:
        args.random_rollouts, args.greedy_rollouts = 4, 2
        args.worlds, args.days, args.follow_up = 3, 20, 40
        args.workers = 2

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    specs = build_specs(args.random_rollouts, args.greedy_rollouts, args.worlds,
                        args.days, args.follow_up)
    print('running %d rollouts (%d workers)...' % (len(specs), args.workers), flush=True)
    results = []
    started = time.perf_counter()
    if args.workers <= 1:
        for i, spec in enumerate(specs, 1):
            results.append(_run_spec(spec))
            print('  %d/%d' % (i, len(specs)), flush=True)
    else:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(_run_spec, spec): spec for spec in specs}
            for i, future in enumerate(as_completed(futures), 1):
                results.append(future.result())
                if i % 20 == 0 or i == len(specs):
                    print('  %d/%d (%.0fs)' % (i, len(specs),
                                               time.perf_counter() - started), flush=True)

    results.sort(key=lambda item: (item['out']['world_seed'], item['out']['variant'],
                                   item['out']['policy'], item['out']['collector_seed']))
    rows = sort_rows([r for item in results for r in item['out']['rows']])
    integrity_report = integrity.run_integrity_suite(n_worlds=2, days=20,
                                                     follow_up=args.follow_up,
                                                     collector_seed=4)
    dataset_audit = integrity.audit_rows(rows)   # horizon taken per row
    source_audit = integrity.audit_source()
    leakage = (analyze.leakage_audit() + source_audit
               + list(features.audit_structure_disclosure()))
    n_immature = sum(1 for r in rows if r['label'] is None)

    train_eval = train_and_evaluate(rows)
    split = train_eval.pop('split')
    val_rows = split[1]

    variant_balance = {}
    for row in rows:
        entry = variant_balance.setdefault(row['variant'], {'rows': 0, 'positives': 0})
        entry['rows'] += 1
        entry['positives'] += int(row['label'] == 1)

    calibration = {}
    for target, name in TARGETS:
        Xtr, ytr, _ = analyze.build_dataset(split[0], target=target)
        Xva, yva, _ = analyze.build_dataset(val_rows, target=target)
        if len(ytr) and len(yva):
            models = dict(analyze.fit_models(Xtr, ytr))
            if 'hist_gb' in models:
                calibration[name] = calibration_bins(yva, analyze.predict(models['hist_gb'], Xva))

    _split_clean = (train_eval['split_overlap']['worlds'] == 0
                    and train_eval['split_overlap']['seeds'] == 0)
    criteria = compute_criteria(
        train_eval,
        integrity_clean=bool(integrity_report['ok']) and not dataset_audit
        and _split_clean)
    stage_signal = criteria['stage_signal']
    msmi_signal = criteria['msmi_signal']
    notes = []
    if not criteria['integrity_clean']:
        notes.append('integrity failed (suite ok: %s, dataset audit violations: %d) - '
                     'the pipeline cannot be trusted until fixed'
                     % (integrity_report['ok'], len(dataset_audit)))
    if not stage_signal:
        notes.append('no stage-target signal on held-out worlds - features or policy '
                     'need rework before training a value model')
    if stage_signal and not msmi_signal:
        notes.append('stage signal exists but MSMI target is too rare/weak at this scale: '
                     'consider more rollouts, auxiliary-target pretraining, or rarer-event '
                     'strategies before the A+C policy')
    if msmi_signal and criteria['integrity_clean']:
        notes.append('pipeline learns the primary metric on held-out worlds: ready to '
                     'design the A+C policy (requires explicit approval)')

    report = {'n_rollouts': len(results),
              'n_random': sum(1 for r in results if r['out']['policy'] == 'random'),
              'n_greedy': sum(1 for r in results if r['out']['policy'] == 'greedy'),
              'n_worlds': len({(r['out']['world_seed']) for r in results}),
              'days': args.days, 'follow_up': args.follow_up,
              'n_rows': len(rows),
              'dataset_audit_violations': len(dataset_audit),
              'n_immature': n_immature,
              'source_audit': source_audit,
              'integrity': integrity_report, 'leakage': leakage,
              'coverage': coverage_block(results),
              'variant_balance': variant_balance,
              'train_eval': train_eval, 'calibration': calibration,
              'criteria': criteria, 'decision_notes': notes,
              'decision': decide(criteria),
              'elapsed_seconds': round(time.perf_counter() - started, 1)}

    write_rows_csv(out_dir / 'rows.csv', rows)
    write_worlds_csv(out_dir / 'worlds.csv', results)
    text = build_report(report)
    (out_dir / 'report.txt').write_text(text, encoding='utf-8')
    (out_dir / 'report.json').write_text(
        __import__('json').dumps({k: v for k, v in report.items()}, indent=2,
                                 default=str), encoding='utf-8')
    print(text)
    print('wrote %s' % (out_dir / 'report.txt'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
