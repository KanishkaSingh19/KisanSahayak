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


SENTENCES = [
    "Inspect the crop every week from December.",
    "Spray Propiconazole 25% EC at 200 ml per acre.",
    "Repeat after 15 days if cloudy weather continues.",
    "Grow resistant varieties like PBW 725.",
    "Do not spray in strong wind.",
]


def _bodies(chunker, header="H\n"):
    return [s[len(header):] for s in chunker._sliding_window_split(" ".join(SENTENCES), header)]


def test_overlap_repeats_end_of_previous_window_within_limit():
    chunker = AgriculturalChunker(chunk_size=120, chunk_overlap=60)
    bodies = _bodies(chunker)
    assert len(bodies) > 1
    for prev, nxt in zip(bodies, bodies[1:]):
        shared = next(n for n in range(min(len(prev), len(nxt)), 0, -1) if prev.endswith(nxt[:n]))
        assert 0 < shared <= 60


def test_larger_overlap_carries_more():
    small = _bodies(AgriculturalChunker(chunk_size=120, chunk_overlap=30))
    large = _bodies(AgriculturalChunker(chunk_size=120, chunk_overlap=100))
    assert len(large) >= len(small)


def test_zero_overlap_repeats_nothing_and_loses_nothing():
    bodies = _bodies(AgriculturalChunker(chunk_size=120, chunk_overlap=0))
    assert " ".join(bodies) == " ".join(SENTENCES)


def test_every_sentence_is_kept():
    joined = " ".join(_bodies(AgriculturalChunker(chunk_size=120, chunk_overlap=60)))
    assert all(s in joined for s in SENTENCES)


def test_overlap_must_be_smaller_than_chunk_size():
    with pytest.raises(ValueError):
        AgriculturalChunker(chunk_size=100, chunk_overlap=100)
