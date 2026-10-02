import asyncio
import os
import re
import uuid
from pathlib import Path
from typing import Optional

from app.config import settings
from app.i18n import t

try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
except ImportError:
    EDGE_TTS_AVAILABLE = False

try:
    from gtts import gTTS
    GTTS_AVAILABLE = True
except ImportError:
    GTTS_AVAILABLE = False

# Languages Edge-TTS has no voice for, spoken with gTTS instead (our code -> gTTS code)
GTTS_LANGUAGES = {"pa": "pa"}


def _gtts_code(language: str) -> Optional[str]:
    lang = language.lower().strip()
    lang = {"punjabi": "pa", "panjabi": "pa"}.get(lang, lang)
    return GTTS_LANGUAGES.get(lang)


def sanitize_text_for_speech(text: str) -> str:
    """Strip markdown headers, asterisks, brackets, and URLs to ensure natural vocalization."""
    clean = re.sub(r"###\s*", "", text)
    clean = re.sub(r"\*\*([^*]+)\*\*", r"\1", clean)
    clean = re.sub(r"\*([^*]+)\*", r"\1", clean)
    clean = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", clean)
    clean = re.sub(r"https?://\S+", "", clean)
    clean = re.sub(r"[⚠️🚨🔍💊🛡️🌾📌•]", "", clean)
    # Condense consecutive whitespaces
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


class EdgeTTSAdapter:
    """Text-to-speech with zero external subscription requirement.

    Microsoft Edge-TTS voices for Hindi and Indian English (Hinglish uses the Hindi voice);
    Edge-TTS has no Punjabi voice, so Punjabi is spoken with gTTS (Google Translate TTS).
    Isolated so failure never crashes the core conversational response.
    """

    def __init__(
        self,
        output_dir: Path = settings.AUDIO_OUTPUT_DIR,
        hindi_voice: str = settings.DEFAULT_HINDI_VOICE,
        punjabi_voice: str = settings.DEFAULT_PUNJABI_VOICE,
        english_voice: str = settings.DEFAULT_ENGLISH_VOICE,
    ):
        self.output_dir = output_dir
        self.hindi_voice = hindi_voice
        self.punjabi_voice = punjabi_voice
        self.english_voice = english_voice
        os.makedirs(self.output_dir, exist_ok=True)

    def select_voice(self, language: str) -> str:
        lang = language.lower().strip()
        if lang in ["pa", "panjabi", "punjabi"]:
            return self.punjabi_voice
        elif lang in ["en", "english"]:
            return self.english_voice
        elif lang in ["hi", "hindi", "hinglish"]:
            return self.hindi_voice
        return self.hindi_voice

    def is_available(self) -> bool:
        return settings.ENABLE_TTS and (EDGE_TTS_AVAILABLE or GTTS_AVAILABLE)

    def engine_for(self, language: str) -> Optional[str]:
        """Which engine speaks this language: "edge", "gtts", or None if none can."""
        if not settings.ENABLE_TTS:
            return None
        if EDGE_TTS_AVAILABLE and self.select_voice(language):
            return "edge"
        if GTTS_AVAILABLE and _gtts_code(language):
            return "gtts"
        return None

    def supports(self, language: str) -> bool:
        """True if spoken answers can be generated in this language."""
        return self.engine_for(language) is not None

    def synthesize_speech(
        self,
        text: str,
        language: str = "hi",
        filename_prefix: str = "advisory",
    ) -> Optional[Path]:
        """Synthesize text into MP3 audio file. Returns path on success, or None on failure."""
        engine = self.engine_for(language)
        if engine is None:
            return None

        clean_text = sanitize_text_for_speech(text)
        if not clean_text:
            return None

        # Long answers are cut to their first 600 characters, with a note to read the rest on screen
        if len(clean_text) > 600:
            clean_text = clean_text[:600] + t("tts_see_screen", language)

        out_filename = f"{filename_prefix}_{uuid.uuid4().hex[:8]}.mp3"
        out_path = self.output_dir / out_filename

        if engine == "gtts":
            return self._synthesize_gtts(clean_text, language, out_path)

        voice = self.select_voice(language)
        try:
            # Run async edge_tts in event loop safely
            async def _run_tts():
                communicate = edge_tts.Communicate(clean_text, voice)
                await communicate.save(str(out_path))

            # Handle existing running loop or new loop
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Running in Streamlit/async environment: create background task
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        pool.submit(asyncio.run, _run_tts()).result(timeout=6.0)
                else:
                    loop.run_until_complete(_run_tts())
            except RuntimeError:
                asyncio.run(_run_tts())

            if out_path.exists() and out_path.stat().st_size > 0:
                return out_path
            return None

        except Exception as e:
            # Non-blocking graceful failure: log warning and continue without audio
            print(f"[Warning] Edge-TTS synthesis failed: {str(e)}. Proceeding with text-only.")
            return None

    def _synthesize_gtts(self, clean_text: str, language: str, out_path: Path) -> Optional[Path]:
        try:
            gTTS(clean_text, lang=_gtts_code(language)).save(str(out_path))
            if out_path.exists() and out_path.stat().st_size > 0:
                return out_path
            return None
        except Exception as e:
            print(f"[Warning] gTTS synthesis failed: {str(e)}. Proceeding with text-only.")
            return None
