from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
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


def section_key(chunk: DocumentChunk) -> Tuple:
    return chunk.metadata.get("doc_id"), chunk.metadata.get("section")


def best_chunk_per_section(results: List[Tuple[DocumentChunk, float]]) -> List[Tuple[DocumentChunk, float]]:
    """Keep only the highest-ranked chunk of each advisory section, in rank order."""
    seen, best = set(), []
    for chunk, score in results:
        section = section_key(chunk)
        if section not in seen:
            seen.add(section)
            best.append((chunk, score))
    return best


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
        """The best `top_k` advisory sections for the query (one chunk each, in ranked order),
        followed by any other retrieved chunks of those same sections. Hybrid search: dense + sparse + RRF."""
        if not self.is_ready:
            raise RuntimeError("HybridRetriever is not initialized. Build or load indices first.")

        limit = top_k or self.final_top_k

        # 1-2. Dense and sparse candidates, ranked by advisory section: a long section split into
        # several chunks must not fill every slot and push other sections out of the ranking
        pool = max(self.k_dense, self.k_sparse) * 4
        dense_all = self.dense_retriever.search(query, top_k=pool)
        sparse_all = self.sparse_retriever.search(query, top_k=pool)
        dense_best = best_chunk_per_section(dense_all)[: self.k_dense]
        sparse_best = best_chunk_per_section(sparse_all)[: self.k_sparse]
        # RRF matches results by chunk id: give each section one representative chunk in both lists
        # (the dense search may rank chunk 2 of a section first and BM25 chunk 0)
        representative: Dict[Tuple, DocumentChunk] = {}
        for chunk, _ in dense_best + sparse_best:
            representative.setdefault(section_key(chunk), chunk)
        dense_results = [(representative[section_key(c)], s) for c, s in dense_best]
        sparse_results = [(representative[section_key(c)], s) for c, s in sparse_best]

        # 3. Fuse with RRF: the top `limit` sections
        fused = reciprocal_rank_fusion(
            dense_results=dense_results,
            sparse_results=sparse_results,
            k=self.rrf_k,
            top_n=limit,
        )
        # Then the rest of those sections, so an LLM answer sees the whole advisory
        chosen = {section_key(c) for c, _, _ in fused}
        listed = {c.chunk_id for c, _, _ in fused}
        for chunk in self.dense_retriever.chunks:
            if section_key(chunk) in chosen and chunk.chunk_id not in listed:
                listed.add(chunk.chunk_id)
                fused.append((chunk, 0.0, {"same_section_as_above": True}))

        # 4. Format into structured RetrievalResult objects with formal citations
        results: List[RetrievalResult] = []
        for chunk, score, rank_info in fused:
            meta = chunk.metadata
            org = meta.get("source", "ICAR")
            title = meta.get("title", "Advisory")
            sec = meta.get("section", "General")
            crop = meta.get("crop", "Agriculture")

            # The printed pages when the advisory gives them ("PAU Package of Practices ..., pages 18-21")
            citation = f"{meta['reference']} [{sec}]" if meta.get("reference") else f"{org} - {title} [{sec}]"
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
