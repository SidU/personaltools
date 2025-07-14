import streamlit as st

from embedding_utils import load_index, search

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
        for m in matches:
            st.markdown(f"**Example:** {m['prompt']}")
            if m.get('description'):
                st.write(m['description'])
            if m.get('command'):
                st.caption(f"Suggested command: {m['command']}")
            st.caption(f"Score: {m['score']:.2f}")
            st.markdown('---')

