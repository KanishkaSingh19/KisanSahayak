"""GeminiEmbedder with a fake client: batching, task types, and same-size fallback vectors."""

import numpy as np
import pytest

from app.rag.embeddings import GeminiEmbedder


class FakeModels:
    def __init__(self, fail=False):
        self.fail = fail
        self.calls = []

    def embed_content(self, model, contents, config):
        self.calls.append((len(contents), config.task_type))
        if self.fail:
            raise RuntimeError("429 RESOURCE_EXHAUSTED")
        values = [[float(i + 1)] * config.output_dimensionality for i in range(len(contents))]
        return type("Res", (), {"embeddings": [type("E", (), {"values": v})() for v in values]})()


def make(fail=False):
    emb = GeminiEmbedder(api_key="test-key")
    emb.client = type("C", (), {"models": FakeModels(fail)})()
    return emb


def test_documents_are_batched_and_normalized():
    emb = make()
    vectors = emb.embed_documents([f"doc {i}" for i in range(120)])
    assert vectors.shape == (120, 768)
    assert np.allclose(np.linalg.norm(vectors, axis=1), 1.0)
    assert emb.client.models.calls == [(50, "RETRIEVAL_DOCUMENT"), (50, "RETRIEVAL_DOCUMENT"), (20, "RETRIEVAL_DOCUMENT")]


def test_query_uses_query_task_type():
    emb = make()
    assert emb.embed_text("aphids in mustard").shape == (768,)
    assert emb.client.models.calls == [(1, "RETRIEVAL_QUERY")]


@pytest.mark.parametrize("method,arg", [("embed_text", "aphids"), ("embed_documents", ["a", "b"])])
def test_failure_falls_back_to_same_dimension(method, arg):
    result = getattr(make(fail=True), method)(arg)
    assert result.shape[-1] == 768  # never mixes 256- and 768-long vectors
