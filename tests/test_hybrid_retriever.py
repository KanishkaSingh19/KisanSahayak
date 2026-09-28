import pytest
from app.rag.chunker import DocumentChunk
from app.rag.embeddings import LocalDenseEmbedder
from app.rag.hybrid_retriever import HybridRetriever


def test_hybrid_retriever_pipeline(tmp_path):
    embedder = LocalDenseEmbedder(dimension=128)
    retriever = HybridRetriever(embeddings=embedder, final_top_k=2)

    chunks = [
        DocumentChunk(
            chunk_id="chunk_wheat_rust",
            text="Yellow rust in wheat is caused by Puccinia striiformis. Spray Tebuconazole.",
            metadata={"source": "ICAR-PAU", "title": "Wheat Guide", "section": "Yellow Rust", "crop": "Wheat"},
        ),
        DocumentChunk(
            chunk_id="chunk_mustard_aphid",
            text="Mustard aphids cause leaf curling and honeydew. Spray Dimethoate.",
            metadata={"source": "ICAR-DRMR", "title": "Mustard Guide", "section": "Aphids", "crop": "Mustard"},
        ),
    ]

    retriever.build_indices(chunks)
    assert retriever.is_ready is True

    # Search
    results = retriever.retrieve("Tebuconazole yellow rust wheat", top_k=2)
    assert len(results) >= 1
    assert results[0].crop == "Wheat"
    assert "ICAR-PAU" in results[0].citation

    # Test persistence (save and load)
    retriever.save_indices(tmp_path)
    new_retriever = HybridRetriever(embeddings=embedder, final_top_k=2)
    loaded = new_retriever.load_indices(tmp_path)
    assert loaded is True
    assert new_retriever.is_ready is True

    loaded_results = new_retriever.retrieve("Mustard aphids Dimethoate")
    assert len(loaded_results) >= 1
    assert loaded_results[0].crop == "Mustard"
