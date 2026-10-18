"""Seal: sha256 manifest of every artifact in this study (integrity.sha256)."""
import hashlib, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ss_common as s  # noqa: E402


def main():
    files = []
    for p in sorted(s.OUT.rglob('*')):
        if not p.is_file():
            continue
        rel = p.relative_to(s.OUT).as_posix()
        if rel == 'integrity.sha256' or '__pycache__' in rel:
            continue
        files.append(p)
    man = {p.relative_to(s.ROOT).as_posix(): hashlib.sha256(
        p.read_bytes()).hexdigest() for p in files}
    (s.OUT / 'integrity.sha256').write_text(
        ''.join('%s  %s\n' % (d, k) for k, d in sorted(man.items())),
        encoding='utf-8')
    s.log('ss_seal: sealed %d files' % len(man))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
