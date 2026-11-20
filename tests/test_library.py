"""Proof library: ranking approved case studies, verbatim proof sheets, anonymity, workspace isolation."""

from caseforge import library as lib

from .test_verify import approve_via_api, approved_record
from .test_web import client, make_project, web  # noqa: F401  (fixture)

LOGISTICS = ("Northwind Freight planned delivery routes by hand in Excel. We built a route planner with Python and "
             "Postgres. Fuel costs fell 14% in the first quarter. Dispatchers now plan a day in 20 minutes instead of 2 hours.")
DENTAL = ("Bright Smile Dental lost about 18 appointment slots a week to no-shows. We built a no-show predictor. "
          "Weekly no-shows fell from 18 to 11 in 8 weeks. Reception now calls only 15 patients a day.")


def recs():
    a = approved_record(LOGISTICS, client_name="Northwind Freight")
    a.id, a.input.title = "route", "Route planning for a freight company"
    a.approved_hash = a.content_hash()
    b = approved_record(DENTAL, client_name="Bright Smile Dental")
    b.id, b.input.title = "noshow", "No-show prediction for a dental clinic"
    b.approved_hash = b.content_hash()
    return a, b


def test_search_ranks_the_relevant_case_study_first():
    a, b = recs()
    hits = lib.search([b, a], "logistics company that wants lower fuel costs")
    assert hits[0]["id"] == "route" and hits[0]["matches"]
    assert any("14%" in m["text"] for m in hits[0]["matches"] + hits[0]["metrics"])
    assert lib.search([a, b], "dental clinic losing patients")[0]["id"] == "noshow"
    b.claims[0].text += " Changed."  # no longer approved: never in the library
    assert [h["id"] for h in lib.search([a, b], "")] == ["route"]


def test_sheet_quotes_approved_sentences_word_for_word():
    a, b = recs()
    s = lib.sheet([a, b], "lower costs for logistics")
    approved_text = {c.text for r in (a, b) for c in r.active_claims()}
    lines = [x["text"] for blk in s["projects"] for x in blk["sentences"]]
    assert lines and all(t in approved_text for t in lines)
    assert s["projects"][0]["id"] == "route"

    pick = a.active_claims()[0].id
    s = lib.sheet([a, b], "anything", picks={"route": [pick, "not-a-claim"], "noshow": []})
    assert [x["text"] for x in s["projects"][0]["sentences"]] == [a.claim(pick).text] and len(s["projects"]) == 1


def test_anonymous_clients_stay_anonymous_on_the_sheet():
    a, b = recs()
    b.client_signoff = {"decision": "anonymous", "by": "Dana"}
    s = lib.sheet([a, b], "clinic no-shows", picks={"noshow": [c.id for c in b.active_claims()]})
    text = lib.sheet_text(s)
    assert "Bright Smile" not in text and s["projects"][0]["client"] == ""
    b.anon_map = [["Bright Smile Dental", "a dental clinic"]]
    s = lib.sheet([a, b], "", picks={"noshow": [c.id for c in b.active_claims()]})
    assert "Bright Smile" not in lib.sheet_text(s)  # the team's own swaps are used
    s = lib.sheet([a, b], "", picks={"route": [c.id for c in a.active_claims()]}, anonymize_all=True,
                  links={"route": "https://x/v/abc"})
    assert "Northwind Freight" not in lib.sheet_text(s) and "https://x/v/abc" in lib.sheet_text(s)


def test_library_api(web):  # noqa: F811
    c, _ = client(web)
    pid, rec = make_project(c, LOGISTICS)
    approve_via_api(c, pid, rec)
    pid2, _ = make_project(c, DENTAL)  # drafted, not approved: stays out
    r = c.get("/api/library?q=fuel costs").json()
    assert r["n_approved"] == 1 and [x["id"] for x in r["results"]] == [pid]
    token = c.post(f"/api/projects/{pid}/publish", json={}).json()[0]["token"]
    s = c.post("/api/library/sheet", json={"q": "fuel costs"}).json()
    assert s["n_sentences"] and f"/v/{token}" in s["text"]
    html = c.post("/api/library/sheet/view", json={"q": "fuel costs"})
    assert html.status_code == 200 and "Relevant work" in html.text and "<svg" in html.text
    assert c.post("/api/library/sheet", json={"q": "zebra unicorn"}).status_code == 400

    other, _ = client(web, name="Bo", email="b@other.dev")
    assert other.get("/api/library?q=fuel").json()["results"] == []
