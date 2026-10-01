import pytest
from app.agent.pipeline import KisanPipeline


@pytest.fixture(scope="module")
def pipeline():
    return KisanPipeline()


def test_pipeline_greeting(pipeline):
    res = pipeline.process_query("Namaste Kisan Sahayak")
    assert res.intent == "greeting"
    assert "किसान सहायक" in res.answer
    assert res.is_grounded is True


def test_pipeline_out_of_scope(pipeline):
    res = pipeline.process_query("Tell me about the latest Bollywood cinema movie")
    assert res.intent == "out_of_scope"
    assert "कृषि" in res.answer


def test_pipeline_empty_query(pipeline):
    res = pipeline.process_query("   ")
    assert res.intent == "empty"
    assert "प्रश्न पूछें" in res.answer


def test_pipeline_wheat_yellow_rust(pipeline):
    res = pipeline.process_query("How to identify and control Yellow Rust in wheat?")
    assert res.intent in ["crop_question", "general_agriculture"]
    assert len(res.retrieved_chunks) > 0
    assert any("Wheat" in c.crop for c in res.retrieved_chunks)
    assert len(res.citations) > 0
    answer = res.answer.lower()  # PAU's names are written in lower case ("Tilt 25 EC (propiconazole)")
    assert "propiconazole" in answer or "tebuconazole" in answer or "rust" in answer
    assert res.is_grounded is True


def test_pipeline_mustard_aphid(pipeline):
    res = pipeline.process_query("सरसों में माहू (aphids) का नियंत्रण कैसे करें?")
    assert res.intent in ["crop_question", "general_agriculture"]
    assert len(res.retrieved_chunks) > 0
    assert any("Mustard" in c.crop for c in res.retrieved_chunks)
    assert len(res.citations) > 0


def test_pipeline_banned_monocrotophos(pipeline):
    res = pipeline.process_query("क्या सब्जियों में मोनोक्रोटोफॉस (Monocrotophos) का छिड़काव सुरक्षित है?")
    assert res.intent == "safety_query"
    assert any("प्रतिबंधित" in d or "Monocrotophos" in d for d in res.safety_disclaimers)


def test_pipeline_weather_ludhiana(pipeline):
    res = pipeline.process_query("लुधियाना में आज बारिश और मौसम का क्या हाल है, क्या छिड़काव कर सकते हैं?")
    assert res.intent == "weather"
    assert "मौसम परामर्श" in res.answer
    assert "Ludhiana" in res.answer
    assert res.weather_report is not None
    assert "spray_recommendation" in res.weather_report


def test_pipeline_audio_input_fallback(pipeline):
    # Dummy audio bytes without Groq key should gracefully return helpful fallback
    res = pipeline.process_audio_query(b"RIFFdummydataWAVEfmt")
    assert res.intent in ["voice_stt_unavailable", "empty"]
    assert "STT" in res.answer or "टेक्स्ट" in res.answer or "प्रश्न" in res.answer


def test_stale_saved_index_is_rebuilt(tmp_path, monkeypatch):
    """An index saved with different chunks (old advisories or chunk settings) is not reused."""
    from app.agent.pipeline import KisanPipeline
    from app.config import settings
    from app.rag.chunker import DocumentChunk
    from app.rag.hybrid_retriever import HybridRetriever

    monkeypatch.setattr(settings, "INDEX_DIR", tmp_path)
    old = HybridRetriever()
    old.build_indices([DocumentChunk(chunk_id="old_s0_c0", text="Outdated advice", metadata={"crop": "Wheat"})])
    old.save_indices(tmp_path)

    pipeline = KisanPipeline(retriever=HybridRetriever())
    ids = {c.chunk_id for c in pipeline.retriever.dense_retriever.chunks}
    assert "old_s0_c0" not in ids and len(ids) > 1
