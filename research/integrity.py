"""Integrity audits: prove the collected rows cannot leak and do not drift.

Checks
- forbidden feature names (hidden truth/bias/response_rate/seed/variant/ids/...)
- declared structure-informed features match what is actually present
- temporal soundness: features['day'] == row day, maturity strictly after assignment,
  label present iff matured at the horizon, label stable at its own maturity day
- world snapshot unchanged by a rollout (Simulator must deep-copy)
- determinism: same (world, collector seed) -> identical rows
"""
import json
from pathlib import Path

import kit

import features
import labels as lab
from collect import collect_rows

REQUIRED_ROW_KEYS = ('day', 'a', 'b', 'features', 'introduction_id',
                     'label', 'maturity_day')


def audit_rows(rows, horizon=None):
    """List of violations (empty == clean)."""
    violations = []
    seen = set()
    for i, row in enumerate(rows):
        for key in REQUIRED_ROW_KEYS:
            if key not in row:
                violations.append('row%d:missing:%s' % (i, key))
        features_row = row.get('features', {})
        for bad in features.audit_feature_keys(list(features_row)):
            violations.append('row%d:forbidden:%s' % (i, bad))
        if 'day' in features_row and features_row['day'] != row.get('day'):
            violations.append('row%d:temporal:features_day_mismatch' % i)
        dup = (row.get('world_seed'), row.get('variant'), row.get('policy'),
               row.get('collector_seed'), row.get('day'), row.get('a'), row.get('b'))
        if dup in seen:
            violations.append('row%d:duplicate:%s' % (i, dup))
        seen.add(dup)
        maturity = row.get('maturity_day')
        if maturity is not None and maturity <= row.get('day', 0):
            violations.append('row%d:temporal:maturity_not_after_assignment' % i)
        label = row.get('label')
        if label is not None and label not in (0, 1):
            violations.append('row%d:label:invalid:%r' % (i, label))
        effective = horizon if horizon is not None else row.get('horizon')
        if effective is not None and maturity is not None:
            if maturity <= effective and label is None:
                violations.append('row%d:label:premature_none' % i)
            if maturity > effective and label is not None:
                violations.append('row%d:label:unmatured_value' % i)
    return violations


HIDDEN_ACCESS_PATTERNS = ("['truth']", "['bias']", "['second_bias']",
                          "['response_rate']", "['exit_day']", "['ask_log']")
SOURCE_TARGETS = ('features.py', 'collect.py', 'analyze.py',
                  'run_experiment.py', 'labels.py')


def audit_source(files=None):
    """Static scan: no module may READ a hidden member field. (empty == clean)
    Files is {name: text}; defaults to the research modules that build data."""
    if files is None:
        base = Path(__file__).resolve().parent
        files = {name: (base / name).read_text(encoding='utf-8')
                 for name in SOURCE_TARGETS if (base / name).exists()}
    violations = []
    for name, text in files.items():
        for pattern in HIDDEN_ACCESS_PATTERNS:
            if pattern in text:
                violations.append('%s:%s' % (name, pattern))
    return violations


def _stable(obj):
    return json.dumps(obj, sort_keys=True, default=str)


def run_integrity_suite(n_worlds=2, days=25, follow_up=40, collector_seed=4):
    """End-to-end audit over a few small rollouts; report dict with per-check booleans."""
    checks = {}
    violations = []
    worlds = [kit.generate(500 + i, 100) for i in range(n_worlds)]

    checks['forbidden_keys'] = features.audit_feature_keys() == []
    checks['structure_disclosure'] = features.audit_structure_disclosure() == []

    snapshots = [_stable(w) for w in worlds]
    outputs = [collect_rows(w, collector_seed=collector_seed, days=days,
                            follow_up=follow_up) for w in worlds]
    checks['snapshot_unchanged'] = all(_stable(w) == s for w, s in zip(worlds, snapshots))

    all_rows = [r for out in outputs for r in out['rows']]
    found = audit_rows(all_rows, horizon=max(out['horizon'] for out in outputs))
    checks['rows_audit'] = not found
    violations.extend(found)

    stable = True
    for out in outputs:
        grouped = lab.group_events(out['events'])
        for row in out['rows']:
            evs = grouped[row['introduction_id']]
            if lab.label_msmi(evs, row['day'], row['maturity_day']) != row['label']:
                stable = False
    checks['label_stability'] = stable

    again = collect_rows(worlds[0], collector_seed=collector_seed, days=days,
                         follow_up=follow_up)
    checks['determinism'] = _stable(again['rows']) == _stable(outputs[0]['rows'])

    return {'checks': checks, 'violations': violations, 'ok': all(checks.values())}
