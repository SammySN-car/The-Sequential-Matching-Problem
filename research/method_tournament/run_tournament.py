"""Phase runner for the method tournament (design.md section 4).

Runs a named phase over its frozen seed x variant grid. Every arm is executed
through the official evaluate.episode subprocess protocol (60 decision days +
40 follow-up); the shared greedy control is `policy.py --baseline greedy`, run
once per world. Episode rows append to per_phase/<phase>_rows.jsonl (resumable,
later rows overwrite earlier per (method, seed, variant)); a done flag seals a
completed phase. confirm1/confirm2 verify hashes/policy_freeze_after_screening.txt
before executing (design.md section 8).
"""
import argparse
import hashlib
import json
import pathlib
import sys
import time
from concurrent.futures import ThreadPoolExecutor

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))
import evaluate  # noqa: E402  (frozen repo harness, imported after path setup)
from kit import generate  # noqa: E402

VARIANTS = ('development', 'sparse', 'cold_start', 'delayed', 'shift', 'drift')
CONTROL = '__control__'
PHASES = {
    'smoke': {'seeds': (90290,), 'variants': ('development',)},
    'screening': {'seeds': (143, 144, 145), 'variants': VARIANTS},
    'confirm1': {'seeds': (146, 147, 148, 149, 150, 151), 'variants': VARIANTS},
    'confirm2': {'seeds': (152, 153, 154, 155, 156, 157,
                           158, 159, 160, 161, 162, 163), 'variants': VARIANTS},
}
FREEZE_MANIFEST = HERE / 'hashes' / 'policy_freeze_after_screening.txt'
ROOT_FILES = frozenset(('kit.py', 'policy.py', 'policy_ac.py',
                        'evaluate.py', 'organise.py', 'Dockerfile'))
CODE_FILES = ('methods_a.py', 'methods_b.py', 'methods_c.py', 'methods_d.py',
              'methods_e.py', 'common.py', 'alloc.py', 'registry.py',
              '_cli.py', 'gen_policies.py', 'run_tournament.py',
              'analyse_tournament.py', 'instrument.py', 'design.md',
              'methods.json', 'kit.py', 'policy.py', 'policy_ac.py',
              'evaluate.py', 'organise.py', 'Dockerfile')


def code_fingerprint():
    """SHA-256 over the full behavior/spec file list (design.md section 8).

    The digest is carried on every runner row. On resume, any row with a
    foreign digest triggers a whole-phase purge to
    per_phase/<phase>_rows_v<hex8>.jsonl so two code versions can never mix
    inside one phase file; every invocation is appended to
    per_phase/<phase>_attempts.jsonl regardless of outcome.
    """
    h = hashlib.sha256()
    for rel in CODE_FILES:
        path = (ROOT / rel) if rel in ROOT_FILES else (HERE / rel)
        h.update(rel.encode('utf-8') + b'\0')
        h.update(path.read_bytes())
        h.update(b'\0')
    for launcher in sorted((HERE / 'policies').glob('*.py')):
        h.update(launcher.name.encode('utf-8') + b'\0')
        h.update(launcher.read_bytes())
        h.update(b'\0')
    return h.hexdigest()


def control_command():
    return [sys.executable, str(ROOT / 'policy.py'), '--baseline', 'greedy']


def method_command(mid):
    return [sys.executable, str(HERE / 'policies' / (mid + '.py')),
            '--baseline', 'greedy']


def worlds(phase):
    cfg = PHASES[phase]
    return [(seed, variant) for seed in cfg['seeds'] for variant in cfg['variants']]


def load_methods(phase):
    """Arms for a phase, excluding the shared control (design.md section 4)."""
    if phase in ('smoke', 'screening'):
        data = json.loads((HERE / 'methods.json').read_text(encoding='utf-8'))
        return sorted(m['method_id'] for m in data['methods']
                      if m['implementation_status'] == 'implemented')
    if phase == 'confirm1':
        return json.loads((HERE / 'screening_results.json')
                          .read_text(encoding='utf-8'))['retained']
    if phase == 'confirm2':
        return json.loads((HERE / 'confirmation_results.json')
                          .read_text(encoding='utf-8'))['selected']
    raise ValueError('unknown phase: ' + phase)


def verify_freeze(manifest=FREEZE_MANIFEST, base=None):
    """Design section 8: abort if any frozen file changed since screening.

    Manifest lines are `<digest>  <repo-root-relative path>`; default base is
    the repo root so the same manifest verifies from any working directory.
    """
    base = ROOT if base is None else base
    if not pathlib.Path(manifest).exists():
        raise SystemExit('freeze manifest missing: ' + str(manifest))
    bad = []
    for line in pathlib.Path(manifest).read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line:
            continue
        digest, rel = line.split(None, 1)
        target = base / rel.strip()
        if not target.exists() or \
                hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            bad.append(rel.strip())
    if bad:
        raise SystemExit('freeze verification FAILED: ' + ', '.join(sorted(bad)))


def row_key(row):
    return (row['method'], row['seed'], row['variant'])


def load_rows(path):
    rows = []
    if path.exists():
        for line in path.read_text(encoding='utf-8').splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows


def dedupe(rows):
    """Append-only semantics: the last row per (method, seed, variant) wins."""
    out = {}
    for row in rows:
        out[row_key(row)] = row
    return list(out.values())


def expected_keys(phase, methods):
    return {(m, seed, variant) for m in methods
            for seed, variant in worlds(phase)}


def purge_stale(rows_path, fp):
    """Archive a phase file written under a different code fingerprint.

    Whole-phase purge (design.md section 8): rows from two code versions can
    never share one file. Returns the archive path, or None when nothing was
    archived (file missing or every row already carries fp).
    """
    if not rows_path.exists():
        return None
    prior = load_rows(rows_path)
    if not any(r.get('code_sha256') != fp for r in prior):
        return None
    tag = hashlib.sha256(rows_path.read_bytes()).hexdigest()[:8]
    archive = rows_path.with_name('%s_v%s.jsonl' % (rows_path.stem, tag))
    rows_path.rename(archive)
    return archive


def append_attempt(path, phase, fingerprint, planned, written, invalid,
                   purged, code):
    """Append-only attempt history (design.md section 8).

    Every runner invocation is recorded regardless of outcome - including
    purges, incomplete runs (exit 2), and sealed-phase no-ops - so failed
    attempts stay visible in per_phase/<phase>_attempts.jsonl.
    """
    rec = {'ts': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
           'phase': phase, 'fingerprint': fingerprint,
           'episodes_planned': planned, 'episodes_written': written,
           'invalid': invalid, 'purged': purged, 'exit': code}
    with path.open('a', encoding='utf-8') as fh:
        fh.write(json.dumps(rec, sort_keys=True, allow_nan=False) + '\n')
    return code


def run_one(phase, method, seed, variant, code_sha256):
    cmd = control_command() if method == CONTROL else method_command(method)
    try:
        row = evaluate.episode(generate(seed, 200, 'evaluation', variant), cmd)
    except (ValueError, TypeError, KeyError, OSError) as error:
        row = {'valid': False, 'error': str(error)}
    row.update(phase=phase, method=method, seed=seed, variant=variant,
               code_sha256=code_sha256)
    return row


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', required=True, choices=sorted(PHASES))
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args(argv)
    phase = args.phase
    if phase in ('confirm1', 'confirm2'):
        verify_freeze()
    methods = load_methods(phase) + [CONTROL]
    per_phase = HERE / 'per_phase'
    per_phase.mkdir(exist_ok=True)
    rows_path = per_phase / (phase + '_rows.jsonl')
    done_path = per_phase / (phase + '.done')
    attempts_path = per_phase / (phase + '_attempts.jsonl')
    fp = code_fingerprint()
    # First attempt records the phase-start fingerprint; never overwritten
    # (design.md section 8: analysis asserts every screening row against the
    # pre-screening fingerprint - screening's file name is unchanged - while
    # confirm rows are asserted against their own phase-start file; cross-phase
    # file identity stays enforced by verify_freeze() on the 51-file manifest).
    pre = HERE / 'hashes' / ('pre_%s_fingerprint.txt' % phase)
    pre.parent.mkdir(exist_ok=True)
    if not pre.exists():
        pre.write_text(fp + '\n', encoding='utf-8')

    if done_path.exists():
        print('phase already sealed: %s (delete per_phase/%s.done to rerun)'
              % (phase, phase))
        return append_attempt(attempts_path, phase, fp, 0, 0, 0, None, 0)
    archived = purge_stale(rows_path, fp)
    purged = archived.name if archived else None
    if purged:
        print('code fingerprint changed: prior rows archived to %s' % purged,
              flush=True)
    prior = dedupe(load_rows(rows_path))
    done = {row_key(r) for r in prior if r.get('valid')}
    todo = [(m, seed, variant) for m in methods
            for seed, variant in worlds(phase)
            if (m, seed, variant) not in done]
    print('%s: %d valid rows sealed, %d episodes to run (fp %s)'
          % (phase, len(done), len(todo), fp[:16]), flush=True)
    started = time.time()
    written = 0
    if todo:
        with rows_path.open('a', encoding='utf-8') as sink, \
                ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
            futures = [pool.submit(run_one, phase, m, s, v, fp)
                       for m, s, v in todo]
            for i, future in enumerate(futures, 1):
                row = future.result()
                sink.write(json.dumps(row, sort_keys=True, allow_nan=False) + '\n')
                sink.flush()
                written = i
                if i % 10 == 0 or i == len(futures):
                    print('  %d/%d episodes written' % (i, len(futures)),
                          flush=True)
    rows = dedupe(load_rows(rows_path))
    missing = sorted(expected_keys(phase, methods) - {row_key(r) for r in rows})
    invalid = sorted(row_key(r) for r in rows if not r.get('valid'))
    summary = {'phase': phase, 'arms': methods, 'worlds': len(worlds(phase)),
               'episodes': len(rows), 'invalid': len(invalid),
               'invalid_keys': [list(k) for k in invalid],
               'missing': [list(k) for k in missing],
               'code_sha256': fp, 'purged': purged,
               'wall_seconds': round(time.time() - started, 1)}
    print(json.dumps(summary, indent=2, sort_keys=True))
    if missing:
        return append_attempt(attempts_path, phase, fp, len(todo), written, len(invalid), purged, 2)
    done_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + '\n',
                         encoding='utf-8')
    with (HERE / 'run_log.txt').open('a', encoding='utf-8') as log:
        log.write('%s phase %s sealed: %d episodes, %d invalid (fp %s)\n'
                  % (time.strftime('%Y-%m-%dT%H:%M:%S'), phase,
                     len(rows), len(invalid), fp[:16]))
    return append_attempt(attempts_path, phase, fp, len(todo), written,
                          len(invalid), purged, 0 if not invalid else 3)


if __name__ == '__main__':
    raise SystemExit(main())
