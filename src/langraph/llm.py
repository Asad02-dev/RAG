from openai import OpenAI

from configs.settings import OPENAI_API_KEY, OPENAI_MODEL


client = OpenAI(api_key=OPENAI_API_KEY)


def call_llm(prompt: str, messages: list, json_mode: bool = False) -> str:

    # The whole conversation is sent as one text block: "[from] text"
    conversation = "\n".join(
        f"[{message['from']}] {message['text']}"
        for message in messages
    )

    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": conversation},
        ],
        response_format={"type": "json_object"} if json_mode else None,
    )

    return response.choices[0].message.content
