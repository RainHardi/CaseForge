"""Brand rules that a machine can check (Target T-12). Warnings, shown at review time."""

from __future__ import annotations

import re

from .models import ProjectRecord

MAX_WORDS = 30
BANNED = ["!", "?", "we are proud", "excited to", "leverag", "synergy", "best-in-class", "world-class"]


def brand_warnings(record: ProjectRecord) -> list[str]:
    out: list[str] = []
    for c in record.active_claims():
        words = len(c.text.split())
        if words > MAX_WORDS:
            out.append(f"{c.id}: {words} words (brand limit {MAX_WORDS})")
        low = c.text.lower()
        for b in BANNED:
            if b in low:
                out.append(f"{c.id}: contains '{b}'")
        if re.search(r"\b(I|my|me)\b", c.text):
            out.append(f"{c.id}: first person singular — brand voice is 'we'")
    if not record.active_claims("summary"):
        out.append("No summary sentence — the one-page summary will start with The Challenge")
    if len(record.input.title) > 70:
        out.append("Title is longer than 70 characters")
    return out
