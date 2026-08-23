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

print("\nall %d assertions passed" % PASS)
