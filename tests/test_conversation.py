import pytest

from app.agent.router import IntentRouter
from app.agent.state import ConversationTurn
from app.agent.synthesizer import format_history
from app.tools.location import Place

APHID_TURN = ConversationTurn(
    query="How to control aphids in mustard?", answer="Spray Thiamethoxam 25% WG @ 50-80 g per acre...",
    intent="crop_question", crop="Mustard", topic="Aphid",
)
WEATHER_TURN = ConversationTurn(
    query="aaj delhi mein kaisa mausam hai", answer="Delhi: 23.4°C ...", intent="weather", district="Delhi",
)


@pytest.fixture
def router():
    return IntentRouter()


def test_follow_up_keeps_crop_and_pest(router):
    res = router.classify_with_context("What is the dose?", APHID_TURN)
    assert res.detected_crop == "Mustard" and res.detected_topic == "Aphid"


def test_follow_up_new_crop_keeps_pest(router):
    res = router.classify_with_context("What about wheat?", APHID_TURN)
    assert res.detected_crop == "Wheat" and res.detected_topic == "Aphid"
    assert res.intent == "crop_question"


def test_new_topic_is_not_overridden(router):
    res = router.classify_with_context("How to control pink bollworm in cotton?", APHID_TURN)
    assert res.detected_crop == "Cotton" and res.detected_topic == "Pink Bollworm"


@pytest.mark.parametrize("query", ["aur Sangrur mein?", "What about Sangrur?", "ਅਤੇ ਸੰਗਰੂਰ ਵਿੱਚ?"])
def test_weather_follow_up_with_new_place(router, query):
    res = router.classify_with_context(query, WEATHER_TURN)
    assert res.intent == "weather" and res.detected_district == "Sangrur"


@pytest.mark.parametrize("query", ["kya spray kar sakta hoon?", "Should I irrigate?", "Will it rain?"])
def test_weather_follow_up_keeps_place(router, query):
    res = router.classify_with_context(query, WEATHER_TURN)
    assert res.intent == "weather" and res.detected_district == "Delhi"


def test_no_history_behaves_like_before(router):
    assert router.classify_with_context("What is the dose?", None).detected_crop is None


def test_history_prompt_is_recent_and_short():
    turns = [APHID_TURN.model_copy(update={"query": f"q{i}", "answer": "x" * 2000}) for i in range(5)]
    text = format_history(turns)
    assert "q4" in text and "q2" in text and "q1" not in text  # only the last 3 turns
    assert len(text) < 3 * 600 + 200  # long answers are shortened


@pytest.fixture(scope="module")
def pipeline():
    from app.agent.pipeline import KisanPipeline
    from app.agent.synthesizer import DeterministicGroundedSynthesizer

    return KisanPipeline(synthesizer=DeterministicGroundedSynthesizer())


def test_pipeline_follow_up_retrieves_previous_topic(pipeline):
    res = pipeline.process_query("What is the dose?", language="en", generate_audio=False, history=[APHID_TURN])
    assert res.retrieved_chunks[0].crop == "Mustard"
    assert "Aphid" in res.retrieved_chunks[0].section


def test_pipeline_weather_follow_up(pipeline, monkeypatch):
    places = {"Delhi": Place(name="Delhi", latitude=28.65, longitude=77.23),
              "Sangrur": Place(name="Sangrur", latitude=30.25, longitude=75.84)}
    monkeypatch.setattr(pipeline.weather_tool, "resolve_place", lambda name: places.get(name))
    first = pipeline.process_query("aaj delhi mein kaisa mausam hai", language="en", generate_audio=False)
    second = pipeline.process_query(
        "aur Sangrur mein?", language="en", generate_audio=False, history=[ConversationTurn.from_answer(first)]
    )
    assert second.intent == "weather" and second.processing_metadata["district"] == "Sangrur"


def test_follow_up_skips_back_over_a_weather_question(router):
    history = [APHID_TURN, WEATHER_TURN]
    res = router.classify_with_context("What was the dose again?", history)
    assert res.detected_crop == "Mustard" and res.detected_topic == "Aphid"
    assert res.follow_up_of == APHID_TURN.query


def test_weather_question_reuses_earlier_place_after_crop_question(router):
    res = router.classify_with_context("Will it rain today?", [WEATHER_TURN, APHID_TURN])
    assert res.intent == "weather" and res.detected_district == "Delhi"


def test_turn_remembers_the_advisory_used_when_pest_was_not_named():
    from app.agent.state import GroundedAnswer

    answer = GroundedAnswer(
        query="My wheat leaves have yellow powdery stripes", intent="general_agriculture", answer="Yellow Rust...",
        citations=[], retrieved_chunks=[], is_grounded=True,
        processing_metadata={"detected_crop": "Wheat", "detected_topic": "Agronomy/General",
                             "top_section": "Yellow Rust (Pila Rataua / Peeli Kungi) Identification and Management"},
    )
    assert ConversationTurn.from_answer(answer).topic.startswith("Yellow Rust")


def test_pipeline_three_turn_conversation_keeps_context(pipeline, monkeypatch):
    monkeypatch.setattr(pipeline.weather_tool, "resolve_place", lambda name: Place(name=name, latitude=30.9, longitude=75.85))
    history = []
    for question in ["How to control aphids in mustard?", "aaj Ludhiana mein mausam kaisa hai?", "What was the dose again?"]:
        res = pipeline.process_query(question, language="en", generate_audio=False, history=history)
        history.append(ConversationTurn.from_answer(res))
    assert res.retrieved_chunks[0].crop == "Mustard" and "Aphid" in res.retrieved_chunks[0].section


def test_pipeline_symptom_then_pronoun_follow_up(pipeline):
    first = pipeline.process_query("My wheat leaves have yellow powdery stripes", language="en", generate_audio=False)
    second = pipeline.process_query(
        "Is it dangerous?", language="en", generate_audio=False, history=[ConversationTurn.from_answer(first)]
    )
    assert "Yellow Rust" in second.retrieved_chunks[0].section
