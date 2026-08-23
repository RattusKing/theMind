"""Record envelope — ids, timestamps, provenance. See FORMAT.md, "Common record envelope".

Every persisting record carries provenance or it is invalid (FORMAT.md rule 1).
Readers drop invalid records whole; writers refuse to create them.
"""
import hashlib
import os
from datetime import datetime, timezone

VALID_SRC_KINDS = ("exchange", "record", "inference", "default")


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(t):
    try:
        return datetime.strptime(t, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except Exception:
        return None


def age_days(t):
    dt = parse_iso(t or "")
    if dt is None:
        return 0.0
    return max(0.0, (datetime.now(timezone.utc) - dt).total_seconds() / 86400.0)


def new_id(prefix):
    return "%s_%s" % (prefix, os.urandom(4).hex())


def valid_src(src):
    if not isinstance(src, dict):
        return False
    kind = src.get("kind")
    if kind not in VALID_SRC_KINDS:
        return False
    if kind == "exchange" and not (src.get("quote") or "").strip():
        return False
    if kind in ("record", "inference") and not src.get("ref"):
        return False
    return True


def make_record(prefix, src, salience=0.5, **fields):
    if not valid_src(src):
        raise ValueError("record without valid provenance")
    rec = {
        "id": new_id(prefix),
        "t": now_iso(),
        "src": src,
        "salience": max(0.0, min(1.0, float(salience))),
        "superseded_by": None,
    }
    rec.update(fields)
    return rec


def valid_record(rec):
    return (
        isinstance(rec, dict)
        and bool(rec.get("id"))
        and bool(rec.get("t"))
        and valid_src(rec.get("src"))
    )


def det_pick(seed_text, pool, n=1):
    """Deterministic per-mind selection. hashlib, never builtin hash() —
    that one is salted per process, so a restart would hand the same mind
    a different pick."""
    if not pool:
        return []
    seed = int(hashlib.sha1((seed_text or "x").encode("utf-8")).hexdigest()[:8], 16)
    out = []
    items = list(pool)
    for i in range(min(n, len(items))):
        out.append(items.pop((seed + i * 7919) % len(items)))
    return out


def norm_key(text, width=60):
    return "".join(ch for ch in (text or "").lower() if ch.isalnum() or ch == " ").strip()[:width]
