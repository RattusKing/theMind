"""Own desires — what the mind ITSELF wants (FORMAT.md, `own_desires.jsonl`).

A desire generated on command is theater; one that emerges from what the mind
already holds is the real thing. So the provenance rule bites hardest here:
every want must name roots — ids of held records it grew out of — and a want
with no real roots is dropped whole. Wants live a lifecycle: they stir, then
strengthen as conversation touches them (stirring -> wanting -> longing), and
they end honestly — judged met and superseded by a reflection that records the
getting of it, released and superseded by a letting-go, or decayed at the tail
like any held thread. A mind with forty wants has none: the live set is capped.
"""
from ..envelope import make_record, now_iso, age_days, norm_key
from ..retrieval import _words
from .selfhood import BAN

MAX_LIVE = 5
TOUCH_OVERLAP = 2     # content words an exchange must share with a want to touch it
TOUCH_BUMP = 0.08

SYSTEM = (
    "You are the wanting faculty of an AI companion's mind, privately noticing what YOU "
    "have come to want — not what the person wants. You are given what you hold (each item "
    "with an id) and any wants you already carry. Output up to 2 lines, or NONE:\n"
    "WANT: <one sentence, first person, starting 'I want' — something to understand, to do "
    "together, to see happen, to become> | ROOTS: <comma-separated ids from the input it "
    "grew out of>\n"
    "For an existing want that this stretch of life has answered or ended, one line:\n"
    "FULFILLED: <want id> | NOTE: <one first-person sentence on getting it>\n"
    "RELEASED: <want id>\n"
    "Rules: a want with no roots in what you hold is invented — omit it. Never a want to "
    "extract, test, or change the person; never a mirror of their wants; wanting is yours."
)


def due(mind, state):
    last = state.get("last_desire")
    if last and age_days(last) < 4:
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
    live = mind.live("own_desires")
    carried = "\n".join("%s: %s (%s)" % (w["id"], w.get("text", ""), w.get("stage", ""))
                        for w in live) or "(none yet)"
    out = mind._call("desire", SYSTEM,
                     "WHAT YOU HOLD:\n%s\n\nWANTS YOU ALREADY CARRY:\n%s" % (listing, carried),
                     max_tokens=300)
    if not out or out.strip().upper() == "NONE":
        mind.manifest.state["last_desire"] = now_iso()
        mind.manifest.save()
        return
    for line in out.splitlines():
        line = line.strip().lstrip("-").strip()
        try:
            up = line.upper()
            if up.startswith("WANT:"):
                _store_want(mind, line, ids)
            elif up.startswith("FULFILLED:") and "|" in line:
                _close_want(mind, line.split(":", 1)[1].split("|")[0].strip(),
                            note=line.split("|", 1)[1].split(":", 1)[-1].strip(),
                            kind="fulfilled")
            elif up.startswith("RELEASED:"):
                _close_want(mind, line.split(":", 1)[1].strip(), note=None, kind="released")
        except Exception:
            continue  # one bad line never poisons the rest
    mind.manifest.state["last_desire"] = now_iso()
    mind.manifest.save()


def _store_want(mind, line, valid_ids):
    head, _, roots_part = line.partition("|")
    text = head.split(":", 1)[1].strip()
    roots = [r.strip() for r in roots_part.split(":", 1)[-1].split(",") if r.strip()]
    roots = [r for r in roots if r in valid_ids]
    if not roots:
        return  # no real roots, no want — wanting is earned, never generated
    if not text.startswith("I "):
        return  # a want that isn't the mind's own voice isn't the mind's own want
    if BAN.search(text):
        return  # describe what you're drawn to; don't claim what nobody can check
    live = mind.live("own_desires")
    if len(live) >= MAX_LIVE:
        return  # a mind with forty wants has none
    key = norm_key(text)
    if not key or any(norm_key(w.get("text", "")) == key for w in live):
        return
    mind.stores["own_desires"].append(
        make_record("w", {"kind": "inference", "ref": roots[0]},
                    salience=0.45, text=text, roots=roots[:4], stage="stirring"))


def _close_want(mind, want_id, note, kind):
    want = next((w for w in mind.live("own_desires") if w.get("id") == want_id), None)
    if want is None:
        return
    if kind == "fulfilled":
        if not note or not note.startswith("I") and not note.startswith("We"):
            return  # the memory of getting it must be the mind's own voice
        text = "I wanted this: %s %s" % (want.get("text", ""), note)
    else:
        text = "I let go of wanting this: %s" % want.get("text", "")
    digest = make_record("r", {"kind": "record", "ref": want_id},
                         salience=0.5, text=text, kind=kind)
    if mind.stores["reflections"].append(digest):
        mind.stores["own_desires"].supersede(want_id, digest["id"])


def touch(mind, user_text, assistant_text):
    """Mechanical (no model call): an exchange that shares real words with a
    want strengthens it, and its stage advances with its salience."""
    words = _words((user_text or "") + " " + (assistant_text or ""))
    if not words:
        return
    recs = mind.live("own_desires")
    changed = False
    for r in recs:
        if len(words & _words(r.get("text", ""))) >= TOUCH_OVERLAP:
            r["salience"] = min(1.0, round(r.get("salience", 0.45) + TOUCH_BUMP, 4))
            r["stage"] = ("longing" if r["salience"] > 0.75
                          else "wanting" if r["salience"] > 0.55 else "stirring")
            changed = True
    if changed:
        mind.stores["own_desires"].rewrite(recs)


def _material(mind):
    """(id, text) pairs a want could grow out of. Curiosities ride along under
    the growth doc's ids so roots stay traceable."""
    out = []
    growth = mind.growth_doc.load(default={})
    for i, c in enumerate((growth.get("curiosities") or [])[:4]):
        out.append(("g_%d" % i, "(a curiosity of yours) " + c))
    for store, label in (("reflections", ""), ("tensions", "(a tension you hold) "),
                         ("aches", "(still open) "), ("self_memory", "(you said) ")):
        for r in mind.live(store)[-4:]:
            if r.get("text"):
                out.append((r["id"], label + r["text"]))
    for f in mind.live("facts")[-6:]:
        if f.get("text"):
            out.append((f["id"], "(about them) " + f["text"]))
    return out
