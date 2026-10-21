# Run from the project folder:  streamlit run src/hybrid_agent/streamlit_app.py

import io
import sys
import logging

sys.path.insert(0, ".")   # so the "src..." and "configs..." imports work

import streamlit as st

from src.hybrid_agent.agent import chat, history


st.title("🔗 Hybrid Agent (LangGraph + Foundry)")
st.caption("Ask about the weather, a submission, or the web, e.g. \"Who is the cedant of submission 1547612, and is there any recent news about it?\"")

# Each conversation has its own memory. Same ID = the agent remembers it.
thread_id = st.sidebar.text_input("Conversation ID", value="user-1")

# Show the saved conversation
for message in history(thread_id):
    if message.type == "human":
        st.chat_message("user").write(message.text)
    elif message.type == "ai" and message.text:
        st.chat_message("assistant").write(message.text)

question = st.chat_input("Ask a question")

if question:

    st.chat_message("user").write(question)

    # Send the agent's log lines into `logs`, as "time  message"
    logs = io.StringIO()
    handler = logging.StreamHandler(logs)
    handler.setFormatter(logging.Formatter("%(asctime)s  %(message)s", datefmt="%H:%M:%S"))
    logger = logging.getLogger("hybrid_agent")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)

    with st.spinner("Thinking..."):
        answer = chat(thread_id, question)

    logger.removeHandler(handler)

    st.chat_message("assistant").write(answer)

    with st.expander("Logs"):
        st.code(logs.getvalue())
