"""Step 3 — the faithfulness checker (BT-4). Independent of the writer.

Two layers, and the stricter one wins:
  1. Rules (always on, deterministic): numbers, named tools/companies/people and inflated
     words in a claim must appear in the input; every generated claim must cite a fact.
  2. Model (when Gemini is on): a separate call that sees only the SOURCE and the claims —
     not the facts, not the writing prompt — and labels each claim.
     Offline, layer 2 is replaced by word-overlap with the input.
If the model forgets a claim, that claim is marked unsupported (fail closed).
"""

from __future__ import annotations

from pydantic import BaseModel

from . import prompts
from .llm import LLM
from .models import Claim, Label, ProjectRecord, worst
from .textutil import (
    best_overlap,
    inflated_words,
    named_terms,
    normalize,
    numbers_in,
    split_sentences,
    term_in_source,
)


class Verdict(BaseModel):
    claim_id: str
    label: str
    reason: str = ""
    evidence: str = ""


class CheckResult(BaseModel):
    verdicts: list[Verdict]


def rule_flags(claim: Claim, source: str, known_fact_ids: set[str]) -> list[str]:
    flags: list[str] = []
    src_norm = normalize(source)
    src_numbers = numbers_in(source)
    for n in sorted(numbers_in(claim.text) - src_numbers):
        flags.append(f"number '{n}' is not in the input")
    for term in sorted(named_terms(claim.text)):
        if not term_in_source(term, src_norm):
            flags.append(f"name '{term}' is not in the input")
    for word in sorted(inflated_words(claim.text)):
        if word not in src_norm.split():
            flags.append(f"inflated wording '{word}' is not in the input")
    if not claim.manual:
        if not claim.fact_ids:
            flags.append("cites no source fact")
        elif any(fid not in known_fact_ids for fid in claim.fact_ids):
            flags.append("cites a fact id that does not exist")
    return flags


def check_claims(record: ProjectRecord, llm: LLM | None, only_ids: set[str] | None = None) -> None:
    """Labels claims in place. only_ids = re-check just these (after an edit)."""
    source = record.input.source_text()
    known = {f.id for f in record.facts}
    targets = [c for c in record.active_claims() if only_ids is None or c.id in only_ids]
    if not targets:
        return

    for c in targets:
        c.rule_flags = rule_flags(c, source, known)

    verdicts: dict[str, Verdict] = {}
    if llm:
        claim_lines = "\n".join(f"{c.id}: {c.text}" for c in targets)
        result = llm.generate_json(
            prompts.CHECK_SYSTEM, prompts.CHECK_PROMPT.format(source=source, claims=claim_lines), CheckResult
        )
        record.llm_calls = llm.calls
        verdicts = {v.claim_id.strip(): v for v in result.verdicts}
    else:
        sentences = split_sentences(source)
        for c in targets:
            score, match = best_overlap(c.text, sentences)
            label = "supported" if score >= 0.85 else "reworded" if score >= 0.6 else "unsupported"
            reason = f"{round(score * 100)}% of the claim's words appear in one input sentence"
            verdicts[c.id] = Verdict(claim_id=c.id, label=label, reason=reason, evidence=match if score >= 0.6 else "")

    for c in targets:
        v = verdicts.get(c.id)
        if v is None:
            model_label, reason, evidence = Label.unsupported, "checker returned no verdict (fail closed)", ""
        else:
            try:
                model_label = Label(v.label.strip().lower())
            except ValueError:
                model_label = Label.unsupported
            reason, evidence = v.reason, v.evidence
        rule_label = Label.unsupported if c.rule_flags else None
        c.model_label = model_label
        c.label = worst(rule_label, model_label)
        c.reason = reason if not c.rule_flags else "; ".join(c.rule_flags) + (f" | {reason}" if reason else "")
        c.evidence = evidence
