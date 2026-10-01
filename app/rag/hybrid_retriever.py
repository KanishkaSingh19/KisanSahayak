from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from app.config import settings
from app.rag.bm25_retriever import BM25Retriever, tokenize_text
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
    kind: str = "advisory"  # "advisory" (data/raw) or "pau" (PAU Package of Practices chapter)
    rank_details: Dict[str, Any] = Field(default_factory=dict)


SIBLINGS_PER_SECTION = 3  # extra chunks of a top section passed on with it (a long PAU section has many)


def section_key(chunk: DocumentChunk) -> Tuple:
    return chunk.metadata.get("doc_id"), chunk.metadata.get("section")


# Words that name no topic: they appear in many section titles or in every question
TITLE_STOPWORDS = {"the", "and", "for", "how", "what", "which", "when", "control", "management", "crop", "crops",
                   "wheat", "paddy", "rice", "cotton", "mustard", "rapeseed", "basmati", "desi", "pau", "with",
                   "should", "can", "about", "tell", "give", "best", "my", "in", "of", "to", "do", "is", "are"}


def _stem(word: str) -> str:
    """"varieties" -> "variety", "weeds" -> "weed", "harvesting" -> "harvest"."""
    if word.endswith("ies"):
        return word[:-3] + "y"
    word = word.rstrip("s")
    return word[:-3] if word.endswith("ing") and len(word) > 6 else word


def _title_words(text: str) -> set:
    return {_stem(w) for w in tokenize_text(text) if len(w) > 2 and w not in TITLE_STOPWORDS}


def title_matches(query: str, results: List[Tuple[DocumentChunk, float]]) -> List[Tuple[DocumentChunk, float]]:
    """The sections whose title shares words with the query, most shared words first (ties keep the
    order of `results`). "Weeds in wheat" -> "Wheat - Weed Control" before "Wheat - Sowing Method"."""
    wanted = _title_words(query)
    scored = [(chunk, float(len(wanted & _title_words(chunk.metadata.get("section", ""))))) for chunk, _ in results]
    return sorted([(c, s) for c, s in scored if s > 0], key=lambda item: -item[1])


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

    def retrieve(self, query: str, top_k: Optional[int] = None, kind: Optional[str] = None,
                 crop: Optional[str] = None) -> List[RetrievalResult]:
        """The best `top_k` advisory sections for the query (one chunk each, in ranked order),
        followed by any other retrieved chunks of those same sections. Hybrid search: dense + sparse + RRF.
        `kind` limits the search to "advisory" or "pau" chunks (None: all), and `crop` to one crop's
        chunks plus those for all crops ("Paddy" matches "Paddy (Rice)")."""
        if not self.is_ready:
            raise RuntimeError("HybridRetriever is not initialized. Build or load indices first.")

        limit = top_k or self.final_top_k

        # 1-2. Dense and sparse candidates, ranked by advisory section: a long section split into
        # several chunks must not fill every slot and push other sections out of the ranking
        pool = len(self.dense_retriever.chunks) if kind or crop else max(self.k_dense, self.k_sparse) * 4

        def wanted(results):
            return [
                (c, s) for c, s in results
                if (not kind or c.metadata.get("kind", "advisory") == kind)
                and (not crop or str(c.metadata.get("crop", "")).lower().startswith((crop.lower(), "all crops")))
            ]

        dense_all = wanted(self.dense_retriever.search(query, top_k=pool))
        sparse_all = wanted(self.sparse_retriever.search(query, top_k=pool))
        dense_best = best_chunk_per_section(dense_all)[: self.k_dense]
        sparse_best = best_chunk_per_section(sparse_all)[: self.k_sparse]
        # RRF matches results by chunk id: give each section one representative chunk in both lists
        # (the dense search may rank chunk 2 of a section first and BM25 chunk 0)
        representative: Dict[Tuple, DocumentChunk] = {}
        for chunk, _ in dense_best + sparse_best:
            representative.setdefault(section_key(chunk), chunk)
        dense_results = [(representative[section_key(c)], s) for c, s in dense_best]
        sparse_results = [(representative[section_key(c)], s) for c, s in sparse_best]
        # PAU's chapters have many long sections that mention a topic in passing ("weeds" in the
        # sowing section): rank the sections whose own title names it as well
        title_results = None
        if kind == "pau":
            title_results = []
            for chunk, score in title_matches(query, best_chunk_per_section(dense_all))[: self.k_dense]:
                title_results.append((representative.setdefault(section_key(chunk), chunk), score))

        # 3. Fuse with RRF: the top `limit` sections
        fused = reciprocal_rank_fusion(
            dense_results=dense_results,
            sparse_results=sparse_results,
            k=self.rrf_k,
            top_n=limit,
            title_results=title_results,
        )
        # Then the rest of those sections (up to SIBLINGS_PER_SECTION more chunks each, in their
        # order of relevance), so an LLM answer sees the whole advisory
        chosen = {section_key(c) for c, _, _ in fused}
        listed = {c.chunk_id for c, _, _ in fused}
        added: Dict[Tuple, int] = {}
        ranked = [c for c, _ in dense_all] + [c for c in self.dense_retriever.chunks]
        for chunk in ranked:
            key = section_key(chunk)
            if key in chosen and chunk.chunk_id not in listed and added.get(key, 0) < SIBLINGS_PER_SECTION:
                listed.add(chunk.chunk_id)
                added[key] = added.get(key, 0) + 1
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
                    kind=meta.get("kind", "advisory"),
                    rank_details=rank_info,
                )
            )

        return results
