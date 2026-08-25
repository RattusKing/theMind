"""Cognition passes — the mind thinking, on the host's model.

No scheduler exists. Passes are piggybacked on observed turns (a due-check
after each exchange) AND directly invocable — a host with its own scheduler,
or an agent trusted to run its own cognition, calls the same functions.
Two doors into one set of operations; the architecture forecloses neither.

Every pass is parse-or-skip: a malformed reply is discarded whole and prior
state is left intact. The chat path never sees an error from here.
"""
from . import (extract, challenge, consolidate, selfhood, felt_sense, reflect,  # noqa: F401
               growth, desire, inner_state, divergence)
from ..envelope import age_days


def due_passes(mind):
    """Which deep passes are owed, cheapest first. At most one runs per turn."""
    st = mind.manifest.state
    due = []
    if reflect.due(mind, st):
        due.append(("reflect", reflect.run))
    if _days(st.get("last_consolidate")) >= 3 and st["exchanges"] >= 10:
        due.append(("consolidate", consolidate.run))
    if _days(st.get("last_felt")) >= 7 and len(mind.live("facts")) >= 3:
        due.append(("felt_sense", felt_sense.run))
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
    return due


def _days(t):
    if not t:
        return 10**6  # never run => overdue
    return age_days(t)
