from app.agent.synthesizer import (
    SOURCE_LLM,
    SOURCE_NO_RESULTS,
    SOURCE_TEMPLATE_LLM_FAILED,
    SOURCE_TEMPLATE_OFFLINE,
    DeterministicGroundedSynthesizer,
    GeminiSynthesizer,
)
from app.rag.hybrid_retriever import RetrievalResult

CHUNK = RetrievalResult(
    chunk_id="c1",
    text="Symptoms & Identification: Aphids suck sap.\nRecommended Action & Chemical Dosage: Spray Thiamethoxam 25% WG @ 50 g per acre.",
    score=0.9,
    citation="ICAR-DRMR [Mustard Aphid]",
    source_agency="ICAR-DRMR",
    crop="Mustard",
    section="Mustard Aphid",
)


class _Models:
    def __init__(self, reply=None, error=None, busy_models=()):
        self.reply, self.error, self.busy_models = reply, error, set(busy_models)
        self.calls = []

    def generate_content(self, model, contents):
        self.calls.append(model)
        if self.error or model in self.busy_models:
            raise self.error or RuntimeError("503 UNAVAILABLE")
        return type("Resp", (), {"text": self.reply})()


class _Client:
    def __init__(self, **kwargs):
        self.models = _Models(**kwargs)


def _gemini(**kwargs):
    syn = GeminiSynthesizer(api_key="test-key", model_name="test-model", fallback_model="backup-model")
    syn.client = _Client(**kwargs)
    return syn


def test_offline_template_source():
    answer, source = DeterministicGroundedSynthesizer().generate("aphid", [CHUNK], "en")
    assert source == SOURCE_TEMPLATE_OFFLINE
    assert "Thiamethoxam" in answer


def test_no_results_source():
    _, source = DeterministicGroundedSynthesizer().generate("aphid", [], "en")
    assert source == SOURCE_NO_RESULTS


def test_llm_success_source():
    answer, source = _gemini(reply="Spray Thiamethoxam.").generate("aphid", [CHUNK], "en")
    assert source == SOURCE_LLM
    assert answer == "Spray Thiamethoxam."


def test_busy_model_hands_over_to_fallback_model():
    syn = _gemini(reply="From backup.", busy_models={"test-model"})
    answer, source = syn.generate("aphid", [CHUNK], "en")
    assert source == SOURCE_LLM
    assert answer == "From backup."
    assert syn.client.models.calls == ["test-model", "backup-model"]


def test_model_out_of_quota_is_skipped_next_time():
    syn = _gemini(reply="From backup.", error=None, busy_models=set())

    def models_call(model, contents):
        syn.client.models.calls.append(model)
        if model == "test-model":
            raise RuntimeError("429 RESOURCE_EXHAUSTED quota")
        return type("Resp", (), {"text": "From backup."})()

    syn.client.models.generate_content = models_call
    syn.generate("aphid", [CHUNK], "en")
    syn.generate("aphid", [CHUNK], "en")
    # The first question tries the main model; the second goes straight to the backup
    assert syn.client.models.calls == ["test-model", "backup-model", "backup-model"]


def test_llm_failure_falls_back_to_template():
    syn = _gemini(error=RuntimeError("503 UNAVAILABLE"))
    answer, source = syn.generate("aphid", [CHUNK], "en")
    assert source == SOURCE_TEMPLATE_LLM_FAILED
    assert "Crop Advisory" in answer
    assert syn.client.models.calls == ["test-model", "backup-model"]


TRANSLATIONS = {"pa": {"Mustard Aphid": {"section_title": "ਸਰ੍ਹੋਂ ਦਾ ਚੇਪਾ", "symptoms": "ਚੇਪਾ ਰਸ ਚੂਸਦਾ ਹੈ।", "recommended_action": "Thiamethoxam 25% WG @ 50 g ਪ੍ਰਤੀ ਏਕੜ ਛਿੜਕਾਅ ਕਰੋ।"}}}


def test_offline_template_uses_translation():
    answer = DeterministicGroundedSynthesizer(translations=TRANSLATIONS).synthesize("aphid", [CHUNK], "pa")
    assert "ਸਰ੍ਹੋਂ ਦਾ ਚੇਪਾ" in answer
    assert "ਛਿੜਕਾਅ ਕਰੋ" in answer
    assert "Aphids suck sap" not in answer


def test_offline_template_english_and_missing_translation_stay_english():
    syn = DeterministicGroundedSynthesizer(translations=TRANSLATIONS)
    assert "Aphids suck sap" in syn.synthesize("aphid", [CHUNK], "en")
    assert "Aphids suck sap" in syn.synthesize("aphid", [CHUNK], "hi")  # no Hindi entry -> original text


def test_saved_translations_keep_every_number():
    """Doses, percentages and dates must survive translation unchanged."""
    import json
    import re

    from app.agent.synthesizer import load_translations
    from app.config import settings

    translations = load_translations()
    if not translations:
        return  # translations not generated
    numbers = lambda s: set(re.findall(r"\d+(?:\.\d+)?", s))
    for path in settings.RAW_DATA_DIR.glob("*.json"):
        for section in json.loads(path.read_text(encoding="utf-8"))["sections"]:
            for lang, sections in translations.items():
                translated = sections.get(section["section_title"])
                assert translated, f"{lang} missing '{section['section_title']}'"
                for field, text in translated.items():
                    missing = numbers(section[field]) - numbers(text)
                    assert not missing, f"{lang} / {section['section_title']} / {field} lost {missing}"


def test_synthesize_still_returns_text():
    assert _gemini(reply="ok").synthesize("aphid", [CHUNK]) == "ok"


def test_offline_answer_has_the_whole_advisory_field():
    """A long section is split into chunks; the offline answer must not lose the part in the second chunk."""
    from app.rag.hybrid_retriever import RetrievalResult

    chunk = RetrievalResult(
        chunk_id="wheat_s0_c0", text="Recommended Action & Chemical Dosage: Spray Propiconazole 25% EC @ 200 ml.",
        score=1.0, citation="PAU", source_agency="PAU", crop="Wheat",
        section="Yellow Rust (Pila Rataua / Peeli Kungi) Identification and Management",
    )
    answer = DeterministicGroundedSynthesizer().synthesize("What should I spray?", [chunk], language="en")
    assert "Repeat spray after 15 days" in answer
