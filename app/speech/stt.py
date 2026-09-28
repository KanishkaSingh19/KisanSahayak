import io
import os
from pathlib import Path
from typing import Optional, Tuple
import requests

from app.config import settings


class WhisperSTTAdapter:
    """Robust Speech-to-Text adapter utilizing Groq-hosted Whisper Large v3.

    Provides isolated, resilient audio transcription for Hindi, Punjabi, and Hinglish.
    Guaranteed never to crash the application flow on API absence or network outage.
    """

    def __init__(self, api_key: Optional[str] = None, model: str = settings.GROQ_WHISPER_MODEL):
        self.api_key = api_key if api_key is not None else settings.GROQ_API_KEY
        self.model = model
        self.endpoint = "https://api.groq.com/openai/v1/audio/transcriptions"

    def is_available(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

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
        prompt: Optional[str] = "कृषि प्रश्न, गेहूं, सरसों, धान, कीटनाशक, Punjab, Haryana, UP",
    ) -> Tuple[bool, str]:
        """Transcribe audio bytes using Groq Whisper with graceful fallback."""
        if not audio_bytes:
            return False, "Empty audio buffer received."

        if not self.is_available():
            return (
                False,
                "Voice STT requires GROQ_API_KEY. Please provide your query via text input or set GROQ_API_KEY in .env.",
            )

        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
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
            return False, f"Groq Whisper connection timeout/error: {str(e)}. Falling back to text input."
        except Exception as e:
            return False, f"Unexpected audio processing error: {str(e)}"
