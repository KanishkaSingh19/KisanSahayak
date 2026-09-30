"""Run the 25-question feature test set (evalset/questions.json) through the KisanSahayak pipeline.

    python evalset/run_evalset.py          # offline answers: repeatable, no Gemini quota
    python evalset/run_evalset.py --llm    # real Gemini answers (uses API quota)
    python evalset/run_evalset.py --llm --pause 5   # stay under the free tier's per-minute limit

Typed cases (including multi-turn conversations and farm profiles) are checked automatically;
photo and voice cases are listed as manual checks. Weather uses live Open-Meteo data.
Writes evalset/results.md and results.json (results_llm.* with --llm).
"""

import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.agent.pipeline import KisanPipeline
from app.agent.state import ConversationTurn, FarmerProfile
from app.agent.synthesizer import DeterministicGroundedSynthesizer
from app.config import settings

EVALSET_DIR = Path(__file__).resolve().parent


def in_script(text: str, script: str) -> bool:
    low, high = {"gurmukhi": ("਀", "੿"), "devanagari": ("ऀ", "ॿ")}[script]
    return any(low <= ch <= high for ch in text)


def check_turn(res, expect: dict) -> list:
    """Return the failed checks for one answer (empty list = pass)."""
    # What the farmer sees: the answer plus its safety notes
    shown = "\n".join([res.answer, *res.safety_disclaimers])
    low = shown.lower()
    meta = res.processing_metadata
    top = res.retrieved_chunks[0].section if res.retrieved_chunks else ""
    problems = []
    if "intent" in expect and res.intent not in expect["intent"]:
        problems.append(f"intent {res.intent}, expected {' or '.join(expect['intent'])}")
    if "section" in expect and expect["section"].lower() not in top.lower():
        problems.append(f"top advisory '{top or 'none'}', expected '{expect['section']}'")
    if "answer_any" in expect and not any(k.lower() in low for k in expect["answer_any"]):
        problems.append(f"answer mentions none of {expect['answer_any']}")
    missing = [k for k in expect.get("answer_all", []) if k.lower() not in low]
    if missing:
        problems.append(f"answer is missing {missing}")
    found = [k for k in expect.get("answer_none", []) if k.lower() in low]
    if found:
        problems.append(f"answer should not mention {found}")
    if "script" in expect and not in_script(res.answer, expect["script"]):
        problems.append(f"answer is not in {expect['script']} script")
    if "district" in expect and (meta.get("district") or "").lower() != expect["district"].lower():
        problems.append(f"weather for '{meta.get('district')}', expected '{expect['district']}'")
    if expect.get("no_advisory") and res.retrieved_chunks:
        # Any advisory shown here would be for another crop, with doses that do not apply
        problems.append(f"showed an advisory for another crop ('{top}')")
    if "eligibility" in expect and meta.get("pmk_eligibility") != expect["eligibility"]:
        problems.append(f"eligibility '{meta.get('pmk_eligibility')}', expected '{expect['eligibility']}'")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--llm", action="store_true", help="Use the configured LLM (Gemini) instead of offline answers")
    parser.add_argument("--pause", type=float, default=0, help="Seconds to wait between questions (free-tier rate limits)")
    args = parser.parse_args()

    data = json.loads((EVALSET_DIR / "questions.json").read_text(encoding="utf-8"))
    pipeline = KisanPipeline() if args.llm else KisanPipeline(synthesizer=DeterministicGroundedSynthesizer())
    answers = (
        f"LLM ({settings.GEMINI_MODEL}, backup {settings.GEMINI_FALLBACK_MODEL}; see 'Answers by source')"
        if args.llm else "offline template (no API quota)"
    )

    rows, report, turns_total, turns_passed = [], [], 0, 0
    sources = {}  # answer_source -> count, to show which answers really came from the LLM
    for case in data["cases"]:
        if case["mode"] != "text":
            rows.append((case, "manual", []))
            continue
        history, case_problems, case_log = [], [], []
        for n, turn in enumerate(case["turns"], 1):
            profile = FarmerProfile(**turn["profile"]) if "profile" in turn else None
            if args.pause and turns_total:
                time.sleep(args.pause)
            start = time.perf_counter()
            res = pipeline.process_query(
                turn["query"], language=turn.get("language", case["language"]), generate_audio=False,
                history=history, profile=profile,
            )
            ms = int((time.perf_counter() - start) * 1000)
            source = res.processing_metadata.get("answer_source")
            if source == "llm" and getattr(pipeline.synthesizer, "last_model", None):
                source = f"llm:{pipeline.synthesizer.last_model}"  # which model actually answered
            if args.llm and source == "template_llm_failed":
                # Out of quota (or the models are down): stop rather than score template answers as LLM ones
                print(f"\nStopped at case {case['id']}, turn {n}: every Gemini model failed (usually the API quota).")
                print("No results were written. Change GEMINI_API_KEY in .env and run again.")
                return 2
            if source:
                sources[source] = sources.get(source, 0) + 1
            history.append(ConversationTurn.from_answer(res))
            problems = check_turn(res, turn["expect"])
            turns_total += 1
            turns_passed += not problems
            case_problems += [f"turn {n} (\"{turn['query']}\"): {p}" for p in problems]
            case_log.append({
                "query": turn["query"], "intent": res.intent, "ms": ms, "passed": not problems, "problems": problems,
                "top_section": res.retrieved_chunks[0].section if res.retrieved_chunks else None,
                "district": res.processing_metadata.get("district"), "answer_source": source, "answer": res.answer,
            })
        rows.append((case, "pass" if not case_problems else "FAIL", case_problems))
        report.append({"id": case["id"], "feature": case["feature"], "passed": not case_problems, "turns": case_log})
        print(f"{case['id']:>2}. {'PASS' if not case_problems else 'FAIL'}  {case['feature']}")
        for p in case_problems:
            print(f"      - {p}")

    auto = [r for r in rows if r[1] != "manual"]
    passed = sum(r[1] == "pass" for r in auto)
    lines = [
        "# KisanSahayak feature test results",
        "",
        f"*{date.today()} · {len(data['cases'])} test cases (`evalset/questions.json`) · answers: {answers} · "
        f"search embeddings: {settings.EMBEDDING_PROVIDER} · weather: live Open-Meteo*",
        "",
        "| Result | Value |",
        "|---|---|",
        f"| Automated cases passed | **{passed}/{len(auto)}** |",
        f"| Conversation turns passed | {turns_passed}/{turns_total} |",
        f"| Manual cases (photo, voice) | {len(rows) - len(auto)}, see `evalset/questions.md` |",
        f"| Answers by source | {', '.join(f'{k}: {v}' for k, v in sorted(sources.items())) or 'n/a'} |",
        "",
        "| # | Feature | Result |",
        "|---|---|---|",
    ]
    lines += [f"| {c['id']} | {c['feature']} | {status} |" for c, status, _ in rows]
    failed = [(c, p) for c, status, p in rows if status == "FAIL"]
    if failed:
        lines += ["", "## Failures", ""]
        for c, problems in failed:
            lines += [f"- **{c['id']}. {c['feature']}**"] + [f"  - {p}" for p in problems]
    llm_answers = sum(v for k, v in sources.items() if k.startswith("llm"))
    if args.llm and llm_answers < sum(sources.values()):
        lines += ["", f"Note: {llm_answers} of {sum(sources.values())} generated answers came from the LLM; the rest "
                  "fell back to the offline template (usually API quota or a busy model)."]
    name = "results_llm" if args.llm else "results"
    (EVALSET_DIR / f"{name}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (EVALSET_DIR / f"{name}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nAutomated cases passed: {passed}/{len(auto)} · turns passed: {turns_passed}/{turns_total}")
    print(f"Answers by source: {sources}")
    print(f"Wrote evalset/{name}.md and evalset/{name}.json")
    return 0 if passed == len(auto) else 1


if __name__ == "__main__":
    sys.exit(main())
