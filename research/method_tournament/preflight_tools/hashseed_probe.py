"""PYTHONHASHSEED independence probe: fixture seeds >= 90210 only.
Prints one sha256 digest of world serialization + 60-day baseline ask/match actions."""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

from kit import Simulator, baseline_asks, baseline_match, generate  # noqa: E402

parts = []
for seed in (90210, 90211):
    world = generate(seed, 200, 'evaluation', 'development')
    parts.append(json.dumps(world['members'], sort_keys=True, default=str))
sim = Simulator(generate(90210, 200, 'evaluation', 'development'))
for day in range(60):
    asks = baseline_asks(sim.observe())
    parts.append(json.dumps(asks, sort_keys=True))
    sim.resolve_asks(asks)
    pairs = baseline_match(sim.observe())
    parts.append(json.dumps(pairs, sort_keys=True))
    sim.advance(pairs)
parts.append(json.dumps(sim.metrics(), sort_keys=True, default=str))
print(hashlib.sha256('\x1f'.join(parts).encode()).hexdigest())