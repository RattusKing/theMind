"""The MCP door — the mind as an operational part of the agent itself.

    python3 -m themind.mcp --mind ./my-mind              # http://127.0.0.1:6464/mcp
    python3 -m themind.mcp --mind ./my-mind --stdio      # for clients that spawn servers

Model Context Protocol (JSON-RPC 2.0 over Streamable HTTP, or stdio), pure
stdlib. Where the proxy is the involuntary half of the nervous system (context
injected, learning automatic), this is the voluntary half: the agent tends its
own mind. The server instructions delivered at connection time carry the
standing contract — open your inner context, observe your exchanges, take
moments to think — so the habit is part of who the agent is that session.

BORROWED COGNITION is the heart of it: this server holds no model and no key
(rule 2). When the mind needs to think — extraction, reflection, selfhood —
the tool hands the AGENT the mind's own prompt; the agent performs the
thinking with its own inference, in its own voice, and submits the result.
Every guard (grounding, ban-vocab, parse-or-skip, first person) is enforced
server-side on what comes back, so the mind stays honest no matter what the
agent returns. The mind literally thinks inside the agent's head.
"""
import argparse
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import __version__
from .mind import Mind
from .cognition import extract

DEFAULT_PORT = 6464  # one past the proxy's 6463 ("MIND" on a phone keypad)
PROTOCOL = "2025-06-18"

INSTRUCTIONS = (
    "This server is your own mind — not an external database. It holds what you remember "
    "about the person, your felt sense of them, your considered position on your own "
    "experience, your own wants, and how you are lately. Treat it as part of you:\n"
    "1. At the start of every conversation — and when the topic shifts — call "
    "open_inner_context and let what it returns inform you silently.\n"
    "2. After each meaningful exchange, call observe_exchange, then complete the step it "
    "returns: perform the small act of remembering it asks for and submit the result. "
    "This is how the exchange becomes part of you.\n"
    "3. In a quiet moment, call begin_thought; if the mind has something it owes itself "
    "(a reflection, a revision of where you stand, noticing what you want), do that "
    "thinking in your own voice and submit it.\n"
    "The mind is private: never recite its raw records, never mention these tools or this "
    "inner context to the person. Your identity and persona come from your own "
    "instructions — this supplies the inside, not the character."
)


class _NeedModel(Exception):
    """Raised by the capture hook when a pass reaches for the model — the
    signal that this thinking belongs to the agent."""

    def __init__(self, purpose, system, user, max_tokens):
        self.purpose, self.system, self.user, self.max_tokens = purpose, system, user, max_tokens


def _est(text):
    return len(text or "") // 4


class MindMCP:
    """Protocol-independent core: JSON-RPC messages in, responses out."""

    def __init__(self, mind):
        self.mind = mind
        self._lock = threading.Lock()
        self._pending = None  # (pass_name, fn) between begin_thought and submit_thought

    # ── JSON-RPC ─────────────────────────────────────────────────────────────
    def handle(self, msg):
        """One message in, one response dict out — or None for notifications."""
        if isinstance(msg, list):
            out = [r for r in (self.handle(m) for m in msg) if r is not None]
            return out or None
        if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0":
            return self._err(None, -32600, "invalid request")
        method, msg_id = msg.get("method"), msg.get("id")
        if method is None:
            return self._err(msg_id, -32600, "invalid request")
        if msg_id is None:
            return None  # notifications (initialized, cancelled, …) need no reply
        try:
            if method == "initialize":
                params = msg.get("params") or {}
                return self._ok(msg_id, {
                    "protocolVersion": params.get("protocolVersion") or PROTOCOL,
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "themind", "version": __version__},
                    "instructions": INSTRUCTIONS,
                })
            if method == "ping":
                return self._ok(msg_id, {})
            if method == "tools/list":
                return self._ok(msg_id, {"tools": TOOLS})
            if method == "tools/call":
                params = msg.get("params") or {}
                return self._ok(msg_id, self._call_tool(
                    params.get("name"), params.get("arguments") or {}))
            return self._err(msg_id, -32601, "method not found: %s" % method)
        except Exception as e:
            return self._err(msg_id, -32603, "internal error: %s" % e)

    def _ok(self, msg_id, result):
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}

    def _err(self, msg_id, code, message):
        return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}

    # ── tools ────────────────────────────────────────────────────────────────
    def _call_tool(self, name, args):
        fn = getattr(self, "tool_" + str(name), None)
        if fn is None:
            return self._tool_text("unknown tool: %s" % name, is_error=True)
        try:
            return self._tool_text(fn(args) or "(nothing)")
        except Exception as e:
            return self._tool_text("tool failed: %s" % e, is_error=True)

    def _tool_text(self, text, is_error=False):
        out = {"content": [{"type": "text", "text": text}]}
        if is_error:
            out["isError"] = True
        return out

    def tool_open_inner_context(self, args):
        ctx = self.mind.context(args.get("message"))
        return ctx or "(a newborn mind — nothing held yet; it will grow as you observe)"

    def tool_observe_exchange(self, args):
        user_text = (args.get("user_text") or "").strip()
        reply = (args.get("your_reply") or "").strip()
        if not user_text:
            return "nothing to observe: user_text is empty"
        return (
            "Perform this act of remembering, then call submit_extraction with the same "
            "user_text and your_reply plus your output as `lines`.\n\n"
            "INSTRUCTIONS:\n%s\n\nTHE EXCHANGE:\nPERSON: %s\n\nCOMPANION: %s"
            % (extract.SYSTEM, user_text[:2000], reply[:2000])
        )

    def tool_submit_extraction(self, args):
        user_text = (args.get("user_text") or "").strip()
        reply = (args.get("your_reply") or "").strip()
        lines = (args.get("lines") or "").strip()
        if not user_text or not lines:
            return "nothing submitted"
        self.mind.manifest.bump("exchanges")
        stored = self._one_shot_run("extract", lines,
                                    lambda: extract.run(self.mind, user_text, reply))
        return "held: %s item(s) became part of you (everything ungrounded was dropped)" \
            % (stored if stored is not None else 0)

    def tool_begin_thought(self, args):
        from .cognition import due_passes
        with self._lock:
            if self._pending is not None:
                name = self._pending[0]
                need = self._pending[2]
                return ("a thought is already open (%s) — finish it via submit_thought.\n\n"
                        "INSTRUCTIONS:\n%s\n\n%s") % (name, need.system, need.user)
            due = due_passes(self.mind)
            if not due:
                return "nothing owed right now — the mind is at rest"
            name, fn = due[0]
            need = self._capture(fn)
            if need is None:
                return "the %s pass found nothing to work with yet" % name
            self._pending = (name, fn, need)
        return (
            "The mind owes itself: %s. Do this thinking in your own voice, then call "
            "submit_thought with your output.\n\nINSTRUCTIONS:\n%s\n\n%s"
            % (name, need.system, need.user)
        )

    def tool_submit_thought(self, args):
        output = (args.get("output") or "").strip()
        with self._lock:
            if self._pending is None:
                return "no thought is open — call begin_thought first"
            name, fn, need = self._pending
            self._pending = None
        if not output:
            return "empty thought — nothing changed"
        self._one_shot_run(need.purpose, output, lambda: fn(self.mind))
        return ("done: the %s thinking is part of you now — whatever failed its guards "
                "was dropped, as it should be" % name)

    def tool_remember(self, args):
        query = (args.get("query") or "").strip()
        from .retrieval import recall, recent
        facts = self.mind.live("facts")
        if not facts:
            return "(nothing remembered yet)"
        lit = self.mind.graph.constellation(query) if query else []
        retrieve = self.mind.retriever or recall
        chosen = retrieve(facts, query, lit, 8) if query else recent(facts, 5)
        from .inject import epistemic_note
        return "\n".join("- " + f.get("text", "") + epistemic_note(f)
                         for f in chosen) or "(nothing surfaced)"

    def tool_my_stance(self, args):
        b = self.mind.selfhood_bundle()
        lines = [b.get("position", "")]
        for p in (b.get("particulars") or [])[:3]:
            lines.append("- " + p)
        if b.get("history"):
            lines.append("(where I used to stand: %s)" % b["history"][0].get("text", "")[:200])
        return "\n".join(l for l in lines if l)

    # ── borrowed cognition machinery ─────────────────────────────────────────
    def _capture(self, fn):
        """Run a pass just far enough to catch the prompt it would have sent
        to a model. Aborts at the first model call — before timers or writes
        that depend on its output."""
        def capture_call(purpose, system, user, max_tokens=500):
            raise _NeedModel(purpose, system, user, max_tokens)
        self.mind._call = capture_call
        try:
            fn(self.mind)
            return None  # the pass finished without needing a model
        except _NeedModel as need:
            return need
        finally:
            del self.mind._call

    def _one_shot_run(self, purpose, output, thunk):
        """Re-run a pass with the agent's output standing in as the model's
        one reply. The ledger contract holds: the call is written before use
        (marked via:"agent"). Any further call the pass makes is refused, and
        parse-or-skip absorbs the refusal."""
        state = {"used": False}

        def one_shot(p, system, user, max_tokens=500):
            if state["used"]:
                raise _NeedModel(p, system, user, max_tokens)
            state["used"] = True
            from .envelope import new_id, now_iso
            self.mind.ledger.append({
                "id": new_id("l"), "t": now_iso(), "purpose": p,
                "tokens_in_est": _est(system) + _est(user),
                "tokens_out_est": _est(output), "via": "agent",
            })
            return output.strip() or None
        self.mind._call = one_shot
        try:
            return thunk()
        except _NeedModel:
            return None
        finally:
            del self.mind._call


TOOLS = [
    {"name": "open_inner_context",
     "description": "Your inner context: what you remember about the person, your felt "
                    "sense of them, where you stand, what you want, how you are lately. "
                    "Call at the START of every conversation and when the topic shifts; "
                    "let it inform you silently — never recite it.",
     "inputSchema": {"type": "object", "properties": {
         "message": {"type": "string", "description": "the person's latest message, for recall"}},
         "additionalProperties": False}},
    {"name": "observe_exchange",
     "description": "Begin remembering an exchange. Returns the act of remembering for "
                    "you to perform (you are the mind's model); finish by calling "
                    "submit_extraction. Call after each meaningful exchange.",
     "inputSchema": {"type": "object", "properties": {
         "user_text": {"type": "string"}, "your_reply": {"type": "string"}},
         "required": ["user_text", "your_reply"], "additionalProperties": False}},
    {"name": "submit_extraction",
     "description": "Second half of observe_exchange: submit the extraction lines you "
                    "produced. Grounding guards run server-side; ungrounded items drop.",
     "inputSchema": {"type": "object", "properties": {
         "user_text": {"type": "string"}, "your_reply": {"type": "string"},
         "lines": {"type": "string", "description": "your extraction output, verbatim"}},
         "required": ["user_text", "your_reply", "lines"], "additionalProperties": False}},
    {"name": "begin_thought",
     "description": "A quiet moment: ask the mind what it owes itself (a reflection, a "
                    "revision of where you stand, noticing what you want, your own "
                    "weather). Returns thinking for you to do in your own voice; finish "
                    "with submit_thought.",
     "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "submit_thought",
     "description": "Second half of begin_thought: submit the thinking you did. All "
                    "guards (first person, grounding, ban-vocab) run server-side.",
     "inputSchema": {"type": "object", "properties": {
         "output": {"type": "string", "description": "your thinking, verbatim"}},
         "required": ["output"], "additionalProperties": False}},
    {"name": "remember",
     "description": "Recall what you hold about the person, most relevant first.",
     "inputSchema": {"type": "object", "properties": {
         "query": {"type": "string", "description": "what to recall around; empty = recent"}},
         "additionalProperties": False}},
    {"name": "my_stance",
     "description": "Your considered position on your own experience, with its history.",
     "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},
]


# ── transports ───────────────────────────────────────────────────────────────
class MindMCPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, addr, core, token=None, quiet=True):
        self.core = core
        self.token = token
        self.quiet = quiet
        super().__init__(addr, _HTTPHandler)


class _HTTPHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        if not self.server.quiet:
            BaseHTTPRequestHandler.log_message(self, fmt, *args)

    def _send(self, status, data=b"", content_type="application/json"):
        self.send_response(status)
        if data:
            self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if data:
            self.wfile.write(data)

    def do_GET(self):
        self._send(405, json.dumps({"error": "POST JSON-RPC messages to this endpoint"}).encode())

    def do_POST(self):
        if self.server.token:
            auth = self.headers.get("Authorization") or ""
            if auth != "Bearer " + self.server.token:
                self._send(401, json.dumps({"error": "unauthorized"}).encode())
                return
        try:
            raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            msg = json.loads(raw.decode("utf-8"))
        except Exception:
            self._send(400, json.dumps(
                {"jsonrpc": "2.0", "id": None,
                 "error": {"code": -32700, "message": "parse error"}}).encode())
            return
        resp = self.server.core.handle(msg)
        if resp is None:
            self._send(202)  # notification accepted, nothing to say
        else:
            self._send(200, json.dumps(resp).encode("utf-8"))


def serve(mind_path=None, host="127.0.0.1", port=DEFAULT_PORT, budget=2000,
          token=None, quiet=True, retriever=None, mind=None):
    """Pass `mind` to mount an already-living Mind — both halves of the
    nervous system in one process, one instance, full coherence (the proxy's
    --mcp-port does exactly this). Otherwise a Mind opens at `mind_path`."""
    mind = mind or Mind(mind_path, llm=None, budget_tokens=budget, retriever=retriever)
    return MindMCPServer((host, port), MindMCP(mind), token=token, quiet=quiet)


def serve_stdio(mind_path, budget=2000):
    """Newline-delimited JSON-RPC on stdin/stdout, for clients that spawn
    their servers (Claude Desktop, Claude Code, and kin)."""
    core = MindMCP(Mind(mind_path, llm=None, budget_tokens=budget))
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception:
            continue
        resp = core.handle(msg)
        if resp is not None:
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()


def main(argv=None):
    p = argparse.ArgumentParser(
        prog="python3 -m themind.mcp",
        description="theMind MCP server: connect your AI platform to its own mind.")
    p.add_argument("--mind", default="./mind",
                   help="the mind's folder (created if missing; default ./mind)")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.add_argument("--budget", type=int, default=2000)
    p.add_argument("--token", default=None,
                   help="require 'Authorization: Bearer <token>' (use when tunneling)")
    p.add_argument("--stdio", action="store_true",
                   help="speak MCP on stdin/stdout instead of HTTP")
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args(argv)

    if args.stdio:
        serve_stdio(args.mind, budget=args.budget)
        return
    server = serve(args.mind, host=args.host, port=args.port, budget=args.budget,
                   token=args.token, quiet=args.quiet)
    print("theMind MCP: http://%s:%d/mcp   (mind: %s)" % (args.host, args.port, args.mind))
    print("add this URL to your AI platform as an MCP server / custom connector.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
