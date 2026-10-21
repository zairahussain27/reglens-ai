import os
import tempfile
from pathlib import Path

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["UPLOAD_DIR"] = f"{_tmp}/uploads"
os.environ["ANTHROPIC_API_KEY"] = ""

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.config import get_settings  # noqa: E402

# Tests must never inherit credentials from the developer's .env or write to a
# real Qdrant collection. Use the SQL retrieval path and omit Google sign-in.
_settings = get_settings()
_settings.qdrant_url = None
_settings.qdrant_api_key = None
_settings.google_client_id = None
_settings.seed_dir = Path(_tmp) / "seed"
_settings.seed_dir.mkdir(parents=True, exist_ok=True)
_seed_texts = {
    "01_listing.txt": "Title: SEBI Listing Obligations and Disclosure Requirements (LODR) Regulations, 2015\nRegulator: SEBI\n\nListed entities must publish annual financial results and promptly disclose material events to the stock exchange.",
    "02_lending.txt": "Title: RBI Guidelines on Digital Lending\nRegulator: RBI\n\nDigital lending service providers must disclose loan terms and provide borrowers with a copy of the loan agreement.",
    "03_privacy.txt": "Title: Digital Personal Data Protection Act, 2023\nRegulator: MeitY\n\nA data fiduciary must provide notice and obtain consent before processing personal data, subject to applicable law.",
    "04_gst.txt": "Title: GST Rules\nRegulator: CBIC / GST\n\nA registered person must maintain records of purchases, supplies, input tax credit, and tax payable.",
    "05_msme.txt": "Title: MSME Development Act\nRegulator: Other\n\nBuyers must pay micro and small enterprises within the period prescribed by law.",
    "06_insider.txt": "Title: Prohibition of Insider Trading Regulations\nRegulator: SEBI\n\nDesignated persons must follow the trading window and maintain required disclosures.",
}
for _name, _content in _seed_texts.items():
    (_settings.seed_dir / _name).write_text(_content, encoding="utf-8")


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:  # runs lifespan => tables + seed regulations
        yield c


@pytest.fixture()
def auth(client):
    import uuid
    email = f"{uuid.uuid4().hex[:8]}@example.com"
    r = client.post("/api/auth/signup", json={"name": "Test User", "email": email, "password": "Passw0rd!x"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}, r.json()["user"]
