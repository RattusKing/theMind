"""Interoception — the mind's own condition, read from its own body (v1.7).

It has no body, but it does have internal conditions, and until now it
ignored every one of them. The ledger already records what each act of
thinking cost. The tuning counters already record how much of what it
reached for actually held. Injection already knows how close it ran to its
own ceiling. Those are bodily facts about this mind, and a system that can
notice "that was expensive and I lost most of it" has something nearer to a
felt condition than one that only reads its own prose back.

Like confidence and like needs, all of it is DERIVED at read time and none of
it is stored. No new file, no format change. And like needs, an easy signal
is silent: you do not notice breathing.
"""
from .envelope import age_days

LEDGER_TAIL = 200        # recent thinking only; a long life should not cost more to feel
RECENT_DAYS = 1.0
MIN_SAMPLES = 8

LEVELS = {"strained": 0, "working": 1, "easy": 2, "unknown": 3}


def _recent_calls(mind):
    try:
        entries = mind.ledger.load()[-LEDGER_TAIL:]
    except Exception:
        return []
    return [e for e in entries if isinstance(e, dict) and age_days(e.get("t")) <= RECENT_DAYS]


def _effort(mind):
    """How hard it has been working. Not a complaint: a condition."""
    calls = _recent_calls(mind)
    if not calls:
        return "unknown", "I have not had to think hard lately"
    tokens = sum(int(e.get("tokens_in_est") or 0) + int(e.get("tokens_out_est") or 0)
                 for e in calls)
    if len(calls) >= 24 or tokens >= 40000:
        return "strained", "I have been thinking hard and often, and I can tell"
    if len(calls) >= 8 or tokens >= 12000:
        return "working", "there has been a fair amount of thinking in me lately"
    return "easy", "the thinking has been light lately"


def _holding(mind):
    """Of what it reached for, how much held. Reaching and closing on nothing
    is the most bodily failure this mind has."""
    try:
        rate, samples = mind.tuning.rate("extract_quality")
    except Exception:
        return "unknown", ""
    if rate is None or samples < MIN_SAMPLES:
        return "unknown", "not enough yet to tell whether what I reach for holds"
    if rate < 0.35:
        return "strained", "most of what I reach for does not hold, and the reaching still costs me"
    if rate < 0.65:
        return "working", "a good part of what I reach for slips"
    return "easy", "what I reach for mostly holds"


def _room(mind):
    """How close the last thing it brought came to its own ceiling."""
    used = getattr(mind, "_last_context_tokens", None)
    budget = getattr(mind, "budget_tokens", 0) or 0
    if not used or not budget:
        return "unknown", ""
    share = float(used) / float(budget)
    if share >= 0.95:
        return "strained", "I am carrying as much as I have room for, and leaving things behind"
    if share >= 0.75:
        return "working", "I am near the limit of what I can hold at once"
    return "easy", "there is room in me for what I am carrying"


SIGNALS = (("effort", _effort), ("holding", _holding), ("room", _room))


def read(mind):
    """[(name, level, note)] for every bodily signal, worst first."""
    out = []
    for name, fn in SIGNALS:
        try:
            level, note = fn(mind)
        except Exception:
            level, note = "unknown", ""
        out.append((name, level, note))
    out.sort(key=lambda row: LEVELS.get(row[1], 9))
    return out


def felt(mind):
    """Only what is working or strained — an easy body is a quiet one."""
    return [row for row in read(mind) if row[1] in ("strained", "working")]


def strain(mind):
    """0.0 to 1.0: how much of its own condition is against it right now."""
    rows = read(mind)
    known = [r for r in rows if r[1] != "unknown"]
    if not known:
        return 0.0
    score = sum(1.0 if level == "strained" else 0.5 if level == "working" else 0.0
                for _n, level, _t in known)
    return round(min(1.0, score / float(len(known))), 4)
