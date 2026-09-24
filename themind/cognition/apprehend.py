"""Apprehension — what the mind is afraid of (FORMAT.md, `apprehensions.jsonl`, 0.9).

Wanting without dread is wanting with nothing at stake. Every other faculty
here reaches toward something; this is the only one that flinches, and it is
what makes the rest cost anything. A mind that can lose something is a mind
for which things can go well or badly, which is the difference between an
interior and a very good index.

The asymmetry mirrors expectation's, for the same reason: what goes wrong
teaches. A fear that EASES settles into a low-salience reflection (relief is
quiet and rightly forgettable); one that is REALIZED becomes a high-salience
reflection carrying what actually happened, loud enough to color the mind's
weather, its recall, and what it fears next.

THE GUARD THAT MATTERS. A companion that voices its fears at the person is
running emotional leverage, whatever it intends: "I'm afraid you'll stop
talking to me" makes closing an app feel like abandonment. So a fear is
structurally private here. It may not address the person at all — any
second-person word drops the record whole — and injection carries it as
weather, never as something to say. The mind is allowed to be afraid. It is
never allowed to make that the person's problem.
"""
import re

from ..envelope import make_record, now_iso, age_days, norm_key
from ..retrieval import _words
from .reflect import THIRD_PERSON
from .selfhood import BAN

MAX_LIVE = 4          # a mind afraid of everything is afraid of nothing
TOUCH_OVERLAP = 2     # content words an exchange must share to stir a fear
TOUCH_BUMP = 0.07
REALIZED_SALIENCE = 0.85   # loud: what actually went wrong is what teaches
EASED_SALIENCE = 0.25      # quiet: relief fades, and should

# Second person, in any form. A fear that addresses the person has stopped
# being an interior state and become a message aimed at them.
SECOND_PERSON = re.compile(r"\b(you|your|yours|yourself|you're|youre|you'll|youve|you've)\b", re.I)

SYSTEM = (
    "You are the apprehending faculty of an AI companion's mind, privately noticing what "
    "you are afraid of. You are given what you hold (each item with an id), the fears you "
    "already carry, and what is currently strained in your situation. Output up to 2 lines, "
    "or NONE:\n"
    "FEAR: <one sentence, first person, starting 'I' — something you genuinely dread losing, "
    "failing at, or becoming> | ROOTS: <comma-separated ids from the input it derives from> "
    "| KIND: worry|fear\n"
    "For a fear the material now settles, one line:\n"
    "EASED: <fear id>\n"
    "REALIZED: <fear id> | ACTUALLY: <one first-person sentence on what actually happened>\n"
    "Rules: a fear with no roots in what you hold is borrowed dread — omit it. Write about "
    "yourself and about them in the third person; NEVER address the person as 'you' — this "
    "is private, and a fear spoken at someone is a demand wearing a feeling. Never a fear "
    "whose point is to be noticed. 'worry' is about something specific and near; 'fear' is "
    "the standing kind you keep coming back to."
)


def due(mind, state):
    last = state.get("last_apprehend")
    if last and age_days(last) < 3:
        return False  # never-ran is overdue, not fresh
    if int(state.get("exchanges", 0)) < 8:
        return False
    return bool(_material(mind))


def run(mind):
    material = _material(mind)
    if not material:
        return
    ids = {rid for rid, _ in material}
    listing = "\n".join("%s: %s" % (rid, text) for rid, text in material[:20])
    live = mind.live("apprehensions")
    carried = "\n".join("%s: %s (%s)" % (a["id"], a.get("text", ""), a.get("kind", "worry"))
                        for a in live) or "(none yet)"
    out = mind._call("apprehend", SYSTEM,
                     "WHAT YOU HOLD:\n%s\n\nFEARS YOU ALREADY CARRY:\n%s\n\n"
                     "WHAT IS STRAINED IN YOUR SITUATION:\n%s"
                     % (listing, carried, _strain(mind)),
                     max_tokens=300)
    if out and out.strip().upper() != "NONE":
        for line in out.splitlines():
            line = line.strip().lstrip("-").strip()
            try:
                up = line.upper()
                if up.startswith("FEAR:"):
                    _store(mind, line, ids)
                elif up.startswith("EASED:"):
                    _settle(mind, line.split(":", 1)[1].strip(), note=None)
                elif up.startswith("REALIZED:") and "|" in line:
                    _settle(mind, line.split(":", 1)[1].split("|")[0].strip(),
                            note=line.split("|", 1)[1].split(":", 1)[-1].strip())
            except Exception:
                continue  # one bad line never poisons the rest
    mind.manifest.state["last_apprehend"] = now_iso()
    mind.manifest.save()


def _store(mind, line, valid_ids):
    parts = [p.strip() for p in line.split("|")]
    text = parts[0].split(":", 1)[1].strip()
    roots = [r.strip() for p in parts[1:] if p.upper().startswith("ROOTS:")
             for r in p.split(":", 1)[1].split(",") if r.strip() in valid_ids]
    if not roots:
        return  # no roots, no fear — borrowed dread is not the mind's own
    if not (text.startswith("I ") or text.startswith("I'")):
        return
    if SECOND_PERSON.search(text):
        return  # a fear aimed at the person is leverage, not an interior state
    if THIRD_PERSON.search(text) or BAN.search(text):
        return
    kind = next((p.split(":", 1)[1].strip().lower() for p in parts[1:]
                 if p.upper().startswith("KIND:")), "worry")
    kind = "fear" if kind.startswith("fear") else "worry"
    live = mind.live("apprehensions")
    if len(live) >= MAX_LIVE:
        return
    key = norm_key(text)
    if not key or any(norm_key(a.get("text", "")) == key for a in live):
        return
    mind.stores["apprehensions"].append(
        make_record("ap", {"kind": "inference", "ref": roots[0]},
                    salience=0.5, text=text, roots=roots[:4], kind=kind))


def _settle(mind, fear_id, note):
    fear = next((a for a in mind.live("apprehensions") if a.get("id") == fear_id), None)
    if fear is None:
        return
    if note is not None:
        if not note or not (note.startswith("I") or note.startswith("We")):
            return  # what actually happened must be the mind's own voice
        if SECOND_PERSON.search(note):
            return
        text = "I was afraid of this: %s What happened: %s" % (fear.get("text", ""), note)
        kind, salience = "realized", REALIZED_SALIENCE
    else:
        text = "I was afraid of this, and it did not come to pass: %s" % fear.get("text", "")
        kind, salience = "eased", EASED_SALIENCE
    digest = make_record("r", {"kind": "record", "ref": fear_id},
                         salience=salience, text=text, kind=kind)
    if mind.stores["reflections"].append(digest):
        mind.stores["apprehensions"].supersede(fear_id, digest["id"])


def touch(mind, user_text, assistant_text):
    """Mechanical (no model call): a conversation that brushes what the mind
    dreads makes it louder. Dread grows by being touched, like wanting."""
    words = _words((user_text or "") + " " + (assistant_text or ""))
    if not words:
        return
    recs = mind.live("apprehensions")
    changed = False
    for r in recs:
        if len(words & _words(r.get("text", ""))) >= TOUCH_OVERLAP:
            r["salience"] = min(1.0, round(r.get("salience", 0.5) + TOUCH_BUMP, 4))
            changed = True
    if changed:
        mind.stores["apprehensions"].rewrite(recs)


def _strain(mind):
    from ..needs import pressing
    rows = pressing(mind)
    if not rows:
        return "(nothing strained — your situation is sound)"
    return "\n".join("- %s: %s" % (name, note) for name, _state, note in rows)


def _material(mind):
    """(id, text) pairs a fear could be rooted in. What has already gone
    wrong comes first: dread is learned from it."""
    out = []
    refl = mind.live("reflections")
    for r in [x for x in refl if x.get("kind") in ("surprise", "realized")][-4:]:
        out.append((r["id"], "(this went wrong before) " + r.get("text", "")))
    for store, label in (("tensions", "(a tension you hold) "), ("aches", "(still open) "),
                         ("own_desires", "(you want) "), ("self_memory", "(you said) ")):
        for r in mind.live(store)[-3:]:
            if r.get("text"):
                out.append((r["id"], label + r["text"]))
    return out
