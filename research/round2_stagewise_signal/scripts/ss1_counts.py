"""Section 3: unconditional + conditional funnel counts, stratified.

Produces stage_counts.csv (overall + day band + baseline score + soft-field
count + goal status + selected flags + headroom) and stage_by_variant.csv.
All unselected-pair labels remain diagnostic simulator counterfactuals.
"""
import csv, json, sys, time
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ss_common as s  # noqa: E402

# conditional conversions: (label, denom stage, target stage)
COND = [
    ('mutual_given_responded', 'both_responded', 'mutual'),
    ('date_given_mutual', 'mutual', 'date'),
    ('deadline_given_date', 'date', 'date_within_deadline'),
    ('timely_second_given_date', 'date', 'timely_second'),
    ('msmi_given_deadline', 'date_within_deadline', 'final_msmi'),
]


def rate_row(scope, denom_mask, target, fr, stratum_type, stratum_value):
    y = fr['stages'][target][denom_mask]
    seeds = [x for x, m in zip(fr['seeds'], denom_mask) if m]
    n = int(denom_mask.sum())
    n_pos = int(y.sum())
    if n == 0:
        return dict(stratum_type=stratum_type, stratum_value=stratum_value,
                    scope=scope, stage=target, n_denom=0, n_pos=0,
                    rate='', ci95_low='', ci95_high='', power_flag='empty')
    rate = float(y.mean())
    ci = s.seed_boot_rate(y, seeds)
    return dict(stratum_type=stratum_type, stratum_value=stratum_value,
                scope=scope, stage=target, n_denom=n, n_pos=n_pos,
                rate=round(rate, 6), ci95_low=round(ci[0], 6),
                ci95_high=round(ci[1], 6),
                power_flag=s.power_flag(y, seeds))


def main():
    t0 = time.time()
    s.log('ss1_counts start')
    fr = s.build_frame()
    n = len(fr['seeds'])
    rows = []

    def block(mask, stype, sval):
        for st in s.STAGES:
            rows.append(rate_row('unconditional', mask, st, fr, stype, sval))
        for clabel, dstage, tstage in COND:
            rows.append(rate_row(clabel, mask & (fr['stages'][dstage] == 1),
                                 tstage, fr, stype, sval))

    # overall
    block(np.ones(n, dtype=bool), 'overall', 'all')
    # variant
    for v in sorted(set(fr['variants'])):
        block(np.array([x == v for x in fr['variants']]), 'variant', v)
    # day band
    for b in ('0-9', '10-19', '20-39', '40-59'):
        block(np.array([x == b for x in fr['day_band']]), 'day_band', b)
    # baseline pair score
    for sc in sorted(set(fr['pair_score'].tolist())):
        block(fr['pair_score'] == sc, 'baseline_score', str(int(sc)))
    # observed soft-field count
    for k in range(0, 8):
        block(fr['n_soft_observed'] == k, 'n_soft_observed', str(k))
    # relationship-goal status
    for g in ('match', 'mismatch', 'unknown', 'declined'):
        block(np.array([x == g for x in fr['goal']]), 'goal_status', g)
    # selection flags (selected vs unselected = descriptive counterfactual)
    for val, lab in ((1, 'greedy_selected'), (0, 'greedy_unselected')):
        block(fr['greedy_selected'] == val, 'greedy_selected', lab)
    for val, lab in ((1, 'f2_selected'), (0, 'f2_unselected')):
        block(fr['f2_selected'] == val, 'f2_selected', lab)
    # headroom states
    for val, lab in ((1, 'headroom_state'), (0, 'nonheadroom_state')):
        block(fr['headroom'] == val, 'headroom_state', lab)

    with open(s.OUT / 'stage_counts.csv', 'w', newline='',
              encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)
    s.log('wrote stage_counts.csv (%d rows)' % len(rows))

    # ---- stage_by_variant.csv: unconditional funnel + losses -------------
    vrows = []
    for v in sorted(set(fr['variants'])):
        m = np.array([x == v for x in fr['variants']])
        rec = dict(variant=v, n_opportunities=int(m.sum()))
        for st in s.STAGES:
            y = fr['stages'][st][m]
            rec['n_' + st] = int(y.sum())
            rec['rate_' + st] = round(float(y.mean()), 6)
        # successive losses
        rec['lost_responded_to_mutual'] = rec['n_both_responded'] - rec['n_mutual']
        rec['lost_mutual_to_date'] = rec['n_mutual'] - rec['n_date']
        rec['lost_date_missed_deadline'] = rec['n_date'] - rec['n_date_within_deadline']
        rec['lost_date_to_timely_second'] = rec['n_date'] - rec['n_timely_second']
        rec['lost_deadline_and_second_to_msmi'] = (
            rec['n_date_within_deadline'] - rec['n_final_msmi'])
        vrows.append(rec)
    with open(s.OUT / 'stage_by_variant.csv', 'w', newline='',
              encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=list(vrows[0]))
        w.writeheader(); w.writerows(vrows)
    s.log('wrote stage_by_variant.csv (%d rows)' % len(vrows))

    # overall funnel summary for the report
    summ = {}
    m = np.ones(n, dtype=bool)
    for st in s.STAGES:
        y = fr['stages'][st]
        summ[st] = dict(n=int(y.sum()), rate=round(float(y.mean()), 6),
                        ci=s.seed_boot_rate(y, fr['seeds']))
    summ['event_details'] = {
        k: int(sum(1 for r in fr['event_detail'] if r.get(k)))
        for k in ('n_intro_no_response', 'n_intro_explicit_no',
                  'n_second_missing', 'n_second_late')}
    (s.OUT / 'funnel_summary.json').write_text(
        json.dumps(summ, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    s.log('wrote funnel_summary.json')
    s.log('ss1_counts done (%.1fs)' % (time.time() - t0))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
