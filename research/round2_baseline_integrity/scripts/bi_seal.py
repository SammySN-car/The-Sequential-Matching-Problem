"""bi_seal: write integrity.sha256 over this study's own artifacts.

Excludes integrity.sha256 itself, bi_verify output (verify output goes to
console only), and __pycache__. One 'sha256  relative/path' line per file,
sorted, LF newlines, UTF-8. Re-runnable: overwrites the previous seal.
"""
import hashlib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent

EXCLUDE = {"integrity.sha256", "verify_output.txt"}


def iter_files():
    for p in sorted(OUT.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(OUT).as_posix()
        if rel.startswith("__pycache__/") or p.name.endswith(".pyc"):
            continue
        if rel in EXCLUDE:
            continue
        yield rel, p


def main():
    lines = []
    for rel, p in iter_files():
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        lines.append("%s  %s" % (h, rel))
    seal = OUT / "integrity.sha256"
    seal.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("[bi_seal] wrote integrity.sha256: %d files" % len(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
