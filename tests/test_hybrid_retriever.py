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


def _chunk(cid, section, text, **meta):
    return DocumentChunk(chunk_id=cid, text=text, metadata={"doc_id": "d", "section": section, "crop": "Paddy", **meta})


def test_a_long_section_does_not_crowd_out_other_sections():
    """Three chunks of one section must not take all three result slots."""
    retriever = HybridRetriever(embeddings=LocalDenseEmbedder(dimension=128), final_top_k=2)
    retriever.build_indices([
        _chunk("bph_0", "Brown Planthopper", "planthopper hoppers spray base of plants"),
        _chunk("bph_1", "Brown Planthopper", "planthopper hopper burn patches spray"),
        _chunk("bph_2", "Brown Planthopper", "planthopper neem extract spray"),
        _chunk("sb_0", "Sheath Blight", "sheath blight lesions spray Nativo"),
    ])
    results = retriever.retrieve("planthopper spray")
    assert [r.section for r in results[:2]] == ["Brown Planthopper", "Sheath Blight"]
    # The section's other chunks follow, so an LLM answer still sees the whole advisory
    assert {r.chunk_id for r in results} >= {"bph_0", "bph_1", "bph_2"}


def test_citation_shows_the_page_reference():
    retriever = HybridRetriever(embeddings=LocalDenseEmbedder(dimension=128), final_top_k=1)
    retriever.build_indices([_chunk("sb_0", "Sheath Blight", "sheath blight Nativo",
                                    reference="PAU Package of Practices, Kharif 2026, pages 16-19")])
    assert retriever.retrieve("sheath blight")[0].citation == "PAU Package of Practices, Kharif 2026, pages 16-19 [Sheath Blight]"
