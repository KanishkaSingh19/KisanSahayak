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
    delhi = Place(name="Delhi", latitude=28.65, longitude=77.23, state="Delhi")
    monkeypatch.setattr(weather_tool, "geocode", lambda name, timeout: delhi if name == "Delhi" else None)
    tool = AgWeatherTool()
    assert tool.resolve_place("Delhi") == delhi
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
    assert "Couldn't find" in res.answer and "Ludhiana" in res.answer
