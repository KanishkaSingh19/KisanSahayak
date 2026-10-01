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


# ------------------------------------------------------------------ numbers in an LLM answer
# Doses, thresholds, intervals and amounts must come from the sources, never from the LLM: every number
# in an LLM answer has to appear in the text it was given (or the question). Harmless rewording is
# allowed: "second week" / "2nd week", "two sprays" / "2 sprays", "1.0 litre" / "1 litre", "२००" / "200",
# "2,000" / "2000".
_INDIC_DIGITS = str.maketrans("०१२३४५६७८९੦੧੨੩੪੫੬੭੮੯", "01234567890123456789")
_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "half": 0.5, "twice": 2, "once": 1,
}
_LIST_NUMBERING = re.compile(r"(?m)^\s*(?:[-*]\s*)?\d+[.)]\s+")  # "1. Manual control": formatting, not a fact
# Units, so "400 g" is not backed by "400 ml" (unit word -> one spelling)
_UNITS = {
    "g": "g", "gm": "g", "gram": "g", "grams": "g", "ग्राम": "g", "ਗ੍ਰਾਮ": "g",
    "kg": "kg", "kilo": "kg", "kilogram": "kg", "किलो": "kg", "किलोग्राम": "kg", "ਕਿਲੋ": "kg",
    "ml": "ml", "millilitre": "ml", "milliliter": "ml", "मिलीलीटर": "ml", "मिली": "ml", "ਮਿਲੀਲੀਟਰ": "ml", "ਮਿਲੀ": "ml",
    "l": "l", "litre": "l", "litres": "l", "liter": "l", "liters": "l", "लीटर": "l", "ਲੀਟਰ": "l",
    "%": "%", "percent": "%", "per cent": "%", "प्रतिशत": "%", "ਪ੍ਰਤੀਸ਼ਤ": "%",
    "day": "day", "days": "day", "din": "day", "दिन": "day", "ਦਿਨ": "day", "ਦਿਨਾਂ": "day",
    "week": "week", "weeks": "week", "hafte": "week", "सप्ताह": "week", "हफ्ते": "week", "ਹਫ਼ਤੇ": "week",
    "kg/acre": "kg", "g/acre": "g", "ml/acre": "ml",
}
_UNIT_PATTERN = "|".join(sorted((re.escape(u) for u in _UNITS), key=len, reverse=True))
# A number or a range ("80-125") and the unit after it, if any ("30-day" is 30 days)
_AMOUNT = re.compile(rf"(\d+(?:\.\d+)?)(?:\s*(?:-|to)\s*(\d+(?:\.\d+)?))?(?:\s*-?\s*({_UNIT_PATTERN})(?![\wऀ-੿]))?",
                     re.IGNORECASE)


def _clean_numbers(text: str) -> str:
    text = _LIST_NUMBERING.sub("", text.translate(_INDIC_DIGITS))
    return re.sub(r"(?<=\d),(?=\d{2,3}\b)", "", text)  # 2,000 and 1,00,000 -> 2000 and 100000


def numbers_in(text: str, words: bool = True) -> set:
    """The numbers a text states, normalised ("1.0" and "1" are the same number). With `words`, number
    words count too ("second week" states 2)."""
    text = _clean_numbers(text)
    found = {float(n) for n in re.findall(r"\d+(?:\.\d+)?", text)}
    if words:
        found |= {float(v) for w, v in _NUMBER_WORDS.items() if re.search(rf"\b{w}\b", text, re.IGNORECASE)}
    return {f"{n:g}" for n in found}


def amounts_in(text: str, words: bool = False) -> set:
    """Amounts with their unit ("400 g", "80 l"); both ends of a range get the unit ("80-125 liters").
    With `words`, number words before a unit count too ("six weeks" is "6 week")."""
    text = _clean_numbers(text)
    found = set()
    for low, high, unit in _AMOUNT.findall(text):
        if unit:
            unit = _UNITS[unit.lower()]
            found |= {f"{float(n):g} {unit}" for n in (low, high) if n}
    if words:
        for word, value in _NUMBER_WORDS.items():
            for unit in re.findall(rf"\b{word}\s*-?\s*({_UNIT_PATTERN})(?![\wऀ-੿])", text, re.IGNORECASE):
                found.add(f"{float(value):g} {_UNITS[unit.lower()]}")
    return found


def unbacked_numbers(answer: str, sources: List[str]) -> List[str]:
    """What `answer` states that none of `sources` do (empty: every number is backed). An amount with a
    unit must match an amount with the same unit ("400 g" is not backed by "400 ml"); a bare number must
    appear somewhere. Number words in the answer ("any one of these") are wording, not claims."""
    source = " ".join(sources)
    amounts = amounts_in(answer) - amounts_in(source, words=True)
    bare = numbers_in(answer, words=False) - numbers_in(source) - {a.split()[0] for a in amounts_in(answer)}
    return sorted(amounts | bare, key=lambda x: float(x.split()[0]))


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
