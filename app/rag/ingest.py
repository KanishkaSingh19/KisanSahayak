import argparse
import sys
from pathlib import Path

# Add project root to sys.path if run directly
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from typing import List

from app.config import settings
from app.rag.chunker import AgriculturalChunker, DocumentChunk
from app.rag.hybrid_retriever import HybridRetriever
from app.rag.embeddings import gemini_cache_key, gemini_cached_keys
from app.rag.pau_kb import pau_kb_files

PAU_MAX_UNCACHED = 20  # PAU chunks the app may embed itself on a cold start (one small batch)


def load_knowledge_chunks(raw_dir: Path = settings.RAW_DATA_DIR) -> List[DocumentChunk]:
    """Everything the app searches: the advisories in `raw_dir`, plus PAU's Package of Practices
    chapters when they have been built (settings.PAU_KB_DIR) and USE_PAU_KB is on."""
    chunker = AgriculturalChunker(chunk_size=settings.CHUNK_SIZE, chunk_overlap=settings.CHUNK_OVERLAP)
    chunks = chunker.load_and_chunk_directory(raw_dir)
    if settings.USE_PAU_KB and pau_kb_files():
        pau = chunker.load_and_chunk_directory(settings.PAU_KB_DIR)
        if settings.EMBEDDING_PROVIDER == "gemini":
            # Embedding ~400 PAU chunks on a cold start exceeds the free Gemini quota (13 minutes, then
            # local vectors anyway): use PAU only when the shipped vector cache covers it
            cached = gemini_cached_keys()
            missing = sum(gemini_cache_key(c.text) not in cached for c in pau)
            if missing > PAU_MAX_UNCACHED:
                print(f"[Warning] {missing} PAU chunks have no cached Gemini vectors "
                      "(run scripts/build_embedding_cache.py): starting without PAU's chapters.")
                return chunks
        chunks += pau
    return chunks


def ingest_documents(raw_dir: Path = settings.RAW_DATA_DIR, index_dir: Path = settings.INDEX_DIR) -> int:
    """Ingest agricultural raw JSON documents, chunk, index, and serialize."""
    print(f"Loading raw agricultural documents from: {raw_dir}")
    chunks = load_knowledge_chunks(raw_dir)

    print(f"Extracted {len(chunks)} contextual chunks across all crop advisories.")
    for idx, c in enumerate(chunks[:3]):
        print(f"  Sample Chunk [{c.chunk_id}]: {c.text[:80]}...")

    print("Building Hybrid (FAISS Dense + BM25 Sparse) indices...")
    retriever = HybridRetriever()
    retriever.build_indices(chunks)

    print(f"Saving indices to: {index_dir}")
    retriever.save_indices(index_dir)
    print("Ingestion and indexing completed successfully.")
    return len(chunks)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest agricultural knowledge base into FAISS and BM25.")
    parser.add_argument("--raw-dir", type=Path, default=settings.RAW_DATA_DIR, help="Path to raw json documents")
    parser.add_argument("--index-dir", type=Path, default=settings.INDEX_DIR, help="Path to save index artifacts")
    args = parser.parse_args()

    ingest_documents(args.raw_dir, args.index_dir)
