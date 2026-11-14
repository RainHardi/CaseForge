"""Extra output formats written from the APPROVED case study (Target: more output formats).

Same rule as everywhere else: every sentence is checked against the original notes, and a format
with a flagged sentence cannot be copied or downloaded until a person fixes it.
"""

from __future__ import annotations

from pydantic import BaseModel

from .checker import label_claims
from .llm import LLM
from .models import Claim, DerivedOutput, ProjectRecord
from .review import ReviewError, can_export

FORMATS: dict[str, dict[str, str]] = {
    "linkedin": {
        "title": "LinkedIn post",
        "blurb": "A short post announcing the project, 4–6 sentences.",
        "brief": "A LinkedIn post by the delivery company about this project. 4 to 6 short sentences. "
                 "First sentence hooks with the client's problem or the clearest result. Friendly, "
                 "professional, first person plural. No hashtags, no emojis, no questions.",
    },
    "proposal": {
        "title": "Proposal paragraph",
        "blurb": "A 'relevant experience' paragraph to paste into proposals and bids.",
        "brief": "A 'relevant experience' paragraph for a proposal or tender. 3 to 5 sentences, formal, "
                 "third person ('the team'). Problem, what was delivered, how, and the outcome.",
    },
    "pitch": {
        "title": "Elevator pitch",
        "blurb": "Two sentences a salesperson can say out loud.",
        "brief": "Exactly two sentences a salesperson can say out loud: the problem and what changed.",
    },
}

SYSTEM = """You rewrite an APPROVED case study into a shorter format.
You may ONLY use the numbered approved sentences. Every sentence you write must list the ids
(`source_ids`) of the approved sentences it is based on.
Never add a number, name, tool, date, client detail or outcome that is not in the cited sentences.
No inflated words (significantly, dramatically, seamless, cutting-edge, world-class, revolutionary)
unless that exact word is in a cited sentence. If there is not enough material, write fewer sentences."""

PROMPT = """FORMAT: {brief}

Project: {title}
Client: {client}

APPROVED SENTENCES:
{claims}

Return the sentences of the new format as JSON."""


class FormatSentence(BaseModel):
    text: str
    source_ids: list[str]


class FormatResult(BaseModel):
    sentences: list[FormatSentence]


def _approved(record: ProjectRecord) -> list[Claim]:
    return record.active_claims()


def build_format(record: ProjectRecord, kind: str, llm: LLM | None) -> DerivedOutput:
    if kind not in FORMATS:
        raise ReviewError(f"Unknown format {kind!r}")
    if not can_export(record):
        raise ReviewError("Approve the case study first — formats are written only from approved text.")
    approved = _approved(record)
    known = {c.id for c in approved}

    if llm:
        lines = "\n".join(f"{c.id}: {c.text}" for c in approved)
        result = llm.generate_json(SYSTEM, PROMPT.format(
            brief=FORMATS[kind]["brief"], title=record.input.title or "(untitled)",
            client=record.input.client_name or "the client", claims=lines), FormatResult)
        raw = [(s.text, s.source_ids) for s in result.sentences]
    else:
        raw = _offline(record, kind)

    sentences = []
    for i, (text, ids) in enumerate(raw, 1):
        text = " ".join(text.split())
        if text:
            sentences.append(Claim(id=f"S{i}", section="summary", text=text, fact_ids=[x for x in ids if x]))
    # same checker as the case study, against the ORIGINAL notes; citations must be approved sentences
    label_claims(sentences, record.input.source_text(), known, llm)
    if llm:
        record.llm_calls = llm.calls
    out = DerivedOutput(kind=kind, sentences=sentences, based_on_hash=record.approved_hash)
    record.outputs[kind] = out
    record.log("format written", f"{FORMATS[kind]['title']}: {len(sentences)} sentences, "
               f"{len(out.blocking)} flagged")
    return out


def _offline(record: ProjectRecord, kind: str) -> list[tuple[str, list[str]]]:
    """No model: reuse approved sentences verbatim, picked per format."""
    by = {s: record.active_claims(s) for s in ("summary", "client_problem", "work_done", "results")}
    pick: list[Claim] = []
    if kind == "pitch":
        pick = (by["client_problem"][:1] or by["summary"][:1]) + (by["results"][:1] or by["work_done"][:1])
    else:
        pick = by["summary"][:1] + by["client_problem"][:1] + by["work_done"][:2] + by["results"][:2]
    seen, out = set(), []
    for c in pick:
        if c.id not in seen and c.text.lower() not in seen:
            seen.update({c.id, c.text.lower()})
            out.append((c.text, [c.id]))
    return out


def edit_format_sentence(record: ProjectRecord, kind: str, sid: str, text: str | None, llm: LLM | None,
                         delete: bool = False) -> DerivedOutput:
    out = record.outputs.get(kind)
    if not out:
        raise ReviewError("Write the format first.")
    target = next((s for s in out.sentences if s.id == sid), None)
    if target is None:
        raise ReviewError(f"No sentence {sid!r}")
    if delete:
        target.deleted = True
    else:
        target.text, target.edited, target.deleted = " ".join((text or "").split()), True, False
        target.manual = True  # a person wrote it; no citation needed, but rules + model still apply
        label_claims([target], record.input.source_text(), {c.id for c in _approved(record)}, llm)
    record.log("format edited", f"{kind} {sid}")
    return out


def format_ready(record: ProjectRecord, kind: str) -> bool:
    out = record.outputs.get(kind)
    return bool(out and not out.blocking and out.based_on_hash == record.approved_hash and can_export(record)
                and any(not s.deleted for s in out.sentences))
