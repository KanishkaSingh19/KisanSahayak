"""Farmer profile personalisation and PM-KISAN scheme guidance."""

import pytest

from app.agent.router import IntentRouter
from app.agent.state import ConversationTurn, FarmerProfile
from app.agent.synthesizer import DeterministicGroundedSynthesizer
from app.tools.location import Place
from app.tools.schemes import SchemeGuide, check_eligibility, load_scheme, load_schemes


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


@pytest.mark.parametrize("name", ["PM-KISAN", "PMFBY crop insurance", "Kisan Credit Card"])
def test_every_scheme_file_is_complete_and_its_numbers_match_in_every_language(name):
    import re

    data = load_schemes()[name]
    assert data["source_url"].startswith("https://") and data["last_verified"] and data["names"]
    for section in data["sections"]:
        assert set(section["text"]) == {"en", "pa", "hinglish", "hi"}, section["id"]
        numbers = set(re.findall(r"\d+(?:[.,]\d+)?", section["text"]["en"]))
        for lang, text in section["text"].items():
            assert numbers <= set(re.findall(r"\d+(?:[.,]\d+)?", text)), (name, section["id"], lang)
        assert not re.search(r"[ऀ-੿]", section["text"]["hinglish"]), (name, section["id"])  # Latin letters only


@pytest.mark.parametrize("query,topic", [
    ("How do I apply for PM Fasal Bima Yojana?", "PMFBY crop insurance"),
    ("ਕੀ ਪੰਜਾਬ ਵਿੱਚ ਫ਼ਸਲ ਬੀਮਾ ਮਿਲਦਾ ਹੈ?", "PMFBY crop insurance"),
    ("Kisan credit card scheme kaise banwayein", "Kisan Credit Card"),
    ("किसान क्रेडिट कार्ड पर ब्याज कितना है?", "Kisan Credit Card"),
    ("PM Kisan mein kitna paisa milta hai?", "PM-KISAN"),
    ("मृदा स्वास्थ्य कार्ड योजना क्या है?", "other scheme: Soil Health Card"),
    ("PM Kisan Maandhan pension scheme", "other scheme: PM-KISAN Maandhan pension"),
    ("Which government schemes are there for farmers?", None),
])
def test_each_scheme_is_recognised_by_name(query, topic):
    """A question about one scheme must never get another scheme's rules."""
    result = IntentRouter().classify(query)
    assert result.intent == "scheme_query" and result.detected_topic == topic


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


def test_changed_profile_district_wins_over_earlier_profile_place(pipeline, monkeypatch):
    monkeypatch.setattr(pipeline.weather_tool, "resolve_place", lambda name: Place(name=name, latitude=30.0, longitude=76.0))
    first = pipeline.process_query("What's the weather today?", language="en", generate_audio=False,
                                   profile=FarmerProfile(district="Patiala"))
    history = [ConversationTurn.from_answer(first)]
    second = pipeline.process_query("What's the weather today?", language="en", generate_audio=False,
                                    history=history, profile=FarmerProfile(district="Noida"))
    assert second.processing_metadata["district"] == "Noida"


def test_place_named_in_question_is_still_carried_over(pipeline, monkeypatch):
    monkeypatch.setattr(pipeline.weather_tool, "resolve_place", lambda name: Place(name=name, latitude=28.6, longitude=77.2))
    first = pipeline.process_query("Weather in Delhi today?", language="en", generate_audio=False,
                                   profile=FarmerProfile(district="Noida"))
    history = [ConversationTurn.from_answer(first)]
    second = pipeline.process_query("Will it rain tomorrow?", language="en", generate_audio=False,
                                    history=history, profile=FarmerProfile(district="Noida"))
    assert second.processing_metadata["district"] == "Delhi"


def test_crop_insurance_answer_says_punjab_does_not_run_it(pipeline):
    res = pipeline.process_query("How do I apply for PM Fasal Bima Yojana?", language="en", generate_audio=False)
    assert res.processing_metadata["detected_topic"] == "PMFBY crop insurance"
    assert "Punjab has not implemented PMFBY" in res.answer and "pmfby.gov.in" in res.safety_disclaimers[0]


def test_kcc_interest_answer_in_hinglish(pipeline):
    res = pipeline.process_query("Kisan credit card par byaj kitna lagta hai?", language="hinglish", generate_audio=False)
    assert "7%" in res.answer and "4%" in res.answer and "Rs 3 lakh" in res.answer
    assert "bank" in res.safety_disclaimers[0]


def test_other_scheme_is_referred_not_answered_with_pm_kisan(pipeline):
    res = pipeline.process_query("PM Kisan Maandhan pension scheme", language="en", generate_audio=False)
    assert "maandhan.in" in res.answer and "6,000" not in res.answer and not res.retrieved_chunks


def test_claim_follow_up_stays_on_crop_insurance():
    previous = ConversationTurn(query="How do I apply for PM Fasal Bima Yojana?", answer="...", intent="scheme_query",
                                topic="PMFBY crop insurance")
    res = IntentRouter().classify_with_context("How do I claim if hail damages my wheat?", [previous])
    assert res.intent == "scheme_query" and res.detected_topic == "PMFBY crop insurance"
