import io
from types import SimpleNamespace
from unittest.mock import patch


def test_auth_flow(client):
    r = client.post("/api/auth/signup", json={"name": "Asha Rao", "email": "asha@example.com", "password": "short"})
    assert r.status_code == 422 and "password" in r.json()["detail"]
    r = client.post("/api/auth/signup", json={"name": "Asha Rao", "email": "asha@example.com", "password": "longenough1"})
    assert r.status_code == 200 and r.json()["user"]["role"] == "user"
    assert client.post("/api/auth/signup", json={"name": "A", "email": "ASHA@example.com", "password": "longenough1"}).status_code == 409
    assert client.post("/api/auth/login", json={"email": "asha@example.com", "password": "nope"}).status_code == 401
    tok = client.post("/api/auth/login", json={"email": "asha@example.com", "password": "longenough1"}).json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    assert client.get("/api/auth/me", headers=h).json()["email"] == "asha@example.com"
    assert client.get("/api/auth/me").status_code == 401
    assert client.put("/api/auth/me", headers=h, json={"name": "Asha R"}).json()["name"] == "Asha R"
    assert client.post("/api/auth/password", headers=h, json={"current": "bad", "new": "anotherpass1"}).status_code == 400
    assert client.post("/api/auth/password", headers=h, json={"current": "longenough1", "new": "anotherpass1"}).status_code == 200
    assert client.get("/api/config").json() == {"google_client_id": None}


def test_auth_preflight(client):
    for path in ("/api/auth/signup", "/api/auth/login"):
        response = client.options(
            path,
            headers={
                "Origin": "https://reglens-ai-zeta.vercel.app",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "https://reglens-ai-zeta.vercel.app"
        assert "POST" in response.headers["access-control-allow-methods"]


def test_seed_regulations_and_ask(client, auth):
    h, _ = auth
    regs = client.get("/api/regulations", headers=h).json()
    assert len(regs) >= 5 and all(r["status"] == "ready" for r in regs)
    r = client.post("/api/ask", headers=h, json={"question": "What are the listing obligations for listed entities?"}).json()
    assert r["found"] and r["sources"] and "[1]" in r["answer"]
    assert "Listing Obligations" in r["sources"][0]["doc"]
    miss = client.post("/api/ask", headers=h, json={"question": "quantum cryptography lattice zebra"}).json()
    assert miss["found"] is False and miss["sources"] == []
    assert len(client.get("/api/ask/history", headers=h).json()) == 2
    scope = client.get("/api/ask/scope", headers=h).json()
    assert scope["regulations"] >= 5 and scope["library"] == 0


def test_ask_falls_back_when_qdrant_has_legacy_points(client, auth):
    h, _ = auth
    legacy_point = SimpleNamespace(payload={"source_type": "official_regulation"}, score=0.9)
    with patch("app.services.vector_store.enabled", return_value=True), \
         patch("app.services.vector_store.search", return_value=[legacy_point]):
        result = client.post("/api/ask", headers=h, json={
            "question": "What are the listing obligations for listed entities?"
        }).json()
    assert result["found"] is True
    assert "Listing Obligations" in result["sources"][0]["doc"]


def test_library_enable_in_ask_and_isolation(client, auth):
    h, _ = auth
    txt = b"Our internal travel policy requires all employees to book flights through the approved vendor Zephyrix before departure."
    d = client.post("/api/documents", headers=h, data={"kind": "Policy"}, files={"file": ("travel.txt", io.BytesIO(txt))}).json()
    assert d["status"] == "ready" and d["use_in_ai"] is False
    q = {"question": "Which vendor must employees use to book flights?"}
    assert client.post("/api/ask", headers=h, json=q).json()["found"] is False
    assert client.patch(f"/api/documents/{d['id']}", headers=h, json={"use_in_ai": True}).json()["use_in_ai"] is True
    ans = client.post("/api/ask", headers=h, json=q).json()
    assert ans["found"] and "Zephyrix" in ans["answer"]
    # another workspace must not see it
    other = client.post("/api/auth/signup", json={"name": "Other", "email": "o@example.com", "password": "longenough1"}).json()["token"]
    oh = {"Authorization": f"Bearer {other}"}
    assert client.get("/api/documents", headers=oh).json() == []
    assert client.get(f"/api/documents/{d['id']}/file", headers=oh).status_code == 404
    assert client.post("/api/ask", headers=oh, json=q).json()["found"] is False
    assert client.get(f"/api/documents/{d['id']}/file", headers=h).content == txt
    assert client.delete(f"/api/documents/{d['id']}", headers=h).status_code == 204
    assert client.post("/api/ask", headers=h, json=q).json()["found"] is False
    bad = client.post("/api/documents", headers=h, data={"kind": "Policy"}, files={"file": ("x.pdf", io.BytesIO(b"not a pdf"))})
    assert bad.status_code == 415


def test_regulation_upload_admin_and_delete(client, auth):
    h, _ = auth
    body = b"Payment aggregators must maintain a net worth of fifteen crore rupees at all times and settle merchants within T+1."
    r = client.post("/api/regulations", headers=h, data={"regulator": "RBI", "title": "PA Guidelines"}, files={"file": ("pa.txt", io.BytesIO(body))})
    assert r.status_code == 200 and r.json()["status"] == "ready" and r.json()["own"] is True
    assert client.post("/api/regulations", headers=h, data={"regulator": "Nope"}, files={"file": ("pa.txt", io.BytesIO(body))}).status_code == 422
    platform = next(x for x in client.get("/api/regulations", headers=h).json() if not x["own"])
    assert client.delete(f"/api/regulations/{platform['id']}", headers=h).status_code == 403
    assert client.delete(f"/api/regulations/{r.json()['id']}", headers=h).status_code == 204
    assert client.post("/api/regulations/from-url", headers=h, json={"url": "http://127.0.0.1:8000/x", "regulator": "RBI"}).status_code == 422


def test_only_designated_account_can_add_regulations(client):
    body = b"A regulation requires quarterly compliance reports from every covered entity."
    other = client.post("/api/auth/signup", json={"name": "Other", "email": "other-reg@example.com", "password": "longenough1"}).json()
    other_headers = {"Authorization": f"Bearer {other['token']}"}
    assert client.post("/api/regulations", headers=other_headers, data={"regulator": "RBI"},
                       files={"file": ("reg.txt", io.BytesIO(body))}).status_code == 403

    admin = client.post("/api/auth/signup", json={"name": "Zaira Hussain", "email": "zairahussain27@gmail.com", "password": "longenough1"}).json()
    admin_headers = {"Authorization": f"Bearer {admin['token']}"}
    assert admin["user"]["role"] == "admin"
    assert client.post("/api/regulations", headers=admin_headers, data={"regulator": "RBI"},
                       files={"file": ("reg.txt", io.BytesIO(body))}).status_code == 200


def test_filings(client, auth):
    h, _ = auth
    f = client.post("/api/filings", headers=h, data={"kind": "GST - GSTR-3B", "period": "Apr 2026", "due_on": "2020-05-20", "amount": "1200.50"},
                    files={"file": ("proof.pdf", io.BytesIO(b"%PDF-1.4 proof"))}).json()
    assert f["overdue"] is True and f["fy"] == "2020-21" and f["has_file"]
    lst = client.get("/api/filings", headers=h).json()
    assert lst["summary"]["overdue"] == 1 and lst["summary"]["pending"] == 1
    p = client.patch(f"/api/filings/{f['id']}", headers=h, json={"status": "Filed"}).json()
    assert p["status"] == "Filed" and p["paid_on"] and not p["overdue"]
    csv = client.get("/api/filings/export/csv?fy=2020-21", headers=h)
    assert "GSTR-3B" in csv.text and csv.headers["content-type"].startswith("text/csv")
    assert "GSTR-3B" not in client.get("/api/filings/export/csv?fy=1999-00", headers=h).text
    assert client.get(f"/api/filings/{f['id']}/file", headers=h).status_code == 200
    assert client.delete(f"/api/filings/{f['id']}", headers=h).status_code == 204


def test_company_assessment_risk_reports_alerts(client, auth):
    h, _ = auth
    dash = client.get("/api/dashboard", headers=h).json()
    assert dash["profile"]["completion_percent"] == 0 and dash["regulations"] >= 5 and dash["assessment"] is None
    bad = client.put("/api/company", headers=h, json={"pan": "123"})
    assert bad.status_code == 422
    ok = client.put("/api/company", headers=h, json={
        "legal_name": "Acme Pay", "country": "India", "entity_type": "Private Limited", "industry": "Fintech", "activity": "Digital lending",
        "state": "Karnataka", "turnover": "₹5 crore to ₹50 crore", "employees": "11 to 50", "operations_scope": "Pan-India",
        "customer_type": "Consumers (B2C)", "supply_type": "Services", "import_export": "No", "regulated_financial": "Yes",
        "listed_entity": "No", "data_handled": "Aadhaar, PAN", "pan": "abcde1234f", "established_year": "2019",
        "registrations": [{"registration_type": "GST", "required_status": "required", "status": "active"}]})
    assert ok.status_code == 200 and ok.json()["profile"]["complete"] and ok.json()["company"]["pan"] == "ABCDE1234F"
    a = client.post("/api/assessments", headers=h).json()
    by = {f["title"]: f for f in a["findings"]}
    assert by["RBI Guidelines on Digital Lending"]["applicability"] == "Applicable"
    assert by["SEBI Listing Obligations and Disclosure Requirements (LODR) Regulations, 2015"]["applicability"] == "Not Applicable"
    assert by["Digital Personal Data Protection Act, 2023"]["applicability"] == "Applicable"
    fid = by["RBI Guidelines on Digital Lending"]["id"]
    r = client.patch(f"/api/assessments/{a['id']}/findings/{fid}", headers=h,
                     json={"compliance_status": "Non-Compliant", "severity": "High", "likelihood": "High", "evidence_ids": [999]})
    assert r.status_code == 422
    r = client.patch(f"/api/assessments/{a['id']}/findings/{fid}", headers=h,
                     json={"compliance_status": "Non-Compliant", "severity": "High", "likelihood": "High"}).json()
    assert r["compliance_score"] == 0 and r["risk_score"] > 0
    done = client.post(f"/api/assessments/{a['id']}/complete", headers=h).json()
    assert done["status"] == "complete"
    assert client.patch(f"/api/assessments/{a['id']}/findings/{fid}", headers=h, json={"severity": "Low"}).status_code == 409
    risk = client.get("/api/risk", headers=h).json()
    assert any("Digital Lending" in x["title"] for x in risk["register"]) and risk["overall"] == "High"
    client.post("/api/assessments", headers=h)  # second assessment must not duplicate risks
    client.post(f"/api/assessments/{done['id'] + 1}/complete", headers=h)
    assert sum("Digital Lending" in x["title"] for x in client.get("/api/risk", headers=h).json()["register"]) == 1
    dash = client.get("/api/dashboard", headers=h).json()
    assert dash["assessment"] and dash["open"] >= 1
    rep = client.post("/api/reports", headers=h, json={"name": "Q3 summary", "kind": "Compliance summary"}).json()
    pdf = client.get(f"/api/reports/{rep['id']}/pdf", headers=h)
    assert pdf.content.startswith(b"%PDF") and pdf.headers["content-type"] == "application/pdf"
    for kind in ("Risk review", "Regulation updates"):
        rid = client.post("/api/reports", headers=h, json={"name": kind, "kind": kind}).json()["id"]
        assert client.get(f"/api/reports/{rid}/pdf", headers=h).content.startswith(b"%PDF")
    assert client.post("/api/reports", headers=h, json={"name": "x", "kind": "bogus"}).status_code == 422
    assert client.get("/api/alerts/unread-count", headers=h).json()["count"] >= 1  # assessment alert
    client.post("/api/alerts/read-all", headers=h)
    assert client.get("/api/alerts/unread-count", headers=h).json()["count"] == 0


def test_reminders_alerts_settings_risk_crud(client, auth):
    h, user = auth
    rem = client.post("/api/reminders", headers=h, json={"title": "File TDS", "due": "2020-01-10", "lead": 3}).json()
    alerts = client.get("/api/alerts", headers=h).json()
    assert any("File TDS" in a["title"] for a in alerts)
    assert len(client.get("/api/alerts", headers=h).json()) == len(alerts)  # idempotent
    assert client.patch(f"/api/reminders/{rem['id']}", headers=h, json={"done": True}).json()["done"] is True
    s = client.put("/api/settings", headers=h, json={"name": "Acme HQ", "regulators": ["RBI", "bogus"], "reminders": False, "changes": True, "weekly": True, "default_lead": 5}).json()
    assert s["regulators"] == ["RBI"] and s["name"] == "Acme HQ" and s["weekly"] is True
    assert client.get("/api/auth/me", headers=h).json()["workspace_name"] == "Acme HQ"
    r = client.post("/api/risk", headers=h, json={"title": "Consent log gaps", "area": "Consent", "level": "Low", "due": "2020-01-01"}).json()
    assert client.get("/api/risk", headers=h).json()["overdue"] == 1
    assert client.patch(f"/api/risk/{r['id']}", headers=h, json={"status": "Resolved"}).json()["status"] == "Resolved"
    assert client.patch(f"/api/risk/{r['id']}", headers=h, json={"level": "Extreme"}).status_code == 422
    assert client.delete(f"/api/risk/{r['id']}", headers=h).status_code == 204
    assert client.get("/api/does-not-exist", headers=h).status_code == 404
