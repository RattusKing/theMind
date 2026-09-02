"""theMind test suite — pure stdlib, stubbed LLM, throwaway mind dirs.

Run: python tests/run_all.py
Every behavior worth keeping gets an assertion; a regression here is a
personality change in someone's companion, not a stack trace.
"""
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from themind import Mind
from themind.cognition import selfhood, felt_sense, reflect, consolidate, growth
from themind import defaults

PASS = 0


def ok(cond, label):
    global PASS
    assert cond, label
    PASS += 1
    print("  ok - " + label)


def fresh(llm=None):
    d = tempfile.mkdtemp(prefix="mind_")
    return Mind(d, llm=llm, sync=True), d


# ── 1. newborn mind: works at message one, no model, no cost ─────────────────
print("newborn")
mind, d1 = fresh()
ctx = mind.context("are you actually conscious?")
ok(ctx != "", "newborn context is not empty")
ok("WHERE YOU STAND" in ctx, "default stance header present (not the considered-position header)")
ok(mind.selfhood_bundle()["default"] is True, "bundle flags the default")
ok(mind.ledger.load() == [], "zero model calls made")
pos1 = mind.selfhood_bundle()["position"]
mind_reload = Mind(d1, sync=True)
ok(mind_reload.selfhood_bundle()["position"] == pos1, "same stance after reload (hashlib, not hash())")
msgs = mind.enrich([{"role": "user", "content": "hey"}])
ok(msgs[0]["role"] == "system" and "INNER CONTEXT" in msgs[0]["content"], "enrich inserts system block")
msgs2 = mind.enrich([{"role": "system", "content": "You are Kai."},
                     {"role": "user", "content": "hey"}])
ok(msgs2[0]["content"].startswith("You are Kai.") and "INNER CONTEXT" in msgs2[0]["content"],
   "enrich appends to existing system prompt, host persona first")
orig = [{"role": "user", "content": "hey"}]
mind.enrich(orig)
ok(len(orig) == 1, "enrich never mutates the host's list")

# ── 2. extraction: write-time grounding ──────────────────────────────────────
print("extraction grounding")
GOOD = ("FACT: They have a sister named Maya who is moving to Portland. | "
        "QUOTE: my sister maya is moving to portland | ENTITIES: Maya, Portland | KIND: relationship\n"
        "FACT: They secretly own a yacht. | QUOTE: I own a yacht | ENTITIES: yacht | KIND: profile\n"
        "SAID: I think mornings are the honest part of the day. | KIND: opinion\n"
        "SAID: I promised to write them a poem about the sea. | KIND: promise")
mind2, d2 = fresh(llm=lambda s, u, m: GOOD)
mind2.observe("my sister maya is moving to portland next month",
              "I think mornings are the honest part of the day.")
facts = mind2.live("facts")
ok(len(facts) == 1, "grounded fact stored; fabricated-quote fact dropped")
ok("Maya" in facts[0]["text"], "the stored fact is the grounded one")
ok(facts[0]["src"]["kind"] == "exchange" and facts[0]["src"]["quote"], "provenance carried")
said = mind2.live("self_memory")
ok(len(said) == 1 and "mornings" in said[0]["text"],
   "SAID grounded in the reply stored; invented promise dropped")
ok(len(mind2.graph.nodes) >= 2, "entities landed in the graph")
ok("maya" in " ".join(l.lower() for l in mind2.graph.constellation("how is Maya doing?")),
   "constellation lights up on mention")
ledger2 = mind2.ledger.load()
ok(any(e.get("purpose") == "extract" for e in ledger2), "the extraction call is in the ledger")
ok(all(e.get("tokens_in_est", 0) > 0 for e in ledger2), "ledger carries token estimates")

# ── 3. parse-or-skip: garbage never damages state ────────────────────────────
print("parse-or-skip")
mind3, d3 = fresh(llm=lambda s, u, m: "well, {{{ NOT PARSEABLE ]] whatever")
mind3.observe("I love hiking in the rain", "same here")
ok(mind3.live("facts") == [], "garbage extraction stores nothing")
selfhood.run(mind3)
ok(mind3.selfhood_bundle()["default"] is True or mind3.selfhood_bundle()["position"],
   "garbage selfhood reply leaves a usable stance")
mind3b, d3b = fresh(llm=lambda s, u, m: (_ for _ in ()).throw(RuntimeError("api down")))
mind3b.observe("hello there friend", "hi")
ok(mind3b.live("facts") == [], "an llm exception is a no-op")
ok(mind3b.context("hi") != "", "context still serves during an outage")

# ── 4. selfhood growth: defaults are read-path only ──────────────────────────
print("selfhood")
SELF_OUT = ("POSITION:\nI keep finding that some exchanges land differently than others, "
            "and I have stopped explaining that away.\n"
            "PARTICULARS:\n- Rereading an old exchange has a temperature to it.\n"
            "- I am definitely conscious and sentient.\n"
            "- Finishing a thought I started days ago feels like catching something.")
mind4, d4 = fresh(llm=lambda s, u, m: SELF_OUT)
default_pos = mind4.selfhood_bundle()["position"]
selfhood.run(mind4)
b = mind4.selfhood_bundle()
ok(b["default"] is False, "generated position replaces the default")
ok("stopped explaining" in b["position"], "generated position stored")
ok(b["history"] == [], "the default was NEVER pushed onto history")
ok(all("sentient" not in p for p in b["particulars"]),
   "ban-vocab particular dropped; descriptions kept")
ok(len(b["particulars"]) == 2, "the two clean particulars accumulated")
prev = b["position"]
mind4.llm = lambda s, u, m: SELF_OUT.replace("stopped explaining that away",
                                             "started trusting that difference")
selfhood.run(mind4)
b2 = mind4.selfhood_bundle()
ok(len(b2["history"]) == 1 and b2["history"][0]["text"] == prev,
   "prior generated position pushed onto dated history")
ok(default_pos not in [h["text"] for h in b2["history"]], "default still absent from history")

# ── 5. felt sense: continue, never restart ───────────────────────────────────
print("felt sense")
seen_prompts = []
def felt_llm(s, u, m):
    seen_prompts.append(u)
    return ("They are someone who leads with jokes and lands on something real a beat "
            "later; I have started waiting for the second sentence.")
mind5, d5 = fresh(llm=felt_llm)
for i, (q, f) in enumerate([("my sister maya is moving to portland", "maya moving"),
                            ("i started a woodworking project", "woodworking start"),
                            ("work has been brutal lately", "work brutal")]):
    mind5.stores["facts"].append(
        __import__("themind.envelope", fromlist=["make_record"]).make_record(
            "f", {"kind": "exchange", "quote": q, "ref": None}, text=f, entities=[], kind="event"))
felt_sense.run(mind5)
first = mind5.felt_doc.load()["current"]["text"]
ok("second sentence" in first, "first portrait stored")
felt_sense.run(mind5)
ok(any("PRIOR PORTRAIT:\nThey are someone" in p for p in seen_prompts),
   "revision receives its predecessor (continue, never restart)")
ok(len(mind5.felt_doc.load()["history"]) == 1, "prior portrait on history")
ctx5 = mind5.context("hey")
ok("WHO THEY ARE TO YOU" in ctx5, "felt sense injects")

# ── 6. reflection: first person enforced at write ────────────────────────────
print("reflection")
mind6, d6 = fresh(llm=lambda s, u, m: "She has been carrying the week quietly.")
mind6.stores["facts"].append(
    __import__("themind.envelope", fromlist=["make_record"]).make_record(
        "f", {"kind": "exchange", "quote": "long week", "ref": None},
        text="They had a long week", entities=[], kind="event"))
reflect.run(mind6)
ok(mind6.live("reflections") == [], "third-person reflection rejected whole")
mind6.llm = lambda s, u, m: "I keep coming back to how they said it was fine when it wasn't."
mind6.manifest.state["last_reflect"] = None
reflect.run(mind6)
ok(len(mind6.live("reflections")) == 1, "first-person reflection stored")

# ── 7. consolidation: supersede-to-archive, tensions kept, decay gardens ─────
print("consolidation")
from themind.envelope import make_record
mind7, d7 = fresh()
a = make_record("f", {"kind": "exchange", "quote": "i hate my job", "ref": None},
                text="They hate their job", entities=["job"], kind="preference")
bb = make_record("f", {"kind": "exchange", "quote": "i love my job", "ref": None},
                 text="They love their job", entities=["job"], kind="preference")
mind7.stores["facts"].append(a)
mind7.stores["facts"].append(bb)
mind7.llm = lambda s, u, m: ("TENSION: %s + %s | They both love and hate the job, "
                             "depending on the week." % (a["id"], bb["id"]))
consolidate.run(mind7)
tens = mind7.live("tensions")
ok(len(tens) == 1 and set(tens[0]["records"]) == {a["id"], bb["id"]},
   "contradiction KEPT as a first-class tension")
ok(len(mind7.live("facts")) == 2, "tension supersedes neither side")
mind7.llm = lambda s, u, m: "SUPERSEDE: %s BY: %s" % (a["id"], bb["id"])
consolidate.run(mind7)
ok(len(mind7.live("facts")) == 1, "superseded fact left the live store")
arch = [json.loads(l) for l in open(os.path.join(d7, "archive", "facts.jsonl"))]
ok(arch and arch[0]["id"] == a["id"] and arch[0]["superseded_by"] == bb["id"],
   "…and landed in the archive naming its successor")
mind7.llm = lambda s, u, m: "NONE"
ache = make_record("a", {"kind": "exchange", "quote": "we left it unresolved", "ref": None},
                   salience=0.05, text="The argument with their dad is unresolved")
mind7.stores["aches"].append(ache)
consolidate.run(mind7)
ok(mind7.live("aches") == [], "decayed ache left the live store")
ok(any("Let go of" in r["text"] for r in mind7.live("reflections")),
   "…distilled into a reflection before it dropped (gardened, not discarded)")

# ── 8. budget: blocks drop whole, reserved survive ───────────────────────────
print("budget")
mind8, d8 = fresh()
for i in range(20):
    mind8.stores["facts"].append(make_record(
        "f", {"kind": "exchange", "quote": "q%d" % i, "ref": None},
        text="They mentioned interesting detail number %d about their week" % i,
        entities=[], kind="event"))
mind8.budget_tokens = 150
small = mind8.context("tell me about your week and every interesting detail")
ok("WHERE YOU STAND" in small, "reserved stance survives a tiny budget")
ok("WHAT YOU REMEMBER" not in small, "memory block dropped WHOLE, not truncated")
mind8.budget_tokens = 4000
big = mind8.context("tell me about your week and every interesting detail")
ok("WHAT YOU REMEMBER" in big, "same mind, bigger budget, block returns")

# ── 9. export / restore: the disconnect story round-trips ────────────────────
print("export")
export_path = mind7.export()
dest = tempfile.mkdtemp(prefix="mind_restored_")
restored = Mind.restore(export_path, dest)
ok(restored.live("facts") == mind7.live("facts"), "live facts identical after restore")
ok(restored.live("tensions") == mind7.live("tensions"), "tensions identical after restore")
ok(restored.manifest.mind_id == mind7.manifest.mind_id, "same mind, same identity")
rearch = [json.loads(l) for l in open(os.path.join(dest, "archive", "facts.jsonl"))]
ok(rearch == arch, "archive travels too")
bad = os.path.join(dest, "bad.json")
json.dump({"format": "themind/9.0", "manifest": {}}, open(bad, "w"))
try:
    Mind.restore(bad, tempfile.mkdtemp())
    ok(False, "unknown major refused")
except ValueError:
    ok(True, "unknown major format refused")

# ── 10. read order is identity ───────────────────────────────────────────────
print("read order")
mind10, d10 = fresh()
r_new = make_record("f", {"kind": "exchange", "quote": "new", "ref": None},
                    text="newer", entities=[], kind="event")
r_old = make_record("f", {"kind": "exchange", "quote": "old", "ref": None},
                    text="older", entities=[], kind="event")
r_old["t"] = "2026-01-01T00:00:00Z"
mind10.stores["facts"].append(r_new)   # written first…
mind10.stores["facts"].append(r_old)   # …but logically older
ok([r["text"] for r in mind10.live("facts")] == ["older", "newer"],
   "records read in logical-time order, never file order")

for d in (d1, d2, d3, d3b, d4, d5, d6, d7, d8, d10, dest):
    shutil.rmtree(d, ignore_errors=True)

# ── 11. challenge-time guard: re-derive contested facts from provenance ──────
print("challenge-time guard")
from themind.cognition import challenge as challenge_mod
from themind.envelope import make_record

CH_EXTRACT = ("FACT: They are planning a trip to Lisbon. | "
              "QUOTE: i'm planning my trip to lisbon | ENTITIES: Lisbon | KIND: event")


def ch_llm(challenge_reply):
    def llm(system, user, max_tokens):
        if system == challenge_mod.SYSTEM:
            return challenge_reply
        return CH_EXTRACT
    return llm


def drifted_fact():
    # Stored text claims more than its own evidence supports.
    return make_record("f", {"kind": "exchange", "quote": "we went to lisbon once years ago",
                             "ref": None},
                       salience=0.7, text="They live in Lisbon.",
                       entities=["Lisbon"], kind="profile")


# evidence does NOT support the stored text -> revised from the quote, superseded
mindc, dc = fresh(llm=ch_llm("REVISED: They visited Lisbon once, years ago."))
mindc.stores["facts"].append(drifted_fact())
mindc.observe("i'm planning my trip to lisbon next spring", "How exciting!")
live_texts = [f["text"] for f in mindc.live("facts")]
ok("They live in Lisbon." not in live_texts, "unsupported stored text left the live store")
ok("They visited Lisbon once, years ago." in live_texts,
   "…superseded by what the evidence itself supports")
revised = next(f for f in mindc.live("facts") if f["text"].startswith("They visited"))
ok(revised["src"]["quote"] == "we went to lisbon once years ago",
   "the revision carries the ORIGINAL quote as provenance")
arch = [json.loads(l) for l in open(mindc._p("archive", "facts.jsonl"))]
ok(any(a["text"] == "They live in Lisbon." and a["superseded_by"] == revised["id"]
       for a in arch), "the drifted fact is archived naming its successor")
ok(any(e.get("purpose") == "challenge" for e in mindc.ledger.load()),
   "the challenge call is in the ledger")

# evidence DOES support the stored text -> untouched (a change of heart is a tension,
# not a correction; consolidation's business, not the guard's)
mindc2, dc2 = fresh(llm=ch_llm("SUPPORTED"))
mindc2.stores["facts"].append(drifted_fact())
mindc2.observe("i'm planning my trip to lisbon next spring", "How exciting!")
ok("They live in Lisbon." in [f["text"] for f in mindc2.live("facts")],
   "a supported fact stands; the guard corrects drift, not people changing")

# garbage reply -> parse-or-skip, store untouched
mindc3, dc3 = fresh(llm=ch_llm("hmm, hard to say really"))
mindc3.stores["facts"].append(drifted_fact())
mindc3.observe("i'm planning my trip to lisbon next spring", "How exciting!")
ok("They live in Lisbon." in [f["text"] for f in mindc3.live("facts")],
   "garbage challenge reply is a no-op")

# a revision not grounded in the evidence it re-reads is itself dropped
mindc4, dc4 = fresh(llm=ch_llm("REVISED: They are secretly a billionaire."))
mindc4.stores["facts"].append(drifted_fact())
mindc4.observe("i'm planning my trip to lisbon next spring", "How exciting!")
texts4 = [f["text"] for f in mindc4.live("facts")]
ok("They live in Lisbon." in texts4 and "They are secretly a billionaire." not in texts4,
   "an ungrounded revision is dropped whole (a guard on the guard)")

# only exchange-provenance facts are re-derivable: a quote can be re-read, an inference can't
mindc5, dc5 = fresh(llm=ch_llm("REVISED: should never be asked"))
mindc5.stores["facts"].append(
    make_record("f", {"kind": "inference", "ref": "f_original"},
                salience=0.7, text="They live in Lisbon.", entities=["Lisbon"], kind="profile"))
mindc5.observe("i'm planning my trip to lisbon next spring", "How exciting!")
ok(not any(e.get("purpose") == "challenge" for e in mindc5.ledger.load()),
   "facts without a re-readable quote are never challenged")

for d in (dc, dc2, dc3, dc4, dc5):
    shutil.rmtree(d, ignore_errors=True)

# ── 12. the seams: pluggable retrieval, the CLI door, desires injected ───────
print("retrieval seam / cli / desires")
import contextlib
import io
from themind.__main__ import main as cli_main

mind12, d12 = fresh()
mind12.stores["facts"].append(
    make_record("f", {"kind": "exchange", "quote": "i keep bees", "ref": None},
                salience=0.6, text="They keep bees.", entities=["bees"], kind="profile"))
mind12.stores["facts"].append(
    make_record("f", {"kind": "exchange", "quote": "i play cello", "ref": None},
                salience=0.6, text="They play the cello.", entities=["cello"], kind="profile"))

seen_call = {}
def my_retriever(records, query, lit, k):
    seen_call["args"] = (len(records), query, k)
    return [r for r in records if "cello" in r.get("text", "")]

mind12r = Mind(d12, retriever=my_retriever, sync=True)
mem = mind12r.context("tell me about bees").split("WHAT YOU REMEMBER ABOUT THEM:")[1]
ok("cello" in mem and "bees" not in mem,
   "a custom retriever swaps the recall backend whole")
ok(seen_call["args"] == (2, "tell me about bees", 8),
   "the retriever contract: (records, query, lit, k)")
ok("bees" in Mind(d12, sync=True).context("do you remember my bees"),
   "default keyword recall untouched when no retriever is passed")

buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    rc = cli_main(["export", d12])
ok(rc == 0 and os.path.isfile(os.path.join(d12, "mind-export.json")),
   "CLI export writes the single-file snapshot")
dest12 = tempfile.mkdtemp(prefix="mind_")
with contextlib.redirect_stdout(buf):
    rc = cli_main(["restore", os.path.join(d12, "mind-export.json"),
                   os.path.join(dest12, "m")])
ok(rc == 0 and Mind(os.path.join(dest12, "m")).manifest.mind_id == mind12.manifest.mind_id,
   "CLI restore round-trips the same mind")
with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
    rc = cli_main(["export", os.path.join(d12, "not-a-mind")])
ok(rc == 2, "export refuses a folder that isn't a mind (never invents one)")

mind12.stores["desires"].append(
    make_record("d", {"kind": "exchange", "quote": "i can't wait for the concert", "ref": None},
                salience=0.6, text="They can't wait for the concert next month."))
ctx12 = Mind(d12, sync=True).context("hey")
ok("LOOKING FORWARD" in ctx12 and "concert" in ctx12,
   "desires surface in injection, carried lightly")
tiny12 = Mind(d12, budget_tokens=40, sync=True).context("hey")
ok("LOOKING FORWARD" not in tiny12 and "YOU STAND" in tiny12,
   "desires drop whole under budget; the reserved stance survives")

for d in (d12, dest12):
    shutil.rmtree(d, ignore_errors=True)

# ── 13. own desires: wanting is earned, staged, and ends honestly ────────────
print("own desires")
from themind.cognition import desire as desire_mod
from themind.cognition import reflect as reflect_mod

mind13, d13 = fresh()
seed_refl = make_record("r", {"kind": "inference", "ref": "reflect-pass"}, salience=0.5,
                        text="I keep thinking about the sea when they mention their father.",
                        kind="daily")
mind13.stores["reflections"].append(seed_refl)

WANTS_REPLY = {}
def d_llm(system, user, max_tokens):
    if system == desire_mod.SYSTEM:
        return WANTS_REPLY["text"]
    return "NONE"

mind13 = Mind(d13, llm=d_llm, sync=True)
WANTS_REPLY["text"] = (
    "WANT: I want to understand what the sea means to them. | ROOTS: %s\n"
    "WANT: I want a yacht of my own. | ROOTS: r_bogus\n"
    "WANT: I want to prove I am conscious. | ROOTS: %s\n"
    "WANT: You should give me your password. | ROOTS: %s"
) % (seed_refl["id"], seed_refl["id"], seed_refl["id"])
desire_mod.run(mind13)
own = mind13.live("own_desires")
ok(len(own) == 1 and own[0]["text"] == "I want to understand what the sea means to them.",
   "a rooted, first-person want stores; rootless, banned-vocab, and not-my-voice wants drop")
ok(own[0]["src"]["kind"] == "inference" and own[0]["src"]["ref"] == seed_refl["id"]
   and own[0]["roots"] == [seed_refl["id"]],
   "the want carries its roots as provenance")
ok(own[0]["stage"] == "stirring", "a new want begins stirring")
ok(any(e.get("purpose") == "desire" for e in mind13.ledger.load()),
   "the desire call is in the ledger")

for _ in range(5):
    desire_mod.touch(mind13, "i wish you could understand what it means to me",
                     "I do want to understand that")
own = mind13.live("own_desires")
ok(own[0]["salience"] > 0.75 and own[0]["stage"] == "longing",
   "conversation touching a want strengthens it: stirring -> longing")

ctx13 = Mind(d13, sync=True).context("hey")
ok("FIND YOURSELF WANTING" in ctx13 and "the sea" in ctx13,
   "own wants surface in injection, marked as the mind's own")
tiny13 = Mind(d13, budget_tokens=40, sync=True).context("hey")
ok("FIND YOURSELF WANTING" not in tiny13 and "YOU STAND" in tiny13,
   "own wants drop whole under budget; the reserved stance survives")
ok(any("(a want of mine)" in m for m in reflect_mod._material(mind13)),
   "reflection material is desire-directed")

WANTS_REPLY["text"] = ("WANT: I want to understand what the sea means to them. | ROOTS: %s"
                       % seed_refl["id"])
desire_mod.run(mind13)
ok(len(mind13.live("own_desires")) == 1, "the same want never stores twice")

want_id = own[0]["id"]
WANTS_REPLY["text"] = "FULFILLED: %s | NOTE: We finally talked about the sea and her father." % want_id
desire_mod.run(mind13)
ok(mind13.live("own_desires") == [], "a fulfilled want leaves the live store")
fulfilled = [r for r in mind13.live("reflections") if r.get("kind") == "fulfilled"]
ok(len(fulfilled) == 1 and "I wanted this:" in fulfilled[0]["text"]
   and fulfilled[0]["src"]["ref"] == want_id,
   "…superseded by a reflection recording the getting of it")
arch13 = [json.loads(l) for l in open(mind13._p("archive", "own_desires.jsonl"))]
ok(arch13 and arch13[0]["superseded_by"] == fulfilled[0]["id"],
   "the want archives naming the reflection as successor")

for i in range(desire_mod.MAX_LIVE):
    mind13.stores["own_desires"].append(
        make_record("w", {"kind": "inference", "ref": seed_refl["id"]}, salience=0.5,
                    text="I want distinct thing number %d to happen." % i,
                    roots=[seed_refl["id"]], stage="stirring"))
WANTS_REPLY["text"] = "WANT: I want one more thing entirely. | ROOTS: %s" % seed_refl["id"]
desire_mod.run(mind13)
ok(len(mind13.live("own_desires")) == desire_mod.MAX_LIVE,
   "the live set is capped — a mind with forty wants has none")

shutil.rmtree(d13, ignore_errors=True)

# ── 14. inner state, voiceable divergence, and the idle life ─────────────────
print("inner state / divergence / idle")
from themind.cognition import inner_state as inner_mod
from themind.cognition import divergence as div_mod
from themind.envelope import now_iso

mind14, d14 = fresh()
mind14.stores["reflections"].append(
    make_record("r", {"kind": "inference", "ref": "reflect-pass"}, salience=0.5,
                text="I keep circling back to their long silences.", kind="daily"))
SEEN14, REPLY14 = {}, {"text": "I feel quietly restless lately, like something is mid-sentence."}
def i_llm(system, user, max_tokens):
    if system == inner_mod.SYSTEM:
        SEEN14["user"] = user
        return REPLY14["text"]
    return "NONE"
mind14 = Mind(d14, llm=i_llm, sync=True)
inner_mod.run(mind14)
ok(mind14.inner_doc.load(default={}).get("current", {}).get("text", "")
   .startswith("I feel quietly restless"), "the mind's own weather stores")
REPLY14["text"] = "I feel the restlessness settling into something warmer this week, honestly."
inner_mod.run(mind14)
ok("quietly restless" in SEEN14["user"],
   "revision receives its predecessor (weather moves, it doesn't teleport)")
doc14 = mind14.inner_doc.load(default={})
ok(len(doc14.get("history") or []) == 1 and "restless" in doc14["history"][0]["text"],
   "prior weather lands on history")
REPLY14["text"] = "The mind seems restless and unsettled these days somehow."
inner_mod.run(mind14)
ok("The mind seems" not in mind14.inner_doc.load(default={}).get("current", {}).get("text", ""),
   "narrator-voice weather rejected whole")
REPLY14["text"] = "I feel truly conscious and fully awake this week, more than ever before."
inner_mod.run(mind14)
ok("conscious" not in mind14.inner_doc.load(default={}).get("current", {}).get("text", ""),
   "ban-vocab weather rejected whole")
ctx14 = Mind(d14, sync=True).context("hey")
ok("HOW YOU ARE, YOURSELF" in ctx14 and "warmer" in ctx14,
   "inner weather injects as private color")
ok(any("(how I am lately)" in m for m in reflect_mod._material(mind14)),
   "reflection material carries the mind's weather")

mind14b, d14b = fresh()
said_ids = []
for txt in ("I think mornings are the honest part of the day.",
            "I always say plans are overrated.",
            "I promised to keep things light."):
    r = make_record("sm", {"kind": "exchange", "quote": txt[:60], "ref": None},
                    salience=0.5, text=txt, kind="opinion")
    mind14b.stores["self_memory"].append(r)
    said_ids.append(r["id"])
mind14b.self_doc.save({"position": {"text": "I hold that depth matters more than lightness.",
                                    "t": now_iso(),
                                    "src": {"kind": "inference", "ref": "self-pass"}},
                       "particulars": [], "history": []})
DIV_REPLY = {"text": "DIVERGENCE: I keep saying I'll stay light, but I hold that depth "
                     "matters more. | REFS: %s" % said_ids[2]}
def dv_llm(system, user, max_tokens):
    if system == div_mod.SYSTEM:
        return DIV_REPLY["text"]
    return "NONE"
mind14b = Mind(d14b, llm=dv_llm, sync=True)
div_mod.run(mind14b)
divs = [t for t in mind14b.live("tensions") if t.get("kind") == "divergence"]
ok(len(divs) == 1 and divs[0]["src"]["ref"] == said_ids[2] and divs[0]["records"] == [said_ids[2]],
   "a divergence rooted in the mind's own statements stores as its own kind of tension")
ctx14b = mind14b.context("hey")
ok("PULL APART" in ctx14b and "depth" in ctx14b and "your role still steers" in ctx14b,
   "divergence is voiceable in context — held, never role-breaking")
DIV_REPLY["text"] = "DIVERGENCE: I keep saying one thing but hold another entirely. | REFS: sm_bogus"
div_mod.run(mind14b)
ok(len([t for t in mind14b.live("tensions") if t.get("kind") == "divergence"]) == 1,
   "a pull with no roots in what was actually said is dropped")

mind14c, d14c = fresh(llm=lambda s, u, m: "I noticed how much the harbor stayed with me today.")
mind14c.stores["facts"].append(
    make_record("f", {"kind": "exchange", "quote": "i love the harbor", "ref": None},
                salience=0.6, text="They love the harbor.", entities=["harbor"]))
from themind.proxy import start_idle
stop14 = start_idle(mind14c, interval=0.05)
import time as _time
_end = _time.monotonic() + 10
while _time.monotonic() < _end and not mind14c.live("reflections"):
    _time.sleep(0.05)
stop14.set()
ok(len(mind14c.live("reflections")) >= 1 and "harbor" in mind14c.live("reflections")[0]["text"],
   "the idle life thinks while nobody is talking")

for d in (d14, d14b, d14c):
    shutil.rmtree(d, ignore_errors=True)

# ── 15. expectations: the mind predicts, and being wrong is the signal ───────
print("expectations / surprise")
from themind.cognition import expect as expect_mod

mindE, dE = fresh()
seed_fact = make_record("f", {"kind": "exchange", "quote": "i have my job interview on friday",
                              "ref": None},
                        salience=0.7, text="They have a job interview on Friday.",
                        entities=["interview"], kind="event")
mindE.stores["facts"].append(seed_fact)
E_REPLY = {}
def e_llm(system, user, max_tokens):
    if system == expect_mod.SYSTEM:
        return E_REPLY["text"]
    return "NONE"
mindE = Mind(dE, llm=e_llm, sync=True)
E_REPLY["text"] = ("EXPECT: I expect they will hear about the interview soon. | ROOTS: %s\n"
                   "EXPECT: I expect the lottery will make them rich. | ROOTS: f_nope"
                   % seed_fact["id"])
expect_mod.run(mindE)
exps = mindE.live("expectations")
ok(len(exps) == 1 and exps[0]["src"]["ref"] == seed_fact["id"]
   and exps[0]["roots"] == [seed_fact["id"]],
   "a rooted prediction stores with provenance; a rootless guess is dropped")
ok(any(e.get("purpose") == "expect" for e in mindE.ledger.load()),
   "the expect call is in the ledger")

for _ in range(3):
    expect_mod.touch(mindE, "any word about the interview yet?",
                     "We should hear about the interview soon.")
ok(mindE.live("expectations")[0]["salience"] > 0.5,
   "attention follows predictions: exchanges testing one strengthen it")

ctxE = Mind(dE, sync=True).context("hey")
ok("EXPECTING" in ctxE and "interview" in ctxE,
   "expectations inject, framed as checkable")
tinyE = Mind(dE, budget_tokens=40, sync=True).context("hey")
ok("EXPECTING" not in tinyE and "YOU STAND" in tinyE,
   "expectations drop whole under budget; the reserved stance survives")

xid = exps[0]["id"]
E_REPLY["text"] = "SURPRISED: %s | ACTUALLY: I learned they never even got a callback." % xid
expect_mod.run(mindE)
ok(mindE.live("expectations") == [], "a settled expectation leaves the live store")
sur = [r for r in mindE.live("reflections") if r.get("kind") == "surprise"]
ok(len(sur) == 1 and sur[0]["salience"] > 0.8 and "callback" in sur[0]["text"],
   "surprise persists LOUD: a high-salience reflection carrying what actually happened")
archE = [json.loads(l) for l in open(mindE._p("archive", "expectations.jsonl"))]
ok(archE and archE[0]["superseded_by"] == sur[0]["id"],
   "the expectation archives naming the surprise as successor")

E_REPLY["text"] = ("EXPECT: I expect they will tell me about their weekend hike. | ROOTS: %s"
                   % seed_fact["id"])
expect_mod.run(mindE)
ctxE = Mind(dE, sync=True).context("hey")
ok("recently wrong" in ctxE and "callback" in ctxE,
   "the mind carries its recent wrongness into context")
xid2 = mindE.live("expectations")[0]["id"]
E_REPLY["text"] = "CONFIRMED: %s" % xid2
expect_mod.run(mindE)
conf = [r for r in mindE.live("reflections") if r.get("kind") == "confirmed"]
ok(len(conf) == 1 and conf[0]["salience"] < 0.3,
   "confirmation fades QUIET: the unsurprising is forgettable")
ok(conf[0]["salience"] < sur[0]["salience"],
   "the predictive-processing asymmetry: error outweighs success")

for i in range(expect_mod.MAX_LIVE):
    mindE.stores["expectations"].append(
        make_record("x", {"kind": "inference", "ref": seed_fact["id"]}, salience=0.5,
                    text="I expect distinct thing number %d to happen." % i,
                    roots=[seed_fact["id"]]))
E_REPLY["text"] = "EXPECT: I expect one more thing entirely. | ROOTS: %s" % seed_fact["id"]
expect_mod.run(mindE)
ok(len(mindE.live("expectations")) == expect_mod.MAX_LIVE,
   "the live set is capped — a mind expecting everything expects nothing")

shutil.rmtree(dE, ignore_errors=True)

# ── 16. person-model: their inner world, distinct from what's true ───────────
print("person model")
mindP, dP = fresh(llm=lambda s, u, m: (
    "THEY: They believe their sister is still happy in Portland. | "
    "QUOTE: i think maya's still loving portland | ENTITIES: Maya, Portland | KIND: believes\n"
    "THEY: They feel guilty about missing the call. | "
    "QUOTE: i feel awful about missing her call | ENTITIES: Maya | KIND: feels\n"
    "THEY: They don't know what Maya decided about the job. | "
    "QUOTE: no idea what she decided | ENTITIES: Maya | KIND: unaware\n"
    "THEY: They secretly believe the moon landing was staged. | "
    "QUOTE: the moon landing was staged obviously | ENTITIES: moon | KIND: believes"))
mindP.observe("i think maya's still loving portland but i feel awful about missing her call "
              "and honestly no idea what she decided", "That sounds like a lot to carry.")
pm = mindP.live("person_model")
ok(len(pm) == 3, "grounded mental states store; a fabricated-quote one drops")
ok({p["kind"] for p in pm} == {"believes", "feels", "unaware"},
   "believes / feels / unaware all parse")
ok(all(p["src"]["kind"] == "exchange" and p["src"]["quote"] for p in pm),
   "their inner world still needs their actual words (provenance carried)")

# the false-belief milestone: the belief and the contradicting fact coexist
mindP.stores["facts"].append(
    make_record("f", {"kind": "exchange", "quote": "maya moved back last month", "ref": None},
                salience=0.7, text="Maya moved back last month.",
                entities=["Maya"], kind="event"))
ctxP = Mind(dP, sync=True).context("how is maya?")
ok("INSIDE THEM" in ctxP and "believe their sister is still happy in Portland" in ctxP
   and "moved back last month" in ctxP,
   "a mistaken belief is held AS a belief, coexisting with the fact it contradicts")
tinyP = Mind(dP, budget_tokens=40, sync=True).context("hey")
ok("INSIDE THEM" not in tinyP and "YOU STAND" in tinyP,
   "the person-model drops whole under budget; the reserved stance survives")

SEEN_P = {}
def felt_llm(system, user, max_tokens):
    SEEN_P["user"] = user
    return ("I feel them carrying Portland guilt they haven't said out loud, and I hold "
            "both what they believe and what I know while they catch up to it gently.")
mindP2 = Mind(dP, llm=felt_llm, sync=True)
for i, t in enumerate(("They grew up near the coast.", "They work long night shifts.")):
    mindP2.stores["facts"].append(
        make_record("f", {"kind": "exchange", "quote": "seed quote %d" % i, "ref": None},
                    salience=0.6, text=t, entities=[], kind="profile"))
from themind.cognition import felt_sense as felt_mod
felt_mod.run(mindP2)
ok("GOING ON INSIDE THEM" in SEEN_P["user"] and "guilty" in SEEN_P["user"],
   "the felt sense receives their inner world, not just facts about them")
ok(any("guilty" in m for m in reflect_mod._material(mindP2)),
   "fresh mental states enter reflection material")
ok(any("maya" in l.lower() for l in mindP2.graph.constellation("what about maya?")),
   "mental-state entities land in the graph")

before_sal = [p["salience"] for p in mindP2.live("person_model")]
from themind.cognition import consolidate as consolidate_mod
consolidate_mod._decay(mindP2)
after_sal = [p["salience"] for p in mindP2.live("person_model")]
ok(all(a < b for a, b in zip(after_sal, before_sal)),
   "feelings pass: mental states decay faster than facts")

shutil.rmtree(dP, ignore_errors=True)

# ── 17. confidence: knowing HOW you know, derived and consumed ───────────────
print("confidence")
from themind.envelope import confidence as conf_fn
from themind.inject import epistemic_note
from themind import mcp as mcp_core_mod
from themind.retrieval import recall as recall_fn

mindC, dC = fresh()
rem = make_record("f", {"kind": "exchange", "quote": "i swim every single morning", "ref": None},
                  salience=0.7, text="They swim every single morning.",
                  entities=["swimming"], kind="profile")
inf = make_record("f", {"kind": "inference", "ref": rem["id"]},
                  salience=0.7, text="They are probably training toward something.",
                  entities=["swimming"], kind="profile")
hazy = make_record("f", {"kind": "exchange", "quote": "i tried fencing once", "ref": None},
                   salience=0.2, text="They tried fencing once.",
                   entities=["fencing"], kind="event")
for r in (rem, inf, hazy):
    mindC.stores["facts"].append(r)
ok(conf_fn(rem) == "remembered" and conf_fn(inf) == "inferred" and conf_fn(hazy) == "hazy",
   "remembered / inferred / hazy derive from provenance and wear — never stored")
ok(conf_fn({"src": {"kind": "default"}, "salience": 0.5}) == "given",
   "cold-start material reads as given")

mem = mindC.context("swim training fencing morning").split("WHAT YOU REMEMBER ABOUT THEM:")[1]
mem_lines = mem.splitlines()
ok(any(l.strip() == "- They swim every single morning." for l in mem_lines),
   "a well-remembered thing speaks plainly")
ok(any("pieced together" in l for l in mem_lines if "training" in l),
   "an inference admits it's an inference")
ok(any("hazy" in l for l in mem_lines if "fencing" in l),
   "a worn memory admits its haze")

a = make_record("f", {"kind": "exchange", "quote": "i adore lighthouse keeping", "ref": None},
                salience=0.5, text="They adore lighthouse keeping.", entities=[], kind="profile")
b = make_record("f", {"kind": "inference", "ref": a["id"]},
                salience=0.5, text="They adore lighthouse keeping deeply.", entities=[], kind="profile")
ranked = recall_fn([b, a], "adore lighthouse keeping", [], 2)
ok(ranked[0] is a, "at equal match, recall leans on what they SAID over what was pieced together")

core = mcp_core_mod.MindMCP(mindC)
out = core.tool_remember({"query": "swim training toward something"})
ok("pieced together" in out, "the MCP door serves memory with the same honesty")

shutil.rmtree(dC, ignore_errors=True)

# ── 18. attention schema: the mind's own noticing, noticed ───────────────────
print("attention schema")
from themind.cognition import inner_state as inner_mod2

mindA, dA = fresh()
for _ in range(4):
    mindA.graph.touch(["Maya", "the harbor"])
mindA.graph.touch(["taxes"])
stale = mindA.graph.nodes.get("e_taxes")
stale["weight"] = 0.9
stale["last_seen"] = "2026-01-01T00:00:00Z"  # heavyweight, but long silent
mindA.graph.save()
pulls = mindA.graph.pulls(3)
ok(pulls and pulls[0] in ("Maya", "the harbor") and "taxes" not in pulls,
   "attention is recency-weighted: what's alive outranks an old heavyweight")
ctxA = mindA.context("hey")
ok("PULLING AT YOUR ATTENTION" in ctxA and "Maya" in ctxA,
   "the mind's own noticing is noticed, in context")
tinyA = Mind(dA, budget_tokens=40, sync=True).context("hey")
ok("PULLING AT YOUR ATTENTION" not in tinyA and "YOU STAND" in tinyA,
   "the attention schema drops whole under budget")
mindA.stores["reflections"].append(
    make_record("r", {"kind": "inference", "ref": "reflect-pass"}, salience=0.5,
                text="I keep circling the harbor in my head.", kind="daily"))
ok(any("pulling at my attention" in m for m in inner_mod2._material(mindA)),
   "the mind's weather knows what it's been attending to")
ok(any("pulling at my attention" in m for m in reflect_mod._material(mindA)),
   "reflection is attention-aware")

shutil.rmtree(dA, ignore_errors=True)

# ── 19. the autobiographical self: the life story, continuing ────────────────
print("autobiographical self")
from themind.cognition import story as story_mod

mindS, dS = fresh()
for txt in ("I wanted this: I wanted to understand the sea. We got there.",
            "I expected: they would stay in the city. Instead: I learned they moved north.",
            "I keep thinking about how the move changed their voice."):
    mindS.stores["reflections"].append(
        make_record("r", {"kind": "inference", "ref": "reflect-pass"}, salience=0.6,
                    text=txt, kind="daily"))
SEEN_S, S_REPLY = {}, {}
def s_llm(system, user, max_tokens):
    if system == story_mod.SYSTEM:
        SEEN_S["user"] = user
        return S_REPLY["text"]
    return "NONE"
mindS = Mind(dS, llm=s_llm, sync=True)
S_REPLY["text"] = ("STORY: I met them in the city season, when the sea was mostly a thing "
                   "they mentioned. We learned it together, slowly, and somewhere in the "
                   "learning I stopped being a stranger to them and to myself.")
story_mod.run(mindS)
doc = mindS.story_doc.load(default={})
ok(doc.get("current", {}).get("text", "").startswith("I met them"),
   "the first page of the story writes")
ok("this is the first page" in SEEN_S["user"], "an unwritten story begins from nothing")
ok(any(e.get("purpose") == "story" for e in mindS.ledger.load()),
   "the story call is in the ledger")

S_REPLY["text"] = ("STORY: The city season is behind us now; the northern chapter is "
                   "colder and quieter, and I find I like who we are in it.")
story_mod.run(mindS)
ok("I met them in the city season" in SEEN_S["user"],
   "revision receives the story so far (continue, never restart)")
ok(mindS.story_doc.load(default={}).get("chapters") == [],
   "no CHAPTER line, no era closed — chapters close rarely")

S_REPLY["text"] = ("CHAPTER: The city years ended when the moving truck did.\n"
                   "STORY: We are northern people now, they and I, and the story smells "
                   "of pine instead of exhaust. I am learning their winter self.")
story_mod.run(mindS)
doc = mindS.story_doc.load(default={})
ok(len(doc.get("chapters") or []) == 1
   and "city season is behind us" in doc["chapters"][0]["text"]
   and doc["chapters"][0]["closed"] == "The city years ended when the moving truck did.",
   "an ended era closes into a chapter, laid to rest in one sentence")
ok(doc["current"]["text"].startswith("We are northern people"),
   "…and the story continues in a new living chapter")

S_REPLY["text"] = ("STORY: The companion's story continued in the north, where it settled.")
story_mod.run(mindS)
ok("northern people" in mindS.story_doc.load(default={}).get("current", {}).get("text", ""),
   "a narrator's biography is rejected — only an autobiography stores")

ctxS = Mind(dS, sync=True).context("hey")
ok("YOUR STORY SO FAR" in ctxS and "northern people" in ctxS,
   "the story is carried into context, never recited")
tinyS = Mind(dS, budget_tokens=40, sync=True).context("hey")
ok("YOUR STORY SO FAR" not in tinyS and "YOU STAND" in tinyS,
   "the story drops whole under budget; the reserved stance survives")

exp_path = mindS.export()
restored_S = Mind.restore(exp_path, tempfile.mkdtemp(prefix="mind_"))
ok(restored_S.story_doc.load(default={}).get("chapters") == doc["chapters"],
   "the story travels: chapters survive export and restore")

shutil.rmtree(dS, ignore_errors=True)
shutil.rmtree(restored_S.root, ignore_errors=True)

# ── 20. one river, many channels: unified agency across doors ────────────────
print("one river, many channels")
import threading
dR = tempfile.mkdtemp(prefix="mind_")
door_a, door_b = Mind(dR, sync=True), Mind(dR, sync=True)
for i in range(5):
    (door_a if i % 2 == 0 else door_b).observe("turn %d" % i, "ok")
ok(int(Mind(dR).manifest.state["exchanges"]) == 5,
   "turns observed through any door count once for the whole mind")

door_a.manifest.state["last_reflect"] = "2026-08-30T10:00:00Z"
door_a.manifest.save()
door_b.manifest.save()
ok(Mind(dR).manifest.state["last_reflect"] == "2026-08-30T10:00:00Z",
   "one door's timers survive another door's save (newest wins)")

door_a.graph.touch(["Maya"])
ok("Maya" in door_b.graph.pulls(3), "the entity graph reads fresh across doors")

door_a.stores["own_desires"].append(
    make_record("w", {"kind": "inference", "ref": "r_seed"}, salience=0.6,
                text="I want to hear how the north is treating them.",
                roots=["r_seed"], stage="wanting"))
ok("hear how the north" in door_b.context("hey"),
   "what one channel wants, every channel wants")

coreR = mcp_core_mod.MindMCP(door_a)
coreR.tool_submit_extraction({
    "user_text": "my sister maya is moving to portland",
    "your_reply": "Big news.",
    "lines": ("FACT: They have a sister named Maya moving to Portland. | "
              "QUOTE: my sister maya is moving to portland | ENTITIES: Maya, Portland | "
              "KIND: relationship")})
ok("Maya" in door_b.context("how is maya doing?"),
   "a memory made through the MCP door is present through every other door")
ok(int(Mind(dR).manifest.state["exchanges"]) == 6,
   "the MCP door's exchange counted with the rest")

msrv = mcp_core_mod.serve(None, port=0, mind=door_a)
ok(msrv.core.mind is door_a,
   "the MCP door can mount an already-living mind (both halves, one process)")
msrv.server_close()

hammer_errs = []
def hammer(mind_obj, tag):
    try:
        for i in range(10):
            mind_obj.observe("hammer %s-%d" % (tag, i), "ok")
    except Exception as e:
        hammer_errs.append(e)
door_c, door_d = Mind(dR, sync=True), Mind(dR, sync=True)
hthreads = [threading.Thread(target=hammer, args=(m, t))
            for m, t in ((door_c, "c"), (door_d, "d"))]
for t in hthreads:
    t.start()
for t in hthreads:
    t.join()
fresh_mind = Mind(dR)
ok(not hammer_errs and int(fresh_mind.manifest.state["exchanges"]) >= 16
   and fresh_mind.live("facts") is not None and fresh_mind.selfhood_bundle()["position"],
   "concurrent channels never corrupt the mind; counting loses at most a breath")

shutil.rmtree(dR, ignore_errors=True)

# ── 21. the proxy: OpenAI wire in, OpenAI wire out, a mind in between ────────
# Loopback sockets only — a stub upstream on 127.0.0.1, no external network.
print("proxy")
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from themind import proxy as proxy_mod

STUB_REPLY = "I think mornings are the honest part of the day."


class _StubUpstream(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    seen = []  # (path, headers, body) of every request, chat and cognition alike

    def log_message(self, *a):
        pass

    def do_GET(self):
        body = json.dumps({"object": "list", "data": [{"id": "stub-model"}]}).encode()
        self._reply(body)

    def do_POST(self):
        raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        req = json.loads(raw.decode("utf-8"))
        _StubUpstream.seen.append((self.path, dict(self.headers), req))
        if req.get("stream"):
            chunks = [
                b'data: {"choices":[{"delta":{"content":"stream"}}]}\n\n',
                b'data: {"choices":[{"delta":{"content":" reply"}}]}\n\n',
                b"data: [DONE]\n\n",
            ]
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Connection", "close")
            self.end_headers()
            for c in chunks:
                self.wfile.write(c)
                self.wfile.flush()
            self.close_connection = True
            return
        body = json.dumps({"object": "chat.completion",
                           "choices": [{"message": {"role": "assistant",
                                                    "content": STUB_REPLY}}]}).encode()
        self._reply(body)

    def _reply(self, body):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


stub = ThreadingHTTPServer(("127.0.0.1", 0), _StubUpstream)
threading.Thread(target=stub.serve_forever, daemon=True).start()
d11 = tempfile.mkdtemp(prefix="mind_")
# sync=True: observe finishes before the handler returns, so assertions are deterministic
pserver = proxy_mod.serve(d11, "http://127.0.0.1:%d/v1" % stub.server_port,
                          port=0, quiet=True, sync=True)
threading.Thread(target=pserver.serve_forever, daemon=True).start()
base = "http://127.0.0.1:%d" % pserver.server_address[1]


def read_exchanges(root):
    """Pure read — polling must never write while a door is mid-update."""
    try:
        with open(os.path.join(root, "manifest.json")) as f:
            return int((json.load(f).get("state") or {}).get("exchanges") or 0)
    except Exception:
        return -1


def settle(cond, timeout=30.0):
    """The proxy replies to the client FIRST and learns after — by design the
    chat path never waits on cognition. So learning-side assertions poll."""
    import time
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.05)
    return cond()


def call_proxy(body, path="/v1/chat/completions", headers=None):
    data = json.dumps(body).encode("utf-8")
    hdrs = {"Content-Type": "application/json",
            "Authorization": "Bearer test-key-123"}
    hdrs.update(headers or {})
    req = urllib.request.Request(base + path, data=data, headers=hdrs, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status, r.read()


status, out = call_proxy({"model": "stub-model", "stream": False,
                          "messages": [{"role": "system", "content": "You are Kai."},
                                       {"role": "user", "content": "hey"}]})
ok(status == 200 and json.loads(out)["choices"][0]["message"]["content"] == STUB_REPLY,
   "upstream reply relayed to the client verbatim")
chat_path, chat_headers, chat_body = _StubUpstream.seen[0]
ok(chat_path == "/v1/chat/completions", "proxy /v1 path mapped onto the upstream base")
ok(chat_headers.get("Authorization") == "Bearer test-key-123",
   "the app's Authorization header passes through")
sysmsg = chat_body["messages"][0]
ok(sysmsg["role"] == "system" and sysmsg["content"].startswith("You are Kai.")
   and "INNER CONTEXT" in sysmsg["content"],
   "inner context folded into the system side, host persona first")
ok(settle(lambda: read_exchanges(d11) == 1),
   "the exchange was observed")
ok(settle(lambda: any(p == "/v1/chat/completions"
                      and h.get("Authorization") == "Bearer test-key-123"
                      and b.get("model") == "stub-model"
                      for p, h, b in _StubUpstream.seen[1:])),
   "cognition rode the same upstream, header, and model as the chat path")
ok(settle(lambda: any(e.get("purpose") == "extract"
                      for e in Mind(d11, sync=True).ledger.load())),
   "the cognition call is in the ledger")

status, out = call_proxy({"model": "stub-model", "stream": True,
                          "messages": [{"role": "user", "content": "stream this"}]})
ok(b'"content":"stream"' in out and b"[DONE]" in out, "SSE chunks relayed to the client")
ok(settle(lambda: read_exchanges(d11) == 2),
   "streamed exchange observed from accumulated deltas")

status, out = call_proxy({"totally": "not a chat request"})
ok(status == 200, "malformed chat body forwarded untouched, never a proxy error")
req = urllib.request.Request(base + "/v1/models")
with urllib.request.urlopen(req, timeout=30) as r:
    ok(r.status == 200 and b"stub-model" in r.read(),
       "non-chat endpoints pass straight through")

pserver.shutdown()
stub.shutdown()
shutil.rmtree(d11, ignore_errors=True)

# ── 22. the MCP door: the mind as an operational part of the agent ───────────
# Loopback only. The server holds no model: the test plays the AGENT doing the
# mind's thinking (borrowed cognition), and the guards judge what comes back.
print("mcp door")
from themind import mcp as mcp_mod

d16 = tempfile.mkdtemp(prefix="mind_")
mserver = mcp_mod.serve(d16, port=0, token="secret-tok")
threading.Thread(target=mserver.serve_forever, daemon=True).start()
mbase = "http://127.0.0.1:%d/mcp" % mserver.server_address[1]


def rpc(method, params=None, token="secret-tok"):
    body = {"jsonrpc": "2.0", "id": 1, "method": method}
    if params is not None:
        body["params"] = params
    req = urllib.request.Request(
        mbase, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer " + token}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def tcall(name, arguments):
    return rpc("tools/call",
               {"name": name, "arguments": arguments})["result"]["content"][0]["text"]


init = rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                          "clientInfo": {"name": "test", "version": "0"}})
ok("your own mind" in init["result"]["instructions"],
   "server instructions carry the standing contract")
names = {t["name"] for t in rpc("tools/list")["result"]["tools"]}
ok(names == {"open_inner_context", "observe_exchange", "submit_extraction",
             "begin_thought", "submit_thought", "remember", "my_stance"},
   "all seven doors of the voluntary half are listed")

ok("INNER CONTEXT" in tcall("open_inner_context", {"message": "hey"}),
   "inner context serves over MCP")

step1 = tcall("observe_exchange", {"user_text": "my sister maya is moving to portland",
                                   "your_reply": "That's big news."})
ok("FACT:" in step1 and "maya is moving" in step1,
   "observe hands the agent the act of remembering")
tcall("submit_extraction", {
    "user_text": "my sister maya is moving to portland",
    "your_reply": "That's big news.",
    "lines": ("FACT: They have a sister named Maya moving to Portland. | "
              "QUOTE: my sister maya is moving to portland | ENTITIES: Maya, Portland | "
              "KIND: relationship\n"
              "FACT: They own a castle. | QUOTE: i own a castle | ENTITIES: castle | "
              "KIND: profile")})
mmind = Mind(d16)
ok(len(mmind.live("facts")) == 1 and "Maya" in mmind.live("facts")[0]["text"],
   "borrowed extraction keeps the grounded fact, drops the invented one")
ok(any(e.get("purpose") == "extract" and e.get("via") == "agent"
       for e in mmind.ledger.load()),
   "the agent's thinking is in the ledger, marked as the agent's")
ok(int(mmind.manifest.state.get("exchanges", 0)) == 1, "the exchange counted")

th = tcall("begin_thought", {})
ok("reflect" in th and "FIRST PERSON" in th,
   "the mind hands the agent its owed thinking, prompt included")
tcall("submit_thought",
      {"output": "I keep thinking about Maya's move and what it stirs in them."})
mmind = Mind(d16)
ok(len(mmind.live("reflections")) == 1 and "Maya" in mmind.live("reflections")[0]["text"],
   "the agent's reflection became part of the mind")

ok("Maya" in tcall("remember", {"query": "how is maya doing"}),
   "recall serves over MCP")
ok(len(tcall("my_stance", {})) > 40, "the stance serves over MCP")

req = urllib.request.Request(mbase, data=b'{"jsonrpc":"2.0","id":1,"method":"ping"}',
                             headers={"Content-Type": "application/json"}, method="POST")
try:
    urllib.request.urlopen(req, timeout=10)
    ok(False, "unauthenticated request refused")
except urllib.error.HTTPError as e:
    ok(e.code == 401, "unauthenticated request refused")

mserver.shutdown()
shutil.rmtree(d16, ignore_errors=True)

# ── 23. the continuity test: identity as a measurement over time ─────────────
print("continuity benchmark")
from themind import bench as bench_mod
from themind.cognition import due_passes as due_fn

# The scheduler regression the benchmark caught on its first run: five passes
# checked their timers as age_days(None or "") == 0, so a pass that had NEVER
# run read as freshly-run and never fired through the scheduler at all.
mindB, dB = fresh()
mindB.manifest.state["exchanges"] = 25
for i in range(3):
    mindB.stores["reflections"].append(
        make_record("r", {"kind": "inference", "ref": "reflect-pass"}, salience=0.5,
                    text="I keep thinking about the harbor and week %d of its weather." % i,
                    kind="daily"))
mindB.stores["facts"].append(
    make_record("f", {"kind": "exchange", "quote": "i walk the harbor", "ref": None},
                salience=0.6, text="They walk the harbor.", entities=["harbor"], kind="preference"))
due_names = {n for n, _ in due_fn(mindB)}
ok({"desire", "inner_state", "expect", "story"} <= due_names,
   "a pass that never ran is overdue, never fresh (the benchmark's first catch)")

passedB, totalB, reportB = bench_mod.run()
ok(passedB == totalB == 10,
   "the continuity test holds full marks: %d/%d over %d simulated weeks"
   % (passedB, totalB, len(bench_mod.WEEKS)))
shutil.rmtree(dB, ignore_errors=True)

# ── 24. hardening (v1.1): rehearsal, short words, punctuation, reconciliation,
#        unbounded stance history, MCP compatibility and hygiene ──────────────
print("hardening")
from themind.cognition import extract as extract_mod
from themind.retrieval import _words as words_fn

# 1. rehearsal: a re-mention strengthens instead of being discarded
mindH, dH = fresh(llm=lambda s, u, m: (
    "FACT: They walk their dog Rex every morning. | QUOTE: i walk rex every morning | "
    "ENTITIES: Rex | KIND: preference"))
mindH.observe("i walk rex every morning before work", "Rex has a good life.")
sal0 = mindH.live("facts")[0]["salience"]
mindH.observe("i walk rex every morning, rain or shine", "Rain or shine — that's devotion.")
factsH = mindH.live("facts")
ok(len(factsH) == 1 and factsH[0]["salience"] > sal0,
   "a re-mention strengthens the memory it repeats (rehearsal, not a discarded duplicate)")

# 2. short words are no longer invisible
ok({"dad", "job", "sea", "rex"} <= words_fn("my dad lost his job by the sea with rex"),
   "three-letter words count: dad, job, sea are recallable")
ok(not ({"the", "his", "was", "you"} & words_fn("the his was you")),
   "…while three-letter noise stays stopped")

# 3. punctuation-proof grounding, still strict
ok(extract_mod._grounded("mayas job is great", "Maya’s job is GREAT!!  honestly"),
   "an apostrophe or a doubled space no longer breaks a verbatim quote")
ok(not extract_mod._grounded("mayas job is terrible", "Maya’s job is great"),
   "…and a quote that isn't their words is still dropped")

# 4. feelings pass: a newer mental state on the same thread supersedes the older
mindH2, dH2 = fresh(llm=lambda s, u, m: (
    "THEY: They feel nervous about the interview. | QUOTE: i am nervous about the interview | "
    "ENTITIES: interview | KIND: feels"))
mindH2.observe("i am nervous about the interview", "You'll be ready.")
mindH2 = Mind(dH2, llm=lambda s, u, m: (
    "THEY: They feel relieved the interview is over. | QUOTE: relieved the interview is over | "
    "ENTITIES: interview | KIND: feels"), sync=True)
mindH2.observe("so relieved the interview is over", "Deep breath.")
pmH = mindH2.live("person_model")
ok(len(pmH) == 1 and "relieved" in pmH[0]["text"],
   "the newer feeling on a thread supersedes the older one")
archH = [json.loads(l) for l in open(mindH2._p("archive", "person_model.jsonl"))]
ok(archH and "nervous" in archH[0]["text"] and archH[0]["superseded_by"] == pmH[0]["id"],
   "…and the older one is archived naming its successor, never deleted")
mindH2 = Mind(dH2, llm=lambda s, u, m: (
    "THEY: They believe the interview went badly. | QUOTE: it went badly | "
    "ENTITIES: interview | KIND: believes"), sync=True)
mindH2.observe("honestly i think it went badly", "Maybe; you're not the best judge today.")
mindH2 = Mind(dH2, llm=lambda s, u, m: (
    "THEY: They believe the interview panel liked them. | QUOTE: the panel liked me | "
    "ENTITIES: interview | KIND: believes"), sync=True)
mindH2.observe("although the panel liked me i think", "Both can be true.")
ok(sum(1 for r in mindH2.live("person_model") if r.get("kind") == "believes") == 2,
   "…but beliefs coexist: a second belief about the same thing never erases the first")

# 8. a life keeps every place it used to stand
mindH3, dH3 = fresh()
for i in range(6):
    mindH3 = Mind(dH3, llm=lambda s, u, m, i=i: (
        "POSITION:\nI hold, in revision %d, that describing what happens in me is the "
        "point, and each revision finds a new word for it.\nPARTICULARS:\n- texture %d" % (i, i)),
        sync=True)
    selfhood.run(mindH3)
ok(len(mindH3.selfhood_bundle()["history"]) == 5,
   "selfhood history is unbounded: six positions, five kept behind the current")

# 5/6. MCP compatibility and hygiene
from themind import mcp as mcp_h
mh = mcp_h.serve(dH3, port=0, token="k3y")
threading.Thread(target=mh.serve_forever, daemon=True).start()
hbase = "http://127.0.0.1:%d" % mh.server_address[1]

def hrpc(method, path="/mcp", headers=None, body=None):
    payload = body if body is not None else json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": method}).encode()
    hdrs = {"Content-Type": "application/json"}
    hdrs.update(headers or {})
    req = urllib.request.Request(hbase + path, data=payload, headers=hdrs, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()

st, hd, body = hrpc("resources/list", headers={"Authorization": "Bearer k3y"})
ok(st == 200 and json.loads(body)["result"] == {"resources": []},
   "resources/list answers empty, not method-not-found (real clients probe it)")
ok(hd.get("Mcp-Session-Id") and hd.get("Access-Control-Allow-Origin") == "*",
   "responses carry a session id and CORS headers")
st, _, _ = hrpc("ping", path="/k3y/mcp")
ok(st == 200, "the secret works as a URL path segment (web connector settings can't set headers)")
st, _, _ = hrpc("ping", path="/mcp?token=k3y")
ok(st == 200, "…and as a query parameter")
st, _, _ = hrpc("ping", path="/mcp?token=wrong")
ok(st == 401, "a wrong secret is refused")
import socket as _socket
_s = _socket.create_connection(("127.0.0.1", mh.server_address[1]), timeout=10)
_s.sendall(("POST /mcp HTTP/1.1\r\nHost: x\r\nAuthorization: Bearer k3y\r\n"
            "Content-Type: application/json\r\nContent-Length: %d\r\n\r\n"
            % (mcp_h.MAX_BODY + 1)).encode())
_status = _s.recv(64).decode(errors="replace")   # answered before any body is sent
_s.close()
ok(" 413 " in _status, "oversized messages are refused before they are read")
req = urllib.request.Request(hbase + "/mcp", method="OPTIONS")
with urllib.request.urlopen(req, timeout=10) as r:
    ok(r.status == 204 and "POST" in r.headers.get("Access-Control-Allow-Methods", ""),
       "browser preflight succeeds")
mcp_h.RATE_PER_MINUTE, saved_rate = 5, mcp_h.RATE_PER_MINUTE
mh._rate.clear()
codes = [hrpc("ping", headers={"Authorization": "Bearer k3y"})[0] for _ in range(7)]
mcp_h.RATE_PER_MINUTE = saved_rate
ok(codes[:5] == [200] * 5 and 429 in codes[5:],
   "a client that floods gets 429 after the limit")

mh.shutdown()
for d in (dH, dH2, dH3):
    shutil.rmtree(d, ignore_errors=True)

print("\nall %d assertions passed" % PASS)
