# Run from the project folder:  streamlit run src/supervisor_parallel/streamlit_app.py

import io
import sys
import time
import logging
import threading

sys.path.insert(0, ".")   # so the "src..." and "configs..." imports work

import streamlit as st

from configs.settings import NEO4J_DATABASE
from src.services.neo4j_service import driver
from src.supervisor_parallel.supervisor import review


st.title("🧭 Supervisor Parallel Review")

records, _, _ = driver.execute_query("MATCH (s:Submission) RETURN s.name AS name", database_=NEO4J_DATABASE)
submission_key = st.selectbox("Submission", [record["name"] for record in records])


if st.button("Run review", type="primary"):

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
