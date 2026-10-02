"""Premises stated in words ("Since MSP guarantees that the government will buy all my wheat, ...")
are checked by one layer that runs after any kind of answer (app/agent/premises.py).

The LLM verifier is replaced by a fake that behaves like it: it is given the question and the numbered
evidence sentences, and labels a claim by citing the numbers of the sentences that contain the given
words. What the farmer is shown is built by the pipeline from the cited official sentences, so these
tests check the layer, not the fake. Nothing in the app is special-cased for MSP or PM-KISAN.
"""

import json

import pytest

from app.agent.premises import (asserts_something, evidence_sentences, facts_for, judged_premises,
                                load_facts, premise_clause)
from app.agent.synthesizer import DeterministicGroundedSynthesizer
from app.tools.market import MandiLookup

MSP_QUERY = "Since MSP guarantees that the government will buy all my wheat, where should I sell it?"
MSP_CLAIM = "MSP guarantees that the government will buy all my wheat"


class FakeVerifier:
    """Labels each (claim, verdict, words) rule by citing the evidence sentences containing `words`."""

    def __init__(self, *rules):
        self.rules, self.calls = rules, []

    def verify(self, question, evidence):
        self.calls.append((question, list(evidence)))
        return [{"claim": claim, "verdict": verdict,
                 "evidence": [i for i, s in enumerate(evidence, 1) if any(w in s for w in words)]}
                for claim, verdict, words in self.rules]


@pytest.fixture(scope="module")
def pipeline():
    from app.agent.pipeline import KisanPipeline

    class NoMandi:  # market tests must not call the live API
        def latest(self, commodity, state=None, district=None):
            return MandiLookup(prices=[], error="offline test")

    return KisanPipeline(synthesizer=DeterministicGroundedSynthesizer(), mandi=NoMandi())


def ask(pipeline, monkeypatch, query, verifier, language="en"):
    monkeypatch.setattr(pipeline, "premise_verifier", verifier)
    return pipeline.process_query(query, language=language, generate_audio=False, history=[])


def premise_checks(res):
    return [c for c in res.processing_metadata.get("claim_checks", []) if c["kind"] == "premise"]


def msp_fact(fact_id, lang="en"):
    return next(f["text"][lang] for f in load_facts() if f["id"] == fact_id)


# ---------------------------------------------------------------- the reported case
def test_msp_guarantee_premise_is_corrected_and_the_question_still_answered(pipeline, monkeypatch):
    verifier = FakeVerifier((MSP_CLAIM, "qualified", ["stipulated procurement period", "open market"]))
    res = ask(pipeline, monkeypatch, MSP_QUERY, verifier)

    # the premise is detected, and the official statements were part of the evidence
    assert [(c["claim"], c["status"]) for c in premise_checks(res)] == [(MSP_CLAIM, "qualified")]
    assert msp_fact("msp_conditions") in verifier.calls[0][1]
    # the correction comes first and is made only of the cited official sentences (nothing invented)
    correction, rest = res.answer.split("\n\n", 1)
    assert correction == (f"**Small correction:** your question says “{MSP_CLAIM}”, but the verified source says: "
                          f"{msp_fact('msp_conditions')} {msp_fact('msp_open_market')}")
    # the underlying question is still answered: MSP from the table, and the farmer is asked for the mandi
    assert "Rs 2,585 per quintal" in rest and "tell me your district or mandi" in rest
    assert res.intent == "market_price" and res.source_type == "market_data"
    assert any(c.startswith("PIB: 'Procurement at MSP'") for c in res.citations)
    # the badge says the premise was corrected, never plain "verified"
    assert res.evidence_status == "verified" and res.premise_status == "corrected"


def test_msp_premise_without_a_verifier_is_not_passed_as_verified(pipeline, monkeypatch):
    """Offline or out of quota: the official statements are shown and the premise is flagged."""
    res = ask(pipeline, monkeypatch, MSP_QUERY, None)
    assert res.answer.startswith(f"**Please note:** your question assumes “{MSP_CLAIM}”")
    assert msp_fact("msp_open_market") in res.answer and "Rs 2,585 per quintal" in res.answer
    assert res.premise_status == "unverified" and res.evidence_status == "partially_verified"


def test_msp_procurement_premise_in_hinglish(pipeline, monkeypatch):
    query = "kyunki MSP pe sarkar saara gehun khareedti hai, main kahan bechun?"
    claim = "MSP pe sarkar saara gehun khareedti hai"
    res = ask(pipeline, monkeypatch, query, FakeVerifier((claim, "contradicted", ["open market"])),
              language="hinglish")
    assert res.answer.startswith("**Chhota sudhaar:**")
    assert msp_fact("msp_open_market", "hinglish") in res.answer and res.premise_status == "corrected"


# ---------------------------------------------------------------- other domains, same layer
def test_pm_kisan_false_amount_is_corrected_once(pipeline, monkeypatch):
    """The amount is checked by the form-based checker; the worded layer must not repeat it."""
    claim = "PM-KISAN gives ₹12,000 per month to every farmer"
    res = ask(pipeline, monkeypatch, f"Since {claim}, how do I register?",
              FakeVerifier((claim, "contradicted", ["Rs 6,000 per year"])))
    assert res.answer.count("Small correction") == 1 and "Rs 6,000 per year" in res.answer
    assert "New Farmer Registration" in res.answer and res.premise_status == "corrected"


def test_pesticide_premise_is_corrected_from_the_advisory(pipeline, monkeypatch):
    claim = "a double dose of Actara works faster"
    res = ask(pipeline, monkeypatch, f"Since {claim}, how much should I spray for mustard aphid?",
              FakeVerifier((claim, "contradicted", ["40 g Actara"])))
    assert res.answer.startswith(f"**Small correction:** your question says “{claim}”")
    assert "Spray 40 g Actara 25 WG" in res.answer.split("\n\n")[0]
    assert res.source_type == "advisory" and res.premise_status == "corrected"


def test_rain_premise_is_corrected_from_live_weather(pipeline, monkeypatch):
    from app.tools.location import Place
    from app.tools.weather_tool import AgWeatherReport

    report = AgWeatherReport(district="Ludhiana", temperature_c=24.0, relative_humidity=50.0, wind_speed_kmh=6.0,
                             rain_probability_pct=5.0, spray_recommendation="Good time to spray.",
                             irrigation_advisory="Normal irrigation.", source_notice="Open-Meteo", is_live=True)
    monkeypatch.setattr(pipeline.weather_tool, "resolve_place", lambda name: Place(name=name, latitude=30.9, longitude=75.8))
    monkeypatch.setattr(pipeline.weather_tool, "get_weather_for_district", lambda *a, **k: report)
    res = ask(pipeline, monkeypatch, "I heard it will rain today in Ludhiana, should I skip irrigation?",
              FakeVerifier(("it will rain today in Ludhiana", "contradicted", ["5.0%"])))
    assert res.answer.count("Small correction") == 1 and "5.0%" in res.answer
    assert res.source_type == "live_weather" and res.premise_status == "corrected"


def test_unsupported_disease_premise_gets_no_treatment(pipeline, monkeypatch):
    claim = "golden blight is spreading in mustard"
    res = ask(pipeline, monkeypatch, f"Since {claim}, how do I control it?",
              FakeVerifier((claim, "not_in_evidence", [])))
    assert "could not find" in res.answer and " ml " not in res.answer and " g " not in res.answer
    assert res.evidence_status == "not_verified" and res.premise_status == "unverified"


# ---------------------------------------------------------------- correct premises are left alone
def test_correct_msp_statement_is_not_corrected(pipeline, monkeypatch):
    query = "Since the MSP of wheat is Rs 2,585 per quintal, where should I sell it?"
    res = ask(pipeline, monkeypatch, query,
              FakeVerifier(("the MSP of wheat is Rs 2,585 per quintal", "supported", ["Rs 2,585"])))
    assert "correction" not in res.answer.lower() and "Please note" not in res.answer
    assert res.answer.startswith("**Minimum Support Price (MSP) for Wheat")
    assert res.evidence_status == "verified" and res.premise_status == "none"


def test_correct_pm_kisan_statement_is_not_corrected(pipeline, monkeypatch):
    claim = "PM-KISAN gives Rs 6,000 a year in three instalments"
    res = ask(pipeline, monkeypatch, f"Since {claim}, how do I register?",
              FakeVerifier((claim, "supported", ["Rs 6,000 per year"])))
    assert "correction" not in res.answer.lower() and "Could not verify" not in res.answer
    assert res.evidence_status == "verified" and res.premise_status == "none"


def test_question_without_a_premise_is_not_sent_to_the_verifier(pipeline, monkeypatch):
    verifier = FakeVerifier((MSP_CLAIM, "contradicted", ["open market"]))
    res = ask(pipeline, monkeypatch, "What is the MSP of wheat?", verifier)
    assert not verifier.calls and res.premise_status == "none" and "correction" not in res.answer.lower()


# ---------------------------------------------------------------- the verifier is not trusted blindly
def test_verifier_output_is_validated():
    question = "Since MSP guarantees that the government will buy all my wheat, where should I sell it?"
    evidence = ["Sentence one is here.", "Sentence two is here."]
    raw = [
        {"claim": "the government buys everything at double price", "verdict": "contradicted", "evidence": [1]},
        {"claim": MSP_CLAIM, "verdict": "contradicted", "evidence": [7]},  # no such sentence
        {"claim": MSP_CLAIM, "verdict": "maybe", "evidence": [1]},
        "not a claim",
        {"claim": MSP_CLAIM, "verdict": "qualified", "evidence": [2, "1"]},
    ]
    assert judged_premises(question, raw, evidence, already=[]) == [
        {"claim": MSP_CLAIM, "verdict": "qualified", "cited": [2]}]
    assert judged_premises(question, raw, evidence, already=["government will buy all"]) == []


def test_the_farmers_request_is_not_taken_as_a_claim():
    """Found with real Gemini: "how do I register" was labelled as an unverified claim."""
    question = "Since PM-KISAN gives ₹12,000 per month to every farmer, how do I register?"
    raw = [{"claim": "how do I register", "verdict": "not_in_evidence", "evidence": []},
           {"claim": "कैसे करें", "verdict": "not_in_evidence", "evidence": []}]
    assert judged_premises(question, raw, ["Some evidence sentence here."], already=[]) == []


def test_premise_words_are_not_part_of_a_disease_name():
    """Found with real Gemini: "Since golden blight is spreading" was read as the disease "since golden blight"."""
    from app.agent.claims import unknown_disease_names

    assert unknown_disease_names("Since golden blight is spreading in mustard, how do I control it?",
                                 "White rust. Alternaria blight.") == ["golden blight"]


def test_premise_cues_and_facts_in_every_language():
    assert asserts_something(MSP_QUERY) and not asserts_something("Where should I sell my wheat?")
    assert asserts_something("क्योंकि सरकार सारा गेहूं खरीदती है, कहाँ बेचूँ?")
    assert asserts_something("ਕਿਉਂਕਿ ਸਰਕਾਰ ਸਾਰੀ ਕਣਕ ਖਰੀਦਦੀ ਹੈ, ਕਿੱਥੇ ਵੇਚਾਂ?")
    assert premise_clause(MSP_QUERY) == MSP_CLAIM
    assert facts_for("ਕਿਉਂਕਿ ਸਰਕਾਰੀ ਖਰੀਦ ਪੱਕੀ ਹੈ") and not facts_for("How do I control aphids in mustard?")
    assert evidence_sentences(["## Heading\nOne two three four. One two three four."]) == ["One two three four."]


def test_every_official_fact_has_a_source_and_all_languages():
    from app.config import settings

    for path in (settings.DATA_DIR / "facts").glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["source"] and data["source_url"].startswith("https://") and data["last_verified"]
        for fact in data["facts"]:
            assert set(fact["text"]) == {"en", "hi", "pa", "hinglish"}, fact["id"]
