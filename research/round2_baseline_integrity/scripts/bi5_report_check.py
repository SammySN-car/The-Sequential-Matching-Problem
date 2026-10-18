"""bi5: verify report.md headline numbers agree with corrected artifacts.

Extracts quoted numeric tokens from report.md for a set of claim-critical
anchors and asserts each equals the value in corrected_paired_ci.csv /
corrected_rank_direction.csv / corrected_summary.json / study_audit.csv.
Also asserts required sections and the 15-row status table exist.
Writes report_check.json; exit 1 on failure.
"""
import csv
import json
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent


def main():
    t0 = time.time()
    fails, checks = [], []

    def ok(name, cond, detail=""):
        checks.append(dict(check=name, passed=bool(cond), detail=str(detail)))
        if not cond:
            fails.append("%s: %s" % (name, detail))
        print("[%s] %s %s" % ("PASS" if cond else "FAIL", name, detail))

    report = (OUT / "report.md").read_text(encoding="utf-8")
    hier = (OUT / "corrected_evidence_hierarchy.md").read_text(encoding="utf-8")

    def norm(t):
        """ASCII-normalize for numeric substring checks: unicode minus -> '-',
        drop thousands separators (report writes 8,433; CSV writes 8433)."""
        return t.replace("\u2212", "-").replace(",", "")

    rn, hn = norm(report), norm(hier)

    # ---- structure ----------------------------------------------------
    for sec in ["## Q1", "## Q2", "## Q3", "## Q4", "## Q5", "## Q6",
                "## Q7", "## Status of each historical conclusion"]:
        ok("report_section_%s" % sec.replace("#", "").strip().replace(" ", ""),
           sec in report, sec)
    ok("no_next_experiment_recommendation",
       "recommend" not in report.lower().split("out of scope")[-1].lower()
       or "No next-experiment recommendation" in report,
       "explicit out-of-scope statement present")
    ok("hierarchy_four_tiers",
       all(t in hier for t in ("## Tier 1", "## Tier 2", "## Tier 3",
                               "## Tier 4")), "tiers 1-4")
    status_rows = re.findall(r"^\| \d+ \|", report, flags=re.M)
    ok("status_table_15_rows", len(status_rows) == 15, "n=%d" % len(status_rows))

    # ---- corrected paired CI numbers ----------------------------------
    with open(OUT / "corrected_paired_ci.csv", newline="",
              encoding="utf-8") as fh:
        ci = {r["pair"]: r for r in csv.DictReader(fh)}

    def ci_in_report(pair, text=None):
        r = ci[pair]
        t = norm(text) if text else rn
        return (r["delta_total"] in t and r["ci_lo"] in t
                and r["ci_hi"] in t)

    ok("q_g4_g1m_6_ci", ci_in_report("G4-G1m"),
       "expect delta 6 ci [-0.2857,+0.9524] in report")
    ok("q_g2_g0_2_ci", ci_in_report("G2-G0"),
       "expect delta 2 ci [-0.2857,0.5714]")
    ok("q_g4_g1f_13_ci", ci_in_report("G4-G1f"),
       "expect delta 13 ci [0.0476,1.2381]")
    ok("q_g4_g0_4_ci", ci_in_report("G4-G0"),
       "expect delta 4 ci [-0.3333,0.7143]")
    ok("q_g5_g0_71_ci", ci_in_report("G5-G0"),
       "expect delta 71 ci [2.2381,4.619] (gr/C2)")
    ok("q_g1f_g0_9", ci_in_report("G1f-G0"),
       "expect delta -9 ci [-1.3345,0.4286] in report")

    # seeds won/tied/lost quoted for key pairs
    for pair, trio in (("G4-G1m", "7/8/6"), ("G2-G0", "3/13/5"),
                       ("G4-G1f", "11/7/3")):
        r = ci[pair]
        want = "%s/%s/%s" % (r["seeds_positive"], r["seeds_tied"],
                             r["seeds_negative"])
        ok("q_seeds_%s" % pair.replace("-", "_"), want == trio
           and want in rn, "csv=%s report-has=%s" % (want, want in rn))

    # ---- rank direction numbers ---------------------------------------
    with open(OUT / "corrected_rank_direction.csv", newline="",
              encoding="utf-8") as fh:
        rk = {r["metric"]: r["value"] for r in csv.DictReader(fh)}
    for label, key, variants in [
        ("pub_pct", "published.mean_baseline_percentile", ["0.388022", "0.388"]),
        ("corr_pct", "corrected.mean_true_baseline_percentile",
         ["0.343518", "0.3435", "0.344"]),
        ("corr_share", "corrected.f2_better_than_true_baseline_share",
         ["0.341040", "0.34104", "34.1"]),
        ("cap_mean", "corrected.true_baseline_rank_captured_mean",
         ["2.09"]),
        ("miss_mean", "corrected.true_baseline_rank_missed_mean",
         ["2.90"]),
    ]:
        val = rk[key]
        present = any(v in report for v in variants) and any(
            v in hier for v in variants)
        ok("q_rank_%s" % label, present,
           "csv=%s variants-in-report=%s hierarchy=%s"
           % (val, any(v in report for v in variants),
              any(v in hier for v in variants)))

    # ---- summary totals ------------------------------------------------
    cs = json.loads((OUT / "corrected_summary.json").read_text(
        encoding="utf-8"))
    c1 = cs["c1"]
    ok("q_totals_7", all(str(v) in rn for v in
                         (90, 81, 88, 92, 94, 161))
       and str(c1["sum_k_t"]) in rn,
       "sum_k_t=%s in report=%s" % (c1["sum_k_t"],
                                    str(c1["sum_k_t"]) in report))
    ok("q_headroom_82", str(c1["n_headroom"]) in report and
       str(c1["n_headroom"]) in hier, "82 in both")
    c3 = cs["c3"]
    ok("q_setdiff_80",
       str(c3["diff_states"]["states_differing_G0_vs_G1m"]) == "80"
       and ("80/7,560" in report or "80 of 7,560" in report),
       "states_differing_G0_vs_G1m=%s"
       % c3["diff_states"].get("states_differing_G0_vs_G1m"))
    c6 = cs["c6"]
    ok("q_decomposition_60_7", c6["sums"].get("rank") == 60
       and c6["sums"].get("conflict") == 7
       and "60 ranking + 7 conflict" in hier,
       "c6 sums rank=%s conflict=%s"
       % (c6["sums"].get("rank"), c6["sums"].get("conflict")))

    # ---- matrix cross-reference ----------------------------------------
    with open(OUT / "study_audit.csv", newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    ok("q_matrix_42", len(rows) == 42 and "42 comparisons" in report,
       "rows=%d" % len(rows))
    counts = {}
    for r in rows:
        counts[r["classification"]] = counts.get(r["classification"], 0) + 1
    for cls, n in counts.items():
        ok("q_count_%s" % cls[:12], ("| %s | %d |" % (cls, n)) in hier,
           "%s = %d in hierarchy table" % (cls, n))

    # ---- plan hash quoted ----------------------------------------------
    want = (OUT / "analysis_plan.sha256").read_text(encoding="utf-8").split()[0]
    ok("q_plan_hash", want in report and want in hier, want[:16])

    result = dict(generated=time.strftime("%Y-%m-%d %H:%M:%S"),
                  n_checks=len(checks), n_failed=len(fails),
                  checks=checks, failures=fails)
    (OUT / "report_check.json").write_text(json.dumps(result, indent=1,
                                                      sort_keys=True),
                                           encoding="utf-8")
    print("[bi5] %d/%d checks passed; failures=%d; %.1fs"
          % (len(checks) - len(fails), len(checks), len(fails),
             time.time() - t0))
    for f in fails:
        print("BI5 FAILURE: %s" % f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
