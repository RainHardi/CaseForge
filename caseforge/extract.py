"""Step 1 — pull out only the facts the input states (BT-3).

Every fact must carry a quote that is then found in the input by plain string matching.
Facts whose quote isn't in the input are dropped, so the writer never sees them.
"""

from __future__ import annotations

import re

from pydantic import BaseModel

from . import prompts
from .llm import LLM
from .models import FIELD_KEYS, Conflict, Fact, ProjectInput
from .textutil import is_hedged, locate_quote, quote_in_source, split_sentences, tidy_sentence, unwrap

CHUNK_CHARS = 9000  # big dumps are read in parts so nothing is skipped


class ExtractedFact(BaseModel):
    field: str
    statement: str
    quote: str


class ExtractedConflict(BaseModel):
    topic: str
    values: list[str]
    quotes: list[str] = []


class Extraction(BaseModel):
    title_suggestion: str = ""
    client_name: str = ""
    facts: list[ExtractedFact]
    conflicts: list[ExtractedConflict] = []


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
        fact.source_ref = locate_quote(fact.quote, source)
        fact.estimate = is_hedged(fact.quote) or is_hedged(fact.statement)
        (kept if fact.grounded else dropped).append(fact)
    # renumber kept facts so ids are compact: F1..Fn
    for n, f in enumerate(kept, 1):
        f.id = f"F{n}"
    return kept, dropped, raw


def conflicts_from(raw: Extraction, source: str) -> list[Conflict]:
    """Keep only disagreements whose values really are in the notes."""
    out = []
    for c in raw.conflicts:
        low = source.lower()
        vals = [v for v in dict.fromkeys(v.strip() for v in c.values)
                if v and re.search(rf"(?<![\w.,]){re.escape(v.lower())}(?![\w]|[.,]\d)", low)]
        if len(vals) >= 2 and not _is_a_change(vals, source):
            out.append(Conflict(topic=c.topic.strip(), values=vals, quotes=c.quotes[:4]))
    return out


_SEQUENCE = re.compile(r"\b(began|started|initially|at first|original\w*|then|later|reached|rose|grew|dropped|fell|"
                       r"reduced|increased|ended|final\w*|from|before|after|now|until|by the end)\b", re.I)


def _is_a_change(values: list[str], source: str) -> bool:
    """"Headcount began at 6 and reached 11 in August, then dropped to 7" is one sentence telling how a
    value CHANGED — not two sources disagreeing. When ALL the values sit in one sentence with words
    like began / reached / then / from … to, it is a history and no question is asked. (A value from
    another place in the notes — "I think the final count was 9" — still makes it a question.)"""
    for s in split_sentences(source):
        low = s.lower()
        if all(v.lower() in low for v in values) and len(_SEQUENCE.findall(s)) >= 2:
            return True   # every value is in this one sentence: it tells a history
    return False


def chunks(source: str, size: int = CHUNK_CHARS) -> list[str]:
    """Split on blank lines into parts of at most ~size characters (a paragraph is never cut)."""
    parts, cur = [], ""
    for para in re.split(r"\n\s*\n", source):
        if cur and len(cur) + len(para) > size:
            parts.append(cur)
            cur = ""
        cur = f"{cur}\n\n{para}" if cur else para
    if cur:
        parts.append(cur)
    return parts


def _extract_llm(source: str, llm: LLM) -> Extraction:
    parts = chunks(source)
    merged = Extraction(facts=[], conflicts=[])
    for part in parts:
        r = llm.generate_json(prompts.EXTRACT_SYSTEM, prompts.EXTRACT_PROMPT.format(source=part), Extraction)
        merged.facts += r.facts
        merged.conflicts += r.conflicts
        merged.title_suggestion = merged.title_suggestion or r.title_suggestion
        merged.client_name = merged.client_name or r.client_name
    return merged


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


# "Design notes from Amira Haddad (UX designer), written during week 3: interviewed 9 dispatchers…"
# — the part before the colon says who wrote the note; the fact is what follows.
_ATTRIB = re.compile(r"^[^.!?:]{0,140}\b(?:from|notes? by|message|notebook|sent by|quoted|written by|"
                     r"collected (?:during|by|at)|other facts|should include)\b[^.!?:]{0,120}:\s+(?=\S)", re.I)
_FILLER = re.compile(r"^(?:(?:ok(?:ay)?|so|yeah|yep|right|well|btw|fyi|also)[ ,]+)+(?:for the record[.,:]?\s+)?", re.I)
_LABEL = re.compile(r"^[A-Za-z][A-Za-z ]{0,30}:\s+")


def offline_title(notes: str) -> tuple[str, str]:
    """(title, the line it came from). Messy notes usually start with a heading line; it is used as
    the title when it looks like one — short, no full stop. A label before a colon is dropped."""
    for line in unwrap(notes).splitlines():
        line = line.strip(" #*-\t")
        if not line:
            continue
        label = _LABEL.match(line)
        head = line[label.end():].strip() if label else line
        chatty = line[0] in "[(" or line[0].isdigit() or (label and len(label.group(0).split()) <= 2)
        if not chatty and 2 <= len(head.split()) <= 12 and len(head) <= 90 and head[-1] not in ".!?,":
            return head[0].upper() + head[1:], line
        return "", ""
    return "", ""


def _extract_offline(inp: ProjectInput) -> Extraction:
    """No model: every sentence of the input becomes a fact, verbatim. Faithful by construction."""
    facts: list[ExtractedFact] = []
    for field in FIELD_KEYS:
        for s in split_sentences(getattr(inp, field)):
            facts.append(ExtractedFact(field=field, statement=tidy_sentence(s), quote=s))
    title, title_line = (inp.title, "") if inp.title else offline_title(inp.raw_notes)
    for block in [inp.raw_notes, *inp.reviewer_additions]:
        for s in split_sentences(block):
            if title_line and s.strip(" #*-\t") == title_line:
                continue  # the heading is the title, not a fact
            content = _FILLER.sub("", _SPEAKER.sub("", s).strip()).strip()
            said = _ATTRIB.sub("", content).strip()
            if len(said.split()) >= 4 and not re.match(r"(?:he|she|they)\b", said, re.I):
                content = said   # (kept whole when it would start with "he said": the name is in the prefix)
            if len(content.split()) < 3 or _CHATTER.match(content):
                continue
            facts.append(ExtractedFact(field=_route(content), statement=tidy_sentence(content), quote=content))
    return Extraction(title_suggestion=title, client_name=inp.client_name, facts=facts)
