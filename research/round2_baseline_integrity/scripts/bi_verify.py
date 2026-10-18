"""bi_verify: final verification gate (plan sec.8).

1. integrity.sha256 re-checked against current study files (byte-exact).
2. All 7 prior study seals re-verified with their own recorded rules
   (read-only; never re-run their scripts). Path bases: ceiling/fc/mo/
   goal_rule/stagewise manifests are repo-root-relative; eda/opr are
   study-dir-relative. run_log staleness tolerated where bi0 tolerated it.
3. The 9 protected files unchanged vs bi0 recorded hashes.
4. analysis_plan.md still matches its frozen .sha256.
5. bi4 validation.json still shows 0 failures (re-run bi4 first if any
   artifact changed).
Prints a PASS/FAIL line per check; exit 1 on any failure.
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
ROOT = OUT.parent.parent


def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    fails = []

    def ok(name, cond, detail=""):
        print("[%s] verify:%s %s" % ("PASS" if cond else "FAIL", name, detail))
        if not cond:
            fails.append(name)

    # ---- 1. own seal ---------------------------------------------------
    seal = OUT / "integrity.sha256"
    bad, n = [], 0
    for line in seal.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        want, rel = line.split("  ", 1)
        n += 1
        p = OUT / rel
        if not p.exists():
            bad.append(rel + " (missing)")
        elif sha256(p) != want:
            bad.append(rel + " (changed)")
    # no unsealed extras (except excluded names)
    sealed = {ln.split("  ", 1)[1]
              for ln in seal.read_text(encoding="utf-8").splitlines()
              if ln.strip()}
    for p in OUT.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(OUT).as_posix()
        if rel.startswith("__pycache__/") or p.name.endswith(".pyc"):
            continue
        if rel in ("integrity.sha256", "verify_output.txt"):
            continue
        if rel not in sealed:
            bad.append(rel + " (unsealed)")
    ok("own_seal", not bad, "files=%d bad=%s" % (n, bad))

    # ---- 2. prior seals ------------------------------------------------
    # Replicates bi0's read-only verification: read each study's own
    # integrity.sha256, resolve path base (root-relative; study-dir for
    # entries not found and not research/-prefixed), tolerate run_log
    # staleness exactly as bi0 did. Never re-runs their scripts.
    SEALS = ["round2_decision_ceiling", "round2_eda",
             "round2_fixed_cardinality", "round2_goal_rule",
             "round2_missed_oracle", "round2_opr",
             "round2_stagewise_signal"]
    seal_fail, seal_n = [], 0
    for name in SEALS:
        m = ROOT / "research" / name / "integrity.sha256"
        if not m.exists():
            seal_fail.append(name + " (manifest missing)")
            continue
        for line in m.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            want, rel = line.split("  ", 1)
            seal_n += 1
            q = ROOT / rel
            if not q.exists() and not rel.startswith("research/"):
                q = m.parent / rel
            if not q.exists() or sha256(q) != want:
                if rel.endswith("run_log.txt"):
                    continue  # tolerated per bi0 (ceiling/goal_rule/stagewise)
                seal_fail.append("%s:%s" % (name, rel))
    ok("prior_seals", not seal_fail, "%d seals, %d entries; bad=%s"
       % (len(SEALS), seal_n, seal_fail or "none"))

    # ---- 3. protected files -------------------------------------------
    ih = json.loads((OUT / "input_hashes.json").read_text(encoding="utf-8"))
    changed = []
    for rel, rec in ih["protected"].items():
        want = rec if isinstance(rec, str) else rec.get("sha256")
        if sha256(ROOT / rel) != want:
            changed.append(rel)
    ok("protected_unchanged", not changed, "9 files; changed=%s" % changed)

    # ---- 4. frozen plan ------------------------------------------------
    want = (OUT / "analysis_plan.sha256").read_text(encoding="utf-8").split()[0]
    ok("plan_frozen", sha256(OUT / "analysis_plan.md") == want, want[:16])

    # ---- 5. validation gate -------------------------------------------
    v = json.loads((OUT / "validation.json").read_text(encoding="utf-8"))
    ok("bi4_gate", v["n_failed"] == 0, "%d checks, failed=%d"
       % (v["n_checks"], v["n_failed"]))
    r = json.loads((OUT / "report_check.json").read_text(encoding="utf-8"))
    ok("bi5_gate", r["n_failed"] == 0, "%d checks, failed=%d"
       % (r["n_checks"], r["n_failed"]))

    print("[bi_verify] %s (%d failures)"
          % ("ALL CHECKS PASSED" if not fails else "FAILURES: " + str(fails),
             len(fails)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
