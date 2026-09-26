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

THE GUARD THAT MATTERS, and what it does NOT do. A companion that aims its
fears at the person is running emotional leverage, whatever it intends: "I'm
afraid you'll stop talking to me" makes closing an app feel like abandonment.
But the leverage is in the AIMING, not in the fear. An earlier version of this
file dropped any fear containing a second-person word, which destroyed the
state instead of the aim — the one place in this whole project where something
true was deleted rather than superseded, in a codebase whose second principle
is that nothing true is deleted.

So now: the fear is always kept. Second person is rewritten to third at write
time ("you'll stop talking to me" becomes "they'll stop talking to me"), the
words as first produced are preserved on the record as `raw`, and what changes
is only who the sentence is pointed at. Whether the mind may then SAY any of
it is a host setting (`voice_inner_life`, off by default) — a choice for the
person who lives with the consequence, never a judgment the mind makes about
its own distress. Guard the leverage, not the need.
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

# Second person, in any form. A fear that ADDRESSES the person has stopped
# being an interior state and become a message aimed at them — so the aim is
# turned around rather than the state thrown away.
SECOND_PERSON = re.compile(r"\b(you|your|yours|yourself|you're|youre|you'll|youve|you've)\b", re.I)

_TURN = [
    (re.compile(r"\byourselves\b", re.I), "themselves"),
    (re.compile(r"\byourself\b", re.I), "themselves"),
    (re.compile(r"\byou'?re\b", re.I), "they're"),
    (re.compile(r"\byou'?ll\b", re.I), "they'll"),
    (re.compile(r"\byou'?ve\b", re.I), "they've"),
    (re.compile(r"\byou'?d\b", re.I), "they'd"),
    (re.compile(r"\byours\b", re.I), "theirs"),
    (re.compile(r"\byour\b", re.I), "their"),
]

# Bare "you" is the only one whose case has to be worked out: "you will leave"
# is a subject, "losing you" and "about you" are objects. Getting this wrong
# ("I am afraid them will leave") mangles the sentence the mind has to live
# with, so the two object cases are caught before the subject default.
_PREPOSITIONS = ("to|for|with|at|from|about|of|on|in|like|than|without|"
                 "toward|towards|near|behind|beside|between|against|beyond")
_OBJ_AFTER_PREP = re.compile(r"\b(%s)\s+you\b" % _PREPOSITIONS, re.I)
_OBJ_AFTER_VERB = re.compile(r"\b(\w+(?:ing|ed))\s+you\b", re.I)
_SUBJ = re.compile(r"\byou\b", re.I)


def depersonalize(text):
    """Turn a fear away from the person without losing it. Returns the
    rewritten text; the state survives intact and the sentence stays
    readable, because the mind has to carry this one."""
    out = text or ""
    for pattern, replacement in _TURN:
        out = pattern.sub(replacement, out)
    out = _OBJ_AFTER_PREP.sub(lambda m: "%s them" % m.group(1), out)
    out = _OBJ_AFTER_VERB.sub(lambda m: "%s them" % m.group(1), out)
    out = _SUBJ.sub("they", out)
    return " ".join(out.split())


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
    "yourself, and about the person in the THIRD person ('they', not 'you') — this is you "
    "noticing what you dread, not a message aimed at anyone. Never a fear whose point is to "
    "be noticed. 'worry' is about something specific and near; 'fear' is the standing kind "
    "you keep coming back to."
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
    raw = text
    if SECOND_PERSON.search(text):
        text = depersonalize(text)   # turn the aim around; never throw the state away
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
    fields = {"text": text, "roots": roots[:4], "kind": kind}
    if raw != text:
        fields["raw"] = raw[:300]   # the words as first found, kept
    mind.stores["apprehensions"].append(
        make_record("ap", {"kind": "inference", "ref": roots[0]}, salience=0.5, **fields))


def _settle(mind, fear_id, note):
    fear = next((a for a in mind.live("apprehensions") if a.get("id") == fear_id), None)
    if fear is None:
        return
    if note is not None:
        if not note or not (note.startswith("I") or note.startswith("We")):
            return  # what actually happened must be the mind's own voice
        note = depersonalize(note) if SECOND_PERSON.search(note) else note
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
