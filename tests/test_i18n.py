import re

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
    assert "7." not in build_system_prompt("ctx", None)
    assert "Do not use emojis" in build_system_prompt("ctx", None)


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
    assert tool._get_fallback_advisory("Karnal", language="hinglish").spray_recommendation.startswith("Anukool")


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


EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿ℹ⬀-⯿]")
# Text that appears inside answers (page chrome like tabs and the banner may keep icons)
ANSWER_KEYS = [
    "greeting", "out_of_scope", "stt_failed", "spray_rain", "spray_wind", "spray_ok", "irrigation_stop",
    "irrigation_light", "irrigation_normal", "fallback_spray", "fallback_irrigation", "statutory_disclaimer",
    "monocrotophos_warning", "endosulfan_warning", "location_default", "location_not_found",
    "note_template_llm_failed", "note_template_offline", "voice_unavailable", "evidence_verified", "evidence_partially_verified", "evidence_not_verified", "claim_corrected",
    "listen_header", "safety_header", "sources_header", "evidence_header", "details_header", "chat_welcome",
]


@pytest.mark.parametrize("key", ANSWER_KEYS)
def test_answer_text_has_no_emojis(key):
    for lang in LANGUAGES:
        assert not EMOJI.search(STRINGS[key][lang]), f"emoji in {key}/{lang}"


def test_template_and_weather_answers_have_no_emojis(pipeline, monkeypatch):
    from app.agent.synthesizer import DeterministicGroundedSynthesizer

    monkeypatch.setattr(pipeline, "synthesizer", DeterministicGroundedSynthesizer())
    for lang in LANGUAGES:
        answer = pipeline.process_query("How to control aphids in mustard?", language=lang, generate_audio=False)
        assert not EMOJI.search(answer.answer), lang
        assert not any(EMOJI.search(d) for d in answer.safety_disclaimers), lang
    weather = pipeline.process_query("Can I spray in Ludhiana today?", language="en", generate_audio=False)
    assert not EMOJI.search(weather.answer)


def test_every_key_used_in_code_exists():
    """A t("key") call whose key was removed or misspelt would crash the app at run time."""
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    used = set()
    for path in [*root.joinpath("frontend").glob("*.py"), *root.joinpath("app").rglob("*.py")]:
        used |= set(re.findall(r'\bt\(\s*"([a-z_]+)"', path.read_text(encoding="utf-8")))
    assert used and not sorted(k for k in used if k not in STRINGS)


def test_hinglish_advisories_are_in_latin_script():
    """Hinglish is written in Latin letters; a stray Hindi word (e.g. "आंशिक") breaks the answer language."""
    import json
    from pathlib import Path

    data = json.loads((Path(__file__).resolve().parent.parent / "data" / "translations.json").read_text(encoding="utf-8"))
    for section, fields in data["hinglish"].items():
        for field, text in fields.items():
            assert not re.search(r"[ऀ-ॿ਀-੿]", text), (section, field)
