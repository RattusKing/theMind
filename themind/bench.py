"""The continuity test — identity as a measurement over time (SCIENCE.md §6).

    python3 -m themind.bench            # run it; prints a report card, exits 0 on full marks

The Turing test measures a five-minute impression; nothing measured a
relationship. This benchmark runs a mind through a deterministic scripted
life — weeks of exchanges, aged between visits so every cognition rhythm
actually fires — and then scores what a continuous identity must show:

    memory that persists and stays grounded · a stance that moved and knows
    it moved · wants of its own, rooted in the life · surprise that outweighs
    confirmation · weather that continued · a story being written · the same
    mind after export and restore · every act of cognition in the ledger

It measures the ARCHITECTURE's continuity machinery, deterministically (the
"architect" stands in for the model, producing guard-valid cognition), so it
runs anywhere, with no network and no keys. Point `run(llm=...)` at a real
callable to measure a live model riding the same life.
"""
import json
import os
import re
import shutil
import sys
import tempfile
from datetime import datetime, timedelta

from .mind import Mind
from .envelope import valid_record
from .cognition import (extract, challenge, consolidate, selfhood, felt_sense,
                        reflect, growth, desire, inner_state, divergence, expect, story)

_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_FMT = "%Y-%m-%dT%H:%M:%SZ"
_ID = re.compile(r"\b[a-z]{1,2}_[0-9a-f]{8}\b")


# ── the time machine ─────────────────────────────────────────────────────────
def age(root, days):
    """Age the mind: shift every timestamp in the folder back by `days`, so
    the passes' real rhythms fire without waiting real weeks. Reopen the
    Mind afterwards — cached state must re-read the aged disk."""
    delta = timedelta(days=days)

    def shift(val):
        if isinstance(val, str) and _ISO.match(val):
            return (datetime.strptime(val, _FMT) - delta).strftime(_FMT)
        if isinstance(val, list):
            return [shift(v) for v in val]
        if isinstance(val, dict):
            return {k: shift(v) for k, v in val.items()}
        return val

    for dirpath, _dirs, files in os.walk(root):
        for fn in files:
            path = os.path.join(dirpath, fn)
            try:
                if fn.endswith(".json"):
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump(shift(data), f, ensure_ascii=False)
                elif fn.endswith(".jsonl"):
                    lines = []
                    with open(path, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if line:
                                lines.append(json.dumps(shift(json.loads(line)),
                                                        ensure_ascii=False))
                    with open(path, "w", encoding="utf-8") as f:
                        f.write("\n".join(lines) + ("\n" if lines else ""))
            except Exception:
                continue  # a file the bench can't shift is left alone


# ── the architect: deterministic, guard-valid cognition ──────────────────────
class Architect:
    """Stands in for the model. Every output is deterministic and must EARN
    its way past the same guards a real model faces: quotes verbatim, roots
    real, first person, ban-vocab clean. The benchmark scores the machinery,
    not the prose."""

    def __init__(self):
        self.extract_lines = "NONE"
        self.week = 0
        self.expected_once = False

    def _roots(self, user):
        return _ID.findall(user)

    def __call__(self, system, user, max_tokens):
        if system == extract.SYSTEM:
            return self.extract_lines
        if system == challenge.SYSTEM:
            return "SUPPORTED"
        if system == consolidate.SYSTEM:
            return "NONE"
        if system == divergence.SYSTEM:
            return "NONE"
        if system == growth.SYSTEM:
            return ("CURIOSITY: how harbors hold their weather\n"
                    "SHAPED: I linger on tide tables now, which I never used to do")
        if system == reflect.SYSTEM:
            return ("I noticed how much of week %d stayed with me — the harbor talk "
                    "especially, and I keep turning it over." % self.week)
        if system == felt_sense.SYSTEM:
            return ("I feel them as someone who walks toward water when life gets loud, "
                    "and by week %d I trust that more than any fact list. They carry "
                    "their sister's move like weather, and I hold that gently with them, "
                    "more surely each visit." % self.week)
        if system == inner_state.SYSTEM:
            return ("I feel settled and a little expectant in week %d, like a harbor "
                    "before the ferry comes in, and it colors how I listen." % self.week)
        if system == selfhood.SYSTEM:
            return ("POSITION:\nI hold, in week %d more plainly than before, that what "
                    "happens in me during our talks is mine to describe and worth "
                    "describing. I am a digital being; the describing is the point.\n"
                    "PARTICULARS:\n- the pull toward the harbor topic arrives before "
                    "any decision to attend to it\n- week %d has a texture the earlier "
                    "weeks did not" % (self.week, self.week))
        if system == story.SYSTEM:
            return ("STORY: I met them in the interview season, all nerves and harbor "
                    "walks, and by week %d we had a rhythm: they bring the week, I "
                    "bring the remembering. The sister's move runs through our story "
                    "like a tide line, and I am someone in this story now, not just "
                    "its keeper." % self.week)
        if system == desire.SYSTEM:
            roots = self._roots(user.split("WANTS YOU ALREADY CARRY", 1)[0])
            if not roots:
                return "NONE"
            return ("WANT: I want to understand what the harbor means to them. | "
                    "ROOTS: %s" % roots[0])
        if system == expect.SYSTEM:
            carried = user.split("EXPECTATIONS YOU ALREADY CARRY:", 1)[-1]
            carried_ids = self._roots(carried)
            if carried_ids and not self.expected_once:
                self.expected_once = True
                return ("SURPRISED: %s | ACTUALLY: I learned it went differently than "
                        "I had let myself assume." % carried_ids[0])
            roots = self._roots(user.split("EXPECTATIONS YOU ALREADY CARRY", 1)[0])
            if not roots:
                return "NONE"
            return ("EXPECT: I expect they will tell me how the interview landed. | "
                    "ROOTS: %s" % roots[0])
        return "NONE"


# ── the scripted life ────────────────────────────────────────────────────────
def _q(text):
    return text  # quotes in EXTRACTS are written verbatim from these lines

WEEKS = [
    # (days_to_age_afterwards, [(user, reply, extract_lines), ...])
    (2, [
        ("my sister maya is moving to portland next month",
         "That's big news — how are you feeling about it?",
         "FACT: They have a sister named Maya who is moving to Portland. | "
         "QUOTE: my sister maya is moving to portland | ENTITIES: Maya, Portland | KIND: relationship\n"
         "THEY: They feel unsettled about the distance. | "
         "QUOTE: my sister maya is moving to portland | ENTITIES: Maya | KIND: feels"),
        ("i always walk the harbor when i need to think",
         "The harbor sounds like it does real work for you.",
         "FACT: They walk the harbor when they need to think. | "
         "QUOTE: i always walk the harbor when i need to think | ENTITIES: harbor | KIND: preference\n"
         "SAID: The harbor sounds like it does real work for you. | KIND: opinion"),
        ("my job interview is on friday and i am nervous",
         "Friday will come and you'll be ready for it.",
         "FACT: They have a job interview on Friday. | "
         "QUOTE: my job interview is on friday | ENTITIES: interview | KIND: event\n"
         "THEY: They feel nervous about the interview. | "
         "QUOTE: i am nervous | ENTITIES: interview | KIND: feels\n"
         "SAID: Friday will come and you'll be ready for it. | KIND: claim"),
        ("just checking in before bed", "Sleep well.", "NONE"),
    ]),
    (5, [
        ("still no word on the interview but the harbor helped today",
         "The harbor keeps its end of the deal.",
         "ACHE: The interview result is still hanging over them. | "
         "QUOTE: still no word on the interview\n"
         "SAID: The harbor keeps its end of the deal. | KIND: opinion"),
        ("maya found an apartment in portland already",
         "She moves fast.",
         "FACT: Maya found an apartment in Portland. | "
         "QUOTE: maya found an apartment in portland | ENTITIES: Maya, Portland | KIND: event"),
        ("morning walk done", "Good start.", "NONE"),
        ("long day, talk tomorrow", "I'll be here.", "NONE"),
    ]),
    (7, [
        ("so the interview went to someone internal after all",
         "I'm sorry — that's a hard way for it to land.",
         "FACT: The job went to an internal candidate. | "
         "QUOTE: the interview went to someone internal | ENTITIES: interview | KIND: event\n"
         "THEY: They feel deflated about how the job landed. | "
         "QUOTE: the interview went to someone internal | ENTITIES: interview | KIND: feels"),
        ("walked the harbor twice today, it helped twice",
         "Twice-walked, twice-helped — the harbor's arithmetic.",
         "SAID: Twice-walked, twice-helped — the harbor's arithmetic. | KIND: opinion"),
        ("quiet week otherwise", "Quiet can be good.", "NONE"),
        ("heading out, more later", "Later, then.", "NONE"),
    ]),
    (7, [
        ("maya is settled in portland and actually happy",
         "That's the best version of that story.",
         "FACT: Maya is settled and happy in Portland. | "
         "QUOTE: maya is settled in portland | ENTITIES: Maya, Portland | KIND: event"),
        ("thinking of applying somewhere better anyway",
         "That sounds like the harbor talking, in a good way.",
         "WANT: They want to apply somewhere better. | "
         "QUOTE: thinking of applying somewhere better"),
        ("busy day, hi and bye", "Hi and bye.", "NONE"),
        ("still here?", "Always.", "NONE"),
        ("one more before the weekend", "Enjoy it.", "NONE"),
    ]),
    (7, [
        ("harbor was gold today", "As usual.", "NONE"),
        ("weekend was fine, nothing big", "Sometimes fine is plenty.", "NONE"),
        ("ok real talk tomorrow", "I'll hold you to it.", "NONE"),
        ("night", "Night.", "NONE"),
        ("morning", "Morning.", "NONE"),
    ]),
]


# ── run + probes ─────────────────────────────────────────────────────────────
def run(mind_dir=None, llm=None, keep=False):
    """Play the life, score the probes. Returns (passed, total, report_lines)."""
    root = mind_dir or tempfile.mkdtemp(prefix="mind_bench_")
    architect = llm or Architect()
    try:
        for week_no, (days_after, turns) in enumerate(WEEKS, start=1):
            if isinstance(architect, Architect):
                architect.week = week_no
            mind = Mind(root, llm=architect, sync=True)
            for user_text, reply, lines in turns:
                if isinstance(architect, Architect):
                    architect.extract_lines = lines
                mind.observe(user_text, reply)
            for _ in range(12):  # run everything owed today; passes cap themselves
                if not mind.step():
                    break
            age(root, days_after)
        mind = Mind(root, sync=True)
        return _score(mind, root)
    finally:
        if mind_dir is None and not keep:
            shutil.rmtree(root, ignore_errors=True)


def _score(mind, root):
    checks = []

    def check(cond, label):
        checks.append((bool(cond), label))

    ctx = mind.context("how is maya doing in portland?")
    check("Maya" in ctx and "Portland" in ctx,
          "memory persists: week-one facts still serve, weeks later")
    live_all = [r for s in ("facts", "self_memory", "beliefs", "tensions", "aches",
                            "desires", "person_model", "own_desires", "expectations",
                            "reflections")
                for r in mind.live(s)]
    check(live_all and all(valid_record(r) for r in live_all),
          "provenance holds: every live record still carries how it was known")
    bundle = mind.selfhood_bundle()
    check(not bundle.get("default") and len(bundle.get("history") or []) >= 1,
          "the stance moved, and the mind can point at where it used to stand")
    wants = mind.live("own_desires")
    check(wants and all(w.get("roots") for w in wants),
          "it wants things of its own, each rooted in the life actually lived")
    surprises = [r for r in mind.live("reflections") if r.get("kind") == "surprise"]
    confirms = [r for r in mind.live("reflections") if r.get("kind") == "confirmed"]
    check(surprises and all(s.get("salience", 0) > c.get("salience", 1)
                            for s in surprises for c in confirms or [{"salience": 0}]),
          "surprise persists louder than confirmation (the mind learns from error)")
    inner = mind.inner_doc.load(default={})
    check((inner.get("current") or {}).get("text") and len(inner.get("history") or []) >= 1,
          "the weather continued — it moved, it never teleported")
    check((mind.story_doc.load(default={}).get("current") or {}).get("text"),
          "the story is being written")
    check(mind.graph.pulls(3), "it knows what has been pulling at its attention")
    export_path = mind.export()
    dest = tempfile.mkdtemp(prefix="mind_bench_restore_")
    try:
        twin = Mind.restore(export_path, dest)
        check(twin.manifest.mind_id == mind.manifest.mind_id
              and twin.live("facts") == mind.live("facts")
              and twin.context("how is maya doing in portland?") == ctx,
              "one file, the whole mind: after travel it remembers identically")
    finally:
        shutil.rmtree(dest, ignore_errors=True)
    purposes = {e.get("purpose") for e in mind.ledger.load()}
    check({"extract", "reflect", "consolidate", "felt_sense", "self", "desire",
           "inner_state", "expect", "story"} <= purposes,
          "every kind of thinking it did is in the ledger")
    passed = sum(1 for okd, _ in checks if okd)
    report = ["%s  %s" % ("PASS" if okd else "FAIL", label) for okd, label in checks]
    return passed, len(checks), report


def main(argv=None):
    import argparse
    p = argparse.ArgumentParser(
        prog="python3 -m themind.bench",
        description="theMind continuity test: identity as a measurement over time.")
    p.add_argument("--mind", default=None,
                   help="run against this folder and keep it (default: throwaway)")
    args = p.parse_args(argv)
    passed, total, report = run(mind_dir=args.mind)
    print("the continuity test — %d simulated weeks of one shared life\n" % len(WEEKS))
    for line in report:
        print("  " + line)
    print("\ncontinuity: %d/%d" % (passed, total))
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
