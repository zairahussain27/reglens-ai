from types import SimpleNamespace

from app.services import assessment_ai, scoring


def obligation(status, refs=("P1",), criticality="Medium"):
    return {
        "requirement": "A requirement",
        "status": status,
        "criticality": criticality,
        "evidence_refs": list(refs),
        "evidence_quote": "",
        "citation": "REG1",
        "reasoning": "",
        "action": "Review the control",
        "confidence": 0.8,
    }


def test_ungrounded_status_is_downgraded():
    result = assessment_ai.normalize_obligations(
        [obligation("Compliant", refs=()), obligation("Non-Compliant", refs=("NOPE",)),
         obligation("Compliant", refs=("p1",))],
        {"P1": "Industry: Fintech"},
        {"REG1"},
    )

    assert [item["status"] for item in result] == [
        "Unable to Determine", "Unable to Determine", "Compliant"
    ]
    assert result[2]["evidence_refs"] == ["P1"]


def test_fabricated_quote_is_removed():
    result = assessment_ai.normalize_obligations(
        [obligation("Compliant", refs=("P1",)) | {"evidence_quote": "not in evidence"}],
        {"P1": "Industry: Fintech"},
        {"REG1"},
    )

    assert result[0]["evidence"] == ""
    assert result[0]["confidence"] < 0.8


def test_weighted_score_excludes_unknown_obligations():
    items = [
        obligation("Compliant", criticality="High"),
        obligation("Non-Compliant", criticality="Low"),
        obligation("Unable to Determine"),
    ]
    finding = SimpleNamespace(
        id=1,
        title="Regulation",
        applicability="Applicable",
        ai_evaluated=True,
        ai_findings=items,
        compliance_status=scoring.overall_status(items),
        recommendation="",
    )

    summary = scoring.compliance_summary([finding])

    assert summary["score"] == 75.0
    assert summary["coverage"] == 0.67
    assert summary["assessed"] == 2
    assert finding.compliance_status == "Partially Compliant"
