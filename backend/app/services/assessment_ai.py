"""AI evaluation of one regulation against everything we know about the business.

Flow (kept in three steps so calls can run in parallel safely):
  prepare()  – reads the DB, builds the prompt           (main thread)
  Job.call() – the HTTP request to the model              (worker thread, no DB)
  apply()    – validates the answer and writes the finding (main thread)

Grounding rule enforced in code: a status of Compliant / Partially Compliant / Non-Compliant is only kept when it
cites at least one real evidence reference we supplied. Otherwise it becomes 'Unable to Determine' (needs evidence).
"""
import logging
import re
from dataclasses import dataclass, field

from sqlalchemy import select

from ..models import Chunk, Finding, Regulation
from . import ai_client, context_pack, scoring

log = logging.getLogger("reglens.assessment_ai")
STATUSES = {"Compliant", "Partially Compliant", "Non-Compliant", "Unable to Determine"}
LEVELS = {"Low", "Medium", "High"}
APPLICABILITY = {"Applicable", "Not Applicable", "Unknown"}
MAX_OBLIGATIONS = 12

SYSTEM = (
    "You are a careful Indian regulatory compliance analyst. You are given (1) passages of ONE regulation labelled REG1, REG2..., "
    "and (2) evidence about the business labelled P (profile), R (registration), F (filing record) and D (uploaded document).\n"
    "Task: identify the most material obligations in the REG passages that apply to this business and judge, for each, whether the "
    "business meets it using ONLY the labelled evidence.\n"
    "Rules:\n"
    "- Status is one of: Compliant, Partially Compliant, Non-Compliant, Unable to Determine.\n"
    "- Compliant / Partially Compliant / Non-Compliant require evidence_refs listing the labels you relied on (for example "
    "[\"R1\",\"F2\"]). Never invent a label. A filing record, active registration, expired registration, overdue filing or an "
    "explicit profile answer all count as evidence.\n"
    "- If no evidence speaks to the obligation, use Unable to Determine. Absence of a document is NOT proof of non-compliance.\n"
    "- evidence_quote is a short verbatim excerpt from the cited evidence (or empty).\n"
    "- criticality (High/Medium/Low) reflects penalty or business impact if unmet. citation is the REG label the obligation comes from.\n"
    "- action is one concrete next step for the business (max 25 words).\n"
    "- Give 4 to 10 obligations. Do not give legal advice; this is an estimate for review.\n"
    "JSON keys: applicability (Applicable|Not Applicable|Unknown), applicability_reason, summary (2 sentences, plain English), "
    "severity (Low|Medium|High), likelihood (Low|Medium|High), confidence (0 to 1), obligations: [{requirement, citation, "
    "criticality, status, evidence_refs, evidence_quote, reasoning (max 30 words), action, confidence (0 to 1)}]."
)


@dataclass
class Outcome:
    ok: bool
    error: str | None = None


@dataclass
class Job:
    prompt: str
    valid_refs: dict[str, str]  # evidence ref -> evidence text
    passage_refs: set[str]
    decide_applicability: bool
    result: dict = field(default_factory=dict)

    def call(self) -> dict:
        return ai_client.complete_json(SYSTEM, self.prompt, max_tokens=4500, timeout=50)


def _clamp(value, default: float | None = None) -> float | None:
    try:
        return round(max(0.0, min(1.0, float(value))), 2)
    except (TypeError, ValueError):
        return default


def _norm(text: str) -> str:
    return re.sub(r"\W+", " ", text.casefold()).strip()


def normalize_obligations(raw, valid_refs: dict[str, str], passage_refs: set[str]) -> list[dict]:
    """Validate AI obligations: drop junk, verify citations, downgrade ungrounded verdicts."""
    out: list[dict] = []
    for item in (raw if isinstance(raw, list) else [])[:MAX_OBLIGATIONS]:
        if not isinstance(item, dict) or not str(item.get("requirement", "")).strip():
            continue
        status = item.get("status") if item.get("status") in STATUSES else "Unable to Determine"
        refs_in = item.get("evidence_refs") or []
        refs_in = refs_in if isinstance(refs_in, list) else [refs_in]
        refs = [r for r in dict.fromkeys(str(x).strip().upper() for x in refs_in) if r in valid_refs]
        confidence = _clamp(item.get("confidence"), 0.5)
        reasoning = str(item.get("reasoning", ""))[:400]
        quote = str(item.get("evidence_quote", ""))[:400].strip()
        if quote and not any(_norm(quote) in _norm(valid_refs[r]) for r in refs):
            quote = ""  # not found in the cited evidence, so we do not show it
            confidence = max(0.0, (confidence or 0.5) - 0.2)
        downgraded = status != "Unable to Determine" and not refs
        if downgraded:
            status = "Unable to Determine"
            reasoning = (reasoning + " " if reasoning else "") + "No verifiable evidence was cited, so this could not be confirmed."
        citation = str(item.get("citation", "")).strip().upper()
        out.append({"requirement": str(item["requirement"]).strip()[:400], "status": status,
                    "criticality": item.get("criticality") if item.get("criticality") in LEVELS else "Medium",
                    "citation": citation if citation in passage_refs else "", "evidence_refs": refs,
                    "evidence": quote, "source": ", ".join(refs), "reasoning": reasoning.strip(),
                    "action": str(item.get("action", ""))[:300].strip(), "confidence": confidence,
                    "downgraded": downgraded})
    return out


def prepare(db, finding: Finding, regulation: Regulation, company: dict, workspace_id: int) -> Job | Outcome:
    if not ai_client.available():
        return Outcome(False, "No AI provider is configured. Add GROQ_API_KEY to the backend environment.")
    chunks = db.scalars(select(Chunk).where(Chunk.source_type == "regulation", Chunk.source_id == regulation.id)).all()
    if not chunks:
        return Outcome(False, "This regulation has no indexed text. Re-upload it or check its ingestion status.")
    profile_query = " ".join(str(company.get(k) or "") for k in ("industry", "activity", "description")) + " " + \
        " ".join(context_pack._as_list(company.get("data_handled"))) + " " + regulation.title
    passages = context_pack.select_regulation_passages(list(chunks), profile_query, limit=10)
    passage_refs = {f"REG{i + 1}" for i in range(len(passages))}
    reg_text = "\n\n".join(f"[REG{i + 1} p.{c.page or '?'}] {c.text[:1000]}" for i, c in enumerate(passages))
    evidence = context_pack.business_evidence(db, workspace_id, company)
    evidence += context_pack.document_evidence(
        db, workspace_id, regulation.title + " " + " ".join(c.text[:400] for c in passages[:3]), start=1)
    decide = finding.applicability == "Unknown"
    task = ("Also decide applicability (Applicable / Not Applicable / Unknown) from the business profile."
            if decide else "Applicability is already decided as Applicable; set applicability to Applicable.")
    prompt = (f"Regulation: {regulation.title} (regulator: {regulation.regulator})\n{task}\n\n"
              f"REGULATION PASSAGES\n{reg_text}\n\nBUSINESS EVIDENCE\n{context_pack.render(evidence)[:9000]}")
    return Job(prompt, {e.ref: e.text for e in evidence}, passage_refs, decide)


def apply(finding: Finding, job: Job, result: dict) -> Outcome:
    """Validate the model answer and write it to the finding. Nothing is written if the answer is unusable."""
    applicability = finding.applicability
    if job.decide_applicability:
        applicability = result.get("applicability") if result.get("applicability") in APPLICABILITY else "Unknown"
    obligations = []
    if applicability == "Applicable":
        obligations = normalize_obligations(result.get("obligations"), job.valid_refs, job.passage_refs)
        if not obligations:
            return Outcome(False, "The AI returned no usable obligations for this regulation. Try again.")
    if job.decide_applicability:
        finding.applicability = applicability
        finding.applicability_reason = str(result.get("applicability_reason", ""))[:1000] or finding.applicability_reason
    finding.ai_evaluated = True
    finding.ai_summary = str(result.get("summary", ""))[:1500]
    finding.ai_confidence = _clamp(result.get("confidence"))
    if applicability != "Applicable":
        finding.compliance_status, finding.ai_findings = "Unable to Determine", []
        finding.missing_info = ([{"question": "Provide more business profile information to confirm applicability."}]
                                if applicability == "Unknown" else [])
        return Outcome(True)
    finding.ai_findings = obligations
    finding.compliance_status = scoring.overall_status(obligations)
    finding.severity = result.get("severity") if result.get("severity") in LEVELS else "Medium"
    finding.likelihood = result.get("likelihood") if result.get("likelihood") in LEVELS else "Medium"
    gaps = [o for o in sorted(obligations, key=lambda o: -scoring.URGENCY.get(o["status"], 1))
            if o["status"] != "Compliant" and o["action"]]
    finding.recommendation = " ".join(o["action"] for o in gaps[:3]) or finding.recommendation
    if finding.ai_confidence is None:
        known = [o["confidence"] for o in obligations if o["confidence"] is not None]
        finding.ai_confidence = round(sum(known) / len(known), 2) if known else None
    return Outcome(True)


def evaluate_finding(db, finding: Finding, regulation: Regulation, company: dict, workspace_id: int) -> Outcome:
    job = prepare(db, finding, regulation, company, workspace_id)
    if isinstance(job, Outcome):
        return job
    try:
        return apply(finding, job, job.call())
    except ai_client.AIError as exc:
        log.warning("AI evaluation failed for regulation %s: %s", regulation.id, exc)
        return Outcome(False, str(exc))