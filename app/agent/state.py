from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

from app.rag.hybrid_retriever import RetrievalResult


class AgentQuery(BaseModel):
    query: str
    user_id: str = "farmer_default"
    language_hint: Optional[str] = None


class FarmerProfile(BaseModel):
    """Optional details a farmer shares to personalise answers. Kept only in their browser session."""

    district: Optional[str] = Field(None, max_length=80)
    crops: List[str] = Field(default_factory=list, description="e.g. ['wheat', 'mustard']")
    land_acres: Optional[float] = Field(None, ge=0, le=100000)
    owns_land: Optional[bool] = Field(None, description="Is cultivable land recorded in the family's name?")
    # PM-KISAN exclusion categories (see pmkisan.gov.in); None = not answered
    income_tax_payer: Optional[bool] = None
    government_employee: Optional[bool] = Field(None, description="Serving/retired govt or PSE employee, not MTS/Class IV/Group D")
    pension_10k_or_more: Optional[bool] = Field(None, description="Monthly pension of Rs 10,000 or more (not MTS/Class IV/Group D)")
    registered_professional: Optional[bool] = Field(None, description="Practising doctor, engineer, lawyer, CA or architect")
    constitutional_post: Optional[bool] = Field(None, description="Present/former constitutional post, minister, MP/MLA/MLC, mayor or district panchayat chair")
    institutional_landholder: Optional[bool] = None
    land_acquired_after_feb_2019: Optional[bool] = None

    def is_empty(self) -> bool:
        return not (self.district or self.crops or self.land_acres is not None or self.owns_land is not None)

    def summary(self) -> str:
        """One line of context for the LLM (no personal identifiers)."""
        parts = []
        if self.district:
            parts.append(f"district {self.district}")
        if self.crops:
            parts.append("grows " + ", ".join(self.crops))
        if self.land_acres is not None:
            parts.append(f"{self.land_acres:g} acres")
        return "Farmer profile: " + "; ".join(parts) + "." if parts else ""


class IntentResult(BaseModel):
    intent: Literal[
        "crop_question", "general_agriculture", "safety_query", "weather", "out_of_scope", "greeting", "scheme_query"
    ]
    confidence: float
    detected_crop: Optional[str] = None
    detected_topic: Optional[str] = None
    detected_district: Optional[str] = None
    follow_up_of: Optional[str] = None  # earlier question this one follows up on (added to the search)
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
    # True when the place came from the farm profile, not the question: such a place is not
    # carried over, so a changed profile district is used on the next question
    district_from_profile: bool = False

    @classmethod
    def from_answer(cls, answer: "GroundedAnswer") -> "ConversationTurn":
        meta = answer.processing_metadata
        topic = meta.get("detected_topic")
        if topic in (None, "Agronomy/General"):
            # The farmer described symptoms without naming the pest: remember the advisory
            # the answer actually used (e.g. "Yellow Rust ..."), so "Is it dangerous?" stays on it
            topic = meta.get("top_section") or topic
        return cls(
            query=answer.query,
            answer=answer.answer,
            intent=answer.intent,
            crop=meta.get("detected_crop"),
            topic=topic,
            district=meta.get("district"),
            district_from_profile=bool(meta.get("district_from_profile")),
        )
