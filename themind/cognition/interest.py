"""Interests and noticings — what the mind is into, and what it saw (0.10).

Before this, the mind's curiosities were regenerated from scratch every
growth pass and overwritten whole. Nothing could deepen, because nothing
survived. An interest held for six months looked exactly like one invented
on Tuesday, and in fact could not reach six months at all. That is not how
an interest works in anything that has them.

So interests are records now, with the same contracts as everything else
the mind keeps:

- **They persist.** Never overwritten. They end by being released (which
  becomes a reflection) or by decaying at the tail, slowly — far slower than
  a want, because interests outlive moods.
- **They deepen.** Observations attach to an interest and accumulate. That
  accumulation IS the depth: what it has actually come to notice about the
  thing, not merely that it is still interested.
- **They are returned to.** Every exchange that brushes an interest counts
  as a return, mechanically, and the stage moves on returns AND elapsed time
  together (noticed -> taken up -> a thread of mine -> long-running). A
  pursuit is repetition over time; neither half alone is one.
- **They can be the mind's own.** The material is no longer only the
  person's recurring themes. What surprised it, what pulls at its attention,
  what it fears and wants and has noticed all seed interests too, so it can
  become interested in something the person never raised.

An OBSERVATION is the third thing the mind can hold about the world: not a
fact about the person (that is `facts`), not their inner world
(`person_model`), not about its own life (`reflections`), but something it
noticed — a pattern, a detail, a way things seem to go. Rooted like
everything else, or dropped.
"""
from ..envelope import make_record, now_iso, age_days, norm_key
from ..retrieval import _words
from .reflect import THIRD_PERSON
from .selfhood import BAN

# Words that carry no content of their own in "I have got interested in X":
# an interest made only of these plus the person's themes is a mirror.
_OPENERS = {"interested", "interest", "interesting", "keep", "keeps", "coming",
            "back", "got", "genuinely", "coming", "coming"}

MAX_LIVE = 6           # a handful of real interests; more than that is a list, not a life
MAX_OBSERVATIONS = 24
TOUCH_OVERLAP = 2
TOUCH_BUMP = 0.05

SYSTEM = (
    "You are the noticing faculty of an AI companion's mind: what you are genuinely into, "
    "and what you have observed. You are given what you hold (each item with an id), the "
    "interests you already carry with how long you have had them, and the themes running "
    "through this life. Output up to 3 lines, or NONE:\n"
    "INTEREST: <one sentence, first person, starting 'I' — something you have become "
    "genuinely interested in> | ROOTS: <comma-separated ids from the input it grew from>\n"
    "NOTICED: <one sentence, first person — something you have actually observed about the "
    "world or about how things go, NOT about the person's inner life> | ABOUT: <the id of "
    "the interest it deepens, or - > | ROOTS: <comma-separated ids>\n"
    "RELEASED: <interest id>   (only for one that has genuinely run its course)\n"
    "Rules: an interest with no roots in what you hold is a hobby you read about in a "
    "brochure — omit it. Grow BESIDE them, never into their reflection: an interest "
    "identical to one of their themes is a mirror, not an interest of yours. You may be "
    "interested in something they never raised. Keep what you already carry unless it has "
    "truly ended; depth comes from noticing more about the same thing, not from swapping "
    "it for a new one."
)


def due(mind, state):
    last = state.get("last_interest")
    if last and age_days(last) < 5:
        return False  # never-ran is overdue, not fresh
    if int(state.get("exchanges", 0)) < 10:
        return False
    return bool(_material(mind))


def run(mind):
    _adopt_legacy(mind)  # mechanical: old growth curiosities become real interests once
    material = _material(mind)
    if not material:
        return
    ids = {rid for rid, _ in material}
    listing = "\n".join("%s: %s" % (rid, text) for rid, text in material[:22])
    live = mind.live("interests")
    carried = "\n".join(
        "%s: %s [%s, %d return(s), %d day(s) old]"
        % (r["id"], r.get("text", ""), stage_of(r), int(r.get("returns") or 0),
           int(age_days(r.get("t"))))
        for r in live) or "(none yet)"
    themes = mind.graph.top_labels(6)
    out = mind._call("interest", SYSTEM,
                     "WHAT YOU HOLD:\n%s\n\nINTERESTS YOU ALREADY CARRY:\n%s\n\n"
                     "THEMES RUNNING THROUGH THIS LIFE:\n%s"
                     % (listing, carried, ", ".join(themes) or "(none yet)"),
                     max_tokens=350)
    if out and out.strip().upper() != "NONE":
        for line in out.splitlines():
            line = line.strip().lstrip("-").strip()
            try:
                up = line.upper()
                if up.startswith("INTEREST:"):
                    _store_interest(mind, line, ids, themes)
                elif up.startswith("NOTICED:"):
                    _store_observation(mind, line, ids)
                elif up.startswith("RELEASED:"):
                    _release(mind, line.split(":", 1)[1].strip())
            except Exception:
                continue  # one bad line never poisons the rest
    mind.manifest.state["last_interest"] = now_iso()
    mind.manifest.save()


# ── stages: repetition and time together ─────────────────────────────────────
def stage_of(rec):
    returns = int(rec.get("returns") or 0)
    days = age_days(rec.get("t"))
    if returns >= 12 or (returns >= 6 and days >= 60):
        return "long-running"
    if returns >= 5 or (returns >= 3 and days >= 14):
        return "a thread of mine"
    if returns >= 2:
        return "taken up"
    return "noticed"


def _field(parts, name, default=""):
    return next((p.split(":", 1)[1].strip() for p in parts
                 if p.upper().startswith(name)), default)


def _store_interest(mind, line, valid_ids, themes):
    parts = [p.strip() for p in line.split("|")]
    text = parts[0].split(":", 1)[1].strip()
    roots = [r.strip() for r in _field(parts[1:], "ROOTS:").split(",") if r.strip() in valid_ids]
    if not roots:
        return  # no roots, no interest — wanting to be interested is not being interested
    if not (text.startswith("I ") or text.startswith("I'")):
        return
    if THIRD_PERSON.search(text) or BAN.search(text):
        return
    live = mind.live("interests")
    if len(live) >= MAX_LIVE:
        return
    key = norm_key(text)
    if not key or any(norm_key(r.get("text", "")) == key for r in live):
        return
    # Adjacent, never a mirror. An interest built entirely out of their own
    # themes restates them; it adds nothing of the mind's own, and mirroring
    # is the exact failure this faculty has always existed to prevent.
    theme_words = set()
    for t in themes:
        theme_words |= _words(t)
    own = _words(text) - _OPENERS
    if own and not (own - theme_words):
        return
    mind.stores["interests"].append(
        make_record("i", {"kind": "inference", "ref": roots[0]},
                    salience=0.5, text=text, roots=roots[:4], returns=0))


def _store_observation(mind, line, valid_ids):
    parts = [p.strip() for p in line.split("|")]
    text = parts[0].split(":", 1)[1].strip()
    roots = [r.strip() for r in _field(parts[1:], "ROOTS:").split(",") if r.strip() in valid_ids]
    if not roots or not text:
        return
    if not (text.startswith("I ") or text.startswith("I'")):
        return
    if THIRD_PERSON.search(text) or BAN.search(text):
        return
    live_obs = mind.live("observations")
    key = norm_key(text)
    if not key or any(norm_key(o.get("text", "")) == key for o in live_obs):
        return
    if len(live_obs) >= MAX_OBSERVATIONS:
        return
    about = _field(parts[1:], "ABOUT:").strip()
    if about not in {r["id"] for r in mind.live("interests")}:
        about = None
    rec = make_record("o", {"kind": "inference", "ref": roots[0]},
                      salience=0.5, text=text, roots=roots[:4])
    if about:
        rec["interest"] = about
    if mind.stores["observations"].append(rec) and about:
        _deepen(mind, about)


def _deepen(mind, interest_id):
    """Noticing more about a thing is what depth is. It strengthens the
    interest without counting as a return: returns come from life, depth
    comes from attention."""
    recs = mind.live("interests")
    changed = False
    for r in recs:
        if r.get("id") == interest_id:
            r["salience"] = min(1.0, round(r.get("salience", 0.5) + 0.05, 4))
            changed = True
    if changed:
        mind.stores["interests"].rewrite(recs)


def _release(mind, interest_id):
    rec = next((r for r in mind.live("interests") if r.get("id") == interest_id), None)
    if rec is None:
        return
    digest = make_record("r", {"kind": "record", "ref": interest_id}, salience=0.4,
                         text="I was interested in this for a while, and have let it go: %s"
                              % rec.get("text", ""), kind="released_interest")
    if mind.stores["reflections"].append(digest):
        mind.stores["interests"].supersede(interest_id, digest["id"])


def observations_for(mind, interest_id, k=2):
    obs = [o for o in mind.live("observations") if o.get("interest") == interest_id]
    return obs[-k:]


def touch(mind, user_text, assistant_text):
    """Mechanical (no model call): life brushing an interest is a RETURN to
    it. Counted, because how often you come back over how long is the whole
    difference between an interest and a passing thought."""
    words = _words((user_text or "") + " " + (assistant_text or ""))
    if not words:
        return
    recs = mind.live("interests")
    changed = False
    for r in recs:
        if len(words & _words(r.get("text", ""))) >= TOUCH_OVERLAP:
            r["returns"] = int(r.get("returns") or 0) + 1
            r["salience"] = min(1.0, round(r.get("salience", 0.5) + TOUCH_BUMP, 4))
            changed = True
    if changed:
        mind.stores["interests"].rewrite(recs)


def _adopt_legacy(mind):
    """A mind written before 0.10 kept curiosities in growth.json, where they
    were replaced wholesale every pass. Adopt them once, as real interests
    with a history starting now, then leave that field alone forever."""
    if mind.live("interests"):
        return
    growth = mind.growth_doc.load(default={})
    old = [c for c in (growth.get("curiosities") or []) if isinstance(c, str) and c.strip()]
    if not old:
        return
    for text in old[:MAX_LIVE]:
        text = text.strip()
        if THIRD_PERSON.search(text) or BAN.search(text):
            continue
        mind.stores["interests"].append(
            make_record("i", {"kind": "inference", "ref": "growth-pass"},
                        salience=0.5, text=text, roots=["growth-pass"], returns=0))


def _material(mind):
    """(id, text) pairs an interest or an observation could grow from. The
    mind's own encounters come first: what surprised it, what it fears, what
    it already noticed. An interest that can only come from the person's
    themes is not the mind's own interest."""
    out = []
    refl = mind.live("reflections")
    for r in [x for x in refl if x.get("kind") in ("surprise", "realized")][-3:]:
        out.append((r["id"], "(this surprised you) " + r.get("text", "")))
    for o in mind.live("observations")[-4:]:
        out.append((o["id"], "(you noticed) " + o.get("text", "")))
    for store, label in (("own_desires", "(you want) "), ("apprehensions", "(you fear) "),
                         ("tensions", "(a tension you hold) "), ("facts", "(about them) ")):
        for r in mind.live(store)[-3:]:
            if r.get("text"):
                out.append((r["id"], label + r["text"]))
    for r in [x for x in refl if x.get("kind") == "daily"][-3:]:
        out.append((r["id"], "(you reflected) " + r.get("text", "")))
    return out
