# Cost per farmer question

*2026-10-01 · measured token counts, published prices · Rs 95.2 per USD*

- Answer prompt (instructions + 3 advisory chunks + question): **1035 tokens** on average (980–1091, 8 sample questions in 4 languages)
- Answer: **212 tokens** on average (72–595, 25 real Gemini answers)

| Question | Cost (Rs) | Cost (USD) | Notes |
|---|---|---|---|
| Greeting, off-topic, weather, market price, not-covered referral | 0.000 | 0.00000 | no LLM call |
| PM-KISAN question | 0.149 | 0.00157 | 1 answer (eligibility itself is rule-based) |
| Typed crop question (Gemini 3.7 Flash) | 0.150 | 0.00157 | 1 embedding + 1 answer |
| Typed crop question, from 1 Jan 2027 prices | 0.299 | 0.00315 | standard Gemini 3.7 Flash price |
| Typed crop question (backup: Flash-Lite) | 0.055 | 0.00058 | when the main model is busy |
| Voice question, English/Hindi/Hinglish (Groq Whisper + answer) | 0.179 | 0.00188 | 10 s minimum billing |
| Voice question, Punjabi (Gemini audio + answer) | 0.182 | 0.00191 | ~6 s of speech |
| Photo diagnosis (vision + embedding + answer) | 0.338 | 0.00355 | ~1100 image tokens |
| Spoken answer (Edge-TTS / gTTS) | 0.000 | 0.00000 | free services |

**Every kind of question costs well under Rs 1**: the most expensive (a photo) is about Rs 0.34; a typed question is about Rs 0.15. Rs 1 buys roughly 7 typed questions.

## Prices used

| Service | Price | Note |
|---|---|---|
| gemini-3.7-flash | $0.75 in / $3.75 out per 1M tokens | introductory price until 31 Dec 2026; then 1.50 / 7.50 |
| gemini-flash-lite | $0.25 in / $1.5 out per 1M tokens | backup model |
| gemini-embedding-001 | $0.15 in / $0 out per 1M tokens | search embedding of the question |
| groq-whisper-large-v3 | $0.111/hour of audio | billed for at least 10 s per request |

Free-tier API keys (used for this hackathon) cost nothing but are rate-limited. Answer tokens are the visible text; if the model also bills internal "thinking" tokens, the answer cost can be a few times higher, still well under Rs 1. Prices change: re-check Google AI and Groq pricing pages before quoting.
