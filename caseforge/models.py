"""Data shapes for the whole system. Everything that is stored is one of these."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

# The fixed template. Order here = order in every output document.
INPUT_FIELDS: list[tuple[str, str]] = [
    ("client_problem", "Client problem"),
    ("work_done", "Work done"),
    ("technical_approach", "Technical approach"),
    ("tools", "Tools and technologies"),
    ("challenges", "Challenges"),
    ("results", "Results"),
]

SECTIONS: list[tuple[str, str]] = [
    ("summary", "Summary"),
    ("client_problem", "The Challenge"),
    ("work_done", "What We Did"),
    ("technical_approach", "Technical Approach"),
    ("tools", "Tools & Technologies"),
    ("challenges", "Obstacles We Worked Through"),
    ("results", "Results"),
]
SECTION_KEYS = [k for k, _ in SECTIONS]
SECTION_TITLES = dict(SECTIONS)
FIELD_KEYS = [k for k, _ in INPUT_FIELDS]


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Label(str, Enum):
    supported = "supported"  # stated in the input
    reworded = "reworded"  # same meaning, said more professionally
    unsupported = "unsupported"  # not in the input -> blocks approval
    contradicted = "contradicted"  # goes against the input -> blocks approval


SEVERITY = {Label.supported: 0, Label.reworded: 1, Label.unsupported: 2, Label.contradicted: 3}
BLOCKING_LABELS = {Label.unsupported, Label.contradicted}


def worst(*labels: Label | None) -> Label | None:
    present = [lab for lab in labels if lab is not None]
    return max(present, key=lambda lab: SEVERITY[lab]) if present else None


class ImageRef(BaseModel):
    filename: str
    caption: str = ""
    section: str = "work_done"  # which section the image sits next to


class ProjectInput(BaseModel):
    """What the user gives us. Any field may be empty; raw_notes can hold everything."""

    title: str = ""
    client_name: str = ""
    client_problem: str = ""
    work_done: str = ""
    technical_approach: str = ""
    tools: str = ""
    challenges: str = ""
    results: str = ""
    raw_notes: str = ""  # messy input: rough notes, pasted chat, anything
    reviewer_additions: list[str] = Field(default_factory=list)  # facts added during review
    images: list[ImageRef] = Field(default_factory=list)

    def source_text(self) -> str:
        """The single source of truth every claim is checked against."""
        parts: list[str] = []
        if self.title:
            parts.append(f"[Project title]\n{self.title}")
        if self.client_name:
            parts.append(f"[Client]\n{self.client_name}")
        for key, label in INPUT_FIELDS:
            value = getattr(self, key).strip()
            if value:
                parts.append(f"[{label}]\n{value}")
        if self.raw_notes.strip():
            parts.append(f"[Raw notes]\n{self.raw_notes.strip()}")
        for i, add in enumerate(self.reviewer_additions, 1):
            parts.append(f"[Reviewer addition {i}]\n{add.strip()}")
        for img in self.images:
            if img.caption:
                parts.append(f"[Image caption: {img.filename}]\n{img.caption}")
        return "\n\n".join(parts)


class Fact(BaseModel):
    id: str
    field: str  # one of FIELD_KEYS
    statement: str  # the fact, in plain words
    quote: str  # exact text from the input that states it
    grounded: bool = True  # quote was found in the input


class Claim(BaseModel):
    id: str
    section: str  # one of SECTION_KEYS
    text: str
    fact_ids: list[str] = Field(default_factory=list)
    label: Label | None = None  # final label (worst of rules + model)
    model_label: Label | None = None
    reason: str = ""
    evidence: str = ""
    rule_flags: list[str] = Field(default_factory=list)
    deleted: bool = False
    edited: bool = False
    manual: bool = False  # added by the reviewer

    @property
    def blocking(self) -> bool:
        return not self.deleted and (self.label is None or self.label in BLOCKING_LABELS)


class Gap(BaseModel):
    id: str
    field: str
    message: str
    blocking: bool = False
    resolved: bool = False
    resolution: str = ""


class Event(BaseModel):
    at: str = Field(default_factory=now)
    action: str
    detail: str = ""
    by: str = ""


Status = Literal["input", "drafted", "approved", "rejected"]


class ProjectRecord(BaseModel):
    id: str
    created_at: str = Field(default_factory=now)
    input: ProjectInput
    facts: list[Fact] = Field(default_factory=list)
    dropped_facts: list[Fact] = Field(default_factory=list)  # extracted but not found in input
    claims: list[Claim] = Field(default_factory=list)
    gaps: list[Gap] = Field(default_factory=list)
    brand_warnings: list[str] = Field(default_factory=list)
    status: Status = "input"
    approved_by: str = ""
    approved_at: str = ""
    approved_hash: str = ""
    engine: str = ""  # "gemini:<model>" or "offline"
    llm_calls: int = 0
    history: list[Event] = Field(default_factory=list)

    # ---- helpers -------------------------------------------------------
    def active_claims(self, section: str | None = None) -> list[Claim]:
        return [c for c in self.claims if not c.deleted and (section is None or c.section == section)]

    def claim(self, claim_id: str) -> Claim:
        for c in self.claims:
            if c.id == claim_id:
                return c
        raise KeyError(f"No claim {claim_id!r}")

    def gap(self, gap_id: str) -> Gap:
        for g in self.gaps:
            if g.id == gap_id:
                return g
        raise KeyError(f"No gap {gap_id!r}")

    def content_hash(self) -> str:
        """Fingerprint of exactly what would be published."""
        payload = {
            "title": self.input.title,
            "client": self.input.client_name,
            "claims": [(c.id, c.section, c.text) for c in self.active_claims()],
            "images": [i.model_dump() for i in self.input.images],
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    def log(self, action: str, detail: str = "", by: str = "") -> None:
        self.history.append(Event(action=action, detail=detail, by=by))

    def next_id(self, prefix: str, existing: list[str]) -> str:
        n = 1
        while f"{prefix}{n}" in existing:
            n += 1
        return f"{prefix}{n}"
