import pytest
from app.rag.chunker import DocumentChunk
from app.rag.embeddings import LocalDenseEmbedder
from app.rag.faiss_retriever import FAISSRetriever


def test_faiss_retriever_search():
    embedder = LocalDenseEmbedder(dimension=128)
    retriever = FAISSRetriever(embeddings=embedder)

    chunks = [
        DocumentChunk(chunk_id="c1", text="Wheat rust disease symptoms and fungicide spray.", metadata={"crop": "Wheat"}),
        DocumentChunk(chunk_id="c2", text="Mustard aphid control with thiamethoxam.", metadata={"crop": "Mustard"}),
        DocumentChunk(chunk_id="c3", text="Rice bacterial leaf blight water management.", metadata={"crop": "Rice"}),
    ]

    retriever.build_index(chunks)
    results = retriever.search("wheat rust disease", top_k=2)

    assert len(results) == 2
    top_chunk, score = results[0]
    assert top_chunk.chunk_id == "c1"
    assert score > 0.0


def test_faiss_retriever_rejects_mismatched_dimension(tmp_path):
    chunks = [DocumentChunk(chunk_id="c1", text="Wheat rust disease symptoms.", metadata={"crop": "Wheat"})]
    old = FAISSRetriever(embeddings=LocalDenseEmbedder(dimension=128))
    old.build_index(chunks)
    old.save(tmp_path)

    # Switching embedding providers changes the vector size; the stale index must not load
    new = FAISSRetriever(embeddings=LocalDenseEmbedder(dimension=64))
    assert new.load(tmp_path) is False
    assert FAISSRetriever(embeddings=LocalDenseEmbedder(dimension=128)).load(tmp_path) is True


def test_faiss_retriever_empty():
    embedder = LocalDenseEmbedder(dimension=128)
    retriever = FAISSRetriever(embeddings=embedder)
    retriever.build_index([])
    results = retriever.search("anything", top_k=5)
    assert len(results) == 0
