from openai import OpenAI

from configs.settings import OPENAI_API_KEY, OPENAI_MODEL


client = OpenAI(api_key=OPENAI_API_KEY)


def call_llm(prompt: str, json_mode: bool = False) -> str:

    # Everything the agent needs is already inside the prompt
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"} if json_mode else None,
    )

    return response.choices[0].message.content
