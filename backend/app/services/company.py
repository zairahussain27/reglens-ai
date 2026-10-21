"""Business-profile schema, completeness and rule-based regulation applicability."""
import re

OPTIONS = {
    "countries": ["India", "United States", "United Kingdom", "Singapore", "United Arab Emirates", "Other"],
    "entity_types": ["Private Limited", "Public Limited", "LLP", "Partnership", "Sole Proprietorship",
                     "One Person Company", "Section 8 Company", "Other"],
    "states": ["Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa", "Gujarat", "Haryana",
               "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur",
               "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu",
               "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal", "Andaman and Nicobar Islands",
               "Chandigarh", "Dadra and Nagar Haveli and Daman and Diu", "Delhi", "Jammu and Kashmir", "Ladakh",
               "Lakshadweep", "Puducherry"],
    "turnover": ["Up to ₹40 lakh", "₹40 lakh to ₹1.5 crore", "₹1.5 crore to ₹5 crore", "₹5 crore to ₹50 crore",
                 "₹50 crore to ₹250 crore", "Above ₹250 crore"],
    "employees": ["1 to 10", "11 to 50", "51 to 200", "201 to 1000", "Above 1000"],
    "operations_scopes": ["Single state", "Multiple states", "Pan-India", "India and overseas"],
    "customer_types": ["Consumers (B2C)", "Businesses (B2B)", "Both B2B and B2C", "Government"],
    "supply_types": ["Goods", "Services", "Both goods and services"],
    "yes_no_unknown": ["Yes", "No", "Unknown"],
    "registration_types": ["GST", "Shops and Establishment", "Udyam (MSME)", "RBI (NBFC / PA / PPI)",
                           "SEBI registration", "IRDAI registration", "FIU-IND", "Other"],
}

LIST_FIELDS = ["business_types", "licences", "data_handled", "securities_activities", "other_activities"]
TEXT_FIELDS = ["legal_name", "country", "entity_type", "industry", "activity", "description", "state", "turnover",
               "employees", "operations_scope", "customer_type", "supply_type", "import_export",
               "import_export_details", "regulated_financial", "financial_activity_details", "listed_entity",
               "securities_activity_details", "gstin", "pan"]
INT_FIELDS = ["established_year", "branches"]
REQUIRED = {
    "legal_name": "Legal name", "country": "Country", "entity_type": "Entity type", "industry": "Industry",
    "activity": "Main business activity", "state": "State", "turnover": "Annual turnover", "employees": "Employees",
    "operations_scope": "Operations", "customer_type": "Customers", "supply_type": "Supplies",
    "import_export": "Import or export", "regulated_financial": "Regulated financial activity",
    "listed_entity": "Listed entity",
}
CRITICAL = ["regulated_financial", "listed_entity", "industry", "activity", "supply_type"]
PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
GSTIN_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
REG_STATUS = {"unknown", "not_applied", "pending", "active", "rejected", "expired", "not_applicable"}
REG_REQUIRED = {"unknown", "required", "not_required"}


def profile_status(data: dict, dismissed: bool = False) -> dict:
    missing = [label for key, label in REQUIRED.items() if not data.get(key)]
    pct = round(100 * (len(REQUIRED) - len(missing)) / len(REQUIRED))
    return {"complete": not missing, "dismissed": dismissed, "completion_percent": pct, "missing": missing}


def critical_missing(data: dict) -> list[str]:
    return [REQUIRED.get(k, k) for k in CRITICAL if not data.get(k)]


def _blob(d: dict) -> str:
    parts = [d.get(k) or "" for k in ("industry", "activity", "description", "financial_activity_details",
                                      "securities_activity_details")]
    for k in LIST_FIELDS:
        parts.extend(d.get(k) or [])
    return " ".join(str(p) for p in parts).lower()


def _has_active_reg(d: dict, needle: str) -> bool:
    return any(needle in (r.get("registration_type") or "").lower() and r.get("status") == "active"
               for r in d.get("registrations") or [])


def evaluate(regulator: str, d: dict) -> tuple[str, str, list[dict]]:
    """Return (applicability, reason, missing_info) for a regulator against the business profile."""
    reg, blob = (regulator or "").lower().strip(), _blob(d)
    fin, listed = d.get("regulated_financial"), d.get("listed_entity")
    ask = lambda q: [{"question": q}]  # noqa: E731

    if reg == "rbi":
        if fin == "Yes" or _has_active_reg(d, "rbi"):
            return "Applicable", "You told us you carry out RBI-regulated financial activity.", []
        if fin == "No":
            return "Not Applicable", "You told us you do not carry out regulated financial activity.", []
        return "Unknown", "Applicability depends on regulated financial activity.", ask("Do you carry out regulated financial activity (lending, payments, deposits)?")
    if reg == "sebi":
        if listed == "Yes" or d.get("securities_activities") or _has_active_reg(d, "sebi"):
            return "Applicable", "You are a listed entity or carry out securities-market activity.", []
        if listed == "No":
            return "Not Applicable", "You are not listed and report no securities activity.", []
        return "Unknown", "Applicability depends on listing / securities activity.", ask("Is your entity listed on a stock exchange?")
    if reg == "irdai":
        if "insur" in blob or _has_active_reg(d, "irdai"):
            return "Applicable", "Your profile mentions insurance activity.", []
        if d.get("industry") or d.get("activity"):
            return "Not Applicable", "No insurance activity in your profile.", []
        return "Unknown", "We need your industry and activity.", ask("What is your industry and main business activity?")
    if reg == "npci":
        if re.search(r"payment|upi|wallet|fintech|bharat ?bill|settlement", blob):
            return "Applicable", "Your profile mentions payments activity.", []
        if fin == "No":
            return "Not Applicable", "No regulated financial or payments activity.", []
        return "Unknown", "Applies to payment-system participants.", ask("Do you operate or participate in a payment system (UPI, cards, wallets)?")
    if reg == "meity":
        if d.get("data_handled"):
            return "Applicable", "You handle digital personal data (" + ", ".join(d["data_handled"][:3]) + ").", []
        return "Unknown", "Applies when digital personal data is processed.", ask("What personal data do you collect or process?")
    if reg in {"cbic / gst", "cbic", "gst"}:
        if d.get("gstin") or _has_active_reg(d, "gst"):
            return "Applicable", "You hold a GSTIN / active GST registration.", []
        if d.get("supply_type"):
            return "Unknown", "You supply goods or services; applicability depends on GST registration and turnover.", ask("Are you registered under GST (GSTIN)?")
        return "Unknown", "We need your supply type and GST status.", ask("Do you supply goods or services, and are you GST-registered?")
    return "Unknown", "Applicability must be reviewed manually.", ask("Does this regulation apply to your business activities?")
