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
import re

from ..envelope import make_record, norm_key
from ..retrieval import _words
from . import challenge, desire, expect

REINFORCE = 0.05  # a re-mention strengthens what it repeats (the spacing effect)

_QUOTE_STRIP = re.compile(r"[^0-9a-z\s]")
_CURLY = {"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"', "\u2013": "-", "\u2014": "-"}


def _norm_quote(text):
    """Casefold, straighten curly quotes, drop punctuation, collapse whitespace.
    The grounding rule stays exactly as strict — their words, contiguous, or
    nothing — it just stops failing on an apostrophe or a doubled space."""
    text = (text or "").lower()
    for k, v in _CURLY.items():
        text = text.replace(k, v)
    text = text.replace("'", "")   # maya's -> mayas: an apostrophe never splits a word
    return " ".join(_QUOTE_STRIP.sub(" ", text).split())


def _grounded(quote, user_text):
    q = _norm_quote(quote)
    return bool(q) and q in _norm_quote(user_text)

SYSTEM = (
    "You are the memory-extraction faculty of an AI companion's mind. From this exchange, "
    "extract only what is really there. Output one item per line, or the single word NONE.\n"
    "FACT: <one sentence about the person, third person> | QUOTE: <short verbatim quote from "
    "THEIR message> | ENTITIES: <comma-separated names/things> | KIND: profile|event|preference|relationship\n"
    "THEY: <one sentence about their INNER world — something they believe (may be false), "
    "feel (may pass), or don't know — never a fact about the world> | QUOTE: <verbatim from "
    "THEIR message> | ENTITIES: <comma-separated> | KIND: believes|feels|unaware\n"
    "ACHE: <something left emotionally unresolved or hanging> | QUOTE: <verbatim from their message>\n"
    "WANT: <something they want or look forward to> | QUOTE: <verbatim from their message>\n"
    "SAID: <a durable opinion, claim, or promise the COMPANION voiced> | KIND: opinion|claim|promise\n"
    "Rules: never invent; never extract a FACT or THEY from the companion's words; small "
    "talk extracts nothing; quotes must be copied exactly; a THEY line is theirs, not the "
    "truth — never convert a belief into a fact or a fact into a belief."
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
    asst_words = _words(assistant_text or "")
    for line in out.splitlines():
        line = line.strip().lstrip("-").strip()
        parts = line.split("|")
        head = parts[0].strip()
        try:
            if head.upper().startswith("FACT:"):
                quote = next((_field(p, "QUOTE:") for p in parts if _field(p, "QUOTE:")), None)
                if not quote or not _grounded(quote, user_text):
                    continue  # write-time grounding: no real source, no record
                ents = next((_field(p, "ENTITIES:") for p in parts if _field(p, "ENTITIES:")), "") or ""
                kind = next((_field(p, "KIND:") for p in parts if _field(p, "KIND:")), "profile") or "profile"
                entities = [e.strip() for e in ents.split(",") if e.strip()][:5]
                rec = make_record("f", {"kind": "exchange", "quote": quote[:200], "ref": None},
                                  salience=0.6, text=_field(head, "FACT:"),
                                  entities=entities, kind=kind.strip().lower()[:20])
                if not _is_new(mind, "facts", rec):
                    _reinforce(mind, "facts", rec)  # said again: it matters more, not less
                elif mind.stores["facts"].append(rec):
                    mind.graph.touch(entities, src_ref=rec["id"])
                    new_facts.append(rec)
                    stored += 1
            elif head.upper().startswith("THEY:"):
                quote = next((_field(p, "QUOTE:") for p in parts if _field(p, "QUOTE:")), None)
                if not quote or not _grounded(quote, user_text):
                    continue  # their inner world still needs their actual words
                ents = next((_field(p, "ENTITIES:") for p in parts if _field(p, "ENTITIES:")), "") or ""
                kind = (next((_field(p, "KIND:") for p in parts if _field(p, "KIND:")), "") or "").strip().lower()
                kind = ("believes" if kind.startswith("belie")
                        else "feels" if kind.startswith("feel")
                        else "unaware" if kind.startswith("una") or kind.startswith("unk")
                        else "believes")
                entities = [e.strip() for e in ents.split(",") if e.strip()][:5]
                rec = make_record("pm", {"kind": "exchange", "quote": quote[:200], "ref": None},
                                  salience=0.55, text=_field(head, "THEY:"),
                                  entities=entities, kind=kind)
                if not _is_new(mind, "person_model", rec):
                    _reinforce(mind, "person_model", rec)
                elif mind.stores["person_model"].append(rec):
                    mind.graph.touch(entities, src_ref=rec["id"])
                    _reconcile_mental_states(mind, rec)  # feelings pass: the newer one on a thread wins
                    stored += 1
            elif head.upper().startswith("ACHE:") or head.upper().startswith("WANT:"):
                name = "ACHE:" if head.upper().startswith("ACHE:") else "WANT:"
                quote = next((_field(p, "QUOTE:") for p in parts if _field(p, "QUOTE:")), None)
                if not quote or not _grounded(quote, user_text):
                    continue
                store = "aches" if name == "ACHE:" else "desires"
                rec = make_record(store[0], {"kind": "exchange", "quote": quote[:200], "ref": None},
                                  salience=0.6, text=_field(head, name))
                if not _is_new(mind, store, rec):
                    _reinforce(mind, store, rec)
                elif mind.stores[store].append(rec):
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
    try:
        desire.touch(mind, user_text, assistant_text)   # mechanical; no model call
        expect.touch(mind, user_text, assistant_text)   # attention follows predictions
    except Exception:
        pass
    return stored


def _is_new(mind, store, rec):
    key = norm_key(rec.get("text", ""))
    if not key:
        return False
    return all(norm_key(r.get("text", "")) != key for r in mind.live(store))


def _reinforce(mind, store, rec):
    """Rehearsal. A re-mention used to be discarded as a duplicate — so a
    memory could only ever decay, however often it came up. Now the repeat
    strengthens the record it repeats. Logical time `t` is untouched (read
    order is identity); only wear changes."""
    key = norm_key(rec.get("text", ""))
    if not key:
        return False
    recs = mind.stores[store].load()  # the whole file, so a rewrite loses nothing
    hit = False
    for r in recs:
        if r.get("superseded_by"):
            continue
        if norm_key(r.get("text", "")) == key:
            r["salience"] = min(1.0, round(float(r.get("salience", 0.5)) + REINFORCE, 4))
            hit = True
    if hit:
        mind.stores[store].rewrite(recs)
    return hit


def _reconcile_mental_states(mind, new):
    """A newer FEELING on the same thread supersedes the older one: 'feels
    nervous about the interview' gives way to 'feels deflated about the
    interview'. Never deleted — archived naming its successor, like every
    supersede in the mind. Feelings only: beliefs coexist (the false-belief
    milestone — two beliefs about one thing are a person, not a bug)."""
    if new.get("kind") != "feels":
        return
    ents = {e.lower() for e in (new.get("entities") or [])}
    if not ents:
        return
    for old in mind.live("person_model"):
        if old.get("id") == new.get("id") or old.get("kind") != new.get("kind"):
            continue
        if ents & {e.lower() for e in (old.get("entities") or [])}:
            mind.stores["person_model"].supersede(old["id"], new["id"])
