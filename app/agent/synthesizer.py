import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from app.config import settings
from app.i18n import LLM_LANGUAGE_INSTRUCTIONS, normalize_language, t
from app.rag.hybrid_retriever import RetrievalResult

SYSTEM_PROMPT = """You are KisanSahayak, an expert agricultural AI assistant grounded strictly in verified Indian agricultural research from ICAR, PAU, and the Ministry of Agriculture.

STRICT GROUNDING RULES:
1. Answer the farmer's question ONLY using the factual context provided below.
2. If the context does not contain the answer, clearly say that verified ICAR/PAU information on this topic was not found,
   and advise the farmer to contact their nearest Krishi Vigyan Kendra (KVK).
3. Do not invent any pesticide dosage, chemical name, or agricultural advice.
4. Clearly state chemical dosages and precautions if mentioned in the context.
5. End your response by listing the official sources used.
{language_rule}
CONTEXT:
----------------
{context}
----------------
"""


def build_system_prompt(context: str, language: Optional[str] = None) -> str:
    """Fill the grounding prompt, adding an answer-language rule when a language is chosen."""
    language_rule = ""
    if language:
        instruction = LLM_LANGUAGE_INSTRUCTIONS[normalize_language(language)]
        language_rule = f"6. {instruction} Keep pesticide/chemical names and dosages exactly as written in the context.\n"
    return SYSTEM_PROMPT.format(context=context, language_rule=language_rule)


GEMINI_TIMEOUT_MS = 10_000  # per request; normal answers take 2-5 s
QUOTA_COOLDOWN_SEC = 600  # skip a model for 10 minutes after "quota exhausted" (429)

HISTORY_TURNS = 3  # earlier exchanges shown to the LLM
HISTORY_ANSWER_CHARS = 500  # each earlier answer is shortened to keep the prompt small


def format_history(history) -> str:
    """Recent conversation as plain text, so the LLM can resolve follow-ups like "what is the dose?"."""
    if not history:
        return ""
    lines = ["PREVIOUS CONVERSATION (context only; answer the latest question):"]
    for turn in history[-HISTORY_TURNS:]:
        answer = turn.answer if len(turn.answer) <= HISTORY_ANSWER_CHARS else turn.answer[:HISTORY_ANSWER_CHARS] + "..."
        lines.append(f"Farmer: {turn.query}\nAssistant: {answer}")
    return "\n\n".join(lines) + "\n\n"


# Where an answer came from, reported alongside it by generate()
SOURCE_LLM = "llm"                          # written by Gemini/OpenAI
SOURCE_TEMPLATE_OFFLINE = "template_offline"  # no LLM configured
SOURCE_TEMPLATE_LLM_FAILED = "template_llm_failed"  # LLM call failed (busy, network, quota)
SOURCE_NO_RESULTS = "no_results"            # nothing relevant retrieved


TRANSLATIONS_PATH = settings.DATA_DIR / "translations.json"


def load_translations(path: Path = TRANSLATIONS_PATH) -> Dict[str, Dict[str, Dict[str, str]]]:
    """Pre-translated advisory sections, {lang: {section_title: {field: text}}} (see scripts/translate_advisories.py)."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


class DeterministicGroundedSynthesizer:
    """Offline, deterministic grounded response generator.

    Synthesizes clear, structured agricultural advisories directly from retrieved
    factual chunks without external LLM API dependency. Uses pre-translated advisory
    text for the farmer's language when available, otherwise the original English.
    """

    def __init__(self, translations: Optional[Dict[str, Dict[str, Dict[str, str]]]] = None):
        self.translations = load_translations() if translations is None else translations

    def generate(
        self, query: str, chunks: List[RetrievalResult], language: Optional[str] = None, history=None
    ) -> Tuple[str, str]:
        """Return (answer, source)."""
        source = SOURCE_TEMPLATE_OFFLINE if chunks else SOURCE_NO_RESULTS
        return self.synthesize(query, chunks, language), source

    def synthesize(self, query: str, chunks: List[RetrievalResult], language: Optional[str] = None) -> str:
        lang = language or "hi"
        if not chunks:
            return t("no_verified_info", lang)

        top_chunk = chunks[0]
        topic = top_chunk.section
        crop = top_chunk.crop

        symptoms = ""
        action = ""
        preventive = ""
        warning = ""

        # Aggregate ONLY across chunks matching the same crop and section
        for c in chunks:
            if c.crop != crop or c.section != topic:
                continue
            lines = [line.strip() for line in c.text.split("\n") if line.strip()]
            for line in lines:
                if line.startswith("Symptoms & Identification:") and not symptoms:
                    symptoms = line.replace("Symptoms & Identification:", "").strip()
                elif line.startswith("Recommended Action & Chemical Dosage:") and not action:
                    action = line.replace("Recommended Action & Chemical Dosage:", "").strip()
                elif line.startswith("Preventive Measures:") and not preventive:
                    preventive = line.replace("Preventive Measures:", "").strip()
                elif line.startswith("Safety Warning:") and not warning:
                    warning = line.replace("Safety Warning:", "").strip()

        # Swap in the pre-translated section for the farmer's language, if there is one
        title = topic
        translated = self.translations.get(normalize_language(lang), {}).get(topic) if lang != "en" else None
        if translated:
            title = translated.get("section_title", topic)
            symptoms = translated.get("symptoms", symptoms)
            action = translated.get("recommended_action", action)
            preventive = translated.get("preventive_measures", preventive)
            warning = translated.get("critical_safety_warning", warning)

        response_parts = [
            f"### 🌾 {t('crop_advisory', lang)}: {crop} ({title})\n",
        ]

        if symptoms:
            response_parts.append(f"**🔍 {t('identification', lang)}:**\n{symptoms}\n")

        if action:
            response_parts.append(f"**💊 {t('recommended_control', lang)}:**\n{action}\n")

        if preventive:
            response_parts.append(f"**🛡️ {t('preventive_measures', lang)}:**\n{preventive}\n")

        if warning:
            response_parts.append(f"**⚠️ {t('special_warning', lang)}:**\n{warning}\n")

        # Fallback if specific tags are not present
        if not (symptoms or action or preventive or warning):
            response_parts.append(f"{top_chunk.text}\n")

        return "\n".join(response_parts)


class GeminiSynthesizer:
    """Response generation via Google Gemini API."""

    def __init__(
        self,
        api_key: str,
        model_name: str = settings.GEMINI_MODEL,
        fallback_model: Optional[str] = settings.GEMINI_FALLBACK_MODEL,
    ):
        from google import genai
        from google.genai import types

        # One quick retry only when a model is momentarily busy (503). A used-up quota (429)
        # won't recover in seconds, so that model is skipped for a while (see generate()).
        retry = types.HttpRetryOptions(attempts=2, initial_delay=0.5, max_delay=1.0, http_status_codes=[500, 503])
        self.client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(retry_options=retry, timeout=GEMINI_TIMEOUT_MS),
        )
        self.model_name = model_name
        self.models = [m for m in (model_name, fallback_model) if m]
        self.fallback = DeterministicGroundedSynthesizer()
        self._skip_until: Dict[str, float] = {}  # model -> time until which its quota is exhausted

    def generate(
        self, query: str, chunks: List[RetrievalResult], language: Optional[str] = None, history=None
    ) -> Tuple[str, str]:
        """Return (answer, source); tries each Gemini model in turn, then the offline template."""
        if not chunks:
            return self.fallback.generate(query, chunks, language)

        context_str = "\n\n".join([f"Source [{c.citation}]:\n{c.text}" for c in chunks])
        prompt = (
            f"{build_system_prompt(context_str, language)}\n\n"
            f"{format_history(history)}Farmer Query: {query}\n\nGrounded Answer:"
        )

        for model in self.models:
            if time.time() < self._skip_until.get(model, 0):
                continue  # quota used up recently: don't make the farmer wait for another refusal
            try:
                response = self.client.models.generate_content(model=model, contents=prompt)
                return response.text.strip(), SOURCE_LLM
            except Exception as e:
                message = str(e)
                if "429" in message or "RESOURCE_EXHAUSTED" in message:
                    self._skip_until[model] = time.time() + QUOTA_COOLDOWN_SEC
                print(f"[Warning] Gemini ({model}) failed: {message[:200]}")

        print("[Warning] All Gemini models failed. Using offline template.")
        return self.fallback.synthesize(query, chunks, language), SOURCE_TEMPLATE_LLM_FAILED

    def synthesize(self, query: str, chunks: List[RetrievalResult], language: Optional[str] = None) -> str:
        return self.generate(query, chunks, language)[0]


class OpenAISynthesizer:
    """Response generation via OpenAI API."""

    def __init__(self, api_key: str, model_name: str = settings.OPENAI_MODEL):
        from openai import OpenAI

        self.client = OpenAI(api_key=api_key)
        self.model_name = model_name
        self.fallback = DeterministicGroundedSynthesizer()

    def generate(
        self, query: str, chunks: List[RetrievalResult], language: Optional[str] = None, history=None
    ) -> Tuple[str, str]:
        """Return (answer, source); falls back to the offline template if OpenAI fails."""
        if not chunks:
            return self.fallback.generate(query, chunks, language)

        context_str = "\n\n".join([f"Source [{c.citation}]:\n{c.text}" for c in chunks])
        try:
            resp = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": build_system_prompt(context_str, language)},
                    *[
                        message
                        for turn in (history or [])[-HISTORY_TURNS:]
                        for message in (
                            {"role": "user", "content": turn.query},
                            {"role": "assistant", "content": turn.answer[:HISTORY_ANSWER_CHARS]},
                        )
                    ],
                    {"role": "user", "content": query},
                ],
                temperature=0.2,
            )
            return resp.choices[0].message.content.strip(), SOURCE_LLM
        except Exception as e:
            print(f"[Warning] OpenAI ({self.model_name}) failed: {str(e)[:200]}. Using offline template.")
            return self.fallback.synthesize(query, chunks, language), SOURCE_TEMPLATE_LLM_FAILED

    def synthesize(self, query: str, chunks: List[RetrievalResult], language: Optional[str] = None) -> str:
        return self.generate(query, chunks, language)[0]


def get_synthesizer():
    """Factory to get the configured synthesizer."""
    provider = settings.LLM_PROVIDER.lower()
    if provider == "gemini" and settings.GEMINI_API_KEY:
        try:
            return GeminiSynthesizer(settings.GEMINI_API_KEY, settings.GEMINI_MODEL)
        except Exception:
            return DeterministicGroundedSynthesizer()
    elif provider == "openai" and settings.OPENAI_API_KEY:
        try:
            return OpenAISynthesizer(settings.OPENAI_API_KEY, settings.OPENAI_MODEL)
        except Exception:
            return DeterministicGroundedSynthesizer()
    return DeterministicGroundedSynthesizer()
