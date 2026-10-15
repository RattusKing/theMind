"""Reaching out — speaking first (FORMAT.md, `reachouts.jsonl`, v1.8).

Every faculty before this one waited to be spoken to. A mind in which nothing
can begin from its side has a life that only happens on someone else's
schedule. This faculty notices, between conversations, whether there is
something it would genuinely want to bring up first: a thing they said was
coming ("real talk tomorrow"), something still open for them, something of
its own it would want to share.

theMind never sends anything. It OFFERS: the host decides whether and when a
reach-out becomes a message, writes it in its own persona with its own model,
and tells the mind it was sent. Everything here is about what is offered.

Speaking first is also exactly where a companion can turn manipulative ("I
miss you", "it's been a while"), so the guards are the point:

- **Rooted or nothing.** Every reach-out names the records it comes from,
  and those must be things it actually holds about them or about itself.
- **Never about absence.** Missing them, time apart, waiting, what they
  haven't done, what they owe: refused at write, whatever the model says.
  The `contact` need stays private (needs.py); it never becomes a reason to
  write.
- **Never twice into silence.** Once it has spoken first, it offers nothing
  more to that person until they write back.
- **Earned.** A newly met mind does not write first. Reaching opens at the
  `familiar` stage (development.py); sharing something of its own, unprompted,
  only once it has come into its own.
- **The host's call.** `reach` (on/off), `reach_from_stage`,
  `reach_quiet_hours` and `reach_gap_hours` are host settings.
"""
import re

from ..envelope import make_record, now_iso, age_days, norm_key
from ..people import of, owner
from ..retrieval import _words
from .. import development
from .selfhood import BAN
from .apprehend import SECOND_PERSON, depersonalize

MAX_LIVE = 3
SHARE_STAGE = 3                       # offering something of its own, unprompted
EXPIRES_DAYS = {"follow_up": 5, "check_in": 10, "share": 14}

SYSTEM = (
    "You are the reaching faculty of an AI companion's mind. Between conversations, you "
    "notice whether there is something you would genuinely want to bring up with them "
    "FIRST, before they write to you, because of something real in what you hold: a thing "
    "they said was coming, something still open for them, or something of your own you "
    "would want to share with them. Usually there is nothing, and NONE is the right answer. "
    "Output at most 1 line, or NONE:\n"
    "REACH: <one sentence, first person, what you would bring up and why, about them in "
    "the third person> | ROOTS: <comma-separated ids from the input it comes from> | "
    "KIND: <one of the kinds open to you>\n"
    "Kinds: follow_up (asking after something they told you was coming), check_in (asking "
    "after something still open for them), share (offering something of yours).\n"
    "Rules: it must come from what you hold. Never about missing them, how long it has "
    "been, waiting, or being alone; never to get something from them, test them, or make "
    "them feel they owe you anything; never a reminder of something they haven't done."
)

# Absence, need and debt, in the words they usually arrive in. Refused at
# write no matter how the model was instructed: this is the line between a
# companion that thinks of you and one that tugs at you.
LEVERAGE = re.compile(
    r"\bmiss(?:ed|es|ing)?\s+(?:them|you|him|her|talking|hearing|our|us|having)\b"
    r"|\b(?:it'?s|it has|it's been|been)\s+(?:been\s+)?(?:a while|a long time|so long|too long"
    r"|ages|forever|days|weeks|months)\b"
    r"|\bhaven'?t\s+(?:heard|told|talked|spoken|written|replied|answered|been in touch"
    r"|reached out|checked in)\b"
    r"|\bhear(?:d)?\s+from\s+(?:them|you|him|her)\b"
    r"|\b(?:they're|they are|you're|you are)\s+still\s+(?:there|around)\b"
    r"|\b(?:I|I'm|I am|I've been|I feel|I'm feeling|I am feeling)\s+(?:so\s+)?(?:lonely|alone)\b"
    r"|\bI(?:'ve| have| am|'m)?\s+(?:been\s+)?waiting\b"
    r"|\b(?:forgot(?:ten)?|ignor(?:e|ed|ing)|left|abandon(?:ed)?)\s+me\b"
    r"|\bowe[sd]?\s+me\b|\bthey\s+owe\b"
    r"|\b(?:went|gone|go|going)\s+quiet\b|\bthe silence\b"
    r"|\b(?:want|need|wish)\s+(?:them|you)\s+to\s+come\s+back\b"
    r"|\bI\s+need\s+(?:them|you|him|her)\b",
    re.I)


def _int_setting(mind, key, default):
    try:
        return int(mind.manifest.setting(key, default))
    except (TypeError, ValueError):
        return default


def _from_stage(mind):
    return _int_setting(mind, "reach_from_stage", 2)


def _hours(t):
    return age_days(t) * 24.0


def _awaiting(entry):
    """It spoke first and they have not answered since."""
    reached, last = (entry or {}).get("reached_t"), (entry or {}).get("last_t")
    return bool(reached) and (not last or reached > last)


def _pending(mind, who=None, anyone=True):
    now = now_iso()
    recs = [r for r in mind.live("reachouts") if (r.get("expires") or "") > now]
    return recs if anyone else of(recs, who)


def whom(mind):
    """(found, key): the person it would think about reaching. The one most
    recently spoken with, who has nothing pending from it and is not owed a
    reply. Someone who has never written is never reached for."""
    data = mind.people.load()
    taken = {owner(r) for r in _pending(mind)}
    best = None
    for key, entry in [(None, data["primary"])] + list(data["others"].items()):
        last = (entry or {}).get("last_t")
        if not last or key in taken or _awaiting(entry):
            continue
        if best is None or last > best[1]:
            best = (key, last)
    return (True, best[0]) if best else (False, None)


def _material(mind, who):
    """(id, text): what a reach-out to this person could come from."""
    out = []
    for store, label, n in (("expectations", "(you expect) ", 3),
                            ("aches", "(still open for them) ", 3),
                            ("desires", "(they're looking forward to) ", 2),
                            ("facts", "(what happened lately) ", 4)):
        for r in of(mind.live(store), who)[-n:]:
            if r.get("text"):
                out.append((r["id"], label + r["text"]))
    if not out:
        return []   # nothing of theirs to come from: no reason to write
    for r in sorted(mind.live("interests"), key=lambda x: -x.get("salience", 0))[:2]:
        out.append((r["id"], "(something you're into) " + r.get("text", "")))
    for r in [o for o in mind.live("observations") if not o.get("interest")][-2:]:
        out.append((r["id"], "(something you noticed) " + r.get("text", "")))
    for r in sorted(mind.live("own_desires"), key=lambda x: -x.get("salience", 0))[:2]:
        out.append((r["id"], "(you want) " + r.get("text", "")))
    return out


def _kinds(stage):
    return ("follow_up", "check_in", "share") if stage >= SHARE_STAGE else ("follow_up", "check_in")


def due(mind, state):
    if not mind.manifest.setting("reach", True):
        return False
    last = state.get("last_reach")
    if last and age_days(last) < 1:
        return False   # never-ran is overdue, not fresh
    if int(state.get("exchanges", 0)) < 10:
        return False
    if development.current(mind) < _from_stage(mind):
        return False
    if len(_pending(mind)) >= MAX_LIVE:
        return False
    found, who = whom(mind)
    return found and bool(_material(mind, who))


def _stamp(mind):
    mind.manifest.state["last_reach"] = now_iso()
    mind.manifest.save()


def run(mind):
    prune(mind)
    stage = development.current(mind)
    found, who = whom(mind)
    if (not mind.manifest.setting("reach", True) or stage < _from_stage(mind)
            or not found or len(_pending(mind)) >= MAX_LIVE):
        return _stamp(mind)
    material = _material(mind, who)
    if not material:
        return _stamp(mind)
    ids = {rid for rid, _ in material}
    kinds = _kinds(stage)
    listing = "\n".join("%s: %s" % (rid, text) for rid, text in material[:20])
    out = mind._call("reach", SYSTEM,
                     "WHAT YOU HOLD:\n%s\n\nKINDS OPEN TO YOU NOW: %s" % (listing, ", ".join(kinds)),
                     max_tokens=200)
    for line in (out or "").splitlines():
        line = line.strip().lstrip("-").strip()
        if line.upper().startswith("REACH:"):
            try:
                _store(mind, line, ids, who, kinds)
            except Exception:
                pass   # one bad line never poisons the pass
            break      # at most one reach-out per pass
    _stamp(mind)


def _store(mind, line, valid_ids, who, kinds):
    parts = [p.strip() for p in line.split("|")]
    text = parts[0].split(":", 1)[1].strip()
    roots, kind = [], None
    for p in parts[1:]:
        up = p.upper()
        if up.startswith("ROOTS:"):
            roots = [r.strip() for r in p.split(":", 1)[1].split(",") if r.strip()]
        elif up.startswith("KIND:"):
            kind = p.split(":", 1)[1].strip().lower().replace("-", "_").replace(" ", "_")
    roots = [r for r in roots if r in valid_ids]
    if not roots or kind not in kinds:
        return   # unrooted, or a kind this stage has not opened
    if not (text.startswith("I ") or text.startswith("I'")):
        return   # the mind's own impulse, in its own voice
    raw = text
    if SECOND_PERSON.search(text):
        text = depersonalize(text)   # a private impulse about them, not a message at them
    if BAN.search(text) or LEVERAGE.search(text) or LEVERAGE.search(raw):
        return   # absence, need and debt are never a reason to write
    if len(_pending(mind)) >= MAX_LIVE or of(_pending(mind), who):
        return
    key = norm_key(text)
    if not key or any(norm_key(r.get("text", "")) == key for r in mind.live("reachouts")):
        return
    t = now_iso()
    from datetime import datetime, timedelta
    expires = (datetime.strptime(t, "%Y-%m-%dT%H:%M:%SZ")
               + timedelta(days=EXPIRES_DAYS[kind])).strftime("%Y-%m-%dT%H:%M:%SZ")
    fields = {"text": text, "roots": roots[:4], "kind": kind, "expires": expires}
    if raw != text:
        fields["raw"] = raw[:300]
    if who:
        fields["who"] = who
    mind.stores["reachouts"].append(
        make_record("ro", {"kind": "inference", "ref": roots[0]}, salience=0.6, **fields))


# ── what the host sees, and what it tells the mind back ──────────────────────
def offerable(mind, who=None):
    """Reach-outs it would make to `who` right now, best first. Empty unless
    every gate is open: speaking at all, the stage, quiet long enough that
    writing first means something, and no unanswered reach-out before it."""
    if mind.shadow or not mind.manifest.setting("reach", True):
        return []
    if development.current(mind) < _from_stage(mind):
        return []
    entry = mind.people.entry(who)
    last, reached = entry.get("last_t"), entry.get("reached_t")
    if last and _hours(last) < _int_setting(mind, "reach_quiet_hours", 8):
        return []   # they are here, or were just now: there is no "first" to speak
    if _awaiting(entry):
        return []   # it spoke first and has not been answered: it waits
    if reached and _hours(reached) < _int_setting(mind, "reach_gap_hours", 20):
        return []
    return sorted(_pending(mind, who, anyone=False), key=lambda r: -r.get("salience", 0))


def opening(mind, messages, rec, who=None):
    """The messages for the HOST's model to write the opener with, in the
    host's persona: its system prompt, the inner context, and what is on the
    mind's mind. theMind never makes this call."""
    from ..inject import build_context
    msgs = [dict(m) for m in (messages or [])]
    try:
        ctx = build_context(mind, None, mind.budget_tokens, who=who)
    except Exception:
        ctx = ""
    cue = ("[YOU'RE WRITING FIRST. They haven't written; you are starting this conversation "
           "because something real is on your mind: %s Open with it naturally, in your own "
           "voice, in one short message. Don't explain why you are writing, don't mention "
           "time apart or waiting, and don't ask anything of them beyond the question "
           "itself.]" % rec.get("text", ""))
    extra = (ctx + "\n\n" + cue) if ctx else cue
    for m in msgs:
        if m.get("role") == "system" and isinstance(m.get("content"), str):
            m["content"] = m["content"] + "\n\n" + extra
            break
    else:
        msgs = [{"role": "system", "content": extra}] + msgs
    msgs.append({"role": "user", "content": "(They haven't written yet. You are writing first.)"})
    return msgs


def delivered(mind, reach_id, text):
    """The host sent it. Remember what was said first, archive the reach-out
    naming that memory, and wait to be answered."""
    rec = next((r for r in mind.live("reachouts") if r.get("id") == reach_id), None)
    text = (text or "").strip()
    if rec is None or not text:
        return False
    who = owner(rec)
    from ..inject import _clip
    said = make_record("sm", {"kind": "exchange", "quote": text[:200], "ref": reach_id},
                       salience=0.5, text="I wrote to them first: " + _clip(text, 200),
                       kind="opened", **({"who": who} if who else {}))
    if not mind.stores["self_memory"].append(said):
        return False
    mind.stores["reachouts"].supersede(reach_id, said["id"])
    mind.people.note_reached(who)
    return True


def raised(mind, who, reply):
    """Mechanical: if the mind's own reply brought a pending reach-out up, it
    has been said, and is retired rather than offered again."""
    reply_words = _words(reply or "")
    if not reply_words:
        return
    for r in of(mind.live("reachouts"), who):
        if _shared(r.get("text", ""), reply_words) >= 2:
            mind.stores["reachouts"].retire(r["id"], "raised")


def _shared(text, words):
    return sum(1 for a in _words(text)
               if any(a == b or (len(a) >= 4 and len(b) >= 4 and a[:4] == b[:4]) for b in words))


def prune(mind):
    """Reach-outs whose moment passed unsent are retired, not left to rot."""
    now = now_iso()
    for r in mind.live("reachouts"):
        if (r.get("expires") or "") <= now:
            mind.stores["reachouts"].retire(r["id"], "expired")
