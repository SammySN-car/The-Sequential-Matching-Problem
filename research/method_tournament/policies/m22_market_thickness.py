"""Auto-generated launcher for m22_market_thickness. Do not edit; regenerate instead."""
import pathlib
import sys
_HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))
sys.path.insert(0, str(_HERE.parents[2]))
from _cli import run
from registry import REGISTRY
raise SystemExit(run(REGISTRY['m22_market_thickness']))
