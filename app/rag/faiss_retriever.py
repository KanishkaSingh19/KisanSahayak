import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from app.rag.chunker import DocumentChunk
from app.rag.embeddings import BaseEmbeddings, get_embeddings_manager

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False


class FAISSRetriever:
    """FAISS-based dense semantic vector retriever with pure-numpy fallback."""

    def __init__(self, embeddings: Optional[BaseEmbeddings] = None):
        self.embeddings = embeddings or get_embeddings_manager()
        self.dimension = self.embeddings.get_dimension()
        self.chunks: List[DocumentChunk] = []
        self.vectors: Optional[np.ndarray] = None
        self.faiss_index = None

    def build_index(self, chunks: List[DocumentChunk]) -> None:
        """Embed all chunks and populate the dense index."""
        self.chunks = chunks
        if not chunks:
            self.vectors = np.zeros((0, self.dimension), dtype=np.float32)
            return

        texts = [c.text for c in chunks]
        self.vectors = self.embeddings.embed_documents(texts)
        # Ensure float32
        self.vectors = np.ascontiguousarray(self.vectors, dtype=np.float32)

        if FAISS_AVAILABLE:
            # Inner Product (equivalent to Cosine Similarity since vectors are normalized)
            self.faiss_index = faiss.IndexFlatIP(self.dimension)
            self.faiss_index.add(self.vectors)

    def search(self, query: str, top_k: int = 5) -> List[Tuple[DocumentChunk, float]]:
        """Search dense index and return list of (DocumentChunk, score) tuples."""
        if not self.chunks or self.vectors is None or len(self.chunks) == 0:
            return []

        query_vec = self.embeddings.embed_text(query).astype(np.float32)
        query_vec = np.ascontiguousarray(query_vec.reshape(1, -1))

        effective_k = min(top_k, len(self.chunks))

        if FAISS_AVAILABLE and self.faiss_index is not None:
            distances, indices = self.faiss_index.search(query_vec, effective_k)
            results = []
            for idx, score in zip(indices[0], distances[0]):
                if idx < len(self.chunks) and idx >= 0:
                    results.append((self.chunks[idx], float(score)))
            return results
        else:
            # Fallback pure-numpy cosine similarity
            # Since vectors are L2-normalized: dot product is cosine similarity
            scores = np.dot(self.vectors, query_vec.T).flatten()
            top_indices = np.argsort(scores)[::-1][:effective_k]
            results = [(self.chunks[i], float(scores[i])) for i in top_indices]
            return results

    def save(self, index_dir: Path) -> None:
        """Persist index and metadata to disk."""
        os.makedirs(index_dir, exist_ok=True)
        chunks_data = [c.model_dump() for c in self.chunks]
        with open(index_dir / "dense_chunks.json", "w", encoding="utf-8") as f:
            json.dump(chunks_data, f, ensure_ascii=False, indent=2)

        if self.vectors is not None:
            np.save(index_dir / "dense_vectors.npy", self.vectors)

        if FAISS_AVAILABLE and self.faiss_index is not None:
            faiss.write_index(self.faiss_index, str(index_dir / "faiss.index"))

    def load(self, index_dir: Path) -> bool:
        """Load persisted index and chunks from disk."""
        chunks_path = index_dir / "dense_chunks.json"
        vectors_path = index_dir / "dense_vectors.npy"

        if not chunks_path.exists():
            return False

        # Index built with a different embedding provider/dimension: force a rebuild
        if vectors_path.exists():
            vectors = np.load(vectors_path)
            if vectors.ndim != 2 or vectors.shape[1] != self.dimension:
                return False
            self.vectors = vectors

        with open(chunks_path, "r", encoding="utf-8") as f:
            chunks_data = json.load(f)
        self.chunks = [DocumentChunk(**item) for item in chunks_data]

        faiss_path = index_dir / "faiss.index"
        if FAISS_AVAILABLE and faiss_path.exists():
            self.faiss_index = faiss.read_index(str(faiss_path))
        elif self.vectors is not None and FAISS_AVAILABLE:
            self.faiss_index = faiss.IndexFlatIP(self.dimension)
            self.faiss_index.add(np.ascontiguousarray(self.vectors, dtype=np.float32))

        return True
