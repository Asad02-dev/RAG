# Run from the project folder:  streamlit run src/supervisor_langgraph/streamlit_app.py

import sys

sys.path.insert(0, ".")   # so the "src..." and "configs..." imports work

import streamlit as st

from src.supervisor_langgraph.supervisor import app, chat, MAX_STEPS


# Example prompts, shown on the right to copy and paste
PROMPTS = [
    "Should we quote this submission 1440741?",
    "Coverage should be All Risks property including flood, limit USD 10M per occurrence.",
]


def show_step(message):

    # One step: the supervisor hands the work to an agent, or an agent answers
    sender = message.name or message.type

    for call in getattr(message, "tool_calls", []):
        if call["name"].startswith("transfer_to_"):
            st.markdown(f"**{sender}** → hands over to **{call['name'].removeprefix('transfer_to_')}**")
        else:
            st.markdown(f"**{sender}** → calls `{call['name']}`")

    if message.type == "ai" and message.text:
        st.markdown(f"**{sender}:** {message.text}")


def show_answer(messages: list):

    # The final answer is the last message with text (the supervisor's reply)
    answers = [m.text for m in messages if m.type == "ai" and m.text]
    if not answers:
        st.write("No answer was given for this question.")
        return

    # Colour it by the underwriter's decision: red = decline, yellow = need more info, green = quote
    decisions = [m.text for m in messages if m.text.startswith("DECISION:")]
    decision = decisions[-1] if decisions else ""

    if "DECLINE" in decision:
        st.error(answers[-1])
    elif "NEED MORE INFO" in decision:
        st.warning(answers[-1])
    elif "QUOTE" in decision:
        st.success(answers[-1])
    else:
        st.write(answers[-1])


st.set_page_config(page_title="Supervisor Agent", layout="wide")
st.title("🧭 Supervisor Agent")
st.caption("The supervisor sends your question to the TA agent (submission facts) and the Underwriter agent (quote decision).")

# Each case has its own memory. Same Case ID = the conversation continues.
case_id = st.sidebar.text_input("Case ID", value="case-1")
config = {"configurable": {"thread_id": case_id}, "recursion_limit": MAX_STEPS}

# The chat on the left, the prompt gallery on the right
chat_col, gallery_col = st.columns([2, 1])

with gallery_col:
    st.subheader("Prompt gallery")
    st.caption("Copy a prompt (icon at the right of each box) and paste it in the question box.")
    for prompt in PROMPTS:
        st.code(prompt, language=None, wrap_lines=True)

question = st.chat_input("Ask about a submission")

with chat_col:

    # The saved conversation, split into turns: one user question + everything that followed it
    saved = app.get_state(config).values.get("messages", [])
    turns = []
    for message in saved:
        if message.type == "human":
            turns.append({"question": message.text, "messages": []})
        elif turns:
            turns[-1]["messages"].append(message)

    for turn in turns:
        st.chat_message("user").write(turn["question"])
        with st.chat_message("assistant"):
            with st.expander("Agent steps"):
                for message in turn["messages"]:
                    show_step(message)
            show_answer(turn["messages"])

    if question:

        st.chat_message("user").write(question)

        try:
            with st.spinner("The agents are working..."):
                chat(case_id, question)

        except Exception as error:
            st.error(f"Something went wrong: {error}")
            st.stop()

        # Show the new answer and its steps from the saved conversation
        st.rerun()
