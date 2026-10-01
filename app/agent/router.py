import re
import unicodedata
from typing import List, Optional
from app.agent.guardrails import AgriculturalGuardrails
from app.crops import COVERED_CROPS, CROP_NAMES, OTHER_PLANTS
from app.textmatch import contains_term
from app.agent.state import ConversationTurn, IntentResult
from app.tools.location import detect_place
from app.tools.schemes import OTHER_SCHEME_PREFIX, detect_other_scheme, detect_scheme

# Lexicons for multilingual agricultural intent detection
CROPS_DICT = {crop: CROP_NAMES[crop] for crop in COVERED_CROPS}

PESTS_AND_DISEASES = {
    "yellow_rust": ["yellow rust", "peeli kungi", "pila rataua", "puccinia", "kungi", "पीली कुंगी", "ਪੀਲੀ ਕੁੰਗੀ"],
    "karnal_bunt": ["karnal bunt", "tilletia", "bunt", "करनाल बंट"],
    "aphid": ["aphid", "aphids", "mahu", "mahun", "chetpa", "chepa", "tilla", "माहू", "ਚੇਪਾ", "ਚੇਪੇ"],
    "white_rust": ["white rust", "safed kungi", "blister", "सफेद कुंगी"],
    # Before "blb": "tana jhulsa" (stem blight) also contains "jhulsa"
    "sheath_blight": ["sheath blight", "tana jhulsa", "saanp ki khaal", "snake skin", "शीथ ब्लाइट", "तना झुलसा", "ਸ਼ੀਥ ਬਲਾਈਟ"],
    "blb": ["bacterial leaf blight", "blb", "peela jhulsa", "jhulsa", "झुलसा"],
    "bph": ["brown planthopper", "bph", "bhoora tilla", "bhoora tela", "plant hopper", "planthopper", "hopper burn"],
    "pink_bollworm": ["pink bollworm", "gulabi sundhi", "sundhi", "bollworm", "गुलाबी सुंडी", "ਗੁਲਾਬੀ ਸੁੰਡੀ"],
    "whitefly": ["whitefly", "safed makhi", "chitta machhar", "safed machhar", "leaf curl", "सफेद मक्खी"],
}

SAFETY_KEYWORDS = [
    "banned", "monocrotophos", "endosulfan", "poison", "poisoning", "toxic",
    "paraquat", "phorate", "prohibited", "antidote", "safety", "ppe",
    "प्रतिबंधित", "जहर", "कीटनाशक सुरक्षा",
]

WEATHER_KEYWORDS = [
    "weather", "mausam", "rain", "barish", "varsa", "baarish", "meenh", "spray window",
    "wind", "temperature", "rainfall", "मौसम", "बारिश", "तापमान", "हवा", "ਮੀਂਹ", "ਮੌਸਮ",
]

# What a weather question actually asks about, so the answer only includes what was asked
SPRAY_KEYWORDS = [
    "spray", "sprays", "spraying", "chhidkaav", "chhidkav", "chidkav", "dawai", "dawa", "keetnashak", "pesticide",
    "छिड़काव", "दवा", "कीटनाशक", "ਛਿੜਕਾਅ", "ਦਵਾਈ", "ਸਪਰੇਅ", "ਕੀਟਨਾਸ਼ਕ",
]
IRRIGATION_KEYWORDS = [
    "irrigation", "irrigate", "watering", "paani", "pani", "sinchai", "sichai",
    "सिंचाई", "पानी", "ਸਿੰਚਾਈ", "ਪਾਣੀ",
]

# Words that keep a conversation about a scheme on that scheme even when a crop is named
SCHEME_FOLLOW_UP_WORDS = ["claim", "compensation", "premium", "insured", "interest", "loan", "limit", "collateral",
                          "dava", "daava", "muavza", "muaavza", "byaj", "karza", "दावा", "मुआवज़ा", "मुआवजा",
                          "प्रीमियम", "ब्याज", "ऋण", "ਦਾਅਵਾ", "ਮੁਆਵਜ਼ਾ", "ਪ੍ਰੀਮੀਅਮ", "ਵਿਆਜ", "ਕਰਜ਼ਾ"]
# "Scheme" in general; each scheme's own names are in its file in data/schemes/
SCHEME_KEYWORDS = ["yojana", "yojna", "scheme", "schemes", "sarkari yojana", "योजना", "योजनाएं", "ਯੋਜਨਾ", "ਯੋਜਨਾਵਾਂ"]

# Market prices: MSP and mandi rates
MARKET_KEYWORDS = [
    "msp", "minimum support price", "support price", "price", "prices", "rate", "rates", "bhav", "bhaav", "bhaw",
    "mandi", "keemat", "kimat", "daam", "samarthan mulya",
    "भाव", "मंडी", "कीमत", "दाम", "समर्थन मूल्य", "ਭਾਅ", "ਮੰਡੀ", "ਕੀਮਤ", "ਰੇਟ", "ਸਮਰਥਨ ਮੁੱਲ",
]
# "seed rate" is a sowing question and "stock market" is off-topic
NOT_MARKET = re.compile(r"seed rate|stock|growth rate|rate of (spray|application)|spray rate|dose rate", re.I)

# "Spray water" is watering (irrigation), not a pesticide spray
SPRAY_WATER = re.compile(
    r"\bspray(ing)?\s+(of\s+)?(water|paani|pani)\b|\b(water|paani|pani)\s+(ka\s+|di\s+)?(spray|chhidka+v)"
    r"|पानी\s*(का)?\s*छिड़काव|ਪਾਣੀ\s*(ਦਾ)?\s*ਛਿੜਕਾਅ"
)
# "Should I spray again?", "second spray": whether to repeat a treatment depends on the crop and the
# problem, not on the weather
REPEAT_SPRAY_KEYWORDS = ["again", "second", "once", "twice", "repeat", "another", "dobara", "dubara", "phir se",
                         "doosra", "dusra", "दोबारा", "फिर से", "दूसरा", "ਦੁਬਾਰਾ", "ਫਿਰ ਤੋਂ", "ਦੂਜਾ", "ਦੂਜੀ"]


def sprays_water(clean: str) -> bool:
    return bool(SPRAY_WATER.search(clean))


def asks_repeat_spray(clean: str) -> bool:
    """"I have sprayed once, should I spray again?" """
    return (not sprays_water(clean) and any(matches_keyword(k, clean) for k in SPRAY_KEYWORDS)
            and any(matches_keyword(k, clean) for k in REPEAT_SPRAY_KEYWORDS))


TIME_KEYWORDS = [
    "today", "now", "tonight", "tomorrow", "aaj", "abhi", "kal",
    "आज", "अभी", "कल", "ਅੱਜ", "ਹੁਣ", "ਕੱਲ੍ਹ",
]

GREETING_KEYWORDS = [
    "hello", "hi", "namaste", "namaskar", "sat sri akal", "pranam", "kisan sahayak",
    "ram ram", "salaam", "hey",
]

OUT_OF_SCOPE_KEYWORDS = [
    "cricket", "ipl", "movie", "film", "song", "politics", "election", "president", "minister",
    "football", "bollywood", "actor", "actress", "code", "python", "java", "stock market",
]

# Crops our verified advisories do NOT cover: answering these from another crop's advisory
# would give a wrong dose, so they get a "not covered, ask your KVK" reply instead
UNCOVERED_CROPS = {**{k: v for k, v in CROP_NAMES.items() if k not in COVERED_CROPS}, **OTHER_PLANTS}


BANNED_CHECK = AgriculturalGuardrails()


# Farming topics our verified advisories do NOT cover. Real Kisan Call Centre questions are mostly
# about these (weeds, nutrient deficiencies, varieties, prices...): answering them with the nearest
# advisory would give advice for a different problem, so they get a "not covered" reply instead.
UNCOVERED_TOPICS = {
    "weeds": ["weed", "weeds", "weedicide", "herbicide", "kharpatwar", "nadeen", "motha", "swank", "dila",
              "wild oats", "jangli jai", "phalaris", "gulli danda", "gullidanda", "खरपतवार", "नदीन", "मोथा",
              "गुल्ली डंडा", "गुल्लीडंडा", "ਨਦੀਨ", "ਨਦੀਨਾਂ", "ਮੋਥਾ", "ਨਦੀਨਨਾਸ਼ਕ", "ਗੁੱਲੀ ਡੰਡਾ", "ਗੁੱਲੀਡੰਡਾ"],
    "nutrient deficiency": ["deficiency", "zinc", "iron", "manganese", "boron", "calcium", "magnesium", "yellowing",
                            "kami", "कमी", "पीलापन", "पीला पड़", "ਘਾਟ", "ਪੀਲਾਪਣ", "ਪੀਲੀ ਪੈ", "जिंक", "ਜ਼ਿੰਕ"],
    "varieties": ["variety", "varieties", "hybrid", "hybrids", "kism", "kisme", "kismon", "kismein", "किस्म", "किस्में",
                  "हाइब्रिड", "ਕਿਸਮ", "ਕਿਸਮਾਂ", "ਹਾਈਬ੍ਰਿਡ"],
    "yield and growth": ["yield", "growth", "quality", "paidawar", "badhwar", "jhaad", "पैदावार", "बढ़वार", "गुणवत्ता",
                         "ਝਾੜ", "ਵਾਧਾ", "ਗੁਣਵੱਤਾ", "growth regulator", "foliar spray"],
    "nano fertilizers": ["nano urea", "nano dap", "नैनो", "ਨੈਨੋ"],
    "nursery and transplanting": ["nursery", "transplant", "transplanting", "seed treatment", "seedling", "नर्सरी",
                                  "रोपाई", "बीज उपचार", "ਪਨੀਰੀ", "ਲੁਆਈ", "ਬੀਜ ਨੂੰ ਸੋਧ", "ਬੀਜ ਸੋਧ"],
    "other pests and diseases": ["stem borer", "leaf folder", "root rot", "foot rot", "smut", "powdery mildew",
                                 "army worm", "armyworm", "thrips", "jassid", "jassids", "virus", "nematode",
                                 "nematodes", "wilt", "parawilt", "para wilt", "leaf spot", "root weevil", "fruit fly",
                                 "fruit flies", "termite", "termites", "rat", "rats", "rodent", "rodents",
                                 "downy mildew", "sucking pest", "sucking pests", "रस चूसने", "पाउडरी मिल्ड्यू", "चूर्णिल", "tana chhedak", "patta lapet", "jad galan", "deemak", "chuhe",
                                 "तना छेदक", "पत्ता लपेट", "जड़ गलन", "दीमक", "चूहे", "थ्रिप्स", "धब्बा", "ਥ੍ਰਿਪਸ", "ਥਰਿੱਪਸ",
                                 "mealybug", "mealy bug", "painted bug", "मिलीबग", "ਮਿਲੀਬੱਗ", "जैसिड", "ਜੈਸਿਡ",
                                 "ਗੜੂੰਆਂ", "ਪੱਤਾ ਲਪੇਟ", "ਜੜ੍ਹ", "ਸਿਉਂਕ", "ਚੂਹਿਆਂ", "ਕਾਂਗਿਆਰੀ", "ਸੋਕਾ ਰੋਗ"],
    # Caterpillars ("sundi") are covered for cotton only: see CROP_COVERED_TOPICS
    "pesticide mixing": ["tank mix", "tank mixing", "jar test", "mixing", "milakar", "मिलाकर", "ਮਿਕਸਿੰਗ",
                         "emamectin", "chlorpyriphos", "chloropyriphos", "cypermethrin", "इमामेक्टिन", "ਇਮਾਮੈਕਟਿਨ"],
    "irrigation timing": ["last irrigation", "aakhri paani", "आखिरी सिंचाई", "ਆਖ਼ਰੀ ਪਾਣੀ"],
    "harvest and storage": ["harvest", "harvesting", "storage", "maturity", "pakne", "पकने", "ਪੱਕਣ", "khali", "खली"],
    "straw management": ["straw", "stubble", "parali", "पराली", "ਪਰਾਲੀ", "ਨਾੜ"],
}
# Words that point back to an earlier question ("this disease", "iska ilaj")
REFERS_BACK = ["this", "it", "that", "these", "iska", "iski", "iske", "uska", "uski", "iss",
               "इस", "इसका", "इसकी", "इसके", "उस", "ਇਸ", "ਇਹ", "ਇਸਦੇ", "ਇਸ ਦੀ", "ਉਸ"]

# Topics covered for some crops only: (topic, words, crops whose advisories answer them)
CROP_COVERED_TOPICS = [
    ("fertilizer", ["fertilizer", "fertiliser", "khaad", "khad", "urea", "npk", "खाद", "ਖਾਦ"], {"Wheat", "Mustard"}),
    ("sulphur", ["sulphur", "sulfur", "gandhak", "गंधक", "ਗੰਧਕ", "ਸਲਫ਼ਰ"], {"Mustard"}),
    ("irrigation", ["irrigation", "irrigate", "paani", "pani", "water", "sinchai", "सिंचाई", "पानी", "ਪਾਣੀ", "ਸਿੰਚਾਈ"],
     {"Wheat", "Mustard"}),
    ("sowing", ["sowing", "sow", "seed rate", "bijai", "buwai", "बुवाई", "बिजाई", "ਬਿਜਾਈ"], {"Wheat"}),
    # "sundi" (caterpillar) in cotton is the bollworm our cotton advisory covers
    ("caterpillars", ["caterpillar", "catterpiller", "caterpiller", "sundi", "सुंडी", "ਸੁੰਡੀ", "illi", "illiyon", "bollworm"], {"Cotton"}),
]


# Crops each pest or disease is covered for ("aphid in cotton" is not covered: only wheat and mustard aphids are)
TOPIC_CROPS = {
    "Yellow Rust": {"Wheat"}, "Karnal Bunt": {"Wheat"}, "Aphid": {"Wheat", "Mustard"}, "White Rust": {"Mustard"},
    "Sheath Blight": {"Paddy"}, "Blb": {"Paddy"}, "Bph": {"Paddy"}, "Pink Bollworm": {"Cotton"}, "Whitefly": {"Cotton"},
}


# English words for the Hindi, Punjabi and Hinglish topic words above. PAU's Package of Practices is in
# English, so a question answered from it is searched with these ("धान में जिंक की कमी" -> "zinc deficiency").
SEARCH_TERMS = {
    "kharpatwar": "weeds", "nadeen": "weeds", "motha": "motha weeds", "swank": "swank weeds", "dila": "dila weeds",
    "jangli jai": "wild oats", "gulli danda": "Phalaris minor", "gullidanda": "Phalaris minor",
    "खरपतवार": "weeds", "नदीन": "weeds", "मोथा": "motha weeds", "गुल्ली डंडा": "Phalaris minor",
    "गुल्लीडंडा": "Phalaris minor", "ਨਦੀਨ": "weeds", "ਨਦੀਨਾਂ": "weeds", "ਮੋਥਾ": "motha weeds",
    "ਨਦੀਨਨਾਸ਼ਕ": "weedicide", "ਗੁੱਲੀ ਡੰਡਾ": "Phalaris minor", "ਗੁੱਲੀਡੰਡਾ": "Phalaris minor",
    "kami": "deficiency", "कमी": "deficiency", "पीलापन": "yellowing", "पीला पड़": "yellowing", "ਘਾਟ": "deficiency",
    "ਪੀਲਾਪਣ": "yellowing", "ਪੀਲੀ ਪੈ": "yellowing", "जिंक": "zinc", "ਜ਼ਿੰਕ": "zinc",
    "kism": "varieties", "kisme": "varieties", "kismon": "varieties", "kismein": "varieties", "किस्म": "varieties",
    "किस्में": "varieties", "ਕਿਸਮ": "varieties", "ਕਿਸਮਾਂ": "varieties",
    "paidawar": "yield", "badhwar": "growth", "jhaad": "yield", "पैदावार": "yield", "बढ़वार": "growth",
    "गुणवत्ता": "quality", "ਝਾੜ": "yield", "ਵਾਧਾ": "growth", "ਗੁਣਵੱਤਾ": "quality",
    "नैनो": "nano", "ਨੈਨੋ": "nano",
    "नर्सरी": "nursery", "रोपाई": "transplanting", "बीज उपचार": "seed treatment", "ਪਨੀਰੀ": "nursery",
    "ਲੁਆਈ": "transplanting", "ਬੀਜ ਨੂੰ ਸੋਧ": "seed treatment", "ਬੀਜ ਸੋਧ": "seed treatment",
    "रस चूसने": "sucking pests", "पाउडरी मिल्ड्यू": "powdery mildew", "चूर्णिल": "powdery mildew",
    "tana chhedak": "stem borer", "patta lapet": "leaf folder", "jad galan": "root rot", "deemak": "termites",
    "chuhe": "rats rodents", "तना छेदक": "stem borer", "पत्ता लपेट": "leaf folder", "जड़ गलन": "root rot",
    "दीमक": "termites", "चूहे": "rats rodents", "थ्रिप्स": "thrips", "धब्बा": "leaf spot",
    "मिलीबग": "mealybug", "ਮਿਲੀਬੱਗ": "mealybug", "जैसिड": "jassid", "ਜੈਸਿਡ": "jassid",
    "हाइब्रिड": "hybrids", "ਹਾਈਬ੍ਰਿਡ": "hybrids", "parali": "paddy straw", "पराली": "paddy straw",
    "ਪਰਾਲੀ": "paddy straw", "ਨਾੜ": "straw",
    "ਥ੍ਰਿਪਸ": "thrips", "ਥਰਿੱਪਸ": "thrips", "ਗੜੂੰਆਂ": "stem borer", "ਪੱਤਾ ਲਪੇਟ": "leaf folder", "ਜੜ੍ਹ": "root rot", "ਸਿਉਂਕ": "termites",
    "ਚੂਹਿਆਂ": "rats rodents", "ਕਾਂਗਿਆਰੀ": "smut", "ਸੋਕਾ ਰੋਗ": "wilt",
    "milakar": "tank mixing", "मिलाकर": "tank mixing", "ਮਿਕਸਿੰਗ": "tank mixing", "इमामेक्टिन": "emamectin",
    "ਇਮਾਮੈਕਟਿਨ": "emamectin",
    "aakhri paani": "last irrigation", "आखिरी सिंचाई": "last irrigation", "ਆਖ਼ਰੀ ਪਾਣੀ": "last irrigation",
    "pakne": "maturity harvesting", "पकने": "maturity harvesting", "ਪੱਕਣ": "maturity harvesting",
    "khali": "cake", "खली": "cake",
    "khaad": "fertilizer", "khad": "fertilizer", "खाद": "fertilizer", "ਖਾਦ": "fertilizer",
    "gandhak": "sulphur", "गंधक": "sulphur", "ਗੰਧਕ": "sulphur", "ਸਲਫ਼ਰ": "sulphur",
    "paani": "irrigation", "pani": "irrigation", "sinchai": "irrigation", "सिंचाई": "irrigation",
    "पानी": "irrigation", "ਪਾਣੀ": "irrigation", "ਸਿੰਚਾਈ": "irrigation",
    "bijai": "sowing", "buwai": "sowing", "बुवाई": "sowing", "बिजाई": "sowing", "ਬਿਜਾਈ": "sowing",
    "sundi": "caterpillar bollworm", "सुंडी": "caterpillar bollworm", "ਸੁੰਡੀ": "caterpillar bollworm",
    "illi": "caterpillar", "illiyon": "caterpillar",
}


# Words PAU uses in the titles of the sections on each topic ("Weed Control", "Plant Protection - Insect Pests")
TOPIC_HINTS = {
    "weeds": "weed control", "nutrient deficiency": "fertilizer application", "varieties": "improved varieties",
    "yield and growth": "fertilizer application", "nursery and transplanting": "nursery transplanting",
    "other pests and diseases": "insect pests diseases", "pesticide mixing": "spray technology",
    "irrigation timing": "irrigation", "harvest and storage": "harvesting storage", "fertilizer": "fertilizer application",
    "sulphur": "fertilizer application", "irrigation": "irrigation", "sowing": "sowing",
    "caterpillars": "insect pests bollworms", "straw management": "straw management",
}


def topic_search_terms(clean: str) -> str:
    """The farming topics a question names, in English, with the words PAU uses in its section titles
    ("गेहूं में गुल्ली डंडा" -> "Phalaris minor weed control")."""
    topics = list(UNCOVERED_TOPICS.items()) + [(topic, words) for topic, words, _ in CROP_COVERED_TOPICS]
    terms = []
    for topic, words in topics:
        matched = [w for w in words if matches_keyword(w, clean)]
        for word in matched + ([TOPIC_HINTS[topic]] if matched and topic in TOPIC_HINTS else []):
            term = SEARCH_TERMS.get(word, word if word.isascii() else None)
            if term and term not in terms:
                terms.append(term)
    return " ".join(terms)


def uncovered_topic(clean: str, crop: Optional[str]) -> Optional[str]:
    """The uncovered topic a question asks about, or None if our advisories may answer it."""
    # Topics we never cover win: "weeds in wheat after irrigation" is a weeds question
    for topic, words in UNCOVERED_TOPICS.items():
        if any(matches_keyword(w, clean) for w in words):
            return topic
    for topic, words, crops in CROP_COVERED_TOPICS:
        if any(matches_keyword(w, clean) for w in words):
            if crop in crops:
                return None  # e.g. fertilizer for wheat: covered
            if crop:
                return f"{topic} for {crop.lower()}"
    return None


def normalize_indic(text: str) -> str:
    """One spelling for letters that can be written several ways.

    Speech-to-text and keyboards mix Gurmukhi bindi (ਂ) and tippi (ੰ), which sound the same
    (ਕੁਂਗੀ = ਕੁੰਗੀ), and nukta letters can be one character or two (ਫ਼).
    """
    return unicodedata.normalize("NFC", text).replace("ਂ", "ੰ")


def matches_keyword(keyword: str, text: str, whole_word: bool = False) -> bool:
    """Match a keyword in any script. Indian-script topic words are stems and may match inside longer
    words; pass whole_word=True for names (crops), which must not ("तिल" is not in "तिलहन")."""
    kw = keyword.lower().strip()
    if kw.isascii():
        return contains_term(kw, text)
    return contains_term(normalize_indic(kw), normalize_indic(text), whole_word=whole_word)


def detect_covered_crop(clean: str) -> Optional[str]:
    """The covered crop a question names (wheat, mustard, paddy, cotton), in any script."""
    for crop_name, aliases in CROPS_DICT.items():
        if any(matches_keyword(alias, clean, whole_word=True) for alias in aliases):
            return crop_name.capitalize()
    return None


def detect_pest(clean: str) -> Optional[str]:
    """The covered pest or disease a question names. The most specific (longest) name wins:
    "safed kungi" is white rust, not "kungi" (yellow rust); "bhoora tilla" is brown planthopper, not "tilla" (aphid)."""
    matches = [
        (len(alias), topic) for topic, aliases in PESTS_AND_DISEASES.items()
        for alias in aliases if matches_keyword(alias, clean)
    ]
    return max(matches)[1].replace("_", " ").title() if matches else None


def weather_topics(query: str) -> set:
    """Which extra advice a weather question asks for: {"spray", "irrigation"} or empty."""
    clean = query.lower()
    topics = set()
    if sprays_water(clean):
        return {"irrigation"}
    if any(matches_keyword(k, clean) for k in SPRAY_KEYWORDS):
        topics.add("spray")
    if any(matches_keyword(k, clean) for k in IRRIGATION_KEYWORDS):
        topics.add("irrigation")
    return topics


class IntentRouter:
    """Classifies user query intent with multilingual agricultural entity extraction."""

    def __init__(self, pau_available: bool = False):
        # With PAU's Package of Practices loaded, questions about a covered crop on a topic our own
        # advisories don't cover (weeds, varieties, fertilizer for paddy...) are answered from PAU
        # instead of being referred to the KVK. The pipeline sets this when the chapters are indexed.
        self.pau_available = pau_available

    def classify(self, query: str) -> IntentResult:
        clean = query.lower().strip()

        # Rule 1. Greetings
        if any(matches_keyword(g, clean) for g in GREETING_KEYWORDS) and len(clean.split()) <= 4:
            return IntentResult(
                intent="greeting",
                confidence=0.98,
                reasoning="Short conversational greeting identified.",
            )

        # Rule 2. Government scheme questions (before the off-topic check: "minister" or "government"
        # appear in legitimate eligibility questions). A scheme we have no checked guidance for is
        # recognised by name, so it is never answered with PM-KISAN's rules.
        other = detect_other_scheme(clean)
        scheme = None if other else detect_scheme(clean)
        if other or scheme or any(matches_keyword(k, clean) for k in SCHEME_KEYWORDS):
            topic = f"{OTHER_SCHEME_PREFIX}{other[0]}" if other else scheme  # None: no scheme named
            return IntentResult(
                intent="scheme_query",
                confidence=0.93,
                detected_topic=topic,
                reasoning=f"Question about a government scheme: {topic or 'not named'}.",
            )

        # Rule 3. Market prices (before the off-topic and crop checks: "MSP of maize" is a price question)
        if not NOT_MARKET.search(clean) and any(matches_keyword(k, clean) for k in MARKET_KEYWORDS):
            return IntentResult(
                intent="market_price",
                confidence=0.92,
                detected_topic="Market prices",
                detected_district=detect_place(query),
                reasoning="Question about MSP or mandi prices.",
            )

        # Rule 4. Off-topic questions
        for oos in OUT_OF_SCOPE_KEYWORDS:
            if matches_keyword(oos, clean):
                return IntentResult(
                    intent="out_of_scope",
                    confidence=0.92,
                    reasoning=f"Query references non-agricultural topic: '{oos}'",
                )

        # What the question is about: place (verified later by geocoding), covered crop, pest or disease
        detected_district: Optional[str] = detect_place(query)
        detected_crop = detect_covered_crop(clean)
        detected_topic = detect_pest(clean)

        # Rule 5. Weather and spray timing
        # "Can I spray today?" is a spray-timing (weather) question unless a pest is named or it asks
        # whether to spray again; "Should I spray water today?" asks when to irrigate
        asks_today = any(matches_keyword(k, clean) for k in TIME_KEYWORDS)
        asks_spray_timing = (
            not detected_topic and asks_today and not asks_repeat_spray(clean)
            and (sprays_water(clean) or any(matches_keyword(k, clean) for k in SPRAY_KEYWORDS))
        )
        if asks_spray_timing or any(matches_keyword(w, clean) for w in WEATHER_KEYWORDS):
            return IntentResult(
                intent="weather",
                confidence=0.96,
                detected_crop=detected_crop,
                detected_topic="Ag-Weather & Spray Window Advisory",
                detected_district=detected_district,
                reasoning="Agricultural weather, rainfall probability, or spraying condition query.",
            )

        # Rule 6. Pesticide safety (a banned pesticide named in any script counts, so the warning
        # always wins, e.g. over "crop not covered" for "मोनोक्रोटोफॉस on brinjal")
        if any(matches_keyword(s, clean) for s in SAFETY_KEYWORDS) or BANNED_CHECK.check_banned_chemicals(query)[0]:
            return IntentResult(
                intent="safety_query",
                confidence=0.95,
                detected_crop=detected_crop,
                detected_topic=detected_topic,
                detected_district=detected_district,
                reasoning="Query specifically pertains to pesticide bans, toxicity, or safety protocols.",
            )

        # Rule 7. A crop our advisories don't cover (and none they do): say so instead of answering
        # from another crop's advisory. Banned-pesticide questions were handled above.
        if not detected_crop:
            uncovered = next(
                (name for name, aliases in UNCOVERED_CROPS.items() if any(matches_keyword(a, clean, whole_word=True) for a in aliases)),
                None,
            )
            if uncovered:
                return IntentResult(
                    intent="crop_not_covered",
                    confidence=0.9,
                    detected_topic=uncovered,
                    reasoning=f"Question about {uncovered}, which the verified advisories do not cover.",
                )

        # Rule 8. A farming topic our advisories don't cover (weeds, deficiencies, varieties, prices...) when no
        # pest or disease we cover is named, or a covered pest asked about another crop ("aphid in cotton")
        topic_gap = None
        if not detected_topic:
            topic_gap = uncovered_topic(clean, detected_crop)
        elif detected_crop and detected_crop not in TOPIC_CROPS.get(detected_topic, {detected_crop}):
            topic_gap = f"{detected_topic.lower()} in {detected_crop.lower()}"
        if topic_gap and self.pau_available and detected_crop:
            return IntentResult(
                intent="crop_question",
                confidence=0.85,
                detected_crop=detected_crop,
                # English words for the search (PAU's book is in English); the topic name if none
                detected_topic=(topic_search_terms(clean) if not detected_topic else "") or topic_gap,
                detected_district=detected_district,
                use_pau=True,
                reasoning=f"Question about {topic_gap}: answered from PAU's Package of Practices.",
            )
        if topic_gap:
            return IntentResult(
                intent="topic_not_covered",
                confidence=0.85,
                detected_crop=detected_crop,
                detected_topic=topic_gap,
                reasoning=f"Question about {topic_gap}, which the verified advisories do not cover.",
            )

        # Rule 9. Crop pest and disease questions
        if detected_topic or (detected_crop and any(w in clean for w in ["spray", "disease", "pest", "control", "ilaj", "roktham", "dawa", "dawai", "keeda", "keet"])):
            return IntentResult(
                intent="crop_question",
                confidence=0.94,
                detected_crop=detected_crop,
                detected_topic=detected_topic,
                detected_district=detected_district,
                reasoning="Identified disease/pest management query for crop.",
            )

        # Rule 10. General farming (irrigation, sowing, fertilizer)
        agri_words = ["irrigation", "sowing", "seed", "fertilizer", "urea", "dap", "paani", "bijai", "khad", "soil", "kheti", "yield", "pau", "icar"]
        if detected_crop or any(w in clean for w in agri_words):
            return IntentResult(
                intent="general_agriculture",
                confidence=0.88,
                detected_crop=detected_crop,
                detected_topic=detected_topic or "Agronomy/General",
                detected_district=detected_district,
                reasoning="Query pertains to crop production, agronomic management, or soil/fertilizer.",
            )

        # Default fallback: Treat as general agriculture to attempt retrieval before rejecting
        return IntentResult(
            intent="general_agriculture",
            confidence=0.70,
            detected_crop=detected_crop,
            detected_topic=detected_topic,
            detected_district=detected_district,
            reasoning="Defaulted to general agriculture for knowledge retrieval.",
        )

    def classify_with_context(self, query: str, history=None) -> IntentResult:
        """Classify a message, filling in crop, pest or place from earlier turns for follow-ups.

        `history` is the conversation so far (a list of ConversationTurn, oldest first) or a
        single previous turn. The whole conversation is searched, not just the last turn:
        "What was the dose again?" still means mustard aphids after a weather question in between,
        and "aur Sangrur mein?" after a weather question asks for Sangrur's weather.
        """
        if isinstance(history, ConversationTurn):
            history = [history]
        history = list(history or [])
        result = self.classify(query)
        if not history:
            return result
        result = self._refers_back(query, result)
        result = self._pau_topic_follow_up(query, result, history)
        place_reply = self._place_reply(query, result, history[-1])
        if place_reply:
            return place_reply
        if history[-1].awaiting_crop and result.detected_crop and result.intent in CROP_INTENTS + ("topic_not_covered",):
            # "Wheat, for aphids" answering "which crop and problem?": search it with the original question
            result.follow_up_of = history[-1].query
            if result.intent == "general_agriculture":
                result.intent = "crop_question"
            result.reasoning += " Reply to 'which crop?': the original question is added to the search."
            return result
        if result.intent in ("greeting", "out_of_scope", "crop_not_covered", "topic_not_covered"):
            return result
        # Checked in this order; the first that applies decides
        for follow_up in (self._price_follow_up, self._scheme_follow_up, self._weather_follow_up, self._crop_follow_up):
            decided = follow_up(query, result, history)
            if decided is not None:
                return decided
        return result

    @staticmethod
    def _refers_back(query: str, result: IntentResult) -> IntentResult:
        """"Which varieties resist this disease?" asks about the earlier topic, not about varieties in general."""
        if result.intent == "topic_not_covered" and any(matches_keyword(w, query.lower()) for w in REFERS_BACK):
            return IntentResult(intent="general_agriculture", confidence=0.7, detected_crop=result.detected_crop,
                                reasoning="Refers back to an earlier question.")
        return result

    def _pau_topic_follow_up(self, query: str, result: IntentResult, history: List[ConversationTurn]) -> IntentResult:
        """"And weeds?" after a wheat question: a topic our advisories don't cover, for the crop of the
        last crop question, is answered from PAU's Package of Practices."""
        if not (self.pau_available and result.intent == "topic_not_covered" and not result.detected_crop):
            return result
        last_crop = next((turn for turn in reversed(history) if turn.intent in CROP_INTENTS and turn.crop), None)
        if not last_crop:
            return result
        return IntentResult(
            intent="crop_question",
            confidence=0.8,
            detected_crop=last_crop.crop,
            detected_topic=topic_search_terms(query.lower().strip()) or result.detected_topic,
            detected_district=result.detected_district,
            use_pau=True,
            reasoning=f"Question about {result.detected_topic} for {last_crop.crop} (earlier question): answered from PAU.",
        )

    @staticmethod
    def _place_reply(query: str, result: IntentResult, previous: ConversationTurn) -> Optional[IntentResult]:
        """The last answer asked "which place?": a short reply ("NOIDA", "Sangrur", "ਸੰਗਰੂਰ") is the place,
        and the original weather or price question is answered for it."""
        topic_named = result.detected_topic not in (None, "Agronomy/General", "Market prices",
                                                    "Ag-Weather & Spray Window Advisory")
        if not (previous.awaiting_place and len(query.split()) <= 4
                and result.intent not in ("greeting", "out_of_scope", "scheme_query")
                and not result.detected_crop and not topic_named):
            return None
        return IntentResult(
            intent=previous.intent,
            confidence=0.9,
            detected_topic="Market prices" if previous.intent == "market_price" else "Ag-Weather & Spray Window Advisory",
            detected_district=result.detected_district or query.strip(" ?.!,").title(),
            follow_up_of=previous.query,
            reasoning="Reply to 'which place?': answering the earlier question for this place.",
        )

    @staticmethod
    def _price_follow_up(query: str, result: IntentResult, history: List[ConversationTurn]) -> Optional[IntentResult]:
        """Prices keep the place of the last price question ("rice ka rate?" after Delhi), and short
        follow-ups ("and mustard?", "Sangrur mandi?") right after a price answer stay on prices."""
        last_market = next((turn for turn in reversed(history) if turn.intent == "market_price"), None)
        # A place named in an earlier price question (not one filled in from the farm profile)
        market_place = (
            last_market.district if last_market and last_market.district and not last_market.district_from_profile else None
        )
        if result.intent == "market_price":
            if not result.detected_district and market_place:
                result.detected_district = market_place
                result.reasoning += " Place carried over from an earlier price question."
            return result
        previous = history[-1]
        if previous.intent == "market_price" and len(query.split()) <= 6 and (
            result.detected_crop or result.detected_district or result.intent == "crop_not_covered"
        ):
            return IntentResult(
                intent="market_price",
                confidence=0.85,
                detected_topic="Market prices",
                detected_district=result.detected_district or market_place,
                follow_up_of=previous.query,
                reasoning="Follow-up to the previous price question.",
            )
        return None

    @staticmethod
    def _scheme_follow_up(query: str, result: IntentResult, history: List[ConversationTurn]) -> Optional[IntentResult]:
        """"How do I apply?" / "What documents?" right after a scheme answer: the same scheme. So is
        "How do I claim if hail damages my wheat?" after a crop insurance answer, though it names a crop."""
        about_scheme = _names_no_subject(result) or any(matches_keyword(w, query.lower()) for w in SCHEME_FOLLOW_UP_WORDS)
        if history[-1].intent == "scheme_query" and about_scheme and result.intent in CROP_INTENTS:
            return IntentResult(
                intent="scheme_query",
                confidence=0.85,
                detected_topic=history[-1].topic,
                follow_up_of=history[-1].query,
                reasoning=f"Follow-up to the previous question about {history[-1].topic or 'a scheme'}.",
            )
        return None

    @staticmethod
    def _weather_follow_up(query: str, result: IntentResult, history: List[ConversationTurn]) -> Optional[IntentResult]:
        """Weather keeps the place of the last weather question, and "aur Sangrur?" / "kal?" after a
        weather answer stay on weather."""
        if result.intent == "weather":
            last_weather = next((turn for turn in reversed(history) if turn.intent == "weather"), None)
            if (not result.detected_district and last_weather and last_weather.district
                    and not last_weather.district_from_profile):
                result.detected_district = last_weather.district
                result.reasoning += " Place carried over from an earlier weather question."
            return result
        previous = history[-1]
        if (previous.intent == "weather" and _names_no_subject(result) and not asks_repeat_spray(query.lower())
                and (result.detected_district or weather_topics(query))):
            return IntentResult(
                intent="weather",
                confidence=0.85,
                detected_topic="Ag-Weather & Spray Window Advisory",
                detected_district=result.detected_district or (None if previous.district_from_profile else previous.district),
                follow_up_of=previous.query,  # "Sangrur" answering "Can I spray today?" keeps the spray question
                reasoning="Follow-up to the previous weather question.",
            )
        return None

    @staticmethod
    def _crop_follow_up(query: str, result: IntentResult, history: List[ConversationTurn]) -> Optional[IntentResult]:
        """Crop, pest and safety follow-ups use the most recent crop question, even if other questions
        (e.g. weather) came in between."""
        last_crop = next((turn for turn in reversed(history) if turn.intent in CROP_INTENTS and turn.crop), None)
        if not last_crop or result.intent not in CROP_INTENTS:
            return None
        previous_topic = last_crop.topic if last_crop.topic not in (None, "Agronomy/General") else None
        if _names_no_subject(result):
            # "What is the dose?" / "Is it dangerous?" -> same crop and pest as before
            inherited = "crop_question" if last_crop.intent == "image_diagnosis" else last_crop.intent
            return IntentResult(
                intent=result.intent if result.confidence > 0.70 else inherited,
                confidence=0.85,
                detected_crop=last_crop.crop,
                detected_topic=previous_topic,
                detected_district=result.detected_district,
                follow_up_of=last_crop.query,
                use_pau=last_crop.used_pau,
                reasoning="Follow-up: crop and pest carried over from an earlier question.",
            )
        topic = result.detected_topic if result.detected_topic not in (None, "Agronomy/General") else None
        if result.detected_crop and not topic and previous_topic and len(query.split()) <= 5:
            # "What about wheat?" -> same pest, new crop
            result.detected_topic = previous_topic
            result.intent = "crop_question"
            result.use_pau = last_crop.used_pau
            result.reasoning = "Follow-up: pest carried over to a new crop."
        return result


# A photo diagnosis counts as a crop question, so "What is the dose?" after a photo stays on it
CROP_INTENTS = ("crop_question", "general_agriculture", "safety_query", "image_diagnosis")


def _names_no_subject(result: IntentResult) -> bool:
    """True when a message names neither a crop nor a pest ("What is the dose?")."""
    topic = result.detected_topic if result.detected_topic not in (None, "Agronomy/General") else None
    return not result.detected_crop and not topic
