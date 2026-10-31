"""B3: nothing exports without approval. B2: documents open and match the approved text."""

import pytest
from pypdf import PdfReader

from caseforge import review
from caseforge.models import Label, ProjectInput
from caseforge.pipeline import generate
from caseforge.render import ExportBlocked
from caseforge.render.html import render_portfolio_page
from caseforge.render.pdf import render_case_study, render_one_pager

from .conftest import SAMPLE_FILES


@pytest.fixture
def drafted(make_record):
    return generate(make_record(SAMPLE_FILES[0]), None)


def test_export_blocked_before_approval(drafted, store, tmp_path):
    with pytest.raises(ExportBlocked):
        render_case_study(drafted, store.image_dir(drafted.id), tmp_path / "x.pdf")
    with pytest.raises(ExportBlocked):
        render_portfolio_page(drafted, store.image_dir(drafted.id), tmp_path / "x.html")


def test_draft_preview_is_watermarked(drafted, store, tmp_path):
    out = render_case_study(drafted, store.image_dir(drafted.id), tmp_path / "d.pdf", draft=True)
    text = "".join(p.extract_text() for p in PdfReader(out).pages)
    assert "NOT APPROVED" in text


def test_planted_claim_blocks_approval_until_fixed(drafted):
    c = review.add_claim(drafted, "results", "Revenue grew by 25% in the first quarter.", None, "tester")
    assert c.label == Label.unsupported
    with pytest.raises(review.ReviewError):
        review.approve(drafted, "tester")
    review.edit_claim(drafted, c.id, "Weekly no-shows fell from about 18 to 11.", None, "tester")
    assert drafted.claim(c.id).label in (Label.supported, Label.reworded)
    review.approve(drafted, "tester")
    assert review.can_export(drafted)


def test_delete_also_unblocks(drafted):
    c = review.add_claim(drafted, "tools", "We deployed it on Kubernetes.", None)
    review.delete_claim(drafted, c.id)
    review.approve(drafted, "tester")
    assert drafted.status == "approved"


def test_add_to_source_makes_claim_supported_and_is_logged(drafted):
    c = review.add_claim(drafted, "results", "The clinic plans to roll it out to 2 more branches.", None)
    assert c.label == Label.unsupported
    review.add_to_source(drafted, "The clinic plans to roll it out to 2 more branches.", None, "results", "Odina")
    assert drafted.claim(c.id).label == Label.supported
    assert any(e.action == "added to source" and e.by == "Odina" for e in drafted.history)


def test_edit_after_approval_withdraws_it(drafted):
    review.approve(drafted, "tester")
    review.edit_claim(drafted, "C2", drafted.claim("C2").text + " ", None)  # whitespace-only change
    assert review.can_export(drafted)  # no real change -> approval stands
    first = drafted.claim("C3")
    review.edit_claim(drafted, first.id, "Reception staff phoned every patient the day before.", None)
    assert drafted.status == "drafted" and not review.can_export(drafted)


def test_blocking_gap_needs_acknowledgement(store):
    inp = ProjectInput(title="No results", client_problem="Students asked the same visa questions by email.",
                       work_done="We made a chatbot on top of the FAQ pages.")
    rec = generate(store.create(inp), None)
    assert any(g.blocking and g.field == "results" for g in rec.gaps)
    with pytest.raises(review.ReviewError):
        review.approve(rec, "tester")
    for g in rec.gaps:
        if g.blocking:
            review.resolve_gap(rec, g.id, "No measured result exists; leave it out.", "tester")
    review.approve(rec, "tester")
    assert review.can_export(rec)


def test_approved_documents_match_approved_text(drafted, store, tmp_path):
    review.approve(drafted, "tester")
    img = store.image_dir(drafted.id)
    pdf = render_case_study(drafted, img, tmp_path / "cs.pdf")
    one = render_one_pager(drafted, img, tmp_path / "op.pdf")
    html = render_portfolio_page(drafted, img, tmp_path / "p.html")
    text = " ".join(" ".join(p.extract_text().split()) for p in PdfReader(pdf).pages)
    for c in drafted.active_claims():
        assert " ".join(c.text.split())[:40] in text, c.text
    assert len(PdfReader(one).pages) == 1
    assert "weekly no-shows fell" in html.read_text()
    assert "<img" in html.read_text()  # the sample image is placed in Results


@pytest.mark.parametrize("n", [1, 400])
def test_layout_survives_tiny_and_huge_input(store, tmp_path, n):
    sentence = "We cleaned the stock data and built a dashboard for the warehouse team."
    inp = ProjectInput(title="Length test", client_problem="Stock counts were done by hand.",
                       work_done=" ".join([sentence] * n), results="The manager said counting is faster.")
    rec = generate(store.create(inp), None)
    for g in rec.gaps:
        if g.blocking:
            review.resolve_gap(rec, g.id, "ok", "t")
    review.approve(rec, "t")
    one = render_one_pager(rec, store.image_dir(rec.id), tmp_path / f"one{n}.pdf")
    full = render_case_study(rec, store.image_dir(rec.id), tmp_path / f"full{n}.pdf")
    assert len(PdfReader(one).pages) == 1
    assert len(PdfReader(full).pages) >= 1
