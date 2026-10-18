# Round 2 Design - Gated Maximum-Weight Allocation (PREREGISTERED, FROZEN)

Status: FROZEN before any performance evaluation. Written 2026-10-12.
Changing any constant, rule, seed, or criterion below after evaluation starts
invalidates the experiment. The only permitted post-freeze changes are
documented implementation DEFECTS (stop, document, then fix per plan section 5).

## 0. Pre-change audit (recorded before any file creation)

| Item | Value |
|---|---|
| HEAD | a8e26b35118cfa8e886a02f93984923e43ab64f6 |
| git status | exactly: ` M policy.py`, `?? docs/superpowers/`, `?? policy_ac.py`, `?? research/`, `?? test_policy.py` |
| Frozen Round 1 policy.py | 379cc2d9519e8d3b9295f6c0bf2039e7a1a40d30729f6be0a9dfd17f6fddb47c (MATCHES results/artifact.sha256) |
| Frozen Round 1 policy_ac.py | 90fb9ad306e89bfb3cc11d072c68de7ee3b1667e8709596979d04be41fa56a97 (MATCHES) |
| kit.py / evaluate.py / organise.py | 0d2cb3d3... / d09cc14b... / da9d6b3a... (recorded; never modified) |
| Dockerfile | python:3.12.7-slim; COPY kit.py policy.py; ENTRYPOINT python policy.py; USER 65534; unchanged |
| No-arg `python policy.py` | default mode = A+C (Round 1 integrated policy); empty-state request returns `{"asks": [], "memory": {}}`, exit 0 |
| evaluate.py --baseline | choices frozen: greedy, no_asks, random (cannot add arms via CLI) |

## 1. Organizer questions this design answers

Q1 (observable enablement signal): the exact max-weight allocation is enabled
only when a DETERMINISTIC, OBSERVABLE gate passes on the current feasible
graph (bipartite, node count <= cap, and the exact matching is provably better
than greedy on the existing observable objective without losing cardinality).

Q2 (fixed before evaluation, works unseen): the gate is frozen in this
document before any seed in {301..312} is touched. It contains no thresholds
tuned to results; both conditions are exact comparisons on today's graph.

Q3 (close-this-line criterion): this line of investigation closes if the
gated policy fails to beat greedy on the preregistered primary metric (see
section 5 promotion criteria). A null/inconclusive result means greedy stays.

## 2. Background audit of the previous maximum-weight method (m25)

Source: research/method_tournament/methods_d.py decide_m25 + alloc.py.

- Exact branch: Hungarian/Kuhn-Munkres O(n^3) (E-maxx assignment) when the
  feasible graph is 2-colorable (bipartite) and node count <=
  HUNGARIAN_NODE_CAP = 180.
- Fallback branch: greedy take + one-swap local improvement (documented
  approximation), applied to the ZERO-SCORE-PRUNED edge list.
- m25 pruned zero-score edges before both branches (exact for weight value,
  but it destroys cardinality because zero-score pairs are legal, useful
  introductions that official greedy keeps).
- m25 adopted the exact matching UNCONDITIONALLY (no gate).
- Tournament outcome: eliminated at screening. Rows show the damage pattern:
  seed 143 development: 55 assignments vs control 115 (coverage 0.265 vs
  0.425); sparse: 8 vs 31 assignments. Cardinality collapse, not weight gain,
  was the failure mode.

Conclusion carried into this design: an exact maximum-weight allocator needs
(a) zero-score edges kept in the graph, and (b) an adoption gate that refuses
any allocation that loses cardinality or does not strictly improve the
observable score sum.

## 3. Frozen candidate specification

### 3.1 Shared machinery (arms B and C; arm A is official policy.py greedy)

Ask phase: exactly kit.baseline_asks(state) - identical to official greedy.

Match phase, step 1 (baseline allocation): enumerate available members;
feasible, never-previously-introduced pairs; score each pair with the OFFICIAL
observed-field rule (identical formula to kit.baseline_match: count of
observed equal SOFT fields). Construct the official greedy non-overlapping
matching (sort by (-score, pair_key), take while both members free). Record
K_greedy (pair count) and S_greedy (score sum).

Match phase, step 2 (exact allocation, when available): the exact branch is
attempted ONLY when both hold:
  E1. the feasible graph is bipartite (deterministic BFS two-coloring),
  E2. node count <= HUNGARIAN_NODE_CAP = 180.
Solver: pure-Python O(n^3) Hungarian assignment (Vorobyev/E-maxx formulation;
algorithm attribution: e-maxx.ru English mirror; same formulation as
research/method_tournament/alloc.py hungarian_max_weight, re-implemented
locally so zero-weight real pairs are retained in the output - m25's w>0
output filter is intentionally NOT copied). Returns exact maximum-weight
non-overlapping matching K_exact (includes zero-score pairs), S_exact.

Match phase, step 3 (arms differ only here):
- Arm B (UNGATED ablation): adopt K_exact whenever step 2 ran; otherwise
  official greedy. No gate.
- Arm C (GATED candidate): adopt K_exact ONLY if BOTH:
    G1. len(K_exact) >= K_greedy            (no cardinality loss)
    G2. S_exact > S_greedy                  (strict observable-score gain)
  Otherwise adopt the official greedy matching unchanged.
- Non-bipartite, over-cap, or any solver failure -> both arms B and C use
  official greedy (never a partial or invalid matching).

The gate has NO tunable constants. G1/G2 are exact comparisons on integers.

### 3.2 Explicit interpretation boundary (frozen)

G1+G2 prove only that the adopted allocation improves the existing observable
matching-score objective without reducing the number of introductions. They
do NOT prove higher realized MSMI. Section 5 evaluates that hypothesis
honestly.

### 3.3 What is NOT changed

Clarification policy (baseline_asks), scoring rule, hard-feasibility rules,
memory/latency/protocol constraints, simulator semantics. Arms A/B/C differ
ONLY in the match-phase allocation rule above.

## 4. Arms (5, identical worlds, paired)

| Arm | ID | Implementation |
|---|---|---|
| A | greedy | official: python policy.py --baseline greedy |
| B | ungated_mw | research/round2/policies/mw_alloc.py --arm ungated |
| C | gated_mw (candidate) | research/round2/policies/mw_alloc.py --arm gated |
| D1 | no_asks | official: python policy.py --baseline no_asks |
| D2 | random | official: python policy.py --baseline random |

## 5. Evaluation protocol (frozen)

### 5.1 Seeds and worlds (freshness AUDITED 2026-10-12)

Consumed public eval seeds (excluded): 95, 101-163, 182, 200 (ambiguous,
excluded), 256, 90210-90212, 90290.
- FIXTURE/validation seeds (implementation sanity ONLY, never performance):
  90250, 90251, 90252 (reserved range 90200-90299, unused).
- EVALUATION seeds (performance, paired, never touched before): 301, 302,
  303, 304, 305, 306, 307, 308, 309, 310, 311, 312.
- Variants: all six (development, sparse, cold_start, delayed, shift, drift).
- Worlds: kit.generate(seed, 200, 'evaluation', variant); 12 x 6 = 72 worlds;
  5 arms => 360 episodes. All arms on identical worlds.

### 5.2 Primary metric

Official evaluate.summarise primary score: msmi_per_100_arrived_members,
equally averaged across the six scenario families. Candidate = arm C (gated).

### 5.3 Secondary metrics

Coverage; zero-selection days (per-world fraction of the 60 decision days
with zero pairs); introductions per 100; mutual acceptances per 100; MSMI per
introduction; mutual acceptance per introduction; ask cost; solver
activation frequency (share of match phases where E1+E2 held); gate rejection
breakdown (G1 fail, G2 fail, both pass); score gain when gate adopts;
cardinality change; per-family MSMI differences; inference seconds.

### 5.4 Statistical method (frozen)

Paired per-world differences (same seed+variant), clustered by seed:
mean diff d over 72 worlds; seed-level means (12 values); two-sided t CI,
df=11. Primary CI at 95% (t=2.201); the 99% CI (t=3.106) is also reported.
Wins/ties/losses counted over the 72 paired worlds. Single superiority claim
(gated vs greedy on primary metric) - no multiplicity correction needed for
the single primary claim; the ungated-vs-greedy ablation contrast is
descriptive (labeled as such).

### 5.5 Promotion criteria (all required)

1. Mean paired diff (C - A) > 0 on the primary metric.
2. 95% CI lower bound > 0.
3. Zero invalid episodes across all 360.
4. No catastrophic family degradation: every family's paired mean diff
   >= -0.20 MSMI/100 absolute.
5. Determinism (PYTHONHASHSEED 0 vs 1 vs random: identical action_sha256),
   local/container parity, latency: every invoke < 10 s and episode mean
   invoke < 2 s.

If 1-5 all pass -> promote arm C into policy.py as the submitted default.
If any fails -> keep greedy; report honestly; do not rebrand.

### 5.6 Stopping rule

Run the full grid; no interim performance looks. A genuine implementation
defect (invalid episode) stops the run: document, fix the defect only, hash,
restart the affected worlds from scratch.

### 5.7 Post-freeze prohibitions

No gate edits, no solver edits, no score-weight edits, no method swaps, no
seed-dependent logic, no post-result tuning.

## 6. Validity gates (hard; failure = ineligible)

Full official response schema; ask budget/costs; non-overlap; reciprocal
hard feasibility; no repeat pairs; memory <= 1 MiB; latency < 10 s/invoke;
deterministic under PYTHONHASHSEED in {0,1,random}; pure stdlib; no network;
root regression suites (test_kit, test_runner, test_release, test_policy)
plus research suites stay green; candidate unit tests green; local/container
parity on all 72 gated-arm episodes.

## 7. Diagnostics

Gate telemetry accumulates in policy memory (aggregate counters only, no
per-member data): attempted, bipartite, over_cap, gate_pass, g1_fail,
g2_fail, adopted_exact, sum_score_gain_adopted, sum_card_delta_adopted,
per-day solver seconds max. Memory stays < 1 KiB.

Calibration diagnostic (section 6 of the build spec): the deployed candidate
does NOT emit probabilities; its score is an integer agreement count (0-4)
used only for ranking/allocation. Diagnostic: MSMI conversion by score band
of the introduced pair, with counts and Wilson 95% intervals, collected by a
separate replay pass (never used for tuning). Context: Round 1 model AUC
0.5937 [0.5667, 0.6208], log-loss worse than constant - ranking-only, never
thresholded. No model is trained for this round.

## 8. Freeze / integrity

Frozen at preregistration: this design.md, experiment_plan.json.
After implementation and before eval: SHA-256 manifest of policy.py,
policy_ac.py, kit.py, evaluate.py, organise.py, Dockerfile, .dockerignore,
and every research/round2/ source file (integrity/manifest.sha256). Verified
before and after the run; any mismatch aborts.

## 9. Close-this-line criterion (organizer Q3, frozen)

If promotion criteria fail: the gated-allocation line closes for this
competition. The report will state that optimizing the observable score
objective - even conservatively, even without cardinality loss - did not
convert to realized MSMI on unseen seeds, consistent with the Round 1
autopsy finding (no validated decision-time signal; score-vs-oracle
Spearman 0.12). No successor allocation method will be invented post-hoc
within this round unless time remains AND it was named here in advance:
the only pre-named fallback is "no further allocation-method changes; keep
greedy." (n02/n03/n04 remain excluded per their autopsy verdict.)