"""Per-acre doses worked out for the farmer's own land size (from the farm profile).

"160 g per acre" becomes "160 g per acre (5.44 kg for your 34 acres)". The arithmetic is done here,
never by the LLM, so a total can't be invented. Only sentences that say "per acre" are touched,
and only amounts with a weight or volume unit (g, kg, ml, litres) — not "25 WG", "5 aphids" or "4%".
"""

import re
from typing import Tuple

from app.i18n import t

NUMBER = r"(\d+(?:\.\d+)?)(?:\s*(?:-|to)\s*(\d+(?:\.\d+)?))?"
UNITS = {
    # unit word -> (base unit, factor to the base unit)
    "g": ("g", 1), "gm": ("g", 1), "gram": ("g", 1), "grams": ("g", 1), "ग्राम": ("g", 1), "ਗ੍ਰਾਮ": ("g", 1),
    "kg": ("g", 1000), "kilo": ("g", 1000), "किलो": ("g", 1000), "किलोग्राम": ("g", 1000), "ਕਿਲੋ": ("g", 1000),
    "ml": ("ml", 1), "milliliter": ("ml", 1), "millilitre": ("ml", 1), "मिलीलीटर": ("ml", 1), "मिली": ("ml", 1),
    "ਮਿਲੀਲੀਟਰ": ("ml", 1), "ਮਿਲੀ": ("ml", 1),
    "l": ("ml", 1000), "litre": ("ml", 1000), "litres": ("ml", 1000), "liter": ("ml", 1000), "liters": ("ml", 1000),
    "लीटर": ("ml", 1000), "ਲੀਟਰ": ("ml", 1000),
}
UNIT_PATTERN = "|".join(sorted((re.escape(u) for u in UNITS), key=len, reverse=True))
# The amount, its unit and, when it follows directly, "per acre" (the total is shown after it)
DOSE = re.compile(
    rf"(?<![\w.]){NUMBER}\s*({UNIT_PATTERN})(?![\wऀ-੿])"
    r"((?:\s+of\s+water)?\s*(?:per\s+acre|/\s*acre|prati\s+acre|प्रति\s*एकड़|ਪ੍ਰਤੀ\s*ਏਕੜ))?",
    re.IGNORECASE,
)
PER_ACRE = re.compile(r"per\s+acre|/\s*acre|prati\s+acre|प्रति\s*एकड़|एकड़\s*में|ਪ੍ਰਤੀ\s*ਏਕੜ|ਏਕੜ\s*ਵਿੱਚ", re.IGNORECASE)
SENTENCE = re.compile(r"(?<=[.!?।;])\s+|\n")


def _number(value: float) -> str:
    """5.44, 13.6, 2,720: rounded for reading, never in scientific notation."""
    if value >= 100:
        return f"{value:,.0f}"
    return f"{value:.1f}".rstrip("0").rstrip(".") if value >= 10 else f"{value:.2f}".rstrip("0").rstrip(".")


def _fmt(amount: float, base: str) -> str:
    """Grams as g or kg, millilitres as ml or litres."""
    if base == "g":
        return f"{_number(amount / 1000)} kg" if amount >= 1000 else f"{_number(amount)} g"
    return f"{_number(amount / 1000)} litres" if amount >= 1000 else f"{_number(amount)} ml"


def _total(match: re.Match, acres: float) -> str:
    low, high, unit = match.group(1), match.group(2), match.group(3).lower()
    base, factor = UNITS[unit]
    if high:
        # Both ends in the unit of the larger one: "27.2-34 kg", never "800-1.2 kg"
        top = _fmt(float(high) * factor * acres, base)
        divisor = 1000 if top.split()[1] in ("kg", "litres") else 1
        return f"{_number(float(low) * factor * acres / divisor)}-{top}"
    return _fmt(float(low) * factor * acres, base)


def scale_doses(text: str, acres: float, lang: str) -> Tuple[str, bool]:
    """`text` with the total for `acres` after every per-acre amount, and whether anything changed."""
    if not acres or acres <= 0:
        return text, False
    acres_text = f"{acres:g}"
    changed = False

    def annotate(match: re.Match) -> str:
        nonlocal changed
        changed = True
        return f"{match.group(0)} ({t('dose_total', lang, total=_total(match, acres), acres=acres_text)})"

    pieces = []
    last = 0
    for boundary in list(SENTENCE.finditer(text)) + [None]:
        end = boundary.start() if boundary else len(text)
        sentence = text[last:end]
        pieces.append(DOSE.sub(annotate, sentence) if PER_ACRE.search(sentence) else sentence)
        if boundary:
            pieces.append(boundary.group(0))
            last = boundary.end()
    out = "".join(pieces)
    if changed:
        out += "\n\n_" + t("dose_total_note", lang, acres=acres_text) + "_"
    return out, changed
