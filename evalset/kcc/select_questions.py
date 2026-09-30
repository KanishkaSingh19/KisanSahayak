"""Select real farmer queries from the Punjab Kisan Call Centre logs for the 200-question test set.

    python evalset/kcc/select_questions.py      # needs data/kcc/punjab.csv (see evalset/kcc/README.md)

Queries are ranked by how often farmers asked them (not by whether KisanSahayak can answer them),
near-duplicates are merged, and log entries that are not questions (call transfers, survey calls,
contact-number requests, merged or garbled rows) are skipped. Writes evalset/kcc/selected.json.
"""

import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data" / "kcc" / "punjab.csv"
OUT = Path(__file__).resolve().parent / "selected.json"

QUOTAS = {"wheat": 52, "paddy": 52, "cotton": 30, "mustard": 26, "weather": 15, "pmkisan": 15, "pesticide": 10}

SKIP = re.compile(
    r"kisan call cent|contact n|phone n|survey call|viksit krishi|vksa|kisan mela|transfer|mandi board|"
    r"whatsapp|chief agricultural officer|call center|\?\s*\?\s*\?|information regarding .*\? .*information regarding",
    re.I,
)
PESTICIDE = re.compile(
    r"monocrotophos|endosulfan|phorate|paraquat|chlor?o?pyri?phos|emamectin|tank mix|jar test|mixing of insecticide|"
    r"gap between the application of any chemical and rain",
    re.I,
)
PM_KISAN = re.compile(r"kisan samman|pm kisan|pm-kisan|samman nidhi|sanman nidhi|pmkisan", re.I)
CROP_PATTERNS = [
    ("wheat", r"\bwheat\b"),
    ("paddy", r"paddy|basmati|\brice\b|\bdhan\b"),
    ("cotton", r"cotton|kapas|narma"),
    ("mustard", r"must|sarson|\braya\b|toria|rapeseed"),
]
SYNONYMS = {
    "aphids": "aphid", "rice": "paddy", "yojna": "yojana", "sanman": "samman", "catterpiller": "caterpillar",
    "magnese": "manganese", "weed": "weeds", "requirment": "requirement", "pradhan": "pm", "mantri": "",
    "basmati": "paddy", "pmkisan": "pmkisan",
}
# Words that do not change what is asked: "zinc deficiency management in paddy field" = "deficiency of zinc in paddy"
GENERIC = set(
    "information regarding about query farmer asked the of in a an to for that crop field control management "
    "application dose requirement better improve improvement how method detail details kisan nidhi yojana scheme "
    "with their iformation informatin inofrmation samman".split()
)


def clean(q: str) -> str:
    q = re.sub(r"\s+", " ", q.replace("\n", " ")).strip(" -")
    return re.sub(r"\s*\?[\s?]*$", "?", q)


def dedupe_key(q: str) -> frozenset:
    q = q.lower().replace("white fly", "whitefly").replace("pm kisan", "pmkisan").replace("pm-kisan", "pmkisan")
    words = [SYNONYMS.get(w, w) for w in re.findall(r"[a-z0-9]+", q)]
    words = [w for w in words if not re.fullmatch(r"(19|20)\d\d", w)]  # "transplanting of paddy 2025" = "... of paddy"
    return frozenset(w for w in words if w and w not in GENERIC and not re.fullmatch(r"inf\w*|regard\w*", w))


def topic(r) -> str:
    q = r["QueryText"]
    if PM_KISAN.search(q):
        return "pmkisan"
    if q.strip().startswith("Farmer asked query on Weather"):
        return "weather"
    if PESTICIDE.search(q):
        return "pesticide"
    # The crop named in the question wins over the log's crop column, which is sometimes wrong
    for name, pattern in CROP_PATTERNS:
        if re.search(pattern, q, re.I):
            return name
    for name, pattern in CROP_PATTERNS:
        if re.search(pattern, r["Crop"], re.I):
            return name
    return ""


def main() -> int:
    if not SOURCE.exists():
        print(f"Missing {SOURCE}. See evalset/kcc/README.md for the download.")
        return 1
    csv.field_size_limit(10**9)
    rows = list(csv.DictReader(SOURCE.open(encoding="utf-8", errors="replace")))
    counts, example, answers, districts = defaultdict(Counter), {}, {}, Counter()
    for r in rows:
        tp = topic(r)
        if not tp:
            continue
        if tp == "weather":
            districts[r["DistrictName"].strip().title()] += 1
            continue
        q = clean(r["QueryText"])
        # A long text after the question mark is the advisor's answer pasted into the query field
        merged = "?" in q and len(q.split("?", 1)[1].strip()) > 25
        if SKIP.search(q) or merged or len(q) < 12:
            continue
        key = dedupe_key(q)
        counts[tp][key] += 1
        example.setdefault((tp, key), q)
        answers.setdefault((tp, key), re.sub(r"\s+", " ", r["KccAns"]).strip())

    selected = []
    for tp, quota in QUOTAS.items():
        if tp == "weather":
            # KCC logs weather calls as "Farmer asked query on Weather", with the caller's district
            for district, n in districts.most_common(quota):
                selected.append({"topic": tp, "kcc_query": "Farmer asked query on Weather", "district": district,
                                 "times_asked": n, "kcc_answer": ""})
            continue
        # Most asked first; ties broken by text so the selection is repeatable
        ranked = sorted(counts[tp].items(), key=lambda kv: (-kv[1], example[(tp, kv[0])]))
        for key, n in ranked[:quota]:
            selected.append({"topic": tp, "kcc_query": example[(tp, key)], "times_asked": n,
                             "kcc_answer": answers[(tp, key)]})
    OUT.write_text(json.dumps(selected, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(selected)} queries from {len(rows)} log rows -> {OUT.relative_to(ROOT)}")
    print(dict(Counter(s["topic"] for s in selected)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
