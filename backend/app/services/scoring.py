"""Compliance score, evidence coverage, confidence and remediation actions."""
POINTS = {"Compliant": 100, "Partially Compliant": 50, "Non-Compliant": 0}
CRITICALITY_WEIGHT = {"High": 3, "Medium": 2, "Low": 1}
URGENCY = {"Non-Compliant": 3, "Partially Compliant": 2, "Unable to Determine": 1}
DEFAULT_ACTION = {
    "Non-Compliant": "Close this gap: assign an owner and due date, implement the control and keep proof of it.",
    "Partially Compliant": "Complete the missing parts of this requirement and attach proof once done.",
    "Unable to Determine": "Provide evidence showing how you meet this requirement, enable it for AI in the Library, then re-run the AI evaluation.",
}


def _weighted(units: list[dict]) -> float:
    weights = [CRITICALITY_WEIGHT.get(unit.get("criticality"), 2) for unit in units]
    return sum(POINTS[unit["status"]] * weight for unit, weight in zip(units, weights)) / sum(weights)


def overall_status(items: list[dict]) -> str:
    known = [item for item in items if item.get("status") in POINTS]
    if not known:
        return "Unable to Determine"
    score = _weighted(known)
    if score >= 90 and len(known) / len(items) >= 0.8:
        return "Compliant"
    if score < 20:
        return "Non-Compliant"
    return "Partially Compliant"


def finding_units(finding) -> list[dict]:
    items = [item for item in (finding.ai_findings or []) if isinstance(item, dict) and item.get("requirement")]
    manual = {"requirement": "Manually confirmed status", "status": finding.compliance_status,
              "criticality": "Medium", "confidence": 1.0, "source": "manual"}
    if finding.ai_evaluated and items:
        return [manual] if finding.compliance_status != overall_status(items) else items
    return [manual] if finding.compliance_status in POINTS else []


def compliance_summary(findings) -> dict:
    applicable = [finding for finding in findings if finding.applicability == "Applicable"]
    by_finding, all_units = {}, []
    for finding in applicable:
        units = finding_units(finding)
        known = [unit for unit in units if unit["status"] in POINTS]
        by_finding[finding.id] = {"score": round(_weighted(known), 1) if known else None,
                                  "assessed": len(known), "total": len(units)}
        all_units += units
    assessed = [unit for unit in all_units if unit["status"] in POINTS]
    waiting = sum(1 for finding in applicable if not finding_units(finding) and not finding.ai_evaluated)
    score = round(_weighted(assessed), 1) if assessed else None
    coverage = round(len(assessed) / len(all_units), 2) if all_units else None
    confidences = [float(unit["confidence"]) for unit in assessed if isinstance(unit.get("confidence"), (int, float))]
    confidence = None
    if assessed:
        value = (sum(confidences) / len(confidences) if confidences else 0.6) * (0.5 + 0.5 * (coverage or 0))
        confidence = "High" if value >= 0.7 else "Medium" if value >= 0.45 else "Low"
    reason = None
    if score is None:
        reason = ("No applicable regulations in this assessment. Complete your Business Profile so applicability can be decided."
                  if not applicable else
                  f"{waiting} applicable regulation(s) are waiting for AI evaluation. Run the AI evaluation to calculate the score."
                  if waiting else "The AI could not verify any obligation. Add evidence and re-run the evaluation.")
    basis = None if score is None else ("provisional" if waiting or (coverage or 0) < 0.5 else "evidence-based")
    return {"score": score, "coverage": coverage, "confidence": confidence, "basis": basis, "reason": reason,
            "assessed": len(assessed), "total": len(all_units), "waiting": waiting, "by_finding": by_finding}


def action_plan(findings, limit: int = 15) -> list[dict]:
    plan = []
    for finding in findings:
        if finding.applicability != "Applicable":
            continue
        for unit in finding_units(finding):
            status = unit["status"]
            if status == "Compliant":
                continue
            rank = URGENCY.get(status, 1) * CRITICALITY_WEIGHT.get(unit.get("criticality"), 2)
            action = unit.get("action") or (finding.recommendation if unit.get("source") == "manual" else "") \
                or DEFAULT_ACTION.get(status, DEFAULT_ACTION["Unable to Determine"])
            plan.append({"finding_id": finding.id, "regulation": finding.title, "requirement": unit["requirement"],
                         "status": status, "criticality": unit.get("criticality", "Medium"),
                         "citation": unit.get("citation", ""), "action": action, "rank": rank,
                         "priority": "Critical" if rank >= 8 else "High" if rank >= 5 else "Medium" if rank >= 3 else "Low"})
    plan.sort(key=lambda item: (-item["rank"], item["regulation"]))
    return plan[:limit]
