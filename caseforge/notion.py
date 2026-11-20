"""Read a Notion page (or database) into plain text notes.

The user makes a Notion integration, shares the project page with it and pastes the token and
the page link. CaseForge reads the page, its sub-pages and database rows, and puts the text in the
notes box — like an uploaded file — so the user sees and edits it before anything goes to the AI.
The token is used for this one import and never stored.
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
            raise NotionError("Notion rejected the token. Copy the Internal Integration Secret again.")
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
