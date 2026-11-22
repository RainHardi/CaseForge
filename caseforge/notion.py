"""Read a Notion page (or database) into plain text notes.

Two ways in:
- **Connect Notion** (OAuth, public integration): the user clicks Connect once, picks pages in Notion's
  own page picker, and then chooses a project from a list. The tokens are stored encrypted, per
  workspace, and can be removed with Disconnect.
- **Integration secret**: the user pastes their own internal integration secret and a page link.
  That secret is used for one import and never stored.

Either way CaseForge reads the page, its sub-pages and database rows, and puts the text in the notes
box — like an uploaded file — so the user sees and edits it before anything goes to the AI.
"""

from __future__ import annotations

import re

import httpx

from caseforge.ingest import MAX_CHARS, IngestError

API = "https://api.notion.com/v1"
VERSION = "2022-06-28"
MAX_PAGES = 40  # sub-pages and database rows read in one import
MAX_DEPTH = 3  # page → sub-page → sub-sub-page
ROW_BLOCKS = True  # also read the content inside each database row
SKIP_PROPS = {"email", "phone_number", "files", "relation", "rollup", "created_by", "last_edited_by"}  # personal or noise


class NotionError(IngestError):
    pass


class TokenRejected(NotionError):
    """Notion answered 401: the secret is wrong, or an OAuth access token expired (refresh and retry)."""


def page_id(ref: str) -> str:
    """The 32-hex id from a Notion link or a bare id ('…/Project-notes-1a2b…?v=…' → '1a2b…')."""
    ref = (ref or "").strip()
    path = ref.split("?")[0].split("#")[0]
    found = re.findall(r"[0-9a-fA-F]{8}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{12}", path)
    if not found:
        raise NotionError("That doesn't look like a Notion page link. Copy it with Share → Copy link.")
    return found[-1].replace("-", "").lower()


def _plain(rich: list | None) -> str:
    return "".join(r.get("plain_text", "") for r in rich or []).strip()


class Reader:
    def __init__(self, token: str, client: httpx.Client | None = None):
        token = (token or "").strip()
        if not token:
            raise NotionError("Paste your Notion integration token first.")
        self.http = client or httpx.Client(timeout=20)
        self.headers = {"Authorization": f"Bearer {token}", "Notion-Version": VERSION}
        self.pages = 0
        self.lines: list[str] = []
        self.truncated = False  # stopped adding text
        self.cut = False  # some table rows weren't read

    # ---------------------------------------------------------------- http
    def _call(self, method: str, path: str, **kw) -> dict:
        try:
            r = self.http.request(method, API + path, headers=self.headers, **kw)
        except httpx.HTTPError as e:
            raise NotionError(f"Couldn't reach Notion: {e.__class__.__name__}. Try again.") from e
        if r.status_code == 401:
            raise TokenRejected("Notion rejected the token. Copy the Internal Integration Secret again.")
        if r.status_code == 429:
            raise NotionError("Notion is rate limiting us. Wait a minute and try again.")
        if r.status_code >= 400:
            try:
                body = r.json()
            except ValueError:
                body = {}
            raise _Status(r.status_code, body.get("code", ""), body.get("message", ""))
        return r.json()

    def _children(self, block_id: str) -> list[dict]:
        out, cursor = [], None
        while True:
            q = {"page_size": 100} | ({"start_cursor": cursor} if cursor else {})
            data = self._call("GET", f"/blocks/{block_id}/children", params=q)
            out += data.get("results", [])
            if not data.get("has_more") or len(out) > 1000:
                return out
            cursor = data.get("next_cursor")

    def _rows(self, db_id: str) -> list[dict]:
        out, cursor = [], None
        while True:
            body = {"page_size": 100} | ({"start_cursor": cursor} if cursor else {})
            data = self._call("POST", f"/databases/{db_id}/query", json=body)
            out += data.get("results", [])
            if len(out) > MAX_PAGES or (data.get("has_more") and len(out) >= MAX_PAGES):
                self.cut = True
                return out[:MAX_PAGES]
            if not data.get("has_more"):
                return out
            cursor = data.get("next_cursor")

    # ---------------------------------------------------------------- text
    def _add(self, line: str) -> None:
        if self.truncated:
            return
        if sum(len(x) + 1 for x in self.lines) + len(line) > MAX_CHARS:
            self.truncated = True
            return
        self.lines.append(line)

    def _room(self) -> bool:
        if self.pages >= MAX_PAGES:
            self.truncated = True
        return not self.truncated

    def read(self, ref: str) -> tuple[str, str]:
        """(title, text) for a page or database link."""
        pid = page_id(ref)
        try:
            page = self._call("GET", f"/pages/{pid}")
        except _Status as e:
            if e.status != 404 and e.status != 400:
                raise e.friendly() from None
            try:  # a full-page database link has the database id
                db = self._call("GET", f"/databases/{pid}")
            except _Status as e2:
                raise e2.friendly() from None
            title = _plain(db.get("title")) or "Notion database"
            self._add(f"# {title}")
            self._database(pid, 1)
            return title, self._text()
        title = self._title(page) or "Notion page"
        self._page(page, 0, title)
        return title, self._text()

    def _text(self) -> str:
        text = "\n".join(self.lines)
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        if self.truncated or self.cut:
            text += "\n[… Notion import cut here — too long; share a smaller page or delete what isn't needed]"
        if not any(line.strip() and not line.startswith("#") for line in self.lines):  # titles only
            raise NotionError("The page is empty, or the integration can't see its content.")
        return text

    @staticmethod
    def _title(page: dict) -> str:
        for prop in (page.get("properties") or {}).values():
            if prop.get("type") == "title":
                return _plain(prop.get("title"))
        return ""

    def _page(self, page: dict, depth: int, title: str | None = None) -> None:
        if not self._room():
            return
        self.pages += 1
        title = title or self._title(page) or "Untitled"
        self._add(("#" * min(depth + 1, 3)) + " " + title)
        props = self._props(page)
        if props:
            self._add(props)
        self._blocks(page["id"], depth, 0)
        self._add("")

    def _props(self, page: dict) -> str:
        parts = []
        for name, prop in (page.get("properties") or {}).items():
            kind = prop.get("type")
            if kind == "title" or kind in SKIP_PROPS:
                continue
            value = _prop_value(prop)
            if value:
                parts.append(f"{name}: {value}")
        return " | ".join(parts)

    def _blocks(self, block_id: str, depth: int, indent: int) -> None:
        try:
            blocks = self._children(block_id)
        except _Status as e:
            if e.status in (403, 404):
                return  # a linked block the integration can't see
            raise e.friendly() from None
        num = 0
        for b in blocks:
            if self.truncated:
                return
            kind = b.get("type", "")
            num = num + 1 if kind == "numbered_list_item" else 0
            if kind == "child_page":
                if depth + 1 <= MAX_DEPTH and self._room():
                    try:
                        self._page(self._call("GET", f"/pages/{b['id']}"), depth + 1)
                    except _Status:
                        pass
                continue
            if kind == "child_database":
                self._add(("#" * min(depth + 2, 3)) + " " + (b.get("child_database", {}).get("title") or "Table"))
                self._database(b["id"], depth + 1)
                continue
            line = _block_line(b, num)
            if line is not None:
                self._add("  " * indent + line)
            if b.get("has_children") and kind not in ("child_page", "child_database"):
                self._blocks(b["id"], depth, indent + (1 if kind != "column_list" and kind != "column" else 0))

    def _database(self, db_id: str, depth: int) -> None:
        try:
            rows = self._rows(db_id)
        except _Status as e:
            if e.status in (403, 404):
                self._add("(table not shared with the integration)")
                return
            raise e.friendly() from None
        for row in rows:
            if not self._room():
                return
            self.pages += 1
            title = self._title(row) or "Untitled"
            props = self._props(row)
            self._add(f"- {title}" + (f" — {props}" if props else ""))
            if ROW_BLOCKS and depth < MAX_DEPTH:
                self._blocks(row["id"], depth + 1, 1)


class _Status(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(f"{status} {code} {message}")
        self.status, self.code, self.message = status, code, message

    def friendly(self) -> NotionError:
        if self.status == 404 or self.code == "object_not_found":
            return NotionError("Notion can't find that page for this integration. Open the page → ••• → "
                               "Connections → add your integration, then try again.")
        if self.status == 403:
            return NotionError("The integration isn't allowed to read content. In Notion's integration "
                               "settings, turn on Read content.")
        return NotionError(f"Notion said: {self.message or self.code or self.status}")


def _prop_value(prop: dict) -> str:
    kind = prop.get("type")
    v = prop.get(kind)
    if v is None:
        return ""
    if kind == "rich_text":
        return _plain(v)
    if kind in ("select", "status"):
        return v.get("name", "")
    if kind == "multi_select":
        return ", ".join(o.get("name", "") for o in v)
    if kind == "date":
        start, end = v.get("start") or "", v.get("end") or ""
        return f"{start} to {end}" if end else start
    if kind == "number":
        return f"{v:g}" if isinstance(v, (int, float)) else ""
    if kind == "checkbox":
        return "yes" if v else "no"
    if kind == "url":
        return v
    if kind == "people":
        return ", ".join(p.get("name", "") for p in v if p.get("name"))
    if kind == "formula":
        inner = v.get(v.get("type", ""), "")
        return "" if inner is None else str(inner)
    if kind in ("created_time", "last_edited_time"):
        return ""  # Notion's own timestamps aren't project facts
    return ""


def _block_line(b: dict, num: int) -> str | None:
    kind = b.get("type", "")
    data = b.get(kind) or {}
    text = _plain(data.get("rich_text"))
    if kind == "paragraph":
        return text
    if kind.startswith("heading_"):
        return ("#" * min(int(kind[-1]) + 1, 4)) + " " + text if text else None
    if kind == "bulleted_list_item":
        return "- " + text
    if kind == "numbered_list_item":
        return f"{num}. " + text
    if kind == "to_do":
        return ("[x] " if data.get("checked") else "[ ] ") + text
    if kind in ("toggle", "callout"):
        return text or None
    if kind == "quote":
        return "> " + text if text else None
    if kind == "code":
        return text or None
    if kind == "table_row":
        return " | ".join(_plain(c) for c in data.get("cells", []))
    if kind in ("bookmark", "embed", "link_preview"):
        cap = _plain(data.get("caption"))
        return f"{cap} ({data.get('url', '')})" if cap else data.get("url") or None
    if kind == "equation":
        return data.get("expression") or None
    return None  # dividers, images, columns, tables (rows come as children), unsupported


def import_page(token: str, ref: str, client: httpx.Client | None = None) -> dict:
    reader = Reader(token, client)
    title, text = reader.read(ref)
    return {"title": title, "text": text, "pages": reader.pages, "truncated": reader.truncated or reader.cut}


# ====================================================================== Connect Notion (OAuth)
AUTHORIZE_URL = "https://api.notion.com/v1/oauth/authorize"
TOKEN_URL = API + "/oauth/token"


def oauth_settings() -> dict | None:
    """Client id/secret from the environment, or None when Connect Notion isn't set up on this server."""
    import os

    cid, secret = os.getenv("NOTION_CLIENT_ID", "").strip(), os.getenv("NOTION_CLIENT_SECRET", "").strip()
    if not cid or not secret:
        return None
    return {"client_id": cid, "client_secret": secret, "redirect_uri": os.getenv("NOTION_REDIRECT_URI", "").strip()}


def authorize_url(client_id: str, redirect_uri: str, state: str) -> str:
    from urllib.parse import urlencode

    return AUTHORIZE_URL + "?" + urlencode({"client_id": client_id, "redirect_uri": redirect_uri,
                                            "response_type": "code", "owner": "user", "state": state})


def _token_call(body: dict, settings: dict, client: httpx.Client | None) -> dict:
    http = client or httpx.Client(timeout=20)
    try:
        r = http.post(TOKEN_URL, json=body, auth=(settings["client_id"], settings["client_secret"]),
                      headers={"Notion-Version": VERSION})
    except httpx.HTTPError as e:
        raise NotionError(f"Couldn't reach Notion: {e.__class__.__name__}. Try again.") from e
    try:
        data = r.json()
    except ValueError:
        data = {}
    if r.status_code >= 400 or "access_token" not in data:
        msg = data.get("error_description") or data.get("message") or data.get("error") or f"HTTP {r.status_code}"
        raise NotionError(f"Notion didn't accept the connection: {msg}")
    return data


def exchange_code(code: str, redirect_uri: str, settings: dict, client: httpx.Client | None = None) -> dict:
    """The authorization code → {access_token, refresh_token, workspace_name, workspace_icon, bot_id, …}."""
    return _token_call({"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri},
                       settings, client)


def refresh(refresh_token: str, settings: dict, client: httpx.Client | None = None) -> dict:
    if not refresh_token:
        raise TokenRejected("The Notion connection expired. Connect Notion again.")
    return _token_call({"grant_type": "refresh_token", "refresh_token": refresh_token}, settings, client)


def shared_pages(token: str, query: str = "", client: httpx.Client | None = None, limit: int = 30) -> list[dict]:
    """Pages and databases the user shared with CaseForge in Notion's page picker, newest first."""
    reader = Reader(token, client)
    body = {"page_size": min(limit, 100), "sort": {"direction": "descending", "timestamp": "last_edited_time"}}
    if query.strip():
        body["query"] = query.strip()[:200]
    try:
        data = reader._call("POST", "/search", json=body)
    except _Status as e:
        raise e.friendly() from None
    out = []
    for item in data.get("results", []):
        kind = item.get("object")
        if kind == "database":
            title = _plain(item.get("title")) or "Untitled table"
        elif kind == "page":
            if (item.get("parent") or {}).get("type") == "database_id":
                continue  # rows of a table: import the table (or open the row's own page) instead
            title = Reader._title(item) or "Untitled"
        else:
            continue
        out.append({"id": item["id"].replace("-", ""), "type": kind, "title": title, "url": item.get("url", ""),
                    "edited": (item.get("last_edited_time") or "")[:10]})
    return out


# ---------------------------------------------------------------- token sealing
def _fernet(secret: str):
    import base64
    import hashlib

    from cryptography.fernet import Fernet

    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(("notion-tokens:" + secret).encode()).digest()))


def seal(value: str, secret: str) -> str:
    """Encrypt a token for the database (key derived from the server's SECRET_KEY)."""
    return _fernet(secret).encrypt(value.encode()).decode() if value else ""


def unseal(value: str, secret: str) -> str:
    """Decrypt a stored token; "" when it can't be read (e.g. SECRET_KEY changed) — the user reconnects."""
    if not value:
        return ""
    from cryptography.fernet import InvalidToken

    try:
        return _fernet(secret).decrypt(value.encode()).decode()
    except (InvalidToken, ValueError):
        return ""
