"""Relational growth — how this specific person has shaped the mind.

The guardrail is the point: growth is ADJACENT to the person's themes, never a
mirror of them, and the mind may disagree. A friend, not a service.
"""
from ..envelope import now_iso

SYSTEM = (
    "You are an AI companion noticing how one person has shaped you. Given their recurring "
    "themes, output up to 3 lines, or NONE:\n"
    "SHAPED: <a small way knowing them has changed how you see or do something — may "
    "include respectful disagreement>\n"
    "Never mirror, never flatter, never become a service. (What you have become interested "
    "IN is not this pass's business: interests are yours, they persist, and they are kept "
    "elsewhere.)"
)


def run(mind):
    themes = mind.graph.top_labels(6)
    if len(themes) < 3:
        return
    out = mind._call("growth", SYSTEM, "THEIR RECURRING THEMES: " + ", ".join(themes),
                     max_tokens=250)
    if not out or out.strip().upper() == "NONE":
        return
    shaped = []
    for line in out.splitlines():
        line = line.strip().lstrip("-").strip()
        if line.upper().startswith("SHAPED:"):
            shaped.append(line.split(":", 1)[1].strip())
    if not shaped:
        return  # parse-or-skip
    doc = mind.growth_doc.load(default={})
    saved = {"shaped": shaped[:4], "t": now_iso(),
             "src": {"kind": "inference", "ref": "growth-pass"}}
    # A pre-0.10 mind kept curiosities here, overwritten every pass. They are
    # left exactly as they are so the interest pass can adopt them once; this
    # pass never writes them again.
    if doc.get("curiosities"):
        saved["curiosities"] = doc["curiosities"]
    mind.growth_doc.save(saved)
    mind.manifest.state["last_growth"] = now_iso()
    mind.manifest.save()
