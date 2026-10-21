"""Shared calculations used by dashboard, risk, assessments and reports."""
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Assessment, Company, Risk

LEVEL_W = {"Low": 1, "Medium": 2, "High": 3}
COMPLIANCE_PTS = {"Compliant": 100, "Partially Compliant": 50, "Non-Compliant": 0}
COMPLIANCE_GAP_WEIGHT = {"Non-Compliant": 1.0, "Partially Compliant": 0.5, "Unable to Determine": 0.5, "Compliant": 0.0}
EVIDENCE_GAP_WEIGHT = 0.25
UNKNOWN_APPLICABILITY_WEIGHT = 0.5
RISK_FORMULA = (
    "Per regulation: 100 × (severity ÷ 3) × (likelihood ÷ 3) × the highest applicable gap weight. "
    "Gap weights: non-compliant 1.0, partially compliant or unassessed 0.5, unverified compliant evidence 0.25. "
    "Unknown applicability uses 0.5; not-applicable findings are excluded; resolved findings score 0. "
    "The assessment score is the mean of applicable and potentially applicable findings. "
    "Risk levels: Low 0–29, Medium 30–69, High 70–100."
)


def get_company(db: Session, workspace_id: int) -> Company:
    c = db.get(Company, workspace_id)
    if not c:
        c = Company(workspace_id=workspace_id, data={})
        db.add(c)
        db.flush()
    return c


def latest_assessment(db: Session, workspace_id: int) -> Assessment | None:
    return db.scalars(select(Assessment).where(Assessment.workspace_id == workspace_id)
                      .order_by(Assessment.id.desc()).limit(1)).first()


def compute_scores(findings) -> tuple[float | None, int | None, dict]:
    applicable = [f for f in findings if f.applicability == "Applicable"]
    points: list[int] = []
    for finding in applicable:
        structured = finding.ai_findings or []
        if finding.ai_evaluated and structured:
            points.extend(COMPLIANCE_PTS[item["status"]] for item in structured
                          if isinstance(item, dict) and item.get("status") in COMPLIANCE_PTS)
        elif finding.compliance_status in COMPLIANCE_PTS:
            points.append(COMPLIANCE_PTS[finding.compliance_status])
    compliance = round(sum(points) / len(points), 1) if points else None
    risk = risk_details(findings)["score"]
    counts = {
        "applicable": len(applicable),
        "not_applicable": sum(f.applicability == "Not Applicable" for f in findings),
        "unknown": sum(f.applicability == "Unknown" for f in findings),
        "compliant": sum(f.compliance_status == "Compliant" for f in applicable),
        "non_compliant": sum(f.compliance_status == "Non-Compliant" for f in applicable),
        # "Compliant" claimed without evidence, or evidence not yet verified by an admin
        "evidence_gaps": sum(f.compliance_status == "Compliant" and (not f.evidence_ids or not f.evidence_verified) for f in applicable),
    }
    return compliance, risk, counts


def risk_finding(f) -> dict:
    applicability = f.applicability or "Unknown"
    compliance_status = f.compliance_status or "Unable to Determine"
    severity_label = f.severity if f.severity in LEVEL_W else "Medium"
    likelihood_label = f.likelihood if f.likelihood in LEVEL_W else "Medium"
    remediation_status = f.remediation_status or "Open"
    if applicability == "Not Applicable":
        return {"score": 0, "reason": "Excluded because the regulation is not applicable to the current business profile."}

    severity = LEVEL_W[severity_label]
    likelihood = LEVEL_W[likelihood_label]
    gap_weight = COMPLIANCE_GAP_WEIGHT.get(compliance_status, 0.5)
    evidence_gap = applicability == "Applicable" and compliance_status == "Compliant" and (
        not (f.evidence_ids or []) or not f.evidence_verified)
    evidence_weight = EVIDENCE_GAP_WEIGHT if evidence_gap else 0.0
    applicability_weight = UNKNOWN_APPLICABILITY_WEIGHT if applicability == "Unknown" else 0.0
    effective_weight = max(gap_weight, evidence_weight, applicability_weight)
    score = round(100 * (severity / 3) * (likelihood / 3) * effective_weight)
    if remediation_status in {"Resolved", "Verified"}:
        score = 0

    reasons = [f"Severity {severity_label.lower()} ({severity}/3)", f"likelihood {likelihood_label.lower()} ({likelihood}/3)"]
    reasons.append(f"{compliance_status.lower()} compliance status ({gap_weight:.2f} compliance-gap weight)")
    if evidence_gap:
        reasons.append(f"missing or unverified evidence ({evidence_weight:.2f} evidence-gap weight)")
    if applicability == "Unknown":
        reasons.append(f"applicability is unknown ({applicability_weight:.2f} potential-gap weight)")
    reasons.append(f"effective gap weight {effective_weight:.2f}")
    if score == 0 and remediation_status in {"Resolved", "Verified"}:
        reasons.append("remediation is resolved or verified")
    return {"score": score, "reason": "; ".join(reasons) + f"; contribution {score}/100."}


def risk_details(findings) -> dict:
    candidates = [f for f in findings if (f.applicability or "Unknown") in {"Applicable", "Unknown"}]
    if not candidates:
        return {"score": None, "level": "Not scored", "formula": RISK_FORMULA,
                "reasons": ["No applicable or potentially applicable regulations were selected."],
                "contributors": [], "estimated": False, "applicable_count": 0, "unknown_count": 0,
                "unassessed_count": 0}
    details = [(f, risk_finding(f)) for f in candidates]
    score = round(sum(item["score"] for _, item in details) / len(details))
    level = "Low" if score < 30 else "Medium" if score < 70 else "High"
    reasons = [f"{f.title}: {detail['reason']}" for f, detail in details]
    applicable_count = sum((f.applicability or "Unknown") == "Applicable" for f in candidates)
    unknown_count = sum((f.applicability or "Unknown") == "Unknown" for f in candidates)
    unassessed_count = sum(
        (f.compliance_status or "Unable to Determine") == "Unable to Determine"
        or any(item.get("status") == "Unable to Determine" for item in (f.ai_findings or []) if isinstance(item, dict))
        for f, _ in details)
    contributors = [{"title": f.title, "applicability": f.applicability or "Unknown",
                     "compliance_status": f.compliance_status or "Unable to Determine",
                     "severity": f.severity if f.severity in LEVEL_W else "Medium",
                     "likelihood": f.likelihood if f.likelihood in LEVEL_W else "Medium",
                     "score": detail["score"], "reason": detail["reason"]}
                    for f, detail in details]
    return {"score": score, "level": level, "formula": RISK_FORMULA, "reasons": reasons,
            "contributors": contributors, "estimated": bool(unknown_count or unassessed_count),
            "applicable_count": applicable_count, "unknown_count": unknown_count,
            "unassessed_count": unassessed_count}


def risk_summary(db: Session, workspace_id: int) -> dict:
    rows = db.scalars(select(Risk).where(Risk.workspace_id == workspace_id).order_by(Risk.id.desc())).all()
    today = date.today()
    open_ = [r for r in rows if r.status != "Resolved" and not r.ignored]
    by_area: dict[str, list[int]] = {}
    for r in open_:
        by_area.setdefault(r.area, []).append(LEVEL_W.get(r.level, 2))
    areas = [{"area": a, "score": round(100 * sum(w) / (3 * len(w)))} for a, w in sorted(by_area.items())]
    top = max((LEVEL_W.get(r.level, 2) for r in open_), default=0)
    return {
        "overall": {0: "None", 1: "Low", 2: "Medium", 3: "High"}[top],
        "open": len(open_),
        "overdue": sum(1 for r in open_ if r.due and r.due < today),
        "resolved": sum(1 for r in rows if r.status == "Resolved"),
        "ignored": sum(1 for r in rows if r.ignored),
        "by_area": areas,
        "rows": rows,
    }
