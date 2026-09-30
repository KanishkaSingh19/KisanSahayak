"""Build the 200-question test set from the selected KCC queries.

    python evalset/kcc/build_testset.py

Input:  selected.json (real queries, from select_questions.py) and translations.json.
Output: kcc_200.json: 50 questions each in English, Hindi, Punjabi and Hinglish.

Languages rotate through each topic, so every topic is asked in every language. English questions are
the exact KCC text; the other three are translations (KCC logs record queries in English only).
Each question is labelled with what a correct answer needs, using the rules in `expected()`.
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
LANGUAGES = ["en", "hi", "pa", "hinglish"]
SOURCE = "Kisan Call Centre, Punjab, Jan-Jul 2025 (data.gov.in KCC transcripts, via huggingface.co/datasets/whitesnek/punjab_kcc)"

# (pattern on the English KCC query, advisory section that answers it); first match wins
SECTION_RULES = [
    (r"monocrotophos|endosulfan|phorate|paraquat", "Banned"),
    (r"yellow rust|stripe rust", "Yellow Rust"),
    (r"karnal bunt", "Karnal Bunt"),
    (r"wheat.*aphid|aphid.*wheat", "Wheat Aphid"),
    (r"(mustard|rapeseed|raya|toria|sarson).*aphid|aphid.*(mustard|rapeseed|raya|toria|sarson)", "Mustard Aphid"),
    (r"(white rust|blight).*(mustard|rapeseed)|(mustard|rapeseed).*(white rust|blight)", "White Rust"),
    (r"(water management|irrigation|first water|fertili[sz]er|nutrient).*(mustard|oilseed|rapeseed|raya|toria)|"
     r"(mustard|oilseed|rapeseed).*(water management|irrigation|fertili[sz]er|nutrient)", "Mustard Fertilizer"),
    # Wheat advisory: sowing time, seed rate, N-P-K fertilizer and the critical (first, CRI) irrigation
    (r"^(?!.*last irrigation)(?!.*(herbicide|weed|yellowing|growth|urea application before))"
     r".*((fertili[sz]er|irrigat|water management|sowing time|seed rate).*wheat|wheat.*(fertili[sz]er|irrigat|sowing time|seed rate))",
     "Wheat Sowing"),
    (r"plant hopper", "Brown Planthopper"),
    (r"sheath blight", "Sheath Blight"),
    (r"bacterial leaf blight|\bblb\b", "Bacterial Leaf Blight"),
    (r"pink.{0,12}boll ?worm", "Pink Bollworm"),
    (r"white ?fly", "Cotton Whitefly"),
]
UNCOVERED_CROP = re.compile(r"\bmaize\b|sugarcane crop$", re.I)


def expected(item: dict) -> dict:
    """What a correct answer needs for this question."""
    if item["topic"] == "weather":
        return {"kind": "weather", "district": item["district"]}
    if item["topic"] == "pmkisan":
        return {"kind": "scheme"}
    q = item["kcc_query"].lower()
    if re.search(r"\bmsp\b|support price|\brate of\b|\bprice", q):
        return {"kind": "market"}
    for pattern, section in SECTION_RULES:
        if re.search(pattern, q):
            return {"kind": "banned" if section == "Banned" else "advisory", "section": section}
    if UNCOVERED_CROP.search(q):
        return {"kind": "not_in_kb", "note": "crop not covered"}
    return {"kind": "not_in_kb"}


def weather_question(district: str) -> str:
    return f"What is the weather forecast for {district} today?"


def main() -> int:
    selected = json.loads((HERE / "selected.json").read_text(encoding="utf-8"))
    translations = json.loads((HERE / "translations.json").read_text(encoding="utf-8"))
    items = []
    for i, s in enumerate(selected):
        lang = LANGUAGES[i % 4]
        if lang == "en":
            question = weather_question(s["district"]) if s["topic"] == "weather" else s["kcc_query"]
        else:
            question = translations.get(str(i))
            if not question:
                print(f"Missing translation for {i} ({lang}): {s['kcc_query']}")
                return 1
        items.append({
            "id": i + 1,
            "language": lang,
            "question": question,
            "topic": s["topic"],
            "kcc_query": s["kcc_query"] + (f" ({s['district']})" if s.get("district") else ""),
            "times_asked": s["times_asked"],
            "translated": lang != "en",
            "rewritten": s["topic"] == "weather",  # KCC logs weather calls without the question text
            "expected": expected(s),
            "kcc_answer": s["kcc_answer"],
        })
    out = {
        "description": (
            "200 real farmer queries from Kisan Call Centre logs, 50 each in English, Hindi, Punjabi and Hinglish. "
            "English questions are the exact logged text; Hindi, Punjabi and Hinglish are translations of other real "
            "queries, because KCC logs record queries in English. Weather queries are logged without text and are "
            "rewritten as a forecast question for the caller's district. kcc_answer is the Farm Tele Advisor's answer."
        ),
        "source": SOURCE,
        "selection": "Most frequently asked distinct queries per topic (evalset/kcc/select_questions.py), "
                     "not chosen by whether KisanSahayak can answer them.",
        "questions": items,
    }
    (HERE / "kcc_200.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    kinds = Counter(q["expected"]["kind"] for q in items)
    print(f"Wrote evalset/kcc/kcc_200.json: {len(items)} questions")
    print("by language:", dict(Counter(q["language"] for q in items)))
    print("by topic:   ", dict(Counter(q["topic"] for q in items)))
    print("expected:   ", dict(kinds))
    return 0


if __name__ == "__main__":
    sys.exit(main())
