import json
import difflib
from pathlib import Path
import sys

# Ensure repo root is on sys.path for local module imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from bot_finder_app.embedding_utils import load_index, search


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


def fuzzy_search(query: str) -> list:
    """Return bot IDs that fuzzily match the query by name or description."""
    if not query:
        return BOT_NAMES
    query = query.lower().strip()
    scored = []
    for bot_id, data in BOTS.items():
        name = data.get("name", bot_id)
        desc = get_description(data)
        text = f"{name} {desc}".lower()
        if query in text:
            score = 1.0
        else:
            score = max(
                difflib.SequenceMatcher(None, query, name.lower()).ratio(),
                difflib.SequenceMatcher(None, query, desc.lower()).ratio() if desc else 0,
            )
        if score > 0.3:
            scored.append((score, bot_id))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [b for _, b in scored]


def semantic_search(query: str) -> list:
    """Return bot IDs ordered by semantic similarity to the query."""
    if not query:
        return BOT_NAMES
    matches = search(query, INDEX, top_n=len(BOT_NAMES))
    results = []
    for bot_id, items in matches:
        if items and items[0].get("score", 0) > 0.2:
            results.append(bot_id)
    return results


st.set_page_config(page_title="Teams Bot Explorer", layout="wide")

if "selected_bot" not in st.session_state:
    st.session_state.selected_bot = None
if "search_results" not in st.session_state:
    st.session_state.search_results = BOT_NAMES
if "last_action" not in st.session_state:
    st.session_state.last_action = "dropdown"

col_left, col_center, col_right = st.columns([1, 2, 2])

with col_left:
    st.header("Find Bots")
    dd_value = st.selectbox(
        "Browse bots",
        BOT_NAMES,
        format_func=lambda x: BOTS[x].get("name", x),
        key="dropdown",
    )
    if st.button("Select", key="select_btn"):
        st.session_state.selected_bot = dd_value
        st.session_state.search_results = [dd_value]
        st.session_state.last_action = "dropdown"

    name_query = st.text_input("Name search", key="name_query")
    if st.button("Search by name", key="name_btn"):
        st.session_state.search_results = fuzzy_search(name_query)
        st.session_state.selected_bot = None
        st.session_state.last_action = "name"

    message_query = st.text_input("Semantic search", key="msg_query")
    if st.button("Search message", key="msg_btn"):
        st.session_state.search_results = semantic_search(message_query)
        st.session_state.selected_bot = None
        st.session_state.last_action = "semantic"


with col_center:
    st.header("Results")
    results = st.session_state.search_results
    if not results:
        st.write("No bots found")
    for bot_id in results:
        name = BOTS[bot_id].get("name", bot_id)
        if st.button(name, key=f"res_{bot_id}"):
            st.session_state.selected_bot = bot_id
            st.session_state.last_action = "select"
        st.caption(bot_id)


with col_right:
    bot_id = st.session_state.selected_bot
    if bot_id:
        bot_data = BOTS.get(bot_id, {})
        st.subheader(f"{bot_data.get('name', bot_id)} ({bot_id})")
        st.write(get_description(bot_data))

        tags = bot_data.get("categories") or bot_data.get("tags")
        if tags:
            st.write("**Tags:** " + ", ".join(tags))

        meta_keys = ["version", "developerName", "creatorId"]
        metadata = {k: bot_data.get(k) for k in meta_keys if bot_data.get(k)}
        if metadata:
            with st.expander("Metadata"):
                st.json(metadata)

        commands = get_commands(bot_data)
        if commands:
            st.subheader("Commands")
            for cmd in commands:
                with st.expander(cmd["title"]):
                    st.write(cmd["description"] or "No description")

        examples = bot_data.get("examplePrompts") or []
        if examples:
            st.subheader("Example Prompts")
            for ex in examples:
                with st.expander(ex.get("prompt")):
                    if ex.get("description"):
                        st.write(ex["description"])
                    if ex.get("command"):
                        st.caption(f"Command: {ex['command']}")

        json_str = json.dumps(bot_data, ensure_ascii=False, indent=2)
        st.download_button(
            "Download JSON",
            json_str,
            file_name=f"{bot_id}.json",
        )
        with st.expander("Raw JSON"):
            st.json(bot_data)
    else:
        st.write("Select a bot to see details")
