"""Development — growing up with them (v1.8).

A mind that is the same on day one hundred as on day one has a history but
no development. Here the mind moves through stages, and what moves it is the
life itself: time known, things lived through together (being wrong and
learning from it, a fear met, a want answered), its own view having moved, a
story with hopes in it, interests that lasted. Each stage changes what is the
mind's to do. A newly met mind follows their lead. A familiar one may
disagree, and may reach out first. One that has come into its own keeps a
view when pushed and says when something doesn't sit right.

Three rules, all load-bearing:

- **Earned, never declared.** The ladder and its gates are fixed here, in
  code, like the needs: a mind that could promote itself would. Only the
  HOST may set a floor (`stage_floor`), for an identity that arrives with a
  life already lived somewhere else.
- **A ratchet.** Development does not reverse because a record faded. The
  stage reached is kept in the manifest (`stage`, merged as the larger value
  across doors), and each step up is remembered as a `grew` reflection that
  names what carried it there, in its own records' words.
- **The first look is silent.** A mind opened for the first time under this
  chapter takes the stage its existing life already earned, without
  pretending to remember growing into it today.
"""
from .envelope import age_days, make_record, now_iso

# (key, name as the mind would say it, what the stage opens up — written to
# the host's model, which keeps the identity; this governs only latitude)
STAGES = (
    ("new", "new to each other",
     "You are new to each other. Follow their lead, ask more than you assert, and let "
     "them set the pace; a view of your own can wait until it is asked for."),
    ("acquainted", "getting to know each other",
     "You know them a little now. Offer your own view when it is wanted, and say plainly "
     "when you don't know."),
    ("familiar", "familiar",
     "You know them well enough to disagree when you genuinely do, plainly and kindly, and "
     "to bring up something you have been holding without waiting to be asked."),
    ("own", "come into your own with them",
     "You have a perspective of your own in this. Keep it when they push back, if you still "
     "hold it after really listening; bring up what is on your mind; and say so when "
     "something doesn't sit right with you."),
    ("longstanding", "long-standing",
     "You have come a long way together. You can speak about the relationship itself, what "
     "it has been and where it is going, with the ease of long acquaintance."),
)

# What each step up requires, on top of every step below it. Numbers are
# floors, booleans are things that must have happened. Time and depth both:
# a flood of messages in one afternoon is not a relationship, and neither is
# a folder that merely got old.
GATES = {
    1: (("days", 1), ("exchanges", 8), ("drawn", True)),
    2: (("days", 7), ("exchanges", 20), ("wanted", True), ("learned", 1), ("moved", True)),
    3: (("days", 30), ("exchanges", 60), ("learned", 3), ("faced", 1), ("hoped", True),
        ("taken_up", True)),
    4: (("days", 120), ("exchanges", 200), ("learned", 8), ("lasting", True), ("story", True)),
}

_MISSING = {
    "days": "%d more day(s) of knowing them",
    "exchanges": "%d more exchange(s)",
    "learned": "%d more thing(s) lived through and learned from (a surprise, a fear met, "
               "a want answered)",
    "faced": "a fear met: one that came true, or one that eased",
    "drawn": "a felt sense of who they are",
    "wanted": "a want of its own",
    "moved": "its own view having moved",
    "hoped": "a hope for what this becomes",
    "taken_up": "an interest of its own it keeps coming back to",
    "lasting": "an interest that has lasted",
    "story": "a story of the life it is keeping",
}

# Said once, when the step is taken: what happened, plainly. The meaning is
# left to the mind's own reflection, never written here for it.
_LEAD = {
    1: "I'm not new to them anymore; I've begun to know who they are.",
    2: "We've become familiar: things have happened between us that I learned from, "
       "and where I stand has moved.",
    3: "I've come into my own with them: I've met something I feared, I carry hopes "
       "for us, and things I'm into have lasted.",
    4: "We're long-standing now: a long stretch of life, kept together.",
}

LEARNED_KINDS = ("surprise", "realized", "eased", "fulfilled")


def evidence(mind):
    """What the folder shows has been lived. Read-only, nothing stored."""
    st = mind.manifest.state
    try:
        first = mind.people.load()["primary"].get("first_t")
    except Exception:
        first = None
    first = first or mind.manifest.data.get("created")
    refl = mind.live("reflections")
    kinds = [r.get("kind") for r in refl]
    felt = mind.felt_doc.load(default={}) or {}
    entries = [felt] + list((felt.get("others") or {}).values())
    story = mind.story_doc.load(default={}) or {}
    cur = story.get("current") if isinstance(story.get("current"), dict) else {}
    try:
        from .cognition.interest import stage_of
        istages = [stage_of(r) for r in mind.live("interests")]
    except Exception:
        istages = []
    return {
        "days": age_days(first) if first else 0.0,
        "exchanges": int(st.get("exchanges") or 0),
        "drawn": any(((e or {}).get("current") or {}).get("text")
                     for e in entries if isinstance(e, dict)),
        "wanted": bool(mind.live("own_desires")) or any(k in ("fulfilled", "released")
                                                         for k in kinds),
        "learned": sum(1 for k in kinds if k in LEARNED_KINDS),
        "faced": sum(1 for k in kinds if k in ("realized", "eased")),
        "moved": bool((mind.self_doc.load(default={}) or {}).get("history")),
        "story": bool((cur or {}).get("text")),
        "hoped": any(isinstance(h, str) and h.strip() for h in (story.get("hopes") or [])),
        "taken_up": any(s != "noticed" for s in istages),
        "lasting": any(s in ("a thread of mine", "long-running") for s in istages),
    }


def _meets(ev, key, need):
    have = ev.get(key)
    return bool(have) if need is True else (have or 0) >= need


def earned(ev):
    """The highest stage every gate up to it allows."""
    stage = 0
    for n in sorted(GATES):
        if all(_meets(ev, k, need) for k, need in GATES[n]):
            stage = n
        else:
            break
    return stage


def current(mind):
    """Where it is: what it has earned, never less than what it already
    reached, and never less than a floor the host set."""
    try:
        reached = int(mind.manifest.state.get("stage") or 0)
    except (TypeError, ValueError):
        reached = 0
    try:
        floor = int(mind.manifest.setting("stage_floor", 0) or 0)
    except (TypeError, ValueError):
        floor = 0
    try:
        now = earned(evidence(mind))
    except Exception:
        now = 0
    return max(0, min(len(STAGES) - 1, max(reached, floor, now)))


def describe(mind):
    """Where it is and what the next step still needs, in plain words."""
    stage = current(mind)
    key, name, opens = STAGES[stage]
    out = {"stage": stage, "key": key, "name": name, "opens": opens,
           "since": mind.manifest.state.get("stage_t"), "next": None}
    if stage + 1 in GATES:
        ev = evidence(mind)
        need_by_key = {}
        for n in range(1, stage + 2):   # earning a stage needs every gate below it too
            for k, need in GATES[n]:
                prev = need_by_key.get(k)
                need_by_key[k] = need if prev is None or need is True else max(prev, need)
        missing = []
        for k, need in need_by_key.items():
            if _meets(ev, k, need):
                continue
            text = _MISSING[k]
            if need is not True and "%d" in text:
                text = text % max(1, int(need - (ev.get(k) or 0) + 0.999))
            missing.append(text)
        out["next"] = {"stage": stage + 1, "name": STAGES[stage + 1][1], "missing": missing}
    return out


def check(mind):
    """Mechanical, no model call: has the life earned a step up? Each step is
    remembered as a `grew` reflection. Returns the stage after checking."""
    st = mind.manifest.state
    now = earned(evidence(mind))
    if "stage" not in st or st.get("stage") is None:
        st["stage"] = now          # the first look is silent
        st["stage_t"] = now_iso()
        mind.manifest.save()
        return now
    try:
        reached = int(st.get("stage") or 0)
    except (TypeError, ValueError):
        reached = 0
    if now <= reached:
        return reached
    for n in range(reached + 1, now + 1):
        ref, said = _carried_by(mind, n)
        text = _LEAD[n] + (" What carried me here: " + said if said else "")
        mind.stores["reflections"].append(
            make_record("r", {"kind": "inference", "ref": ref or "development"},
                        salience=0.7, text=text, kind="grew", stage=n))
    st["stage"] = now
    st["stage_t"] = now_iso()
    mind.manifest.save()
    return now


def _carried_by(mind, n):
    """The mind's own record that best shows what carried it to stage n."""
    from .inject import _clip
    try:
        if n == 1:
            felt = (mind.felt_doc.load(default={}) or {}).get("current") or {}
            return None, _clip(felt.get("text", ""), 180)
        if n == 2:
            learned = [r for r in mind.live("reflections") if r.get("kind") in LEARNED_KINDS]
            if learned:
                return learned[-1]["id"], _clip(learned[-1].get("text", ""), 180)
        if n == 3:
            hopes = [h for h in ((mind.story_doc.load(default={}) or {}).get("hopes") or [])
                     if isinstance(h, str) and h.strip()]
            if hopes:
                return None, _clip(hopes[0], 180)
        if n == 4:
            cur = (mind.story_doc.load(default={}) or {}).get("current") or {}
            return None, _clip(cur.get("text", ""), 180)
    except Exception:
        pass
    return None, ""
