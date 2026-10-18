"""Round 2 Stage 4 - Q3: promotion-comparison noise from STORED Stage 2/3 runs.

READ-ONLY. Reads the 9 frozen Stage 3 arm run JSONs (evaluate output format),
extracts per-seed primary scores, computes paired differences and a
sampling-noise estimate for a FUTURE frozen-candidate comparison.
No re-runs, no new seeds, no tuning.
"""
import json
import math
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
S3 = REPO / 'research' / 'round2_stage3_intermediate_floor'
OUT_JSON = HERE / 'q3_noise_results.json'
ARMS = ('frozen', 'intermediate', 'nofloor')
SEEDS = (104, 105, 106)


def primary(path):
    d = json.loads(Path(path).read_text(encoding='utf-8'))
    if 'summary' in d and 'primary_score' in d['summary']:
        return d['summary']['primary_score'], sorted(d.keys())
    raise SystemExit('unexpected arm run schema: %s' % path)


def main():
    out = {'schema': 'round2_stage4_q3_v1',
           'source_files': {}, 'primary_by_arm_seed': {},
           'paired_differences': {}, 'noise_estimate': {},
           'msmi_events': {}}
    keys_seen = None
    for arm in ARMS:
        for seed in SEEDS:
            p = S3 / ('arm_%s_seed%d.json' % (arm, seed))
            val, keys = primary(p)
            out['source_files']['%s_seed%d' % (arm, seed)] = {
                'file': str(p.relative_to(REPO)).replace('\\', '/'),
                'primary_score': val}
            out['primary_by_arm_seed'].setdefault(arm, {})[str(seed)] = val
            if keys_seen is None:
                keys_seen = keys
    out['arm_run_top_level_keys'] = keys_seen

    for a, b in (('intermediate', 'frozen'), ('nofloor', 'frozen'),
                 ('nofloor', 'intermediate')):
        diffs = [out['primary_by_arm_seed'][a][str(s)]
                 - out['primary_by_arm_seed'][b][str(s)] for s in SEEDS]
        mean = statistics.mean(diffs)
        sd = statistics.stdev(diffs) if len(diffs) > 1 else None
        out['paired_differences']['%s_minus_%s' % (a, b)] = {
            'per_seed': {str(s): d for s, d in zip(SEEDS, diffs)},
            'mean': mean, 'sd_across_seeds': sd,
            'sem': (sd / math.sqrt(len(diffs))) if sd is not None else None}

    # sampling guidance from the frozen-vs-intermediate paired SD
    key = 'intermediate_minus_frozen'
    sd = out['paired_differences'][key]['sd_across_seeds']
    guide = {}
    if sd:
        for d in (0.05, 0.10, 0.20):
            # normal approx, 2-sided alpha .05, power .80: n ~ ((1.96+.84)*sd/d)^2
            n = ((1.96 + 0.84) * sd / d) ** 2
            guide['detect_mean_diff_%.2f' % d] = {
                'approx_n_paired_seeds': int(math.ceil(n)),
                'formula': 'n = ceil(((1.96+0.84)*sd/d)^2), sd = paired '
                           'across-seed SD, normal approximation'}
    out['noise_estimate'] = {
        'basis': '3 paired development seeds (104-106) from frozen Stage 3; '
                 'descriptive, not a power analysis claim',
        'paired_sd_key': key, 'paired_sd': sd,
        'normal_approx_guidance': guide,
        'msmi_rarity_note': 'primary score counts MSMI events (9-13 per arm '
                            'over 18 episodes); Poisson relative SE of a '
                            'count k is 1/sqrt(k) ~ 0.28-0.33'}

    # MSMI event counts per arm from frozen Stage 3 summary.json (stored)
    s3sum = json.loads((S3 / 'summary.json').read_text(encoding='utf-8'))
    out['msmi_events']['from_stage3_summary_note'] = (
        'stored report: MSMI events frozen 9 / intermediate 13 / nofloor 10 '
        'over 18 episodes each')

    OUT_JSON.write_text(json.dumps(out, indent=2), encoding='utf-8')
    print('[Q3] primary by arm:', json.dumps(out['primary_by_arm_seed']))
    print('[Q3] paired diffs:',
          json.dumps({k: {'mean': v['mean'], 'sd': v['sd_across_seeds']}
                      for k, v in out['paired_differences'].items()}))
    print('[Q3] guidance:',
          json.dumps(out['noise_estimate']['normal_approx_guidance']))
    print('[Q3] wrote', OUT_JSON.name)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())