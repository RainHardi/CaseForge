"""Client sign-off: what the client is asked, answers, confirmations, fixes, anonymity, the no-login page."""

import pytest

from caseforge import review
from caseforge import signoff as so
from caseforge import verify as vf

from .test_verify import approve_via_api, approved_record
from .test_web import client, make_project, web  # noqa: F401  (fixture)

NOTES = ("Acme Clinics booked appointments by phone. We built Acme Clinics a booking portal in React. "
         "Bookings per day went from 40 to 65 after launch. The clinic manager said \"we stopped losing patients\". "
         "The team ran weekly demos.")


def all_confirm(req, **over):
    return {it["id"]: over.get(it["id"], {"action": "confirm"}) for it in req["items"]}


def test_client_is_asked_about_numbers_quotes_and_mentions_only():
    rec = approved_record(NOTES)
    req = so.request(rec, "Dana")
    asked = {it["text"] for it in req["items"]}
    assert asked and all(so.needs_client(rec, it["text"], it["section"]) for it in req["items"])
    assert any("40" in t or "65" in t for t in asked)
    skipped = [c for c in rec.active_claims() if c.text not in asked]
    assert all(not any(ch.isdigit() for ch in c.text) and "Acme" not in c.text and c.section != "results" for c in skipped)
    assert req["hash"] == rec.approved_hash and req["contact"] == "Dana"


def test_answers_are_validated():
    rec = approved_record(NOTES)
    req = so.request(rec)
    first = req["items"][0]["id"]
    with pytest.raises(so.SignoffError, match="name"):
        so.submit(req, all_confirm(req), "named", "")
    with pytest.raises(so.SignoffError, match="published"):
        so.submit(req, all_confirm(req), "", "Dana")
    with pytest.raises(so.SignoffError, match="every item"):
        so.submit(req, {}, "named", "Dana")
    with pytest.raises(so.SignoffError, match="should say"):
        so.submit(req, all_confirm(req, **{first: {"action": "fix", "text": req["items"][0]["text"]}}), "named", "Dana")


def test_confirmations_keep_the_approval_and_fixes_need_a_new_one():
    rec = approved_record(NOTES)
    req = so.request(rec)
    ids = [it["id"] for it in req["items"]]
    fix_id = next(it["id"] for it in req["items"] if "65" in it["text"])
    rm_id = next(i for i in ids if i != fix_id)
    fixed = rec.claim(fix_id).text.replace("65", "70")
    req = so.submit(req, all_confirm(req, **{fix_id: {"action": "fix", "text": fixed}, rm_id: {"action": "remove"}}),
                    "anonymous", "Dana Lee")
    marked = so.apply_answers(rec, req)
    assert marked == len(ids) - 2 and review.can_export(rec)  # confirming changes no text
    assert rec.client_signoff["decision"] == "anonymous" and rec.client_signoff["by"] == "Dana Lee"

    with pytest.raises(vf.VerifyError, match="anonymous"):
        vf.snapshot(rec, show_client=True)
    view = vf.public_view(vf.snapshot(rec, show_client=False), rec.content_hash())
    assert view["n_confirmed"] == marked and view["signoff"]["by"] == "Dana Lee"

    so.use_suggestion(rec, req, fix_id, None, "Rain")
    c = rec.claim(fix_id)
    assert c.text == fixed and c.client_confirmed and not c.blocking  # the client's correction is now a source
    assert any("Correction confirmed by the client" in a for a in rec.input.reviewer_additions)
    assert not review.can_export(rec)  # the text changed: approve again
    so.use_suggestion(rec, req, rm_id, None, "Rain")
    assert rec.claim(rm_id).deleted

    review.edit_claim(rec, fix_id, "Bookings per day went up after launch.", None, "Rain")
    assert not rec.claim(fix_id).client_confirmed  # the client confirmed other words


def test_client_page_flow(web):  # noqa: F811
    c, _ = client(web)
    pid, rec = make_project(c, NOTES)
    assert c.post(f"/api/projects/{pid}/signoff", json={}).status_code == 400  # approve first
    approve_via_api(c, pid, rec)
    links = c.post(f"/api/projects/{pid}/signoff", json={"contact": "Dana"}).json()
    token, items = links[0]["token"], links[0]["items"]
    assert links[0]["state"] == "open" and links[0]["url"].endswith("/s/" + token)

    anon = type(c)(web.app)
    page = anon.get(f"/s/{token}")
    assert page.status_code == 200 and "Please confirm" in page.text and items[0]["text"] in page.text
    bad = anon.post(f"/s/{token}", json={"answers": {}, "decision": "named", "signed_by": "Dana"})
    assert bad.status_code == 400
    answers = {it["id"]: {"action": "confirm"} for it in items}
    answers[items[-1]["id"]] = {"action": "remove"}
    ok = anon.post(f"/s/{token}", json={"answers": answers, "decision": "named", "signed_by": "Dana Lee"})
    assert ok.status_code == 200, ok.text
    assert "Thank you" in anon.get(f"/s/{token}").text
    assert anon.post(f"/s/{token}", json={"answers": answers, "decision": "named", "signed_by": "X"}).status_code == 409

    got = c.get(f"/api/projects/{pid}/signoffs").json()[0]
    assert got["state"] == "answered" and got["signed_by"] == "Dana Lee"
    rec = c.get(f"/api/projects/{pid}").json()
    assert rec["can_export"] and sum(1 for cl in rec["claims"] if cl["client_confirmed"]) == len(items) - 1

    # the Verified link now says what the client confirmed
    vtok = c.post(f"/api/projects/{pid}/publish", json={}).json()[0]["token"]
    assert "Confirmed by the client" in anon.get(f"/v/{vtok}").text

    other, _ = client(web, name="Bo", email="b@other.dev")
    assert other.post(f"/api/projects/{pid}/signoffs/{token}/use/{items[-1]['id']}").status_code == 404
    rec = c.post(f"/api/projects/{pid}/signoffs/{token}/use/{items[-1]['id']}").json()
    assert not rec["can_export"]  # removing a sentence needs a new approval
    assert c.get(f"/api/projects/{pid}/signoffs").json()[0]["items"][-1]["applied"]

    # a link sent before an edit can't be answered any more
    approve_via_api(c, pid, rec)
    t2 = c.post(f"/api/projects/{pid}/signoff", json={}).json()[0]["token"]
    first = next(cl for cl in rec["claims"] if not cl["deleted"])
    c.post(f"/api/projects/{pid}/claims/{first['id']}/edit", json={"text": first["text"] + " Also."})
    assert "has changed" in anon.get(f"/s/{t2}").text
    assert c.delete(f"/api/projects/{pid}/signoffs/{t2}").status_code == 200
    assert anon.get(f"/s/{t2}").status_code == 404
