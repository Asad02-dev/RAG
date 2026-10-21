# Run from the project folder:  streamlit run src/orchestrator_agent/streamlit_app.py

import io
import sys
import logging

sys.path.insert(0, ".")   # so the "src..." and "configs..." imports work

import streamlit as st

from src.orchestrator_agent.agent import chat, history, count_tokens


# Example prompts, shown on the right to copy and paste
PROMPTS = [
    "Hi",
    "How can you assist me today?",
    "How to create a submission",
    "Give me the submission detail of 1547612",
    "What is the temperature there?",
    "What is the weather at the location of submission 1547704",
    "Give me forecast of next 15 days",
]


def show_tokens(tokens: dict | None):

    # The tokens used for one answer, in small grey text under it (nothing if OpenAI failed)
    if tokens:
        st.caption(f"Tokens: input {tokens['input']:,} · output {tokens['output']:,} · total {tokens['total']:,}")


st.set_page_config(page_title="Orchestrator Agent", layout="wide")
st.title("🤖 Orchestrator Agent")
st.caption("Ask about the weather, a submission, or both, e.g. \"What is the weather at the location of submission 1547612?\"")

# Each conversation has its own memory. Same ID = the agent remembers it.
thread_id = st.sidebar.text_input("Conversation ID", value="user-1")

# The chat on the left, the prompt gallery on the right
chat_col, gallery_col = st.columns([2, 1])

with gallery_col:
    st.subheader("Prompt gallery")
    st.caption("Copy a prompt (icon at the right of each box) and paste it in the question box.")
    for prompt in PROMPTS:
        st.code(prompt, language=None, wrap_lines=True)

question = st.chat_input("Ask a question")

with chat_col:

    # The saved conversation, split into turns: one question + the messages that answered it
    turns = []
    for message in history(thread_id):
        if message.type == "human":
            turns.append({"question": message.text, "messages": []})
        elif turns:
            turns[-1]["messages"].append(message)

    for turn in turns:
        st.chat_message("user").write(turn["question"])
        answers = [m.text for m in turn["messages"] if m.type == "ai" and m.text]
        if answers:
            with st.chat_message("assistant"):
                st.write(answers[-1])
                show_tokens(count_tokens(turn["messages"]))

    if question:

        st.chat_message("user").write(question)

        # Send the agent's log lines into `logs`, as "time  message"
        logs = io.StringIO()
        handler = logging.StreamHandler(logs)
        handler.setFormatter(logging.Formatter("%(asctime)s  %(message)s", datefmt="%H:%M:%S"))
        logger = logging.getLogger("orchestrator_agent")
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)

        with st.spinner("Thinking..."):
            answer, tokens = chat(thread_id, question)

        logger.removeHandler(handler)

        with st.chat_message("assistant"):
            st.write(answer)
            show_tokens(tokens)

        with st.expander("Logs"):
            st.code(logs.getvalue())
