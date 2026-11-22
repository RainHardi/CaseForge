"""CaseForge website: landing page + app, served by one FastAPI server.

Run locally:   uvicorn web.main:app --reload            → http://localhost:8000
Share laptop:  devtunnel host -p 8000 --allow-anonymous  (see docs/DEPLOY.md)
Host for free: Render (web) + Neon (Postgres)            (see docs/DEPLOY.md)
"""

from __future__ import annotations

import json
import os
import secrets
import tempfile
import time
from collections import defaultdict
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from pydantic import BaseModel

from caseforge import anonymize as anon
from caseforge import formats as fmt
from caseforge import library as lib
from caseforge import report as rpt
from caseforge import review
from caseforge import signoff as so
from caseforge import verify as vf
from caseforge.brandkit import BUNDLED_FONTS, BrandKit, auto_brand, from_guidelines, from_logo, kit_warnings, presets, publisher
from caseforge.config import ROOT, get_settings
from caseforge.db import DB, AuthError
from caseforge.ingest import ALL_TYPES, IngestError, extract_text, is_image
from caseforge.llm import LLMError, get_llm
from caseforge.models import FIELD_KEYS, SECTION_TITLES, ImageRef, ProjectInput, ProjectRecord
from caseforge import notion as nt
from caseforge.notion import import_page as notion_import
from caseforge.pipeline import generate
from caseforge.render import ExportBlocked
from caseforge.render.html import render_portfolio_page
from caseforge.render.proof_sheet import proof_sheet_html
from caseforge.render.signoff_page import signoff_page
from caseforge.render.verified import GONE, qr_svg, verified_page
from caseforge.render.pdf import export_name, render_case_study, render_one_pager

STATIC = Path(__file__).parent / "static"
SECRET = os.getenv("SECRET_KEY") or secrets.token_hex(32)  # set it when hosting, or logins reset on restart
DAILY_LIMIT = int(os.getenv("DAILY_AI_LIMIT", "30"))
MAX_FILE_MB = 10
COOKIE = "cf_session"
SESSION_DAYS = 14

app = FastAPI(title="CaseForge", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.middleware("http")
async def _fresh_code(request: Request, call_next):
    """Pages, scripts and styles are re-checked on every load (a 304 when unchanged),
    so an updated app.js shows up without a hard refresh."""
    resp = await call_next(request)
    path = request.url.path
    if path in ("/", "/app") or path.endswith((".js", ".css", ".html")):
        resp.headers["Cache-Control"] = "no-cache"
    return resp

_db: DB | None = None
_signer = URLSafeTimedSerializer(SECRET, salt="caseforge-session")
_failed_logins: dict[str, list[float]] = defaultdict(list)


def db() -> DB:
    global _db
    if _db is None:
        _db = DB()
    return _db


def llm():
    try:
        return get_llm()
    except LLMError:
        return None


# ------------------------------------------------------------------ errors
@app.exception_handler(review.ReviewError)
@app.exception_handler(AuthError)
@app.exception_handler(IngestError)
@app.exception_handler(ExportBlocked)
@app.exception_handler(vf.VerifyError)
@app.exception_handler(so.SignoffError)
async def _bad_request(request: Request, exc: Exception):
    return JSONResponse({"detail": str(exc)}, status_code=400)


@app.exception_handler(KeyError)
async def _missing(request: Request, exc: Exception):
    return JSONResponse({"detail": f"Not found: {exc}"}, status_code=404)


@app.exception_handler(LLMError)
async def _llm_down(request: Request, exc: Exception):
    return JSONResponse({"detail": f"The AI service is busy or unavailable — try again in a minute. ({exc})"},
                        status_code=503)


# ------------------------------------------------------------------ sessions
def _set_session(resp: Response, request: Request, uid: str) -> None:
    secure = request.headers.get("x-forwarded-proto", request.url.scheme) == "https"
    resp.set_cookie(COOKIE, _signer.dumps(uid), max_age=SESSION_DAYS * 86400, httponly=True,
                    samesite="lax", secure=secure)


def current_user(request: Request) -> dict:
    token = request.cookies.get(COOKIE)
    if not token:
        raise HTTPException(401, "Please log in.")
    try:
        uid = _signer.loads(token, max_age=SESSION_DAYS * 86400)
    except (BadSignature, SignatureExpired):
        raise HTTPException(401, "Your session expired. Please log in again.")
    user = db().user(uid)
    if not user:
        raise HTTPException(401, "Please log in.")
    return user


def get_project(project_id: str, user: dict = Depends(current_user)) -> ProjectRecord:
    rec = db().load(user["workspace_id"], project_id)
    if rec is None:  # other workspaces' projects simply don't exist for you
        raise HTTPException(404, "Project not found.")
    return rec


def view(rec: ProjectRecord, user: dict) -> dict:
    data = rec.model_dump(mode="json")
    data["blockers"] = review.blockers(rec)
    data["can_export"] = review.can_export(rec)
    data["source_text"] = rec.input.source_text()
    data["sections"] = [{"key": k, "title": t} for k, t in SECTION_TITLES.items()]
    data["formats"] = {k: {**v, "ready": fmt.format_ready(rec, k),
                           "stale": bool(k in rec.outputs and rec.outputs[k].based_on_hash != rec.approved_hash)}
                       for k, v in fmt.FORMATS.items()}
    data["quota_left"] = db().quota_left(user["id"], DAILY_LIMIT)
    data["report_blockers"] = rpt.report_blockers(rec) if rec.report else []
    data["report_ready"] = rpt.report_ready(rec)
    return data


# ------------------------------------------------------------------ pages
@app.get("/", include_in_schema=False)
def landing():
    return FileResponse(STATIC / "index.html")


@app.get("/app", include_in_schema=False)
def app_page():
    return FileResponse(STATIC / "app.html")


@app.get("/healthz", include_in_schema=False)
def health():
    return {"ok": True}


@app.get("/api/config")
def config():
    s = get_settings()
    return {"ai": bool(llm()), "model": s.gemini_model if llm() else "offline", "daily_limit": DAILY_LIMIT,
            "file_types": ALL_TYPES, "max_file_mb": MAX_FILE_MB, "notion_connect": bool(nt.oauth_settings())}


# ------------------------------------------------------------------ auth
class SignupBody(BaseModel):
    name: str
    email: str
    password: str
    company: str = ""
    invite_code: str = ""


class LoginBody(BaseModel):
    email: str
    password: str


@app.post("/api/signup")
def signup(body: SignupBody, request: Request, response: Response):
    user = db().signup(body.name, body.email, body.password, body.company, body.invite_code)
    _set_session(response, request, user["id"])
    return user


@app.post("/api/login")
def login(body: LoginBody, request: Request, response: Response):
    key = f"{request.client.host if request.client else ''}:{body.email.lower()}"
    recent = [t for t in _failed_logins[key] if time.time() - t < 900]
    if len(recent) >= 10:
        raise AuthError("Too many failed attempts. Try again in 15 minutes.")
    try:
        user = db().login(body.email, body.password)
    except AuthError:
        _failed_logins[key] = recent + [time.time()]
        raise
    _failed_logins.pop(key, None)
    _set_session(response, request, user["id"])
    return user


@app.post("/api/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE)
    return {"ok": True}


@app.get("/api/me")
def me(user: dict = Depends(current_user)):
    members = db().members(user["workspace_id"])
    return {**user, "members": members, "owner": bool(members) and members[0]["id"] == user["id"],
            "quota_left": db().quota_left(user["id"], DAILY_LIMIT), "daily_limit": DAILY_LIMIT}


# ------------------------------------------------------------------ account settings
class ProfileBody(BaseModel):
    name: str
    email: str


class PasswordBody(BaseModel):
    current: str
    new: str


class NameBody(BaseModel):
    name: str


class ConfirmBody(BaseModel):
    password: str


@app.post("/api/me/profile")
def update_profile(body: ProfileBody, user: dict = Depends(current_user)):
    db().update_profile(user["id"], body.name, body.email)
    return me(db().user(user["id"]))


@app.post("/api/me/password")
def change_password(body: PasswordBody, user: dict = Depends(current_user)):
    db().change_password(user["id"], body.current, body.new)
    return {"ok": True}


@app.post("/api/me/leave")
def leave_workspace(user: dict = Depends(current_user)):
    db().leave_workspace(user["id"])
    return me(db().user(user["id"]))


@app.post("/api/me/delete")
def delete_account(body: ConfirmBody, response: Response, user: dict = Depends(current_user)):
    db().delete_account(user["id"], body.password)
    response.delete_cookie(COOKIE)
    return {"ok": True}


@app.post("/api/workspace/name")
def rename_workspace(body: NameBody, user: dict = Depends(current_user)):
    db().rename_workspace(user["id"], user["workspace_id"], body.name)
    return me(db().user(user["id"]))


@app.post("/api/workspace/invite")
def new_invite(user: dict = Depends(current_user)):
    db().new_invite_code(user["id"], user["workspace_id"])
    return me(db().user(user["id"]))


@app.post("/api/workspace/members/{member_id}/remove")
def remove_member(member_id: str, user: dict = Depends(current_user)):
    db().remove_member(user["id"], user["workspace_id"], member_id)
    return me(db().user(user["id"]))


# ------------------------------------------------------------------ samples
SAMPLES = {
    "northwind": ("Big messy project dump", ROOT / "samples" / "04_northwind" / "notes.txt"),
    "rough-notes": ("Messy notes", ROOT / "samples" / "02_rough_notes" / "notes.txt"),
    "pasted-chat": ("Pasted chat", ROOT / "samples" / "03_pasted_chat" / "chat.txt"),
    "clean-form": ("Clean form", ROOT / "samples" / "01_clean_form" / "input.json"),
}


@app.get("/api/samples")
def samples():
    return [{"key": k, "label": label} for k, (label, p) in SAMPLES.items() if p.exists()]


@app.get("/api/samples/{key}")
def sample(key: str):
    if key not in SAMPLES or not SAMPLES[key][1].exists():
        raise HTTPException(404, "No such sample")
    label, path = SAMPLES[key]
    if path.suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        parts = [f"{k.replace('_', ' ').capitalize()}: {data[k]}" for k in FIELD_KEYS if data.get(k)]
        return {"title": data.get("title", ""), "client": data.get("client_name", ""), "notes": "\n".join(parts)}
    return {"title": "", "client": "", "notes": path.read_text(encoding="utf-8")}


# ------------------------------------------------------------------ files → text preview
@app.post("/api/extract")
async def extract(files: list[UploadFile] = File(...), user: dict = Depends(current_user)):
    out = []
    for f in files:
        data = await f.read()
        if len(data) > MAX_FILE_MB * 1024 * 1024:
            out.append({"name": f.filename, "error": f"Larger than {MAX_FILE_MB} MB."})
        elif is_image(f.filename or ""):
            out.append({"name": f.filename, "image": True})
        else:
            try:
                out.append({"name": f.filename, "text": extract_text(f.filename or "file.txt", data)})
            except IngestError as e:
                out.append({"name": f.filename, "error": str(e)})
    return out


class NotionBody(BaseModel):
    token: str = ""
    url: str = ""


@app.post("/api/notion")
def notion(body: NotionBody, user: dict = Depends(current_user)):
    """A shared Notion page → text for the notes box. The token is used once and never saved or logged."""
    return notion_import(body.token[:200], body.url[:2000])


# ---- Connect Notion (OAuth public integration). Off unless NOTION_CLIENT_ID / NOTION_CLIENT_SECRET are set.
NOTION_STATE_MAX_AGE = 600  # seconds the user has to finish Notion's consent screen


def _notion_settings(request: Request) -> dict:
    s = nt.oauth_settings()
    if not s:
        raise HTTPException(404, "Connect Notion isn't set up on this server. Use an integration secret instead.")
    if not s["redirect_uri"]:
        base = os.getenv("PUBLIC_URL", "").rstrip("/") or str(request.base_url).rstrip("/")
        s["redirect_uri"] = f"{base}/api/notion/callback"
    return s


def _notion_tokens(user: dict) -> tuple[str, str]:
    row = db().notion(user["workspace_id"])
    if not row:
        raise review.ReviewError("Notion isn't connected for this workspace. Click Connect Notion first.")
    access = nt.unseal(row["access_token"], SECRET)
    if not access:  # SECRET_KEY changed since it was stored: the token can't be read any more
        db().drop_notion(user["workspace_id"])
        raise review.ReviewError("The Notion connection needs to be made again. Click Connect Notion.")
    return access, nt.unseal(row["refresh_token"], SECRET)


def _with_notion(request: Request, user: dict, fn):
    """Runs fn(access_token); on an expired token refreshes once, stores the new tokens and retries."""
    access, refresh_token = _notion_tokens(user)
    try:
        return fn(access)
    except nt.TokenRejected:
        try:
            fresh = nt.refresh(refresh_token, _notion_settings(request))
        except nt.NotionError:
            db().drop_notion(user["workspace_id"])
            raise review.ReviewError("The Notion connection expired. Click Connect Notion again.")
        row = db().notion(user["workspace_id"]) or {}
        db().set_notion(user["workspace_id"], row.get("user_id", user["id"]), row.get("notion_workspace", ""),
                        row.get("bot_id", ""), nt.seal(fresh["access_token"], SECRET),
                        nt.seal(fresh.get("refresh_token") or refresh_token, SECRET))
        return fn(fresh["access_token"])


@app.get("/api/notion/connect", include_in_schema=False)
def notion_connect(request: Request, user: dict = Depends(current_user)):
    s = _notion_settings(request)
    state = URLSafeTimedSerializer(SECRET, salt="notion-oauth").dumps(
        {"u": user["id"], "w": user["workspace_id"], "n": secrets.token_hex(8)})
    return RedirectResponse(nt.authorize_url(s["client_id"], s["redirect_uri"], state), status_code=302)


@app.get("/api/notion/callback", include_in_schema=False)
def notion_callback(request: Request, code: str = "", state: str = "", error: str = ""):
    back = "/app?notion={}#new"
    if error:
        return RedirectResponse(back.format("cancelled"), status_code=302)
    try:
        data = URLSafeTimedSerializer(SECRET, salt="notion-oauth").loads(state, max_age=NOTION_STATE_MAX_AGE)
        user = current_user(request)
    except (BadSignature, SignatureExpired, HTTPException):
        return RedirectResponse(back.format("expired"), status_code=302)
    if data.get("u") != user["id"] or data.get("w") != user["workspace_id"] or not code:
        return RedirectResponse(back.format("expired"), status_code=302)
    try:
        tok = nt.exchange_code(code, _notion_settings(request)["redirect_uri"], _notion_settings(request))
    except nt.NotionError:
        return RedirectResponse(back.format("failed"), status_code=302)
    db().set_notion(user["workspace_id"], user["id"], tok.get("workspace_name") or "Notion", tok.get("bot_id", ""),
                    nt.seal(tok["access_token"], SECRET), nt.seal(tok.get("refresh_token", ""), SECRET))
    return RedirectResponse(back.format("connected"), status_code=302)


@app.get("/api/notion/status")
def notion_status(user: dict = Depends(current_user)):
    row = db().notion(user["workspace_id"])
    return {"available": bool(nt.oauth_settings()), "connected": bool(row),
            "workspace": row["notion_workspace"] if row else "",
            "since": row["updated_at"].isoformat() if row else ""}


@app.get("/api/notion/pages")
def notion_pages(request: Request, q: str = "", user: dict = Depends(current_user)):
    return _with_notion(request, user, lambda token: nt.shared_pages(token, q))


class NotionPick(BaseModel):
    id: str


@app.post("/api/notion/import")
def notion_import_connected(body: NotionPick, request: Request, user: dict = Depends(current_user)):
    return _with_notion(request, user, lambda token: notion_import(token, body.id[:100]))


@app.post("/api/notion/disconnect")
def notion_disconnect(user: dict = Depends(current_user)):
    db().drop_notion(user["workspace_id"])
    return {"connected": False}


# ------------------------------------------------------------------ projects
@app.get("/api/projects")
def list_projects(user: dict = Depends(current_user)):
    return db().list_projects(user["workspace_id"])


@app.post("/api/projects")
async def create_project(title: str = Form(""), client_name: str = Form(""), notes: str = Form(""),
                         images: list[UploadFile] = File(default=[]), logo: UploadFile | None = File(default=None),
                         user: dict = Depends(current_user)):
    inp = ProjectInput(title=title.strip()[:200], client_name=client_name.strip()[:200], raw_notes=notes)
    if not inp.source_text().strip():
        raise review.ReviewError("Add some notes or upload a file first.")
    rec = db().create_project(user["workspace_id"], user["id"], inp)
    for f in images:
        data = await f.read()
        if f.filename and is_image(f.filename) and len(data) <= MAX_FILE_MB * 1024 * 1024:
            if not (logo and logo.filename) and not rec.input.logo and "logo" in f.filename.lower():
                rec.input.logo = db().add_image(rec.id, "brandlogo-" + f.filename, data)  # "acme_logo.png" among the files
                continue
            name = db().add_image(rec.id, f.filename, data)
            rec.input.images.append(ImageRef(filename=name, section="results"))
    if logo is not None and logo.filename:
        _save_logo(rec, logo.filename, await logo.read())
    db().save(rec)
    return view(rec, user)


def _save_logo(rec: ProjectRecord, filename: str, data: bytes) -> None:
    if not is_image(filename) or len(data) > 2 * 1024 * 1024:
        raise review.ReviewError("Upload a PNG or JPG logo under 2 MB.")
    try:
        from_logo(data, "check")
    except Exception:
        raise review.ReviewError("Couldn't read that logo — try a PNG or JPG.")
    rec.input.logo = db().add_image(rec.id, "brandlogo-" + filename, data)


@app.post("/api/projects/{project_id}/logo")
async def project_logo(file: UploadFile = File(...), rec: ProjectRecord = Depends(get_project),
                       user: dict = Depends(current_user)):
    """Add or replace this project's logo. A designed report takes the new logo and its colours at once."""
    _save_logo(rec, file.filename or "logo.png", await file.read())
    if rec.report is not None:
        rpt.set_brand(rec, _resolve_brand(user, "auto", rec), user["name"])
    return _done(rec, user)


@app.get("/api/projects/{project_id}")
def get_one(rec: ProjectRecord = Depends(get_project), user: dict = Depends(current_user)):
    return view(rec, user)


@app.delete("/api/projects/{project_id}")
def delete_one(rec: ProjectRecord = Depends(get_project), user: dict = Depends(current_user)):
    db().delete_project(user["workspace_id"], rec.id)
    return {"ok": True}


@app.post("/api/projects/{project_id}/generate")
def generate_one(rec: ProjectRecord = Depends(get_project), user: dict = Depends(current_user)):
    db().use_quota(user["id"], DAILY_LIMIT)
    generate(rec, llm())
    db().save(rec)
    return view(rec, user)


# ------------------------------------------------------------------ review actions
class TextBody(BaseModel):
    text: str = ""
    section: str = ""
    field: str = ""


def _done(rec: ProjectRecord, user: dict) -> dict:
    db().save(rec)
    return view(rec, user)


@app.post("/api/projects/{project_id}/claims/{claim_id}/edit")
def edit_claim(claim_id: str, body: TextBody, rec: ProjectRecord = Depends(get_project),
               user: dict = Depends(current_user)):
    review.edit_claim(rec, claim_id, body.text, llm(), user["name"])
    review.refresh_gaps(rec)
    return _done(rec, user)


@app.post("/api/projects/{project_id}/claims/{claim_id}/delete")
def delete_claim(claim_id: str, rec: ProjectRecord = Depends(get_project), user: dict = Depends(current_user)):
    review.delete_claim(rec, claim_id, user["name"])
    review.refresh_gaps(rec)
    return _done(rec, user)


@app.post("/api/projects/{project_id}/claims/{claim_id}/restore")
def restore_claim(claim_id: str, rec: ProjectRecord = Depends(get_project), user: dict = Depends(current_user)):
    review.restore_claim(rec, claim_id, llm(), user["name"])
    review.refresh_gaps(rec)
    return _done(rec, user)


@app.post("/api/projects/{project_id}/claims/{claim_id}/confirm")
def confirm_claim(claim_id: str, rec: ProjectRecord = Depends(get_project), user: dict = Depends(current_user)):
    c = rec.claim(claim_id)
    review.add_to_source(rec, c.text, llm(), c.section if c.section in FIELD_KEYS else "work_done", user["name"])
    return _done(rec, user)


@app.post("/api/projects/{project_id}/claims")
def add_claim(body: TextBody, rec: ProjectRecord = Depends(get_project), user: dict = Depends(current_user)):
    review.add_claim(rec, body.section, body.text, llm(), user["name"])
    review.refresh_gaps(rec)
    return _done(rec, user)


@app.post("/api/projects/{project_id}/gaps/{gap_id}/resolve")
def resolve_gap(gap_id: str, body: TextBody, rec: ProjectRecord = Depends(get_project),
                user: dict = Depends(current_user)):
    review.resolve_gap(rec, gap_id, body.text or "Left out — not in the notes", user["name"])
    return _done(rec, user)


@app.post("/api/projects/{project_id}/gaps/{gap_id}/add")
def fill_gap(gap_id: str, body: TextBody, rec: ProjectRecord = Depends(get_project),
             user: dict = Depends(current_user)):
    g = rec.gap(gap_id)
    if g.field not in FIELD_KEYS:
        raise review.ReviewError("This one can't be answered with text.")
    review.add_to_source(rec, body.text, llm(), g.field, user["name"])
    review.add_claim(rec, g.field, body.text, llm(), user["name"])
    review.refresh_gaps(rec)
    return _done(rec, user)


@app.post("/api/projects/{project_id}/approve")
def approve(rec: ProjectRecord = Depends(get_project), user: dict = Depends(current_user)):
    review.approve(rec, user["name"])
    return _done(rec, user)


@app.post("/api/projects/{project_id}/reject")
def reject(body: TextBody, rec: ProjectRecord = Depends(get_project), user: dict = Depends(current_user)):
    review.reject(rec, user["name"], body.text)
    return _done(rec, user)


@app.get("/api/projects/{project_id}/images/{filename}")
def image(filename: str, rec: ProjectRecord = Depends(get_project)):
    data = db().image(rec.id, filename)
    if data is None:
        raise HTTPException(404)
    return Response(data, media_type="image/png" if filename.lower().endswith(".png") else "image/jpeg")


# ------------------------------------------------------------------ exports
RENDERERS = {
    "case-study": (render_case_study, "application/pdf", ".pdf"),
    "one-pager": (render_one_pager, "application/pdf", ".pdf"),
    "portfolio": (render_portfolio_page, "text/html", ".html"),
}


@app.get("/api/projects/{project_id}/export/{kind}")
def export(kind: str, draft: bool = False, anonymized: bool = False, rec: ProjectRecord = Depends(get_project),
           user: dict = Depends(current_user)):
    if kind not in RENDERERS:
        raise HTTPException(404)
    fn, mime, ext = RENDERERS[kind]
    target = anon.anonymized(rec) if anonymized else rec
    with tempfile.TemporaryDirectory() as tmp:
        imgs = db().write_images(rec.id, Path(tmp) / "images")
        name = export_name(target, kind, draft).replace(".pdf", ext)
        if anonymized:
            name = name.replace(ext, "_anonymized" + ext)
        path = fn(target, imgs, Path(tmp) / name, draft=draft)
        data = path.read_bytes()
    if not draft:
        rec.log("exported", name, user["name"])
        db().save(rec)
    return Response(data, media_type=mime, headers={"Content-Disposition": f'attachment; filename="{name}"'})


# ------------------------------------------------------------------ extra formats
@app.post("/api/projects/{project_id}/formats/{kind}")
def write_format(kind: str, rec: ProjectRecord = Depends(get_project), user: dict = Depends(current_user)):
    if not review.can_export(rec):
        raise review.ReviewError("Approve the case study first — formats are written only from approved text.")
    db().use_quota(user["id"], DAILY_LIMIT)
    fmt.build_format(rec, kind, llm())
    return _done(rec, user)


class FormatEdit(BaseModel):
    text: str = ""
    delete: bool = False


@app.post("/api/projects/{project_id}/formats/{kind}/{sid}")
def edit_format(kind: str, sid: str, body: FormatEdit, rec: ProjectRecord = Depends(get_project),
                user: dict = Depends(current_user)):
    fmt.edit_format_sentence(rec, kind, sid, body.text, llm(), delete=body.delete)
    return _done(rec, user)


@app.get("/api/projects/{project_id}/formats/{kind}/text")
def format_text(kind: str, rec: ProjectRecord = Depends(get_project)):
    if not fmt.format_ready(rec, kind):
        raise review.ReviewError("Fix the flagged sentences first (or re-write it if the case study changed).")
    sep = "\n\n" if kind == "linkedin" else " "
    return PlainTextResponse(rec.outputs[kind].text(sep))


# ------------------------------------------------------------------ brand kits
def _brand_view(bid: str, name: str, kit: dict, preset: bool, logo: str = "") -> dict:
    k = BrandKit.model_validate(kit)
    return {"id": bid, "name": name, "preset": preset, "kit": k.model_dump(), "logo": logo, "warnings": kit_warnings(k)}


@app.get("/api/brands")
def list_brands(user: dict = Depends(current_user)):
    out = [_brand_view(b["id"], b["name"], {**b["kit"], "logo": b["logo"]}, False, b["logo"])
           for b in db().list_brands(user["workspace_id"])]
    out += [_brand_view(f"preset:{k}", v.name, v.model_dump(), True) for k, v in presets().items()]
    auto = _brand_view("auto", "Auto — your logo, or matched to your notes", auto_brand("", user.get("workspace_name", "")).model_dump(), True)
    return {"brands": [auto] + out, "fonts": list(BUNDLED_FONTS)}


@app.post("/api/brands/from-logo")
async def brand_from_logo(file: UploadFile = File(...), name: str = Form(""), user: dict = Depends(current_user)):
    """The easy way to a brand kit: upload a logo, the colours come from it."""
    data = await file.read()
    if not is_image(file.filename or "") or len(data) > 2 * 1024 * 1024:
        raise review.ReviewError("Upload a PNG or JPG logo under 2 MB.")
    company = name.strip() or user.get("workspace_name", "") or "My company"
    try:
        kit = from_logo(data, company, company)
    except Exception:
        raise review.ReviewError("Couldn't read that image — try a PNG or JPG.")
    bid = db().save_brand(user["workspace_id"], kit.model_dump())
    db().set_brand_logo(user["workspace_id"], bid, file.filename or "logo.png", data)
    return _brand_view(bid, kit.name, kit.model_dump(), False, file.filename or "logo.png")


@app.post("/api/brands")
def save_brand(body: dict, user: dict = Depends(current_user)):
    kit = BrandKit.model_validate(body.get("kit", {}))
    bid = db().save_brand(user["workspace_id"], kit.model_dump(), "" if str(body.get("id", "")).startswith("preset:") else str(body.get("id", "")))
    return {"id": bid}


@app.post("/api/brands/import")
async def import_brand(text: str = Form(""), name: str = Form("Imported brand"),
                       file: UploadFile | None = File(default=None), user: dict = Depends(current_user)):
    content = text
    if file is not None and file.filename:
        content += "\n" + extract_text(file.filename, await file.read())
    if not content.strip():
        raise review.ReviewError("Paste the brand guidelines or upload the guidelines file.")
    model = llm()
    if model:
        db().use_quota(user["id"], DAILY_LIMIT)
    kit = from_guidelines(content, model, name)
    return _brand_view("", kit.name, kit.model_dump(), False)


@app.post("/api/brands/{brand_id}/logo")
async def brand_logo(brand_id: str, file: UploadFile = File(...), user: dict = Depends(current_user)):
    data = await file.read()
    if not is_image(file.filename or "") or len(data) > 2 * 1024 * 1024:
        raise review.ReviewError("Upload a PNG or JPG logo under 2 MB.")
    if not db().brand(user["workspace_id"], brand_id):
        raise HTTPException(404, "Brand not found.")
    db().set_brand_logo(user["workspace_id"], brand_id, file.filename or "logo.png", data)
    return {"ok": True}


@app.delete("/api/brands/{brand_id}")
def delete_brand(brand_id: str, user: dict = Depends(current_user)):
    db().delete_brand(user["workspace_id"], brand_id)
    return {"ok": True}


def _resolve_brand(user: dict, brand_id: str, rec: ProjectRecord) -> BrandKit:
    if brand_id in ("", "auto"):
        # Auto = the company's own look when there is a logo, else a palette matched to the notes.
        company = publisher(user.get("workspace_name", ""))
        base = auto_brand(rec.input.source_text(), company)
        data = db().image(rec.id, rec.input.logo) if rec.input.logo else None
        if data:                       # 1. the logo uploaded with this project: colours come from it
            try:
                kit = from_logo(data, f"{company or 'Your company'} · from your logo", company)
            except Exception:
                return base
            kit.heading_font, kit.body_font, kit.motif = base.heading_font, base.body_font, base.motif
            kit.logo = rec.input.logo
            return kit
        for b in db().list_brands(user["workspace_id"]):   # 2. the workspace's newest brand kit with a logo
            if b["logo"]:
                full = db().brand(user["workspace_id"], b["id"])
                kit = BrandKit.model_validate(full["kit"])
                if full["logo_data"]:
                    kit.logo = db().add_image(rec.id, f"logo-{b['id']}-{b['logo']}", full["logo_data"])
                return kit
        return base                    # 3. no logo anywhere: matched to what the notes are about
    if brand_id.startswith("preset:"):
        p = presets().get(brand_id.split(":", 1)[1])
        if not p:
            raise HTTPException(404, "Brand not found.")
        return p
    b = db().brand(user["workspace_id"], brand_id)
    if not b:
        raise HTTPException(404, "Brand not found.")
    kit = BrandKit.model_validate(b["kit"])
    if b["logo_data"]:  # the logo travels with the project so the report renders on its own
        kit.logo = db().add_image(rec.id, f"logo-{b['id']}-{b['logo']}", b["logo_data"])
    return kit


# ------------------------------------------------------------------ proof library
class SheetBody(BaseModel):
    q: str = ""
    picks: dict[str, list[str]] = {}
    anonymized: bool = False


def _workspace_records(user: dict) -> list[ProjectRecord]:
    out = []
    for p in db().list_projects(user["workspace_id"]):
        if p["status"] == "approved":
            r = db().load(user["workspace_id"], p["id"])
            if r:
                out.append(r)
    return out


def _sheet_links(request: Request, recs: list[ProjectRecord], anonymized: bool) -> dict[str, str]:
    """Each case study's live Verified link for the approved version, named or anonymized to match the sheet."""
    out = {}
    for r in recs:
        hide = anonymized or r.client_signoff.get("decision") == "anonymous"
        for x in db().published_for(r.workspace_id, r.id):
            if x["revoked"] or x["hash"] != r.approved_hash:
                continue
            if (hide and (x["anonymized"] or (not x["show_client"] and not r.anon_map))) or (not hide and not x["anonymized"]):
                out[r.id] = _public_url(request, x["token"])
                break
    return out


def _sheet(request: Request, body: SheetBody, user: dict) -> dict:
    recs = _workspace_records(user)
    s = lib.sheet(recs, body.q, body.picks or None, body.anonymized, _sheet_links(request, recs, body.anonymized))
    if not s["projects"]:
        raise review.ReviewError("Nothing to put on the sheet. Search for something your approved case studies cover.")
    return s


@app.get("/api/library")
def library(q: str = "", user: dict = Depends(current_user)):
    recs = _workspace_records(user)
    return {"q": q, "results": lib.search(recs, q[:300]), "n_approved": len(recs)}


@app.post("/api/library/sheet")
def library_sheet(body: SheetBody, request: Request, user: dict = Depends(current_user)):
    s = _sheet(request, body, user)
    return {**s, "text": lib.sheet_text(s)}


@app.post("/api/library/sheet/view")
def library_sheet_view(body: SheetBody, request: Request, user: dict = Depends(current_user)):
    return Response(proof_sheet_html(_sheet(request, body, user), publisher(user.get("workspace_name", ""))), media_type="text/html")


@app.post("/api/library/sheet/pdf")
def library_sheet_pdf(body: SheetBody, request: Request, user: dict = Depends(current_user)):
    from caseforge.render.report_pdf import html_to_pdf
    html = proof_sheet_html(_sheet(request, body, user), publisher(user.get("workspace_name", "")))
    with tempfile.TemporaryDirectory() as tmp:
        out = html_to_pdf(html, Path(tmp) / "proof-sheet.pdf")
        data = out.read_bytes()
    return Response(data, media_type="application/pdf",
                    headers={"Content-Disposition": 'attachment; filename="proof-sheet.pdf"'})


# ------------------------------------------------------------------ anonymized version
class SwapsBody(BaseModel):
    swaps: list[dict] = []


def _anon_view(rec: ProjectRecord) -> dict:
    saved = {t.lower() for t, _ in rec.anon_map}
    rows = [{"term": t, "replace": r, "kind": "saved", "on": True} for t, r in rec.anon_map]
    rows += [s for s in anon.suggest(rec) if s["term"].lower() not in saved] if review.can_export(rec) else []
    preview = []
    if rec.anon_map:
        for c in rec.active_claims():
            new = anon.apply(c.text, rec.anon_map)
            if new != c.text:
                preview.append({"id": c.id, "before": c.text, "after": new})
    texts = [anon.apply(x, rec.anon_map) for x in [rec.input.title] + [c.text for c in rec.active_claims()]]
    return {"swaps": rows, "preview": preview, "saved": bool(rec.anon_map),
            "left": anon.leftovers(texts, rec.anon_map) if rec.anon_map else [],
            "client_wants_anonymous": rec.client_signoff.get("decision") == "anonymous",
            "has_images": bool(rec.input.images or rec.input.logo)}


@app.get("/api/projects/{project_id}/anon")
def get_anon(rec: ProjectRecord = Depends(get_project), user: dict = Depends(current_user)):
    return _anon_view(rec)


@app.post("/api/projects/{project_id}/anon")
def save_anon(body: SwapsBody, rec: ProjectRecord = Depends(get_project), user: dict = Depends(current_user)):
    rec.anon_map = anon.clean([s for s in body.swaps if s.get("on", True)])
    rec.log("anonymized version set", f"{len(rec.anon_map)} name swaps", user["name"])
    db().save(rec)
    return _anon_view(rec)


def _anon_link(request: Request, rec: ProjectRecord) -> str:
    """The newest live anonymized Verified link for the approved version (for the anonymized PDF's QR)."""
    if not review.can_export(rec):
        return ""
    for token, copy_ in ((x["token"], db().published_copy(x["token"])) for x in db().published_for(rec.workspace_id, rec.id)
                         if not x["revoked"] and x["hash"] == rec.approved_hash):
        if copy_ and copy_[0].get("anon"):
            return _public_url(request, token)
    return ""


# ------------------------------------------------------------------ verified links
class PublishBody(BaseModel):
    evidence: str = "full"     # full · masked · labels
    show_client: bool = True
    anonymized: bool = False   # swap the client and people's names (anonymized version)


def _public_url(request: Request, token: str) -> str:
    base = os.getenv("PUBLIC_URL", "").rstrip("/") or str(request.base_url).rstrip("/")
    return f"{base}/v/{token}"


def _links(request: Request, rec: ProjectRecord, user: dict) -> list[dict]:
    out = db().published_for(user["workspace_id"], rec.id)
    for x in out:
        x["url"] = _public_url(request, x["token"])
        x["current"] = x["hash"] == rec.approved_hash and review.can_export(rec)
        del x["hash"]
    return out


@app.get("/api/projects/{project_id}/published")
def list_published(request: Request, rec: ProjectRecord = Depends(get_project), user: dict = Depends(current_user)):
    return _links(request, rec, user)


@app.post("/api/projects/{project_id}/publish")
def publish(body: PublishBody, request: Request, rec: ProjectRecord = Depends(get_project),
            user: dict = Depends(current_user)):
    copy = vf.snapshot(rec, body.evidence, body.show_client, body.anonymized)
    token = vf.new_token()
    db().publish(user["workspace_id"], rec.id, token, copy)
    rec.log("verified link published", f"{token} · evidence {body.evidence}"
            + (" · anonymized" if body.anonymized else "" if body.show_client else " · client hidden"), user["name"])
    db().save(rec)
    return _links(request, rec, user)


@app.post("/api/projects/{project_id}/published/{token}/revoke")
def revoke(token: str, request: Request, rec: ProjectRecord = Depends(get_project), user: dict = Depends(current_user)):
    if not db().revoke(user["workspace_id"], token):
        raise HTTPException(404, "Link not found.")
    rec.log("verified link revoked", token, user["name"])
    db().save(rec)
    return _links(request, rec, user)


def _live(token: str):
    found = db().published_copy(token) if len(token) <= 20 else None
    if not found:
        return None
    copy, ws, pid = found
    rec = db().load(ws, pid)
    return copy, (rec.content_hash() if rec else None)


def _current_link(request: Request, rec: ProjectRecord) -> str:
    """The newest live Verified link for exactly the approved version, for the QR in the PDF."""
    if not review.can_export(rec):
        return ""
    for x in db().published_for(rec.workspace_id, rec.id):
        if not x["revoked"] and x["hash"] == rec.approved_hash and not x.get("anonymized"):
            return _public_url(request, x["token"])
    return ""


@app.get("/v/{token}", include_in_schema=False)
def verified(token: str):
    found = _live(token)
    if not found:
        return Response(GONE, status_code=404, media_type="text/html")
    db().count_view(token)
    html = verified_page(vf.public_view(*found))
    return Response(html, media_type="text/html", headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex"})


@app.post("/v/{token}/check", include_in_schema=False)
def verified_check(token: str):
    db().count_view(token, "checks")
    return Response(status_code=204)


@app.get("/v/{token}/qr.svg", include_in_schema=False)
def verified_qr(token: str, request: Request):
    if not db().published_copy(token):
        raise HTTPException(404)
    return Response(qr_svg(_public_url(request, token), standalone=True), media_type="image/svg+xml")


# ------------------------------------------------------------------ client sign-off
class SignoffBody(BaseModel):
    contact: str = ""


class ClientAnswers(BaseModel):
    answers: dict = {}
    decision: str = ""
    signed_by: str = ""


def _signoff_url(request: Request, token: str) -> str:
    base = os.getenv("PUBLIC_URL", "").rstrip("/") or str(request.base_url).rstrip("/")
    return f"{base}/s/{token}"


def _signoffs(request: Request, rec: ProjectRecord, user: dict) -> list[dict]:
    live = rec.content_hash() if review.can_export(rec) else None
    out = []
    for token, req in db().signoffs_for(user["workspace_id"], rec.id):
        claims = {c.id: c for c in rec.claims}
        rows = []
        for it in req["items"]:
            a = req["answers"].get(it["id"], {})
            c = claims.get(it["id"])
            applied = bool(c and ((a.get("action") == "remove" and c.deleted)
                                  or (a.get("action") == "fix" and c.text == a.get("text"))))
            rows.append({"id": it["id"], "text": it["text"], "action": a.get("action", ""),
                         "suggestion": a.get("text", ""), "applied": applied})
        out.append({"token": token, "url": _signoff_url(request, token), "state": so.state(req, live),
                    "contact": req.get("contact", ""), "created_at": req["created_at"], "expires_at": req["expires_at"],
                    "signed_by": req.get("signed_by", ""), "decision": req.get("decision", ""),
                    "submitted_at": req.get("submitted_at", ""), "items": rows})
    return out


@app.get("/api/projects/{project_id}/signoffs")
def list_signoffs(request: Request, rec: ProjectRecord = Depends(get_project), user: dict = Depends(current_user)):
    return _signoffs(request, rec, user)


@app.post("/api/projects/{project_id}/signoff")
def ask_client(body: SignoffBody, request: Request, rec: ProjectRecord = Depends(get_project),
               user: dict = Depends(current_user)):
    req = so.request(rec, body.contact)
    token = so.new_token()
    db().add_signoff(user["workspace_id"], rec.id, token, req)
    rec.log("client sign-off requested", f"{len(req['items'])} items" + (f" · {req['contact']}" if req["contact"] else ""),
            user["name"])
    db().save(rec)
    return _signoffs(request, rec, user)


@app.delete("/api/projects/{project_id}/signoffs/{token}")
def cancel_signoff(token: str, request: Request, rec: ProjectRecord = Depends(get_project),
                   user: dict = Depends(current_user)):
    if not db().delete_signoff(user["workspace_id"], token):
        raise HTTPException(404, "Sign-off link not found.")
    return _signoffs(request, rec, user)


@app.post("/api/projects/{project_id}/signoffs/{token}/use/{claim_id}")
def use_client_suggestion(token: str, claim_id: str, rec: ProjectRecord = Depends(get_project),
                          user: dict = Depends(current_user)):
    found = db().signoff(token)
    if not found or found[2] != rec.id or found[1] != user["workspace_id"]:
        raise HTTPException(404, "Sign-off not found.")
    model = llm()
    if model and found[0]["answers"].get(claim_id, {}).get("action") == "fix":
        db().use_quota(user["id"], DAILY_LIMIT)
    so.use_suggestion(rec, found[0], claim_id, model, user["name"])
    return _done(rec, user)


def _client_request(token: str):
    found = db().signoff(token) if len(token) <= 24 else None
    if not found:
        return None
    req, ws, pid = found
    rec = db().load(ws, pid)
    live = rec.content_hash() if rec and review.can_export(rec) else None
    return req, rec, so.state(req, live)


@app.get("/s/{token}", include_in_schema=False)
def client_page(token: str):
    found = _client_request(token)
    if not found:
        return Response(GONE, status_code=404, media_type="text/html")
    req, _, st = found
    return Response(signoff_page(req, st), media_type="text/html",
                    headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex"})


@app.post("/s/{token}", include_in_schema=False)
def client_submit(token: str, body: ClientAnswers):
    found = _client_request(token)
    if not found:
        raise HTTPException(404, "This link isn't available.")
    req, rec, st = found
    if st != "open":
        raise HTTPException(409, {"answered": "These answers were already sent. Thank you.",
                                  "expired": "This link has expired. Ask the team for a new one.",
                                  "changed": "The team changed the case study since sending this link. Ask them for a new one."}[st])
    req = so.submit(req, body.answers, body.decision, body.signed_by)
    db().save_signoff(token, req)
    if rec:
        so.apply_answers(rec, req)
        db().save(rec)
    return {"ok": True}


# ------------------------------------------------------------------ designed report
class DesignBody(BaseModel):
    brand_id: str = "auto"
    keep_text: bool = False     # Redesign: a new look for the same checked wording (no AI call)


class ChatBody(BaseModel):
    text: str


class ElementBody(BaseModel):
    path: str
    text: str = ""
    estimate: bool = False


@app.post("/api/projects/{project_id}/report")
def design_report(body: DesignBody, rec: ProjectRecord = Depends(get_project), user: dict = Depends(current_user)):
    if not review.can_export(rec):
        raise review.ReviewError("Approve the case study first — the report is designed only from approved text.")
    d = rec.report
    if body.keep_text and d and d.based_on_hash == rec.approved_hash and not d.blocking:
        rpt.redesign(rec, user["name"])
        return _done(rec, user)
    kit = _resolve_brand(user, body.brand_id, rec)
    db().use_quota(user["id"], DAILY_LIMIT)
    rpt.build_report(rec, kit, llm())
    return _done(rec, user)


@app.post("/api/projects/{project_id}/report/brand")
def report_brand(body: DesignBody, rec: ProjectRecord = Depends(get_project), user: dict = Depends(current_user)):
    """Switch the brand of the designed report: same content and layout, new look — no AI call."""
    rpt.set_brand(rec, _resolve_brand(user, body.brand_id, rec), user["name"])
    return _done(rec, user)


@app.post("/api/projects/{project_id}/report/chat")
def report_chat(body: ChatBody, rec: ProjectRecord = Depends(get_project), user: dict = Depends(current_user)):
    model = llm()
    if model:
        db().use_quota(user["id"], DAILY_LIMIT)
    rpt.chat_report(rec, body.text, model, user["name"])
    return _done(rec, user)


@app.post("/api/projects/{project_id}/report/edit")
def edit_report(body: ElementBody, rec: ProjectRecord = Depends(get_project), user: dict = Depends(current_user)):
    rpt.edit_element(rec, body.path, body.text, llm(), user["name"])
    return _done(rec, user)


@app.post("/api/projects/{project_id}/report/remove")
def remove_report_element(body: ElementBody, rec: ProjectRecord = Depends(get_project),
                          user: dict = Depends(current_user)):
    rpt.remove_element(rec, body.path, user["name"])
    return _done(rec, user)


@app.post("/api/projects/{project_id}/report/estimate")
def mark_estimate(body: ElementBody, rec: ProjectRecord = Depends(get_project), user: dict = Depends(current_user)):
    rpt.set_metric_estimate(rec, int(body.path.split(".")[-1]), body.estimate, llm(), user["name"])
    return _done(rec, user)


@app.post("/api/projects/{project_id}/report/approve")
def approve_report(rec: ProjectRecord = Depends(get_project), user: dict = Depends(current_user)):
    rpt.approve_report(rec, user["name"])
    return _done(rec, user)


@app.get("/api/projects/{project_id}/report/preview")
def report_preview(request: Request, anonymized: bool = False, rec: ProjectRecord = Depends(get_project)):
    from caseforge.render.report_pdf import report_html
    if rec.report is None:
        raise HTTPException(404, "Design the report first.")
    with tempfile.TemporaryDirectory() as tmp:
        imgs = db().write_images(rec.id, Path(tmp))
        target = anon.anonymized(rec) if anonymized else rec
        html = report_html(target, target.report, imgs, draft=not rpt.report_ready(target),
                           verify_url="" if anonymized else _current_link(request, rec))
    # on screen: grey desk, pages scaled to the frame width (print/PDF untouched)
    fit = ("<style>@media screen{html{background:#e9e9e6}body{margin:0}.page{margin:0 auto 18px;"
           "box-shadow:0 6px 24px rgba(0,0,0,.18)}}</style><script>(function(){function z(){"
           "if(document.body.dataset.ready!=='1')return setTimeout(z,50);"
           "document.documentElement.style.zoom=Math.min(1,(innerWidth-24)/document.querySelector('.page').offsetWidth);}"
           "addEventListener('load',z);addEventListener('resize',z);})();</script>")
    return Response(html.replace("</body>", fit + "</body>"), media_type="text/html")


@app.get("/api/projects/{project_id}/report/pdf")
def report_pdf(request: Request, draft: bool = False, anonymized: bool = False,
               rec: ProjectRecord = Depends(get_project), user: dict = Depends(current_user)):
    from caseforge.render.report_pdf import render_report
    with tempfile.TemporaryDirectory() as tmp:
        imgs = db().write_images(rec.id, Path(tmp) / "img")
        name = f"{rec.id}_report{'_anonymized' if anonymized else ''}{'_DRAFT' if draft else ''}.pdf"
        target = anon.anonymized(rec) if anonymized else rec
        data = render_report(target, Path(tmp) / name, imgs, draft=draft,
                             verify_url=_anon_link(request, rec) if anonymized else _current_link(request, rec)).read_bytes()
    if not draft:
        rec.log("report exported", name, user["name"])
        db().save(rec)
    return Response(data, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{name}"'})
