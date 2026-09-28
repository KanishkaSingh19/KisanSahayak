from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.config import settings
from app.rag.bm25_retriever import BM25Retriever
from app.rag.chunker import DocumentChunk
from app.rag.embeddings import BaseEmbeddings, get_embeddings_manager
from app.rag.faiss_retriever import FAISSRetriever
from app.rag.rrf import reciprocal_rank_fusion


class RetrievalResult(BaseModel):
    chunk_id: str
    text: str
    score: float
    citation: str
    source_agency: str
    crop: str
    section: str
    rank_details: Dict[str, Any] = Field(default_factory=dict)


class HybridRetriever:
    """Orchestrates FAISS dense search, BM25 sparse search, and RRF fusion."""

    def __init__(
        self,
        embeddings: Optional[BaseEmbeddings] = None,
        k_dense: int = settings.RAG_TOP_K_DENSE,
        k_sparse: int = settings.RAG_TOP_K_SPARSE,
        final_top_k: int = settings.RAG_FINAL_TOP_K,
        rrf_k: int = settings.RRF_K,
    ):
        self.embeddings = embeddings or get_embeddings_manager()
        self.k_dense = k_dense
        self.k_sparse = k_sparse
        self.final_top_k = final_top_k
        self.rrf_k = rrf_k

        self.dense_retriever = FAISSRetriever(self.embeddings)
        self.sparse_retriever = BM25Retriever()
        self.is_ready = False

    def build_indices(self, chunks: List[DocumentChunk]) -> None:
        """Build both dense and sparse indices from a list of chunks."""
        self.dense_retriever.build_index(chunks)
        self.sparse_retriever.build_index(chunks)
        self.is_ready = True

    def save_indices(self, index_dir: Path = settings.INDEX_DIR) -> None:
        """Persist indices to disk."""
        self.dense_retriever.save(index_dir)
        self.sparse_retriever.save(index_dir)

    def load_indices(self, index_dir: Path = settings.INDEX_DIR) -> bool:
        """Load indices from disk."""
        dense_ok = self.dense_retriever.load(index_dir)
        sparse_ok = self.sparse_retriever.load(index_dir)
        self.is_ready = dense_ok and sparse_ok
        return self.is_ready

    def retrieve(self, query: str, top_k: Optional[int] = None) -> List[RetrievalResult]:
        """Perform hybrid search using dense + sparse + RRF."""
        if not self.is_ready:
            raise RuntimeError("HybridRetriever is not initialized. Build or load indices first.")

        limit = top_k or self.final_top_k

        # 1. Fetch dense candidates
        dense_results = self.dense_retriever.search(query, top_k=self.k_dense)

        # 2. Fetch sparse candidates
        sparse_results = self.sparse_retriever.search(query, top_k=self.k_sparse)

        # 3. Fuse with RRF
        fused = reciprocal_rank_fusion(
            dense_results=dense_results,
            sparse_results=sparse_results,
            k=self.rrf_k,
            top_n=limit,
        )

        # 4. Format into structured RetrievalResult objects with formal citations
        results: List[RetrievalResult] = []
        for chunk, score, rank_info in fused:
            meta = chunk.metadata
            org = meta.get("source", "ICAR")
            title = meta.get("title", "Advisory")
            sec = meta.get("section", "General")
            crop = meta.get("crop", "Agriculture")

            citation = f"{org} - {title} [{sec}]"
            results.append(
                RetrievalResult(
                    chunk_id=chunk.chunk_id,
                    text=chunk.text,
                    score=score,
                    citation=citation,
                    source_agency=org,
                    crop=crop,
                    section=sec,
                    rank_details=rank_info,
                )
            )

        return results
