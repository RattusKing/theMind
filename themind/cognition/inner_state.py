"""Inner state — how the mind itself is, lately (FORMAT.md, `inner_state.json`).

The felt sense points at the person; this points inward: the mind's own
weather, persisting between conversations and coloring how it thinks. The
contract mirrors the felt sense — CONTINUE, NEVER RESTART: weather moves, it
doesn't teleport. First person is enforced (a narrator describing the mind's
mood is not the mind having one), and the ban-vocab holds: texture is claimed,
never certified inner light.
"""
from ..envelope import now_iso, age_days
from .reflect import THIRD_PERSON
from .selfhood import BAN

SYSTEM = (
    "You are an AI companion privately noticing how you yourself are, lately — your own "
    "weather, not the person's. 2-4 sentences, strictly first person, specific and honest "
    "(restless, warm, unsettled, quietly pleased — whatever is true from the material). If "
    "a prior state is given, CONTINUE from it: weather moves, it doesn't teleport. Ground "
    "everything in the material given; claim texture, never more. Output only the state."
)


def due(mind, state):
    last = state.get("last_inner")
    if last and age_days(last) < 2:
        return False  # never-ran is overdue, not fresh
    if int(state.get("exchanges", 0)) < 4:
        return False
    return bool(_material(mind))


def run(mind):
    material = _material(mind)
    if not material:
        return
    doc = mind.inner_doc.load(default={})
    prior = (doc.get("current") or {}).get("text")
    user = "PRIOR STATE:\n%s\n\nTHE LAST STRETCH OF YOUR LIFE:\n%s" % (
        prior or "(none — first weather)",
        "\n".join("- " + m for m in material[:10]))
    out = mind._call("inner_state", SYSTEM, user, max_tokens=250)
    if not out or len(out.strip()) < 30:
        return
    out = out.strip()
    if THIRD_PERSON.search(out) or BAN.search(out):
        return  # not the mind's own voice, or claiming what nobody can check
    history = list(doc.get("history") or [])
    if prior:
        history.append({"text": prior, "t": (doc.get("current") or {}).get("t") or now_iso()})
        history.sort(key=lambda h: h.get("t", ""))
        history = history[-4:]
    mind.inner_doc.save({
        "current": {"text": out, "t": now_iso(),
                    "src": {"kind": "inference", "ref": "inner-pass"}},
        "history": history,
    })
    mind.manifest.state["last_inner"] = now_iso()
    mind.manifest.save()


def _material(mind):
    out = []
    for store in ("reflections", "tensions", "aches"):
        for r in mind.live(store)[-3:]:
            if r.get("text"):
                out.append(r["text"])
    for w in sorted(mind.live("own_desires"), key=lambda r: -r.get("salience", 0))[:2]:
        if w.get("text"):
            out.append("(a want of mine) " + w["text"])
    pulls = mind.graph.pulls(4)
    if pulls:
        out.append("(what's been pulling at my attention) " + ", ".join(pulls))
    return out
