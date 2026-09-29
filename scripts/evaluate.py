"""Evaluate KisanSahayak on the hand-written test set in eval/test_set.json.

    python scripts/evaluate.py                      # offline: no Gemini calls, repeatable
    python scripts/evaluate.py --embeddings gemini  # compare search backends
    python scripts/evaluate.py --llm 8              # also check 8 real Gemini answers (uses quota)

Writes eval/results_<embeddings>.md (for the slides) and eval/results_<embeddings>.json.
"""

import argparse
import json
import re
import statistics
import sys
import time
from collections import defaultdict
from datetime import date
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.agent.pipeline import KisanPipeline
from app.agent.router import IntentRouter
from app.agent.state import ConversationTurn
from app.agent.synthesizer import DeterministicGroundedSynthesizer, get_synthesizer
from app.config import settings
from app.rag.chunker import AgriculturalChunker
from app.rag.embeddings import GeminiEmbedder, LocalDenseEmbedder
from app.rag.hybrid_retriever import HybridRetriever

EVAL_DIR = project_root / "eval"
LANGS = ["en", "pa", "hinglish", "hi"]


def make_embeddings(name: str):
    if name == "minilm":
        from app.rag.embeddings import MiniLMEmbedder
        return MiniLMEmbedder()
    if name == "gemini":
        return GeminiEmbedder(settings.GEMINI_API_KEY)
    return LocalDenseEmbedder(settings.EMBEDDING_DIM)


def pct(hits: int, total: int) -> str:
    return f"{hits}/{total} ({100 * hits / total:.0f}%)" if total else "n/a"


def script_ok(text: str, lang: str) -> bool:
    has_gurmukhi = any("਀" <= ch <= "੿" for ch in text)
    has_devanagari = any("ऀ" <= ch <= "ॿ" for ch in text)
    if lang == "pa":
        return has_gurmukhi
    if lang == "hi":
        return has_devanagari
    return not (has_gurmukhi or has_devanagari)


def numbers_in(text: str) -> set:
    # Ignore list numbering ("1. When to spray"): it is formatting, not a dose or date
    text = re.sub(r"(?m)^\s*(?:[-*]\s*)?\d+[.)]\s+", "", text)
    return set(re.findall(r"\d+(?:\.\d+)?", text))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--embeddings", choices=["minilm", "gemini", "local"], default=settings.EMBEDDING_PROVIDER)
    parser.add_argument("--llm", type=int, default=0, help="Also generate N real Gemini answers (uses API quota)")
    args = parser.parse_args()

    data = json.loads((EVAL_DIR / "test_set.json").read_text(encoding="utf-8"))
    print(f"Building search index with {args.embeddings} embeddings...")
    embeddings = make_embeddings(args.embeddings)
    retriever = HybridRetriever(embeddings=embeddings)
    retriever.build_indices(AgriculturalChunker(settings.CHUNK_SIZE, settings.CHUNK_OVERLAP).load_and_chunk_directory(settings.RAW_DATA_DIR))
    # Offline template answers: repeatable and no API quota
    pipeline = KisanPipeline(retriever=retriever, synthesizer=DeterministicGroundedSynthesizer())
    router = IntentRouter()
    failures, results = [], {}

    # 1. Retrieval + intent -------------------------------------------------------------
    by_lang = defaultdict(lambda: {"total": 0, "top1": 0, "top3": 0})
    top1 = top3 = intent_ok = 0
    latencies, false_alarms, normal_questions = [], 0, 0
    for item in data["retrieval"]:
        start = time.perf_counter()
        res = pipeline.process_query(item["query"], language=item["language"], generate_audio=False)
        latencies.append((time.perf_counter() - start) * 1000)
        sections = [c.section for c in res.retrieved_chunks]
        hit1 = bool(sections) and item["section"] in sections[0]
        hit3 = any(item["section"] in s for s in sections[:3])
        stats = by_lang[item["language"]]
        stats["total"] += 1
        stats["top1"] += hit1
        stats["top3"] += hit3
        top1 += hit1
        top3 += hit3
        intent_ok += res.intent in item["intents"]
        if not hit1:
            failures.append(f"Retrieval: \"{item['query']}\" → got *{sections[0] if sections else 'nothing'}*, expected *{item['section']}*")
        if res.intent not in item["intents"]:
            failures.append(f"Intent: \"{item['query']}\" → {res.intent}, expected {' or '.join(item['intents'])}")
        # A banned-pesticide warning is a false alarm only on questions that aren't about banned pesticides
        about_banned = item["section"] == "Banned and Strictly" or pipeline.guardrails.check_banned_chemicals(item["query"])[0]
        if not about_banned:
            normal_questions += 1
            if any("CIBRC" in d for d in res.safety_disclaimers):
                false_alarms += 1
                failures.append(f"False alarm: banned-pesticide warning on \"{item['query']}\"")
    n = len(data["retrieval"])
    results["retrieval"] = {"questions": n, "top1": top1, "top3": top3, "by_language": dict(by_lang)}

    # 2. Weather place detection ----------------------------------------------------------
    weather_ok = 0
    for item in data["weather"]:
        r = router.classify(item["query"])
        ok = r.intent == "weather" and r.detected_district == item["place"]
        weather_ok += ok
        if not ok:
            failures.append(f"Weather: \"{item['query']}\" → {r.intent}/{r.detected_district}, expected weather/{item['place']}")

    # 3. Greetings / off-topic ------------------------------------------------------------
    scope_ok = 0
    for item in data["scope"]:
        got = router.classify(item["query"]).intent
        scope_ok += got == item["intent"]
        if got != item["intent"]:
            failures.append(f"Scope: \"{item['query']}\" → {got}, expected {item['intent']}")

    # 4. Banned pesticide warnings --------------------------------------------------------
    safety_ok = 0
    for item in data["safety"]:
        res = pipeline.process_query(item["query"], language=item["language"], generate_audio=False)
        ok = any("CIBRC" in d for d in res.safety_disclaimers)
        safety_ok += ok
        if not ok:
            failures.append(f"Safety: no banned-pesticide warning for \"{item['query']}\"")

    # 5. Follow-up questions --------------------------------------------------------------
    follow_ok = 0
    for item in data["follow_ups"]:
        if "first_weather_place" in item:
            previous = ConversationTurn(query="weather?", answer="...", intent="weather", district=item["first_weather_place"])
            r = router.classify_with_context(item["second"], previous)
            ok = r.intent == "weather" and r.detected_district == item["place"]
            got = f"{r.intent}/{r.detected_district}"
        else:
            first = pipeline.process_query(item["first"], language="en", generate_audio=False)
            second = pipeline.process_query(
                item["second"], language="en", generate_audio=False, history=[ConversationTurn.from_answer(first)]
            )
            got = second.retrieved_chunks[0].section if second.retrieved_chunks else "nothing"
            ok = item.get("section", "") in got
        follow_ok += ok
        if not ok:
            failures.append(f"Follow-up: \"{item['second']}\" → {got}")

    # 6. Optional: real Gemini answers ----------------------------------------------------
    llm = None
    if args.llm:
        print(f"Generating {args.llm} Gemini answers (uses API quota)...")
        llm_pipeline = KisanPipeline(retriever=retriever, synthesizer=get_synthesizer())
        picks = data["retrieval"][:: max(1, len(data["retrieval"]) // args.llm)][: args.llm]
        llm = {"questions": len(picks), "from_llm": 0, "right_script": 0, "numbers_grounded": 0, "latency_ms": [], "answers": []}
        for item in picks:
            start = time.perf_counter()
            res = llm_pipeline.process_query(item["query"], language=item["language"], generate_audio=False)
            llm["latency_ms"].append((time.perf_counter() - start) * 1000)
            llm["from_llm"] += res.processing_metadata.get("answer_source") == "llm"
            llm["right_script"] += script_ok(res.answer, item["language"])
            source_numbers = numbers_in(" ".join(c.text for c in res.retrieved_chunks) + " " + item["query"])
            invented = numbers_in(res.answer) - source_numbers
            llm["numbers_grounded"] += not invented
            llm["answers"].append({"query": item["query"], "language": item["language"], "answer": res.answer, "invented_numbers": sorted(invented)})
            if invented:
                failures.append(f"LLM: \"{item['query']}\" has numbers not in the sources: {sorted(invented)}")

    fallbacks = getattr(embeddings, "fallback_count", 0)
    results.update({
        "embedding_fallbacks": fallbacks,
        "date": date.today().isoformat(),
        "embeddings": args.embeddings,
        "intent": {"correct": intent_ok, "total": n},
        "weather_place": {"correct": weather_ok, "total": len(data["weather"])},
        "scope": {"correct": scope_ok, "total": len(data["scope"])},
        "banned_warnings": {"caught": safety_ok, "total": len(data["safety"]), "false_alarms": false_alarms, "checked": normal_questions},
        "follow_ups": {"correct": follow_ok, "total": len(data["follow_ups"])},
        "latency_ms": {"median": statistics.median(latencies), "p95": sorted(latencies)[int(0.95 * (n - 1))]},
        "llm": llm,
        "failures": failures,
    })

    # Report --------------------------------------------------------------------------------
    total_questions = sum(len(data[k]) for k in ("retrieval", "weather", "scope", "safety", "follow_ups"))
    lines = [
        "# KisanSahayak evaluation results",
        "",
        f"*{results['date']} · {total_questions} hand-written test questions in English, Punjabi, Hinglish and Hindi "
        f"(`eval/test_set.json`) · search embeddings: **{args.embeddings}** · answers: offline template "
        "(deterministic, no API quota)*",
        "",
    ]
    if fallbacks:
        lines += [
            f"> ⚠️ **INVALID RUN:** {fallbacks} Gemini embedding calls failed (usually quota) and fell back to the basic "
            "local embedder, so the search scores below understate Gemini search. Re-run when the quota resets.",
            "",
        ]
    lines += [
        "| Metric | Result |",
        "|---|---|",
        f"| Right advisory ranked 1st | **{pct(top1, n)}** |",
        f"| Right advisory in top 3 | **{pct(top3, n)}** |",
        f"| Question type (intent) recognised | {pct(intent_ok, n)} |",
        f"| Weather: right place detected | {pct(weather_ok, len(data['weather']))} |",
        f"| Greetings / off-topic handled | {pct(scope_ok, len(data['scope']))} |",
        f"| Banned-pesticide questions warned | **{pct(safety_ok, len(data['safety']))}** |",
        f"| False banned-pesticide warnings | {false_alarms} of {normal_questions} questions not about banned pesticides |",
        f"| Follow-up questions kept context | {pct(follow_ok, len(data['follow_ups']))} |",
        f"| Response time without LLM (median / p95) | {results['latency_ms']['median']:.0f} ms / {results['latency_ms']['p95']:.0f} ms |",
    ]
    if llm:
        k = llm["questions"]
        lines += [
            f"| Gemini answers generated (not fallback) | {pct(llm['from_llm'], k)} |",
            f"| Gemini answers in the right script | {pct(llm['right_script'], k)} |",
            f"| Gemini answers with no invented numbers | {pct(llm['numbers_grounded'], k)} |",
            f"| Gemini response time (median) | {statistics.median(llm['latency_ms']) / 1000:.1f} s |",
        ]
    lines += ["", "## Retrieval by language", "", "| Language | Right advisory 1st | In top 3 |", "|---|---|---|"]
    for lang in LANGS:
        s = by_lang.get(lang)
        if s:
            lines.append(f"| {lang} | {pct(s['top1'], s['total'])} | {pct(s['top3'], s['total'])} |")
    lines += ["", "## Failures", ""] + ([f"- {f}" for f in failures] or ["- None"])
    lines += [
        "",
        "## Notes",
        "",
        "- The test questions were written by the team, not collected from farmers; a field test set is future work.",
        "- Retrieval, intent, weather-place, safety and follow-up checks do not call the LLM, so they are repeatable.",
        "- A false banned-pesticide warning means a warning on a question that is not about banned pesticides.",
        "- \"No invented numbers\" means every number in a Gemini answer (doses, percentages, dates) appears in the retrieved advisory text or the question.",
    ]
    EVAL_DIR.mkdir(exist_ok=True)
    (EVAL_DIR / f"results_{args.embeddings}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (EVAL_DIR / f"results_{args.embeddings}.json").write_text(json.dumps(results, ensure_ascii=False, indent=2, default=float), encoding="utf-8")
    if llm:
        # Kept in its own files so later offline runs never overwrite the (quota-using) Gemini check
        k = llm["questions"]
        llm_lines = [
            "# KisanSahayak: real Gemini answer check",
            "",
            f"*{results['date']} · {k} questions from `eval/test_set.json` · search embeddings: {args.embeddings}*",
            "",
            "| Metric | Result |",
            "|---|---|",
            f"| Gemini answers generated (not fallback) | {pct(llm['from_llm'], k)} |",
            f"| Gemini answers in the requested script | {pct(llm['right_script'], k)} |",
            f"| Gemini answers with no invented numbers | {pct(llm['numbers_grounded'], k)} |",
            f"| Gemini response time (median) | {statistics.median(llm['latency_ms']) / 1000:.1f} s |",
            "",
            "\"No invented numbers\": every number in the answer (doses, percentages, dates) appears in the "
            "retrieved advisory text or the question; list numbering (\"1.\") is ignored. Full answers are in "
            "`eval/results_llm.json`.",
        ]
        (EVAL_DIR / "results_llm.md").write_text("\n".join(llm_lines) + "\n", encoding="utf-8")
        (EVAL_DIR / "results_llm.json").write_text(json.dumps(llm, ensure_ascii=False, indent=2, default=float), encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
