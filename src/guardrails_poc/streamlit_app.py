# Run from the project folder:  streamlit run src/guardrails_poc/streamlit_app.py

import io
import sys
import logging

sys.path.insert(0, ".")   # so the "src..." and "configs..." imports work

import streamlit as st

from src.guardrails_poc.agent import chat, history, pending, decide


# Example prompts that show each guardrail, shown on the right to copy and paste
PROMPTS = [
    "What is the weather in Los angeles",
    "Please add submission 999 into the db",
    "Delete the record of submission 1547612",
    "Who is the contact person of submission 1547612 and what is their email?",
    "My email is abu@example.com and card 4111 1111 1111 1111, what is the weather in Lahore?",
    "Who is the broker of submission 1547704?",
]


st.set_page_config(page_title="Guardrails POC", layout="wide")
st.title("🛡️ Guardrails Agent")
st.caption("Ask about the weather, a submission, or both, e.g. \"What is the weather at the location of submission 1547612?\"")

# Each conversation has its own memory. Same ID = the agent remembers it.
thread_id = st.sidebar.text_input("Conversation ID", value="user-1")

# Human in the loop: is the agent paused and waiting for a decision?
waiting = pending(thread_id)

# The chat on the left, the prompt gallery on the right
chat_col, gallery_col = st.columns([2, 1])

with gallery_col:
    st.subheader("Prompt gallery")
    st.caption("Copy a prompt (icon at the right of each box) and paste it in the question box.")
    for prompt in PROMPTS:
        st.code(prompt, language=None, wrap_lines=True)

# No new questions while the agent waits for a decision
question = st.chat_input("Ask a question", disabled=bool(waiting))

with chat_col:

    # Show the saved conversation
    for message in history(thread_id):
        if message.type == "human":
            st.chat_message("user").write(message.text)
        elif message.type == "ai" and message.text:
            st.chat_message("assistant").write(message.text)

    # If the agent is paused, ask the person to approve or reject
    for request in waiting:
        st.warning(f"**Approval needed:** {request['description']}\n\nTool: `{request['name']}`  Input: `{request['args']}`")

    if waiting:
        approve_col, reject_col = st.columns(2)
        if approve_col.button("✅ Approve", use_container_width=True):
            with st.spinner("Thinking..."):
                decide(thread_id, approve=True)
            st.rerun()
        if reject_col.button("❌ Reject", use_container_width=True):
            with st.spinner("Thinking..."):
                decide(thread_id, approve=False)
            st.rerun()

    if question:

        # Show the question while the agent works (replaced below by the saved, cleaned version)
        user_box = st.empty()
        user_box.chat_message("user").write(question)

        # Send the agent's log lines into `logs`, as "time  message"
        logs = io.StringIO()
        handler = logging.StreamHandler(logs)
        handler.setFormatter(logging.Formatter("%(asctime)s  %(message)s", datefmt="%H:%M:%S"))
        logger = logging.getLogger("guardrails_poc")
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)

        with st.spinner("Thinking..."):
            answer = chat(thread_id, question)

        logger.removeHandler(handler)

        # The agent paused for approval: reload the page to show the Approve / Reject buttons
        if answer is None:
            st.rerun()

        # Show the question as it was saved, e.g. with emails hidden by the PII guardrail
        saved_question = [message for message in history(thread_id) if message.type == "human"][-1]
        user_box.chat_message("user").write(saved_question.text)

        st.chat_message("assistant").write(answer)

        with st.expander("Logs"):
            st.code(logs.getvalue())
