"""Grounded, structured compliance evaluations for applicable assessment findings."""
import json
import logging
import re

import httpx
from sqlalchemy import select

from ..config import get_settings
from ..models import Chunk, Document, Finding, Regulation

log = logging.getLogger("reglens.assessment_ai")
settings = get_settings()
STATUSES = {"Compliant", "Partially Compliant", "Non-Compliant", "Unable to Determine"}
LEVELS = {"Low", "Medium", "High"}
GROQ_FALLBACK_MODEL = "openai/gpt-oss-120b"


def _json_object(text: str) -> dict:
    cleaned = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", text.strip(), flags=re.I)
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end < start:
        raise ValueError("Model returned no JSON object")
    value = json.loads(cleaned[start:end + 1])
    if not isinstance(value, dict):
        raise ValueError("Model JSON must be an object")
    return value


def _complete(system: str, prompt: str) -> str | None:
    if settings.anthropic_api_key:
        response = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": settings.anthropic_api_key, "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            json={"model": settings.anthropic_model, "max_tokens": 1200, "system": system,
                  "messages": [{"role": "user", "content": prompt}]}, timeout=45)
        response.raise_for_status()
        return "\n".join(block.get("text", "") for block in response.json().get("content", [])
                         if block.get("type") == "text")
    if settings.groq_api_key:
        def request(model: str):
            return httpx.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.groq_api_key}", "content-type": "application/json"},
                json={"model": model, "max_tokens": 1200, "response_format": {"type": "json_object"},
                      "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]},
                timeout=45)
        response = request(settings.groq_model)
        if response.status_code == 404 and settings.groq_model != GROQ_FALLBACK_MODEL:
            log.warning("Groq model %s returned 404; retrying with %s", settings.groq_model, GROQ_FALLBACK_MODEL)
            response = request(GROQ_FALLBACK_MODEL)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    return None


def evaluate_finding(db, finding: Finding, regulation: Regulation, company: dict, workspace_id: int) -> bool:
    """Evaluate one applicable regulation; return False if grounded AI output is unavailable."""
    if finding.applicability != "Applicable":
        return False
    chunks = db.scalars(select(Chunk).where(Chunk.source_type == "regulation", Chunk.source_id == regulation.id)
                        .order_by(Chunk.page, Chunk.id).limit(8)).all()
    if not chunks:
        return False
    evidence_docs = db.scalars(select(Document).where(
        Document.workspace_id == workspace_id, Document.use_in_ai.is_(True), Document.status == "ready"
    ).order_by(Document.id.desc()).limit(5)).all()
    doc_chunks = db.scalars(select(Chunk).where(Chunk.source_type == "document",
                                           Chunk.source_id.in_([doc.id for doc in evidence_docs]))
                            .order_by(Chunk.id).limit(10)).all() if evidence_docs else []
    source_text = "\n\n".join(f"[REGULATION p.{chunk.page or '?'}] {chunk.text[:1800]}" for chunk in chunks)
    evidence_text = "\n\n".join(f"[BUSINESS EVIDENCE: {chunk.title}, p.{chunk.page or '?'}] {chunk.text[:1000]}"
                                for chunk in doc_chunks)
    system = (
        "You are a cautious Indian regulatory compliance analyst. Evaluate only the supplied regulation, business profile, "
        "and business evidence. Return only a JSON object with keys summary, confidence, severity, likelihood, obligations. "
        "Each obligation has requirement, status (Compliant/Partially Compliant/Non-Compliant/Unable to Determine), evidence "
        "(short supporting quote or empty string), source (source label or empty), and reasoning. Include material obligations "
        "supported by the regulation passages. Never infer that an undocumented control exists. Use Unable to Determine when "
        "actual compliance cannot be established. Do not claim confirmed non-compliance from absent documents alone; that is "
        "Unable to Determine. A known unmet obligation may be Non-Compliant. Severity and likelihood must be Low, Medium, or High. "
        "Confidence is a number from 0 to 1. This is an estimate for review, not legal advice."
    )
    prompt = (f"Regulation: {regulation.title} ({regulation.regulator})\n"
              f"Business profile (JSON): {json.dumps(company, ensure_ascii=False, default=str)[:5000]}\n\n"
              f"Regulation passages:\n{source_text[:9000]}\n\n"
              f"Available enabled business evidence (may be empty):\n{evidence_text[:5000]}\n\n"
              "Use only obligations found in the supplied regulation passages.")
    try:
        raw = _complete(system, prompt)
        if not raw:
            return False
        result = _json_object(raw)
        obligations = result.get("obligations")
        if not isinstance(obligations, list) or not obligations:
            return False
        normalized = []
        for item in obligations[:20]:
            if not isinstance(item, dict) or not str(item.get("requirement", "")).strip():
                continue
            status = item.get("status") if item.get("status") in STATUSES else "Unable to Determine"
            evidence = str(item.get("evidence", ""))[:600]
            source = str(item.get("source", ""))[:200]
            business_source = any(token in source.casefold() for token in ("business evidence", "business profile", "profile"))
            if status in {"Compliant", "Partially Compliant", "Non-Compliant"} and (not evidence or not business_source):
                status = "Unable to Determine"
            normalized.append({"requirement": str(item["requirement"])[:500], "status": status,
                               "evidence": evidence, "source": source,
                               "reasoning": str(item.get("reasoning", ""))[:700]})
        if not normalized:
            return False
        statuses = [item["status"] for item in normalized]
        known = [status for status in statuses if status != "Unable to Determine"]
        if not known:
            overall = "Unable to Determine"
        elif "Non-Compliant" in known:
            overall = "Partially Compliant" if any(status in {"Compliant", "Partially Compliant"} for status in known) else "Non-Compliant"
        elif "Partially Compliant" in known:
            overall = "Partially Compliant"
        elif len(known) == len(statuses) and all(status == "Compliant" for status in statuses):
            overall = "Compliant"
        else:
            overall = "Unable to Determine"
        try:
            confidence = max(0.0, min(1.0, float(result.get("confidence"))))
        except (TypeError, ValueError):
            confidence = None
        finding.compliance_status = overall
        finding.severity = result.get("severity") if result.get("severity") in LEVELS else "Medium"
        finding.likelihood = result.get("likelihood") if result.get("likelihood") in LEVELS else "Medium"
        finding.ai_evaluated = True
        finding.ai_confidence = confidence
        finding.ai_summary = str(result.get("summary", ""))[:1500]
        finding.ai_findings = normalized
        return True
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        log.warning("AI assessment failed for regulation %s: %s", regulation.id, exc)
        return False
