import os
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv("c:/MyProjects/RAG/.env")
client = genai.Client()

texts = ["hello", "world"]

try:
    result = client.models.embed_content(
        model="gemini-embedding-2",
        contents=[types.Content(parts=[types.Part.from_text(text=t)]) for t in texts],
    )
    print("List of Content objects:", len(result.embeddings))
except Exception as e:
    print("Error 1:", e)

try:
    result = client.models.embed_content(
        model="gemini-embedding-2",
        contents=[{"text": t} for t in texts],
    )
    print("List of dicts:", len(result.embeddings))
except Exception as e:
    print("Error 2:", e)

try:
    result = client.models.embed_content(
        model="gemini-embedding-2",
        contents=texts,
    )
    print("List of strings:", len(result.embeddings))
except Exception as e:
    print("Error 3:", e)
