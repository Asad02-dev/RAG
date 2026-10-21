# First start the API:     uvicorn src.mcp_agent.api:app --port 8001
# Then run from the project folder:  streamlit run src/mcp_agent/streamlit_app.py

import requests
import streamlit as st

# Where the agent's API runs (api.py)
API_URL = "http://localhost:8001"


st.title("🔌 MCP Agent")
st.caption("Ask about the weather, a submission, or both, e.g. \"What is the weather at the location of submission 1547612?\"")

# Each conversation has its own memory. Same ID = the agent remembers it.
thread_id = st.sidebar.text_input("Conversation ID", value="user-1")

# Show the saved conversation (asked from the API)
try:
    saved_messages = requests.get(f"{API_URL}/history", params={"thread_id": thread_id}, timeout=60).json()
except requests.ConnectionError:
    st.error("The agent's API is not running. Start it first:  uvicorn src.mcp_agent.api:app --port 8001")
    st.stop()

for message in saved_messages:
    if message["type"] == "human":
        st.chat_message("user").write(message["text"])
    elif message["type"] == "ai" and message["text"]:
        st.chat_message("assistant").write(message["text"])

question = st.chat_input("Ask a question")

if question:

    st.chat_message("user").write(question)

    # Send the question to the API; it returns the answer and the agent's log lines
    with st.spinner("Thinking..."):
        reply = requests.post(f"{API_URL}/chat", json={"thread_id": thread_id, "question": question}, timeout=300).json()

    st.chat_message("assistant").write(reply["answer"])

    with st.expander("Logs"):
        st.code(reply["logs"])
