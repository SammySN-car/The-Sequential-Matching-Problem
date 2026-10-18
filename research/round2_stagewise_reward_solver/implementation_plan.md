# Round2 Solver Experiment - Implementation Plan (execution-side)

Companion to the FROZEN `analysis_plan.md` (sha256 ed1210c2...). That document
owns the science (corpus, gates, metrics, decision rules, all frozen). This
document owns file layout, module interfaces and task order. Nothing here may
contradict it; clarifications are logged in run_log.txt.

## File layout (all new; nothing outside this directory is written)

- `analysis_plan.md` / `.sha256`      - frozen pre-registration
- `implementation_plan.md`            - this file
- `run_log.txt`                       - append-only log
- `policy_candidate.py`               - new candidate policy (S.5 contract)
- `scripts/sr_features.py`            - byte-identical copy (hash 76fc12f6...)
- `scripts/sr_policy_core.py`         - byte-identical copy (hash 02af1e6a...)
  NOTE: sr_policy_core is copied to experiment ROOT (imported as sr_policy_core
  by policy_candidate via sys.path on the experiment dir; sr_features via
  sys.path on scripts/). Both copies verified byte-identical at copy time.
- `scripts/srws_solver.py`            - exact-k solver (Task 1)
- `scripts/srws_solver_test.py`       - C1-C6 battery -> results/solver_validation.json (Task 2)
- `scripts/srws_policy_test.py`       - P1-P3 -> results/policy_validity.json (Task 3)
- `scripts/srws_benchmark.py`         - corpus materialisation + R-A..R-D timing (Task 4)
- `scripts/srws_eval_run.py`          - runs both arms via evaluate.py CLI (Task 5)
- `scripts/srws_eval_aggregate.py`    - paired stats -> results/paired_stats.json (Task 5)
- `scripts/srws_integrity.py`         - new seal + read-only parent-seal check (Task 6)
- `report.md`                         - final report (Task 6)
- `results/*.json`                   - machine-readable outputs
- `integrity.sha256`                  - final seal

## Module interfaces (exact contracts; tasks depend on these)

### scripts/srws_solver.py

```python
class SolverError(Exception): ...          # precondition violation / structural failure
class InfeasibleKError(SolverError): ...   # no matching of size k exists

def solve_exact_k(edges, weights, k):
    """edges: sequence of (u, v) str pairs, u != v, no duplicate pairs,
    any order. weights: sequence of Python floats, same length, each in [0,1).
    k: int >= 0.
    Returns (indices, meta):
      indices - tuple of indices into `edges`, sorted ascending, forming a
                vertex-disjoint set of exactly k edges maximising the exact
                sum of weights; among primary optima the unique set maximising
                the binary tie weights (== lexicographically smallest set under
                canonical (u<v) sorted edge order).
      meta    - {'n_vertices': int, 'n_aug_edges': int, 'aug_N': int,
                 'value_int': str, 'value_float': float}
                value_int = exact combined primary numerator sum as decimal
                string (huge ints are not JSON-safe); value_float =
                math.fsum of the selected original float weights.
    Raises InfeasibleKError if no size-k matching exists; SolverError on any
    precondition violation (length mismatch, empty edge with u==v, k<0,
    k > floor(n/2) is InfeasibleKError). Never returns a partial matching.
    Deterministic: no RNG, no clock in the decision path."""
```

Realisation note (logged): S.4.1 sentence "minimises the negated combined
weights" is realised in the mathematically equivalent standard form - a
maximum-weight matching routine with maxcardinality=True applied to the
COMBINED weights directly (both forms compute argmax SUM(C) subject to
perfectness; a min-routine would instead be fed -C). No objective, tie-policy
or gate differs. The routine is an own-implementation primal-dual blossom for
general graphs, pure stdlib, exact integer weights (as_integer_ratio scaling,
common power-of-two denominator), O(V^3)-class. No NetworkX/SciPy/external
process/network/GPU/new packages.

### policy_candidate.py

Parent-candidate structure (asks = kit.baseline_asks verbatim; --baseline
accepted+ignored; artifact sha-verified at import; P_hat = p1*p2*p3 stdlib
mirror), with these changes: imports srws_solver.solve_exact_k; NO greedy
fallback - SolverError/InfeasibleKError/any exception in match => stderr
diagnostic + SystemExit(2) (episode fails loudly); instrumentation env var
`SRS_INSTRUMENTATION_DIR`, one line per match: {day, n_edges, k_greedy,
k_chosen, solver_seconds, invocation_seconds, pid}. pairs = selected edges in
ascending input-edge index order (canonical edge order fed to solver).

### scripts/srws_benchmark.py

Corpus (frozen in S.7): R-A all 3000 day-0 states via
generate(seed,200,'evaluation',variant) + observe(); R-B all recorded rows with
n_edges>=40; R-C the 53 v4 stress states; R-D 3000-row uniform sample of the
remaining non-day-0 rows via random.Random(20261014) over the sorted
(seed_group, variant, day) list. Replay = in-process greedy trajectory
(baseline_asks/resolve_asks/baseline_match/advance) to the recorded day;
reconstruction mismatch on n_edges or k_greedy => state excluded + counted.
Per state: solver-only timing (candidate scoring path -> solver) and
end-to-end subprocess timing exactly as evaluate.py invokes the policy.
Outputs results/benchmark_corpus.json + results/runtime_benchmark.json with
R-gate verdicts and p50/p95/p99/max.

### scripts/srws_eval_run.py

Subprocess-wraps the UNMODIFIED evaluator twice (arms) with the full 100-seed
list x variants all; appends per-episode JSONL progress as it runs (crash
safe); records commands, timestamps, exit codes; sets SRS_INSTRUMENTATION_DIR
for the candidate arm only.

### scripts/srws_eval_aggregate.py

d_g per seed group (6-variant means), mean, B=10000 paired bootstrap
(random.Random(71001), percentile 2.5/97.5), win/tie/loss, per-variant paired
means, totals, invalid counts, instrumentation cardinality audit
(k_chosen==k_greedy on every line) -> results/paired_stats.json.

## Task order (SDD; each task reviewed before the next)

1. srws_solver.py + own smoke (empty/k0/known-small cases).
2. srws_solver_test.py battery C1-C6 (>=10000 brute-force cases) ->
   results/solver_validation.json. Any bug => fix task, re-run, log.
3. policy_candidate.py + srws_policy_test.py (P1-P3, pilot seed 40001 smoke).
4. srws_benchmark.py corpus + timing -> R-gate verdict.
5. srws_eval_run.py + srws_eval_aggregate.py -> final paired evaluation
   (GATED: only if 1-4 all pass) -> results/paired_stats.json.
6. report.md + srws_integrity.py seal + parent-seal-unchanged check + closure.

Gates are enforced between tasks: task 5 may not start unless
results/solver_validation.json passed=true AND
results/runtime_benchmark.json all_gates_passed=true AND
results/policy_validity.json passed=true.
