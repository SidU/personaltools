import streamlit as st

from embedding_utils import load_index, search
from invocation_utils import build_suggested_invocation

st.set_page_config(page_title="Bot Finder")

@st.cache_resource(show_spinner=False)
def load_resources():
    return load_index()

index, bots = load_resources()

st.title("Teams Bot Finder")
query = st.text_input("Ask something about your work")

if query:
    results = search(query, index, top_n=5)
    for bot_id, matches in results:
        bot_data = bots.get(bot_id, {})
        st.subheader(f"{bot_data.get('name', bot_id)}")
        desc = bot_data.get('description') or bot_data.get('shortDescription') or ''
        if desc:
            st.write(desc)
        suggestion = build_suggested_invocation(query, bot_id, bot_data)
        if suggestion:
            st.caption(f"Suggested Invocation: {suggestion}")
        for m in matches:
            kind = m.get('kind', 'example')
            if kind == 'app_description':
                st.markdown(f"**Description match:** {m['prompt']}")
            elif kind == 'command':
                st.markdown(f"**Command:** {m.get('command', '')}")
                st.write(m['description'] or m['prompt'])
            else:
                st.markdown(f"**Example:** {m['prompt']}")
                if m.get('description'):
                    st.write(m['description'])
            if kind != 'command' and m.get('command'):
                st.caption(f"Suggested command: {m['command']}")
            st.caption(f"Score: {m['score']:.2f}")
            st.markdown('---')

