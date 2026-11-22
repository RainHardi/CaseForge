"""Connect Notion (OAuth): token exchange and refresh, shared-page list, encrypted storage, the full web flow."""

import base64
import json
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from caseforge import notion as nt

from .test_web import client, web  # noqa: F401  (fixture)

SETTINGS = {"client_id": "cid", "client_secret": "csecret", "redirect_uri": "https://cf.test/api/notion/callback"}


def fake(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_exchange_and_refresh_use_basic_auth():
    seen = []

    def handler(req):
        seen.append(req)
        body = json.loads(req.content)
        if body["grant_type"] == "authorization_code" and body["code"] == "good":
            return httpx.Response(200, json={"access_token": "acc1", "refresh_token": "ref1", "workspace_name": "Team 5"})
        if body["grant_type"] == "refresh_token" and body["refresh_token"] == "ref1":
            return httpx.Response(200, json={"access_token": "acc2", "refresh_token": "ref2"})
        return httpx.Response(400, json={"error": "invalid_grant", "error_description": "bad code"})

    tok = nt.exchange_code("good", SETTINGS["redirect_uri"], SETTINGS, fake(handler))
    assert tok["access_token"] == "acc1" and tok["workspace_name"] == "Team 5"
    assert seen[0].url == nt.TOKEN_URL
    assert seen[0].headers["Authorization"] == "Basic " + base64.b64encode(b"cid:csecret").decode()
    assert json.loads(seen[0].content)["redirect_uri"] == SETTINGS["redirect_uri"]
    assert nt.refresh("ref1", SETTINGS, fake(handler))["access_token"] == "acc2"
    with pytest.raises(nt.NotionError, match="bad code"):
        nt.exchange_code("nope", SETTINGS["redirect_uri"], SETTINGS, fake(handler))
    with pytest.raises(nt.TokenRejected):
        nt.refresh("", SETTINGS, fake(handler))


def test_authorize_url_and_shared_pages():
    url = urlparse(nt.authorize_url("cid", SETTINGS["redirect_uri"], "st8"))
    q = parse_qs(url.query)
    assert url.geturl().startswith(nt.AUTHORIZE_URL)
    assert q == {"client_id": ["cid"], "redirect_uri": [SETTINGS["redirect_uri"]], "response_type": ["code"],
                 "owner": ["user"], "state": ["st8"]}

    def handler(req):
        assert req.headers["Authorization"] == "Bearer acc" and req.url.path == "/v1/search"
        assert json.loads(req.content)["query"] == "north"
        return httpx.Response(200, json={"results": [
            {"object": "page", "id": "1a2b3c4d-5e6f-4708-9a0b-1c2d3e4f5a6b", "url": "https://notion.so/p",
             "last_edited_time": "2026-11-20T10:00:00Z", "parent": {"type": "workspace"},
             "properties": {"title": {"type": "title", "title": [{"plain_text": "Northwind portal"}]}}},
            {"object": "page", "id": "row1", "parent": {"type": "database_id"}, "properties": {}},
            {"object": "database", "id": "db1", "title": [{"plain_text": "Timeline"}], "parent": {"type": "page_id"}},
        ]})

    pages = nt.shared_pages("acc", "north", fake(handler))
    assert [(p["title"], p["type"]) for p in pages] == [("Northwind portal", "page"), ("Timeline", "database")]
    assert pages[0]["id"] == "1a2b3c4d5e6f47089a0b1c2d3e4f5a6b" and pages[0]["edited"] == "2026-11-20"


def test_tokens_are_sealed():
    sealed = nt.seal("secret-token", "server-key")
    assert sealed and "secret-token" not in sealed
    assert nt.unseal(sealed, "server-key") == "secret-token"
    assert nt.unseal(sealed, "another-key") == ""  # SECRET_KEY changed → reconnect, no crash
    assert nt.seal("", "k") == "" and nt.unseal("", "k") == ""


def test_off_without_client_credentials(web, monkeypatch):  # noqa: F811
    monkeypatch.delenv("NOTION_CLIENT_ID", raising=False)
    c, _ = client(web)
    assert c.get("/api/config").json()["notion_connect"] is False
    assert c.get("/api/notion/status").json() == {"available": False, "connected": False, "workspace": "", "since": ""}
    assert c.get("/api/notion/connect", follow_redirects=False).status_code == 404


def test_connect_flow(web, monkeypatch):  # noqa: F811
    monkeypatch.setenv("NOTION_CLIENT_ID", "cid")
    monkeypatch.setenv("NOTION_CLIENT_SECRET", "csecret")
    c, _ = client(web)
    assert c.get("/api/config").json()["notion_connect"] is True

    r = c.get("/api/notion/connect", follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"].startswith(nt.AUTHORIZE_URL)
    q = parse_qs(urlparse(r.headers["location"]).query)
    state, redirect = q["state"][0], q["redirect_uri"][0]
    assert redirect.endswith("/api/notion/callback")

    def exchange(code, redirect_uri, settings, client=None):
        assert code == "the-code" and redirect_uri == redirect and settings["client_secret"] == "csecret"
        return {"access_token": "acc1", "refresh_token": "ref1", "workspace_name": "Team 5 Notion", "bot_id": "b"}
    monkeypatch.setattr(web.nt, "exchange_code", exchange)

    assert "notion=expired" in c.get("/api/notion/callback?code=x&state=forged", follow_redirects=False).headers["location"]
    assert "notion=cancelled" in c.get("/api/notion/callback?error=access_denied", follow_redirects=False).headers["location"]
    other, _ = client(web, name="Bo", email="b@other.dev")  # someone else can't finish this user's sign-in
    assert "notion=expired" in other.get(f"/api/notion/callback?code=the-code&state={state}",
                                         follow_redirects=False).headers["location"]
    done = c.get(f"/api/notion/callback?code=the-code&state={state}", follow_redirects=False)
    assert done.headers["location"] == "/app?notion=connected#new"

    st = c.get("/api/notion/status").json()
    assert st["connected"] and st["workspace"] == "Team 5 Notion"
    row = web.db().notion(c.get("/api/me").json()["workspace_id"])
    assert row["access_token"] != "acc1" and "acc1" not in row["access_token"]  # stored encrypted
    assert other.get("/api/notion/status").json()["connected"] is False

    monkeypatch.setattr(web.nt, "shared_pages", lambda token, q="": [{"id": "p1", "title": f"seen with {token}",
                                                                       "type": "page", "url": "", "edited": ""}])
    assert c.get("/api/notion/pages").json()[0]["title"] == "seen with acc1"

    calls = []

    def importer(token, ref):  # the first try hits an expired token; after the refresh it works
        calls.append(token)
        if token == "acc1":
            raise nt.TokenRejected("expired")
        return {"title": "Northwind", "text": f"notes for {ref}", "pages": 1, "truncated": False}
    monkeypatch.setattr(web, "notion_import", importer)
    monkeypatch.setattr(web.nt, "refresh", lambda rt, s, client=None: {"access_token": "acc2", "refresh_token": "ref2"})
    out = c.post("/api/notion/import", json={"id": "p1"}).json()
    assert out["text"] == "notes for p1" and calls == ["acc1", "acc2"]
    assert c.get("/api/notion/pages").json()[0]["title"] == "seen with acc2"  # the new token was stored

    def dead(rt, s, client=None):
        raise nt.NotionError("revoked")
    monkeypatch.setattr(web.nt, "refresh", dead)
    monkeypatch.setattr(web, "notion_import", lambda token, ref: (_ for _ in ()).throw(nt.TokenRejected("x")))
    r = c.post("/api/notion/import", json={"id": "p1"})
    assert r.status_code == 400 and "Connect Notion again" in r.json()["detail"]
    assert c.get("/api/notion/status").json()["connected"] is False  # a dead connection is removed

    c.get(f"/api/notion/callback?code=the-code&state={c.get('/api/notion/connect', follow_redirects=False).headers['location'].split('state=')[1]}",
          follow_redirects=False)
    assert c.get("/api/notion/status").json()["connected"]
    assert c.post("/api/notion/disconnect").json() == {"connected": False}
    assert c.get("/api/notion/status").json()["connected"] is False
