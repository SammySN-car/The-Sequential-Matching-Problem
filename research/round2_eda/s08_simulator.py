"""S08: generator-side outcome-model source facts (DIAGNOSTIC ONLY).

Extracts the structural outcome equations from kit.py (lines cited) and
computes prior-sampling quantiles of each funnel multiplier. These are
generator internals, NOT observable to any policy; they explain empirical
funnel rates and AUC ceilings but cannot be used for policy design or
causal claims about the simulated world.
"""
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root for kit
from eda_common import TABLES, log, write_csv  # noqa: E402
import kit  # noqa: E402


def sigmoid(z):
    return 1.0 / (1.0 + math.exp(-z))


def main():
    log('S08 generator source facts start')

    weights = {'relationship_goal': .7, 'relationship_pace': .4,
               'lifestyle': .25, 'conversations': .2}
    shift_w = {'relationship_goal': .25, 'relationship_pace': .8,
               'lifestyle': -.25, 'conversations': .5}

    facts = [
        {'fact': 'acceptance_inputs', 'value': 'sigmoid(-0.25 + bias + fit + shared + drift)',
         'source': 'kit.py L133-140 (_prob)'},
        {'fact': 'fit_weights_default', 'value': str(weights), 'source': 'kit.py L135'},
        {'fact': 'fit_weights_shift', 'value': str(shift_w), 'source': 'kit.py L136'},
        {'fact': 'fit_match_value', 'value': '+1 equal, -0.5 unequal', 'source': 'kit.py L137'},
        {'fact': 'shared_shock', 'value': 'N(0, 0.45), pair-level, used by BOTH acceptance and second intention',
         'source': 'kit.py L157, L139, L179'},
        {'fact': 'member_bias', 'value': 'N(0, 0.7), per member, hidden', 'source': 'kit.py L64, L139'},
        {'fact': 'second_bias', 'value': 'N(0, 0.5), per member, hidden', 'source': 'kit.py L65, L179'},
        {'fact': 'response_rate', 'value': 'U(0.55, 0.98), per member, hidden; gates response AND second answer',
         'source': 'kit.py L64, L159, L178'},
        {'fact': 'drift_effect', 'value': '-0.5 on acceptance logit when variant=drift and day>=35',
         'source': 'kit.py L138'},
        {'fact': 'date_probability', 'value': 'Bernoulli(0.78), constant, independent of fit',
         'source': 'kit.py L171'},
        {'fact': 'date_delay', 'value': 'max(response_days) + U(1..14); delayed variant +U(5..12)',
         'source': 'kit.py L169-170'},
        {'fact': 'second_yes_probability',
         'value': 'sigmoid(0.15 + second_bias + shared + 0.4*[goal match])', 'source': 'kit.py L179'},
        {'fact': 'second_on_time_probability', 'value': 'P(U(1..5) delay <= 3) = 3/5 per member',
         'source': 'kit.py L178, L180'},
        {'fact': 'msmi_deadline', 'value': 'date_day - assigned_day <= 30 AND both seconds yes <=3d',
         'source': 'kit.py L197'},
        {'fact': 'hard_fields_outcome_effect', 'value': 'ZERO - hard fields are feasibility-only (eligibility)',
         'source': 'kit.py L69-88 vs L133-140'},
        {'fact': 'soft_declined_truth_visibility', 'value': 'asks reveal truth only if field_status != declined',
         'source': 'kit.py L125-128'},
        {'fact': 'declined_is_fixed_at_generation', 'value': '7% of unobserved fields marked declined at generate()',
         'source': 'kit.py L57'},
        {'fact': 'age_zone_gender_outcome_effect', 'value': 'ZERO - feasibility/features only, never in _prob',
         'source': 'kit.py L41-43, L74-86 vs L133-140'},
        {'fact': 'history_wait_competition_outcome_effect',
         'value': 'ZERO - allocation-side only; conversion equations have no state terms',
         'source': 'kit.py L133-189'},
    ]
    write_csv(TABLES / 'generator_source_facts.csv', facts)

    # ---- prior-sampling quantiles of each funnel multiplier ----
    # (independent draw from the published generator priors; NOT world rollouts)
    r = random.Random(4242)
    n = 200_000
    both_resp, p_acc, p_sec, p_sec_on_time = [], [], [], []
    # only 4 of the 7 soft fields enter _prob (kit.py L135-136)
    fit_fields = ['relationship_goal', 'relationship_pace', 'lifestyle', 'conversations']
    p_goal_eq = 1.0 / len(kit.OPTIONS['relationship_goal'])
    for _ in range(n):
        ra, rb = r.uniform(.55, .98), r.uniform(.55, .98)
        both_resp.append(1.0 if (r.random() < ra and r.random() < rb) else 0.0)
        bias_a = r.gauss(0, .7)
        shared = r.gauss(0, .45)
        fit = 0.0
        for k in fit_fields:
            same = r.choice(kit.OPTIONS[k]) == r.choice(kit.OPTIONS[k])
            fit += weights[k] * (1 if same else -.5)
        p_acc.append(sigmoid(-.25 + bias_a + fit + shared))
        sb_a = r.gauss(0, .5)
        goal_match = 1 if r.random() < p_goal_eq else 0
        p_sec.append(sigmoid(.15 + sb_a + shared + .4 * goal_match))
        p_sec_on_time.append(ra * (3.0 / 5.0) * sigmoid(.15 + sb_a + shared + .4 * goal_match))

    def q(xs, p):
        s = sorted(xs)
        return s[int(p * (len(s) - 1))]

    sims = [
        {'multiplier': 'P(both respond)', 'mean': round(sum(both_resp) / n, 4),
         'p10': '', 'p50': '', 'p90': '',
         'note': 'empirical funnel n01: 0.562 (matches E[R]^2 = 0.585 prior)'},
        {'multiplier': 'P(accept | actor A)', 'mean': round(sum(p_acc) / n, 4),
         'p10': round(q(p_acc, .10), 4), 'p50': round(q(p_acc, .50), 4),
         'p90': round(q(p_acc, .90), 4),
         'note': 'shared+bias+fit; empirical mutual/responded n01: 0.270 (two-actor product)'},
        {'multiplier': 'P(date | both accept)', 'mean': 0.78, 'p10': '', 'p50': '', 'p90': '',
         'note': 'constant 0.78; empirical date/mutual n01: 0.754, scale800: 0.777'},
        {'multiplier': 'P(second yes on time | actor A, responded)', 'mean': round(sum(p_sec_on_time) / n, 4),
         'p10': round(q(p_sec_on_time, .10), 4), 'p50': round(q(p_sec_on_time, .50), 4),
         'p90': round(q(p_sec_on_time, .90), 4),
         'note': 'response_rate*3/5*p_yes; empirical sqrt(0.094)~0.31/actor consistent'},
        {'multiplier': 'P(date <= 30d | date)', 'mean': 0.989, 'p10': '', 'p50': '', 'p90': '',
         'note': 'empirical msmi/second n01: 0.989 (deadline rarely binds)'},
    ]
    write_csv(TABLES / 'generator_prior_multipliers.csv', sims)

    # latent-vs-observable map
    lat = [
        {'variable': 'member bias', 'hidden': 'yes', 'observable_via_asks': 'no',
         'affects': 'acceptance logit'},
        {'variable': 'second_bias', 'hidden': 'yes', 'observable_via_asks': 'no',
         'affects': 'second intention logit'},
        {'variable': 'response_rate', 'hidden': 'yes', 'observable_via_asks': 'no',
         'affects': 'response gates + second answer gate'},
        {'variable': 'pair shared shock', 'hidden': 'yes', 'observable_via_asks': 'no',
         'affects': 'acceptance AND second intention (correlates the two stages)'},
        {'variable': 'soft truth fields (4 REL)', 'hidden': 'partial',
         'observable_via_asks': 'yes iff field_status != declined (S02: ~34% members have >=1 declined hard; soft declines also exist)',
         'affects': 'fit (acceptance) + goal match (second)'},
        {'variable': 'hard fields', 'hidden': 'partial', 'observable_via_asks': 'yes iff not declined',
         'affects': 'feasibility ONLY'},
        {'variable': 'variant drift/shift/cold_start', 'hidden': 'no (variant is public)',
         'observable_via_asks': 'n/a', 'affects': 'weights (shift), -0.5 drift logit, lower cold-start soft coverage'},
    ]
    write_csv(TABLES / 'generator_latent_map.csv', lat)

    log('S08 done - generator facts extracted; prior multipliers diagnostic-only')


if __name__ == '__main__':
    main()
