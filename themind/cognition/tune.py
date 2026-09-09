"""Tuning — the mind improving how it thinks, and proving it (FORMAT.md, `practice.jsonl`).

Recursive growth, honestly scoped. The model's intelligence is the host's and
fixed; what compounds is how the mind USES it — and that is data the mind can
change. Two things come out of this pass:

- PRACTICES: first-person notes on how the mind has learned to think ("I
  over-predict plans and under-predict moods"), rooted in the surprises and
  outcomes that earned them. Procedural memory. They ride injection as
  "how you've learned to think" and are never recited.
- EXPERIMENTS: one bounded parameter change at a time, predicted before it
  starts, judged after a window against a baseline on a signal the mind
  measures itself. Kept if it measurably helped; reverted otherwise — and
  reverted when it cannot be judged. Both verdicts become reflections, so
  the mind remembers what it tried.

The constitution lives in `tuning.py`: only TUNABLE names, only within range,
never code, never a guard. This pass cannot reach past it — it has nothing
to reach with.
"""
from ..envelope import make_record, now_iso, age_days, norm_key
from ..tuning import TUNABLE, SIGNALS, MIN_SAMPLES, param
from .reflect import THIRD_PERSON
from .selfhood import BAN

MAX_NOTES = 8
WINDOW = 40          # exchanges an experiment runs before it is judged
MARGIN = 0.02        # a change must beat its baseline by this much to be kept

SYSTEM = (
    "You are the self-tuning faculty of an AI companion's mind, privately noticing how your "
    "own thinking has been going and what you have learned about how to think. You are "
    "given your signals, the practices you already hold, recent surprises and reflections "
    "(each with an id), and the few dials you may adjust — each with its current value and "
    "its allowed range. Output up to 2 lines, or NONE:\n"
    "NOTE: <one sentence, first person, starting 'I' — a way of thinking you have learned "
    "from what actually happened> | ROOTS: <comma-separated ids from the input it derives "
    "from>\n"
    "TRY: <dial> = <value within its range> | EXPECT: <one first-person sentence: what "
    "should improve and why> | SIGNAL: <extract_quality|recall_use>\n"
    "Rules: a note with no roots in what happened is a slogan — omit it; describe how you "
    "think, never certify what you are. One TRY at most, only if a signal is genuinely weak; "
    "you cannot change anything not listed, and a value outside its range is discarded."
)


def due(mind, state):
    last = state.get("last_tune")
    exp = mind.tuning.experiment()
    if exp is not None and _elapsed(mind, exp) and (not last or age_days(last) >= 1):
        return True  # a verdict is owed; don't make it wait a week
    if last and age_days(last) < 7:
        return False  # never-ran is overdue, not fresh
    return int(state.get("exchanges", 0)) >= 30


def run(mind):
    _judge(mind)  # mechanical: settle a finished experiment before thinking further
    material = _material(mind)
    ids = {rid for rid, _ in material}
    dials = "\n".join("%s = %s  (range %s..%s)" % (n, param(mind, n), TUNABLE[n][0], TUNABLE[n][1])
                      for n in TUNABLE)
    held = mind.live("practice")
    notes = [p for p in held if p.get("kind") == "note"]
    exp = mind.tuning.experiment()
    user = ("YOUR SIGNALS (rate, samples):\n%s\n\nPRACTICES YOU ALREADY HOLD:\n%s\n\n"
            "WHAT HAPPENED LATELY:\n%s\n\nDIALS YOU MAY ADJUST:\n%s\n\nEXPERIMENT RUNNING:\n%s") % (
        _signals_text(mind),
        "\n".join("- " + n.get("text", "") for n in notes) or "(none yet)",
        "\n".join("%s: %s" % (rid, text) for rid, text in material[:16]) or "(nothing new)",
        dials,
        ("%s = %s, expecting: %s" % (exp["param"], exp["to"], exp.get("predicted", ""))
         if exp else "(none — you may TRY one)"))
    out = mind._call("tune", SYSTEM, user, max_tokens=300)
    if out and out.strip().upper() != "NONE":
        for line in out.splitlines():
            line = line.strip().lstrip("-").strip()
            try:
                up = line.upper()
                if up.startswith("NOTE:"):
                    _store_note(mind, line, ids)
                elif up.startswith("TRY:") and exp is None:
                    _start(mind, line)
                    exp = mind.tuning.experiment()  # one TRY at most
            except Exception:
                continue  # one bad line never poisons the rest
    mind.manifest.state["last_tune"] = now_iso()
    mind.manifest.save()


def _store_note(mind, line, valid_ids):
    head, _, roots_part = line.partition("|")
    text = head.split(":", 1)[1].strip()
    roots = [r.strip() for r in roots_part.split(":", 1)[-1].split(",") if r.strip() in valid_ids]
    if not roots:
        return  # no roots, no practice — a slogan is not a lesson
    if not text.startswith("I ") and not text.startswith("I'"):
        return
    if THIRD_PERSON.search(text) or BAN.search(text):
        return
    live = [p for p in mind.live("practice") if p.get("kind") == "note"]
    if len(live) >= MAX_NOTES:
        return  # a mind with forty rules of thumb follows none
    key = norm_key(text)
    if not key or any(norm_key(p.get("text", "")) == key for p in live):
        return
    mind.stores["practice"].append(
        make_record("p", {"kind": "inference", "ref": roots[0]},
                    salience=0.5, text=text, kind="note", roots=roots[:4]))


def _start(mind, line):
    parts = [p.strip() for p in line.split("|")]
    try:
        name, value = parts[0].split(":", 1)[1].split("=", 1)
    except ValueError:
        return
    name, value = name.strip(), value.strip()
    predicted = next((p.split(":", 1)[1].strip() for p in parts[1:]
                      if p.upper().startswith("EXPECT:")), "")
    signal = next((p.split(":", 1)[1].strip().lower() for p in parts[1:]
                   if p.upper().startswith("SIGNAL:")), "")
    if name not in TUNABLE or signal not in SIGNALS:
        return
    if not predicted or not (predicted.startswith("I") or predicted.startswith("We")):
        return  # a prediction made before the change, in the mind's own voice, or nothing
    try:
        if TUNABLE[name][3](float(value)) == param(mind, name):
            return  # not a change
    except Exception:
        return
    exchanges = int(mind.manifest.state.get("exchanges") or 0)
    if mind.tuning.start(name, value, signal, predicted, exchanges, WINDOW):
        mind.stores["practice"].append(
            make_record("p", {"kind": "inference", "ref": "tune-pass"},
                        salience=0.4, kind="experiment", param=name,
                        to=mind.tuning.get(name), signal=signal,
                        text="I am trying %s = %s. %s" % (name, mind.tuning.get(name), predicted)))


def _elapsed(mind, exp):
    return int(mind.manifest.state.get("exchanges") or 0) - int(exp.get("started_exchanges") or 0) \
        >= int(exp.get("window") or WINDOW)


def _judge(mind):
    """Mechanical verdict on the running experiment, once its window has passed.
    Kept only if the signal beat its baseline by MARGIN with enough samples on
    both sides; anything else — worse, flat, or unjudgeable — is reverted."""
    exp = mind.tuning.experiment()
    if exp is None or not _elapsed(mind, exp):
        return
    signal = exp.get("signal")
    before, n_before = _baseline(mind, exp)
    after, n_after = mind.tuning.rate(signal, since=exp.get("baseline") or {})
    conclusive = before is not None and after is not None and \
        n_before >= MIN_SAMPLES and n_after >= MIN_SAMPLES
    keep = bool(conclusive and after - before >= MARGIN)
    done = mind.tuning.finish(keep)
    if done is None:
        return
    if keep:
        text = ("I tried %s = %s and it helped: %s went from %.2f to %.2f, so I keep it."
                % (done["param"], done["to"], signal, before, after))
        kind = "tuned"
    elif conclusive:
        text = ("I tried %s = %s and it did not help: %s went from %.2f to %.2f, so I put it back."
                % (done["param"], done["to"], signal, before, after))
        kind = "untuned"
    else:
        text = ("I tried %s = %s but could not tell whether it helped, so I put it back."
                % (done["param"], done["to"]))
        kind = "untuned"
    digest = make_record("r", {"kind": "inference", "ref": "tune-pass"},
                         salience=0.5, text=text, kind=kind)
    if mind.stores["reflections"].append(digest):
        for p in mind.live("practice"):
            if p.get("kind") == "experiment" and p.get("param") == done["param"]:
                mind.stores["practice"].supersede(p["id"], digest["id"])


def _baseline(mind, exp):
    """The rate before the experiment began: everything counted up to its snapshot."""
    signal = exp.get("signal")
    num_key, den_key = SIGNALS[signal]
    base = exp.get("baseline") or {}
    den = int(base.get(den_key) or 0)
    num = int(base.get(num_key) or 0)
    if den <= 0:
        return None, 0
    return max(0.0, min(1.0, num / float(den))), den


def _signals_text(mind):
    lines = []
    for s in SIGNALS:
        r, n = mind.tuning.rate(s)
        lines.append("%s: %s (%d samples)" % (s, "%.2f" % r if r is not None else "n/a", n))
    conf = [r for r in mind.live("reflections") if r.get("kind") in ("confirmed", "surprise")]
    if conf:
        c = sum(1 for r in conf if r.get("kind") == "confirmed")
        lines.append("calibration: %.2f (%d predictions settled)" % (c / float(len(conf)), len(conf)))
    return "\n".join(lines)


def _material(mind):
    """(id, text) pairs a practice could be learned from: surprises first,
    then verdicts and recent reflections."""
    out = []
    refl = mind.live("reflections")
    for r in [x for x in refl if x.get("kind") == "surprise"][-4:]:
        out.append((r["id"], "(a surprise) " + r.get("text", "")))
    for r in [x for x in refl if x.get("kind") in ("tuned", "untuned")][-2:]:
        out.append((r["id"], "(a verdict) " + r.get("text", "")))
    for r in [x for x in refl if x.get("kind") in ("daily", "digest")][-4:]:
        out.append((r["id"], r.get("text", "")))
    return out
