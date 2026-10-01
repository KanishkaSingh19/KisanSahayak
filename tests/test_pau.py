"""Questions our advisories don't cover, answered from PAU's Package of Practices chapters.

The real chapters are not in the repository (copyrighted), so these tests use a small fake chapter.
"""

import pytest

from app.agent.pipeline import KisanPipeline
from app.agent.router import IntentRouter, topic_search_terms
from app.agent.state import ConversationTurn
from app.agent.synthesizer import DeterministicGroundedSynthesizer
from app.config import settings
from app.rag import pau_kb
from app.rag.chunker import AgriculturalChunker
from app.rag.embeddings import LocalDenseEmbedder
from app.rag.hybrid_retriever import HybridRetriever

FAKE_WHEAT = {
    "source_organization": "Punjab Agricultural University (PAU), Ludhiana",
    "document_title": "PAU Package of Practices for Crops of Punjab, Rabi 2025-26",
    "crop": "Wheat",
    "season": "Rabi",
    "kind": "pau_package_of_practices",
    "sections": [
        {"section_title": "Wheat - Weed Control - i. Control of Phalaris minor (Gulli danda)",
         "pau_text": "Phalaris minor (gulli danda) is the most serious weed of wheat. Spray a recommended herbicide "
                     "before the first irrigation, using a flat fan nozzle.", "pages": "12-14"},
        {"section_title": "Wheat - Harvesting and Threshing",
         "pau_text": "Harvest and thresh wheat as soon as fully ripe, to avoid grain shattering.", "pages": "17"},
    ],
}
FAKE_PADDY = {**FAKE_WHEAT, "crop": "Paddy (Rice)", "season": "Kharif", "document_title": "PAU Package of Practices, Kharif 2026",
              "sections": [{"section_title": "Paddy (Rice) - Weed Control",
                            "pau_text": "Control weeds in paddy with butachlor before transplanting weeds emerge.",
                            "pages": "7"}]}


def _chunks():
    chunker = AgriculturalChunker(settings.CHUNK_SIZE, settings.CHUNK_OVERLAP)
    return (chunker.load_and_chunk_directory(settings.RAW_DATA_DIR)
            + chunker.chunk_pau_document(FAKE_WHEAT, "pau_rabi_wheat")
            + chunker.chunk_pau_document(FAKE_PADDY, "pau_kharif_paddy"))


@pytest.fixture(scope="module")
def retriever():
    r = HybridRetriever(embeddings=LocalDenseEmbedder(dimension=128))
    r.build_indices(_chunks())
    return r


@pytest.fixture(scope="module")
def pipeline(retriever):
    return KisanPipeline(retriever=retriever, synthesizer=DeterministicGroundedSynthesizer())


def test_pau_sections_are_chunked_with_their_pages():
    chunks = AgriculturalChunker(1000, 150).chunk_pau_document(FAKE_WHEAT, "pau_rabi_wheat")
    assert [c.metadata["kind"] for c in chunks] == ["pau", "pau"]
    assert chunks[0].metadata["reference"] == "PAU Package of Practices for Crops of Punjab, Rabi 2025-26, pages 12-14"
    assert chunks[1].metadata["reference"].endswith("page 17")
    assert "PAU recommendation: Phalaris minor" in chunks[0].text


def test_search_can_be_limited_to_pau_and_one_crop(retriever):
    results = retriever.retrieve("weed control", kind="pau", crop="Paddy")
    assert results and {r.kind for r in results} == {"pau"}
    assert all(r.crop.startswith("Paddy") for r in results)
    assert all(r.kind == "advisory" for r in retriever.retrieve("weed control", kind="advisory"))


def test_topics_are_searched_in_english():
    assert "Phalaris minor" in topic_search_terms("गेहूं में गुल्ली डंडा का इलाज")
    assert "weed control" in topic_search_terms("ਕਣਕ ਵਿੱਚ ਨਦੀਨਾਂ ਦੀ ਰੋਕਥਾਮ")
    assert "zinc" in topic_search_terms("धान में जिंक की कमी")


def test_router_sends_uncovered_topics_of_covered_crops_to_pau():
    with_pau, without = IntentRouter(pau_available=True), IntentRouter()
    weeds = with_pau.classify("How to control weeds in wheat?")
    assert weeds.intent == "crop_question" and weeds.use_pau and weeds.detected_crop == "Wheat"
    assert without.classify("How to control weeds in wheat?").intent == "topic_not_covered"
    # A topic our own advisories cover still uses them
    assert not with_pau.classify("How do I control yellow rust in wheat?").use_pau
    # No crop named: still referred (PAU's chapters are per crop)
    assert with_pau.classify("How do I control weeds?").intent == "topic_not_covered"


def test_follow_ups_stay_on_pau():
    router = IntentRouter(pau_available=True)
    wheat = ConversationTurn(query="Yellow rust in wheat?", answer="...", intent="crop_question", crop="Wheat",
                             topic="Yellow Rust")
    weeds = router.classify_with_context("And weeds?", [wheat])
    assert weeds.use_pau and weeds.detected_crop == "Wheat"
    pau_turn = ConversationTurn(query="Weeds in wheat?", answer="...", intent="crop_question", crop="Wheat",
                                topic="weeds weed control", used_pau=True)
    assert router.classify_with_context("What is the dose?", [pau_turn]).use_pau


def test_pipeline_answers_from_pau_with_the_page(pipeline):
    res = pipeline.process_query("gehun mein gulli danda ka ilaj", language="en", generate_audio=False)
    assert res.processing_metadata["knowledge"] == "pau"
    assert "Phalaris minor" in res.answer and "pages 12-14" in res.answer
    assert any("pages 12-14" in c for c in res.citations)
    # The farmer's language for the note around PAU's (English) text
    hindi = pipeline.process_query("गेहूं में गुल्ली डंडा का इलाज", language="hi", generate_audio=False)
    assert hindi.processing_metadata["knowledge"] == "pau" and "अंग्रेज़ी" in hindi.answer


def test_covered_topics_still_use_our_advisories(pipeline):
    res = pipeline.process_query("How do I control yellow rust in wheat?", language="en", generate_audio=False)
    assert res.processing_metadata["knowledge"] == "advisory"
    assert res.retrieved_chunks[0].section.startswith("Yellow Rust")


def test_a_missing_pau_build_never_breaks_the_app(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "USE_PAU_KB", True)
    monkeypatch.setattr(settings, "PAU_AUTO_BUILD", True)

    def offline(kb_dir):
        raise ConnectionError("pau.edu unreachable")

    monkeypatch.setattr(pau_kb, "build_pau_kb", offline)
    assert pau_kb.ensure_pau_kb(tmp_path / "kb") is False


def test_on_gemini_pau_is_left_out_without_cached_vectors(tmp_path, monkeypatch):
    """Embedding ~400 PAU chunks on a cold start took 13 minutes on the free quota: start without them."""
    import json

    from app.rag import ingest

    kb = tmp_path / "kb"
    kb.mkdir()
    big = {**FAKE_WHEAT, "sections": [{**FAKE_WHEAT["sections"][0], "section_title": f"Wheat - Topic {i}"}
                                      for i in range(ingest.PAU_MAX_UNCACHED + 5)]}
    (kb / "pau_rabi_wheat.json").write_text(json.dumps(big), encoding="utf-8")
    monkeypatch.setattr(settings, "USE_PAU_KB", True)
    monkeypatch.setattr(settings, "PAU_KB_DIR", kb)
    monkeypatch.setattr(ingest, "pau_kb_files", lambda: [kb / "pau_rabi_wheat.json"])
    monkeypatch.setattr(ingest, "gemini_cached_keys", lambda: set())
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "gemini")
    assert not any(c.metadata.get("kind") == "pau" for c in ingest.load_knowledge_chunks())
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "minilm")  # local embeddings: no quota to run out
    assert any(c.metadata.get("kind") == "pau" for c in ingest.load_knowledge_chunks())
