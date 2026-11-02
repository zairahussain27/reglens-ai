"""Single entry point for LLM calls with retries, JSON parsing and clear errors."""
import json
import logging
import re
import time

import httpx

from ..config import get_settings

log = logging.getLogger("reglens.ai")
settings = get_settings()
RETRY_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}
GROQ_FALLBACK_MODEL = "openai/gpt-oss-120b"


class AIError(Exception):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def provider() -> str | None:
    if settings.groq_api_key:
        return "groq"
    return None


def available() -> bool:
    return provider() is not None


def status() -> dict:
    p = provider()
    model = settings.groq_model if p == "groq" else None
    return {"available": p is not None, "provider": p, "model": model}


def _post(url: str, headers: dict, payload: dict, timeout: float, attempts: int = 2) -> dict:
    last = "unknown error"
    last_status = None
    for attempt in range(attempts):
        try:
            response = httpx.post(url, headers=headers, json=payload, timeout=timeout)
        except httpx.HTTPError as exc:
            last, last_status = f"network error ({type(exc).__name__})", None
        else:
            if response.status_code < 400:
                try:
                    return response.json()
                except ValueError as exc:
                    raise AIError("The AI provider returned invalid JSON.", response.status_code) from exc
            last, last_status = f"HTTP {response.status_code}: {response.text[:240]}", response.status_code
            if response.status_code not in RETRY_STATUS:
                raise AIError(last, last_status)
        if attempt + 1 < attempts:
            time.sleep(1.5 * (attempt + 1))
    raise AIError(last, last_status)


def _groq(system: str, prompt: str, max_tokens: int, timeout: float, json_mode: bool) -> str:
    def body(model: str, effort: bool) -> dict:
        payload = {"model": model, "max_tokens": max_tokens, "temperature": 0.1,
                   "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]}
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        if effort and model.startswith("openai/gpt-oss"):
            payload["reasoning_effort"] = "low"
        return payload

    tries = [(settings.groq_model, True), (settings.groq_model, False), (GROQ_FALLBACK_MODEL, False)]
    seen, last = set(), None
    for model, effort in tries:
        if (model, effort) in seen:
            continue
        seen.add((model, effort))
        try:
            data = _post(
                "https://api.groq.com/openai/v1/chat/completions",
                {"Authorization": f"Bearer {settings.groq_api_key}", "content-type": "application/json"},
                body(model, effort), timeout,
            )
        except AIError as exc:
            last = exc
            if exc.status in (400, 404, 422):
                log.warning("Groq rejected %s (effort=%s): %s", model, effort, exc)
                continue
            raise
        try:
            choice = data["choices"][0]
            if choice.get("finish_reason") == "length":
                raise AIError("The model response was cut off. Try again.")
            return (choice["message"].get("content") or "").strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise AIError("Unexpected response from Groq.") from exc
    raise last or AIError("Groq request failed.")


def complete_text(system: str, prompt: str, max_tokens: int = 900, timeout: float = 45) -> str:
    if not available():
        raise AIError("No AI provider is configured. Set GROQ_API_KEY.")
    text = _groq(system, prompt, max_tokens, timeout, json_mode=False)
    if not text:
        raise AIError("The model returned an empty response.")
    return text


def parse_json(text: str) -> dict:
    cleaned = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", text.strip(), flags=re.I)
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end < start:
        raise AIError("The model did not return JSON.")
    try:
        value = json.loads(cleaned[start:end + 1])
    except ValueError as exc:
        raise AIError("The model returned malformed JSON.") from exc
    if not isinstance(value, dict):
        raise AIError("The model JSON must be an object.")
    return value


def complete_json(system: str, prompt: str, max_tokens: int = 4000, timeout: float = 45) -> dict:
    if not available():
        raise AIError("No AI provider is configured. Set GROQ_API_KEY.")
    text = _groq(system + "\nReturn ONLY one valid JSON object. No markdown, no commentary.",
                 prompt, max_tokens, timeout, json_mode=True)
    return parse_json(text)
