"""Pre-translate advisory sections so offline (no-LLM) answers are in the farmer's language.

Run once after changing data/raw/*.json:
    python scripts/translate_advisories.py

Writes data/translations.json:  {lang: {section_title: {field: translated_text}}}.
Safe to re-run: sections already translated are skipped. A translation is rejected if any
number from the source (doses, percentages, dates) is missing, so dosages can't drift.
"""

import json
import re
import sys
import time
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.config import settings

FIELDS = ["section_title", "symptoms", "recommended_action", "preventive_measures", "critical_safety_warning"]
LANGUAGE_NAMES = {
    "pa": "Punjabi in Gurmukhi script",
    "hi": "Hindi in Devanagari script",
    "hinglish": "Hinglish (Hindi written in Roman/English letters, as farmers type on WhatsApp)",
}
OUTPUT_PATH = settings.DATA_DIR / "translations.json"

PROMPT = """Translate these fields of an official Indian agricultural advisory for farmers.

Return JSON with keys "pa", "hi" and "hinglish". Each value is an object with exactly the same keys as the input.
- pa: {pa}
- hi: {hi}
- hinglish: {hinglish}

Strict rules:
1. Translate faithfully and simply. Do not add, remove or change any advice.
2. Keep every number exactly as written, using Western digits 0-9 (e.g. 250-300, 25%, 3:30, 10-15).
3. Keep chemical/pesticide names, formulation codes (EC, WG, WP, WS) and units (ml, g, kg, liters, acre, hectare) in English letters.
4. Keep variety names (e.g. RH-749) and scientific names in English.

Input:
{fields}
"""


def numbers_in(text: str) -> set:
    return set(re.findall(r"\d+(?:\.\d+)?", text))


def numbers_preserved(source: dict, translated: dict) -> bool:
    return all(numbers_in(source[k]) <= numbers_in(translated.get(k, "")) for k in source)


def translate_section(client, model_names, fields: dict):
    from google.genai import types

    prompt = PROMPT.format(fields=json.dumps(fields, ensure_ascii=False, indent=1), **LANGUAGE_NAMES)
    for model in model_names:
        try:
            resp = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.1),
            )
            result = json.loads(resp.text)
            if all(lang in result and set(fields) <= set(result[lang]) for lang in LANGUAGE_NAMES):
                return result
            print(f"    {model}: incomplete JSON, trying next model")
        except Exception as e:
            print(f"    {model}: {str(e)[:100]}")
    return None


def main() -> int:
    from google import genai

    if not settings.GEMINI_API_KEY:
        print("GEMINI_API_KEY is not set in .env")
        return 1
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    models = [m for m in (settings.GEMINI_MODEL, settings.GEMINI_FALLBACK_MODEL) if m]

    translations = json.loads(OUTPUT_PATH.read_text(encoding="utf-8")) if OUTPUT_PATH.exists() else {}
    for lang in LANGUAGE_NAMES:
        translations.setdefault(lang, {})

    failed = []
    for path in sorted(settings.RAW_DATA_DIR.glob("*.json")):
        for section in json.loads(path.read_text(encoding="utf-8"))["sections"]:
            title = section["section_title"]
            if all(title in translations[lang] for lang in LANGUAGE_NAMES):
                continue
            fields = {k: section[k] for k in FIELDS if section.get(k)}
            print(f"Translating: {title}")

            result = None
            for attempt in range(2):
                result = translate_section(client, models, fields)
                if result and all(numbers_preserved(fields, result[lang]) for lang in LANGUAGE_NAMES):
                    break
                if result:
                    print("    a number changed in translation, retrying")
                result = None
                time.sleep(2)

            if result is None:
                failed.append(title)
                continue
            for lang in LANGUAGE_NAMES:
                translations[lang][title] = {k: result[lang][k] for k in fields}
            OUTPUT_PATH.write_text(json.dumps(translations, ensure_ascii=False, indent=2), encoding="utf-8")

    done = len(translations["hi"])
    print(f"\nTranslated sections: {done}. Saved to {OUTPUT_PATH}")
    if failed:
        print(f"Not translated (re-run later): {failed}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
