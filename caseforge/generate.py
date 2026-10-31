"""Step 2 — write the case study from the extracted facts only (never from the raw notes)."""

from __future__ import annotations

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
    # keep the fixed template order
    claims.sort(key=lambda c: SECTION_KEYS.index(c.section))
    for n, c in enumerate(claims, 1):
        c.id = f"C{n}"
    return claims


def _write_llm(inp: ProjectInput, facts: list[Fact], llm: LLM) -> Written:
    fact_lines = "\n".join(f"{f.id} [{f.field}] {f.statement}" for f in facts)
    prompt = prompts.WRITE_PROMPT.format(
        title=inp.title or "(not given)", client=inp.client_name or "(not given — say 'the client')",
        facts=fact_lines,
    )
    return llm.generate_json(prompts.WRITE_SYSTEM, prompt, Written)


def _write_offline(inp: ProjectInput, facts: list[Fact]) -> Written:
    """No model: each fact becomes one sentence, verbatim, in its section. Plain but faithful."""
    sentences = [WrittenSentence(section=f.field, text=f.statement, fact_ids=[f.id]) for f in facts]
    lead = next((f for f in facts if f.field == "client_problem"), None) or next(
        (f for f in facts if f.field == "work_done"), None
    )
    if lead:
        sentences.insert(0, WrittenSentence(section="summary", text=lead.statement, fact_ids=[lead.id]))
    return Written(sentences=sentences)
