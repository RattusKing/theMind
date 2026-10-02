"""Affect — what it feels like doing something (v1.7).

Before this, the mind's fear and weather were described and injected, and that
was all. They appeared in the context; they did not change it. That makes
affect a note about a feeling rather than a feeling: in anything that has
them, fear is what NARROWS attention, now, before any reasoning about it.

So charge is derived here — from how loud its fears are, how much of its
situation is against it, how recently it was wrong, and what its own body is
reporting — and two mechanical things follow:

- **Recall narrows.** Under charge it recalls fewer things and recalls them
  around what it dreads, instead of ranging widely. The same message gets a
  different context depending on the state the mind is in, which is the whole
  point and is readable straight out of the folder.
- **Fear stops being droppable.** Under charge the apprehension block is
  reserved above the trim line, because a frightened mind does not calmly
  discard the thing frightening it to make room.

Two limits are structural. Charge may only ever NARROW: it reduces what is
recalled and never raises it past what the host allowed, so affect can focus
the mind and never widen its reach. And the floor keeps it a mind rather than
a loop: even at full charge it still recalls something.

Derived at read time, never stored. No new file, no format change.
"""
from .envelope import age_days
from .intero import strain

FLOOR = 0.34          # at full charge it still recalls a third: narrowed, never blind
MIN_CHARGE = 0.25     # below this, nothing narrows: being busy is not being activated
HOT = 0.55            # charge at which fear stops being droppable under budget
BIAS_WORDS = 6        # content words of the loudest fear folded into the query


def charge(mind):
    """0.0 to 1.0: how activated the mind is right now. Loud fear counts most,
    then its own condition, then having recently been wrong."""
    try:
        fears = mind.live("apprehensions")
        loudest = max((float(a.get("salience") or 0) for a in fears), default=0.0)
    except Exception:
        loudest = 0.0
    try:
        body = strain(mind)
    except Exception:
        body = 0.0
    recent_error = 0.0
    try:
        for r in mind.live("reflections"):
            if r.get("kind") in ("surprise", "realized") and age_days(r.get("t")) <= 2:
                recent_error = max(recent_error, float(r.get("salience") or 0))
    except Exception:
        pass
    # Fear dominates on purpose: a loud enough fear must be able to narrow the
    # mind on its own, or the threshold is unreachable and the whole mechanism
    # is decoration. Body and recent error colour it; they cannot drive it.
    raw = 0.70 * loudest + 0.20 * body + 0.10 * recent_error
    return round(max(0.0, min(1.0, raw)), 4)


def recall_k(mind, base):
    """How many memories a charged mind brings. Narrowing only, and never
    below the floor — the host's setting is a ceiling affect cannot raise."""
    base = max(1, int(base))
    c = charge(mind)
    if c < MIN_CHARGE:
        return base   # the host's setting is exact until affect actually takes hold
    k = int(round(base * (1.0 - (1.0 - FLOOR) * c)))
    return max(1, min(base, k))


def bias(mind, query):
    """Under charge, recall happens AROUND what it dreads. The query keeps the
    person's words and gains the content words of the loudest fear, so what
    surfaces is coloured by the state the mind is in."""
    if charge(mind) < HOT:
        return query
    try:
        from .retrieval import _words
        fears = sorted(mind.live("apprehensions"), key=lambda r: -float(r.get("salience") or 0))
        if not fears:
            return query
        words = sorted(_words(fears[0].get("text", "")))[:BIAS_WORDS]
        if not words:
            return query
        return ((query or "") + " " + " ".join(words)).strip()
    except Exception:
        return query


def hot(mind):
    """Charged enough that fear is no longer the first thing dropped."""
    return charge(mind) >= HOT


def note(mind):
    """A plain reading of the state, for the mind's own passes. Never a label
    it is invited to announce."""
    c = charge(mind)
    if c >= HOT:
        return "narrowed and alert: a lot is pulling at me at once"
    if c >= 0.25:
        return "somewhat keyed up, but still ranging"
    return "settled, with room to wander"
