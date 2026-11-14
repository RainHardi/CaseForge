"""Website API: accounts, workspace isolation, full flow, approval lock, formats, daily limit."""

import importlib

import pytest
from fastapi.testclient import TestClient

from .conftest import SAMPLE_FILES


@pytest.fixture
def web(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("DAILY_AI_LIMIT", "6")
    monkeypatch.setenv("CASEFORGE_LLM_MODE", "offline")
    import web.main as m
    m = importlib.reload(m)
    m._db = None
    return m


def client(m, name="Abdulaziz", email="a@team.dev", invite=""):
    c = TestClient(m.app)
    r = c.post("/api/signup", json={"name": name, "email": email, "password": "password123",
                                    "company": "Team 5", "invite_code": invite})
    assert r.status_code == 200, r.text
    return c, r.json()


def make_project(c, notes=None):
    notes = notes or SAMPLE_FILES[1].read_text()
    r = c.post("/api/projects", data={"title": "Noodle inventory", "notes": notes})
    assert r.status_code == 200, r.text
    pid = r.json()["id"]
    r = c.post(f"/api/projects/{pid}/generate")
    assert r.status_code == 200, r.text
    return pid, r.json()


def test_pages_and_login_required(web):
    c = TestClient(web.app)
    assert c.get("/").status_code == 200 and "CaseForge" in c.get("/").text
    assert c.get("/app").status_code == 200
    assert c.get("/api/projects").status_code == 401


def test_signup_login_and_bad_password(web):
    c, user = client(web)
    assert user["workspace_name"] == "Team 5"
    c2 = TestClient(web.app)
    assert c2.post("/api/login", json={"email": "a@team.dev", "password": "wrong-pass"}).status_code == 400
    assert c2.post("/api/login", json={"email": "A@team.dev", "password": "password123"}).status_code == 200
    assert c2.get("/api/me").json()["email"] == "a@team.dev"
    assert TestClient(web.app).post("/api/signup", json={"name": "x", "email": "a@team.dev",
                                                         "password": "password123"}).status_code == 400


def test_workspaces_are_isolated_and_invites_share(web):
    a, ua = client(web)
    pid, _ = make_project(a)
    b, _ = client(web, "Stranger", "b@other.dev")
    assert b.get("/api/projects").json() == []
    assert b.get(f"/api/projects/{pid}").status_code == 404
    assert b.post(f"/api/projects/{pid}/approve").status_code == 404
    t, _ = client(web, "Teammate", "t@team.dev", invite=ua["invite_code"])
    assert [p["id"] for p in t.get("/api/projects").json()] == [pid]


def test_full_flow_with_planted_claim(web):
    c, _ = client(web)
    pid, rec = make_project(c)
    assert rec["status"] == "drafted"
    assert c.get(f"/api/projects/{pid}/export/case-study").status_code == 400  # locked
    assert c.get(f"/api/projects/{pid}/export/case-study?draft=true").status_code == 200
    rec = c.post(f"/api/projects/{pid}/claims", json={"section": "results", "text": "Counting time fell by 40%."}).json()
    bad = [x for x in rec["claims"] if "40%" in x["text"]][0]
    assert bad["label"] == "unsupported"
    assert c.post(f"/api/projects/{pid}/approve").status_code == 400
    rec = c.post(f"/api/projects/{pid}/claims/{bad['id']}/delete").json()
    for g in rec["gaps"]:
        if g["blocking"] and not g["resolved"]:
            rec = c.post(f"/api/projects/{pid}/gaps/{g['id']}/resolve", json={"text": "left out"}).json()
    rec = c.post(f"/api/projects/{pid}/approve").json()
    assert rec["can_export"] and rec["approved_by"] == "Abdulaziz"
    for kind in ("case-study", "one-pager", "portfolio"):
        r = c.get(f"/api/projects/{pid}/export/{kind}")
        assert r.status_code == 200 and len(r.content) > 500


def test_formats_need_approval_and_are_checked(web):
    c, _ = client(web)
    pid, rec = make_project(c, SAMPLE_FILES[0].read_text())
    assert c.post(f"/api/projects/{pid}/formats/linkedin").status_code == 400  # not approved yet
    for g in rec["gaps"]:
        if g["blocking"]:
            c.post(f"/api/projects/{pid}/gaps/{g['id']}/resolve", json={"text": "ok"})
    c.post(f"/api/projects/{pid}/approve")
    rec = c.post(f"/api/projects/{pid}/formats/linkedin").json()
    out = rec["outputs"]["linkedin"]
    assert out["sentences"] and rec["formats"]["linkedin"]["ready"]
    assert c.get(f"/api/projects/{pid}/formats/linkedin/text").status_code == 200
    sid = out["sentences"][0]["id"]
    rec = c.post(f"/api/projects/{pid}/formats/linkedin/{sid}", json={"text": "We cut costs by 70% with Kubernetes."}).json()
    assert not rec["formats"]["linkedin"]["ready"]
    assert c.get(f"/api/projects/{pid}/formats/linkedin/text").status_code == 400


def test_daily_limit(web):
    c, _ = client(web)
    r = c.post("/api/projects", data={"notes": "- we built a dashboard, python + react"}).json()
    codes = [c.post(f"/api/projects/{r['id']}/generate").status_code for _ in range(7)]
    assert codes[:6] == [200] * 6 and codes[6] == 400
    assert c.get("/api/me").json()["quota_left"] == 0


def test_file_extract_preview(web):
    c, _ = client(web)
    r = c.post("/api/extract", files=[("files", ("notes.txt", b"We built a chatbot with Python.", "text/plain"))])
    assert r.json()[0]["text"] == "We built a chatbot with Python."


def test_brands_and_designed_report(web):
    c, _ = client(web)
    brands = c.get("/api/brands").json()
    assert any(b["id"] == "preset:northwind" for b in brands["brands"]) and "Manrope" in brands["fonts"]
    kit = c.post("/api/brands/import", data={"text": "Primary colour #123456. Headings in Inter.", "name": "Acme"}).json()
    bid = c.post("/api/brands", json={"kit": kit["kit"]}).json()["id"]
    png = (b"\x89PNG\r\n\x1a\n" + b"\0" * 32)
    assert c.post(f"/api/brands/{bid}/logo", files={"file": ("logo.png", png, "image/png")}).status_code == 200
    assert any(b["id"] == bid and b["logo"] for b in c.get("/api/brands").json()["brands"])

    pid, rec = make_project(c, SAMPLE_FILES[0].read_text())
    assert c.post(f"/api/projects/{pid}/report", json={"brand_id": bid}).status_code == 400  # needs approval
    for g in rec["gaps"]:
        if g["blocking"]:
            c.post(f"/api/projects/{pid}/gaps/{g['id']}/resolve", json={"text": "ok"})
    c.post(f"/api/projects/{pid}/approve")
    rec = c.post(f"/api/projects/{pid}/report", json={"brand_id": bid}).json()
    assert rec["report"]["elements"] and not rec["report_ready"]
    html = c.get(f"/api/projects/{pid}/report/preview")
    assert html.status_code == 200 and "DRAFT" in html.text
    assert c.get(f"/api/projects/{pid}/report/pdf").status_code == 400  # not approved
    r = c.post(f"/api/projects/{pid}/report/approve")
    assert r.status_code == 200, r.text
    assert r.json()["report_ready"]
    assert c.delete(f"/api/brands/{bid}").status_code == 200


def test_auto_brand_logo_brand_and_chat(web):
    import io
    from PIL import Image
    c, _ = client(web)
    brands = c.get("/api/brands").json()["brands"]
    assert brands[0]["id"] == "auto"
    buf = io.BytesIO(); Image.new("RGB", (60, 30), (230, 57, 70)).save(buf, "PNG")
    kit = c.post("/api/brands/from-logo", files={"file": ("logo.png", buf.getvalue(), "image/png")}, data={"name": "Acme"}).json()
    assert kit["kit"]["colors"]["primary"] == "#E63946" and kit["logo"]
    pid, rec = make_project(c, SAMPLE_FILES[0].read_text())
    for g in rec["gaps"]:
        if g["blocking"]:
            c.post(f"/api/projects/{pid}/gaps/{g['id']}/resolve", json={"text": "ok"})
    c.post(f"/api/projects/{pid}/approve")
    rec = c.post(f"/api/projects/{pid}/report", json={}).json()          # no brand chosen → auto
    # auto = the company's own look: the workspace has a logo, so its colours and logo are used
    assert rec["report"]["brand"]["colors"]["primary"] == "#E63946" and rec["report"]["brand"]["logo"]
    rec = c.post(f"/api/projects/{pid}/report/brand", json={"brand_id": "preset:northwind"}).json()
    assert rec["report"]["brand"]["name"] == "Northwind Digital Works"
    rec = c.post(f"/api/projects/{pid}/report/brand", json={"brand_id": kit["id"]}).json()
    assert rec["report"]["brand"]["colors"]["primary"] == "#E63946"
    rec = c.post(f"/api/projects/{pid}/report/chat", json={"text": "make it editorial"}).json()
    assert rec["report"]["layout"]["theme"] == "editorial" and rec["report"]["chat"][-1]["role"] == "ai"


def test_logo_uploaded_with_the_notes_sets_the_report_colours(web):
    """No brand kit, no clicks: a logo given with the notes is used on the report and gives it its colours."""
    import io
    from PIL import Image
    c, _ = client(web)
    buf = io.BytesIO(); Image.new("RGB", (60, 30), (20, 120, 200)).save(buf, "PNG")
    r = c.post("/api/projects", data={"notes": SAMPLE_FILES[1].read_text()},
               files={"logo": ("acme.png", buf.getvalue(), "image/png")})
    pid = r.json()["id"]
    assert r.json()["input"]["logo"].startswith("brandlogo-")
    rec = c.post(f"/api/projects/{pid}/generate").json()
    for g in rec["gaps"]:
        if g["blocking"]:
            c.post(f"/api/projects/{pid}/gaps/{g['id']}/resolve", json={"text": "ok"})
    c.post(f"/api/projects/{pid}/approve")
    rec = c.post(f"/api/projects/{pid}/report", json={}).json()
    brand = rec["report"]["brand"]
    assert brand["colors"]["primary"] == "#1478C8" and brand["logo"] == rec["input"]["logo"]
    assert "data:image/png;base64" in c.get(f"/api/projects/{pid}/report/preview").text    # the logo is on the page
    # a new logo later: the designed report follows at once
    buf = io.BytesIO(); Image.new("RGB", (60, 30), (200, 40, 40)).save(buf, "PNG")
    rec = c.post(f"/api/projects/{pid}/logo", files={"file": ("new.png", buf.getvalue(), "image/png")}).json()
    assert rec["report"]["brand"]["colors"]["primary"] == "#C82828"
    # redesign gives a different look, never the same one twice in a row
    before = (rec["report"]["layout"]["frame"], rec["report"]["layout"]["theme"])
    rec = c.post(f"/api/projects/{pid}/report", json={}).json()
    assert (rec["report"]["layout"]["frame"], rec["report"]["layout"]["theme"]) != before
    # prompting: a new fact goes into the notes under the reviewer's name; a different design on request
    rec = c.post(f"/api/projects/{pid}/report/chat", json={"text": "note: the factory has 40 warehouse staff"}).json()
    assert any("40 warehouse staff" in a for a in rec["input"]["reviewer_additions"])
    look = (rec["report"]["layout"]["frame"], rec["report"]["layout"]["theme"])
    rec = c.post(f"/api/projects/{pid}/report/chat", json={"text": "give me a different design"}).json()
    assert (rec["report"]["layout"]["frame"], rec["report"]["layout"]["theme"]) != look
