import os
from pathlib import Path
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Base paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    RAW_DATA_DIR: Path = DATA_DIR / "raw"
    INDEX_DIR: Path = DATA_DIR / "indices"

    # App metadata
    APP_NAME: str = "KisanSahayak"
    APP_ENV: str = "development"
    DEBUG: bool = True

    # LLM Provider: "gemini", "openai", or "mock"
    LLM_PROVIDER: Literal["gemini", "openai", "mock"] = "mock"
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.7-flash"
    # Tried when the main model is busy, before falling back to the offline template ("" = none)
    GEMINI_FALLBACK_MODEL: str = "gemini-flash-lite-latest"
    OPENAI_MODEL: str = "gpt-4o-mini"

    # Speech Configuration (Phase 2)
    GROQ_API_KEY: str = ""
    GROQ_WHISPER_MODEL: str = "whisper-large-v3"
    ENABLE_TTS: bool = True
    DEFAULT_HINDI_VOICE: str = "hi-IN-MadhurNeural"
    DEFAULT_PUNJABI_VOICE: str = ""  # Edge-TTS has no Punjabi (pa-IN) voice; empty = text-only
    DEFAULT_ENGLISH_VOICE: str = "en-IN-NeerjaNeural"
    AUDIO_OUTPUT_DIR: Path = BASE_DIR / "data" / "audio"

    # Embedding Provider: "local", "minilm", "gemini", "openai"
    EMBEDDING_PROVIDER: Literal["local", "minilm", "gemini", "openai"] = "local"
    EMBEDDING_DIM: int = 256  # For lightweight local deterministic dense projection
    MINILM_MODEL: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    HF_CACHE_DIR: str = ""  # Where Hugging Face models are downloaded; empty = default cache

    # RAG parameters
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 150
    RAG_TOP_K_DENSE: int = 5
    RAG_TOP_K_SPARSE: int = 5
    RAG_FINAL_TOP_K: int = 3
    RRF_K: int = 60

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parent.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

# Ensure directories exist
os.makedirs(settings.DATA_DIR, exist_ok=True)
os.makedirs(settings.RAW_DATA_DIR, exist_ok=True)
os.makedirs(settings.INDEX_DIR, exist_ok=True)
os.makedirs(settings.AUDIO_OUTPUT_DIR, exist_ok=True)
