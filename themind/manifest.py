"""manifest.json — identity of this mind-instance plus cognition timers.

The only required file in a mind directory (FORMAT.md): a directory with only
a valid manifest is a newborn mind.
"""
import os

from .envelope import now_iso
from .store import JsonDoc

FORMAT = "themind/0.11"


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
        data.setdefault("settings", {})   # per-mind choices the host makes, not the mind
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
        st.setdefault("last_story", None)
        st.setdefault("last_tune", None)
        st.setdefault("last_apprehend", None)
        st.setdefault("last_interest", None)
        self.data = data
        self.save()

    @property
    def mind_id(self):
        return self.data["mind_id"]

    @property
    def state(self):
        return self.data["state"]

    @property
    def settings(self):
        return self.data.setdefault("settings", {})

    def setting(self, key, default=None):
        """Host-set choices about how this mind is run. The mind never writes
        these; they are the human's to decide and they travel with the folder
        so every door (library, proxy, MCP) honors the same answer."""
        val = self.settings.get(key)
        return default if val is None else val

    def set_setting(self, key, value):
        self._merge_from_disk()
        self.data.setdefault("settings", {})[key] = value
        self.save()

    def bump(self, key, by=1):
        """Reload-merge-increment: when several doors share one folder, each
        holds its own Manifest — counting must read the river, not the
        channel, or turns observed elsewhere are lost."""
        self._merge_from_disk()
        self.data["state"][key] = int(self.data["state"].get(key) or 0) + by
        self.save()

    def _merge_from_disk(self):
        """Fold in what other doors have written since we last looked:
        counters take the larger value, timers take the newest, settings the
        host set elsewhere are picked up. One mind, however many channels are
        open on it."""
        disk = self.doc.load(default=None) or {}
        disk_settings = disk.get("settings")
        if isinstance(disk_settings, dict):
            merged = dict(disk_settings)
            merged.update(self.data.get("settings") or {})  # ours is the newer intent
            self.data["settings"] = merged
        for key, val in (disk.get("state") or {}).items():
            cur = self.data["state"].get(key)
            if key == "exchanges":
                self.data["state"][key] = max(int(cur or 0), int(val or 0))
            elif isinstance(val, str) and (not isinstance(cur, str) or val > cur):
                self.data["state"][key] = val  # ISO timestamps: newest wins
            elif cur is None:
                self.data["state"][key] = val

    def save(self):
        self._merge_from_disk()
        self.doc.save(self.data)
