"""LLM access with schema validation and one corrective retry."""
import logging
import os
import re

from pydantic import ValidationError


log = logging.getLogger("talentverse.ai")


class AIError(Exception):
    """Raised for any AI failure that should be shown to the user."""


def _friendly(exc: Exception) -> str:
    """Map provider errors to a useful message. The full error goes to the server log."""
    text = str(exc).lower()
    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    if status in (401, 403) or "api key" in text or "api_key" in text or "permission" in text:
        return "The AI key was rejected. Check the API key set on the server."
    if status == 404 or "not found" in text or "is not supported" in text:
        return "The AI model name was not found. Check GEMINI_MODEL (or ANTHROPIC_MODEL) on the server."
    if status == 429 or "quota" in text or "rate limit" in text or "resource_exhausted" in text:
        return "The AI service quota or rate limit was reached. Wait a minute and try again."
    if status in (500, 502, 503, 504) or "overloaded" in text or "unavailable" in text:
        return "The AI service is busy right now. Try again in a moment."
    return "The AI service failed. Check the server logs for the exact error."


def _call_model(system: str, user: str, json_mode: bool = True) -> str:
    provider = os.getenv("AI_PROVIDER", "gemini").lower()
    try:
        if provider == "anthropic":
            if not os.getenv("ANTHROPIC_API_KEY"):
                raise AIError("The AI service is not configured on the server.")
            import anthropic
            client = anthropic.Anthropic()
            msg = client.messages.create(
                model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5"),
                max_tokens=4000,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")

        if not os.getenv("GEMINI_API_KEY"):
            raise AIError("The AI service is not configured on the server.")
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

        def run(with_thinking: bool):
            kwargs = dict(system_instruction=system)
            if json_mode:
                kwargs["response_mime_type"] = "application/json"
            level = os.getenv("GEMINI_THINKING_LEVEL", "low").strip()
            if with_thinking and level and level != "off":
                # Extraction is simple, so low reasoning effort is much faster.
                kwargs["thinking_config"] = types.ThinkingConfig(thinking_level=level)
            return client.models.generate_content(
                model=model, contents=user, config=types.GenerateContentConfig(**kwargs))

        try:
            resp = run(True)
        except Exception as exc:
            # Older SDKs or models may not accept thinking_level: retry without it.
            if "thinking" in str(exc).lower() or isinstance(exc, (TypeError, ValueError)):
                log.warning("Retrying without thinking config: %s", str(exc)[:200])
                resp = run(False)
            else:
                raise
        return resp.text or ""
    except AIError:
        raise
    except Exception as exc:  # network, quota, auth, SDK errors
        log.error("AI call failed: %s: %s", type(exc).__name__, str(exc)[:400])
        raise AIError(_friendly(exc)) from exc


def _json_text(raw: str) -> str:
    raw = (raw or "").strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw)
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("reply contained no JSON object")
    return raw[start:end + 1]


def _summarize(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        parts = [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()[:5]]
        return "; ".join(parts)
    return str(exc)


def structured_call(model_cls, system: str, user: str, attempts: int = 2):
    """Call the LLM, validate against a Pydantic model, retry once with the errors."""
    prompt = user
    for _ in range(attempts):
        raw = _call_model(system, prompt)
        try:
            return model_cls.model_validate_json(_json_text(raw))
        except ValueError as exc:  # includes pydantic.ValidationError
            prompt = (user + "\n\nYour previous reply was rejected: "
                      + _summarize(exc) + "\nReturn corrected JSON only.")
    raise AIError("The AI returned data that failed validation twice. Please try again.")


def generate_text(system: str, user: str) -> str:
    """Plain-text reply (used by the mentor chatbot)."""
    text = (_call_model(system, user, json_mode=False) or "").strip()
    if not text:
        raise AIError("The AI returned an empty reply. Please try again.")
    return text
