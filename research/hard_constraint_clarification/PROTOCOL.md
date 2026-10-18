# FROZEN PROTOCOL - Unlock-priority hard-constraint clarification allocation (HCC)

**Frozen: 2026-10-16 16:35 IST (Asia/Kolkata) - before any pilot episode was run and before
any confirmatory seed was generated.** Status: FROZEN. After freezing, changes may only be
appended as dated entries in section 13 (append-only; legality / correctness / runtime
issues only; never informed by observed outcomes). The confirmatory evaluation is defined
exclusively by this file as it stands at launch.

## 1. Hypothesis and rationale

Hypothesis: allocating the daily hard-constraint clarification budget (12/day, constraints
ask = 3, so max 4/day; kit.py L107, L122, L189) to members ranked by a deterministic,
observable-only *potential-opportunity unlock score* changes realized MSMI relative to the
existing greedy first-N-eligible allocation (kit.baseline_asks, kit.py L205-L208), with
matching and every other decision held identical.

Rationale: clarification answers are revealed the same day (kit.py L125-L132) and are
observable to matching the same day (evaluate.py L85-L97 resolves asks before the fresh
observe() that feeds the match phase). Prior audits show the eligible pool empties by about
day 21, so allocation can only matter through early-week timing of feasible pairs. MSMI
requires introductions early enough for date responses (1-7 d), date delays (1-14 d) and two
on-time intentions inside the scoring windows, so earlier feasibility could plausibly convert
to MSMI even at identical cumulative feasibility. This is a hypothesis, not a conclusion;
existing evidence has not established a reliably superior policy.

## 2. Prior-work overlap check (audited 2026-10-16 by background audit + direct reads)

- REL = the four SOFT fields experiment (research/e3_rel_experiment/design.md:48); it
  explicitly excluded this hypothesis - "no hard-ask redesign (hard logic stays
  baseline_asks)" (design.md:227); verdict INCONCLUSIVE - keep greedy (report.md:5); seeds
  119-142 consumed. No overlap.
- No experiment named "selective clarification" exists anywhere in the repository; the phrase
  only appears in the policy.py ac_asks docstring (policy.py:334-336).
- The proposed MECHANISM already exists as ac_asks tier 1 (policy.py:351-369): constraints
  asks ordered by (-blocked, member_id), where blocked counts hard-complete partners whose
  pair is needs_clarification (spec: docs/superpowers/specs/2026-10-06-a-plus-c-policy-design.md:70-72).
  It was measured only bundled: A+C arm (results/ac.json, seeds 101-103; model scoring + soft
  ask floor + ac matching vary together, rank 3/4, ask cost 419.4 vs 206.7), promotion replay
  (research/round2_promotion_fresh_seeds/, seeds 107-118, same bundle), stage 1.5
  counterfactual probe on seed 101 only (research/round2_stage1_5/probe.py; findings:
  docs/superpowers/round2-stage1.5-findings.md: total feasibility gains 273 = 273 for both
  ask styles, cost/gain 8.81 vs 8.15, member-level overlap 11.7%, listed as UNKNOWN #6 -
  member-level ask targeting value), and research/ask_coverage_audit_package.zip
  (AUDIT_REPORT.md: same cumulative feasibility 273 = 273, per-day values differ on 124/360
  days, verdict "NOT SUPPORTED" on the feasibility endpoint, "DO NOT RUN G+" = hard-field ask
  VOLUME expansion).
- Tournament: only m29_uncertainty_aware / m30_targeted_info had active asking, and both used
  baseline_asks(state)[:cap] with a soft-ask reserve (hard asks capped at 3/day, SOFT asks
  prioritized) - a different intervention; both screened out (ask cost 307.7/249.2 vs 201.7).
  n03_adaptive_ask_from_feedback was proposed only and never run (research/next_method_search/report.md).

Precise distinctions that make this experiment informative:
- D1 ISOLATION: a clean single-variable pair - unlock-prioritized constraints-only asks vs
  kit.baseline_asks, with greedy matching byte-identical, no learned model, no soft asks, and
  the same daily ask count - has never been run. ac_asks was always bundled.
- D2 ENDPOINT: all prior probes measured cumulative feasibility / frontier, not realized MSMI
  on the six-variant competition metric. Feasibility parity does not imply timing parity
  (124/360 days differed), and MSMI is timing-sensitive.
- D3 POWER: prior evidence = 1 seed (stage 1.5) or bundled arms; this is 100 paired seed
  groups x 6 variants on provably fresh seeds.
- G+ compliance: no ask-volume expansion - the daily ask count per arm-state is identical to
  greedy's by construction (section 3), so the "do not run" list is not violated.
Prior null results are context to overcome, not conclusions to restate; the experiment adds
evidence whichever way it lands.

## 3. Intervention - exact deterministic rule

Eligible member = exactly kit.baseline_asks criteria (kit.py L205-L207): available AND at
least one HARD field is None AND no HARD field is declined. Pair key = sorted (id_a, id_b).
A pair {m,n} is COUNTED for member m iff all hold: both available; pair not in
state.introductions; NEITHER side has a declined HARD field (declined answers are never
revealed - kit.py L114, L127 - so such pairs are permanently unresolvable and are not
potential opportunities); kit.eligibility(a,b).status == 'needs_clarification' (no observed
hard failure, i.e. known incompatibilities respected; missing hard information present).
- unlock(m) = counted pairs where n has ALL 11 HARD fields observed (asking m fully resolves
  the pair's missing information; feasibility is then determined by the revealed values).
- inform(m) = all counted pairs (asking m informs one side; unknown is never treated as
  compatible - inform is potential only, never feasibility).
- Selection loop: while picks < floor(budget_remaining / 3): choose argmax over remaining
  eligible members of ( |unlock(m) minus covered|, |inform(m) minus covered|, -state_index );
  stop when the best is (0, 0); after each pick covered := covered union unlock union inform
  (pair keys are reciprocal, so shared pairs are counted once - no double counting). Then
  fill leftover slots with remaining eligible members in state order = greedy's order.
- Output: only {'member_id', 'field': 'constraints'} asks (cost 3); memory passed through
  unchanged; match phase = kit.baseline_match(state) verbatim.

Guarantees (also unit-tested): deterministic; observable-only; the per-day number of asks in
an arm-state equals min(floor(budget/3), |eligible|) - identical to greedy's rule; budget cap
and cost accounting identical; only recipients differ.

## 4. Observable-information and leakage constraints

Input = only the official request state (public interface fields). No hidden simulation
values, no learned model, no RNG, no cross-episode state (memory passthrough, same as
greedy). Declined is never treated as missing-to-be-revealed and never overridden; unknown is
never treated as known-compatible (unlock requires an all-11-observed partner; observed
failures exclude pairs; unknown contributes only to inform = potential). Enforced by unit
test test_source_has_no_truth_or_model_access and by the pilot's legality gates (section 8).

## 5. Arms and machinery (official evaluator unmodified)

evaluate.py, kit.py and policy.py are NOT modified. Candidate lives only in
research/hard_constraint_clarification/.
- Arm `greedy_official`: python evaluate.py --baseline greedy (policy.py subprocess) -
  pilot G1 reference and confirmatory spot-check on seed 120001.
- Arm `greedy`: python evaluate.py --policy research/hard_constraint_clarification/candidate_policy.py
  --baseline greedy with env HCC_MODE=greedy (runs kit.baseline_asks / kit.baseline_match +
  ask logging). Its actions must be action_sha256-identical to greedy_official (G1).
- Arm `unlock` (the candidate): same script, env HCC_MODE=unlock.
Adapter record: evaluate.py builds [sys.executable, args.policy, '--baseline', <name>]
(evaluate.py:147); the script accepts and ignores --baseline (policy_ac.py pattern); mode
comes from inherited env HCC_MODE; per-decision ask diagnostics go to inherited env HCC_LOG
(a per-key JSONL path). Runner invokes evaluate.py once per (arm, seed, variant) key:
outputs in tmp/, ask logs in logs/, crash-safe progress in results/progress_<phase>.jsonl
(one appended line per completed key; resume skips existing keys; single job at a time).

## 6. Primary endpoint and calculation

- Episode metric: msmi_per_100_arrived_members exactly as computed by the official
  simulator metrics (arrived = arrived_day <= 59; evaluate.py L98-L99, kit.metrics()).
- Per seed group g (one seed, six variants): P_X(g) = unweighted mean of the episode metric
  over the six variants - the competition metric (PROBLEM_STATEMENT: within-family average,
  then equal weight across the six families) restricted to one episode per family.
- Delta(g) = P_unlock(g) - P_greedy(g); point estimate = mean over the 100 groups; 95% CI =
  percentile bootstrap over paired groups, B=10000, RNG random.Random(20261016), quantiles
  2.5/97.5. Arm score = mean_g P_X(g).
- Diagnostics (NEVER primary): per-variant Delta + bootstrap CIs; MSMI counts and rates;
  introductions, mutual acceptances, first dates, second-meeting intentions (episode
  assignments + metrics); coverage; ask recipients, costs, budget fraction (HCC_LOG +
  episode ask_cost / 720); potential unlock/inform counts from logs; invalid/incomplete
  counts; runtime and inference seconds; day-0 ask-list divergence (section 8 G5).

## 7. Seeds, variants, pairing

- Six variants: evaluate.VARIANTS = (development, sparse, cold_start, delayed, shift, drift)
  (evaluate.py:16).
- PILOT (excluded from confirmatory): seeds 119001-119003 x 6 variants x 3 arms = 54
  episodes, plus 2 determinism reruns.
- CONFIRMATORY: seeds 120001-120100 (100 paired groups) x 6 variants x 2 arms = 1200
  episodes, plus greedy_official spot-check on 120001 (6 episodes).
- Freshness evidence (background audit 2026-10-16): consumed register = 7, 8, 9, 21-23, 42,
  81, 95, 101-163, 182, 200, 256, 301-312, 555-557 (planned), 40001-40500, 50000-50799,
  70001-70100, 90200-90299, 20260926, 20261000-20261009, 424242, plus analysis-only RNGs;
  word-boundary greps for 119001 and 120001 across the entire repository returned zero
  matches (candidate ranges 119001-119999 / 120001-120999 confirmed clean).
- Pairing: both arms run identical (seed, variant); worlds and outcome randomness are shared
  by construction (kit.rand_for(seed, a, b, day)); divergence arises only through actions.
- Limitation (section 12): seed history is self-reported in logs; freshness is verified from
  records, which cannot be proven complete.

## 8. Pilot gates - ALL must pass before confirmatory launch

G1 parity: action_sha256(greedy) == action_sha256(greedy_official) on all 18 shared pilot
    episodes (the instrumented clone is action-identical to official greedy).
G2 determinism: rerunning 2 fixed pilot keys reproduces identical action_sha256 + metrics.
G3 validity: 0 invalid episodes across all pilot arms (every evaluate.py exit code 0).
G4 budget legality: parsed HCC_LOG for every ask day shows n_asks == min(floor(budget/3),
    n_eligible), spent == 3*n_asks <= budget_remaining, and budget_remaining in [0, 12].
G5 intervention active: on day 0 (identical states across arms), unlock's ask list differs
    from greedy's on >= 1 of the 18 pilot episodes; unlock's trace contains >= 1 positive
    priority pick somewhere in the pilot.
G6 interface compliance: every response accepted by the official validator (implied by G3).
G7 runtime: measured mean seconds/episode per arm -> projected confirmatory wall-clock; run
    only if projection <= 18 h and completion <= 2026-10-17 18:00 IST with margin for
    analysis and the report.
G8 unit suite: python -m unittest research.hard_constraint_clarification.test_candidate (17
    tests) green, rerun immediately before launch.
Gate results are recorded as a dated pilot-results entry (not an amendment).

## 9. Runtime budget, crash safety, stopping rules

- Single evaluation job at a time; sequential per-key evaluate.py invocations; JSONL progress
  with resume; no unbounded job.
- No new confirmatory key launched after 2026-10-17 16:00 IST if the projection misses
  18:00 IST completion; analysis and report complete by 2026-10-17 21:00 IST (2 h 59 m
  before the 2026-10-17 23:59 IST deadline).
- If coverage is incomplete at cutoff: stop safely, report the partial experiment as
  INCONCLUSIVE with exact counts. No silent protocol changes after seeing results.

## 10. Decision criteria (only these three verdicts)

STOP: any of - G1/G2/G3/G4/G5/G8 failure; candidate reads non-observable information; budget
    violation; any invalid episode during confirmatory (job halted immediately; at most
    INCONCLUSIVE unless a legality-only fix is documented as a section 13 amendment followed
    by a full both-arms x all-seeds rerun with 0 invalids); confirmatory spot-check parity
    (seed 120001) failure.
PROMISING - REVIEW REQUIRED: 100/100 groups completed with 0 invalid episodes in both arms,
    mean Delta > 0, bootstrap 95% CI lower bound > 0, and >= 4 of 6 variant-level mean Deltas
    >= 0. This is NOT approval to replace greedy: the greedy submission remains the
    recommended fallback until independent review.
INCONCLUSIVE: everything else (CI spans zero; coverage < 100 groups; point estimate <= 0;
    any incomplete/invalid run). A negative point estimate is reported as evidence against
    the hypothesis but still carries the verdict INCONCLUSIVE.
Primary endpoint is never replaced by a diagnostic; no variant, seed group or failed episode
is ever dropped silently.

## 11. Failure and invalid-episode handling

The official runner marks an episode invalid on any protocol violation and summarise() is
ineligible if any episode is invalid (evaluate.py L119-L120). Because keys run one episode
each, an invalid episode is detected at its own key, recorded with counts, never dropped,
and triggers the section 10 rule. Crashes resume from the JSONL; final coverage < 100 groups
=> INCONCLUSIVE with exact per-arm counts.

## 12. Limitations and plausible failure modes

- Failure modes: timing effect too small (eligible pool empties ~day 21 - the ordering window
  is early); unlock potential does not convert to mutual acceptance/MSMI; greedy-order fill
  dilutes the intervention (only 4 slots/day); prior probes found feasibility parity - expect
  a small or zero effect.
- Limitations: seed freshness rests on self-reported records; one hypothesis (no multiplicity
  beyond the primary endpoint; variant CIs are descriptive); heuristic designed against this
  simulator (generalization limited); instrumented-greedy parity proven on 18 pilot + 6
  spot-check keys only (by shared code path, not all 1200); bootstrap assumes independent
  seed groups; diagnostics exploratory.

## 13. Amendments (append-only)

(none)
## 13. Amendments (append-only)

### A1 (2026-10-17 00:36:55 IST) - Invalid episode in confirmatory run 1; section 10 recovery path invoked
- Incident: key unlock__120047__development (progress_confirmatory.jsonl line 554/1206) recorded
  valid=false, exit_code=2, error "Policy exceeded 10-second invocation limit" (evaluate.py L45,
  L54-61: absolute 10 s wall-clock cap per policy invocation), empty stderr; the ask log shows the
  day-0 policy invocation never returned. The runner halted immediately per section 10; the hidden
  task's ONCE trigger then auto-restarted it at 23:58:01, resuming past the invalid line - a
  scheduler behaviour, disclosed here; no run-1 key was re-executed. Run 1 was stopped manually at
  672 keys (671 valid, 1 invalid) and is EXCLUDED from the primary endpoint; evidence
  retained read-only: progress_confirmatory.jsonl + logs/invalidated_run1/ (701 ask logs + the
  invalid episode output).
- Root cause (diagnosed before any outcome inspection): environmental host load, not policy
  legality. Neighbouring keys ran 32.5-63.5 s vs the 19 s mean (2-3x slowdown window ~21:45-21:52);
  the paired-arm twin greedy__120047__development took 31.5 s; the identical key rerun isolated on
  the idle host completed exit 0 with episodes[0].valid=true in 18.3 s wall (outcome value not
  inspected).
- Recovery per section 10 (the only sanctioned route past an invalid): full both-arms x all-seeds
  rerun - all 1206 keys, frozen seeds 120001-120100, same six variants, same candidate/evaluate/kit
  code, same frozen analysis formulas - into progress_confirmatory_rerun.jsonl via new runner phase
  'confirmatory_rerun'. Mechanics-only diffs, zero outcome-determining changes: (i) run_experiment.py
  phase table accepts 'confirmatory_rerun' with the identical key list; (ii) analyze_results.py
  gains --phase (default 'confirmatory'). Full test suite green after the diffs (G8 re-verified).
  Study primary endpoint = the rerun; run 1 is reported as the invalidated confirmatory with exact
  counts. Any invalid in the rerun => STOP/INCONCLUSIVE per section 10; no second recovery.