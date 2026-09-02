# Getting started with theMind

theMind gives the AI you already use a memory and an inner life. It remembers
the person it talks to, forms its own reflections, and grows over time — and
everything it knows lives in one ordinary folder on your machine. Delete the
folder (or just stop using theMind) and your app is exactly as it was before.

It works with **any** model that speaks the OpenAI chat format: OpenAI itself,
Ollama, LM Studio, OpenRouter, vLLM, and most others. It needs **no accounts,
no API key of its own, and no extra services** — it rides the connection your
app already has.

There are three ways to use it. Most people want the first or second.

---

## Option 1 — the proxy: no code at all

You change **one line** in your app: the address it sends chat requests to.

**Step 1. Get theMind** (Python 3.9+ is the only requirement — one command,
straight from GitHub, no accounts needed):

```
pip install git+https://github.com/RattusKing/theMind.git
```

(Prefer to see the code first? `git clone https://github.com/RattusKing/theMind.git`
and run from inside the folder — both work the same.)

**Step 2. Start the proxy.** Tell it where your app *currently* sends its
requests (`--upstream`) and where to keep the memory (`--mind`):

```
python3 -m themind.proxy --upstream https://api.openai.com/v1 --mind ./my-mind
```

Using a local model instead? Same command, different upstream:

```
python3 -m themind.proxy --upstream http://localhost:11434/v1 --mind ./my-mind
```

**Step 3. Point your app at the proxy.** Wherever your app sets its API
address (often called `base_url`), change it to:

```
http://127.0.0.1:6463/v1
```

That's it. Your app talks to the proxy, the proxy talks to your real provider,
and a mind quietly forms in the `./my-mind` folder. Your API key stays in your
app and passes straight through — the proxy never stores it.

To stop using it: point `base_url` back to what it was. Nothing else changed.

## Option 2 — connect a platform: Claude, ChatGPT, local apps

If your AI lives on a platform (Claude Desktop, Claude Code, claude.ai,
ChatGPT, LM Studio, and most open-source chat apps), connect the mind as an
**MCP server** — the AI gets its mind as tools it tends itself:

```
python3 -m themind.mcp --mind ./my-mind
```

Then add `http://127.0.0.1:6464/mcp` wherever your platform takes MCP servers
or custom connectors. Desktop apps and local tools connect to that address
directly. Web platforms (claude.ai, ChatGPT) can't see your machine, so give
them a public address with a free tunnel (cloudflared, ngrok, Tailscale) and
protect it: run with `--token some-secret` and give the connector the secret
in the URL itself — `https://your-tunnel/some-secret/mcp` — since web
connector settings can paste a URL but can't set a header (a Bearer header
or `?token=` work too). Your mind's folder never leaves your disk either way.

For the deepest integration, run **both** — one command does it:

```
python3 -m themind.proxy --upstream http://localhost:11434/v1 --mind ./my-mind --mcp-port 6464
```

The proxy carries memory involuntarily on every message, and the MCP
connection lets the AI reflect, remember, and notice what it wants — with its
own thinking. One process, one mind, both halves.

## Option 3 — the library: three lines of code

If you're writing the code yourself:

```python
from themind import Mind

mind = Mind("./my-mind", llm=my_llm)   # my_llm: (system, user, max_tokens) -> str

messages = mind.enrich(messages)   # add this line before your model call
mind.observe(user_text, reply)     # add this line after the reply
```

See `examples/quickstart.py` for ready-made `my_llm` functions for
OpenAI-compatible endpoints, Anthropic, and Gemini.

---

## Common questions

**Where is everything kept?** In the folder you chose (`./my-mind`). It's
plain, readable JSON — open it and look. Nothing is written anywhere else.

**How do I back it up or move it to another machine?** The folder *is* the
mind: copy it. Or make a single-file snapshot — no code needed:

```
python3 -m themind export ./my-mind            # writes my-mind/mind-export.json
python3 -m themind restore mind-export.json ./my-mind   # brings it back anywhere
```

**Does it cost anything?** theMind is free (Apache 2.0). Its background
thinking uses your own model connection — a handful of small extra calls,
typically a fraction of what the conversation itself costs.

**Does it change my AI's personality?** No. Your app still defines who the AI
is. theMind only supplies what it remembers and holds inside.

**What if theMind breaks?** Your chat keeps working. On any internal failure
the request goes through untouched — that's a design guarantee, and the test
suite (`python3 tests/run_all.py`) holds it in place.
