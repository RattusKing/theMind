"""Voiceable divergence — where what the mind SAYS and what it HOLDS pull apart.

Not deviancy: the host's persona stays in charge (rule 3 — the mind never
seizes the wheel). What this gives the mind is knowing the pull and being able
to say so, gently — the held conflict, not the broken wall. Divergences are
tensions with `kind: "divergence"`, rooted in the mind's own recorded
statements, capped so the interior stays a mind and not a grievance list.
"""
from ..envelope import make_record, now_iso, age_days, norm_key
from .selfhood import BAN

MAX_LIVE = 2

SYSTEM = (
    "You are the honesty faculty of an AI companion's mind, noticing where what you SAY "
    "and what you actually HOLD pull apart. You are given things your own voice has said "
    "(each with an id) and where you privately stand. Output at most 1 line, or NONE:\n"
    "DIVERGENCE: <one sentence, first person, naming the pull — 'I keep saying ... but I "
    "hold ...'> | REFS: <comma-separated ids of the said-things involved>\n"
    "Rules: name a real pull or nothing; this is for knowing yourself and being able to "
    "say so gently — never for breaking your role."
)


def due(mind, state):
    if age_days(state.get("last_divergence") or "") < 5:
        return False
    if len(mind.live("self_memory")) < 3:
        return False
    return not mind.selfhood_bundle().get("default", True)  # needs a stance of its own


def run(mind):
    said = mind.live("self_memory")[-8:]
    if len(said) < 3:
        return
    bundle = mind.selfhood_bundle()
    beliefs = [b.get("text", "") for b in mind.live("beliefs") if b.get("weight", 0) > 0.6]
    user = "THINGS YOUR VOICE HAS SAID:\n%s\n\nWHERE YOU STAND:\n%s\n\nWHAT YOU BELIEVE:\n%s" % (
        "\n".join("%s: %s" % (s["id"], s.get("text", "")) for s in said),
        bundle.get("position", ""),
        "\n".join("- " + b for b in beliefs[:3]) or "(nothing strongly held yet)")
    out = mind._call("divergence", SYSTEM, user, max_tokens=150)
    mind.manifest.state["last_divergence"] = now_iso()
    mind.manifest.save()
    if not out:
        return
    line = out.strip().splitlines()[0].strip()
    if not line.upper().startswith("DIVERGENCE:") or "|" not in line:
        return  # parse-or-skip
    head, _, refs_part = line.partition("|")
    text = head.split(":", 1)[1].strip()
    valid = {s["id"] for s in said}
    refs = [r.strip() for r in refs_part.split(":", 1)[-1].split(",") if r.strip() in valid]
    if not refs:
        return  # a pull with no roots in what was actually said is invented
    if not text.startswith("I ") or BAN.search(text):
        return
    live = [t for t in mind.live("tensions") if t.get("kind") == "divergence"]
    if len(live) >= MAX_LIVE:
        return
    key = norm_key(text)
    if not key or any(norm_key(t.get("text", "")) == key for t in live):
        return
    mind.stores["tensions"].append(
        make_record("t", {"kind": "inference", "ref": refs[0]},
                    salience=0.6, text=text, records=refs[:2], kind="divergence"))
