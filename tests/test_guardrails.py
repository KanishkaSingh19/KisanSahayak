import pytest
from app.agent.guardrails import AgriculturalGuardrails


def test_guardrails_banned_chemical_detection():
    guardrails = AgriculturalGuardrails()

    violation, chems = guardrails.check_banned_chemicals("Can I spray Monocrotophos on tomato?")
    assert violation is True
    assert "monocrotophos" in chems

    violation, chems = guardrails.check_banned_chemicals("Use Endosulfan for pest control")
    assert violation is True
    assert "endosulfan" in chems

    clean_violation, _ = guardrails.check_banned_chemicals("Use Tebuconazole for wheat rust")
    assert clean_violation is False


@pytest.mark.parametrize(
    "text,chemical",
    [
        ("क्या सब्जियों में मोनोक्रोटोफॉस डाल सकते हैं?", "monocrotophos"),
        ("ਕੀ ਸਬਜ਼ੀਆਂ ਉੱਤੇ ਮੋਨੋਕ੍ਰੋਟੋਫ਼ਾਸ ਪਾ ਸਕਦੇ ਹਾਂ?", "monocrotophos"),
        ("ਕੀ ਸਬਜ਼ੀਆਂ ਉੱਤੇ ਮੋਨੋਕ੍ਰੋਟੋਫ਼ਾਸ ਪਾ ਸਕਦੇ ਹਾਂ?", "monocrotophos"),  # ਫ਼ typed as ਫ + nukta
        ("कपास में एंडोसल्फान का छिड़काव", "endosulfan"),
    ],
)
def test_guardrails_detect_banned_chemicals_in_hindi_and_punjabi(text, chemical):
    violation, chems = AgriculturalGuardrails().check_banned_chemicals(text)
    assert violation is True and chemical in chems


def test_guardrails_enforce_safety_disclaimers():
    guardrails = AgriculturalGuardrails()
    ans, disclaimers = guardrails.enforce_safety("Spray Tebuconazole @ 200 ml per acre", "Wheat rust")
    assert len(disclaimers) >= 1
    assert "Statutory Disclaimer" in disclaimers[0] or "वैधानिक सूचना" in disclaimers[0]


def test_guardrails_banned_monocrotophos_warning():
    guardrails = AgriculturalGuardrails()
    ans, disclaimers = guardrails.enforce_safety("You can try Monocrotophos", "Monocrotophos for brinjal")
    assert any("मोनोक्रोटोफॉस (Monocrotophos)" in d for d in disclaimers)
    assert any("CIBRC" in d for d in disclaimers)


def test_guardrails_grounding_validation():
    guardrails = AgriculturalGuardrails()
    context = ["Spray Tebuconazole 25.9% EC @ 200 ml per acre for wheat yellow rust."]

    # High overlap
    grounded, score = guardrails.validate_grounding("Spray Tebuconazole 200 ml for wheat yellow rust", context)
    assert grounded is True
    assert score > 0.4

    # Low overlap
    ungrounded, score = guardrails.validate_grounding("Quantum entanglement and relativity in astrophysics", context)
    assert ungrounded is False
    assert score < 0.2
