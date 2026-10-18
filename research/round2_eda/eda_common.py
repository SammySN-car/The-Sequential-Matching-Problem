import hashlib
import json
import math
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
TABLES = OUT / 'tables'
PLOTS = OUT / 'plots'
for p in (TABLES, PLOTS):
    p.mkdir(parents=True, exist_ok=True)
LOG = OUT / 'run_log.txt'


def log(msg):
    stamp = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    line = f'[{stamp}] {msg}'
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(line + '\n')
    print(line, flush=True)


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


def write_csv(path, rows, fieldnames=None):
    import csv
    rows = list(rows)
    if not rows:
        log(f'WARNING: empty table {path.name}')
        Path(path).write_text('', encoding='utf-8')
        return
    fieldnames = fieldnames or list(rows[0].keys())
    with open(path, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    log(f'wrote {path.name} ({len(rows)} rows)')


def read_jsonl(path):
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def load_n01_intros():
    return list(read_jsonl(ROOT / 'research' / 'next_method_search' / 'n01_introductions.jsonl'))


def load_n01_days():
    return list(read_jsonl(ROOT / 'research' / 'next_method_search' / 'n01_days.jsonl'))


def mean(xs):
    """Arithmetic mean; 0.0 for empty sequences."""
    xs = list(xs)
    return sum(xs) / len(xs) if xs else 0.0
