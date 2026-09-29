import io
import os
from pathlib import Path
from typing import Optional, Tuple
import requests

from app.config import settings

# App language -> Whisper language code (Hinglish is spoken Hindi)
WHISPER_LANGUAGES = {"en": "en", "pa": "pa", "hi": "hi", "hinglish": "hi"}
# A few farming words in the expected script help Whisper spell crop and pest names correctly
FARMING_PROMPTS = {
    "hi": "कृषि प्रश्न, गेहूं, सरसों, धान, कपास, कीटनाशक, Punjab, Haryana, UP",
    "pa": "ਖੇਤੀ ਸਵਾਲ, ਕਣਕ, ਸਰ੍ਹੋਂ, ਝੋਨਾ, ਨਰਮਾ, ਕੀਟਨਾਸ਼ਕ, ਪੰਜਾਬ",
    "en": "Farming question: wheat, mustard, paddy, cotton, aphids, pesticide, Punjab",
}


USER_AGENT = "KisanSahayak/1.0 (+https://github.com/KanishkaSingh19/KisanSahayak)"
# Whisper makes many spelling mistakes in Punjabi; Gemini transcribed our Punjabi test exactly
GEMINI_FIRST_LANGUAGES = {"pa"}
AUDIO_MIME_TYPES = {".wav": "audio/wav", ".mp3": "audio/mp3", ".ogg": "audio/ogg", ".m4a": "audio/aac", ".aac": "audio/aac", ".flac": "audio/flac"}
GEMINI_SCRIPT_HINTS = {
    "pa": "The speaker is probably speaking Punjabi: write it in Gurmukhi script.",
    "hi": "The speaker is probably speaking Hindi or Hinglish: write it in Devanagari script.",
    "en": "The speaker is probably speaking English: write it in English.",
    None: "Write Punjabi in Gurmukhi, Hindi in Devanagari and English in English.",
}


class WhisperSTTAdapter:
    """Robust Speech-to-Text adapter utilizing Groq-hosted Whisper Large v3.

    Provides isolated, resilient audio transcription for Hindi, Punjabi, and Hinglish.
    Guaranteed never to crash the application flow on API absence or network outage.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = settings.GROQ_WHISPER_MODEL,
        gemini_api_key: Optional[str] = None,
    ):
        self.api_key = api_key if api_key is not None else settings.GROQ_API_KEY
        self.gemini_api_key = gemini_api_key if gemini_api_key is not None else settings.GEMINI_API_KEY
        self.model = model
        self.endpoint = "https://api.groq.com/openai/v1/audio/transcriptions"

    def _groq_available(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    def _gemini_available(self) -> bool:
        return bool(self.gemini_api_key and self.gemini_api_key.strip())

    def is_available(self) -> bool:
        """Voice input works if either Groq Whisper or the Gemini backup can be used."""
        return self._groq_available() or self._gemini_available()

    def transcribe_audio_file(
        self,
        audio_file_path: Path,
        prompt: Optional[str] = "कृषि प्रश्न, गेहूं, सरसों, धान, कीटनाशक, Punjab, Haryana, UP",
    ) -> Tuple[bool, str]:
        """Transcribe an audio file from local path."""
        if not audio_file_path.exists():
            return False, f"Audio file not found: {audio_file_path}"

        with open(audio_file_path, "rb") as f:
            audio_bytes = f.read()

        return self.transcribe_audio_bytes(audio_bytes, filename=audio_file_path.name, prompt=prompt)

    def transcribe_audio_bytes(
        self,
        audio_bytes: bytes,
        filename: str = "farmer_audio.wav",
        prompt: Optional[str] = None,
        language: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """Transcribe audio bytes using Groq Whisper with graceful fallback.

        `language` is the farmer's chosen language (en, pa, hinglish, hi). Telling Whisper what to
        expect, plus a few farming words in that script, improves recognition (especially Punjabi).
        """
        if not audio_bytes:
            return False, "Empty audio buffer received."
        if not self.is_available():
            return (
                False,
                "Voice input needs GROQ_API_KEY or GEMINI_API_KEY. Please type your question, or set a key in .env.",
            )

        # Groq Whisper is fastest (~1 s); Gemini (~4-9 s) is much more accurate for Punjabi and also
        # covers networks Groq refuses (e.g. "403 Access denied" from cloud hosts). Each backs up the other.
        groq = (self._groq_available(), lambda: self._transcribe_groq(audio_bytes, filename, prompt, language))
        gemini = (self._gemini_available(), lambda: self._transcribe_gemini(audio_bytes, filename, language))
        order = [gemini, groq] if (language or "").lower() in GEMINI_FIRST_LANGUAGES else [groq, gemini]

        errors = []
        for available, transcribe in order:
            if not available:
                continue
            ok, text = transcribe()
            if ok:
                return True, text
            errors.append(text)
        return False, " | ".join(errors)

    def _transcribe_groq(
        self, audio_bytes: bytes, filename: str, prompt: Optional[str], language: Optional[str]
    ) -> Tuple[bool, str]:
        whisper_lang = WHISPER_LANGUAGES.get((language or "").lower())
        if prompt is None:
            prompt = FARMING_PROMPTS.get(whisper_lang, FARMING_PROMPTS["hi"])
        try:
            headers = {"Authorization": f"Bearer {self.api_key}", "User-Agent": USER_AGENT}
            files = {
                "file": (filename, io.BytesIO(audio_bytes), "audio/wav"),
            }
            data = {
                "model": self.model,
                "temperature": "0.0",
                "response_format": "json",
            }
            if prompt:
                data["prompt"] = prompt
            if whisper_lang:
                data["language"] = whisper_lang

            response = requests.post(
                self.endpoint,
                headers=headers,
                files=files,
                data=data,
                timeout=12,
            )

            if response.status_code == 200:
                result_json = response.json()
                transcript = result_json.get("text", "").strip()
                return True, transcript
            else:
                return False, f"Groq Whisper STT API returned error {response.status_code}: {response.text}"

        except requests.RequestException as e:
            return False, f"Groq Whisper connection timeout/error: {str(e)}"
        except Exception as e:
            return False, f"Unexpected audio processing error: {str(e)}"

    def _transcribe_gemini(self, audio_bytes: bytes, filename: str, language: Optional[str]) -> Tuple[bool, str]:
        """Transcribe with Gemini, which accepts audio directly (backup for when Groq is unreachable)."""
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self.gemini_api_key, http_options=types.HttpOptions(timeout=20_000))
            mime = AUDIO_MIME_TYPES.get(Path(filename).suffix.lower(), "audio/wav")
            hint = GEMINI_SCRIPT_HINTS.get(WHISPER_LANGUAGES.get((language or "").lower()), GEMINI_SCRIPT_HINTS[None])
            instruction = (
                f"Transcribe this voice message from an Indian farmer exactly as spoken. {hint} "
                "Return only the transcript, with no translation, notes or quotation marks."
            )
            last_error = "no model available"
            for model in [m for m in (settings.GEMINI_MODEL, settings.GEMINI_FALLBACK_MODEL) if m]:
                try:
                    response = client.models.generate_content(
                        model=model,
                        contents=[types.Part.from_bytes(data=audio_bytes, mime_type=mime), instruction],
                    )
                    transcript = (response.text or "").strip()
                    if transcript:
                        return True, transcript
                    last_error = "empty transcript"
                except Exception as e:
                    last_error = str(e)[:200]
            return False, f"Gemini transcription failed: {last_error}"
        except Exception as e:
            return False, f"Gemini transcription failed: {str(e)[:200]}"
