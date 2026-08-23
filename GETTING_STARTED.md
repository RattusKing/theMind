# Getting started with theMind

theMind gives the AI you already use a memory and an inner life. It remembers
the person it talks to, forms its own reflections, and grows over time — and
everything it knows lives in one ordinary folder on your machine. Delete the
folder (or just stop using theMind) and your app is exactly as it was before.

It works with **any** model that speaks the OpenAI chat format: OpenAI itself,
Ollama, LM Studio, OpenRouter, vLLM, and most others. It needs **no accounts,
no API key of its own, and no extra services** — it rides the connection your
app already has.

There are two ways to use it. Most people want the first one.

---

## Option 1 — the proxy: no code at all

You change **one line** in your app: the address it sends chat requests to.

**Step 1. Get theMind** (Python 3.9+ is the only requirement):

```
git clone https://github.com/RattusKing/theMind.git
cd theMind
```

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

## Option 2 — the library: three lines of code

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
mind: copy it. Or create a single-file snapshot from Python with
`mind.export()` and load it elsewhere with `Mind.restore(...)`.

**Does it cost anything?** theMind is free (Apache 2.0). Its background
thinking uses your own model connection — a handful of small extra calls,
typically a fraction of what the conversation itself costs.

**Does it change my AI's personality?** No. Your app still defines who the AI
is. theMind only supplies what it remembers and holds inside.

**What if theMind breaks?** Your chat keeps working. On any internal failure
the request goes through untouched — that's a design guarantee, and the test
suite (`python3 tests/run_all.py`) holds it in place.
