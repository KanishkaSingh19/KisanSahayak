"""One chat-box message: typed text, a voice note and a photo in any combination, sent together."""

import pytest

from app.agent.pipeline import KisanPipeline
from app.agent.synthesizer import DeterministicGroundedSynthesizer


@pytest.fixture(scope="module")
def pipeline():
    return KisanPipeline(synthesizer=DeterministicGroundedSynthesizer())


@pytest.fixture
def calls(pipeline, monkeypatch):
    """Record what reaches the photo diagnosis and speech-to-text, without calling any API."""
    seen = {}

    def image(image_bytes, question="", **kwargs):
        seen["image"] = (image_bytes, question)
        return pipeline.process_query(question or "photo", language="en", generate_audio=False)

    def stt(audio, filename="", language=None):
        seen["stt"] = audio
        return (audio != b"noise"), ("wheat leaves have yellow stripes" if audio != b"noise" else "could not understand")

    monkeypatch.setattr(pipeline, "process_image_query", image)
    monkeypatch.setattr(pipeline.stt_adapter, "transcribe_audio_bytes", stt)
    return seen


def test_text_and_photo_go_together(pipeline, calls):
    pipeline.process_message("what should I spray?", image_bytes=b"jpg", language="en")
    assert calls["image"] == (b"jpg", "what should I spray?")


def test_voice_and_photo_go_together(pipeline, calls):
    res = pipeline.process_message("", image_bytes=b"jpg", audio=(b"wav", "recording.wav"), language="en")
    assert calls["image"] == (b"jpg", "wheat leaves have yellow stripes")
    assert res.processing_metadata["stt_transcript"] == "wheat leaves have yellow stripes"


def test_text_voice_and_photo_are_one_question(pipeline, calls):
    pipeline.process_message("In Sangrur.", image_bytes=b"jpg", audio=(b"wav", "recording.wav"), language="en")
    assert calls["image"][1] == "In Sangrur. wheat leaves have yellow stripes"


def test_voice_only_is_answered_as_before(pipeline, calls):
    res = pipeline.process_message("", audio=(b"wav", "recording.wav"), language="en")
    assert "image" not in calls and res.processing_metadata["stt_transcript"] == "wheat leaves have yellow stripes"


def test_unclear_voice_with_a_photo_still_sends_the_photo(pipeline, calls):
    pipeline.process_message("", image_bytes=b"jpg", audio=(b"noise", "recording.wav"), language="en")
    assert calls["image"] == (b"jpg", "")
