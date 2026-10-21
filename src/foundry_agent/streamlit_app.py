# Run from the project folder:  streamlit run src/foundry_agent/streamlit_app.py

import io
import sys
import logging

sys.path.insert(0, ".")   # so the "src..." and "configs..." imports work

import streamlit as st

from src.foundry_agent.agent import chat, history


st.title("☁️ Foundry Agent")
st.caption("Ask about the weather, a submission, or both, e.g. \"What is the weather at the location of submission 1547612?\"")

# Each conversation has its own memory. Same ID = the agent remembers it.
thread_id = st.sidebar.text_input("Conversation ID", value="user-1")

# Show the saved conversation
for message in history(thread_id):
    st.chat_message(message["role"]).write(message["text"])

question = st.chat_input("Ask a question")

if question:

    st.chat_message("user").write(question)

    # Send the agent's log lines into `logs`, as "time  message"
    logs = io.StringIO()
    handler = logging.StreamHandler(logs)
    handler.setFormatter(logging.Formatter("%(asctime)s  %(message)s", datefmt="%H:%M:%S"))
    logger = logging.getLogger("foundry_agent")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)

    with st.spinner("Thinking..."):
        answer = chat(thread_id, question)

    logger.removeHandler(handler)

    st.chat_message("assistant").write(answer)

    with st.expander("Logs"):
        st.code(logs.getvalue())
