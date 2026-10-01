"""Every number a farmer sees comes from the sources or from code: an LLM answer that states any other
number is replaced by the checked text."""

import pytest

from app.agent.guardrails import numbers_in, unbacked_numbers
from app.agent.pipeline import KisanPipeline
from app.agent.synthesizer import DeterministicGroundedSynthesizer

SOURCE = ["Spray 20 g Actara in 80-100 litres of water per acre from the second week of December. "
          "Give two sprays of 2 litres neem extract. Rs 2,000 per instalment."]


def test_rewording_is_not_a_new_number():
    answer = ("1. Spray 20 g Actara in 80-100 liters per acre.\n2. Start in the 2nd week of December.\n"
              "Use any one of these. 2 sprays of 2 litres. Rs 2000.")
    assert unbacked_numbers(answer, SOURCE) == []
    assert unbacked_numbers("२० ग्राम Actara, 1.0 litre", ["20 g Actara, 1 litre"]) == []
    # Found by real Gemini: the source says "at 30-day intervals", Gemini wrote "every 30 days"
    assert unbacked_numbers("repeat every 30 days", ["two more applications at 30-day intervals"]) == []
    # Also found by real Gemini: the source says "six weeks", Gemini wrote "6 weeks"
    assert unbacked_numbers("no nitrogen after 6 weeks", ["no nitrogen later than six weeks after transplanting"]) == []


def test_a_changed_or_added_number_is_caught():
    assert unbacked_numbers("Spray 200 g Actara in 80 litres.", SOURCE) == ["200 g"]
    assert unbacked_numbers("Spray 20 g Actara, repeat after 15 days.", SOURCE) == ["15 day"]
    # The number exists in the source, but with another unit: still not backed
    assert unbacked_numbers("Use 2 g neem extract.", SOURCE) == ["2 g"]


def test_number_words_count_in_the_source_only():
    assert numbers_in("the second week") == {"2"} and numbers_in("the second week", words=False) == set()


class FakeLLM:
    """Answers like Gemini would, with whatever text the test gives it."""

    def __init__(self, text):
        self.text = text
        self.fallback = DeterministicGroundedSynthesizer()

    def generate(self, query, chunks, language=None, history=None, context_note=""):
        return self.text, "llm"


@pytest.fixture(scope="module")
def pipeline():
    return KisanPipeline(synthesizer=DeterministicGroundedSynthesizer())


def ask(pipeline, monkeypatch, llm_text, query="How do I control aphids in mustard?"):
    monkeypatch.setattr(pipeline, "synthesizer", FakeLLM(llm_text))
    return pipeline.process_query(query, language="en", generate_audio=False)


def test_faithful_llm_answer_is_kept(pipeline, monkeypatch):
    res = ask(pipeline, monkeypatch, "Spray 40 g Actara 25 WG in 80-125 litres of water per acre.")
    assert res.processing_metadata["answer_source"] == "llm" and res.processing_metadata["unbacked_numbers"] == []
    assert res.answer.startswith("Spray 40 g Actara")


def test_llm_answer_with_a_wrong_dose_is_replaced(pipeline, monkeypatch):
    res = ask(pipeline, monkeypatch, "Spray 400 g Actara 25 WG per acre.")  # the advisory says 40 g
    assert res.processing_metadata["answer_source"] == "template_numbers_replaced"
    assert res.processing_metadata["unbacked_numbers"] == ["400 g"]  # the source has 400 ml Rogor, not 400 g
    assert "40 g Actara" in res.answer and "400 g Actara" not in res.answer


def test_scheme_answer_with_a_wrong_amount_is_replaced(pipeline, monkeypatch):
    res = ask(pipeline, monkeypatch, "PM-KISAN gives Rs 8,000 a year.", query="PM Kisan mein kitna paisa milta hai?")
    assert res.processing_metadata["answer_source"] == "template_numbers_replaced"
    assert "6,000" in res.answer and "8,000" not in res.answer
