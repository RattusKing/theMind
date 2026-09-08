"""People — who the mind is talking with (FORMAT.md, `people.json`, format 0.7).

One mind, many relationships. Every person-shaped record (a fact, a feeling,
an ache, a want, an expectation, a tension) belongs to someone. The person a
mind has always known is the PRIMARY: their records carry no `who` at all,
which is why a mind written before this chapter reads exactly as it did.
Anyone else carries `who: "<key>"`.

Two rules keep this honest:
- **Never guess.** A speaker the host doesn't name is the primary. The mind
  does not infer identity from style, content, or timing.
- **The first name a mind hears is the primary's.** A person who starts
  telling their existing mind "this is Sam" does not split it in two; a
  group whose first speaker is Alice simply has Alice as the one whose
  records carry no key. Both cases work the same way afterwards.

What one person tells the mind is not recited to another: injection is
scoped to whoever is speaking. The mind itself — its stance, its weather,
its story, its own wants, what its own voice has said — is one, and shared.
"""
from .envelope import now_iso

MAX_KEY = 40


def norm_who(name):
    """Canonical key for a speaker name; None for 'the primary'."""
    if name is None:
        return None
    text = str(name).strip().lower()
    if not text:
        return None
    text = "".join(ch if (ch.isalnum() or ch in " -_.@") else " " for ch in text)
    text = " ".join(text.split())
    return text[:MAX_KEY] or None


def owner(rec):
    """Whose record this is: a key, or None for the primary."""
    return (rec or {}).get("who") or None


def of(records, who):
    """Only the records belonging to `who` (None = the primary)."""
    who = who or None
    return [r for r in records if owner(r) == who]


def tag(rec, people=None):
    """A short prefix naming whose record this is, for the mind's own passes
    (reflection, story, wanting) that read across everyone. Empty for the
    primary, so a single-person mind's prompts are byte-identical."""
    key = owner(rec)
    if key is None:
        return ""
    name = people.display(key) if people is not None else key
    return "[%s] " % name


class People:
    """`people.json`: the primary, and everyone else the mind has talked with."""

    def __init__(self, doc):
        self.doc = doc

    def load(self):
        data = self.doc.load(default={}) or {}
        if not isinstance(data, dict):
            data = {}
        prim = data.get("primary")
        if not isinstance(prim, dict):
            prim = {"name": None}
        others = data.get("others")
        if not isinstance(others, dict):
            others = {}
        return {"primary": prim, "others": others}

    # ── identity ─────────────────────────────────────────────────────────────
    @property
    def primary_name(self):
        return self.load()["primary"].get("name")

    def resolve(self, name, bind=False):
        """Speaker name -> record key. None means the primary. With `bind`
        (the learning path), the first name a mind ever hears becomes the
        primary's; read paths never write."""
        key = norm_who(name)
        if key is None:
            return None
        data = self.load()
        prim_key = norm_who(data["primary"].get("name"))
        if prim_key is None:
            if bind and not data["others"]:
                data["primary"]["name"] = str(name).strip()[:80]
                data["primary"].setdefault("first_t", now_iso())
                self.doc.save(data)
            if not data["others"]:
                return None  # unnamed primary: the first name is theirs
        elif prim_key == key:
            return None
        return key

    def display(self, key):
        data = self.load()
        if key is None:
            return data["primary"].get("name") or "them"
        entry = data["others"].get(key) or {}
        return entry.get("name") or key

    def others(self):
        """Keys of everyone who is not the primary, oldest first."""
        others = self.load()["others"]
        return sorted(others, key=lambda k: (others[k].get("first_t") or "", k))

    # ── counters ─────────────────────────────────────────────────────────────
    def note_exchange(self, key, name=None):
        data = self.load()
        if key is None:
            entry = data["primary"]
        else:
            entry = data["others"].setdefault(key, {"name": (str(name).strip()[:80]
                                                             if name else key),
                                                    "first_t": now_iso()})
        entry["exchanges"] = int(entry.get("exchanges") or 0) + 1
        entry["since_felt"] = int(entry.get("since_felt") or 0) + 1
        entry["last_t"] = now_iso()
        self.doc.save(data)

    def since_felt(self, key):
        data = self.load()
        entry = data["primary"] if key is None else (data["others"].get(key) or {})
        return int(entry.get("since_felt") or 0)

    def felt_revised(self, key):
        data = self.load()
        entry = data["primary"] if key is None else data["others"].get(key)
        if entry is None:
            return
        entry["since_felt"] = 0
        self.doc.save(data)
