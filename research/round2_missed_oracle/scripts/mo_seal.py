"""Seal the missed-oracle study: write manifest_start, log, then integrity
LAST (nothing may be written after the seal)."""
import hashlib, json, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
MO = HERE.parent
REPO = HERE.parent.parent.parent          # repo root: The-Sequential-Matching-Problem


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def collect(root):
    out = []
    for p in sorted(root.rglob('*')):
        if p.is_file() and p.name not in ('integrity.sha256', 'manifest_end.json'):
            out.append(p)
    return out


def rel(p):
    return str(p.relative_to(REPO)).replace('\\', '/')


# manifest_start
files = collect(MO)
(MO / 'manifest_start.json').write_text(json.dumps(
    dict(n_files=len(files), sha256={rel(p): sha(p) for p in files}),
    indent=1, sort_keys=True) + '\n', encoding='utf-8')

# log
with open(MO / 'run_log.txt', 'a', encoding='utf-8') as fh:
    fh.write('[%s] mo_seal: writing manifest_start then integrity LAST.\n'
             % time.strftime('%Y-%m-%dT%H:%M:%S'))

# manifest_end
files = collect(MO)
(MO / 'manifest_end.json').write_text(json.dumps(
    dict(n_files=len(files), sha256={rel(p): sha(p) for p in files}),
    indent=1, sort_keys=True) + '\n', encoding='utf-8')

# integrity LAST - includes run_log.txt (no writes after this point)
files = collect(MO)
lines = ['%s  %s' % (sha(p), rel(p)) for p in files]
(MO / 'integrity.sha256').write_text('\n'.join(lines) + '\n', encoding='utf-8')
print('sealed %d files' % len(files))
