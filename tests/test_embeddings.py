import numpy as np
import pytest
from app.rag.embeddings import LocalDenseEmbedder


def test_local_dense_embedder_dimension():
    embedder = LocalDenseEmbedder(dimension=256)
    vec = embedder.embed_text("Yellow rust in wheat crop")
    assert isinstance(vec, np.ndarray)
    assert vec.shape == (256,)
    assert vec.dtype == np.float32


def test_local_dense_embedder_normalization():
    embedder = LocalDenseEmbedder(dimension=256)
    vec = embedder.embed_text("Mustard aphid spraying dosage")
    norm = np.linalg.norm(vec)
    assert pytest.approx(norm, rel=1e-4) == 1.0


def test_local_dense_embedder_similarity():
    embedder = LocalDenseEmbedder(dimension=256)
    v1 = embedder.embed_text("Yellow rust in wheat")
    v2 = embedder.embed_text("Peeli kungi in gehun wheat")
    v3 = embedder.embed_text("Deep space galaxy astrophysics")

    sim_related = np.dot(v1, v2)
    sim_unrelated = np.dot(v1, v3)

    assert sim_related > sim_unrelated
