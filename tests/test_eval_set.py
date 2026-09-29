"""The evaluation test set must stay consistent with the advisory data it is labelled against."""

import json

from app.config import settings

TEST_SET = json.loads((settings.BASE_DIR / "eval" / "test_set.json").read_text(encoding="utf-8"))
SECTIONS = [
    section["section_title"]
    for path in settings.RAW_DATA_DIR.glob("*.json")
    for section in json.loads(path.read_text(encoding="utf-8"))["sections"]
]


def test_every_label_matches_exactly_one_section():
    labels = [q["section"] for q in TEST_SET["retrieval"]] + [
        q["section"] for q in TEST_SET["follow_ups"] if "section" in q
    ]
    for label in labels:
        matches = [s for s in SECTIONS if label in s]
        assert len(matches) == 1, f"'{label}' matches {matches}"


def test_every_section_and_language_is_covered():
    covered = {s for s in SECTIONS for q in TEST_SET["retrieval"] if q["section"] in s}
    assert covered == set(SECTIONS)
    assert {q["language"] for q in TEST_SET["retrieval"]} == {"en", "pa", "hinglish", "hi"}
