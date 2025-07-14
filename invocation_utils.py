import os

try:
    import openai
except Exception:  # pragma: no cover - optional dependency
    openai = None

def extract_options(query: str):
    """Return (question, options) parsed from the user query."""
    if not query:
        return query, None
    if "?" in query:
        q_part, rest = query.split("?", 1)
        question = q_part.strip() + "?"
        parts = [p.strip() for p in rest.split(",") if p.strip()]
        if len(parts) >= 2:
            return question, parts
        return question, None
    return query.strip(), None


def generate_options(question: str):
    """Use OpenAI to generate poll options or return defaults."""
    if openai and os.getenv("OPENAI_API_KEY"):
        try:
            resp = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": "Generate two short poll options separated by commas.",
                    },
                    {"role": "user", "content": question},
                ],
                max_tokens=20,
            )
            text = resp.choices[0].message.content.strip()
            opts = [o.strip(" -") for o in text.replace("\n", ",").split(",") if o.strip()]
            if len(opts) >= 2:
                return opts[:2]
        except Exception:
            pass
    return ["Yes", "No"]


def build_suggested_invocation(query: str, bot_id: str, bot_data: dict) -> str | None:
    """Return a suggested invocation string for the given query and bot."""
    if not query:
        return None
    question, options = extract_options(query)
    if not options:
        options = generate_options(question)
    bot_name = bot_data.get("name", bot_id)
    mention = f"@{bot_name}".replace("  ", " ").strip()
    invocation = f"{mention} {question} {', '.join(options)}"
    return invocation
