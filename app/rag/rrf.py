from typing import Any, Dict, List, Tuple
from app.rag.chunker import DocumentChunk


def reciprocal_rank_fusion(
    dense_results: List[Tuple[DocumentChunk, float]],
    sparse_results: List[Tuple[DocumentChunk, float]],
    k: int = 60,
    dense_weight: float = 1.0,
    sparse_weight: float = 1.0,
    top_n: int = 3,
) -> List[Tuple[DocumentChunk, float, Dict[str, Any]]]:
    """Combine ranked results from dense and sparse retrievers using Reciprocal Rank Fusion.

    Returns:
        List of tuples: (DocumentChunk, fused_rrf_score, rank_metadata)
    """
    scores: Dict[str, float] = {}
    chunk_map: Dict[str, DocumentChunk] = {}
    rank_metadata: Dict[str, Dict[str, Any]] = {}

    # 1. Process dense ranked results
    for rank_idx, (chunk, raw_score) in enumerate(dense_results):
        rank = rank_idx + 1
        cid = chunk.chunk_id
        chunk_map[cid] = chunk
        rrf_val = dense_weight * (1.0 / (k + rank))
        scores[cid] = scores.get(cid, 0.0) + rrf_val

        if cid not in rank_metadata:
            rank_metadata[cid] = {"dense_rank": rank, "dense_raw": raw_score, "sparse_rank": None, "sparse_raw": None}
        else:
            rank_metadata[cid]["dense_rank"] = rank
            rank_metadata[cid]["dense_raw"] = raw_score

    # 2. Process sparse ranked results
    for rank_idx, (chunk, raw_score) in enumerate(sparse_results):
        rank = rank_idx + 1
        cid = chunk.chunk_id
        chunk_map[cid] = chunk
        rrf_val = sparse_weight * (1.0 / (k + rank))
        scores[cid] = scores.get(cid, 0.0) + rrf_val

        if cid not in rank_metadata:
            rank_metadata[cid] = {"dense_rank": None, "dense_raw": None, "sparse_rank": rank, "sparse_raw": raw_score}
        else:
            rank_metadata[cid]["sparse_rank"] = rank
            rank_metadata[cid]["sparse_raw"] = raw_score

    # 3. Sort by fused RRF score descending
    sorted_items = sorted(scores.items(), key=lambda item: item[1], reverse=True)

    # 4. Construct final results
    final_results = []
    for cid, fused_score in sorted_items[:top_n]:
        final_results.append((chunk_map[cid], fused_score, rank_metadata[cid]))

    return final_results
