"""Grounded answer generation. Uses Anthropic or Groq when configured, otherwise extraction."""
import logging
import re

import httpx

from ..config import get_settings
from .retrieval import Hit, tokenize

log = logging.getLogger("reglens.llm")
settings = get_settings()

SYSTEM = (
    "You are RegLens AI, a compliance research assistant for Indian businesses. Answer ONLY from the numbered "
    "source passages provided. Cite sources inline like [1] or [2]. If the passages do not contain the answer, say "
    "you could not find it in the available sources. Be concise, precise and never invent section numbers, dates "
    "or penalties. This is research support, not legal advice."
)
NOT_FOUND = ("I couldn't find an answer to that in your regulations or enabled Library documents. "
             "Try rephrasing, add the relevant regulation under Regulations, or enable a Library document for Ask.")


def _extractive(question: str, hits: list[Hit]) -> str:
    q = set(tokenize(question))
    picked: list[tuple[int, str]] = []
    for n, h in enumerate(hits[:3], start=1):
        sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", h.text) if len(s.strip()) > 30]
        for s in sorted(sents, key=lambda s: len(q & set(tokenize(s))), reverse=True)[:2]:
            if q & set(tokenize(s)):
                picked.append((n, s))
    if not picked:
        picked = [(1, hits[0].text[:400])]
    return "Here is what the sources say:\n\n" + "\n\n".join(f"{s} [{n}]" for n, s in picked[:4])


def answer(question: str, hits: list[Hit]) -> str:
    if not hits:
        return NOT_FOUND
    context = "\n\n".join(
        f"[{i}] {h.title}{f' (page {h.page})' if h.page else ''}\n{h.text}" for i, h in enumerate(hits, start=1))
    if settings.anthropic_api_key:
        try:
            r = httpx.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": settings.anthropic_api_key,
                         "anthropic-version": "2023-06-01",
                         "content-type": "application/json"},
                json={"model": settings.anthropic_model, "max_tokens": 900, "system": SYSTEM,
                      "messages": [{"role": "user", "content": f"Sources:\n{context}\n\nQuestion: {question}"}]},
                timeout=45,
            )
            r.raise_for_status()
            text = "".join(block.get("text", "") for block in r.json()["content"]
                           if block.get("type") == "text").strip()
            return text or _extractive(question, hits)
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            log.warning("Anthropic call failed, using extractive answer: %s", exc)
            return _extractive(question, hits)
    if not settings.groq_api_key:
        return _extractive(question, hits)
    try:
        r = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.groq_api_key}",
                     "content-type": "application/json"},
            json={"model": settings.groq_model, "max_tokens": 900,
                  "messages": [{"role": "system", "content": SYSTEM},
                               {"role": "user", "content": f"Sources:\n{context}\n\nQuestion: {question}"}]},
            timeout=45,
        )
        r.raise_for_status()
        text = r.json()["choices"][0]["message"]["content"].strip()
        return text or _extractive(question, hits)
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("LLM call failed, using extractive answer: %s", exc)
        return _extractive(question, hits)
