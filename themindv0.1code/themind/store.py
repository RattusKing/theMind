"""On-disk stores — JSON Lines for record stores, JSON docs for singletons.

Implements FORMAT.md rules 2 (supersede, never overwrite), 3 (append-mostly,
human-readable) and 5 (corrupt reads degrade, never damage): a malformed line
is skipped whole; a malformed file reads as empty; writes are atomic
(tmp + rename) so a crash leaves prior state intact.
"""
import json
import os

from .envelope import now_iso, valid_record


def _atomic_write(path, text):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


class Jsonl:
    """One JSONL record store, with its archive twin (FORMAT.md `archive/`)."""

    def __init__(self, path, archive_path=None, validate=True):
        self.path = path
        self.archive_path = archive_path
        self.validate = validate

    def load(self):
        recs = []
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except Exception:
                        continue  # skipped whole, never partially applied
                    if self.validate and not valid_record(rec):
                        continue
                    recs.append(rec)
        except FileNotFoundError:
            pass
        except Exception:
            return []
        return recs

    def append(self, rec):
        if self.validate and not valid_record(rec):
            return False
        try:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            return True
        except Exception:
            return False

    def rewrite(self, records):
        try:
            _atomic_write(
                self.path,
                "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records),
            )
            return True
        except Exception:
            return False

    def supersede(self, old_id, successor_id):
        """Move `old_id` to the archive with `superseded_by` set. Nothing true
        is deleted; history is how a mind knows it has changed."""
        recs = self.load()
        keep, gone = [], []
        for r in recs:
            (gone if r.get("id") == old_id else keep).append(r)
        if not gone:
            return False
        for r in gone:
            r["superseded_by"] = successor_id
            r["archived_t"] = now_iso()
            self._archive(r)
        return self.rewrite(keep)

    def _archive(self, rec):
        if not self.archive_path:
            return
        try:
            with open(self.archive_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except Exception:
            pass


class JsonDoc:
    """A single JSON document store (graph, self, felt_sense, growth)."""

    def __init__(self, path):
        self.path = path

    def load(self, default=None):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default if default is not None else {}

    def save(self, obj):
        try:
            _atomic_write(self.path, json.dumps(obj, ensure_ascii=False, indent=1))
            return True
        except Exception:
            return False
