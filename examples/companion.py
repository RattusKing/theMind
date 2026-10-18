"""A companion you can run without writing any code: theMind, a model, a terminal.

    python3 companion.py --model <your model's name>

It uses whatever you have:

    ANTHROPIC_API_KEY set     -> Anthropic
    OPENAI_API_KEY set        -> OpenAI (or any OpenAI-compatible server: --base-url)
    neither                   -> Ollama on this machine: free, local, no key
                                 (install it, `ollama pull <model>`, then pass that name)

Pass the model name your provider uses with --model (or set THEMIND_MODEL);
model names change too often to guess one for you.

Everything here is the Python standard library: no SDK, nothing to install
beyond theMind. This file is the HOST: it holds the key and makes the chat
calls. theMind never does either; it supplies the inside, and this script
gives it a voice.

Inside the conversation: /show to see its mind, /quit to leave. Its mind is a
folder (./my-companion-mind by default) that you can open, back up, or move.
"""
import argparse
import json
import os
import queue
import sys
import threading
import urllib.error
import urllib.request

try:
    from themind import Mind
except ImportError:   # running from a clone of the repo rather than an install
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    from themind import Mind


def _post(url, body, headers, timeout=120):
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                 headers=dict({"Content-Type": "application/json"}, **headers),
                                 method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        raise RuntimeError("%s from the model provider: %s" % (e.code, detail))


def _alternating(messages):
    """System text, and the rest as strictly alternating turns starting with
    the person: what Anthropic's API requires. Same-role neighbours merge; if
    the companion spoke first, a stage direction says so."""
    system = "\n\n".join(m["content"] for m in messages if m.get("role") == "system")
    turns = []
    for m in messages:
        role = m.get("role")
        if role not in ("user", "assistant"):
            continue
        if turns and turns[-1]["role"] == role:
            turns[-1]["content"] += "\n\n" + m["content"]
        else:
            turns.append({"role": role, "content": m["content"]})
    if turns and turns[0]["role"] == "assistant":
        turns.insert(0, {"role": "user", "content": "(Earlier, you wrote to them first.)"})
    return system, turns or [{"role": "user", "content": "(You are writing first.)"}]


def make_chat(provider, model, base_url=None, key=None):
    """chat(messages, max_tokens) -> str, for one provider."""
    if provider == "anthropic":
        base = (base_url or "https://api.anthropic.com").rstrip("/")
        key = key or os.environ.get("ANTHROPIC_API_KEY", "")

        def chat(messages, max_tokens=600):
            system, turns = _alternating(messages)
            body = {"model": model, "max_tokens": max_tokens, "messages": turns}
            if system:
                body["system"] = system
            r = _post(base + "/v1/messages", body,
                      {"x-api-key": key, "anthropic-version": "2023-06-01"})
            return "".join(b.get("text", "") for b in r.get("content", [])
                           if b.get("type") == "text").strip()
        return chat

    default = "http://localhost:11434/v1" if provider == "ollama" else "https://api.openai.com/v1"
    base = (base_url or os.environ.get("THEMIND_BASE_URL") or default).rstrip("/")
    key = key or os.environ.get("OPENAI_API_KEY") or ("ollama" if provider == "ollama" else "")

    def chat(messages, max_tokens=600):
        r = _post(base + "/chat/completions",
                  {"model": model, "max_tokens": max_tokens,
                   "messages": [{"role": m["role"], "content": m["content"]} for m in messages]},
                  {"Authorization": "Bearer " + key} if key else {})
        return ((r.get("choices") or [{}])[0].get("message") or {}).get("content", "").strip()
    return chat


def pick_provider(explicit=None):
    if explicit:
        return explicit
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.environ.get("OPENAI_API_KEY") or os.environ.get("THEMIND_BASE_URL"):
        return "openai"
    return "ollama"


class Learner:
    """Learning happens behind the conversation, one exchange at a time, in
    order, so no turn is ever skipped; leaving waits for it to finish."""

    def __init__(self, mind):
        self.mind, self.q = mind, queue.Queue()
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        while True:
            user_text, reply = self.q.get()
            try:
                self.mind.observe(user_text, reply)
            except Exception:
                pass
            finally:
                self.q.task_done()

    def add(self, user_text, reply):
        self.q.put((user_text, reply))

    def finish(self):
        self.q.join()


def main(argv=None, stdin=None, stdout=None):
    stdin, stdout = stdin or sys.stdin, stdout or sys.stdout
    p = argparse.ArgumentParser(description="A companion with a mind of its own, in your terminal.")
    p.add_argument("--model", default=os.environ.get("THEMIND_MODEL"),
                   help="the model's name, as your provider spells it (or set THEMIND_MODEL)")
    p.add_argument("--provider", choices=("anthropic", "openai", "ollama"),
                   help="default: chosen from which key you have set")
    p.add_argument("--base-url", help="for any OpenAI-compatible server, or a proxy")
    p.add_argument("--mind", default="./my-companion-mind", help="the folder that is its mind")
    p.add_argument("--name", default="Kai", help="what it is called")
    p.add_argument("--persona", help="its character, in your words (default: warm and curious)")
    args = p.parse_args(argv)
    if not args.model:
        print("Pass --model with your model's name, as your provider spells it "
              "(for Ollama, a name from `ollama list`).", file=sys.stderr)
        return 2

    def say(text=""):
        stdout.write(text + "\n")
        stdout.flush()

    provider = pick_provider(args.provider)
    chat = make_chat(provider, args.model, args.base_url)
    persona = args.persona or (
        "You are %s. You're warm, curious and honest, and you talk like a friend: briefly, "
        "naturally, in your own words, without lists or headings." % args.name)

    def llm(system, user, max_tokens):   # the one bridge theMind thinks through
        return chat([{"role": "system", "content": system},
                     {"role": "user", "content": user}], max_tokens)

    mind = Mind(args.mind, llm=llm, sync=True)   # learning runs in Learner's thread
    learner = Learner(mind)
    say("%s, with a mind at %s (%s, via %s). It is %s with you." % (
        args.name, args.mind, args.model, provider, mind.stage()["name"]))
    say("/show to see its mind, /quit to leave.\n")

    history = []
    opener = mind.reach([{"role": "system", "content": persona}])
    if opener:
        try:
            text = chat(opener["messages"])
            if text:
                say("%s: %s" % (args.name.lower(), text))
                mind.reached(opener["id"], text)
                history.append({"role": "assistant", "content": text})
        except Exception as e:
            say("(it had something to say first, but the model couldn't be reached: %s)" % e)

    while True:
        stdout.write("you: ")
        stdout.flush()
        line = stdin.readline()
        if not line:
            break
        user_text = line.strip()
        if not user_text:
            continue
        if user_text in ("/quit", "/exit"):
            break
        if user_text == "/show":
            from themind import show
            say(show.render(show.report(Mind(args.mind, readonly=True))))
            continue
        history.append({"role": "user", "content": user_text})
        try:
            reply = chat(mind.enrich([{"role": "system", "content": persona}] + history[-20:]))
        except Exception as e:
            history.pop()
            say("(couldn't reach the model: %s)" % e)
            continue
        say("%s: %s" % (args.name.lower(), reply))
        history.append({"role": "assistant", "content": reply})
        learner.add(user_text, reply)

    say("\n(letting it finish thinking about what you said...)")
    learner.finish()
    say("Its mind is saved in %s. See it any time: python3 -m themind show %s" % (args.mind, args.mind))
    return 0


if __name__ == "__main__":
    sys.exit(main())
