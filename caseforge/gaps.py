"""Missing-information flags. CaseForge reports a gap instead of filling it."""

from __future__ import annotations

from .models import Claim, Fact, Gap, ProjectInput
from .textutil import numbers_in


def find_gaps(inp: ProjectInput, facts: list[Fact], claims: list[Claim] | None = None) -> list[Gap]:
    """A topic counts as covered if a fact is filed under it OR the draft has a sentence in that
    section (the model sometimes files 'python + react' under work done, then writes it under Tools)."""
    texts: dict[str, list[str]] = {}
    for f in facts:
        texts.setdefault(f.field, []).append(f.statement)
    for c in claims or []:
        if not c.deleted:
            texts.setdefault(c.section, []).append(c.text)

    gaps: list[Gap] = []

    def add(field: str, message: str, blocking: bool = False) -> None:
        gaps.append(Gap(id=f"G{len(gaps) + 1}", field=field, message=message, blocking=blocking))

    if not texts.get("client_problem"):
        add("client_problem", "Your notes don't say what problem the client had. "
            "A case study needs one.", blocking=True)
    if not texts.get("work_done"):
        add("work_done", "Your notes don't say what the team actually did.", blocking=True)
    results = texts.get("results", [])
    if not results:
        add("results", "Your notes don't mention any result. CaseForge won't invent one.", blocking=True)
    elif not any(numbers_in(t) for t in results):
        add("results", "No measured result (no number). Results will only be described in your own words.")
    if not texts.get("tools"):
        add("tools", "No tools or technologies are named.")
    if not texts.get("challenges"):
        add("challenges", "No challenges are described.")
    if not inp.client_name:
        add("client_name", "No client name, so the document will say \"the client\".")
    if not inp.images:
        add("images", "No images added.")
    return gaps
