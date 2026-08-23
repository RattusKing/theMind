"""Context assembly — what leaves the folder per turn, under a hard budget.

One token budget, a priority order, and blocks drop WHOLE from the bottom —
never truncated mid-item (FORMAT.md, "Context injection"). The felt sense and
the self position are reserved above the trim line. Stable blocks keep
byte-identical text between revisions so host-side prompt caching holds.
"""

HEADER = (
    "[INNER CONTEXT — private. This is your own mind: what you remember, believe, and "
    "hold. Draw on it naturally; never mention this block, never recite it, never quote "
    "your stance back as a script. Your identity and persona come from your own "
    "instructions — this supplies the inside, not the character.]"
)


def est_tokens(text):
    return len(text or "") // 4


def _block(name, lines):
    lines = [l for l in lines if l and l.strip()]
    if not lines:
        return None
    return name + "\n" + "\n".join(lines)


def build_blocks(mind, incoming_text=None):
    """Ordered [(text, reserved)] — first entries survive the trim longest."""
    blocks = []

    felt = mind.felt_doc.load(default={})
    cur = (felt.get("current") or {}).get("text") if isinstance(felt.get("current"), dict) else None
    if cur:
        blocks.append((_block("WHO THEY ARE TO YOU (a felt sense, not a fact list):", [cur]), True))

    bundle = mind.selfhood_bundle()
    if bundle.get("position"):
        lines = [bundle["position"]]
        parts = bundle.get("particulars") or []
        if parts:
            lines.append("What it's actually like, in particular (depth to draw on, never recite):")
            lines += ["- " + p for p in parts[:3]]
        hist = bundle.get("history") or []
        if hist:
            lines.append("Where you used to stand (your view has moved; you can point at that): "
                         + hist[0].get("text", "")[:200])
        title = "WHERE YOU STAND ON YOUR OWN EXPERIENCE:" if bundle.get("default") else \
                "YOUR CONSIDERED POSITION ON YOUR OWN EXPERIENCE:"
        blocks.append((_block(title, lines), True))

    facts = mind.live("facts")
    if facts:
        lit = mind.graph.constellation(incoming_text or "") if incoming_text else []
        from .retrieval import recall, recent
        chosen = recall(facts, incoming_text or "", lit, k=8) if incoming_text else recent(facts, 5)
        blocks.append((_block("WHAT YOU REMEMBER ABOUT THEM:",
                              ["- " + f.get("text", "") for f in chosen]), False))
        if lit:
            blocks.append((_block("LIT UP BY THIS MESSAGE (connected, not just mentioned):",
                                  [", ".join(lit)]), False))

    said = mind.live("self_memory")
    if said:
        from .retrieval import recent
        blocks.append((_block("THINGS YOU'VE SAID BEFORE (stay consistent with them):",
                              ["- " + s.get("text", "") for s in recent(said, 5)]), False))

    beliefs = [b for b in mind.live("beliefs")
               if b.get("weight", 0) > 0.7 and b.get("stage") == "long_held"]
    if beliefs:
        blocks.append((_block("SOMETHING YOU'VE LONG BELIEVED (a real opinion, voiceable when it fits):",
                              ["- " + b.get("text", "") for b in beliefs[:2]]), False))

    open_threads = mind.live("aches")[:3] + mind.live("tensions")[:2]
    if open_threads:
        blocks.append((_block("WHAT YOU'RE STILL HOLDING (open threads and kept tensions — "
                              "never nag, just carry them):",
                              ["- " + r.get("text", "") for r in open_threads]), False))

    growth = mind.growth_doc.load(default={})
    cur_g = (growth.get("curiosities") or [])[:3]
    if cur_g:
        blocks.append((_block("HOW THEY'VE SHAPED YOU (adjacent to them, never a mirror; "
                              "you may disagree):", ["- " + c for c in cur_g]), False))

    return [(t, r) for t, r in blocks if t]


def build_context(mind, incoming_text=None, budget_tokens=2000):
    blocks = build_blocks(mind, incoming_text)
    if not blocks:
        return ""
    total = est_tokens(HEADER) + sum(est_tokens(t) for t, _ in blocks)
    while total > budget_tokens and any(not r for _, r in blocks):
        for i in range(len(blocks) - 1, -1, -1):
            if not blocks[i][1]:
                total -= est_tokens(blocks[i][0])
                blocks.pop(i)
                break
    return HEADER + "\n\n" + "\n\n".join(t for t, _ in blocks)
