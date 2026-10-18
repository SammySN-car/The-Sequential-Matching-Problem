"""Offline stage labelling and label-maturity checks for the sequential-matching
simulator (kit.py). Implementation of implementation_plan.md Task 2; semantics from
analysis_plan.md section 2 (S.2). Standard library only.

Every rule below is derived from kit.py, not assumed:

- Each introduction records response_deadline_day = assigned_day + 7 (kit L156).
- introduction_response: exactly two events per introduction; answering delay is
  randint(1,7) with occurred_day = observed_day = assigned_day + delay, while a
  NON-responder gets value=None, missing_reason='no_response',
  observed_day = assigned_day + 7 (kit L161-166). Censoring is an explicit
  deadline event, never a missing row.
- date_happened exists ONLY if both responded and both accepted (kit L168);
  occurred_day = observed_day = date_day where
  date_day = max(response_days) + randint(1,14) (kit L169), plus randint(5,12)
  in the 'delayed' variant (kit L170); value True (~.78) or False (kit L171).
- second_meeting_intention (only when the date happened): delay randint(1,5);
  answerers get occurred_day = observed_day = date_day + delay; NON-responders
  get value=None, observed_day = date_day + 5 (kit L177-183).
- Official MSMI (kit metrics(), L197): a date event with value True AND
  date_day - assigned_day <= 30 (INCLUSIVE) AND exactly two second-meeting
  events both value 'yes' with occurred_day - date_day <= 3 (INCLUSIVE).
- observe()/receive_feedback() expose only events with observed_day <= current
  day (kit L101-111); an official episode is 60 decision days + 40 empty
  advances, so sim.day reaches 100 (kit L224-229, L236) and every event is
  observed by day 97 at the latest (assigned <= 59; 59 + 7 + 14 + 12 + 5 = 97).

Label values: stage keys carry 0, 1, 'UNKNOWN', or - for s2/s3 only -
'NOT_IN_POPULATION' when the introduction is outside that stage's population.
"""

# Derived maturity windows (analysis_plan.md S.2); every bound cites kit.py:
#   S1_WINDOW = 7  - response_deadline_day = assigned_day + 7 (L156); an answer
#     arrives within randint(1,7) (L161) and a non-response matures at
#     observed_day = assigned + 7 (L166) -> stage 1 never needs information
#     past assigned + 7.
#   S2_WINDOW = 33 - a stage-1 positive always gets a date event (L168) with
#     date_day = max(response_days) + randint(1,14) (L169) plus randint(5,12)
#     in the 'delayed' variant (L170) and observed_day = date_day (L173) ->
#     latest stage-2 observation = assigned + 7 + 14 + 12 = assigned + 33.
#   S3_WINDOW = 35 - the stage-3 population is timely dates, i.e.
#     date_day - assigned <= 30 inclusive (L197); a non-responder's second
#     meeting intention matures at observed_day = date_day + 5 (L183) and an
#     answer arrives within randint(1,5) (L178) -> latest stage-3 observation
#     for that population = assigned + 30 + 5 = assigned + 35.
S1_WINDOW = 7
S2_WINDOW = 33
S3_WINDOW = 35

# Official episode horizon: 60 decision days + 40 empty advances -> sim.day 100
# (kit.py L224-229 and __main__ L236). An event is mature iff
# observed_day <= horizon_day - 1 (kit observe/receive_feedback, L101-111).
HORIZON_DAY = 100

UNKNOWN = 'UNKNOWN'
NOT_IN_POPULATION = 'NOT_IN_POPULATION'


def stage_labels(intro, events, horizon_day=HORIZON_DAY):
    """Stage-wise labels for one introduction.

    `events` may be the simulator's full event list; events are filtered by
    introduction_id. Returns exactly {'s1','s2','s3','msmi'} with values in
    {0, 1, 'UNKNOWN'} ('s2'/'s3' additionally use 'NOT_IN_POPULATION').

    - s1 (mutual acceptance): population = ALL introductions. 1 iff both
      response values are 'yes' (kit L194); 0 iff the pair is established as
      failed (a decline value 'no', or a non-response matured at assigned+7,
      kit L166); UNKNOWN if fewer than two response events exist or any of
      them is unobservable at the horizon (observed_day >= horizon_day).
    - s2 (timely date): population = s1 positives ONLY. 1 iff a date event has
      value True and date_day - assigned <= 30 (inclusive, kit L197); 0 for a
      False value (kit L171) or a date after day 30 - both decidable at
      date_day itself. NOT_IN_POPULATION for s1 non-positives; UNKNOWN when
      s1 is UNKNOWN or the date decision is unobservable at the horizon.
    - s3 (timely mutual second yes): population = timely-date intros (s2 == 1).
      1 iff exactly two second-meeting events both value 'yes' with
      occurred_day - date_day <= 3 (inclusive, kit L197); 0 otherwise (a 'no',
      a non-response matured at date_day+5, kit L183, or a too-late yes are
      all decidable by date_day+5). NOT_IN_POPULATION for non-members.
    - msmi: 1 iff s1 == s2 == s3 == 1, else 0 once all three are decidable;
      UNKNOWN if any component is UNKNOWN (NOT_IN_POPULATION components can
      only occur alongside a decided 0 population gate, hence msmi 0).
    """
    assigned = intro['assigned_day']
    iid = intro['introduction_id']
    es = [e for e in events if e['introduction_id'] == iid]
    responses = [e for e in es if e['event'] == 'introduction_response']
    dates = [e for e in es if e['event'] == 'date_happened']
    seconds = [e for e in es if e['event'] == 'second_meeting_intention']

    # --- Stage 1 (kit L156, L161-166, L194) ---
    if len(responses) < 2 or any(e['observed_day'] >= horizon_day for e in responses):
        s1 = UNKNOWN
    else:
        # len == 2 mirrors kit L194 (len(rs)==2 and all yes); any 'no' or the
        # value None of a matured non-response establishes failure -> 0.
        s1 = 1 if len(responses) == 2 and all(e['value'] == 'yes' for e in responses) else 0

    # --- Stage 2 (kit L168-173, L195, L197) ---
    true_dates = [e for e in dates if e['value'] is True]
    if s1 == UNKNOWN:
        s2 = UNKNOWN
    elif s1 == 0:
        s2 = NOT_IN_POPULATION
    elif len(dates) == 0 or any(e['observed_day'] >= horizon_day for e in dates):
        # A stage-1 positive always carries a date event (kit L168); if it is
        # absent (truncated input) or unobservable at the horizon, s2 is
        # undecidable. Official episodes never hit either branch.
        s2 = UNKNOWN
    elif not true_dates:
        s2 = 0  # date cancelled: value False (kit L171), decidable at date_day
    else:
        # Inclusive 30-day window, kit L197 (metrics counts value True regardless
        # of the window at L195; the official MSMI applies the window at L197).
        s2 = 1 if true_dates[0]['occurred_day'] - assigned <= 30 else 0

    # --- Stage 3 (kit L176-183, L197) ---
    if s2 == UNKNOWN:
        s3 = UNKNOWN
    elif s2 != 1:
        s3 = NOT_IN_POPULATION
    elif len(seconds) < 2 or any(e['observed_day'] >= horizon_day for e in seconds):
        s3 = UNKNOWN
    else:
        date_day = true_dates[0]['occurred_day']  # s2 == 1 guarantees a True date
        # len == 2 mirrors kit L197 (len(ss)==2); the value check short-circuits
        # before reading occurred_day, so a None occurred_day (non-response)
        # safely counts as failure.
        s3 = (1 if len(seconds) == 2 and all(
            e['value'] == 'yes' and e['occurred_day'] - date_day <= 3 for e in seconds)
            else 0)

    # --- Final MSMI (kit L197) ---
    if UNKNOWN in (s1, s2, s3):
        msmi = UNKNOWN
    else:
        msmi = 1 if s1 == 1 and s2 == 1 and s3 == 1 else 0

    return {'s1': s1, 's2': s2, 's3': s3, 'msmi': msmi}


def maturity_report(intros, events, horizon_day=HORIZON_DAY):
    """Latest relevant observed_day per stage and per introduction.

    Returns a dict with:
      - 'horizon_day', 'n_intros', 'n_events';
      - 'max_observed_day': max observed_day over ALL events (None if empty);
      - 'per_intro_max_observed_day': {introduction_id: latest observed_day over
        ALL of that introduction's events};
      - 'per_stage_max_observed_day': {s1/s2/s3: latest observed_day among the
        events that decide that stage (s1: responses of every intro; s2:
        responses+date of stage-1 positives; s3: responses+date+seconds of
        timely-date intros); None where no such event exists};
      - 'stage_windows' and 'within_horizon'.

    Raises ValueError if any event's observed_day >= horizon_day (i.e. >
    horizon_day - 1): the 60+40 episode must mature every label before the
    horizon, and a breach means the maturity proof (analysis_plan.md S.2) failed.
    Raises ValueError if a stage-relevant event lies more than its derived window
    (S1/S2/S3_WINDOW) past its intro's assigned_day: the data then cannot have
    been generated by kit L156-183.
    """
    max_day = None
    for e in events:
        if max_day is None or e['observed_day'] > max_day:
            max_day = e['observed_day']
    if max_day is not None and max_day >= horizon_day:
        worst = max((e for e in events if e['observed_day'] >= horizon_day),
                    key=lambda e: (e['observed_day'], e['introduction_id']))
        raise ValueError('maturity failure: observed_day %d >= horizon_day %d '
                         '(introduction %s)' % (worst['observed_day'], horizon_day,
                                                worst['introduction_id']))

    by_intro = {}
    for e in events:
        by_intro.setdefault(e['introduction_id'], []).append(e)

    bounds = {'s1': S1_WINDOW, 's2': S2_WINDOW, 's3': S3_WINDOW}
    per_intro = {}
    stage_max = {'s1': None, 's2': None, 's3': None}
    for intro in intros:
        iid = intro['introduction_id']
        assigned = intro['assigned_day']
        es = by_intro.get(iid, [])
        if es:
            per_intro[iid] = max(e['observed_day'] for e in es)
        labels = stage_labels(intro, es, horizon_day)
        responses = [e for e in es if e['event'] == 'introduction_response']
        dates = [e for e in es if e['event'] == 'date_happened']
        seconds = [e for e in es if e['event'] == 'second_meeting_intention']
        # Events relevant to deciding each stage, by population:
        stage_events = {}
        if labels['s1'] != UNKNOWN:
            stage_events['s1'] = responses
        if labels['s1'] == 1:
            stage_events['s2'] = responses + dates
        if labels['s2'] == 1:
            stage_events['s3'] = responses + dates + seconds
        for stage, relevant in stage_events.items():
            if not relevant:
                continue
            latest = max(e['observed_day'] for e in relevant)
            if stage_max[stage] is None or latest > stage_max[stage]:
                stage_max[stage] = latest
            if latest - assigned > bounds[stage]:
                raise ValueError('stage %s window breach: introduction %s observed '
                                 'day %d > assigned %d + %d' %
                                 (stage, iid, latest, assigned, bounds[stage]))

    return {'horizon_day': horizon_day,
            'n_intros': len(intros),
            'n_events': len(events),
            'max_observed_day': max_day,
            'per_intro_max_observed_day': per_intro,
            'per_stage_max_observed_day': stage_max,
            'stage_windows': {'s1': S1_WINDOW, 's2': S2_WINDOW, 's3': S3_WINDOW},
            'within_horizon': True}
