"""Designed report: brand kits, smarter checks, planner, approval gate, PDF render."""

import json
from pathlib import Path

import pytest

from caseforge import report, review
from caseforge.brandkit import BrandKit, contrast, from_guidelines, kit_warnings, load, text_warnings
from caseforge.checker import CheckResult, Verdict
from caseforge.extract import Extraction, ExtractedConflict, ExtractedFact, chunks
from caseforge.generate import Written, WrittenSentence
from caseforge.llm import FakeLLM
from caseforge.models import Label, ProjectInput
from caseforge.pipeline import generate
from caseforge.render import ExportBlocked
from caseforge.render.report_pdf import render_report, report_html
from caseforge.report import ReportPlan
from caseforge.textutil import estimate_flags, locate_quote

ROOT = Path(__file__).resolve().parent.parent
NOTES = (ROOT / "samples" / "04_northwind" / "notes.txt").read_text()
FIXTURE = json.loads((ROOT / "tests" / "fixtures" / "northwind_plan.json").read_text())


# ------------------------------------------------------------------ smarter checks
def test_estimate_must_stay_an_estimate():
    src = "Annual savings estimate given by the finance director was 1.1 million euros, not verified."
    assert estimate_flags("The system saves 1.1 million euros a year.", src)
    assert not estimate_flags("Savings are estimated at 1.1 million euros a year.", src)


def test_quote_location_names_file_and_line():
    src = "[Raw notes]\n--- from metrics.docx ---\nintro line\nfuel consumption down 9.4 percent"
    assert locate_quote("fuel consumption down 9.4 percent", src) == "metrics.docx, line 2"


def test_big_dump_is_read_in_parts():
    text = "\n\n".join(f"Paragraph {i} " + "word " * 300 for i in range(40))
    parts = chunks(text)
    assert len(parts) > 1 and all(len(p) <= 9000 + 2000 for p in parts)
    assert "".join(parts).count("Paragraph") == 40


def test_conflicting_numbers_become_a_blocking_question(store):
    def respond(system, prompt, schema):
        if schema is Extraction:
            return Extraction(facts=[ExtractedFact(field="work_done", statement="Team began at 6 people",
                                                   quote="Team headcount began at 6 people")],
                              conflicts=[ExtractedConflict(topic="team size", values=["6", "11", "9", "42"])])
        if schema is Written:
            return Written(sentences=[WrittenSentence(section="work_done", text="The team began with 6 people.", fact_ids=["F1"])])
        ids = [x.split(":")[0] for x in prompt.split("CLAIMS:")[1].strip().splitlines()]
        return CheckResult(verdicts=[Verdict(claim_id=i, label="supported") for i in ids])

    rec = generate(store.create(ProjectInput(raw_notes=NOTES)), FakeLLM(respond))
    assert rec.conflicts and rec.conflicts[0].values == ["6", "11", "9"]  # "42" isn't in the notes
    g = [g for g in rec.gaps if g.field.startswith("conflict")][0]
    assert g.blocking
    review.resolve_gap(rec, g.id, "9 distinct people over the whole project", "Odina")
    assert any("Confirmed by Odina" in a for a in rec.input.reviewer_additions)


# ------------------------------------------------------------------ brand kit
def test_brand_guidelines_import_offline():
    kit = from_guidelines((ROOT / "samples" / "brands" / "northwind_brand_guidelines.md").read_text(), None, "NW")
    assert kit.colors.primary == "#0E6E73" and kit.colors.accent == "#F2765C"
    assert kit.heading_font == "Plus Jakarta Sans" and kit.body_font == "Source Serif 4"
    assert "best-in-class" in kit.banned_words


def test_brand_checks():
    bad = BrandKit(colors={"ink": "#BBBBBB", "paper": "#FFFFFF"})
    assert any("hard to read" in w for w in kit_warnings(bad))
    assert contrast("#000000", "#FFFFFF") > 20
    kit = load("northwind")
    w = text_warnings(kit, [("subtitle", "A best-in-class platform.")])
    assert any("best-in-class" in x for x in w)


# ------------------------------------------------------------------ planner + approval gate
@pytest.fixture
def approved(make_record):
    from .conftest import SAMPLE_FILES
    rec = generate(make_record(SAMPLE_FILES[0]), None)
    for g in rec.gaps:
        if g.blocking:
            review.resolve_gap(rec, g.id, "ok", "t")
    review.approve(rec, "Abdulaziz")
    return rec


def test_report_needs_an_approved_case_study(make_record):
    from .conftest import SAMPLE_FILES
    rec = generate(make_record(SAMPLE_FILES[0]), None)
    with pytest.raises(review.ReviewError):
        report.build_report(rec, load("humblebee"), None)


def test_offline_report_flow_and_gate(approved, tmp_path):
    d = report.build_report(approved, load("northwind"), None)
    assert d.plan.title and d.elements and not d.blocking
    with pytest.raises(ExportBlocked):
        render_report(approved, tmp_path / "r.pdf")  # not approved yet
    report.approve_report(approved, "Abdulaziz")
    assert report.report_ready(approved)
    report.edit_element(approved, "subtitle", d.plan.subtitle + " ", None)  # same words → still fine
    review.edit_claim(approved, "C2", "Reception staff phoned every patient the day before.", None)
    assert not report.report_ready(approved)  # case study changed → report must be redesigned


def test_model_plan_with_invented_number_is_flagged(approved):
    first = approved.active_claims()[0]

    def respond(system, prompt, schema):
        if schema is report.PlanOut:
            return report.PlanOut(title="Clinic no-shows", subtitle=first.text, cites=[{"field": "subtitle", "ids": [first.id]}],
                              metrics=[{"value": "45", "unit": "%", "label": "fewer no-shows", "cites": [first.id]}])
        ids = [x.split(":")[0] for x in prompt.split("CLAIMS:")[1].strip().splitlines()]
        return CheckResult(verdicts=[Verdict(claim_id=i, label="supported") for i in ids])

    d = report.build_report(approved, load("humblebee"), FakeLLM(respond))
    bad = [e for e in d.elements if e.id == "metrics.0"][0]
    assert bad.label == Label.unsupported and "45" in bad.reason
    with pytest.raises(review.ReviewError):
        report.approve_report(approved, "t")
    report.remove_element(approved, "metrics.0")
    report.approve_report(approved, "t")
    assert report.report_ready(approved)


def test_repeats_and_unlabelled_estimates_are_warned():
    plan = ReportPlan.model_validate(FIXTURE)
    plan.challenge_intro = "Fuel use fell 9.4 percent."  # 9.4 is also a big number on the results page
    plan.metrics[3].estimate = False              # 1.1 M€ is an estimate in the notes
    w = report.report_warnings(plan, load("northwind"), NOTES)
    assert any("'9.4' appears twice" in x for x in w)
    assert any("ESTIMATED" in x for x in w)


def test_html_uses_brand_and_pale_colours_never_become_text():
    from caseforge.models import ProjectRecord
    plan = ReportPlan.model_validate(FIXTURE)
    rec = ProjectRecord(id="x", input=ProjectInput(raw_notes=NOTES))
    hb = report.ReportDesign(brand=load("humblebee"), plan=plan)
    html = report_html(rec, hb)
    assert "'Manrope'" in html and "--pri-ink: #111111" in html  # yellow is too pale for text on white
    nw = report_html(rec, report.ReportDesign(brand=load("northwind"), plan=plan))
    assert "'Plus Jakarta Sans'" in nw and "--pri-ink: #0E6E73" in nw
    assert "ESTIMATED" in html and "DRAFT" in html


def test_pdf_render_is_five_pages(approved, tmp_path):
    pytest.importorskip("playwright")
    from pypdf import PdfReader
    report.build_report(approved, load("humblebee"), None)
    try:
        out = render_report(approved, tmp_path / "draft.pdf", draft=True)
    except Exception as e:  # no Chromium installed on this machine
        pytest.skip(f"Chromium not available: {e}")
    pages = PdfReader(out).pages
    assert 3 <= len(pages) <= 5


# ------------------------------------------------------------------ content-driven layout
def _plan(**changes):
    raw = json.loads(json.dumps(FIXTURE))
    raw.update(changes)
    return ReportPlan.model_validate(raw)


def test_layout_follows_the_content():
    from caseforge.layout import compose
    impact = compose(_plan())
    assert impact.story == "impact" and impact.cover == "hero-number"
    assert impact.pages[0].sections[0].key == "summary"            # the executive summary leads, with the numbers
    assert any(b.kind == "metrics" for b in impact.pages[0].sections[0].blocks)
    assert impact.hero_metric >= 0 and not FIXTURE["metrics"][impact.hero_metric].get("estimate")
    assert impact.notes

    change = compose(_plan(metrics=[], comparisons=FIXTURE["comparisons"][:1], quote={}))
    assert change.story == "transformation" and change.cover == "from-to"

    events = [{"when": w, "text": "x"} for w in ("Feb 2024", "Mar 2024", "June 2024", "Nov 2024")]
    journey = compose(_plan(metrics=[], comparisons=[], timeline=events))
    assert journey.story == "journey"
    impl = next(s for p in journey.pages for s in p.sections if s.key == "implementation")
    assert impl.label == "How it unfolded" and any(b.kind == "timeline" and b.variant == "gantt" for b in impl.blocks)

    people = compose(_plan(metrics=[], comparisons=[]))
    assert people.story == "people" and people.cover == "quote"

    # block shapes follow how much there is
    one = compose(_plan(challenges=FIXTURE["challenges"][:1]))
    kinds = {(b.kind, b.variant) for p in one.pages for s in p.sections for b in s.blocks}
    assert ("challenges", "statement") in kinds
    assert len({impact.story, change.story, journey.story, people.story}) == 4
    assert all(2 <= len(x.pages) <= 6 for x in (impact, change, journey, people))


def test_hero_number_is_not_repeated_inside():
    plan = _plan()
    from caseforge.models import ProjectRecord
    rec = ProjectRecord(id="x", input=ProjectInput(raw_notes=NOTES))
    d = report.ReportDesign(brand=load("northwind"), plan=plan)
    from caseforge.layout import compose
    d.layout = compose(plan)
    html = report_html(rec, d)
    hero = plan.metrics[d.layout.hero_metric]
    assert html.count(f">{hero.value}<small>") == 1


def test_every_model_schema_works_with_gemini_developer_api():
    """Gemini's Developer API rejects JSON schemas with free-form maps (additionalProperties)."""
    from caseforge.checker import CheckResult
    from caseforge.extract import Extraction
    from caseforge.formats import FormatResult
    from caseforge.generate import Written
    for schema in (report.PlanOut, report.ChatOut, BrandKit, CheckResult, Extraction, FormatResult, Written):
        text = json.dumps(schema.model_json_schema())
        assert "additionalProperties" not in text, schema.__name__


def test_title_case_and_missing_citations_are_not_false_flags(approved):
    """Real Gemini runs: Title Case step titles and uncited framing lines were flagged although true."""
    first, second = approved.active_claims()[0], approved.active_claims()[1]

    def respond(system, prompt, schema):
        if schema is report.PlanOut:
            return report.PlanOut(title="Clinic reminders", subtitle=first.text,  # no cites given
                                  steps=[{"title": "Reminder Scheduling", "text": second.text, "cites": [second.id]}])
        ids = [x.split(":")[0] for x in prompt.split("CLAIMS:")[1].strip().splitlines()]
        return CheckResult(verdicts=[Verdict(claim_id=i, label="supported") for i in ids])

    d = report.build_report(approved, load("humblebee"), FakeLLM(respond))
    byid = {e.id: e for e in d.elements}
    assert byid["subtitle"].fact_ids == [first.id] or first.id in byid["subtitle"].fact_ids
    assert byid["subtitle"].label == Label.supported, byid["subtitle"].reason
    assert byid["steps.0"].label == Label.supported, byid["steps.0"].reason


# ------------------------------------------------------------------ art direction, themes, chat, auto brand
def test_art_direction_and_reviewer_prefs_change_the_layout():
    from caseforge.layout import Prefs, compose
    plan = _plan()
    base = compose(plan)
    assert base.theme == "bold" and base.frame == "dashboard"  # impact story → bold tiles by default
    alt = compose(plan, Prefs(story="people", cover="quote", theme="editorial", order=["challenge", "solution"],
                              variants=["metrics=row"], hide=["tech"], reason="Story-led client"))
    assert (alt.story, alt.cover, alt.theme) == ("people", "quote", "editorial")
    keys = [s.key for pg in alt.pages for s in pg.sections]
    assert [k for k in keys if k not in ("summary", "intro")][0] == "challenge"   # the summary always opens
    blocks = [b for p in alt.pages for s in p.sections for b in s.blocks]
    assert not any(b.kind == "tech" for b in blocks)
    assert any("Story-led client" in n for n in alt.notes)
    # impossible choices are ignored: no dates → no journey; no comparisons → no from-to cover
    imp = compose(_plan(comparisons=[]), Prefs(story="journey", cover="from-to"))
    assert imp.story != "journey" and imp.cover != "from-to"


def test_report_chat_offline_changes_layout_and_withdraws_approval(approved):
    report.build_report(approved, load("northwind"), None)
    report.approve_report(approved, "Abdulaziz")
    reply = report.chat_report(approved, "make it dark like a magazine and hide the timeline, use #E63946", None, "Abdulaziz")
    d = approved.report
    assert d.layout.frame == "magazine"
    assert d.layout.theme == "dark" and "timeline" in d.prefs.hide and d.brand.colors.primary == "#E63946"
    assert not report.report_ready(approved)            # any change needs a new approval
    assert d.chat[-1].role == "ai" and reply


def test_report_chat_text_change_is_fact_checked(approved):
    d = report.build_report(approved, load("humblebee"), None)

    def respond(system, prompt, schema):
        if schema is report.ChatOut:
            return report.ChatOut(reply="Changed the subtitle.",
                                  ops=[report.ChatOp(op="text", target="subtitle", value="No-shows fell by 80% overnight.")])
        ids = [x.split(":")[0] for x in prompt.split("CLAIMS:")[1].strip().splitlines()]
        return CheckResult(verdicts=[Verdict(claim_id=i, label="supported") for i in ids])

    reply = report.chat_report(approved, "make the subtitle punchier", FakeLLM(respond))
    sub = [e for e in approved.report.elements if e.id == "subtitle"][0]
    assert sub.label == Label.unsupported and "80" in sub.reason   # the invented number is caught
    assert "Heads up" in reply


def test_brand_swap_keeps_content_and_auto_brand_follows_the_notes(approved):
    from caseforge.brandkit import auto_brand
    d = report.build_report(approved, load("humblebee"), None)
    before = [e.text for e in d.elements]
    report.set_brand(approved, load("northwind"))
    assert [e.text for e in approved.report.elements] == before and approved.report.brand.name.startswith("Northwind")
    assert auto_brand(NOTES).name == "Auto · logistics"
    assert auto_brand("Patients at the clinic missed appointments.").name == "Auto · health"
    assert auto_brand("").name == "Auto · technology"


# ------------------------------------------------------------------ publishable output: wrapped notes, tidy plans, full pages
WRAPPED = """Raw Project Information: Northwind Digital Works - Meridian /
Dispatch Optimizer

Typed from Tomas Ferreira's notebook (backend lead): the routing engine is written in Python 3.11
with Google OR-Tools for the vehicle routing problem solver. Solver time for 220 stops was 94
seconds in the first build, reduced to 9 seconds after moving the distance matrix calculation to a
precomputed cache in Redis. Deployed on AWS eu-west-1 using Terraform and ECS Fargate.

Metrics sent by Priya Raman, project manager, three days after go-live: 1,340 routes planned in
the first 72 hours, 96.2 percent of drivers logged in successfully on the first day, planning time per
morning reduced from about 18 minutes to 3 minutes for each dispatcher. Late deliveries were
reduced from 14 percent to 6.1 percent. Contract signed 9 February 2024, kickoff on 4 March 2024.
The system went live on 18 November 2024 and the pilot was completed in February 2025.
"""


def test_hard_wrapped_notes_are_read_as_whole_sentences():
    from caseforge.textutil import number_is_hedged, split_sentences
    sents = split_sentences(WRAPPED)
    assert any(s.endswith("precomputed cache in Redis.") and "94 seconds" in s for s in sents)  # 3 lines → 1 sentence
    assert not any(s.endswith(("was 94", "planned in", "time per")) for s in sents)
    assert split_sentences("a: one\nb: two\nc: three\nd: four") == ["a: one", "b: two", "c: three", "d: four"]  # chat stays as lines
    # the estimate belongs to its own number, not to every number in a long sentence
    long = next(s for s in sents if "96.2" in s)
    assert number_is_hedged(long, "18") and not number_is_hedged(long, "96.2")
    assert "line" in locate_quote("Solver time for 220 stops was 94 seconds in the first build", WRAPPED)


def test_offline_report_from_wrapped_notes_is_clean(store):
    rec = generate(store.create(ProjectInput(raw_notes=WRAPPED)), None)
    assert rec.input.title == "Northwind Digital Works - Meridian / Dispatch Optimizer"
    for g in rec.gaps:
        if g.blocking:
            review.resolve_gap(rec, g.id, "ok", "t")
    review.approve(rec, "A")
    d = report.build_report(rec, load("northwind"), None)
    p = d.plan
    assert not d.blocking, [(e.id, e.reason) for e in d.blocking]
    texts = [t for _, t, _ in report.elements_of(p)]
    assert not any("…" in t for t in texts)                                   # nothing is cut mid-sentence
    assert "Tomas" not in p.tech and "Priya" not in p.tech and {"Python", "Terraform"} <= set(p.tech)
    pairs = {k.label: (k.before, k.after, k.estimate) for k in p.comparisons}
    assert pairs["Late deliveries"] == (14, 6.1, False)
    assert pairs["Planning time per morning"] == (18, 3, True)               # "about 18 minutes" stays an estimate
    assert pairs["Solver time for 220 stops"] == (94, 9, False)
    assert [m.value for m in p.metrics] == ["96.2"] and not p.metrics[0].estimate
    assert [e.when for e in p.timeline][:3] == ["9 February 2024", "4 March 2024", "18 November 2024"]
    assert "ESTIMATED" in report_html(rec, d)


def test_polish_only_removes():
    plan = _plan(tech=["Python", "Tomas", "ECS", "ECS Fargate", "python", "Priya Raman"],
                 metrics=[{"value": "14", "unit": "%", "label": "late deliveries before"},
                          {"value": "11.8", "unit": "%", "label": "average improvement"}],
                 comparisons=[{"label": "Late deliveries", "before": 14, "after": 6.1, "unit": "%"}],
                 challenge_intro="Routes were planned by hand.",
                 challenges=[{"title": "Manual", "text": "Routes were planned by hand."}, {"title": "", "text": "  "}])
    out = report.polish(plan, WRAPPED)
    assert out.tech == ["Python", "ECS Fargate"]                              # no people, no duplicates, no fragments
    assert [m.value for m in out.metrics] == ["11.8"]                         # 14 % is already in the chart
    assert out.challenges == []                                               # said once already; empty item gone


def test_shorten_never_cuts_mid_phrase_or_drops_a_hedge():
    assert report.shorten("Created 3 rounds of Figma prototypes, tested with 6 users in the second round, and more "
                          "text that makes this sentence far too long for a card.", 60) == "Created 3 rounds of Figma prototypes."
    assert report.shorten("We wrote a mock server of the interface to continue development, but it caused 14 defects "
                          "when the real one behaved differently.", 70) == ""    # the "but" matters
    assert report.shorten("Savings were 1.1 million euros for the first full year of operation, although that "
                          "number is an estimate nobody verified.", 70) == ""    # the estimate wording would be lost


def test_pages_are_balanced_and_a_long_solution_is_split():
    from caseforge.layout import Prefs, compose
    big = _plan(pillars=[{"title": f"Part {i}", "text": "A part of the work described in one full sentence of normal length."}
                         for i in range(4)],
                steps=[{"title": f"Step {i}", "text": "What happens in this step."} for i in range(5)],
                timeline=[{"when": f"{m} 2024", "text": "Something was delivered."} for m in ("March", "May", "July", "October")])
    for frame in ("stack", "sidebar", "magazine", "dashboard", "split"):
        L = compose(big, Prefs(frame=frame))
        loads = [sum(s.weight for s in p.sections) for p in L.pages]
        assert 2 <= len(L.pages) <= 7 and max(loads) <= 112, (frame, loads)
        assert min(loads) >= 35, (frame, loads)                              # no half-empty page
        for p in L.pages:                                                    # a heading always has content under it
            for s in p.sections:
                assert s.key == "close" or any(b.slot == "main" for b in s.blocks), (frame, s.key)
    # a section too long for one page continues on the next
    huge = _plan(pillars=[{"title": f"Part {i}", "text": "A part of the work described in one long sentence that runs on "
                                                          "for a while so the card is tall. " * 3} for i in range(8)],
                 solution_intro="We built it. " * 16)
    keys = [s.key for p in compose(huge, Prefs(frame="stack")).pages for s in p.sections]
    assert "solution" in keys and "solution+" in keys


# ------------------------------------------------------------------ real-model failure modes (seen on a live Gemini run)
@pytest.fixture
def northwind(store):
    rec = generate(store.create(ProjectInput(raw_notes=NOTES)), None)
    for g in rec.gaps:
        if g.blocking:
            review.resolve_gap(rec, g.id, "ok", "t")
    review.approve(rec, "A")
    return rec


def _all_supported(prompt):
    ids = [x.split(":")[0] for x in prompt.split("CLAIMS:")[1].strip().splitlines()]
    return CheckResult(verdicts=[Verdict(claim_id=i, label="supported") for i in ids])


def test_thin_model_plan_is_filled_and_bad_citations_do_not_block(northwind):
    """The live run returned 7 elements, cited ids that don't exist, and two true lines were blocked for it."""
    def respond(system, prompt, schema):
        if schema is report.PlanOut:
            return report.PlanOut(title="Dispatch Optimizer", subtitle="Meridian case study for Calloway Freight Group",
                                  brief="Meridian dispatch optimization for Calloway Freight Group.",
                                  cites=[{"field": "brief", "ids": ["F99"]}])
        return _all_supported(prompt)

    d = report.build_report(northwind, load("northwind"), FakeLLM(respond))
    assert not d.blocking, [(e.id, e.reason) for e in d.blocking]            # no "cites no source fact"
    p = d.plan
    assert p.subtitle.startswith("Meridian case study")                       # the model's own words are kept
    assert p.comparisons and p.metrics and p.timeline and p.tech and p.challenges and p.quote.text   # the rest is filled
    assert any("filled by rules" in w for w in d.warnings)
    assert len(d.elements) > 15 and 2 <= len(d.layout.pages) <= 12
    cov = d.coverage                                                          # every approved sentence somewhere
    assert cov["total"] == cov["designed"] + cov["facts"] == len(northwind.active_claims())
    assert len(d.plan.facts) == cov["facts"]


def test_second_live_run_three_flags_are_settled_without_the_reviewer(northwind):
    """Seen live: a true subtitle failed for "not phrased as a subtitle", a headline said "significantly",
    and "from 18minutes to 3minutes (estimated)" failed for the ESTIMATED tag the notes call for."""
    def respond(system, prompt, schema):
        if schema is report.PlanOut:
            return report.PlanOut(
                title="Dispatch Optimizer", subtitle="Reducing planning time for Calloway Freight Group",
                headlines={"results": "Planning time reduced significantly", "solution": "A routing engine in the cloud"},
                comparisons=[{"label": "Planning time", "before": 18, "after": 3, "unit": "minutes", "estimate": True},
                             {"label": "Late deliveries", "before": 14, "after": 9, "unit": "%"}],
                outcomes=[{"title": "Award", "text": "The project won a national award in 2031."}])
        out = []
        for line in prompt.split("CLAIMS:")[1].strip().splitlines():
            if ": " not in line:
                continue
            i, text = line.split(": ", 1)
            if i == "subtitle" and text.startswith("Reducing"):
                out.append(Verdict(claim_id=i, label="unsupported", reason="The subtitle introduces a purpose not phrased as a subtitle in the source."))
            elif i == "headlines.solution":
                out.append(Verdict(claim_id=i, label="unsupported", reason="The cloud is an inference."))
            elif "(estimated)" in text and i.startswith("comparisons"):
                assert "18 minutes" in text                                       # written the way the notes write it
                out.append(Verdict(claim_id=i, label="unsupported", reason="It adds the tag '(estimated)' which is not stated for this metric."))
            elif "from 14 percent to 9" in text:
                out.append(Verdict(claim_id=i, label="contradicted", reason="The source says 6.1 percent."))
            else:
                out.append(Verdict(claim_id=i, label="supported"))
        return CheckResult(verdicts=out)

    d = report.build_report(northwind, load("northwind"), FakeLLM(respond))
    p, flagged = d.plan, {e.id: e.reason for e in d.blocking}
    assert p.headlines.results == "Planning time reduced"                       # the degree word is gone, the fact stays
    assert p.headlines.solution == ""                                           # rejected headline → the plain section label
    assert not p.subtitle.startswith("Reducing") and "subtitle" not in flagged  # replaced by an approved sentence
    est = next(e for e in d.elements if e.id == "comparisons.0")
    assert est.label == Label.reworded and "about 18 minutes" in est.evidence   # the tag stands: the notes hedge it
    # real problems are never repaired away: a wrong number and an invented outcome stay red
    assert "comparisons.1" in flagged and any(k.startswith("outcomes") for k in flagged)
    assert any("replaced by plain labels" in w for w in d.warnings)


def test_busy_model_falls_back_instead_of_failing(northwind):
    from caseforge.llm import LLMError

    def busy(system, prompt, schema):
        raise LLMError("Gemini API error 503: UNAVAILABLE")

    d = report.build_report(northwind, load("northwind"), FakeLLM(busy))
    assert d.plan.metrics and not d.blocking
    assert any("AI designer was busy" in w for w in d.warnings) and any("AI checker was busy" in w for w in d.warnings)


def test_redesign_never_repeats_and_graphs_follow_the_numbers(northwind):
    from caseforge.layout import Prefs, compose
    looks = []
    for _ in range(4):
        d = report.build_report(northwind, load("northwind"), None)
        looks.append((d.layout.frame, d.layout.theme))
    assert all(a != b for a, b in zip(looks, looks[1:])) and len(set(looks)) >= 3
    two = _plan(comparisons=FIXTURE["comparisons"][:2] if len(FIXTURE["comparisons"]) >= 2 else
                [{"label": "A", "before": 14, "after": 6, "unit": "%"}, {"label": "B", "before": 18, "after": 3, "unit": " min"}])
    kinds = {(b.kind, b.variant) for pg in compose(two, Prefs(frame="stack")).pages for s in pg.sections for b in s.blocks}
    assert ("comparison", "columns") in kinds                                 # two pairs → columns
    money = _plan(metrics=[{"value": "1.1", "unit": "M €", "label": "savings"}, {"value": "96.2", "unit": "%", "label": "of drivers"}])
    kinds = {(b.kind, b.variant) for pg in compose(money, Prefs(frame="stack", cover="motif", variants=["metrics=rings"])).pages
             for s in pg.sections for b in s.blocks}
    assert ("metrics", "rings") not in kinds                                  # euros are never drawn as a percentage ring


def test_a_value_that_changes_over_time_is_not_a_conflict():
    from caseforge.extract import conflicts_from
    raw = Extraction(facts=[], conflicts=[ExtractedConflict(topic="Team headcount", values=["6 people", "11 in August 2024"]),
                                          ExtractedConflict(topic="team size", values=["6", "11", "9"])])
    out = conflicts_from(raw, NOTES)
    assert [c.topic for c in out] == ["team size"]      # 6 → 11 is a history; 6 / 11 / 9 is a real question


def test_a_persons_workspace_name_is_never_printed_and_the_chat_can_change_the_header(northwind):
    """Seen live: "Abdulaziz's workspace" sat in the corner of every page, and the chat could not remove it."""
    from caseforge.brandkit import auto_brand, publisher
    assert publisher("Abdulaziz's workspace") == "" and publisher("Northwind Digital Works") == "Northwind Digital Works"
    d = report.build_report(northwind, auto_brand(NOTES, publisher("Abdulaziz's workspace")), None)
    html = report_html(northwind, d)
    assert "workspace" not in html and "Your company" not in html and "Auto ·" not in html
    d.brand.company = "Abdulaziz's workspace"                                  # a report designed before this fix
    assert "Abdulaziz" not in report_html(northwind, d)

    def model(system, prompt, schema):
        assert '"op":"brand"' in system and "hide" in system
        if "call us" in prompt.rsplit("REVIEWER:", 1)[-1]:
            return report.ChatOut(reply="Done.", ops=[report.ChatOp(op="brand", target="name", value="Northwind Digital Works")])
        return report.ChatOut(reply="", ops=[report.ChatOp(op="layout", target="hide", value="brand")])
    report.chat_report(northwind, "call us Northwind Digital Works", FakeLLM(model), "A")
    assert report_html(northwind, northwind.report).count("Northwind Digital Works") >= 3   # header on each page + footer
    reply = report.chat_report(northwind, "remove the header from all pages", FakeLLM(model), "A")
    assert "taken off the pages" in reply and 'class="wordmark"' not in report_html(northwind, northwind.report)
    report.chat_report(northwind, "remove my name from the header", None, "A")       # works without AI too
    assert "brand" in northwind.report.prefs.hide


def test_redesign_keeps_the_checked_text_and_everyday_abbreviations_are_not_names(northwind):
    """Seen live: every Redesign re-worded the report, and now and then a new line turned red —
    "name 'UI' is not in the input" for a sentence about the interface."""
    from caseforge.textutil import named_terms
    assert "UI" not in named_terms("A driver application with high-contrast UI for truck cabs")
    assert {"API", "GPS"} <= named_terms("The app uses the API and GPS")       # real technology is still a name
    calls = []

    def model(system, prompt, schema):
        calls.append(schema.__name__)
        if schema is report.PlanOut:
            return report.PlanOut(title="Dispatch Optimizer", solution_intro="We built a routing engine with a clear UI.")
        return _all_supported(prompt)

    d = report.build_report(northwind, load("northwind"), FakeLLM(model))
    assert not d.blocking
    texts, look, n = [e.text for e in d.elements], (d.layout.frame, d.layout.theme), len(calls)
    for _ in range(3):
        d = report.redesign(northwind, "A")
        assert [e.text for e in d.elements] == texts and not d.blocking         # same words, still all backed
        assert (d.layout.frame, d.layout.theme) != look                         # a different look each time
        look = (d.layout.frame, d.layout.theme)
    assert len(calls) == n                                                      # and no AI call at all


# ------------------------------------------------------------------ third live run (14 Nov)
def test_estimate_is_not_lost_when_the_same_number_is_also_a_date():
    """Live: the chat wrote "Cutting route planning from 18 minutes to 3" (dropping "about") and it passed,
    because "18 November" made 18 look unhedged. Same with "I think … was 9" next to "9 February"."""
    assert estimate_flags("Cutting route planning from 18 minutes to 3", NOTES)
    assert not estimate_flags("A routing engine and driver app that cut planning time from about 18 minutes to 3", NOTES)
    assert estimate_flags("The final count on the payroll sheet was 9 distinct people over the whole project.", NOTES)
    assert not estimate_flags("The system went live on 18 November 2024.", NOTES)
    assert not estimate_flags("We interviewed 9 dispatchers and 12 drivers.", NOTES)


def test_polish_shows_each_number_once_and_keeps_new_clauses():
    """Live: 96.2 %, 9.4 % and 14 % → 6.1 % were each printed as a big number AND inside an outcome."""
    plan = ReportPlan(
        title="Dispatch Optimizer", subtitle="Planning time cut from about 18 minutes to 3",
        brief="We cut planning time from about 18 minutes to 3 minutes.",
        challenge_intro="Calloway operates 14 warehouses.",
        metrics=[{"value": "96.2", "unit": "percent", "label": "drivers logged in on day one"},
                 {"value": "9.4", "unit": "%", "label": "less fuel"}],
        comparisons=[{"label": "Late deliveries", "before": 14, "after": 6.1, "unit": "%"}],
        outcomes=[{"title": "Adoption", "text": "1,340 routes planned in the first 72 hours and 96.2 percent of drivers "
                                                "logged in successfully on the first day"},
                  {"title": "Fuel", "text": "Fuel consumption down 9.4 percent and late deliveries reduced from "
                                            "14 percent to 6.1 percent"}],
        timeline=[{"when": "9 February 2024", "text": "Contract signed 9 February 2024."},
                  {"when": "30 September 2024", "text": "Original go-live was 30 September 2024."}])
    p = report.polish(plan, NOTES)
    assert p.metrics[0].unit == "%"                                     # "96.2%", not "96.2percent"
    assert p.brief == ""                                                # only restated the cover
    assert [o.text for o in p.outcomes] == ["1,340 routes planned in the first 72 hours"]
    assert p.comparisons                                                # "14 warehouses" is not "14 %"
    assert [e.text for e in p.timeline] == ["Contract signed.", "Original go-live."]
    assert not [w for w in report.report_warnings(p, load("northwind"), NOTES) if "twice" in w]


def test_shorten_never_leaves_a_heading_before_a_colon():
    text = ("Two production incidents in the first month: a timezone error for the Poland border routes on "
            "24 November and a cache invalidation problem on 2 December.")
    assert report.shorten(text, 90) != "Two production incidents in the first month."


def test_thin_model_plan_is_asked_for_again(northwind):
    calls = []

    def respond(system, prompt, schema):
        if schema is report.PlanOut:
            calls.append(prompt)
            if len(calls) == 1:
                return report.PlanOut(title="Dispatch Optimizer", subtitle="A routing engine and driver app")
            return report.PlanOut(title="Dispatch Optimizer", subtitle="A routing engine and driver app",
                                  tech=["Python", "PostgreSQL"],
                                  metrics=[{"value": "11.8", "unit": "%", "label": "shorter routes in the pilot"}])
        return _all_supported(prompt)

    d = report.build_report(northwind, load("northwind"), FakeLLM(respond))
    assert len(calls) == 2 and "left most of the plan empty" in calls[1]
    assert d.plan.metrics[0].value == "11.8"


def test_redesign_drops_the_old_art_reason(northwind):
    report.build_report(northwind, load("northwind"), None)
    northwind.report.prefs.reason = "Dark technical layout"
    d = report.redesign(northwind)
    assert d.prefs.reason == ""


def test_a_date_is_never_flagged_as_an_estimate_and_milestones_do_not_repeat_results():
    """Second live run: "3 March 2025: A follow-up contract … was signed" was failed because the notes'
    sentence also says "an estimated value"; a milestone repeated the 9.4 % fuel result."""
    assert not estimate_flags("3 March 2025: A follow-up contract for phase 2 was signed.", NOTES)
    plan = ReportPlan(title="x", metrics=[{"value": "9.4", "unit": "%", "label": "less fuel"}],
                      timeline=[{"when": "February 2025", "text": "The client reported fuel consumption down 9.4 percent."},
                                {"when": "4 March 2024", "text": "Kickoff."}])
    assert [e.when for e in report.polish(plan, NOTES).timeline] == ["4 March 2024"]


def test_delivery_judgements_need_the_notes_and_misfiled_sentences_move():
    """Live 19 Nov: "delivered within an agreed timeframe and budget" passed although the project went live
    late and was invoiced above the contract; team size and testing were filed under The Solution."""
    from caseforge.checker import rule_flags
    from caseforge.generate import tidy_section
    from caseforge.models import Claim
    c = Claim(id="x", section="summary", text="The project was delivered within an agreed timeframe and budget.", manual=True)
    assert any("judgement" in f for f in rule_flags(c, NOTES, set()))
    assert tidy_section("work_done", "Team headcount began at 6 people and reached 11 in August 2024.") == "implementation"
    assert tidy_section("results", "The project received an internal Northwind Excellence Award in April 2025.") == "lessons"
    assert tidy_section("results", "Late deliveries fell from 14 percent to 6.1 percent.") == "results"
    assert tidy_section("work_done", "The dispatcher dashboard uses a map-first layout.") == "work_done"
