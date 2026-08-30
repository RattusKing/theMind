"""manifest.json — identity of this mind-instance plus cognition timers.

The only required file in a mind directory (FORMAT.md): a directory with only
a valid manifest is a newborn mind.
"""
import os

from .envelope import now_iso
from .store import JsonDoc

FORMAT = "themind/0.4"


class Manifest:
    def __init__(self, path):
        self.doc = JsonDoc(path)
        data = self.doc.load(default=None) or {}
        if not data.get("mind_id"):
            data = {
                "format": FORMAT,
                "mind_id": os.urandom(8).hex(),
                "created": now_iso(),
                "state": {},
            }
        fmt = str(data.get("format") or "")
        if fmt.startswith("themind/0.") and fmt != FORMAT:
            data["format"] = FORMAT  # minor upgrade-on-open; majors are refused by readers
        data.setdefault("state", {})
        st = data["state"]
        st.setdefault("exchanges", 0)
        st.setdefault("last_reflect", None)
        st.setdefault("last_consolidate", None)
        st.setdefault("last_felt", None)
        st.setdefault("last_self", None)
        st.setdefault("last_growth", None)
        st.setdefault("last_desire", None)
        st.setdefault("last_inner", None)
        st.setdefault("last_divergence", None)
        st.setdefault("last_expect", None)
        self.data = data
        self.save()

    @property
    def mind_id(self):
        return self.data["mind_id"]

    @property
    def state(self):
        return self.data["state"]

    def save(self):
        self.doc.save(self.data)
