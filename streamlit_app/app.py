import json
from pathlib import Path
import sys

# Ensure repo root is on sys.path for local module imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from bot_finder_app.embedding_utils import load_index, search


# Directory containing the augmented bot definitions
DEFS_DIR = Path(__file__).resolve().parent.parent / "augmented_defs"


@st.cache_resource(show_spinner=False)
def load_data():
    """Load bot definitions and embedding index."""
    index, bots = load_index()
    return index, bots


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


INDEX, BOTS = load_data()
BOT_NAMES = list(BOTS.keys())


def search_bots(query: str):
    """Return bot IDs matching the user query via embeddings."""
    if not query:
        return BOT_NAMES
    matches = search(query, INDEX, top_n=len(BOT_NAMES))
    # Filter to bots with a reasonable similarity score
    results = []
    for bot_id, items in matches:
        if items and items[0].get("score", 0) > 0.2:
            results.append(bot_id)
    return results


st.sidebar.title("Teams Bot Explorer")
search_query = st.sidebar.text_input("Search bots")
options = search_bots(search_query)
if not options:
    st.sidebar.write("No bots found")
    st.stop()
selected_bot = st.sidebar.selectbox(
    "Select a bot",
    options,
    format_func=lambda bot_id: BOTS[bot_id].get("name", bot_id),
)

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
with st.expander("Raw JSON"):
    st.json(bot_data)
