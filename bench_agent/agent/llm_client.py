import os
from openai import OpenAI

def make_client() -> OpenAI:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    return OpenAI(api_key=api_key)

def chat(client: OpenAI, model: str, messages: list[dict]) -> str:
    resp = client.chat.completions.create(model=model, messages=messages)
    return resp.choices[0].message.content or ""
