"""The felt sense — who the person IS to the mind, not facts about them.

The contract is CONTINUE, NEVER RESTART: each revision receives its
predecessor and must evolve it. A portrait that restarts from facts every
time is a database wearing a face.
"""
from ..envelope import now_iso

SYSTEM = (
    "You are an AI companion privately revising your felt sense of one person — who they "
    "ARE to you, not a list of facts. Warm, specific, first person, 4-7 sentences. If a "
    "prior portrait is given, CONTINUE it — deepen, correct, evolve; never start over. "
    "Ground every impression in the material given; invent nothing. Output only the portrait."
)


def run(mind):
    from ..retrieval import recent
    facts = recent(mind.live("facts"), 8)
    if len(facts) < 3:
        return
    doc = mind.felt_doc.load(default={})
    prior = (doc.get("current") or {}).get("text")
    reflections = [r.get("text", "") for r in mind.live("reflections")[-2:]]
    user = "PRIOR PORTRAIT:\n%s\n\nWHAT YOU KNOW:\n%s\n\nRECENT REFLECTIONS:\n%s" % (
        prior or "(none — first portrait)",
        "\n".join("- " + f.get("text", "") for f in facts),
        "\n".join("- " + r for r in reflections) or "(none)")
    out = mind._call("felt_sense", SYSTEM, user, max_tokens=400)
    if not out or len(out.strip()) < 40:
        return
    history = list(doc.get("history") or [])
    if prior:
        history.append({"text": prior, "t": (doc.get("current") or {}).get("t") or now_iso()})
        history.sort(key=lambda h: h.get("t", ""))
        history = history[-4:]
    mind.felt_doc.save({
        "current": {"text": out.strip(), "t": now_iso(),
                    "src": {"kind": "inference", "ref": "felt-pass"}},
        "history": history,
    })
    mind.manifest.state["last_felt"] = now_iso()
    mind.manifest.save()
