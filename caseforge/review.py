"""Human review and approval (BT-5). The only way to reach 'approved'.

Export checks `can_export`, which needs status == approved AND the content unchanged since
approval. Any edit after approval drops the project back to 'drafted'.
"""

from __future__ import annotations

from .brand import brand_warnings
from .checker import check_claims
from .gaps import find_gaps
from .llm import LLM
from .models import FIELD_KEYS, SECTION_KEYS, Claim, Fact, ProjectRecord, now


class ReviewError(ValueError):
    pass


def _touch(record: ProjectRecord) -> None:
    if record.status == "approved":
        record.status = "drafted"
        record.log("approval withdrawn", "content changed after approval")
    record.approved_hash = ""
    record.brand_warnings = brand_warnings(record)


def edit_claim(record: ProjectRecord, claim_id: str, new_text: str, llm: LLM | None, by: str = "") -> Claim:
    c = record.claim(claim_id)
    new_text = " ".join(new_text.split())
    if not new_text:
        raise ReviewError("Empty text — delete the claim instead.")
    old = c.text
    if new_text == old and not c.deleted:
        return c  # nothing changed, approval stands
    c.text, c.edited, c.deleted = new_text, True, False
    check_claims(record, llm, only_ids={c.id})
    _touch(record)
    record.log("edited", f"{c.id}: '{old}' -> '{new_text}' (now {c.label.value if c.label else '?'})", by)
    return c


def delete_claim(record: ProjectRecord, claim_id: str, by: str = "") -> None:
    c = record.claim(claim_id)
    c.deleted = True
    _touch(record)
    record.log("deleted", f"{c.id}: '{c.text}'", by)


def restore_claim(record: ProjectRecord, claim_id: str, llm: LLM | None, by: str = "") -> None:
    c = record.claim(claim_id)
    c.deleted = False
    check_claims(record, llm, only_ids={c.id})
    _touch(record)
    record.log("restored", c.id, by)


def add_claim(record: ProjectRecord, section: str, text: str, llm: LLM | None, by: str = "") -> Claim:
    if section not in SECTION_KEYS:
        raise ReviewError(f"Unknown section {section!r}")
    c = Claim(id=record.next_id("C", [x.id for x in record.claims]), section=section,
              text=" ".join(text.split()), manual=True)
    record.claims.append(c)
    check_claims(record, llm, only_ids={c.id})
    _touch(record)
    record.log("added claim", f"{c.id} [{section}]: '{c.text}' (now {c.label.value if c.label else '?'})", by)
    return c


def add_to_source(record: ProjectRecord, text: str, llm: LLM | None, field: str = "work_done",
                  by: str = "") -> None:
    """The reviewer confirms a fact that wasn't in the notes. It becomes part of the source
    (and a fact), with an audit entry, and every claim is re-checked against the larger source."""
    text = text.strip()
    if not text:
        raise ReviewError("Nothing to add.")
    if field not in FIELD_KEYS:
        raise ReviewError(f"Unknown field {field!r}")
    record.input.reviewer_additions.append(text)
    record.facts.append(Fact(id=record.next_id("F", [f.id for f in record.facts]), field=field,
                             statement=text, quote=text))
    check_claims(record, llm)
    old_resolved = {g.field: g for g in record.gaps if g.resolved}
    record.gaps = find_gaps(record.input, record.facts, record.claims)
    for g in record.gaps:  # keep earlier acknowledgements
        if g.field in old_resolved:
            g.resolved, g.resolution = True, old_resolved[g.field].resolution
    _touch(record)
    record.log("added to source", text, by)


def refresh_gaps(record: ProjectRecord) -> None:
    """Recompute missing-info flags (e.g. after adding info or images), keeping earlier answers."""
    old = {g.field: g for g in record.gaps if g.resolved}
    record.gaps = find_gaps(record.input, record.facts, record.claims)
    for g in record.gaps:
        if g.field in old:
            g.resolved, g.resolution = True, old[g.field].resolution


def resolve_gap(record: ProjectRecord, gap_id: str, note: str, by: str = "") -> None:
    g = record.gap(gap_id)
    if not note.strip():
        raise ReviewError("Say how the gap was handled (e.g. 'no measured result exists').")
    g.resolved, g.resolution = True, note.strip()
    record.log("gap resolved", f"{g.id} [{g.field}]: {note.strip()}", by)


def blockers(record: ProjectRecord) -> list[str]:
    out: list[str] = []
    if record.status not in ("drafted", "approved"):
        out.append(f"project is '{record.status}', not drafted")
    for c in record.active_claims():
        if c.label is None:
            out.append(f"{c.id} has not been checked")
        elif c.blocking:
            out.append(f"{c.id} is {c.label.value}: {c.text}")
    for g in record.gaps:
        if g.blocking and not g.resolved:
            out.append(f"{g.id} unresolved: {g.message}")
    if not record.active_claims():
        out.append("there are no claims to publish")
    return out


def approve(record: ProjectRecord, reviewer: str) -> None:
    if not reviewer.strip():
        raise ReviewError("Approval needs the reviewer's name.")
    problems = blockers(record)
    if problems:
        raise ReviewError("Cannot approve:\n- " + "\n- ".join(problems))
    record.status = "approved"
    record.approved_by = reviewer.strip()
    record.approved_at = now()
    record.approved_hash = record.content_hash()
    record.log("approved", f"hash {record.approved_hash[:12]}", reviewer.strip())


def reject(record: ProjectRecord, reviewer: str, reason: str) -> None:
    record.status = "rejected"
    record.approved_hash = ""
    record.log("rejected", reason, reviewer)


def can_export(record: ProjectRecord) -> bool:
    return (
        record.status == "approved"
        and bool(record.approved_hash)
        and record.approved_hash == record.content_hash()
    )
