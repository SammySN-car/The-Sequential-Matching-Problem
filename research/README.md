# research/ - training-data pipeline prototype (Round 1)

Validates ONLY the data pipeline for the Sequential Matching Problem kit:
can we collect rollout data, label it soundly, extract legal features, and train
a model that predicts on HELD-OUT WORLDS? It does **not** implement the A+C
policy, RL, hyperparameter tuning, or the 10,000-rollout production run.

## Files

| file | purpose |
|---|---|
| `labels.py` | MSMI + stage labels (mutual, date); maturity rule; `None` for immature |
| `features.py` | 44 decision-time pair features, symmetric, NaN for unknowns, leakage audits |
| `collect.py` | opportunity `scan()`, `RandomCollector` (bundled asks, eps/jitter matching), `collect_rows()` |
| `integrity.py` | audits: forbidden names, temporal soundness, snapshot, label stability, determinism |
| `analyze.py` | world-level splits, HistGB + constant baseline, metrics, leakage audit |
| `run_experiment.py` | parallel driver -> `out/rows.csv`, `out/worlds.csv`, `out/report.txt` |
| `test_pipeline.py` | TDD suite for all of the above |

## Run

```powershell
# from the repo root
python -m unittest research.test_pipeline -v   # 68 tests
python -m research.run_experiment --smoke      # end-to-end smoke
python -m research.run_experiment --random-rollouts 400 --greedy-rollouts 40 --workers 12
```

## Hard rules encoded (and audited) here

1. Only introduced pairs are labelled; un-introduced pairs are never stored as 0.
2. `label is None` (immature) is never coerced to 0; rollouts run 60 + 40 days so
   every label matures (maturity = max `observed_day` of the introduction's events).
3. Features at day `t` use only feedback with `observed_day <= t`, and mask fields
   whose `field_observed_day > t`.
4. No `truth`, `bias`, `second_bias`, `response_rate`, `exit_day`, `seed`, `variant`,
   raw events, ask logs, or identifiers may appear as feature names (audited).
5. Splits are by whole world `(world_seed, variant)` - never by row.
6. Structure-informed features (`weighted_soft_score`, `weighted_soft_covered`) reuse
   the published kit weights and are disclosed, not hidden.

## Outputs

- `out/rows.csv` - one row per introduced pair: meta, `label`/`label_mutual`/`label_date`, `feat_*`
- `out/worlds.csv` - one row per rollout: metrics, coverage, timing
- `out/report.txt` - sections A-F ending in PROCEED / PROCEED WITH CHANGES / STOP
- `out/report.json` - machine-readable version of the report

New files live only in this directory; `kit.py`, `evaluate.py`, `policy.py` are untouched.
