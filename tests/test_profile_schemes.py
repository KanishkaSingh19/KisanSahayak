"""Farmer profile personalisation and PM-KISAN scheme guidance."""

import pytest

from app.agent.router import IntentRouter
from app.agent.state import ConversationTurn, FarmerProfile
from app.agent.synthesizer import DeterministicGroundedSynthesizer
from app.tools.location import Place
from app.tools.schemes import SchemeGuide, check_eligibility, load_scheme


@pytest.mark.parametrize(
    "query",
    [
        "Am I eligible for PM-KISAN?",
        "PM Kisan yojana mein kitna paisa milta hai?",
        "पीएम किसान योजना के लिए कौन पात्र है?",
        "ਪੀਐਮ ਕਿਸਾਨ ਯੋਜਨਾ ਲਈ ਅਰਜ਼ੀ ਕਿਵੇਂ ਦੇਈਏ?",
        "Can a minister's family get PM-KISAN?",  # "minister" must not make it off-topic
    ],
)
def test_scheme_questions_are_recognised(query):
    assert IntentRouter().classify(query).intent == "scheme_query"


def test_scheme_follow_up_stays_on_scheme():
    previous = ConversationTurn(query="PM Kisan mein kitna paisa milta hai?", answer="Rs 6,000...", intent="scheme_query", topic="PM-KISAN")
    res = IntentRouter().classify_with_context("How do I apply?", [previous])
    assert res.intent == "scheme_query"


@pytest.mark.parametrize(
    "profile,status,reasons",
    [
        (None, "needs_info", []),
        (FarmerProfile(), "needs_info", []),
        (FarmerProfile(owns_land=True), "likely_eligible", []),
        (FarmerProfile(owns_land=False), "not_eligible", ["pmk_reason_no_land"]),
        (FarmerProfile(owns_land=True, income_tax_payer=True), "not_eligible", ["pmk_reason_income_tax"]),
        (FarmerProfile(owns_land=True, government_employee=True, pension_10k_or_more=True), "not_eligible",
         ["pmk_reason_government", "pmk_reason_pension"]),
    ],
)
def test_eligibility_rules(profile, status, reasons):
    got_status, got_reasons, _ = check_eligibility(profile)
    assert got_status == status and got_reasons == reasons


def test_land_after_2019_flags_possible_hold():
    assert check_eligibility(FarmerProfile(owns_land=True, land_acquired_after_feb_2019=True))[2] is True


def test_scheme_file_is_complete_and_dated():
    data = load_scheme()
    assert data["source_url"] == "https://pmkisan.gov.in" and data["last_verified"]
    for section in data["sections"]:
        assert set(section["text"]) == {"en", "pa", "hinglish", "hi"}, section["id"]
        # Amounts must match across languages
        for amount in ("6,000", "2,000", "10,000"):
            if amount in section["text"]["en"]:
                assert all(amount in text for text in section["text"].values()), (section["id"], amount)


@pytest.mark.parametrize("query,first", [("How do I apply for PM-KISAN?", "apply"), ("PM kisan mein kitna paisa milta hai", "benefit"), ("PM-KISAN eKYC", "ekyc")])
def test_relevant_scheme_sections(query, first):
    assert SchemeGuide().select_sections(query)[0]["id"] == first


@pytest.fixture(scope="module")
def pipeline():
    from app.agent.pipeline import KisanPipeline

    return KisanPipeline(synthesizer=DeterministicGroundedSynthesizer())


def test_scheme_answer_offline_in_punjabi(pipeline):
    res = pipeline.process_query("PM Kisan mein kitna paisa milta hai?", language="pa", generate_audio=False)
    assert res.intent == "scheme_query"
    assert "Rs 6,000" in res.answer and "ਕਿਸ਼ਤਾਂ" in res.answer
    assert "pmkisan.gov.in" in res.safety_disclaimers[0]


def test_scheme_answer_includes_rule_based_eligibility(pipeline):
    eligible = pipeline.process_query("Am I eligible for PM-KISAN?", language="en", generate_audio=False,
                                      profile=FarmerProfile(owns_land=True))
    assert "likely eligible" in eligible.answer
    excluded = pipeline.process_query("Am I eligible for PM-KISAN?", language="en", generate_audio=False,
                                      profile=FarmerProfile(owns_land=True, income_tax_payer=True))
    assert "likely NOT eligible" in excluded.answer and "income tax" in excluded.answer


def test_profile_district_used_for_weather(pipeline, monkeypatch):
    monkeypatch.setattr(pipeline.weather_tool, "resolve_place", lambda name: Place(name=name, latitude=30.25, longitude=75.84))
    res = pipeline.process_query("Will it rain today?", language="en", generate_audio=False,
                                 profile=FarmerProfile(district="Sangrur"))
    assert res.processing_metadata["district"] == "Sangrur"
    assert "No place was recognised" not in res.answer


def test_profile_crop_used_when_none_named(pipeline):
    res = pipeline.process_query("How do I control aphids?", language="en", generate_audio=False,
                                 profile=FarmerProfile(crops=["mustard"]))
    assert res.retrieved_chunks[0].crop == "Mustard" and "Aphid" in res.retrieved_chunks[0].section


def test_profile_summary_has_no_personal_identifiers():
    summary = FarmerProfile(district="Sangrur", crops=["wheat"], land_acres=5, income_tax_payer=True).summary()
    assert summary == "Farmer profile: district Sangrur; grows wheat; 5 acres."
