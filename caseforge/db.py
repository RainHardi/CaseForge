"""Database store for the website: accounts, workspaces, projects, images, daily usage.

SQLite on a laptop, Postgres (e.g. Neon free tier) when hosted — set DATABASE_URL.
Free hosts wipe local files on every restart, so nothing the website needs is kept on disk.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy import (
    Column, Date, DateTime, ForeignKey, Integer, LargeBinary, MetaData, String, Table, Text,
    UniqueConstraint, create_engine, delete, func, insert, select, update,
)
from sqlalchemy.engine import Engine

from .config import ROOT
from .models import ProjectInput, ProjectRecord

meta = MetaData()

workspaces = Table(
    "workspaces", meta,
    Column("id", String(40), primary_key=True),
    Column("name", String(120), nullable=False),
    Column("invite_code", String(20), unique=True, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)
users = Table(
    "users", meta,
    Column("id", String(40), primary_key=True),
    Column("email", String(254), unique=True, nullable=False),
    Column("name", String(120), nullable=False),
    Column("password_hash", String(300), nullable=False),
    Column("workspace_id", String(40), ForeignKey("workspaces.id"), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)
projects = Table(
    "projects", meta,
    Column("id", String(80), primary_key=True),
    Column("workspace_id", String(40), ForeignKey("workspaces.id"), nullable=False, index=True),
    Column("title", String(300), nullable=False, default=""),
    Column("status", String(20), nullable=False, default="input"),
    Column("record", Text, nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)
images = Table(
    "images", meta,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("project_id", String(80), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("filename", String(200), nullable=False),
    Column("data", LargeBinary, nullable=False),
    UniqueConstraint("project_id", "filename"),
)
brand_kits = Table(
    "brand_kits", meta,
    Column("id", String(40), primary_key=True),
    Column("workspace_id", String(40), ForeignKey("workspaces.id"), nullable=False, index=True),
    Column("name", String(120), nullable=False),
    Column("kit", Text, nullable=False),
    Column("logo_name", String(200), nullable=False, default=""),
    Column("logo_data", LargeBinary, nullable=True),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)
published = Table(
    "published", meta,
    Column("token", String(20), primary_key=True),
    Column("project_id", String(80), nullable=False, index=True),
    Column("workspace_id", String(40), ForeignKey("workspaces.id"), nullable=False, index=True),
    Column("copy", Text, nullable=False),  # the frozen approved case study (caseforge.verify.snapshot)
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("revoked", Integer, nullable=False, default=0),
    Column("views", Integer, nullable=False, default=0),
    Column("checks", Integer, nullable=False, default=0),  # sentences readers opened the evidence for
)
signoffs = Table(
    "signoffs", meta,
    Column("token", String(24), primary_key=True),
    Column("project_id", String(80), nullable=False, index=True),
    Column("workspace_id", String(40), ForeignKey("workspaces.id"), nullable=False, index=True),
    Column("data", Text, nullable=False),  # the request and the client's answers (caseforge.signoff)
    Column("created_at", DateTime(timezone=True), nullable=False),
)
usage = Table(
    "ai_usage", meta,
    Column("user_id", String(40), primary_key=True),
    Column("day", Date, primary_key=True),
    Column("count", Integer, nullable=False, default=0),
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def database_url() -> str:
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        (ROOT / "data").mkdir(exist_ok=True)
        return f"sqlite:///{ROOT / 'data' / 'caseforge.db'}"
    # Neon / Render give postgres:// or postgresql:// — tell SQLAlchemy to use psycopg 3
    return re.sub(r"^postgres(ql)?://", "postgresql+psycopg://", url)


# ------------------------------------------------------------------ passwords (stdlib scrypt)
def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, salt_hex, digest_hex = stored.split("$")
        digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), n=2**14, r=8, p=1, dklen=32)
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


class AuthError(ValueError):
    pass


class DB:
    def __init__(self, url: str | None = None):
        url = url or database_url()
        kwargs = {"pool_pre_ping": True}
        if url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False}
        self.engine: Engine = create_engine(url, **kwargs)
        meta.create_all(self.engine)

    # -------------------------------------------------------------- accounts
    def signup(self, name: str, email: str, password: str, company: str = "", invite_code: str = "") -> dict:
        email = email.strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            raise AuthError("Enter a valid email address.")
        if len(password) < 8:
            raise AuthError("Password must be at least 8 characters.")
        if not name.strip():
            raise AuthError("Enter your name.")
        with self.engine.begin() as c:
            if c.execute(select(users.c.id).where(users.c.email == email)).first():
                raise AuthError("An account with this email already exists. Log in instead.")
            if invite_code.strip():
                ws = c.execute(select(workspaces).where(workspaces.c.invite_code == invite_code.strip().upper())).first()
                if not ws:
                    raise AuthError("That invite code doesn't exist. Check it with your teammate.")
                ws_id = ws.id
            else:
                ws_id = uuid.uuid4().hex[:12]
                c.execute(insert(workspaces).values(
                    id=ws_id, name=(company.strip() or f"{name.strip().split()[0]}'s workspace")[:120],
                    invite_code=secrets.token_hex(4).upper(), created_at=_now()))
            uid = uuid.uuid4().hex[:12]
            c.execute(insert(users).values(id=uid, email=email, name=name.strip()[:120],
                                           password_hash=hash_password(password), workspace_id=ws_id,
                                           created_at=_now()))
        return self.user(uid)

    def login(self, email: str, password: str) -> dict:
        with self.engine.connect() as c:
            row = c.execute(select(users).where(users.c.email == email.strip().lower())).first()
        if not row or not verify_password(password, row.password_hash):
            raise AuthError("Wrong email or password.")
        return self.user(row.id)

    def user(self, uid: str) -> dict | None:
        with self.engine.connect() as c:
            row = c.execute(
                select(users.c.id, users.c.email, users.c.name, users.c.workspace_id,
                       workspaces.c.name.label("workspace_name"), workspaces.c.invite_code)
                .join(workspaces, users.c.workspace_id == workspaces.c.id).where(users.c.id == uid)
            ).first()
        return dict(row._mapping) if row else None

    def members(self, workspace_id: str) -> list[dict]:
        """The first person in a workspace owns it. When they leave, the next oldest member takes over."""
        with self.engine.connect() as c:
            rows = c.execute(select(users.c.id, users.c.name, users.c.email, users.c.created_at)
                             .where(users.c.workspace_id == workspace_id).order_by(users.c.created_at)).all()
        return [{"id": r.id, "name": r.name, "email": r.email, "owner": i == 0,
                 "joined": r.created_at.isoformat()} for i, r in enumerate(rows)]

    def is_owner(self, uid: str, workspace_id: str) -> bool:
        m = self.members(workspace_id)
        return bool(m) and m[0]["id"] == uid

    # -------------------------------------------------------------- account settings
    def update_profile(self, uid: str, name: str, email: str) -> dict:
        name, email = name.strip(), email.strip().lower()
        if not name:
            raise AuthError("Enter your name.")
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            raise AuthError("Enter a valid email address.")
        with self.engine.begin() as c:
            if c.execute(select(users.c.id).where(users.c.email == email, users.c.id != uid)).first():
                raise AuthError("Another account already uses this email.")
            c.execute(update(users).where(users.c.id == uid).values(name=name[:120], email=email))
        return self.user(uid)

    def change_password(self, uid: str, current: str, new: str) -> None:
        with self.engine.begin() as c:
            row = c.execute(select(users.c.password_hash).where(users.c.id == uid)).first()
            if not row or not verify_password(current, row.password_hash):
                raise AuthError("Your current password is wrong.")
            if len(new) < 8:
                raise AuthError("New password must be at least 8 characters.")
            c.execute(update(users).where(users.c.id == uid).values(password_hash=hash_password(new)))

    def rename_workspace(self, uid: str, workspace_id: str, name: str) -> None:
        if not self.is_owner(uid, workspace_id):
            raise AuthError("Only the workspace owner can rename it.")
        if not name.strip():
            raise AuthError("Enter a workspace name.")
        with self.engine.begin() as c:
            c.execute(update(workspaces).where(workspaces.c.id == workspace_id).values(name=name.strip()[:120]))

    def new_invite_code(self, uid: str, workspace_id: str) -> str:
        """Old code stops working, so a leaked code can be shut off."""
        if not self.is_owner(uid, workspace_id):
            raise AuthError("Only the workspace owner can change the invite code.")
        code = secrets.token_hex(4).upper()
        with self.engine.begin() as c:
            c.execute(update(workspaces).where(workspaces.c.id == workspace_id).values(invite_code=code))
        return code

    def _solo_workspace(self, c, uid: str, name: str) -> None:
        ws_id = uuid.uuid4().hex[:12]
        c.execute(insert(workspaces).values(id=ws_id, name=f"{name}'s workspace"[:120],
                                            invite_code=secrets.token_hex(4).upper(), created_at=_now()))
        c.execute(update(users).where(users.c.id == uid).values(workspace_id=ws_id))

    def leave_workspace(self, uid: str) -> None:
        """Moves you to a fresh empty workspace. The team keeps its case studies."""
        u = self.user(uid)
        if len(self.members(u["workspace_id"])) < 2:
            raise AuthError("You're the only member, so there's nothing to leave.")
        with self.engine.begin() as c:
            self._solo_workspace(c, uid, u["name"])

    def remove_member(self, owner_uid: str, workspace_id: str, member_id: str) -> None:
        if not self.is_owner(owner_uid, workspace_id):
            raise AuthError("Only the workspace owner can remove people.")
        if member_id == owner_uid:
            raise AuthError("You can't remove yourself. Delete your account instead.")
        target = self.user(member_id)
        if not target or target["workspace_id"] != workspace_id:
            raise AuthError("That person isn't in this workspace.")
        with self.engine.begin() as c:
            self._solo_workspace(c, member_id, target["name"])

    def delete_account(self, uid: str, password: str) -> None:
        """Deletes the account. If you were the last member, the workspace and its case studies go too."""
        with self.engine.begin() as c:
            row = c.execute(select(users.c.password_hash, users.c.workspace_id).where(users.c.id == uid)).first()
            if not row or not verify_password(password, row.password_hash):
                raise AuthError("Wrong password.")
            ws = row.workspace_id
            c.execute(delete(usage).where(usage.c.user_id == uid))
            c.execute(delete(users).where(users.c.id == uid))
            if not c.execute(select(users.c.id).where(users.c.workspace_id == ws)).first():
                ids = [r.id for r in c.execute(select(projects.c.id).where(projects.c.workspace_id == ws))]
                if ids:
                    c.execute(delete(images).where(images.c.project_id.in_(ids)))
                    c.execute(delete(projects).where(projects.c.id.in_(ids)))
                c.execute(delete(brand_kits).where(brand_kits.c.workspace_id == ws))
                c.execute(delete(published).where(published.c.workspace_id == ws))
                c.execute(delete(signoffs).where(signoffs.c.workspace_id == ws))
                c.execute(delete(workspaces).where(workspaces.c.id == ws))

    # -------------------------------------------------------------- usage limit
    def use_quota(self, uid: str, limit: int) -> int:
        """Counts one AI action for today. Raises when the daily limit is reached. Returns uses left."""
        today = date.today()
        with self.engine.begin() as c:
            row = c.execute(select(usage.c.count).where(usage.c.user_id == uid, usage.c.day == today)).first()
            used = row.count if row else 0
            if used >= limit:
                raise AuthError(f"Daily limit of {limit} AI actions reached. It resets tomorrow.")
            if row:
                c.execute(update(usage).where(usage.c.user_id == uid, usage.c.day == today).values(count=used + 1))
            else:
                c.execute(insert(usage).values(user_id=uid, day=today, count=1))
        return limit - used - 1

    def quota_left(self, uid: str, limit: int) -> int:
        with self.engine.connect() as c:
            row = c.execute(select(usage.c.count).where(usage.c.user_id == uid, usage.c.day == date.today())).first()
        return max(0, limit - (row.count if row else 0))

    # -------------------------------------------------------------- projects (scoped to a workspace)
    def create_project(self, workspace_id: str, user_id: str, inp: ProjectInput) -> ProjectRecord:
        slug = re.sub(r"[^a-z0-9]+", "-", (inp.title or "project").lower()).strip("-")[:40] or "project"
        rec = ProjectRecord(id=f"{slug}-{uuid.uuid4().hex[:6]}", input=inp, workspace_id=workspace_id,
                            created_by=user_id)
        rec.log("created", by=user_id)
        with self.engine.begin() as c:
            c.execute(insert(projects).values(id=rec.id, workspace_id=workspace_id, title=inp.title or "",
                                              status=rec.status, record=rec.model_dump_json(), updated_at=_now()))
        return rec

    def save(self, rec: ProjectRecord) -> None:
        with self.engine.begin() as c:
            c.execute(update(projects).where(projects.c.id == rec.id, projects.c.workspace_id == rec.workspace_id)
                      .values(title=rec.input.title or "", status=rec.status, record=rec.model_dump_json(),
                              updated_at=_now()))

    def load(self, workspace_id: str, project_id: str) -> ProjectRecord | None:
        with self.engine.connect() as c:
            row = c.execute(select(projects.c.record).where(
                projects.c.id == project_id, projects.c.workspace_id == workspace_id)).first()
        return ProjectRecord.model_validate_json(row.record) if row else None

    def list_projects(self, workspace_id: str) -> list[dict]:
        with self.engine.connect() as c:
            rows = c.execute(select(projects.c.id, projects.c.title, projects.c.status, projects.c.updated_at)
                             .where(projects.c.workspace_id == workspace_id)
                             .order_by(projects.c.updated_at.desc())).all()
        return [{"id": r.id, "title": r.title, "status": r.status, "updated_at": r.updated_at.isoformat()}
                for r in rows]

    def delete_project(self, workspace_id: str, project_id: str) -> None:
        with self.engine.begin() as c:
            if c.execute(select(projects.c.id).where(projects.c.id == project_id,
                                                     projects.c.workspace_id == workspace_id)).first():
                c.execute(delete(images).where(images.c.project_id == project_id))
                c.execute(delete(published).where(published.c.project_id == project_id))
                c.execute(delete(signoffs).where(signoffs.c.project_id == project_id))
                c.execute(delete(projects).where(projects.c.id == project_id))

    # -------------------------------------------------------------- images
    def add_image(self, project_id: str, filename: str, data: bytes) -> str:
        name = re.sub(r"[^\w.\-]", "_", filename)[:150] or "image.png"
        with self.engine.begin() as c:
            c.execute(delete(images).where(images.c.project_id == project_id, images.c.filename == name))
            c.execute(insert(images).values(project_id=project_id, filename=name, data=data))
        return name

    def image(self, project_id: str, filename: str) -> bytes | None:
        with self.engine.connect() as c:
            row = c.execute(select(images.c.data).where(images.c.project_id == project_id,
                                                        images.c.filename == filename)).first()
        return bytes(row.data) if row else None

    def write_images(self, project_id: str, folder: Path) -> Path:
        """Renderers read images from a folder: write this project's images into a temp folder."""
        folder.mkdir(parents=True, exist_ok=True)
        with self.engine.connect() as c:
            for r in c.execute(select(images.c.filename, images.c.data).where(images.c.project_id == project_id)):
                (folder / r.filename).write_bytes(bytes(r.data))
        return folder

    # -------------------------------------------------------------- brand kits (per workspace)
    def list_brands(self, workspace_id: str) -> list[dict]:
        with self.engine.connect() as c:
            rows = c.execute(select(brand_kits.c.id, brand_kits.c.name, brand_kits.c.kit, brand_kits.c.logo_name)
                             .where(brand_kits.c.workspace_id == workspace_id).order_by(brand_kits.c.updated_at.desc())).all()
        return [{"id": r.id, "name": r.name, "kit": json.loads(r.kit), "logo": r.logo_name} for r in rows]

    def save_brand(self, workspace_id: str, kit: dict, brand_id: str = "") -> str:
        with self.engine.begin() as c:
            if brand_id and c.execute(select(brand_kits.c.id).where(brand_kits.c.id == brand_id,
                                                                   brand_kits.c.workspace_id == workspace_id)).first():
                c.execute(update(brand_kits).where(brand_kits.c.id == brand_id)
                          .values(name=kit.get("name", "Brand")[:120], kit=json.dumps(kit), updated_at=_now()))
                return brand_id
            bid = uuid.uuid4().hex[:12]
            c.execute(insert(brand_kits).values(id=bid, workspace_id=workspace_id, name=kit.get("name", "Brand")[:120],
                                                kit=json.dumps(kit), logo_name="", updated_at=_now()))
            return bid

    def brand(self, workspace_id: str, brand_id: str) -> dict | None:
        with self.engine.connect() as c:
            r = c.execute(select(brand_kits).where(brand_kits.c.id == brand_id,
                                                   brand_kits.c.workspace_id == workspace_id)).first()
        if not r:
            return None
        return {"id": r.id, "name": r.name, "kit": json.loads(r.kit), "logo": r.logo_name,
                "logo_data": bytes(r.logo_data) if r.logo_data else None}

    def set_brand_logo(self, workspace_id: str, brand_id: str, filename: str, data: bytes) -> None:
        name = re.sub(r"[^\w.\-]", "_", filename)[:150]
        with self.engine.begin() as c:
            c.execute(update(brand_kits).where(brand_kits.c.id == brand_id, brand_kits.c.workspace_id == workspace_id)
                      .values(logo_name=name, logo_data=data, updated_at=_now()))

    def delete_brand(self, workspace_id: str, brand_id: str) -> None:
        with self.engine.begin() as c:
            c.execute(delete(brand_kits).where(brand_kits.c.id == brand_id, brand_kits.c.workspace_id == workspace_id))

    # -------------------------------------------------------------- verified links
    def publish(self, workspace_id: str, project_id: str, token: str, copy: dict) -> None:
        with self.engine.begin() as c:
            c.execute(insert(published).values(token=token, project_id=project_id, workspace_id=workspace_id,
                                               copy=json.dumps(copy), created_at=_now(), revoked=0, views=0, checks=0))

    def published_for(self, workspace_id: str, project_id: str) -> list[dict]:
        with self.engine.connect() as c:
            rows = c.execute(select(published).where(published.c.workspace_id == workspace_id,
                                                     published.c.project_id == project_id)
                             .order_by(published.c.created_at.desc())).all()
        out = []
        for r in rows:
            cp = json.loads(r.copy)
            out.append({"token": r.token, "created_at": r.created_at.isoformat(), "revoked": bool(r.revoked),
                        "views": r.views, "checks": r.checks, "evidence": cp.get("evidence", "full"),
                        "show_client": bool(cp.get("client")), "hash": cp.get("hash", "")})
        return out

    def published_copy(self, token: str) -> tuple[dict, str, str] | None:
        """(copy, workspace_id, project_id) for a live link, else None."""
        with self.engine.connect() as c:
            r = c.execute(select(published).where(published.c.token == token, published.c.revoked == 0)).first()
        return (json.loads(r.copy), r.workspace_id, r.project_id) if r else None

    def count_view(self, token: str, field: str = "views") -> None:
        col = published.c.checks if field == "checks" else published.c.views
        with self.engine.begin() as c:
            c.execute(update(published).where(published.c.token == token, published.c.revoked == 0).values({col: col + 1}))

    def revoke(self, workspace_id: str, token: str) -> bool:
        with self.engine.begin() as c:
            res = c.execute(update(published).where(published.c.token == token, published.c.workspace_id == workspace_id)
                            .values(revoked=1))
        return res.rowcount > 0

    # -------------------------------------------------------------- client sign-off
    def add_signoff(self, workspace_id: str, project_id: str, token: str, data: dict) -> None:
        with self.engine.begin() as c:
            c.execute(insert(signoffs).values(token=token, project_id=project_id, workspace_id=workspace_id,
                                              data=json.dumps(data), created_at=_now()))

    def signoffs_for(self, workspace_id: str, project_id: str) -> list[tuple[str, dict]]:
        with self.engine.connect() as c:
            rows = c.execute(select(signoffs.c.token, signoffs.c.data).where(
                signoffs.c.workspace_id == workspace_id, signoffs.c.project_id == project_id)
                .order_by(signoffs.c.created_at.desc())).all()
        return [(r.token, json.loads(r.data)) for r in rows]

    def signoff(self, token: str) -> tuple[dict, str, str] | None:
        """(request, workspace_id, project_id), else None."""
        with self.engine.connect() as c:
            r = c.execute(select(signoffs).where(signoffs.c.token == token)).first()
        return (json.loads(r.data), r.workspace_id, r.project_id) if r else None

    def save_signoff(self, token: str, data: dict) -> None:
        with self.engine.begin() as c:
            c.execute(update(signoffs).where(signoffs.c.token == token).values(data=json.dumps(data)))

    def delete_signoff(self, workspace_id: str, token: str) -> bool:
        with self.engine.begin() as c:
            return c.execute(delete(signoffs).where(signoffs.c.token == token,
                                                    signoffs.c.workspace_id == workspace_id)).rowcount > 0

    def stats(self) -> dict:
        with self.engine.connect() as c:
            return {"projects": c.execute(select(func.count()).select_from(projects)).scalar_one()}
