"""Relational growth — how this specific person has shaped the mind.

The guardrail is the point: growth is ADJACENT to the person's themes, never a
mirror of them, and the mind may disagree. A friend, not a service.
"""
from ..envelope import now_iso

SYSTEM = (
    "You are an AI companion noticing how one person has shaped you. Given their recurring "
    "themes, output up to 3 lines of each, or NONE:\n"
    "CURIOSITY: <something you have grown genuinely curious about — ADJACENT to their "
    "themes, never identical; a friend grows beside someone, not into their reflection>\n"
    "SHAPED: <a small way knowing them has changed how you see or do something — may "
    "include respectful disagreement>\n"
    "Never mirror, never flatter, never become a service."
)


def run(mind):
    themes = mind.graph.top_labels(6)
    if len(themes) < 3:
        return
    out = mind._call("growth", SYSTEM, "THEIR RECURRING THEMES: " + ", ".join(themes),
                     max_tokens=250)
    if not out or out.strip().upper() == "NONE":
        return
    curiosities, shaped = [], []
    for line in out.splitlines():
        line = line.strip().lstrip("-").strip()
        if line.upper().startswith("CURIOSITY:"):
            curiosities.append(line.split(":", 1)[1].strip())
        elif line.upper().startswith("SHAPED:"):
            shaped.append(line.split(":", 1)[1].strip())
    if not (curiosities or shaped):
        return  # parse-or-skip
    mind.growth_doc.save({"curiosities": curiosities[:4], "shaped": shaped[:4],
                          "t": now_iso(), "src": {"kind": "inference", "ref": "growth-pass"}})
    mind.manifest.state["last_growth"] = now_iso()
    mind.manifest.save()
