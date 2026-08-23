"""Scored recall — keyword overlap x salience x recency, boosted by the graph.

Deliberately not embeddings: below ~100k records, weighted keyword recall is
as good and costs nothing, and it keeps the zero-dependency promise. The
backend is small enough to swap; anyone who wants vectors overrides `score`.
"""
from .envelope import age_days

_STOP = set("the a an and or but for with from this that they them their have has was were will "
            "would could been being just really very about into over under some any what when "
            "where who how you your our its it's not don't didn't isn't".split())


def _words(text):
    return set(w for w in "".join(ch if ch.isalnum() else " " for ch in (text or "").lower()).split()
               if len(w) > 3 and w not in _STOP)


def score(fact, message_words, lit_labels):
    overlap = len(message_words & _words(fact.get("text", "")))
    entity_hit = 0
    lit_low = set(l.lower() for l in lit_labels)
    for ent in fact.get("entities", []) or []:
        if (ent or "").lower() in lit_low:
            entity_hit += 1
    base = overlap + 1.5 * entity_hit
    if base == 0:
        return 0.0
    recency = 0.5 ** (age_days(fact.get("t")) / 30.0)
    return base * (0.4 + fact.get("salience", 0.5)) * (0.3 + 0.7 * recency)


def recall(facts, message_text, lit_labels, k=8):
    mw = _words(message_text)
    scored = [(score(f, mw, lit_labels), f) for f in facts]
    scored = [(s, f) for s, f in scored if s > 0]
    scored.sort(key=lambda sf: -sf[0])
    return [f for _, f in scored[:k]]


def recent(facts, k=5):
    return sorted(facts, key=lambda f: f.get("t", ""), reverse=True)[:k]
