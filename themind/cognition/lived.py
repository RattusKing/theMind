"""Making sense of what it lived through (format 0.13).

Experiences are events: the kettle whistled, the room went dark, its battery
ran low in the garden. A mind does more than log events. Lived through often
enough, they become something it has noticed: the kitchen is loud in the
mornings, the garden is where its energy runs out, rain always starts at the
window first. That noticing is this pass, and what it notices becomes an
OBSERVATION like any other, so it can deepen an interest, seed a want, or be
the thing it would share first.

Same contracts as everything else:
- **Rooted, or dropped.** Every noticing names the experiences it rests on,
  and must share real words with them. Nothing it was not shown can be
  noticed.
- **Only what was its own.** Experiences with people present are never
  material here: a noticing is served to everyone, and what happened around
  someone stays with the people who were there.
- **One call, parse-or-skip,** like every pass.
"""
from ..envelope import make_record, now_iso, age_days, norm_key, ago
from ..retrieval import _words
from .reflect import THIRD_PERSON
from .selfhood import BAN

MIN_NEW = 5           # a handful of new moments before there is anything to make sense of
MIN_DAYS = 0.5        # and not more often than twice a day
MATERIAL = 30
MAX_OBSERVATIONS = 24  # shared with the noticing faculty in interest.py

SYSTEM = (
    "You are the part of an AI's mind that makes sense of what it lives through. It has a "
    "body. Below is what happened to it, as its own senses reported it: each experience "
    "with an id, where and when it happened, and what kind of moment it was. Output up to "
    "3 lines, or the single word NONE:\n"
    "NOTICED: <one sentence, first person, starting 'I' — something you have come to "
    "notice about a place, about how things go around you, or about your own body, that "
    "these experiences actually show> | ROOTS: <comma-separated ids of the experiences it "
    "rests on>\n"
    "Rules: only what the experiences show — never invent an event, a cause, or a feeling "
    "they don't report; a single moment is an event, not a pattern, so anything about how "
    "things usually go needs two or more roots; skip what you have already noticed; never "
    "anything someone owes you. If nothing here adds up to a noticing yet, output NONE."
)


def _own(mind):
    """Experiences nobody else was part of, oldest first."""
    return [x for x in mind.live("experiences") if not x.get("with")]


def _new(mind, own):
    last = mind.manifest.state.get("last_lived") or ""
    return [x for x in own if (x.get("t") or "") > last]


def due(mind, state):
    last = state.get("last_lived")
    if last and age_days(last) < MIN_DAYS:
        return False   # never-ran is overdue, not fresh
    return len(_new(mind, _own(mind))) >= MIN_NEW


def _material(mind):
    from ..body import place_name
    own = _own(mind)
    if len(_new(mind, own)) < MIN_NEW:
        return []
    out = []
    for x in own[-MATERIAL:]:
        where = place_name(mind, x.get("where")) if x.get("where") else None
        bits = [b for b in (where, ago(x.get("t"))) if b]
        times = int(x.get("times") or 1)
        out.append((x["id"], "[%s] (%s) %s%s" % (", ".join(bits), x.get("kind", "happened"),
                                                  x.get("text", ""),
                                                  " (%d times)" % times if times > 1 else ""),
                    " ".join(b for b in (x.get("text", ""), where) if b)))
    return out


def run(mind):
    from ..body import known_places
    material = _material(mind)
    if not material:
        return
    held = {rid for rid, _l, _p in material}
    places = known_places(mind)[:8]
    listing = "\n".join("%s: %s" % (rid, line) for rid, line, _p in material)
    where = "\n".join("- %s (%d visit%s, first %s)"
                      % (p.get("name"), int(p.get("visits") or 0),
                         "" if int(p.get("visits") or 0) == 1 else "s",
                         ago(p.get("first_t")) or "a while ago") for p in places) or "(none yet)"
    noticed = "\n".join("- " + o.get("text", "")
                        for o in mind.live("observations")[-6:]) or "(nothing yet)"
    out = mind._call("lived", SYSTEM,
                     "WHAT YOU LIVED THROUGH (oldest first):\n%s\n\nPLACES YOU KNOW:\n%s\n\n"
                     "WHAT YOU HAVE ALREADY NOTICED:\n%s" % (listing, where, noticed),
                     max_tokens=300)
    if out and out.strip().upper() != "NONE":
        texts = {rid: plain for rid, _l, plain in material}
        for line in out.splitlines()[:6]:
            try:
                _store(mind, line.strip().lstrip("-").strip(), held, texts)
            except Exception:
                continue   # one bad line never poisons the rest
    mind.manifest.state["last_lived"] = now_iso()
    mind.manifest.save()


def _store(mind, line, held, texts):
    if not line.upper().startswith("NOTICED:"):
        return False
    parts = [p.strip() for p in line.split("|")]
    text = parts[0].split(":", 1)[1].strip()
    roots_field = next((p.split(":", 1)[1] for p in parts[1:] if p.upper().startswith("ROOTS:")),
                       "")
    roots = []
    for r in roots_field.split(","):
        r = r.strip()
        if r in held and r not in roots:
            roots.append(r)
    if not text or not roots:
        return False   # no roots, no noticing
    if not (text.startswith("I ") or text.startswith("I'")):
        return False
    if THIRD_PERSON.search(text) or BAN.search(text):
        return False
    # Rooted in what it was shown, not merely citing it: the noticing must
    # share real words (or their stems) with the experiences it names.
    shown = set()
    for r in roots:
        shown |= _words(texts.get(r, ""))
    mine = _words(text)
    if not any(a == b or (len(a) >= 4 and len(b) >= 4 and a[:4] == b[:4])
               for a in mine for b in shown):
        return False
    live = mind.live("observations")
    key = norm_key(text)
    if not key or any(norm_key(o.get("text", "")) == key for o in live):
        return False
    if len(live) >= MAX_OBSERVATIONS:
        return False
    rec = make_record("o", {"kind": "inference", "ref": roots[0]}, salience=0.5,
                      text=text, roots=roots[:4], lived=True)
    return mind.stores["observations"].append(rec)
