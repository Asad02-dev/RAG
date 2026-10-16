from langchain_openai import ChatOpenAI

from configs.settings import OPENAI_API_KEY, OPENAI_MODEL


# One OpenAI chat model, shared by the orchestrator and the three agents.
# use_responses_api=True: newer models (e.g. gpt-5.6) only support tools through OpenAI's Responses API.
model = ChatOpenAI(
    model=OPENAI_MODEL,
    api_key=OPENAI_API_KEY,
    use_responses_api=True,
)
