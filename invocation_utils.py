import os
from typing import Iterable

try:  # pragma: no cover - optional dependency
    import openai
except Exception:  # pragma: no cover - optional dependency
    openai = None


def _get_commands(bot_data: dict) -> list[str]:
    """Return a list of command titles extracted from bot metadata."""
    commands: list[str] = []
    for bot in bot_data.get("bots", []):
        for cl in bot.get("commandLists", []):
            for cmd in cl.get("commands", []):
                title = cmd.get("title")
                if isinstance(title, str) and title.strip():
                    commands.append(title.strip())
    return commands


def _get_examples(bot_data: dict) -> list[str]:
    """Return example prompts from bot metadata."""
    examples = []
    for ex in bot_data.get("examplePrompts", []):
        prompt = ex.get("prompt")
        if isinstance(prompt, str) and prompt.strip():
            examples.append(prompt.strip())
    return examples


def _join_items(items: Iterable[str], limit: int) -> str:
    """Return comma-separated items truncated to given limit."""
    return ", ".join(list(items)[:limit])


def build_suggested_invocation(query: str, bot_id: str, bot_data: dict) -> str | None:
    """Return a suggested invocation string for the given query and bot."""
    if not query:
        return None

    bot_name = bot_data.get("name", bot_id)
    commands = _get_commands(bot_data)
    examples = _get_examples(bot_data)

    if openai and os.getenv("OPENAI_API_KEY"):
        try:
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You suggest how to invoke a Teams bot. "
                        "Only return a single-line invocation."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Bot name: {bot_name}\n"
                        f"User question: {query}\n"
                        f"Commands: {_join_items(commands, 5) or 'None'}\n"
                        f"Examples: {_join_items(examples, 3) or 'None'}"
                    ),
                },
            ]
            resp = openai.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                max_tokens=60,
            )
            suggestion = resp.choices[0].message.content.strip()
            if not suggestion.startswith("@"):  # ensure mention prefix
                suggestion = f"@{bot_name} " + suggestion
            return suggestion
        except Exception:
            pass

    # Fallback heuristics if OpenAI is unavailable or errors
    if examples:
        return examples[0]
    return f"@{bot_name} {query.strip()}"
