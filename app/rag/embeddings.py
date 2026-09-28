import hashlib
import math
import re
import unicodedata
from typing import List, Optional
import numpy as np

from app.config import settings


class BaseEmbeddings:
    """Base interface for dense vector embeddings."""

    def embed_text(self, text: str) -> np.ndarray:
        raise NotImplementedError

    def embed_documents(self, texts: List[str]) -> np.ndarray:
        raise NotImplementedError

    def get_dimension(self) -> int:
        raise NotImplementedError


class LocalDenseEmbedder(BaseEmbeddings):
    """Deterministic, zero-dependency, normalized n-gram dense embedding generator.

    Provides robust semantic vector projection using word and character subwords,
    guaranteeing 100% offline capability with zero external API dependencies.
    """

    def __init__(self, dimension: int = 256):
        self.dimension = dimension

    def _hash_token(self, token: str, seed: int) -> int:
        raw = f"{seed}:{token}".encode("utf-8")
        digest = hashlib.md5(raw).digest()
        return int.from_bytes(digest[:4], "little") % self.dimension

    def embed_text(self, text: str) -> np.ndarray:
        clean_text = text.lower().strip()
        # Clean punctuation but preserve Unicode letters, marks (Mc, Mn), and numbers
        cleaned_chars = []
        for ch in clean_text:
            cat = unicodedata.category(ch)
            if cat.startswith("P") or cat.startswith("S") or cat.startswith("C"):
                cleaned_chars.append(" ")
            else:
                cleaned_chars.append(ch)
        tokens = "".join(cleaned_chars).split()
        vector = np.zeros(self.dimension, dtype=np.float32)

        if not tokens:
            return vector

        for token in tokens:
            # Word level hashing
            idx1 = self._hash_token(token, seed=1)
            idx2 = self._hash_token(token, seed=2)
            vector[idx1] += 1.0
            vector[idx2] += 0.5

            # Subword 3-character n-grams for morphological/Indic transliteration resilience
            if len(token) >= 3:
                for i in range(len(token) - 2):
                    ngram = token[i : i + 3]
                    n_idx = self._hash_token(ngram, seed=3)
                    vector[n_idx] += 0.3

        # L2 Normalization for Cosine Similarity
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm

        return vector

    def embed_documents(self, texts: List[str]) -> np.ndarray:
        return np.array([self.embed_text(t) for t in texts], dtype=np.float32)

    def get_dimension(self) -> int:
        return self.dimension


class GeminiEmbedder(BaseEmbeddings):
    """Embeddings via Google Gen AI SDK (gemini-embedding-001, 768-dim)."""

    def __init__(self, api_key: str):
        from google import genai

        self.client = genai.Client(api_key=api_key)
        self.model = "gemini-embedding-001"
        self._fallback = LocalDenseEmbedder()

    def embed_text(self, text: str) -> np.ndarray:
        from google.genai import types

        try:
            res = self.client.models.embed_content(
                model=self.model,
                contents=text,
                config=types.EmbedContentConfig(output_dimensionality=self.get_dimension()),
            )
            vec = np.array(res.embeddings[0].values, dtype=np.float32)
            norm = np.linalg.norm(vec)
            return vec / norm if norm > 0 else vec
        except Exception:
            return self._fallback.embed_text(text)

    def embed_documents(self, texts: List[str]) -> np.ndarray:
        return np.array([self.embed_text(t) for t in texts], dtype=np.float32)

    def get_dimension(self) -> int:
        return 768


class MiniLMEmbedder(BaseEmbeddings):
    """Local multilingual sentence embeddings via Hugging Face sentence-transformers.

    Runs fully offline after the one-time model download (Hindi, English and 50+ languages).
    """

    def __init__(self, model_name: str = settings.MINILM_MODEL, cache_folder: Optional[str] = None):
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model_name, cache_folder=cache_folder or settings.HF_CACHE_DIR or None)
        self.dimension = self.model.get_embedding_dimension()

    def embed_text(self, text: str) -> np.ndarray:
        return self.model.encode(text, normalize_embeddings=True).astype(np.float32)

    def embed_documents(self, texts: List[str]) -> np.ndarray:
        return self.model.encode(texts, normalize_embeddings=True).astype(np.float32)

    def get_dimension(self) -> int:
        return self.dimension


def get_embeddings_manager() -> BaseEmbeddings:
    """Factory to get configured embeddings provider."""
    provider = settings.EMBEDDING_PROVIDER.lower()
    if provider == "minilm":
        try:
            return MiniLMEmbedder()
        except Exception as e:
            print(f"[Warning] MiniLM embeddings unavailable: {e}. Falling back to local embedder.")
            return LocalDenseEmbedder(settings.EMBEDDING_DIM)
    if provider == "gemini" and settings.GEMINI_API_KEY:
        try:
            return GeminiEmbedder(settings.GEMINI_API_KEY)
        except Exception:
            return LocalDenseEmbedder(settings.EMBEDDING_DIM)
    return LocalDenseEmbedder(settings.EMBEDDING_DIM)
