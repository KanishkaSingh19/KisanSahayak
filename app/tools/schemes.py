"""Government scheme guidance (PM-KISAN, PMFBY crop insurance, Kisan Credit Card), grounded in
official text.

Facts live in data/schemes/*.json, one file per scheme, each checked against official sources (listed
in the file with the date checked), with every section written in all four languages so answers work
without the LLM. PM-KISAN eligibility is decided by fixed rules from the farmer profile, never by the LLM.
Other well-known schemes are recognised by name and referred to their official website.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import List, Optional, Tuple

from app.agent.state import FarmerProfile
from app.config import settings
from app.rag.hybrid_retriever import RetrievalResult

SCHEME_DIR = settings.DATA_DIR / "schemes"
SCHEME_FILE = SCHEME_DIR / "pm_kisan.json"
DEFAULT_SECTIONS = ["benefit", "eligibility", "apply"]
PM_KISAN = "PM-KISAN"
OTHER_SCHEME_PREFIX = "other scheme: "  # detected_topic for a scheme we have no checked guidance for

# Schemes farmers ask about that we have no checked guidance for: (name, words that name it, official site)
OTHER_SCHEMES = [
    ("Soil Health Card", ["soil health card", "soil card", "मृदा स्वास्थ्य कार्ड", "सॉइल हेल्थ कार्ड", "ਸੋਇਲ ਹੈਲਥ ਕਾਰਡ",
                          "ਮਿੱਟੀ ਸਿਹਤ ਕਾਰਡ"], "soilhealth.dac.gov.in"),
    ("PM-KISAN Maandhan pension", ["maandhan", "maan dhan", "mandhan", "मानधन", "ਮਾਨਧਨ"], "maandhan.in"),
    ("PM-KUSUM solar pump", ["kusum", "solar pump", "सोलर पंप", "ਸੋਲਰ ਪੰਪ"], "pmkusum.mnre.gov.in"),
    ("PM Krishi Sinchai Yojana (drip and sprinkler)", ["krishi sinchai", "pmksy", "per drop more crop", "drip subsidy",
                                                       "कृषि सिंचाई योजना", "ਖੇਤੀ ਸਿੰਚਾਈ ਯੋਜਨਾ"], "pmksy.gov.in"),
]

# Profile field -> exclusion reason key in app.i18n (PM-KISAN exclusion categories)
EXCLUSIONS = [
    ("institutional_landholder", "pmk_reason_institutional"),
    ("constitutional_post", "pmk_reason_constitutional"),
    ("government_employee", "pmk_reason_government"),
    ("pension_10k_or_more", "pmk_reason_pension"),
    ("income_tax_payer", "pmk_reason_income_tax"),
    ("registered_professional", "pmk_reason_professional"),
]


@lru_cache(maxsize=None)
def load_scheme(path: Path = SCHEME_FILE) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_schemes(scheme_dir: Path = SCHEME_DIR) -> dict:
    """{short name: scheme data} for every scheme file ("PM-KISAN", "PMFBY crop insurance", ...)."""
    schemes = {}
    for path in sorted(Path(scheme_dir).glob("*.json")):
        data = load_scheme(path)
        schemes[data.get("short_name", path.stem)] = data
    return schemes


def _longest_name(clean: str, names) -> int:
    return max((len(n) for n in names if _matches(n, clean)), default=0)


def detect_scheme(text: str, schemes: Optional[dict] = None) -> Optional[str]:
    """The covered scheme a message names; if names of several match, the longest match wins."""
    clean = text.lower()
    scored = [(_longest_name(clean, data.get("names", [])), name) for name, data in (schemes or load_schemes()).items()]
    best = max(scored, default=(0, None))
    return best[1] if best[0] else None


def detect_other_scheme(text: str) -> Optional[Tuple[str, str]]:
    """(name, official site) of a scheme we have no checked guidance for, if the message names one."""
    clean = text.lower()
    return next(((name, site) for name, words, site in OTHER_SCHEMES if any(_matches(w, clean) for w in words)), None)


def _matches(keyword: str, text: str) -> bool:
    from app.agent.router import matches_keyword

    return matches_keyword(keyword, text)


class SchemeGuide:
    def __init__(self, data: Optional[dict] = None):
        self.data = data or load_scheme()
        self.sections = {s["id"]: s for s in self.data["sections"]}
        self.name = self.data.get("short_name", PM_KISAN)
        self.key = self.name.split()[0].lower().replace("-", "_")  # "pm_kisan", "pmfby", "kisan"

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
        chosen = [s for _, s in scored[:3]] or [self.sections[i] for i in self.data.get("default_sections", DEFAULT_SECTIONS)]
        # Sections every answer needs ("PMFBY is not run in Punjab")
        always = [self.sections[i] for i in self.data.get("always_sections", []) if self.sections[i] not in chosen]
        return always + chosen

    def as_context(self, sections: List[dict]) -> List[RetrievalResult]:
        """Sections in English as retrieval results, so the LLM answers only from this text."""
        return [
            RetrievalResult(
                chunk_id=f"{self.key}_{s['id']}", text=f"{s['title']}: {s['text']['en']}", score=1.0,
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
