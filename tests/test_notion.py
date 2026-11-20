"""Notion import: links → ids, blocks/sub-pages/tables → notes text, friendly errors. Uses a fake Notion API."""

import httpx
import pytest

from caseforge.notion import MAX_PAGES, NotionError, import_page, page_id

PAGE = "1a2b3c4d5e6f47089a0b1c2d3e4f5a6b"
SUB = "22222222222222222222222222222222"
DB = "33333333333333333333333333333333"
ROW = "44444444444444444444444444444444"


def rt(text):
    return [{"plain_text": text}]


def block(kind, text="", **extra):
    return {"id": extra.pop("id", "b" + text[:6]), "type": kind, "has_children": extra.pop("has_children", False),
            kind: {"rich_text": rt(text), **extra}}


def title_props(title, **more):
    return {"Name": {"type": "title", "title": rt(title)}, **more}


def fake_notion(seen, pages=None, children=None, databases=None, rows=None, status=None):
    pages = pages or {}
    children = children or {}
    databases = databases or {}
    rows = rows or {}

    def handler(request: httpx.Request):
        seen.append(request)
        if status:
            return httpx.Response(status, json={"code": "x", "message": "nope"})
        parts = request.url.path.split("/")  # /v1/<kind>/<id>[/children|/query]
        kind, oid = parts[2], parts[3]
        if kind == "pages" and oid in pages:
            return httpx.Response(200, json=pages[oid])
        if kind == "blocks" and oid in children:
            got = children[oid]
            if isinstance(got, tuple):  # two pages of results
                first, second = got
                if request.url.params.get("start_cursor") == "next":
                    return httpx.Response(200, json={"results": second, "has_more": False})
                return httpx.Response(200, json={"results": first, "has_more": True, "next_cursor": "next"})
            return httpx.Response(200, json={"results": got, "has_more": False})
        if kind == "blocks":
            return httpx.Response(200, json={"results": [], "has_more": False})
        if kind == "databases" and parts[-1] == "query" and oid in rows:
            return httpx.Response(200, json={"results": rows[oid], "has_more": False})
        if kind == "databases" and oid in databases:
            return httpx.Response(200, json=databases[oid])
        return httpx.Response(404, json={"code": "object_not_found", "message": "not found"})

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_page_id_from_links_and_bare_ids():
    assert page_id(f"https://www.notion.so/team/Northwind-project-{PAGE}?pvs=4") == PAGE
    assert page_id("1a2b3c4d-5e6f-4708-9a0b-1c2d3e4f5a6b") == PAGE
    assert page_id(f"https://www.notion.so/{DB}?v=99999999999999999999999999999999") == DB  # the view id is after "?"
    with pytest.raises(NotionError):
        page_id("https://example.com/no-id-here")


def test_page_subpages_tables_and_properties_become_notes():
    seen = []
    client = fake_notion(
        seen,
        pages={
            PAGE: {"id": PAGE, "properties": title_props(
                "Northwind portal", Status={"type": "status", "status": {"name": "Done"}},
                Owner={"type": "email", "email": "pm@example.com"})},
            SUB: {"id": SUB, "properties": title_props("Retro")},
        },
        children={
            PAGE: ([block("heading_2", "Problem"), block("paragraph", "Orders were tracked in 3 spreadsheets."),
                    block("numbered_list_item", "Interview staff"), block("numbered_list_item", "Build portal")],
                   [block("to_do", "Launch", checked=True),
                    block("bulleted_list_item", "Stack", has_children=True, id="stack"),
                    {"id": SUB, "type": "child_page", "has_children": True, "child_page": {"title": "Retro"}},
                    {"id": DB, "type": "child_database", "has_children": False, "child_database": {"title": "Timeline"}}]),
            "stack": [block("bulleted_list_item", "FastAPI and Postgres")],
            SUB: [block("quote", "Handover took two weeks longer than planned.")],
        },
        rows={DB: [{"id": ROW, "properties": title_props(
            "Pilot", When={"type": "date", "date": {"start": "2024-03-01", "end": "2024-04-15"}},
            Team={"type": "number", "number": 6})}]},
    )
    out = import_page("secret_abc", f"https://www.notion.so/Northwind-{PAGE}", client)
    text = out["text"]
    assert out["title"] == "Northwind portal" and out["pages"] == 3 and not out["truncated"]
    assert text.startswith("# Northwind portal\nStatus: Done")
    assert "pm@example.com" not in text  # personal properties are skipped
    for line in ["## Problem", "Orders were tracked in 3 spreadsheets.", "1. Interview staff", "2. Build portal",
                 "[x] Launch", "- Stack", "  - FastAPI and Postgres", "## Retro",
                 "> Handover took two weeks longer than planned.", "## Timeline",
                 "- Pilot — When: 2024-03-01 to 2024-04-15 | Team: 6"]:
        assert line in text, line
    assert all(r.headers["Authorization"] == "Bearer secret_abc" and r.headers["Notion-Version"] for r in seen)
    assert all(r.method == "GET" or r.url.path.endswith("/query") for r in seen)  # read only


def test_full_page_database_link_is_read_as_a_table():
    rows = [{"id": f"{i:032d}", "properties": title_props(f"Task {i}")} for i in range(MAX_PAGES + 5)]
    client = fake_notion([], databases={DB: {"id": DB, "title": rt("Sprint board")}}, rows={DB: rows})
    out = import_page("t", DB, client)
    assert out["title"] == "Sprint board" and "- Task 0" in out["text"]
    assert out["pages"] == MAX_PAGES and out["truncated"]  # stops at the page limit and says so


def test_errors_tell_the_user_what_to_do():
    with pytest.raises(NotionError, match="Connections"):
        import_page("t", PAGE, fake_notion([]))  # not shared with the integration
    with pytest.raises(NotionError, match="token"):
        import_page("t", PAGE, fake_notion([], status=401))
    with pytest.raises(NotionError, match="secret|token"):
        import_page("", PAGE, fake_notion([]))
    empty = fake_notion([], pages={PAGE: {"id": PAGE, "properties": {}}})
    with pytest.raises(NotionError, match="empty"):
        import_page("t", PAGE, empty)  # a title and nothing else


def test_web_route_needs_login_and_returns_text(tmp_path, monkeypatch):
    import importlib

    from fastapi.testclient import TestClient

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'n.db'}")
    monkeypatch.setenv("CASEFORGE_LLM_MODE", "offline")
    import web.main as m
    m = importlib.reload(m)
    m._db = None
    c = TestClient(m.app)
    assert c.post("/api/notion", json={"token": "t", "url": PAGE}).status_code == 401
    c.post("/api/signup", json={"name": "A", "email": "a@x.dev", "password": "password123", "company": "T"})
    monkeypatch.setattr(m, "notion_import", lambda token, url: {"title": "P", "text": "hello", "pages": 1, "truncated": False})
    r = c.post("/api/notion", json={"token": "t", "url": PAGE})
    assert r.status_code == 200 and r.json()["text"] == "hello"

    def bad(token, url):
        raise NotionError("Notion rejected the token.")
    monkeypatch.setattr(m, "notion_import", bad)
    r = c.post("/api/notion", json={"token": "t", "url": PAGE})
    assert r.status_code == 400 and "token" in r.json()["detail"]
