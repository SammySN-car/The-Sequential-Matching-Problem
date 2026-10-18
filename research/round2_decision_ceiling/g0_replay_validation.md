# G0 - Counterfactual Replay Validation

**Status: GO - proceed to sections 3-7**

Protocol horizon 100 = 60 decision days + 40 follow-up days (`evaluate.episode`, `evaluate.py` L80-115).

| Test | Result | Criterion |
|---|---|---|
| T1 pair-orientation invariance | PASS | 50 runs, 0 mismatches |
| T2 batch independence | PASS | 50 days, 0 mismatches |
| T2L snapshot leak | PASS | 50 snapshots unchanged |
| T3 isolated replay exact match | PASS | 8433/8433 exact on mature, y_msmi, y_mutual, y_date, y_second, missing |
| T3b action digest reproduction | PASS | 126/126 digests equal n01_replay_rows |
| T4 label sums vs official | PASS | 126/126 per-world sums equal; 0 immature at horizon 100 |
| T5 determinism | PASS | two full passes bit-identical |

## Method

Each counterfactual run starts from `copy.deepcopy(Simulator)` taken after `resolve_asks` and before `advance` on the decision day, giving the copy its own `introductions`, `events`, `past` and `busy` (the only containers `kit.Simulator.advance` writes, verified against kit.py L141-189). The pair is run alone with `advance([[a,b]])` under the sorted orientation produced at kit.py L152, then followed with `advance([])` to day 100 so labels use the same maturity rules as the official rollout. A fingerprint of the four mutated containers is taken before and after every isolated run; any change aborts the pass.

## Per-world detail

| seed | variant | selected | compared | mismatch | digest | sums |
|---|---|---|---|---|---|---|
| 143 | cold_start | 70 | 70 | 0 | ok | ok |
| 143 | delayed | 114 | 114 | 0 | ok | ok |
| 143 | development | 114 | 114 | 0 | ok | ok |
| 143 | drift | 114 | 114 | 0 | ok | ok |
| 143 | shift | 113 | 113 | 0 | ok | ok |
| 143 | sparse | 18 | 18 | 0 | ok | ok |
| 144 | cold_start | 69 | 69 | 0 | ok | ok |
| 144 | delayed | 80 | 80 | 0 | ok | ok |
| 144 | development | 76 | 76 | 0 | ok | ok |
| 144 | drift | 76 | 76 | 0 | ok | ok |
| 144 | shift | 79 | 79 | 0 | ok | ok |
| 144 | sparse | 15 | 15 | 0 | ok | ok |
| 145 | cold_start | 82 | 82 | 0 | ok | ok |
| 145 | delayed | 76 | 76 | 0 | ok | ok |
| 145 | development | 83 | 83 | 0 | ok | ok |
| 145 | drift | 83 | 83 | 0 | ok | ok |
| 145 | shift | 81 | 81 | 0 | ok | ok |
| 145 | sparse | 23 | 23 | 0 | ok | ok |
| 146 | cold_start | 76 | 76 | 0 | ok | ok |
| 146 | delayed | 61 | 61 | 0 | ok | ok |
| 146 | development | 62 | 62 | 0 | ok | ok |
| 146 | drift | 62 | 62 | 0 | ok | ok |
| 146 | shift | 62 | 62 | 0 | ok | ok |
| 146 | sparse | 23 | 23 | 0 | ok | ok |
| 147 | cold_start | 78 | 78 | 0 | ok | ok |
| 147 | delayed | 94 | 94 | 0 | ok | ok |
| 147 | development | 95 | 95 | 0 | ok | ok |
| 147 | drift | 95 | 95 | 0 | ok | ok |
| 147 | shift | 99 | 99 | 0 | ok | ok |
| 147 | sparse | 41 | 41 | 0 | ok | ok |
| 148 | cold_start | 50 | 50 | 0 | ok | ok |
| 148 | delayed | 68 | 68 | 0 | ok | ok |
| 148 | development | 70 | 70 | 0 | ok | ok |
| 148 | drift | 70 | 70 | 0 | ok | ok |
| 148 | shift | 71 | 71 | 0 | ok | ok |
| 148 | sparse | 17 | 17 | 0 | ok | ok |
| 149 | cold_start | 59 | 59 | 0 | ok | ok |
| 149 | delayed | 92 | 92 | 0 | ok | ok |
| 149 | development | 87 | 87 | 0 | ok | ok |
| 149 | drift | 88 | 88 | 0 | ok | ok |
| 149 | shift | 89 | 89 | 0 | ok | ok |
| 149 | sparse | 23 | 23 | 0 | ok | ok |
| 150 | cold_start | 36 | 36 | 0 | ok | ok |
| 150 | delayed | 51 | 51 | 0 | ok | ok |
| 150 | development | 54 | 54 | 0 | ok | ok |
| 150 | drift | 54 | 54 | 0 | ok | ok |
| 150 | shift | 54 | 54 | 0 | ok | ok |
| 150 | sparse | 17 | 17 | 0 | ok | ok |
| 151 | cold_start | 96 | 96 | 0 | ok | ok |
| 151 | delayed | 89 | 89 | 0 | ok | ok |
| 151 | development | 97 | 97 | 0 | ok | ok |
| 151 | drift | 97 | 97 | 0 | ok | ok |
| 151 | shift | 98 | 98 | 0 | ok | ok |
| 151 | sparse | 27 | 27 | 0 | ok | ok |
| 152 | cold_start | 55 | 55 | 0 | ok | ok |
| 152 | delayed | 54 | 54 | 0 | ok | ok |
| 152 | development | 54 | 54 | 0 | ok | ok |
| 152 | drift | 54 | 54 | 0 | ok | ok |
| 152 | shift | 53 | 53 | 0 | ok | ok |
| 152 | sparse | 21 | 21 | 0 | ok | ok |
| 153 | cold_start | 54 | 54 | 0 | ok | ok |
| 153 | delayed | 70 | 70 | 0 | ok | ok |
| 153 | development | 67 | 67 | 0 | ok | ok |
| 153 | drift | 68 | 68 | 0 | ok | ok |
| 153 | shift | 72 | 72 | 0 | ok | ok |
| 153 | sparse | 11 | 11 | 0 | ok | ok |
| 154 | cold_start | 90 | 90 | 0 | ok | ok |
| 154 | delayed | 82 | 82 | 0 | ok | ok |
| 154 | development | 77 | 77 | 0 | ok | ok |
| 154 | drift | 77 | 77 | 0 | ok | ok |
| 154 | shift | 79 | 79 | 0 | ok | ok |
| 154 | sparse | 22 | 22 | 0 | ok | ok |
| 155 | cold_start | 79 | 79 | 0 | ok | ok |
| 155 | delayed | 88 | 88 | 0 | ok | ok |
| 155 | development | 100 | 100 | 0 | ok | ok |
| 155 | drift | 100 | 100 | 0 | ok | ok |
| 155 | shift | 100 | 100 | 0 | ok | ok |
| 155 | sparse | 22 | 22 | 0 | ok | ok |
| 156 | cold_start | 78 | 78 | 0 | ok | ok |
| 156 | delayed | 76 | 76 | 0 | ok | ok |
| 156 | development | 88 | 88 | 0 | ok | ok |
| 156 | drift | 88 | 88 | 0 | ok | ok |
| 156 | shift | 87 | 87 | 0 | ok | ok |
| 156 | sparse | 24 | 24 | 0 | ok | ok |
| 157 | cold_start | 53 | 53 | 0 | ok | ok |
| 157 | delayed | 72 | 72 | 0 | ok | ok |
| 157 | development | 76 | 76 | 0 | ok | ok |
| 157 | drift | 76 | 76 | 0 | ok | ok |
| 157 | shift | 76 | 76 | 0 | ok | ok |
| 157 | sparse | 23 | 23 | 0 | ok | ok |
| 158 | cold_start | 78 | 78 | 0 | ok | ok |
| 158 | delayed | 98 | 98 | 0 | ok | ok |
| 158 | development | 102 | 102 | 0 | ok | ok |
| 158 | drift | 102 | 102 | 0 | ok | ok |
| 158 | shift | 104 | 104 | 0 | ok | ok |
| 158 | sparse | 14 | 14 | 0 | ok | ok |
| 159 | cold_start | 59 | 59 | 0 | ok | ok |
| 159 | delayed | 79 | 79 | 0 | ok | ok |
| 159 | development | 82 | 82 | 0 | ok | ok |
| 159 | drift | 82 | 82 | 0 | ok | ok |
| 159 | shift | 82 | 82 | 0 | ok | ok |
| 159 | sparse | 11 | 11 | 0 | ok | ok |
| 160 | cold_start | 54 | 54 | 0 | ok | ok |
| 160 | delayed | 53 | 53 | 0 | ok | ok |
| 160 | development | 49 | 49 | 0 | ok | ok |
| 160 | drift | 49 | 49 | 0 | ok | ok |
| 160 | shift | 50 | 50 | 0 | ok | ok |
| 160 | sparse | 15 | 15 | 0 | ok | ok |
| 161 | cold_start | 77 | 77 | 0 | ok | ok |
| 161 | delayed | 91 | 91 | 0 | ok | ok |
| 161 | development | 84 | 84 | 0 | ok | ok |
| 161 | drift | 84 | 84 | 0 | ok | ok |
| 161 | shift | 91 | 91 | 0 | ok | ok |
| 161 | sparse | 13 | 13 | 0 | ok | ok |
| 162 | cold_start | 72 | 72 | 0 | ok | ok |
| 162 | delayed | 72 | 72 | 0 | ok | ok |
| 162 | development | 75 | 75 | 0 | ok | ok |
| 162 | drift | 76 | 76 | 0 | ok | ok |
| 162 | shift | 76 | 76 | 0 | ok | ok |
| 162 | sparse | 11 | 11 | 0 | ok | ok |
| 163 | cold_start | 51 | 51 | 0 | ok | ok |
| 163 | delayed | 61 | 61 | 0 | ok | ok |
| 163 | development | 61 | 61 | 0 | ok | ok |
| 163 | drift | 61 | 61 | 0 | ok | ok |
| 163 | shift | 61 | 61 | 0 | ok | ok |
| 163 | sparse | 19 | 19 | 0 | ok | ok |
