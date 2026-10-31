"""Quick check that your Gemini key and model work. Run: python test_connection.py"""
import os
from dotenv import load_dotenv
from google import genai
from google.genai import errors

load_dotenv()
key = os.getenv("GEMINI_API_KEY")
model = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
if not key:
    raise SystemExit("No GEMINI_API_KEY in .env")

client = genai.Client(api_key=key)

print("Models your key can use:")
for m in client.models.list():
    if "generateContent" in (m.supported_actions or []) and "flash" in m.name:
        print("  ", m.name.replace("models/", ""))

print(f"\nTesting: {model}")
try:
    reply = client.models.generate_content(model=model, contents="Say OK if you can read this.")
    print("Reply:", reply.text)
except errors.APIError as e:
    print(f"ERROR {e.code}: {e.message}")