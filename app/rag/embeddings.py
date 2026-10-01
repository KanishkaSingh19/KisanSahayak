import hashlib
import time
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional
import numpy as np

from app.config import settings

# Gemini document vectors computed once (scripts/build_embedding_cache.py) and committed, so that a
# cold start on Streamlit Cloud does not re-embed every chunk against the free tier's per-minute limit
GEMINI_CACHE_PATH = settings.DATA_DIR / "vectors" / "gemini_embedding_cache.npz"


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


def gemini_cache_key(text: str, model: str = "gemini-embedding-001", dimension: int = 768) -> str:
    return hashlib.sha1(f"{model}|{dimension}|{text}".encode("utf-8")).hexdigest()


def gemini_cached_keys(path: Path = GEMINI_CACHE_PATH) -> set:
    """Keys of the shipped Gemini document vectors (no API client needed)."""
    return set(np.load(path)["keys"].tolist()) if Path(path).exists() else set()


class GeminiEmbedder(BaseEmbeddings):
    """Embeddings via the Gemini API (gemini-embedding-001, 768-dim).

    Used where local models don't fit (e.g. Streamlit Community Cloud). If an API call fails,
    the local embedder is used at the same 768 dimensions, so vectors never have mixed sizes.
    """

    DIMENSION = 768
    BATCH_SIZE = 50
    RATE_LIMIT_WAIT_SEC = 30
    RATE_LIMIT_RETRIES = 2  # per batch
    MAX_RATE_LIMIT_WAIT_SEC = 60  # in total, per index build: the app must start


    def __init__(self, api_key: str, model: str = "gemini-embedding-001"):
        from google import genai
        from google.genai import types

        retry = types.HttpRetryOptions(attempts=2, initial_delay=0.5, max_delay=1.0, http_status_codes=[500, 503])
        self.client = genai.Client(api_key=api_key, http_options=types.HttpOptions(retry_options=retry, timeout=10_000))
        self.model = model
        self._fallback = LocalDenseEmbedder(self.DIMENSION)
        self.fallback_count = 0  # texts embedded locally because the API call failed
        self._cache: Optional[Dict[str, np.ndarray]] = None

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

    def cache_key(self, text: str) -> str:
        return gemini_cache_key(text, self.model, self.DIMENSION)

    def load_cache(self, path: Path = GEMINI_CACHE_PATH) -> Dict[str, np.ndarray]:
        """Document vectors computed earlier ({sha1 of model, size and text: vector}), shipped with the
        app so a cold start does not re-embed hundreds of texts against the free tier's limits."""
        if self._cache is None:
            self._cache = {}
            if Path(path).exists():
                data = np.load(path)
                self._cache = dict(zip(data["keys"].tolist(), data["vectors"]))
        return self._cache

    def save_cache(self, path: Path = GEMINI_CACHE_PATH) -> None:
        cache = self.load_cache(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(path, keys=np.array(list(cache)), vectors=np.array(list(cache.values()), dtype=np.float32))

    def missing_from_cache(self, texts: List[str]) -> int:
        cache = self.load_cache()
        return sum(self.cache_key(t) not in cache for t in texts)

    def _embed_with_rate_limit(self, batch: List[str], deadline: float) -> np.ndarray:
        """Embed a batch of documents, waiting out the free tier's per-minute limit (429) until
        `deadline` at most: past it, the app must start rather than wait."""
        for attempt in range(self.RATE_LIMIT_RETRIES + 1):
            try:
                return self._embed(batch, "RETRIEVAL_DOCUMENT")
            except Exception as e:
                last_try = attempt == self.RATE_LIMIT_RETRIES or time.time() + self.RATE_LIMIT_WAIT_SEC > deadline
                if "429" not in str(e) or last_try:
                    raise
                print(f"[Info] Gemini embedding rate limit: waiting {self.RATE_LIMIT_WAIT_SEC} s before retrying.")
                time.sleep(self.RATE_LIMIT_WAIT_SEC)
        raise RuntimeError("unreachable: the last attempt re-raises")

    def embed_documents(self, texts: List[str], max_wait_sec: Optional[float] = None) -> np.ndarray:
        """Vectors for `texts`: from the shipped cache where possible, from the API otherwise. Waits for
        rate limits for `max_wait_sec` in total; once the quota is out, the rest use the local embedder."""
        cache = self.load_cache()
        deadline = time.time() + (self.MAX_RATE_LIMIT_WAIT_SEC if max_wait_sec is None else max_wait_sec)
        missing = [t for t in dict.fromkeys(texts) if self.cache_key(t) not in cache]
        quota_out = False
        for start in range(0, len(missing), self.BATCH_SIZE):
            batch = missing[start : start + self.BATCH_SIZE]
            try:
                if quota_out:
                    raise RuntimeError("quota used up earlier in this build")
                vectors = self._embed_with_rate_limit(batch, deadline)
                cache.update({self.cache_key(t): v for t, v in zip(batch, vectors)})
            except Exception as e:
                quota_out = quota_out or "429" in str(e)
                print(f"[Warning] Gemini embedding failed: {str(e)[:120]}. Using local embedder for this batch.")
                self.fallback_count += len(batch)
                local = {t: v for t, v in zip(batch, self._fallback.embed_documents(batch))}
                cache.update({f"local:{t}": v for t, v in local.items()})  # this run only, never saved
        if not texts:
            return np.zeros((0, self.DIMENSION), dtype=np.float32)
        return np.array([cache.get(self.cache_key(t), cache.get(f"local:{t}")) for t in texts], dtype=np.float32)

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
