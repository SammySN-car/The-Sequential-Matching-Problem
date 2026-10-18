"""bi4: independent validation gate before report authoring (plan sec.7).

Asserts:
  1. bi0/bi1/bi2/bi3 all recorded pass status with zero failures.
  2. C2: all 14 published pair CIs match evaluation.json bit-for-bit.
  3. C7: fc main/headroom/contrast CIs bit-for-bit vs statistics.json.
  4. Matrix completeness: 42 rows, all 17 columns non-empty, allowed vocab.
  5. Claim-critical corrected numbers present in corrected CSVs.
  6. Protected files unchanged vs bi0 recorded hashes.
  7. analysis_plan.md hash still matches its frozen .sha256.
Writes validation.json; exit 1 on any failure.
"""
import csv
import hashlib
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
ROOT = OUT.parent.parent  # repo root

ALLOWED = {"CORRECT_AND_COMPARABLE", "CORRECT_BUT_NOT_COMPARABLE",
           "DIRECTION_BUG", "OTHER_IMPLEMENTATION_DEFECT",
           "UNVERIFIABLE_FROM_SAVED_ARTIFACTS"}


def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    t0 = time.time()
    fails, checks = [], []

    def ok(name, cond, detail=""):
        checks.append(dict(check=name, passed=bool(cond), detail=str(detail)))
        if not cond:
            fails.append("%s: %s" % (name, detail))
        print("[%s] %s %s" % ("PASS" if cond else "FAIL", name, detail))

    # ---- 1. upstream script status -------------------------------------
    ih = json.loads((OUT / "input_hashes.json").read_text(encoding="utf-8"))
    sf = json.loads((OUT / "source_facts.json").read_text(encoding="utf-8"))
    cs = json.loads((OUT / "corrected_summary.json").read_text(encoding="utf-8"))
    ms = json.loads((OUT / "matrix_summary.json").read_text(encoding="utf-8"))

    ok("bi0_clean", ih.get("inputs_missing") == []
       and ih.get("protected_missing") == []
       and ih.get("seal_fail_non_runlog") == []
       and ih.get("counterfactual_seed_error") is None
       and ih.get("f2_policy_like_files") == [],
       "inputs_missing=%s protected_missing=%s seal_fail=%s seed_err=%s "
       "f2_policy=%s" % (ih.get("inputs_missing"), ih.get("protected_missing"),
                         ih.get("seal_fail_non_runlog"),
                         ih.get("counterfactual_seed_error"),
                         ih.get("f2_policy_like_files")))
    ok("bi0_inventory_21", ih.get("inventory") is not None
       and len(ih["inventory"]) == 21, "n=%s"
       % (len(ih["inventory"]) if ih.get("inventory") else -1))
    ok("bi1_pass", sf.get("failures") == [] and sf.get("n_facts") == 10
       and sf.get("negation_scan_hits") == [],
       "facts=%s failures=%s neg_hits=%s" % (sf.get("n_facts"),
                                             sf.get("failures"),
                                             sf.get("negation_scan_hits")))
    ok("bi2_pass", cs.get("failures") == [],
       "failures=%s" % (cs.get("failures"),))
    ok("bi3_pass", ms.get("failures") == [] and ms.get("n_rows") == 42,
       "rows=%s failures=%s" % (ms.get("n_rows"), ms.get("failures")))

    # ---- 2. C2 exact match --------------------------------------------
    c2 = cs["c2"]
    ok("c2_all_14_match", c2["pairs"] == 14 and c2["exact_matches"] == 14
       and c2["failures"] == [],
       "%s/%s failures=%s" % (c2["exact_matches"], c2["pairs"], c2["failures"]))

    # ---- 3. C7 bit-for-bit --------------------------------------------
    c7 = cs["c7"]
    main_bad = [k for k, v in c7["fc_main"].items() if not v["match"]]
    ok("c7_main", len(c7["fc_main"]) == 5 and not main_bad, str(main_bad))
    hr_bad = [k for k, v in c7["fc_headroom"].items() if not v["match"]]
    ok("c7_headroom", len(c7["fc_headroom"]) == 5 and not hr_bad, str(hr_bad))
    ok("c7_contrast", c7["fc_contrast"]["match"] is True
       and c7["fc_contrast"]["delta"] == 13, str(c7["fc_contrast"]))
    ok("c7_gr_pairs", c7["gr_pairs_exact"] == c7["gr_pairs_total"] == 14,
       "%s/%s" % (c7["gr_pairs_exact"], c7["gr_pairs_total"]))

    # ---- 4. matrix completeness ---------------------------------------
    with open(OUT / "study_audit.csv", newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    ok("matrix_42_rows", len(rows) == 42, "n=%d" % len(rows))
    empty = [(i, k) for i, r in enumerate(rows) for k, v in r.items()
             if not str(v).strip()]
    ok("matrix_no_empty_cells", not empty, str(empty[:5]))
    bad = sorted({r["classification"] for r in rows} - ALLOWED)
    ok("matrix_vocab", not bad, str(bad))
    bug = sum(1 for r in rows if r["direction_bug_applies"] == "yes")
    ok("matrix_bug_rows", bug == 7, "n=%d" % bug)

    # ---- 5. claim-critical corrected numbers --------------------------
    with open(OUT / "corrected_paired_ci.csv", newline="", encoding="utf-8") as fh:
        ci = {r["pair"]: r for r in csv.DictReader(fh)}
    ok("ci_14_rows", len(ci) == 14, "n=%d" % len(ci))
    ok("ci_all_match_published",
       all(r["matches_evaluation_json"] == "True" for r in ci.values()),
       str([k for k, r in ci.items() if r["matches_evaluation_json"] != "True"]))
    g4g1m = ci.get("G4-G1m")
    ok("g4_g1m_delta_6_incl0", g4g1m is not None
       and g4g1m["delta_total"] == "6"
       and float(g4g1m["ci_lo"]) <= 0 <= float(g4g1m["ci_hi"]),
       g4g1m and "delta=%s ci=[%s,%s]" % (g4g1m["delta_total"],
                                          g4g1m["ci_lo"], g4g1m["ci_hi"]))
    g2g0 = ci.get("G2-G0")
    ok("g2_g0_delta_2_incl0", g2g0 is not None and g2g0["delta_total"] == "2"
       and float(g2g0["ci_lo"]) <= 0 <= float(g2g0["ci_hi"]),
       g2g0 and "delta=%s ci=[%s,%s]" % (g2g0["delta_total"],
                                         g2g0["ci_lo"], g2g0["ci_hi"]))
    g4g1f = ci.get("G4-G1f")
    ok("g4_g1f_delta_13_excl0", g4g1f is not None and g4g1f["delta_total"] == "13"
       and g4g1f["ci_excludes_zero"] == "True",
       g4g1f and "delta=%s excl0=%s" % (g4g1f["delta_total"],
                                        g4g1f["ci_excludes_zero"]))
    with open(OUT / "corrected_rank_direction.csv", newline="",
              encoding="utf-8") as fh:
        rk = {r["metric"]: r["value"] for r in csv.DictReader(fh)}
    ok("c5_count_pct_corrected",
       rk.get("published.mean_baseline_percentile") == "0.388022"
       and rk.get("corrected.mean_true_baseline_percentile") == "0.343518",
       "pub=%s corr=%s" % (rk.get("published.mean_baseline_percentile"),
                           rk.get("corrected.mean_true_baseline_percentile")))
    ok("c5_f2_better_share",
       rk.get("published.f2_better_than_baseline_share") == "0.323699"
       and rk.get("corrected.f2_better_than_true_baseline_share") == "0.34104",
       "pub=%s corr=%s" % (rk.get("published.f2_better_than_baseline_share"),
                           rk.get("corrected.f2_better_than_true_baseline_share")))
    ok("c5_sign_chain", rk.get("corrected.sign_chain_all_match") == "True"
       and rk.get("corrected.sign_chain_rows_verified") == "173",
       "rows=%s" % rk.get("corrected.sign_chain_rows_verified"))

    # ---- 6. protected files unchanged ---------------------------------
    prot = None
    for key in ("protected_files", "protected", "protected_hashes"):
        if isinstance(ih.get(key), dict):
            prot = ih[key]
            break
    ok("protected_recorded", prot is not None and len(prot) >= 9,
       "n=%d" % (len(prot) if prot else -1))
    changed = []
    if prot:
        for rel, rec in prot.items():
            want = rec if isinstance(rec, str) else rec.get("sha256")
            got = sha256(ROOT / rel)
            if got != want:
                changed.append(rel)
    ok("protected_unchanged", not changed, str(changed))

    # ---- 7. frozen plan hash ------------------------------------------
    plan = OUT / "analysis_plan.md"
    want = (OUT / "analysis_plan.sha256").read_text(encoding="utf-8").split()[0]
    ok("plan_frozen", sha256(plan) == want, sha256(plan)[:16])

    result = dict(generated=time.strftime("%Y-%m-%d %H:%M:%S"),
                  n_checks=len(checks), n_failed=len(fails),
                  checks=checks, failures=fails)
    (OUT / "validation.json").write_text(json.dumps(result, indent=1,
                                                    sort_keys=True),
                                         encoding="utf-8")
    print("[bi4] %d/%d checks passed; failures=%d; %.1fs"
          % (len(checks) - len(fails), len(checks), len(fails),
             time.time() - t0))
    for f in fails:
        print("BI4 FAILURE: %s" % f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
