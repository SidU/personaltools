import json
import difflib
from pathlib import Path
import sys
import pandas as pd

# Ensure repo root is on sys.path for local module imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # noqa: E402

import streamlit as st  # noqa: E402

from bot_finder_app.embedding_utils import load_index, search  # noqa: E402
from invocation_utils import build_suggested_invocation, expand_query_with_ai  # noqa: E402,E501


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
    """Return list of commands with their descriptions and scopes."""
    commands = []
    for bot in app.get("bots", []):
        for cl in bot.get("commandLists", []):
            scopes = cl.get("scopes") or []
            for cmd in cl.get("commands", []):
                title = cmd.get("title")
                desc = cmd.get("description", "")
                if title:
                    commands.append(
                        {
                            "title": title,
                            "description": desc,
                            "scopes": scopes,
                        }
                    )
    return commands


def get_scopes(app):
    """Return set of scopes supported by a bot manifest."""
    scopes = set()
    for bot in app.get("bots", []):
        scopes.update(bot.get("scopes") or [])
    return scopes


def is_notification_only(app) -> bool:
    """Return True if any bot in the app is notification only."""
    for bot in app.get("bots", []):
        if bot.get("isNotificationOnly"):
            return True
    return False


INDEX, BOTS = load_data()
BOT_NAMES = list(BOTS.keys())
ALL_SCOPES = sorted({s for b in BOTS.values() for s in get_scopes(b)})
NOTIF_OPTIONS = ["Any", "Notification only", "Interactive"]


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
                difflib.SequenceMatcher(None, query, desc.lower()).ratio()
                if desc else 0,
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


def filter_by_scopes(bot_ids: list, scopes: list) -> list:
    """Return bot IDs that support at least one of the given scopes."""
    if not scopes:
        return bot_ids
    filtered = []
    wanted = set(scopes)
    for bot_id in bot_ids:
        data = BOTS.get(bot_id, {})
        if get_scopes(data) & wanted:
            filtered.append(bot_id)
    return filtered


def filter_by_notification(bot_ids: list, option: str) -> list:
    """Return bot IDs filtered by notification-only setting."""
    if option == "Any":
        return bot_ids
    want_notification = option == "Notification only"
    filtered = []
    for bot_id in bot_ids:
        data = BOTS.get(bot_id, {})
        if is_notification_only(data) == want_notification:
            filtered.append(bot_id)
    return filtered


def generate_csv(bot_ids: list) -> str:
    """Return CSV string for the given bot app IDs."""
    lines = ["App Name,App ID,Bot ID"]
    for app_id in bot_ids:
        app = BOTS.get(app_id, {})
        app_name = app.get("name", app_id)
        for bot in app.get("bots", []):
            bot_id = bot.get("id", "")
            lines.append(f"{app_name},{app_id},{bot_id}")
    return "\n".join(lines)


def reset_filters():
    """Clear all search fields and filters."""
    st.session_state.selected_bot = None
    st.session_state.search_results = BOT_NAMES
    st.session_state.last_action = "dropdown"
    st.session_state.name_query = ""
    st.session_state.msg_query = ""
    st.session_state.ai_expand = False
    st.session_state.scope_filter = []
    st.session_state.notif_filter = NOTIF_OPTIONS[0]
    st.session_state.dropdown = BOT_NAMES[0]
    st.session_state.sort_alpha = False


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
    ai_expand = st.checkbox(
        "Enhance with AI",
        key="ai_expand",
        disabled=not message_query.strip(),
    )
    def _run_semantic_search() -> None:
        """Perform semantic search and update session state."""
        query = st.session_state.msg_query
        if st.session_state.ai_expand:
            query = expand_query_with_ai(query)
        st.session_state.expanded_query = query
        st.session_state.msg_query = query
        st.session_state.search_results = semantic_search(query)
        st.session_state.selected_bot = None
        st.session_state.last_action = "semantic"

    st.button("Find", key="msg_btn", on_click=_run_semantic_search)

    scope_filter = st.multiselect(
        "Filter by scope",
        ALL_SCOPES,
        key="scope_filter",
    )

    notif_filter = st.selectbox(
        "Filter by bot type",
        NOTIF_OPTIONS,
        key="notif_filter",
    )

    st.button("Reset", key="reset_btn", on_click=reset_filters)


with col_center:
    selected_scopes = st.session_state.get("scope_filter", [])
    notif_option = st.session_state.get("notif_filter", "Any")
    results = filter_by_scopes(
        st.session_state.search_results,
        selected_scopes,
    )
    results = filter_by_notification(results, notif_option)
    st.header(f"Results ({len(results)})")
    sort_alpha = st.checkbox("Sort alphabetically", key="sort_alpha")
    if sort_alpha:
        results = sorted(
            results,
            key=lambda b: BOTS[b].get("name", b).lower(),
        )
    if results:
        csv_str = generate_csv(results)
        st.download_button(
            "Export as CSV",
            csv_str,
            file_name="bot-results.csv",
            mime="text/csv",
        )
        st.divider()
        df = pd.DataFrame(
            {
                "App Name": [BOTS[b].get("name", b) for b in results],
                "App ID": results,
            }
        )
        default_idx = (
            results.index(st.session_state.selected_bot)
            if st.session_state.selected_bot in results
            else 0
        )
        selected_res = st.radio(
            "Select a bot",
            results,
            format_func=lambda x: BOTS[x].get("name", x),
            index=default_idx,
            key="result_select",
        )
        if selected_res != st.session_state.selected_bot:
            st.session_state.selected_bot = selected_res
            st.session_state.last_action = "select"

        def _highlight(row):
            if row["App ID"] == st.session_state.selected_bot:
                return ["background-color: #ffeeba"] * len(row)
            return [""] * len(row)

        st.table(df.style.apply(_highlight, axis=1))
    else:
        st.write("No bots found")


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
        selected_scopes = st.session_state.get("scope_filter", [])
        if selected_scopes:
            commands = [
                c
                for c in commands
                if not c["scopes"] or set(c["scopes"]) & set(selected_scopes)
            ]
        if commands:
            st.subheader("Commands")
            for cmd in commands:
                with st.expander(cmd["title"]):
                    if cmd["scopes"]:
                        st.caption("Scopes: " + ", ".join(cmd["scopes"]))
                    st.write(cmd["description"] or "No description")

        suggestion = build_suggested_invocation(
            st.session_state.get("msg_query", ""),
            bot_id,
            bot_data,
            st.session_state.get("scope_filter", []),
        )
        if suggestion:
            st.subheader("Suggested Invocation")
            st.code(suggestion)
        else:
            st.info("No valid invocation could be generated for this bot.")

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
