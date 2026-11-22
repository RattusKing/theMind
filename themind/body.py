"""A body: what it lives through, where, and how its body is (format 0.13).

Until now everything this mind knew arrived as words: what someone told it,
and what it said back. A mind with a body lives through things nobody says.
Sam walks in. The room goes dark. It is picked up. Its battery runs low in
the garden. This gives those a place, under the same contracts as
everything else it keeps.

- **Provenance still holds.** An experience persists only with the body's
  own report as its evidence: `src.kind` "sensed", the report verbatim as
  the quote, the sense that made it as the ref. It can no more invent having
  been in the kitchen than invent being told something.
- **theMind never moves the body.** It is told what happened; it commands
  nothing. What the body does is the host's, the way sending a message
  first is the host's.
- **What happened around someone stays with the people who were there.** An
  experience with people present is served to them and to no one else.
- **A flood earns nothing.** The same report again within minutes
  strengthens what is held instead of adding to it, and an hour can only add
  so much.
- **An easy body is a quiet one.** A reading is felt only when it is working
  or strained, and only while it is fresh: a battery level from yesterday
  says nothing about now.
"""
from datetime import datetime, timezone

from .envelope import make_record, now_iso, parse_iso, age_days, norm_key, ago
from .people import norm_who

KINDS = ("saw", "heard", "touched", "did", "felt", "arrived", "left", "happened")
_KIND_ALIASES = {"see": "saw", "seen": "saw", "hear": "heard", "touch": "touched",
                 "do": "did", "done": "did", "feel": "felt", "arrive": "arrived",
                 "leave": "left", "happen": "happened"}

MAX_TEXT = 300            # an experience is a moment, not a transcript
REPEAT_MINUTES = 15       # the same report again this soon strengthens what is held
PER_HOUR = 120            # what an hour can add; a sensor stream is not a life
MAX_LIVE = 500            # past this, the faintest old experiences fade to the archive
PLACE_FRESH_HOURS = 12    # past this, where it last was is no longer where it is
VISIT_GAP_HOURS = 3       # back at the same place after this long is a new visit
BODY_FRESH_MINUTES = 30   # past this, a reading no longer says how the body is

# Each body signal reads 0..1. Energy is good when high; the rest are good
# when low. (working, strained) thresholds, and how each level feels.
SIGNALS = {
    "energy": {"low_is_bad": True, "working": 0.35, "strained": 0.15,
               "notes": ("my energy is running low", "my energy is nearly gone"),
               "crossed": ("My energy ran very low.", "My energy came back.")},
    "heat": {"low_is_bad": False, "working": 0.65, "strained": 0.85,
             "notes": ("I am running warm", "I am running hot, close to my limit"),
             "crossed": ("I ran hot, close to my limit.", "I cooled down again.")},
    "strain": {"low_is_bad": False, "working": 0.65, "strained": 0.85,
               "notes": ("my body is working hard", "my body is working at its limit"),
               "crossed": ("My body worked at its limit.", "The strain on my body eased.")},
    "damage": {"low_is_bad": False, "working": 0.2, "strained": 0.5,
               "notes": ("something in my body is not quite right",
                         "part of me is damaged and not working as it should"),
               "crossed": ("Part of me was damaged.", "The damage in me was mended.")},
}
_SIGNAL_ALIASES = {"battery": "energy", "charge": "energy", "power": "energy",
                   "temperature": "heat", "load": "strain", "effort": "strain"}


# ── small readers ────────────────────────────────────────────────────────────
def _clean(text, n=MAX_TEXT):
    from .inject import _clip
    return _clip(" ".join(str(text or "").split()), n)


def _kind(kind):
    k = str(kind or "").strip().lower()
    k = _KIND_ALIASES.get(k, k)
    return k if k in KINDS else "happened"


def _source(source):
    s = "".join(ch if (ch.isalnum() or ch in " -_.:/") else " " for ch in str(source or "body"))
    return " ".join(s.split())[:40] or "body"


def _when(at):
    """The moment it happened: the host's timestamp if it is a real one
    (a body may report in batches), else now. Never the future."""
    dt = parse_iso(at) if isinstance(at, str) else None
    if dt is None:
        return now_iso()
    now = datetime.now(timezone.utc)
    if (dt - now).total_seconds() > 300 or (now - dt).days > 365:
        return now_iso()
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _value(v):
    try:
        v = float(v)
    except Exception:
        return None
    if v != v:          # NaN
        return None
    if 1.0 < v <= 100.0:
        v = v / 100.0   # a percentage
    return max(0.0, min(1.0, v))


def visible(rec, who):
    """An experience with people present is theirs to hear about. One with
    nobody present is the mind's own."""
    present = rec.get("with")
    return not present or (who or None) in present


# ── places ───────────────────────────────────────────────────────────────────
def _places(mind):
    doc = mind.places_doc.load(default={}) or {}
    if not isinstance(doc.get("places"), dict):
        doc["places"] = {}
    return doc


def place_name(mind, key, doc=None):
    if not key:
        return None
    doc = doc or _places(mind)
    return (doc["places"].get(key) or {}).get("name") or key


def _arrive(mind, where, t):
    key = norm_who(where)
    if not key:
        return None
    doc = _places(mind)
    p = doc["places"].get(key)
    if p is None:
        p = doc["places"][key] = {"name": " ".join(str(where).split())[:60],
                                  "first_t": t, "last_t": None, "visits": 0}
    last = p.get("last_t")
    if doc.get("here") != key or not last or age_days(last) * 24.0 >= VISIT_GAP_HOURS:
        p["visits"] = int(p.get("visits") or 0) + 1
    if not last or t >= last:
        p["last_t"] = t
    if not doc.get("here_t") or t >= doc["here_t"]:
        doc["here"], doc["here_t"] = key, t
    mind.places_doc.save(doc)
    return key


def here(mind):
    """Where it is now, if it knows: {key, name, visits, first_t, since}."""
    doc = _places(mind)
    key, t = doc.get("here"), doc.get("here_t")
    if not key or not t or age_days(t) * 24.0 > PLACE_FRESH_HOURS:
        return None
    p = doc["places"].get(key) or {}
    return {"key": key, "name": p.get("name") or key, "visits": int(p.get("visits") or 0),
            "first_t": p.get("first_t"), "since": t}


def known_places(mind):
    """Every place it has been, most visited first."""
    doc = _places(mind)
    rows = [dict(v, key=k) for k, v in doc["places"].items() if isinstance(v, dict)]
    rows.sort(key=lambda p: (-int(p.get("visits") or 0), p.get("first_t") or ""))
    return rows


# ── experiences ──────────────────────────────────────────────────────────────
def experience(mind, what, kind=None, where=None, present=None, source=None,
               intensity=None, entities=None, at=None):
    """Record something it lived through. Returns the record's id, or None
    when there was nothing to keep (empty, or the hour is full)."""
    return _record(mind, _clean(what), None, kind, where, present, source, intensity,
                   entities, at)


def _record(mind, text, quote, kind, where, present, source, intensity, entities, at):
    if not text:
        return None
    kind = _kind(kind)
    t = _when(at)
    store = mind.stores["experiences"]
    recs = store.load()
    tail = recs[-PER_HOUR * 2:]
    if sum(1 for r in tail if age_days(r.get("t")) * 24.0 < 1.0) >= PER_HOUR:
        return None
    place = norm_who(where) if where else None
    key = norm_key(text)
    for r in reversed(tail):
        if (r.get("kind") == kind and r.get("where") == place and norm_key(r.get("text")) == key
                and abs(age_days(r.get("last_t") or r.get("t")) - age_days(t)) * 1440.0
                < REPEAT_MINUTES):
            # The same thing again, this soon: it matters more, it is not two things.
            r["times"] = int(r.get("times") or 1) + 1
            r["salience"] = round(min(1.0, float(r.get("salience") or 0.5) + 0.03), 4)
            r["last_t"] = max(t, r.get("last_t") or r.get("t"))
            store.rewrite(recs)
            if place:
                _arrive(mind, where, t)
            return r["id"]
    try:
        strength = float(intensity) if intensity is not None else 0.4
    except Exception:
        strength = 0.4
    strength = max(0.0, min(1.0, strength))
    fields = {"text": text, "kind": kind, "times": 1}
    if place:
        fields["where"] = _arrive(mind, where, t)
    if present:
        names = present if isinstance(present, (list, tuple)) else [present]
        keys = []
        for n in names:
            if isinstance(n, str) and n.strip():
                # The learning path: like the first voice it hears, the first
                # person its body is ever with becomes the primary.
                k = mind.people.resolve(n, bind=True)
                mind.people.note_seen(k, n)
                if k not in keys:
                    keys.append(k)
        if keys:
            fields["with"] = keys
    ents = [" ".join(str(e).split())[:40] for e in (entities or [])
            if isinstance(e, str) and e.strip()][:5]
    if ents:
        fields["entities"] = ents
    rec = make_record("x", {"kind": "sensed", "quote": (quote or text)[:MAX_TEXT],
                            "ref": _source(source)},
                      salience=0.35 + 0.4 * strength, **fields)
    rec["t"] = t
    if not store.append(rec):
        return None
    labels = list(ents)
    if place:
        labels.append(place_name(mind, place))
    if labels:
        mind.graph.touch(labels, src_ref=rec["id"])
    _fade(mind, store)
    return rec["id"]


def _fade(mind, store):
    """Past the ceiling, the faintest of the oldest experiences move to the
    archive. Nothing is deleted; it is simply no longer close to hand."""
    recs = store.load()
    over = len(recs) - MAX_LIVE
    if over <= 0:
        return
    oldest = sorted(recs, key=lambda r: r.get("t", ""))[:max(over * 4, 20)]
    for r in sorted(oldest, key=lambda r: (float(r.get("salience") or 0), r.get("t", "")))[:over]:
        store.retire(r["id"], "faded")


def lived(mind, who=None):
    """Every experience this speaker may hear about, oldest first."""
    recs = [r for r in mind.live("experiences") if visible(r, who)]
    return recs


def describe(mind, rec, who=None, doc=None):
    """'Sam walked in (kitchen, with Sam, 2 hours ago)'."""
    parts = []
    if rec.get("where"):
        parts.append(place_name(mind, rec["where"], doc))
    names = [mind.people.display(k) for k in (rec.get("with") or [])]
    if names:
        parts.append("with " + ", ".join(names))
    if int(rec.get("times") or 1) > 1:
        parts.append("%d times" % int(rec["times"]))
    a = ago(rec.get("t"))
    if a:
        parts.append(a)
    return rec.get("text", "") + (" (%s)" % ", ".join(parts) if parts else "")


# ── the body's condition ─────────────────────────────────────────────────────
def level_of(name, value):
    spec = SIGNALS[name]
    if spec["low_is_bad"]:
        if value <= spec["strained"]:
            return "strained"
        if value <= spec["working"]:
            return "working"
        return "easy"
    if value >= spec["strained"]:
        return "strained"
    if value >= spec["working"]:
        return "working"
    return "easy"


def sense(mind, readings, at=None):
    """Take the body's readings. A reading that crosses into strain, or
    comes all the way back from it, is also something it lived through."""
    if not isinstance(readings, dict):
        return read(mind)
    t = _when(at)
    doc = mind.body_doc.load(default={}) or {}
    signals = doc.get("signals") if isinstance(doc.get("signals"), dict) else {}
    levels = doc.get("levels") if isinstance(doc.get("levels"), dict) else {}
    crossings = []
    for raw, v in readings.items():
        name = _SIGNAL_ALIASES.get(str(raw).strip().lower(), str(raw).strip().lower())
        if name not in SIGNALS:
            continue
        value = _value(v)
        if value is None:
            continue
        signals[name] = {"value": round(value, 4), "t": t}
        level, before = level_of(name, value), levels.get(name)
        if level == "strained" and before != "strained":
            crossings.append((name, 0, value))
        elif level == "easy" and before == "strained":
            crossings.append((name, 1, value))
        levels[name] = level
    doc["signals"], doc["levels"] = signals, levels
    mind.body_doc.save(doc)
    spot = here(mind)
    for name, which, value in crossings:
        _record(mind, SIGNALS[name]["crossed"][which], "%s %.2f" % (name, value), "felt",
                spot["name"] if spot else None, None, "body",
                0.8 if which == 0 else 0.4, None, t)
    return read(mind)


def read(mind):
    """[(signal, level, note)] for every fresh reading, worst first."""
    doc = mind.body_doc.load(default={}) or {}
    signals = doc.get("signals") if isinstance(doc.get("signals"), dict) else {}
    out = []
    for name, spec in SIGNALS.items():
        s = signals.get(name)
        if not isinstance(s, dict) or s.get("value") is None:
            continue
        if age_days(s.get("t")) * 1440.0 > BODY_FRESH_MINUTES:
            continue
        level = level_of(name, float(s["value"]))
        note = {"working": spec["notes"][0], "strained": spec["notes"][1]}.get(level, "")
        out.append(("body " + name, level, note))
    rank = {"strained": 0, "working": 1, "easy": 2}
    out.sort(key=lambda row: rank.get(row[1], 9))
    return out


def felt(mind):
    """Only what is working or strained."""
    return [row for row in read(mind) if row[1] in ("working", "strained")]
