"""Cognition passes — the mind thinking, on the host's model.

No scheduler exists. Passes are piggybacked on observed turns (a due-check
after each exchange) AND directly invocable — a host with its own scheduler,
or an agent trusted to run its own cognition, calls the same functions.
Two doors into one set of operations; the architecture forecloses neither.

Every pass is parse-or-skip: a malformed reply is discarded whole and prior
state is left intact. The chat path never sees an error from here.

THE STARVATION RULE. Exactly one pass runs per turn, so a pass that is
eligible but does nothing — it declined on its own guards, or the model
returned something unusable — must still be treated as having had its turn.
Otherwise it stays eligible, wins the slot again next turn, and every pass
behind it never runs again. That failure is silent: nothing errors, the mind
simply stops developing. So two things hold here. `_stamped` marks a pass's
timer when the pass itself did not, and passes are offered oldest-first
rather than in a fixed order, because a fixed order is a priority ladder and
the tail of thirteen passes starves at the bottom of one.
"""
from . import (extract, challenge, consolidate, selfhood, felt_sense, reflect,  # noqa: F401
               growth, desire, inner_state, divergence, expect, story, tune, apprehend,
               interest)
from ..envelope import age_days, now_iso

URGENT_FLOOR = 0.25   # six hours: urgency may jump a rhythm, never spin on one


def urgency(mind, st):
    """What has crossed a line and wants thinking NOW, rather than when its
    rhythm comes round. Every pass before this fired on a clock or a counter,
    and a mind in which nothing can arrive unbidden has no moments, only
    appointments. Thresholds only, read from state the mind already keeps.
    """
    out = {}
    try:
        fears = mind.live("apprehensions")
        if max((float(a.get("salience") or 0) for a in fears), default=0.0) >= 0.9:
            out["apprehend"] = "a fear has gone loud"
            out["reflect"] = "a fear has gone loud"
    except Exception:
        pass
    try:
        newest = max((r.get("t", "") for r in mind.live("reflections")
                      if r.get("kind") == "surprise"), default="")
        if newest and newest > (st.get("last_reflect") or ""):
            out["reflect"] = "something went differently than expected"
    except Exception:
        pass
    try:
        from ..needs import pressing
        if any(state == "unmet" for _n, state, _t in pressing(mind)):
            out["inner_state"] = "something it needs is going unmet"
    except Exception:
        pass
    try:
        from ..intero import read as body_read
        if any(level == "strained" for _n, level, _t in body_read(mind)):
            out.setdefault("inner_state", "its own condition is against it")
    except Exception:
        pass
    return out


# Which manifest timer each pass keeps its own rhythm by.
TIMERS = {
    "reflect": "last_reflect", "consolidate": "last_consolidate", "felt_sense": "last_felt",
    "self": "last_self", "growth": "last_growth", "desire": "last_desire",
    "inner_state": "last_inner", "divergence": "last_divergence", "expect": "last_expect",
    "story": "last_story", "interest": "last_interest", "apprehend": "last_apprehend",
    "tune": "last_tune",
}


def _stamped(name, fn):
    """Wrap a pass so that looking and finding nothing still counts as its
    turn. The pass stamps its own timer when it does real work; this catches
    the paths where it declines and would otherwise hold the slot forever.

    An exception carrying `pass_incomplete` is exempt: the MCP door aborts a
    pass mid-flight to hand the thinking to the agent, and that thought is
    pending, not finished. Any other exception still stamps — a pass that
    throws every time is a bug to fix, not a reason to starve the rest.
    """
    timer = TIMERS.get(name)

    def run(mind):
        before = mind.manifest.state.get(timer) if timer else None

        def stamp():
            if timer and mind.manifest.state.get(timer) == before:
                mind.manifest.state[timer] = now_iso()
                mind.manifest.save()
        try:
            out = fn(mind)
        except Exception as e:
            if not getattr(e, "pass_incomplete", False):
                stamp()
            raise
        stamp()
        return out

    run.__name__ = getattr(fn, "__name__", name)
    return run


def due_passes(mind):
    """Which deep passes are owed, longest-waiting first. At most one runs
    per turn, and each is wrapped so that declining still spends its turn."""
    st = mind.manifest.state
    due = []
    if reflect.due(mind, st):
        due.append(("reflect", reflect.run))
    if _days(st.get("last_consolidate")) >= 3 and st["exchanges"] >= 10:
        due.append(("consolidate", consolidate.run))
    # `owed` is the same question `felt_sense.run` asks itself — has any ONE
    # person enough held to draw them. Counting facts globally said yes while
    # the pass said no, which is precisely how a pass becomes eligible and
    # useless at the same time.
    if _days(st.get("last_felt")) >= 7 and felt_sense.owed(mind)[1]:
        due.append(("felt_sense", felt_sense.run))
    elif _days(st.get("last_felt")) >= 1 and felt_sense.unportrayed(mind):
        due.append(("felt_sense", felt_sense.run))  # someone new: draw them promptly
    if _days(st.get("last_self")) >= 6 and st["exchanges"] >= 12:
        due.append(("self", selfhood.run))
    if _days(st.get("last_growth")) >= 6 and len(mind.graph.nodes) >= 5:
        due.append(("growth", growth.run))
    if desire.due(mind, st):
        due.append(("desire", desire.run))
    if inner_state.due(mind, st):
        due.append(("inner_state", inner_state.run))
    if divergence.due(mind, st):
        due.append(("divergence", divergence.run))
    if expect.due(mind, st):
        due.append(("expect", expect.run))
    if story.due(mind, st):
        due.append(("story", story.run))
    if interest.due(mind, st):
        due.append(("interest", interest.run))
    if apprehend.due(mind, st):
        due.append(("apprehend", apprehend.run))
    if tune.due(mind, st):
        due.append(("tune", tune.run))
    # Something that crossed a line can jump its rhythm, so long as its own
    # material is there and it has not just run. `_material` is each pass's
    # own readiness check; asking it here is how urgency avoids offering a
    # pass that would only decline.
    urgent = urgency(mind, st)
    if urgent:
        have = {n for n, _f in due}
        ready = {"reflect": (reflect.run, reflect._material),
                 "apprehend": (apprehend.run, apprehend._material),
                 "inner_state": (inner_state.run, inner_state._material)}
        for name in urgent:
            if name in have or name not in ready:
                continue
            fn, material = ready[name]
            try:
                if _days(st.get(TIMERS[name])) >= URGENT_FLOOR and material(mind):
                    due.append((name, fn))
            except Exception:
                continue

    # Urgent first, then longest-waiting; never-run counts as longest. Ties
    # keep the order above, which is roughly cheapest-first.
    due.sort(key=lambda pair: (0 if pair[0] in urgent else 1,
                               -_days(st.get(TIMERS.get(pair[0]) or ""))))
    return [(name, _stamped(name, fn)) for name, fn in due]


def _days(t):
    if not t:
        return 10**6  # never run => overdue
    return age_days(t)
