"""Claims inside a question are checked against the evidence: corrected when contradicted, flagged when
they cannot be verified, left alone when correct. Statuses never contradict each other.

The mechanism is generic (app/agent/claims.py): nothing here is special-cased for PM-KISAN.
"""

import pytest

from app.agent.state import ConversationTurn
from app.agent.synthesizer import DeterministicGroundedSynthesizer
from app.tools.market import MandiLookup


@pytest.fixture(scope="module")
def pipeline():
    from app.agent.pipeline import KisanPipeline

    class NoMandi:  # market tests must not call the live API
        def latest(self, commodity, state=None, district=None):
            return MandiLookup(prices=[], error="offline test")

    return KisanPipeline(synthesizer=DeterministicGroundedSynthesizer(), mandi=NoMandi())


def ask(pipeline, query, language="en", history=None):
    return pipeline.process_query(query, language=language, generate_audio=False, history=history or [])


def statuses(res):
    return [c["status"] for c in res.processing_metadata.get("claim_checks", [])]


# 1. PM-KISAN false amount: corrected, then the registration question is still answered
def test_false_scheme_amount_is_corrected_and_question_answered(pipeline):
    res = ask(pipeline, "Since PM-KISAN gives ₹12,000 per month to every farmer, how do I register?")
    assert statuses(res) == ["contradicted"]
    assert res.answer.startswith("**Small correction:**")
    assert "₹12,000 per month" in res.answer and "Rs 6,000 per year" in res.answer
    assert "New Farmer Registration" in res.answer  # the underlying question is still answered
    assert res.evidence_status == "verified" and res.source_type == "scheme"


# 2. PM-KISAN correct amount: no correction
def test_correct_scheme_amount_is_not_corrected(pipeline):
    res = ask(pipeline, "PM-KISAN gives Rs 6,000 a year, how do I register?")
    assert statuses(res) == ["supported"] and "correction" not in res.answer.lower()


# 3. A disease the evidence does not mention: no treatment is invented
def test_unknown_disease_gets_no_treatment(pipeline):
    res = ask(pipeline, "How do I control golden blight in mustard?")
    assert "golden blight" in res.answer and "could not find" in res.answer
    assert not res.retrieved_chunks and " ml " not in res.answer and " g " not in res.answer
    assert res.evidence_status == "not_verified"


# 4. A pesticide the evidence does not recommend for this problem: no dose for it
def test_unrecommended_pesticide_gets_no_dose(pipeline):
    res = ask(pipeline, "What is the dose of imidacloprid for mustard aphid?")
    assert "unknown_product" in statuses(res)
    assert "“imidacloprid” is not among the products" in res.answer
    assert res.evidence_status == "partially_verified"


# 5. A false agricultural premise (a dose) is corrected from the advisory
def test_false_dose_premise_is_corrected(pipeline):
    res = ask(pipeline, "Since 100 g Actara is recommended for mustard aphid, when should I spray?")
    assert statuses(res) == ["contradicted"]
    assert "“100 g Actara”" in res.answer and "40 g Actara" in res.answer


# 6. Insufficient evidence: not called false, said to be unverified
def test_claim_without_evidence_is_unverified_not_false(pipeline):
    res = ask(pipeline, "Since PM-KISAN pays Rs 500 per acre, how do I apply?")
    assert statuses(res) == ["unverified"]
    assert "Could not verify" in res.answer and "correction" not in res.answer.lower()
    assert res.evidence_status == "partially_verified"


# 7. A normal question with no premise: nothing added
def test_normal_question_has_no_claim_notes(pipeline):
    res = ask(pipeline, "How do I control aphids in mustard?")
    assert statuses(res) == [] and "correction" not in res.answer.lower()
    assert res.evidence_status == "verified" and res.source_type == "advisory"


# 8. Multilingual: the correction and the quoted fact are in the farmer's language
def test_false_premise_in_hindi(pipeline):
    res = ask(pipeline, "पीएम किसान में हर महीने 12000 रुपये मिलते हैं, आवेदन कैसे करें?", language="hi")
    assert statuses(res) == ["contradicted"]
    assert res.answer.startswith("**छोटा सुधार:**") and "Rs 6,000" in res.answer and "हर साल" in res.answer


# 9. A follow-up carrying a false premise is checked too
def test_false_premise_in_a_follow_up(pipeline):
    first = ask(pipeline, "How do I register for PM-KISAN?")
    res = ask(pipeline, "But I heard it gives ₹12,000 a month, is that right?",
              history=[ConversationTurn.from_answer(first)])
    assert res.intent == "scheme_query" and statuses(res) == ["contradicted"]
    assert "Rs 6,000 per year" in res.answer


def test_false_msp_premise_is_corrected_from_the_msp_table(pipeline):
    res = ask(pipeline, "Since the MSP of wheat is Rs 3,000 per quintal, should I sell to the government?")
    assert res.intent == "market_price" and statuses(res) == ["contradicted"]
    assert "Rs 3,000 per quintal" in res.answer and "Minimum Support Price" in res.answer


def test_false_weather_premise_uses_live_data(pipeline, monkeypatch):
    from app.tools.location import Place
    from app.tools.weather_tool import AgWeatherReport

    report = AgWeatherReport(district="Ludhiana", temperature_c=24.0, relative_humidity=50.0, wind_speed_kmh=6.0,
                             rain_probability_pct=5.0, spray_recommendation="Good time to spray.",
                             irrigation_advisory="Normal irrigation.", source_notice="Open-Meteo", is_live=True)
    monkeypatch.setattr(pipeline.weather_tool, "resolve_place", lambda name: Place(name=name, latitude=30.9, longitude=75.8))
    monkeypatch.setattr(pipeline.weather_tool, "get_weather_for_district", lambda *a, **k: report)
    res = ask(pipeline, "Since it will rain today in Ludhiana, should I skip irrigation?")
    assert res.intent == "weather" and statuses(res) == ["contradicted"]
    assert "5.0%" in res.answer and res.answer.startswith("**Small correction:**")
    assert res.evidence_status == "verified" and res.source_type == "live_weather"


def test_statuses_do_not_contradict_each_other(pipeline):
    """Not covered -> "not verified", never "verified" next to "not found"; greetings have no status."""
    referral = ask(pipeline, "How do I control red rot in sugarcane?")
    assert referral.evidence_status == "not_verified" and referral.source_type is None
    assert referral.review_status == "recommended"
    assert ask(pipeline, "Namaste").evidence_status == "not_applicable"


def test_llm_not_found_marker_means_not_verified(pipeline, monkeypatch):
    class NotFoundLLM:
        fallback = DeterministicGroundedSynthesizer()

        def generate(self, query, chunks, language=None, history=None, context_note=""):
            return "[NOT_FOUND] Verified information on this was not found. Please contact your KVK.", "llm"

    monkeypatch.setattr(pipeline, "synthesizer", NotFoundLLM())
    res = ask(pipeline, "How do I control aphids in mustard?")
    assert "[NOT_FOUND]" not in res.answer and res.evidence_status == "not_verified"


def test_llm_repeating_the_false_amount_is_replaced(pipeline, monkeypatch):
    """The farmer's own number is not evidence: an LLM answer accepting "₹12,000 per month" is replaced."""
    class AgreeingLLM:
        fallback = DeterministicGroundedSynthesizer()

        def generate(self, query, chunks, language=None, history=None, context_note=""):
            return "Yes, you get Rs 12,000 per month. Register on pmkisan.gov.in.", "llm"

    monkeypatch.setattr(pipeline, "synthesizer", AgreeingLLM())
    res = ask(pipeline, "Since PM-KISAN gives ₹12,000 per month to every farmer, how do I register?")
    assert res.processing_metadata["answer_source"] == "template_numbers_replaced"
    assert "Yes, you get Rs 12,000" not in res.answer and "Small correction" in res.answer


def test_scheme_question_is_answered_from_official_text_when_the_llm_declines(pipeline, monkeypatch):
    """The question's own words matched the official application section: a refusal is not accepted."""
    class DecliningLLM:
        fallback = DeterministicGroundedSynthesizer()

        def generate(self, query, chunks, language=None, history=None, context_note=""):
            return "[NOT_FOUND] Verified information was not found. Please contact your KVK.", "llm"

    monkeypatch.setattr(pipeline, "synthesizer", DecliningLLM())
    res = ask(pipeline, "Since PM-KISAN gives ₹12,000 per month to every farmer, how do I register?")
    assert res.processing_metadata["answer_source"] == "template_llm_declined"
    assert "Small correction" in res.answer and "New Farmer Registration" in res.answer
    assert res.evidence_status == "verified"


def test_disease_names_known_to_the_knowledge_base_are_not_refused():
    """Found on real KCC questions: a synonym, another spelling, or one of several names is known."""
    from app.agent.claims import unknown_disease_names

    text = "Yellow or stripe rust. Parawilt: sudden drooping. Foot rot of paddy."
    assert unknown_disease_names("Control of yellow or stripe rust of wheat?", text) == []
    assert unknown_disease_names("kapas mein para wilt ka ilaj", text) == []
    assert unknown_disease_names("bakanae/foot rot/fusarium blight disease in paddy?", text) == []
    assert unknown_disease_names("how do I treat golden wilt virus?", text) == ["golden wilt virus"]
