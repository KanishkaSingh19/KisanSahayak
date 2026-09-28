"""Find the place a farmer is asking about and turn it into coordinates.

1. Known places (English, Hindi and Punjabi spellings) are matched directly, offline.
2. Other place names in Latin script ("weather in Nashik", "Sangrur mein mausam") are looked
   up with the free Open-Meteo geocoding API, accepting only an exact name match in India.
"""

import re
from functools import lru_cache
from typing import List, Optional

import requests
from pydantic import BaseModel

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"


class Place(BaseModel):
    name: str
    latitude: float
    longitude: float
    state: Optional[str] = None


# Canonical English name -> spellings farmers may use (Latin, Devanagari, Gurmukhi)
PLACE_ALIASES = {
    "Ludhiana": ["ludhiana", "लुधियाना", "ਲੁਧਿਆਣਾ"],
    "Amritsar": ["amritsar", "अमृतसर", "ਅੰਮ੍ਰਿਤਸਰ"],
    "Bathinda": ["bathinda", "bhatinda", "बठिंडा", "ਬਠਿੰਡਾ"],
    "Patiala": ["patiala", "पटियाला", "ਪਟਿਆਲਾ"],
    "Jalandhar": ["jalandhar", "jullundur", "जालंधर", "ਜਲੰਧਰ"],
    "Sangrur": ["sangrur", "संगरूर", "ਸੰਗਰੂਰ"],
    "Moga": ["moga", "मोगा", "ਮੋਗਾ"],
    "Firozpur": ["firozpur", "ferozepur", "फिरोजपुर", "ਫਿਰੋਜ਼ਪੁਰ"],
    "Mohali": ["mohali", "मोहाली", "ਮੋਹਾਲੀ"],
    "Chandigarh": ["chandigarh", "चंडीगढ़", "ਚੰਡੀਗੜ੍ਹ"],
    "Delhi": ["delhi", "new delhi", "dilli", "दिल्ली", "ਦਿੱਲੀ"],
    "Karnal": ["karnal", "करनाल", "ਕਰਨਾਲ"],
    "Hisar": ["hisar", "hissar", "हिसार", "ਹਿਸਾਰ"],
    "Sirsa": ["sirsa", "सिरसा", "ਸਿਰਸਾ"],
    "Varanasi": ["varanasi", "banaras", "वाराणसी", "ਵਾਰਾਣਸੀ"],
    "Lucknow": ["lucknow", "लखनऊ", "ਲਖਨਊ"],
    "Kanpur": ["kanpur", "कानपुर", "ਕਾਨਪੁਰ"],
    "Indore": ["indore", "इंदौर", "ਇੰਦੌਰ"],
    "Bhopal": ["bhopal", "भोपाल", "ਭੋਪਾਲ"],
    "Jaipur": ["jaipur", "जयपुर", "ਜੈਪੁਰ"],
    "Kota": ["kota", "कोटा", "ਕੋਟਾ"],
    "Patna": ["patna", "पटना", "ਪਟਨਾ"],
}

# Words that sit in place-like positions but are never places
_NOT_PLACES = {
    "aaj", "kal", "abhi", "today", "tomorrow", "now", "the", "my", "our", "khet", "field", "farm",
    "mausam", "weather", "barish", "baarish", "rain", "spray", "wheat", "gehun", "sarson", "mustard",
    "paddy", "dhan", "cotton", "kapas", "crop", "fasal", "area", "village", "gaon", "pind", "india",
}

# "in Nashik", "at Sangrur", "for Moga" / "Nashik mein", "Sangrur me", "Moga vich"
_BEFORE = re.compile(r"\b(?:in|at|for|near)\s+([a-z][a-z]{2,}(?:\s+[a-z]{3,})?)\b")
_AFTER = re.compile(r"\b([a-z][a-z]{2,})\s+(?:mein|me|main|vich|ch|da|ka|ki|ke)\b")


def _contains(alias: str, text: str) -> bool:
    if any(ord(c) > 127 for c in alias):
        return alias in text
    return bool(re.search(rf"\b{re.escape(alias)}\b", text))


def find_known_place(text: str) -> Optional[str]:
    """Canonical name of a known place mentioned in the text, in any script."""
    clean = text.lower()
    for name, aliases in PLACE_ALIASES.items():
        if any(_contains(alias, clean) for alias in aliases):
            return name
    return None


def place_candidates(text: str) -> List[str]:
    """Possible unknown place names in Latin-script text, most likely first."""
    clean = text.lower()
    found = []
    for pattern in (_BEFORE, _AFTER):
        for match in pattern.findall(clean):
            words = [w for w in match.split() if w not in _NOT_PLACES]
            if words:
                candidate = " ".join(words)
                if candidate not in found:
                    found.append(candidate)
    return found


def detect_place(text: str) -> Optional[str]:
    """Best guess at the place a question is about (not yet verified to exist)."""
    known = find_known_place(text)
    if known:
        return known
    candidates = place_candidates(text)
    return candidates[0].title() if candidates else None


@lru_cache(maxsize=512)
def geocode(name: str, timeout_sec: float = 4.0) -> Optional[Place]:
    """Exact-name lookup of an Indian place via Open-Meteo geocoding; None if not found or offline."""
    try:
        resp = requests.get(
            GEOCODING_URL,
            params={"name": name, "count": 5, "countryCode": "IN", "format": "json"},
            timeout=timeout_sec,
        )
        resp.raise_for_status()
        for result in resp.json().get("results") or []:
            if result.get("country_code") == "IN" and result.get("name", "").lower() == name.lower():
                return Place(
                    name=result["name"],
                    latitude=result["latitude"],
                    longitude=result["longitude"],
                    state=result.get("admin1"),
                )
    except (requests.RequestException, ValueError, KeyError):
        pass
    return None
