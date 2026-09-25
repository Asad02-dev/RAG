import os
from google import genai
from dotenv import load_dotenv

load_dotenv("c:/MyProjects/RAG/.env")

client = genai.Client()
texts = ["hello", "world", "this is a test"]
result = client.models.embed_content(
    model="gemini-embedding-2",
    contents=texts,
)
print("Returned embeddings:", len(result.embeddings))
