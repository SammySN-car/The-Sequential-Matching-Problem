"""Finalize container_fidelity.json structure (honest, self-documenting)."""
import json
from pathlib import Path

path = Path(__file__).resolve().parent / 'container_fidelity.json'
j = json.loads(path.read_text(encoding='utf-8'))
old_mm = j.get('mismatches', {})
ce = j.get('control_extra', {})

parity = {
    'E1_local_vs_container': old_mm.get('E1', []),
    'E2_local_vs_container': old_mm.get('E2', []),
    'E3_local_vs_container': old_mm.get('E3', []),
    'C_greedy_derived_image_local_vs_container':
        ce.get('C_greedy_derived_image', []),
    'C_ac_official_image_local_vs_container':
        ce.get('C_ac_official_image', []),
}
ac_invalid = ce.get('C_ac_invalid', [])
note = (
    'The frozen Dockerfile ENTRYPOINT runs policy.py with NO args; policy.py '
    'argparse default is ac (A+C), not greedy - see docs/POLICY_INTERFACE.md. '
    'Therefore: (1) official-image parity is verified on its default A+C mode '
    '(C_ac_*), (2) greedy parity uses the derived Dockerfile.control image '
    '(e3-control-greedy), and (3) the original plain-image comparison '
    '(e3-control vs local greedy, 12/12 differing) is the expected mode '
    'difference, not an environment divergence. Evidence: day-by-day '
    'request/response diff over all 60 days showed NO divergence for greedy '
    'local vs container (seed 119, development); one cold-start 10s '
    'invocation timeout in the verification slice was retried successfully '
    'after a warm-up invoke.')

out = {
    'images': dict(j.get('images', {}),
                   C_greedy_derived='e3-control-greedy'),
    'slice_seeds': j.get('slice_seeds'),
    'episodes_per_comparison': j.get('episodes_per_arm'),
    'parity_checks': parity,
    'ac_official_image_invalid': ac_invalid,
    'note': note,
}
out['pass'] = (all(v == [] for v in parity.values()) and not ac_invalid)
path.write_text(json.dumps(out, indent=2, allow_nan=False) + '\n',
                encoding='utf-8')
print('parity checks:', {k: len(v) for k, v in parity.items()})
print('ac_invalid:', len(ac_invalid), '| PASS:', out['pass'])
