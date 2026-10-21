# Run from the project folder:  streamlit run src/supervisor_parallel/streamlit_app.py

import io
import sys
import time
import logging
import threading

sys.path.insert(0, ".")   # so the "src..." and "configs..." imports work

import streamlit as st

from src.supervisor_parallel.supervisor import review


# Submission numbers, shown on the right to copy
PROMPTS = [
    "1440741",
    "1547700",
    "1547612",
]


st.set_page_config(page_title="Submission Quote Review", layout="wide")
st.title("🧭 Submission Quote Review")
st.caption("Three agents check the submission at the same time (data, history and risk), "
           "then the supervisor gives the quote recommendation.")

# The review on the left, the prompt gallery on the right
main_col, gallery_col = st.columns([2, 1])

with gallery_col:
    st.subheader("Prompt gallery")
    st.caption("Copy a submission number (icon at the right of each box).")
    for prompt in PROMPTS:
        st.code(prompt, language=None, wrap_lines=True)

with main_col:

    # Paste a submission number from the prompt gallery
    submission_key = st.text_input("Submission number", placeholder="e.g. 1547612").strip()


    if st.button("Run review", type="primary", disabled=not submission_key):

        st.subheader("Logs")
        log_box = st.empty()
        logs = io.StringIO()
        result = {}

        # Send the agents' log lines into `logs`, as "time  message"
        handler = logging.StreamHandler(logs)
        handler.setFormatter(logging.Formatter("%(asctime)s  %(message)s", datefmt="%H:%M:%S"))
        logger = logging.getLogger("supervisor_parallel")
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)

        def run():
            result.update(review(submission_key))

        start = time.time()

        # Run the review in the background and show the logs every 0.3 seconds
        worker = threading.Thread(target=run)
        worker.start()
        while worker.is_alive():
            log_box.code(logs.getvalue())
            time.sleep(0.3)

        logger.removeHandler(handler)
        log_box.code(logs.getvalue())

        for step in result["steps"]:
            st.caption(f"Supervisor called in one step: {', '.join(step)}")

        st.subheader("Recommendation")
        if "NO QUOTE" in result["review"]:
            st.error(result["review"])
        elif "NEED MORE INFO" in result["review"]:
            st.warning(result["review"])
        else:
            st.success(result["review"])

        st.caption(f"Total time: {time.time() - start:.1f} seconds")

        st.subheader("Agents")
        left, middle, right = st.columns(3)
        left.markdown("**Data Check**")
        left.write(result["data_check"])
        middle.markdown("**History**")
        middle.write(result["history"])
        right.markdown("**Risk**")
        right.write(result["risk"])
