import time
from dataclasses import dataclass
from typing import List, Optional
from app.config import settings
from app.crops import COVERED_CROPS
from app.i18n import normalize_language, t
from app.agent.state import ConversationTurn, FarmerProfile, GroundedAnswer, IntentResult
from app.tools.schemes import OTHER_SCHEME_PREFIX, OTHER_SCHEMES, PM_KISAN, SchemeGuide, check_eligibility, load_schemes
from app.agent.router import IntentRouter, asks_repeat_spray, topic_search_terms, weather_topics
from app.agent.synthesizer import (SOURCE_LLM_DECLINED, SOURCE_NUMBERS_REPLACED, DeterministicGroundedSynthesizer,
                                   get_synthesizer)
from app.agent.guardrails import AgriculturalGuardrails, unbacked_numbers
from app.agent.claims import (CONTRADICTED, SUPPORTED, UNKNOWN_PRODUCT, UNKNOWN_PROBLEM, UNVERIFIED, check_claims,
                              localize_fact, unknown_disease_names, without_claims)
from app.agent.premises import (QUALIFIED, asserts_something, evidence_sentences, facts_for, get_premise_verifier,
                                judged_premises, premise_clause)
from app.rag.hybrid_retriever import HybridRetriever
from app.rag.ingest import load_knowledge_chunks
from app.speech.stt import WhisperSTTAdapter
from app.speech.tts import EdgeTTSAdapter
from app.tools.dose import scale_doses
from app.tools.location import STATES, state_named
from app.tools.market import MarketPriceService, detect_commodity, load_msp, state_for
from app.tools.vision import CropVision
from app.tools.weather_tool import AgWeatherTool

# The LLM starts its reply with this when the sources it was given do not answer the question (see the
# system prompt); the pipeline removes it and reports the answer as not verified
NOT_FOUND_MARKER = "[NOT_FOUND]"
# Answers that state no facts, so there is nothing to verify
NO_EVIDENCE_INTENTS = ("greeting", "out_of_scope", "empty", "error", "voice_stt_unavailable", "image_unavailable")


def strip_not_found(draft: str):
    """(the reply without the marker, whether the LLM said the sources do not answer the question)."""
    text = draft.lstrip()
    if text.startswith(NOT_FOUND_MARKER):
        return text[len(NOT_FOUND_MARKER):].lstrip(" :\n"), True
    return draft, False


def is_confident(results, keyword_only: bool = False) -> bool:
    """The meaning-based (dense) and keyword (BM25) searches both rank the top result first (or just
    keyword search, with `keyword_only`). On the labelled test questions, a top result they agree on
    was wrong 4 times in 54; one they disagree on, 12 times in 41."""
    main = [c for c in results if not c.rank_details.get("same_section_as_above")]
    if not main or main[0].rank_details.get("sparse_rank") != 1:
        return False
    return keyword_only or main[0].rank_details.get("dense_rank") == 1


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
        premise_verifier=None,
    ):
        # Checks assumptions stated in words ("Since MSP guarantees ..."); None without an LLM
        self.premise_verifier = premise_verifier or get_premise_verifier()
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

    def process_message(
        self,
        text: str = "",
        image_bytes: Optional[bytes] = None,
        audio: Optional[tuple] = None,
        language: Optional[str] = None,
        history: Optional[List[ConversationTurn]] = None,
        profile: Optional[FarmerProfile] = None,
    ) -> GroundedAnswer:
        """One message from the chat box: typed text, a voice note (audio bytes, filename) and a photo,
        in any combination. The voice note is transcribed and joined to the text; with a photo, both
        are the question about the photo."""
        text = (text or "").strip()
        transcript = ""
        if audio is not None:
            if not text and image_bytes is None:
                return self.process_audio_query(audio[0], filename=audio[1], language=language, generate_audio=False,
                                                history=history, profile=profile)
            ok, said = self.stt_adapter.transcribe_audio_bytes(audio[0], filename=audio[1], language=language)
            transcript = said.strip() if ok else ""  # the text or photo still carries the message
        question = " ".join(part for part in (text, transcript) if part)
        if image_bytes is not None:
            result = self.process_image_query(image_bytes, question=question, language=language, history=history,
                                              profile=profile)
        else:
            result = self.process_query(question, language=language, generate_audio=False, history=history,
                                        profile=profile)
        if transcript:
            result.processing_metadata["stt_transcript"] = transcript
        return result

    def process_image_query(
        self,
        image_bytes: bytes,
        question: str = "",
        language: Optional[str] = None,
        history: Optional[List[ConversationTurn]] = None,
        profile: Optional[FarmerProfile] = None,
    ) -> GroundedAnswer:
        """Diagnose a crop photo (see `_photo_answer`), with the answer's evidence and review status."""
        result = self._photo_answer(image_bytes, question, language, history, profile)
        return self._with_status(self._check_premises(question, result.detected_language, result))

    def _photo_answer(
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
        draft, not_found = strip_not_found(draft)
        meta["llm_not_found"] = not_found
        # Every number must come from the advisories (or what the photo model and farmer said)
        unbacked = self._unbacked(draft, source, [f"{c.text} {c.citation}" for c in retrieved] + [llm_query, summary],
                                  history, profile)
        if unbacked:
            draft, source = self._offline().synthesize(farmer_question, retrieved, language=lang), SOURCE_NUMBERS_REPLACED
        answer, disclaimers = self.guardrails.enforce_safety(f"{summary}\n\n{draft}", question, language=lang)
        is_grounded, score = self.guardrails.validate_grounding(draft, [c.text for c in retrieved])
        meta.update({
            "answer_source": source,
            "unbacked_numbers": unbacked,
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
            result = self._handler(intent.intent)(req)
            # Assumptions in the question are checked the same way whatever kind of answer it got
            return self._with_status(self._check_premises(clean_query, detected_lang, result))
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
        # A stated temperature or "it will rain" is checked against the live report
        checks = check_claims(req.query, [answer], [answer], weather=report.model_dump())
        answer = self._with_premise_notes(answer, checks, lang)
        citations = [report.source_notice] + (["ICAR Agromet Advisory Guidelines"] if topics else [])
        return self._reply(
            req, answer, citations=citations, audio_output_path=self._speak(req, answer),
            weather_report=report.model_dump(),
            meta={"district": report.district, "district_from_profile": from_profile, "location_found": True,
                  "is_live_weather": report.is_live, "claim_checks": self._claims_meta(checks),
                  "premise_evidence": [answer]},
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
            return self._reply(req, t("market_which_crop", lang, crops=crops), meta={**meta, "asks_back": True})

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

        answer = "\n".join(parts)
        # A stated price or MSP is checked against the MSP table and the mandi prices just fetched
        checks = check_claims(req.query, [answer], [answer])
        meta.update({"claim_checks": self._claims_meta(checks), "market_data": "Rs " in answer,
                     "premise_evidence": [answer]})
        return self._reply(
            req, self._with_premise_notes(answer, checks, lang), meta=meta, citations=citations,
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
                               meta={"detected_topic": None, "asks_back": True})
        sections = guide.select_sections(" ".join(filter(None, [req.intent.follow_up_of, req.query])))
        context = guide.as_context(sections)
        # Claims in the question are checked against the whole official text of the scheme, not only the
        # sections chosen for the answer ("₹12,000 per month ... how do I register?")
        checks = check_claims(req.query, [s["text"]["en"] for s in guide.data["sections"]],
                              [s["text"].get(lang, s["text"]["en"]) for s in guide.data["sections"]])
        if guide.name != PM_KISAN:
            return self._answer_other_scheme(req, guide, sections, context, checks)

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
            req.query, context, language=req.llm_language, history=req.history,
            context_note=" ".join(notes + [self._premise_note_for_llm(checks)]),
        )
        draft, not_found = strip_not_found(draft)
        unbacked = self._unbacked(draft, source, [f"{c.text} {c.citation}" for c in context] + notes
                                  + [without_claims(req.query)] + self._evidence_of(checks), req.history, req.profile)
        # The LLM declined although the question's own words matched official sections: show that text
        declined = not_found and guide.answers(" ".join(filter(None, [req.intent.follow_up_of, req.query])))
        if source != "llm" or unbacked or declined:
            draft = guide.offline_answer(sections, lang)  # stored official text in the farmer's language
            source = SOURCE_NUMBERS_REPLACED if unbacked else SOURCE_LLM_DECLINED if declined else source
            not_found = False

        is_grounded, score = self.guardrails.validate_grounding(draft, [c.text for c in context])
        answer = f"{eligibility_text}\n\n{draft}" if eligibility_text else draft
        return self._reply(
            req, self._with_premise_notes(answer, checks, lang),
            citations=[guide.citation],
            retrieved_chunks=context,
            is_grounded=is_grounded or source != "llm",
            safety_disclaimers=[t("scheme_disclaimer", lang, date=guide.data["last_verified"])],
            meta={"answer_source": source, "unbacked_numbers": unbacked, "detected_topic": PM_KISAN,
                  "pmk_eligibility": status, "claim_checks": self._claims_meta(checks), "llm_not_found": not_found,
                  "grounding_score": score, "top_section": sections[0]["title"],
                  "premise_evidence": [s["text"]["en"] for s in guide.data["sections"]]},
        )

    def _answer_other_scheme(self, req: "Request", guide: SchemeGuide, sections, context, checks) -> GroundedAnswer:
        """PMFBY or Kisan Credit Card: the checked official text (no eligibility rules: the bank or the
        insurance company decides)."""
        notes = [req.profile.summary()] if req.profile and not req.profile.is_empty() else []
        draft, source = self.synthesizer.generate(
            req.query, context, language=req.llm_language, history=req.history,
            context_note=" ".join(notes + [self._premise_note_for_llm(checks)]),
        )
        draft, not_found = strip_not_found(draft)
        unbacked = self._unbacked(draft, source, [f"{c.text} {c.citation}" for c in context]
                                  + [without_claims(req.query)] + self._evidence_of(checks), req.history, req.profile)
        declined = not_found and guide.answers(" ".join(filter(None, [req.intent.follow_up_of, req.query])))
        if source != "llm" or unbacked or declined:
            draft = guide.offline_answer(sections, req.lang)  # stored official text in the farmer's language
            source = SOURCE_NUMBERS_REPLACED if unbacked else SOURCE_LLM_DECLINED if declined else source
            not_found = False
        draft = self._with_premise_notes(draft, checks, req.lang)
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
            meta={"answer_source": source, "unbacked_numbers": unbacked, "detected_topic": guide.name,
                  "grounding_score": score, "claim_checks": self._claims_meta(checks), "llm_not_found": not_found,
                  "top_section": sections[0]["title"],
                  "premise_evidence": [s["text"]["en"] for s in guide.data["sections"]]},
        )

    @staticmethod
    def _unbacked(draft: str, source: str, given: List[str], history=None, profile=None) -> List[str]:
        """Numbers in an LLM answer that the text it was given does not state (empty when the answer is
        not from the LLM). `given` is the retrieved or official text and the question; earlier turns and
        the farm profile count too, since the LLM saw them."""
        if source != "llm":
            return []
        seen = list(given) + [f"{turn.query} {turn.answer}" for turn in (history or [])[-3:]]
        if profile and not profile.is_empty():
            seen.append(profile.summary())
        return unbacked_numbers(draft, seen)

    def _offline(self):
        """The template that writes answers from the checked text alone (no LLM)."""
        return getattr(self.synthesizer, "fallback", None) or DeterministicGroundedSynthesizer()

    # ------------------------------------------------------------------ claims in the question
    @staticmethod
    def _premise_note_for_llm(checks) -> str:
        """Tells the LLM which assumptions in the question the sources contradict, so it does not repeat
        them (the correction itself is added by the pipeline, from the source text)."""
        return " ".join(
            f'The farmer\'s question assumes "{c.claim}", but the sources say: "{c.evidence[0]}". '
            "A correction with the right figure is shown above your answer, so do not mention the farmer's "
            "figure, and do not accept it; just answer the rest of the question."
            for c in checks if c.status == CONTRADICTED and c.evidence
        )

    @staticmethod
    def _evidence_of(checks) -> List[str]:
        """The source sentences the checks quote: the LLM saw them, so their numbers are backed."""
        return [e for c in checks for e in c.evidence]

    @staticmethod
    def _with_premise_notes(answer: str, checks, lang: str) -> str:
        """`answer` with a note before it for every claim in the question that the evidence contradicts,
        could not confirm, or names a product the evidence does not recommend."""
        notes = []
        for c in checks:
            if c.status == CONTRADICTED:
                fact = localize_fact(c.evidence[0], [answer]) if c.evidence and c.fact == c.evidence[0] else c.fact
                notes.append(t("claim_corrected", lang, claim=c.claim, fact=fact.strip("* ")) if fact
                             else t("claim_contradicted_live", lang, claim=c.claim))
            elif c.status == UNVERIFIED:
                notes.append(t("claim_unverified", lang, claim=c.claim))
            elif c.status == UNKNOWN_PRODUCT:
                notes.append(t("claim_unknown_product", lang, name=c.claim))
        return "\n\n".join(notes + [answer]) if notes else answer

    @staticmethod
    def _claims_meta(checks) -> list:
        return [{"kind": c.kind, "claim": c.claim, "status": c.status, "evidence": c.evidence[:1]} for c in checks]

    def _check_premises(self, question: str, lang: str, result: GroundedAnswer) -> GroundedAnswer:
        """Assumptions stated in words ("Since MSP guarantees that the government will buy all my wheat")
        checked against the evidence the answer used plus the official statements on the question's topic
        (app/agent/premises.py). A contradicted or conditional premise gets a correction made of the cited
        official sentences before the answer; one the evidence does not cover is flagged as unverified."""
        meta = result.processing_metadata
        branch = meta.pop("premise_evidence", None) or [c.text for c in result.retrieved_chunks]
        if result.intent in NO_EVIDENCE_INTENTS or meta.get("asks_back") or not asserts_something(question):
            return result
        facts = facts_for(question)
        evidence = evidence_sentences([f["text"]["en"] for f in facts] + branch)
        raw = None
        if self.premise_verifier is not None and evidence:
            try:
                raw = self.premise_verifier.verify(question, evidence)
            except Exception as e:  # the check must never break an answer
                print(f"[Warning] Premise check failed: {str(e)[:120]}")
        checks = meta.setdefault("claim_checks", [])
        if raw is None:  # no verifier answered (offline, quota): the premise is not passed as verified
            return self._premise_unchecked(question, lang, result, facts, checks)
        judged = judged_premises(question, raw, evidence, already=[c["claim"] for c in checks])
        local = {f["text"]["en"]: f["text"].get(lang, f["text"]["en"]) for f in facts}
        notes, used = [], set()
        for j in judged:
            cited = [evidence[n - 1] for n in j["cited"]]
            if j["verdict"] in (CONTRADICTED, QUALIFIED):
                fact = " ".join(local.get(s) or localize_fact(s, [result.answer]) for s in cited)
                notes.append(t("claim_corrected", lang, claim=j["claim"], fact=fact.strip("* ")))
                used |= {f["source"] for f in facts if f["text"]["en"] in cited}
            elif j["verdict"] == "not_in_evidence":
                notes.append(t("claim_unverified", lang, claim=j["claim"]))
            status = {"not_in_evidence": UNVERIFIED, "supported": SUPPORTED}.get(j["verdict"], j["verdict"])
            checks.append({"kind": "premise", "claim": j["claim"], "status": status, "evidence": cited[:2]})
        if notes:
            result.answer = "\n\n".join(notes + [result.answer])
            result.citations = list(dict.fromkeys(result.citations + sorted(used)))
        meta["premise_checked"] = True
        return result

    @staticmethod
    def _premise_unchecked(question: str, lang: str, result: GroundedAnswer, facts, checks) -> GroundedAnswer:
        """No verifier could judge the premise. Unless a form-based check already handled a claim in the
        question, the premise is marked unverified, with the official statements on its topic if any."""
        clause = premise_clause(question)
        if checks or len(clause.split()) < 2:
            return result
        if facts:
            note = t("premise_unchecked", lang, claim=clause,
                     facts=" ".join(f["text"].get(lang, f["text"]["en"]) for f in facts))
            result.citations = list(dict.fromkeys(result.citations + [f["source"] for f in facts]))
        else:
            note = t("claim_unverified", lang, claim=clause)
        checks.append({"kind": "premise", "claim": clause, "status": UNVERIFIED, "evidence": []})
        result.answer = f"{note}\n\n{result.answer}"
        return result

    # ------------------------------------------------------------------ statuses shown with the answer
    def _with_status(self, result: GroundedAnswer) -> GroundedAnswer:
        """Sets three separate statuses: whether the facts are backed by an authoritative source, which
        kind of source, and whether a KVK expert should review the answer. "Verified" needs evidence
        that answers this question, not merely some related text that was retrieved."""
        from app.review import review_reasons

        meta = result.processing_metadata
        checks = meta.get("claim_checks") or []
        kinds = {c.kind for c in result.retrieved_chunks if not c.rank_details.get("same_section_as_above")}
        if result.intent == "weather":
            source = "live_weather" if result.weather_report else None
        elif result.intent == "market_price":
            source = "market_data" if meta.get("market_data") else None
        elif result.intent == "scheme_query":
            source = "scheme" if result.retrieved_chunks else None
        else:
            source = (result.retrieved_chunks[0].kind if result.retrieved_chunks else None) if kinds else None

        # Asking for a place states no facts, unless the answer already gives the MSP or corrects a premise
        stated = meta.get("market_data") or any(c["status"] in (CONTRADICTED, QUALIFIED) for c in checks)
        if (result.intent in NO_EVIDENCE_INTENTS or (meta.get("needs_place") and not stated) or meta.get("needs_crop")
                or meta.get("asks_back")):
            status = "not_applicable"
        elif (result.intent in ("crop_not_covered", "topic_not_covered") or meta.get("llm_not_found")
              or any(c["status"] == UNKNOWN_PROBLEM for c in checks) or source is None):
            status = "not_verified"
        else:
            weak = (
                (meta.get("answer_source") == "llm" and not result.is_grounded)
                or meta.get("retrieval") == "low_confidence"
                or any(c["status"] in (UNVERIFIED, UNKNOWN_PRODUCT) for c in checks)
                or (meta.get("vision") or {}).get("confidence") not in (None, "high")
            )
            status = "partially_verified" if weak else "verified"
        result.evidence_status, result.source_type = status, source
        statuses = {c["status"] for c in checks}
        result.premise_status = ("corrected" if statuses & {CONTRADICTED, QUALIFIED}
                                 else "unverified" if statuses & {UNVERIFIED, UNKNOWN_PROBLEM, UNKNOWN_PRODUCT}
                                 else "none")
        result.review_status = "recommended" if review_reasons(result) else "not_required"
        return result

    def _search(self, req: "Request", search: str, kind: Optional[str]) -> List:
        intent = req.intent
        # A PAU answer comes from the farmer's crop's chapter (or the general spraying chapter)
        retrieved = self.retriever.retrieve(search, kind=kind, crop=intent.detected_crop if intent.use_pau else None)
        if intent.detected_crop:
            # Equal fusion scores (e.g. wheat vs mustard aphid) must not put another crop first
            # ("Paddy" is the crop "Paddy (Rice)"; the ranked sections stay ahead of the extra chunks that complete them)
            crop = intent.detected_crop.lower()
            retrieved.sort(key=lambda c: (bool(c.rank_details.get("same_section_as_above")),
                                          not (c.crop or "").lower().startswith(crop)))
        return retrieved

    @staticmethod
    def _names_the_question(req: "Request", retrieved) -> bool:
        """The top advisory is titled for the pest the question names, on the crop it names ("aphids in
        mustard" -> "Mustard Aphid (Chetpa/Mahu) Management")."""
        topic, crop = req.intent.detected_topic, req.intent.detected_crop
        main = [c for c in retrieved if not c.rank_details.get("same_section_as_above")]
        if not (main and topic and crop) or topic in ("Agronomy/General",):
            return False
        return topic.lower() in main[0].section.lower() and main[0].crop.lower().startswith(crop.lower())

    def _search_with_check(self, req: "Request", search: str, kind: Optional[str]):
        """Search, check the result, and correct it once if it looks unreliable.

        Returns (results, "confident" | "corrected" | "low_confidence"). The top result is trusted when
        the meaning-based and keyword searches both rank it first. Otherwise the search is repeated with
        the crop and the topic's English words ("ਕਣਕ ਨੂੰ ਪਾਣੀ ਕਦੋਂ ਲਾਈਏ?" -> "Wheat irrigation"), and that
        result is used only if both searches agree on it. If not, the first answer stands and is sent
        to KVK expert review (see app/review.py).
        """
        retrieved = self._search(req, search, kind)
        if is_confident(retrieved) or self._names_the_question(req, retrieved):
            return retrieved, "confident"
        terms = topic_search_terms(req.query.lower().strip())
        retry = " ".join(filter(None, [req.intent.detected_crop, terms]))
        if terms and retry.strip().lower() != search.strip().lower():
            corrected = self._search(req, retry, kind)
            # The retry is plain English topic words, where keyword search is the reliable one
            if is_confident(corrected, keyword_only=True):
                return corrected, "corrected"
        return retrieved, "low_confidence"

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
        retrieved, retrieval = self._search_with_check(req, search, kind)

        # Claims in the question, checked against what was retrieved. A disease the evidence does not
        # mention gets no treatment (the nearest advisory would be about something else)
        # (a pest or disease the router recognised is known, so only other names are checked)
        known_pest = bool(intent.detected_topic) and not intent.use_pau and intent.detected_topic != "Agronomy/General"
        checks = check_claims(req.query, [c.text for c in retrieved], check_names=intent.intent != "safety_query",
                              check_diseases=not known_pest)
        unknown = [c for c in checks if c.status == UNKNOWN_PROBLEM]
        if unknown:
            # Only a name the whole knowledge base for this crop never mentions is unknown: a synonym or a
            # spelling the retrieved text lacks ("stripe rust", PAU's "Parawilt") is not refused
            crop = (intent.detected_crop or "").lower()
            known = " ".join(c.text for c in self.retriever.dense_retriever.chunks
                             if str(c.metadata.get("crop", "")).lower().startswith(crop))
            if not unknown_disease_names(req.query, known):
                checks = [c for c in checks if c.status != UNKNOWN_PROBLEM]
                unknown = []
        if unknown:
            return self._reply(
                req, t("claim_unknown_problem", req.lang, name=unknown[0].claim),
                meta={"detected_crop": intent.detected_crop, "detected_topic": unknown[0].claim,
                      "claim_checks": self._claims_meta(checks), "retrieval": retrieval},
            )

        if hasattr(self.synthesizer, "generate"):
            draft, source = self.synthesizer.generate(
                req.query, retrieved, language=req.llm_language, history=req.history,
                context_note=" ".join(filter(None, [profile.summary() if profile else "",
                                                    self._premise_note_for_llm(checks)])),
            )
        else:
            draft, source = self.synthesizer.synthesize(req.query, retrieved, language=req.llm_language), "unknown"
        draft, not_found = strip_not_found(draft)
        # Every number must come from the sources: an LLM answer with any other number is replaced (the
        # farmer's own claimed amounts do not count as a source)
        unbacked = self._unbacked(draft, source, [f"{c.text} {c.citation}" for c in retrieved]
                                  + [without_claims(req.query), req.intent.follow_up_of or ""] + self._evidence_of(checks),
                                  req.history, profile)
        if unbacked:
            draft, source = self._offline().synthesize(req.query, retrieved, language=req.llm_language), SOURCE_NUMBERS_REPLACED
            not_found = False

        answer, disclaimers = self.guardrails.enforce_safety(draft, req.query, language=req.lang)
        is_grounded, grounding_score = self.guardrails.validate_grounding(answer, [c.text for c in retrieved])
        # The land size in My farm: every per-acre amount also as a total for the farm (worked out in code)
        acres = profile.land_acres if profile else None
        answer, dose_totals = scale_doses(answer, acres, req.lang) if acres else (answer, False)
        answer = self._with_premise_notes(answer, checks, req.lang)
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
                "unbacked_numbers": unbacked,
                "knowledge": retrieved[0].kind if retrieved else (kind or "advisory"),
                "dose_totals_for_acres": acres if dose_totals else None,
                "retrieval": retrieval,
                "claim_checks": self._claims_meta(checks),
                "llm_not_found": not_found,
            },
        )
