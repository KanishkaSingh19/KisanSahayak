"""One list of crop names, used everywhere a crop must be recognised.

The question router, the market-price tool and the place detector all read these names, so a
spelling added here (a Hindi, Punjabi or Hinglish name) is understood by every feature at once.
"""

from typing import Dict, List

# Crops the verified advisories cover
COVERED_CROPS = ("wheat", "mustard", "paddy", "cotton")

# Crop -> names farmers use, in English, Hinglish, Hindi (Devanagari) and Punjabi (Gurmukhi)
CROP_NAMES: Dict[str, List[str]] = {
    "wheat": ["wheat", "gehun", "gehu", "kanak", "गेहूं", "गेहूँ", "ਕਣਕ"],
    "mustard": ["mustard", "sarson", "sarsonn", "raya", "toria", "gobhi sarson", "rapeseed", "सरसों", "तोरिया", "ਸਰ੍ਹੋਂ",
                "ਸਰੋਂ", "ਤੋਰੀਆ", "ਤੋਰੀਏ", "ਰਾਇਆ"],
    "paddy": ["paddy", "rice", "dhan", "dhaan", "jhona", "basmati", "धान", "बासमती", "ਝੋਨਾ", "ਝੋਨੇ", "ਬਾਸਮਤੀ"],
    "cotton": ["cotton", "kapas", "narma", "कपास", "ਨਰਮਾ", "ਨਰਮੇ", "ਕਪਾਹ"],
    "maize": ["maize", "corn", "makka", "makki", "मक्का", "ਮੱਕੀ"],
    # Not the bare word "gram": "50 gram Actara" is a dose, not chickpea
    "gram": ["chana", "chickpea", "bengal gram", "चना", "ਛੋਲੇ"],
    "barley": ["barley", "jau", "जौ", "ਜੌਂ"],
    "lentil": ["lentil", "masur", "masoor", "मसूर", "ਮਸਰ"],
    "moong": ["moong", "green gram", "मूंग", "ਮੂੰਗੀ"],
    "bajra": ["bajra", "pearl millet", "millet", "बाजरा", "ਬਾਜਰਾ"],
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
    "sugarcane": ["sugarcane", "ganna", "ganne", "गन्ना", "गन्ने", "ਗੰਨਾ", "ਗੰਨੇ"],
    "chilli": ["chilli", "chili", "mirch", "मिर्च", "ਮਿਰਚ"],
    "brinjal": ["brinjal", "eggplant", "baingan", "बैंगन", "ਬੈਂਗਣ"],
}

# Plant groups that are not covered either (no MSP or mandi lookup for them)
OTHER_PLANTS: Dict[str, List[str]] = {
    "vegetables": ["cauliflower", "cabbage", "gobhi", "okra", "bhindi", "गोभी", "भिंडी", "ਗੋਭੀ", "ਭਿੰਡੀ"],
    "fruits": ["mango", "banana", "apple", "grapes", "citrus", "kinnow", "आम", "केला", "ਕਿੰਨੂ", "ਅੰਬ"],
}

# Crops with MSP or mandi prices (sugarcane has a cane price set separately; chilli and brinjal no MSP)
PRICED_CROPS = tuple(k for k in CROP_NAMES if k not in ("sugarcane", "chilli", "brinjal"))


def latin_crop_words() -> set:
    """Every Latin-script crop word ("rice", "aloo"...): such words are never place names."""
    return {word for names in CROP_NAMES.values() for name in names if name.isascii() for word in name.split()}
