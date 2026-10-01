import pytest

from app.tools import location, weather_tool
from app.tools.location import Place, detect_place, find_known_place, place_candidates
from app.tools.weather_tool import AgWeatherTool


@pytest.mark.parametrize(
    "query,expected",
    [
        ("aaj delhi mein kaisa mausam hai", "Delhi"),
        ("दिल्ली में आज मौसम कैसा है?", "Delhi"),
        ("ਲੁਧਿਆਣਾ ਵਿੱਚ ਅੱਜ ਮੌਸਮ ਕਿਹੋ ਜਿਹਾ ਹੈ?", "Ludhiana"),
        ("Weather in Sangrur today?", "Sangrur"),
    ],
)
def test_known_places_in_any_script(query, expected):
    assert find_known_place(query) == expected


def test_unknown_place_candidates_skip_non_places():
    assert place_candidates("what is the weather in nashik today") == ["nashik"]
    assert place_candidates("nashik mein mausam kaisa hai") == ["nashik"]
    assert place_candidates("aaj khet mein barish hogi kya") == []
    assert detect_place("kal mausam kaisa rahega?") is None


def test_resolve_place_uses_builtin_coordinates_without_network(monkeypatch):
    monkeypatch.setattr(weather_tool, "geocode", lambda *a, **k: pytest.fail("should not geocode"))
    place = AgWeatherTool().resolve_place("Karnal")
    assert place.name == "Karnal" and round(place.latitude) == 30


def test_resolve_place_geocodes_other_places(monkeypatch):
    nashik = Place(name="Nashik", latitude=20.0, longitude=73.79, state="Maharashtra")
    monkeypatch.setattr(weather_tool, "geocode", lambda name, timeout: nashik if name == "Nashik" else None)
    tool = AgWeatherTool()
    assert tool.resolve_place("Nashik") == nashik
    assert tool.resolve_place("Atlantis") is None


def test_geocode_requires_exact_indian_match(monkeypatch):
    class Resp:
        def __init__(self, results):
            self._results = results

        def raise_for_status(self):
            pass

        def json(self):
            return {"results": self._results}

    location.geocode.cache_clear()
    monkeypatch.setattr(
        location.requests,
        "get",
        lambda *a, **k: Resp([{"name": "Mausampur", "country_code": "IN", "latitude": 27.8, "longitude": 78.6}]),
    )
    assert location.geocode("mausam") is None  # partial match must not count
    location.geocode.cache_clear()


@pytest.fixture(scope="module")
def pipeline():
    from app.agent.pipeline import KisanPipeline
    return KisanPipeline()


def test_pipeline_weather_uses_the_asked_place(pipeline, monkeypatch):
    delhi = Place(name="Delhi", latitude=28.65, longitude=77.23)
    monkeypatch.setattr(pipeline.weather_tool, "resolve_place", lambda name: delhi if name == "Delhi" else None)
    res = pipeline.process_query("aaj delhi mein kaisa mausam hai", language="en", generate_audio=False)
    assert res.intent == "weather"
    assert res.processing_metadata["district"] == "Delhi"
    assert res.processing_metadata["location_found"] is True
    assert "No place was recognised" not in res.answer and "Couldn't find" not in res.answer


@pytest.mark.parametrize(
    "query,expected",
    [
        ("aaj delhi mein kaisa mausam hai", set()),
        ("What's the weather in Ludhiana today, can I spray pesticide?", {"spray"}),
        ("क्या आज छिड़काव कर सकते हैं?", {"spray"}),
        ("ਕੀ ਅੱਜ ਸਿੰਚਾਈ ਕਰਾਂ?", {"irrigation"}),
        ("mausam dekh kar sinchai aur spray kab karein?", {"spray", "irrigation"}),
    ],
)
def test_weather_topics(query, expected):
    from app.agent.router import weather_topics

    assert weather_topics(query) == expected


def test_pipeline_weather_answers_only_what_was_asked(pipeline, monkeypatch):
    delhi = Place(name="Delhi", latitude=28.65, longitude=77.23)
    monkeypatch.setattr(pipeline.weather_tool, "resolve_place", lambda name: delhi)

    plain = pipeline.process_query("aaj delhi mein kaisa mausam hai", language="en", generate_audio=False)
    assert "Spray Advisory" not in plain.answer and "Irrigation Advice" not in plain.answer
    assert "chance of rain" in plain.answer

    spray = pipeline.process_query("Can I spray in Delhi today?", language="en", generate_audio=False)
    assert "Spray Advisory" in spray.answer and "Irrigation Advice" not in spray.answer


def test_pipeline_weather_says_when_place_not_found(pipeline, monkeypatch):
    monkeypatch.setattr(pipeline.weather_tool, "resolve_place", lambda name: None)
    res = pipeline.process_query("weather in atlantis today", language="en", generate_audio=False)
    assert res.processing_metadata["location_found"] is False
    assert "couldn't find" in res.answer.lower() and "Ludhiana" not in res.answer  # no default place
    assert res.weather_report is None


def test_weather_without_a_place_asks(pipeline):
    res = pipeline.process_query("will it rain today?", language="en", generate_audio=False)
    assert res.intent == "weather" and res.processing_metadata["needs_place"] is True
    assert "Which place" in res.answer and res.weather_report is None and "Ludhiana" not in res.answer


def test_replying_with_a_place_answers_the_original_question(pipeline, monkeypatch):
    from app.agent.state import ConversationTurn

    monkeypatch.setattr(pipeline.weather_tool, "resolve_place", lambda name: Place(name=name, latitude=30.2, longitude=75.8))
    asked = pipeline.process_query("Can I spray pesticide today?", language="en", generate_audio=False)
    assert asked.processing_metadata.get("needs_place")
    reply = pipeline.process_query("Sangrur", language="en", generate_audio=False, history=[ConversationTurn.from_answer(asked)])
    assert reply.intent == "weather" and reply.processing_metadata["district"] == "Sangrur"
    assert reply.weather_report and "Spray" in reply.answer  # the spray question is still answered


@pytest.mark.parametrize(
    "text,place",
    [
        ("मानसा में आज मौसम कैसा रहेगा?", "Mansa"),
        ("ਗੁਰਦਾਸਪੁਰ ਵਿੱਚ ਅੱਜ ਮੌਸਮ", "Gurdaspur"),
        ("ਤਰਨ ਤਾਰਨ ਵਿੱਚ ਮੌਸਮ", "Tarn Taran"),
        ("फतेहगढ़ साहिब में मौसम", "Fatehgarh Sahib"),
        ("weather forecast for Hoshiarpur today", "Hoshiarpur"),
        ("weather in Bhatinda", "Bathinda"),
    ],
)
def test_punjab_districts_in_any_script(text, place):
    assert detect_place(text) == place


def test_all_punjab_districts_have_built_in_coordinates():
    """The geocoding service misses several Punjab districts and puts Mansa in Uttar Pradesh."""
    from app.tools.weather_tool import AgWeatherTool

    mansa = AgWeatherTool().resolve_place("Mansa")
    assert 29.5 < mansa.latitude < 30.5 and 75 < mansa.longitude < 76  # Mansa, Punjab
    for name in ["Barnala", "Faridkot", "Fatehgarh Sahib", "Hoshiarpur", "Muktsar", "Tarn Taran", "Nawanshahr"]:
        assert AgWeatherTool().resolve_place(name) is not None, name


@pytest.mark.parametrize("reply,place", [("NOIDA", "Noida"), ("gurgaon", "Gurugram"), ("ਸੰਗਰੂਰ", "Sangrur"), ("Nashik", "Nashik")])
def test_reply_to_which_place_is_the_place(pipeline, monkeypatch, reply, place):
    from app.agent.state import ConversationTurn

    real_resolve = pipeline.weather_tool.resolve_place
    monkeypatch.setattr(pipeline.weather_tool, "resolve_place",
                        lambda name: real_resolve(name) if name != "Nashik" else Place(name="Nashik", latitude=20.0, longitude=73.8))
    asked = pipeline.process_query("WILL IT RAIN TODAY?", language="en", generate_audio=False)
    reply_res = pipeline.process_query(reply, language="en", generate_audio=False, history=[ConversationTurn.from_answer(asked)])
    assert reply_res.intent == "weather" and reply_res.processing_metadata["district"] == place


def test_a_new_question_is_not_taken_as_a_place():
    from app.agent.router import IntentRouter
    from app.agent.state import ConversationTurn

    asked = ConversationTurn(query="will it rain today?", answer="Which place?", intent="weather", awaiting_place=True)
    router = IntentRouter()
    assert router.classify_with_context("How to control aphids in mustard?", [asked]).intent == "crop_question"
    assert router.classify_with_context("hello", [asked]).intent == "greeting"


def test_delhi_ncr_towns_are_built_in():
    for name in ["Noida", "Greater Noida", "Ghaziabad", "Gurugram", "Faridabad", "Sonipat", "Panipat", "Meerut"]:
        assert AgWeatherTool().resolve_place(name) is not None, name
    assert detect_place("नोएडा में मौसम") == "Noida" and detect_place("weather in gurgaon") == "Gurugram"


@pytest.mark.parametrize("question,state", [("weather in Punjab", "Punjab"), ("ਪੰਜਾਬ ਵਿੱਚ ਮੌਸਮ", "Punjab"), ("weather in UP", "Uttar Pradesh")])
def test_weather_for_a_whole_state_asks_for_a_district(pipeline, question, state):
    res = pipeline.process_query(question, language="en", generate_audio=False)
    assert res.weather_report is None and state in res.answer and "district" in res.answer
    assert res.processing_metadata["needs_place"] is True  # the reply ("Ludhiana") is taken as the place
