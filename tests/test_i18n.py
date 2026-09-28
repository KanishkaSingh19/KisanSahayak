import pytest
from app.agent.guardrails import AgriculturalGuardrails
from app.agent.synthesizer import build_system_prompt
from app.i18n import LANGUAGES, SAMPLE_QUESTIONS, STRINGS, normalize_language, t
from app.tools.weather_tool import AgWeatherTool


def test_every_string_has_all_languages():
    for key, entry in STRINGS.items():
        missing = set(LANGUAGES) - set(entry)
        assert not missing, f"'{key}' is missing {missing}"
        assert all(entry[lang].strip() for lang in LANGUAGES), f"'{key}' has an empty translation"


def test_sample_questions_for_every_language():
    assert set(SAMPLE_QUESTIONS) == set(LANGUAGES)
    assert all(len(qs) > 0 for qs in SAMPLE_QUESTIONS.values())


def test_dropdown_order_and_default():
    assert list(LANGUAGES) == ["en", "pa", "hinglish", "hi"]


def test_scripts_match_language():
    greet = {lang: t("greeting", lang) for lang in LANGUAGES}
    assert any("਀" <= ch <= "੿" for ch in greet["pa"])  # Gurmukhi
    assert any("ऀ" <= ch <= "ॿ" for ch in greet["hi"])  # Devanagari
    for lang in ("en", "hinglish"):
        assert not any("ऀ" <= ch <= "੿" for ch in greet[lang])


def test_normalize_language():
    assert normalize_language("Punjabi") == "pa"
    assert normalize_language("english") == "en"
    assert normalize_language("hinglish") == "hinglish"
    assert normalize_language("unknown") == "hi"


def test_prompt_language_rule():
    assert "Gurmukhi" in build_system_prompt("ctx", "pa")
    assert "Roman" in build_system_prompt("ctx", "hinglish")
    assert "6." not in build_system_prompt("ctx", None)


def test_guardrails_warnings_follow_language():
    guardrails = AgriculturalGuardrails()
    _, en = guardrails.enforce_safety("Spray Monocrotophos 200 ml", "Monocrotophos on brinjal", language="en")
    assert any("banned" in d for d in en)
    _, pa = guardrails.enforce_safety("Spray Monocrotophos 200 ml", "Monocrotophos on brinjal", language="pa")
    assert any("ਪਾਬੰਦੀਸ਼ੁਦਾ" in d for d in pa)


def test_weather_advice_follows_language():
    tool = AgWeatherTool()
    spray, irr = tool._evaluate_agronomic_advisory(wind_speed=22.0, rain_prob=10.0, temp=25.0, language="en")
    assert "Strong wind" in spray
    assert tool._get_fallback_advisory("Karnal", language="hinglish").spray_recommendation.startswith("✅ Anukool")


@pytest.fixture(scope="module")
def pipeline():
    from app.agent.pipeline import KisanPipeline
    return KisanPipeline()


@pytest.mark.parametrize("lang,expected", [("en", "farming assistant"), ("pa", "ਸਤ ਸ੍ਰੀ ਅਕਾਲ"), ("hinglish", "Namaste kisan bhai"), ("hi", "किसान सहायक")])
def test_pipeline_greeting_in_chosen_language(pipeline, lang, expected):
    res = pipeline.process_query("Namaste", language=lang, generate_audio=False)
    assert res.intent == "greeting"
    assert expected in res.answer
    assert res.detected_language == lang


def test_pipeline_weather_in_english(pipeline):
    res = pipeline.process_query("What is the weather in Ludhiana today?", language="en", generate_audio=False)
    assert res.intent == "weather"
    assert "Farm Weather Advisory" in res.answer
