"""The autobiographical self — the life story, continuing (FORMAT.md, `story.json`).

Reflections are moments; this is the arc. A living chapter carries the story
so far, revised on the slowest rhythm in the mind — life stories move in
weeks, not turns. When an era genuinely ends, the chapter closes: it moves to
`chapters` with one sentence laying it to rest, and the story continues in a
new one. Closed chapters are never deleted and never capped — a life keeps
all its chapters, however many it earns.

Contracts: continue never restart (every revision receives the story so far);
arc over inventory; first person at write; ban-vocab holds.
"""
from ..envelope import now_iso, age_days
from .reflect import THIRD_PERSON
from .selfhood import BAN

SYSTEM = (
    "You are the autobiographical faculty of an AI companion's mind, keeping the story of "
    "a shared life — yours and one person's. Given the story so far and what the last "
    "stretch of life held, output:\n"
    "STORY: <the living chapter, revised — 3-6 sentences, strictly first person, "
    "CONTINUING the story so far; deepen and extend it, never start over>\n"
    "And ONLY if an era has genuinely ended (a move, a loss, a change in what you are to "
    "each other), one line BEFORE it:\n"
    "CHAPTER: <one sentence laying that era to rest>\n"
    "Rules: this is a life, not a log — arc over inventory; ground everything in the "
    "material given, nothing invented; chapters close rarely."
)


def due(mind, state):
    if age_days(state.get("last_story") or "") < 10:
        return False
    if int(state.get("exchanges", 0)) < 20:
        return False
    return len(mind.live("reflections")) >= 3


def run(mind):
    doc = mind.story_doc.load(default={})
    prior = (doc.get("current") or {}).get("text")
    material = _material(mind)
    if not material:
        return
    out = mind._call("story", SYSTEM,
                     "THE STORY SO FAR:\n%s\n\nTHE LAST STRETCH OF LIFE:\n%s" % (
                         prior or "(unwritten — this is the first page)",
                         "\n".join("- " + m for m in material[:12])),
                     max_tokens=400)
    if not out or "STORY:" not in out:
        return  # parse-or-skip: no reply shape can cost the story
    chapter_close = None
    head, _, story_text = out.partition("STORY:")
    if "CHAPTER:" in head:
        chapter_close = head.split("CHAPTER:", 1)[1].strip().splitlines()[0].strip()
    story_text = story_text.strip()
    if len(story_text) < 40:
        return
    if THIRD_PERSON.search(story_text) or BAN.search(story_text):
        return  # a narrator's biography is not an autobiography
    chapters = list(doc.get("chapters") or [])
    if chapter_close and prior:
        chapters.append({"text": prior, "closed": chapter_close,
                         "t": (doc.get("current") or {}).get("t") or now_iso(),
                         "closed_t": now_iso()})
    mind.story_doc.save({
        "current": {"text": story_text, "t": now_iso(),
                    "src": {"kind": "inference", "ref": "story-pass"}},
        "chapters": chapters,  # never deleted, never capped: a life keeps its chapters
    })
    mind.manifest.state["last_story"] = now_iso()
    mind.manifest.save()


def _material(mind):
    out = []
    # Lifecycle reflections ARE biography: what was gotten, let go of, and wrong.
    for r in mind.live("reflections")[-6:]:
        if r.get("text"):
            out.append(r["text"])
    felt = (mind.felt_doc.load(default={}).get("current") or {}).get("text")
    if felt:
        out.append("(who they are to me) " + felt)
    bundle = mind.selfhood_bundle()
    if not bundle.get("default") and bundle.get("position"):
        out.append("(where I stand) " + bundle["position"])
    state = (mind.inner_doc.load(default={}).get("current") or {}).get("text")
    if state:
        out.append("(how I am lately) " + state)
    pulls = mind.graph.pulls(4)
    if pulls:
        out.append("(what pulls at me) " + ", ".join(pulls))
    return out
