import hashlib
import time
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
    """Embeddings via the Gemini API (gemini-embedding-001, 768-dim).

    Used where local models don't fit (e.g. Streamlit Community Cloud). If an API call fails,
    the local embedder is used at the same 768 dimensions, so vectors never have mixed sizes.
    """

    DIMENSION = 768
    BATCH_SIZE = 50
    RATE_LIMIT_RETRIES = 3  # per batch, while building the index
    RATE_LIMIT_WAIT_SEC = 30

    def __init__(self, api_key: str, model: str = "gemini-embedding-001"):
        from google import genai
        from google.genai import types

        retry = types.HttpRetryOptions(attempts=2, initial_delay=0.5, max_delay=1.0, http_status_codes=[500, 503])
        self.client = genai.Client(api_key=api_key, http_options=types.HttpOptions(retry_options=retry, timeout=10_000))
        self.model = model
        self._fallback = LocalDenseEmbedder(self.DIMENSION)
        self.fallback_count = 0  # texts embedded locally because the API call failed

    def _embed(self, texts: List[str], task_type: str) -> np.ndarray:
        from google.genai import types

        res = self.client.models.embed_content(
            model=self.model,
            contents=texts,
            config=types.EmbedContentConfig(task_type=task_type, output_dimensionality=self.DIMENSION),
        )
        vectors = np.array([e.values for e in res.embeddings], dtype=np.float32)
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        return vectors / np.where(norms > 0, norms, 1.0)

    def embed_text(self, text: str) -> np.ndarray:
        try:
            return self._embed([text], "RETRIEVAL_QUERY")[0]
        except Exception as e:
            print(f"[Warning] Gemini embedding failed: {str(e)[:120]}. Using local embedder for this query.")
            self.fallback_count += 1
            return self._fallback.embed_text(text)

    def _embed_with_rate_limit(self, batch: List[str]) -> np.ndarray:
        """Embed a batch of documents, waiting out the free tier's per-minute limit (429) a few times:
        building the index happens once, and a batch embedded locally instead would search badly."""
        for attempt in range(self.RATE_LIMIT_RETRIES + 1):
            try:
                return self._embed(batch, "RETRIEVAL_DOCUMENT")
            except Exception as e:
                if "429" not in str(e) or attempt == self.RATE_LIMIT_RETRIES:
                    raise
                print(f"[Info] Gemini embedding rate limit: waiting {self.RATE_LIMIT_WAIT_SEC} s before retrying.")
                time.sleep(self.RATE_LIMIT_WAIT_SEC)
        raise RuntimeError("unreachable")

    def embed_documents(self, texts: List[str]) -> np.ndarray:
        batches = []
        for start in range(0, len(texts), self.BATCH_SIZE):
            batch = texts[start : start + self.BATCH_SIZE]
            try:
                batches.append(self._embed_with_rate_limit(batch))
            except Exception as e:
                print(f"[Warning] Gemini embedding failed: {str(e)[:120]}. Using local embedder for this batch.")
                self.fallback_count += len(batch)
                batches.append(self._fallback.embed_documents(batch))
        if not batches:
            return np.zeros((0, self.DIMENSION), dtype=np.float32)
        return np.vstack(batches).astype(np.float32)

    def get_dimension(self) -> int:
        return self.DIMENSION


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
        except Exception as e:
            print(f"[Warning] Gemini embeddings unavailable: {e}. Falling back to local embedder.")
            return LocalDenseEmbedder(settings.EMBEDDING_DIM)
    return LocalDenseEmbedder(settings.EMBEDDING_DIM)
