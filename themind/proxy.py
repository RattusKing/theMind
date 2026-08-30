"""The proxy — Phase 2. Point a base URL at it; zero code.

A small local process speaking the OpenAI wire format. Your app talks to it
exactly as it would talk to OpenAI (or Ollama, LM Studio, OpenRouter, any
compatible server); the proxy folds the mind's inner context into the system
side on the way in, forwards the request to the real upstream untouched
otherwise, relays the reply back byte-for-byte (streaming included), and
learns from the exchange afterwards.

    python3 -m themind.proxy --upstream https://api.openai.com/v1 --mind ./my-mind
    # then point your app's base_url at http://127.0.0.1:6463/v1

Pure stdlib (rule 1). The proxy holds no key of its own and stores none: your
app's Authorization header passes through to the upstream, and the mind's own
cognition rides that same header, held in memory only. Everything the mind
makes of the conversation lives in the mind folder and nowhere else. If the
mind layer fails in any way, the request is forwarded exactly as it arrived —
the chat path never sees an error (rule 5).
"""
import argparse
import json
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .mind import Mind

DEFAULT_PORT = 6463  # M-I-N-D on a phone keypad

_HOP_BY_HOP = {"host", "connection", "keep-alive", "proxy-authenticate",
               "proxy-authorization", "te", "trailers", "transfer-encoding",
               "upgrade", "content-length", "accept-encoding"}


def _content_text(content):
    """The text of an OpenAI message content field — a string, or the text
    parts of a multimodal list. None when there is no text."""
    if isinstance(content, str):
        return content or None
    if isinstance(content, list):
        parts = [p.get("text", "") for p in content
                 if isinstance(p, dict) and p.get("type") == "text"]
        joined = "\n".join(p for p in parts if p)
        return joined or None
    return None


def _last_user_text(messages):
    for m in reversed(messages):
        if isinstance(m, dict) and m.get("role") == "user":
            text = _content_text(m.get("content"))
            if text:
                return text
    return None


class Upstream:
    """The real endpoint, plus the transient state cognition rides on: the
    last Authorization header and model seen on the chat path. In memory
    only — nothing here is ever written to disk."""

    def __init__(self, base, model=None):
        self.base = base.rstrip("/")
        self.cli_model = model     # --model: always wins for cognition
        self.seen_model = None     # else: the model the host's app last used
        self.auth = None
        self._lock = threading.Lock()

    def note(self, auth, model):
        with self._lock:
            if auth:
                self.auth = auth
            if model:
                self.seen_model = model

    def target(self, path):
        """Map the proxy's request path onto the upstream base. The base is
        whatever you would hand an OpenAI client (it may or may not end in
        /v1), so the proxy's own /v1 prefix is dropped before joining."""
        rel = path.split("?", 1)[0]
        if rel == "/v1" or rel.startswith("/v1/"):
            rel = rel[3:] or "/"
        return self.base + rel

    def llm(self, system, user, max_tokens):
        """The mind's one bridge to a model (`Mind._call` is the only caller).
        Rides the chat path's own upstream and header; raises on any failure
        and the mind treats that as a no-op."""
        with self._lock:
            auth, model = self.auth, self.cli_model or self.seen_model
        if not model:
            raise RuntimeError("no model known yet (pass --model or make one chat call first)")
        body = json.dumps({
            "model": model, "max_tokens": max_tokens, "stream": False,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
        }).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if auth:
            headers["Authorization"] = auth
        req = urllib.request.Request(self.base + "/chat/completions",
                                     data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return _content_text(data["choices"][0]["message"].get("content")) or ""


class MindProxy(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, addr, mind, upstream, quiet=False):
        self.mind = mind
        self.upstream = upstream
        self.quiet = quiet
        super().__init__(addr, _Handler)


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    # ── plumbing ─────────────────────────────────────────────────────────────
    def log_message(self, fmt, *args):
        if not self.server.quiet:
            BaseHTTPRequestHandler.log_message(self, fmt, *args)

    def _read_body(self):
        length = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(length) if length > 0 else b""

    def _forward_headers(self):
        out = {}
        for name, value in self.headers.items():
            if name.lower() not in _HOP_BY_HOP:
                out[name] = value
        return out

    def _open_upstream(self, body):
        req = urllib.request.Request(
            self.server.upstream.target(self.path), data=body or None,
            headers=self._forward_headers(), method=self.command)
        try:
            return urllib.request.urlopen(req, timeout=600)
        except urllib.error.HTTPError as e:
            return e  # an HTTPError IS the upstream's response; relay it whole

    def _send(self, status, content_type, data):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _bad_gateway(self, exc):
        msg = json.dumps({"error": {"message": "upstream unreachable: %s" % exc,
                                    "type": "themind_proxy"}}).encode("utf-8")
        try:
            self._send(502, "application/json", msg)
        except Exception:
            pass

    # ── verbs: everything but the chat path is a transparent relay ───────────
    def do_GET(self):
        self._relay(self._read_body())

    def do_DELETE(self):
        self._relay(self._read_body())

    def do_POST(self):
        if self.path.split("?", 1)[0].rstrip("/").endswith("/chat/completions"):
            self._chat()
        else:
            self._relay(self._read_body())

    def _relay(self, body):
        try:
            resp = self._open_upstream(body)
        except Exception as e:
            self._bad_gateway(e)
            return None, None
        try:
            data = resp.read()
            self._send(resp.status,
                       resp.headers.get("Content-Type", "application/json"), data)
            return resp.status, data
        finally:
            resp.close()

    # ── the chat path ────────────────────────────────────────────────────────
    def _chat(self):
        raw = self._read_body()
        out, user_text, wants_stream = raw, None, False
        try:
            body = json.loads(raw.decode("utf-8"))
            wants_stream = bool(body.get("stream"))
            messages = body.get("messages")
            if isinstance(body, dict) and isinstance(messages, list):
                user_text = _last_user_text(messages)
                self.server.upstream.note(self.headers.get("Authorization"),
                                          body.get("model"))
                enriched = dict(body)
                enriched["messages"] = self.server.mind.enrich(messages)
                out = json.dumps(enriched).encode("utf-8")
        except Exception:
            out = raw  # any mind-layer failure: forward the request untouched

        try:
            resp = self._open_upstream(out)
        except Exception as e:
            self._bad_gateway(e)
            return

        try:
            streaming = wants_stream and resp.status == 200 and \
                "text/event-stream" in (resp.headers.get("Content-Type") or "")
            reply = self._relay_stream(resp) if streaming else self._relay_json(resp)
        finally:
            resp.close()

        if user_text and reply:
            try:
                self.server.mind.observe(user_text, reply)
            except Exception:
                pass  # learning must never take the chat path down with it

    def _relay_json(self, resp):
        data = resp.read()
        self._send(resp.status,
                   resp.headers.get("Content-Type", "application/json"), data)
        if resp.status != 200:
            return None
        try:
            parsed = json.loads(data.decode("utf-8"))
            return _content_text(parsed["choices"][0]["message"].get("content"))
        except Exception:
            return None

    def _relay_stream(self, resp):
        """Relay SSE chunks as they arrive; accumulate the assistant's delta
        text on the side so the exchange can be observed afterwards."""
        self.send_response(resp.status)
        self.send_header("Content-Type", resp.headers.get("Content-Type"))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        buf, pieces = b"", []
        while True:
            chunk = resp.read1(65536)
            if not chunk:
                break
            self.wfile.write(chunk)
            self.wfile.flush()
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                line = line.strip()
                if not line.startswith(b"data:"):
                    continue
                payload = line[5:].strip()
                if payload == b"[DONE]":
                    continue
                try:
                    delta = json.loads(payload.decode("utf-8"))
                    piece = delta["choices"][0].get("delta", {}).get("content")
                    if isinstance(piece, str):
                        pieces.append(piece)
                except Exception:
                    pass  # a malformed chunk is relayed anyway, just not learned from
        return "".join(pieces) or None


def serve(mind_path, upstream_base, host="127.0.0.1", port=DEFAULT_PORT,
          budget=2000, model=None, quiet=False, sync=False):
    """Build the server (used by main() and the tests)."""
    upstream = Upstream(upstream_base, model=model)
    mind = Mind(mind_path, llm=upstream.llm, budget_tokens=budget, sync=sync)
    return MindProxy((host, port), mind, upstream, quiet=quiet)


def start_idle(mind, interval=900.0):
    """The idle life: while nobody is talking, the mind keeps thinking. Every
    `interval` seconds one due cognition pass runs (mind.step — same door a
    host scheduler uses; a pass that can't run is a silent no-op). Returns a
    threading.Event; set it to stop the loop."""
    stop = threading.Event()

    def loop():
        while not stop.wait(interval):
            try:
                mind.step()
            except Exception:
                pass  # the idle life never takes the serving path down

    threading.Thread(target=loop, daemon=True).start()
    return stop


def main(argv=None):
    p = argparse.ArgumentParser(
        prog="python3 -m themind.proxy",
        description="theMind local proxy: OpenAI wire format in, OpenAI wire "
                    "format out, a mind in between.")
    p.add_argument("--upstream", required=True,
                   help="the base URL your app used before, e.g. "
                        "https://api.openai.com/v1 or http://localhost:11434/v1")
    p.add_argument("--mind", default="./mind",
                   help="the mind's folder (created if missing; default ./mind)")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.add_argument("--budget", type=int, default=2000,
                   help="max tokens of inner context per turn (default 2000)")
    p.add_argument("--model", default=None,
                   help="model for the mind's own thinking (default: whatever "
                        "model your app's chat calls use)")
    p.add_argument("--mcp-port", type=int, default=0,
                   help="also open the MCP door on this port — both halves of "
                        "the nervous system, one process, one mind (0 = off)")
    p.add_argument("--idle", type=float, default=900.0,
                   help="seconds between idle thoughts while nobody is talking "
                        "(default 900; 0 disables the idle life)")
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args(argv)

    server = serve(args.mind, args.upstream, host=args.host, port=args.port,
                   budget=args.budget, model=args.model, quiet=args.quiet)
    if args.idle > 0:
        start_idle(server.mind, args.idle)
    if args.mcp_port > 0:
        from . import mcp as mcp_door
        mcp_server = mcp_door.serve(host=args.host, port=args.mcp_port,
                                    quiet=args.quiet, mind=server.mind)
        threading.Thread(target=mcp_server.serve_forever, daemon=True).start()
        print("theMind MCP: http://%s:%d/mcp   (same mind — the voluntary half)"
              % (args.host, args.mcp_port))
    print("theMind proxy: http://%s:%d/v1  ->  %s   (mind: %s)"
          % (args.host, args.port, args.upstream, args.mind))
    print("point your app's base_url at the first address; nothing else changes."
          + ("" if args.idle <= 0 else
             "  the mind keeps thinking while idle (every %ds)." % int(args.idle)))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
