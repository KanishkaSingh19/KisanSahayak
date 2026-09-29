"""Government scheme guidance (PM-KISAN), grounded in the official website's text.

Facts live in data/schemes/pm_kisan.json (checked against pmkisan.gov.in, date recorded in the
file), with every section written in all four languages so answers work without the LLM.
Eligibility is decided by fixed rules from the farmer profile, never by the LLM.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import List, Optional, Tuple

from app.agent.state import FarmerProfile
from app.config import settings
from app.rag.hybrid_retriever import RetrievalResult

SCHEME_FILE = settings.DATA_DIR / "schemes" / "pm_kisan.json"
DEFAULT_SECTIONS = ["benefit", "eligibility", "apply"]

# Profile field -> exclusion reason key in app.i18n (PM-KISAN exclusion categories)
EXCLUSIONS = [
    ("institutional_landholder", "pmk_reason_institutional"),
    ("constitutional_post", "pmk_reason_constitutional"),
    ("government_employee", "pmk_reason_government"),
    ("pension_10k_or_more", "pmk_reason_pension"),
    ("income_tax_payer", "pmk_reason_income_tax"),
    ("registered_professional", "pmk_reason_professional"),
]


@lru_cache(maxsize=1)
def load_scheme(path: Path = SCHEME_FILE) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _matches(keyword: str, text: str) -> bool:
    from app.agent.router import matches_keyword

    return matches_keyword(keyword, text)


class SchemeGuide:
    def __init__(self, data: Optional[dict] = None):
        self.data = data or load_scheme()
        self.sections = {s["id"]: s for s in self.data["sections"]}

    @property
    def citation(self) -> str:
        return f"{self.data['source']} ({self.data['source_url']}), checked {self.data['last_verified']}"

    def select_sections(self, query: str) -> List[dict]:
        """Sections whose keywords appear in the question, most matches first; a default set otherwise."""
        clean = query.lower()
        scored = []
        for section in self.data["sections"]:
            hits = sum(_matches(k, clean) for k in section["keywords"])
            if hits:
                scored.append((hits, section))
        scored.sort(key=lambda pair: -pair[0])
        chosen = [s for _, s in scored[:3]] or [self.sections[i] for i in DEFAULT_SECTIONS]
        return chosen

    def as_context(self, sections: List[dict]) -> List[RetrievalResult]:
        """Sections in English as retrieval results, so the LLM answers only from this text."""
        return [
            RetrievalResult(
                chunk_id=f"pm_kisan_{s['id']}", text=f"{s['title']}: {s['text']['en']}", score=1.0,
                citation=f"{self.citation} [{s['title']}]", source_agency=self.data["source"],
                crop="All Crops", section=s["title"],
            )
            for s in sections
        ]

    def offline_answer(self, sections: List[dict], language: str) -> str:
        """Answer from the stored translations when the LLM is unavailable."""
        lang = language if language in ("en", "pa", "hinglish", "hi") else "hi"
        return "\n\n".join(s["text"][lang] for s in sections)


def check_eligibility(profile: Optional[FarmerProfile]) -> Tuple[str, List[str], bool]:
    """PM-KISAN eligibility from the profile using the official exclusion categories.

    Returns (status, reason_keys, may_be_withheld) where status is "likely_eligible",
    "not_eligible" or "needs_info". Rule-based on purpose: no LLM decides eligibility.
    """
    if profile is None:
        return "needs_info", [], False
    reasons = [key for field, key in EXCLUSIONS if getattr(profile, field) is True]
    may_be_withheld = profile.land_acquired_after_feb_2019 is True
    if profile.owns_land is False:
        return "not_eligible", ["pmk_reason_no_land"] + reasons, may_be_withheld
    if reasons:
        return "not_eligible", reasons, may_be_withheld
    if profile.owns_land is True:
        return "likely_eligible", [], may_be_withheld
    return "needs_info", [], may_be_withheld
