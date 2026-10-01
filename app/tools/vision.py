"""Crop photo diagnosis with Gemini Vision.

Gemini only *identifies* what the photo shows (crop, likely disease or pest, visible symptoms,
confidence). Treatment and doses always come from the verified ICAR/PAU/CIBRC advisories via
the normal retrieval + grounding pipeline, never from the vision model.
"""

import io
import json
from typing import List, Literal, Optional, Tuple

from pydantic import BaseModel, Field

from app.config import settings
from app.crops import COVERED_CROPS as SHARED_COVERED_CROPS

# Crops our verified advisories cover (the vision model's "crop" field uses these keys)
COVERED_CROPS = set(SHARED_COVERED_CROPS)
MAX_SIDE_PX = 1024  # photos are shrunk before sending: faster, cheaper, enough detail for leaves

LANGUAGE_NAMES = {"en": "English", "pa": "Punjabi (Gurmukhi script)", "hinglish": "Hinglish (Hindi in Roman letters)", "hi": "Hindi (Devanagari script)"}

PROMPT = """You are an agricultural plant-health assistant for Indian farmers. Look at this photo{question_part}.

Identify ONLY what you can see. Do not recommend any treatment, pesticide or dose.
Return JSON with exactly these keys:
- "is_plant": true if the photo shows a crop plant, leaf, stem, grain or pest on a plant; otherwise false.
- "crop": one of "wheat", "mustard", "paddy", "cotton", "other", "unknown".
- "crop_name": the crop in plain English (e.g. "wheat", "tomato"), or "unknown".
- "problem": the single most likely disease, pest or disorder in plain English (e.g. "yellow rust",
  "aphids", "bacterial leaf blight", "pink bollworm"), or "healthy", or "unknown" if you cannot tell.
- "confidence": "high", "medium" or "low".
- "visible_symptoms": one or two short sentences in English describing what you see.
- "summary_local": the same one or two sentences written in {language}.
- "other_possibilities": up to two other likely problems in plain English (may be empty).
Be honest: if the photo is blurry, too far away or ambiguous, use low confidence or "unknown"."""


class Diagnosis(BaseModel):
    is_plant: bool = False
    crop: Literal["wheat", "mustard", "paddy", "cotton", "other", "unknown"] = "unknown"
    crop_name: str = "unknown"
    problem: str = "unknown"
    confidence: Literal["high", "medium", "low"] = "low"
    visible_symptoms: str = ""
    summary_local: str = ""
    other_possibilities: List[str] = Field(default_factory=list)

    @property
    def covered(self) -> bool:
        """True if our verified advisories cover this crop."""
        return self.crop in COVERED_CROPS

    @property
    def identified(self) -> bool:
        return self.problem.strip().lower() not in ("", "unknown", "healthy")


def prepare_image(image_bytes: bytes) -> Tuple[bytes, str]:
    """Shrink the photo (longest side 1024 px) and re-encode as JPEG; fall back to the original bytes."""
    try:
        from PIL import Image, ImageOps

        with Image.open(io.BytesIO(image_bytes)) as img:
            img = ImageOps.exif_transpose(img).convert("RGB")  # respect phone rotation
            img.thumbnail((MAX_SIDE_PX, MAX_SIDE_PX))
            out = io.BytesIO()
            img.save(out, format="JPEG", quality=85)
            return out.getvalue(), "image/jpeg"
    except Exception:
        return image_bytes, "image/jpeg"


class CropVision:
    """Gemini Vision diagnosis with the same main/backup models as text answers."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key if api_key is not None else settings.GEMINI_API_KEY
        self.models = [m for m in (settings.GEMINI_MODEL, settings.GEMINI_FALLBACK_MODEL) if m]
        self.last_error: Optional[str] = None

    def is_available(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    def diagnose(self, image_bytes: bytes, question: str = "", language: str = "en") -> Optional[Diagnosis]:
        """Return a Diagnosis, or None if the vision service could not be reached (see last_error)."""
        self.last_error = None
        if not self.is_available():
            self.last_error = "GEMINI_API_KEY is not set"
            return None
        from google import genai
        from google.genai import types

        data, mime = prepare_image(image_bytes)
        prompt = PROMPT.format(
            question_part=f' sent with the question: "{question}"' if question else "",
            language=LANGUAGE_NAMES.get(language, "English"),
        )
        client = genai.Client(api_key=self.api_key, http_options=types.HttpOptions(timeout=30_000))
        for model in self.models:
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=[types.Part.from_bytes(data=data, mime_type=mime), prompt],
                    config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.1),
                )
                return parse_diagnosis(response.text)
            except Exception as e:
                self.last_error = f"{model}: {str(e)[:200]}"
                print(f"[Warning] Gemini Vision ({model}) failed: {str(e)[:200]}")
        return None


def parse_diagnosis(text: str) -> Diagnosis:
    """Parse the model's JSON, tolerating code fences and unexpected values."""
    cleaned = (text or "").strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    raw = json.loads(cleaned) if cleaned else {}
    if isinstance(raw, list):
        raw = raw[0] if raw else {}
    crop = str(raw.get("crop", "unknown")).lower().strip()
    confidence = str(raw.get("confidence", "low")).lower().strip()
    return Diagnosis(
        is_plant=bool(raw.get("is_plant", False)),
        crop=crop if crop in ("wheat", "mustard", "paddy", "cotton", "other") else "unknown",
        crop_name=str(raw.get("crop_name") or crop or "unknown"),
        problem=str(raw.get("problem") or "unknown"),
        confidence=confidence if confidence in ("high", "medium", "low") else "low",
        visible_symptoms=str(raw.get("visible_symptoms") or ""),
        summary_local=str(raw.get("summary_local") or raw.get("visible_symptoms") or ""),
        other_possibilities=[str(p) for p in (raw.get("other_possibilities") or [])][:2],
    )
