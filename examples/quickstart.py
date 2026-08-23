"""theMind quickstart — the whole integration is three lines.

theMind never imports a provider SDK. You hand it one callable:

    def llm(system: str, user: str, max_tokens: int) -> str

and that is the only bridge to a model. Below: the callable for the three
common setups, then the loop. Pick one, delete the rest.
"""
from themind import Mind

# ── your llm callable (pick one) ─────────────────────────────────────────────

def llm_openai_compatible(system, user, max_tokens):
    """OpenAI, or anything speaking its wire format (Ollama, LM Studio, vLLM,
    OpenRouter…) — just change base_url."""
    from openai import OpenAI  # pip install openai
    client = OpenAI()  # OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
    r = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=max_tokens,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}])
    return r.choices[0].message.content or ""


def llm_anthropic(system, user, max_tokens):
    import anthropic  # pip install anthropic
    client = anthropic.Anthropic()
    r = client.messages.create(
        model="claude-haiku-4-5", max_tokens=max_tokens, system=system,
        messages=[{"role": "user", "content": user}])
    return "".join(b.text for b in r.content if b.type == "text")


def llm_gemini(system, user, max_tokens):
    from google import genai  # pip install google-genai
    client = genai.Client()
    r = client.models.generate_content(
        model="gemini-2.5-flash",
        config={"system_instruction": system, "max_output_tokens": max_tokens},
        contents=user)
    return r.text or ""


# ── the loop ─────────────────────────────────────────────────────────────────

llm = llm_openai_compatible          # ← your pick
mind = Mind("./my-companion-mind", llm=llm)

PERSONA = "You are Kai, a warm and curious companion."  # YOUR character — theMind
                                                        # supplies the inside, never the identity

history = []
while True:
    user_text = input("you: ").strip()
    if not user_text:
        break

    history.append({"role": "user", "content": user_text})
    messages = mind.enrich([{"role": "system", "content": PERSONA}] + history[-20:])

    # this call is YOUR app's call, exactly as it was before theMind:
    reply = llm_openai_compatible(messages[0]["content"],
                                  "\n".join(m["content"] for m in messages[1:]), 400)
    # (in a real app you pass `messages` straight to your chat endpoint;
    #  the flattening above just keeps this example provider-agnostic)

    print("kai:", reply)
    history.append({"role": "assistant", "content": reply})

    mind.observe(user_text, reply)   # learning + due cognition, background thread
