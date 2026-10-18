# Round 2 Stagewise-Reward Solver Experiment - Pre-Registration (Analysis Plan)

Experiment directory: `research/round2_stagewise_reward_solver/`
Parent experiment: `research/round2_stagewise_reward/` (decision `STOP / REDESIGN`; read-only, 1,638-entry seal untouched)
Status of this document: FROZEN before any solver implementation. The SHA-256
recorded in `analysis_plan.sha256` is authoritative. All deviations, failures
and fixes are appended to `run_log.txt`; this document is never edited after
freezing.

---

## S.1 Objective and single question

One question, one decision:

> Does reward-aware exact-k pair selection improve realized MSMIs in the full
> sequential simulator, when the candidate introduces exactly as many pairs as
> greedy in every individual decision state?

The previous experiment (`round2_stagewise_reward`) stopped at its solver
deployability gate: the reused branch-and-bound exact-k solver took up to
17.199 s on dense states (gate < 3.0 s; evaluator hard limit 10 s). The policy
hypothesis was never tested. This experiment removes the computational
bottleneck with a polynomial-time exact solver and, only if every gate passes,
runs the previously untouched paired evaluation.

Explicit non-goals (out of scope, forbidden in this round): retraining or
recalibrating the model, feature changes, RL, clarification logic, approximate
selectors, alternative policy families, density-threshold policies.

## S.2 Protected surfaces (never modified)

- `policy.py`, `kit.py`, `evaluate.py`, `Dockerfile`, `requirements.txt`
- Every file under `research/round2_stagewise_reward/` including its
  `analysis_plan.md`, `report.md`, `integrity.sha256` (1,638 entries), the
  frozen model `results/model_artifact.json` and all seals
- All other prior research directories
- No git-mutating commands anywhere in this experiment
- All new files live under `research/round2_stagewise_reward_solver/` only

Code provenance: `scripts/sr_features.py` and `sr_policy_core.py` are COPIED
byte-for-byte from the parent experiment (original SHA-256 recorded in the run
log; copy hashes must equal originals). The parent experiment directory is
imported read-only nowhere; the new candidate imports only from the new
directory plus repo-root `kit.py`.

## S.3 Frozen model and scores

- Artifact: `../round2_stagewise_reward/results/model_artifact.json`,
  SHA-256 `7f1ddfe00211e2603e88c4e8318d3a62980aeb8364f51bc41909e8875fa275f2`
  (verified 2026-10-14 at pre-registration time; re-verified before and after
  the final evaluation; any mismatch stops the experiment).
- Edge score: `P_hat(a,b) = p1 * p2 * p3` from the unchanged three frozen
  logistic stages over the unchanged 17 features (pure-stdlib mirror of
  `sr_train.predict_stage`, as in the parent candidate). No retraining, no
  recalibration, no thresholding, no clipping beyond the mirror's own eta
  clamp, no rounding of the produced floats.
- Standing interpretation (from the parent experiment's post-hoc audit, quoted
  as background only): the combined prediction over all 45,803 mature
  validation introductions had ROC-AUC 0.531473, PR-AUC 0.011841 vs 0.010589
  prevalence, mean predicted 0.010359 vs observed 0.010589. Signal is weak.
  This experiment tests whether the existing scores improve DECISIONS; it does
  not try to improve the model, and no positive result is expected to be
  attributable to anything but selection among existing scores.

## S.4 Optimization problem and algorithm (fixed before implementation)

Problem: on the currently feasible undirected graph G = (V, E) with weights
w_e = P_hat(e) (floats in (0,1)), and k = |greedy's matching on this state|,
return a vertex-disjoint edge set M with |M| = k maximising sum_e in M w_e.
The graph is GENERAL (not bipartite): the simulator permits same-gender and
non-binary compatible pairs (`kit.py` GENDERS, mutual `who_to_meet`).

Formulation (dummy-vertex reduction to maximum-weight PERFECT matching):

1. Let V be exactly the set of vertices incident to at least one edge in E;
   n = |V|. Isolated members are excluded by construction.
2. Preconditions, asserted (not assumed): E non-empty implies n >= 2;
   0 <= k <= floor(n/2). k=0 or E empty => return the empty matching directly,
   the solver is never invoked.
3. Add D = n - 2k dummy vertices; connect every dummy to EVERY original vertex
   with primary weight 0 and no tie weight.
4. Solve maximum-weight PERFECT matching on the augmented graph
   (N = n + D = 2n - 2k vertices, always even).
5. Extract the original-original edges; assert the result has exactly k edges
   and is vertex-disjoint.

Correctness of the reduction (proved here, tested in S.6): in any perfect
matching of the augmented graph each dummy is matched with an original vertex
(dummies have no dummy-dummy edges), consuming exactly D = n - 2k originals and
leaving exactly 2k originals that must be paired among themselves, i.e.
exactly k original edges. Conversely any k-edge matching of G extends to a
perfect matching of the augmented graph by pairing the n - 2k unmatched
originals with the D dummies. Dummy edges carry weight 0, so the objective
value equals the original edge-weight sum. Existence: whenever G has a
k-matching (guaranteed: k comes from greedy's own matching), the extension
above exhibits a perfect matching; the augmented graph therefore always has
one, and "no perfect matching found" is treated as a hard solver failure.

Blossom algorithm: a maximum-weight perfect matching implementation for
general graphs based on the primal-dual (blossom) method, implemented in this
experiment in pure Python standard library (no NetworkX, no SciPy, no external
process, no network, no GPU, no new packages). Complexity of the formulation is
polynomial; that fact is NOT evidence about this implementation's runtime - the
measured gates in S.7 decide deployability.

### S.4.1 Numerical policy (fixed before implementation)

- No rounding or quantisation of P_hat. Each float weight is converted EXACTLY
  to its binary rational via `float.as_integer_ratio()`; all weights of one
  state are scaled to exact Python integers with a common power-of-two
  denominator (multiply by 2^(Q - q_i), Q = max q_i). The blossom solver runs
  on these exact integers: zero tolerance, zero epsilon, exact comparisons.
- Deterministic tie-breaking WITHOUT altering the primary objective: rank the E
  edges by canonical order (u, v) with u < v; tie weight t_i = 2^(E-1-i)
  (i = 0 is the first edge); combined integer weight C_i = N_i * B + t_i with
  B = 2^E; dummy edges get C = 0. Because total tie weight over any edge set is
  < B, maximising sum C first maximises the exact primary sum N, then among
  primary optima maximises sum t. Binary tie weights make sum t unique per
  edge SET, so the optimal set is unique and equals the lexicographically
  smallest primary-optimal k-matching under the canonical edge order - the same
  documented tie policy as the old `fc_matching.py`. No floating-point
  perturbation is used anywhere.
- The solver minimises the negated combined weights via a min-weight perfect
  matching routine (exact integer arithmetic); negation is exact.

## S.5 Candidate policy contract (fixed before implementation)

New file `policy_candidate.py` in THIS directory (the parent candidate is
reference only). Contract:

1. CLI: accepts and ignores `--baseline greedy|no_asks|random` (evaluate.py
   always appends it; file identity selects behaviour).
2. Ask phase: `kit.baseline_asks(state)` verbatim - identical to greedy.
3. Match phase: edges from the copied `sr_features.build_feasible_edges`;
   k = len(kit.baseline_match(state)) on the SAME state; P_hat per edge from
   the frozen artifact (hash-verified at import); exact-k selection by the S.4
   solver; pairs emitted in the solver's canonical order; all simulator and
   repeat-pair restrictions preserved by construction (edges are the feasible
   set, matching is vertex-disjoint).
4. NO FALLBACK: there is no greedy-fallback branch. Any solver failure
   (precondition violation, no perfect matching, exception) writes a diagnostic
   to STDERR and exits non-zero, failing the episode loudly. Silent greedy
   substitution is forbidden.
5. Deterministic: identical state => identical pairs (no RNG, no clock
   dependence in the decision path).
6. Protocol-clean: response is exactly {asks|pairs, memory}; no
   instrumentation fields leak into stdout; instrumentation (env
   `SRS_INSTRUMENTATION_DIR`) appends one JSON line per match invocation to a
   separate file: {day, n_edges, k_greedy, k_chosen, solver_seconds,
   invocation_seconds, pid}.
7. Standard library + repo-root `kit.py` + copied `sr_features.py` /
   `sr_policy_core.py` only.

## S.6 Correctness gates (C-series; any failure blocks the final evaluation)

- C1 brute-force battery: >= 10,000 independently generated small-graph cases
  (documented generator seeds; n <= 14 vertices, m <= 40 edges, k drawn across
  0..floor(n/2) plus deliberately infeasible k values), each checked against
  exhaustive enumeration of ALL size-k vertex-disjoint edge sets by OBJECTIVE
  VALUE (not cardinality alone). Case families required: empty graphs; k = 0;
  infeasible edge sets; odd/even n; isolated vertices; sparse and dense;
  equal-weight edges with multiple optima; zero and near-zero weights; very
  close float scores differing in the last bits; graphs where a locally
  highest-weight edge blocks a better total; graphs with no matching of the
  requested cardinality. Zero objective mismatches allowed.
- C2 determinism: repeated solves of the same case (and of every benchmark
  state, S.7) return identical edge sets; primary objective unchanged by
  tie-breaking (verified: reported primary sum equals brute-force optimum).
- C3 structure: every returned matching has exactly k edges, no repeated
  vertices, every edge present in E; augmented-graph extraction returns only
  original-original edges.
- C4 tie policy: on cases with multiple primary optima the returned set equals
  the lexicographically smallest primary-optimal set (checked against
  enumeration's lex-smallest optimum).
- C5 cross-check with old solver: on the same generated small graphs (where
  `fc_matching.solve_exact_k` completes) AND on recorded benchmark states where
  the old solver previously completed, both solvers must return the SAME edge
  set (both implement the same documented lex-smallest tie policy). Agreements
  and disagreements are both recorded; every disagreement must be explained in
  the run log before C5 can pass.
- C6 exact-k from greedy: on every benchmark state (S.7), k = greedy's
  cardinality and the solver returns exactly k edges. Zero violations.

Machine-readable output: `results/solver_validation.json` with per-family
counts, seeds, any failing case IDs, and pass/fail per gate.

## S.7 Benchmark corpus (R-series; fixed BEFORE any new-solver timing)

Corpus selection is frozen at pre-registration. Selection rules, in order,
applied to the recorded parent-experiment state corpus
(`../round2_stagewise_reward/data/states/seed_*.jsonl`, 180,000 rows = 500
seed groups x 6 variants x 60 days):

- R-A: ALL 3,000 day-0 states (every seed group x variant), reconstructed from
  the initial simulator state (no replay needed).
- R-B: ALL recorded states with `n_edges >= 40` at any day (dense tail;
  identified from the recorded `n_edges` field without running the new solver;
  count recorded when materialised).
- R-C: the FIXED 53-state stress set from the parent solver audit
  (`../round2_stagewise_reward/results/solver_validation.json`,
  v4_dense_timing: GLOBAL top-50 by n_edges + 3 zero-edge day-0 states),
  replayed to their recorded (seed_group, variant, day).
- R-D: a uniform random sample of 3,000 of the remaining non-day-0 states,
  drawn with `random.Random(20261014)` over the sorted
  (seed_group, variant, day) list - typical-case coverage.

This corpus is fixed now and is biased toward HARDER (denser) states than the
natural distribution; it may not be reduced or replaced after timing begins.
States are reconstructed by replaying the GREEDY trajectory (in-process
`kit.baseline_asks` / `kit.baseline_match` / `sim.advance`) to the recorded
day; a replayed state must reproduce the recorded row's `n_edges` and
`k_greedy` exactly or the state is excluded and reported (reconstruction
failures are counted, never silently dropped).

For every corpus state we measure BOTH:
- solver-only time (exact-k routine on the state's edges and frozen P_hat
  weights, recomputed by the candidate's own scoring path), and
- END-TO-END match-phase invocation time: a real subprocess
  `python policy_candidate.py --baseline greedy` fed the state JSON on stdin
  exactly as evaluate.py does, wall-clock from process spawn to full response
  (includes interpreter startup and frozen-model scoring).
Weights are always recomputed from the frozen artifact by the candidate's own
code; recorded `edge_priorities` are used only for state-identity checks, never
as solver input.

Machine-readable output: `results/runtime_benchmark.json` + corpus manifest
`results/benchmark_corpus.json` (state IDs, selection rule per state,
reconstruction status).

### Runtime gates (R-gates; thresholds may not change after timing begins)

- R1 solver-only time < 3.0 s on EVERY corpus state (strict maximum).
- R2 end-to-end match-phase invocation < 3.0 s on EVERY corpus state.
- R3 zero solver failures, zero exceptions, zero malformed outputs, zero
  node-limit aborts (the solver has no node limit; any non-termination would
  surface as R1/R2 breach), zero invalid matchings (C3 checks), zero silent
  fallbacks (the fallback branch does not exist - S.5.4).
- R4 every invocation is far below the evaluator's hard 10 s limit (implied by
  R2; stated explicitly).
- R5 runtime dependencies are standard library + repo-root kit.py only
  (verified by import inspection).
Report p50/p95/p99/max for both measurement layers, edge/vertex distributions,
reconstruction failures, and C6 violations. If ANY R-gate fails: produce the
diagnostic report and STOP without running the final evaluation.

## S.8 Pre-evaluation policy validity gates (P-series)

- P1 greedy parity: candidate asks equal `kit.baseline_asks` output on every
  benchmark state; candidate k equals `len(kit.baseline_match(state))` on
  every benchmark state (C6 restated at the protocol level).
- P2 protocol conformance: every emitted response passes evaluate.py's
  `validate_response` shape (exactly {asks|pairs, memory}; pair arity 2;
  memory pass-through; sizes < 1 MiB), verified on all benchmark states plus
  the parent pilot seed group 40001 (6 episodes, smoke only, excluded from all
  claims).
- P3 determinism end-to-end: repeating any benchmark invocation yields
  byte-identical response JSON.
- P4 frozen-artifact hash verified immediately before AND after the final
  evaluation; recorded in the run log.
Machine-readable output: `results/policy_validity.json`.

## S.9 Final paired sequential evaluation (E-series; gated on C+R+P)

Runs ONLY if every C-, R- and P-gate passes. Seeds 70001-70101 range is
70001-70100 (100 seed groups, verified untouched at pre-registration: no data
file for any 70xxx seed; parent sealed check d2 scanned all 1,602 data files
and found no 70xxx row; no evaluation outputs exist).

- Arms: (1) official greedy baseline via the untouched `policy.py` default;
  (2) candidate `research/round2_stagewise_reward_solver/policy_candidate.py`.
- Interface: the evaluator's official CLI, unmodified:
  `python evaluate.py --policy <file> --seeds 70001,...,70100 --variants all
  --output <this-dir>/results/eval_<arm>.json` (trusted-local subprocess mode,
  10 s per-invocation limit enforced by the evaluator itself).
- Both arms cover all six official variants
  (development, sparse, cold_start, delayed, shift, drift) x 100 seed groups =
  600 episodes each; identical seed/variant cells in both arms.
- Instrumentation env var set for the candidate arm only; instrumentation
  files are evidence, never protocol output.
- No tuning of weights, thresholds, constraints or solver behaviour after any
  evaluation outcome is observed. If the candidate times out, crashes, emits
  an invalid action, or violates a pre-registered gate during evaluation: the
  failure and the consumed seeds are recorded, those seeds are NOT described
  as untouched afterwards, no greedy substitution is made, and the experiment
  stops with the corresponding decision.
- Per-state cardinality equality (candidate vs greedy IN THE SAME STATE) is
  audited from instrumentation (k_chosen == k_greedy on every match
  invocation). Total episode introduction counts are reported separately and
  MAY legitimately diverge between arms (different earlier pairs change future
  trajectories); divergence is never itself a violation.

### Primary metric and statistics (fixed before evaluation)

- Per episode: `msmi_per_100_arrived_members` from evaluate.py's own metrics.
- Per seed group per arm: unweighted mean over the 6 variants.
- Primary quantity: paired difference d_g = candidate_g - greedy_g for each of
  the 100 seed groups; point estimate = mean(d_g).
- 95% CI: paired bootstrap over seed groups (resample the 100 d_g with
  replacement; B = 10,000; RNG `random.Random(71001)`; percentile 2.5/97.5).
  Seed groups - not introductions, not variants - are the sampling units.
- Reported alongside: greedy and candidate primary scores; win/tie/loss counts
  over d_g (tie = |d_g| < 1e-12); per-variant paired means; actual MSMIs and
  arrived members per arm; total introductions per arm (reported as trajectory
  outcome, not as a gate); runtime distributions and solver-failure counts
  during evaluation; number of invalid episodes (must be 0 for the candidate
  arm to be interpretable).
- Explicitly NOT success evidence: AUC, log loss, oracle comparisons, any
  single favourable seed.

### Decision rules (fixed; exactly one decision emitted)

- PROCEED: mean paired improvement > 0 AND the 95% CI excludes 0 AND every
  C/R/P gate passed AND zero invalid candidate episodes AND runtime constraints
  held during evaluation.
- PROCEED WITH CHANGES: the experiment is valid and every gate passed, but the
  result is inconclusive (CI includes 0), OR a specific evidence-backed
  limitation is identified that requires another controlled test.
- STOP / REDESIGN: any correctness, integrity, policy-validity or runtime gate
  fails, or valid results do not justify further investment (e.g. CI excludes
  0 at or below 0).

No threshold in this section changes after any result is observed.

## S.10 Integrity and reproducibility

- `run_log.txt`: plan hash, model hash before/after, copy-source hashes, exact
  commands, generator seeds, every failure and fix, benchmark measurements,
  evaluation status, final statistics.
- Machine-readable outputs: `results/solver_validation.json`,
  `results/benchmark_corpus.json`, `results/runtime_benchmark.json`,
  `results/policy_validity.json`, `results/eval_greedy.json`,
  `results/eval_candidate.json`, `results/paired_stats.json`.
- After all work: `integrity.sha256` over this directory (sorted, unique,
  excluding `integrity.sha256` itself and `__pycache__`), same format as the
  parent seal (64-hex, relative forward-slash paths).
- The parent experiment's seal is verified UNCHANGED with a read-only checker
  (the parent's own `sr_verify.py` is NOT run - it writes into the sealed
  directory).
- Deliverable: `report.md` answering the ten pre-registered questions and
  emitting exactly one decision, explicitly separating (a) mathematical
  guarantees of the formulation, (b) measured behaviour of this
  implementation, (c) frozen-model prediction metrics, (d) realized paired
  evaluation results. Polynomial complexity is never cited as evidence of
  runtime compliance.

## S.11 Standing constraints (restated)

Frozen model and features; candidate changes only matching selection; candidate
matches greedy cardinality in every state; final evaluation cannot start until
all solver and policy-runtime gates pass; final evaluation results are never
used for tuning; no approximate solver this round; no density-threshold
fallback; no second experiment after this one; the candidate is never claimed
competition-approved.
