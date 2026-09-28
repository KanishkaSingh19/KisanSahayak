"""API tests with a fake pipeline: fast, offline, and no API quota used."""

import json

import pytest
from fastapi.testclient import TestClient

from app.agent.state import GroundedAnswer
from app.api import app, get_pipeline
from app.tools.location import Place
from app.tools.weather_tool import AgWeatherReport


class FakePipeline:
    def __init__(self, tmp_path):
        self.calls = []
        self.tmp_path = tmp_path
        self.retriever = type("R", (), {"is_ready": True})()
        self.synthesizer = object()
        self.stt_adapter = type("S", (), {"is_available": lambda self: True})()
        self.tts_adapter = FakeTTS(tmp_path)
        self.weather_tool = FakeWeather()

    def _answer(self, query, language, history, transcript=None):
        self.calls.append({"query": query, "language": language, "history": history})
        meta = {"answer_source": "llm", "detected_crop": "Mustard", "detected_topic": "Aphid", "latency_ms": 12}
        if transcript:
            meta["stt_transcript"] = transcript
        return GroundedAnswer(
            query=query, intent="crop_question", answer=f"Answer to: {query}", citations=["ICAR-DRMR"],
            retrieved_chunks=[], is_grounded=True, detected_language=language or "en", processing_metadata=meta,
        )

    def process_query(self, query, language=None, generate_audio=True, history=None):
        return self._answer(query, language, history)

    def process_audio_query(self, audio_bytes, filename="x.wav", language=None, generate_audio=True, history=None):
        return self._answer("sarson mein chepa", language, history, transcript="sarson mein chepa")


class FakeTTS:
    def __init__(self, tmp_path):
        self.tmp_path = tmp_path

    def engine_for(self, lang):
        return None if lang == "hinglish" else "edge"

    def supports(self, lang):
        return self.engine_for(lang) is not None

    def synthesize_speech(self, text, language="en"):
        path = self.tmp_path / "answer.mp3"
        path.write_bytes(b"ID3fake")
        return path


class FakeWeather:
    def resolve_place(self, name):
        return Place(name="Delhi", latitude=28.65, longitude=77.23) if name.lower() == "delhi" else None

    def get_weather_for_district(self, name, language="en", place=None):
        return AgWeatherReport(
            district=place.name, temperature_c=24.0, relative_humidity=80.0, wind_speed_kmh=5.0,
            rain_probability_pct=20.0, spray_recommendation="ok", irrigation_advisory="ok",
            is_live=True, source_notice="test",
        )


@pytest.fixture
def fake(tmp_path):
    pipeline = FakePipeline(tmp_path)
    app.dependency_overrides[get_pipeline] = lambda: pipeline
    yield pipeline
    app.dependency_overrides.clear()


@pytest.fixture
def client(fake):
    return TestClient(app)  # not used as a context manager, so the real models are never loaded


def test_health(client):
    body = client.get("/health").json()
    assert body["status"] == "ok" and body["knowledge_index_ready"] is True
    assert body["text_to_speech"]["hinglish"] is None


def test_ask_returns_answer_and_turn(client):
    res = client.post("/ask", json={"query": "How to control aphids in mustard?", "language": "pa"})
    assert res.status_code == 200
    body = res.json()
    assert body["answer"] == "Answer to: How to control aphids in mustard?"
    assert body["language"] == "pa" and body["detected_crop"] == "Mustard"
    assert body["turn"]["crop"] == "Mustard" and body["turn"]["intent"] == "crop_question"


def test_ask_passes_history_for_follow_ups(client, fake):
    first = client.post("/ask", json={"query": "Aphids in mustard?"}).json()
    client.post("/ask", json={"query": "What is the dose?", "history": [first["turn"]]})
    assert fake.calls[-1]["history"][0].crop == "Mustard"


@pytest.mark.parametrize(
    "payload", [{"query": ""}, {"query": "hi", "language": "fr"}, {"language": "en"}, {"query": "x" * 1001}]
)
def test_ask_rejects_bad_input(client, payload):
    assert client.post("/ask", json=payload).status_code == 422


def test_ask_voice(client, fake):
    turn = {"query": "q", "answer": "a", "intent": "crop_question", "crop": "Mustard"}
    res = client.post(
        "/ask/voice",
        files={"audio": ("note.wav", b"RIFF....WAVE", "audio/wav")},
        data={"language": "hi", "history": json.dumps([turn])},
    )
    assert res.status_code == 200
    assert res.json()["transcript"] == "sarson mein chepa"
    assert fake.calls[-1]["history"][0].crop == "Mustard"


def test_ask_voice_rejects_empty_audio_and_bad_history(client):
    empty = client.post("/ask/voice", files={"audio": ("note.wav", b"", "audio/wav")})
    assert empty.status_code == 422
    bad = client.post("/ask/voice", files={"audio": ("n.wav", b"RIFF", "audio/wav")}, data={"history": "not json"})
    assert bad.status_code == 422


def test_weather(client):
    body = client.get("/weather", params={"place": "Delhi"}).json()
    assert body["district"] == "Delhi" and body["temperature_c"] == 24.0
    assert client.get("/weather", params={"place": "Atlantis"}).status_code == 404


def test_speak_returns_mp3(client):
    res = client.post("/speak", json={"text": "Spray after 3:30 PM", "language": "en"})
    assert res.status_code == 200 and res.headers["content-type"] == "audio/mpeg"
    assert res.content.startswith(b"ID3")


def test_speak_unsupported_language(client):
    assert client.post("/speak", json={"text": "hello", "language": "hinglish"}).status_code == 422


def test_docs_available(client):
    assert client.get("/openapi.json").json()["info"]["title"] == "KisanSahayak API"
