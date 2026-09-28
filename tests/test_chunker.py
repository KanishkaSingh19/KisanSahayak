import pytest
from app.rag.chunker import AgriculturalChunker, DocumentChunk


def test_chunker_basic_structure():
    raw_doc = {
        "source_organization": "ICAR-PAU",
        "document_title": "Wheat Advisory",
        "crop": "Wheat",
        "season": "Rabi",
        "publication_year": 2024,
        "sections": [
            {
                "section_title": "Yellow Rust",
                "disease_pest_name": "Puccinia striiformis",
                "symptoms": "Yellow powder on leaves in linear rows.",
                "recommended_action": "Spray Tebuconazole 25.9% EC @ 200 ml.",
                "preventive_measures": "Grow PBW 725.",
                "critical_safety_warning": "Wear mask.",
            }
        ],
    }

    chunker = AgriculturalChunker(chunk_size=500, chunk_overlap=100)
    chunks = chunker.chunk_structured_document(raw_doc, "wheat_test")

    assert len(chunks) >= 1
    chunk = chunks[0]
    assert isinstance(chunk, DocumentChunk)
    assert "Yellow Rust" in chunk.text
    assert "Tebuconazole" in chunk.text
    assert chunk.metadata["crop"] == "Wheat"
    assert chunk.metadata["source"] == "ICAR-PAU"
    assert chunk.metadata["has_warning"] is True


def test_chunker_sliding_window_split():
    chunker = AgriculturalChunker(chunk_size=150, chunk_overlap=50)
    long_text = (
        "First long sentence about wheat crop protection. "
        "Second detailed sentence explaining fungal spores. "
        "Third sentence describing weather parameters for germination. "
        "Fourth sentence giving precise milliliter chemical dosage."
    )
    splits = chunker._sliding_window_split(long_text, "Crop: Wheat\n")
    assert len(splits) > 1
    for s in splits:
        assert s.startswith("Crop: Wheat\n")
