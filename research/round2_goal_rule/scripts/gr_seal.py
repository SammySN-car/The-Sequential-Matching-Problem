"""Seal the study: SHA-256 manifest over every file in
research/round2_goal_rule (integrity.sha256 itself excluded).
Format: '<sha256>  <ROOT-relative path>', sorted - same convention as the
prior studies. Run after all artifacts are final; gr_verify.py checks it.
"""
import sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gr_common as g  # noqa: E402


def main():
    g.log('gr_seal start')
    files = sorted(p for p in g.OUT.rglob('*')
                   if p.is_file() and p.name != 'integrity.sha256'
                   and '__pycache__' not in p.parts)   # bytecode never sealed
    lines = []
    for p in files:
        rel = p.relative_to(g.ROOT).as_posix()
        lines.append('%s  %s' % (g.sha256(p), rel))
    (g.OUT / 'integrity.sha256').write_text('\n'.join(lines) + '\n',
                                            encoding='utf-8')
    g.log('gr_seal: %d files sealed' % len(files))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
