"""Section 5: relationship-goal (and all 7 soft channels) across the funnel.

Descriptive stage-rate association (with seed-group CI) + cross-validated
predictive separation (stage-model OOF score by channel state, with CI).
Causal effect is NOT established here and is disclaimed in the report.
Channels use the frozen soft-state definitions (s3_signal SOFT_STATES).
"""
import csv, json, sys, time
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ss_common as s  # noqa: E402

goal_csv_cols = ['row_type', 'stage', 'goal_status', 'n_edges', 'n_pos',
                 'rate', 'ci95_low', 'ci95_high', 'mean_stageB_score',
                 'n_a', 'n_b', 'rate_diff', 'diff_ci95_low', 'diff_ci95_high',
                 'mean_score_a', 'mean_score_b', 'score_delta',
                 'score_delta_ci95_low', 'score_delta_ci95_high',
                 'power_flag']
chan_csv_cols = ['row_type', 'channel', 'stage', 'state', 'n_edges', 'n_pos',
                 'rate', 'ci95_low', 'ci95_high', 'mean_stageB_score',
                 'n_a', 'n_b', 'rate_diff', 'diff_ci95_low', 'diff_ci95_high',
                 'mean_score_a', 'mean_score_b', 'score_delta',
                 'score_delta_ci95_low', 'score_delta_ci95_high',
                 'power_flag']


def analyze_channel(ch, fr, stageB):
    """Per-stage rate + match-vs-mismatch contrast for one soft channel."""
    rows = []
    states = [cs.get(ch, 'unknown') for cs in fr['channel_states']]
    for stage in s.STAGES:
        y = fr['stages'][stage]
        sc = stageB[stage]
        # descriptive rates per state
        for st in ('match', 'mismatch', 'unknown', 'declined'):
            m = np.array([x == st for x in states])
            if m.sum() == 0:
                continue
            seeds_c = [x for x, g in zip(fr['seeds'], m) if g]
            ci = s.seed_boot_rate(y[m], seeds_c)
            rows.append(dict(row_type='rate', channel=ch, stage=stage,
                             state=st, n_edges=int(m.sum()),
                             n_pos=int(y[m].sum()),
                             rate=round(float(y[m].mean()), 6),
                             ci95_low=round(ci[0], 6),
                             ci95_high=round(ci[1], 6),
                             mean_stageB_score=round(
                                 float(np.mean(sc[m])), 6)))
        # match vs mismatch contrast
        ma = np.array([x == 'match' for x in states])
        mb = np.array([x == 'mismatch' for x in states])
        if ma.sum() >= 15 and mb.sum() >= 15:
            sa = [(g, float(v)) for g, v in zip(fr['seeds'], y) if True]
            # two-sample cluster bootstrap on stage rates
            rate_a = float(y[ma].mean()); rate_b = float(y[mb].mean())
            diff_ci = s.cluster_boot_diff(
                [(g, float(v)) for g, v, mm in zip(fr['seeds'], y, ma) if mm],
                [(g, float(v)) for g, v, mm in zip(fr['seeds'], y, mb) if mm])
            score_a = float(np.mean(sc[ma])); score_b = float(np.mean(sc[mb]))
            score_ci = s.cluster_boot_diff(
                [(g, float(v)) for g, v, mm in zip(fr['seeds'], sc, ma) if mm],
                [(g, float(v)) for g, v, mm in zip(fr['seeds'], sc, mb) if mm])
            rows.append(dict(row_type='contrast', channel=ch, stage=stage,
                             state='match_minus_mismatch',
                             n_edges='', n_pos='', rate='',
                             ci95_low='', ci95_high='',
                             mean_stageB_score='',
                             n_a=int(ma.sum()), n_b=int(mb.sum()),
                             rate_diff=round(rate_a - rate_b, 6),
                             diff_ci95_low=round(diff_ci[0], 6),
                             diff_ci95_high=round(diff_ci[1], 6),
                             mean_score_a=round(score_a, 6),
                             mean_score_b=round(score_b, 6),
                             score_delta=round(score_a - score_b, 6),
                             score_delta_ci95_low=round(score_ci[0], 6),
                             score_delta_ci95_high=round(score_ci[1], 6),
                             power_flag=s.power_flag(y, fr['seeds'])))
    return rows


def main():
    t0 = time.time()
    s.log('ss3_goal start')
    fr = s.build_frame()
    sb_all = json.loads((s.OUT / 'stage_oof_scores.json').read_text(
        encoding='utf-8'))
    stageB = {st: np.array(sb_all['B_soft_state|%s' % st]) for st in s.STAGES}

    # ---- relationship_goal (dedicated deliverable) -----------------------
    goal_rows = []
    for r in analyze_channel('relationship_goal', fr, stageB):
        r2 = dict(row_type=r.pop('row_type'), channel=r.pop('channel'), **r)
        r2['goal_status'] = r2.pop('state')   # rename for the goal CSV
        goal_rows.append(r2)
    with open(s.OUT / 'stage_by_goal_status.csv', 'w', newline='',
              encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=goal_csv_cols, restval='')
        w.writeheader()
        for r in goal_rows:
            w.writerow({k: r.get(k, '') for k in goal_csv_cols})
    s.log('wrote stage_by_goal_status.csv (%d rows)' % len(goal_rows))

    # ---- all 7 soft channels ---------------------------------------------
    chan_rows = []
    for ch in s.SOFT:
        chan_rows.extend(analyze_channel(ch, fr, stageB))
    with open(s.OUT / 'stage_by_soft_channel.csv', 'w', newline='',
              encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=chan_csv_cols, restval='')
        w.writeheader()
        for r in chan_rows:
            w.writerow({k: r.get(k, '') for k in chan_csv_cols})
    s.log('wrote stage_by_soft_channel.csv (%d rows)' % len(chan_rows))

    # ---- compact JSON of goal contrasts for the report -------------------
    compact = {}
    for r in goal_rows:
        if r.get('row_type') == 'contrast':
            compact[r['stage']] = dict(
                n_match=r['n_a'], n_mismatch=r['n_b'],
                rate_match=None, rate_diff=r['rate_diff'],
                diff_ci=[r['diff_ci95_low'], r['diff_ci95_high']],
                score_delta=r['score_delta'],
                score_delta_ci=[r['score_delta_ci95_low'],
                                r['score_delta_ci95_high']],
                excludes_zero_rate=bool(
                    r['diff_ci95_low'] > 0 or r['diff_ci95_high'] < 0),
                excludes_zero_score=bool(
                    r['score_delta_ci95_low'] > 0
                    or r['score_delta_ci95_high'] < 0))
    # attach match/mismatch rates
    for r in goal_rows:
        if r.get('row_type') == 'rate' and r['stage'] in compact:
            if r['goal_status'] == 'match':
                compact[r['stage']]['rate_match'] = r['rate']
                compact[r['stage']]['n_match_edges'] = r['n_edges']
            if r['goal_status'] == 'mismatch':
                compact[r['stage']]['rate_mismatch'] = r['rate']
    (s.OUT / 'goal_signal.json').write_text(
        json.dumps(compact, indent=1, sort_keys=True) + '\n',
        encoding='utf-8')
    s.log('wrote goal_signal.json')
    s.log('ss3_goal done (%.1fs)' % (time.time() - t0))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
