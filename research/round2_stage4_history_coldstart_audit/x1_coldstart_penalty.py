"""Round 2 Stage 4 - X1: original-floor cold-start penalty from STORED data.

READ-ONLY on frozen diagnostics:
  * Stage 1.5: research/round2_stage1_5/probe_seed101_run{1,2}.json
    (original floor only; per-day counts n_cand/n_above/n_below + category;
    per-variant aggregates incl. floor_removed_pct)
  * Stage 2:   diag_arm_{a,b}_seed{101,102,103}.json
  * Stage 3:   diag_arm_{frozen,intermediate,nofloor}_seed{104,105,106}.json
    (per-variant feasible_total / above_frozen_floor_total /
     above_intermediate_floor_total + per-day counts + selected_scored)

WHAT IS COMPUTED (aggregate level):
  1. determinism: probe run1 vs run2 deep equality
  2. exclusion rate at the ORIGINAL floor per variant, per stored setting
     (rate = 1 - above_frozen/feasible)
  3. threshold contrast on IDENTICAL candidate sets (Stage 3 stores both
     frozen and intermediate counts from the same instrument pass):
     recovery = (above_intermediate - above_frozen)/feasible
  4. cold_start vs other variants, sign consistency across all settings
  5. day-bucket curve of original-floor exclusion from per-day counts
     (day is a PROXY for accumulated history, NOT candidate experience)
  6. zero-selection (all_below_floor) days and greedy-picks-blocked share
  7. outcome context per variant (introduced/mutual/msmi, stored metrics)

WHAT IS NOT COMPUTED - REQUIRED LIMITATION (STOP part):
  candidate-level experience stratification (0/1-2/3+ prior intros per
  feasible candidate) is NOT reconstructible: no stored artifact contains
  per-candidate records for below-floor candidates (counts only), no
  candidate pair ids except for SELECTED pairs (selected_scored), and no
  history/experience field anywhere. Evidence: schema_discovery below.
"""
import hashlib
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
S15 = REPO / 'research' / 'round2_stage1_5'
S2 = REPO / 'research' / 'round2_stage2_floor_ablation'
S3 = REPO / 'research' / 'round2_stage3_intermediate_floor'
OUT_JSON = HERE / 'x1_results.json'

VARIANTS = ['development', 'sparse', 'cold_start', 'delayed', 'shift', 'drift']
DAY_BUCKETS = [('0-9', 0, 9), ('10-19', 10, 19), ('20-39', 20, 39),
               ('40-59', 40, 59)]


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as fh:
        for c in iter(lambda: fh.read(1 << 20), b''):
            h.update(c)
    return h.hexdigest()


def load(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))


def rate_excluded(above, feasible):
    return None if not feasible else 1.0 - above / feasible


def variant_block(rec):
    """Uniform extract from per_variant[variant] of any stored diag/probe."""
    out = {
        'feasible_or_cand': rec.get('feasible_total', rec.get('cand_total')),
        'above_frozen': rec.get('above_frozen_floor_total',
                                rec.get('above_total')),
        'above_intermediate': rec.get('above_intermediate_floor_total'),
        'zero_candidate_days': rec.get('zero_candidate_days'),
        'zero_selected_with_cand': rec.get('zero_selected_with_cand'),
        'zero_selected_categories': rec.get('zero_selected_categories'),
        'decisions': rec.get('decisions'),
        'greedy_n': rec.get('greedy_n'),
        'greedy_below_floor_n': rec.get('greedy_below_floor_n'),
        'introduced': rec.get('introduced'),
        'mutual': (rec.get('metrics') or {}).get('mutual_acceptances',
                                                 rec.get('mutual')),
        'msmi': (rec.get('metrics') or {}).get(
            'mutual_second_meeting_intention', rec.get('msmi')),
    }
    if out['feasible_or_cand'] and out['above_frozen'] is not None:
        out['excl_frozen'] = rate_excluded(out['above_frozen'],
                                           out['feasible_or_cand'])
    else:
        out['excl_frozen'] = None
    if (out['feasible_or_cand'] and out['above_frozen'] is not None
            and out['above_intermediate'] is not None):
        out['excl_intermediate'] = rate_excluded(out['above_intermediate'],
                                                 out['feasible_or_cand'])
        out['recovery_half_floor'] = (
            (out['above_intermediate'] - out['above_frozen'])
            / out['feasible_or_cand'])
    else:
        out['excl_intermediate'] = None
        out['recovery_half_floor'] = None
    if out['greedy_n']:
        out['greedy_blocked_share'] = (out['greedy_below_floor_n']
                                       / out['greedy_n'])
    else:
        out['greedy_blocked_share'] = None
    return out


def day_curve_from_probe(ep):
    """Exclusion by day bucket from stored per-day counts (original floor)."""
    buckets = {name: {'n_cand': 0, 'n_above': 0, 'days': 0}
               for name, _, _ in DAY_BUCKETS}
    for d in ep['days']:
        m = d['match']
        for name, lo, hi in DAY_BUCKETS:
            if lo <= m['day'] <= hi:
                buckets[name]['n_cand'] += m['n_cand']
                buckets[name]['n_above'] += m['n_above']
                buckets[name]['days'] += 1
                break
    out = {}
    for name, b in buckets.items():
        out[name] = {'days': b['days'], 'n_cand': b['n_cand'],
                     'n_above': b['n_above'],
                     'excl_frozen': rate_excluded(b['n_above'], b['n_cand'])}
    return out


def day_curve_from_diag(ep, key_above='n_above'):
    buckets = {name: {'n_cand': 0, 'n_above': 0, 'days': 0}
               for name, _, _ in DAY_BUCKETS}
    for d in ep['days']:
        m = d['match']
        for name, lo, hi in DAY_BUCKETS:
            if lo <= m['day'] <= hi:
                buckets[name]['n_cand'] += m.get('n_cand', 0)
                buckets[name]['n_above'] += m.get(key_above, 0)
                buckets[name]['days'] += 1
                break
    return {name: {'days': b['days'], 'n_cand': b['n_cand'],
                   'n_above': b['n_above'],
                   'excl_frozen': rate_excluded(b['n_above'], b['n_cand'])}
            for name, b in buckets.items()}


def main():
    t0 = time.time()
    out = {'schema': 'round2_stage4_x1_v1',
           'generated': time.strftime('%Y-%m-%d %H:%M:%S'),
           'sources': {}, 'determinism': {}, 'variant_tables': {},
           'coldstart_vs_others': {}, 'day_proxy_curves': {},
           'zero_selection': {}, 'outcome_context': {},
           'schema_discovery': {}, 'limitations': []}

    # ---------- Stage 1.5 (original floor, seed 101) ----------
    p1, p2 = S15 / 'probe_seed101_run1.json', S15 / 'probe_seed101_run2.json'
    pr1, pr2 = load(p1), load(p2)
    out['sources']['stage1.5_probe'] = {
        'file': str(p1.relative_to(REPO)).replace('\\', '/'),
        'sha256_run1': sha256_file(p1), 'sha256_run2': sha256_file(p2),
        'floor': pr1['floor'], 'seed': pr1['seed'], 'schema': pr1['schema']}
    out['determinism']['probe_run1_equals_run2'] = (pr1 == pr2)
    out['schema_discovery']['probe_per_variant_keys'] = sorted(
        pr1['per_variant']['cold_start'])
    out['schema_discovery']['probe_day_match_keys'] = sorted(
        pr1['episodes']['cold_start']['days'][0]['match'])

    rows15 = {}
    for v in VARIANTS:
        rows15[v] = variant_block(pr1['per_variant'][v])
    out['variant_tables']['stage1.5_seed101_original_floor'] = rows15
    out['day_proxy_curves']['stage1.5_seed101_by_variant'] = {
        v: day_curve_from_probe(pr1['episodes'][v]) for v in VARIANTS}
    pooled = {name: {'n_cand': 0, 'n_above': 0, 'days': 0}
              for name, _, _ in DAY_BUCKETS}
    for v in VARIANTS:
        for name in pooled:
            b = out['day_proxy_curves']['stage1.5_seed101_by_variant'][v][name]
            for k in ('n_cand', 'n_above', 'days'):
                pooled[name][k] += b[k]
    out['day_proxy_curves']['stage1.5_seed101_pooled'] = {
        name: {'days': b['days'], 'n_cand': b['n_cand'],
               'n_above': b['n_above'],
               'excl_frozen': rate_excluded(b['n_above'], b['n_cand'])}
        for name, b in pooled.items()}

    # ---------- Stage 2 diags (seeds 101-103; arms a=frozen, b=nofloor) ----------
    s2_rows = {}
    for arm in ('a', 'b'):
        for seed in (101, 102, 103):
            fp = S2 / ('diag_arm_%s_seed%d.json' % (arm, seed))
            d = load(fp)
            key = 's2_arm%s_seed%d' % (arm, seed)
            s2_rows[key] = {
                'file': str(fp.relative_to(REPO)).replace('\\', '/'),
                'arm': d.get('arm'), 'floor': d.get('floor'),
                'schema': d.get('schema'),
                'variants': {v: variant_block(d['per_variant'][v])
                             for v in VARIANTS}}
            if arm == 'a' and seed == 101:
                out['schema_discovery']['stage2_diag_per_variant_keys'] = \
                    sorted(d['per_variant']['cold_start'])
                out['schema_discovery']['stage2_diag_day_match_keys'] = \
                    sorted(d['episodes']['cold_start']['days'][0]['match'])
    out['variant_tables']['stage2'] = s2_rows

    # ---------- Stage 3 diags (seeds 104-106; 3 arms) ----------
    s3_rows = {}
    for arm in ('frozen', 'intermediate', 'nofloor'):
        for seed in (104, 105, 106):
            fp = S3 / ('diag_arm_%s_seed%d.json' % (arm, seed))
            d = load(fp)
            key = 's3_%s_seed%d' % (arm, seed)
            s3_rows[key] = {
                'file': str(fp.relative_to(REPO)).replace('\\', '/'),
                'arm': d.get('arm'), 'floor': d.get('floor'),
                'intermediate_floor': d.get('intermediate_floor'),
                'schema': d.get('schema'),
                'variants': {v: variant_block(d['per_variant'][v])
                             for v in VARIANTS}}
            if arm == 'frozen' and seed == 104:
                out['schema_discovery']['stage3_diag_per_variant_keys'] = \
                    sorted(d['per_variant']['cold_start'])
                out['schema_discovery']['stage3_diag_day_match_keys'] = \
                    sorted(d['episodes']['cold_start']['days'][0]['match'])
    out['variant_tables']['stage3'] = s3_rows

    # ---------- cold_start vs other variants (all settings where comparable) ----------
    def collect_settings():
        settings = []
        for v, blk in rows15.items():
            settings.append(('stage1.5_seed101', None, v, blk))
        for key, row in s2_rows.items():
            for v, blk in row['variants'].items():
                settings.append((key, row['arm'], v, blk))
        for key, row in s3_rows.items():
            for v, blk in row['variants'].items():
                settings.append((key, row['arm'], v, blk))
        return settings

    per_setting = []
    for name, arm, v, blk in collect_settings():
        if blk.get('excl_frozen') is None:
            continue
        others = [b['excl_frozen'] for vv, b in
                  ((vv, bb) for vv, bb in [
                      (vv, (rows15.get(vv)
                            if name == 'stage1.5_seed101'
                            else ((s2_rows.get(name) or s3_rows.get(name))
                                  or {}).get('variants', {}).get(vv)))
                      for vv in VARIANTS if vv != v])
                  if b and b.get('excl_frozen') is not None]
        if not others:
            continue
        mean_others = sum(others) / len(others)
        per_setting.append({
            'setting': name, 'arm': arm, 'variant': v,
            'excl_frozen': blk['excl_frozen'],
            'others_mean': mean_others,
            'diff': blk['excl_frozen'] - mean_others})
    cs = [s for s in per_setting if s['variant'] == 'cold_start']
    out['coldstart_vs_others']['per_setting_all_variants'] = per_setting
    out['coldstart_vs_others']['cold_start_settings'] = cs
    out['coldstart_vs_others']['cold_start_gt_others_count'] = \
        sum(1 for s in cs if s['diff'] > 0)
    out['coldstart_vs_others']['n_settings'] = len(cs)

    # ---------- zero-selection / greedy-blocked summary ----------
    zs = {}
    for name, arm, v, blk in collect_settings():
        zs.setdefault(name, {})[v] = {
            'zero_selected_with_cand': blk.get('zero_selected_with_cand'),
            'zero_selected_categories': blk.get('zero_selected_categories'),
            'decisions': blk.get('decisions'),
            'greedy_blocked_share': blk.get('greedy_blocked_share')}
    out['zero_selection'] = zs

    # ---------- outcome context (stored metrics only) ----------
    oc = {}
    for name, arm, v, blk in collect_settings():
        if name.startswith('stage1.5') or name.startswith('s3'):
            oc.setdefault(name, {})[v] = {
                'introduced': blk.get('introduced'),
                'mutual': blk.get('mutual'), 'msmi': blk.get('msmi')}
    out['outcome_context'] = oc

    # ---------- limitations (required STOP part) ----------
    out['limitations'] = [
        {'id': 'X1-L1',
         'claim': 'candidate-level experience stratification impossible '
                  'from stored data',
         'evidence': [
             'probe/stage2/stage3 per-day match records store COUNTS only '
             '(n_cand/n_above/n_below...); no per-candidate rows for '
             'below-floor candidates',
             'per-candidate pair ids + scores exist ONLY for SELECTED pairs '
             "(key 'selected_scored'); below-floor candidates are a count "
             '(n_below) with no ids/scores/experience',
             "no stored key anywhere contains 'hist_', 'experience', "
             "'prior_intro' or member-history fields for candidates",
             'schema_discovery in this file lists the exact stored keys'],
         'consequence': "the required 'history available at candidate "
                        "decision time' stratification (0/1-2/3+ prior "
                        'intros per feasible candidate) cannot be computed '
                        'without NEW simulator runs, which this stage does '
                        'not perform; reported as STOP for that sub-part',
         'proxy_used': 'variant identity (cold_start) and decision-day '
                       'buckets (early days = low accumulated history) are '
                       'reported as explicitly-labeled proxies only'},
    ]
    out['total_elapsed_seconds'] = round(time.time() - t0, 1)
    OUT_JSON.write_text(json.dumps(out, indent=2), encoding='utf-8')
    print('[X1] probe run1==run2: %s' % out['determinism']
          ['probe_run1_equals_run2'])
    print('[X1] cold_start settings: %d, cold_start > others_mean: %d' % (
        out['coldstart_vs_others']['n_settings'],
        out['coldstart_vs_others']['cold_start_gt_others_count']))
    print('[X1] stage1.5 exclusion by variant:',
          {v: (round(b['excl_frozen'], 4) if b['excl_frozen'] is not None
               else None) for v, b in rows15.items()})
    print('[X1] day-proxy pooled:',
          {k: (round(v2['excl_frozen'], 4) if v2['excl_frozen'] is not None
               else None)
           for k, v2 in out['day_proxy_curves']
           ['stage1.5_seed101_pooled'].items()})
    print('[X1] wrote %s (%d bytes)' % (OUT_JSON.name,
                                        OUT_JSON.stat().st_size))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())