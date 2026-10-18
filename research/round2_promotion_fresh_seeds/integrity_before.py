"""Round 2 promotion - BEFORE-hashes of all frozen artifacts (READ-ONLY)."""
import hashlib
import json
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
FROZEN = [
    'policy.py', 'policy_ac.py', 'kit.py', 'evaluate.py', 'organise.py',
    'Dockerfile', '.dockerignore',
    'research/round2_stage3_intermediate_floor/intermediate_policy.py',
    'research/round2_stage3_intermediate_floor/preregistration.md',
    'research/round2_stage3_intermediate_floor/final_interpretation_and_promotion_audit.md',
    'research/round2_stage3_intermediate_floor/promotion_audit.json',
    'research/round2_stage3_intermediate_floor/report.md',
    'research/round2_stage3_intermediate_floor/summary.json',
    'research/round2_stage3_intermediate_floor/diagnose3.py',
    'research/round2_stage4_history_coldstart_audit/report.md',
    'research/round2_stage4_history_coldstart_audit/summary.json',
    'research/round2_stage4_history_coldstart_audit/run_log.txt',
    'research/round2_stage2_floor_ablation/report.md',
    'research/round2_stage2_floor_ablation/interpretation.md',
    'docs/superpowers/round1-research-record.md',
    'results/artifact.sha256',
]


def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


out = {'schema': 'round2_promotion_integrity_before_v1',
       'generated': time.strftime('%Y-%m-%d %H:%M:%S'),
       'files': {rel: sha256(REPO / rel) for rel in FROZEN}}
out['git_head'] = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=REPO,
                                  capture_output=True, text=True).stdout.strip()
out['git_status_short'] = subprocess.run(['git', 'status', '--short'], cwd=REPO,
                                         capture_output=True, text=True).stdout.splitlines()
# frozen candidate verification
import sys
sys.path.insert(0, str(REPO))
import policy
m = policy.load_model()
out['frozen_candidate'] = {
    'model_floor': float(m['floor']),
    'candidate_floor_half': float(m['floor']) / 2.0,
    'registered_value': 0.003952587007648379,
    'matches_registered': float(m['floor']) / 2.0 == 0.003952587007648379,
}
(HERE / 'integrity_before.json').write_text(json.dumps(out, indent=2),
                                            encoding='utf-8')
print('frozen candidate:', out['frozen_candidate'])
print('files hashed:', len(out['files']), '| git head:', out['git_head'][:12])