# HCC experiment ledger - research/hard_constraint_clarification (untracked research scratch)

## 2026-10-16 pre-flight
- State snapshot: original repo on round2-final-submission @ 0ba7355e1ded2ba04c7273ad13c9c635b8a77bfe, 3 pre-existing untracked entries; NOT modified by this experiment.
- Submission folder HEAD 7288f6ccb3debdcac26ad324c4a79097d7af7fe2 verified read-only, never opened for editing.
- Experiment dir research/hard_constraint_clarification/ did not exist before creation.
- Ruling: adapting executing-plans - plan = the user message (sections 1-9); ledger = this file; NO git commits, NO branch switches anywhere (user section 1). Everything stays untracked under research/.

## Mechanics confirmed (file:line)
- Daily budget: ask_spent resets every day (kit.py L189); budget 12/day, constraints ask costs 3 (kit.py L121) => max 4 constraint asks/day (kit.baseline_asks uses ask_budget_remaining // 3, L208).
- Same-day reveal: evaluate.py episode loop resolves asks (L95) THEN builds the match-phase request from a fresh sim.observe() (L86-L88): clarification answers are observable for matching on the same day.
- HARD = 11 fields (kit.py L9-11); SOFT = 7 fields (L12-13). Constraints ask reveals all non-declined HARD fields (kit.py L125-128); declined fields are NEVER revealed (L114, L127).
- baseline_asks eligibility: available AND >=1 HARD field None AND no HARD field declined (kit.py L206-207); picks first budget//3 in state member order (L208).
- A member with any declined HARD field can never reach eligibility status 'feasible' (eligibility counts None fields as missing, kit.py L74-76, L87; advance requires 'feasible', L151) => permanently unmatchable.
- evaluate.py accepts --policy <path> (L136) and invokes [python, policy, --baseline, <b>] (L147); output schema/summary via summarise() (L118-131); iteration order variant-outer/seed-inner (L149-150); exit 0 iff all episodes valid (L167).
- policy.py greedy: ask -> kit.baseline_asks (L24), match -> kit.baseline_match (L28); argparse default greedy (L602-603).

## Overlap candidate (pending background audit ses_ebbb001baffeWkhfEhREcBDrbO)
- policy.py::ac_asks (L334-409) implements "rule-based selective clarification": tier1 scores members by blocked = count of hard-complete partners whose pair is needs_clarification (L351-364) - numerically the SAME score as the proposed unlock metric. ac_asks was bundled with ac_match (model + score floor) everywhere it was evaluated; isolation with greedy matching is what the audit must confirm has/hasn't been run.

## Rulings
- R1: protocol freeze happens AFTER the overlap/seed audit returns and BEFORE any pilot execution.
- R2: candidate differs from greedy ONLY in ask recipient ordering; eligible set, ask count per day (= min(4, |eligible|) via greedy-order fill of leftover slots), costs, budget cap, and matching (kit.baseline_match) are identical to greedy.
- R3: potential-opportunity metrics exclude pairs with any declined HARD field on either side (permanently unresolvable; declined never revealed) and exclude pairs with observed hard failures (known incompatibilities respected).
- R4: confirmatory baseline arm must be action-identical to official policy.py greedy - pilot gate proves digest equality of the instrumented greedy clone before any confirmatory run.
## 2026-10-16 16:35 IST - PROTOCOL FROZEN (research/hard_constraint_clarification/PROTOCOL.md)
- Background audit returned (session ses_ebbb001baffeWkhfEhREcBDrbO): overlap verdict = distinguishable; REL = soft-field e3 experiment (excluded hard asks explicitly); ac_asks tier1 = same mechanism, never isolated; stage1.5 + ask-coverage audit = feasibility-only prior nulls (273=273, per-day differs 124/360); m29/m30 = different intervention (soft-first, hard cap 3).
- Seed freshness: consumed register inventoried; 119001-119999 and 120001-120999 word-boundary greps = zero hits repo-wide.
- Pilot seeds 119001-119003; confirmatory seeds 120001-120100; bootstrap RNG seed 20261016.
- TDD: RED (ImportError) then GREEN - 17 unit tests pass (candidate_policy.py implements sections 3-4).
- Verified evaluate.VARIANTS = ('development','sparse','cold_start','delayed','shift','drift') (evaluate.py:16); clock 16:31 IST.
## 2026-10-16 17:20 IST - PILOT GATE RESULTS (frozen protocol section 8, dated entry)
- Wiring bug fixed pre-pilot: evaluate output key is `episodes` (evaluate.py:162), not `rows`; the single progress line produced by the buggy parse was deleted (pre-outcome artifact; no protocol change).
- Pilot: 54/54 episodes valid (3 seeds 119001-119003 x 6 variants x 3 arms), evaluate.py exit 0 every key, mean 16.0-17.4 s/episode.
- Replay: 2/2 keys reproduced identical action_sha256 + headline metrics.
- G1 PASS (no digest mismatches; sample: greedy_official == greedy sha c109364072 on 119001/development, metrics equal).
- G2 PASS | G3 PASS (0 invalid) | G4 PASS (budget/count/field legality over all logged ask days).
- G5 PASS (day0_diverged=True, positive_trace=True - intervention active on identical day-0 states).
- G7 PASS: means greedy 16.28 s / unlock 16.47 s / official 16.98 s -> projected confirmatory 5.49 h, ETA 2026-10-16 22:25 <= cutoff 2026-10-17 18:00 (cap 18 h).
- G8 PASS: 50 unit tests OK (17 candidate + 17 runner + 16 gates), re-run immediately pre-launch.
- Verdict: ALL GATES PASS -> confirmatory launch authorized by protocol section 8.
## 2026-10-16 17:45 IST - analyzer built pre-outcome; confirmatory launched
- analyze_results.py implemented test-first against frozen section 6/10 formulas (RED then GREEN; one test fixture corrected pre-implementation: distinct log files, variant delta arithmetic). Combined suite now 71 tests OK (candidate 17 + runner 17 + gates 16 + analysis 21).
- Confirmatory launched 17:25 IST as single background job (shell sh_14476c6c0001zxRnjCmepN0LLW): python run_experiment.py --phase confirmatory = 1206 keys (1200 paired + 6 spot-check), stop-on-invalid default, JSONL resume, no polling.
- REPORT.md drafted with sections 1-4 static (overlap, policy change, leakage audit, pilot gates); sections 5-8 filled mechanically from results/analysis_confirm.json after completion.
## 2026-10-16 19:55 IST - crash + resume (frozen protocol section 9)
- CORRECTION to timestamps above: launch was ~16:57 IST (not 17:25); the background shell was externally reaped at 18:01:29 after ~64 min (harness background lifetime ~1h; no machine-sleep events in 6h; 0 python processes alive at check time 19:46).
- State at death: 243/1206 keys complete, 0 invalid, both arms interleaved through seed 120021, true pace 16.0 s/key (matches in-record means exactly).
- Action per section 9: relaunch with resume (completed keys skipped, append-only progress). No protocol change, no outcome inspection (no analysis run).
## 2026-10-16 20:05 IST - second crash (foreground tool abort) + detached relaunch
- The foreground timeout=0 resume call was aborted by the harness ("Tool execution interrupted"); no sleep events, purely harness lifecycle.
- Per user direction: relaunched as a DETACHED OS process via WMI Win32_Process.Create (runs under WmiPrvSE, outside any harness job/session) using launch_confirmatory.cmd; stdout/stderr -> logs/confirmatory_run.log. Monitoring is no longer coupled to assistant tool calls. PID recorded in chat + below.
- Single-job rule re-verified before launch (zero run_experiment/evaluate processes alive).
## 2026-10-17 00:36:55 IST - run 1 invalid diagnosed (environmental); section 10 full rerun launched
- Line 554 key unlock__120047__development hit evaluate.py's absolute 10 s policy-invocation cap
  during a 2-3x host-load window; identical key passes isolated on idle host (valid, exit 0) ->
  environmental, not a legality defect. Archived: logs/invalidated_run1/ + progress_confirmatory.jsonl.
- Task-Scheduler ONCE auto-restart (23:58) resumed run 1 past the invalid; disclosed in protocol A1;
  run 1 stopped manually at 672 keys and excluded from the primary endpoint.
- Mechanics-only patches (runner phase alias 'confirmatory_rerun'; analyzer --phase) -> 71 tests green.
  Relaunching full both-arms x all-seeds rerun (1206 fresh keys, new progress file, hidden task).
## 2026-10-17 00:56:10 IST - rerun relaunch via wscript-hidden vehicle (user-directed, no windows)
- Vehicle history this night (all disclosed): interactive Task Scheduler actions and WMI-spawned cmd keep
  surfacing a closable console in the user's desktop session; closing it kills the tree (^C evidence in
  rerun_run.log; Last Result 0xC000013A). Those vehicles are retired.
- Final vehicle: task action = wscript.exe (GUI subsystem, no console) -> WScript.Shell.Run(...,0) -> hidden
  cmd -> python -u run_experiment.py --phase confirmatory_rerun. No console attaches to the desktop.
  MultipleInstancesPolicy=IgnoreNew; ExecutionTimeLimit=PT0S.
- Resume point 17/1206; run-1 data untouched (progress_confirmatory.jsonl 672 keys + invalidated_run1 archive).
## 2026-10-17 04:34:01 IST - A1-committed partial summary of the INVALIDATED run 1 (user-requested diagnostic; not a verdict)
- Run 1 (excluded from the study endpoint per A1) summarized with the frozen analyzer machinery
  (same functions as analyze_results.py; BOOT_SEED 20261016, B=10000): 672 records, 1 invalid key
  (unlock__120047__development), 55/100 complete paired groups.
- Descriptive only, NOT the endpoint: mean delta = -0.03030; bootstrap 95% CI [-0.10758, +0.04394];
  groups +18 / -27; per-variant deltas: development -0.06364, sparse -0.01818, cold_start +0.13636,
  delayed -0.03636, shift -0.15455, drift -0.04545.
- By the frozen section 10 rules this partial could support at most INCONCLUSIVE (coverage 55/100,
  and point estimate <= 0). NO decision depends on this summary; the rerun (the study) continues
  unchanged; its file remains sealed until 1206/1206. Disclosed here for transparency.
## 2026-10-17 08:21:54 IST - CONFIRMATORY RERUN COMPLETE; frozen analysis executed; verdict INCONCLUSIVE
- Rerun finished 07:56:14 clean (exit 0): 1206/1206 keys, 0 invalid, greedy 600 / unlock 600 /
  greedy_official 6, spot-check parity PASS, coverage 100/100 paired groups.
- analysis_confirm.json written 08:21 by the frozen formulas (no deviations): greedy 0.35583,
  unlock 0.33833, paired delta -0.01750, 95% CI [-0.06750, +0.03250] (B=10000, seed 20261016);
  per-variant: cold_start +0.085, delayed +0.005, sparse -0.015, drift -0.045, development -0.050,
  shift -0.085 -> 2/6 >= 0; group directions 35/20/45; budget parity exact (120114 spent, 40038
  asks, 19102 recipients each arm).
- Verdict per frozen section 10: INCONCLUSIVE (point not positive; 2/6 variants). No STOP
  conditions. REPORT.md sections 5-8 filled mechanically from the analysis JSON (backup kept as
  REPORT.md.pre_fill.20261017.bak).
- Disposition: greedy remains the recommended submission fallback; nothing is promoted, nothing
  pushed or published. This closes the hard-constraint clarification experiment.