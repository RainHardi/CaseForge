"""Step 1 — pull out only the facts the input states (BT-3).

Every fact must carry a quote that is then found in the input by plain string matching.
Facts whose quote isn't in the input are dropped, so the writer never sees them.
"""

from __future__ import annotations

import re

from pydantic import BaseModel

from . import prompts
from .llm import LLM
from .models import FIELD_KEYS, Fact, ProjectInput
from .textutil import quote_in_source, split_sentences, tidy_sentence


class ExtractedFact(BaseModel):
    field: str
    statement: str
    quote: str


class Extraction(BaseModel):
    title_suggestion: str = ""
    client_name: str = ""
    facts: list[ExtractedFact]


def extract_facts(inp: ProjectInput, llm: LLM | None) -> tuple[list[Fact], list[Fact], Extraction]:
    """Returns (grounded facts, dropped facts, raw extraction)."""
    source = inp.source_text()
    raw = _extract_llm(source, llm) if llm else _extract_offline(inp)

    kept: list[Fact] = []
    dropped: list[Fact] = []
    seen: set[str] = set()
    for i, ef in enumerate(raw.facts, 1):
        field = ef.field if ef.field in FIELD_KEYS else "work_done"
        fact = Fact(id=f"F{i}", field=field, statement=ef.statement.strip(), quote=ef.quote.strip())
        key = fact.statement.lower()
        if key in seen or not fact.statement:
            continue
        seen.add(key)
        fact.grounded = quote_in_source(fact.quote, source)
        (kept if fact.grounded else dropped).append(fact)
    # renumber kept facts so ids are compact: F1..Fn
    for n, f in enumerate(kept, 1):
        f.id = f"F{n}"
    return kept, dropped, raw


def _extract_llm(source: str, llm: LLM) -> Extraction:
    return llm.generate_json(prompts.EXTRACT_SYSTEM, prompts.EXTRACT_PROMPT.format(source=source), Extraction)


# --------------------------------------------------------------------- offline
_ROUTES: list[tuple[str, re.Pattern[str]]] = [
    ("results", re.compile(r"\b(result|outcome|improv|reduc|increas|decreas|saved|faster|slower|"
                           r"feedback|happy|satisf|now (?:they|the)|went live|launched|adopt|"
                           r"measure|numbers|will use|fell|dropped)", re.I)),
    ("challenges", re.compile(r"\b(challeng|hard|difficult|problem we|issue we|bug|struggl|blocker|"
                              r"tricky|took (?:a while|long|forever)|risk|pain|out of date|contradict)", re.I)),
    ("client_problem", re.compile(r"\b(they (?:need|want|had|tracked|got|used to)|wanted|needed|"
                                  r"nobody|by hand|manually|couldn't|could not|no way to)", re.I)),
    ("tools", re.compile(r"\b(python|react|java|sql|postgres|mysql|docker|aws|gcp|azure|fastapi|"
                         r"django|flask|node|typescript|pytorch|tensorflow|streamlit|gemini|openai|"
                         r"kubernetes|redis|excel|figma|we used|stack|built with|library|framework)", re.I)),
    ("client_problem", re.compile(r"\b(client|customer|they (?:need|want|had)|needed|wanted|"
                                  r"pain|manual|spreadsheet|couldn't|could not|no way to|problem)", re.I)),
    ("technical_approach", re.compile(r"\b(architect|pipeline|model|approach|method|design|api|"
                                      r"database|schema|deployed|train|algorithm|integrat)", re.I)),
]
_CHATTER = re.compile(r"^(?:hi|hey|hello|thanks|thank you|lol|haha|ok thanks|okay thanks|sure|cool|nice|"
                      r"good morning|see you)\b", re.I)
_SPEAKER = re.compile(r"^\s*(?:\[[^\]]*\]\s*)?[A-Za-z][\w .]{0,24}:\s+")


def _route(sentence: str) -> str:
    for field, pattern in _ROUTES:
        if pattern.search(sentence):
            return field
    return "work_done"


def _extract_offline(inp: ProjectInput) -> Extraction:
    """No model: every sentence of the input becomes a fact, verbatim. Faithful by construction."""
    facts: list[ExtractedFact] = []
    for field in FIELD_KEYS:
        for s in split_sentences(getattr(inp, field)):
            facts.append(ExtractedFact(field=field, statement=tidy_sentence(s), quote=s))
    for block in [inp.raw_notes, *inp.reviewer_additions]:
        for s in split_sentences(block):
            content = _SPEAKER.sub("", s).strip()
            if len(content.split()) < 3 or _CHATTER.match(content):
                continue
            facts.append(ExtractedFact(field=_route(content), statement=tidy_sentence(content), quote=content))
    return Extraction(title_suggestion=inp.title, client_name=inp.client_name, facts=facts)
