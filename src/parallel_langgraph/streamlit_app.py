"""Streamlit frontend for the parallel submission review.

Run from the project folder:   streamlit run src/parallel_langgraph/streamlit_app.py
"""

import io
import sys
import time
import threading
import contextlib
from pathlib import Path

# Streamlit runs this file directly, so add the project folder to the path for the "src..." imports
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st

from configs.settings import NEO4J_DATABASE
from src.services.neo4j_service import driver
from src.parallel_langgraph.review import review


st.set_page_config(page_title="Parallel Submission Review", page_icon="🕸️")
st.title("🕸️ Parallel Submission Review")
st.caption("Three agents check a submission at the same time, then a merge step gives one recommendation.")


@st.cache_data(ttl=60)
def list_submissions() -> list:

    # All submission numbers in Neo4j, for the dropdown
    records, _, _ = driver.execute_query(
        "MATCH (s:Submission) RETURN s.name AS name ORDER BY name",
        database_=NEO4J_DATABASE,
    )
    return [record["name"] for record in records]


submissions = list_submissions()

if submissions:
    submission_key = st.selectbox("Submission", submissions)
else:
    submission_key = st.text_input("Submission number (no submissions found in Neo4j)")


if st.button("Run review", type="primary", disabled=not submission_key):

    st.subheader("Logs")
    log_box = st.empty()

    logs = io.StringIO()
    result = {}

    def run():
        # Runs the review in the background, so the logs can be shown while the agents work
        try:
            result.update(review(submission_key))
        except Exception as error:
            result["error"] = str(error)

    start = time.time()

    # The agents' log() lines are printed; send them into `logs` and show them every 0.3 seconds
    with contextlib.redirect_stdout(logs):
        worker = threading.Thread(target=run)
        worker.start()
        while worker.is_alive():
            log_box.code(logs.getvalue() or "Starting...", language="text")
            time.sleep(0.3)

    seconds = time.time() - start
    log_box.code(logs.getvalue(), language="text")

    if "error" in result:
        st.error(f"The review failed: {result['error']}")
        st.stop()

    # ── The merged recommendation ──
    st.subheader("Recommendation")
    final = result["review"]
    recommendation = final.get("recommendation", "")
    message = f"**{recommendation}**: {final.get('reason', '')}"

    if recommendation == "QUOTE":
        st.success(message)
    elif recommendation == "NO QUOTE":
        st.error(message)
    else:
        st.warning(message)

    st.caption(f"Total time: {seconds:.1f} seconds")

    # ── What each agent found ──
    st.subheader("Agents")
    data_column, history_column, risk_column = st.columns(3)

    with data_column:
        st.markdown("**Data Check**")
        st.write(result["data_check"])

    with history_column:
        st.markdown("**History**")
        st.write(result["history"])

    with risk_column:
        st.markdown("**Risk**")
        st.write(result["risk"])

    with st.expander("Full result (JSON)"):
        st.json(result)
