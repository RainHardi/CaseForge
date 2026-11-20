"""Verified link: frozen approved copy, masking, fingerprint check, public page, revoke, QR in the report."""

import re

import pytest

from caseforge import review
from caseforge import verify as vf
from caseforge.models import ProjectInput, ProjectRecord
from caseforge.pipeline import generate

from .conftest import SAMPLE_FILES
from .test_web import client, make_project, web  # noqa: F401  (fixture)


def approved_record(notes=None, client_name="Acme Clinics") -> ProjectRecord:
    rec = ProjectRecord(id="p1", input=ProjectInput(title="Booking portal", client_name=client_name,
                                                    raw_notes=notes or SAMPLE_FILES[1].read_text()))
    generate(rec, None)
    for g in rec.gaps:
        if g.blocking and not g.resolved:
            review.resolve_gap(rec, g.id, "ok", "t")
    for c in list(rec.active_claims()):
        if c.blocking:
            review.delete_claim(rec, c.id, "t")
    review.approve(rec, "Rain")
    return rec


def test_mask_keeps_what_the_sentence_says_and_hides_the_rest():
    q = "Acme Clinics paid $48,000 and booking time fell from 9 minutes to 2 minutes, said Dana Lee (dana@acme.com)."
    out = vf.mask_quote(q, "Booking time fell from 9 minutes to 2 minutes.", client="Acme Clinics")
    assert "9 minutes to 2 minutes" in out and "booking time fell" in out
    for secret in ("Acme", "48,000", "Dana", "Lee", "dana@acme.com"):
        assert secret not in out, secret
    assert vf.MASK in out


def test_snapshot_needs_approval_and_matches_the_fingerprint():
    rec = approved_record()
    copy = vf.snapshot(rec)
    assert copy["hash"] == rec.approved_hash and vf.intact(copy)
    n = sum(len(s["sentences"]) for s in copy["sections"])
    assert n == len(rec.active_claims())
    with_quotes = [s for sec in copy["sections"] for s in sec["sentences"] if s["evidence"]]
    assert with_quotes and all(e["quote"] in rec.input.source_text() for s in with_quotes for e in s["evidence"])

    tampered = {**copy, "sections": [dict(sec) for sec in copy["sections"]]}
    first = tampered["sections"][0]
    first["sentences"] = [{**first["sentences"][0], "text": "We tripled revenue overnight."}] + first["sentences"][1:]
    assert not vf.intact(tampered)  # shown text no longer the approved text
    assert not vf.intact({**copy, "hash": "0" * 64})

    rec.claims[0].text += " Edited."  # any edit withdraws the approval
    with pytest.raises(vf.VerifyError):
        vf.snapshot(rec)


def test_labels_only_and_hidden_client_still_verify():
    rec = approved_record(notes="Acme Clinics booked by phone. We built Acme Clinics a booking portal in React. "
                                "Bookings per day went from 40 to 65 after launch.")
    copy = vf.snapshot(rec, evidence="labels", show_client=False)
    text = " ".join(s["text"] for sec in copy["sections"] for s in sec["sentences"])
    assert copy["client"] == "" and "Acme" not in text
    assert all(not s["evidence"] for sec in copy["sections"] for s in sec["sentences"])
    assert vf.intact(copy)
    view = vf.public_view(copy, live_hash=rec.content_hash())
    assert view["intact"] and not view["newer_version"] and "signed" not in view and "project_id" not in view
    assert vf.public_view(copy, live_hash="other")["newer_version"]


def approve_via_api(c, pid, rec):
    for g in rec["gaps"]:
        if g["blocking"]:
            c.post(f"/api/projects/{pid}/gaps/{g['id']}/resolve", json={"text": "ok"})
    for cl in rec["claims"]:
        if not cl["deleted"] and cl["label"] in ("unsupported", "contradicted", None):
            c.post(f"/api/projects/{pid}/claims/{cl['id']}/delete")
    r = c.post(f"/api/projects/{pid}/approve")
    assert r.status_code == 200, r.text
    return r.json()


def test_publish_public_page_revoke_and_qr(web):  # noqa: F811
    c, _ = client(web)
    pid, rec = make_project(c)
    assert c.post(f"/api/projects/{pid}/publish", json={}).status_code == 400  # not approved
    rec = approve_via_api(c, pid, rec)
    links = c.post(f"/api/projects/{pid}/publish", json={"evidence": "full"}).json()
    assert len(links) == 1 and links[0]["current"] and links[0]["url"].endswith("/v/" + links[0]["token"])
    token = links[0]["token"]

    anon = type(c)(web.app)  # a reader with no account
    page = anon.get(f"/v/{token}")
    assert page.status_code == 200 and "Verified case study" in page.text and "noindex" in page.text
    first = next(cl for cl in rec["claims"] if not cl["deleted"])
    assert f'data-id="{first["id"]}"' in page.text
    assert anon.post(f"/v/{token}/check").status_code == 204
    qr = anon.get(f"/v/{token}/qr.svg")
    assert qr.status_code == 200 and qr.text.lstrip().startswith("<svg")
    stats = c.get(f"/api/projects/{pid}/published").json()[0]
    assert stats["views"] == 1 and stats["checks"] == 1

    # someone in another workspace can't see or revoke it
    other, _ = client(web, name="Bo", email="b@other.dev")
    assert other.post(f"/api/projects/{pid}/published/{token}/revoke").status_code == 404

    # editing the project: the link keeps the approved version and says a newer one exists
    c.post(f"/api/projects/{pid}/claims/{first['id']}/edit", json={"text": first["text"] + " Also more."})
    page = anon.get(f"/v/{token}")
    assert "changed this case study since" in page.text and "Also more." not in page.text
    assert not c.get(f"/api/projects/{pid}/published").json()[0]["current"]

    links = c.post(f"/api/projects/{pid}/published/{token}/revoke").json()
    assert links[0]["revoked"]
    assert anon.get(f"/v/{token}").status_code == 404
    assert anon.get("/v/does-not-exist").status_code == 404


def test_report_preview_carries_the_qr_once_published(web):  # noqa: F811
    c, _ = client(web)
    pid, rec = make_project(c, SAMPLE_FILES[0].read_text())
    approve_via_api(c, pid, rec)
    assert c.post(f"/api/projects/{pid}/report", json={"brand_id": "auto"}).status_code == 200
    assert c.post(f"/api/projects/{pid}/report/approve").status_code == 200
    assert "Check any sentence yourself" not in c.get(f"/api/projects/{pid}/report/preview").text
    token = c.post(f"/api/projects/{pid}/publish", json={"evidence": "masked"}).json()[0]["token"]
    html = c.get(f"/api/projects/{pid}/report/preview").text
    assert "Check any sentence yourself" in html and f"/v/{token}" in html and re.search(r'class="vqr"><svg', html)
