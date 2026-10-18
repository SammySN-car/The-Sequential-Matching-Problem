"""Generate thin launchers in policies/ from the registry.
Run after any registry change: python research/method_tournament/gen_policies.py"""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1]))  # repo root (kit.py)
from registry import REGISTRY

TEMPLATE = '''"""Auto-generated launcher for {mid}. Do not edit; regenerate instead."""
import pathlib
import sys
_HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))
sys.path.insert(0, str(_HERE.parents[2]))
from _cli import run
from registry import REGISTRY
raise SystemExit(run(REGISTRY['{mid}']))
'''


def main():
    out = HERE / 'policies'
    out.mkdir(exist_ok=True)
    for mid in sorted(REGISTRY):
        (out / (mid + '.py')).write_text(TEMPLATE.format(mid=mid), encoding='utf-8')
    print('wrote %d launchers' % len(REGISTRY))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
