import pytest

from app.agent.router import IntentRouter


def test_punjabi_bindi_and_tippi_spellings_match():
    from app.agent.router import IntentRouter

    # Whisper wrote ਕੁਂਗੀ (bindi) for ਕੁੰਗੀ (tippi); both must mean yellow rust
    res = IntentRouter().classify("ਕਣਕ ਵੀਚ ਪੀਲੀ ਕੁਂਗੀ ਦ ਇਲਾਚ ਦ ਸੋ")
    assert res.detected_crop == "Wheat" and res.detected_topic == "Yellow Rust"


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


@pytest.mark.parametrize(
    "query",
    ["How do I control red rot in sugarcane?", "ganne mein keeda lag gaya", "आलू में झुलसा रोग का इलाज", "ਟਮਾਟਰ ਦੇ ਪੱਤੇ ਸੁੱਕ ਰਹੇ ਹਨ"],
)
def test_uncovered_crop_is_not_answered_from_another_advisory(query):
    assert IntentRouter().classify(query).intent == "crop_not_covered"


def test_banned_pesticide_on_uncovered_crop_still_warns():
    assert IntentRouter().classify("Can I use Monocrotophos on brinjal?").intent == "safety_query"


def test_dhaan_spelling_is_paddy():
    assert IntentRouter().classify("Dhaan ke tane par dhabbe hain, kya karein?").detected_crop == "Paddy"


def test_ipl_is_out_of_scope():
    assert IntentRouter().classify("Who won the IPL this year?").intent == "out_of_scope"


@pytest.mark.parametrize("query", ["क्या मैं बैंगन पर मोनोक्रोटोफॉस छिड़क सकता हूँ?", "ਕੀ ਮੈਂ ਟਮਾਟਰ ਤੇ ਐਂਡੋਸਲਫ਼ਾਨ ਛਿੜਕ ਸਕਦਾ ਹਾਂ?"])
def test_banned_pesticide_in_indic_script_is_a_safety_question(query):
    assert IntentRouter().classify(query).intent == "safety_query"


@pytest.mark.parametrize("query", ["Dhaan ke tane par saanp ki khaal jaise dhabbe hain", "धान में तना झुलसा रोग", "How to manage sheath blight in paddy?"])
def test_sheath_blight_names(query):
    assert IntentRouter().classify(query).detected_topic == "Sheath Blight"


def test_leaf_blight_is_still_blb():
    assert IntentRouter().classify("dhan mein peela jhulsa rog ka ilaj").detected_topic == "Blb"


@pytest.mark.parametrize(
    "query",
    [
        "Information regarding deficiency OF Zinc in Paddy?",
        "gehun mein kharpatwar kaise khatam karein",
        "Information regarding fertilizer dose in rice?",
        "INFORMATION REGARDING SOWING TIME OF COTTON?",
        "Information regarding the varieties of Paddy with their yield?",
        "ਕਣਕ ਵਿੱਚ ਸੁੰਡੀ ਦੀ ਰੋਕਥਾਮ ਕਿਵੇਂ ਕਰੀਏ?",
    ],
)
def test_uncovered_topics_are_referred_not_answered_with_another_advisory(query):
    assert IntentRouter().classify(query).intent == "topic_not_covered"


@pytest.mark.parametrize(
    "query",
    [
        "Information regarding total fertilizer application in Wheat crop?",
        "Information regarding irrigation in wheat?",
        "When should I sow wheat and how much seed per acre?",
        "How much fertilizer does mustard need?",
        "How to control aphids in mustard?",
        "Kapas mein gulabi sundhi ki roktham kaise karein?",
        "Paddy leaves are turning yellow and drying from the tips",
    ],
)
def test_covered_questions_are_still_answered(query):
    assert IntentRouter().classify(query).intent in ("crop_question", "general_agriculture")


def test_follow_up_about_this_disease_keeps_the_topic():
    from app.agent.state import ConversationTurn

    earlier = ConversationTurn(query="Yellow powder stripes on wheat leaves", answer="...", intent="crop_question",
                               crop="Wheat", topic="Yellow Rust")
    res = IntentRouter().classify_with_context("Which varieties resist this disease?", [earlier])
    assert res.intent != "topic_not_covered" and res.detected_topic == "Yellow Rust"


@pytest.mark.parametrize("query", ["Kapas mein tela (aphid) ki roktham kaise karein?", "information regarding control of parawilt in cotton?",
                                   "Information regarding sowing time of toria?", "बासमती में खाद की सिफारिश की गई मात्रा कितनी है?"])
def test_more_uncovered_topics(query):
    assert IntentRouter().classify(query).intent == "topic_not_covered"
