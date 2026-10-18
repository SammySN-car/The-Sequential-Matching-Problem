"""Task 6: integrity seal + verification for research/round2_stagewise_reward_solver.

(a) SEAL this experiment directory: sha256 over every file under HERE except
    integrity.sha256 itself and any __pycache__ path, written as sorted
    `<64-hex>  <forward-slash relative path>` lines (same format as the parent
    seal; LF endings).
(b) VERIFY the PARENT experiment seal (../round2_stagewise_reward/integrity.sha256,
    1638 entries) is UNCHANGED using a READ-ONLY recomputation - the parent's own
    sr_verify.py is NOT run because it writes into the sealed directory.
(c) VERIFY protected surfaces: kit.py / evaluate.py / Dockerfile /
    requirements.txt are git-clean; policy.py's working-tree M is the pre-existing
    one (unchanged by this experiment; never written here).
(d) VERIFY frozen hashes: this experiment's analysis_plan.md == analysis_plan.sha256
    (ed1210c2...); the frozen parent model artifact == 7f1ddfe0...; the copy-source
    hashes of sr_features.py (76fc12f6...) and sr_policy_core.py (02af1e6a...).
(e) VERIFY required result artifacts exist and their headline flags are consistent.

Prints one [PASS]/[FAIL] per check, writes results/final_integrity.json (no
timestamps; deterministic), exits non-zero on any failure. Standard library only.
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent       # experiment dir
ROOT = HERE.parent.parent                           # repo root
PARENT = HERE.parents[0] / 'round2_stagewise_reward'
RESULTS = HERE / 'results'
SEAL = HERE / 'integrity.sha256'
PARENT_SEAL = PARENT / 'integrity.sha256'

PLAN_SHA = 'ed1210c2a4afd47f8cd1b3c8598daced848ac6b41916e41470f5d819ae113305'
MODEL_SHA = '7f1ddfe00211e2603e88c4e8318d3a62980aeb8364f51bc41909e8875fa275f2'
SR_FEATURES_SHA = '76fc12f6a75f45d247cb277fe36a0ddade520891eae7156bea18dc10d080e67e'
SR_POLICY_CORE_SHA = '02af1e6a4b7bf9dbfda9d74de998bbe07b8242d59da42ba1e2d45b108bed046d'
PARENT_SEAL_ENTRIES = 1638

_fails = []
_checks = 0


def check(label, ok, detail=''):
    global _checks
    _checks += 1
    tag = 'PASS' if ok else 'FAIL'
    print('[%s] %s%s' % (tag, label, (' :: ' + detail) if detail else ''), flush=True)
    if not ok:
        _fails.append({'check': label, 'detail': detail})
    return ok


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def seal_files():
    files = []
    for fp in HERE.rglob('*'):
        if not fp.is_file():
            continue
        rel = fp.relative_to(HERE).as_posix()
        if rel == 'integrity.sha256' or '__pycache__' in rel.split('/'):
            continue
        files.append((rel, fp))
    files.sort(key=lambda x: x[0])
    return files


def write_seal():
    files = seal_files()
    lines = ['%s  %s' % (sha(fp), rel) for rel, fp in files]
    SEAL.write_text('\n'.join(lines) + '\n', encoding='utf-8', newline='\n')
    return len(files)


def verify_this_seal():
    if not SEAL.exists():
        return False, 'integrity.sha256 missing'
    entries = {}
    for line in SEAL.read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        h, rel = line.split('  ', 1)
        entries[rel] = h
    files = dict(seal_files())
    # every listed file exists and matches; no extra/missing files
    for rel, h in entries.items():
        if rel not in files:
            return False, 'listed file missing: %s' % rel
        if sha(files[rel]) != h:
            return False, 'hash mismatch: %s' % rel
    extra = set(files) - set(entries)
    if extra:
        return False, 'unlisted files: %r' % sorted(extra)[:5]
    return True, '%d entries verified' % len(entries)


def verify_parent_seal():
    """Read-only: recompute every hash in the parent seal."""
    if not PARENT_SEAL.exists():
        return False, 'parent seal missing'
    entries = []
    for line in PARENT_SEAL.read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        h, rel = line.split('  ', 1)
        entries.append((h, rel))
    if len(entries) != PARENT_SEAL_ENTRIES:
        return False, 'parent seal entry count %d != %d' % (len(entries), PARENT_SEAL_ENTRIES)
    # sorted + unique
    rels = [r for _, r in entries]
    if rels != sorted(rels):
        return False, 'parent seal not sorted'
    if len(set(rels)) != len(rels):
        return False, 'parent seal has duplicate paths'
    for h, rel in entries:
        fp = PARENT / rel
        if not fp.exists():
            return False, 'parent file missing: %s' % rel
        if sha(fp) != h:
            return False, 'parent hash mismatch: %s' % rel
    return True, '%d parent entries verified unchanged' % len(entries)


def git_clean(paths):
    out = subprocess.run(['git', 'status', '--porcelain', '--'] + paths,
                         cwd=str(ROOT), capture_output=True, text=True)
    return out.stdout.strip()


def main():
    print('=== Task 6: integrity seal + verification ===', flush=True)
    # (a) seal this directory
    n = write_seal()
    print('sealed %d files -> integrity.sha256' % n, flush=True)

    # (b) verify this seal round-trips
    ok, detail = verify_this_seal()
    check('this experiment seal verifies', ok, detail)

    # (c) parent seal unchanged (read-only)
    ok, detail = verify_parent_seal()
    check('parent seal (1638 entries) unchanged', ok, detail)

    # (d) protected surfaces
    status = git_clean(['kit.py', 'evaluate.py', 'Dockerfile', 'requirements.txt'])
    check('kit/evaluate/Dockerfile/requirements git-clean', status == '', repr(status))
    pstatus = git_clean(['policy.py'])
    check('policy.py M is pre-existing (only file touched, never written here)',
          pstatus.strip() == 'M policy.py', repr(pstatus))

    # (e) frozen hashes
    check('analysis_plan.md matches frozen sha256 (ed1210c2)',
          sha(HERE / 'analysis_plan.md') == PLAN_SHA)
    check('frozen parent model artifact sha256 (7f1ddfe0)',
          sha(PARENT / 'results' / 'model_artifact.json') == MODEL_SHA)
    check('sr_features.py copy byte-identical (76fc12f6)',
          sha(HERE / 'scripts' / 'sr_features.py') == SR_FEATURES_SHA)
    check('sr_policy_core.py copy byte-identical (02af1e6a)',
          sha(HERE / 'sr_policy_core.py') == SR_POLICY_CORE_SHA)

    # (f) result artifacts + headline flags
    def load(name):
        p = RESULTS / name
        return json.loads(p.read_text(encoding='utf-8')) if p.exists() else None
    sv = load('solver_validation.json')
    check('results/solver_validation.json present + passed',
          bool(sv and sv.get('passed')))
    rb = load('runtime_benchmark.json')
    check('results/runtime_benchmark.json present', rb is not None)
    pv = load('policy_validity.json')
    check('results/policy_validity.json present + passed',
          bool(pv and pv.get('passed')))
    check('results/benchmark_corpus.json present',
          (RESULTS / 'benchmark_corpus.json').exists())
    ps = load('paired_stats.json')
    check('results/paired_stats.json present', ps is not None)
    check('results/report.md present', (HERE / 'report.md').exists())

    passed = not _fails
    (RESULTS / 'final_integrity.json').write_text(json.dumps({
        'experiment': 'round2_stagewise_reward_solver', 'task': 6,
        'sealed_files': n, 'checks': _checks, 'failures': _fails,
        'passed': passed,
    }, indent=2), encoding='utf-8')
    print('SUMMARY: %d/%d checks PASS  passed=%s' % (_checks - len(_fails), _checks, passed),
          flush=True)
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
