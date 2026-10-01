"""Photo diagnosis: vision parsing, pipeline decisions and follow-ups, with a fake vision model."""

import io

import pytest

from app.agent.state import ConversationTurn
from app.agent.synthesizer import DeterministicGroundedSynthesizer
from app.tools.vision import Diagnosis, parse_diagnosis, prepare_image


def test_parse_diagnosis_tolerates_fences_and_bad_values():
    d = parse_diagnosis('```json\n{"is_plant": true, "crop": "Wheat", "problem": "yellow rust", "confidence": "HIGH", "other_possibilities": ["a","b","c"]}\n```')
    assert d.crop == "wheat" and d.confidence == "high" and d.identified and d.covered
    assert len(d.other_possibilities) == 2
    assert parse_diagnosis('{"crop": "banana", "confidence": "sure"}').crop == "unknown"


def test_prepare_image_shrinks_and_converts_to_jpeg():
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (3000, 2000), "green").save(buf, format="PNG")
    data, mime = prepare_image(buf.getvalue())
    assert mime == "image/jpeg"
    assert max(Image.open(io.BytesIO(data)).size) == 1024


class FakeVision:
    def __init__(self, diagnosis):
        self.diagnosis = diagnosis
        self.last_error = "timeout" if diagnosis is None else None

    def diagnose(self, image_bytes, question="", language="en"):
        return self.diagnosis


@pytest.fixture(scope="module")
def pipeline():
    from app.agent.pipeline import KisanPipeline

    return KisanPipeline(synthesizer=DeterministicGroundedSynthesizer())


def run(pipeline, monkeypatch, diagnosis, question="", language="en"):
    monkeypatch.setattr(pipeline, "vision", FakeVision(diagnosis))
    return pipeline.process_image_query(b"fake-image", question=question, language=language)


YELLOW_RUST = Diagnosis(
    is_plant=True, crop="wheat", crop_name="wheat", problem="yellow rust", confidence="high",
    visible_symptoms="Yellow powdery stripes along the leaf veins.", summary_local="Yellow powdery stripes on the leaves.",
)


def test_covered_disease_gets_advisory_treatment(pipeline, monkeypatch):
    res = run(pipeline, monkeypatch, YELLOW_RUST)
    assert res.intent == "image_diagnosis"
    assert "Yellow Rust" in res.retrieved_chunks[0].section
    assert "most likely **yellow rust**" in res.answer
    assert "200 ml Tilt" in res.answer and "propiconazole" in res.answer  # dose from the advisory
    assert any("AI estimate" in d for d in res.safety_disclaimers)


@pytest.mark.parametrize(
    "diagnosis,expected",
    [
        (Diagnosis(is_plant=False), "doesn't seem to show a crop plant"),
        (YELLOW_RUST.model_copy(update={"confidence": "low"}), "couldn't identify the problem"),
        (YELLOW_RUST.model_copy(update={"problem": "unknown"}), "couldn't identify the problem"),
        (YELLOW_RUST.model_copy(update={"problem": "healthy"}), "looks healthy"),
        (YELLOW_RUST.model_copy(update={"crop": "other", "crop_name": "tomato", "problem": "early blight"}), "don't cover this crop"),
    ],
)
def test_unsure_or_uncovered_photos_give_no_treatment(pipeline, monkeypatch, diagnosis, expected):
    res = run(pipeline, monkeypatch, diagnosis)
    assert expected in res.answer
    assert not res.retrieved_chunks and "Propiconazole" not in res.answer


def test_vision_failure_is_reported(pipeline, monkeypatch):
    res = run(pipeline, monkeypatch, None)
    assert res.intent == "image_unavailable" and res.processing_metadata["error"] == "timeout"


def test_answer_in_farmer_language(pipeline, monkeypatch):
    res = run(pipeline, monkeypatch, YELLOW_RUST, language="pa")
    assert "ਫ਼ੋਟੋ ਜਾਂਚ" in res.answer and res.detected_language == "pa"


def test_follow_up_after_photo_keeps_the_disease(pipeline, monkeypatch):
    first = run(pipeline, monkeypatch, YELLOW_RUST)
    second = pipeline.process_query(
        "What is the dose?", language="en", generate_audio=False, history=[ConversationTurn.from_answer(first)]
    )
    assert second.intent == "crop_question"
    assert "Yellow Rust" in second.retrieved_chunks[0].section
