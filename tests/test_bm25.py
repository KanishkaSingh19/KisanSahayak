import pytest
from app.rag.bm25_retriever import BM25Retriever, tokenize_text
from app.rag.chunker import DocumentChunk


def test_tokenize_text():
    tokens = tokenize_text("Kisan, Sahayak! Spray Tebuconazole 25.9% EC @ 200ml.")
    assert "kisan" in tokens
    assert "sahayak" in tokens
    assert "tebuconazole" in tokens
    assert "200ml" in tokens


def test_bm25_retriever_ranking():
    chunks = [
        DocumentChunk(chunk_id="c1", text="Wheat yellow rust requires Tebuconazole fungicide spray.", metadata={}),
        DocumentChunk(chunk_id="c2", text="Mustard aphids are controlled with Dimethoate or Thiamethoxam.", metadata={}),
        DocumentChunk(chunk_id="c3", text="Paddy brown planthopper can cause severe hopper burn damage.", metadata={}),
    ]

    retriever = BM25Retriever()
    retriever.build_index(chunks)

    results = retriever.search("Tebuconazole wheat yellow rust", top_k=2)
    assert len(results) >= 1
    top_chunk, score = results[0]
    assert top_chunk.chunk_id == "c1"
    assert score > 0


def test_bm25_retriever_zero_match():
    chunks = [
        DocumentChunk(chunk_id="c1", text="Wheat cultivation guide.", metadata={}),
    ]
    retriever = BM25Retriever()
    retriever.build_index(chunks)
    results = retriever.search("astronomy spaceship orbit", top_k=2)
    assert len(results) == 0
