from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..db import get_db
from ..deps import current_user
from ..models import Assessment, Document, Finding, Risk, User
from ..services import alerts, assessment_ai, metrics
from ..services.company import critical_missing, evaluate
from ..utils import iso, parse_date
from .regulations import visible

router = APIRouter(prefix="/assessments")
APPLIC = {"Applicable", "Not Applicable", "Unknown"}
COMPLIANCE = {"Unable to Determine", "Compliant", "Partially Compliant", "Non-Compliant"}
LEVEL = {"Low", "Medium", "High"}
REMEDIATION = {"Open", "In progress", "Resolved", "Verified"}
REG_AREA = {"MeitY": "Consent", "CBIC / GST": "Reporting", "SEBI": "Reporting"}


def _assessment_guidance(f: Finding) -> tuple[str, str]:
    if f.applicability == "Not Applicable":
        return ("No compliance gap identified from the current business profile.",
                "No immediate action is indicated. Review this result if your business activities or profile change.")
    if f.applicability == "Unknown":
        missing = ", ".join(x.get("question", "") for x in (f.missing_info or []) if x.get("question"))
        gap = "Applicability cannot be confirmed with the current business information."
        action = f"Complete the missing profile information ({missing}) and start a new assessment." if missing else \
            "Confirm the relevant business activities in your profile and start a new assessment."
        return gap, action
    if f.compliance_status == "Non-Compliant":
        return ("A compliance gap has been recorded for this applicable regulation.",
                "Create a corrective action for each unmet obligation, assign an owner and due date, and retain evidence of remediation.")
    if f.compliance_status == "Partially Compliant":
        return ("Some obligations may not be fully met.",
                "Identify the unmet obligations, assign an owner and due date for each, and retain evidence as controls are completed.")
    if f.compliance_status == "Compliant":
        if not f.evidence_ids or not f.evidence_verified:
            return ("Marked compliant, but supporting evidence is missing or has not been verified.",
                    "Attach current policy or operating evidence and have the evidence reviewed.")
        return ("No compliance gap is recorded; supporting evidence has been verified.",
                "Keep the control and evidence current, and review again when the regulation or business changes.")
    return ("Compliance has not yet been confirmed against the regulation's obligations.",
            "Review the regulation's obligations against current policies and records, then document unmet requirements and supporting evidence.")


def f_out(f: Finding) -> dict:
    gap, action = _assessment_guidance(f)
    risk = metrics.risk_finding(f)
    return {"id": f.id, "title": f.title, "source_url": f.source_url, "applicability": f.applicability,
            "applicability_reason": f.applicability_reason, "compliance_status": f.compliance_status,
            "severity": f.severity, "likelihood": f.likelihood, "recommendation": f.recommendation,
            "ai_evaluated": f.ai_evaluated, "ai_confidence": f.ai_confidence,
            "ai_summary": f.ai_summary or "", "ai_findings": f.ai_findings or [],
            "compliance_gap": gap, "action_recommendation": action,
            "risk_contribution": risk["score"], "risk_reason": risk["reason"],
            "remediation_status": f.remediation_status, "due_on": iso(f.due_on), "evidence_ids": f.evidence_ids,
            "evidence_verified": f.evidence_verified, "missing_info": f.missing_info}


def a_out(a: Assessment, full: bool = False) -> dict:
    risk = metrics.risk_details(a.findings)
    out = {"id": a.id, "created_at": iso(a.created_at), "status": a.status, "compliance_score": a.compliance_score,
           "risk_score": risk["score"], "risk_level": risk["level"], "risk_formula": risk["formula"],
           "risk_reasons": risk["reasons"], "risk_contributors": risk["contributors"],
           "risk_estimated": risk["estimated"], "applicable_count": risk["applicable_count"],
           "unknown_applicability_count": risk["unknown_count"], "unassessed_count": risk["unassessed_count"],
           "counts": a.counts, "critical_missing": a.critical_missing}
    if full:
        out["findings"] = [f_out(f) for f in a.findings]
    return out


def _get(db: Session, user: User, aid: int) -> Assessment:
    a = db.scalars(select(Assessment).options(selectinload(Assessment.findings))
                   .where(Assessment.id == aid, Assessment.workspace_id == user.workspace_id)).first()
    if not a:
        raise HTTPException(404, "Assessment not found")
    return a


def _rescore(a: Assessment) -> None:
    a.compliance_score, a.risk_score, a.counts = metrics.compute_scores(a.findings)


def _sync_applicable_risk(db: Session, user: User, finding: Finding, assessment: Assessment) -> None:
    """Keep one risk-register entry per applicable regulation, regardless of assessment status."""
    if finding.applicability != "Applicable" or finding.remediation_status in {"Resolved", "Verified"}:
        return
    ref = f"finding:{finding.regulation_id}"
    existing = db.scalars(select(Risk).where(
        Risk.workspace_id == user.workspace_id, Risk.source_ref == ref
    )).first()
    if existing:
        existing.title = f"Compliance gap: {finding.title}"
        existing.area = REG_AREA.get(
            next((reg.regulator for reg in visible(db, user.workspace_id) if reg.id == finding.regulation_id), ""),
            "Reporting")
        existing.level = finding.severity if finding.severity in LEVEL else "Medium"
        existing.source = f"Assessment #{assessment.id}"
        existing.due = finding.due_on
        return
    from ..models import Regulation
    reg = db.get(Regulation, finding.regulation_id) if finding.regulation_id else None
    db.add(Risk(workspace_id=user.workspace_id, title=f"Compliance gap: {finding.title}",
                area=REG_AREA.get(reg.regulator if reg else "", "Reporting"),
                level=finding.severity if finding.severity in LEVEL else "Medium",
                source=f"Assessment #{assessment.id}", source_ref=ref, due=finding.due_on, owner_id=user.id))


@router.get("")
def list_assessments(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Assessment).options(selectinload(Assessment.findings))
                      .where(Assessment.workspace_id == user.workspace_id).order_by(Assessment.id.desc()))
    return [a_out(a) for a in rows]


class AssessmentIn(BaseModel):
    regulation_ids: list[int]


@router.post("")
def start(body: AssessmentIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    company = metrics.get_company(db, user.workspace_id).data
    regs = visible(db, user.workspace_id, only_ready=True)
    if not regs:
        raise HTTPException(409, "Add at least one regulation before starting an assessment")
    selected_ids = set(body.regulation_ids)
    if not selected_ids:
        raise HTTPException(422, "Select at least one regulation")
    regs_by_id = {r.id: r for r in regs}
    if selected_ids - regs_by_id.keys():
        raise HTTPException(422, "Select only published regulations available in your workspace")
    regs = [r for r in regs if r.id in selected_ids]
    a = Assessment(workspace_id=user.workspace_id, created_by=user.id, critical_missing=critical_missing(company))
    for r in regs:
        verdict, reason, missing = evaluate(r.regulator, company)
        finding = Finding(regulation_id=r.id, title=r.title, source_url=r.source_url or "", applicability=verdict,
                          applicability_reason=reason, missing_info=missing,
                          recommendation="Review this regulation against your current practices and record evidence." if verdict == "Applicable" else "")
        a.findings.append(finding)
        if verdict == "Applicable":
            assessment_ai.evaluate_finding(db, finding, r, company, user.workspace_id)
    _rescore(a)
    db.add(a)
    db.flush()
    for finding in a.findings:
        if finding.applicability == "Applicable":
            _sync_applicable_risk(db, user, finding, a)
    db.commit()
    return a_out(_get(db, user, a.id), full=True)


@router.get("/{aid}")
def detail(aid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return a_out(_get(db, user, aid), full=True)


@router.post("/{aid}/evaluate")
def evaluate_existing(aid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Run missing grounded AI evaluations without overwriting existing AI or manual findings."""
    a = _get(db, user, aid)
    regs = {reg.id: reg for reg in visible(db, user.workspace_id)}
    evaluated = 0
    for finding in a.findings:
        regulation = regs.get(finding.regulation_id)
        if finding.applicability == "Applicable" and not finding.ai_evaluated and regulation:
            evaluated += int(assessment_ai.evaluate_finding(db, finding, regulation,
                                                              metrics.get_company(db, user.workspace_id).data,
                                                              user.workspace_id))
    _rescore(a)
    for finding in a.findings:
        if finding.ai_evaluated:
            _sync_applicable_risk(db, user, finding, a)
    db.commit()
    result = a_out(_get(db, user, aid), full=True)
    result["ai_evaluated_now"] = evaluated
    return result


class FindingPatch(BaseModel):
    applicability: str | None = None
    applicability_reason: str | None = None
    compliance_status: str | None = None
    severity: str | None = None
    likelihood: str | None = None
    recommendation: str | None = None
    remediation_status: str | None = None
    due_on: str | None = None
    evidence_ids: list[int] | None = None
    evidence_verified: bool | None = None


def _enum(value, allowed, label):
    if value is not None and value not in allowed:
        raise HTTPException(422, f"Invalid {label}")


@router.patch("/{aid}/findings/{fid}")
def patch_finding(aid: int, fid: int, body: FindingPatch, user: User = Depends(current_user), db: Session = Depends(get_db)):
    a = _get(db, user, aid)
    if a.status == "complete":
        raise HTTPException(409, "This assessment is complete and read-only. Start a new assessment to make changes.")
    f = next((x for x in a.findings if x.id == fid), None)
    if not f:
        raise HTTPException(404, "Finding not found")
    d = body.model_dump(exclude_unset=True)
    _enum(d.get("applicability"), APPLIC, "applicability")
    _enum(d.get("compliance_status"), COMPLIANCE, "compliance status")
    _enum(d.get("severity"), LEVEL, "severity")
    _enum(d.get("likelihood"), LEVEL, "likelihood")
    _enum(d.get("remediation_status"), REMEDIATION, "remediation status")
    if "evidence_ids" in d:
        ids = sorted(set(d["evidence_ids"]))
        found = {x for x in ids if (doc := db.get(Document, x)) and doc.workspace_id == user.workspace_id}
        if found != set(ids):
            raise HTTPException(422, f"Evidence document(s) not found in your Library: {', '.join(map(str, sorted(set(ids) - found)))}")
        if set(ids) != set(f.evidence_ids or []):
            f.evidence_verified = False  # new evidence must be re-reviewed
        f.evidence_ids = ids
    if "due_on" in d:
        f.due_on = parse_date(d["due_on"])
    if "evidence_verified" in d and user.email.lower() == "zairahussain27@gmail.com":
        f.evidence_verified = bool(d["evidence_verified"]) and bool(f.evidence_ids)
    for k in ("applicability", "applicability_reason", "compliance_status", "severity", "likelihood", "recommendation", "remediation_status"):
        if k in d and d[k] is not None:
            setattr(f, k, d[k].strip() if isinstance(d[k], str) else d[k])
    if f.applicability != "Applicable":
        f.missing_info = f.missing_info if f.applicability == "Unknown" else []
    _rescore(a)
    if f.applicability == "Applicable":
        _sync_applicable_risk(db, user, f, a)
    db.commit()
    return a_out(_get(db, user, aid), full=True)


@router.post("/{aid}/complete")
def complete(aid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    a = _get(db, user, aid)
    if a.status != "complete":
        _rescore(a)
        a.status = "complete"
        for f in a.findings:
            _sync_applicable_risk(db, user, f, a)
        alerts.push(db, user.workspace_id, f"Assessment #{a.id} completed",
                    f"Compliance {a.compliance_score if a.compliance_score is not None else 'n/a'}% · Risk {a.risk_score if a.risk_score is not None else 'n/a'}%",
                    f"assess:{a.id}")
        db.commit()
    return a_out(_get(db, user, aid), full=True)
