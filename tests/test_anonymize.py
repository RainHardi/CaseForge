"""Anonymized version: suggestions, safe swaps, numbers untouched, report and Verified link, downloads."""

import re

import pytest

from caseforge import anonymize as an
from caseforge import report as rpt
from caseforge import verify as vf
from caseforge.brandkit import load
from caseforge.review import ReviewError, can_export

from .test_verify import approve_via_api, approved_record
from .test_web import client, make_project, web  # noqa: F401  (fixture)

NOTES = ("Bright Smile Dental lost about 18 appointment slots a week. We built Bright Smile Dental a no-show "
         "predictor in Python. Dana Lee, the practice manager, said reception now calls only 15 patients a day. "
         "Weekly no-shows fell from 18 to 11 in 8 weeks. Contact: dana@brightsmile.example.")
SWAPS = [["Bright Smile Dental", "a dental clinic"], ["Dana Lee", "the practice manager"], ["dana@brightsmile.example", "[email]"]]


def numbers(texts):
    return sorted(n for t in texts for n in re.findall(r"\d+", t))


def rec_with_swaps():
    rec = approved_record(NOTES, client_name="Bright Smile Dental")
    rec.input.title = "No-show prediction for a Dental Clinic"
    rec.approved_hash = rec.content_hash()  # title changed in the test: keep it approved
    rec.anon_map = SWAPS
    return rec


def test_suggestions_tick_the_client_and_leave_names_to_the_team():
    rec = approved_record(NOTES, client_name="Bright Smile Dental")
    rec.input.title = "No-show prediction for a Dental Clinic"
    got = {s["term"]: s for s in an.suggest(rec)}
    assert got["Bright Smile Dental"]["on"] and got["Bright Smile Dental"]["replace"] == "a dental clinic"
    if "Dana Lee" in got:
        assert not got["Dana Lee"]["on"] and got["Dana Lee"]["replace"] == ""


def test_swaps_never_touch_numbers():
    assert an.clean([{"term": "Acme", "replace": "a clinic"}]) == [["Acme", "a clinic"]]
    with pytest.raises(ReviewError, match="numbers"):
        an.clean([{"term": "Acme", "replace": "a clinic with 40 staff"}])
    with pytest.raises(ReviewError, match="numbers"):
        an.clean([{"term": "18", "replace": "some"}])
    with pytest.raises(ReviewError, match="instead"):
        an.clean([{"term": "Dana Lee", "replace": ""}])
    assert an.apply("The Acme team met Acme. A Acme test.", [["Acme", "an online shop"]]) == \
        "An online shop team met an online shop. An online shop test."


def test_anonymized_copy_keeps_every_number_and_the_approval():
    rec = rec_with_swaps()
    before = [c.text for c in rec.active_claims()]
    copy = an.anonymized(rec)
    after = [c.text for c in copy.active_claims()]
    assert numbers(before) == numbers(after)
    joined = " ".join(after + [copy.input.title] + [f.quote for f in copy.facts])
    assert "Bright Smile" not in joined and "Dana Lee" not in joined and "dana@" not in joined
    assert can_export(copy) and copy.input.client_name == ""
    assert [c.text for c in rec.active_claims()] == before and can_export(rec)  # the original is untouched


def test_anonymized_report_stays_approved_and_unnamed():
    rec = rec_with_swaps()
    rpt.build_report(rec, load("northwind"), None)
    for e in list(rec.report.blocking):
        rpt.remove_element(rec, e.id, "t")
    rpt.approve_report(rec, "Rain")
    assert rpt.report_ready(rec)
    copy = an.anonymized(rec)
    assert rpt.report_ready(copy)
    assert "Bright Smile" not in copy.report.plan.model_dump_json() and "Dana Lee" not in copy.report.plan.model_dump_json()


def test_anonymized_verified_link():
    rec = rec_with_swaps()
    copy = vf.snapshot(rec, evidence="full", anonymize=True)
    assert vf.intact(copy) and copy["client"] == ""
    shown = " ".join([copy["title"]] + [s["text"] + " ".join(e["quote"] for e in s["evidence"])
                                        for sec in copy["sections"] for s in sec["sentences"]])
    assert "Bright Smile" not in shown and "Dana Lee" not in shown
    view = vf.public_view(copy, rec.content_hash())
    assert view["anonymized"] and "anon" not in view  # the real names never reach the page
    rec.anon_map = []
    with pytest.raises(vf.VerifyError, match="anonymized"):
        vf.snapshot(rec, anonymize=True)


def test_anonymized_downloads_and_publish(web):  # noqa: F811
    c, _ = client(web)
    pid, rec = make_project(c, NOTES)
    approve_via_api(c, pid, rec)
    assert c.get(f"/api/projects/{pid}/export/portfolio?anonymized=1").status_code == 400  # no swaps yet
    assert c.post(f"/api/projects/{pid}/anon", json={"swaps": [{"term": "Bright Smile Dental", "replace": "a clinic with 9 chairs"}]}).status_code == 400
    v = c.post(f"/api/projects/{pid}/anon", json={"swaps": [{"term": t, "replace": r} for t, r in SWAPS]
                                                  + [{"term": "Harbor", "replace": "", "on": False}]}).json()
    assert v["saved"] and v["preview"] and not v["left"]
    page = c.get(f"/api/projects/{pid}/export/portfolio?anonymized=1")
    assert page.status_code == 200 and "Bright Smile" not in page.text and "a dental clinic" in page.text.lower()
    assert "anonymized" in page.headers["content-disposition"]
    assert c.get(f"/api/projects/{pid}").json()["can_export"]  # saving swaps doesn't touch the approval

    token = c.post(f"/api/projects/{pid}/publish", json={"anonymized": True}).json()[0]["token"]
    pub = type(c)(web.app).get(f"/v/{token}").text
    assert "anonymized version" in pub and "Bright Smile" not in pub and "Dana Lee" not in pub
