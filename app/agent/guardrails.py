import re
import unicodedata
from typing import Dict, List, Tuple

from app.i18n import t

BANNED_PESTICIDES = [
    "endosulfan",
    "monocrotophos",
    "aldrin",
    "dieldrin",
    "chlordane",
    "ddt",
    "methyl parathion",
    "phorate",
    "paraquat",
]

# Hindi (Devanagari) and Punjabi (Gurmukhi) spellings farmers may type for the chemicals above
BANNED_PESTICIDE_ALIASES: Dict[str, List[str]] = {
    "monocrotophos": ["मोनोक्रोटोफॉस", "मोनोक्रोटोफोस", "ਮੋਨੋਕ੍ਰੋਟੋਫ਼ਾਸ", "ਮੋਨੋਕ੍ਰੋਟੋਫਾਸ"],
    "endosulfan": ["एंडोसल्फान", "एन्डोसल्फान", "ਐਂਡੋਸਲਫ਼ਾਨ", "ਐਂਡੋਸਲਫਾਨ"],
    "ddt": ["डीडीटी", "ਡੀਡੀਟੀ"],
    "phorate": ["फोरेट", "ਫੋਰੇਟ"],
    "paraquat": ["पैराक्वाट", "ਪੈਰਾਕੁਆਟ"],
}

STATUTORY_DISCLAIMER = t("statutory_disclaimer", "hi")


def _normalize(text: str) -> str:
    # NFC gives one encoding for letters like ਫ਼ / फ़ that can be typed two ways
    return unicodedata.normalize("NFC", text).lower()


class AgriculturalGuardrails:
    """Safety and grounding validator for agricultural responses."""

    def __init__(self, banned_list: List[str] = BANNED_PESTICIDES):
        self.banned_list = banned_list

    def check_banned_chemicals(self, text: str) -> Tuple[bool, List[str]]:
        """Detect banned or restricted chemicals, written in English, Hindi or Punjabi script."""
        found = []
        clean = _normalize(text)
        for chemical in self.banned_list:
            in_english = re.search(rf"\b{re.escape(chemical)}\b", clean)
            in_indic = any(_normalize(alias) in clean for alias in BANNED_PESTICIDE_ALIASES.get(chemical, []))
            if in_english or in_indic:
                found.append(chemical)
        return len(found) > 0, found

    def enforce_safety(self, draft_answer: str, user_query: str, language: str = "hi") -> Tuple[str, List[str]]:
        """Inspect both query and draft answer for safety violations; warnings are in `language`."""
        disclaimers: List[str] = []

        # 1. Check if user or draft mentions banned chemicals
        query_violation, q_chems = self.check_banned_chemicals(user_query)
        ans_violation, a_chems = self.check_banned_chemicals(draft_answer)

        all_chems = list(set(q_chems + a_chems))

        if "monocrotophos" in all_chems:
            disclaimers.append(t("monocrotophos_warning", language))

        if "endosulfan" in all_chems:
            disclaimers.append(t("endosulfan_warning", language))

        # Standard safety reminder for any chemical spray
        chemical_action_words = [
            "spray", "dose", "ml", "gram", "gm", "fungicide", "insecticide",
            "छिड़काव", "कीटनाशक", "ਛਿੜਕਾਅ", "ਕੀਟਨਾਸ਼ਕ", "chhidkaav", "keetnashak",
        ]
        if any(w in draft_answer.lower() for w in chemical_action_words):
            disclaimers.append(t("statutory_disclaimer", language))

        return draft_answer, disclaimers

    def validate_grounding(self, draft_answer: str, context_chunks: List[str]) -> Tuple[bool, float]:
        """Validate if key entities and claims in draft answer are grounded in context."""
        if not context_chunks:
            return False, 0.0

        full_context = " ".join(context_chunks).lower()
        answer_words = set(re.findall(r"\b[a-zA-Z]{4,}\b", draft_answer.lower()))

        if not answer_words:
            return True, 1.0

        matched_words = sum(1 for w in answer_words if w in full_context)
        grounding_ratio = matched_words / len(answer_words)

        is_grounded = grounding_ratio >= 0.35  # Grounded ratio threshold
        return is_grounded, round(grounding_ratio, 3)
