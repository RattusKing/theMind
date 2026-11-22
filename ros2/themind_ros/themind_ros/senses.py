"""What the robot's senses report, turned into what the mind lives through.

This half of the bridge knows nothing about ROS. It takes plain values (a
battery percentage, a place name, a list of who is in the room, a line of
JSON) and turns them into calls on a `themind.Mind`, so it can be tested
anywhere and reused under any robot framework. `bridge.py` is the thin ROS 2
node around it.

The same contracts as the rest of theMind hold here:
- It is told, never guesses. A speaker nobody names is the person the mind
  usually talks with, and a reading it cannot read is ignored, not imagined.
- It never moves anything. Nothing here publishes a command to the body.
- What happened around someone stays with the people who were there: every
  moment carries who was in the room when it happened.
"""
import json
import math


def _names(value):
    """A list of names from a JSON list, a comma-separated string, or a list."""
    if isinstance(value, str):
        text = value.strip()
        if text.startswith(("[", "{")):
            try:
                value = json.loads(text)   # an object, or broken JSON, is not a list of names
            except Exception:
                return None
        else:
            value = [n for n in text.split(",")]
    if not isinstance(value, (list, tuple)):
        return None
    out = []
    for n in value:
        if isinstance(n, str) and n.strip() and n.strip() not in out:
            out.append(n.strip()[:80])
    return out


def _payload(text):
    """A message's text as a dict: JSON when it is a JSON object, else the
    plain words as {"text": ...}. Broken JSON is nothing, not words."""
    text = (text or "").strip()
    if not text:
        return None
    if text.startswith("{"):
        try:
            data = json.loads(text)
        except Exception:
            return None
        return data if isinstance(data, dict) else None
    return {"text": text}


def _at_place(name):
    """'kitchen' -> 'the kitchen'; 'the porch' and 'Ana's room' stay as they are."""
    low = name.lower()
    if low.startswith(("the ", "a ", "an ")) or name[:1].isupper():
        return name
    return "the " + name


class Senses:
    """One robot's senses, feeding one mind. Holds only what the senses last
    said: where it is, who is in the room, and what it was last told."""

    def __init__(self, mind, prefix="ros2"):
        self.mind = mind
        self.prefix = prefix
        self.where = None
        self.present = []
        self.heard = None      # (who, text): said to it, waiting for its reply
        self.offered = None    # the reach-out last offered, by id

    def _source(self, topic):
        return "%s:%s" % (self.prefix, topic) if topic else self.prefix

    # ── the body ─────────────────────────────────────────────────────────────
    def battery(self, percentage):
        """sensor_msgs/BatteryState.percentage: 0..1, NaN when unknown."""
        try:
            value = float(percentage)
        except Exception:
            return None
        if math.isnan(value) or math.isinf(value) or value < 0:
            return None
        return self.mind.sense_body({"energy": value})

    def body(self, text):
        """A JSON object of readings: {"energy", "heat", "strain", "damage"}."""
        data = _payload(text)
        if not data or "text" in data and len(data) == 1:
            return None
        return self.mind.sense_body(data)

    # ── the world ────────────────────────────────────────────────────────────
    def place(self, name, topic="/themind/place"):
        """Where the robot is now. Arriving somewhere new is a moment of its
        own; being told the same place again is not."""
        name = " ".join(str(name or "").split())[:60]
        if not name or name == self.where:
            return None
        self.where = name
        return self.mind.experience("I arrived at %s." % _at_place(name), kind="arrived",
                                    where=name, present=self.present or None,
                                    source=self._source(topic))

    def people(self, value, topic="/themind/present"):
        """Who is in the room now, from whatever recognizes them. Someone
        coming in or leaving is a moment, shared with whoever was there."""
        names = _names(value)
        if names is None:
            return []
        came = [n for n in names if n not in self.present]
        went = [n for n in self.present if n not in names]
        before = list(self.present)
        self.present = names
        ids = []
        for n in came:
            ids.append(self.mind.experience("%s came in." % n, kind="arrived", where=self.where,
                                            present=names, source=self._source(topic)))
        for n in went:
            ids.append(self.mind.experience("%s left." % n, kind="left", where=self.where,
                                            present=before, source=self._source(topic)))
        return ids

    def experience(self, text, topic="/themind/experience"):
        """A moment, as plain words or a JSON object with text, kind, where,
        with, intensity and entities. Where and who default to what the senses
        last said; a moment that says where it happened says where the body is."""
        data = _payload(text)
        if not data:
            return None
        what = data.get("text") or data.get("what")
        if not isinstance(what, str) or not what.strip():
            return None
        present = _names(data["with"]) if "with" in data else (self.present or None)
        where = data.get("where") if isinstance(data.get("where"), str) else self.where
        if where and where.strip():
            self.where = " ".join(where.split())[:60]   # it happened to the body, so the body was there
        ents = data.get("entities") if isinstance(data.get("entities"), list) else None
        return self.mind.experience(what, kind=data.get("kind"), where=where, present=present,
                                    source=data.get("source") if isinstance(data.get("source"), str)
                                    else self._source(topic),
                                    intensity=data.get("intensity"), entities=ents,
                                    at=data.get("at") if isinstance(data.get("at"), str) else None)

    # ── talking ──────────────────────────────────────────────────────────────
    def hear(self, text):
        """Someone said something to it: plain words, or {"who", "text"}.
        Returns what the robot's dialogue should add to its system prompt:
        {"who", "heard", "context"}, or None."""
        data = _payload(text)
        if not data or not isinstance(data.get("text"), str) or not data["text"].strip():
            return None
        who = data.get("who") if isinstance(data.get("who"), str) and data["who"].strip() else None
        said = data["text"].strip()
        self.heard = (who, said)
        return {"who": who, "heard": said, "context": self.mind.context(said, who=who)}

    def said(self, text):
        """What the robot said aloud: plain words, or {"text", "reach_id"}.
        A reply to what it heard is learned from; something it brought up
        first is remembered as having been said."""
        data = _payload(text)
        if not data or not isinstance(data.get("text"), str) or not data["text"].strip():
            return None
        words = data["text"].strip()
        rid = data.get("reach_id") or (self.offered if self.heard is None else None)
        if self.heard is not None:
            who, heard = self.heard
            self.heard = None
            self.mind.observe(heard, words, who=who)
            return "observed"
        if rid and self.mind.reached(rid, words):
            self.offered = None
            return "reached"
        return None

    def reach(self):
        """Something it would bring up first, to the one person in the room,
        as {"id", "text", "kind", "who", "messages"}: only when exactly one
        person is there to say it to, and only once per offer."""
        if len(self.present) != 1:
            return None
        who = self.present[0]
        r = self.mind.reach(None, who=who)
        if not r or r["id"] == self.offered:
            return None
        self.offered = r["id"]
        return dict(r, who=who)

    def state(self):
        """How it is, for anyone watching: where, who, its body, its stage."""
        spot = self.mind.place()
        return {"where": (spot or {}).get("name") or self.where, "present": list(self.present),
                "body": [{"signal": n.replace("body ", "", 1), "level": lv, "note": note}
                         for n, lv, note in self.mind.sense_body({})],
                "stage": self.mind.stage().get("name")}
