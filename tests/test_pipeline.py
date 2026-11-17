"""End-to-end (offline) on the three sample inputs, plus the Gemini code path with a fake model."""

import pytest

from caseforge.checker import CheckResult, Verdict
from caseforge.extract import Extraction, ExtractedFact
from caseforge.generate import Fix, Fixes, Written, WrittenSentence
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
        if schema is Fixes:   # the second try: this model has nothing better to offer
            return Fixes(fixes=[])
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
    check_prompt = [p for p in llm.prompts if "CLAIMS:" in p][-1]
    assert "FACTS:" not in check_prompt and "FACT F" not in check_prompt and "SOURCE:" in check_prompt


def _repairing_gemini(second_try: str):
    """Writes a summary with the roles mixed up (seen in a live run); the checker rejects it."""
    bad = "The factory used the factory's dashboard to count stock."

    def respond(system, prompt, schema):
        if schema is Extraction:
            return Extraction(facts=[
                ExtractedFact(field="work_done", statement="We built a dashboard", quote="we did a dashboard"),
                ExtractedFact(field="results", statement="Friday count is faster", quote="friday count is way faster now")])
        if schema is Written:
            return Written(sentences=[WrittenSentence(section="summary", text=bad, fact_ids=["F1"]),
                                      WrittenSentence(section="results", text="The Friday count is now faster.", fact_ids=["F2"])])
        if schema is Fixes:
            assert "REJECTED SENTENCE: " + bad in prompt and "FACT F1: We built a dashboard" in prompt and "WHY: roles" in prompt
            return Fixes(fixes=[Fix(claim_id="C1", text=second_try)])
        lines = [x.split(":", 1) for x in prompt.split("CLAIMS:")[1].strip().splitlines() if x[:1] == "C" and ":" in x]
        return CheckResult(verdicts=[Verdict(claim_id=i, label="unsupported" if "factory's" in t else "supported",
                                             reason="roles are the wrong way round" if "factory's" in t else "ok")
                                     for i, t in lines])
    return FakeLLM(respond)


def test_rejected_sentence_gets_a_second_try_and_is_checked_again(make_record):
    rec = generate(make_record(SAMPLE_FILES[1]), _repairing_gemini("We built a dashboard for the factory."))
    assert rec.claim("C1").text == "We built a dashboard for the factory." and not rec.claim("C1").blocking
    assert any(e.action == "sentence auto-repaired" for e in rec.history)


def test_second_try_that_fails_too_falls_back_to_the_fact_itself(make_record):
    rec = generate(make_record(SAMPLE_FILES[1]), _repairing_gemini("The factory's own dashboard counts the factory's stock."))
    assert rec.claim("C1").text == "We built a dashboard" and not rec.claim("C1").blocking


def test_format_with_model_flags_invented_number(make_record):
    """Gemini path for the extra formats: a sentence the model invents is still caught."""
    from caseforge import formats, review
    from caseforge.formats import FormatResult, FormatSentence
    rec = generate(make_record(SAMPLE_FILES[0]), None)
    for g in rec.gaps:
        if g.blocking:
            review.resolve_gap(rec, g.id, "ok", "t")
    review.approve(rec, "t")
    first = rec.active_claims()[0]

    def respond(system, prompt, schema):
        if schema is FormatResult:
            return FormatResult(sentences=[FormatSentence(text=first.text, source_ids=[first.id]),
                                           FormatSentence(text="Revenue doubled within 6 months.", source_ids=[first.id])])
        ids = [line.split(":")[0] for line in prompt.split("CLAIMS:")[1].strip().splitlines()]
        return CheckResult(verdicts=[Verdict(claim_id=i, label="supported") for i in ids])

    out = formats.build_format(rec, "linkedin", FakeLLM(respond))
    assert out.sentences[0].label == Label.supported
    assert out.sentences[1].label == Label.unsupported
    assert not formats.format_ready(rec, "linkedin")


def test_account_settings(tmp_path):
    from caseforge.db import DB, AuthError
    import pytest
    d = DB(f"sqlite:///{tmp_path}/t.db")
    a = d.signup("Abdulaziz Rizamukhamedov", "a@x.io", "password1")
    assert a["workspace_name"] == "Abdulaziz's workspace"
    b = d.signup("Husan", "h@x.io", "password2", invite_code=a["invite_code"])
    ws = a["workspace_id"]
    assert [m["owner"] for m in d.members(ws)] == [True, False]
    with pytest.raises(AuthError):
        d.rename_workspace(b["id"], ws, "Team 5")  # only the owner
    d.rename_workspace(a["id"], ws, "HumbleBee Studio")
    assert d.user(b["id"])["workspace_name"] == "HumbleBee Studio"
    old = a["invite_code"]; assert d.new_invite_code(a["id"], ws) != old
    with pytest.raises(AuthError):
        d.update_profile(a["id"], "Aziz", "h@x.io")  # email taken
    assert d.update_profile(a["id"], "Aziz", "aziz@x.io")["name"] == "Aziz"
    with pytest.raises(AuthError):
        d.change_password(a["id"], "wrong-pass", "newpassword")
    d.change_password(a["id"], "password1", "newpassword")
    d.login("aziz@x.io", "newpassword")
    d.remove_member(a["id"], ws, b["id"])
    assert d.user(b["id"])["workspace_id"] != ws
    d.create_project(ws, a["id"], __import__("caseforge.models", fromlist=["ProjectInput"]).ProjectInput(title="t", raw_notes="n"))
    d.delete_account(a["id"], "newpassword")
    assert d.user(a["id"]) is None and d.list_projects(ws) == []


def test_slow_gemini_switches_model_then_gives_up():
    import time
    import httpx
    from pydantic import BaseModel
    from caseforge import llm as L

    class S(BaseModel):
        x: int = 0
    calls = []

    class Models:
        def generate_content(self, model, **k):
            calls.append(model)
            if model == "main":
                raise httpx.ReadTimeout("slow")
            return type("R", (), {"parsed": S(x=1), "text": ""})()
    g = L.GeminiLLM.__new__(L.GeminiLLM)
    g._client = type("C", (), {"models": Models()})()
    g.model, g.fallbacks, g.max_attempts, g.calls, g.budget_until = "main", ("backup",), 3, 0, 0.0
    assert g.generate_json("s", "p", S).x == 1 and calls == ["main", "main", "backup"]
    g.fallbacks, g.budget_until = (), time.monotonic() - 1   # job time used up: fail fast, no call
    calls.clear()
    import pytest
    with pytest.raises(L.LLMError):
        g.generate_json("s", "p", S)
    assert calls == []


def test_writer_gets_a_sentence_budget_and_section_rules():
    """Third live run: 51 facts came back as 50 sentences in the extractor's sections (contract dates and
    team size under Results). Long notes are condensed; the [field] is only a first guess."""
    from caseforge import prompts
    from caseforge.generate import _write_llm, sentence_budget
    from caseforge.llm import FakeLLM
    from caseforge.models import Fact, ProjectInput
    from caseforge.generate import Written

    assert sentence_budget(5)["budget"] == 5 and sentence_budget(51)["budget"] == 26
    assert sentence_budget(200)["cap"] <= 36
    seen = {}

    def respond(system, prompt, schema):
        seen["system"], seen["prompt"] = system, prompt
        return Written(sentences=[])

    facts = [Fact(id=f"F{i}", field="results", statement=f"Fact number {i}.", quote=f"Fact number {i}.")
             for i in range(1, 52)]
    _write_llm(ProjectInput(raw_notes="x"), facts, FakeLLM(respond))
    assert "about 26 sentences" in seen["prompt"] and "never more than 31" in seen["prompt"]
    assert "A date, budget or team size is NOT a result" in seen["system"]
    assert "{fields}" not in prompts.WRITE_SYSTEM
