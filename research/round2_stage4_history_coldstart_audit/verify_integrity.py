"""Round 2 Stage 4 - after-hash verification of ALL frozen files (READ-ONLY)."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
EXPECTED = {
    'policy.py': '379CC2D9519E8D3B',
    'policy_ac.py': '90FB9AD306E89BFB',
    'kit.py': '0D2CB3D3B46CA2A6',
    'evaluate.py': 'D09CC14BF634A741',
    'organise.py': 'DA9D6B3A197F1FF8',
    'Dockerfile': 'FEF95FA3D6BC038F',
    '.dockerignore': '6FA959B629F9ED8C',
    'research/round2_stage3_intermediate_floor/preregistration.md': 'FA11A2FB4DF53D50',
    'research/round2_stage3_intermediate_floor/final_interpretation_and_promotion_audit.md': 'B76AE4ABAC72F5EB',
    'research/round2_stage3_intermediate_floor/promotion_audit.json': '0138D36F0B13DF42',
    'research/round2_stage3_intermediate_floor/intermediate_policy.py': 'A76FD0EE0C2B9579',
    'research/round2_stage3_intermediate_floor/report.md': 'D47BAE2512527587',
    'research/round2_stage3_intermediate_floor/summary.json': 'C4B4EF5690B617C6',
    'research/round2_stage2_floor_ablation/report.md': '09E4FF744184ADFA',
    'research/round2_stage2_floor_ablation/interpretation.md': 'E46A066AC6D97E2C',
    'docs/superpowers/round1-research-record.md': '661115F512A41B5A',
    'results/artifact.sha256': '79ACD52BDC11C909',
}


def sha16(rel):
    h = hashlib.sha256()
    with open(REPO / rel, 'rb') as fh:
        for c in iter(lambda: fh.read(1 << 20), b''):
            h.update(c)
    return h.hexdigest()[:16].upper()


result = {'checked': len(EXPECTED), 'all_match': True, 'files': {}}
for rel, exp in EXPECTED.items():
    got = sha16(rel)
    ok = got == exp
    result['files'][rel] = {'expected': exp, 'got': got, 'match': ok}
    if not ok:
        result['all_match'] = False
    print('%-4s %-10s %s' % ('OK' if ok else 'FAIL', got, rel))
print('ALL MATCH:', result['all_match'])
(HERE / 'integrity_after.json').write_text(
    json.dumps(result, indent=2), encoding='utf-8')