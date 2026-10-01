"""Find the place a farmer is asking about and turn it into coordinates.

1. Known places (English, Hindi and Punjabi spellings) are matched directly, offline.
2. Other place names in Latin script ("weather in Nashik", "Sangrur mein mausam") are looked
   up with the free Open-Meteo geocoding API, accepting only an exact name match in India.
"""

import re
import unicodedata
from functools import lru_cache
from typing import List, Optional

import requests
from pydantic import BaseModel

from app.crops import latin_crop_words
from app.textmatch import contains_term

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
    "Mohali": ["mohali", "sas nagar", "मोहाली", "ਮੋਹਾਲੀ"],
    "Barnala": ["barnala", "बरनाला", "ਬਰਨਾਲਾ"],
    "Faridkot": ["faridkot", "फरीदकोट", "ਫ਼ਰੀਦਕੋਟ", "ਫਰੀਦਕੋਟ"],
    "Fatehgarh Sahib": ["fatehgarh sahib", "fatehgarh", "फतेहगढ़ साहिब", "ਫ਼ਤਿਹਗੜ੍ਹ ਸਾਹਿਬ", "ਫਤਿਹਗੜ੍ਹ ਸਾਹਿਬ"],
    "Fazilka": ["fazilka", "फाजिल्का", "फ़ाज़िल्का", "ਫ਼ਾਜ਼ਿਲਕਾ", "ਫਾਜ਼ਿਲਕਾ"],
    "Gurdaspur": ["gurdaspur", "गुरदासपुर", "ਗੁਰਦਾਸਪੁਰ"],
    "Hoshiarpur": ["hoshiarpur", "होशियारपुर", "ਹੁਸ਼ਿਆਰਪੁਰ"],
    "Kapurthala": ["kapurthala", "कपूरथला", "ਕਪੂਰਥਲਾ"],
    "Malerkotla": ["malerkotla", "मलेरकोटला", "ਮਾਲੇਰਕੋਟਲਾ"],
    "Mansa": ["mansa", "मानसा", "ਮਾਨਸਾ"],
    "Muktsar": ["muktsar", "sri muktsar sahib", "मुक्तसर", "ਮੁਕਤਸਰ"],
    "Nawanshahr": ["nawanshahr", "shaheed bhagat singh nagar", "sbs nagar", "नवांशहर", "ਨਵਾਂਸ਼ਹਿਰ"],
    "Pathankot": ["pathankot", "पठानकोट", "ਪਠਾਨਕੋਟ"],
    "Rupnagar": ["rupnagar", "ropar", "रूपनगर", "रोपड़", "ਰੂਪਨਗਰ", "ਰੋਪੜ"],
    "Tarn Taran": ["tarn taran", "tarntaran", "तरनतारन", "तरन तारन", "ਤਰਨ ਤਾਰਨ"],
    "Chandigarh": ["chandigarh", "चंडीगढ़", "ਚੰਡੀਗੜ੍ਹ"],
    "Delhi": ["delhi", "new delhi", "dilli", "दिल्ली", "ਦਿੱਲੀ"],
    # Delhi-NCR
    "Noida": ["noida", "नोएडा", "नोयडा", "ਨੋਇਡਾ"],
    "Greater Noida": ["greater noida", "ग्रेटर नोएडा", "ਗ੍ਰੇਟਰ ਨੋਇਡਾ"],
    "Ghaziabad": ["ghaziabad", "गाज़ियाबाद", "गाजियाबाद", "ਗਾਜ਼ੀਆਬਾਦ"],
    "Gurugram": ["gurugram", "gurgaon", "गुरुग्राम", "गुड़गांव", "ਗੁਰੂਗ੍ਰਾਮ"],
    "Faridabad": ["faridabad", "फरीदाबाद", "ਫ਼ਰੀਦਾਬਾਦ", "ਫਰੀਦਾਬਾਦ"],
    "Sonipat": ["sonipat", "sonepat", "सोनीपत", "ਸੋਨੀਪਤ"],
    "Panipat": ["panipat", "पानीपत", "ਪਾਣੀਪਤ"],
    "Meerut": ["meerut", "मेरठ", "ਮੇਰਠ"],
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

# States: weather needs a district or town, but mandi prices can be a state average
STATES = {
    "Punjab": (["punjab", "पंजाब", "ਪੰਜਾਬ"], ["Ludhiana", "Sangrur", "Bathinda", "Amritsar"]),
    "Haryana": (["haryana", "हरियाणा", "ਹਰਿਆਣਾ"], ["Karnal", "Hisar", "Sirsa", "Panipat"]),
    "Uttar Pradesh": (["uttar pradesh", "up", "उत्तर प्रदेश", "ਉੱਤਰ ਪ੍ਰਦੇਸ਼"], ["Noida", "Meerut", "Lucknow", "Kanpur"]),
    "Rajasthan": (["rajasthan", "राजस्थान", "ਰਾਜਸਥਾਨ"], ["Jaipur", "Kota"]),
    "Madhya Pradesh": (["madhya pradesh", "mp", "मध्य प्रदेश", "ਮੱਧ ਪ੍ਰਦੇਸ਼"], ["Indore", "Bhopal"]),
    "Bihar": (["bihar", "बिहार", "ਬਿਹਾਰ"], ["Patna"]),
    "Himachal Pradesh": (["himachal pradesh", "himachal", "हिमाचल", "ਹਿਮਾਚਲ"], ["Shimla", "Mandi"]),
}


def state_named(text: str) -> Optional[str]:
    """The state a place name refers to ("Punjab", "UP", "पंजाब"), or None for a district or town."""
    clean = (text or "").lower().strip(" ?.!,")
    for state, (aliases, _) in STATES.items():
        if any(clean == a or (any(ord(c) > 127 for c in a) and a in clean) for a in aliases):
            return state
    return None


def find_state(text: str) -> Optional[str]:
    """A state mentioned anywhere in a question ("weather in Punjab", "ਪੰਜਾਬ ਵਿੱਚ ਮੌਸਮ", "rate in UP")."""
    clean = unicodedata.normalize("NFC", (text or "").lower())
    # "UP" / "MP" only after "in/at/for": "pick up" is not Uttar Pradesh
    short = re.search(r"\b(?:in|at|for)\s+(up|mp)\b", clean)
    if short:
        return {"up": "Uttar Pradesh", "mp": "Madhya Pradesh"}[short.group(1)]
    for state, (aliases, _) in STATES.items():
        for alias in aliases:
            if alias in ("up", "mp"):
                continue
            if _contains(alias, clean):
                return state
    return None


# Words that sit in place-like positions but are never places
_NOT_PLACES = {
    "aaj", "kal", "abhi", "today", "tomorrow", "now", "the", "my", "our", "khet", "field", "farm",
    "mausam", "weather", "barish", "baarish", "rain", "spray", "crop", "fasal", "area", "village", "gaon", "pind",
    "india", "msp", "rate", "price", "prices", "bhav", "bhaav", "mandi", "keemat", "daam",
} | latin_crop_words()  # "rice ka rate", "aloo ka bhav": crop names are not places

# "in Nashik", "at Sangrur", "for Moga" / "Nashik mein", "Sangrur me", "Moga vich"
_BEFORE = re.compile(r"\b(?:in|at|for|near)\s+([a-z][a-z]{2,}(?:\s+[a-z]{3,})?)\b")
_AFTER = re.compile(r"\b([a-z][a-z]{2,})\s+(?:mein|me|main|vich|ch|da|ka|ki|ke)\b")


def _contains(alias: str, text: str) -> bool:
    return contains_term(alias, text)  # whole words, any script (app/textmatch.py)


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
    state = find_state(text)
    if state:
        return state
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
