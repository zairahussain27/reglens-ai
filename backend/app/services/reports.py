"""Point-in-time report snapshots and PDF rendering."""
import io
from datetime import date
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..models import Regulation, User
from ..utils import iso
from . import metrics

KINDS = ["Compliance summary", "Risk review", "Regulation updates"]
ORANGE = colors.HexColor("#ff5a1f")


def build_snapshot(db: Session, user: User, kind: str) -> dict:
    wid = user.workspace_id
    sections: list[dict] = []
    if kind == "Compliance summary":
        a = metrics.latest_assessment(db, wid)
        if not a:
            sections.append({"heading": "Assessment", "paragraphs": ["No assessment has been created yet."]})
        else:
            c = a.counts or {}
            sections.append({"heading": f"Assessment #{a.id} ({a.status})", "paragraphs": [
                f"Compliance score: {a.compliance_score if a.compliance_score is not None else 'n/a'}%   |   "
                f"Risk score: {a.risk_score if a.risk_score is not None else 'n/a'}%",
                f"Applicable: {c.get('applicable', 0)}, not applicable: {c.get('not_applicable', 0)}, "
                f"unknown: {c.get('unknown', 0)}, evidence gaps: {c.get('evidence_gaps', 0)}."]})
            sections.append({"heading": "Findings", "table": {
                "head": ["Regulation", "Applicability", "Compliance", "Severity", "Remediation"],
                "rows": [[f.title, f.applicability, f.compliance_status, f.severity, f.remediation_status] for f in a.findings]}})
    elif kind == "Risk review":
        s = metrics.risk_summary(db, wid)
        assessment = metrics.latest_assessment(db, wid)
        sections.append({"heading": "Summary", "paragraphs": [
            f"Overall level: {s['overall']}. Open: {s['open']}, overdue: {s['overdue']}, resolved: {s['resolved']}."]})
        if assessment:
            sections.append({"heading": f"Latest assessment #{assessment.id} ({assessment.status})", "paragraphs": [
                f"Risk score: {assessment.risk_score if assessment.risk_score is not None else 'n/a'}%.",
                f"Applicable regulations: {(assessment.counts or {}).get('applicable', 0)}; unknown applicability: {(assessment.counts or {}).get('unknown', 0)}.",
                "Complete the assessment to add applicable regulations to the risk register."]})
            sections.append({"heading": "Applicable assessment findings", "table": {
                "head": ["Regulation", "Compliance", "Severity", "Remediation"],
                "rows": [[f.title, f.compliance_status, f.severity, f.remediation_status]
                         for f in assessment.findings if f.applicability == "Applicable"]}})
        else:
            sections.append({"heading": "Assessment", "paragraphs": ["No assessment has been created yet."]})
        sections.append({"heading": "Risk register", "table": {
            "head": ["Risk", "Area", "Level", "Status", "Due"],
            "rows": [[r.title, r.area, r.level, r.status, iso(r.due) or "-"] for r in s["rows"]]}})
    else:
        regs = db.scalars(select(Regulation).where(or_(Regulation.workspace_id.is_(None), Regulation.workspace_id == wid))
                          .order_by(Regulation.issued_on.desc().nullslast(), Regulation.id.desc()).limit(25)).all()
        sections.append({"heading": "Latest regulations", "table": {
            "head": ["Regulation", "Regulator", "Issued", "Status"],
            "rows": [[r.title, r.regulator, iso(r.issued_on) or "-", r.status] for r in regs]}})
    return {"workspace": user.workspace.name, "kind": kind, "generated": date.today().isoformat(), "sections": sections}


def render_pdf(name: str, snap: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=18 * mm,
                            bottomMargin=18 * mm, title=name)
    base = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=base["Title"], textColor=ORANGE, alignment=0, fontSize=22)
    h2 = ParagraphStyle("h2", parent=base["Heading2"], textColor=colors.HexColor("#1a1a1a"))
    small = ParagraphStyle("small", parent=base["BodyText"], fontSize=8, leading=10)
    story = [Paragraph(escape(name), h1),
             Paragraph(escape(f"{snap.get('workspace', '')}  |  {snap.get('kind', '')}  |  Generated {snap.get('generated', '')}"), base["BodyText"]),
             Spacer(1, 10)]
    for sec in snap.get("sections", []):
        story.append(Paragraph(escape(sec["heading"]), h2))
        for p in sec.get("paragraphs", []):
            story += [Paragraph(escape(p), base["BodyText"]), Spacer(1, 4)]
        t = sec.get("table")
        if t:
            if not t["rows"]:
                story.append(Paragraph("No items.", base["BodyText"]))
                continue
            data = [[Paragraph(f"<b>{escape(h)}</b>", small) for h in t["head"]]] + \
                   [[Paragraph(escape(str(c)), small) for c in row] for row in t["rows"]]
            table = Table(data, repeatRows=1, colWidths=None)
            table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#ffede5")),
                                       ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#ece7e2")),
                                       ("VALIGN", (0, 0), (-1, -1), "TOP")]))
            story += [table, Spacer(1, 8)]
    story.append(Spacer(1, 12))
    story.append(Paragraph("Generated by RegLens AI. Research support only, not legal advice.", small))
    doc.build(story)
    return buf.getvalue()
