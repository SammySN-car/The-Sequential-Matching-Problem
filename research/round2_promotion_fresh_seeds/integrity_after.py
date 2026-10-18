"""Round 2 promotion - AFTER-hashes; asserts zero drift vs integrity_before.json."""
import hashlib
import json
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


before = json.loads((HERE / 'integrity_before.json').read_text(encoding='utf-8'))
after = {'schema': 'round2_promotion_integrity_after_v1',
         'generated': time.strftime('%Y-%m-%d %H:%M:%S'),
         'files': {rel: sha256(REPO / rel) for rel in before['files']}}
after['git_head'] = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=REPO,
                                   capture_output=True, text=True).stdout.strip()
after['git_status_short'] = subprocess.run(['git', 'status', '--short'], cwd=REPO,
                                           capture_output=True, text=True).stdout.splitlines()

mism = {rel: {'before': before['files'][rel], 'after': h}
        for rel, h in after['files'].items() if before['files'][rel] != h}
after['frozen_file_mismatches'] = mism
after['git_head_unchanged'] = before['git_head'] == after['git_head']
after['git_status_unchanged'] = before['git_status_short'] == after['git_status_short']
after['no_new_commits'] = (subprocess.run(['git', 'rev-list', '--count', 'HEAD'],
                                          cwd=REPO, capture_output=True,
                                          text=True).stdout.strip() == '1')
after['all_pass'] = (not mism and after['git_head_unchanged']
                     and after['no_new_commits'])
(HERE / 'integrity_after.json').write_text(json.dumps(after, indent=2),
                                           encoding='utf-8')
print('files checked:', len(after['files']))
print('mismatches:', list(mism) if mism else 'NONE')
print('git head unchanged:', after['git_head_unchanged'],
      '| status unchanged:', after['git_status_unchanged'],
      '| no new commits:', after['no_new_commits'])
print('ALL PASS:', after['all_pass'])