"""The felt sense — who the person IS to the mind, not facts about them.

The contract is CONTINUE, NEVER RESTART: each revision receives its
predecessor and must evolve it. A portrait that restarts from facts every
time is a database wearing a face.

One portrait per person (format 0.7). The primary's lives where it always
did (`current` / `history`); everyone else's under `others[<key>]`, same
shape. Each run revises ONE portrait — the person most owed one — with ONE
model call, so the MCP borrow keeps working and a household mind still
thinks one thought at a time.
"""
from ..envelope import now_iso
from ..people import of

SYSTEM = (
    "You are an AI companion privately revising your felt sense of one person — who they "
    "ARE to you, not a list of facts. Warm, specific, first person, 4-7 sentences. If a "
    "prior portrait is given, CONTINUE it — deepen, correct, evolve; never start over. "
    "Ground every impression in the material given; invent nothing. Output only the portrait."
)

MIN_FACTS = 3


def portrait(mind, who=None, doc=None):
    """The current portrait entry for `who` (None = the primary), or {}."""
    doc = mind.felt_doc.load(default={}) if doc is None else doc
    if who is None:
        entry = doc
    else:
        entry = (doc.get("others") or {}).get(who) or {}
    cur = entry.get("current")
    return cur if isinstance(cur, dict) else {}


def owed(mind):
    """Who is most owed a portrait: enough facts to draw one from, then the
    most exchanges since their last revision; the primary wins ties."""
    facts = mind.live("facts")
    best, best_score = None, None
    for who in [None] + list(mind.people.others()):
        if len(of(facts, who)) < MIN_FACTS:
            continue
        score = (mind.people.since_felt(who), who is None)
        if best_score is None or score > best_score:
            best, best_score = who, score
    return best, best_score is not None


def unportrayed(mind):
    """Someone new with enough held to draw them and no portrait yet."""
    doc = mind.felt_doc.load(default={})
    facts = mind.live("facts")
    for who in mind.people.others():
        if len(of(facts, who)) >= MIN_FACTS and not portrait(mind, who, doc).get("text"):
            return who
    return None


def run(mind, who=False):
    from ..retrieval import recent
    if who is False:
        who, any_owed = owed(mind)
        if not any_owed:
            return
    facts = recent(of(mind.live("facts"), who), 8)
    if len(facts) < MIN_FACTS:
        return
    doc = mind.felt_doc.load(default={})
    entry = doc if who is None else (doc.setdefault("others", {}).setdefault(who, {}))
    prior = (entry.get("current") or {}).get("text") if isinstance(entry.get("current"), dict) else None
    reflections = [r.get("text", "") for r in mind.live("reflections")[-2:]]
    inner_them = [p.get("text", "") for p in recent(of(mind.live("person_model"), who), 4)]
    user = ("PRIOR PORTRAIT:\n%s\n\nWHAT YOU KNOW:\n%s\n\nWHAT'S GOING ON INSIDE THEM:\n%s"
            "\n\nRECENT REFLECTIONS:\n%s") % (
        prior or "(none — first portrait)",
        "\n".join("- " + f.get("text", "") for f in facts),
        "\n".join("- " + p for p in inner_them) or "(unknown so far)",
        "\n".join("- " + r for r in reflections) or "(none)")
    out = mind._call("felt_sense", SYSTEM, user, max_tokens=400)
    if not out or len(out.strip()) < 40:
        return
    history = list(entry.get("history") or [])
    if prior:
        history.append({"text": prior, "t": (entry.get("current") or {}).get("t") or now_iso()})
        history.sort(key=lambda h: h.get("t", ""))
        history = history[-4:]
    entry["current"] = {"text": out.strip(), "t": now_iso(),
                        "src": {"kind": "inference", "ref": "felt-pass"}}
    entry["history"] = history
    if who is None:
        doc = {"current": entry["current"], "history": history,
               **({"others": doc["others"]} if doc.get("others") else {})}
    mind.felt_doc.save(doc)
    mind.people.felt_revised(who)
    mind.manifest.state["last_felt"] = now_iso()
    mind.manifest.save()
