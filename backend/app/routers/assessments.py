from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout, as_completed

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..db import get_db
from ..deps import current_user
from ..models import Assessment, Document, Finding, Regulation, Risk, User
from ..services import ai_client, alerts, assessment_ai, metrics, scoring
from ..services.company import critical_missing, evaluate
from ..utils import iso, parse_date
from .regulations import visible

router = APIRouter(prefix="/assessments")
APPLIC = {"Applicable", "Not Applicable", "Unknown"}
COMPLIANCE = {"Unable to Determine", "Compliant", "Partially Compliant", "Non-Compliant"}
LEVEL = {"Low", "Medium", "High"}
REMEDIATION = {"Open", "In progress", "Resolved", "Verified"}
REG_AREA = {"MeitY": "Consent", "CBIC / GST": "Reporting", "SEBI": "Reporting"}
BATCH_WORKERS = 4
BATCH_DEADLINE_SECONDS = 55


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


def f_out(f: Finding, summary: dict | None = None) -> dict:
    gap, action = _assessment_guidance(f)
    risk = metrics.risk_finding(f)
    units = scoring.finding_units(f)
    known = [u for u in units if u["status"] in scoring.POINTS]
    items = [i for i in (f.ai_findings or []) if isinstance(i, dict)]
    score = (summary or {}).get("by_finding", {}).get(f.id, {}).get("score")
    if summary is None and known:
        score = round(sum(scoring.POINTS[u["status"]] * scoring.CRITICALITY_WEIGHT.get(u.get("criticality"), 2) for u in known)
                      / sum(scoring.CRITICALITY_WEIGHT.get(u.get("criticality"), 2) for u in known), 1)
    return {"id": f.id, "regulation_id": f.regulation_id, "title": f.title, "source_url": f.source_url,
            "applicability": f.applicability, "applicability_reason": f.applicability_reason,
            "compliance_status": f.compliance_status, "severity": f.severity, "likelihood": f.likelihood,
            "recommendation": f.recommendation, "ai_evaluated": f.ai_evaluated, "ai_confidence": f.ai_confidence,
            "ai_summary": f.ai_summary or "", "ai_findings": f.ai_findings or [],
            "score": score, "assessed_obligations": len(known), "total_obligations": len(units),
            "manual_override": bool(items and f.ai_evaluated and units and units[0].get("source") == "manual"),
            "compliance_gap": gap, "action_recommendation": action,
            "risk_contribution": risk["score"], "risk_reason": risk["reason"],
            "remediation_status": f.remediation_status, "due_on": iso(f.due_on), "evidence_ids": f.evidence_ids,
            "evidence_verified": f.evidence_verified, "missing_info": f.missing_info}


def a_out(a: Assessment, full: bool = False) -> dict:
    risk = metrics.risk_details(a.findings)
    summary = scoring.compliance_summary(a.findings)
    out = {"id": a.id, "created_at": iso(a.created_at), "status": a.status, "is_final": a.status == "complete",
           "compliance_score": summary["score"], "compliance_score_reason": summary["reason"],
           "compliance_estimated": summary["basis"] == "provisional",
           "coverage": summary["coverage"], "confidence": summary["confidence"], "score_basis": summary["basis"],
           "assessed_obligations": summary["assessed"], "total_obligations": summary["total"],
           "waiting_for_ai": summary["waiting"],
           "risk_score": risk["score"], "risk_level": risk["level"], "risk_formula": risk["formula"],
           "risk_reasons": risk["reasons"], "risk_contributors": risk["contributors"],
           "risk_estimated": risk["estimated"], "applicable_count": risk["applicable_count"],
           "unknown_applicability_count": risk["unknown_count"], "unassessed_count": risk["unassessed_count"],
           "counts": a.counts, "critical_missing": a.critical_missing, "ai": ai_client.status()}
    if full:
        out["findings"] = [f_out(f, summary) for f in a.findings]
        out["action_plan"] = scoring.action_plan(a.findings)
    return out


def _get(db: Session, user: User, aid: int) -> Assessment:
    a = db.scalars(select(Assessment).options(selectinload(Assessment.findings))
                   .where(Assessment.id == aid, Assessment.workspace_id == user.workspace_id)).first()
    if not a:
        raise HTTPException(404, "Assessment not found")
    return a


def _rescore(a: Assessment) -> None:
    summary = scoring.compliance_summary(a.findings)
    _, a.risk_score, a.counts = metrics.compute_scores(a.findings)
    a.compliance_score = summary["score"]
    a.compliance_score_reason = summary["reason"]
    a.meta = {"coverage": summary["coverage"], "confidence": summary["confidence"], "basis": summary["basis"],
              "assessed": summary["assessed"], "total": summary["total"], "waiting": summary["waiting"]}


def _sync_applicable_risk(db: Session, user: User, finding: Finding, assessment: Assessment) -> None:
    """Keep one risk-register entry per applicable regulation, regardless of assessment status."""
    if finding.applicability != "Applicable" or finding.remediation_status in {"Resolved", "Verified"}:
        return
    ref = f"finding:{finding.regulation_id}"
    reg = db.get(Regulation, finding.regulation_id) if finding.regulation_id else None
    area = REG_AREA.get(reg.regulator if reg else "", "Reporting")
    level = finding.severity if finding.severity in LEVEL else "Medium"
    existing = db.scalars(select(Risk).where(Risk.workspace_id == user.workspace_id, Risk.source_ref == ref)).first()
    if existing:
        existing.title, existing.area, existing.level = f"Compliance gap: {finding.title}", area, level
        existing.source, existing.due = f"Assessment #{assessment.id}", finding.due_on
        return
    db.add(Risk(workspace_id=user.workspace_id, title=f"Compliance gap: {finding.title}", area=area, level=level,
                source=f"Assessment #{assessment.id}", source_ref=ref, due=finding.due_on, owner_id=user.id))


def _regulation_for(db: Session, user: User, finding: Finding) -> Regulation | None:
    reg = db.get(Regulation, finding.regulation_id) if finding.regulation_id else None
    if reg and reg.workspace_id not in (None, user.workspace_id):
        return None
    return reg


@router.get("")
def list_assessments(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Assessment).options(selectinload(Assessment.findings))
                      .where(Assessment.workspace_id == user.workspace_id).order_by(Assessment.id.desc()))
    return [a_out(a) for a in rows]


@router.get("/ai-status")
def ai_status(check: bool = False, user: User = Depends(current_user)):
    """Is an AI provider configured? With ?check=true, also sends a tiny request to prove the key works."""
    info = ai_client.status()
    if check and info["available"]:
        try:
            ai_client.complete_text("Reply with the single word OK.", "ping", max_tokens=300, timeout=25)
            info["ok"] = True
        except ai_client.AIError as exc:
            info.update(ok=False, error=str(exc))
    return info


class AssessmentIn(BaseModel):
    regulation_ids: list[int]


@router.post("")
def start(body: AssessmentIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Create the assessment and decide applicability from the profile. AI evaluation runs per regulation afterwards."""
    company = metrics.get_company(db, user.workspace_id).data
    regs = visible(db, user.workspace_id, only_ready=True)
    if not regs:
        raise HTTPException(409, "Add at least one regulation before starting an assessment")
    selected_ids = set(body.regulation_ids)
    if not selected_ids:
        raise HTTPException(422, "Select at least one regulation")
    if selected_ids - {r.id for r in regs}:
        raise HTTPException(422, "Select only published regulations available in your workspace")
    a = Assessment(workspace_id=user.workspace_id, created_by=user.id, critical_missing=critical_missing(company))
    for r in (r for r in regs if r.id in selected_ids):
        verdict, reason, missing = evaluate(r.regulator, company)
        a.findings.append(Finding(
            regulation_id=r.id, title=r.title, source_url=r.source_url or "", applicability=verdict,
            applicability_reason=reason, missing_info=missing,
            recommendation="Review this regulation against your current practices and record evidence." if verdict == "Applicable" else ""))
    _rescore(a)
    db.add(a)
    db.flush()
    for finding in a.findings:
        _sync_applicable_risk(db, user, finding, a)
    db.commit()
    return a_out(_get(db, user, a.id), full=True)


@router.get("/{aid}")
def detail(aid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return a_out(_get(db, user, aid), full=True)


@router.post("/{aid}/findings/{fid}/evaluate")
def evaluate_one(aid: int, fid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """AI-evaluate a single regulation. The UI calls this once per regulation so progress is visible and no request is long."""
    a = _get(db, user, aid)
    if a.status == "complete":
        raise HTTPException(409, "This assessment is complete and read-only. Start a new assessment to re-evaluate.")
    f = next((x for x in a.findings if x.id == fid), None)
    if not f:
        raise HTTPException(404, "Finding not found")
    reg = _regulation_for(db, user, f)
    if not reg:
        raise HTTPException(404, "Regulation not found")
    if f.applicability == "Not Applicable":
        outcome = assessment_ai.Outcome(True)
    else:
        outcome = assessment_ai.evaluate_finding(db, f, reg, metrics.get_company(db, user.workspace_id).data, user.workspace_id)
    if outcome.ok:
        _rescore(a)
        _sync_applicable_risk(db, user, f, a)
        db.commit()
    else:
        db.rollback()
    a = _get(db, user, aid)
    summary = scoring.compliance_summary(a.findings)
    target = next(x for x in a.findings if x.id == fid)
    return {"ok": outcome.ok, "error": outcome.error, "finding": f_out(target, summary), "assessment": a_out(a)}


@router.post("/{aid}/rescore")
def rescore(aid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    a = _get(db, user, aid)
    _rescore(a)
    for f in a.findings:
        _sync_applicable_risk(db, user, f, a)
    db.commit()
    return a_out(_get(db, user, aid), full=True)


@router.post("/{aid}/evaluate")
def evaluate_existing(aid: int, force: bool = False, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Evaluate every pending regulation in parallel (API/scripting use; the UI uses the per-regulation endpoint)."""
    a = _get(db, user, aid)
    if a.status == "complete":
        raise HTTPException(409, "This assessment is complete and read-only.")
    company = metrics.get_company(db, user.workspace_id).data
    errors: list[str] = []
    jobs: list[tuple[Finding, assessment_ai.Job]] = []
    for f in a.findings:
        reg = _regulation_for(db, user, f)
        if f.applicability == "Not Applicable" or not reg or (f.ai_evaluated and not force):
            continue
        job = assessment_ai.prepare(db, f, reg, company, user.workspace_id)
        if isinstance(job, assessment_ai.Outcome):
            errors.append(f"{f.title}: {job.error}")
        else:
            jobs.append((f, job))
    evaluated = 0
    if jobs:
        pool = ThreadPoolExecutor(max_workers=min(BATCH_WORKERS, len(jobs)))
        futures = {pool.submit(job.call): (f, job) for f, job in jobs}
        try:
            for fut in as_completed(futures, timeout=BATCH_DEADLINE_SECONDS):
                f, job = futures[fut]
                try:
                    outcome = assessment_ai.apply(f, job, fut.result())
                except ai_client.AIError as exc:
                    outcome = assessment_ai.Outcome(False, str(exc))
                if outcome.ok:
                    evaluated += 1
                else:
                    errors.append(f"{f.title}: {outcome.error}")
        except FutureTimeout:
            errors.append("Some regulations timed out. Run the evaluation again to finish them.")
        finally:
            pool.shutdown(wait=False, cancel_futures=True)
    _rescore(a)
    for f in a.findings:
        if f.ai_evaluated:
            _sync_applicable_risk(db, user, f, a)
    db.commit()
    result = a_out(_get(db, user, aid), full=True)
    result["ai_evaluated_now"], result["ai_errors"] = evaluated, errors
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