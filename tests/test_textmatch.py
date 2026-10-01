"""One whole-word matching rule for English, Hinglish, Hindi and Punjabi (app/textmatch.py)."""

import pytest

from app.agent.router import IntentRouter
from app.textmatch import contains_term


@pytest.mark.parametrize("term,text,expected", [
    ("rate", "what is the rate", True),
    ("rate", "pirate ship", False),                 # Latin: whole words only
    ("तिल", "तिल की खेती", True),
    ("तिल", "तिलहन फसलों में सिंचाई", False),        # तिलहन (oilseeds) is not तिल (sesame)
    ("धान", "धानों में खाद", True),                  # vowel signs after the word are fine
    ("ਚੇਪੇ", "ਸਰ੍ਹੋਂ ਵਿੱਚ ਚੇਪੇ ਦੀ ਰੋਕਥਾਮ", True),
    ("ਫ਼ਾਜ਼ਿਲਕਾ", "ਫ਼ਾਜ਼ਿਲਕਾ ਵਿੱਚ ਮੌਸਮ", True),        # nukta letters typed as one or two characters
])
def test_contains_term(term, text, expected):
    assert contains_term(term, text) is expected


def test_oilseed_irrigation_is_not_a_sesame_question():
    res = IntentRouter().classify("तिलहन फसलों में सिंचाई का प्रबंधन कैसे करें?")
    assert res.intent != "crop_not_covered"


def test_one_crop_list_everywhere():
    """Router, market prices and place detection read the same crop names (app/crops.py)."""
    from app.agent import router
    from app.crops import CROP_NAMES
    from app.tools import location, market

    assert router.CROPS_DICT["cotton"] is CROP_NAMES["cotton"] and market.COMMODITY_ALIASES["cotton"] is CROP_NAMES["cotton"]
    assert "ਕਪਾਹ" in router.CROPS_DICT["cotton"]  # a spelling added once is known everywhere
    assert {"rice", "aloo", "makki"} <= location._NOT_PLACES


@pytest.mark.parametrize("query", [
    "बुवाई के 2 महीने बाद गेहूं में कोई भी खरपतवारनाशक क्यों नहीं छिड़क सकते?",  # खरपतवार + नाशक (herbicide)
    "ਝੋਨੇ ਦੇ ਬੀਜ ਨੂੰ ਸੋਧਣ ਦਾ ਤਰੀਕਾ ਦੱਸੋ",                                       # stem ਸੋਧ + verb ending
])
def test_topic_words_match_inside_longer_words(query):
    assert IntentRouter().classify(query).intent == "topic_not_covered"
