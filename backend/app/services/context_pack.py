"""Labelled business and document evidence used to ground AI conclusions."""
import re
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Chunk, Document, Filing
from . import retrieval

PROFILE_FIELDS = [
    ("entity_type", "Entity type"), ("industry", "Industry"), ("activity", "Main business activity"),
    ("description", "Business description"), ("country", "Country"), ("state", "State"),
    ("turnover", "Annual turnover"), ("employees", "Employees"), ("operations_scope", "Operations"),
    ("customer_type", "Customers"), ("supply_type", "Supplies"), ("import_export", "Import or export"),
    ("import_export_details", "Import/export details"), ("regulated_financial", "Regulated financial activity"),
    ("financial_activity_details", "Financial activity details"), ("listed_entity", "Listed entity"),
    ("securities_activity_details", "Securities activity details"),
]
PROFILE_LISTS = [
    ("business_types", "Business types"), ("licences", "Licences held"),
    ("data_handled", "Personal data handled"), ("securities_activities", "Securities activities"),
    ("other_activities", "Other activities"),
]


@dataclass
class Evidence:
    ref: str
    kind: str
    text: str
    label: str


def _as_list(value) -> list:
    if isinstance(value, str):
        return [v.strip() for v in value.split(",") if v.strip()]
    return list(value or [])


def _days(value: date) -> int:
    return (value - date.today()).days


def profile_evidence(data: dict) -> list[Evidence]:
    out = []

    def add(label: str, value: str) -> None:
        out.append(Evidence(f"P{len(out) + 1}", "profile", f"{label}: {value}", f"Business profile - {label}"))

    for key, label in PROFILE_FIELDS:
        value = str(data.get(key) or "").strip()
        if value:
            add(label, value[:400])
    for key, label in PROFILE_LISTS:
        values = _as_list(data.get(key))
        if values:
            add(label, ", ".join(map(str, values[:12])))
    for key, label in (("gstin", "GSTIN"), ("pan", "PAN")):
        add(label, "provided" if data.get(key) else "not provided")
    if data.get("established_year"):
        add("Year established", str(data["established_year"]))
    if data.get("branches") is not None:
        add("Branches", str(data["branches"]))
    return out


def registration_evidence(data: dict) -> list[Evidence]:
    out = []
    for registration in (data.get("registrations") or [])[:20]:
        parts = [f"{registration.get('registration_type')}: required={registration.get('required_status', 'unknown')}",
                 f"status={registration.get('status', 'unknown')}"]
        parts.append("number provided" if registration.get("number") else "no number recorded")
        parts.append("proof document linked" if registration.get("document_id") else "no proof document")
        expiry = registration.get("expiry_date")
        if expiry:
            try:
                days = _days(date.fromisoformat(expiry[:10]))
                parts.append(f"EXPIRED {-days} days ago" if days < 0 else f"expires in {days} days")
            except ValueError:
                pass
        out.append(Evidence(f"R{len(out) + 1}", "registration", ", ".join(parts),
                            f"Registration - {registration.get('registration_type')}"))
    return out


def filing_evidence(db: Session, workspace_id: int) -> list[Evidence]:
    rows = db.scalars(select(Filing).where(Filing.workspace_id == workspace_id)
                      .order_by(Filing.due_on.is_(None), Filing.due_on.desc(), Filing.id.desc()).limit(30)).all()
    out = []
    for filing in rows:
        bits = [f"{filing.kind} {filing.period or ''}".strip() + f": {filing.status}"]
        if filing.due_on:
            bits.append(f"due {filing.due_on.isoformat()}")
        if filing.status in {"Filed", "Paid"} and filing.paid_on and filing.due_on:
            late = (filing.paid_on - filing.due_on).days
            bits.append("filed on time" if late <= 0 else f"filed {late} days late")
        elif filing.status == "Pending" and filing.due_on and filing.due_on < date.today():
            bits.append(f"OVERDUE by {(date.today() - filing.due_on).days} days")
        bits.append("proof uploaded" if filing.file_path else "no proof uploaded")
        out.append(Evidence(f"F{len(out) + 1}", "filing", ", ".join(bits),
                            f"Filing - {filing.kind} {filing.period or ''}".strip()))
    return out


def business_evidence(db: Session, workspace_id: int, data: dict) -> list[Evidence]:
    return profile_evidence(data) + registration_evidence(data) + filing_evidence(db, workspace_id)


def profile_summary(data: dict) -> str:
    bits = [str(data.get(key)) for key in ("entity_type", "industry", "activity", "state", "turnover")
            if data.get(key)]
    if data.get("regulated_financial") == "Yes":
        bits.append("carries out regulated financial activity")
    if data.get("listed_entity") == "Yes":
        bits.append("listed entity")
    if data.get("data_handled"):
        bits.append("handles " + ", ".join(_as_list(data["data_handled"])[:4]))
    return "; ".join(bits)


OBLIGATION = re.compile(
    r"\b(shall|must|required?|requires?|obligat\w+|liable|penalt\w+|within|file|filing|disclos\w+|"
    r"maintain|submit|register\w*|consent|notice|report\w*|comply|prohibit\w*)\b", re.I)


def _index(chunks: list) -> retrieval.Index:
    index = retrieval.Index(chunks=list(chunks))
    for chunk in chunks:
        tokens = retrieval.tokenize(chunk.title + " " + chunk.text)
        frequencies = {}
        for token in tokens:
            frequencies[token] = frequencies.get(token, 0) + 1
        index.tfs.append(frequencies)
        index.lens.append(len(tokens) or 1)
        for token in frequencies:
            index.df[token] = index.df.get(token, 0) + 1
    index.avg_len = sum(index.lens) / len(index.lens) if index.lens else 1.0
    return index


def select_regulation_passages(chunks: list, profile_query: str, limit: int = 10) -> list:
    if len(chunks) <= limit:
        return sorted(chunks, key=lambda chunk: (chunk.page or 0, chunk.id))
    relevance = {hit.chunk_id: hit.score for hit in _index(chunks).search(profile_query, k=len(chunks))} if profile_query else {}
    top = max(relevance.values(), default=0) or 1
    selected = sorted(chunks, key=lambda chunk: min(len(OBLIGATION.findall(chunk.text)), 8) +
                      4 * relevance.get(chunk.id, 0) / top, reverse=True)[:limit]
    return sorted(selected, key=lambda chunk: (chunk.page or 0, chunk.id))


def document_evidence(db: Session, workspace_id: int, query: str, start: int = 1, k: int = 6) -> list[Evidence]:
    documents = select(Document.id).where(Document.workspace_id == workspace_id, Document.use_in_ai.is_(True),
                                           Document.status == "ready")
    chunks = db.scalars(select(Chunk).where(Chunk.source_type == "document", Chunk.source_id.in_(documents))
                        .limit(2000)).all()
    return [Evidence(f"D{start + index}", "document", f"[{hit.title} p.{hit.page or '?'}] {hit.text[:900]}",
                     f"Library - {hit.title}" + (f" p.{hit.page}" if hit.page else ""))
            for index, hit in enumerate(_index(chunks).search(query, k=k))] if chunks else []


def render(evidence: list[Evidence]) -> str:
    return "\n".join(f"[{item.ref}] {item.text}" for item in evidence) or "(no business evidence recorded)"
