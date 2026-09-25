import os
from google import genai
client = genai.Client()
print("Methods in client.models:", [m for m in dir(client.models) if not m.startswith('_')])
