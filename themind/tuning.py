"""Tuning — the one surface a mind may adjust in itself (FORMAT.md, `tuning.json`, 0.8).

THE CONSTITUTION. A mind that improves itself needs a boundary it cannot
move. Here it is, structurally:

- The mind never modifies code. Everything it may change is DATA in its own
  folder, human-readable, with history.
- It may change exactly the parameters listed in TUNABLE, each within a fixed
  range. Nothing else has a name here, so nothing else can be tuned: not a
  guard, not a prompt, not the host's persona, not the budget, not a decay
  floor. An unknown name or an out-of-range value is refused whole.
- Every change is an EXPERIMENT: one at a time, with a prediction made before
  it starts, judged against a baseline on a signal the mind can measure
  without a human. A change that does not measurably help is reverted; one
  that cannot be judged is reverted too. Nothing survives on the mind's own
  say-so.
- The signals are derived from what the mind already records; the counters
  here are the only new state, and they are advisory — no other store reads
  them.
"""
from .envelope import now_iso

# name: (min, max, default, type). This dict IS the constitution's reach.
TUNABLE = {
    "recall_k":      (4, 12, 8, int),        # facts recalled per turn
    "inner_them_k":  (2, 6, 4, int),         # their inner-world lines served per turn
    "touch_overlap": (1, 3, 2, int),         # content words an exchange must share to touch a want/expectation
    "fact_decay":    (0.97, 0.995, 0.985, float),
    "feeling_decay": (0.8, 0.95, 0.9, float),
}

# signal: (numerator counter, denominator counter) — a rate the mind earns turn by turn.
SIGNALS = {
    "extract_quality": ("extract_kept", "extract_proposed"),   # of what it tried to remember, how much was grounded
    "recall_use":      ("recall_used", "recall_served"),       # of what it recalled, how much the reply drew on
}
MIN_SAMPLES = 10   # fewer than this on either side of an experiment: inconclusive, revert


def _cast(name, value):
    lo, hi, _, typ = TUNABLE[name]
    try:
        v = typ(float(value))
    except Exception:
        return None
    if v < lo or v > hi:
        return None
    return v


class Tuning:
    """`tuning.json`: parameter overrides, signal counters, the one running experiment."""

    def __init__(self, doc):
        self.doc = doc

    def load(self):
        data = self.doc.load(default={}) or {}
        if not isinstance(data, dict):
            data = {}
        params = data.get("params") if isinstance(data.get("params"), dict) else {}
        signals = data.get("signals") if isinstance(data.get("signals"), dict) else {}
        exp = data.get("experiment") if isinstance(data.get("experiment"), dict) else None
        return {"params": params, "signals": signals, "experiment": exp}

    # ── parameters ───────────────────────────────────────────────────────────
    def get(self, name):
        """The current value: the override if one is set and valid, else the default."""
        if name not in TUNABLE:
            raise KeyError(name)
        cur = self.load()["params"].get(name)
        v = _cast(name, cur) if cur is not None else None
        return v if v is not None else TUNABLE[name][2]

    def set(self, name, value):
        """Refuses (False) anything outside the constitution: unknown names,
        out-of-range values, wrong types. Never clamps — a proposal that
        oversteps is dropped whole, not bent into shape."""
        if name not in TUNABLE:
            return False
        v = _cast(name, value)
        if v is None:
            return False
        data = self.load()
        data["params"][name] = v
        self.doc.save(data)
        return True

    def reset(self, name):
        data = self.load()
        if name in data["params"]:
            del data["params"][name]
            self.doc.save(data)

    # ── signals ──────────────────────────────────────────────────────────────
    def bump(self, counter, by=1):
        if by <= 0:
            return
        data = self.load()
        data["signals"][counter] = int(data["signals"].get(counter) or 0) + int(by)
        self.doc.save(data)

    def snapshot(self):
        return dict(self.load()["signals"])

    def rate(self, signal, since=None):
        """A signal's rate (0-1) and its sample count, over everything since the
        `since` snapshot (or since the beginning). None when nothing was counted."""
        num_key, den_key = SIGNALS[signal]
        now = self.load()["signals"]
        since = since or {}
        den = int(now.get(den_key) or 0) - int(since.get(den_key) or 0)
        num = int(now.get(num_key) or 0) - int(since.get(num_key) or 0)
        if den <= 0:
            return None, 0
        return max(0.0, min(1.0, num / float(den))), den

    # ── the experiment ───────────────────────────────────────────────────────
    def experiment(self):
        return self.load()["experiment"]

    def start(self, name, value, signal, predicted, exchanges_now, window):
        """Begin the one experiment: apply the value, remember what was, and
        what the mind expects. Refused if one is already running."""
        if self.experiment() is not None or signal not in SIGNALS:
            return False
        if name not in TUNABLE or _cast(name, value) is None:
            return False
        data = self.load()
        was = data["params"].get(name)
        data["experiment"] = {
            "param": name, "from": was, "to": _cast(name, value), "signal": signal,
            "predicted": predicted[:300], "started_t": now_iso(),
            "started_exchanges": int(exchanges_now), "window": int(window),
            "baseline": dict(data["signals"]),
        }
        data["params"][name] = _cast(name, value)
        self.doc.save(data)
        return True

    def finish(self, keep):
        """End the experiment: keep the value, or put back what was."""
        data = self.load()
        exp = data["experiment"]
        if exp is None:
            return None
        if not keep:
            if exp.get("from") is None:
                data["params"].pop(exp["param"], None)
            else:
                data["params"][exp["param"]] = exp["from"]
        data["experiment"] = None
        self.doc.save(data)
        return exp


def param(mind, name):
    """Read a tunable from a mind — the default when the mind has no tuning."""
    try:
        return mind.tuning.get(name)
    except Exception:
        return TUNABLE[name][2]
