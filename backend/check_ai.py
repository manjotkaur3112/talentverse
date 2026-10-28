"""Run `python check_ai.py` to test your AI key and model without using the app."""
from dotenv import load_dotenv

load_dotenv()

import os
import ai

print("Provider:", os.getenv("AI_PROVIDER", "gemini"))
print("Model:   ", os.getenv("GEMINI_MODEL", "gemini-3.8-flash") if os.getenv("AI_PROVIDER", "gemini") == "gemini"
      else os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5"))
try:
    out = ai._call_model("Reply with JSON only.", 'Return {"ok": true}')
    print("SUCCESS. Model replied:", out.strip()[:200])
except Exception as exc:
    print("FAILED:", exc)
    cause = exc.__cause__
    if cause:
        print("Underlying error:", type(cause).__name__, str(cause)[:600])

    if os.getenv("AI_PROVIDER", "gemini") == "gemini" and os.getenv("GEMINI_API_KEY"):
        try:
            from google import genai
            client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
            names = sorted(m.name.replace("models/", "") for m in client.models.list()
                           if "generateContent" in (getattr(m, "supported_actions", None) or ["generateContent"]))
            flash = [n for n in names if "flash" in n]
            print("\nModels your key can use (flash family). Put one in GEMINI_MODEL:")
            for n in flash:
                print("  ", n)
        except Exception as e2:
            print("Could not list models:", type(e2).__name__, str(e2)[:300])
