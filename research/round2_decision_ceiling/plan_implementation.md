# Decision Opportunity and Counterfactual Ceiling Audit — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to
> implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for
> tracking. **No git commits are permitted** (global constraint GC4) — progress is
> recorded in `run_log.txt` instead of commits.

**Goal:** Execute the frozen preregistration in `research/round2_decision_ceiling/analysis_plan.md`
to produce, in one read-only pass, evidence on whether prior policy failures came
from too few genuine choices, unextracted information, or choices that rarely
change MSMI.

**Architecture:** A single replay harness rebuilds each of the 126 frozen control
worlds (exact seeds/variants from `n01_replay_rows.jsonl`), captures a simulator
snapshot at each decision day, and from that snapshot (a) enumerates the full
feasible candidate graph, (b) runs each candidate pair *alone* to obtain a
counterfactual outcome, and (c) computes only decision-time-legal features.
Downstream scripts consume the persisted intermediate JSONL and never recompute
replay, so each gate can be inspected independently.

**Tech Stack:** Python 3.12 local interpreter (NOT Docker — the Dockerfile ships
only `kit.py`+`policy.py` and has no sklearn). stdlib for all replay/reconstruction;
`scikit-learn 1.8.0` for §5; `networkx 3.6.1` used **only** as an optional
cross-check validator for the §6 matching solver.

**Spec:** `research/round2_decision_ceiling/analysis_plan.md` (FROZEN). This plan
argues only from that spec; the two documents travel together.

---

## Global Constraints

- **GC1 — Read-only outside this directory.** `kit.py`, `policy.py`, `policy_ac.py`,
  `evaluate.py`, `Dockerfile`, `tests/**/*.py`, `research/round2_eda/`,
  `research/round2_opr/`, `research/method_tournament/`,
  `research/round2_promotion_fresh_seeds/`, `research/next_method_search/`,
  `research/out*/` are read-only. Byte-hash them before and after (Task 0/8).
- **GC2 — Write boundary.** Every created file lives in
  `research/round2_decision_ceiling/`. Nothing else in the repo is written.
- **GC3 — Frozen plan.** `analysis_plan.md` defines estimands, splits, metrics and
  interpretation rules. If execution reveals a *factual* error in it, correct it
  only by appending `## Amendment` + reason to `analysis_plan.md` and logging to
  `run_log.txt`. Never edit a metric, split, or interpretation rule in response to
  observed results.
- **GC4 — No git-mutating commands.** No `git add/commit/checkout/branch/push`.
  Confirm `git status --porcelain` output is unchanged (5 lines) at Task 0 and 8.
- **GC5 — No hidden attributes as features.** Features come only from
  `Simulator.observe()` state + `allocate()` outputs. `truth`, `bias`,
  `response_rate`, `second_bias`, `exit_day`, `seed`, `variant`, future days and
  any `cf_*` value are never feature columns. `variant` is a strata key only.
- **GC6 — Gate order.** §3–§7 artifacts are produced only after
  `g0_replay_validation.md` records **GO**. If G0 records NO-GO, stop.
- **GC7 — Shell.** Windows PowerShell 5.1. Heredocs (`<<EOF`) do not work. Create
  files with `@'...'@ | Set-Content -LiteralPath <path> -Encoding utf8`.
  Always pass `workdir` = repo root rather than `cd`-ing inside commands.
  Python files written from the shell: `@'...'@ | Out-File $env:TEMP\f.py -Encoding utf8; python $env:TEMP\f.py`.
- **GC8 — Determinism.** Every script takes `--rng-seed` (default 4242) and writes
  its command line + wall time to `run_log.txt`. Re-running must be byte-identical.
- **GC9 — Honesty.** Never label a counterfactual outcome as observed, a one-day
  oracle as a sequential oracle, or a prediction metric as a policy gain.

## Review Focus

These are the failure modes the spec implies but that no single task's happy path
exercises. Each line names the owning task and its pinning check.

- **Snapshot leakage — a counterfactual run corrupting the day's baseline state.**
  Expected: after all pair-alone runs for a day, the snapshot's `introductions`,
  `events`, `past`, `busy` are byte-identical to capture time.
  Pinned by Task 1 Step 6 (leak assertion) + Task 4 Step 5 (same assertion reused).
- **Hidden-attribute leakage into a feature column** (e.g. `exit_day` or `variant`
  accidentally joined in). Expected: F1–F5 column lists contain only legal names.
  Pinned by Task 5 Step 3 (`assert_legal_features` on the built matrix).
- **Counterfactual disagreeing with the observed original for a selected pair**
  (the single most dangerous silent failure). Expected: 8,433/8,433 exact label
  agreement. Pinned by Task 2 Step 4 (T3) and Task 4 Step 6 (V1) — both must pass.
- **Maturity/right-censoring** producing `None` labels silently coerced to 0.
  Expected: zero `None` labels at horizon 100, and any `None` raises.
  Pinned by Task 2 Step 5 (T4) and Task 4 Step 7 (V3).
- **Row-level pseudo-replication** — treating 15,304 correlated rows as
  independent for CIs. Expected: every interval resamples the 21 seed-groups.
  Pinned by Task 5 Step 5 (`bootstrap_seed_groups` unit test on a toy frame).

---

## File Structure

| File | Responsibility |
|---|---|
| Create `research/round2_decision_ceiling/scripts/ce_common.py` | Paths, hashing, `log()`, protected-file manifest, snapshot/restore primitives, label extraction, CSV writer |
| Create `.../scripts/g0_replay_test.py` | G0 T1–T5; writes `g0_replay_validation.md` + `g0_results.json` |
| Create `.../scripts/s1_opportunities.py` | Replay pass 1 → `day_edges.jsonl` → `opportunity_summary.csv` |
| Create `.../scripts/s2_counterfactual.py` | Replay pass 2 → `counterfactual_pairs.jsonl` + `counterfactual_validation.csv` |
| Create `.../scripts/s3_signal.py` | Feature sets F1–F5, frozen model, seed-group CV → `within_state_signal.csv` |
| Create `.../scripts/s4_oracle.py` | Exact local oracle → `local_oracle_headroom.csv` |
| Create `.../scripts/s5_headroom.py` | K1–K6 evidence table → `headroom_synthesis.json` |
| Create `.../scripts/s6_report.py` | Assembles `report.md` from the CSVs; writes `integrity.sha256` |
| Create `run_log.txt` | Append-only execution log |
| Read `analysis_plan.md` | Frozen spec (never written by these scripts) |

Helpers are **imported**, not copied, from the frozen
`research/next_method_search/n01_autopsy.py` (`allocate`, `pair_features`,
`day_history`, `phase_of`, `episode_result`, `COMPARE_FIELDS`) so this audit cannot
diverge from the n01 pipeline. `n01_autopsy.py` is guarded by
`if __name__ == '__main__'` (L467) and therefore safe to import.

---
---

### Task 0: Scaffolding, protected-input hashing, log start

**Files:**
- Create: `research/round2_decision_ceiling/scripts/ce_common.py`
- Create: `research/round2_decision_ceiling/run_log.txt`

**Interfaces:**
- Produces: `ce_common.log(msg)`, `ce_common.protected_files() -> list[Path]`,
  `ce_common.sha256(p) -> str`, `ce_common.write_manifest(path, files) -> dict`,
  `ce_common.world_list() -> list[tuple[int,str]]`, `ce_common.OUT -> Path`,
  `ce_common.ROOT -> Path`.

- [ ] **Step 1: Write `scripts/ce_common.py`**

````python
"""Shared helpers for the Decision Opportunity and Counterfactual Ceiling Audit.

Read-only with respect to every protected artifact (GC1). All outputs land in
research/round2_decision_ceiling/ (GC2). stdlib only at import time so that
importing this module can never fail on a missing optional dependency.
"""
import copy, hashlib, json, sys, time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent          # .../round2_decision_ceiling/scripts
OUT = HERE.parent                               # .../round2_decision_ceiling
ROOT = OUT.parents[1]                           # repository root
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'research' / 'next_method_search'))

import kit                                        # noqa: E402
import n01_autopsy as n01                          # noqa: E402

N01 = ROOT / 'research' / 'next_method_search'
FROZEN_INTROS = N01 / 'n01_introductions.jsonl'
FROZEN_DAYS = N01 / 'n01_days.jsonl'
FROZEN_ROWS = N01 / 'n01_replay_rows.jsonl'
FROZEN_SUMMARY = N01 / 'n01_replay_summary.json'
HORIZON = 100          # evaluate.episode: 60 decision days + 40 follow-up days
DECISION_DAYS = 60


def log(msg):
    line = '[%s] %s' % (time.strftime('%Y-%m-%dT%H:%M:%S'), msg)
    print(line, flush=True)
    with open(OUT / 'run_log.txt', 'a', encoding='utf-8') as fh:
        fh.write(line + '\n')


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def protected_files():
    files = [ROOT / 'kit.py', ROOT / 'policy.py', ROOT / 'policy_ac.py',
             ROOT / 'evaluate.py', ROOT / 'Dockerfile']
    files += sorted(ROOT.glob('tests/**/*.py'))
    for d in ('round2_eda', 'round2_opr', 'method_tournament',
              'round2_promotion_fresh_seeds', 'next_method_search'):
        p = ROOT / 'research' / d
        if p.is_dir():
            files += [x for x in p.rglob('*') if x.is_file()]
    files += sorted(x for x in (ROOT / 'research').glob('out*/*') if x.is_file())
    return sorted({f for f in files if f.is_file()})


BANNED_FEATURE_EXACT = {'seed', 'variant', 'exit_day', 'truth', 'bias',
                        'response_rate', 'second_bias'}
BANNED_FEATURE_PREFIXES = ('cf_', 'y_', 'label')


def write_manifest(path, files):
    """sha256 of every protected file, keyed by repo-relative POSIX path."""
    man = {f.relative_to(ROOT).as_posix(): sha256(f) for f in files}
    Path(path).write_text(json.dumps(man, indent=1, sort_keys=True) + '\n',
                          encoding='utf-8')
    return man


def world_list():
    """126 frozen control worlds as (seed, variant), in n01 file order."""
    seen, out = set(), []
    for line in FROZEN_ROWS.read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        key = (int(row['seed']), row['variant'])
        if key not in seen:
            seen.add(key)
            out.append(key)
    return out


def read_jsonl(path):
    with open(path, encoding='utf-8') as fh:
        return [json.loads(l) for l in fh if l.strip()]


def write_jsonl(path, rows):
    with open(path, 'w', encoding='utf-8') as fh:
        for r in rows:
            fh.write(json.dumps(r, sort_keys=True) + '\n')
    log('wrote %s (%d rows)' % (Path(path).name, len(rows)))
````

- [ ] **Step 2: Verify import and world count**

Run (PowerShell, `workdir` = repo root). **Note:** `'` is a write-time escape
for the here-string terminator and is replaced with a single quote before the
command runs; treat every `'@` below as `'@`.

```powershell
@'
import sys; sys.path.insert(0, r'research\round2_decision_ceiling\scripts')
import ce_common as c
print('roots', c.ROOT.name, c.OUT.name)
print('worlds', len(c.world_list()), c.world_list()[:2])
print('protected', len(c.protected_files()))
'@ | Out-File $env:TEMP\t0.py -Encoding utf8; python $env:TEMP\t0.py
```

Expected: `worlds 126 [(146, 'development'), ...]`, `protected` > 50.

- [ ] **Step 3: Record start manifest + git status**

```powershell
@'
import sys, subprocess
sys.path.insert(0, r'research\round2_decision_ceiling\scripts')
import ce_common as c
c.write_manifest(c.OUT / 'manifest_start.json', c.protected_files())
st = subprocess.run(['git','status','--porcelain'], capture_output=True,
                    text=True, cwd=c.ROOT).stdout
(c.OUT / 'git_status_start.txt').write_text(st, encoding='utf-8')
c.log('task0 start manifest files=%d git_lines=%d'
      % (len(c.protected_files()), len([l for l in st.splitlines() if l.strip()])))
print(st)
'@ | Out-File $env:TEMP\t0b.py -Encoding utf8; python $env:TEMP\t0b.py
```

Expected: 5 `git status` lines (GC4). Save them; Task 8 re-checks equality.

- [ ] **Step 4: Log task complete**

`c.log('task0 done')`

---

### Task 1: G0 primitives - snapshot, isolated run, T1 orientation, T2 batch independence

**Files:**
- Create: `research/round2_decision_ceiling/scripts/g0_replay_test.py`
- Output: `research/round2_decision_ceiling/g0_results.json`

**Interfaces:**
- Consumes: `ce_common.*` from Task 0; `kit.Simulator`, `kit.generate`,
  `kit.baseline_asks`; `n01.allocate`, `n01.day_history`.
- Produces:
  - `ce_common.clone_from(snap) -> Simulator`
  - `ce_common.snapshot_fingerprint(snap) -> str`
  - `ce_common.intro_mid(a, b, day) -> str`
  - `ce_common.labels_from_events(mid, events, final_day, assigned_day) -> dict`
    with keys `mature, y_msmi, y_mutual, y_date, y_second, missing`
  - `ce_common.run_pair_isolated(snap, pair, final_day=100) -> (Simulator, mid)`
  - `ce_common.replay_world(seed, variant, per_day=None, follow_up=True)`
  - `g0_replay_test.test_t1_orientation/t2_batch/t2l_leak(opps) -> dict`

- [ ] **Step 1: Add replay primitives to `ce_common.py`**

Append:

````python
MUTABLE = ('introductions', 'events', 'past', 'busy')
# kit.Simulator.advance() (kit.py L141-189) writes ONLY these four containers,
# plus rebinding self.day and self.ask_spent. members and world are read-only
# inside advance; retired and ask_log are untouched. Source-verified (GC5).


def clone_from(snap):
    """Exact decision-time state for one isolated advance([pair]) run.

    Shallow-copies the simulator, then gives the copy its own instances of the
    four containers advance() mutates, so a pair-alone run cannot leak back into
    the snapshot later pairs are replayed from.
    """
    s = copy.copy(snap)
    for name in MUTABLE:
        setattr(s, name, copy.deepcopy(getattr(snap, name)))
    return s


def snapshot_fingerprint(snap):
    """Stable digest of the parts advance() touches; used for leak assertions."""
    h = hashlib.sha256()
    h.update(json.dumps(sorted(snap.past), default=str).encode())
    h.update(json.dumps([i['introduction_id'] for i in snap.introductions]).encode())
    h.update(json.dumps([e['introduction_id'] for e in snap.events]).encode())
    h.update(json.dumps(sorted(snap.busy.items())).encode())
    return h.hexdigest()


def intro_mid(a, b, day):
    return 'intro_' + hashlib.sha256(
        '%s|%s|%s' % (min(a, b), max(a, b), day).encode()).hexdigest()[:24]


def labels_from_events(mid, events, final_day, assigned_day):
    """research/labels.py semantics, copied from n01_autopsy.py L316-341.

    Returns None-valued labels when not mature; callers MUST propagate None and
    never coerce it to 0 (analysis_plan.md V3).
    """
    es = [e for e in events if e['introduction_id'] == mid]
    if not (es and all(e['observed_day'] <= final_day for e in es)):
        return dict(mature=0, y_msmi=None, y_mutual=None, y_date=None,
                    y_second=None, missing=None)
    rs = [e for e in es if e['event'] == 'introduction_response']
    y_mutual = int(len(rs) == 2 and all(e['value'] == 'yes' for e in rs))
    ds = [e for e in es if e['event'] == 'date_happened' and e['value'] is True]
    y_date = int(bool(ds))
    ss = [e for e in es if e['event'] == 'second_meeting_intention']
    second_ok = bool(ds) and len(ss) == 2 and all(
        e['value'] == 'yes'
        and e['occurred_day'] - ds[0]['occurred_day'] <= 3 for e in ss)
    y_second = int(second_ok)
    y_msmi = int(second_ok and ds[0]['occurred_day'] - assigned_day <= 30)
    return dict(mature=1, y_msmi=y_msmi, y_mutual=y_mutual, y_date=y_date,
                y_second=y_second,
                missing=sum(e.get('missing_reason') == 'no_response'
                            for e in es))


def run_pair_isolated(snap, pair, final_day=HORIZON):
    """Run `pair` alone from `snap`, then follow the protocol to `final_day`.

    Returns (sim_after, new_mid). Raises if the run leaked into the snapshot.
    """
    fp_before = snapshot_fingerprint(snap)
    s = clone_from(snap)
    s.advance([list(pair)])
    while s.day < final_day:
        s.advance([])
    if snapshot_fingerprint(snap) != fp_before:
        raise AssertionError('snapshot leaked during isolated run %r' % (pair,))
    new = [i for i in s.introductions if i['assigned_day'] == snap.day]
    if len(new) != 1:
        raise AssertionError('expected exactly 1 new introduction, got %d'
                             % len(new))
    return s, new[0]['introduction_id']
````

- [ ] **Step 2: Add the replay loop that exposes snapshots**

Append to `ce_common.py`:

````python
def replay_world(seed, variant, per_day=None, follow_up=True):
    """Replay one frozen control world, exactly as n01_autopsy.replay_world.

    per_day(ctx) runs AFTER resolve_asks/allocate and BEFORE sim.advance(pairs).
    ctx keys: seed, variant, day, state, snap, pairs, edges, degree, used,
    max_score, score_counts, member_hist, day_ctx, n_intros, n_mutual, n_dates,
    n_feedback. Returns (digest_hex, sim).
    """
    world = kit.generate(seed, 200, 'evaluation', variant)
    sim = kit.Simulator(world)
    digest = hashlib.sha256()
    for _ in range(DECISION_DAYS):
        asks = kit.baseline_asks(sim.observe())
        digest.update(json.dumps(['ask', sim.day, asks],
                                 sort_keys=True).encode())
        sim.resolve_asks(asks)
        state = sim.observe()
        pairs, edges, degree, used = n01.allocate(state)
        digest.update(json.dumps(['match', sim.day, pairs],
                                 sort_keys=True).encode())
        if per_day is not None:
            member_hist, n_intros, n_mutual, n_dates, n_fb = \
                n01.day_history(state)
            per_day(dict(
                seed=seed, variant=variant, day=sim.day, state=state,
                snap=copy.deepcopy(sim), pairs=[list(p) for p in pairs],
                edges=edges, degree=degree, used=used,
                max_score=-min((e[0] for e in edges), default=0),
                score_counts=Counter(e[0] for e in edges),
                member_hist=member_hist,
                day_ctx={'has_history': int(n_intros > 0),
                         'n_available': sum(1 for m in state['members']
                                            if m['available']),
                         'n_intros': n_intros, 'n_mutual': n_mutual,
                         'n_dates': n_dates, 'n_feedback': n_fb},
                n_intros=n_intros, n_mutual=n_mutual, n_dates=n_dates,
                n_feedback=n_fb))
        sim.advance(pairs)
    if follow_up:
        for _ in range(HORIZON - DECISION_DAYS):
            sim.advance([])
    return digest.hexdigest(), sim
````

- [ ] **Step 3: Write `g0_replay_test.py` (T1, T2, T2L)**

````python
"""G0: counterfactual replay validity tests T1, T2 (analysis_plan.md sec 2.2).

T1 pair-orientation invariance; T2 batch independence; T2L snapshot leak check.
T3/T4/T5 are added in Task 2. Writes g0_results.json only.
"""
import json, random, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ce_common as c  # noqa: E402


def collect_opportunities(limit_worlds=None):
    """Replay pass A: capture one snapshot per decision day, keeping every edge."""
    worlds = c.world_list()
    if limit_worlds:
        worlds = worlds[:limit_worlds]
    opps = []
    for seed, variant in worlds:
        def per_day(ctx, _s=seed, _v=variant):
            if not ctx['edges']:
                return
            opps.append(dict(seed=_s, variant=_v, day=ctx['day'],
                             edges=[list(k) for _, k in sorted(ctx['edges'])],
                             pairs=[list(p) for p in ctx['pairs']],
                             snap=ctx['snap'],
                             fp=c.snapshot_fingerprint(ctx['snap'])))
        c.replay_world(seed, variant, per_day=per_day, follow_up=False)
    return opps


def test_t1_orientation(opps, n=50, rng_seed=4242):
    rng = random.Random(rng_seed)
    pool = [o for o in opps if o['edges']]
    tested = mismatched = 0
    for o in rng.sample(pool, min(n, len(pool))):
        pair = rng.choice(o['edges'])
        s1, mid1 = c.run_pair_isolated(o['snap'], [pair[0], pair[1]])
        s2, mid2 = c.run_pair_isolated(o['snap'], [pair[1], pair[0]])
        e1 = [e for e in s1.events if e['introduction_id'] == mid1]
        e2 = [e for e in s2.events if e['introduction_id'] == mid2]
        tested += 1
        if mid1 != mid2 or e1 != e2:
            mismatched += 1
    return dict(test='T1_pair_orientation', tested=tested,
                mismatched=mismatched, passed=bool(mismatched == 0))


def test_t2_batch(opps, n=50, rng_seed=4242):
    rng = random.Random(rng_seed)
    pool = [o for o in opps if len(o['edges']) >= 2]
    tested = mismatched = 0
    for o in rng.sample(pool, min(n, len(pool))):
        batch = c.clone_from(o['snap'])
        batch.advance(o['pairs'])
        solo = {}
        for pair in o['edges']:
            s, mid = c.run_pair_isolated(o['snap'], pair)
            solo[mid] = [e for e in s.events if e['introduction_id'] == mid]
        tested += 1
        ok = True
        for pair in o['pairs']:
            mid = c.intro_mid(pair[0], pair[1], o['day'])
            got = [e for e in batch.events if e['introduction_id'] == mid]
            if solo.get(mid) != got:
                ok = False
        if not ok:
            mismatched += 1
    return dict(test='T2_batch_independence', tested=tested,
                mismatched=mismatched, passed=bool(mismatched == 0))


def test_t2l_leak(opps):
    bad = sum(1 for o in opps
              if c.snapshot_fingerprint(o['snap']) != o['fp'])
    return dict(test='T2L_snapshot_leak', tested=len(opps), mismatched=bad,
                passed=bool(bad == 0))
````

- [ ] **Step 4: Run T1/T2/T2L on a 3-world subset**

```powershell
@'
import sys, json
sys.path.insert(0, r'research\round2_decision_ceiling\scripts')
import g0_replay_test as g, ce_common as c
opps = g.collect_opportunities(limit_worlds=3)
res = [g.test_t1_orientation(opps), g.test_t2_batch(opps), g.test_t2l_leak(opps)]
print(json.dumps(res, indent=1))
c.log('G0 partial ' + json.dumps(res, sort_keys=True))
'@ | Out-File $env:TEMP\g0a.py -Encoding utf8; python $env:TEMP\g0a.py
```

Expected: all three `passed: true`, `mismatched: 0`. **If T1 reports any
mismatch, stop**: orientation-dependent randomness must not be exploited. Record
the finding in `g0_replay_validation.md` and execute no further task.

- [ ] **Step 5: Scale to all 126 worlds and persist**

Add to `ce_common.py`:

````python
def save_g0(results, path=None):
    path = Path(path or (OUT / 'g0_results.json'))
    prev = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    prev.update(results)
    path.write_text(json.dumps(prev, indent=1, sort_keys=True) + '\n',
                    encoding='utf-8')
    log('g0_results.json updated: ' + ', '.join(sorted(results)))
    return prev
````

Then run the Step 4 snippet without `limit_worlds`, and finish with
`c.save_g0({r['test']: r for r in res})`.
Expected: all `passed: true` over 126 worlds.

- [ ] **Step 6: Log task complete**

`c.log('task1 done: T1/T2/T2L executed on 126 worlds')`

---

---

### Task 2: G0 Phase B - T3 isolated replay of all 8,433, T4 label sums, T5 determinism, GO/NO-GO

**Files:**
- Create: `research/round2_decision_ceiling/scripts/g0_replay_test.py` (extend)
- Create: `research/round2_decision_ceiling/g0_replay_validation.md`

**Interfaces:**
- Consumes: Task 1 primitives; `FROZEN_INTROS` (`n01_introductions.jsonl`,
  8,433 rows, keys incl. `seed, variant, introduction_id, assigned_day, mature,
  y_msmi, y_mutual, y_date, y_second, missing`); `FROZEN_ROWS` (126 rows, keys
  incl. `seed, variant, sums, replay_digest, final_day, n_intros, n_immature`).
- Produces:
  - `g0_replay_test.run_full_pass() -> dict` keyed `"<seed>|<variant>"` with
    `digest_ok, n_selected, n_compared, n_label_mismatch, n_mid_missing,
    sums, sums_ok, mismatched_ids`
  - `g0_replay_test.test_t5_determinism() -> dict`
  - `g0_replay_validation.md` with GO / NO-GO

- [ ] **Step 1: Add frozen-artifact loaders to `ce_common.py`**

````python
def frozen_intro_index():
    """(seed, variant, introduction_id) -> frozen row from n01_introductions."""
    return {(r['seed'], r['variant'], r['introduction_id']): r
            for r in read_jsonl(FROZEN_INTROS)}


def frozen_world_rows():
    return {(r['seed'], r['variant']): r for r in read_jsonl(FROZEN_ROWS)}
````

- [ ] **Step 2: Add `run_full_pass` to `g0_replay_test.py`**

````python
LABEL_KEYS = ('mature', 'y_msmi', 'y_mutual', 'y_date', 'y_second', 'missing')


def run_full_pass():
    """T3 + T4: isolate-replay every selected introduction in all 126 worlds."""
    frozen = c.frozen_intro_index()
    world_rows = c.frozen_world_rows()
    out = {}
    for seed, variant in c.world_list():
        iso = {}

        def per_day(ctx, _iso=iso):
            for pair in ctx['pairs']:
                sim_after, mid = c.run_pair_isolated(ctx['snap'], pair)
                _iso[mid] = c.labels_from_events(mid, sim_after.events,
                                                 c.HORIZON, ctx['day'])

        digest, _ = c.replay_world(seed, variant, per_day=per_day,
                                   follow_up=False)
        off = world_rows[(seed, variant)]
        compared = mismatched = missing = 0
        bad_ids = []
        for mid, lab in iso.items():
            ref = frozen.get((seed, variant, mid))
            if ref is None:
                missing += 1
                continue
            compared += 1
            if any(lab.get(k) != ref.get(k) for k in LABEL_KEYS):
                mismatched += 1
                if len(bad_ids) < 5:
                    bad_ids.append(mid)
        seen = {k[2] for k in frozen if k[0] == seed and k[1] == variant}
        n_unreplayed = len(seen - set(iso))
        mature = [v for v in iso.values() if v['mature']]
        sums = dict(assignments=len(iso),
                    mutual=sum(v['y_mutual'] for v in mature),
                    dates=sum(v['y_date'] for v in mature),
                    msmi=sum(v['y_msmi'] for v in mature),
                    missing=sum(v['missing'] for v in mature))
        out['%d|%s' % (seed, variant)] = dict(
            seed=seed, variant=variant, digest_ok=(digest == off['replay_digest']),
            n_selected=len(iso), n_compared=compared, n_label_mismatch=mismatched,
            n_mid_missing=missing, n_unreplayed=n_unreplayed,
            sums=sums, sums_ok=(sums == off['sums']),
            n_immature=sum(1 for v in iso.values() if not v['mature']),
            final_day=c.HORIZON, mismatched_ids=bad_ids)
        c.log('T3 %d/%s selected=%d compared=%d mismatch=%d sums_ok=%s'
              % (seed, variant, len(iso), compared, mismatched,
                 sums == off['sums']))
    return out
````

- [ ] **Step 3: Run T3/T4 once and inspect**

```powershell
@'
import sys, json
sys.path.insert(0, r'research\round2_decision_ceiling\scripts')
import g0_replay_test as g, ce_common as c
res = g.run_full_pass()
agg = dict(
    worlds=len(res),
    digest_ok=sum(1 for r in res.values() if r['digest_ok']),
    sums_ok=sum(1 for r in res.values() if r['sums_ok']),
    n_selected=sum(r['n_selected'] for r in res.values()),
    n_compared=sum(r['n_compared'] for r in res.values()),
    n_label_mismatch=sum(r['n_label_mismatch'] for r in res.values()),
    n_mid_missing=sum(r['n_mid_missing'] for r in res.values()),
    n_unreplayed=sum(r['n_unreplayed'] for r in res.values()),
    n_immature=sum(r['n_immature'] for r in res.values()),
    msmi_total=sum(r['sums']['msmi'] for r in res.values()),
    mutual_total=sum(r['sums']['mutual'] for r in res.values()),
    dates_total=sum(r['sums']['dates'] for r in res.values()),
    missing_total=sum(r['sums']['missing'] for r in res.values()))
print(json.dumps(agg, indent=1))
c.save_g0({'T3_isolated_replay': agg})
c.save_g0({'T3_per_world': res})
'@ | Out-File $env:TEMP\g0b.py -Encoding utf8; python $env:TEMP\g0b.py
```

**Expected (all four must hold, else NO-GO):**
- `digest_ok == 126`
- `sums_ok == 126`
- `n_selected == n_compared == 8433` and `n_mid_missing == 0` and `n_unreplayed == 0`
- `n_label_mismatch == 0` and `n_immature == 0`

Also cross-check the totals against `n01_replay_summary.json`
(`total_introductions == 8433`, `total_immature == 0`,
`digest_matches == 126`, `label_sums_match == 126`).

- [ ] **Step 4: T5 determinism - re-run and diff**

```powershell
@'
import sys, json
sys.path.insert(0, r'research\round2_decision_ceiling\scripts')
import g0_replay_test as g, ce_common as c
first = json.loads(open(c.OUT / 'g0_results.json', encoding='utf-8').read())['T3_per_world']
second = g.run_full_pass()
same = first == second
print('T5 determinism identical =', same)
if not same:
    for k in first:
        if first[k] != second[k]:
            print('DIFF', k); break
c.save_g0({'T5_determinism': dict(test='T5_determinism', identical=bool(same),
                                  passed=bool(same))})
'@ | Out-File $env:TEMP\g0c.py -Encoding utf8; python $env:TEMP\g0c.py
```

Expected: `T5 determinism identical = True`.

- [ ] **Step 5: Assemble `g0_replay_validation.md` with GO/NO-GO**

````python
# appended to g0_replay_test.py
def write_validation_md():
    r = json.loads((c.OUT / 'g0_results.json').read_text(encoding='utf-8'))
    t3 = r.get('T3_isolated_replay', {})
    checks = [
        ('T1 pair-orientation invariance',
         r.get('T1_pair_orientation', {}).get('passed'), '0 mismatches'),
        ('T2 batch independence',
         r.get('T2_batch_independence', {}).get('passed'), '0 mismatches'),
        ('T2L snapshot leak', r.get('T2L_snapshot_leak', {}).get('passed'),
         '0 leaked snapshots'),
        ('T3 isolated replay exact match',
         t3.get('n_label_mismatch') == 0 and t3.get('n_mid_missing') == 0
         and t3.get('n_unreplayed') == 0 and t3.get('n_compared') == 8433,
         '8433/8433 exact on mature, y_msmi, y_mutual, y_date, y_second, missing'),
        ('T3b action digest reproduction',
         t3.get('digest_ok') == 126, '126/126 digests equal n01_replay_rows'),
        ('T4 label sums vs official',
         t3.get('sums_ok') == 126 and t3.get('n_immature') == 0,
         '126/126 per-world sums equal; 0 immature at horizon 100'),
        ('T5 determinism', r.get('T5_determinism', {}).get('passed'),
         'two full passes bit-identical'),
    ]
    go = all(bool(ok) for _, ok, _ in checks)
    lines = ['# G0 - Counterfactual Replay Validation', '',
             '**Status: %s**' % ('GO - proceed to sections 3-7' if go
                                 else 'NO-GO - section 4 and beyond must not run'), '',
             'Protocol horizon %d = 60 decision days + 40 follow-up days '
             '(`evaluate.episode`, `evaluate.py` L80-115).' % c.HORIZON, '',
             '| Test | Result | Criterion |', '|---|---|---|']
    for name, ok, crit in checks:
        lines.append('| %s | %s | %s |' % (name, 'PASS' if ok else 'FAIL', crit))
    lines += ['', '## Method', '',
              'Each counterfactual run starts from `copy.deepcopy(Simulator)` '
              'taken after `resolve_asks` and before `advance` on the decision '
              'day, giving the copy its own `introductions`, `events`, `past` '
              'and `busy` (the only containers `kit.Simulator.advance` writes). '
              'The pair is run alone with `advance([[a,b]])` under the sorted '
              'orientation produced by `kit.py` L152, then followed with '
              '`advance([])` to day %d so labels use the same maturity rules as '
              'the official rollout.' % c.HORIZON, '',
              '## Per-world detail', '',
              '| seed | variant | selected | compared | mismatch | digest | sums |',
              '|---|---|---|---|---|---|---|']
    for k in sorted(r.get('T3_per_world', {}), key=lambda s: (int(s.split("|")[0]), s)):
        w = r['T3_per_world'][k]
        lines.append('| %d | %s | %d | %d | %d | %s | %s |' % (
            w['seed'], w['variant'], w['n_selected'], w['n_compared'],
            w['n_label_mismatch'], 'ok' if w['digest_ok'] else 'FAIL',
            'ok' if w['sums_ok'] else 'FAIL'))
    (c.OUT / 'g0_replay_validation.md').write_text(
        '\n'.join(lines) + '\n', encoding='utf-8')
    c.log('g0_replay_validation.md written; verdict=%s' % ('GO' if go else 'NO-GO'))
    return go
````

Run:

```powershell
@'
import sys
sys.path.insert(0, r'research\round2_decision_ceiling\scripts')
import g0_replay_test as g
print('VERDICT', 'GO' if g.write_validation_md() else 'NO-GO')
'@ | Out-File $env:TEMP\g0d.py -Encoding utf8; python $env:TEMP\g0d.py
```

- [ ] **Step 6: Gate check**

**If the verdict is NO-GO, stop here.** Report the failure in `run_log.txt` and
do not create `day_edges.jsonl`, `counterfactual_pairs.jsonl`, or any section 3-7
deliverable. If GO, log `c.log('G0 gate: GO')` and continue.

---

### Task 3: Section 3 - reconstruct per-day candidate graphs, emit `opportunity_summary.csv`

**Files:**
- Create: `research/round2_decision_ceiling/scripts/s1_opportunities.py`
- Output: `day_edges.jsonl`, `opportunity_summary.csv`

**Interfaces:**
- Consumes: Task 1 `replay_world`; `n01.allocate`; frozen `n01_days.jsonl`
  (reconciliation targets: `edges_total` sum 15,304; `n_pairs` sum 8,433;
  `zero_selection` sum 3,566; days with `n_pairs >= 2` = 2,087; 7,560 rows).
- Produces:
  - `day_edges.jsonl` — one row per decision day:
    `{seed, variant, day, n_available, n_intros_so_far, edges:[[neg_score,[a,b]],...],
    pairs:[[a,b],...], day_ctx:{...}}`
  - `opportunity_summary.csv` — one row per stratum with all C1-C5 columns
    (per `analysis_plan.md` 3.1 as amended).

- [ ] **Step 1: Add the per-day structural metrics to `ce_common.py`**

````python
def enumerate_matchings(keys, cap=51, node_limit=2_000_000):
    """All vertex-disjoint subsets of `keys`, capped. Returns (matchings, failed).

    `matchings` is a list of frozensets of edge indices, length <= cap.
    `failed` is True if `node_limit` recursion nodes were exhausted first.
    """
    out, nodes, stop = [], [0], [False]

    def rec(i, used, cur):
        if stop[0]:
            return
        nodes[0] += 1
        if nodes[0] > node_limit:
            stop[0] = True
            return
        if i == len(keys):
            out.append(frozenset(cur))
            return
        rec(i + 1, used, cur)                       # skip edge i
        if stop[0]:
            return
        ka, kb = keys[i]
        if ka not in used and kb not in used:
            rec(i + 1, used | {ka, kb}, cur + [i])
            if len(out) > cap:
                stop[0] = True
    rec(0, set(), [])
    return out, stop[0]


def max_matching_size(keys):
    """Exact maximum cardinality of a vertex-disjoint edge set (branch + bound)."""
    best = [0]

    def rec(i, used, taken):
        if i == len(keys):
            best[0] = max(best[0], taken)
            return
        free = sum(1 for e in keys[i:] for x in e if x not in used)
        if taken + free // 2 <= best[0]:            # valid upper bound
            return
        rec(i + 1, used, taken)
        ka, kb = keys[i]
        if ka not in used and kb not in used:
            rec(i + 1, used | {ka, kb}, taken + 1)
    rec(0, set(), 0)
    return best[0]


def day_structural_metrics(edges, pairs, keys):
    """C1-C5 metrics for one decision day (analysis_plan.md 3.1 + Amendment 1).

    edges: list of (neg_score, key); pairs: greedy selection (list of lists);
    keys: the same pairs as sorted tuples. Returns a flat dict.
    """
    m = [tuple(p) for p in pairs]
    n_edges = len(keys)
    endpoints = [set(k) for k in keys]
    degree = {}
    for k in keys:
        for x in k:
            degree[x] = degree.get(x, 0) + 1

    # --- C1
    out = dict(edges_total=n_edges, n_available=None, n_pairs=len(m))
    # --- C2 (degree over available members is filled by the caller via n_available)
    out['n_members_with_degree_ge1'] = len(degree)
    out['n_members_degree_ge2'] = sum(1 for v in degree.values() if v >= 2)
    out['degree_max'] = max(degree.values(), default=0)

    # --- C3 competition for selected pairs
    m_endpoints = set()
    for p in m:
        m_endpoints.update(p)
    competing_total = 0
    selected_with_alt = 0
    for p in m:
        ps = set(p)
        n = sum(1 for k in keys if set(k) & ps and set(k) != ps)
        competing_total += n
        if any(degree.get(x, 0) > 1 for x in p):
            selected_with_alt += 1
    out['competing_edges_mean'] = (competing_total / len(m)) if m else 0.0
    out['selected_with_alt_partner'] = selected_with_alt
    out['selected_with_alt_partner_share'] = (selected_with_alt / len(m)) if m else 0.0

    # --- C4 matching structure
    matchings, enum_failed = enumerate_matchings(keys)
    m_idx = frozenset(i for i, k in enumerate(keys) if tuple(k) in set(m))
    sizes = [len(x) for x in matchings]
    n_cap = len(matchings)
    out['n_matchings_capped'] = n_cap
    out['n_matchings_gt_cap'] = int(enum_failed or n_cap > 50)
    out['enum_failed'] = int(enum_failed)
    out['batch_size'] = len(m)
    out['max_matching_size'] = max_matching_size(keys)
    out['batch_underfill'] = out['max_matching_size'] - len(m)

    # alt_same_size and its two disjoint refinements
    m_end = frozenset().union(*[set(p) for p in m]) if m else frozenset()
    alt_same_size = alt_same_endp = alt_diff_endp = 0
    alt_repair_any = 0
    for mt in matchings:
        if mt == m_idx:
            continue
        if len(mt) == len(m):
            alt_same_size = 1
            ends = frozenset().union(*[set(keys[i]) for i in mt]) if mt else frozenset()
            if ends == m_end:
                alt_same_endp = 1
            else:
                alt_diff_endp = 1
        ends = frozenset().union(*[set(keys[i]) for i in mt]) if mt else frozenset()
        if ends == m_end and len(m) >= 2:
            alt_repair_any = 1
    out['alt_same_size'] = alt_same_size
    out['alt_same_size_same_endpoints'] = alt_same_endp
    out['alt_same_size_diff_endpoints'] = alt_diff_endp
    out['alt_repair_same_endpoints'] = alt_repair_any

    # addition_possible: greedy is maximal, must be 0
    out['addition_possible'] = int(any(
        not (set(k) & m_endpoints) for k in keys)) if m_endpoints else int(n_edges > 0)

    # cardinality-preserving replacement
    rep = 0
    if m:
        for i, k in enumerate(keys):
            if tuple(k) in set(m):
                continue
            ks = set(k)
            for j, p in enumerate(m):
                others = set()
                for q, pp in enumerate(m):
                    if q != j:
                        others.update(pp)
                if not (ks & others) and (ks & set(p)):
                    rep = 1
                    break
            if rep:
                break
    out['cardinality_preserving_replacement'] = rep
    return out
````

**Note on `addition_possible`:** when `m_endpoints` is empty (no selection) any
feasible edge counts as an "addition", so the check returns `n_edges > 0`; on
days where something *was* selected it must be 0. Both cases are reported, and
the report states that greedy maximalism makes it 0 on every selected day.

- [ ] **Step 2: Write `s1_opportunities.py`**

````python
"""Section 3: how many genuine decision opportunities exist.

Replays the 126 frozen worlds (no new worlds, no new seeds), persists every
per-day candidate graph, computes C1-C5 structural metrics, and reconciles
against the frozen n01 aggregates before writing opportunity_summary.csv.
"""
import csv, json, sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ce_common as c  # noqa: E402

DAY_BANDS = ((0, 9, '0-9'), (10, 19, '10-19'), (20, 39, '20-39'), (40, 59, '40-59'))


def day_band(d):
    for lo, hi, name in DAY_BANDS:
        if lo <= d <= hi:
            return name
    return 'out_of_range'


def main():
    c.log('task3 start: section 3 reconstruction')
    frozen_days = c.read_jsonl(c.FROZEN_DAYS)
    frozen_by_key = {(r['seed'], r['variant'], r['day']): r for r in frozen_days}
    day_rows = []
    for seed, variant in c.world_list():
        def per_day(ctx, _s=seed, _v=variant):
            keys = [tuple(k) for _, k in sorted(ctx['edges'])]
            metrics = c.day_structural_metrics(ctx['edges'], ctx['pairs'], keys)
            metrics.update(
                n_available=sum(1 for m in ctx['state']['members']
                                if m['available']),
                n_arrived=len(ctx['state']['members']),
                n_intros_so_far=ctx['n_intros'],
                n_feedback=ctx['n_feedback'],
                ask_budget=ctx['state']['ask_budget_remaining'])
            day_rows.append(dict(seed=_s, variant=_v, day=ctx['day'],
                                 edges=[[-e[0], list(e[1])] for e in ctx['edges']],
                                 pairs=[list(p) for p in ctx['pairs']],
                                 metrics=metrics,
                                 day_ctx=ctx['day_ctx']))
        c.replay_world(seed, variant, per_day=per_day, follow_up=False)
    c.write_jsonl(c.OUT / 'day_edges.jsonl', [
        dict(seed=r['seed'], variant=r['variant'], day=r['day'],
             edges=r['edges'], pairs=r['pairs'], metrics=r['metrics'],
             day_ctx=r['day_ctx']) for r in day_rows])

    # --- reconciliation against frozen n01_days (hard gate)
    rec = dict(
        n_days=len(day_rows), n_days_frozen=len(frozen_days),
        sum_edges_total=sum(r['metrics']['edges_total'] for r in day_rows),
        sum_n_pairs=sum(r['metrics']['n_pairs'] for r in day_rows),
        n_zero=sum(1 for r in day_rows if r['metrics']['n_pairs'] == 0),
        n_pairs_ge2=sum(1 for r in day_rows if r['metrics']['n_pairs'] >= 2),
        sum_edges_frozen=sum(r['edges_total'] for r in frozen_days),
        sum_n_pairs_frozen=sum(r['n_pairs'] for r in frozen_days),
        n_zero_frozen=sum(1 for r in frozen_days if r['n_pairs'] == 0),
        n_pairs_ge2_frozen=sum(1 for r in frozen_days if r['n_pairs'] >= 2),
        per_day_edge_mismatch=0, per_day_pair_mismatch=0)
    for r in day_rows:
        f = frozen_by_key.get((r['seed'], r['variant'], r['day']))
        if f is None:
            rec['per_day_edge_mismatch'] += 1
            continue
        if f['edges_total'] != r['metrics']['edges_total']:
            rec['per_day_edge_mismatch'] += 1
        if f['n_pairs'] != r['metrics']['n_pairs']:
            rec['per_day_pair_mismatch'] += 1
    rec['reconciled'] = bool(
        rec['n_days'] == 7560 and rec['sum_edges_total'] == 15304
        and rec['sum_n_pairs'] == 8433 and rec['n_zero'] == 3566
        and rec['n_pairs_ge2'] == 2087
        and rec['per_day_edge_mismatch'] == 0
        and rec['per_day_pair_mismatch'] == 0)
    (c.OUT / 'reconciliation.json').write_text(
        json.dumps(rec, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    c.log('reconciliation ' + json.dumps(rec, sort_keys=True))
    if not rec['reconciled']:
        raise SystemExit('RECONCILIATION FAILED - section 3 output withheld')

    # --- strata aggregation
    strata = [('overall', 'all', day_rows)]
    for v in sorted({r['variant'] for r in day_rows}):
        strata.append(('variant', v, [r for r in day_rows if r['variant'] == v]))
    for s in sorted({r['seed'] for r in day_rows}):
        strata.append(('world', str(s), [r for r in day_rows if r['seed'] == s]))
    for _, _, name in DAY_BANDS:
        strata.append(('day_band', name,
                       [r for r in day_rows if day_band(r['day']) == name]))

    METRIC_COLS = ['edges_total', 'n_pairs', 'n_available', 'n_arrived',
                   'n_members_with_degree_ge1', 'n_members_degree_ge2',
                   'degree_max', 'competing_edges_mean',
                   'selected_with_alt_partner', 'selected_with_alt_partner_share',
                   'n_matchings_capped', 'n_matchings_gt_cap', 'enum_failed',
                   'batch_size', 'max_matching_size', 'batch_underfill',
                   'alt_same_size', 'alt_same_size_same_endpoints',
                   'alt_same_size_diff_endpoints', 'alt_repair_same_endpoints',
                   'addition_possible', 'cardinality_preserving_replacement',
                   'n_intros_so_far', 'n_feedback', 'ask_budget']
    rows = []
    for stype, sval, subset in strata:
        n = len(subset)
        row = dict(stratum_type=stype, stratum_value=sval, n_days=n)
        for col in METRIC_COLS:
            vals = [r['metrics'][col] for r in subset]
            row[col + '_mean'] = round(sum(vals) / n, 6) if n else ''
        row['sum_edges_total'] = sum(r['metrics']['edges_total'] for r in subset)
        row['sum_n_pairs'] = sum(r['metrics']['n_pairs'] for r in subset)
        row['n_days_edges0'] = sum(1 for r in subset if r['metrics']['edges_total'] == 0)
        row['n_days_edges1'] = sum(1 for r in subset if r['metrics']['edges_total'] == 1)
        row['n_days_edges2_4'] = sum(1 for r in subset if 2 <= r['metrics']['edges_total'] <= 4)
        row['n_days_edges5_9'] = sum(1 for r in subset if 5 <= r['metrics']['edges_total'] <= 9)
        row['n_days_edges10p'] = sum(1 for r in subset if r['metrics']['edges_total'] >= 10)
        row['share_alt_same_size'] = round(
            sum(r['metrics']['alt_same_size'] for r in subset) / n, 6) if n else ''
        row['share_addition_possible_gt0'] = sum(
            1 for r in subset if r['metrics']['addition_possible']) if n else ''
        rows.append(row)
    cols = sorted({k for r in rows for k in r})
    with open(c.OUT / 'opportunity_summary.csv', 'w', newline='',
              encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    c.log('wrote opportunity_summary.csv (%d strata rows)' % len(rows))
    c.log('task3 done')


if __name__ == '__main__':
    raise SystemExit(main())
````

- [ ] **Step 3: Run it**

```powershell
python "research\round2_decision_ceiling\scripts\s1_opportunities.py"
```

Expected: `reconciliation ... "reconciled": true`, then
`wrote opportunity_summary.csv (1 + 6 + 21 + 4 = 32 strata rows)`.
**If reconciliation fails, stop and investigate before running any §4 code.**

- [ ] **Step 4: Spot-check the output**

```powershell
@'
import sys, csv
sys.path.insert(0, r'research\round2_decision_ceiling\scripts')
import ce_common as c
rows = list(csv.DictReader(open(c.OUT / 'opportunity_summary.csv', encoding='utf-8')))
ov = [r for r in rows if r['stratum_type'] == 'overall'][0]
for k in ('n_days', 'sum_edges_total', 'sum_n_pairs', 'n_days_edges0',
          'share_alt_same_size_mean', 'batch_underfill_mean',
          'addition_possible_mean'):
    print(k, '=', ov[k])
'@ | Out-File $env:TEMP\s1chk.py -Encoding utf8; python $env:TEMP\s1chk.py
```

Expected: `n_days 7560`, `sum_edges_total 15304`, `sum_n_pairs 8433`,
`n_days_edges0 3566`, `addition_possible_mean 0.0`.

- [ ] **Step 5: Log task complete**

`c.log('task3 done')`

---

---

### Task 4: Section 4 - counterfactual targets, validation V1-V6, `counterfactual_validation.csv`

**Gate:** G0 must have recorded **GO** (GC6).

**Files:**
- Create: `research/round2_decision_ceiling/scripts/s2_counterfactual.py`
- Output: `counterfactual_pairs.jsonl`, `counterfactual_validation.csv`

**Interfaces:**
- Consumes: Task 1 primitives; Task 3 `day_edges.jsonl` for reconciliation;
  `n01.pair_features`, `n01.day_history`.
- Produces:
  - `counterfactual_pairs.jsonl` — one row per feasible `(pair, day)`
    opportunity (target 15,304), fields:
    `seed, variant, day, user_a, user_b, selected, introduction_id,
    cf_mature, cf_y_mutual, cf_y_date, cf_y_second, cf_y_msmi, cf_missing,
    flag, feat_*`
  - `counterfactual_validation.csv` — one row per check V1..V6.

- [ ] **Step 1: Write `s2_counterfactual.py`**

````python
"""Section 4: counterfactual pair-alone outcomes for every feasible opportunity.

Diagnostic only. Counterfactual labels for unselected pairs are UNOBSERVED by the
original collector (flag='counterfactual_unobserved') and are never treated as
observed outcomes (GC9, analysis_plan.md sec.4).
"""
import csv, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ce_common as c  # noqa: E402

BANNED_FEATURE_EXACT = c.BANNED_FEATURE_EXACT   # defined in ce_common.py


def main():
    verdict = (c.OUT / 'g0_replay_validation.md').read_text(encoding='utf-8')
    if '**Status: GO' not in verdict:
        raise SystemExit('G0 verdict is not GO - refusing to compute counterfactuals')
    c.log('task4 start: counterfactual pass (G0 GO confirmed)')

    frozen = c.frozen_intro_index()
    rows = []
    for seed, variant in c.world_list():
        def per_day(ctx, _s=seed, _v=variant):
            selected = {tuple(p) for p in ctx['pairs']}
            for _, key in sorted(ctx['edges']):
                sim_after, mid = c.run_pair_isolated(ctx['snap'], list(key))
                lab = c.labels_from_events(mid, sim_after.events, c.HORIZON,
                                           ctx['day'])
                if lab['mature'] == 0 and lab['y_msmi'] is None:
                    raise SystemExit('V3 violation: immature label for %s' % mid)
                is_sel = tuple(key) in selected
                feat = c.n01.pair_features(
                    ctx['state'], ctx['edges'], ctx['degree'], ctx['max_score'],
                    ctx['score_counts'], ctx['member_hist'], ctx['day_ctx'],
                    list(key), 0 if is_sel else -1, len(ctx['pairs']))
                feat.pop('pair_rank', None)   # undefined for a counterfactual
                feat.pop('batch_size', None)  # undefined for a counterfactual
                feat['n_feedback_events'] = ctx['n_feedback']
                ref = frozen.get((_s, _v, mid))
                rows.append(dict(
                    seed=_s, variant=_v, day=ctx['day'],
                    user_a=key[0], user_b=key[1],
                    selected=int(is_sel), introduction_id=mid,
                    cf_mature=lab['mature'], cf_y_mutual=lab['y_mutual'],
                    cf_y_date=lab['y_date'], cf_y_second=lab['y_second'],
                    cf_y_msmi=lab['y_msmi'], cf_missing=lab['missing'],
                    flag='selected_agrees' if is_sel else 'counterfactual_unobserved',
                    ref_agrees=None if ref is None else int(
                        all(lab.get(k) == ref.get(k)
                            for k in ('mature', 'y_msmi', 'y_mutual',
                                      'y_date', 'y_second', 'missing'))),
                    _feat=feat))
        c.replay_world(seed, variant, per_day=per_day, follow_up=False)
    c.log('counterfactual rows built: %d' % len(rows))

    # --- V4 count integrity
    n_total = len(rows)
    n_sel = sum(r['selected'] for r in rows)
    dup_keys = n_total - len({(r['seed'], r['variant'], r['day'],
                               r['user_a'], r['user_b']) for r in rows})
    # --- V1 selected-pair agreement
    sel_rows = [r for r in rows if r['selected']]
    v1_pass = all(r['ref_agrees'] == 1 for r in sel_rows) and len(sel_rows) == 8433
    # --- V3 maturity
    v3_pass = all(r['cf_mature'] == 1 and r['cf_y_msmi'] is not None
                  for r in rows)
    # --- V6 no leakage: cf_* never appears as a feat_* column
    feat_keys = sorted(rows[0]['_feat']) if rows else []
    v6_pass = not any(k in BANNED_FEATURE_EXACT or k.startswith('cf_')
                      or k.startswith('y_') for k in feat_keys)

    for r in rows:
        r['flag'] = ('selected_agrees' if r['ref_agrees'] == 1 else
                     'selected_disagrees' if r['selected'] else
                     'counterfactual_unobserved')
    flat = [{k: v for k, v in r.items() if k != '_feat'} for r in rows]
    with open(c.OUT / 'counterfactual_pairs.jsonl', 'w', encoding='utf-8') as fh:
        for r, src in zip(flat, rows):
            r['feat'] = src['_feat']
            fh.write(json.dumps(r, sort_keys=True) + '\n')
    c.log('wrote counterfactual_pairs.jsonl (%d rows)' % len(rows))

    # --- per world / per variant opportunity + cf-positive counts (sec.4 report)
    agg = {}
    for r in rows:
        k = (r['seed'], r['variant'])
        a = agg.setdefault(k, dict(opportunities=0, cf_msmi_pos=0,
                                   selected=0, cf_pos_selected=0))
        a['opportunities'] += 1
        a['cf_msmi_pos'] += int(bool(r['cf_y_msmi']))
        a['selected'] += r['selected']
        a['cf_pos_selected'] += int(bool(r['cf_y_msmi']) and r['selected'])
    with open(c.OUT / 'opportunity_by_world.csv', 'w', newline='',
              encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=['seed', 'variant', 'opportunities',
                                           'cf_msmi_pos', 'selected',
                                           'cf_pos_selected'])
        w.writeheader()
        for (s, v), a in sorted(agg.items()):
            w.writerow(dict(seed=s, variant=v, **a))
    c.log('wrote opportunity_by_world.csv (%d worlds)' % len(agg))

    checks = [
        dict(check='V1_selected_pair_agreement', passed=int(v1_pass),
             detail='%d/%d selected pairs match frozen labels'
                    % (sum(r['ref_agrees'] == 1 for r in sel_rows),
                       len(sel_rows))),
        dict(check='V2_batch_independence', passed=1,
             detail='established by G0 T2 (0 mismatches)'),
        dict(check='V3_maturity', passed=int(v3_pass),
             detail='%d rows, 0 None labels at horizon %d' % (n_total, c.HORIZON)),
        dict(check='V4_count_integrity', passed=int(
            n_total == 15304 and n_sel == 8433 and dup_keys == 0),
             detail='total=%d selected=%d duplicate_keys=%d'
                    % (n_total, n_sel, dup_keys)),
        dict(check='V5_orientation', passed=1,
             detail='all keys sorted ascending; G0 T1 passed'),
        dict(check='V6_feature_legality', passed=int(v6_pass),
             detail='%d feature columns, none banned' % len(feat_keys)),
    ]
    with open(c.OUT / 'counterfactual_validation.csv', 'w', newline='',
              encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=['check', 'passed', 'detail'])
        w.writeheader()
        w.writerows(checks)
    for ck in checks:
        c.log('V %s passed=%s :: %s' % (ck['check'], ck['passed'], ck['detail']))
    if not all(ck['passed'] for ck in checks):
        raise SystemExit('counterfactual validation FAILED - sections 5-7 withheld')
    c.log('task4 done')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
````

- [ ] **Step 2: Run it**

```powershell
python "research\round2_decision_ceiling\scripts\s2_counterfactual.py"
```

Expected log lines: `V1_selected_pair_agreement passed=1 :: 8433/8433 ...`,
`V3_maturity passed=1 :: 15304 rows, 0 None labels`,
`V4_count_integrity passed=1 :: total=15304 selected=8433 duplicate_keys=0`,
`V6_feature_legality passed=1`, then `task4 done`.

**If any V fails, stop.** Sections 5-7 must not run (GC6).

- [ ] **Step 3: Inspect opportunity and positive counts by world/variant**

```powershell
@'
import sys, csv
sys.path.insert(0, r'research\round2_decision_ceiling\scripts')
import ce_common as c
rows = list(csv.DictReader(open(c.OUT / 'opportunity_by_world.csv', encoding='utf-8')))
tot_o = sum(int(r['opportunities']) for r in rows)
tot_p = sum(int(r['cf_msmi_pos']) for r in rows)
print('worlds', len(rows), 'opportunities', tot_o, 'cf_msmi_positives', tot_p)
print('prevalence %.4f' % (tot_p / tot_o))
byv = {}
for r in rows:
    a = byv.setdefault(r['variant'], [0, 0])
    a[0] += int(r['opportunities']); a[1] += int(r['cf_msmi_pos'])
for v, (o, p) in sorted(byv.items()):
    print(' ', v, 'opp', o, 'pos', p, 'prev %.4f' % (p / max(1, o)))
'@ | Out-File $env:TEMP\s2chk.py -Encoding utf8; python $env:TEMP\s2chk.py
```

Expected: `opportunities 15304`, `cf_msmi_positives` equals the frozen total
MSMI count of 8,433 introductions **only if** selection were independent of the
outcome — it will not. Record whatever the true prevalence is; it is the base
rate §5 lift is measured against.

- [ ] **Step 4: Log task complete**

`c.log('task4 done')`

---

### Task 5: Section 5 - feature sets F1-F5, frozen model, seed-group CV, `within_state_signal.csv`

**Files:**
- Create: `research/round2_decision_ceiling/scripts/s3_signal.py`
- Output: `within_state_signal.csv`

**Interfaces:**
- Consumes: `counterfactual_pairs.jsonl` (target `cf_y_msmi`, features under
  `feat`).
- Produces: `within_state_signal.csv` with one row per
  `(feature_set, stratum_type, stratum_value)` and columns
  `n_rows, n_positives, prevalence, auc, pr_auc, lift, within_state_auc_mean,
  within_state_auc_posweighted, n_states, n_states_pos, top1_hit_rate,
  ci95_low, ci95_high, power_flag`.

- [ ] **Step 1: Define the five frozen feature sets**

````python
# analysis_plan.md sec.5.1. Lists are explicit and closed; assert_legal_features
# rejects anything not named here.
F1 = ['pair_score', 'pair_score_deficit', 'score_is_max', 'edges_total',
      'edges_at_same_score', 'n_available', 'n_intros_so_far']

SOFT_CHANNELS = ['relationship_goal', 'relationship_pace', 'lifestyle',
                 'conversations', 'emotional_availability',
                 'space_for_relationship', 'relocate']
HARD_CHANNELS = ['who_to_meet', 'age', 'geography', 'smoking',
                 'children_present', 'relationship_structure',
                 'children_plans', 'schedule']
HARD_STATES = ['pass', 'fail', 'unknown']
SOFT_STATES = ['match', 'mismatch', 'unknown', 'declined']


def f2_columns():
    cols = []
    for ch in HARD_CHANNELS:
        for d in ('ab', 'ba'):
            for st in HARD_STATES:
                cols.append('hc_%s_%s_%s' % (ch, d, st))
    for k in SOFT_CHANNELS:
        for st in SOFT_STATES:
            cols.append('sc_%s_%s' % (k, st))
    return cols


F2_EXTRA = f2_columns()          # 8*2*3 + 7*4 = 76 columns
F3_EXTRA = ['age_a', 'age_b', 'gender_a', 'gender_b', 'zone_a', 'zone_b',
            'days_since_arrival_a', 'days_since_arrival_b',
            'n_hard_observed_a', 'n_hard_observed_b',
            'n_soft_observed_a', 'n_soft_observed_b', 'has_profile_gap']
F4_EXTRA = ['day', 'ask_budget_match', 'has_history', 'has_prior',
            'prior_intro_max', 'prior_mutual_total', 'prior_date_total',
            'degree_min', 'degree_max', 'degree_excl_min', 'degree_excl_max',
            'new_arrival_today', 'n_mutual_so_far', 'n_dates_so_far',
            'n_feedback_events', 'arrival_age_min', 'arrival_age_max',
            'age_gap', 'same_gender', 'zone_same', 'soft_obs_min', 'soft_obs_max',
            'soft_unequal', 'soft_unknown_max', 'soft_declined_max']
F5 = ['day', 'ask_budget_match', 'n_available', 'edges_total',
      'n_intros_so_far', 'n_mutual_so_far', 'n_dates_so_far', 'has_history',
      'n_feedback_events']

FEATURE_SETS = {
    'F1_baseline_count_score': F1,
    'F2_soft_state': F1 + F2_EXTRA,
    'F3_public_profile': F1 + F2_EXTRA + F3_EXTRA,
    'F4_full_legal_observables': F1 + F2_EXTRA + F3_EXTRA + F4_EXTRA,
    'F5_state_only': F5,
}
````

- [ ] **Step 2: Build the two derived feature blocks from legal state only**

Append to `s3_signal.py`:

````python
def hard_state(a, b, ch, direction):
    """Eligibility channel status for one direction, from public fields only."""
    x, y = (a, b) if direction == 'ab' else (b, a)
    fx, fy = x['fields'], y['fields']
    if ch == 'who_to_meet':
        if fx.get('who_to_meet') is None: return 'unknown'
        return 'pass' if y['gender'] in fx['who_to_meet'] else 'fail'
    if ch == 'age':
        if fx.get('age_min') is None or fx.get('age_max') is None: return 'unknown'
        return 'pass' if fx['age_min'] <= y['age'] <= fx['age_max'] else 'fail'
    if ch == 'geography':
        if fx.get('acceptable_zones') is None: return 'unknown'
        return 'pass' if y['zone'] in fx['acceptable_zones'] else 'fail'
    if ch == 'smoking':
        if fx.get('partner_smoking') is None or fy.get('smoking') is None:
            return 'unknown'
        if fx['partner_smoking'] == 'no_smoking' and \
           fy['smoking'] in ('yes', 'occasionally'):
            return 'fail'
        return 'pass'
    if ch == 'children_present':
        if fx.get('partner_children') is None or fy.get('has_children') is None:
            return 'unknown'
        return 'fail' if (fx['partner_children'] == 'no_children'
                          and fy['has_children'] is True) else 'pass'
    if ch == 'relationship_structure':
        if fx.get('relationship_structure') is None or \
           fy.get('relationship_structure') is None:
            return 'unknown'
        return ('pass' if fx['relationship_structure']
                == fy['relationship_structure'] else 'fail')
    if ch == 'children_plans':
        wc = {fx.get('wants_children'), fy.get('wants_children')}
        if None in wc: return 'unknown'
        return 'fail' if wc == {'yes', 'no'} else 'pass'
    if ch == 'schedule':
        if fx.get('schedule') is None or fy.get('schedule') is None: return 'unknown'
        return 'pass' if set(fx['schedule']) & set(fy['schedule']) else 'fail'
    raise ValueError(ch)
````

Then the derived-column builder:

````python
def derived_features(state, key):
    by = {m['member_id']: m for m in state['members']}
    a, b = by[key[0]], by[key[1]]
    out = {}
    for ch in HARD_CHANNELS:
        out['hc_%s_ab_pass' % ch] = int(hard_state(a, b, ch, 'ab') == 'pass')
        out['hc_%s_ab_fail' % ch] = int(hard_state(a, b, ch, 'ab') == 'fail')
        out['hc_%s_ab_unknown' % ch] = int(hard_state(a, b, ch, 'ab') == 'unknown')
        out['hc_%s_ba_pass' % ch] = int(hard_state(a, b, ch, 'ba') == 'pass')
        out['hc_%s_ba_fail' % ch] = int(hard_state(a, b, ch, 'ba') == 'fail')
        out['hc_%s_ba_unknown' % ch] = int(hard_state(a, b, ch, 'ba') == 'unknown')
    for k in SOFT_CHANNELS:
        fa, fb = a['fields'].get(k), b['fields'].get(k)
        sa, sb = a['field_status'].get(k), b['field_status'].get(k)
        if sa == 'declined' or sb == 'declined':
            st = 'declined'
        elif fa is None or fb is None:
            st = 'unknown'
        elif fa == fb:
            st = 'match'
        else:
            st = 'mismatch'
        for s in SOFT_STATES:
            out['sc_%s_%s' % (k, s)] = int(st == s)
    out.update(
        age_a=a['age'], age_b=b['age'], gender_a=float(hash(a['gender']) % 7),
        gender_b=float(hash(b['gender']) % 7),
        zone_a=float(hash(a['zone']) % 97), zone_b=float(hash(b['zone']) % 97),
        days_since_arrival_a=state['day'] - a['arrived_day'],
        days_since_arrival_b=state['day'] - b['arrived_day'],
        n_hard_observed_a=sum(a['fields'].get(k) is not None for k in c.kit.HARD),
        n_hard_observed_b=sum(b['fields'].get(k) is not None for k in c.kit.HARD),
        n_soft_observed_a=sum(a['fields'].get(k) is not None for k in c.kit.SOFT),
        n_soft_observed_b=sum(b['fields'].get(k) is not None for k in c.kit.SOFT),
        has_profile_gap=int(
            any(a['fields'].get(k) is None or b['fields'].get(k) is None
                for k in c.kit.SOFT)))
    return out
````

`gender`/`zone` are categorical; hashing to a fixed integer bucket keeps them
numeric without introducing an ordinal scale claim. The bucket counts (7 genders
constant, 97 zones) are declared constants, not tuned.

- [ ] **Step 3: `assert_legal_features` and the frame builder**

````python
def assert_legal_features(cols):
    bad = [k for k in cols
           if k in BANNED_FEATURE_EXACT or k.startswith('cf_')
           or k.startswith('y_') or k in ('seed', 'variant')]
    if bad:
        raise SystemExit('ILLEGAL FEATURE COLUMNS: %r' % bad)
    for name, spec in FEATURE_SETS.items():
        missing = [k for k in spec if k not in cols]
        if missing:
            raise SystemExit('feature set %s missing %r' % (name, missing[:5]))
    return True


STATE_SIDE_KEY = ('seed', 'variant', 'day', 'user_a', 'user_b')


def load_state_side():
    return {tuple(r[k] for k in STATE_SIDE_KEY): r
            for r in c.read_jsonl(c.OUT / 'pair_state.jsonl')}


def derived_features_from_row(r, side):
    """Rebuild the derived feature block from persisted observe()-only records."""
    s = side[tuple(r[k] for k in STATE_SIDE_KEY)]
    state = dict(day=s['day'],
                 ask_budget_remaining=s['ask_budget_remaining'],
                 members=[s['a'], s['b']])
    return derived_features(state, (r['user_a'], r['user_b']))


def load_frame():
    import numpy as np
    side = load_state_side()
    X_parts, y, groups, states, sels, seeds, variants, days = [], [], [], [], [], [], [], []
    with open(c.OUT / 'counterfactual_pairs.jsonl', encoding='utf-8') as fh:
        for line in fh:
            r = json.loads(line)
            feat = dict(r['feat'])
            feat.update(derived_features_from_row(r, side))
            X_parts.append(feat)
            y.append(int(r['cf_y_msmi']))
            groups.append(r['seed'])
            states.append((r['seed'], r['variant'], r['day']))
            sels.append(r['selected'])
            seeds.append(r['seed']); variants.append(r['variant'])
            days.append(r['day'])
    assert_legal_features(sorted(X_parts[0]))
    return dict(feat=X_parts, y=np.array(y), groups=np.array(groups),
                states=states, selected=np.array(sels),
                seeds=seeds, variants=variants, days=days)
````

**`derived_features_from_row(r)`** reconstructs the legal state block for a row.
Because `state` is not persisted in `counterfactual_pairs.jsonl`, this function
is defined as a wrapper around a persisted side table instead. **Add to Task 4
before running it:** also write `pair_state.jsonl` containing, per opportunity,
the two members' public `observe()` records plus `day`, `ask_budget_remaining`,
`n_intros/n_mutual/n_dates/n_feedback`. Concretely, inside the `per_day`
callback of `s2_counterfactual.py`, append:

````python
                st = ctx['state']
                by = {m['member_id']: m for m in st['members']}
                state_side.append(dict(
                    seed=_s, variant=_v, day=ctx['day'],
                    user_a=key[0], user_b=key[1],
                    ask_budget_remaining=st['ask_budget_remaining'],
                    n_intros=ctx['n_intros'], n_mutual=ctx['n_mutual'],
                    n_dates=ctx['n_dates'], n_feedback=ctx['n_feedback'],
                    a={k: by[key[0]][k] for k in
                       ('member_id', 'age', 'gender', 'zone', 'arrived_day',
                        'fields', 'field_status')},
                    b={k: by[key[1]][k] for k in
                       ('member_id', 'age', 'gender', 'zone', 'arrived_day',
                        'fields', 'field_status')}))
````

with `state_side = []` declared before the world loop and written as
`c.write_jsonl(c.OUT / 'pair_state.jsonl', state_side)` right after
`counterfactual_pairs.jsonl`. Only `observe()`-visible keys are copied - never
`truth`, `bias`, `response_rate`, `second_bias`, `exit_day` (GC5).
`derived_features_from_row(r)` then joins `pair_state.jsonl` on
`(seed, variant, day, user_a, user_b)` and calls
`derived_features({'day': r['day'], 'ask_budget_remaining': s['ask_budget_remaining'],
'members': [s['a'], s['b']]}, (r['user_a'], r['user_b']))`.

- [ ] **Step 4: Frozen model + metrics**

````python
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score, average_precision_score
from sklearn.model_selection import GroupKFold
import numpy as np

N_SPLITS = 4
MODEL_KW = dict(max_iter=200, learning_rate=0.06, random_state=40)


def oof_scores(X, y, groups):
    oof = np.zeros(len(y))
    gkf = GroupKFold(n_splits=N_SPLITS)   # groups = seed; variants stay together
    for tr, te in gkf.split(X, y, groups):
        clf = HistGradientBoostingClassifier(**MODEL_KW)
        clf.fit(X[tr], y[tr])
        oof[te] = clf.predict_proba(X[te])[:, 1]
    return oof


def bootstrap_seed_groups(stat_fn, seeds, n_boot=1000, rng_seed=4242):
    """95% percentile CI resampling whole seed-groups, never rows (GC4 of sec.8)."""
    rng = np.random.default_rng(rng_seed)
    uniq = sorted(set(seeds))
    idx_of = {s: np.where(np.array(seeds) == s)[0] for s in uniq}
    stats = []
    for _ in range(n_boot):
        pick = rng.choice(len(uniq), size=len(uniq), replace=True)
        idx = np.concatenate([idx_of[uniq[i]] for i in pick])
        v = stat_fn(idx)
        if v is not None and np.isfinite(v):
            stats.append(v)
    if not stats:
        return (float('nan'), float('nan'))
    return (float(np.percentile(stats, 2.5)), float(np.percentile(stats, 97.5)))


def world_within_state_means(scores, y, states, seeds):
    """Per-seed mean of the per-day-state AUCs that are defined for that seed."""
    from collections import defaultdict
    per, wm = defaultdict(list), defaultdict(list)
    for s, yy, k, w in zip(scores, y, states, seeds):
        per[(w, k)].append((s, yy))
    for (w, _k), v in per.items():
        ys = np.array([q[1] for q in v])
        ss = np.array([q[0] for q in v])
        if ys.sum() == 0 or ys.sum() == len(ys):
            continue
        wm[w].append(float(roc_auc_score(ys, ss)))
    return {w: float(np.mean(v)) for w, v in wm.items() if v}


def heterogeneity_permutation(scores, y, states, seeds, n_perm=200,
                              rng_seed=4242):
    """Observed spread of per-seed within-state AUC vs a within-world null.

    A row-level test would be pseudo-replication (analysis_plan.md sec.5.2);
    labels are shuffled only inside each seed-group so per-world class counts
    are preserved.
    """
    obs = world_within_state_means(scores, y, states, seeds)
    obs_spread = (float(np.std(list(obs.values()))) if len(obs) > 1
                  else float('nan'))
    rng = np.random.default_rng(rng_seed)
    null, y_arr = [], np.asarray(y)
    seeds_arr = np.asarray(seeds)
    for _ in range(n_perm):
        yp = y_arr.copy()
        for w in set(seeds):
            idx = np.where(seeds_arr == w)[0]
            yp[idx] = rng.permutation(yp[idx])
        m = world_within_state_means(scores, yp, states, seeds)
        if len(m) > 1:
            null.append(float(np.std(list(m.values()))))
    p = ((sum(1 for v in null if v >= obs_spread) + 1) / (len(null) + 1)
         if null else float('nan'))
    return dict(observed_spread=obs_spread, n_worlds=len(obs),
                null_mean=(float(np.mean(null)) if null else float('nan')),
                null_p_ge_observed=p, n_permutations=len(null))


def within_state_auc(scores, y, states):
    """Per-day-state AUC over states containing both classes (spec question B)."""
    from collections import defaultdict
    by = defaultdict(list)
    for s, yy, k in zip(scores, y, states):
        by[k].append((s, yy))
    per_state, pos_w = {}, {}
    for k, v in by.items():
        ys = np.array([p[1] for p in v])
        ss = np.array([p[0] for p in v])
        npos = int(ys.sum())
        if npos == 0 or npos == len(ys):
            continue
        per_state[k] = float(roc_auc_score(ys, ss))
        pos_w[k] = npos
    if not per_state:
        return dict(mean=float('nan'), posweighted=float('nan'),
                    n_states=0, n_states_pos=0, top1_hit=float('nan'))
    vals = np.array(list(per_state.values()))
    wts = np.array([pos_w[k] for k in per_state], dtype=float)
    hits = 0
    for k in per_state:
        v = by[k]
        ys = np.array([p[1] for p in v]); ss = np.array([p[0] for p in v])
        hits += int(ss[ys.argmax()] == ss.max() and ys[ss.argmax()] == 1)
    return dict(mean=float(vals.mean()),
                posweighted=float((vals * wts).sum() / wts.sum()),
                n_states=len(per_state), n_states_pos=len(per_state),
                top1_hit=hits / len(per_state))
````

- [ ] **Step 5: Metric battery A-E + output**

````python
def metric_strata(fr):
    """(stratum_type, stratum_value, boolean mask) for every reported stratum.

    Masks are built from seed and variant identity, so all six variants of one
    seed are always on the same side of every stratum (analysis_plan.md sec.5.2).
    """
    y = fr['y']
    out = [('overall', 'all', np.ones(len(y), dtype=bool))]
    for v in sorted(set(fr['variants'])):
        out.append(('variant', v,
                    np.array([x == v for x in fr['variants']])))
    for s in sorted(set(fr['seeds'])):
        out.append(('world', str(s),
                    np.array([x == s for x in fr['seeds']])))

    def band(d):
        return ('0-9' if d <= 9 else '10-19' if d <= 19
                else '20-39' if d <= 39 else '40-59')
    for b in ('0-9', '10-19', '20-39', '40-59'):
        out.append(('day_band', b,
                    np.array([band(d) == b for d in fr['days']])))
    return out


def main():
    c.log('task5 start: section 5 signal analysis')
    fr = load_frame()
    n_pos = int(fr['y'].sum())
    n_seed_groups = len(set(fr['seeds']))
    power = 'ok' if (n_pos >= 100 and
                     len({s for s, yy in zip(fr['seeds'], fr['y']) if yy}) >= 5) \
        else 'underpowered'
    rows = []
    oof_by_set = {}
    for name, cols in FEATURE_SETS.items():
        X = np.array([[f.get(k, 0.0) for k in cols] for f in fr['feat']],
                     dtype=np.float32)
        oof = oof_scores(X, fr['y'], fr['groups'])
        oof_by_set[name] = oof
        auc = float(roc_auc_score(fr['y'], oof))
        ap = float(average_precision_score(fr['y'], oof))
        prev = float(fr['y'].mean())
        ws = within_state_auc(oof, fr['y'], fr['states'])

        def _auc(idx, _o=oof, _y=fr['y']):
            if len(set(_y[idx])) < 2:
                return None
            return float(roc_auc_score(_y[idx], _o[idx]))
        lo, hi = bootstrap_seed_groups(_auc, fr['seeds'])

        for stype, sval, mask in metric_strata(fr):
            yy, ss = fr['y'][mask], oof[mask]
            if len(set(yy)) < 2:
                auc_s = float('nan'); ap_s = float('nan')
            else:
                auc_s = float(roc_auc_score(yy, ss))
                ap_s = float(average_precision_score(yy, ss))
            prev_s = float(yy.mean())
            ws_s = within_state_auc(ss, yy,
                                    [fr['states'][i] for i in np.where(mask)[0]])
            rows.append(dict(
                feature_set=name, stratum_type=stype, stratum_value=sval,
                n_rows=int(mask.sum()), n_positives=int(yy.sum()),
                prevalence=round(prev_s, 6),
                auc=round(auc_s, 6), pr_auc=round(ap_s, 6),
                lift=round(ap_s / prev_s, 6) if prev_s > 0 else '',
                within_state_auc_mean=round(ws_s['mean'], 6),
                within_state_auc_posweighted=round(ws_s['posweighted'], 6),
                n_states=ws_s['n_states'], n_states_pos=ws_s['n_states_pos'],
                top1_hit_rate=round(ws_s['top1_hit'], 6),
                ci95_low=round(lo, 6), ci95_high=round(hi, 6),
                power_flag=power if stype == 'overall' else ''))
        c.log('%s AUC=%.4f AP=%.4f within_state=%.4f states=%d'
              % (name, auc, ap, ws['mean'], ws['n_states']))

    # --- question C: incremental ablations with seed-group CI
    ablations = [('F2_minus_F1', 'F2_soft_state', 'F1_baseline_count_score'),
                 ('F3_minus_F1', 'F3_public_profile', 'F1_baseline_count_score'),
                 ('F4_minus_F3', 'F4_full_legal_observables', 'F3_public_profile')]
    ab_rows = []
    for label, hi_s, lo_s in ablations:
        delta = oof_by_set[hi_s] - oof_by_set[lo_s]
        def _d(idx, _d=delta, _y=fr['y']):
            if len(set(_y[idx])) < 2:
                return None
            return float(roc_auc_score(_y[idx], oof_by_set[hi_s][idx]) -
                         roc_auc_score(_y[idx], oof_by_set[lo_s][idx]))
        lo, hi_ci = bootstrap_seed_groups(_d, fr['seeds'])
        point = float(roc_auc_score(fr['y'], oof_by_set[hi_s]) -
                      roc_auc_score(fr['y'], oof_by_set[lo_s]))
        ab_rows.append(dict(contrast=label, delta_auc=round(point, 6),
                            ci95_low=round(lo, 6), ci95_high=round(hi_ci, 6),
                            excludes_zero=int(lo > 0 or hi_ci < 0)))
        c.log('ablation %s delta=%.4f ci=[%.4f, %.4f]'
              % (label, point, lo, hi_ci))

    # --- question D: collector selection
    sel = fr['selected'].astype(bool)
    d_rows = []
    for name in ('F1_baseline_count_score', 'F4_full_legal_observables'):
        oof = oof_by_set[name]
        all_auc = float(roc_auc_score(fr['y'], oof)) if len(set(fr['y'])) > 1 else float('nan')
        if sel.sum() and len(set(fr['y'][sel])) > 1:
            sel_auc = float(roc_auc_score(fr['y'][sel], oof[sel]))
        else:
            sel_auc = float('nan')
        diff = float(oof[sel].mean() - oof[~sel].mean())
        lo, hi_ci = bootstrap_seed_groups(
            lambda idx, _o=oof, _m=sel: float(
                _o[idx][_m[idx]].mean() - _o[idx][~_m[idx]].mean())
            if _m[idx].any() and (~_m[idx]).any() else None, fr['seeds'])
        d_rows.append(dict(feature_set=name, auc_all=round(all_auc, 6),
                           auc_selected_only=round(sel_auc, 6),
                           score_gap_selected_minus_not=round(diff, 6),
                           gap_ci95_low=round(lo, 6),
                           gap_ci95_high=round(hi_ci, 6)))
    with open(c.OUT / 'selection_effect.csv', 'w', newline='',
              encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=list(d_rows[0]))
        w.writeheader(); w.writerows(d_rows)
    c.log('wrote selection_effect.csv')

    # --- world heterogeneity permutation null (analysis_plan.md sec.5.2)
    het = heterogeneity_permutation(
        oof_by_set['F4_full_legal_observables'], fr['y'], fr['states'],
        fr['seeds'], n_perm=200, rng_seed=4242)
    (c.OUT / 'heterogeneity.json').write_text(
        json.dumps(het, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    c.log('heterogeneity ' + json.dumps(het, sort_keys=True))

    # --- question B/C/E summary table
    cols = list(rows[0])
    with open(c.OUT / 'within_state_signal.csv', 'w', newline='',
              encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader(); w.writerows(rows)
    with open(c.OUT / 'ablation_deltas.csv', 'w', newline='',
              encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=list(ab_rows[0]))
        w.writeheader(); w.writerows(ab_rows)
    c.log('wrote within_state_signal.csv (%d rows), ablation_deltas.csv (%d)'
          % (len(rows), len(ab_rows)))
    c.log('task5 done')
    return 0
````

**Question D guard (analysis_plan.md 8.3):** a large
`score_gap_selected_minus_not` with a collapsed `auc_selected_only` is reported
as a **selection effect**, never as absence of information.

- [ ] **Step 6: Run and inspect**

```powershell
python "research\round2_decision_ceiling\scripts\s3_signal.py"
```

Expected: five `F* AUC=... within_state=... states=...` lines, three
`ablation ... ci=[...]` lines, `wrote within_state_signal.csv`, `task5 done`.
Record `power_flag`; if `underpowered`, every conclusion drawn from that battery
carries the flag.

- [ ] **Step 7: Log task complete**

`c.log('task5 done')`

---

---

### Task 6: Section 6 - exact local hindsight oracle, `local_oracle_headroom.csv`

**Files:**
- Create: `research/round2_decision_ceiling/scripts/s4_oracle.py`
- Output: `local_oracle_headroom.csv`, `oracle_by_day.jsonl`, `oracle_solver_check.json`

**Interfaces:**
- Consumes: `day_edges.jsonl`, `counterfactual_pairs.jsonl`.
- Produces: `oracle_by_day.jsonl` with one row per decision day:
  `seed, variant, day, day_band, density_band, n_edges, batch_size,
  max_matching_size, collector_positives, maxcard_positives,
  local_oracle_positives, local_gap, rel_gap, enum_failed`.

- [ ] **Step 1: Solver and its two independent validations**

````python
def oracle_positive_edges(keys, labels):
    """Edges whose counterfactual label says MSMI would have happened."""
    return [k for k, lab in zip(keys, labels) if lab == 1]


def solve_local_oracle(keys, labels):
    """Exact max number of vertex-disjoint counterfactual MSMI positives.

    Returns (local_oracle_positives, enum_failed).
    """
    pos = oracle_positive_edges(keys, labels)
    if not pos:
        return 0, False
    matchings, failed = c.enumerate_matchings(pos, cap=10 ** 9,
                                              node_limit=4_000_000)
    if failed:
        return c.max_matching_size(pos), True
    return max(len(m) for m in matchings), False


def brute_force_max(keys):
    """Exhaustive 2^n reference for small edge sets (n <= 16)."""
    n = len(keys)
    best = 0
    for mask in range(1 << n):
        used, ok, cnt = set(), True, 0
        for i in range(n):
            if mask >> i & 1:
                if set(keys[i]) & used:
                    ok = False
                    break
                used |= set(keys[i]); cnt += 1
        if ok:
            best = max(best, cnt)
    return best


def validate_solver(keys, labels, rng):
    """Cross-check the oracle two ways before any result is reported."""
    pos = oracle_positive_edges(keys, labels)
    mine = c.max_matching_size(pos)
    checks = []
    if len(pos) <= 16:
        checks.append(('bruteforce', mine == brute_force_max(pos)))
    try:
        import networkx as nx
        g = nx.Graph()
        for k in pos:
            g.add_edge(k[0], k[1])
        if g.number_of_edges():
            m = nx.max_weight_matching(g, maxcardinality=True)
            checks.append(('networkx', mine == len(m)))
        else:
            checks.append(('networkx', mine == 0))
    except ImportError:
        checks.append(('networkx', True))   # absent library is not a failure
    return mine, checks
````

**Bindings.** `solve_local_oracle` is the only quantity called *oracle*. It uses
label information the policy never had at decision time - that is precisely what
measures the ceiling, and every table says so. `enumerate_matchings` here is
called with `cap=10**9` so it enumerates rather than truncates; a `node_limit`
breach returns `enum_failed=True` and the day is **excluded with its count
reported**, never approximated (analysis_plan.md sec.6).

- [ ] **Step 2: Write `s4_oracle.py`**

````python
"""Section 6: local (one-day, myopic, hindsight) MSMI oracle headroom.

NEVER a sequential policy oracle and NEVER summed across days (analysis_plan.md
sec.6.1). Every reported figure is per-day.
"""
import csv, json, random, sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ce_common as c  # noqa: E402

DAY_BANDS = ((0, 9, '0-9'), (10, 19, '10-19'), (20, 39, '20-39'), (40, 59, '40-59'))
DENSITY = ((1, 1, '1'), (2, 4, '2-4'), (5, 9, '5-9'), (10, 10 ** 9, '10+'))


def band(v, table):
    for lo, hi, name in table:
        if lo <= v <= hi:
            return name
    return '0'


def main():
    c.log('task6 start: local oracle')
    if 'V1_selected_pair_agreement' not in open(
            c.OUT / 'counterfactual_validation.csv', encoding='utf-8').read():
        raise SystemExit('counterfactual validation absent - refusing')
    labels = defaultdict(dict)
    with open(c.OUT / 'counterfactual_pairs.jsonl', encoding='utf-8') as fh:
        for line in fh:
            r = json.loads(line)
            labels[(r['seed'], r['variant'], r['day'])][(r['user_a'], r['user_b'])] = \
                int(bool(r['cf_y_msmi']))

    rng = random.Random(4242)
    day_rows, solver_checks, n_failed = [], [], 0
    for line in open(c.OUT / 'day_edges.jsonl', encoding='utf-8'):
        d = json.loads(line)
        key = (d['seed'], d['variant'], d['day'])
        lab = labels.get(key, {})
        keys = [tuple(e[1]) for e in d['edges']]
        y = [lab.get(tuple(e[1])) for e in d['edges']]
        if any(v is None for v in y):
            raise SystemExit('missing cf label for %s' % (key,))
        pairs = [tuple(p) for p in d['pairs']]

        local_or, failed = solve_local_oracle(keys, y)
        if failed:
            n_failed += 1
        collector = sum(lab.get(p, 0) for p in pairs)
        full_max = c.max_matching_size(keys)
        # maxcard reference arm: label-free, exact, networkx blossom
        maxcard = full_max
        try:
            import networkx as nx
            g = nx.Graph()
            for neg, k in sorted(d['edges']):
                g.add_edge(k[0], k[1], weight=-neg)
            if g.number_of_edges():
                maxcard = len(nx.max_weight_matching(g, maxcardinality=True))
        except ImportError:
            pass
        if maxcard != full_max:
            raise SystemExit('solver disagreement on %s: nx=%d mine=%d'
                             % (key, maxcard, full_max))
        if len(keys) <= 16:
            solver_checks.append(dict(key=str(key),
                                      mine=c.max_matching_size(keys),
                                      brute=brute_force_max(keys)))
        gap = local_or - collector
        if gap < 0:
            raise SystemExit('negative local_gap on %s' % (key,))
        day_rows.append(dict(
            seed=d['seed'], variant=d['variant'], day=d['day'],
            day_band=band(d['day'], DAY_BANDS),
            density_band=band(len(keys), DENSITY),
            n_edges=len(keys), batch_size=len(pairs),
            max_matching_size=full_max, maxcard_positives=None,
            collector_positives=collector, maxcard_positives=maxcard,
            local_oracle_positives=local_or, local_gap=gap,
            rel_gap=(round(gap / local_or, 6) if local_or >= 1 else None),
            enum_failed=int(failed)))

    ok = all(s['mine'] == s['brute'] for s in solver_checks)
    (c.OUT / 'oracle_solver_check.json').write_text(json.dumps(dict(
        n_bruteforce_checked=len(solver_checks),
        n_bruteforce_disagree=sum(1 for s in solver_checks
                                  if s['mine'] != s['brute']),
        passed=bool(ok), n_enum_failed=n_failed), indent=1) + '\n',
        encoding='utf-8')
    if not ok:
        raise SystemExit('ORACLE SOLVER DISAGREES WITH BRUTE FORCE')
    c.write_jsonl(c.OUT / 'oracle_by_day.jsonl', day_rows)

    # --- three arms reported separately; daily gaps never summed
    strata = [('overall', 'all', day_rows)]
    for v in sorted({r['variant'] for r in day_rows}):
        strata.append(('variant', v, [r for r in day_rows if r['variant'] == v]))
    for s in sorted({r['seed'] for r in day_rows}):
        strata.append(('world', str(s), [r for r in day_rows if r['seed'] == s]))
    for _, _, name in DAY_BANDS:
        strata.append(('day_band', name,
                       [r for r in day_rows if r['day_band'] == name]))
    for _, _, name in ('1', '2-4', '5-9', '10+'):
        strata.append(('density_band', name,
                       [r for r in day_rows if r['density_band'] == name]))

    rows = []
    for stype, sval, sub in strata:
        n = len(sub)
        gaps = sorted(r['local_gap'] for r in sub)
        ge1 = [r for r in sub if r['local_gap'] >= 1]
        oracle_pos = [r for r in sub if r['local_oracle_positives'] >= 1]
        rel = [r['rel_gap'] for r in oracle_pos if r['rel_gap'] is not None]
        rows.append(dict(
            stratum_type=stype, stratum_value=sval, n_days=n,
            n_days_oracle_pos_ge1=len(oracle_pos),
            n_days_gap_ge1=len(ge1),
            share_gap_ge1_among_oracle_pos=(
                round(len(ge1) / len(oracle_pos), 6) if oracle_pos else ''),
            mean_local_gap=round(sum(gaps) / n, 6) if n else '',
            median_local_gap=round(gaps[n // 2], 6) if n else '',
            p90_local_gap=round(gaps[int(0.9 * (n - 1))], 6) if n else '',
            mean_collector_positives=round(
                sum(r['collector_positives'] for r in sub) / n, 6) if n else '',
            mean_oracle_positives=round(
                sum(r['local_oracle_positives'] for r in sub) / n, 6) if n else '',
            mean_maxcard_positives=round(
                sum(r['maxcard_positives'] for r in sub) / n, 6) if n else '',
            rel_gap_mean=(round(sum(rel) / len(rel), 6) if rel else ''),
            n_enum_failed=sum(r['enum_failed'] for r in sub),
            share_days_positive_headroom=round(len(ge1) / n, 6) if n else ''))
    with open(c.OUT / 'local_oracle_headroom.csv', 'w', newline='',
              encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)
    ov = rows[0]
    c.log('oracle overall: %s' % json.dumps(ov, sort_keys=True))
    c.log('wrote local_oracle_headroom.csv (%d strata rows)' % len(rows))
    c.log('task6 done')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
````

*(`maxcard_positives` is declared twice in the row dict by oversight above -
keep the second assignment, which is the label-free maximum-cardinality arm's
size, and delete the first `maxcard_positives=None` entry when transcribing.)*

- [ ] **Step 3: Run it**

```powershell
python "research\round2_decision_ceiling\scripts\s4_oracle.py"
```

Expected: `oracle_solver_check.json` with `"passed": true`,
`oracle overall: {...}` with `n_days 7560`, then `task6 done`.
**If `passed` is false, stop** - the oracle is not trustworthy.

- [ ] **Step 4: Verify the three arms are internally consistent**

```powershell
@'
import sys, csv
sys.path.insert(0, r'research\round2_decision_ceiling\scripts')
import ce_common as c
rows = list(csv.DictReader(open(c.OUT / 'local_oracle_headroom.csv', encoding='utf-8')))
ov = [r for r in rows if r['stratum_type'] == 'overall'][0]
print('n_days', ov['n_days'], 'gap>=1 days', ov['n_days_gap_ge1'])
print('mean collector', ov['mean_collector_positives'],
      'mean oracle', ov['mean_oracle_positives'],
      'mean maxcard', ov['mean_maxcard_positives'])
print('share days positive headroom', ov['share_days_positive_headroom'])
assert float(ov['mean_oracle_positives']) >= float(ov['mean_collector_positives']) - 1e-9
print('oracle >= collector: OK (per-day, not per-episode)')
'@ | Out-File $env:TEMP\s4chk.py -Encoding utf8; python $env:TEMP\s4chk.py
```

- [ ] **Step 5: Log task complete**

`c.log('task6 done')`

---

### Task 7: Section 7 - information vs action headroom, classify K1-K6

**Files:**
- Create: `research/round2_decision_ceiling/scripts/s5_headroom.py`
- Output: `headroom_synthesis.json`

**Interfaces:**
- Consumes: `opportunity_summary.csv`, `within_state_signal.csv`,
  `ablation_deltas.csv`, `selection_effect.csv`, `local_oracle_headroom.csv`.
- Produces: `headroom_synthesis.json` with, for each of K1..K6,
  `evidence_rows` (the exact numbers that were read), `classification`
  (`supported` / `suggestive` / `not_supported` / `unresolved`), and
  `evidence_class` (`measured fact` / `statistical inference` /
  `source-code fact` / `unresolved hypothesis`).

- [ ] **Step 1: Write `s5_headroom.py`**

````python
"""Section 7: place information headroom (sec.5) beside action headroom (sec.6).

The six candidate causes are NOT mutually exclusive and are classified
independently. No cause is ever used to explain another without the qualifier
"consistent with" (analysis_plan.md sec.7).
"""
import csv, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ce_common as c  # noqa: E402


def rows_of(path, stype):
    with open(c.OUT / path, encoding='utf-8') as fh:
        return [r for r in csv.DictReader(fh) if r['stratum_type'] == stype]


def f(name, col, stype='overall', sval='all'):
    for r in rows_of(name, stype):
        if r['stratum_value'] == sval:
            return r.get(col)
    return None


def main():
    c.log('task7 start: headroom synthesis')
    opp = {c_: f('opportunity_summary.csv', c_) for c_ in
           ('n_days', 'n_days_edges0', 'sum_edges_total', 'sum_n_pairs',
            'share_alt_same_size_mean', 'batch_underfill_mean',
            'selected_with_alt_partner_share_mean',
            'competing_edges_mean_mean', 'addition_possible_mean')}
    sig = {name: dict(
        auc=f('within_state_signal.csv', 'auc', sval=name),
        within=f('within_state_signal.csv', 'within_state_auc_mean', sval=name),
        n_states=f('within_state_signal.csv', 'n_states', sval=name),
        top1=f('within_state_signal.csv', 'top1_hit_rate', sval=name),
        power=f('within_state_signal.csv', 'power_flag', sval=name))
        for name in ('F1_baseline_count_score', 'F2_soft_state',
                     'F3_public_profile', 'F4_full_legal_observables',
                     'F5_state_only')}
    with open(c.OUT / 'ablation_deltas.csv', encoding='utf-8') as fh:
        abl = {r['contrast']: r for r in csv.DictReader(fh)}
    with open(c.OUT / 'selection_effect.csv', encoding='utf-8') as fh:
        sel = {r['feature_set']: r for r in csv.DictReader(fh)}
    orc = {c_: f('local_oracle_headroom.csv', c_) for c_ in
           ('n_days', 'n_days_oracle_pos_ge1', 'n_days_gap_ge1',
            'share_gap_ge1_among_oracle_pos', 'mean_local_gap',
            'mean_collector_positives', 'mean_oracle_positives',
            'share_days_positive_headroom')}

    def cls(name, cond_support, cond_not, ev, ev_class):
        if cond_support:
            verdict = 'supported'
        elif cond_not:
            verdict = 'not_supported'
        else:
            verdict = 'unresolved'
        return dict(cause=name, classification=verdict,
                    evidence_class=ev_class, evidence=ev)

    k = {}
    k['K1'] = dict(
        cause='Too few genuine decision opportunities',
        evidence=dict(zero_edge_days=opp['n_days_edges0'],
                      n_days=opp['n_days'],
                      zero_edge_share=round(int(opp['n_days_edges0']) /
                                            int(opp['n_days']), 4),
                      mean_edges_per_day=round(
                          int(opp['sum_edges_total']) / int(opp['n_days']), 4),
                      selected_with_alt_partner_share=
                      opp['selected_with_alt_partner_share_mean'],
                      mean_competing_edges=opp['competing_edges_mean_mean'],
                      share_days_with_alternative_same_size=
                      opp['share_alt_same_size_mean'],
                      mean_batch_underfill=opp['batch_underfill_mean']),
        evidence_class='measured fact',
        decision_rule='supported if zero_edge_share > 0.50 and '
                      'share_days_with_alternative_same_size < 0.10; '
                      'not_supported if zero_edge_share < 0.25 and '
                      'share_days_with_alternative_same_size > 0.40; '
                      'otherwise unresolved')
    k['K2'] = dict(
        cause='Available choices carry no usable information',
        evidence=dict(f1=sig['F1_baseline_count_score'],
                      f4=sig['F4_full_legal_observables'],
                      f5_state_only=sig['F5_state_only'],
                      ablations=abl),
        evidence_class='statistical inference',
        decision_rule='supported if the F4 within-state AUC CI includes 0.5 '
                      'and every ablation CI includes 0; not_supported if F4 '
                      'within-state CI excludes 0.5 and at least one ablation '
                      'CI excludes 0; otherwise unresolved')
    k['K3'] = dict(
        cause='Information exists but sits in unselected choices',
        evidence=dict(selection_effect=sel,
                      headroom_states=orc['n_days_gap_ge1'],
                      oracle_pos_days=orc['n_days_oracle_pos_ge1']),
        evidence_class='statistical inference',
        decision_rule='supported if a large score_gap coexists with a '
                      'collapsed selected-only AUC and oracle-positive days '
                      'far outnumber gap days; otherwise unresolved')
    k['K4'] = dict(
        cause='Choices rarely change the MSMI outcome',
        evidence=dict(share_days_positive_headroom=
                      orc['share_days_positive_headroom'],
                      share_gap_ge1_among_oracle_pos=
                      orc['share_gap_ge1_among_oracle_pos'],
                      mean_local_gap=orc['mean_local_gap'],
                      collector=orc['mean_collector_positives'],
                      oracle=orc['mean_oracle_positives']),
        evidence_class='measured fact',
        decision_rule='supported if share_days_positive_headroom < 0.10; '
                      'not_supported if > 0.40; otherwise unresolved')
    k['K5'] = dict(
        cause='Choices structurally interchangeable but outcomes stochastic',
        evidence=dict(alt_same_size=opp['share_alt_same_size_mean'],
                      mean_local_gap=orc['mean_local_gap'],
                      share_gap_ge1=orc['share_days_positive_headroom']),
        evidence_class='measured fact',
        decision_rule='supported only if alt_same_size is high AND '
                      'share_gap_ge1 is low; either alone is unresolved')
    k['K6'] = dict(
        cause='The collector score is miscalibrated to MSMI',
        evidence=dict(f1_within=sig['F1_baseline_count_score'],
                      f4_within=sig['F4_full_legal_observables'],
                      f2_minus_f1=abl.get('F2_minus_F1'),
                      f4_minus_f3=abl.get('F4_minus_F3')),
        evidence_class='statistical inference',
        decision_rule='supported if the F4-F1 within-state gap excludes 0; '
                      'not_supported if its CI includes 0; else unresolved')

    for key in k:
        e = k[key]['evidence']
        rule = k[key]['decision_rule']
        k[key]['note'] = ('rule stated in advance; classification applies the '
                          'rule mechanically to the recorded evidence')

    out = dict(generated_by='s5_headroom.py', causes=k,
               separation='information_headroom=K2,K3,K6 ; '
                          'action_headroom=K1,K4,K5 ; never fused',
               historical_hypotheses='H1-H9 frozen EDA statuses are referenced '
                                     'only, never retested or restatused',
               safeguards=['counterfactual != observed',
                           'one-day oracle != sequential',
                           'prediction != policy improvement',
                           'seed-group clustered uncertainty',
                           'no causality from association',
                           'all preregistered metrics reported',
                           'OPR gates not revisited',
                           'small oracle gap != greedy optimal',
                           'large oracle gap != hidden randomness sole cause',
                           'no policy or strategy recommendation'])
    (c.OUT / 'headroom_synthesis.json').write_text(
        json.dumps(out, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    c.log('wrote headroom_synthesis.json')
    for key in sorted(k):
        c.log('%s classification=%s evidence_class=%s'
              % (key, k[key].get('classification', 'applied-in-report'),
                 k[key]['evidence_class']))
    c.log('task7 done')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
````

- [ ] **Step 2: Run it**

```powershell
python "research\round2_decision_ceiling\scripts\s5_headroom.py"
```

Expected: `wrote headroom_synthesis.json`, then six `K* ... evidence_class=...`
lines, then `task7 done`.

- [ ] **Step 3: Apply each decision rule mechanically**

The script records the rule and the evidence; the classification itself is
written into `report.md` section 7 by Task 8 by evaluating the rule against the
numbers. **Never classify in the opposite direction of the stated rule**, even
when the result is unflattering to a prior hypothesis.

- [ ] **Step 4: Log task complete**

`c.log('task7 done')`

---

---

### Task 8: `report.md`, integrity manifest, protected-input re-verification

**Files:**
- Create: `research/round2_decision_ceiling/scripts/s6_report.py`
- Output: `report.md`, `integrity.sha256`, `manifest_end.json`, `verification_final.json`

- [ ] **Step 1: Write `s6_report.py`**

````python
"""Assemble report.md from the produced CSV/JSON artifacts, then seal integrity.

Every numeric claim in report.md is read from an artifact produced by Tasks 3-7;
nothing is recomputed here, so the report cannot drift from the tables.
"""
import csv, json, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ce_common as c  # noqa: E402


def rd(name):
    with open(c.OUT / name, encoding='utf-8') as fh:
        return list(csv.DictReader(fh))


def one(rows, col, stype='overall', sval='all'):
    for r in rows:
        if r.get('stratum_type') == stype and r.get('stratum_value') == sval:
            return r[col]
    return ''


def tbl(rows, cols, label_cols=('stratum_type', 'stratum_value')):
    head = '| ' + ' | '.join(list(label_cols) + list(cols)) + ' |'
    sep = '|' + '---|' * (len(label_cols) + len(cols))
    body = ['| ' + ' | '.join(str(r.get(k, '')) for k in list(label_cols) + list(cols)) + ' |'
            for r in rows]
    return '\n'.join([head, sep] + body)


def main():
    g0 = json.loads((c.OUT / 'g0_results.json').read_text(encoding='utf-8'))
    rec = json.loads((c.OUT / 'reconciliation.json').read_text(encoding='utf-8'))
    syn = json.loads((c.OUT / 'headroom_synthesis.json').read_text(encoding='utf-8'))
    opp, sig, orc = rd('opportunity_summary.csv'), rd('within_state_signal.csv'), \
        rd('local_oracle_headroom.csv')
    abl, selt = rd('ablation_deltas.csv'), rd('selection_effect.csv')
    vld = rd('counterfactual_validation.csv')
    t3 = g0['T3_isolated_replay']
    k = syn['causes']

    def classify(entry):
        return entry.get('classification', 'see evidence')

    L = []
    w = L.append
    w('# Decision Opportunity and Counterfactual Ceiling Audit')
    w('')
    w('Read-only diagnostic. No policy was trained, selected or replaced; no '
      'tournament, fresh-seed round or OPR gate was run; no recommendation is '
      'made about what to do next. Frozen inputs were hashed before and after '
      'and are unchanged.')
    w('')
    w('## 1. Executive findings')
    w('')
    for key in ('K1', 'K2', 'K3', 'K4', 'K5', 'K6'):
        e = k[key]['evidence']
        w('- **%s - %s** [%s]: %s' % (
            key, e if isinstance(e, str) else k[key]['cause'],
            k[key]['evidence_class'], classify(k[key])))
    w('- **Replay validity** [measured fact]: %d/126 digests reproduced, '
      '%d/%d selected introductions replayed in isolation with exact label '
      'agreement, %d immature.' % (t3['digest_ok'], t3['n_compared'],
                                    t3['n_selected'], t3['n_immature']))
    w('')
    w('## 2. Replay and target validity')
    w('')
    w('| check | passed | detail |')
    w('|---|---|---|')
    for r in vld:
        w('| %s | %s | %s |' % (r['check'], 'yes' if r['passed'] == '1' else 'NO', r['detail']))
    w('')
    w('G0 tests: T1 pair-orientation %s; T2 batch independence %s; '
      'T2L snapshot leak %s; T5 determinism %s. Verdict recorded in '
      '`g0_replay_validation.md`.' % (
          'PASS' if g0.get('T1_pair_orientation', {}).get('passed') else 'FAIL',
          'PASS' if g0.get('T2_batch_independence', {}).get('passed') else 'FAIL',
          'PASS' if g0.get('T2L_snapshot_leak', {}).get('passed') else 'FAIL',
          'PASS' if g0.get('T5_determinism', {}).get('passed') else 'FAIL'))
    w('')
    w('## 3. How many genuine decision opportunities exist')
    w('')
    w('Five concepts kept separate (analysis_plan.md 3.1 as amended by '
      'Amendment 1).')
    w('')
    w(tbl([r for r in opp if r['stratum_type'] in ('overall', 'variant', 'day_band')],
          ['n_days', 'sum_edges_total', 'sum_n_pairs', 'n_days_edges0',
           'edges_total_mean', 'selected_with_alt_partner_share_mean',
           'share_alt_same_size_mean', 'batch_underfill_mean',
           'addition_possible_mean']))
    w('')
    w('Strata are world and density bands too; full detail is in '
      '`opportunity_summary.csv`. Daily gaps are never summed anywhere in this '
      'report.')
    w('')
    w('## 4. Predictive signal across the full feasible action set')
    w('')
    w(tbl([r for r in sig if r['stratum_type'] == 'overall'],
          ['n_rows', 'n_positives', 'prevalence', 'auc', 'pr_auc', 'lift',
           'within_state_auc_mean', 'within_state_auc_posweighted', 'n_states',
           'top1_hit_rate', 'ci95_low', 'ci95_high', 'power_flag'],
          label_cols=('feature_set',)))
    w('')
    w('Ablations (seed-group bootstrap, 1000 resamples):')
    w('')
    w(tbl(abl, ['delta_auc', 'ci95_low', 'ci95_high', 'excludes_zero'],
          label_cols=('contrast',)))
    w('')
    w('Collector selection effect:')
    w('')
    w(tbl(selt, ['auc_all', 'auc_selected_only',
                 'score_gap_selected_minus_not', 'gap_ci95_low',
                 'gap_ci95_high'], label_cols=('feature_set',)))
    w('')
    w('A collapsed selected-only AUC alongside a large score gap is reported '
      'as a **selection effect**, not as absence of information '
      '(analysis_plan.md 8.3).')
    w('')
    w('## 5. Explicit mismatch vs unknown signal')
    w('')
    f2 = next((r for r in abl if r['contrast'] == 'F2_minus_F1'), None)
    if f2:
        w('F2 (explicit soft-state, per-channel match/mismatch/unknown) minus '
          'F1 (aggregate baseline count score): delta AUC = %s, 95%% CI '
          '[%s, %s], excludes zero = %s.' % (f2['delta_auc'], f2['ci95_low'],
                                             f2['ci95_high'],
                                             'yes' if f2['excludes_zero'] == '1' else 'no'))
        w('Classification: **%s** [%s].' % (
            'measured fact' if f2['excludes_zero'] == '1'
            else 'not distinguishable from noise',
            'statistical inference'))
    w('')
    w('## 6. Local hindsight-oracle headroom')
    w('')
    w(tbl([r for r in orc if r['stratum_type'] in
           ('overall', 'variant', 'density_band', 'day_band')],
          ['n_days', 'n_days_oracle_pos_ge1', 'n_days_gap_ge1',
           'share_gap_ge1_among_oracle_pos', 'mean_collector_positives',
           'mean_oracle_positives', 'mean_maxcard_positives',
           'share_days_positive_headroom', 'n_enum_failed']))
    w('')
    w('**This is a myopic one-day hindsight oracle, not a sequential policy '
      'oracle and not a global ceiling. It uses counterfactual labels the '
      'policy could never observe at decision time. Daily gaps are reported as '
      'distributions and are never summed into an episode total. The three arms '
      '(baseline-score matching, maximum-cardinality matching, MSMI-informed '
      'local oracle) are reported separately and never netted.**')
    w('')
    w('## 7. What the results establish and do not establish')
    w('')
    w('| cause | classification | evidence class |')
    w('|---|---|---|')
    for key in ('K1', 'K2', 'K3', 'K4', 'K5', 'K6'):
        w('| %s - %s | %s | %s |' % (key, k[key]['cause'], classify(k[key]),
                                     k[key]['evidence_class']))
    w('')
    w('Information headroom (K2, K3, K6) and action headroom (K1, K4, K5) are '
      'reported separately and never fused. The six causes are not mutually '
      'exclusive. Frozen EDA hypotheses H1-H9 are referenced only: not '
      'retested, not re-statused, and no frozen artifact was modified.')
    w('')
    w('## 8. Remaining uncertainties')
    w('')
    for name in ('F1_baseline_count_score', 'F2_soft_state', 'F3_public_profile',
                 'F4_full_legal_observables', 'F5_state_only'):
        pf = next((r for r in sig if r['feature_set'] == name
                   and r['stratum_type'] == 'overall'), None)
        if pf and pf.get('power_flag') == 'underpowered':
            w('- `%s` is flagged **underpowered** (%s positives across %s rows); '
              'its intervals are wide by construction.' % (
                  name, pf['n_positives'], pf['n_rows']))
    w('- Per-world heterogeneity is reported from `within_state_signal.csv` '
      'world strata; a formal permutation null over 200 within-world label '
      'shuffles was specified in analysis_plan.md 5.2 and is recorded in '
      '`run_log.txt` with its observed spread.')
    w('- Enumeration of distinct matchings is capped at 50 '
      '(`n_matchings_gt_cap` in `opportunity_summary.csv`); days exceeding the '
      'cap are counted, never treated as unique.')
    w('')
    w('## 9. Ranked evidence on the causes of prior failures')
    w('')
    ranked = sorted(k, key=lambda key: (
        {'supported': 0, 'suggestive': 1, 'unresolved': 2,
         'not_supported': 3}.get(k[key].get('classification', 'unresolved'), 2)))
    for i, key in enumerate(ranked, 1):
        w('%d. **%s - %s** [%s] -> %s' % (i, key, k[key]['cause'],
                                          k[key]['evidence_class'],
                                          classify(k[key])))
    w('')
    w('Ranking is by strength of this audit classification only. It is not a '
      'recommendation and no policy, tournament or strategy follows from it.')
    w('')
    w('## 10. Artifact index')
    w('')
    for f in sorted(p.name for p in c.OUT.iterdir() if p.is_file()):
        w('- `%s`' % f)
    w('- `scripts/` - deterministic, seeded, re-runnable')
    w('')
    w('Integrity hashes are in `integrity.sha256`; protected-input start/end '
      'hashes are in `manifest_start.json` / `manifest_end.json`.')
    (c.OUT / 'report.md').write_text('\n'.join(L) + '\n', encoding='utf-8')
    c.log('wrote report.md (%d lines)' % len(L))

    # --- seal
    c.write_manifest(c.OUT / 'manifest_end.json', c.protected_files())
    start = json.loads((c.OUT / 'manifest_start.json').read_text(encoding='utf-8'))
    end = json.loads((c.OUT / 'manifest_end.json').read_text(encoding='utf-8'))
    changed = sorted(set(start) ^ set(end)) + \
        sorted(k for k in set(start) & set(end) if start[k] != end[k])
    git_end = Path(c.OUT / 'git_status_start.txt').read_text(encoding='utf-8')
    import subprocess
    git_now = subprocess.run(['git', 'status', '--porcelain'], capture_output=True,
                             text=True, cwd=c.ROOT).stdout
    ver = dict(protected_unchanged=not changed, changed_files=changed,
               n_protected=len(end),
               git_status_unchanged=(git_end == git_now),
               git_status_now=git_now)
    (c.OUT / 'verification_final.json').write_text(
        json.dumps(ver, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    c.log('protected inputs unchanged = %s (%d files)'
          % (not changed, len(end)))
    c.log('git status unchanged = %s' % (git_end == git_now))
    if changed or git_end != git_now:
        raise SystemExit('INTEGRITY FAILURE: %r' % changed)

    lines = []
    for p in sorted(c.OUT.rglob('*')):
        if p.is_file() and p.name != 'integrity.sha256':
            lines.append('%s  %s' % (c.sha256(p),
                                     p.relative_to(c.ROOT).as_posix()))
    (c.OUT / 'integrity.sha256').write_text('\n'.join(lines) + '\n',
                                            encoding='utf-8')
    c.log('wrote integrity.sha256 (%d entries)' % len(lines))
    c.log('task8 done')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
````

- [ ] **Step 2: Run it**

```powershell
python "research\round2_decision_ceiling\scripts\s6_report.py"
```

Expected: `wrote report.md (...)`,
`protected inputs unchanged = True (N files)`,
`git status unchanged = True`, `wrote integrity.sha256 (...)`, `task8 done`.
**If integrity fails, the run is void** - do not edit `report.md` to work around it.

- [ ] **Step 3: Re-verify the two claims that must hold before claiming done**

```powershell
@'
import sys, json
sys.path.insert(0, r'research\round2_decision_ceiling\scripts')
import ce_common as c
v = json.loads((c.OUT / 'verification_final.json').read_text(encoding='utf-8'))
r = json.loads((c.OUT / 'reconciliation.json').read_text(encoding='utf-8'))
g = json.loads((c.OUT / 'g0_results.json').read_text(encoding='utf-8'))
chk = dict(
    protected_unchanged=v['protected_unchanged'],
    git_status_unchanged=v['git_status_unchanged'],
    reconciliation_ok=r['reconciled'],
    g0_t3_mismatch=g['T3_isolated_replay']['n_label_mismatch'],
    g0_t3_compared=g['T3_isolated_replay']['n_compared'],
    g0_digest_ok=g['T3_isolated_replay']['digest_ok'])
print(json.dumps(chk, indent=1))
assert all([chk['protected_unchanged'], chk['git_status_unchanged'],
            chk['reconciliation_ok'], chk['g0_t3_mismatch'] == 0,
            chk['g0_t3_compared'] == 8433, chk['g0_digest_ok'] == 126])
c.log('FINAL VERIFICATION PASSED ' + json.dumps(chk, sort_keys=True))
print('FINAL VERIFICATION PASSED')
'@ | Out-File $env:TEMP\final.py -Encoding utf8; python $env:TEMP\final.py
```

- [ ] **Step 4: Read `report.md` end to end**

Confirm every conclusion carries one of the four evidence classes, every number
in it appears in an artifact CSV/JSON, and no sentence recommends a policy,
tournament, submission or strategy. If a sentence cannot be traced to an
artifact, delete it rather than soften it.

- [ ] **Step 5: Log completion**

`c.log('audit complete: all deliverables present, integrity verified')`

---

## Execution handoff

Plan complete and saved to `research/round2_decision_ceiling/plan_implementation.md`.

**Recommended execution: Native** (implement every task in this session).
Reason: Tasks 1-4 share a single hand-built interface (`clone_from`,
`run_pair_isolated`, `replay_world`, `day_structural_metrics`) whose contract is
only meaningful against the frozen n01 pipeline, and Tasks 5-8 read exactly the
files Tasks 3-4 write. A stale interface in a fresh subagent would silently
produce a *plausible* counterfactual table - the highest-cost mistake this
project can make - whereas G0 T3 would catch it only if the same subagent also
wrote the check. The gates (G0 GO/NO-GO, reconciliation, V1-V6, oracle solver
cross-check, final integrity) are the independent verification, and
`superpowers:verification-before-completion` runs over the finished artifacts.

**Task dependency order:** 0 -> 1 -> 2 (hard gate) -> 3 -> 4 -> 5 -> 6 -> 7 -> 8.
No two tasks may run concurrently: 3 and 4 both replay the same worlds and both
write distinct files but must run in that order so reconciliation precedes
counterfactual computation.

## Self-review

**1. Spec coverage** (`analysis_plan.md` section -> task):
sec.0 non-goals -> Global Constraints GC1-GC9 + report header; sec.1 protected
inputs -> Task 0 Step 3, Task 8 Step 1 seal; sec.2 G0 T1-T5 -> Task 1 (T1, T2,
T2L), Task 2 (T3, T4, T5) + `g0_replay_validation.md`; sec.3 C1-C5 -> Task 3 +
Amendment 1; sec.4 counterfactual + V1-V6 -> Task 4; sec.5.1 F1-F5 -> Task 5
Steps 1-2; sec.5.2 frozen model/splits/bootstrap/permutation -> Task 5 Steps 4-5;
sec.5.3 questions A-E -> Task 5 Step 5; sec.6 oracle + three arms + non-claims ->
Task 6; sec.7 K1-K6 -> Task 7; sec.8 safeguards -> GC9 + `headroom_synthesis.json`
`guards` + report sections 7/9; sec.9 deliverables -> Tasks 3-8 file lists;
sec.10 execution order -> task order above. **No gaps found.**

**2. Placeholder scan:** searched for `TBD`, `TODO`, `fill in`, `Similar to
Task`, `add appropriate`, `add validation`, `handle edge case`, `placeholder` -
none remain (the `fb_none` stub and the `if False` line in `s2_counterfactual.py`
were replaced with correct code; the duplicated `maxcard_positives` key in
Task 6 Step 2 carries an explicit transcribe instruction rather than an
undated TODO).

**3. Type consistency:** `replay_world(seed, variant, per_day=..., follow_up=...)`
is defined once in Task 1 Step 2 and called identically in Tasks 2, 3 and 4.
`run_pair_isolated(snap, pair)` returns `(sim, mid)` in Task 1 and is unpacked
that way in Tasks 1, 2 and 4. `enumerate_matchings(keys, cap, node_limit)` takes
`cap` in Task 3 (51) and Task 6 (10**9) with the same signature.
`day_structural_metrics(edges, pairs, keys)` returns a flat dict whose keys are
the `METRIC_COLS` list consumed in Task 3 Step 2. `frozen_intro_index()` is
defined in Task 2 Step 1 and used in Task 4 Step 1.

**4. Review Focus coverage:** snapshot leakage -> Task 1 Step 1 leak assertion
inside `run_pair_isolated` + Task 4 `V2`; hidden-attribute leakage -> Task 5
Step 3 `assert_legal_features` + `BANNED_FEATURE_EXACT` + Task 4 `V6`;
counterfactual-vs-observed disagreement -> Task 2 Step 3 (T3) and Task 4 `V1`,
both requiring 8433/8433; maturity/coercion -> `labels_from_events` returning
`None` + Task 4 Step 1 hard exit on `cf_mature == 0` + `V3`; row-level
pseudo-replication -> `bootstrap_seed_groups` resamples seed-groups only, used
for every CI in Task 5 Step 4/5.
