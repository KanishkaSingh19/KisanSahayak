"""KVK expert review queue: which answers are flagged, and the review round trip."""

import pytest

from app.agent.state import GroundedAnswer
from app.i18n import t
from app.review import ReviewQueue, review_reasons


def answer(intent="crop_question", disclaimers=(), meta=None, chunks=()):
    return GroundedAnswer(
        query="q", intent=intent, answer="a", citations=["PAU"], retrieved_chunks=list(chunks), is_grounded=True,
        safety_disclaimers=list(disclaimers), detected_language="en", processing_metadata=dict(meta or {}),
    )


@pytest.mark.parametrize(
    "result,reason",
    [
        (answer(disclaimers=[t("statutory_disclaimer", "hi")]), "pesticide"),
        (answer(intent="safety_query", disclaimers=[t("monocrotophos_warning", "pa")]), "banned_pesticide"),
        (answer(meta={"answer_source": "llm", "grounding_score": 0.2}), "low_grounding"),
        (answer(intent="image_diagnosis", meta={"vision": {"confidence": "medium", "problem": "Leaf rust"}}), "photo_uncertain"),
        (answer(intent="topic_not_covered"), "not_covered"),
        (answer(intent="crop_not_covered"), "not_covered"),
    ],
)
def test_flagged_answers(result, reason):
    assert reason in review_reasons(result)


@pytest.mark.parametrize(
    "result",
    [
        answer(intent="weather"),
        answer(intent="greeting"),
        answer(meta={"answer_source": "llm", "grounding_score": 0.9}),
        answer(meta={"answer_source": "template_offline", "grounding_score": 0.2}),  # offline text is the advisory itself
    ],
)
def test_answers_that_need_no_review(result):
    assert review_reasons(result) == []


def test_real_pesticide_answer_is_flagged():
    from app.agent.pipeline import KisanPipeline
    from app.agent.synthesizer import DeterministicGroundedSynthesizer

    res = KisanPipeline(synthesizer=DeterministicGroundedSynthesizer()).process_query(
        "How to control aphids in mustard?", language="en", generate_audio=False
    )
    assert "pesticide" in review_reasons(res)


def test_queue_round_trip(tmp_path):
    queue = ReviewQueue(tmp_path / "queue.jsonl")
    flagged = answer(intent="topic_not_covered")
    item_id = queue.submit(flagged)
    assert item_id and flagged.processing_metadata["kvk_review"] == item_id
    assert queue.submit(answer(intent="weather")) is None  # nothing to review
    assert queue.stats()["pending"] == 1

    assert queue.review(item_id, "needs_correction", "Spray 40 g Actara per acre", "KVK Ludhiana")
    reviewed = queue.items("reviewed")[0]
    assert reviewed["verdict"] == "needs_correction" and reviewed["correction"].startswith("Spray 40 g")
    assert queue.stats() == {"total": 1, "pending": 0, "reviewed": 1, "correct": 0, "needs_correction": 1, "unsafe": 0}
    with pytest.raises(ValueError):
        queue.review(item_id, "maybe")


def test_queue_stores_no_profile(tmp_path):
    queue = ReviewQueue(tmp_path / "queue.jsonl")
    result = answer(intent="topic_not_covered", meta={"district": "Sangrur"})
    queue.submit(result)
    stored = queue.items()[0]
    assert "district" not in stored and "profile" not in stored
