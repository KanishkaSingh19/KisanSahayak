"""GeminiEmbedder with a fake client: batching, task types, and same-size fallback vectors."""

import numpy as np
import pytest

from app.rag.embeddings import GeminiEmbedder


class FakeModels:
    def __init__(self, fail=False, rate_limited_calls=0):
        self.fail = fail
        self.rate_limited_calls = rate_limited_calls  # the first N calls hit the per-minute limit
        self.calls = []

    def embed_content(self, model, contents, config):
        self.calls.append((len(contents), config.task_type))
        if self.fail or len(self.calls) <= self.rate_limited_calls:
            raise RuntimeError("429 RESOURCE_EXHAUSTED")
        values = [[float(i + 1)] * config.output_dimensionality for i in range(len(contents))]
        return type("Res", (), {"embeddings": [type("E", (), {"values": v})() for v in values]})()


def make(fail=False, rate_limited_calls=0):
    emb = GeminiEmbedder(api_key="test-key")
    emb.client = type("C", (), {"models": FakeModels(fail, rate_limited_calls)})()
    emb.RATE_LIMIT_WAIT_SEC = 0
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


def test_rate_limit_is_waited_out_while_building_the_index():
    """A 429 from the per-minute limit is retried: a batch embedded locally instead would search badly."""
    emb = make(rate_limited_calls=2)
    vectors = emb.embed_documents(["a", "b"])
    assert vectors.shape == (2, 768) and emb.fallback_count == 0
    assert len(emb.client.models.calls) == 3


def test_cached_vectors_need_no_api_call(tmp_path):
    """The shipped cache is used first: a cold start must not re-embed hundreds of chunks."""
    emb = make()
    emb.embed_documents(["a", "b"])  # computed once...
    emb.save_cache(tmp_path / "cache.npz")
    fresh = make(fail=True)
    fresh.load_cache(tmp_path / "cache.npz")
    vectors = fresh.embed_documents(["a", "b"])  # ...then read back, with the API failing
    assert fresh.client.models.calls == [] and fresh.fallback_count == 0 and vectors.shape == (2, 768)


def test_used_up_quota_does_not_hold_up_the_start():
    """Once the quota is out, later batches go straight to the local embedder (no waiting per batch)."""
    emb = make(fail=True)
    emb.embed_documents([f"doc {i}" for i in range(120)])
    assert len(emb.client.models.calls) == emb.RATE_LIMIT_RETRIES + 1  # the first batch only
    assert emb.fallback_count == 120
