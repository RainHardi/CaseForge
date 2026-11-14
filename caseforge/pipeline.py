"""Runs input -> facts -> draft -> check. Stops at review: nothing here can export."""

from __future__ import annotations

import time

from .brand import brand_warnings
from .checker import check_claims
from .extract import conflicts_from, extract_facts
from .gaps import find_gaps
from .generate import rewrite_failed, write_claims
from .llm import LLM, LLMError
from .models import ProjectRecord


REPAIR_IF_UNDER_S = 90  # auto-repair is a bonus: skip it when Gemini was already slow
JOB_BUDGET_S = 240      # a whole draft never takes longer than this; after it, a clear error instead of a spinner


def generate(record: ProjectRecord, llm: LLM | None) -> ProjectRecord:
    started = time.monotonic()
    if llm is not None and hasattr(llm, "budget_until"):
        llm.budget_until = started + JOB_BUDGET_S
    record.engine = llm.name if llm else "offline"
    facts, dropped, raw = extract_facts(record.input, llm)
    if not record.input.title and raw.title_suggestion:
        record.input.title = raw.title_suggestion.strip()
    if not record.input.client_name and raw.client_name:
        # only accept a client name the input actually contains
        if raw.client_name.lower() in record.input.source_text().lower():
            record.input.client_name = raw.client_name.strip()
    record.facts, record.dropped_facts = facts, dropped
    record.conflicts = conflicts_from(raw, record.input.source_text())
    record.claims = write_claims(record.input, facts, llm)
    record.gaps = find_gaps(record.input, facts, record.claims, record.conflicts)
    check_claims(record, llm)
    if time.monotonic() - started < REPAIR_IF_UNDER_S:
        repair(record, llm)
    elif any(c.blocking for c in record.active_claims()):
        record.log("auto-repair skipped", "Gemini was slow; flagged sentences are left for the reviewer")
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


def repair(record: ProjectRecord, llm: LLM | None) -> int:
    """Sentences the checker rejected get an automatic second try before a person has to deal with them.
    1. the writer corrects them from the same facts, told why they failed — then they are checked again;
    2. what still fails is replaced by the fact itself, in the notes' own words — and checked again.
    Nothing skips the checker: a sentence that fails both tries stays red for the reviewer.
    Returns how many sentences were repaired."""
    bad = [c for c in record.active_claims() if c.blocking and c.fact_ids]
    if not llm or not bad:
        return 0
    facts = {f.id: f for f in record.facts}
    before = {c.id: c.text for c in bad}
    try:
        fixes = rewrite_failed(bad, record.facts, llm)
        changed = {c.id for c in bad if fixes.get(c.id) and fixes[c.id] != c.text}
        for c in bad:
            if c.id in changed:
                c.text = fixes[c.id]
        if changed:
            check_claims(record, llm, changed)
        # the fact itself — but only when no other sentence already tells that fact (each fact once)
        told = [i for x in record.active_claims() if not x.blocking for i in x.fact_ids]
        still = [c for c in bad if c.blocking and c.fact_ids[0] in facts and c.fact_ids[0] not in told
                 and c.text != facts[c.fact_ids[0]].statement]
        for c in still:
            c.text, c.fact_ids = facts[c.fact_ids[0]].statement, c.fact_ids[:1]
        if still:
            check_claims(record, llm, {c.id for c in still})
    except LLMError as e:   # the model is busy: leave what failed for the reviewer
        record.log("auto-repair skipped", str(e)[:160])
    fixed = [c for c in bad if not c.blocking]
    for c in fixed:
        record.log("sentence auto-repaired", f"{c.id}: \"{before[c.id]}\" → \"{c.text}\"")
    return len(fixed)
