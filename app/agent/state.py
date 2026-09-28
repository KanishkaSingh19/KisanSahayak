from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

from app.rag.hybrid_retriever import RetrievalResult


class AgentQuery(BaseModel):
    query: str
    user_id: str = "farmer_default"
    language_hint: Optional[str] = None


class IntentResult(BaseModel):
    intent: Literal["crop_question", "general_agriculture", "safety_query", "weather", "out_of_scope", "greeting"]
    confidence: float
    detected_crop: Optional[str] = None
    detected_topic: Optional[str] = None
    detected_district: Optional[str] = None
    reasoning: str = ""


class GroundedAnswer(BaseModel):
    query: str
    intent: str
    answer: str
    citations: List[str]
    retrieved_chunks: List[RetrievalResult]
    is_grounded: bool
    safety_disclaimers: List[str] = Field(default_factory=list)
    audio_output_path: Optional[str] = None
    weather_report: Optional[Dict[str, Any]] = None
    detected_language: str = "hi"
    processing_metadata: Dict[str, Any] = Field(default_factory=dict)


class ConversationTurn(BaseModel):
    """One finished question/answer, kept so follow-up questions can reuse its context."""

    query: str
    answer: str
    intent: str
    crop: Optional[str] = None
    topic: Optional[str] = None
    district: Optional[str] = None

    @classmethod
    def from_answer(cls, answer: "GroundedAnswer") -> "ConversationTurn":
        meta = answer.processing_metadata
        return cls(
            query=answer.query,
            answer=answer.answer,
            intent=answer.intent,
            crop=meta.get("detected_crop"),
            topic=meta.get("detected_topic"),
            district=meta.get("district"),
        )
