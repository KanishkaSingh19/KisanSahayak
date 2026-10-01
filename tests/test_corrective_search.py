"""Corrective search: when the meaning-based and keyword searches disagree on the top advisory, search
again with the crop and the topic's English words, and send still-uncertain answers to expert review."""

from app.agent.pipeline import is_confident
from app.agent.state import GroundedAnswer
from app.rag.hybrid_retriever import RetrievalResult
from app.review import review_reasons


def _result(dense, sparse, extra=False):
    rank = {"dense_rank": dense, "sparse_rank": sparse, **({"same_section_as_above": True} if extra else {})}
    return RetrievalResult(chunk_id="c", text="t", score=0.03, citation="c", source_agency="PAU", crop="Wheat",
                           section="s", rank_details=rank)


def test_confident_only_when_both_searches_rank_it_first():
    assert is_confident([_result(1, 1)])
    assert not is_confident([_result(1, 3)]) and not is_confident([_result(2, 1)])
    assert not is_confident([])
    # A retry made of English topic words is checked by keyword search alone
    assert is_confident([_result(2, 1)], keyword_only=True) and not is_confident([_result(1, 2)], keyword_only=True)


def test_punjabi_watering_question_is_corrected():
    """"ਕਣਕ ਨੂੰ ਪਾਣੀ ਕਦੋਂ ਅਤੇ ਕਿੰਨੀ ਵਾਰ ਲਾਈਏ?" (when to water wheat) used to get the yellow rust advisory."""
    from app.agent.pipeline import KisanPipeline
    from app.agent.synthesizer import DeterministicGroundedSynthesizer

    res = KisanPipeline(synthesizer=DeterministicGroundedSynthesizer()).process_query(
        "ਕਣਕ ਨੂੰ ਪਾਣੀ ਕਦੋਂ ਅਤੇ ਕਿੰਨੀ ਵਾਰ ਲਾਈਏ?", language="pa", generate_audio=False)
    assert res.processing_metadata["retrieval"] in ("confident", "corrected")
    assert res.retrieved_chunks[0].section.startswith("Wheat Sowing Time")


def test_uncertain_answer_goes_to_expert_review():
    answer = GroundedAnswer(query="q", intent="crop_question", answer="a", citations=[], retrieved_chunks=[],
                            is_grounded=True, processing_metadata={"retrieval": "low_confidence"})
    assert "low_retrieval_confidence" in review_reasons(answer)
