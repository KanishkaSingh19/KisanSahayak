import re
import unicodedata
from typing import Optional
from app.agent.guardrails import AgriculturalGuardrails
from app.agent.state import ConversationTurn, IntentResult
from app.tools.location import detect_place

# Lexicons for multilingual agricultural intent detection
CROPS_DICT = {
    "wheat": ["wheat", "gehun", "gehu", "kanak", "गेहूं", "ਕਣਕ"],
    "mustard": ["mustard", "sarson", "sarsonn", "raya", "toria", "gobhi sarson", "rapeseed", "सरसों", "तोरिया", "ਸਰ੍ਹੋਂ",
                "ਸਰੋਂ", "ਤੋਰੀਆ", "ਤੋਰੀਏ", "ਰਾਇਆ"],
    "paddy": ["paddy", "rice", "dhan", "dhaan", "jhona", "basmati", "धान", "बासमती", "ਝੋਨਾ", "ਝੋਨੇ", "ਬਾਸਮਤੀ"],
    "cotton": ["cotton", "kapas", "narma", "कपास", "ਨਰਮਾ", "ਨਰਮੇ"],
}

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

SCHEME_KEYWORDS = [
    "pm kisan", "pm-kisan", "pmkisan", "kisan samman", "samman nidhi", "yojana", "yojna", "scheme",
    "ekyc", "e-kyc", "6000", "6,000",
    "पीएम किसान", "पीएम-किसान", "किसान सम्मान", "सम्मान निधि", "योजना",
    "ਪੀਐਮ ਕਿਸਾਨ", "ਪੀਐਮ-ਕਿਸਾਨ", "ਕਿਸਾਨ ਸਨਮਾਨ", "ਸਨਮਾਨ ਨਿਧੀ", "ਯੋਜਨਾ",
]

# Market prices: MSP and mandi rates
MARKET_KEYWORDS = [
    "msp", "minimum support price", "support price", "price", "prices", "rate", "rates", "bhav", "bhaav", "bhaw",
    "mandi", "keemat", "kimat", "daam", "samarthan mulya",
    "भाव", "मंडी", "कीमत", "दाम", "समर्थन मूल्य", "ਭਾਅ", "ਮੰਡੀ", "ਕੀਮਤ", "ਰੇਟ", "ਸਮਰਥਨ ਮੁੱਲ",
]
# "seed rate" is a sowing question and "stock market" is off-topic
NOT_MARKET = re.compile(r"seed rate|stock|growth rate|rate of (spray|application)|spray rate|dose rate", re.I)

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
UNCOVERED_CROPS = {
    "sugarcane": ["sugarcane", "ganna", "ganne", "गन्ना", "गन्ने", "ਗੰਨਾ", "ਗੰਨੇ"],
    "maize": ["maize", "corn", "makka", "makki", "मक्का", "ਮੱਕੀ"],
    "potato": ["potato", "aloo", "आलू", "ਆਲੂ"],
    "tomato": ["tomato", "tamatar", "टमाटर", "ਟਮਾਟਰ"],
    "onion": ["onion", "pyaz", "pyaaz", "प्याज", "ਪਿਆਜ਼"],
    "chilli": ["chilli", "chili", "mirch", "मिर्च", "ਮਿਰਚ"],
    "brinjal": ["brinjal", "eggplant", "baingan", "बैंगन", "ਬੈਂਗਣ"],
    "soybean": ["soybean", "soyabean", "सोयाबीन"],
    "chickpea": ["chickpea", "chana", "चना", "ਛੋਲੇ"],
    "groundnut": ["groundnut", "peanut", "moongphali", "मूंगफली", "ਮੂੰਗਫਲੀ"],
    "millet": ["bajra", "millet", "jowar", "बाजरा", "ज्वार", "ਬਾਜਰਾ"],
    "barley": ["barley", "jau", "जौ", "ਜੌਂ"],
    "vegetables": ["cauliflower", "cabbage", "gobhi", "okra", "bhindi", "गोभी", "भिंडी", "ਗੋਭੀ", "ਭਿੰਡੀ"],
    "fruits": ["mango", "banana", "apple", "grapes", "citrus", "kinnow", "आम", "केला", "ਕਿੰਨੂ", "ਅੰਬ"],
}


BANNED_CHECK = AgriculturalGuardrails()


# Farming topics our verified advisories do NOT cover. Real Kisan Call Centre questions are mostly
# about these (weeds, nutrient deficiencies, varieties, prices...): answering them with the nearest
# advisory would give advice for a different problem, so they get a "not covered" reply instead.
UNCOVERED_TOPICS = {
    "weeds": ["weed", "weeds", "weedicide", "herbicide", "kharpatwar", "nadeen", "motha", "swank", "dila",
              "wild oats", "jangli jai", "खरपतवार", "नदीन", "मोथा", "ਨਦੀਨ", "ਨਦੀਨਾਂ", "ਮੋਥਾ", "ਨਦੀਨਨਾਸ਼ਕ"],
    "nutrient deficiency": ["deficiency", "zinc", "iron", "manganese", "boron", "calcium", "magnesium", "yellowing",
                            "kami", "कमी", "पीलापन", "पीला पड़", "ਘਾਟ", "ਪੀਲਾਪਣ", "ਪੀਲੀ ਪੈ", "जिंक", "ਜ਼ਿੰਕ"],
    "varieties": ["variety", "varieties", "kism", "kisme", "kismon", "kismein", "किस्म", "किस्में", "ਕਿਸਮ", "ਕਿਸਮਾਂ"],
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
                                 "तना छेदक", "पत्ता लपेट", "जड़ गलन", "दीमक", "चूहे", "थ्रिप्स", "धब्बा",
                                 "ਗੜੂੰਆਂ", "ਪੱਤਾ ਲਪੇਟ", "ਜੜ੍ਹ", "ਸਿਉਂਕ", "ਚੂਹਿਆਂ", "ਕਾਂਗਿਆਰੀ", "ਸੋਕਾ ਰੋਗ"],
    # Caterpillars ("sundi") are covered for cotton only: see CROP_COVERED_TOPICS
    "pesticide mixing": ["tank mix", "tank mixing", "jar test", "mixing", "milakar", "मिलाकर", "ਮਿਕਸਿੰਗ",
                         "emamectin", "chlorpyriphos", "chloropyriphos", "cypermethrin", "इमामेक्टिन", "ਇਮਾਮੈਕਟਿਨ"],
    "irrigation timing": ["last irrigation", "aakhri paani", "आखिरी सिंचाई", "ਆਖ਼ਰੀ ਪਾਣੀ"],
    "harvest and storage": ["harvest", "harvesting", "storage", "maturity", "pakne", "पकने", "ਪੱਕਣ", "khali", "खली"],
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


def matches_keyword(keyword: str, text: str) -> bool:
    """Match keyword supporting both ASCII word boundaries and Unicode Indic scripts."""
    kw = keyword.lower().strip()
    if any(ord(c) > 127 for c in kw):
        return normalize_indic(kw) in normalize_indic(text)
    return bool(re.search(rf"\b{re.escape(kw)}\b", text))


def weather_topics(query: str) -> set:
    """Which extra advice a weather question asks for: {"spray", "irrigation"} or empty."""
    clean = query.lower()
    topics = set()
    if any(matches_keyword(k, clean) for k in SPRAY_KEYWORDS):
        topics.add("spray")
    if any(matches_keyword(k, clean) for k in IRRIGATION_KEYWORDS):
        topics.add("irrigation")
    return topics


class IntentRouter:
    """Classifies user query intent with multilingual agricultural entity extraction."""

    def classify(self, query: str) -> IntentResult:
        clean = query.lower().strip()

        # 1. Check for Greetings
        if any(matches_keyword(g, clean) for g in GREETING_KEYWORDS) and len(clean.split()) <= 4:
            return IntentResult(
                intent="greeting",
                confidence=0.98,
                reasoning="Short conversational greeting identified.",
            )

        # 1b. Government scheme questions (before the off-topic check: "minister" or "government"
        # appear in legitimate eligibility questions)
        if any(matches_keyword(k, clean) for k in SCHEME_KEYWORDS):
            return IntentResult(
                intent="scheme_query",
                confidence=0.93,
                detected_topic="PM-KISAN",
                reasoning="Question about the PM-KISAN government scheme.",
            )

        # 1c. Market prices (before the off-topic and crop checks: "MSP of maize" is a price question)
        if not NOT_MARKET.search(clean) and any(matches_keyword(k, clean) for k in MARKET_KEYWORDS):
            return IntentResult(
                intent="market_price",
                confidence=0.92,
                detected_topic="Market prices",
                detected_district=detect_place(query),
                reasoning="Question about MSP or mandi prices.",
            )

        # 2. Check for explicit Out-of-Scope indicators
        for oos in OUT_OF_SCOPE_KEYWORDS:
            if matches_keyword(oos, clean):
                return IntentResult(
                    intent="out_of_scope",
                    confidence=0.92,
                    reasoning=f"Query references non-agricultural topic: '{oos}'",
                )

        # 3. Detect District / place (any script; unknown names are verified later by geocoding)
        detected_district: Optional[str] = detect_place(query)

        # 4. Detect Crops
        detected_crop: Optional[str] = None
        for crop_name, aliases in CROPS_DICT.items():
            if any(matches_keyword(alias, clean) for alias in aliases):
                detected_crop = crop_name.capitalize()
                break

        # 5. Detect Pest/Disease Topic
        # The most specific (longest) matching name wins: "safed kungi" is white rust, not "kungi" (yellow rust),
        # and "bhoora tilla" is brown planthopper, not "tilla" (aphid)
        detected_topic: Optional[str] = None
        matches = [
            (len(alias), topic_name) for topic_name, aliases in PESTS_AND_DISEASES.items()
            for alias in aliases if matches_keyword(alias, clean)
        ]
        if matches:
            detected_topic = max(matches)[1].replace("_", " ").title()

        # 6. Check for Weather & Spray Window Query
        # "Can I spray today?" is a spray-timing (weather) question unless a pest is named
        asks_spray_timing = (
            not detected_topic
            and any(matches_keyword(k, clean) for k in SPRAY_KEYWORDS)
            and any(matches_keyword(k, clean) for k in TIME_KEYWORDS)
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

        # 7. Check for Safety Query (a banned pesticide named in any script counts, so the warning
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

        # 7b. A crop our advisories don't cover (and none they do): say so instead of answering
        # from another crop's advisory. Banned-pesticide questions were handled above.
        if not detected_crop:
            uncovered = next(
                (name for name, aliases in UNCOVERED_CROPS.items() if any(matches_keyword(a, clean) for a in aliases)),
                None,
            )
            if uncovered:
                return IntentResult(
                    intent="crop_not_covered",
                    confidence=0.9,
                    detected_topic=uncovered,
                    reasoning=f"Question about {uncovered}, which the verified advisories do not cover.",
                )

        # 7c. A farming topic our advisories don't cover (weeds, deficiencies, varieties, prices...) when no
        # pest or disease we cover is named, or a covered pest asked about another crop ("aphid in cotton")
        topic_gap = None
        if not detected_topic:
            topic_gap = uncovered_topic(clean, detected_crop)
        elif detected_crop and detected_crop not in TOPIC_CROPS.get(detected_topic, {detected_crop}):
            topic_gap = f"{detected_topic.lower()} in {detected_crop.lower()}"
        if topic_gap:
            return IntentResult(
                intent="topic_not_covered",
                confidence=0.85,
                detected_crop=detected_crop,
                detected_topic=topic_gap,
                reasoning=f"Question about {topic_gap}, which the verified advisories do not cover.",
            )

        # 8. Check for Crop-specific health/disease query
        if detected_topic or (detected_crop and any(w in clean for w in ["spray", "disease", "pest", "control", "ilaj", "roktham", "dawa", "dawai", "keeda", "keet"])):
            return IntentResult(
                intent="crop_question",
                confidence=0.94,
                detected_crop=detected_crop,
                detected_topic=detected_topic,
                detected_district=detected_district,
                reasoning="Identified disease/pest management query for crop.",
            )

        # 7. General Agriculture (irrigation, sowing, fertilizer, general farming query)
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
        if history and result.intent == "topic_not_covered" and any(matches_keyword(w, query.lower()) for w in REFERS_BACK):
            # "Which varieties resist this disease?" asks about the earlier topic, not about varieties in general
            result = IntentResult(
                intent="general_agriculture",
                confidence=0.7,
                detected_crop=result.detected_crop,
                reasoning="Refers back to an earlier question.",
            )
        if not history or result.intent in ("greeting", "out_of_scope", "crop_not_covered", "topic_not_covered"):
            return result

        # A photo diagnosis counts as a crop question, so "What is the dose?" after a photo stays on it
        crop_intents = ("crop_question", "general_agriculture", "safety_query", "image_diagnosis")
        previous = history[-1]
        last_weather = next((turn for turn in reversed(history) if turn.intent == "weather"), None)
        last_crop = next((turn for turn in reversed(history) if turn.intent in crop_intents and turn.crop), None)
        last_market = next((turn for turn in reversed(history) if turn.intent == "market_price"), None)
        # A place named in an earlier price question (not one filled in from the farm profile)
        market_place = (
            last_market.district if last_market and last_market.district and not last_market.district_from_profile else None
        )

        topic = result.detected_topic if result.detected_topic not in (None, "Agronomy/General") else None
        names_no_subject = not result.detected_crop and not topic

        # Price questions without a place keep the place of the last price question ("rice ka rate?" after Delhi)
        if result.intent == "market_price":
            if not result.detected_district and market_place:
                result.detected_district = market_place
                result.reasoning += " Place carried over from an earlier price question."
            return result

        # Market follow-ups: "and mustard?" / "what about rice?" / "Sangrur mandi?" right after a price answer
        if previous.intent == "market_price" and len(query.split()) <= 6 and result.intent != "market_price" and (
            result.detected_crop or result.detected_district or result.intent in ("crop_not_covered",)
        ):
            return IntentResult(
                intent="market_price",
                confidence=0.85,
                detected_topic="Market prices",
                detected_district=result.detected_district or market_place,
                follow_up_of=previous.query,
                reasoning="Follow-up to the previous price question.",
            )

        # Scheme follow-ups: "How do I apply?" / "What documents?" right after a PM-KISAN answer
        if previous.intent == "scheme_query" and names_no_subject and result.intent in crop_intents:
            return IntentResult(
                intent="scheme_query",
                confidence=0.85,
                detected_topic="PM-KISAN",
                follow_up_of=previous.query,
                reasoning="Follow-up to the previous PM-KISAN question.",
            )

        # Weather follow-ups
        if result.intent == "weather":
            if not result.detected_district and last_weather and last_weather.district and not last_weather.district_from_profile:
                result.detected_district = last_weather.district
                result.reasoning += " Place carried over from an earlier weather question."
            return result
        if previous.intent == "weather" and names_no_subject and (result.detected_district or weather_topics(query)):
            return IntentResult(
                intent="weather",
                confidence=0.85,
                detected_topic="Ag-Weather & Spray Window Advisory",
                detected_district=result.detected_district or (None if previous.district_from_profile else previous.district),
                reasoning="Follow-up to the previous weather question.",
            )

        # Crop / pest / safety follow-ups: use the most recent crop question, even if other
        # questions (e.g. weather) came in between
        if last_crop and result.intent in crop_intents:
            previous_topic = last_crop.topic if last_crop.topic not in (None, "Agronomy/General") else None
            if names_no_subject:
                # "What is the dose?" / "Is it dangerous?" -> same crop and pest as before
                inherited = "crop_question" if last_crop.intent == "image_diagnosis" else last_crop.intent
                return IntentResult(
                    intent=result.intent if result.confidence > 0.70 else inherited,
                    confidence=0.85,
                    detected_crop=last_crop.crop,
                    detected_topic=previous_topic,
                    detected_district=result.detected_district,
                    follow_up_of=last_crop.query,
                    reasoning="Follow-up: crop and pest carried over from an earlier question.",
                )
            if result.detected_crop and not topic and previous_topic and len(query.split()) <= 5:
                # "What about wheat?" -> same pest, new crop
                result.detected_topic = previous_topic
                result.intent = "crop_question"
                result.reasoning = "Follow-up: pest carried over to a new crop."
        return result
