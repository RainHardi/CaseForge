"""Step 2 — write the case study from the extracted facts only (never from the raw notes)."""

from __future__ import annotations

import re

from pydantic import BaseModel

from . import prompts
from .llm import LLM
from .models import SECTION_KEYS, Claim, Fact, ProjectInput


class WrittenSentence(BaseModel):
    section: str
    text: str
    fact_ids: list[str]


class Written(BaseModel):
    sentences: list[WrittenSentence]


def write_claims(inp: ProjectInput, facts: list[Fact], llm: LLM | None) -> list[Claim]:
    if not facts:
        return []
    raw = _write_llm(inp, facts, llm) if llm else _write_offline(inp, facts)
    known = {f.id for f in facts}
    claims: list[Claim] = []
    for s in raw.sentences:
        text = " ".join(s.text.split())
        if not text:
            continue
        section = s.section if s.section in SECTION_KEYS else "work_done"
        claims.append(
            Claim(
                id=f"C{len(claims) + 1}",
                section=section,
                text=text,
                # unknown ids are kept so the checker can flag them
                fact_ids=[fid for fid in s.fact_ids if fid] or [],
            )
        )
        if any(fid not in known for fid in s.fact_ids):
            claims[-1].rule_flags.append("cites a fact id that does not exist")
    # every fact somewhere: one the writer left out comes back in its own words, in its section
    told = {fid for c in claims for fid in c.fact_ids}
    for f in facts:
        if f.id not in told:
            claims.append(Claim(id=f"C{len(claims) + 1}", section=section_for(f), text=f.statement, fact_ids=[f.id]))
    for c in claims:
        c.section = tidy_section(c.section, c.text)
    # keep the fixed template order
    claims.sort(key=lambda c: SECTION_KEYS.index(c.section))
    for n, c in enumerate(claims, 1):
        c.id = f"C{n}"
    return claims


_IMPL = re.compile(r"\b(contract|kick-?off|go-?live|went live|signed|budget|invoic\w*|euros?|dollars?|€|\$|headcount|"
                   r"team (?:of|size|began|grew)|people|engineers|developers|sprint|change requests?|CR-\d+|"
                   r"phase|test cases|testing|security review|training|rollout|roll-out|hired)\b", re.I)
_LESSON = re.compile(r"\b(follow-up|phase 2|phase two|next phase|award|talk|lesson|learned|next step)\b", re.I)


_IMPL_STRONG = re.compile(r"\b(contract (?:was )?signed|contract value|kick-?off|invoic\w*|headcount|payroll|team size|"
                          r"test cases|test coverage|load test|security review|training sessions?|trained|build time|"
                          r"pull requests|commits|ISO \d+|certification|change requests?|CR-\d+|offices? in|contractors)\b", re.I)


def tidy_section(section: str, text: str) -> str:
    """The writer sometimes files how-the-project-ran facts under The Solution, or an award under Results.
    Moves only between neighbouring sections, on clear words; the sentence itself is not touched."""
    if section in ("work_done", "technical_approach", "results") and _LESSON.search(text) and not re.search(r"\d+(?:\.\d+)?\s*(?:%|percent)", text):
        return "lessons"
    if section in ("work_done", "technical_approach") and _IMPL_STRONG.search(text):
        return "implementation"
    return section


def section_for(f: Fact) -> str:
    """Where a fact the writer skipped is put: its field, refined to the standard case-study sections."""
    if f.field == "work_done" and _IMPL.search(f.statement):
        return "implementation"
    if f.field in ("results", "work_done") and _LESSON.search(f.statement):
        return "lessons"
    return f.field if f.field in SECTION_KEYS else "work_done"


class Fix(BaseModel):
    claim_id: str
    text: str


class Fixes(BaseModel):
    fixes: list[Fix]


def rewrite_failed(claims: list[Claim], facts: list[Fact], llm: LLM) -> dict[str, str]:
    """Second try for sentences the checker rejected: the writer gets the sentence, why it failed and
    the facts it cited, and returns a corrected sentence for each. {claim id: new text}"""
    by_id = {f.id: f for f in facts}
    blocks = []
    for c in claims:
        cited = [by_id[i] for i in c.fact_ids if i in by_id]
        if cited:
            blocks.append(f"{c.id} [{c.section}] REJECTED SENTENCE: {c.text}\n  WHY: {c.reason or 'not supported by the notes'}\n"
                          + "\n".join(f"  FACT {f.id}: {f.statement}" for f in cited))
    if not blocks:
        return {}
    out = llm.generate_json(prompts.REPAIR_SYSTEM, prompts.REPAIR_PROMPT.format(items="\n\n".join(blocks)), Fixes)
    known = {c.id for c in claims}
    return {f.claim_id.strip(): " ".join(f.text.split()) for f in out.fixes if f.claim_id.strip() in known and f.text.strip()}


def _write_llm(inp: ProjectInput, facts: list[Fact], llm: LLM) -> Written:
    fact_lines = "\n".join(f"{f.id} [{f.field}] {f.statement}" for f in facts)
    prompt = prompts.WRITE_PROMPT.format(
        title=inp.title or "(not given)", client=inp.client_name or "(not given — say 'the client')",
        facts=fact_lines, n_facts=len(facts),
    )
    return llm.generate_json(prompts.WRITE_SYSTEM, prompt, Written)


def _write_offline(inp: ProjectInput, facts: list[Fact]) -> Written:
    """No model: each fact becomes one sentence, verbatim, in its section. Plain but faithful."""
    sentences = [WrittenSentence(section=section_for(f), text=f.statement, fact_ids=[f.id]) for f in facts]
    lead = next((f for f in facts if f.field == "client_problem"), None) or next(
        (f for f in facts if f.field == "work_done"), None
    )
    if lead:
        sentences.insert(0, WrittenSentence(section="summary", text=lead.statement, fact_ids=[lead.id]))
    return Written(sentences=sentences)
