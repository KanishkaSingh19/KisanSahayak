"""Market prices: MSP table, live mandi prices (mocked) and routing."""

import pytest
import requests

from app.agent.router import IntentRouter
from app.agent.state import ConversationTurn, FarmerProfile
from app.agent.synthesizer import DeterministicGroundedSynthesizer
from app.tools import market
from app.tools.market import MandiLookup, MandiPrice, MandiPriceClient, detect_commodity, load_msp


@pytest.mark.parametrize(
    "query",
    ["MSP OF WHEAT?", "What is the MSP of maize?", "Sangrur mandi mein sarson ka bhav kya hai?", "ਕਣਕ ਦਾ ਭਾਅ ਕੀ ਹੈ?",
     "गेहूं का समर्थन मूल्य कितना है?", "cotton price in Bathinda", "informatin regarding rate of mustard crop?"],
)
def test_price_questions_route_to_market(query):
    assert IntentRouter().classify(query).intent == "market_price"


@pytest.mark.parametrize("query,intent", [
    ("When should I sow wheat and what is the seed rate?", "general_agriculture"),
    ("stock market price today", "out_of_scope"),
])
def test_not_price_questions(query, intent):
    assert IntentRouter().classify(query).intent == intent


@pytest.mark.parametrize("text,key", [
    ("MSP of wheat", "wheat"), ("sarson ka bhav", "mustard"), ("ਝੋਨੇ ਦਾ ਭਾਅ", "paddy"), ("green gram MSP", "moong"),
    ("chana ka rate", "gram"), ("आलू का भाव", "potato"), ("what is the price", None),
])
def test_detect_commodity(text, key):
    assert detect_commodity(text) == key


def test_msp_table_is_dated_and_sourced():
    data = load_msp()
    assert data["last_verified"] and data["source"] and data["unit"] == "Rs per quintal"
    assert data["crops"]["wheat"]["msp"] == 2585 and data["crops"]["paddy"]["variants"]["Grade A"] == 2461


class FakeMandi:
    def __init__(self, lookup):
        self.lookup, self.calls = lookup, []

    def latest(self, commodity, state="Punjab", district=None):
        self.calls.append((commodity, district))
        return self.lookup


def pipeline_with(lookup):
    from app.agent.pipeline import KisanPipeline

    return KisanPipeline(synthesizer=DeterministicGroundedSynthesizer(), mandi=FakeMandi(lookup))


def test_msp_and_live_mandi_prices():
    lookup = MandiLookup(prices=[MandiPrice("Sangrur", "Sangrur", "30/09/2026", 6100, 6450, 6300)], local=True)
    pipeline = pipeline_with(lookup)
    res = pipeline.process_query("Sangrur mandi mein sarson ka bhav?", language="hinglish", generate_audio=False)
    assert res.intent == "market_price"
    assert "Rs 6,200" in res.answer and "Rs 6,300" in res.answer and "30/09/2026" in res.answer
    assert pipeline.mandi.calls == [("mustard", "Sangrur")]
    assert any("data.gov.in" in c for c in res.citations) and res.safety_disclaimers


def test_mandi_unavailable_is_said_not_guessed():
    res = pipeline_with(MandiLookup(error="unreachable")).process_query(
        "MSP of wheat?", language="en", generate_audio=False)
    assert "Rs 2,585" in res.answer and "agmarknet.gov.in" in res.answer and "1800-180-1551" in res.answer
    assert res.processing_metadata["mandi_error"] == "unreachable"


def test_profile_crop_and_district_are_used():
    pipeline = pipeline_with(MandiLookup(error="x"))
    res = pipeline.process_query("What is today's rate?", language="en", generate_audio=False,
                                 profile=FarmerProfile(district="Moga", crops=["paddy"]))
    assert "Rs 2,441" in res.answer and pipeline.mandi.calls == [("paddy", "Moga")]


def test_price_follow_up():
    earlier = ConversationTurn(query="MSP of wheat?", answer="Rs 2,585", intent="market_price")
    assert IntentRouter().classify_with_context("and mustard?", [earlier]).intent == "market_price"


def test_client_backs_off_after_a_failure(monkeypatch):
    calls = []

    def fail(*args, **kwargs):
        calls.append(1)
        raise requests.ConnectionError("reset")

    monkeypatch.setattr(market.requests, "get", fail)
    client = MandiPriceClient()
    assert client.latest("wheat").error and client.latest("wheat").error
    assert len(calls) == 1  # the second question does not wait for the same timeout


def test_client_prefers_district_and_newest_date(monkeypatch):
    def fake_get(url, params, timeout):
        class Resp:
            def raise_for_status(self):
                pass

            def json(self):
                if "filters[district]" in params:
                    return {"records": []}  # nothing reported in this district: fall back to the state
                return {"records": [
                    {"market": "Khanna", "district": "Ludhiana", "arrival_date": "29/09/2026",
                     "min_price": "2500", "max_price": "2600", "modal_price": "2550"},
                    {"market": "Moga", "district": "Moga", "arrival_date": "30/09/2026",
                     "min_price": "2520", "max_price": "2610", "modal_price": "2585"},
                ]}
        return Resp()

    monkeypatch.setattr(market.requests, "get", fake_get)
    lookup = MandiPriceClient().latest("wheat", district="Barnala")
    assert [p.market for p in lookup.prices] == ["Moga"] and lookup.local is False
