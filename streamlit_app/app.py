import json
import os
from pathlib import Path
from difflib import get_close_matches

import streamlit as st


# Directory containing the augmented bot definitions
DEFS_DIR = Path(__file__).resolve().parent.parent / "augmented_defs"


def load_bots():
    """Load all bot definition JSON files into memory."""
    bots = {}
    for path in DEFS_DIR.glob("*.json"):
        try:
            with open(path, "r", encoding="utf-8") as f:
                bots[path.stem] = json.load(f)
        except Exception as e:
            st.error(f"Failed to load {path.name}: {e}")
    return bots


def get_description(app):
    for key in ["description", "longDescription", "shortDescription"]:
        desc = app.get(key)
        if isinstance(desc, str) and desc.strip():
            return desc
    return ""


def get_commands(app):
    commands = []
    for bot in app.get("bots", []):
        for cl in bot.get("commandLists", []):
            for cmd in cl.get("commands", []):
                title = cmd.get("title")
                desc = cmd.get("description", "")
                if title:
                    commands.append({"title": title, "description": desc})
    return commands


BOTS = load_bots()
BOT_NAMES = list(BOTS.keys())


def search_bots(query):
    if not query:
        return BOT_NAMES
    results = []
    q = query.lower()
    for bot_id, data in BOTS.items():
        text_parts = [bot_id.lower(), data.get("name", "").lower(), get_description(data).lower()]
        text_parts.extend(cmd["title"].lower() for cmd in get_commands(data))
        blob = " ".join(text_parts)
        if q in blob or get_close_matches(q, [blob]):
            results.append(bot_id)
    return results


st.sidebar.title("Teams Bot Explorer")
search_query = st.sidebar.text_input("Search bots")
options = search_bots(search_query)
selected_bot = st.sidebar.selectbox("Select a bot", options)

bot_data = BOTS.get(selected_bot, {})

st.header(f"{bot_data.get('name', selected_bot)} ({selected_bot})")

st.write(get_description(bot_data))

# Display additional metadata
meta_keys = ["version", "developerName", "creatorId"]
metadata = {k: bot_data.get(k) for k in meta_keys if bot_data.get(k)}
if metadata:
    with st.expander("Metadata"):
        st.json(metadata)

# Command list
commands = get_commands(bot_data)
if commands:
    st.subheader("Commands")
    for cmd in commands:
        title = cmd["title"]
        desc = cmd["description"]
        with st.expander(title):
            st.write(desc or "No description")

# Example prompts
examples = bot_data.get("examplePrompts") or []
if examples:
    st.subheader("Example Prompts")
    for ex in examples:
        prompt = ex.get("prompt")
        desc = ex.get("description")
        cmd = ex.get("command")
        st.markdown(f"**{prompt}**")
        if desc:
            st.write(desc)
        if cmd:
            st.caption(f"Command: {cmd}")
        st.markdown("---")

# Download button
json_str = json.dumps(bot_data, ensure_ascii=False, indent=2)
st.download_button("Download JSON", json_str, file_name=f"{selected_bot}.json")
