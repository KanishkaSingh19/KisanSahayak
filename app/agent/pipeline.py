import time
from typing import List, Optional
from app.config import settings
from app.i18n import normalize_language, t
from app.agent.state import AgentQuery, ConversationTurn, FarmerProfile, GroundedAnswer, IntentResult
from app.tools.schemes import SchemeGuide, check_eligibility
from app.agent.router import IntentRouter, weather_topics
from app.agent.synthesizer import get_synthesizer
from app.agent.guardrails import AgriculturalGuardrails
from app.rag.hybrid_retriever import HybridRetriever
from app.rag.chunker import AgriculturalChunker
from app.speech.stt import WhisperSTTAdapter
from app.speech.tts import EdgeTTSAdapter
from app.tools.vision import CropVision
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
        vision: Optional[CropVision] = None,
        scheme_guide: Optional[SchemeGuide] = None,
    ):
        self.vision = vision or CropVision()
        self.scheme_guide = scheme_guide or SchemeGuide()
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
        profile: Optional[FarmerProfile] = None,
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
            transcript, user_id=user_id, language=language, generate_audio=generate_audio, history=history,
            profile=profile,
        )
        ans.processing_metadata["stt_transcript"] = transcript
        ans.processing_metadata["input_modality"] = "voice"
        return ans

    def process_image_query(
        self,
        image_bytes: bytes,
        question: str = "",
        language: Optional[str] = None,
        history: Optional[List[ConversationTurn]] = None,
        profile: Optional[FarmerProfile] = None,
    ) -> GroundedAnswer:
        """Diagnose a crop photo with Gemini Vision, then answer from the verified advisories.

        The vision model only names the likely problem; treatment and doses come from retrieval +
        grounded synthesis + guardrails, exactly as for typed questions.
        """
        start_time = time.time()
        lang = normalize_language(language) if language else "hi"
        question = (question or "").strip()

        def reply(answer: str, intent: str, meta: dict, **extra) -> GroundedAnswer:
            meta = {"input_modality": "image", "latency_ms": int((time.time() - start_time) * 1000), **meta}
            return GroundedAnswer(
                query=question or "[Photo]", intent=intent, answer=answer, detected_language=lang,
                processing_metadata=meta, **{"citations": [], "retrieved_chunks": [], "is_grounded": True, **extra},
            )

        diagnosis = self.vision.diagnose(image_bytes, question=question, language=lang)
        if diagnosis is None:
            return reply(t("photo_failed", lang), "image_unavailable", {"error": self.vision.last_error})

        meta = {
            "vision": diagnosis.model_dump(),
            "detected_crop": diagnosis.crop.title() if diagnosis.covered else None,
            "detected_topic": diagnosis.problem if diagnosis.identified else None,
        }
        if not diagnosis.is_plant:
            return reply(t("photo_not_plant", lang), "image_diagnosis", meta)

        summary = t(
            "photo_result", lang, problem=diagnosis.problem, crop=diagnosis.crop_name,
            confidence=t(f"confidence_{diagnosis.confidence}", lang), summary=diagnosis.summary_local,
        )
        if diagnosis.problem.strip().lower() == "healthy":
            return reply(f"{summary}\n\n{t('photo_healthy', lang)}", "image_diagnosis", meta)
        if not diagnosis.identified or diagnosis.confidence == "low":
            return reply(f"{summary}\n\n{t('photo_unclear', lang)}", "image_diagnosis", meta)

        # Search the advisories with what the photo shows, then check they actually cover it
        search = " ".join(filter(None, [diagnosis.crop_name, diagnosis.problem, diagnosis.visible_symptoms, question]))
        retrieved = self.retriever.retrieve(search)
        top_crop = retrieved[0].crop.lower() if retrieved else ""
        if not diagnosis.covered or diagnosis.crop not in top_crop:
            return reply(f"{summary}\n\n{t('photo_not_covered', lang)}", "image_diagnosis", meta)

        farmer_question = question or "What is this problem and how should I treat it?"
        llm_query = (
            f"The farmer sent a photo of their {diagnosis.crop_name} crop. An image model thinks it most likely shows "
            f"{diagnosis.problem} ({diagnosis.confidence} confidence). Visible: {diagnosis.visible_symptoms} "
            f"Farmer's question: {farmer_question}"
        )
        draft, source = self.synthesizer.generate(
            llm_query, retrieved, language=lang if language else None, history=history or [],
            context_note=profile.summary() if profile else "",
        )
        answer, disclaimers = self.guardrails.enforce_safety(f"{summary}\n\n{draft}", question, language=lang)
        is_grounded, score = self.guardrails.validate_grounding(draft, [c.text for c in retrieved])
        meta.update({
            "answer_source": source,
            "grounding_score": score,
            "top_section": retrieved[0].section,
        })
        return reply(
            answer, "image_diagnosis", meta,
            citations=list(dict.fromkeys(c.citation for c in retrieved)),
            retrieved_chunks=retrieved,
            is_grounded=is_grounded,
            safety_disclaimers=[t("photo_disclaimer", lang)] + disclaimers,
        )

    def _answer_scheme(self, query, intent_res, lang, language, history, profile, start_time) -> GroundedAnswer:
        """PM-KISAN answer: rule-based eligibility from the profile + scheme text from the official website."""
        guide = self.scheme_guide
        sections = guide.select_sections(" ".join(filter(None, [intent_res.follow_up_of, query])))
        context = guide.as_context(sections)

        # Eligibility is decided by fixed rules, never by the LLM
        status, reasons, may_be_withheld = check_eligibility(profile)
        asked_eligibility = any(s["id"] in ("eligibility", "exclusions") for s in sections)
        eligibility_text = ""
        if status == "likely_eligible":
            eligibility_text = t("pmk_likely_eligible", lang)
        elif status == "not_eligible":
            eligibility_text = t("pmk_not_eligible", lang, reasons="; ".join(t(r, lang) for r in reasons))
        elif asked_eligibility:
            eligibility_text = t("pmk_needs_info", lang)
        if may_be_withheld:
            eligibility_text += "\n\n" + t("pmk_withheld", lang)

        notes = [profile.summary()] if profile and not profile.is_empty() else []
        if status != "needs_info":
            notes.append(f"Rule-based PM-KISAN eligibility check from the profile: {status.replace('_', ' ')} "
                         "(already shown to the farmer; do not contradict it).")
        draft, source = self.synthesizer.generate(
            query, context, language=lang if language else None, history=history, context_note=" ".join(notes),
        )
        if source != "llm":
            draft = guide.offline_answer(sections, lang)  # stored official text in the farmer's language

        answer = f"{eligibility_text}\n\n{draft}" if eligibility_text else draft
        is_grounded, score = self.guardrails.validate_grounding(draft, [c.text for c in context])
        return GroundedAnswer(
            query=query,
            intent="scheme_query",
            answer=answer,
            citations=[guide.citation],
            retrieved_chunks=context,
            is_grounded=is_grounded or source != "llm",
            safety_disclaimers=[t("scheme_disclaimer", lang, date=guide.data["last_verified"])],
            detected_language=lang,
            processing_metadata={
                "latency_ms": int((time.time() - start_time) * 1000),
                "answer_source": source,
                "detected_topic": "PM-KISAN",
                "pmk_eligibility": status,
                "grounding_score": score,
                "top_section": sections[0]["title"],
            },
        )

    def process_query(
        self,
        query: str,
        user_id: str = "farmer",
        generate_audio: bool = True,
        language: Optional[str] = None,
        history: Optional[List[ConversationTurn]] = None,
        profile: Optional[FarmerProfile] = None,
    ) -> GroundedAnswer:
        """Process farmer query through intent routing, hybrid RAG, synthesis, and guardrails.

        `language` ("en", "pa", "hinglish", "hi") sets the reply language; when omitted it is
        detected from the query script. `history` holds earlier turns of the conversation so
        follow-ups ("what is the dose?", "aur Sangrur mein?") keep their crop, pest or place.
        `profile` (optional) personalises answers: the farmer's district for weather, their crop
        when none is named, and PM-KISAN eligibility.
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
                from_profile = False
                if not requested and profile and profile.district:
                    requested = profile.district  # "Will it rain today?" -> the farmer's own district
                    from_profile = True
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
                        "district_from_profile": from_profile,
                        "location_found": place is not None,
                        "is_live_weather": report.is_live,
                    },
                )

            # 5b. Government scheme guidance (PM-KISAN)
            if intent_res.intent == "scheme_query":
                return self._answer_scheme(clean_query, intent_res, detected_lang, language, history, profile, start_time)

            # No crop named or carried over: use the farmer's crop if their profile lists exactly one we cover
            if not intent_res.detected_crop and profile:
                covered = [c for c in profile.crops if c.lower() in ("wheat", "mustard", "paddy", "cotton")]
                if len(covered) == 1:
                    intent_res.detected_crop = covered[0].title()

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
            if intent_res.detected_crop:
                # Equal fusion scores (e.g. wheat vs mustard aphid) must not put another crop first
                crop = intent_res.detected_crop.lower()
                retrieved.sort(key=lambda c: (c.crop or "").lower() != crop)

            # 7. Response Synthesis
            # Only force an answer language when the farmer chose one; otherwise the LLM mirrors the query
            answer_lang = detected_lang if language else None
            if hasattr(self.synthesizer, "generate"):
                draft_answer, answer_source = self.synthesizer.generate(
                    clean_query, retrieved, language=answer_lang, history=history,
                    context_note=profile.summary() if profile else "",
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
