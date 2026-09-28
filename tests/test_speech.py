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
    adapter = WhisperSTTAdapter(api_key="")
    success, msg = adapter.transcribe_audio_bytes(b"dummy_wav_bytes")
    assert success is False
    assert "GROQ_API_KEY" in msg


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
