"""Dataset building, world-level splits, model fitting, metrics, leakage audit.

Rules:
- rows with label None (immature) are dropped, never converted to 0
- train/val split by WHOLE WORLD (world_seed, variant), never by row
- HistGradientBoostingClassifier handles NaN natively (no imputation)
- constant baseline predicts the training positive rate (calibration floor)
"""
import random

import numpy as np

import features

try:
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.metrics import (roc_auc_score, average_precision_score, log_loss,
                                 brier_score_loss)
except ImportError:  # pragma: no cover - environment guard
    HistGradientBoostingClassifier = None


class ConstantBaseline:
    """Predicts one probability for every row."""

    def __init__(self, rate):
        self.rate = float(rate)

    def predict_proba(self, X):
        n = len(X)
        return np.column_stack([np.full(n, 1.0 - self.rate), np.full(n, self.rate)])


def build_dataset(rows, feature_keys=None, target='label'):
    """(X, y, kept_rows): NaN preserved, immature rows dropped."""
    keys = list(feature_keys or features.FEATURE_KEYS)
    X, y, kept = [], [], []
    for row in rows:
        label = row.get(target)
        if label is None:
            continue
        X.append([row['features'][k] for k in keys])
        y.append(int(label))
        kept.append(row)
    return (np.array(X, dtype=float) if X else np.zeros((0, len(keys))),
            np.array(y, dtype=int), kept)


def world_key(row):
    return (row['world_seed'], row['variant'])


def world_split(rows, val_frac=0.25, split_seed=0):
    """Split by whole worlds: no world may appear on both sides."""
    worlds = sorted({world_key(r) for r in rows})
    if len(worlds) < 2:
        raise ValueError('need at least 2 worlds to split')
    random.Random(split_seed).shuffle(worlds)
    n_val = max(1, min(len(worlds) - 1, int(round(len(worlds) * val_frac))))
    val_worlds = set(worlds[:n_val])
    train = [r for r in rows if world_key(r) not in val_worlds]
    val = [r for r in rows if world_key(r) in val_worlds]
    if not train or not val:
        raise ValueError('empty split side')
    return train, val


def fit_models(X, y):
    """[(name, model)]; hist_gb only when both classes exist."""
    models = [('constant', ConstantBaseline(float(np.mean(y))))]
    if HistGradientBoostingClassifier is not None and len(set(y.tolist())) >= 2:
        model = HistGradientBoostingClassifier(random_state=0, max_iter=200,
                                               learning_rate=0.1)
        model.fit(X, y)
        models.append(('hist_gb', model))
    return models


def predict(model, X):
    return model.predict_proba(np.asarray(X, dtype=float))[:, 1]


def evaluate(y, scores):
    """Metrics dict; roc_auc is None when only one class is present."""
    y = np.asarray(y, dtype=int)
    scores = np.asarray(scores, dtype=float)
    both = len(np.unique(y)) >= 2
    auc = float(roc_auc_score(y, scores)) if both else None
    return {
        'n': int(len(y)),
        'positives': int(y.sum()),
        'prevalence': float(y.mean()) if len(y) else 0.0,
        'roc_auc': auc,
        'auc_ci95': auc_ci(auc, int(y.sum()), int(len(y) - y.sum())),
        'avg_precision': float(average_precision_score(y, scores)) if len(y) else None,
        'log_loss': float(log_loss(y, np.clip(scores, 1e-6, 1 - 1e-6),
                                   labels=[0, 1])) if len(y) else None,
        'brier': float(brier_score_loss(y, scores)) if len(y) else None,
    }


def leakage_audit():
    """Feature names that would leak hidden information (empty == clean)."""
    return features.audit_feature_keys()


def auc_ci(auc, n_pos, n_neg, z=1.96):
    """95% CI for ROC-AUC via Hanley-McNeil (1982) SE; None if not computable."""
    if auc is None or n_pos <= 0 or n_neg <= 0:
        return None
    q1 = auc / (2.0 - auc)
    q2 = 2.0 * auc * auc / (1.0 + auc)
    se = ((auc * (1.0 - auc) + (n_pos - 1) * (q1 - auc * auc)
           + (n_neg - 1) * (q2 - auc * auc)) / (n_pos * n_neg)) ** 0.5
    return (max(0.0, auc - z * se), min(1.0, auc + z * se))


def split_overlap(train_rows, val_rows):
    """World-key and raw-seed overlap between split sides (both must be 0)."""
    train_worlds = {world_key(r) for r in train_rows}
    val_worlds = {world_key(r) for r in val_rows}
    train_seeds = {r['world_seed'] for r in train_rows}
    val_seeds = {r['world_seed'] for r in val_rows}
    return {'worlds': len(train_worlds & val_worlds),
            'seeds': len(train_seeds & val_seeds)}
