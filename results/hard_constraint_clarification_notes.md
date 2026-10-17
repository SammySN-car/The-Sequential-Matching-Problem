# Hard-Constraint Clarification Prioritization - Protocol and Results Note

This note documents a completed post-snapshot paired experiment, added to the Round 2
submission on 17 October 2026. Nothing executable in this package changed: `policy.py`,
`kit.py`, `evaluate.py`, `Dockerfile`, the tests and the six submitted result JSONs are
byte-unchanged, so all previously recorded official evaluation, container and clean-checkout
evidence remains applicable as recorded. The public record for the experiment is this note,
the machine-readable `results/hard_constraint_clarification_summary.json`, and the REPORT.md
section 9 subsection; the full frozen artifacts (protocol, candidate code, per-key run
records, ask logs) remain in the research workspace referenced there.

## 1. Hypothesis and rationale

The optimizer's daily hard-constraint clarification budget (a small ask allowance against
hard-unknown pair constraints) is spent by `baseline_asks` in eligibility/coverage order.
The experiment tested whether re-allocating the same budget by an observable
"potential-opportunity unlock" score - prioritizing eligible members whose clarification can
convert candidate pairs into fully observed pairs - improves realized MSMI per 100 arrived
members over the same episodes. Matching, acceptance behavior, budget rules and the
evaluator were untouched; the candidate differs only in which eligible member receives each
clarification slot.

## 2. Candidate rule (frozen before any confirmatory key)

An eligible member is exactly a member satisfying the `kit.baseline_asks` criteria on
observed state (available; at least one hard-unknown counted pair; no hard decline). Each
eligible member is scored by the number of its counted pairs that would become fully
observed if it answered ("unlock"), tie-broken by all its counted pairs ("inform"), then by
state index; slots fill by marginal (unlock, inform, index); selection stops when no
eligible member remains; any leftover slot fills in greedy order. Daily ask counts are
therefore identical to greedy by construction, and the policies can differ only in
recipient selection.

## 3. Observable-information and legal-information audit

Only observable state is used: no hidden truth, no future knowledge, no seed-specific
constants; unknown is never treated as compatible, and declined is never overridden or
imputed. No learned model and no memory across episodes. Matching and acceptance behavior
are the unmodified `kit` implementation and budget bookkeeping is unchanged. The
instrumented greedy arm was proven action-digest identical to the shipped official policy
(pilot gate G1: 18 keys; confirmatory spot-check: 6 keys at seed 120001).

## 4. Frozen protocol, seeds and amendment A1

The protocol (`research/hard_constraint_clarification/PROTOCOL.md`) was frozen
2026-10-16 16:35 IST before any confirmatory key, locking endpoint, gates, verdict rules and
seed ranges (SHA-256 `70640992...`). Confirmatory seeds are 120001-120100 (verified unused
before the freeze); the 3-seed pilot (119001-119003) is excluded from the endpoint.

Run 1 (`results/progress_confirmatory.jsonl`) was invalidated by a single episode:
`unlock__120047__development` had its day-0 policy invocation exceed the evaluator's
absolute 10 s limit during a host-load window (environmental; the identical episode passed
in isolation on the idle host). The runner halted at 672 recorded keys (1 invalid).
Amendment A1 (PROTOCOL.md section 13) records this and applies the frozen recovery rule: a
full both-arms x all-seeds rerun with mechanics-only changes (runner phase alias; analyzer
`--phase`), with the hypothesis, endpoint and decision rules unchanged. The final rerun
(`results/progress_confirmatory_rerun.jsonl`, SHA-256 `cb26d8f3...`) completed clean:
1206/1206 keys, 0 invalid.

## 5. Sample and validity

100 paired seed groups x 6 scenario variants x 2 arms = 1200 episodes, plus a 6-key official
spot-check at seed 120001 (parity PASS). Coverage 100/100 paired groups; invalid episodes
in the final rerun: 0.

## 6. Primary result (complete final rerun)

Endpoint: mean over 100 seed groups of the equally weighted six-variant mean of
`msmi_per_100_arrived_members`. Confidence interval: percentile bootstrap, B=10000,
seed 20261016.

| Metric | Value |
|---|---:|
| Greedy, instrumented baseline | 0.35583 |
| Opportunity-unlock candidate | 0.33833 |
| Paired difference (candidate - greedy) | -0.01750 |
| 95% confidence interval | [-0.06750, +0.03250] |
| Paired seed groups | 100/100 |
| Invalid episodes (final rerun) | 0 |
| Group directions (win / tie / loss) | 35 / 20 / 45 |

Per-variant paired differences (candidate - greedy): cold_start +0.085, delayed +0.005,
sparse -0.015, drift -0.045, development -0.050, shift -0.085 - only the first two are
non-negative.

## 7. Budget parity and intervention audit (confirmatory scope)

Both arms spent identically over the 600 paired episodes: 116,745 budget units, 38,915 asks
and 18,572 distinct recipients per arm; ask-days, daily ask counts and daily spend are
identical on all 11,255 ask-days, and all 600 episode pairs have equal ask totals and equal
spend. At day level the allocation differed: of the 11,255 ask-days, 1,726 (15.3%) selected
identical member sets in identical order, 517 (4.6%) the same set in a different order, and
9,012 (80.1%) different member sets. Of the 68,475 member-day decisions taken by either
arm, 59,120 (86.3%) were taken by only one arm. In every episode the two arms eventually
asked exactly the same member pool (each member asked at most once per episode;
episode-level recipient sets identical in 600/600 episodes; per-episode action digests all
differ). The intervention actually tested is therefore a day-level re-allocation/timing
change within a fixed final askable pool - not a change of which population is ultimately
asked - and the conclusions are limited accordingly.

Scope note: the analyzer's pooled "asks" block also includes the 3-seed pilot logs (618
episodes per arm, 40,038 asks, 19,102 recipients, 120,114 spend); the confirmatory-only
figures above supersede those for reporting, and the experiment report in the research
workspace quotes the pooled diagnostics.

## 8. Interpretation, limitations and verdict

Frozen verdict: **INCONCLUSIVE**. The point estimate is negative but the confidence interval
spans zero: this is not a statistically established improvement, not an established
degradation, and not evidence that clarification prioritization can never help. No causal
claims are made from exploratory diagnostics; the candidate is not promoted; the validated
greedy default remains the submitted policy. Limitations: true effects smaller than roughly
the observed interval half-width (~0.05) cannot be resolved at this sample size;
variant-level intervals are descriptive; the result is specific to this simulator, these
seeds and this rule; and, because both arms ask the same final member pool, the experiment
speaks to day-level prioritization of the askable pool only.

## 9. Provenance (SHA-256, original research workspace)

| Artifact under `research/hard_constraint_clarification/` | SHA-256 |
|---|---|
| `PROTOCOL.md` (frozen 2026-10-16 + amendment A1) | `7064099242a04134bf239db8e0696f0d7c3db8e9cf42cb71edc407a832524767` |
| `candidate_policy.py` (candidate + instrumented greedy clone) | `1a8cc00da5b5844a545424962ed8b96212fb1215b10d295593d51721af4fa694` |
| `run_experiment.py` | `e67981703f1c6697481cafafcc7ebdec7e492099de77e8456c8bf74448871ba4` |
| `analyze_results.py` | `9ca795b1a3ff342a4ef1de6d26019b2881f6cd8df009c8372e31bab901cdf8b5` |
| `results/progress_confirmatory_rerun.jsonl` (official rerun records) | `cb26d8f32045e64e11cfb4a079aaf3ca2182816faa61f364ff18c3ce21264f79` |
| `results/analysis_confirm.json` (frozen analyzer output) | `278ebb03a022e9f0a823b4733155c1f00de2b0f6f384ef3d2dccf9dd0ee074c2` |
