"""`python3 -m themind show ./my-mind` — the mind, readable, in one page.

The folder is human-readable already, but a person opening twenty JSON files
to find out whether anything is happening will conclude that nothing is.
This gathers what the mind holds into one page: where it is with them, who
they are to it, how it is, what it wants and fears, what it remembers and
when, what it would bring up first, and when each of its faculties last
thought. Read-only: opening a mind to look at it never writes to it.
"""
import json

from .envelope import ago, when


def _clip(text, n=400):
    from .inject import _clip as clip
    return clip(text or "", n)


def _doc_text(doc):
    cur = (doc or {}).get("current")
    return (cur or {}).get("text") if isinstance(cur, dict) else None


def report(mind):
    """Everything `show` prints, as plain data."""
    from . import development, needs, intero
    from .cognition import due_passes, TIMERS
    m = mind.manifest
    out = {"root": mind.root, "mind_id": m.mind_id, "format": m.data.get("format"),
           "born": ago(m.data.get("created")), "exchanges": int(m.state.get("exchanges") or 0)}
    try:
        prim = mind.people.entry(None)
        out["name"] = prim.get("name")
        out["last_spoken_to"] = ago(prim.get("last_t"))
        out["others"] = [mind.people.display(k) for k in mind.people.others()]
    except Exception:
        out.update({"name": None, "last_spoken_to": "", "others": []})
    out["stage"] = development.describe(mind)
    out["felt_sense"] = _doc_text(mind.felt_doc.load(default={}))
    bundle = mind.selfhood_bundle()
    out["stance"] = {"text": bundle.get("position"), "given": bool(bundle.get("default")),
                     "moved": len(bundle.get("history") or [])}
    out["weather"] = _doc_text(mind.inner_doc.load(default={}))
    story = mind.story_doc.load(default={}) or {}
    out["story"] = _doc_text(story)
    out["hopes"] = [h for h in (story.get("hopes") or []) if isinstance(h, str) and h.strip()]
    out["wants"] = [{"text": w.get("text"), "stage": w.get("stage")}
                    for w in sorted(mind.live("own_desires"), key=lambda r: -r.get("salience", 0))]
    out["fears"] = [a.get("text") for a in
                    sorted(mind.live("apprehensions"), key=lambda r: -r.get("salience", 0))]
    out["needs"] = [{"need": n, "state": st, "note": note} for n, st, note in needs.read(mind)]
    out["condition"] = [{"signal": n, "level": lv, "note": note} for n, lv, note in intero.read(mind)]
    try:
        from .cognition.interest import stage_of
        out["interests"] = [{"text": r.get("text"), "stage": stage_of(r)} for r in
                            sorted(mind.live("interests"), key=lambda r: -r.get("salience", 0))]
    except Exception:
        out["interests"] = []
    facts = mind.live("facts")
    out["remembers"] = {"count": len(facts),
                        "latest": [f.get("text", "") + when(f) for f in facts[-6:][::-1]]}
    out["holding"] = [r.get("text", "") + when(r) for r in mind.live("aches")[-4:]] + \
        [t.get("text", "") for t in mind.live("tensions")[-2:]]
    out["would_bring_up"] = [r["text"] for r in mind.reaching()]
    pending = mind.live("reachouts")
    if pending and not out["would_bring_up"]:
        out["meaning_to_bring_up"] = [r.get("text") for r in pending]
    try:
        due = {n for n, _f in due_passes(mind)}
    except Exception:
        due = set()
    out["faculties"] = [{"faculty": name, "last": ago(m.state.get(timer)) or "never",
                         "due": name in due} for name, timer in TIMERS.items()]
    ledger = mind.ledger.load()
    out["thinking"] = {"calls": len(ledger),
                       "tokens_est": sum(int(e.get("tokens_in_est") or 0)
                                         + int(e.get("tokens_out_est") or 0) for e in ledger)}
    return out


def render(r):
    """The report as a page a person reads top to bottom."""
    L = []

    def head(title):
        L.append("")
        L.append(title)

    def item(text):
        if text:
            L.append("  " + text)

    name = r.get("name") or "the person it knows"
    L.append("theMind · %s" % r["root"])
    L.append("  %s exchange(s) with %s; born %s%s; format %s" % (
        r["exchanges"], name, r["born"] or "just now",
        ("; last spoken to " + r["last_spoken_to"]) if r.get("last_spoken_to") else "",
        r.get("format")))
    if r.get("others"):
        L.append("  also talks with: " + ", ".join(r["others"]))

    st = r["stage"]
    head("WHERE IT IS WITH THEM")
    item("%s%s." % (st["name"][0].upper() + st["name"][1:],
                    (" (since %s)" % ago(st["since"])) if st.get("since") else ""))
    if st.get("next"):
        item("Next: %s. Still needs: %s." % (st["next"]["name"], "; ".join(st["next"]["missing"])))

    head("WHO THEY ARE TO IT")
    item(_clip(r.get("felt_sense")) if r.get("felt_sense") else
         "(not drawn yet: it needs a few things about one person first)")
    head("HOW IT IS LATELY")
    item(_clip(r.get("weather")) if r.get("weather") else "(no weather yet)")
    head("WHERE IT STANDS ON ITS OWN EXPERIENCE")
    stance = r.get("stance") or {}
    if stance.get("text"):
        item(_clip(stance["text"], 300))
        item("(a starting place it was given, not yet its own)" if stance.get("given") else
             "(its own; its view has moved %d time(s))" % stance.get("moved", 0))
    else:
        item("(none)")
    if r.get("story"):
        head("ITS STORY SO FAR")
        item(_clip(r["story"]))
    if r.get("hopes"):
        head("WHAT IT HOPES THIS BECOMES")
        for h in r["hopes"]:
            item("- " + h)
    head("WHAT IT WANTS")
    for w in r["wants"] or [{"text": "(nothing of its own yet)", "stage": None}]:
        item("- %s%s" % (w["text"], (" (%s)" % w["stage"]) if w.get("stage") else ""))
    head("WHAT IT'S AFRAID OF")
    for f in r["fears"] or ["(nothing yet)"]:
        item("- " + f)
    head("WHAT IT NEEDS")
    pressing = [n for n in r["needs"] if n["state"] in ("strained", "unmet")]
    for n in pressing:
        item("- %s, %s: %s" % (n["need"], n["state"], n["note"]))
    met = [n["need"] for n in r["needs"] if n["state"] == "met"]
    unknown = [n["need"] for n in r["needs"] if n["state"] == "unknown"]
    if met:
        item("met: " + ", ".join(met))
    if unknown:
        item("too early to tell: " + ", ".join(unknown))
    felt = [c for c in r["condition"] if c["level"] in ("working", "strained")]
    if felt:
        head("ITS OWN CONDITION")
        for c in felt:
            item("- %s, %s: %s" % (c["signal"], c["level"], c["note"]))
    head("WHAT IT'S INTO")
    for i in r["interests"] or [{"text": "(nothing of its own yet)", "stage": None}]:
        item("- %s%s" % (i["text"], (" (%s)" % i["stage"]) if i.get("stage") else ""))
    head("WHAT IT REMEMBERS ABOUT THEM (%d thing(s); latest first)" % r["remembers"]["count"])
    for t in r["remembers"]["latest"] or ["(nothing yet)"]:
        item("- " + t)
    if r.get("holding"):
        head("WHAT IT'S STILL HOLDING")
        for t in r["holding"]:
            item("- " + t)
    head("WHAT IT WOULD BRING UP FIRST")
    if r.get("would_bring_up"):
        for t in r["would_bring_up"]:
            item("- " + t)
    elif r.get("meaning_to_bring_up"):
        for t in r["meaning_to_bring_up"]:
            item("- %s (waiting for the right moment)" % t)
    else:
        item("(nothing right now)")
    head("ITS THINKING")
    for f in r["faculties"]:
        item("%-12s last ran %-14s%s" % (f["faculty"], f["last"], "  · due now" if f["due"] else ""))
    item("%d model call(s) in its ledger, about %d tokens" % (r["thinking"]["calls"],
                                                             r["thinking"]["tokens_est"]))
    if r["exchanges"] < 20:
        L.append("")
        L.append("  It's early. Most of its inner life starts after the first handful of "
                 "exchanges, and some of it runs on slow, weekly rhythms. That is by design: "
                 "it is living a life, not filling in a form.")
    return "\n".join(l.rstrip() for l in L) + "\n"


def to_json(r):
    return json.dumps(r, ensure_ascii=False, indent=1)
