"""Held-out check on real KCC queries that were NOT used while improving KisanSahayak.

    python evalset/kcc/heldout.py

The routing rules were improved using the 200-question set, which makes that set partly a development
set. This script takes the next most frequently asked distinct queries (ranks after the 200, never
looked at while tuning), in their exact logged English, labels them with the same rules as
build_testset.py, and reports the same metrics. Writes heldout_results.md and heldout.json.
"""

import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for path in (str(ROOT), str(HERE)):
    if path not in sys.path:
        sys.path.insert(0, path)

import select_questions as sel  # noqa: E402
from build_testset import expected  # noqa: E402

HELDOUT = {"wheat": 30, "paddy": 30, "cotton": 15, "mustard": 10}


def build() -> list:
    import csv
    import re

    csv.field_size_limit(10**9)
    rows = list(csv.DictReader(sel.SOURCE.open(encoding="utf-8", errors="replace")))
    counts, example = {t: Counter() for t in HELDOUT}, {}
    for r in rows:
        tp = sel.topic(r)
        if tp not in HELDOUT:
            continue
        q = sel.clean(r["QueryText"])
        merged = "?" in q and len(q.split("?", 1)[1].strip()) > 25
        if sel.SKIP.search(q) or merged or len(q) < 12:
            continue
        key = sel.dedupe_key(q)
        counts[tp][key] += 1
        example.setdefault((tp, key), q)
    items = []
    for tp, n in HELDOUT.items():
        ranked = sorted(counts[tp].items(), key=lambda kv: (-kv[1], example[(tp, kv[0])]))
        start = sel.QUOTAS[tp]  # skip the queries already in the 200-question set
        for key, times in ranked[start:start + n]:
            item = {"topic": tp, "kcc_query": example[(tp, key)], "times_asked": times}
            if not re.search(r"[a-z]", item["kcc_query"], re.I):
                continue
            item["expected"] = expected(item)
            items.append(item)
    return items


def main() -> int:
    from app.agent.pipeline import KisanPipeline
    from app.agent.synthesizer import DeterministicGroundedSynthesizer
    from run_kcc import outside_outcome

    items = build()
    pipeline = KisanPipeline(synthesizer=DeterministicGroundedSynthesizer())
    covered = [i for i in items if i["expected"]["kind"] in ("advisory", "banned")]
    outside = [i for i in items if i["expected"]["kind"] == "not_in_kb"]
    top3 = referred = from_pau = 0
    for item in items:
        res = pipeline.process_query(item["kcc_query"], language="en", generate_audio=False)
        sections = [c.section for c in res.retrieved_chunks]
        item["intent"], item["top_sections"] = res.intent, sections[:3]
        if item["expected"]["kind"] == "advisory":
            item["top3"] = any(item["expected"]["section"].lower() in s.lower() for s in sections[:3])
            top3 += item["top3"]
        elif item["expected"]["kind"] == "not_in_kb":
            item.update(outside_outcome(item["topic"], res))
            referred += item["referred"]
            from_pau += item["pau_right_crop"]
    adv = [i for i in covered if i["expected"]["kind"] == "advisory"]
    pct = lambda a, b: f"{a}/{b} ({100 * a / b:.0f}%)" if b else "n/a"  # noqa: E731
    lines = [
        "# Held-out check: real KCC queries not used for tuning",
        "",
        f"*{date.today()} · {len(items)} queries (exact logged English), ranked after the 200-question set · "
        "offline answers*",
        "",
        "| Metric | Result |",
        "|---|---|",
        f"| Covered by our advisories | {len(covered)} |",
        f"| Right advisory in top 3 (covered) | {pct(top3, len(adv))} |",
        f"| Outside our advisories | {len(outside)} |",
        f"| Outside our advisories: answered from PAU's Package of Practices, right crop's chapter | **{pct(from_pau, len(outside))}** |",
        f"| Outside our advisories: referred to KVK / Kisan Call Centre | {pct(referred, len(outside))} |",
        f"| Outside our advisories: shown advice on something else | {pct(len(outside) - referred - from_pau, len(outside))} |",
        "",
        "## Outside our advisories and answered with something other than PAU's chapter for the crop",
        "",
    ]
    lines += [f"- \"{i['kcc_query']}\" → {i['top_sections'][0] if i['top_sections'] else '-'}"
              for i in outside if not i["referred"] and not i["pau_right_crop"]]
    (HERE / "heldout_results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (HERE / "heldout.json").write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
