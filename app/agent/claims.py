"""Claims inside a farmer's question, checked against the evidence an answer is built from.

"Since PM-KISAN gives ₹12,000 per month, how do I register?" carries a claim (₹12,000 per month).
Nothing here knows about PM-KISAN: the claim is extracted by its form (money, a dose, a temperature,
"it will rain", a disease name, a product name) and compared with whatever authoritative evidence the
answer uses (retrieved advisory text, the scheme's official text, live weather, MSP/mandi data):

- contradicted: the evidence states the same kind of fact with a different value -> correct it, quoting
  the evidence, and still answer the question;
- unverified: the evidence says nothing comparable -> say it could not be verified, never call it false;
- supported: the evidence states it -> say nothing.

A disease the evidence does not mention gets no treatment; a product the evidence does not recommend
gets no dose. All rules are deterministic: the LLM never decides whether a claim is true.
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional

from app.agent.guardrails import BANNED_PESTICIDES, numbers_in

SUPPORTED, CONTRADICTED, UNVERIFIED, UNKNOWN_PROBLEM, UNKNOWN_PRODUCT = (
    "supported", "contradicted", "unverified", "unknown_problem", "unknown_product")

_INDIC_DIGITS = str.maketrans("०१२३४५६७८९੦੧੨੩੪੫੬੭੮੯", "01234567890123456789")
_NUM = r"\d[\d,]*(?:\.\d+)?"

# ------------------------------------------------------------------ money: "₹12,000 per month"
_CURRENCY = r"(?:₹|rs\.?|inr|rupees?|रुपये|रुपए|रु\.?|ਰੁਪਏ)"
_SCALE = {"thousand": 1e3, "hazar": 1e3, "hajar": 1e3, "हज़ार": 1e3, "हजार": 1e3, "ਹਜ਼ਾਰ": 1e3, "ਹਜਾਰ": 1e3,
          "lakh": 1e5, "lac": 1e5, "लाख": 1e5, "ਲੱਖ": 1e5, "crore": 1e7, "करोड़": 1e7, "ਕਰੋੜ": 1e7}
_SCALE_PATTERN = "|".join(sorted(map(re.escape, _SCALE), key=len, reverse=True))
_MONEY = re.compile(
    rf"{_CURRENCY}\s*({_NUM})\s*({_SCALE_PATTERN})?|({_NUM})\s*({_SCALE_PATTERN})?\s*{_CURRENCY}", re.IGNORECASE)
# The period a money amount is per, from the words right after it
_PERIODS = [
    ("month", r"month|monthly|mahin|mahine|महीन|माह|ਮਹੀਨ"),
    ("year", r"year|yearly|annual|saal|sal\b|साल|वर्ष|वार्षिक|ਸਾਲ"),
    ("quintal", r"quintal|qtl|क्विंटल|ਕੁਇੰਟਲ"),
    ("acre", r"acre|एकड़|ਏਕੜ"),
    ("instalment", r"instal+ment|kist|kisht|किस्त|ਕਿਸ਼ਤ"),
]
_PER_YEAR = {"month": 12, "year": 1}

# ------------------------------------------------------------------ a dose tied to a product: "100 g Actara"
_DOSE_UNITS = {"g": "g", "gm": "g", "gram": "g", "grams": "g", "kg": "kg", "kilo": "kg", "ml": "ml",
               "l": "l", "litre": "l", "litres": "l", "liter": "l", "liters": "l"}
_DOSE = re.compile(rf"({_NUM})\s*(kg|kilo|grams?|gm|g|ml|litres?|liters?|l)\b\s+(?:of\s+)?([a-z][a-z0-9-]{{2,}})",
                   re.IGNORECASE)
_NOT_PRODUCTS = {"per", "in", "the", "a", "an", "each", "every", "for", "to", "and", "or", "water", "pani", "paani",
                 "seed", "spray", "acre", "is", "was", "dose", "more", "less", "only", "at"}

# ------------------------------------------------------------------ temperature and rain (live weather)
_TEMPERATURE = re.compile(rf"({_NUM})\s*(?:°\s*c?\b|degrees?\b|degree celsius|डिग्री|ਡਿਗਰੀ)", re.IGNORECASE)
_RAIN_CLAIM = re.compile(
    r"\b(it(?:'s| is| will| would)\s+(?:going to\s+)?rain|it(?:'s| is)\s+raining|rain(?:s|ing)? today|since it rain|"
    r"because it(?:'s| is| will) rain|barish ho rahi|barish hogi|baarish hogi|baarish ho rahi)\b|"
    r"बारिश हो रही|बारिश होगी|ਮੀਂਹ ਪੈ ਰਿਹਾ|ਮੀਂਹ ਪਵੇਗਾ",
    re.IGNORECASE)
_QUESTION_WORDS = re.compile(r"\b(will it|is it going|kya)\b|क्या|ਕੀ ", re.IGNORECASE)

# ------------------------------------------------------------------ a named disease: "golden wilt virus"
_DISEASE_NOUNS = r"virus|blight|rot|wilt|rust|smut|mildew|mosaic|scab|canker|spot"
_DISEASE = re.compile(rf"\b((?:[a-z]+\s+){{1,2}})((?:{_DISEASE_NOUNS})(?:\s+(?:{_DISEASE_NOUNS}))*)\b", re.IGNORECASE)
_NOT_QUALIFIERS = {"the", "of", "in", "my", "from", "control", "treat", "treatment", "for", "is", "a", "with", "and",
                   "against", "how", "to", "what", "about", "cure", "has", "have", "got", "there", "this", "that", "or",
                   "kya", "ka", "ki", "ke", "mein", "me", "hai", "do", "i", "crop", "field", "plant", "plants",
                   "wheat", "paddy", "rice", "cotton", "mustard", "on", "by", "any", "some", "stop", "prevent",
                   # words that introduce a premise ("Since golden blight is spreading ...")
                   "since", "because", "as", "heard", "said", "says", "think", "believe", "if", "when", "why",
                   "kyunki", "kyonki", "chunki", "suna", "agar", "jab"}

# ------------------------------------------------------------------ a pesticide named by its chemical name
_CHEMICAL = re.compile(
    r"\b[a-z]{3,}(?:azole|conazole|thrin|fos|phos|carb|mectin|cloprid|thoxam|uron|zeb|sulfan|methoate|pyrifos|"
    r"strobin|diamide|xadiazon|fenthion|thion|ozate)\b", re.IGNORECASE)


@dataclass
class ClaimCheck:
    kind: str  # money, dose, temperature, rain, disease, product
    claim: str  # the words in the question
    status: str  # supported, contradicted, unverified, unknown_problem, unknown_product
    fact: str = ""  # the evidence sentence that contradicts it (in the reply language where possible)
    evidence: List[str] = field(default_factory=list)


def _number(text: str) -> float:
    return float(text.replace(",", ""))


def _sentences(texts: List[str]) -> List[str]:
    out = []
    for text in texts:
        out += [s.strip() for s in re.split(r"(?<=[.!?।])\s+|\n+", text) if s.strip()]
    return out


def _period(after: str, before: str = "") -> Optional[str]:
    """The period named just after an amount ("₹12,000 per month") or just before it ("हर महीने 12000 रुपये")."""
    for window in (after[:40].lower(), before[-20:].lower()):
        for name, pattern in _PERIODS:
            if re.search(pattern, window):
                return name
    return None


def money_facts(text: str) -> List[tuple]:
    """(rupees, period or None, sentence) for every money amount in `text`."""
    facts = []
    for sentence in _sentences([text.translate(_INDIC_DIGITS)]):
        for m in _MONEY.finditer(sentence):
            value, scale = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
            rupees = _number(value) * _SCALE.get((scale or "").lower(), 1)
            facts.append((rupees, _period(sentence[m.end():], sentence[:m.start()]), sentence))
    return facts


def _same_money(a: float, period_a: Optional[str], b: float, period_b: Optional[str]) -> Optional[bool]:
    """True/False if the two amounts can be compared (same period, or month and year), None if not."""
    if period_a == period_b or period_a is None or period_b is None:
        return abs(a - b) < 0.5
    if period_a in _PER_YEAR and period_b in _PER_YEAR:
        return abs(a * _PER_YEAR[period_a] - b * _PER_YEAR[period_b]) < 0.5
    return None


def localize_fact(fact: str, localized: List[str]) -> str:
    """The sentence of the reply-language text that states the same numbers as `fact` (or `fact`)."""
    wanted = numbers_in(fact, words=False)
    if not wanted:
        return fact
    best = max(_sentences(localized), key=lambda s: len(wanted & numbers_in(s, words=False)), default="")
    return best if best and wanted <= numbers_in(best, words=False) else fact


def check_claims(question: str, evidence: List[str], localized: Optional[List[str]] = None,
                 weather: Optional[dict] = None, check_names: bool = False,
                 check_diseases: bool = True) -> List[ClaimCheck]:
    """Claims in `question` checked against `evidence` (authoritative text). `localized` is the same
    evidence in the reply language, used to quote it; `weather` is a live report (temperature_c,
    rain_probability_pct); `check_names` also checks disease and product names (crop answers)."""
    question = question.translate(_INDIC_DIGITS)
    text = " ".join(evidence)
    low = text.lower()
    localized = localized or []
    checks: List[ClaimCheck] = []

    # Money: compared with money amounts of a comparable period in the evidence
    facts = money_facts(text)
    question_words = set(re.findall(r"\w{3,}", question.lower()))
    for claimed, period, _ in money_facts(question):
        claim = _claim_text(question, claimed)
        if period == "quintal":
            # Prices: supported anywhere in the range of current prices (±5%), not only at one value
            values = [value for value, p, _ in facts if p == "quintal"]
            same = [bool(values) and min(values) * 0.95 <= claimed <= max(values) * 1.05]
            comparable = [(same[0], s) for v, p, s in facts if p == "quintal"]
        else:
            verdicts = [(_same_money(claimed, period, value, p), sentence) for value, p, sentence in facts]
            comparable = [(same, sentence) for same, sentence in verdicts if same is not None]
        if any(same for same, _ in comparable):
            checks.append(ClaimCheck("money", claim, SUPPORTED))
        elif comparable:
            # The evidence sentence closest to what the question is about ("MSP" -> the MSP line)
            fact = max((s for _, s in comparable), key=lambda s: len(question_words & set(re.findall(r"\w{3,}", s.lower()))))
            checks.append(ClaimCheck("money", claim, CONTRADICTED, localize_fact(fact, localized), [fact]))
        else:
            checks.append(ClaimCheck("money", claim, UNVERIFIED))

    # A dose: compared with amounts of the same unit in evidence sentences naming the same product
    for m in _DOSE.finditer(question):
        value, unit, product = _number(m.group(1)), _DOSE_UNITS[m.group(2).lower()], m.group(3).lower()
        if product in _NOT_PRODUCTS:
            continue
        about = [s for s in _sentences(evidence) if product in s.lower()]
        # Doses the evidence gives for this same product ("40 g Actara"), not other amounts in the sentence
        stated = [(_number(d.group(1)), _DOSE_UNITS[d.group(2).lower()], s) for s in about
                  for d in _DOSE.finditer(s) if d.group(3).lower() == product]
        if any(abs(n - value) < 1e-9 and u == unit for n, u, _ in stated):
            checks.append(ClaimCheck("dose", m.group(0), SUPPORTED))
        elif stated:
            fact = stated[0][2]
            checks.append(ClaimCheck("dose", m.group(0), CONTRADICTED, localize_fact(fact, localized), [fact]))
        elif about:
            checks.append(ClaimCheck("dose", m.group(0), UNVERIFIED))

    # Weather: a stated temperature or "it will rain", compared with the live report
    if weather:
        temperature = weather.get("temperature_c")
        for m in _TEMPERATURE.finditer(question):
            if temperature is not None and abs(_number(m.group(1)) - float(temperature)) > 5:
                fact = next((s for s in _sentences(localized or evidence) if f"{temperature}" in s), "")
                checks.append(ClaimCheck("temperature", m.group(0), CONTRADICTED, fact))
        rain = weather.get("rain_probability_pct")
        claim = _RAIN_CLAIM.search(question)
        if claim and rain is not None and not _QUESTION_WORDS.search(question[:claim.start()]):
            if float(rain) <= 30:
                fact = next((s for s in _sentences(localized or evidence) if f"{rain}%" in s), "")
                checks.append(ClaimCheck("rain", claim.group(0), CONTRADICTED, fact))
            elif float(rain) >= 50:
                checks.append(ClaimCheck("rain", claim.group(0), SUPPORTED))

    if check_names and evidence:
        # A named disease the evidence does not mention: no treatment can be given for it
        if check_diseases:
            for name in unknown_disease_names(question, text):
                checks.append(ClaimCheck("disease", name, UNKNOWN_PROBLEM))
        # A pesticide the evidence does not recommend: no dose can be given for it
        for m in _CHEMICAL.finditer(question):
            chemical = m.group(0).lower()
            if chemical not in BANNED_PESTICIDES and chemical not in low:
                checks.append(ClaimCheck("product", m.group(0), UNKNOWN_PRODUCT))
    return checks


def unknown_disease_names(question: str, text: str) -> List[str]:
    """Disease names in `question` ("golden wilt virus") that `text` never mentions, when it mentions
    none of them: a question giving several names for one disease ("bakanae/foot rot/fusarium blight")
    is about a known disease if any one is known. Spacing does not matter ("para wilt" is "Parawilt");
    a name counts as mentioned if its last word before the disease word does ("leaf curl virus" is in
    "Leaf Curl Virus")."""
    squashed = re.sub(r"\s+", "", text.lower())
    names, unknown = [], []
    for m in _DISEASE.finditer(question.lower()):
        qualifiers = [w for w in m.group(1).split() if w not in _NOT_QUALIFIERS]
        if not qualifiers:
            continue
        name = " ".join(qualifiers + [m.group(2)])
        short = f"{qualifiers[-1]} {m.group(2)}"
        names.append(name)
        if not any(re.sub(r"\s+", "", n) in squashed for n in (name, short)):
            unknown.append(name)
    return unknown if len(unknown) == len(names) else []


def _claim_text(question: str, rupees: float) -> str:
    """The words of the question that state a money amount (with its period), for quoting back."""
    for m in _MONEY.finditer(question):
        value, scale = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
        if abs(_number(value) * _SCALE.get((scale or "").lower(), 1) - rupees) < 0.5:
            tail = re.match(r"\s*(?:per|a|every|each|har|प्रति|हर|ਪ੍ਰਤੀ|ਹਰ)?\s*\S+", question[m.end():])
            period = tail.group(0) if tail and _period(tail.group(0)) else ""
            return (m.group(0) + period).strip(" ,.;?!")
    return f"Rs {rupees:,.0f}"


def without_claims(question: str) -> str:
    """The question with its money and dose claims removed: the farmer's own numbers are not evidence
    (an LLM answer repeating "₹12,000 per month" must not count as backed by the question)."""
    return _DOSE.sub(" ", _MONEY.sub(" ", question.translate(_INDIC_DIGITS)))
