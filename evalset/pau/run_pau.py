"""Evaluate answers from PAU's Package of Practices (evalset/pau/questions.json).

    python scripts/build_pau_kb.py      # once: the PAU chapters are not in the repository
    python evalset/pau/run_pau.py       # offline answers: repeatable, no API quota

For each question about a covered crop on a topic our own advisories don't cover, checks that it is
answered from PAU (not referred to the KVK), from that crop's chapter, from the expected section
(first, or in the top 3), with the farmer's language around PAU's text. Writes results.md and results.json.
"""

import json
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.agent.pipeline import KisanPipeline  # noqa: E402
from app.agent.synthesizer import DeterministicGroundedSynthesizer  # noqa: E402
from app.config import settings  # noqa: E402
from evalset.kcc.run_kcc import pct, script_ok, stored_answer  # noqa: E402


def main() -> int:
    data = json.loads((HERE / "questions.json").read_text(encoding="utf-8"))
    pipeline = KisanPipeline(synthesizer=DeterministicGroundedSynthesizer())
    if not pipeline.pau_indexed:
        print("PAU's chapters are not built: run  python scripts/build_pau_kb.py  first.")
        return 1
    rows = []
    for q in data["questions"]:
        res = pipeline.process_query(q["question"], language=q["language"], generate_audio=False)
        pau = [c for c in res.retrieved_chunks if c.kind == "pau" and not c.rank_details.get("same_section_as_above")]
        sections = [c.section for c in pau]
        hit = lambda s: any(want.lower() in s.lower() for want in q["section_any"])  # noqa: E731
        rows.append({**q, "intent": res.intent, "top_sections": sections[:3], "result": {
            "from_pau": res.processing_metadata.get("knowledge") == "pau",
            "right_chapter": bool(sections) and sections[0].lower().startswith(q["crop"].lower()),
            "top1": bool(sections) and hit(sections[0]),
            "top3": any(hit(s) for s in sections[:3]),
            "script_ok": script_ok(res.answer, q["language"]),
        }, "answer": stored_answer(res)})
        print(f"{q['id']:>3} {q['language']:<8} {res.intent:<18} {(sections[0] if sections else '-')[:60]}")

    n = len(rows)
    count = lambda key: sum(r["result"][key] for r in rows)  # noqa: E731
    lines = [
        "# Answers from PAU's Package of Practices",
        "",
        f"*{date.today()} · {n} questions (topics our own advisories don't cover, for the four covered crops) · "
        f"offline answers · search embeddings: {settings.EMBEDDING_PROVIDER}*",
        "",
        "| Metric | Result |",
        "|---|---|",
        f"| Answered from PAU (not referred to the KVK) | **{pct(count('from_pau'), n)}** |",
        f"| From the right crop's chapter | {pct(count('right_chapter'), n)} |",
        f"| Expected PAU section first | **{pct(count('top1'), n)}** |",
        f"| Expected PAU section in the top 3 (the LLM sees all three) | {pct(count('top3'), n)} |",
        f"| Answer in the requested language (script) | {pct(count('script_ok'), n)} |",
    ]
    misses = [r for r in rows if not r["result"]["top3"]]
    if misses:
        lines += ["", "## Expected section not in the top 3", ""]
        lines += [f"- ({r['language']}) \"{r['question']}\" → {r['intent']}; got {', '.join(r['top_sections']) or 'nothing'}"
                  for r in misses]
    lines += ["", "PAU's text is shown in English with a note in the farmer's language; the LLM answer translates it. "
              "Whether the passage fully answers the question still needs an agronomist's review."]
    (HERE / "results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (HERE / "results.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
