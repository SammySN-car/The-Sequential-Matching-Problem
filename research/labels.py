"""Labels for introduced pairs: MSMI (mutual second meeting intention).

Contract:
- Only introduced pairs ever receive a label; an un-introduced pair has NO row.
- label_msmi() returns 1/0 when the introduction is mature at `horizon`, else None.
- None must never be coerced to 0 by callers (see integrity audit).

Maturity mirrors what kit.Simulator has actually made observable: every event for
an introduction is created when the introduction is advanced, so the introduction
is fully known once horizon >= max(observed_day) over its events.
"""
RESPONSE = 'introduction_response'
DATE = 'date_happened'
SECOND = 'second_meeting_intention'


def group_events(events):
    """{introduction_id: [event, ...]} over observed feedback events."""
    out = {}
    for e in events:
        out.setdefault(e['introduction_id'], []).append(e)
    return out


def maturity_day(events):
    """First day at which this introduction's outcome is fully known, else None."""
    days = [e['observed_day'] for e in events if e.get('observed_day') is not None]
    return max(days) if days else None


def mature(events, horizon):
    m = maturity_day(events)
    return m is not None and m <= horizon


def label_msmi(events, assigned_day, horizon):
    """1 / 0 once mature at `horizon`, else None. Mirrors kit.Simulator.metrics()."""
    m = maturity_day(events)
    if m is None or m > horizon:
        return None
    responses = [e for e in events if e['event'] == RESPONSE]
    if len(responses) != 2 or not all(e['value'] == 'yes' for e in responses):
        return 0
    dates = [e for e in events if e['event'] == DATE and e['value'] is True]
    if not dates:
        return 0
    date_day = dates[0]['occurred_day']
    if date_day - assigned_day > 30:
        return 0
    seconds = [e for e in events if e['event'] == SECOND]
    if len(seconds) != 2:
        return 0
    if not all(e['value'] == 'yes' and e['occurred_day'] - date_day <= 3 for e in seconds):
        return 0
    return 1


def label_mutual(events, assigned_day, horizon):
    """Both introduction responses 'yes' (stage target; same maturity rule)."""
    m = maturity_day(events)
    if m is None or m > horizon:
        return None
    responses = [e for e in events if e['event'] == RESPONSE]
    return 1 if len(responses) == 2 and all(e['value'] == 'yes' for e in responses) else 0


def label_date(events, assigned_day, horizon):
    """A date actually happened (stage target; same maturity rule)."""
    m = maturity_day(events)
    if m is None or m > horizon:
        return None
    return 1 if any(e['event'] == DATE and e['value'] is True for e in events) else 0