"""Gates G2 (determinism rerun) and G3 (local vs container agreement)."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

SKIP_KEYS = {'inference_seconds', 'mode'}


def strip(o):
    if isinstance(o, dict):
        return {k: strip(v) for k, v in o.items()
                if k not in SKIP_KEYS and k != 'ranking_key_descending'}
    if isinstance(o, list):
        return [strip(x) for x in o]
    return o


def compare(a, b):
    """Returns (equal, list_of_diff_paths) after stripping nondeterminism."""
    diffs = []
    sa, sb = strip(a), strip(b)

    def walk(x, y, p):
        if type(x) is not type(y):
            diffs.append((p, type(x).__name__, type(y).__name__))
            return
        if isinstance(x, dict):
            if sorted(x) != sorted(y):
                diffs.append((p + '.keys',
                              sorted(set(x) - set(y)), sorted(set(y) - set(x))))
                return
            for k in x:
                walk(x[k], y[k], p + '.' + str(k))
        elif isinstance(x, list):
            if len(x) != len(y):
                diffs.append((p + '.len', len(x), len(y)))
                return
            for i, (u, v) in enumerate(zip(x, y)):
                walk(u, v, '%s[%d]' % (p, i))
        else:
            if x != y:
                diffs.append((p, x, y))
    walk(sa, sb, '')
    # ranking_key_descending: compare deterministic prefix (first 4 elems)
    ra, rb = a['summary']['ranking_key_descending'], b['summary']['ranking_key_descending']
    if ra[:4] != rb[:4]:
        diffs.append(('summary.ranking_key_descending[:4]', ra[:4], rb[:4]))
    return (not diffs), diffs


out = {}

# ---- G2 determinism ----
pairs = [
    ('arm_greedy_seed107.json', 'arm_greedy_seed107_rerun.json'),
    ('arm_original_seed107.json', 'arm_original_seed107_rerun.json'),
    ('arm_floorhalf_seed107.json', 'arm_floorhalf_seed107_rerun.json'),
    ('arm_floorhalf_seed118.json', 'arm_floorhalf_seed118_rerun.json'),
]
g2 = []
for a, b in pairs:
    ja = json.loads((HERE / a).read_text(encoding='utf-8'))
    jb = json.loads((HERE / b).read_text(encoding='utf-8'))
    eq, diffs = compare(ja, jb)
    # explicit action digest check
    da = [e['action_sha256'] for e in ja['episodes']]
    db = [e['action_sha256'] for e in jb['episodes']]
    g2.append({'pair': '%s vs %s' % (a, b), 'equal_excl_inference': eq,
               'action_sha256_all_match': da == db,
               'primary_match': ja['summary']['primary_score'] == jb['summary']['primary_score'],
               'n_diffs': len(diffs), 'diffs': diffs[:5]})
out['G2_determinism'] = g2

# ---- G3 container ----
jl = json.loads((HERE / 'arm_original_seed107.json').read_text(encoding='utf-8'))
jc = json.loads((HERE / 'arm_original_seed107_container.json').read_text(encoding='utf-8'))
eq, diffs = compare(jl, jc)
da = [e['action_sha256'] for e in jl['episodes']]
db = [e['action_sha256'] for e in jc['episodes']]
out['G3_container'] = {
    'scope': 'A+C arm (arm B) seed 107, all 6 variants; image '
             'sequential-policy:1.0 (image policy.py/kit.py sha256 verified '
             'byte-identical to repo). Docker path runs policy.py with no '
             'args -> default ac mode == arm B; container-vs-local-arm-A was '
             'the initial (wrong-target) comparison, corrected here.',
    'equal_excl_inference_and_mode': eq,
    'action_sha256_all_match': da == db,
    'primary_match': jl['summary']['primary_score'] == jc['summary']['primary_score'],
    'local_mode': jl['mode'], 'container_mode': jc['mode'], 'note_initial_wrong_target': 'compared vs greedy first (mismatch, expected: different policy); corrected to arm B',
    'n_diffs': len(diffs), 'diffs': diffs[:10],
    'arms_b_c_container_note': 'A+C arms cannot run in the frozen image: '
                               'Dockerfile ships kit.py+policy.py only with '
                               'ENTRYPOINT policy.py; Dockerfile is frozen.',
}

(HERE / 'gates_g2_g3.json').write_text(json.dumps(out, indent=2), encoding='utf-8')
for p in g2:
    print('G2', p['pair'], '-> equal:', p['equal_excl_inference'],
          '| digests:', p['action_sha256_all_match'], '| diffs:', p['n_diffs'])
c = out['G3_container']
print('G3 container -> equal:', c['equal_excl_inference_and_mode'],
      '| digests:', c['action_sha256_all_match'],
      '| diffs:', c['n_diffs'])
if not (all(p['equal_excl_inference'] for p in g2) and eq):
    print('DETAILS:', [p['diffs'] for p in g2 if not p['equal_excl_inference']], diffs[:10])