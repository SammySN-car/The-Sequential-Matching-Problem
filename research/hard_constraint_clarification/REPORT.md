# Report - Hard-constraint clarification allocation (unlock priority)

Round 2 research experiment, isolated under `research/hard_constraint_clarification/` in the
original repository. No submission folder file, branch, commit, result artifact or sealed
experiment was touched (submission backup stayed at `7288f6c`, verified read-only).
Protocol: `PROTOCOL.md`, frozen 2026-10-16 16:35 IST before any pilot episode. Ledger:
`PROGRESS.md`. Machine results: `results/analysis_confirm.json`.

## 1. Prior-work overlap check (audited 2026-10-16 before design freeze)

- **REL** = `research/e3_rel_experiment/` (the four SOFT fields, `design.md:48`); it
  explicitly excluded this hypothesis: "no hard-ask redesign (hard logic stays
  `baseline_asks`)" (`design.md:227`); verdict INCONCLUSIVE - keep greedy; seeds 119-142.
- No experiment named "selective clarification" exists in the repository.
- The proposed mechanism already exists as `policy.py::ac_asks` tier 1 (`policy.py:351-369`,
  `(-blocked, member_id)` ordering; spec `2026-10-06-a-plus-c-policy-design.md:70-72`) but was
  measured only **bundled**: A+C arm (`results/ac.json`, seeds 101-103, model + floor + soft
  asks vary together), promotion replay (seeds 107-118), stage 1.5 counterfactual on seed 101
  only (`round2-stage1.5-findings.md`: total feasibility 273 = 273, member overlap 11.7%,
  listed UNKNOWN #6), and the ask-coverage audit (`research/ask_coverage_audit_package.zip`,
  "same cumulative feasibility 273 = 273", "NOT SUPPORTED" on feasibility, "DO NOT RUN G+" =
  ask *volume* expansion). Tournament m29/m30 capped hard asks and prioritized soft asks -
  a different intervention; both screened out.
- **Precise distinctions (why this run is informative):** (D1) a clean single-variable pair -
  unlock-prioritized constraints-only asks vs `kit.baseline_asks` with byte-identical greedy
  matching, no model, no soft asks, identical daily ask count - has never been run; (D2) all
  prior probes measured cumulative *feasibility*, not realized MSMI on the six-variant
  competition metric (feasibility parity does not imply timing parity: per-day values differed
  on 124/360 days); (D3) prior evidence = 1 seed or bundled arms, this = 100 paired groups x
  6 variants on provably fresh seeds. No G+ violation: ask volume is unchanged by construction.

## 2. Exact clarification policy change

Only the **recipient order** of the daily `field: constraints` clarification changes.
Eligible set = exactly `kit.baseline_asks` criteria (`kit.py:205-207`: available AND >=1 HARD
field None AND no HARD declined). A pair is counted only if both available, not previously
introduced, neither side has a declined HARD field (declined answers are never revealed -
`kit.py:114,127`), and `kit.eligibility` status is `needs_clarification` (no observed hard
failure). `unlock(m)` = counted pairs whose partner has all 11 HARD fields observed;
`inform(m)` = all counted pairs. Selection: argmax (|unlock minus covered|, |inform minus
covered|, -state index), covered set prevents double counting (pairs are reciprocal), stop at
zero potential, then leftover slots filled in greedy state order - so the per-day ask count
equals `min(floor(budget/3), |eligible|)` exactly as greedy's. Match phase =
`kit.baseline_match` verbatim; memory passthrough; costs/budget identical (3/day-budget
accounting unchanged: 12/day, kit.py:107,122,189). Implementation:
`candidate_policy.py` (17 unit tests; selector at `hcc_asks`/`selection_trace`).

## 3. Observable-information and leakage audit

- Input = only the official `request.state` (POLICY_INTERFACE fields); no hidden simulation
  values, no learned model (`test_source_has_no_truth_or_model_access` greps the source for
  truth/model/propensity tokens), no RNG in the selector, no cross-episode memory.
- Unknown never treated as compatible: `unlock` requires an all-11-observed partner;
  observed hard failures exclude pairs from both scores; unknown pairs contribute only to
  `inform` = potential (never feasibility). Declined never treated as missing-to-reveal and
  never overridden: declined members are never asked (eligibility filter) and declined-partner
  pairs are never counted as potential (`test_declined_partner_pair_not_counted_as_potential`).
- Confirmation answers are same-day observable (`evaluate.py:85-97` resolves asks before the
  fresh `observe()` feeding matching); the candidate reads that updated state exactly as the
  official policy does. Same-day timing equal for both arms.

## 4. Pilot: correctness and runtime (excluded from confirmatory)

Pilot = seeds 119001-119003 x 6 variants x 3 arms = 54 episodes + 2 replay keys; gates per
frozen section 8, recorded in `PROGRESS.md`:

| Gate | Result |
|---|---|
| G1 parity official<->instrumented greedy | PASS (0 digest mismatches; e.g. `c109364072` on 119001/development, metrics equal) |
| G2 determinism replay (2 keys) | PASS (identical digests + headline metrics) |
| G3 validity | PASS (54/54 + 2/2 valid, evaluate exit 0 everywhere) |
| G4 budget legality (all logged ask days) | PASS (n_asks = min(floor(b/3), n_eligible), spent <= budget in [0,12], fields all `constraints`) |
| G5 intervention active | PASS (day-0 ask lists diverge on identical states; positive priority traces present) |
| G7 runtime projection | PASS (means 16.28/16.47/16.98 s per episode -> 5.49 h projected, ETA 2026-10-16 22:25 <= 2026-10-17 18:00 cutoff) |
| G8 unit suite | PASS (71 tests: 17 candidate + 17 runner + 16 gates + 21 analysis) |

One pre-pilot wiring bug was found and fixed before any gate ran (evaluate's output key is
`episodes`, `evaluate.py:162`); the single bogus progress line was deleted and noted in the
ledger - no protocol change, no outcome inspection.

## 5. Confirmatory sample and paired results

Completed: 100/100 paired seed groups (120001-120100) x 6 variants x 2 arms = 1200 valid
episodes (0 invalid) plus the 6-key official spot-check (parity PASS). The first confirmatory
attempt (run 1) halted on one invalid episode; per PROTOCOL.md section 13 amendment A1 it was
replaced by the full both-arms x all-seeds rerun, and every number in this report comes from
that rerun (`results/progress_confirmatory_rerun.jsonl`, finished 2026-10-17 07:56 IST, clean
exit, 0 invalid, executed 1191 + resumed 15 = 1206 keys).

Primary endpoint (mean over 100 seed groups of the equally weighted six-variant mean of
`msmi_per_100_arrived_members`, paired by seed; 95% percentile bootstrap CI, B=10000,
seed=20261016; `results/analysis_confirm.json`):

| arm | score |
|---|---|
| greedy (instrumented clone) | 0.35583 |
| unlock candidate | 0.33833 |
| paired delta (unlock - greedy) | **-0.01750** |
| 95% CI | **[-0.06750, +0.03250]** |

Group-level direction: 35 positive / 20 ties / 45 negative of 100 paired groups.

**Verdict: INCONCLUSIVE** (frozen section 10 rules). Reasons emitted by the frozen analyzer:
point estimate -0.01750 not positive; only 2/6 variant-level deltas >= 0. The experiment is
mechanically valid (coverage 100/100, 0 invalid, spot-check parity PASS, budget parity
confirmed); the verdict reflects the data, not a defect.

## 6. Variant-level outcomes and confidence interval

Descriptive only; the primary endpoint is the pooled delta in section 5.

| variant | greedy | unlock | delta | 95% CI (descriptive) |
|---|---|---|---|---|
| cold_start | 0.310 | 0.395 | +0.0850 | [-0.0150, +0.1850] |
| delayed | 0.460 | 0.465 | +0.0050 | [-0.0900, +0.1000] |
| sparse | 0.120 | 0.105 | -0.0150 | [-0.0600, +0.0300] |
| drift | 0.415 | 0.370 | -0.0450 | [-0.1350, +0.0450] |
| development | 0.435 | 0.385 | -0.0500 | [-0.1400, +0.0450] |
| shift | 0.395 | 0.310 | -0.0850 | [-0.1900, +0.0150] |

Intervention-delivery diagnostics (ask logs) confirm the design constraints held: both arms
spent identically (total 120114 budget units; fraction 0.2699; 40038 asks to 19102 distinct
recipients each; mean 1.08 asks/day). The candidate therefore changed only recipient ordering,
never budget volume - matching PROTOCOL.md sections 3 and 5. Potential diagnostics (unlock
arm): summed potential-inform pairs 680,307; summed potential-unlock pairs 130,541 at ask
days. Mutual acceptances per episode were near-identical (10.40 greedy vs 10.45 unlock);
coverage means 0.3340 vs 0.3349.

## 7. Limitations and verdict

Limitations (pre-stated, `PROTOCOL.md` section 12; all still apply): seed freshness rests on
self-reported records; variant CIs are descriptive; the heuristic was designed against this
simulator; instrumented-greedy parity is proven on 18 pilot + 6 spot-check keys; the bootstrap
assumes independent seed groups; diagnostics are exploratory; prior evidence predicted a small
or zero effect. The observed CI half-width (~0.05) means any true effect smaller than roughly
0.05 MSMI/100 cannot be resolved at this sample size. The early-week timing window, imperfect
conversion of potential-unlock pairs into realized MSMIs, and greedy-order fill dilution
remain the plausible mechanisms behind the slightly negative point estimate.

_Verdict (frozen section 10): **INCONCLUSIVE** - point estimate not positive (-0.01750); only
2/6 variant deltas >= 0 (promising required >= 4); CI spans zero. A negative point estimate is
reported here as evidence against the hypothesis, and still carries no stronger claim than
INCONCLUSIVE. No STOP conditions arose: 0 invalid episodes in the rerun, spot-check parity
PASS, budget legality confirmed, coverage 100/100._

## 8. Recommendation - fallback status

**The greedy submission remains the recommended fallback; no candidate is promoted.** Per
frozen section 10, even a PROMISING verdict would not be approval to replace greedy; the
observed verdict (INCONCLUSIVE, negative-leaning) leaves the submission position unchanged.
The unlock-ordering hypothesis is not supported at this scale and is recorded for the public
record as a null/negative result.