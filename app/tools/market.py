"""Market prices: Minimum Support Price (MSP) and live mandi prices.

- MSP comes from data/market/msp.json (Government of India Cabinet decisions, with the date checked).
- Live mandi prices come from Agmarknet's daily prices on data.gov.in, when that service can be reached.
  If it cannot, the answer says so and points to agmarknet.gov.in / eNAM / the Kisan Call Centre:
  a price is never guessed.
"""

import json
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


# Identify the app honestly to public data services (generic library user agents are often refused)
HEADERS = {"User-Agent": "KisanSahayak/1.0 (farmer advisory app; github.com/KanishkaSingh19/KisanSahayak)"}


@dataclass
class MandiPrice:
    market: str  # a mandi, or the area an average covers (e.g. "Punjab")
    district: str
    date: str  # as published, dd/mm/yyyy
    min_price: Optional[float]  # None when the source only gives an average
    max_price: Optional[float]
    modal_price: float


@dataclass
class MandiLookup:
    prices: List[MandiPrice] = field(default_factory=list)
    local: bool = False  # prices are from the farmer's district (otherwise state-wide)
    error: Optional[str] = None  # why live prices could not be fetched
    source: str = ""  # citation for the prices shown


class MandiPriceClient:
    """Latest daily mandi prices from Agmarknet (via data.gov.in)."""

    DOWN_COOLDOWN_SEC = 600  # after a failure, don't make every farmer wait for the same timeout

    def __init__(self, api_key: Optional[str] = None, timeout_sec: float = 5.0):
        self.api_key = api_key or settings.DATA_GOV_API_KEY or SAMPLE_API_KEY
        self.timeout_sec = timeout_sec
        self._down_until = 0.0

    def _fetch(self, filters: Dict[str, str]) -> List[Dict]:
        params = {"api-key": self.api_key, "format": "json", "limit": 50}
        params.update({f"filters[{k}]": v for k, v in filters.items()})
        resp = requests.get(MANDI_URL, params=params, timeout=self.timeout_sec, headers=HEADERS)
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
        return MandiLookup(prices=[p for p in prices if p.date == newest][:5], local=local,
                           source="Agmarknet daily mandi prices (data.gov.in)")


# ----------------------------------------------------------------------------- Agmarknet 2.0
AGMARKNET_FILTERS_URL = "https://api.agmarknet.gov.in/v1/dashboard-filters/?dashboard_name=marketwise_price_arrival"
AGMARKNET_DATA_URL = "https://api.agmarknet.gov.in/v1/dashboard-data/"
# Agmarknet commodity ids (from the dashboard filters)
AGMARKNET_IDS = {
    "wheat": 1, "paddy": 2, "maize": 4, "jowar": 5, "gram": 6, "urad": 8, "moong": 9, "groundnut": 10, "sesamum": 11,
    "mustard": 12, "soybean": 13, "sunflower": 14, "cotton": 15, "onion": 23, "potato": 24, "bajra": 28, "barley": 29,
    "ragi": 30, "tur": 45, "safflower": 48, "lentil": 52, "tomato": 65, "nigerseed": 83,
}
# "All" values in the dashboard's filters
ALL_GROUPS, ALL_VARIETIES, ALL_STATES, ALL_DISTRICTS, ALL_MARKETS, FAQ_GRADE = 100000, 100021, 100006, 100007, 100009, 4

# Our place names -> state, for places outside Punjab that the app knows
PLACE_STATES = {
    "karnal": "Haryana", "hisar": "Haryana", "sirsa": "Haryana", "varanasi": "Uttar Pradesh", "lucknow": "Uttar Pradesh",
    "kanpur": "Uttar Pradesh", "indore": "Madhya Pradesh", "bhopal": "Madhya Pradesh", "jaipur": "Rajasthan",
    "kota": "Rajasthan", "patna": "Bihar", "delhi": "NCT of Delhi", "chandigarh": "Chandigarh",
}


PUNJAB_DISTRICTS = {
    "amritsar", "barnala", "bathinda", "faridkot", "fatehgarh sahib", "fazilka", "firozpur", "gurdaspur", "hoshiarpur",
    "jalandhar", "kapurthala", "ludhiana", "malerkotla", "mansa", "moga", "mohali", "muktsar", "nawanshahr",
    "pathankot", "patiala", "rupnagar", "sangrur", "tarn taran",
}


def state_for(place: str, resolve=None) -> Optional[str]:
    """The state a place is in: built-in places first, then `resolve` (a place lookup returning .state).

    There is no default state: None means the state is not known, and the farmer should be asked.
    """
    key = place.lower().strip()
    if key in PUNJAB_DISTRICTS:
        return "Punjab"
    if key in PLACE_STATES:
        return PLACE_STATES[key]
    if resolve is not None:
        found = resolve(place)
        if found is not None and getattr(found, "state", None):
            return found.state
    return None


def _letters(name: str) -> str:
    return re.sub(r"[^a-z]", "", name.lower())


def _same_place(ours: str, theirs: str) -> bool:
    """Agmarknet spells some districts differently: Bhatinda, Ferozpur, Tarntaran, "Ropar (Rupnagar)"."""
    a, b = _letters(ours), _letters(theirs)
    spellings = {"bathinda": "bhatinda", "firozpur": "ferozpur", "fatehgarhsahib": "fatehgarh", "rupnagar": "ropar"}
    a = spellings.get(a, a)
    return a == b or b.startswith(a) or a.startswith(b) or a in b


class AgmarknetClient:
    """Average daily mandi prices from Agmarknet 2.0 (agmarknet.gov.in), by state or district."""

    DOWN_COOLDOWN_SEC = 600
    FILTERS_MAX_AGE_SEC = 24 * 3600

    def __init__(self, timeout_sec: float = 8.0):
        self.timeout_sec = timeout_sec
        self._down_until = 0.0
        self._filters: Optional[Dict] = None
        self._filters_at = 0.0

    def _get_filters(self) -> Dict:
        if self._filters is None or time.time() - self._filters_at > self.FILTERS_MAX_AGE_SEC:
            resp = requests.get(AGMARKNET_FILTERS_URL, timeout=self.timeout_sec, headers=HEADERS)
            resp.raise_for_status()
            self._filters, self._filters_at = resp.json()["data"], time.time()
        return self._filters

    def _ids(self, state: str, district: Optional[str]):
        filters = self._get_filters()
        state_row = next((s for s in filters["state_data"] if _same_place(state, s["state_name"])), None)
        if not state_row:
            return None, None
        district_id = None
        if district:
            district_id = next((d["id"] for d in filters["district_data"]
                                if d["state_id"] == state_row["state_id"] and _same_place(district, d["district_name"])), None)
        return state_row["state_id"], district_id

    def _query(self, commodity_id: int, state_id: int, district_id: Optional[int]) -> Dict:
        body = {
            "dashboard": "marketwise_price_arrival", "date": time.strftime("%Y-%m-%d"), "group": [ALL_GROUPS],
            "commodity": [commodity_id], "variety": ALL_VARIETIES, "state": state_id,
            "district": [district_id or ALL_DISTRICTS], "market": [ALL_MARKETS], "grades": [FAQ_GRADE],
            "limit": 10, "format": "json",
        }
        resp = requests.post(AGMARKNET_DATA_URL, json=body, timeout=self.timeout_sec, headers=HEADERS)
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def _parse(data: Dict, place: str) -> List[MandiPrice]:
        """One average price per reported day: the newest of the last three days that have a price."""
        content = data.get("data")
        if not isinstance(content, dict) or not content.get("records"):
            return []
        # Column titles carry the dates, e.g. {"key": "as_on_price", "title": "29 Sep, 2026"}
        dates = {}
        for group in content.get("columns", []):
            for col in group.get("columns", []):
                if col.get("key", "").endswith("_price") and col["key"] != "msp_price":
                    try:
                        dates[col["key"]] = time.strftime("%d/%m/%Y", time.strptime(col["title"], "%d %b, %Y"))
                    except (KeyError, ValueError):
                        continue
        record = content["records"][0]
        prices = []
        for key in ("as_on_price", "one_day_ago_price", "two_day_ago_price"):
            if record.get(key) and key in dates:
                try:
                    prices.append(MandiPrice(market=place, district=place, date=dates[key], min_price=None,
                                             max_price=None, modal_price=float(record[key])))
                except ValueError:
                    continue
        return prices

    def latest(self, commodity: str, state: str = "Punjab", district: Optional[str] = None) -> MandiLookup:
        commodity_id = AGMARKNET_IDS.get(commodity)
        if not commodity_id:
            return MandiLookup(error="no Agmarknet prices for this commodity")
        if time.time() < self._down_until:
            return MandiLookup(error="Agmarknet unreachable (recent failure)")
        try:
            state_id, district_id = self._ids(state, district)
            if not state_id:
                return MandiLookup(error=f"state not found on Agmarknet: {state}")
            prices, local = [], False
            if district_id:
                prices = self._parse(self._query(commodity_id, state_id, district_id), district)
                local = bool(prices)
            if not prices:
                prices = self._parse(self._query(commodity_id, state_id, None), state)
        except (requests.RequestException, ValueError, KeyError) as e:
            self._down_until = time.time() + self.DOWN_COOLDOWN_SEC
            return MandiLookup(error=f"Agmarknet unreachable ({type(e).__name__})")
        if not prices:
            return MandiLookup(error="no recent prices reported on Agmarknet")
        return MandiLookup(prices=prices, local=local, source="Agmarknet daily prices (agmarknet.gov.in)")


class MarketPriceService:
    """Tries each price source in turn: data.gov.in (per-mandi prices), then Agmarknet (averages)."""

    def __init__(self, sources=None):
        self.sources = sources if sources is not None else [MandiPriceClient(), AgmarknetClient()]

    def latest(self, commodity: str, state: Optional[str] = None, district: Optional[str] = None) -> MandiLookup:
        state = state or (state_for(district) if district else None)
        if not state:
            return MandiLookup(error="no place given")  # no default state: the farmer is asked instead
        errors = []
        for source in self.sources:
            lookup = source.latest(commodity, state=state, district=district)
            if lookup.prices:
                return lookup
            errors.append(lookup.error or "no prices")
        return MandiLookup(error="; ".join(errors))
