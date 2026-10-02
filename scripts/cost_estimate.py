"""Estimate the cost of one farmer question from real token counts.

    python scripts/cost_estimate.py

Prompt tokens are counted with Gemini's count_tokens (free, no answer quota) on the exact prompts
the app builds for sample questions in all four languages; answer tokens are counted on the real
Gemini answers saved in evalset/results_llm.json. Prices are set in PRICES below (check them before
quoting). Writes docs/cost_estimate.md.
"""

import json
import statistics
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from google import genai  # noqa: E402

from app.agent.pipeline import KisanPipeline  # noqa: E402
from app.agent.synthesizer import DeterministicGroundedSynthesizer, build_system_prompt  # noqa: E402
from app.config import settings  # noqa: E402
from app.tools.vision import PROMPT as VISION_PROMPT  # noqa: E402

# USD per 1M tokens (Gemini) / per hour of audio (Groq), checked 2026-10-01; rupees per dollar the same day
PRICES = {
    "gemini-3.7-flash": {"in": 0.75, "out": 3.75, "note": "introductory price until 31 Dec 2026; then 1.50 / 7.50"},
    "gemini-flash-lite": {"in": 0.25, "out": 1.50, "note": "backup model"},
    "gemini-embedding-001": {"in": 0.15, "note": "search embedding of the question"},
    "groq-whisper-large-v3": {"hour": 0.111, "min_seconds": 10, "note": "billed for at least 10 s per request"},
}
INR_PER_USD = 95.2
IMAGE_TOKENS = 1100      # upper estimate for one photo at default resolution
AUDIO_TOKENS_PER_SEC = 32  # Gemini audio input
VOICE_SECONDS = 6          # typical spoken question
SAMPLES = [
    ("How to control aphids in mustard crop?", "en"),
    ("What are the symptoms and treatment of yellow rust in wheat?", "en"),
    ("ਸਰ੍ਹੋਂ ਵਿੱਚ ਚੇਪੇ ਦੀ ਰੋਕਥਾਮ ਕਿਵੇਂ ਕਰੀਏ?", "pa"),
    ("ਨਰਮੇ ਵਿੱਚ ਗੁਲਾਬੀ ਸੁੰਡੀ ਦੀ ਰੋਕਥਾਮ ਕਿਵੇਂ ਕਰੀਏ?", "pa"),
    ("Dhan mein bhoora tilla (BPH) ka kya ilaj hai?", "hinglish"),
    ("Gehun mein sinchai ka sahi samay kya hai?", "hinglish"),
    ("धान में भूरा तेला (BPH) का क्या इलाज है?", "hi"),
    ("गेहूं में पीली कुंगी के लक्षण और उपचार क्या हैं?", "hi"),
]


def usd(tokens_in: float, tokens_out: float, model: str) -> float:
    p = PRICES[model]
    return (tokens_in * p["in"] + tokens_out * p.get("out", 0)) / 1e6


def main() -> int:
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    count = lambda text: client.models.count_tokens(model=settings.GEMINI_MODEL, contents=text).total_tokens  # noqa: E731
    pipeline = KisanPipeline(synthesizer=DeterministicGroundedSynthesizer())

    prompt_tokens = []
    for query, lang in SAMPLES:
        res = pipeline.process_query(query, language=lang, generate_audio=False)
        context = "\n\n".join(f"Source [{c.citation}]:\n{c.text}" for c in res.retrieved_chunks)
        prompt = f"{build_system_prompt(context, lang)}\n\nFarmer Query: {query}\n\nGrounded Answer:"
        prompt_tokens.append(count(prompt))
    answers = [t["answer"] for case in json.loads((ROOT / "evalset" / "results_llm.json").read_text(encoding="utf-8"))
               for t in case["turns"] if (t.get("answer_source") or "").startswith("llm")]
    answer_tokens = [count(a) for a in answers]
    p_in, p_out = statistics.mean(prompt_tokens), statistics.mean(answer_tokens)
    q_tokens = 30  # question embedding

    text_main = usd(p_in, p_out, "gemini-3.7-flash") + usd(q_tokens, 0, "gemini-embedding-001")
    text_lite = usd(p_in, p_out, "gemini-flash-lite") + usd(q_tokens, 0, "gemini-embedding-001")
    text_2027 = (p_in * 1.5 + p_out * 7.5) / 1e6 + usd(q_tokens, 0, "gemini-embedding-001")
    groq = PRICES["groq-whisper-large-v3"]["hour"] * max(VOICE_SECONDS, 10) / 3600
    gemini_audio = usd(VOICE_SECONDS * AUDIO_TOKENS_PER_SEC + 60, 40, "gemini-3.7-flash")
    vision = usd(IMAGE_TOKENS + count(VISION_PROMPT), 250, "gemini-3.7-flash")

    rows = [
        ("Greeting, off-topic, weather, market price, not-covered referral", 0.0, "no LLM call"),
        ("PM-KISAN question", usd(p_in, p_out, "gemini-3.7-flash"), "1 answer (eligibility itself is rule-based)"),
        ("Typed crop question (Gemini 3.7 Flash)", text_main, "1 embedding + 1 answer"),
        ("Typed crop question, from 1 Jan 2027 prices", text_2027, "standard Gemini 3.7 Flash price"),
        ("Typed crop question (backup: Flash-Lite)", text_lite, "when the main model is busy"),
        ("Voice question, English/Hindi/Hinglish (Groq Whisper + answer)", groq + text_main, "10 s minimum billing"),
        ("Voice question, Punjabi (Gemini audio + answer)", gemini_audio + text_main, f"~{VOICE_SECONDS} s of speech"),
        ("Photo diagnosis (vision + embedding + answer)", vision + text_main, f"~{IMAGE_TOKENS} image tokens"),
        ("Spoken answer (Edge-TTS / gTTS)", 0.0, "free services"),
    ]
    lines = [
        "# Cost per farmer question",
        "",
        f"*{date.today()} · measured token counts, published prices · Rs {INR_PER_USD} per USD*",
        "",
        f"- Answer prompt (instructions + 3 advisory chunks + question): **{p_in:.0f} tokens** on average "
        f"({min(prompt_tokens)}–{max(prompt_tokens)}, {len(prompt_tokens)} sample questions in 4 languages)",
        f"- Answer: **{p_out:.0f} tokens** on average ({min(answer_tokens)}–{max(answer_tokens)}, "
        f"{len(answer_tokens)} real Gemini answers)",
        "",
        "| Question | Cost (Rs) | Cost (USD) | Notes |",
        "|---|---|---|---|",
    ]
    lines += [f"| {name} | {c * INR_PER_USD:.3f} | {c:.5f} | {note} |" for name, c, note in rows]
    worst = max(c for _, c, _ in rows)
    lines += [
        "",
        f"**Every kind of question costs well under Rs 1**: the most expensive (a photo) is about "
        f"Rs {worst * INR_PER_USD:.2f}; a typed question is about Rs {text_main * INR_PER_USD:.2f}. "
        f"Rs 1 buys roughly {1 / (text_main * INR_PER_USD):.0f} typed questions.",
        "",
        "## Prices used",
        "",
        "| Service | Price | Note |",
        "|---|---|---|",
    ]
    for model, p in PRICES.items():
        price = f"${p['hour']}/hour of audio" if "hour" in p else f"${p['in']} in / ${p.get('out', 0)} out per 1M tokens"
        lines.append(f"| {model} | {price} | {p['note']} |")
    lines += [
        "",
        "Free-tier API keys (used for this hackathon) cost nothing but are rate-limited. Answer tokens are the "
        "visible text; if the model also bills internal \"thinking\" tokens, the answer cost can be a few times "
        "higher, still well under Rs 1. Prices change: re-check Google AI and Groq pricing pages before quoting.",
        "",
        "Not measured above: a question that states an assumption (\"since ...\", \"I heard ...\") makes one extra "
        "Gemini call to check it (`app/agent/premises.py`), including on weather and price questions.",
    ]
    out = ROOT / "docs" / "cost_estimate.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
