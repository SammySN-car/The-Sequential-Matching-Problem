"""sr_verify: final integrity gate for research/round2_stagewise_reward (Task 11).

Checks (a)-(i) per the Task 11 dispatch / implementation_plan.md Task 11:
  (a) baseline-integrity verifier re-run via subprocess (protected files + 7 prior seals)
  (b) analysis_plan.md matches its frozen analysis_plan.sha256
  (c) model_artifact.json matches its frozen .sha256 AND the Task-6 recorded hash 7f1ddfe0...
  (d) seed groups pairwise disjoint (pilot/fit/val/final-eval) and NO 70xxx data files
      (the final evaluation was never run - pre-registered stop, plan S.11 / R1.1 rules 1-2)
  (e) every deliverable of plan S.12 exists
  (f) result-artifact flags match the narrative (solver failed V4, pilot passed, stages OK)
  (g) run_log.txt non-empty and contains the MAIN COLLECTION line
  (h) results/pilot_candidate_official.json: 6 episodes, all valid
  (i) integrity.sha256 present; every listed hash recomputed against its file; sorted + unique
plus a label-maturity scan (max observed day <= 99) supporting report Q3.

Prints one [PASS]/[FAIL] line per check; writes results/final_integrity.json (deterministic,
no timestamps); exits non-zero on any failure. Read-only over every pre-existing artifact.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent      # experiment dir
ROOT = HERE.parent.parent                          # repo root
RESULTS = HERE / "results"
DATA = HERE / "data"

PLAN_SHA256 = "80615fbcc3d09c41e052ce96ff88a57aff147c99a3a056b1a9e906fd7f80308b"
MODEL_SHA256_PREFIX = "7f1ddfe0"
PILOT_SEED = 40001
FIT_RANGE = (40002, 40400)
VAL_RANGE = (40401, 40500)
FINAL_EVAL_RANGE = (70001, 70100)
HORIZON_DAY = 99

DELIVERABLES = [
    "analysis_plan.md",
    "analysis_plan.sha256",
    "sr_policy_core.py",
    "policy_parity.py",
    "policy_candidate.py",
    "scripts/sr_features.py",
    "scripts/sr_label.py",
    "scripts/sr_collect.py",
    "scripts/sr_train.py",
    "scripts/sr_solver_test.py",
    "scripts/sr_pilot.py",
    "scripts/sr_offline_rank.py",
    "scripts/sr_candidate_test.py",
    "scripts/sr_verify.py",
    "results/feature_audit.json",
    "results/model_artifact.json",
    "results/model_artifact.sha256",
    "results/train_metrics.json",
    "results/solver_validation.json",
    "results/pilot_report.json",
    "results/offline_ranking.json",
    "results/pilot_candidate_official.json",
    "data/n_decision.json",
    "report.md",
    "run_log.txt",
    "integrity.sha256",
]

# Task-10 (skipped) outputs that must NOT exist
ABSENT = [
    "scripts/sr_eval_run.py",
    "scripts/sr_eval_aggregate.py",
    "results/paired_stats.json",
    "results/cardinality_check.json",
]


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    checks = []

    def ok(name, cond, detail):
        checks.append({"name": name, "status": "PASS" if cond else "FAIL",
                       "detail": detail})
        print("[%s] %s: %s" % ("PASS" if cond else "FAIL", name, detail))

    # (a) baseline-integrity verifier: 9 protected files + 7 prior research seals
    bi = ROOT / "research" / "round2_baseline_integrity" / "scripts" / "bi_verify.py"
    try:
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        p = subprocess.run([sys.executable, "-B", str(bi)], capture_output=True,
                           text=True, encoding="utf-8", env=env, timeout=600)
        bi_lines = [ln for ln in p.stdout.splitlines() if ln.startswith("[")]
        ok("a_baseline_integrity", p.returncode == 0,
           "bi_verify exit=%d; %d checks; %s"
           % (p.returncode, len(bi_lines),
              bi_lines[-1] if bi_lines else "no output"))
    except Exception as exc:  # noqa: BLE001 - report any verifier failure
        ok("a_baseline_integrity", False, "bi_verify did not run: %r" % (exc,))

    # (b) frozen analysis plan
    want_plan = (HERE / "analysis_plan.sha256").read_text(encoding="utf-8").split()[0]
    got_plan = sha256(HERE / "analysis_plan.md")
    ok("b_plan_hash_frozen",
       got_plan == want_plan == PLAN_SHA256,
       "analysis_plan.md sha256=%s declared=%s task6_recorded=%s"
       % (got_plan[:16], want_plan[:16], PLAN_SHA256[:16]))

    # (c) frozen model artifact
    want_model = (RESULTS / "model_artifact.sha256").read_text(encoding="utf-8").split()[0]
    got_model = sha256(RESULTS / "model_artifact.json")
    ok("c_model_artifact_frozen",
       got_model == want_model and got_model.startswith(MODEL_SHA256_PREFIX),
       "model_artifact.json sha256=%s declared=%s prefix_7f1ddfe0=%s"
       % (got_model[:16], want_model[:16],
          got_model.startswith(MODEL_SHA256_PREFIX)))

    # (d1) seed groups pairwise disjoint
    artifact = json.loads((RESULTS / "model_artifact.json").read_text(encoding="utf-8"))
    metrics = json.loads((RESULTS / "train_metrics.json").read_text(encoding="utf-8"))
    pilot = {PILOT_SEED}
    fit = set(range(FIT_RANGE[0], FIT_RANGE[1] + 1))
    val = set(range(VAL_RANGE[0], VAL_RANGE[1] + 1))
    final_eval = set(range(FINAL_EVAL_RANGE[0], FINAL_EVAL_RANGE[1] + 1))
    art_fit = set(metrics["split"]["fit_seeds"])
    art_val = set(metrics["split"]["val_seeds"])
    art_excl = set(artifact["split"]["excluded"])
    disjoint = (not (pilot & fit) and not (pilot & val) and not (pilot & final_eval)
                and not (fit & val) and not (fit & final_eval) and not (val & final_eval))
    ok("d1_seed_groups_disjoint",
       disjoint and art_fit == fit and art_val == val and art_excl == pilot,
       "pilot=1 fit=%d val=%d final_eval=%d; artifact fit/val/excluded match=%s; "
       "pairwise_disjoint=%s"
       % (len(fit), len(val), len(final_eval),
          art_fit == fit and art_val == val and art_excl == pilot, disjoint))

    # (d2) final-eval seeds 70001-70100 never touched: no data file by name or content
    name_hit, content_hit, n_files, n_bytes = [], [], 0, 0
    seed_re = re.compile(rb'"seed(?:_group)?"\s*:\s*70\d{3}')
    for dp, _dn, fnames in os.walk(DATA):
        for fname in fnames:
            if not fname.endswith(".jsonl"):
                continue
            if re.match(r"seed_70\d{3}\.jsonl$", fname):
                name_hit.append(fname)
            blob = Path(dp, fname).read_bytes()
            n_files += 1
            n_bytes += len(blob)
            if seed_re.search(blob):
                content_hit.append(fname)
    ok("d2_final_eval_seeds_untouched",
       not name_hit and not content_hit,
       "no file named seed_70xxx and no '\"seed(_group)?\": 70xxx' row in %d data "
       "files (%d bytes scanned); seeds 70001-70100 never simulated"
       % (n_files, n_bytes))

    # (d3) skipped Task-10 outputs absent
    stale = [rel for rel in ABSENT if (HERE / rel).exists()]
    ok("d3_final_eval_outputs_absent", not stale,
       "no %s on disk; final paired evaluation was skipped per plan S.11 stop"
       % ", ".join(ABSENT) if not stale else "unexpected: %s" % stale)

    # (e) deliverables present
    missing = [rel for rel in DELIVERABLES if not (HERE / rel).is_file()]
    ok("e_deliverables_present", not missing,
       "%d/%d plan-S.12 deliverables present%s"
       % (len(DELIVERABLES) - len(missing), len(DELIVERABLES),
          "" if not missing else "; missing=%s" % missing))

    # (f) artifact flags match the narrative
    sv = json.loads((RESULTS / "solver_validation.json").read_text(encoding="utf-8"))
    v4 = sv["v4_dense_timing"]["gates"]
    v4_ok = (not sv["passed"]
             and v4["max_seconds_lt_3"] is False
             and v4["zero_node_limit_failures"] is False
             and v4["max_seconds"] > 3.0)
    ok("f1_solver_validation_narrative", v4_ok,
       "solver_validation.passed=false; v4 max_seconds=%.3f (>3.0 gate); "
       "v4_max_seconds_lt_3=%s; v4_zero_node_limit_failures=%s; node_limit_failures=%d"
       % (v4["max_seconds"], v4["max_seconds_lt_3"],
          v4["zero_node_limit_failures"], v4["node_limit_failures"]))

    pilot_rep = json.loads((RESULTS / "pilot_report.json").read_text(encoding="utf-8"))
    ok("f2_pilot_report_pass",
       pilot_rep.get("overall") == "PASS",
       "pilot_report.overall=%s (P1-P6)" % pilot_rep.get("overall"))

    statuses = {k: v["status"] for k, v in artifact["stages"].items()}
    gates_ok = all(g["passed"] for g in metrics["gates"].values())
    ok("f3_model_stages_ok",
       statuses == {"s1": "OK", "s2": "OK", "s3": "OK"} and gates_ok,
       "model_artifact stage statuses=%s; train_metrics fit gates passed=%s"
       % (statuses, gates_ok))

    rank = json.loads((RESULTS / "offline_ranking.json").read_text(encoding="utf-8"))
    rank_ok = all(c["ok"] for c in rank["integrity"]["checks"].values()) \
        and not rank["integrity"]["problems"]
    ok("f4_offline_ranking_integrity",
       rank_ok,
       "%d integrity checks all ok=%s; problems=%d"
       % (len(rank["integrity"]["checks"]), rank_ok, len(rank["integrity"]["problems"])))

    # (g) run log
    run_log = (HERE / "run_log.txt").read_text(encoding="utf-8")
    ok("g_run_log_main_collection",
       bool(run_log.strip()) and "MAIN COLLECTION" in run_log,
       "run_log.txt %d lines, %d bytes; MAIN COLLECTION line present=%s"
       % (len(run_log.splitlines()), len(run_log.encode("utf-8")),
          "MAIN COLLECTION" in run_log))

    # (h) candidate pilot episodes all valid
    cand = json.loads((RESULTS / "pilot_candidate_official.json")
                      .read_text(encoding="utf-8"))
    eps = cand.get("episodes", [])
    ok("h_candidate_pilot_valid",
       len(eps) == 6 and all(e.get("valid") is True for e in eps),
       "pilot_candidate_official: %d episodes, all valid=%s (smoke only, pilot seed)"
       % (len(eps), all(e.get("valid") is True for e in eps)))

    # label maturity: every joined label matured before the 60+40 horizon (Q3)
    max_day, rows = -1, 0
    for p in sorted((DATA / "labels").glob("*.jsonl")):
        with p.open(encoding="utf-8") as fh:
            for line in fh:
                d = json.loads(line)
                rows += 1
                if d.get("max_observed_day", -1) > max_day:
                    max_day = d["max_observed_day"]
    ok("j_label_maturity_within_horizon",
       rows > 0 and max_day <= HORIZON_DAY,
       "%d label rows across %d seed groups; max_observed_day=%d <= %d"
       % (rows, len(list((DATA / "labels").glob("*.jsonl"))), max_day, HORIZON_DAY))

    # (i) integrity seal: present, sorted, unique, every hash recomputed
    seal = HERE / "integrity.sha256"
    if not seal.is_file():
        ok("i1_manifest_present", False, "integrity.sha256 absent (not sealed yet)")
        ok("i2_manifest_entries_match", False, "no manifest to verify")
    else:
        ok("i1_manifest_present", True, "integrity.sha256 present")
        lines = [ln for ln in seal.read_text(encoding="utf-8").splitlines() if ln.strip()]
        rels = []
        bad = []
        for ln in lines:
            want, rel = ln.split("  ", 1)
            rels.append(rel)
            f = HERE / rel
            if not f.is_file():
                bad.append(rel + " (missing)")
            elif sha256(f) != want:
                bad.append(rel + " (changed)")
        ok("i2_manifest_entries_match", not bad,
           "%d entries recomputed; bad=%s" % (len(rels), bad or "none"))
        ok("i3_manifest_sorted_unique",
           rels == sorted(rels) and len(rels) == len(set(rels)),
           "sorted=%s unique=%s; excludes integrity.sha256 and __pycache__"
           % (rels == sorted(rels), len(rels) == len(set(rels))))

    n_pass = sum(1 for c in checks if c["status"] == "PASS")
    n_total = len(checks)
    overall = "PASS" if n_pass == n_total else "FAIL"
    out = {
        "task": 11,
        "decision": "STOP / REDESIGN",
        "note": ("final verification of the sealed experiment directory; the pre-registered "
                 "final paired evaluation (seeds 70001-70100) was skipped per analysis_plan "
                 "S.11 stop conditions and R1.1 decision rules 1-2 (V4 dense-timing gates "
                 "failed), so realized MSMIs and the paired effect size are NOT MEASURED"),
        "checks": checks,
        "n_pass": n_pass,
        "n_total": n_total,
        "overall": overall,
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "final_integrity.json").write_text(
        json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("[sr_verify] %s (%d/%d checks passed)" % (overall, n_pass, n_total))
    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
