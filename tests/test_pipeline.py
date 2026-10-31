"""End-to-end (offline) on the three sample inputs, plus the Gemini code path with a fake model."""

import pytest

from caseforge.checker import CheckResult, Verdict
from caseforge.extract import Extraction, ExtractedFact
from caseforge.generate import Written, WrittenSentence
from caseforge.llm import FakeLLM
from caseforge.models import BLOCKING_LABELS, Label
from caseforge.pipeline import generate

from .conftest import SAMPLE_FILES


@pytest.mark.parametrize("path", SAMPLE_FILES, ids=lambda p: p.parent.name)
def test_offline_draft_has_no_unsupported_claims(make_record, path):
    rec = generate(make_record(path), None)
    assert rec.status == "drafted"
    assert rec.claims, "a draft was produced"
    bad = [c for c in rec.active_claims() if c.label in BLOCKING_LABELS]
    assert bad == [], [(c.text, c.reason) for c in bad]


def test_missing_result_is_flagged_not_invented(make_record):
    rec = generate(make_record(SAMPLE_FILES[2]), None)  # pasted chat, no measured result
    results_gap = [g for g in rec.gaps if g.field == "results"]
    assert results_gap
    assert all("%" not in c.text for c in rec.active_claims("results"))


def test_clean_input_has_measurable_result(make_record):
    rec = generate(make_record(SAMPLE_FILES[0]), None)
    assert not [g for g in rec.gaps if g.field == "results"]
    assert rec.active_claims("results")


# ------------------------------------------------------------------ LLM path with a fake model
def _fake_gemini(invent_number=True, skip_verdict_for=None, model_says_supported=True):
    def respond(system, prompt, schema):
        if schema is Extraction:
            return Extraction(title_suggestion="Noodle inventory", client_name="", facts=[
                ExtractedFact(field="tools", statement="Python and React were used", quote="python + react"),
                ExtractedFact(field="results", statement="Friday count is faster", quote="friday count is way faster now"),
                # hallucinated quote -> must be dropped by grounding
                ExtractedFact(field="results", statement="Costs fell by half", quote="costs were cut in half"),
            ])
        if schema is Written:
            sentences = [
                WrittenSentence(section="tools", text="We built the dashboard with Python and React.", fact_ids=["F1"]),
                WrittenSentence(section="results", text="The Friday stock count is now faster.", fact_ids=["F2"]),
            ]
            if invent_number:
                sentences.append(WrittenSentence(section="results", text="Counting time fell by 40%.", fact_ids=["F2"]))
            return Written(sentences=sentences)
        if schema is CheckResult:
            ids = [line.split(":")[0] for line in prompt.split("CLAIMS:")[1].strip().splitlines()]
            label = "supported" if model_says_supported else "unsupported"
            return CheckResult(verdicts=[Verdict(claim_id=i, label=label, reason="ok") for i in ids if i != skip_verdict_for])
        raise AssertionError(schema)

    return FakeLLM(respond)


def test_hallucinated_fact_is_dropped(make_record):
    rec = generate(make_record(SAMPLE_FILES[1]), _fake_gemini())
    assert [f.statement for f in rec.dropped_facts] == ["Costs fell by half"]
    assert all("half" not in f.statement for f in rec.facts)


def test_rules_override_a_lenient_model(make_record):
    """The model says 'supported' to everything, but the invented 40% is still caught."""
    rec = generate(make_record(SAMPLE_FILES[1]), _fake_gemini(invent_number=True))
    planted = [c for c in rec.claims if "40%" in c.text][0]
    assert planted.label == Label.unsupported
    assert "number '40'" in planted.reason


def test_missing_verdict_fails_closed(make_record):
    rec = generate(make_record(SAMPLE_FILES[1]), _fake_gemini(invent_number=False, skip_verdict_for="C1"))
    assert rec.claim("C1").label == Label.unsupported


def test_checker_never_sees_the_facts_list(make_record):
    llm = _fake_gemini()
    generate(make_record(SAMPLE_FILES[1]), llm)
    check_prompt = llm.prompts[-1]
    assert "FACTS:" not in check_prompt and "SOURCE:" in check_prompt
