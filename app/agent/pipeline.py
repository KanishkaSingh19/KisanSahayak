import time
from typing import List, Optional
from app.config import settings
from app.i18n import normalize_language, t
from app.agent.state import AgentQuery, ConversationTurn, GroundedAnswer, IntentResult
from app.agent.router import IntentRouter, weather_topics
from app.agent.synthesizer import get_synthesizer
from app.agent.guardrails import AgriculturalGuardrails
from app.rag.hybrid_retriever import HybridRetriever
from app.rag.chunker import AgriculturalChunker
from app.speech.stt import WhisperSTTAdapter
from app.speech.tts import EdgeTTSAdapter
from app.tools.weather_tool import AgWeatherTool

# Shown (with a visible note) when the farmer names no place or one that can't be found
DEFAULT_WEATHER_DISTRICT = "Ludhiana"


def detect_language(text: str) -> str:
    """Detect language and script from text (Punjabi Gurmukhi, Hindi Devanagari, or Hinglish)."""
    # Gurmukhi Unicode block
    if any("\u0A00" <= ch <= "\u0A7F" for ch in text):
        return "pa"
    # Devanagari Unicode block
    if any("\u0900" <= ch <= "\u097F" for ch in text):
        return "hi"
    return "hi"


class KisanPipeline:
    """End-to-End Orchestrator for KisanSahayak with Phase 2 Voice & Weather."""

    def __init__(
        self,
        retriever: Optional[HybridRetriever] = None,
        router: Optional[IntentRouter] = None,
        synthesizer=None,
        guardrails: Optional[AgriculturalGuardrails] = None,
        weather_tool: Optional[AgWeatherTool] = None,
        stt_adapter: Optional[WhisperSTTAdapter] = None,
        tts_adapter: Optional[EdgeTTSAdapter] = None,
    ):
        self.router = router or IntentRouter()
        self.guardrails = guardrails or AgriculturalGuardrails()
        self.synthesizer = synthesizer or get_synthesizer()
        self.retriever = retriever or HybridRetriever()
        self.weather_tool = weather_tool or AgWeatherTool()
        self.stt_adapter = stt_adapter or WhisperSTTAdapter()
        self.tts_adapter = tts_adapter or EdgeTTSAdapter()

        # Auto-initialize retriever if not already loaded
        if not self.retriever.is_ready:
            self._ensure_retriever_initialized()

    def _ensure_retriever_initialized(self) -> None:
        """Attempt to load saved indices; if not found, automatically ingest raw documents."""
        loaded = self.retriever.load_indices(settings.INDEX_DIR)
        if not loaded:
            # Ingest from raw data directory
            chunker = AgriculturalChunker(chunk_size=settings.CHUNK_SIZE, chunk_overlap=settings.CHUNK_OVERLAP)
            chunks = chunker.load_and_chunk_directory(settings.RAW_DATA_DIR)
            self.retriever.build_indices(chunks)
            self.retriever.save_indices(settings.INDEX_DIR)

    def process_audio_query(
        self,
        audio_bytes: bytes,
        filename: str = "farmer_voice.wav",
        user_id: str = "farmer",
        language: Optional[str] = None,
        generate_audio: bool = True,
        history: Optional[List[ConversationTurn]] = None,
    ) -> GroundedAnswer:
        """Process spoken farmer query via Groq Whisper STT with graceful fallback."""
        start_time = time.time()
        success, transcript = self.stt_adapter.transcribe_audio_bytes(audio_bytes, filename=filename, language=language)

        if not success:
            return GroundedAnswer(
                query="[Voice Input]",
                intent="voice_stt_unavailable",
                answer=t("stt_failed", language or "hi"),
                citations=[],
                retrieved_chunks=[],
                is_grounded=True,
                safety_disclaimers=[],
                detected_language=normalize_language(language) if language else "hi",
                # Technical reason for developers (shown under Details), not in the farmer's message
                processing_metadata={
                    "stt_status": "failed",
                    "stt_error": transcript,
                    "latency_ms": int((time.time() - start_time) * 1000),
                },
            )

        # Transcribed successfully: route into regular grounded processing pipeline
        ans = self.process_query(
            transcript, user_id=user_id, language=language, generate_audio=generate_audio, history=history
        )
        ans.processing_metadata["stt_transcript"] = transcript
        ans.processing_metadata["input_modality"] = "voice"
        return ans

    def process_query(
        self,
        query: str,
        user_id: str = "farmer",
        generate_audio: bool = True,
        language: Optional[str] = None,
        history: Optional[List[ConversationTurn]] = None,
    ) -> GroundedAnswer:
        """Process farmer query through intent routing, hybrid RAG, synthesis, and guardrails.

        `language` ("en", "pa", "hinglish", "hi") sets the reply language; when omitted it is
        detected from the query script. `history` holds earlier turns of the conversation so
        follow-ups ("what is the dose?", "aur Sangrur mein?") keep their crop, pest or place.
        """
        history = history or []
        start_time = time.time()
        clean_query = query.strip()
        detected_lang = normalize_language(language) if language else detect_language(clean_query)

        # 1. Validation for empty or invalid queries
        if not clean_query:
            return GroundedAnswer(
                query=query,
                intent="empty",
                answer=t("empty_query", detected_lang),
                citations=[],
                retrieved_chunks=[],
                is_grounded=True,
                safety_disclaimers=[],
                detected_language=detected_lang,
            )

        try:
            # 2. Intent Detection & Canonical Entity Extraction
            intent_res: IntentResult = self.router.classify_with_context(clean_query, history)

            # 3. Handle Greetings
            if intent_res.intent == "greeting":
                greeting_text = t("greeting", detected_lang)
                audio_path = self.tts_adapter.synthesize_speech(greeting_text, language=detected_lang) if generate_audio else None
                return GroundedAnswer(
                    query=clean_query,
                    intent=intent_res.intent,
                    answer=greeting_text,
                    citations=["ICAR & PAU Agricultural Extension"],
                    retrieved_chunks=[],
                    is_grounded=True,
                    safety_disclaimers=[],
                    audio_output_path=str(audio_path) if audio_path else None,
                    detected_language=detected_lang,
                    processing_metadata={"latency_ms": int((time.time() - start_time) * 1000)},
                )

            # 4. Handle Out-of-Scope Queries
            if intent_res.intent == "out_of_scope":
                oos_text = t("out_of_scope", detected_lang)
                return GroundedAnswer(
                    query=clean_query,
                    intent=intent_res.intent,
                    answer=oos_text,
                    citations=[],
                    retrieved_chunks=[],
                    is_grounded=True,
                    safety_disclaimers=[],
                    detected_language=detected_lang,
                    processing_metadata={"latency_ms": int((time.time() - start_time) * 1000)},
                )

            # 5. Handle Agricultural Weather Tool Intent (Phase 2)
            if intent_res.intent == "weather":
                lang = detected_lang
                requested = intent_res.detected_district
                place = self.weather_tool.resolve_place(requested) if requested else None
                location_note = ""
                if place is None:
                    # Never silently swap in another place: say which default is shown and why
                    key = "location_not_found" if requested else "location_default"
                    location_note = t(key, lang, place=requested or "", default=DEFAULT_WEATHER_DISTRICT) + "\n\n"
                report = self.weather_tool.get_weather_for_district(DEFAULT_WEATHER_DISTRICT, language=lang, place=place)
                district = report.district

                # Answer only what was asked: spray / irrigation advice only when the question mentions it
                topics = weather_topics(clean_query)
                summary = t(
                    "weather_summary", lang, place=report.district, temp=report.temperature_c,
                    humidity=report.relative_humidity, wind=report.wind_speed_kmh, rain=report.rain_probability_pct,
                )
                parts = [f"{location_note}### {t('weather_advisory_title', lang)}: {report.district}\n\n{summary}"]
                if "spray" in topics:
                    parts.append(f"**{t('spray_advisory', lang)}:**\n{report.spray_recommendation}")
                if "irrigation" in topics:
                    parts.append(f"**{t('irrigation_advice', lang)}:**\n{report.irrigation_advisory}")
                weather_ans = "\n\n".join(parts)
                citations = [report.source_notice]
                if topics:
                    citations.append("ICAR Agromet Advisory Guidelines")
                audio_path = self.tts_adapter.synthesize_speech(weather_ans, language=detected_lang) if generate_audio else None

                return GroundedAnswer(
                    query=clean_query,
                    intent=intent_res.intent,
                    answer=weather_ans,
                    citations=citations,
                    retrieved_chunks=[],
                    is_grounded=True,
                    safety_disclaimers=[],
                    audio_output_path=str(audio_path) if audio_path else None,
                    weather_report=report.model_dump(),
                    detected_language=detected_lang,
                    processing_metadata={
                        "latency_ms": int((time.time() - start_time) * 1000),
                        "district": district,
                        "location_found": place is not None,
                        "is_live_weather": report.is_live,
                    },
                )

            # 6. Hybrid Agricultural Retrieval (FAISS + BM25 + RRF)
            # Add the crop and pest (detected, or carried over from the previous turn) so that
            # short follow-ups like "what is the dose?" still retrieve the right advisory
            context_terms = [
                term for term in (intent_res.detected_crop, intent_res.detected_topic)
                if term and term != "Agronomy/General" and term.lower() not in clean_query.lower()
            ]
            if intent_res.follow_up_of:
                # "Is it dangerous?" alone matches nothing; with the earlier question it finds the right advisory
                context_terms.append(intent_res.follow_up_of)
            search_query = " ".join(context_terms + [clean_query])

            retrieved = self.retriever.retrieve(search_query)

            # 7. Response Synthesis
            # Only force an answer language when the farmer chose one; otherwise the LLM mirrors the query
            answer_lang = detected_lang if language else None
            if hasattr(self.synthesizer, "generate"):
                draft_answer, answer_source = self.synthesizer.generate(
                    clean_query, retrieved, language=answer_lang, history=history
                )
            else:
                draft_answer, answer_source = self.synthesizer.synthesize(clean_query, retrieved, language=answer_lang), "unknown"

            # 8. Safety Guardrails & Grounding Check
            sanitized_answer, disclaimers = self.guardrails.enforce_safety(draft_answer, clean_query, language=detected_lang)
            context_texts = [c.text for c in retrieved]
            is_grounded, grounding_score = self.guardrails.validate_grounding(sanitized_answer, context_texts)

            # 9. Deduplicate citations
            raw_citations = [c.citation for c in retrieved]
            unique_citations = list(dict.fromkeys(raw_citations))

            # 10. Non-blocking Optional Audio Synthesis
            audio_path = None
            if generate_audio and settings.ENABLE_TTS:
                audio_path = self.tts_adapter.synthesize_speech(sanitized_answer, language=detected_lang)

            latency = int((time.time() - start_time) * 1000)

            return GroundedAnswer(
                query=clean_query,
                intent=intent_res.intent,
                answer=sanitized_answer,
                citations=unique_citations,
                retrieved_chunks=retrieved,
                is_grounded=is_grounded,
                safety_disclaimers=disclaimers,
                audio_output_path=str(audio_path) if audio_path else None,
                detected_language=detected_lang,
                processing_metadata={
                    "latency_ms": latency,
                    "grounding_score": grounding_score,
                    "detected_crop": intent_res.detected_crop,
                    "detected_topic": intent_res.detected_topic,
                    "router_confidence": intent_res.confidence,
                    "router_reasoning": intent_res.reasoning,
                    "top_section": retrieved[0].section if retrieved else None,
                    "answer_source": answer_source,
                },
            )

        except Exception as e:
            return GroundedAnswer(
                query=clean_query,
                intent="error",
                answer=t("processing_error", detected_lang, error=str(e)),
                citations=[],
                retrieved_chunks=[],
                is_grounded=False,
                safety_disclaimers=[t("error_handling_active", detected_lang)],
                detected_language=detected_lang,
                processing_metadata={"error": str(e)},
            )
