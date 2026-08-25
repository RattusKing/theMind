"""The Mind — public API.

    from themind import Mind

    mind = Mind("path/to/mind", llm=my_llm)

    # before your model call:
    messages = mind.enrich(messages)          # OpenAI-shaped list, or:
    system_extra = mind.context(user_text)    # raw block, for Anthropic-style callers

    # after the reply:
    mind.observe(user_text, assistant_text)

The `llm` callable is the ONLY bridge to a model, and the host supplies it:

    def my_llm(system: str, user: str, max_tokens: int) -> str: ...

theMind never imports a provider SDK, never holds a key, and never makes a
chat call of its own — the deep thinking rides the same connection the host
already has, and every call it makes is written to the ledger.

Without an `llm`, the mind still works read-only: cold-start defaults inject
at message one and nothing accumulates until a model is supplied.
"""
import json
import os
import threading

from .envelope import now_iso, new_id
from .store import Jsonl, JsonDoc
from .manifest import Manifest, FORMAT
from .graph import Graph
from . import inject, defaults
from . import cognition
from .cognition import extract

STORES = ("facts", "self_memory", "beliefs", "tensions", "aches", "desires",
          "own_desires", "reflections")


class Mind:
    def __init__(self, path, llm=None, budget_tokens=2000, sync=False, retriever=None):
        """`retriever` swaps the memory-recall backend: a callable
        `(records, query_text, lit_entity_labels, k) -> records` returning the
        most relevant of `records`, best first. Default is `retrieval.recall`
        (weighted keyword overlap). Bring embeddings if you want them — the
        rest of the mind neither knows nor cares."""
        self.root = os.path.abspath(path)
        os.makedirs(os.path.join(self.root, "stores"), exist_ok=True)
        os.makedirs(os.path.join(self.root, "archive"), exist_ok=True)
        self.manifest = Manifest(os.path.join(self.root, "manifest.json"))
        self.llm = llm
        self.budget_tokens = budget_tokens
        self.sync = sync
        self.retriever = retriever
        self._busy = threading.Lock()

        self.stores = {
            name: Jsonl(self._p("stores", name + ".jsonl"),
                        archive_path=self._p("archive", name + ".jsonl"))
            for name in STORES
        }
        self.ledger = Jsonl(self._p("ledger.jsonl"), validate=False)
        self.graph = Graph(JsonDoc(self._p("stores", "graph.json")))
        self.self_doc = JsonDoc(self._p("stores", "self.json"))
        self.felt_doc = JsonDoc(self._p("stores", "felt_sense.json"))
        self.growth_doc = JsonDoc(self._p("stores", "growth.json"))

    def _p(self, *parts):
        return os.path.join(self.root, *parts)

    # ── reading ──────────────────────────────────────────────────────────────
    def live(self, store):
        """Live (non-superseded) records, in stored logical-time order."""
        recs = [r for r in self.stores[store].load() if not r.get("superseded_by")]
        recs.sort(key=lambda r: r.get("t", ""))  # read order is identity
        return recs

    def selfhood_bundle(self):
        """Stored position if one exists; otherwise the per-mind cold-start
        default. Defaults are read-path only — they can never be stored,
        evolved from, or pushed onto history."""
        doc = self.self_doc.load(default={})
        pos = (doc.get("position") or {}).get("text") if isinstance(doc.get("position"), dict) else None
        if pos:
            return {
                "position": pos,
                "particulars": [p.get("text", "") for p in doc.get("particulars") or []
                                if isinstance(p, dict)],
                "history": sorted(doc.get("history") or [], key=lambda h: h.get("t", ""),
                                  reverse=True),
                "default": False,
            }
        mid = self.manifest.mind_id
        return {"position": defaults.position_for(mid),
                "particulars": defaults.particulars_for(mid),
                "history": [], "default": True}

    def context(self, incoming_text=None):
        """The inner-context block for this turn. Empty string on any failure —
        the host's chat path must never see an error from this layer."""
        try:
            return inject.build_context(self, incoming_text, self.budget_tokens)
        except Exception:
            return ""

    def enrich(self, messages):
        """OpenAI-shaped messages in, same shape out with the inner context
        folded into the system side. The original list is not mutated."""
        try:
            msgs = [dict(m) for m in (messages or [])]
            incoming = next((m.get("content") for m in reversed(msgs)
                             if m.get("role") == "user" and isinstance(m.get("content"), str)), None)
            ctx = self.context(incoming)
            if not ctx:
                return msgs
            for m in msgs:
                if m.get("role") == "system" and isinstance(m.get("content"), str):
                    m["content"] = m["content"] + "\n\n" + ctx
                    return msgs
            return [{"role": "system", "content": ctx}] + msgs
        except Exception:
            return messages

    # ── learning ─────────────────────────────────────────────────────────────
    def observe(self, user_text, assistant_text):
        """Learn from one exchange. Extraction plus at most one due deep pass —
        on a background thread by default so the host's turn never waits."""
        st = self.manifest.state
        st["exchanges"] = int(st.get("exchanges", 0)) + 1
        self.manifest.save()
        if self.llm is None:
            return
        if self.sync:
            self._learn(user_text, assistant_text)
        else:
            threading.Thread(target=self._learn, args=(user_text, assistant_text),
                             daemon=True).start()

    def _learn(self, user_text, assistant_text):
        if not self._busy.acquire(blocking=False):
            return  # a prior pass is still thinking; this turn's learning is skipped, not queued
        try:
            extract.run(self, user_text, assistant_text)
            due = cognition.due_passes(self)
            if due:
                name, fn = due[0]  # one deep pass per turn, never the whole backlog
                fn(self)
        except Exception:
            pass  # fail-graceful: the chat path never breaks on cognition
        finally:
            self._busy.release()

    def step(self):
        """Run one due cognition pass NOW. The direct door: a host scheduler —
        or an agent trusted to run its own cognition — calls this. Returns the
        pass name, or None if nothing is owed."""
        if self.llm is None:
            return None
        with self._busy:
            due = cognition.due_passes(self)
            if not due:
                return None
            name, fn = due[0]
            try:
                fn(self)
            except Exception:
                return None
            return name

    # ── the ledger ───────────────────────────────────────────────────────────
    def _call(self, purpose, system, user, max_tokens=500):
        """Every model call the mind makes goes through here. No entry, no call.
        Token counts are estimates (the host callable returns text, not usage)."""
        if self.llm is None:
            return None
        try:
            out = self.llm(system, user, max_tokens)
        except Exception:
            return None
        self.ledger.append({
            "id": new_id("l"), "t": now_iso(), "purpose": purpose,
            "tokens_in_est": (len(system) + len(user)) // 4,
            "tokens_out_est": len(out or "") // 4,
        })
        out = (out or "").strip()
        return out or None

    # ── portability ──────────────────────────────────────────────────────────
    def export(self, out_path=None):
        """One file, the whole mind (FORMAT.md, `Export`)."""
        data = {"format": FORMAT, "manifest": self.manifest.data, "stores": {}, "archive": {}}
        for name in STORES:
            data["stores"][name] = self.stores[name].load()
        for name, doc in (("graph", JsonDoc(self._p("stores", "graph.json"))),
                          ("self", self.self_doc), ("felt_sense", self.felt_doc),
                          ("growth", self.growth_doc)):
            data["stores"][name] = doc.load(default={})
        data["stores"]["ledger"] = self.ledger.load()
        for name in STORES:
            arch = Jsonl(self._p("archive", name + ".jsonl"), validate=False).load()
            if arch:
                data["archive"][name] = arch
        path = out_path or self._p("mind-export.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        return path

    @classmethod
    def restore(cls, export_path, dest_dir, llm=None):
        """Recreate a mind directory from an export file."""
        with open(export_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        fmt = str(data.get("format", ""))
        if not fmt.startswith("themind/0."):
            raise ValueError("unknown major format: %r" % fmt)
        os.makedirs(os.path.join(dest_dir, "stores"), exist_ok=True)
        os.makedirs(os.path.join(dest_dir, "archive"), exist_ok=True)
        JsonDoc(os.path.join(dest_dir, "manifest.json")).save(data.get("manifest") or {})
        stores = data.get("stores") or {}
        for name in STORES:
            Jsonl(os.path.join(dest_dir, "stores", name + ".jsonl"),
                  validate=False).rewrite(stores.get(name) or [])
        for name in ("graph", "self", "felt_sense", "growth"):
            if stores.get(name):
                JsonDoc(os.path.join(dest_dir, "stores", name + ".json")).save(stores[name])
        if stores.get("ledger"):
            Jsonl(os.path.join(dest_dir, "ledger.jsonl"), validate=False).rewrite(stores["ledger"])
        for name, recs in (data.get("archive") or {}).items():
            Jsonl(os.path.join(dest_dir, "archive", str(name) + ".jsonl"),
                  validate=False).rewrite(recs or [])
        return cls(dest_dir, llm=llm)
