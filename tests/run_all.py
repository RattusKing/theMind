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

# ── 13. the proxy: OpenAI wire in, OpenAI wire out, a mind in between ────────
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


def settle(cond, timeout=10.0):
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
ok(settle(lambda: int(Mind(d11, sync=True).manifest.state.get("exchanges", 0)) == 1),
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
ok(settle(lambda: int(Mind(d11, sync=True).manifest.state.get("exchanges", 0)) == 2),
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

print("\nall %d assertions passed" % PASS)
