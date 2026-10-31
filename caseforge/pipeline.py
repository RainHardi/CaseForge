"""Runs input -> facts -> draft -> check. Stops at review: nothing here can export."""

from __future__ import annotations

from .brand import brand_warnings
from .checker import check_claims
from .extract import extract_facts
from .gaps import find_gaps
from .generate import write_claims
from .llm import LLM
from .models import ProjectRecord


def generate(record: ProjectRecord, llm: LLM | None) -> ProjectRecord:
    record.engine = llm.name if llm else "offline"
    facts, dropped, raw = extract_facts(record.input, llm)
    if not record.input.title and raw.title_suggestion:
        record.input.title = raw.title_suggestion.strip()
    if not record.input.client_name and raw.client_name:
        # only accept a client name the input actually contains
        if raw.client_name.lower() in record.input.source_text().lower():
            record.input.client_name = raw.client_name.strip()
    record.facts, record.dropped_facts = facts, dropped
    record.claims = write_claims(record.input, facts, llm)
    record.gaps = find_gaps(record.input, facts, record.claims)
    check_claims(record, llm)
    record.brand_warnings = brand_warnings(record)
    record.status = "drafted"
    record.approved_hash = record.approved_by = record.approved_at = ""
    if llm:
        record.llm_calls = llm.calls
    record.log(
        "generated",
        f"{len(facts)} facts ({len(dropped)} dropped as not found in input), "
        f"{len(record.claims)} claims, engine={record.engine}",
    )
    return record
