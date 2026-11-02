"""Grounded answer generation for Ask. Uses the configured AI provider, otherwise falls back to extraction."""
import logging
import re

from . import ai_client
from .retrieval import Hit, tokenize

log = logging.getLogger("reglens.llm")

SYSTEM = (
    "You are RegLens AI, a compliance research assistant for Indian businesses. Answer ONLY from the numbered "
    "source passages provided. Cite sources inline like [1] or [2]. If the passages do not contain the answer, say "
    "you could not find it in the available sources. Be concise, precise and never invent section numbers, dates "
    "or penalties. If a business profile is given, tailor the answer to it, but say so when applicability depends on "
    "facts you do not have. This is research support, not legal advice."
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


def answer(question: str, hits: list[Hit], profile: str = "") -> str:
    if not hits:
        return NOT_FOUND
    if not ai_client.available():
        return _extractive(question, hits)
    context = "\n\n".join(
        f"[{i}] {h.title}{f' (page {h.page})' if h.page else ''}\n{h.text}" for i, h in enumerate(hits, start=1))
    business = f"Business profile: {profile}\n\n" if profile else ""
    try:
        return ai_client.complete_text(SYSTEM, f"{business}Sources:\n{context}\n\nQuestion: {question}", max_tokens=1500)
    except ai_client.AIError as exc:
        log.warning("LLM call failed, using extractive answer: %s", exc)
        return _extractive(question, hits)