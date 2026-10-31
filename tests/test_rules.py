from caseforge.checker import rule_flags
from caseforge.models import Claim
from caseforge.textutil import inflated_words, named_terms, numbers_in, quote_in_source

SOURCE = """[Work done]
We did a dashboard, python + react. Scans go straight into postgres.
[Results]
Manager said friday count is way faster now. Went live in march. 3 excel files were replaced."""


def test_numbers():
    assert numbers_in("reduced time by 40%") == {"40"}
    assert numbers_in("from 1,200 to 900 users, 2.5x faster") == {"1200", "900", "2.5"}
    assert numbers_in("doubled the throughput") == {"2"}
    assert numbers_in("one of the tools") == set()


def test_named_terms():
    assert "Kubernetes" in named_terms("We deployed it on Kubernetes.")
    assert "AWS" in named_terms("It runs on AWS.")
    assert "GPT-4" in named_terms("We used GPT-4 for summaries.")
    assert named_terms("We built a dashboard.") == set()


def test_inflated():
    assert inflated_words("This dramatically improved speed") == {"dramatically"}


def test_quote_grounding():
    assert quote_in_source("python + react", SOURCE)
    assert quote_in_source("Manager said Friday count is way faster", SOURCE)
    assert not quote_in_source("Python backend and React frontend", SOURCE)


def _flags(text):
    return rule_flags(Claim(id="C1", section="results", text=text, fact_ids=["F1"]), SOURCE, {"F1"})


def test_planted_claims_are_flagged():
    assert _flags("Processing time fell by 40%.")
    assert _flags("We deployed the dashboard on Kubernetes.")
    assert _flags("The client, a Fortune 500 manufacturer, adopted it.")
    assert _flags("Friday counts became dramatically faster.")


def test_faithful_claims_pass():
    assert _flags("We built a dashboard with Python and React.") == []
    assert _flags("The manager said the Friday count is way faster now.") == []
    assert _flags("The system replaced 3 Excel files.") == []


def test_generated_claim_must_cite_a_fact():
    c = Claim(id="C1", section="results", text="We built a dashboard.", fact_ids=[])
    assert "cites no source fact" in rule_flags(c, SOURCE, {"F1"})
    c = Claim(id="C1", section="results", text="We built a dashboard.", fact_ids=["F9"])
    assert "cites a fact id that does not exist" in rule_flags(c, SOURCE, {"F1"})
