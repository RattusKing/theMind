"""Expectations — the mind predicts, and being wrong is the signal.

Predictive processing in one sentence: a mind is a model of its world, run
forward, that learns most from its errors. So the lifecycle enforces the
asymmetry that matters (FORMAT.md, `expectations.jsonl`): a CONFIRMED
expectation fades into a low-salience reflection — the unsurprising is
forgettable — while a SURPRISED one becomes a HIGH-salience reflection
carrying what actually happened, loud enough to color the mind's weather and
future recall. Prediction error is what deserves thought.

The provenance rule holds here as everywhere: no roots among held records,
no prediction — an expectation with no basis is a guess wearing a costume.
"""
from ..envelope import make_record, now_iso, age_days, norm_key
from ..retrieval import _words

MAX_LIVE = 6
TOUCH_OVERLAP = 2   # content words an exchange must share to test a prediction
TOUCH_BUMP = 0.06
SURPRISE_SALIENCE = 0.85   # loud: error is the signal
CONFIRM_SALIENCE = 0.25    # quiet: the unsurprising is forgettable

SYSTEM = (
    "You are the predicting faculty of an AI companion's mind, privately running your "
    "model of one person forward. You are given what you hold (each item with an id) and "
    "the expectations you already carry. Output up to 2 lines, or NONE:\n"
    "EXPECT: <one sentence, first person, starting 'I expect' — something you genuinely "
    "anticipate about them or your shared life> | ROOTS: <comma-separated ids from the "
    "input it derives from>\n"
    "For an expectation the material now settles, one line:\n"
    "CONFIRMED: <expectation id>\n"
    "SURPRISED: <expectation id> | ACTUALLY: <one first-person sentence on what happened "
    "instead>\n"
    "Rules: an expectation with no roots in what you hold is a guess wearing a costume — "
    "omit it. Predict the checkable, never the flattering; being wrong is worth more to "
    "you than being right."
)


def due(mind, state):
    if age_days(state.get("last_expect") or "") < 2:
        return False
    if int(state.get("exchanges", 0)) < 6:
        return False
    return bool(_material(mind))


def run(mind):
    material = _material(mind)
    if not material:
        return
    ids = {rid for rid, _ in material}
    listing = "\n".join("%s: %s" % (rid, text) for rid, text in material[:20])
    live = mind.live("expectations")
    carried = "\n".join("%s: %s" % (x["id"], x.get("text", "")) for x in live) or "(none yet)"
    out = mind._call("expect", SYSTEM,
                     "WHAT YOU HOLD:\n%s\n\nEXPECTATIONS YOU ALREADY CARRY:\n%s"
                     % (listing, carried),
                     max_tokens=300)
    if out and out.strip().upper() != "NONE":
        for line in out.splitlines():
            line = line.strip().lstrip("-").strip()
            try:
                up = line.upper()
                if up.startswith("EXPECT:"):
                    _store(mind, line, ids)
                elif up.startswith("CONFIRMED:"):
                    _settle(mind, line.split(":", 1)[1].strip(), note=None)
                elif up.startswith("SURPRISED:") and "|" in line:
                    _settle(mind, line.split(":", 1)[1].split("|")[0].strip(),
                            note=line.split("|", 1)[1].split(":", 1)[-1].strip())
            except Exception:
                continue  # one bad line never poisons the rest
    mind.manifest.state["last_expect"] = now_iso()
    mind.manifest.save()


def _store(mind, line, valid_ids):
    head, _, roots_part = line.partition("|")
    text = head.split(":", 1)[1].strip()
    roots = [r.strip() for r in roots_part.split(":", 1)[-1].split(",") if r.strip() in valid_ids]
    if not roots:
        return  # no roots, no prediction
    if not text.startswith("I "):
        return
    live = mind.live("expectations")
    if len(live) >= MAX_LIVE:
        return  # a mind expecting everything expects nothing
    key = norm_key(text)
    if not key or any(norm_key(x.get("text", "")) == key for x in live):
        return
    mind.stores["expectations"].append(
        make_record("x", {"kind": "inference", "ref": roots[0]},
                    salience=0.5, text=text, roots=roots[:4]))


def _settle(mind, exp_id, note):
    exp = next((x for x in mind.live("expectations") if x.get("id") == exp_id), None)
    if exp is None:
        return
    if note is not None:
        if not note or not (note.startswith("I") or note.startswith("We")):
            return  # what-actually-happened must be the mind's own voice
        text = "I expected: %s Instead: %s" % (exp.get("text", ""), note)
        kind, salience = "surprise", SURPRISE_SALIENCE
    else:
        text = "As I expected: %s" % exp.get("text", "")
        kind, salience = "confirmed", CONFIRM_SALIENCE
    digest = make_record("r", {"kind": "record", "ref": exp_id},
                         salience=salience, text=text, kind=kind)
    if mind.stores["reflections"].append(digest):
        mind.stores["expectations"].supersede(exp_id, digest["id"])


def touch(mind, user_text, assistant_text):
    """Mechanical (no model call): attention goes where predictions are being
    tested — an exchange sharing real words with an expectation strengthens it."""
    words = _words((user_text or "") + " " + (assistant_text or ""))
    if not words:
        return
    recs = mind.live("expectations")
    changed = False
    for r in recs:
        if len(words & _words(r.get("text", ""))) >= TOUCH_OVERLAP:
            r["salience"] = min(1.0, round(r.get("salience", 0.5) + TOUCH_BUMP, 4))
            changed = True
    if changed:
        mind.stores["expectations"].rewrite(recs)


def _material(mind):
    """(id, text) pairs a prediction could derive from."""
    out = []
    for f in mind.live("facts")[-8:]:
        if f.get("text"):
            out.append((f["id"], "(about them) " + f["text"]))
    for store, label in (("aches", "(still open) "), ("desires", "(they want) "),
                         ("own_desires", "(you want) "), ("tensions", "(a tension) ")):
        for r in mind.live(store)[-3:]:
            if r.get("text"):
                out.append((r["id"], label + r["text"]))
    return out
