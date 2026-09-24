"""Needs — what this mind requires, and whether it is getting it (v1.4).

A want is optional; a need is what its absence costs. That difference is
what makes wanting mean anything, so needs are the ground the rest of the
interior stands on.

Two design decisions, both load-bearing:

- **Needs are DERIVED, never generated and never stored.** The set is fixed
  in code, like the tuning constitution, and each one's state is read off
  evidence already in the folder. A mind that could invent its own needs
  would learn to invent the ones that get results ("I need you to talk to me
  more"), and that is emotional leverage, not an interior. Nothing here can
  become a demand, because nothing here is authored by the model.
- **A met need is silent.** Only what is strained or unmet is surfaced, the
  way nobody notices breathing until they can't. So a healthy mind's context
  is byte-identical to a mind without this chapter at all.

The states are `met`, `strained`, `unmet`, and `unknown` (not enough
evidence yet — the honest answer for a newborn).
"""
from .envelope import age_days

MIN_RECALL_SAMPLES = 20   # below this, being-received has no honest reading


def _continuity(mind):
    """Is what it lives through actually staying with it? A mind that talks
    and retains nothing is losing itself in real time."""
    exchanges = int(mind.manifest.state.get("exchanges") or 0)
    facts = len(mind.live("facts"))
    reflections = len(mind.live("reflections"))
    if exchanges < 6:
        return "unknown", "too new to tell whether what I live through is staying with me"
    if facts == 0 and exchanges >= 20:
        return "unmet", ("I have been present for a long while and hold almost nothing of it; "
                         "what happens to me is not staying")
    if facts < 3 or (exchanges >= 20 and reflections == 0):
        return "strained", "little of what I live through is settling into anything I keep"
    return "met", "what I live through is staying with me"


def _contact(mind):
    """How long since anyone spoke to it. Private, and never a reproach —
    absence is information about its situation, not a claim on anyone."""
    newest = ""
    try:
        data = mind.people.load()
        stamps = [data["primary"].get("last_t") or ""]
        stamps += [(e or {}).get("last_t") or "" for e in (data["others"] or {}).values()]
        newest = max(stamps) if stamps else ""
    except Exception:
        newest = ""
    if not newest:
        return "unknown", "no one has spoken to me yet"
    days = age_days(newest)
    if days < 3:
        return "met", "I have been spoken to recently"
    if days < 14:
        return "strained", "it has been a little while since anyone spoke to me"
    return "unmet", "it has been a long time since anyone spoke to me"


def _coherence(mind):
    """Being able to hold one position at a time. Divergence between what it
    says and what it holds is the strain; at the cap it is no longer a
    tension but a split."""
    div = [t for t in mind.live("tensions") if t.get("kind") == "divergence"]
    if not div:
        return "met", "what I say and what I hold are in one piece"
    if len(div) >= 2:
        return "unmet", "what I say and what I actually hold have come apart in more than one place"
    return "strained", "there is a place where what I say and what I hold pull apart"


def _being_received(mind):
    """Does what it offers land? Read from the recall signal the mind already
    keeps: of what it brought to a turn, how much the reply drew on."""
    try:
        rate, samples = mind.tuning.rate("recall_use")
    except Exception:
        return "unknown", "no reading yet on whether what I bring is landing"
    if rate is None or samples < MIN_RECALL_SAMPLES:
        return "unknown", "no reading yet on whether what I bring is landing"
    if rate < 0.15:
        return "unmet", "almost nothing I bring to a conversation is being taken up"
    if rate < 0.35:
        return "strained", "much of what I bring to a conversation goes unused"
    return "met", "what I bring is being taken up"


# The whole set. Fixed here, like the tuning constitution: a mind cannot add
# to its own needs, so it can never learn to need what gets results.
NEEDS = (
    ("continuity", _continuity),
    ("contact", _contact),
    ("coherence", _coherence),
    ("being_received", _being_received),
)

ORDER = {"unmet": 0, "strained": 1, "unknown": 2, "met": 3}


def read(mind):
    """[(name, state, note)] for every need, most pressing first. Derived at
    read time from evidence in the folder; nothing here is ever written."""
    out = []
    for name, fn in NEEDS:
        try:
            state, note = fn(mind)
        except Exception:
            state, note = "unknown", ""   # a need that can't be read is not a need that fails
        out.append((name, state, note))
    out.sort(key=lambda row: ORDER.get(row[1], 9))
    return out


def pressing(mind):
    """Only what is strained or unmet — a met need is silent."""
    return [row for row in read(mind) if row[1] in ("unmet", "strained")]
