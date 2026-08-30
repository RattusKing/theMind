"""The entity graph — associative memory's shape (FORMAT.md `graph.json`).

A mention activates a node and its neighborhood; the lit constellation, not a
flat similarity list, is what enters context. Weights strengthen with evidence
and decay without it.
"""
from .envelope import now_iso, norm_key


def _slug(label):
    return "e_" + norm_key(label).replace(" ", "_")[:40]


class Graph:
    def __init__(self, doc):
        self.doc = doc
        self._refresh()

    def _refresh(self):
        """Re-read the doc so every door on this folder sees one graph. The
        stores are coherent by construction (each read hits disk); this keeps
        the one cached organ honest too."""
        data = self.doc.load(default=None) or {}
        self.nodes = {n["id"]: n for n in data.get("nodes", []) if isinstance(n, dict) and n.get("id")}
        self.edges = {}
        for e in data.get("edges", []):
            if isinstance(e, dict) and e.get("a") and e.get("b"):
                self.edges[self._ekey(e["a"], e["b"])] = e

    @staticmethod
    def _ekey(a, b):
        return "|".join(sorted((a, b)))

    def save(self):
        self.doc.save({"nodes": list(self.nodes.values()), "edges": list(self.edges.values())})

    def touch(self, labels, src_ref=None):
        """Register co-mentioned entities: create/strengthen nodes, link pairs."""
        self._refresh()
        ids = []
        for label in labels:
            label = (label or "").strip()
            if not label:
                continue
            nid = _slug(label)
            if not nid or nid == "e_":
                continue
            node = self.nodes.get(nid)
            if node is None:
                node = {"id": nid, "label": label, "kind": "unknown", "weight": 0.3,
                        "last_seen": now_iso()}
                self.nodes[nid] = node
            else:
                node["weight"] = min(1.0, node.get("weight", 0.3) + 0.1)
                node["last_seen"] = now_iso()
            ids.append(nid)
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                key = self._ekey(ids[i], ids[j])
                edge = self.edges.get(key)
                if edge is None:
                    self.edges[key] = {"a": ids[i], "b": ids[j], "rel": "with",
                                       "weight": 0.3,
                                       "src": {"kind": "record", "ref": src_ref or ids[i]}}
                else:
                    edge["weight"] = min(1.0, edge.get("weight", 0.3) + 0.15)
        self.save()
        return ids

    def constellation(self, text, limit=8):
        """Node labels lit up by this text: direct mentions plus their strongest
        neighbors."""
        self._refresh()
        low = (text or "").lower()
        lit = []
        for node in self.nodes.values():
            label = (node.get("label") or "").lower()
            if len(label) >= 3 and label in low:
                lit.append(node["id"])
        neighborhood = dict((nid, 1.0) for nid in lit)
        for edge in self.edges.values():
            for a, b in ((edge["a"], edge["b"]), (edge["b"], edge["a"])):
                if a in lit and b not in neighborhood:
                    neighborhood[b] = edge.get("weight", 0.0)
        ranked = sorted(neighborhood.items(), key=lambda kv: -kv[1])[:limit]
        return [self.nodes[nid]["label"] for nid, _ in ranked if nid in self.nodes]

    def top_labels(self, n=6):
        self._refresh()
        ranked = sorted(self.nodes.values(), key=lambda nd: -nd.get("weight", 0.0))
        return [nd["label"] for nd in ranked[:n]]

    def pulls(self, k=4):
        """The attention schema, derived — never stored: what has been pulling
        at the mind's attention lately. The graph IS the attention trace
        (touch strengthens, absence decays); this is the mind reading it
        about itself. Recency-weighted so an old heavyweight that hasn't come
        up gives way to what's alive now."""
        from .envelope import age_days
        self._refresh()
        scored = []
        for nd in self.nodes.values():
            w = nd.get("weight", 0.0) * (0.5 ** (age_days(nd.get("last_seen")) / 7.0))
            if w > 0.1:
                scored.append((w, nd.get("label", "")))
        scored.sort(key=lambda wl: -wl[0])
        return [label for _, label in scored[:k] if label]

    def decay(self, factor=0.98, floor=0.05):
        self._refresh()
        for node in self.nodes.values():
            node["weight"] = round(node.get("weight", 0.3) * factor, 4)
        self.edges = {k: e for k, e in self.edges.items()
                      if e.get("weight", 0.0) * factor >= floor}
        for e in self.edges.values():
            e["weight"] = round(e.get("weight", 0.3) * factor, 4)
        self.save()
