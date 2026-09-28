import pytest


@pytest.mark.parametrize(
    "query,intent",
    [
        ("Can I spray in Delhi today?", "weather"),
        ("kya aaj spray kar sakte hain?", "weather"),
        ("ਕੀ ਅੱਜ ਛਿੜਕਾਅ ਕਰ ਸਕਦੇ ਹਾਂ?", "weather"),
        ("Which spray for aphids in mustard today?", "crop_question"),  # names a pest: crop advice
    ],
)
def test_spray_timing_is_a_weather_question(query, intent):
    from app.agent.router import IntentRouter

    assert IntentRouter().classify(query).intent == intent
from app.agent.router import IntentRouter


def test_intent_router_greetings():
    router = IntentRouter()
    r1 = router.classify("Namaste")
    assert r1.intent == "greeting"

    r2 = router.classify("Sat sri akal ji")
    assert r2.intent == "greeting"


def test_intent_router_out_of_scope():
    router = IntentRouter()
    r = router.classify("Who won the cricket match yesterday?")
    assert r.intent == "out_of_scope"


def test_intent_router_crop_question():
    router = IntentRouter()
    r = router.classify("gehun me peeli kungi ka ilaj kya hai?")
    assert r.intent == "crop_question"
    assert r.detected_crop == "Wheat"
    assert r.detected_topic == "Yellow Rust"


def test_intent_router_mustard_aphid():
    router = IntentRouter()
    r = router.classify("sarson me mahu keeda kaise rokein?")
    assert r.intent == "crop_question"
    assert r.detected_crop == "Mustard"
    assert r.detected_topic == "Aphid"


def test_intent_router_safety_query():
    router = IntentRouter()
    r = router.classify("Is monocrotophos banned in India?")
    assert r.intent == "safety_query"


def test_intent_router_general_agri():
    router = IntentRouter()
    r = router.classify("wheat sowing time and first irrigation")
    assert r.intent == "general_agriculture"
    assert r.detected_crop == "Wheat"
