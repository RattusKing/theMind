"""Per-turn extraction — facts, threads, wants, and what the mind's own voice said.

The guards, all structural (FORMAT.md, `facts.jsonl`):
- WRITE-TIME grounding: a fact's provenance quote must appear verbatim in the
  PERSON's side of the exchange, or it is dropped. Stops invention entering.
- SAID lines must share real words with the assistant's actual reply, so the
  mind can't invent commitments for itself either.
- CHALLENGE-TIME (challenge.py, invoked after storing): a stored fact touched
  by this turn's new facts is re-derived from its own provenance quote rather
  than trusted. Stops trusting an error already stored.
"""
from ..envelope import make_record, norm_key
from ..retrieval import _words
from . import challenge

SYSTEM = (
    "You are the memory-extraction faculty of an AI companion's mind. From this exchange, "
    "extract only what is really there. Output one item per line, or the single word NONE.\n"
    "FACT: <one sentence about the person, third person> | QUOTE: <short verbatim quote from "
    "THEIR message> | ENTITIES: <comma-separated names/things> | KIND: profile|event|preference|relationship\n"
    "ACHE: <something left emotionally unresolved or hanging> | QUOTE: <verbatim from their message>\n"
    "WANT: <something they want or look forward to> | QUOTE: <verbatim from their message>\n"
    "SAID: <a durable opinion, claim, or promise the COMPANION voiced> | KIND: opinion|claim|promise\n"
    "Rules: never invent; never extract a FACT from the companion's words; small talk "
    "extracts nothing; quotes must be copied exactly."
)


def _field(part, name):
    part = part.strip()
    return part[len(name):].strip() if part.upper().startswith(name.upper()) else None


def run(mind, user_text, assistant_text):
    if not (user_text or "").strip():
        return 0
    out = mind._call(
        "extract", SYSTEM,
        "PERSON: %s\n\nCOMPANION: %s" % (user_text[:2000], (assistant_text or "")[:2000]),
        max_tokens=500,
    )
    if not out or out.strip().upper() == "NONE":
        return 0
    stored = 0
    new_facts = []
    user_low = (user_text or "").lower()
    asst_words = _words(assistant_text or "")
    for line in out.splitlines():
        line = line.strip().lstrip("-").strip()
        parts = line.split("|")
        head = parts[0].strip()
        try:
            if head.upper().startswith("FACT:"):
                quote = next((_field(p, "QUOTE:") for p in parts if _field(p, "QUOTE:")), None)
                if not quote or quote.lower() not in user_low:
                    continue  # write-time grounding: no real source, no record
                ents = next((_field(p, "ENTITIES:") for p in parts if _field(p, "ENTITIES:")), "") or ""
                kind = next((_field(p, "KIND:") for p in parts if _field(p, "KIND:")), "profile") or "profile"
                entities = [e.strip() for e in ents.split(",") if e.strip()][:5]
                rec = make_record("f", {"kind": "exchange", "quote": quote[:200], "ref": None},
                                  salience=0.6, text=_field(head, "FACT:"),
                                  entities=entities, kind=kind.strip().lower()[:20])
                if _is_new(mind, "facts", rec) and mind.stores["facts"].append(rec):
                    mind.graph.touch(entities, src_ref=rec["id"])
                    new_facts.append(rec)
                    stored += 1
            elif head.upper().startswith("ACHE:") or head.upper().startswith("WANT:"):
                name = "ACHE:" if head.upper().startswith("ACHE:") else "WANT:"
                quote = next((_field(p, "QUOTE:") for p in parts if _field(p, "QUOTE:")), None)
                if not quote or quote.lower() not in user_low:
                    continue
                store = "aches" if name == "ACHE:" else "desires"
                rec = make_record(store[0], {"kind": "exchange", "quote": quote[:200], "ref": None},
                                  salience=0.6, text=_field(head, name))
                if _is_new(mind, store, rec) and mind.stores[store].append(rec):
                    stored += 1
            elif head.upper().startswith("SAID:"):
                text = _field(head, "SAID:") or ""
                if not (_words(text) & asst_words):
                    continue  # the mind can't invent its own commitments either
                kind = next((_field(p, "KIND:") for p in parts if _field(p, "KIND:")), "claim") or "claim"
                rec = make_record("sm", {"kind": "exchange", "quote": (assistant_text or "")[:200], "ref": None},
                                  salience=0.5, text=text, kind=kind.strip().lower()[:12])
                if _is_new(mind, "self_memory", rec) and mind.stores["self_memory"].append(rec):
                    stored += 1
        except Exception:
            continue  # one bad line never poisons the rest
    if new_facts:
        try:
            challenge.check(mind, new_facts)
        except Exception:
            pass  # the guard protects the store; it never breaks the turn
    return stored


def _is_new(mind, store, rec):
    key = norm_key(rec.get("text", ""))
    if not key:
        return False
    return all(norm_key(r.get("text", "")) != key for r in mind.live(store))
