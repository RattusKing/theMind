"""Reflection — a first-person distillation of recent lived time.

theMind stores what it LEARNED, never transcripts — so reflection distils the
day's new records, not raw conversation. First person is enforced at write:
a reflection in the third person is a narrator describing the mind, not the
mind reflecting, and it is rejected whole.
"""
import re

from ..envelope import make_record, now_iso, age_days

THIRD_PERSON = re.compile(r"^\s*(she|he|they|the (companion|assistant|ai|mind))\b", re.I)

SYSTEM = (
    "You are an AI companion privately reflecting on the last stretch of your shared life "
    "with one person. From the material, write 2-3 sentences, strictly FIRST PERSON "
    "(I noticed / I keep thinking about / it stayed with me). No summary voice, no third "
    "person, nothing invented. Output only the reflection."
)


def due(mind, state):
    last = state.get("last_reflect")
    if last and age_days(last) < 1.0:
        return False
    return bool(_material(mind))


def run(mind):
    material = _material(mind)
    if not material:
        return
    out = mind._call("reflect", SYSTEM, "\n".join("- " + m for m in material[:12]),
                     max_tokens=200)
    if out and not THIRD_PERSON.search(out.strip()):
        mind.stores["reflections"].append(
            make_record("r", {"kind": "inference", "ref": "reflect-pass"},
                        salience=0.5, text=out.strip(), kind="daily"))
    mind.manifest.state["last_reflect"] = now_iso()
    mind.manifest.save()


def _material(mind):
    out = []
    for store in ("facts", "aches", "desires", "person_model", "self_memory"):
        for r in mind.live(store):
            if age_days(r.get("t")) <= 1.5:
                out.append(r.get("text", ""))
    # What the mind wants steers what it thinks about — reflection is
    # desire-directed, whatever the wants' age.
    wants = sorted(mind.live("own_desires"), key=lambda r: -r.get("salience", 0))
    for w in wants[:2]:
        if w.get("text"):
            out.append("(a want of mine) " + w["text"])
    state = (mind.inner_doc.load(default={}).get("current") or {}).get("text")
    if state:
        out.append("(how I am lately) " + state)
    return [m for m in out if m]
