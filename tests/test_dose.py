"""Per-acre doses worked out for the land size in My farm (arithmetic in code, never by the LLM)."""

from app.tools.dose import scale_doses


def test_per_acre_dose_gets_the_farm_total():
    text, changed = scale_doses("Atlantis 3.6 WDG: 160 g per acre.", 34, "en")
    assert changed and "160 g per acre (5.44 kg for your 34 acres)" in text
    assert "If only part of your land is under this crop" in text


def test_every_amount_in_a_per_acre_sentence_and_ranges():
    text, _ = scale_doses("Spray 40 g Actara 25 WG or 400 ml Rogor 30 EC in 80-125 liters of water per acre.", 34, "en")
    assert "40 g (1.36 kg for your 34 acres)" in text
    assert "400 ml (13.6 litres for your 34 acres)" in text
    assert "(2,720-4,250 litres for your 34 acres)" in text
    assert "25 WG (" not in text  # formulation codes are not amounts


def test_range_ends_share_a_unit():
    text, _ = scale_doses("Apply 25-35 g per acre.", 40, "en")
    assert "(1-1.4 kg for your 40 acres)" in text


def test_other_sentences_and_amounts_are_left_alone():
    original = "Treat the seed with 2 g per kg seed. Spray only above 5 aphids per earhead."
    assert scale_doses(original, 34, "en") == (original, False)
    assert scale_doses("160 g per acre", None, "en") == ("160 g per acre", False)


def test_hindi_answer():
    text, changed = scale_doses("200 मिलीलीटर Tilt 25 EC को 200 लीटर पानी में मिलाकर प्रति एकड़ छिड़काव करें।", 10, "hi")
    assert changed and "आपके 10 एकड़ के लिए 2 litres" in text
