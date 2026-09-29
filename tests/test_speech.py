from pathlib import Path
import pytest
from app.speech.stt import WhisperSTTAdapter
from app.speech.tts import EdgeTTSAdapter, sanitize_text_for_speech


def test_sanitize_text_for_speech():
    raw = (
        "### 🌾 फसल परामर्श: Wheat (Yellow Rust)\n"
        "**💊 अनुशंसित उपचार:** Spray Tebuconazole @ 200 ml. [Source](https://icar.gov.in)\n"
        "• Wear PPE gloves."
    )
    cleaned = sanitize_text_for_speech(raw)
    assert "###" not in cleaned
    assert "**" not in cleaned
    assert "https://" not in cleaned
    assert "Tebuconazole" in cleaned
    assert "Wear PPE gloves" in cleaned


def test_stt_adapter_empty_audio():
    adapter = WhisperSTTAdapter(api_key="")
    success, msg = adapter.transcribe_audio_bytes(b"")
    assert success is False
    assert "Empty audio buffer" in msg


def test_stt_adapter_missing_key():
    adapter = WhisperSTTAdapter(api_key="", gemini_api_key="")
    assert adapter.is_available() is False
    success, msg = adapter.transcribe_audio_bytes(b"dummy_wav_bytes")
    assert success is False
    assert "GROQ_API_KEY" in msg


class _GroqResp:
    def __init__(self, status, body):
        self.status_code, self._body = status, body
        self.text = str(body)

    def json(self):
        return self._body


def test_groq_refusal_falls_back_to_gemini(monkeypatch):
    from app.speech import stt

    headers_seen = {}

    def groq_403(url, headers, files, data, timeout):
        headers_seen.update(headers)
        return _GroqResp(403, {"error": {"message": "Access denied. Please check your network settings."}})

    monkeypatch.setattr(stt.requests, "post", groq_403)
    adapter = WhisperSTTAdapter(api_key="groq-key", gemini_api_key="gemini-key")
    monkeypatch.setattr(adapter, "_transcribe_gemini", lambda audio, filename, language: (True, "सरसों में माहू"))
    ok, text = adapter.transcribe_audio_bytes(b"RIFF....", language="hi")
    assert ok and text == "सरसों में माहू"
    assert headers_seen["User-Agent"].startswith("KisanSahayak")  # not python-requests' default


def test_both_speech_services_failing_reports_both(monkeypatch):
    from app.speech import stt

    monkeypatch.setattr(stt.requests, "post", lambda *a, **k: _GroqResp(403, {"error": "denied"}))
    adapter = WhisperSTTAdapter(api_key="groq-key", gemini_api_key="gemini-key")
    monkeypatch.setattr(adapter, "_transcribe_gemini", lambda *a: (False, "Gemini transcription failed: quota"))
    ok, msg = adapter.transcribe_audio_bytes(b"RIFF....")
    assert not ok and "403" in msg and "Gemini transcription failed" in msg


@pytest.mark.parametrize("lang,first", [("pa", "gemini"), ("hi", "groq"), ("en", "groq"), ("hinglish", "groq")])
def test_speech_service_order_by_language(monkeypatch, lang, first):
    calls = []
    adapter = WhisperSTTAdapter(api_key="groq-key", gemini_api_key="gemini-key")
    monkeypatch.setattr(adapter, "_transcribe_groq", lambda *a: calls.append("groq") or (True, "ok"))
    monkeypatch.setattr(adapter, "_transcribe_gemini", lambda *a: calls.append("gemini") or (True, "ok"))
    adapter.transcribe_audio_bytes(b"RIFF....", language=lang)
    assert calls == [first]


def test_gemini_only_is_enough_for_voice():
    assert WhisperSTTAdapter(api_key="", gemini_api_key="gemini-key").is_available() is True


def test_tts_adapter_voice_selection():
    adapter = EdgeTTSAdapter()
    assert adapter.select_voice("pa") == ""  # Edge-TTS has no Punjabi voice
    assert "hi-IN" in adapter.select_voice("hi")
    assert "hi-IN" in adapter.select_voice("hinglish")
    assert "en-IN" in adapter.select_voice("en")


def test_tts_engine_selection():
    from app.speech import tts

    adapter = EdgeTTSAdapter()
    if tts.EDGE_TTS_AVAILABLE:
        assert adapter.engine_for("en") == "edge"
        assert adapter.engine_for("hinglish") == "edge"
    # Edge-TTS has no Punjabi voice, so Punjabi goes to gTTS when it's installed
    assert adapter.engine_for("pa") == ("gtts" if tts.GTTS_AVAILABLE else None)
    assert adapter.engine_for("punjabi") == adapter.engine_for("pa")


def test_tts_punjabi_uses_gtts(monkeypatch, tmp_path):
    from app.speech import tts

    calls = []

    class FakeGTTS:
        def __init__(self, text, lang):
            calls.append((text, lang))

        def save(self, path):
            Path(path).write_bytes(b"ID3fake-mp3")

    monkeypatch.setattr(tts, "GTTS_AVAILABLE", True)
    monkeypatch.setattr(tts, "gTTS", FakeGTTS, raising=False)
    adapter = EdgeTTSAdapter(output_dir=tmp_path)
    path = adapter.synthesize_speech("ਸਤ ਸ੍ਰੀ ਅਕਾਲ", language="pa")
    assert path is not None and path.exists()
    assert calls == [("ਸਤ ਸ੍ਰੀ ਅਕਾਲ", "pa")]


def test_tts_no_engine_returns_none(monkeypatch):
    from app.speech import tts

    monkeypatch.setattr(tts, "GTTS_AVAILABLE", False)
    adapter = EdgeTTSAdapter()
    assert adapter.supports("pa") is False
    assert adapter.synthesize_speech("ਸਤ ਸ੍ਰੀ ਅਕਾਲ", language="pa") is None


def test_tts_adapter_graceful_handling():
    adapter = EdgeTTSAdapter()
    # Should not raise exception even with empty or arbitrary strings
    res = adapter.synthesize_speech("")
    assert res is None


@pytest.mark.parametrize("app_lang,whisper_lang", [("pa", "pa"), ("hi", "hi"), ("hinglish", "hi"), ("en", "en")])
def test_stt_tells_whisper_the_language(monkeypatch, app_lang, whisper_lang):
    from app.speech import stt

    sent = {}

    class Resp:
        status_code = 200

        def json(self):
            return {"text": "sarson mein chepa"}

    def fake_post(url, headers, files, data, timeout):
        sent.update(data)
        return Resp()

    monkeypatch.setattr(stt.requests, "post", fake_post)
    ok, text = WhisperSTTAdapter(api_key="test-key").transcribe_audio_bytes(b"RIFF....", language=app_lang)
    assert ok and text == "sarson mein chepa"
    assert sent["language"] == whisper_lang
    assert sent["prompt"] == stt.FARMING_PROMPTS[whisper_lang]


def test_stt_without_language_lets_whisper_detect(monkeypatch):
    from app.speech import stt

    sent = {}
    monkeypatch.setattr(stt.requests, "post", lambda url, headers, files, data, timeout: sent.update(data) or type("R", (), {"status_code": 200, "json": lambda self: {"text": "x"}})())
    WhisperSTTAdapter(api_key="test-key").transcribe_audio_bytes(b"RIFF....")
    assert "language" not in sent
