"""Challenge-time guard — the second guard on the fact path (FORMAT.md, `facts.jsonl`).

Write-time grounding only stops errors *entering*; it does nothing about one
already stored. So when a fresh exchange touches the same ground as a stored
fact, the stored text is re-derived from its own provenance quote rather than
trusted. A fact its evidence no longer supports is superseded by what the
evidence does support — never silently edited, never silently dropped.

A genuine change of heart is NOT the guard's business: if the evidence supports
the stored text, both records stand and consolidation keeps the contradiction
as a tension. The guard corrects drift from evidence, not people changing.
"""
from ..envelope import make_record
from ..retrieval import _words

SYSTEM = (
    "You are the challenge faculty of an AI companion's mind. A stored memory about a person "
    "is being re-checked against its own evidence, because a new exchange touches the same "
    "ground. Judge ONLY whether the evidence quote, on its own, supports the stored text — "
    "the new statement is context, not evidence. Reply with exactly one line:\n"
    "SUPPORTED\n"
    "REVISED: <one sentence, third person, stating only what the evidence itself supports>\n"
    "Rules: small wording drift is SUPPORTED; a stored text claiming more than the quote "
    "says is REVISED; if the quote supports nothing about them, still use REVISED with the "
    "little it does say."
)

MAX_PER_TURN = 2  # a guard on the turn's cost, not just its content


def check(mind, new_facts):
    """Re-derive stored facts contested by this turn's newly stored facts.
    A stored fact is contested when a new fact shares an entity with it.
    Only exchange-provenance facts can be re-derived — a quote is the one
    kind of evidence that can be re-read."""
    ran = 0
    for new in new_facts:
        if ran >= MAX_PER_TURN:
            break
        ents = set(e.lower() for e in new.get("entities") or [])
        if not ents:
            continue
        for old in mind.live("facts"):
            if old.get("id") == new.get("id"):
                continue
            if not (ents & set(e.lower() for e in old.get("entities") or [])):
                continue
            src = old.get("src") or {}
            quote = (src.get("quote") or "").strip()
            if src.get("kind") != "exchange" or not quote:
                continue  # no re-readable evidence; consolidation's problem, not ours
            _challenge(mind, old, quote, new)
            ran += 1
            break  # at most one challenge per new fact


def _challenge(mind, old, quote, new):
    user = ('STORED: %s\nEVIDENCE (verbatim from the person): "%s"\nNEW (just said): %s'
            % (old.get("text", ""), quote, new.get("text", "")))
    out = mind._call("challenge", SYSTEM, user, max_tokens=120)
    if not out:
        return
    line = out.strip().splitlines()[0].strip()
    up = line.upper()
    if up.startswith("SUPPORTED") or not up.startswith("REVISED:") or ":" not in line:
        return  # supported, or parse-or-skip: no reply shape can damage the store
    text = line.split(":", 1)[1].strip()
    if not text or not (_words(text) & _words(quote)):
        return  # the revision itself must be grounded in the evidence it re-reads
    rec = make_record("f", {"kind": "exchange", "quote": quote[:200], "ref": None},
                      salience=old.get("salience", 0.5), text=text,
                      entities=(old.get("entities") or [])[:5],
                      kind=old.get("kind", "profile"))
    if mind.stores["facts"].append(rec):
        mind.stores["facts"].supersede(old["id"], rec["id"])
