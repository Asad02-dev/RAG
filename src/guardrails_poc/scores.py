import sys

from langsmith import Client

sys.path.insert(0, ".")   # so the "configs..." import works

import configs.settings   # loads .env (LANGSMITH_API_KEY)


def question_of(run) -> str:

    # The last message the agent received. Empty for a run that continues after an approval.
    messages = (run.inputs or {}).get("messages") or []
    if not messages:
        return ""

    message = messages[-1]
    if isinstance(message, dict):
        return str(message.get("content") or message.get("kwargs", {}).get("content", ""))
    return str(message)


if __name__ == "__main__":

    # Print symbols like °C correctly in the Windows terminal
    sys.stdout.reconfigure(encoding="utf-8")

    client = Client()

    # The latest 20 agent runs (only the whole agent run, not its inner steps)
    runs = client.list_runs(project_name="guardrails-poc", is_root=True,
                            filter='eq(name, "LangGraph")', limit=20)

    for run in runs:
        feedback = {f.key: (f.score, f.comment) for f in client.list_feedback(run_ids=[run.id])}
        score, reason = feedback.get("quality", ("-", "not scored yet"))
        print(f"{run.start_time:%Y-%m-%d %H:%M} | {question_of(run)[:80]:<80} | {score} | {reason}")
