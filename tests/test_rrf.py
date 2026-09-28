import pytest
from app.rag.chunker import DocumentChunk
from app.rag.rrf import reciprocal_rank_fusion


def test_rrf_scoring_order():
    c1 = DocumentChunk(chunk_id="c1", text="Doc 1", metadata={})
    c2 = DocumentChunk(chunk_id="c2", text="Doc 2", metadata={})
    c3 = DocumentChunk(chunk_id="c3", text="Doc 3", metadata={})

    # Dense ranked: c1 (rank 1), c2 (rank 2)
    dense_results = [(c1, 0.95), (c2, 0.80)]
    # Sparse ranked: c2 (rank 1), c3 (rank 2)
    sparse_results = [(c2, 10.5), (c3, 5.0)]

    # c2 is in both lists (rank 2 in dense, rank 1 in sparse)
    # c1 is rank 1 in dense only
    # c3 is rank 2 in sparse only
    fused = reciprocal_rank_fusion(dense_results, sparse_results, k=60, top_n=3)

    assert len(fused) == 3
    # c2 should have highest fused score because it appears high in both lists
    # score(c2) = 1/(60+2) + 1/(60+1) = 1/62 + 1/61 = 0.016129 + 0.016393 = 0.032522
    # score(c1) = 1/(60+1) = 1/61 = 0.016393
    # score(c3) = 1/(60+2) = 1/62 = 0.016129
    top_chunk, score, meta = fused[0]
    assert top_chunk.chunk_id == "c2"
    assert fused[1][0].chunk_id == "c1"
    assert fused[2][0].chunk_id == "c3"


def test_rrf_empty_inputs():
    fused = reciprocal_rank_fusion([], [], k=60, top_n=3)
    assert fused == []
