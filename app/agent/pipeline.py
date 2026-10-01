import time
from dataclasses import dataclass
from typing import List, Optional
from app.config import settings
from app.crops import COVERED_CROPS
from app.i18n import normalize_language, t
from app.agent.state import ConversationTurn, FarmerProfile, GroundedAnswer, IntentResult
from app.tools.schemes import OTHER_SCHEME_PREFIX, OTHER_SCHEMES, PM_KISAN, SchemeGuide, check_eligibility, load_schemes
from app.agent.router import IntentRouter, asks_repeat_spray, weather_topics
from app.agent.synthesizer import get_synthesizer
from app.agent.guardrails import AgriculturalGuardrails
from app.rag.hybrid_retriever import HybridRetriever
from app.rag.ingest import load_knowledge_chunks
from app.speech.stt import WhisperSTTAdapter
from app.speech.tts import EdgeTTSAdapter
from app.tools.dose import scale_doses
from app.tools.location import STATES, state_named
from app.tools.market import MarketPriceService, detect_commodity, load_msp, state_for
from app.tools.vision import CropVision
from app.tools.weather_tool import AgWeatherTool

@dataclass
class Request:
    """What every answer needs: the question, its language, the conversation and the farm profile."""

    query: str
    lang: str  # language of the reply
    chosen_language: Optional[str]  # the language the farmer picked (None: detected from the script)
    history: List[ConversationTurn]
    profile: Optional[FarmerProfile]
    intent: IntentResult
    start_time: float
    generate_audio: bool

    @property
    def llm_language(self) -> Optional[str]:
        # Only force the answer language when the farmer chose one; otherwise the LLM mirrors the question
        return self.lang if self.chosen_language else None


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
        mandi: Optional[MarketPriceService] = None,
    ):
        self.vision = vision or CropVision()
        self.mandi = mandi or MarketPriceService()
        self.scheme_guide = scheme_guide or SchemeGuide()  # PM-KISAN
        self.schemes = {name: SchemeGuide(data) for name, data in load_schemes().items()}
        self.schemes[PM_KISAN] = self.scheme_guide
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
        # PAU's Package of Practices chapters are searched only for topics our advisories don't cover
        self.pau_indexed = any(c.metadata.get("kind") == "pau" for c in self.retriever.dense_retriever.chunks)
        self.router.pau_available = self.pau_indexed

    def _ensure_retriever_initialized(self) -> None:
        """Load saved indices; rebuild them from the raw documents if they are missing or stale."""
        chunks = load_knowledge_chunks()  # fast: no embeddings
        loaded = self.retriever.load_indices(settings.INDEX_DIR)
        # An index saved before the advisories or the chunk settings changed must not be reused
        saved = [(c.chunk_id, c.text) for c in self.retriever.dense_retriever.chunks] if loaded else []
        if not loaded or sorted(saved) != sorted((c.chunk_id, c.text) for c in chunks):
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
        retrieved = self.retriever.retrieve(search, kind="advisory" if self.pau_indexed else None)
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

    # ------------------------------------------------------------------ answering a typed question
    def process_query(
        self,
        query: str,
        user_id: str = "farmer",
        generate_audio: bool = True,
        language: Optional[str] = None,
        history: Optional[List[ConversationTurn]] = None,
        profile: Optional[FarmerProfile] = None,
    ) -> GroundedAnswer:
        """Route a farmer's question to the right kind of answer.

        `language` ("en", "pa", "hinglish", "hi") sets the reply language; when omitted it is
        detected from the query script. `history` holds earlier turns of the conversation so
        follow-ups ("what is the dose?", "aur Sangrur mein?") keep their crop, pest or place.
        `profile` (optional) personalises answers: the farmer's district for weather, their crop
        when none is named, and PM-KISAN eligibility.
        """
        start_time = time.time()
        clean_query = query.strip()
        detected_lang = normalize_language(language) if language else detect_language(clean_query)
        if not clean_query:
            return GroundedAnswer(
                query=query, intent="empty", answer=t("empty_query", detected_lang), citations=[], retrieved_chunks=[],
                is_grounded=True, safety_disclaimers=[], detected_language=detected_lang,
            )
        try:
            intent = self.router.classify_with_context(clean_query, history or [])
            req = Request(clean_query, detected_lang, language, history or [], profile, intent, start_time, generate_audio)
            return self._handler(intent.intent)(req)
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

    def _handler(self, intent: str):
        """The method that answers each kind of question; anything else is a crop question."""
        return {
            "greeting": self._answer_greeting,
            "out_of_scope": self._answer_out_of_scope,
            "crop_not_covered": self._answer_not_covered,
            "topic_not_covered": self._answer_not_covered,
            "weather": self._answer_weather,
            "scheme_query": self._answer_scheme,
            "market_price": self._answer_market,
        }.get(intent, self._answer_crop)

    def _reply(self, req: "Request", answer: str, meta: Optional[dict] = None, **fields) -> GroundedAnswer:
        """An answer with the usual defaults: no sources, nothing retrieved, nothing to warn about."""
        values = {"citations": [], "retrieved_chunks": [], "is_grounded": True, "safety_disclaimers": [], **fields}
        return GroundedAnswer(
            query=req.query,
            intent=req.intent.intent,
            answer=answer,
            detected_language=req.lang,
            processing_metadata={"latency_ms": int((time.time() - req.start_time) * 1000), **(meta or {})},
            **values,
        )

    def _speak(self, req: "Request", text: str) -> Optional[str]:
        path = self.tts_adapter.synthesize_speech(text, language=req.lang) if req.generate_audio else None
        return str(path) if path else None

    def _answer_greeting(self, req: "Request") -> GroundedAnswer:
        text = t("greeting", req.lang)
        return self._reply(req, text, citations=["ICAR & PAU Agricultural Extension"],
                           audio_output_path=self._speak(req, text))

    def _answer_out_of_scope(self, req: "Request") -> GroundedAnswer:
        return self._reply(req, t("out_of_scope", req.lang))

    def _answer_not_covered(self, req: "Request") -> GroundedAnswer:
        """A crop or topic the verified advisories don't cover: refer the farmer instead of borrowing
        another crop's or topic's advice."""
        return self._reply(req, t(req.intent.intent, req.lang),
                           meta={"detected_crop": req.intent.detected_crop, "detected_topic": req.intent.detected_topic})

    def _answer_weather(self, req: "Request") -> GroundedAnswer:
        """Live weather for a place, with spray / irrigation advice only when asked. There is no default
        place: with none known, or a whole state named, the farmer is asked which district."""
        lang, requested, from_profile = req.lang, req.intent.detected_district, False
        if not requested and req.profile and req.profile.district:
            requested, from_profile = req.profile.district, True  # "Will it rain today?" -> the farmer's district
        whole_state = state_named(requested) if requested else None
        place = self.weather_tool.resolve_place(requested) if requested and not whole_state else None
        if place is None:
            if whole_state:  # "weather in Punjab": the weather differs by district, so ask which one
                answer = t("location_is_state", lang, state=whole_state, examples=", ".join(STATES[whole_state][1]))
            else:
                answer = t("location_not_found" if requested else "location_default", lang, place=requested or "")
            return self._reply(req, answer, meta={"location_found": False, "needs_place": True})

        report = self.weather_tool.get_weather_for_district(place.name, language=lang, place=place)
        # Spray / irrigation advice only when the question (or, for a reply like "Sangrur", the question
        # it answers) mentions it
        topics = weather_topics(f"{req.query} {req.intent.follow_up_of or ''}")
        summary = t(
            "weather_summary", lang, place=report.district, temp=report.temperature_c,
            humidity=report.relative_humidity, wind=report.wind_speed_kmh, rain=report.rain_probability_pct,
        )
        parts = [f"### {t('weather_advisory_title', lang)}: {report.district}\n\n{summary}"]
        if "spray" in topics:
            parts.append(f"**{t('spray_advisory', lang)}:**\n{report.spray_recommendation}")
        if "irrigation" in topics:
            parts.append(f"**{t('irrigation_advice', lang)}:**\n{report.irrigation_advisory}")
        answer = "\n\n".join(parts)
        citations = [report.source_notice] + (["ICAR Agromet Advisory Guidelines"] if topics else [])
        return self._reply(
            req, answer, citations=citations, audio_output_path=self._speak(req, answer),
            weather_report=report.model_dump(),
            meta={"district": report.district, "district_from_profile": from_profile, "location_found": True,
                  "is_live_weather": report.is_live},
        )

    def _answer_market(self, req: "Request") -> GroundedAnswer:
        """MSP from the government table plus the latest mandi prices (numbers only from the data,
        never the LLM). Mandi prices need a place: with none known, the farmer is asked."""
        lang, intent, profile = req.lang, req.intent, req.profile
        msp_data = load_msp()
        commodity = detect_commodity(req.query) or (detect_commodity(intent.follow_up_of) if intent.follow_up_of else None)
        if not commodity and profile and len(profile.crops) == 1:
            commodity = detect_commodity(profile.crops[0])  # "What is today's rate?" -> the farmer's crop
        district = intent.detected_district or (profile.district if profile and profile.district else None)
        meta = {
            "answer_source": "market_tool", "detected_topic": "Market prices", "district": district,
            # a place from the farm profile is not carried over, so a changed profile district is used next time
            "district_from_profile": bool(district and not intent.detected_district),
        }

        def crop_name(key: str) -> str:
            if key in COVERED_CROPS:
                return t(f"crop_{key}", lang)
            return msp_data["crops"].get(key, {}).get("name", key.title())

        if not commodity:
            crops = ", ".join(crop_name(k) for k in msp_data["crops"])
            return self._reply(req, t("market_which_crop", lang, crops=crops), meta=meta)

        meta["detected_crop"] = commodity.title()
        parts, citations = [], []
        msp = msp_data["crops"].get(commodity)
        if msp:
            parts.append(t("market_msp", lang, crop=crop_name(commodity), season=msp["season"], price=f"{msp['msp']:,}"))
            if msp.get("variants"):
                variants = ", ".join(f"{name} Rs {price:,}" for name, price in msp["variants"].items())
                parts.append(t("market_msp_variants", lang, variants=variants))
            if msp.get("previous"):
                parts.append(t("market_msp_previous", lang, season=msp["previous"]["season"],
                               price=f"{msp['previous']['msp']:,}"))
            citations.append(msp_data["source"])
        else:
            parts.append(t("market_no_msp", lang, crop=crop_name(commodity)))

        # A state named on its own ("wheat price in Punjab") asks for the state average
        whole_state = state_named(district) if district else None
        if whole_state:
            state, district = whole_state, None
        else:
            state = state_for(district, self.weather_tool.resolve_place) if district else None

        if not state:
            if district:
                parts.append("\n" + t("market_place_unknown", lang, place=district))
                meta["mandi_error"] = f"place not found: {district}"
            else:
                parts.append("\n" + t("market_ask_place", lang))
                meta["mandi_error"] = "no place given"
                meta["needs_place"] = True  # the farmer's next message is taken as the place
        else:
            lookup = self.mandi.latest(commodity, state=state, district=district)
            if lookup.prices:
                parts.append("\n" + t("market_mandi_header", lang, crop=crop_name(commodity), date=lookup.prices[0].date))
                parts += [
                    t("market_mandi_row", lang, market=p.market, district=p.district, modal=f"{p.modal_price:,.0f}",
                      low=f"{p.min_price:,.0f}", high=f"{p.max_price:,.0f}")
                    if p.min_price is not None else
                    t("market_avg_row", lang, date=p.date, price=f"{p.modal_price:,.0f}", place=p.market)
                    for p in lookup.prices
                ]
                if district and not lookup.local:
                    parts.append(t("market_state_fallback", lang, district=district, state=state))
                citations.append(lookup.source or "Agmarknet daily mandi prices")
                meta["mandi_local"] = lookup.local
            else:
                parts.append("\n" + t("market_mandi_unavailable", lang))
                meta["mandi_error"] = lookup.error

        return self._reply(
            req, "\n".join(parts), meta=meta, citations=citations,
            safety_disclaimers=[t("market_disclaimer", lang, date=msp_data["last_verified"])],
        )

    def _answer_scheme(self, req: "Request") -> GroundedAnswer:
        """Scheme answer from the checked official text (PM-KISAN, PMFBY crop insurance, Kisan Credit
        Card), with rule-based PM-KISAN eligibility from the profile. Other schemes are referred to their
        official website; "which schemes?" lists the ones covered."""
        lang, topic = req.lang, req.intent.detected_topic or ""
        if topic.startswith(OTHER_SCHEME_PREFIX):
            name = topic[len(OTHER_SCHEME_PREFIX):]
            site = next(site for other, _, site in OTHER_SCHEMES if other == name)
            return self._reply(req, t("scheme_not_covered", lang, name=name, site=site,
                                      covered=", ".join(self.schemes)), meta={"detected_topic": None})
        guide = self.schemes.get(topic)
        if guide is None:
            return self._reply(req, t("scheme_which", lang, covered=", ".join(self.schemes)),
                               meta={"detected_topic": None})
        sections = guide.select_sections(" ".join(filter(None, [req.intent.follow_up_of, req.query])))
        context = guide.as_context(sections)
        if guide.name != PM_KISAN:
            return self._answer_other_scheme(req, guide, sections, context)

        # Eligibility is decided by fixed rules, never by the LLM
        status, reasons, may_be_withheld = check_eligibility(req.profile)
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

        notes = [req.profile.summary()] if req.profile and not req.profile.is_empty() else []
        if status != "needs_info":
            notes.append(f"Rule-based PM-KISAN eligibility check from the profile: {status.replace('_', ' ')} "
                         "(already shown to the farmer; do not contradict it).")
        draft, source = self.synthesizer.generate(
            req.query, context, language=req.llm_language, history=req.history, context_note=" ".join(notes),
        )
        if source != "llm":
            draft = guide.offline_answer(sections, lang)  # stored official text in the farmer's language

        is_grounded, score = self.guardrails.validate_grounding(draft, [c.text for c in context])
        return self._reply(
            req, f"{eligibility_text}\n\n{draft}" if eligibility_text else draft,
            citations=[guide.citation],
            retrieved_chunks=context,
            is_grounded=is_grounded or source != "llm",
            safety_disclaimers=[t("scheme_disclaimer", lang, date=guide.data["last_verified"])],
            meta={"answer_source": source, "detected_topic": PM_KISAN, "pmk_eligibility": status,
                  "grounding_score": score, "top_section": sections[0]["title"]},
        )

    def _answer_other_scheme(self, req: "Request", guide: SchemeGuide, sections, context) -> GroundedAnswer:
        """PMFBY or Kisan Credit Card: the checked official text (no eligibility rules: the bank or the
        insurance company decides)."""
        notes = [req.profile.summary()] if req.profile and not req.profile.is_empty() else []
        draft, source = self.synthesizer.generate(
            req.query, context, language=req.llm_language, history=req.history, context_note=" ".join(notes),
        )
        if source != "llm":
            draft = guide.offline_answer(sections, req.lang)  # stored official text in the farmer's language
        is_grounded, score = self.guardrails.validate_grounding(draft, [c.text for c in context])
        site = guide.data.get("official_site")
        disclaimer = (t("scheme_disclaimer_general", req.lang, site=site, date=guide.data["last_verified"]) if site
                      else t("scheme_disclaimer_bank", req.lang, date=guide.data["last_verified"]))
        return self._reply(
            req, draft,
            citations=[guide.citation],
            retrieved_chunks=context,
            is_grounded=is_grounded or source != "llm",
            safety_disclaimers=[disclaimer],
            meta={"answer_source": source, "detected_topic": guide.name, "grounding_score": score,
                  "top_section": sections[0]["title"]},
        )

    def _answer_crop(self, req: "Request") -> GroundedAnswer:
        """Crop, pest and pesticide questions: hybrid search of the verified advisories, a grounded
        answer, then safety guardrails and a grounding check."""
        intent, profile = req.intent, req.profile
        # No crop named or carried over: use the farmer's crop if their profile lists exactly one we cover
        if not intent.detected_crop and profile:
            covered = [c for c in profile.crops if c.lower() in COVERED_CROPS]
            if len(covered) == 1:
                intent.detected_crop = covered[0].title()
        # "Should I spray again?" with no crop or problem to go on: ask, rather than show some advisory
        if (not intent.detected_crop and intent.detected_topic in (None, "Agronomy/General")
                and not intent.follow_up_of and asks_repeat_spray(req.query.lower())):
            return self._reply(req, t("spray_ask_crop", req.lang), meta={"needs_crop": True})

        # Add the crop and pest (detected, or carried over from an earlier turn) so that short
        # follow-ups like "what is the dose?" still retrieve the right advisory
        context_terms = [
            term for term in (intent.detected_crop, intent.detected_topic)
            if term and term != "Agronomy/General" and term.lower() not in req.query.lower()
        ]
        if intent.follow_up_of:
            # "Is it dangerous?" alone matches nothing; with the earlier question it finds the right advisory
            context_terms.append(intent.follow_up_of)
        # Our checked advisories answer the topics they cover (and symptom descriptions); PAU's chapters
        # answer the topics the router sends there. (Searching both for every question let PAU's English
        # text win Hindi/Punjabi symptom questions our advisories answer: see evalset/pau/README.md.)
        kind = "pau" if intent.use_pau else ("advisory" if self.pau_indexed else None)
        search = " ".join(context_terms + [req.query])
        if intent.use_pau and not req.query.isascii() and context_terms:
            # PAU's book is in English: Gurmukhi/Devanagari words only add noise to its search, so
            # search with the crop and topic in English ("Cotton thrips")
            search = " ".join(context_terms)
        # A PAU answer comes from the farmer's crop's chapter (or the general spraying chapter)
        retrieved = self.retriever.retrieve(search, kind=kind, crop=intent.detected_crop if intent.use_pau else None)
        if intent.detected_crop:
            # Equal fusion scores (e.g. wheat vs mustard aphid) must not put another crop first
            # ("Paddy" is the crop "Paddy (Rice)"; the ranked sections stay ahead of the extra chunks that complete them)
            crop = intent.detected_crop.lower()
            retrieved.sort(key=lambda c: (bool(c.rank_details.get("same_section_as_above")),
                                          not (c.crop or "").lower().startswith(crop)))

        if hasattr(self.synthesizer, "generate"):
            draft, source = self.synthesizer.generate(
                req.query, retrieved, language=req.llm_language, history=req.history,
                context_note=profile.summary() if profile else "",
            )
        else:
            draft, source = self.synthesizer.synthesize(req.query, retrieved, language=req.llm_language), "unknown"

        answer, disclaimers = self.guardrails.enforce_safety(draft, req.query, language=req.lang)
        is_grounded, grounding_score = self.guardrails.validate_grounding(answer, [c.text for c in retrieved])
        # The land size in My farm: every per-acre amount also as a total for the farm (worked out in code)
        acres = profile.land_acres if profile else None
        answer, dose_totals = scale_doses(answer, acres, req.lang) if acres else (answer, False)
        audio = self._speak(req, answer) if settings.ENABLE_TTS else None
        return self._reply(
            req, answer,
            citations=list(dict.fromkeys(c.citation for c in retrieved)),
            retrieved_chunks=retrieved,
            is_grounded=is_grounded,
            safety_disclaimers=disclaimers,
            audio_output_path=audio,
            meta={
                "grounding_score": grounding_score,
                "detected_crop": intent.detected_crop,
                "detected_topic": intent.detected_topic,
                "router_confidence": intent.confidence,
                "router_reasoning": intent.reasoning,
                "top_section": retrieved[0].section if retrieved else None,
                "answer_source": source,
                "knowledge": retrieved[0].kind if retrieved else (kind or "advisory"),
                "dose_totals_for_acres": acres if dose_totals else None,
            },
        )
