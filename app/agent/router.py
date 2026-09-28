import re
from typing import Optional
from app.agent.state import ConversationTurn, IntentResult
from app.tools.location import detect_place

# Lexicons for multilingual agricultural intent detection
CROPS_DICT = {
    "wheat": ["wheat", "gehun", "gehu", "kanak", "गेहूं", "ਕਣਕ"],
    "mustard": ["mustard", "sarson", "sarsonn", "raya", "सरसों", "ਸਰ੍ਹੋਂ"],
    "paddy": ["paddy", "rice", "dhan", "jhona", "धान", "ਝੋਨਾ", "ਝੋਨੇ"],
    "cotton": ["cotton", "kapas", "narma", "कपास", "ਨਰਮਾ", "ਨਰਮੇ"],
}

PESTS_AND_DISEASES = {
    "yellow_rust": ["yellow rust", "peeli kungi", "pila rataua", "puccinia", "kungi", "पीली कुंगी", "ਪੀਲੀ ਕੁੰਗੀ"],
    "karnal_bunt": ["karnal bunt", "tilletia", "bunt", "करनाल बंट"],
    "aphid": ["aphid", "aphids", "mahu", "mahun", "chetpa", "chepa", "tilla", "माहू", "ਚੇਪਾ", "ਚੇਪੇ"],
    "white_rust": ["white rust", "safed kungi", "blister", "सफेद कुंगी"],
    "blb": ["bacterial leaf blight", "blb", "peela jhulsa", "jhulsa", "झुलसा"],
    "bph": ["brown planthopper", "bph", "bhoora tilla", "hopper burn"],
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

TIME_KEYWORDS = [
    "today", "now", "tonight", "tomorrow", "aaj", "abhi", "kal",
    "आज", "अभी", "कल", "ਅੱਜ", "ਹੁਣ", "ਕੱਲ੍ਹ",
]

GREETING_KEYWORDS = [
    "hello", "hi", "namaste", "namaskar", "sat sri akal", "pranam", "kisan sahayak",
    "ram ram", "salaam", "hey",
]

OUT_OF_SCOPE_KEYWORDS = [
    "cricket", "movie", "song", "politics", "president", "minister",
    "football", "bollywood", "code", "python", "java", "stock market",
]


def matches_keyword(keyword: str, text: str) -> bool:
    """Match keyword supporting both ASCII word boundaries and Unicode Indic scripts."""
    kw = keyword.lower().strip()
    if any(ord(c) > 127 for c in kw):
        return kw in text
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
        detected_topic: Optional[str] = None
        for topic_name, aliases in PESTS_AND_DISEASES.items():
            if any(matches_keyword(alias, clean) for alias in aliases):
                detected_topic = topic_name.replace("_", " ").title()
                break

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

        # 7. Check for Safety Query
        if any(matches_keyword(s, clean) for s in SAFETY_KEYWORDS):
            return IntentResult(
                intent="safety_query",
                confidence=0.95,
                detected_crop=detected_crop,
                detected_topic=detected_topic,
                detected_district=detected_district,
                reasoning="Query specifically pertains to pesticide bans, toxicity, or safety protocols.",
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

    def classify_with_context(self, query: str, previous: Optional[ConversationTurn] = None) -> IntentResult:
        """Classify a message, filling in crop, pest or place from the previous turn for follow-ups.

        "What is the dose?" after an aphid question stays on mustard aphids; "aur Sangrur mein?"
        after a weather question asks for Sangrur's weather.
        """
        result = self.classify(query)
        if previous is None or result.intent in ("greeting", "out_of_scope"):
            return result

        topic = result.detected_topic if result.detected_topic not in (None, "Agronomy/General") else None
        names_no_subject = not result.detected_crop and not topic

        # Follow-ups to a weather answer
        if previous.intent == "weather":
            if result.intent == "weather":
                if not result.detected_district and previous.district:
                    result.detected_district = previous.district
                    result.reasoning += " Place carried over from the previous question."
                return result
            if names_no_subject and (result.detected_district or weather_topics(query)):
                return IntentResult(
                    intent="weather",
                    confidence=0.85,
                    detected_topic="Ag-Weather & Spray Window Advisory",
                    detected_district=result.detected_district or previous.district,
                    reasoning="Follow-up to the previous weather question.",
                )
            return result

        # Follow-ups to a crop / pest / safety answer
        crop_intents = ("crop_question", "general_agriculture", "safety_query")
        if previous.intent in crop_intents and result.intent in crop_intents:
            previous_topic = previous.topic if previous.topic not in (None, "Agronomy/General") else None
            if names_no_subject and previous.crop:
                # "What is the dose?" -> same crop and pest as before
                return IntentResult(
                    intent=result.intent if result.confidence > 0.70 else previous.intent,
                    confidence=0.85,
                    detected_crop=previous.crop,
                    detected_topic=previous_topic,
                    detected_district=result.detected_district,
                    reasoning="Follow-up: crop and pest carried over from the previous question.",
                )
            if result.detected_crop and not topic and previous_topic and len(query.split()) <= 5:
                # "What about wheat?" -> same pest, new crop
                result.detected_topic = previous_topic
                result.intent = "crop_question"
                result.reasoning = "Follow-up: pest carried over to a new crop."
        return result
