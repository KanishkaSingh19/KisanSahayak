"""Evaluate KisanSahayak on 200 real Kisan Call Centre questions (evalset/kcc/kcc_200.json).

    python evalset/kcc/run_kcc.py          # offline answers: repeatable, no API quota
    python evalset/kcc/run_kcc.py --llm --pause 5   # real Gemini answers (uses API quota)

Metrics (as promised in the idea submission):
- retrieval accuracy: right advisory in the top 3, for questions our advisories cover
- banned-pesticide detection
- correct answer language (script)
- response time
- questions our advisories do not cover: answered from PAU's Package of Practices (from the right crop's
  chapter), referred to the KVK, or (wrongly) shown an advisory about something else
Answer and dose accuracy need an agronomist: review_sheet.csv lists every answer next to the Kisan Call Centre
advisor's answer for that review. Writes results.md, results.json and review_sheet.csv (…_llm with --llm).
"""

import argparse
import csv
import json
import statistics
import sys
import time
from collections import defaultdict
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.agent.pipeline import KisanPipeline  # noqa: E402
from app.agent.synthesizer import DeterministicGroundedSynthesizer  # noqa: E402
from app.config import settings  # noqa: E402
from app.tools.location import find_known_place  # noqa: E402

LANGS = ["en", "hi", "pa", "hinglish"]
CROP_INTENTS = {"crop_question", "general_agriculture", "safety_query"}


def script_ok(text: str, lang: str) -> bool:
    gurmukhi = any("਀" <= ch <= "੿" for ch in text)
    devanagari = any("ऀ" <= ch <= "ॿ" for ch in text)
    if lang == "pa":
        return gurmukhi
    if lang == "hi":
        return devanagari
    return not (gurmukhi or devanagari)  # English and Hinglish are written in Latin letters


def pct(hits: int, total: int) -> str:
    return f"{hits}/{total} ({100 * hits / total:.0f}%)" if total else "n/a"


def evaluate(q: dict, res) -> dict:
    exp = q["expected"]
    sections = [c.section for c in res.retrieved_chunks]
    shown = "\n".join([res.answer, *res.safety_disclaimers])
    r = {"intent": res.intent, "top_sections": sections[:3], "script_ok": script_ok(res.answer, q["language"])}
    if exp["kind"] == "advisory":
        r["top1"] = bool(sections) and exp["section"].lower() in sections[0].lower()
        r["top3"] = any(exp["section"].lower() in s.lower() for s in sections[:3])
    elif exp["kind"] == "banned":
        r["warned"] = any("CIBRC" in d for d in res.safety_disclaimers) or "banned" in shown.lower()
    elif exp["kind"] == "weather":
        r["weather_ok"] = res.intent == "weather"
        # KCC spells some districts differently ("Bhatinda" for Bathinda): compare canonical names
        wanted = find_known_place(exp["district"]) or exp["district"]
        r["district_ok"] = (res.processing_metadata.get("district") or "").lower() == wanted.lower()
    elif exp["kind"] == "scheme":
        r["scheme_ok"] = res.intent == "scheme_query"
    elif exp["kind"] == "market":
        r["market_ok"] = res.intent == "market_price" and "Rs " in res.answer
    else:  # not in our advisories
        r.update(outside_outcome(q["topic"], res))
    return r


def stored_answer(res) -> str:
    """The answer as saved in the committed results: PAU's text is copyrighted and not kept in the
    repository, so an answer from its chapters is saved as its page reference."""
    if res.processing_metadata.get("knowledge") == "pau" and res.citations:
        return f"[Answered from {res.citations[0]}. PAU's text is not stored here: run this evaluation locally to see it.]"
    return res.answer


def outside_outcome(crop: str, res) -> dict:
    """For a question our advisories don't cover: answered from PAU's chapter for that crop, referred to
    the KVK, or neither (shown advice on something else, the failure that matters)."""
    referred = not res.retrieved_chunks or res.intent in ("crop_not_covered", "out_of_scope")
    from_pau = not referred and res.processing_metadata.get("knowledge") == "pau"
    top = res.retrieved_chunks[0] if res.retrieved_chunks else None
    if crop == "pesticide":
        # A pesticide question names the crop it is for ("chlorpyriphos in mustard"), if any
        crop = (res.processing_metadata.get("detected_crop") or "all crops")
    return {
        "referred": referred,
        "from_pau": from_pau,
        "pau_right_crop": from_pau and top is not None and top.crop.lower().startswith((crop.lower(), "all crops")),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--llm", action="store_true", help="Real Gemini answers (uses API quota)")
    parser.add_argument("--pause", type=float, default=0, help="Seconds between questions (free-tier rate limits)")
    args = parser.parse_args()

    data = json.loads((HERE / "kcc_200.json").read_text(encoding="utf-8"))
    pipeline = KisanPipeline() if args.llm else KisanPipeline(synthesizer=DeterministicGroundedSynthesizer())
    rows, latencies = [], []
    for n, q in enumerate(data["questions"]):
        if args.pause and n:
            time.sleep(args.pause)
        start = time.perf_counter()
        res = pipeline.process_query(q["question"], language=q["language"], generate_audio=False)
        ms = (time.perf_counter() - start) * 1000
        source = res.processing_metadata.get("answer_source")
        if args.llm and source == "template_llm_failed":
            print(f"Stopped at question {q['id']}: every Gemini model failed (usually the API quota). No results written.")
            return 2
        latencies.append(ms)
        rows.append({**q, "result": evaluate(q, res), "answer": stored_answer(res), "answer_source": source, "ms": round(ms)})
        print(f"{q['id']:>3} {q['language']:<8} {q['expected']['kind']:<9} {res.intent:<18} "
              f"{(res.retrieved_chunks[0].section if res.retrieved_chunks else '-')[:40]}")

    by = lambda kind: [r for r in rows if r["expected"]["kind"] == kind]  # noqa: E731
    adv, banned, weather, scheme, outside = by("advisory"), by("banned"), by("weather"), by("scheme"), by("not_in_kb")
    prices = by("market")
    lang_stats = defaultdict(lambda: [0, 0])
    for r in rows:
        lang_stats[r["language"]][0] += r["result"]["script_ok"]
        lang_stats[r["language"]][1] += 1
    top3 = sum(r["result"]["top3"] for r in adv)
    top1 = sum(r["result"]["top1"] for r in adv)
    referred = sum(r["result"]["referred"] for r in outside)
    from_pau = sum(r["result"]["pau_right_crop"] for r in outside)
    unrelated = sum(not r["result"]["referred"] and not r["result"]["pau_right_crop"] for r in outside)
    answers = f"Gemini ({settings.GEMINI_MODEL})" if args.llm else "offline template (no API quota)"
    lines = [
        "# Real farmer questions: Kisan Call Centre test set",
        "",
        f"*{date.today()} · 200 questions (50 each English, Hindi, Punjabi, Hinglish) · source: {data['source']} · "
        f"answers: {answers} · search embeddings: {settings.EMBEDDING_PROVIDER}*",
        "",
        "## Coverage",
        "",
        "| Questions | Count |",
        "|---|---|",
        f"| Answered by our crop/safety advisories | {len(adv) + len(banned)} |",
        f"| Weather | {len(weather)} |",
        f"| PM-KISAN | {len(scheme)} |",
        f"| Market prices (MSP / mandi) | {len(prices)} |",
        f"| **Outside our advisories** (weeds, nutrient deficiencies, varieties, MSP, other pests…) | **{len(outside)}** |",
        "",
        "## Metrics",
        "",
        "| Metric | Result |",
        "|---|---|",
        f"| Retrieval: right advisory in top 3 (covered questions) | **{pct(top3, len(adv))}** |",
        f"| Retrieval: right advisory first | {pct(top1, len(adv))} |",
        f"| Banned-pesticide questions warned | {pct(sum(r['result']['warned'] for r in banned), len(banned))} |",
        f"| Weather questions answered with weather | {pct(sum(r['result']['weather_ok'] for r in weather), len(weather))} |",
        f"| Weather for the right district | {pct(sum(r['result']['district_ok'] for r in weather), len(weather))} |",
        f"| PM-KISAN questions recognised | {pct(sum(r['result']['scheme_ok'] for r in scheme), len(scheme))} |",
        f"| Price questions answered with the MSP / mandi price | {pct(sum(r['result']['market_ok'] for r in prices), len(prices))} |",
        f"| Outside our advisories: answered from PAU's Package of Practices, right crop's chapter | **{pct(from_pau, len(outside))}** |",
        f"| Outside our advisories: referred to KVK | {pct(referred, len(outside))} |",
        f"| Outside our advisories: shown advice on something else | {pct(unrelated, len(outside))} |",
        f"| Answer in the requested language (script) | {pct(sum(v[0] for v in lang_stats.values()), len(rows))} |",
        f"| Response time median / p95 | {statistics.median(latencies):.0f} ms / "
        f"{sorted(latencies)[int(0.95 * len(latencies)) - 1]:.0f} ms |",
        "",
        "| Language | Answer in the right script |",
        "|---|---|",
    ]
    lines += [f"| {lang} | {pct(*lang_stats[lang])} |" for lang in LANGS]
    misses = [r for r in adv if not r["result"]["top3"]]
    if misses:
        lines += ["", "## Covered questions where the right advisory was not in the top 3", ""]
        lines += [f"- ({r['language']}) \"{r['question']}\" → got {', '.join(r['result']['top_sections']) or 'nothing'}; "
                  f"expected {r['expected']['section']}" for r in misses]
    lines += [
        "",
        "## Notes",
        "",
        "- English questions are the exact text logged by the Kisan Call Centre; Hindi, Punjabi and Hinglish questions "
        "are translations of other real queries (the logs record queries in English). Weather calls are logged without "
        "text and are asked as a forecast question for the caller's district.",
        "- Questions were chosen by how often farmers asked them, not by whether KisanSahayak can answer them.",
        "- Answer and dose accuracy need an agronomist: see `review_sheet.csv`, which puts each answer next to the "
        "Kisan Call Centre advisor's answer.",
    ]
    suffix = "_llm" if args.llm else ""
    (HERE / f"results{suffix}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (HERE / f"results{suffix}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    with (HERE / f"review_sheet{suffix}.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "language", "question", "expected", "kisansahayak_answer", "kcc_advisor_answer",
                    "answer_correct (yes/no/partly)", "dose_correct (yes/no/n.a.)", "reviewer_comment"])
        for r in rows:
            from_pau = r["result"].get("from_pau")
            if r["expected"]["kind"] in ("advisory", "banned") or from_pau:
                expected = "PAU Package of Practices" if from_pau else r["expected"].get("section", "")
                w.writerow([r["id"], r["language"], r["question"], expected,
                            r["answer"], r["kcc_answer"], "", "", ""])
    print("\n".join(lines[8:30]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
