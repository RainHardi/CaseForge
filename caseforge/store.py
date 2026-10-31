"""Project Store: one folder per project, holding a JSON record and its images."""

from __future__ import annotations

import re
import shutil
import uuid
from pathlib import Path

from .config import get_settings
from .models import ProjectInput, ProjectRecord


class Store:
    def __init__(self, root: Path | None = None):
        self.root = Path(root or get_settings().data_dir)
        self.root.mkdir(parents=True, exist_ok=True)

    def folder(self, project_id: str) -> Path:
        if not re.fullmatch(r"[\w-]+", project_id):
            raise ValueError(f"Bad project id {project_id!r}")
        return self.root / project_id

    def image_dir(self, project_id: str) -> Path:
        d = self.folder(project_id) / "images"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def create(self, inp: ProjectInput) -> ProjectRecord:
        slug = re.sub(r"[^a-z0-9]+", "-", (inp.title or "project").lower()).strip("-")[:40] or "project"
        rec = ProjectRecord(id=f"{slug}-{uuid.uuid4().hex[:6]}", input=inp)
        rec.log("created")
        self.save(rec)
        return rec

    def save(self, rec: ProjectRecord) -> None:
        folder = self.folder(rec.id)
        folder.mkdir(parents=True, exist_ok=True)
        tmp = folder / "record.json.tmp"
        tmp.write_text(rec.model_dump_json(indent=2), encoding="utf-8")
        tmp.replace(folder / "record.json")

    def load(self, project_id: str) -> ProjectRecord:
        path = self.folder(project_id) / "record.json"
        return ProjectRecord.model_validate_json(path.read_text(encoding="utf-8"))

    def list(self) -> list[ProjectRecord]:
        recs = []
        for p in sorted(self.root.glob("*/record.json")):
            try:
                recs.append(ProjectRecord.model_validate_json(p.read_text(encoding="utf-8")))
            except Exception:  # a broken file should not take the app down
                continue
        return sorted(recs, key=lambda r: r.created_at, reverse=True)

    def add_image(self, project_id: str, src: Path | None = None, name: str = "", data: bytes | None = None) -> str:
        name = re.sub(r"[^\w.\-]", "_", name or (src.name if src else "image.png"))
        dest = self.image_dir(project_id) / name
        if data is not None:
            dest.write_bytes(data)
        elif src is not None:
            shutil.copy(src, dest)
        return name

    def image_path(self, project_id: str, filename: str) -> Path:
        return self.image_dir(project_id) / filename

    def delete(self, project_id: str) -> None:
        shutil.rmtree(self.folder(project_id), ignore_errors=True)
