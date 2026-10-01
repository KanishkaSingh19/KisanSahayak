import json
import math
import os
from pathlib import Path
from typing import Dict, List, Tuple

from app.rag.chunker import DocumentChunk

try:
    from rank_bm25 import BM25Okapi
    RANK_BM25_AVAILABLE = True
except ImportError:
    RANK_BM25_AVAILABLE = False


import unicodedata


def tokenize_text(text: str) -> List[str]:
    """Tokenize text into lowercase terms, properly preserving Indic scripts and diacritics."""
    cleaned_chars = []
    for ch in text.lower():
        cat = unicodedata.category(ch)
        # P = Punctuation, S = Symbol, C = Other/Control
        if cat.startswith("P") or cat.startswith("S") or cat.startswith("C"):
            cleaned_chars.append(" ")
        else:
            cleaned_chars.append(ch)
    cleaned = "".join(cleaned_chars)
    tokens = cleaned.split()
    return [t for t in tokens if len(t) > 1]



class BuiltinBM25:
    """Pure-Python BM25Okapi implementation for zero-dependency execution."""

    def __init__(self, corpus: List[List[str]], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus_size = len(corpus)
        self.doc_lengths = [len(doc) for doc in corpus]
        self.avg_doc_len = sum(self.doc_lengths) / (self.corpus_size or 1)

        self.doc_freqs: Dict[str, int] = {}
        self.doc_term_counts: List[Dict[str, int]] = []

        for doc in corpus:
            counts: Dict[str, int] = {}
            for term in doc:
                counts[term] = counts.get(term, 0) + 1
            self.doc_term_counts.append(counts)
            for term in counts.keys():
                self.doc_freqs[term] = self.doc_freqs.get(term, 0) + 1

        self.idf: Dict[str, float] = {}
        for term, freq in self.doc_freqs.items():
            # Standard Lucene/BM25 IDF formula
            self.idf[term] = math.log(1.0 + (self.corpus_size - freq + 0.5) / (freq + 0.5))

    def get_scores(self, query_tokens: List[str]) -> List[float]:
        scores = [0.0] * self.corpus_size
        for term in query_tokens:
            if term not in self.idf:
                continue
            term_idf = self.idf[term]
            for doc_idx, term_counts in enumerate(self.doc_term_counts):
                tf = term_counts.get(term, 0)
                if tf == 0:
                    continue
                doc_len = self.doc_lengths[doc_idx]
                denom = tf + self.k1 * (1.0 - self.b + self.b * (doc_len / (self.avg_doc_len or 1)))
                scores[doc_idx] += term_idf * (tf * (self.k1 + 1.0)) / denom
        return scores


class BM25Retriever:
    """Sparse keyword retriever utilizing BM25Okapi."""

    def __init__(self):
        self.chunks: List[DocumentChunk] = []
        self.tokenized_corpus: List[List[str]] = []
        self.bm25_model = None

    def build_index(self, chunks: List[DocumentChunk]) -> None:
        """Tokenize chunks and build BM25 sparse index."""
        self.chunks = chunks
        self.tokenized_corpus = [tokenize_text(c.text) for c in chunks]

        if not self.chunks:
            return

        if RANK_BM25_AVAILABLE:
            self.bm25_model = BM25Okapi(self.tokenized_corpus)
        else:
            self.bm25_model = BuiltinBM25(self.tokenized_corpus)

    def search(self, query: str, top_k: int = 5) -> List[Tuple[DocumentChunk, float]]:
        """Search BM25 index and return list of (DocumentChunk, score) tuples."""
        if not self.chunks or self.bm25_model is None:
            return []

        query_tokens = tokenize_text(query)
        if not query_tokens:
            return []

        scores = self.bm25_model.get_scores(query_tokens)
        effective_k = min(top_k, len(self.chunks))

        indexed_scores = list(enumerate(scores))
        indexed_scores.sort(key=lambda x: x[1], reverse=True)

        results = []
        for idx, score in indexed_scores[:effective_k]:
            if score > 0:
                results.append((self.chunks[idx], float(score)))

        return results

    def save(self, index_dir: Path) -> None:
        """Persist BM25 chunks and tokenized corpus."""
        os.makedirs(index_dir, exist_ok=True)
        chunks_data = [c.model_dump() for c in self.chunks]
        with open(index_dir / "bm25_chunks.json", "w", encoding="utf-8") as f:
            json.dump(chunks_data, f, ensure_ascii=False, indent=2)

    def load(self, index_dir: Path) -> bool:
        """Load persisted BM25 corpus and reconstruct index."""
        chunks_path = index_dir / "bm25_chunks.json"
        if not chunks_path.exists():
            return False

        with open(chunks_path, "r", encoding="utf-8") as f:
            chunks_data = json.load(f)

        chunks = [DocumentChunk(**item) for item in chunks_data]
        self.build_index(chunks)
        return True
