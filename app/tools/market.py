"""Market prices: Minimum Support Price (MSP) and live mandi prices.

- MSP comes from data/market/msp.json (Government of India Cabinet decisions, with the date checked).
- Live mandi prices come from Agmarknet's daily prices on data.gov.in, when that service can be reached.
  If it cannot, the answer says so and points to agmarknet.gov.in / eNAM / the Kisan Call Centre:
  a price is never guessed.
"""

import json
import os
import re
import time
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

import requests

from app.config import settings

MSP_PATH = settings.DATA_DIR / "market" / "msp.json"
MANDI_URL = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"
# data.gov.in's documented public sample key (limited rows); set DATA_GOV_API_KEY for your own
SAMPLE_API_KEY = "579b464db66ec23bdd000001cdd3946e44ce4aad7209ff7b23ac571b"

# Commodity -> spellings farmers use (Latin, Devanagari, Gurmukhi)
COMMODITY_ALIASES: Dict[str, List[str]] = {
    "wheat": ["wheat", "gehun", "gehu", "kanak", "गेहूं", "गेहूँ", "ਕਣਕ"],
    "mustard": ["mustard", "sarson", "raya", "rapeseed", "toria", "सरसों", "ਸਰ੍ਹੋਂ", "ਸਰੋਂ", "ਰਾਇਆ"],
    "paddy": ["paddy", "rice", "dhan", "dhaan", "jhona", "basmati", "धान", "ਝੋਨਾ", "ਝੋਨੇ"],
    "cotton": ["cotton", "kapas", "narma", "कपास", "ਨਰਮਾ", "ਨਰਮੇ", "ਕਪਾਹ"],
    "maize": ["maize", "corn", "makka", "makki", "मक्का", "ਮੱਕੀ"],
    "gram": ["gram", "chana", "chickpea", "चना", "ਛੋਲੇ"],
    "barley": ["barley", "jau", "जौ", "ਜੌਂ"],
    "lentil": ["lentil", "masur", "masoor", "मसूर", "ਮਸਰ"],
    "moong": ["moong", "green gram", "मूंग", "ਮੂੰਗੀ"],
    "bajra": ["bajra", "pearl millet", "बाजरा", "ਬਾਜਰਾ"],
    "jowar": ["jowar", "sorghum", "ज्वार", "ਜਵਾਰ"],
    "ragi": ["ragi", "finger millet", "रागी"],
    "tur": ["tur", "arhar", "toor", "अरहर", "तुअर", "ਅਰਹਰ"],
    "urad": ["urad", "black gram", "उड़द", "ਮਾਂਹ"],
    "groundnut": ["groundnut", "peanut", "moongphali", "मूंगफली", "ਮੂੰਗਫਲੀ"],
    "sunflower": ["sunflower", "surajmukhi", "सूरजमुखी", "ਸੂਰਜਮੁਖੀ"],
    "soybean": ["soybean", "soyabean", "सोयाबीन"],
    "sesamum": ["sesamum", "sesame", "til", "तिल", "ਤਿਲ"],
    "safflower": ["safflower", "kusum", "कुसुम"],
    "nigerseed": ["nigerseed", "niger seed", "ramtil"],
    "potato": ["potato", "aloo", "आलू", "ਆਲੂ"],
    "onion": ["onion", "pyaz", "pyaaz", "प्याज", "ਪਿਆਜ਼"],
    "tomato": ["tomato", "tamatar", "टमाटर", "ਟਮਾਟਰ"],
}

# Commodity names in Agmarknet's daily price data
AGMARKNET_NAMES = {
    "wheat": "Wheat", "mustard": "Mustard", "paddy": "Paddy(Dhan)(Common)", "cotton": "Cotton", "maize": "Maize",
    "gram": "Bengal Gram(Gram)(Whole)", "barley": "Barley (Jau)", "lentil": "Lentil (Masur)(Whole)",
    "moong": "Green Gram (Moong)(Whole)", "bajra": "Bajra(Pearl Millet/Cumbu)", "jowar": "Jowar(Sorghum)",
    "tur": "Arhar (Tur/Red Gram)(Whole)", "urad": "Black Gram (Urd Beans)(Whole)", "groundnut": "Groundnut",
    "sunflower": "Sunflower", "soybean": "Soyabean", "sesamum": "Sesamum(Sesame,Gingelly,Til)",
    "potato": "Potato", "onion": "Onion", "tomato": "Tomato",
}


def _norm(text: str) -> str:
    return unicodedata.normalize("NFC", text).lower()


def detect_commodity(text: str) -> Optional[str]:
    """The commodity a question asks about; the longest matching name wins ("green gram" over "gram")."""
    clean = _norm(text)
    best = None
    for key, aliases in COMMODITY_ALIASES.items():
        for alias in aliases:
            a = _norm(alias)
            found = a in clean if any(ord(c) > 127 for c in a) else re.search(rf"\b{re.escape(a)}\b", clean)
            if found and (best is None or len(a) > best[0]):
                best = (len(a), key)
    return best[1] if best else None


@lru_cache(maxsize=1)
def load_msp(path: Path = MSP_PATH) -> Dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


@dataclass
class MandiPrice:
    market: str
    district: str
    date: str  # as published, dd/mm/yyyy
    min_price: float
    max_price: float
    modal_price: float


@dataclass
class MandiLookup:
    prices: List[MandiPrice] = field(default_factory=list)
    local: bool = False  # prices are from the farmer's district (otherwise state-wide)
    error: Optional[str] = None  # why live prices could not be fetched


class MandiPriceClient:
    """Latest daily mandi prices from Agmarknet (via data.gov.in)."""

    DOWN_COOLDOWN_SEC = 600  # after a failure, don't make every farmer wait for the same timeout

    def __init__(self, api_key: Optional[str] = None, timeout_sec: float = 5.0):
        self.api_key = api_key or os.environ.get("DATA_GOV_API_KEY") or SAMPLE_API_KEY
        self.timeout_sec = timeout_sec
        self._down_until = 0.0

    def _fetch(self, filters: Dict[str, str]) -> List[Dict]:
        params = {"api-key": self.api_key, "format": "json", "limit": 50}
        params.update({f"filters[{k}]": v for k, v in filters.items()})
        resp = requests.get(MANDI_URL, params=params, timeout=self.timeout_sec)
        resp.raise_for_status()
        return resp.json().get("records") or []

    def latest(self, commodity: str, state: str = "Punjab", district: Optional[str] = None) -> MandiLookup:
        name = AGMARKNET_NAMES.get(commodity)
        if not name:
            return MandiLookup(error="no mandi price data for this commodity")
        if time.time() < self._down_until:
            return MandiLookup(error="mandi price service unreachable (recent failure)")
        try:
            records, local = [], False
            if district:
                records = self._fetch({"state.keyword": state, "district": district, "commodity": name})
                local = bool(records)
            if not records:
                records = self._fetch({"state.keyword": state, "commodity": name})
        except (requests.RequestException, ValueError) as e:
            self._down_until = time.time() + self.DOWN_COOLDOWN_SEC
            return MandiLookup(error=f"mandi price service unreachable ({type(e).__name__})")
        prices = []
        for r in records:
            try:
                prices.append(MandiPrice(
                    market=r["market"], district=r.get("district", ""), date=r["arrival_date"],
                    min_price=float(r["min_price"]), max_price=float(r["max_price"]), modal_price=float(r["modal_price"]),
                ))
            except (KeyError, TypeError, ValueError):
                continue
        if not prices:
            return MandiLookup(error="no recent prices reported")
        # Newest first (dates are dd/mm/yyyy)
        prices.sort(key=lambda p: tuple(reversed(p.date.split("/"))), reverse=True)
        newest = prices[0].date
        return MandiLookup(prices=[p for p in prices if p.date == newest][:5], local=local)
