"""KisanSahayak REST API (FastAPI).

Exposes the same KisanPipeline the Streamlit app uses, so other clients (mobile app,
WhatsApp bot, IVR) can ask questions, fetch weather and get spoken answers.

Run:   uvicorn app.api:app --port 8000
Docs:  http://localhost:8000/docs
"""

import json
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import Any, Dict, List, Literal, Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel, Field, ValidationError

from app.agent.pipeline import DEFAULT_WEATHER_DISTRICT, KisanPipeline
from app.agent.state import ConversationTurn, FarmerProfile, GroundedAnswer
from app.agent.synthesizer import GeminiSynthesizer, OpenAISynthesizer
from app.config import settings
from app.review import ReviewQueue

Language = Literal["en", "pa", "hinglish", "hi"]
MAX_HISTORY_TURNS = 20
MAX_AUDIO_BYTES = 10 * 1024 * 1024  # 10 MB voice note


@lru_cache(maxsize=1)
def get_pipeline() -> KisanPipeline:
    """One shared pipeline (loading MiniLM and the indices takes about a minute)."""
    return KisanPipeline()


@lru_cache(maxsize=1)
def get_review_queue() -> ReviewQueue:
    """Pesticide, uncertain and unanswered answers wait here for a KVK expert (see app/review.py)."""
    return ReviewQueue()


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_pipeline()  # load models at startup so the first request is fast
    yield


app = FastAPI(
    title="KisanSahayak API",
    description=(
        "Multilingual farming assistant: verified ICAR/PAU/CIBRC advice, live weather and "
        "voice, in English, Punjabi, Hinglish and Hindi."
    ),
    version="1.0.0",
    lifespan=lifespan,
)
# Public, read-only style API with no cookies or credentials, so any client may call it
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"], allow_headers=["*"])


# ----------------------------------------------------------------------------- models
class AskRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000, examples=["How to control aphids in mustard?"])
    language: Language = "en"
    history: List[ConversationTurn] = Field(
        default_factory=list,
        description="Earlier turns of this conversation (the `turn` field of previous responses), oldest first.",
    )
    profile: Optional[FarmerProfile] = Field(
        None, description="Optional farm details: district for weather, crops, and PM-KISAN eligibility answers"
    )


class Evidence(BaseModel):
    citation: str
    text: str
    score: float


class AskResponse(BaseModel):
    answer: str
    language: str
    intent: str
    answer_source: Optional[str] = Field(
        None, description="llm, template_offline, template_llm_failed or no_results"
    )
    is_grounded: bool
    citations: List[str]
    safety_disclaimers: List[str]
    detected_crop: Optional[str] = None
    detected_topic: Optional[str] = None
    district: Optional[str] = None
    weather: Optional[Dict[str, Any]] = None
    evidence: List[Evidence] = Field(default_factory=list)
    transcript: Optional[str] = Field(None, description="Voice requests only: what the farmer said")
    photo_diagnosis: Optional[Dict[str, Any]] = Field(None, description="Photo requests only: what the vision model saw")
    latency_ms: Optional[int] = None
    sent_for_review: Optional[str] = Field(
        None, description="Review-queue id when the answer was sent for KVK expert review (pesticide, uncertain, not covered)"
    )
    turn: ConversationTurn = Field(..., description="Append this to `history` for the next question")


class SpeakRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)
    language: Language = "en"


class HealthResponse(BaseModel):
    status: str
    knowledge_index_ready: bool
    llm: str
    speech_to_text: bool
    text_to_speech: Dict[str, Optional[str]]


def parse_profile(raw: str) -> Optional[FarmerProfile]:
    """Optional farm profile sent as a JSON form field (multipart endpoints)."""
    if not raw.strip():
        return None
    try:
        return FarmerProfile(**json.loads(raw))
    except (ValueError, TypeError, ValidationError):
        raise HTTPException(status_code=422, detail="profile must be a JSON farm profile object")


def to_response(result: GroundedAnswer, review_queue: Optional[ReviewQueue] = None) -> AskResponse:
    if review_queue is not None:
        try:
            review_queue.submit(result)
        except OSError as e:  # the review queue must never break an answer
            print(f"[Warning] Could not add answer to the review queue: {e}")
    meta = result.processing_metadata
    return AskResponse(
        answer=result.answer,
        language=result.detected_language,
        intent=result.intent,
        answer_source=meta.get("answer_source"),
        is_grounded=result.is_grounded,
        citations=result.citations,
        safety_disclaimers=result.safety_disclaimers,
        detected_crop=meta.get("detected_crop"),
        detected_topic=meta.get("detected_topic"),
        district=meta.get("district"),
        weather=result.weather_report,
        evidence=[Evidence(citation=c.citation, text=c.text, score=c.score) for c in result.retrieved_chunks],
        transcript=meta.get("stt_transcript"),
        photo_diagnosis=meta.get("vision"),
        latency_ms=meta.get("latency_ms"),
        sent_for_review=meta.get("kvk_review"),
        turn=ConversationTurn.from_answer(result),
    )


# ----------------------------------------------------------------------------- endpoints
@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/docs")


@app.get("/health", response_model=HealthResponse, tags=["system"])
def health(pipeline: KisanPipeline = Depends(get_pipeline)):
    """Which services are active: knowledge index, LLM, speech-to-text and text-to-speech."""
    if isinstance(pipeline.synthesizer, GeminiSynthesizer):
        llm = f"gemini:{settings.GEMINI_MODEL}"
    elif isinstance(pipeline.synthesizer, OpenAISynthesizer):
        llm = f"openai:{settings.OPENAI_MODEL}"
    else:
        llm = "offline-template"
    return HealthResponse(
        status="ok",
        knowledge_index_ready=pipeline.retriever.is_ready,
        llm=llm,
        speech_to_text=pipeline.stt_adapter.is_available(),
        text_to_speech={lang: pipeline.tts_adapter.engine_for(lang) for lang in ("en", "pa", "hinglish", "hi")},
    )


@app.post("/ask", response_model=AskResponse, tags=["advice"])
def ask(
    request: AskRequest,
    pipeline: KisanPipeline = Depends(get_pipeline),
    review_queue: ReviewQueue = Depends(get_review_queue),
):
    """Ask a crop, pest, pesticide-safety or weather question. Pass `history` for follow-up questions."""
    result = pipeline.process_query(
        request.query,
        language=request.language,
        generate_audio=False,
        history=request.history[-MAX_HISTORY_TURNS:],
        profile=request.profile,
    )
    return to_response(result, review_queue)


@app.post("/ask/image", response_model=AskResponse, tags=["advice"])
async def ask_image(
    image: UploadFile = File(..., description="Photo of the affected crop (jpg, png or webp), up to 10 MB"),
    question: str = Form("", max_length=1000, description="Optional question about the photo"),
    language: Language = Form("en"),
    history: str = Form("[]", description="JSON list of earlier `turn` objects"),
    profile: str = Form("", description="Optional JSON farm profile"),
    pipeline: KisanPipeline = Depends(get_pipeline),
    review_queue: ReviewQueue = Depends(get_review_queue),
):
    """Diagnose a crop photo with Gemini Vision; treatment comes from the verified advisories.
    `photo_diagnosis` in the response holds what the vision model saw."""
    try:
        turns = [ConversationTurn(**t) for t in json.loads(history)]
    except (ValueError, TypeError, ValidationError):
        raise HTTPException(status_code=422, detail="history must be a JSON list of turn objects")
    data = await image.read()
    if not data:
        raise HTTPException(status_code=422, detail="Empty image file")
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Image file is larger than 10 MB")
    result = pipeline.process_image_query(
        data, question=question, language=language, history=turns[-MAX_HISTORY_TURNS:], profile=parse_profile(profile)
    )
    return to_response(result, review_queue)


@app.post("/ask/voice", response_model=AskResponse, tags=["advice"])
async def ask_voice(
    audio: UploadFile = File(..., description="Voice note (wav, mp3, m4a or ogg), up to 10 MB"),
    language: Language = Form("en"),
    history: str = Form("[]", description="JSON list of earlier `turn` objects"),
    profile: str = Form("", description="Optional JSON farm profile"),
    pipeline: KisanPipeline = Depends(get_pipeline),
    review_queue: ReviewQueue = Depends(get_review_queue),
):
    """Ask by voice note: transcribed with Whisper, then answered like /ask."""
    try:
        turns = [ConversationTurn(**t) for t in json.loads(history)]
    except (ValueError, TypeError, ValidationError):
        raise HTTPException(status_code=422, detail="history must be a JSON list of turn objects")
    data = await audio.read()
    if not data:
        raise HTTPException(status_code=422, detail="Empty audio file")
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Audio file is larger than 10 MB")
    result = pipeline.process_audio_query(
        data,
        filename=audio.filename or "voice.wav",
        language=language,
        generate_audio=False,
        history=turns[-MAX_HISTORY_TURNS:],
        profile=parse_profile(profile),
    )
    return to_response(result, review_queue)


@app.get("/weather", tags=["weather"])
def weather(place: str = DEFAULT_WEATHER_DISTRICT, language: Language = "en", pipeline: KisanPipeline = Depends(get_pipeline)):
    """Current weather with spray and irrigation advice for any place in India."""
    found = pipeline.weather_tool.resolve_place(place)
    if found is None:
        raise HTTPException(status_code=404, detail=f"Place not found in India: {place}")
    report = pipeline.weather_tool.get_weather_for_district(found.name, language=language, place=found)
    return report.model_dump()


@app.post(
    "/speak",
    tags=["voice"],
    response_class=FileResponse,
    responses={200: {"content": {"audio/mpeg": {}}, "description": "MP3 audio"}},
)
def speak(request: SpeakRequest, pipeline: KisanPipeline = Depends(get_pipeline)):
    """Read text aloud (e.g. an answer from /ask) in the chosen language. Returns an MP3."""
    if not pipeline.tts_adapter.supports(request.language):
        raise HTTPException(status_code=422, detail=f"Spoken answers are not available for '{request.language}'")
    path = pipeline.tts_adapter.synthesize_speech(request.text, language=request.language)
    if path is None:
        raise HTTPException(status_code=503, detail="Speech service unavailable, please try again")
    return FileResponse(path, media_type="audio/mpeg", filename="kisansahayak_answer.mp3")
