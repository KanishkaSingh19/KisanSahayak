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
    lookup = MandiLookup(prices=[MandiPrice("Sangrur", "Sangrur", "30/09/2026", 6100, 6450, 6300)], local=True,
                         source="Agmarknet daily mandi prices (data.gov.in)")
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
    def fake_get(url, params, timeout, headers):
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


# ----------------------------------------------------------------------------- Agmarknet 2.0
FILTERS = {"data": {
    "state_data": [{"state_id": 100006, "state_name": "All States/UTs"}, {"state_id": 28, "state_name": "Punjab"}],
    "district_data": [{"id": 454, "state_id": 28, "district_name": "Bhatinda"}, {"id": 472, "state_id": 28, "district_name": "Sangrur"},
                      {"id": 471, "state_id": 28, "district_name": "Ropar (Rupnagar)"}],
}}
PRICE_DATA = {"status": "success", "data": {
    "columns": [
        {"key": "commodity_info", "columns": [{"key": "msp_price", "title": "MSP (Rs./Quintal) 2026-27"}]},
        {"key": "price_group", "columns": [{"key": "as_on_price", "title": "29 Sep, 2026"},
                                           {"key": "one_day_ago_price", "title": "28 Sep, 2026"},
                                           {"key": "two_day_ago_price", "title": "27 Sep, 2026"}]},
    ],
    "records": [{"cmdt_name": "Cotton", "msp_price": "8267.00", "as_on_price": "8691.18",
                 "one_day_ago_price": "8439.51", "two_day_ago_price": None}],
}}
NO_DATA = {"status": False, "message": "No data available.", "data": []}


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


@pytest.fixture
def agmarknet(monkeypatch):
    sent = []
    monkeypatch.setattr(market.requests, "get", lambda url, timeout, headers: FakeResponse(FILTERS))

    def post(url, json, timeout, headers):
        sent.append({"body": json, "headers": headers})
        return FakeResponse(NO_DATA if json["district"] != [market.ALL_DISTRICTS] else PRICE_DATA)

    monkeypatch.setattr(market.requests, "post", post)
    return sent


def test_agmarknet_falls_back_from_district_to_state(agmarknet):
    lookup = market.AgmarknetClient().latest("cotton", state="Punjab", district="Bathinda")
    assert [(p.date, p.modal_price) for p in lookup.prices] == [("29/09/2026", 8691.18), ("28/09/2026", 8439.51)]
    assert lookup.local is False and lookup.prices[0].min_price is None and "agmarknet" in lookup.source
    assert agmarknet[0]["body"]["district"] == [454]  # "Bathinda" matched Agmarknet's "Bhatinda"
    assert "KisanSahayak" in agmarknet[0]["headers"]["User-Agent"]  # identifies itself honestly


@pytest.mark.parametrize("ours,theirs", [("Bathinda", "Bhatinda"), ("Rupnagar", "Ropar (Rupnagar)"), ("Tarn Taran", "Tarntaran"),
                                         ("Firozpur", "Ferozpur"), ("Fatehgarh Sahib", "Fatehgarh")])
def test_district_spellings(ours, theirs):
    assert market._same_place(ours, theirs)


def test_service_uses_the_next_source_when_one_fails():
    class Source:
        def __init__(self, lookup):
            self.lookup, self.states = lookup, []

        def latest(self, commodity, state="Punjab", district=None):
            self.states.append(state)
            return self.lookup

    down = Source(MandiLookup(error="data.gov.in unreachable"))
    up = Source(MandiLookup(prices=[MandiPrice("Punjab", "Punjab", "29/09/2026", None, None, 2471)], source="Agmarknet"))
    lookup = market.MarketPriceService([down, up]).latest("paddy", district="Karnal")
    assert lookup.prices[0].modal_price == 2471 and up.states == ["Haryana"]  # Karnal is in Haryana
    both_down = market.MarketPriceService([down, down]).latest("paddy")
    assert not both_down.prices and "unreachable" in both_down.error


def test_average_prices_and_state_note_in_answer():
    lookup = MandiLookup(prices=[MandiPrice("Punjab", "Punjab", "29/09/2026", None, None, 8691.18)], local=False,
                         source="Agmarknet daily prices (agmarknet.gov.in)")
    res = pipeline_with(lookup).process_query("Cotton price in Bathinda mandi", language="en", generate_audio=False)
    assert "Rs 8,691 per quintal (average of reporting mandis, Punjab)" in res.answer
    assert "No mandi in Bathinda reported this crop recently" in res.answer
    assert "Agmarknet daily prices (agmarknet.gov.in)" in res.citations


def test_price_follow_up_keeps_the_place():
    earlier = ConversationTurn(query="what is msp of wheat in delhi", answer="...", intent="market_price", district="Delhi")
    router = IntentRouter()
    follow_up = router.classify_with_context("what about rice?", [earlier])
    assert follow_up.intent == "market_price" and follow_up.detected_district == "Delhi"
    full_question = router.classify_with_context("rice ka rate kya hai?", [earlier])
    assert full_question.intent == "market_price" and full_question.detected_district == "Delhi"
    new_place = router.classify_with_context("cotton price in Bathinda", [earlier])
    assert new_place.detected_district == "Bathinda"  # a newly named place wins


def test_profile_place_is_not_carried_over():
    earlier = ConversationTurn(query="today's rate?", answer="...", intent="market_price", district="Moga",
                               district_from_profile=True)
    assert IntentRouter().classify_with_context("what about rice?", [earlier]).detected_district is None


def test_follow_up_answer_uses_the_remembered_place():
    pipeline = pipeline_with(MandiLookup(error="x"))
    first = pipeline.process_query("what is msp of wheat in delhi", language="en", generate_audio=False)
    second = pipeline.process_query("what about rice?", language="en", generate_audio=False,
                                    history=[ConversationTurn.from_answer(first)])
    assert "Rs 2,441" in second.answer and pipeline.mandi.calls == [("wheat", "Delhi"), ("paddy", "Delhi")]
