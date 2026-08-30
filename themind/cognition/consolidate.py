"""Consolidation — the deep-sleep pass. Reconcile, strengthen, garden.

Contradictions are either superseded or deliberately KEPT as tensions —
forcing resolution flattens people into portraits of someone who doesn't
exist. The tail decays and is distilled before it drops, never just dropped.
"""
from ..envelope import make_record, now_iso, norm_key

SYSTEM = (
    "You are the consolidation faculty of an AI companion's mind, reconciling what it holds "
    "about one person. You are given stored records, each with an id. Output one line per "
    "finding, or NONE.\n"
    "SUPERSEDE: <old_id> BY: <new_id>   (the newer record genuinely replaces the older)\n"
    "TENSION: <id1> + <id2> | <one sentence stating the contradiction as a fact about them>\n"
    "BELIEF: <a general belief the mind could reasonably form from these> | WEIGHT: <0.1-0.6>\n"
    "Rules: people are not tidy — prefer TENSION over SUPERSEDE unless one record clearly "
    "corrects the other. Only use ids that appear in the input. At most 5 lines."
)


def run(mind):
    facts = mind.live("facts")
    # Mechanical dedupe first — no model needed for identical canonical text.
    seen = {}
    for f in sorted(facts, key=lambda r: r.get("t", "")):
        key = norm_key(f.get("text", ""))
        if key in seen:
            mind.stores["facts"].supersede(seen[key]["id"], f["id"])
        seen[key] = f
    facts = mind.live("facts")

    # Reconciliation over entity-sharing groups (bounded input, parse-or-skip).
    grouped = _entity_groups(facts)
    if grouped:
        listing = "\n".join("%s: %s" % (f["id"], f.get("text", "")) for f in grouped[:30])
        out = mind._call("consolidate", SYSTEM, listing, max_tokens=400)
        ids = set(f["id"] for f in facts)
        for line in (out or "").splitlines():
            _apply(mind, line.strip(), ids)

    _decay(mind)
    mind.graph.decay()
    mind.manifest.state["last_consolidate"] = now_iso()
    mind.manifest.save()


def _entity_groups(facts):
    by_ent = {}
    for f in facts:
        for e in f.get("entities", []) or []:
            by_ent.setdefault(e.lower(), []).append(f)
    out, seen = [], set()
    for group in by_ent.values():
        if len(group) >= 2:
            for f in group:
                if f["id"] not in seen:
                    seen.add(f["id"])
                    out.append(f)
    return out


def _apply(mind, line, valid_ids):
    try:
        up = line.upper()
        if up.startswith("SUPERSEDE:") and " BY:" in up:
            old = line.split(":", 1)[1].split("BY:")[0].strip().rstrip(",")
            new = line[up.index(" BY:") + 4:].strip()
            if old in valid_ids and new in valid_ids and old != new:
                mind.stores["facts"].supersede(old, new)
        elif up.startswith("TENSION:") and "|" in line:
            ids_part, text = line.split("|", 1)
            named = [tok.strip() for tok in ids_part.split(":", 1)[1].replace("+", " ").split()
                     if tok.strip() in valid_ids]
            if len(named) >= 2 and text.strip():
                rec = make_record("t", {"kind": "inference", "ref": named[0]},
                                  salience=0.6, text=text.strip(), records=named[:2])
                mind.stores["tensions"].append(rec)
        elif up.startswith("BELIEF:") and "|" in line:
            text, wpart = line.split("|", 1)
            text = text.split(":", 1)[1].strip()
            try:
                weight = max(0.1, min(0.6, float(wpart.upper().replace("WEIGHT:", "").strip())))
            except Exception:
                weight = 0.3
            key = norm_key(text)
            if not text or not key:
                return
            for b in mind.live("beliefs"):
                if norm_key(b.get("text", "")) == key:
                    b["weight"] = min(1.0, b.get("weight", 0.3) + 0.1)
                    b["stage"] = ("long_held" if b["weight"] > 0.85
                                  else "held" if b["weight"] > 0.6 else "forming")
                    mind.stores["beliefs"].rewrite(mind.live("beliefs"))
                    return
            mind.stores["beliefs"].append(
                make_record("b", {"kind": "inference", "ref": "consolidation"},
                            salience=0.5, text=text, weight=weight, stage="forming"))
    except Exception:
        pass  # one bad line never damages stored state


def _decay(mind):
    for store, factor in (("facts", 0.985), ("aches", 0.85), ("desires", 0.85),
                          ("own_desires", 0.9), ("expectations", 0.85)):
        recs = mind.live(store)
        keep = []
        for r in recs:
            r["salience"] = round(r.get("salience", 0.5) * factor, 4)
            if r["salience"] < 0.05:
                # Distil before drop: the tail is gardened, not discarded.
                digest = make_record("r", {"kind": "record", "ref": r["id"]},
                                     salience=0.3, text="Let go of: " + r.get("text", ""),
                                     kind="digest")
                mind.stores["reflections"].append(digest)
                r["superseded_by"] = digest["id"]
                mind.stores[store]._archive(r)
            else:
                keep.append(r)
        mind.stores[store].rewrite(keep)
