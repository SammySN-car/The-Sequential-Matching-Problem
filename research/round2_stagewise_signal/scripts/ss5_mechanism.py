"""Section 7: source-mechanism description (NOT a predictive model).

Reads kit.py, verifies the frozen equation lines still match, and writes
mechanism_notes.md mapping each outcome stage to its explicit dependence on
hidden generator values. Hidden values never enter a feature matrix.
"""
import json, re, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ss_common as s  # noqa: E402

# frozen source fragments (kit.py) -> what they govern
FRAGMENTS = {
    'shared_randomness': "shared=r.gauss(0,.45)",
    'responded_uses_response_rate': "responded.append(r.random()<actor['response_rate'])",
    'accept_uses_prob': "accept.append(r.random()<self._prob(actor,other,shared))",
    'accept_weights_default': "weights={'relationship_goal':.7,'relationship_pace':.4,'lifestyle':.25,'conversations':.2}",
    'accept_weights_shift': "weights={'relationship_goal':.25,'relationship_pace':.8,'lifestyle':-.25,'conversations':.5}",
    'fit_equation': "fit=sum(w*(1 if f[k]==g[k] else -.5) for k,w in weights.items())",
    'drift': "drift=-.5 if variant=='drift' and self.day>=35 else 0",
    'accept_logit': "z=-.25+a['bias']+fit+shared+drift",
    'intro_delay': "delay=r.randint(1,7)",
    'date_day': "date_day=max(response_days)+r.randint(1,14)",
    'date_delayed_extra': "if self.world['variant']=='delayed': date_day+=r.randint(5,12)",
    'date_happened_prob': "happened=r.random()<.78",
    'second_answer_rate': "answer=r.random()<actor['response_rate'];delay=r.randint(1,5)",
    'second_logit_goal_agreement': "p=1/(1+math.exp(-(.15+actor['second_bias']+shared+.4*(actor['truth']['relationship_goal']==other['truth']['relationship_goal']))))",
    'second_yes_and_on_time': "yes=r.random()<p;seconds.append(answer and yes);on_time.append(delay<=3)",
    'msmi_official': "msmi+=bool(ds) and ds[0]['occurred_day']-intro['assigned_day']<=30 and len(ss)==2 and all(e['value']=='yes' and e['occurred_day']-ds[0]['occurred_day']<=3 for e in ss)",
}


def main():
    t0 = time.time()
    s.log('ss5_mechanism start')
    kit_src = (s.ROOT / 'kit.py').read_text(encoding='utf-8-sig')
    verified, missing = {}, []
    for name, frag in FRAGMENTS.items():
        if frag in kit_src:
            line_no = kit_src[:kit_src.index(frag)].count('\n') + 1
            verified[name] = dict(line=line_no, fragment=frag)
        else:
            missing.append(name)
    if missing:
        raise SystemExit('kit.py fragments drifted, cannot describe: %s'
                         % missing)
    s.log('verified %d/kit.py equation fragments' % len(verified))

    md = []
    md.append('# Source-Mechanism Description (isolated; not a predictive model)\n')
    md.append('Every equation below is a SOURCE-CODE FACT read from `kit.py` '
              'and verified by `ss5_mechanism.py` against the current file. '
              'Hidden generator values (`response_rate`, `bias`, '
              '`second_bias`, `truth`, `shared`, date/delay randomness) are '
              'described here ONLY. They are banned from every feature matrix '
              '(BANNED_FEATURE_EXACT) and no variance-explained claim is '
              'made from these associations.\n')
    md.append('## The two acceptance-relevant logits\n')
    md.append('**Initial acceptance** (`_prob`, kit.py L%d-%d): '
              '`z = -0.25 + bias_a + fit + shared + drift`, '
              '`p = sigmoid(z)`. `fit = sum_k w_k * (1 if truth_a[k]==truth_b[k] '
              'else -0.5)` over the FOUR soft truths '
              '{relationship_goal, relationship_pace, lifestyle, '
              'conversations} with default weights {0.7, 0.4, 0.25, 0.2} '
              '(kit.py L%d). The `shift` variant swaps these to '
              '{0.25, 0.8, -0.25, 0.5} (L%d). `drift = -0.5` in `drift` '
              'variant from day 35 (L%d). `shared ~ N(0,0.45)` is pair-level '
              'randomness COMMON to both actors (L%d); `bias_a` is a hidden '
              'per-member attribute (L%d).\n'
              % (verified['accept_logit']['line'],
                 verified['accept_logit']['line'],
                 verified['accept_weights_default']['line'],
                 verified['accept_weights_shift']['line'],
                 verified['drift']['line'],
                 verified['shared_randomness']['line'],
                 verified['accept_logit']['line']))
    md.append('**Second-meeting intention** (kit.py L%d): '
              '`p = sigmoid(0.15 + second_bias_a + shared + '
              '0.4 * [truth_a[relationship_goal]==truth_b[relationship_goal]])`. '
              'Note: relationship-goal agreement enters BOTH logits (weight '
              '0.7 in `fit`, +0.4 here); the other three soft truths enter '
              'ONLY the initial-acceptance `fit`.\n'
              % verified['second_logit_goal_agreement']['line'])
    md.append('## Stage-by-stage dependence on hidden values\n')
    md.append('| Stage | Explicit hidden dependence | Legal observable correlate |')
    md.append('|---|---|---|')
    md.append('| T1 both_responded | `response_rate` only (L%d) | none (response is independent of truths) |'
              % verified['responded_uses_response_rate']['line'])
    md.append('| T2 mutual | `response_rate`, `bias`, 4 soft `truth` (fit), `shared`, `drift` | the 7 soft channels (observed match/mismatch/unknown) partially reveal the 4 truths |')
    md.append('| T3 date | T2 + date randomness `p=0.78` (L%d) + timing `U(1,14)` (L%d) | none beyond T2 |'
              % (verified['date_happened_prob']['line'],
                 verified['date_day']['line']))
    md.append('| T4 date_within_deadline | T3 + timing; `delayed` variant adds `U(5,12)` days (L%d) | `variant` is legal at decision time |'
              % verified['date_delayed_extra']['line'])
    md.append('| T5 timely_second | `response_rate`, `second_bias`, `shared`, goal-agreement `+0.4`, delay `U(1,5)` with on-time `<=3` (L%d) | relationship-goal channel (observed) is the only legal correlate of the `+0.4` term |'
              % verified['second_yes_and_on_time']['line'])
    md.append('| T6 final_msmi | T4 AND T5 (official def, L%d) | inherits T4+T5 observables |'
              % verified['msmi_official']['line'])
    md.append('## What this predicts about the observed funnel (and how to read it)\n')
    md.append('- The T1 null (no observable signal; measured AUC 0.496, CI '
              'includes 0.5) is EXACTLY what the mechanism predicts: T1 '
              'depends only on hidden `response_rate`, which generation '
              'draws independently of every observable field.')
    md.append('- The relationship-goal association should APPEAR at T2 (it '
              'enters `fit` at weight 0.7) and PERSIST to T5/T6 (the +0.4 '
              'second logit). The measured funnel matches: goal match-vs-'
              'mismatch CI excludes 0 at T2, T3, T4, T5, T6 but not T1.')
    md.append('- `lifestyle`/`pace`/`conversations` enter `fit` but NOT the '
              'second logit, so their association should fade at T5/T6; '
              'measured: pace/conversations show T2-T4 association, but only '
              'goal (and marginally conversations) persist to T5/T6.')
    md.append('- T4 is nearly free (only 8 deadline misses, all `delayed`): '
              'the 30-day deadline rarely binds because `date_day` is usually '
              'well inside 30 days except under the `delayed` +U(5,12).')
    md.append('- T5 is the dominant collapse (1689 dates -> 174 timely-'
              'second): it compounds hidden `response_rate`, `second_bias`, '
              '`shared`, AND a pure-timing coin (`delay<=3`). The timing '
              'component is NOT predictable from any observable, which caps '
              'T5/T6 achievable AUC.')
    md.append('\n## Honesty notes\n')
    md.append('- These are mechanism facts, not measurements of real human '
              'behaviour; the simulator is synthetic and invented.')
    md.append('- Association of an observable channel with a stage does NOT '
              'mean the channel causes the outcome; the channel only '
              'partially reveals a hidden truth that the equation uses.')
    md.append('- No hidden value is used as a predictor anywhere in this '
              'study; this file is a description kept deliberately separate '
              'from the predictive analysis.')
    (s.OUT / 'mechanism_notes.md').write_text('\n'.join(md) + '\n',
                                              encoding='utf-8')
    s.log('wrote mechanism_notes.md (%d fragments verified)' % len(verified))
    s.log('ss5_mechanism done (%.1fs)' % (time.time() - t0))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
