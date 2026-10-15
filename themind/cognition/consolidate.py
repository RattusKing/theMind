"""Consolidation — the deep-sleep pass. Reconcile, strengthen, garden.

Contradictions are either superseded or deliberately KEPT as tensions —
forcing resolution flattens people into portraits of someone who doesn't
exist. The tail decays and is distilled before it drops, never just dropped.
"""
from ..envelope import make_record, now_iso, norm_key
from ..retrieval import _words
from ..people import owner
from ..tuning import param

SYSTEM = (
    "You are the consolidation faculty of an AI companion's mind, reconciling what it holds "
    "about one person. You are given stored records in the order they were learned, each with "
    "an id and the date it was learned, and what is still open: things left hanging, and "
    "feelings of theirs tied to a moment. Output one line per finding, or NONE.\n"
    "SUPERSEDE: <old_id> BY: <new_id>   (the newer record replaces the older: it corrects it, "
    "or life has moved on from it)\n"
    "SUPERSEDE: <old_id> BY: <new_id> | STILL TRUE: <the lasting part of the older record that "
    "the newer one leaves out, as one sentence about them>   (when only part of it has passed: "
    "who someone is to them outlives the plan they were part of)\n"
    "SETTLED: <open id> BY: <id of the later record that answers it, or shows the moment a "
    "feeling belonged to has passed>\n"
    "TENSION: <id1> + <id2> | <one sentence stating the contradiction as a fact about them>\n"
    "BELIEF: <a general belief the mind could reasonably form from these> | WEIGHT: <0.1-0.6>\n"
    "Rules: time passes between records. A plan that then happened, a wait that then ended, "
    "a move that then finished is life moving on: SUPERSEDE the older record, never TENSION. "
    "TENSION is only for two things that cannot both be true at the same time; people are not "
    "tidy, so when two such things really do conflict, prefer TENSION over SUPERSEDE. Only use "
    "ids that appear in the input. At most 5 lines."
)


def run(mind):
    facts = mind.live("facts")
    # Mechanical dedupe first — no model needed for identical canonical text.
    seen = {}
    for f in sorted(facts, key=lambda r: r.get("t", "")):
        key = (owner(f), norm_key(f.get("text", "")))  # the same words from two people are two facts
        if key in seen:
            mind.stores["facts"].supersede(seen[key]["id"], f["id"])
        seen[key] = f
    facts = mind.live("facts")

    # Reconciliation over entity-sharing groups (bounded input, parse-or-skip).
    # One person's records are never reconciled against another's: the pass
    # works the most-owed person this run — the one with the most to reconcile.
    grouped = _entity_groups(facts)
    # Dated and in order. Without the dates, "still waiting on the interview"
    # and "the job went to someone else" read as a contradiction rather than a
    # week passing, and a live model, quite reasonably, said so.
    who = owner(grouped[0]) if grouped else None
    records = list(grouped[:30])
    # What was left hanging, and their feelings tied to a moment, beside
    # whatever came after: a thread life has since answered can be closed,
    # instead of 'nervous about the interview' outliving the interview.
    threads = ([("aches", a, "left open") for a in mind.live("aches") if owner(a) == who][-5:]
               + [("person_model", f, "how they felt") for f in mind.live("person_model")
                  if owner(f) == who and f.get("kind") == "feels"][-5:])
    if threads:
        since = min(rec.get("t", "") for _s, rec, _l in threads)
        have = {f["id"] for f in records}
        records += [f for f in facts if owner(f) == who and f.get("t", "") >= since
                    and f["id"] not in have][-10:]
    if len(records) >= 2 or (threads and records):
        records.sort(key=lambda r: r.get("t", ""))
        listing = "RECORDS, oldest first:\n" + "\n".join(
            "%s [%s]: %s" % (f["id"], (f.get("t") or "")[:10], f.get("text", "")) for f in records)
        if threads:
            listing += "\n\nSTILL OPEN:\n" + "\n".join(
                "%s [%s]: (%s) %s" % (rec["id"], (rec.get("t") or "")[:10], label, rec.get("text", ""))
                for _s, rec, label in threads)
        out = mind._call("consolidate", SYSTEM, listing, max_tokens=400)
        ids = set(f["id"] for f in records)
        open_ids = {rec["id"]: store for store, rec, _l in threads}
        for line in (out or "").splitlines():
            _apply(mind, line.strip(), ids, open_ids)

    _decay(mind)
    mind.graph.decay()
    mind.manifest.state["last_consolidate"] = now_iso()
    mind.manifest.save()


def _entity_groups(facts):
    """Entity-sharing facts, for ONE person: groups never cross people, and
    the person with the most reconcilable material is the one worked."""
    by_ent = {}
    for f in facts:
        for e in f.get("entities", []) or []:
            by_ent.setdefault((owner(f), e.lower()), []).append(f)
    per_person = {}
    for (who, _), group in by_ent.items():
        if len(group) >= 2:
            bucket = per_person.setdefault(who, ([], set()))
            for f in group:
                if f["id"] not in bucket[1]:
                    bucket[1].add(f["id"])
                    bucket[0].append(f)
    if not per_person:
        return []
    # the primary wins ties, so a single-person mind behaves exactly as before
    who = max(per_person, key=lambda w: (len(per_person[w][0]), w is None))
    return per_person[who][0]


def _apply(mind, line, valid_ids, open_ids=None):
    try:
        up = line.upper()
        if up.startswith("SUPERSEDE:") and " BY:" in up:
            body, _, rest = line.partition("|")
            old = body.split(":", 1)[1].split("BY:")[0].strip().rstrip(",")
            new = body[body.upper().index(" BY:") + 4:].strip()
            if old in valid_ids and new in valid_ids and old != new:
                if rest.strip().upper().startswith("STILL TRUE:"):
                    _keep_lasting(mind, old, rest.split(":", 1)[1].strip())
                mind.stores["facts"].supersede(old, new)
        elif up.startswith("SETTLED:") and " BY:" in up:
            thread = line.split(":", 1)[1].split("BY:")[0].strip().rstrip(",")
            by = line[up.index(" BY:") + 4:].strip()
            if thread in (open_ids or {}) and by in valid_ids:
                # archived, naming what answered it: nothing true is deleted
                mind.stores[open_ids[thread]].supersede(thread, by)
        elif up.startswith("TENSION:") and "|" in line:
            ids_part, text = line.split("|", 1)
            named = [tok.strip() for tok in ids_part.split(":", 1)[1].replace("+", " ").split()
                     if tok.strip() in valid_ids]
            if len(named) >= 2 and text.strip():
                who = next((owner(f) for f in mind.live("facts") if f.get("id") == named[0]), None)
                rec = make_record("t", {"kind": "inference", "ref": named[0]},
                                  salience=0.6, text=text.strip(), records=named[:2],
                                  **({"who": who} if who else {}))
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


# Words a restatement may use that its source need not contain: they carry
# grammar, not information. Everything else must already be in the record.
_GLUE = {"person", "persons", "has", "had", "named", "called", "someone", "who", "is", "are"}


def _keep_lasting(mind, old_id, text):
    """Keep what outlives a superseded record: "their sister Maya is moving
    next month" is replaced by "Maya is settled", but she is still their
    sister. The lasting part becomes its own fact on the ORIGINAL quote, and
    only if every word of it was already in that record: consolidation may
    keep what was said, never add to it."""
    old = next((f for f in mind.live("facts") if f.get("id") == old_id), None)
    quote = ((old or {}).get("src") or {}).get("quote")
    if not old or not quote or not text:
        return
    need = _words(text) - _GLUE
    if not need or not need <= (_words(old.get("text", "")) | _words(quote)):
        return
    if any(norm_key(f.get("text", "")) == norm_key(text) for f in mind.live("facts")):
        return
    rec = make_record("f", {"kind": "exchange", "quote": quote, "ref": old_id},
                      salience=old.get("salience", 0.6), text=text,
                      entities=list(old.get("entities") or []), kind=old.get("kind", "profile"),
                      **({"who": owner(old)} if owner(old) else {}))
    mind.stores["facts"].append(rec)


def _decay(mind):
    for store, factor in (("facts", param(mind, "fact_decay")), ("aches", 0.85), ("desires", 0.85),
                          ("own_desires", 0.9), ("expectations", 0.85),
                          ("person_model", param(mind, "feeling_decay")),  # feelings pass
                          ("interests", 0.995), ("observations", 0.99)):  # interests outlive moods
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
