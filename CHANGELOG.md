# Changelog

## 1.0.0 - 5 October 2026

- Published the final participant PS, technical ranking, execution limits, schedule and submission route.
- Included 2,000 fully synthetic adults across ten pools with versioned field definitions and checksums.
- Added a JSON policy boundary, local and offline-container evaluation, three runnable baselines and checked reference results.
- Added public question, defect, research and final-submission forms.
- Clarified ownership and the adapter boundary for later Vouchsafe assessment.

This release replaces the unpublished 0.1 development draft. All participant-facing files use schema 1.0.0. Private organiser worlds and production data are excluded.

### Release clarifications - 5 October 2026

- Made probability estimates optional throughout; distinguished directional and joint predictions when reported.
- Stated the exact pair-level MSMI formula and distinct-member coverage denominator.
- Clarified self-validation, conditional organiser feedback, and the deadline freeze even when private assessment occurs later.
- Required an immutable archive URL and SHA-256 as the alternative to a repository commit SHA.
- Aligned event communication with Discord, aligned the README with the existing GitHub Issues submission route.
- Explicitly fixed the evaluator denominator at decision day 59 and made CSV regeneration preserve the published LF line endings. Dataset records, schema and ranking order are unchanged.

### Round 1 schedule and submission-route update - 5 October 2026

- Moved Round 1 research submission to a Google Form; the form link will be released soon through Discord and the submission guide.
- Brought the research deadline forward from 11 October to **9 October 2026, 23:59 IST**.
- Set Round 1 result announcement for **by 11 October 2026, 22:00 IST** and Round 2 start for **12 October 2026**.
- Retained the final build deadline of **18 October 2026, 23:59 IST** and its Final submission issue route.
- Retired the Research submission issue template and aligned the guides and downloadable PDF. Google Form receipt times govern Round 1; the version pinned before the final deadline governs Round 2.
- Published the [public schedule correction](https://github.com/RomeoJulietLove/The-Sequential-Matching-Problem/issues/1) before applying the revised rules.

### Round 2 submission preparation - 16 October 2026

- Corrected the operative final build deadline for this team to **17 October 2026, 23:59 IST**. The 18 October date above and in the supplied `docs/SUBMISSION.md`, `PROBLEM_STATEMENT.md` and `docs/FAQ.md` is the original schedule; those documents remain unmodified.
- Corrected the stale `policy_ac.py` docstring sentence about the container argparse default (it now records that the current default is `greedy` and that the A+C research policy is not the container's default execution path), and completed `REPORT.md` with the report-guide items found missing in pre-submission audit (real-world scope caveat, partial-observation failure mechanisms, per-seed variation). Documentation only: no policy, evaluation, Dockerfile or result-JSON bytes changed.

### Round 2 report update - hard-constraint clarification experiment - 17 October 2026

- Added the REPORT.md section 9 subsection "Hard-Constraint Clarification Prioritization": a post-snapshot pre-registered paired experiment on day-level clarification recipient allocation (100 paired seed groups x 6 variants x 2 arms; final rerun 1206/1206 keys, 0 invalid). Result **INCONCLUSIVE (negative-leaning)**: paired delta -0.01750 MSMI per 100 arrived members, 95% CI [-0.06750, +0.03250], 35/20/45 win/tie/loss, 2 of 6 variants non-negative. The verdict preserves the greedy default.
- Added compact supporting evidence so the result is inspectable inside this repository: `results/hard_constraint_clarification_summary.json` (machine-readable: protocol hashes, sample, scores, interval, variants, budget parity, intervention audit, verdict) and `results/hard_constraint_clarification_notes.md` (protocol/results note: hypothesis, selection rule, legal-information audit, amendment A1 and the run-1 invalid-episode disclosure, intervention audit, limitations, provenance).
- Documentation and supporting evidence only: `policy.py`, `kit.py`, `evaluate.py`, `Dockerfile`, the tests and the six submitted result JSONs are byte-unchanged, so the previously recorded official evaluation, container and clean-checkout evidence remains applicable as recorded; those commands were not rerun.
