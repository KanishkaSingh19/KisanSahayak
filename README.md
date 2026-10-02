# 🌾 KisanSahayak (किसान सहायक) 

> **Voice-first Multilingual AI Farming Assistant for Indian Farmers**  
> *Grounded agricultural RAG (FAISS + BM25 + Reciprocal Rank Fusion) with voice input/output and live ag-weather spray advisories*

[![tests](https://github.com/KanishkaSingh19/KisanSahayak/actions/workflows/tests.yml/badge.svg)](https://github.com/KanishkaSingh19/KisanSahayak/actions/workflows/tests.yml)

### 🚀 Live app: **https://kisansahayak1.streamlit.app/**
*(Free hosting sleeps when idle: if you see a "wake up" screen, click it and allow about a minute to start.)*

Farmers ask about crops, pests, pesticides, weather, crop prices or government schemes in Hindi, Punjabi, Hinglish or English — by text, voice note or crop photo. Answers are grounded in curated ICAR, PAU Ludhiana and CIBRC advisories, PAU's *Package of Practices* and official scheme and price sources, with citations, banned-chemical checks and spray disclaimers.

**Evaluated on 200 real Kisan Call Centre queries from Punjab (Jan–Jul 2025)** in English, Hindi, Punjabi and Hinglish:
- answered in the requested language for 200/200;
- weather given for the right district for 15/15;
- the right advisory in the top 3 for 25/25 of the queries our advisories cover;
- 125/140 (89%) of the other queries answered from the right crop's chapter of PAU's *Package of Practices*.

It is backed by safety and adversarial tests and 414 automated tests in CI. See [Evaluation](#-evaluation).

---

## ✨ Features

- **Crop & pest advisories** for wheat, mustard, paddy and cotton (yellow rust, karnal bunt, aphid, white rust, BLB, BPH, pink bollworm, whitefly), with multilingual aliases (e.g. *sarson* / सरसों / ਸਰ੍ਹੋਂ).
- **Grounded answers only** — responses come from the `data/raw/` advisories or, for other topics of the four covered crops, PAU's *Package of Practices* chapters, and list their sources; if nothing relevant is found, the farmer is referred to their local KVK.
- **Pesticide safety guardrails** — CIBRC banned-chemical scan (Monocrotophos, Endosulfan, DDT, Phorate, Paraquat, …) and a statutory disclaimer on any spray/dosage answer.
- **Ag-weather & spray window** — live [Open-Meteo](https://open-meteo.com/) data for any place in India (44 common districts and towns built in, others found with Open-Meteo's place search) with spray and irrigation advice when asked; a whole state asks which district; falls back to seasonal defaults when offline.
- **System status sidebar** — shows which LLM and speech-to-text services are actually active.
- **Voice input** — spoken questions are transcribed with Whisper Large v3 via Groq (Gemini audio for Punjabi, and as a backup); the API's `/ask/voice` also accepts voice-note files (WAV/MP3/M4A/OGG).
- **Voice output** — tap Listen to hear the answer: English, Hindi and Hinglish via Edge-TTS, Punjabi via gTTS (Edge-TTS has no Punjabi voice).
- **One chat box for text, photo and voice** — type a question, attach a photo with **+** (on a phone this also offers the camera), record a voice note with the microphone, or use **Take a photo** under the box (laptop or phone camera; the photo is attached to your next message). Any combination is sent together with the arrow: the voice note is transcribed and joined to the text, and with a photo both become the question about the photo. Answers to spoken questions are read aloud.
- **Photo diagnosis** — Gemini Vision names the likely disease or pest and its confidence, and the treatment comes only from the verified advisories. Unclear photos, healthy plants and crops the advisories don't cover get no treatment, and every photo answer carries an "AI estimate, confirm with your KVK" note.
- **PM-KISAN guidance** — benefit, eligibility, exclusions, how to apply, eKYC, status checks and why an instalment can be held, from the official site ([pmkisan.gov.in](https://pmkisan.gov.in), checked 30 Sep 2026) in all four languages. Eligibility is decided by fixed rules from the farm profile, never by the LLM, and every answer says to confirm on the official portal.
- **Crop insurance (PMFBY) and Kisan Credit Card guidance** — premiums, what is covered, who can enrol, how to enrol and claim (72 hours, helpline 14447); KCC interest (7%, 4% with timely repayment), loan limit, collateral-free limit, who can get one and how to apply. Written from official sources (PMFBY operational guidelines, PIB releases of 2025-26, checked 1 Oct 2026) in all four languages. Crop insurance answers always say that **Punjab has not implemented PMFBY**. Other schemes (Soil Health Card, PM-KISAN Maandhan, PM-KUSUM, PMKSY) are recognised by name and referred to their official website instead of being answered with another scheme's rules.
- **My farm profile (optional)** — district, crops, land and a few yes/no PM-KISAN questions. Used for the local weather when no place is named, for the crop when a question names none (if only one covered crop is listed), and for eligibility. Nothing is stored: it lasts only for the browser session and asks for no name, phone or Aadhaar.
- **Language switch** — English (default), Punjabi, Hinglish or Hindi for the UI, the answer, warnings and voice.
- **Gemini fallback chain** — a busy main model hands over to a backup model, then to the offline template with a visible note.
- **Market prices** — asks like "MSP of wheat" or "sarson ka bhav Sangrur mandi" get the government Minimum Support Price (Kharif 2026-27 and Rabi 2026-27, with the previous season; `data/market/msp.json`, source and date shown) plus the latest mandi prices: per-mandi prices from data.gov.in, or, if that is down, the daily average from Agmarknet 2.0 (agmarknet.gov.in; district first, otherwise the state, and the answer says which). The app identifies itself as KisanSahayak in these requests. If both are unreachable, the answer says so and points to agmarknet.gov.in, eNAM and the Kisan Call Centre; a price is never guessed. Uses the farmer's district and crop from the profile.
- **Checking what the question assumes** — a claim in the question is checked before it is accepted. Figures (an amount, a dose, a price, the temperature, "it will rain") are checked in code against the evidence; an assumption stated in words ("Since MSP guarantees that the government will buy all my wheat, …") is checked, for every kind of answer, by Gemini against numbered sentences from the evidence used and from official statements in `data/facts/` (e.g. PIB on procurement at MSP). Gemini can only cite sentences by number; the farmer sees a **Small correction** made of the cited official sentences, in their language, and then the answer to the rest of the question. When Gemini is unavailable the official statements are shown and the assumption is marked unchecked. A corrected assumption shows the badge "Verified · premise corrected", never plain "Verified".
- **KVK expert review** — answers with a pesticide spray or dose, banned-pesticide questions, weakly grounded AI answers, uncertain photo diagnoses and questions we can't answer are sent to a review queue (the farmer sees "Sent for KVK expert review"). KVK experts mark them correct, needs correction (with the right advice) or unsafe on the **KVK expert review** page, and can download the queue as CSV. Set `REVIEW_PASSCODE` to restrict the page. Only the question and answer are stored.
- **Topics not covered** — questions about weeds, nutrient deficiencies, varieties, prices and other pests are referred to the Kisan Call Centre (1800-180-1551) and the KVK instead of being answered with an unrelated advisory.
- **Crops not covered** — a question about a crop the advisories don't cover (sugarcane, potato, tomato, …) gets a "not covered, contact your KVK" reply instead of advice borrowed from another crop.
- **Scope handling** — greetings and off-topic queries (cricket, movies, politics, …) get a polite redirect.

---

## 🤖 AI Models & Providers

Every AI component is optional. Without API keys the app runs fully offline-capable with deterministic fallbacks.

| Component | Provider / Model | Needs | Fallback when not configured |
|---|---|---|---|
| Answer generation | Google Gemini (`GEMINI_MODEL`) or OpenAI `gpt-4o-mini` (`OPENAI_MODEL`) | `LLM_PROVIDER` + matching API key | Deterministic template filled from retrieved advisory text |
| Speech-to-text | Groq-hosted `whisper-large-v3`; Gemini audio for Punjabi and as backup | `GROQ_API_KEY` (and `GEMINI_API_KEY`) | The farmer is asked to try again or type the question |
| Photo diagnosis | Gemini Vision (same main/backup models) identifies crop, likely problem and confidence; never gives treatment | `GEMINI_API_KEY` | "Couldn't analyse the photo" message |
| Text-to-speech | Microsoft Edge-TTS (`en-IN-NeerjaNeural`, `hi-IN-MadhurNeural`); gTTS for Punjabi, since Edge-TTS has no Punjabi voice | `edge-tts` and `gTTS` packages + internet, no key | Text-only answer |
| Dense embeddings | Hugging Face `paraphrase-multilingual-MiniLM-L12-v2` (384-dim, runs locally) | `EMBEDDING_PROVIDER=minilm` + `sentence-transformers` (one-time ~470 MB model download) | Local embedder |
| | Gemini `gemini-embedding-001` (768-dim) | `EMBEDDING_PROVIDER=gemini` + `GEMINI_API_KEY` | Local embedder |
| | Local hashed word + character n-gram vectors (256-dim) | Nothing (default, `EMBEDDING_PROVIDER=local`) | — |
| Premise check | Gemini labels assumptions stated in words against numbered evidence sentences (figures are checked in code) | `GEMINI_API_KEY` | Official statements shown, assumption marked unchecked |
| Intent routing | Rule-based multilingual keyword lexicons (no model) | — | — |

> **Note:** `LLM_PROVIDER` defaults to `mock` in `app/config.py`. With no `.env` file, no LLM is called and answers come from the deterministic template.

---

## 🚀 Architecture

```
Farmer message: text, voice note and/or photo (one chat box)
   │
   ├── Voice ──► [Whisper STT via Groq; Gemini audio for Punjabi] (app/speech/stt.py) ──► transcript
   ├── Photo ──► [Gemini Vision: likely problem + confidence] (app/tools/vision.py) ──► search terms
   │
   ▼
[Language Detection + Intent & Entity Extraction] (app/agent/router.py)
   │   crop · pest/disease · place · scheme · follow-ups from the conversation
   │
   ├── Greeting / off-topic / crop not covered ──► Polite redirect or KVK / Kisan Call Centre referral
   ├── Weather ──► [Open-Meteo Ag-Weather Tool] (app/tools/weather_tool.py): spray / irrigation advice
   ├── Prices ───► [MSP table + data.gov.in / Agmarknet mandi prices] (app/tools/market.py)
   ├── Schemes ──► [PM-KISAN, PMFBY, KCC official texts + eligibility rules] (app/tools/schemes.py)
   ▼ Crop / Safety / General Agriculture
[Hybrid Agricultural RAG] (app/rag/hybrid_retriever.py)
   ├── Dense Semantic Search (FAISS / app/rag/faiss_retriever.py)
   ├── Sparse Keyword Search (BM25Okapi / app/rag/bm25_retriever.py)
   ├── Reciprocal Rank Fusion (k=60 / app/rag/rrf.py)
   └── Corrective search: retry in English terms when the two searches disagree (app/agent/pipeline.py)
   │   our advisories, or PAU's Package of Practices chapter for the crop (app/rag/pau_kb.py)
   ▼
[Grounded Answer Synthesizer] (app/agent/synthesizer.py)
   │   Gemini (main → backup model) / OpenAI / deterministic template
   ▼
[Checks on every answer]
   ├── Numbers: every amount must be in the sources (app/agent/guardrails.py); per-acre totals in code (app/tools/dose.py)
   ├── Claims in the question: figures in code (app/agent/claims.py), worded premises (app/agent/premises.py)
   ├── Banned Chemical Scan (CIBRC) and Statutory Spray Disclaimers (app/agent/guardrails.py)
   └── Evidence / source / KVK review statuses (app/review.py)
   │
   ▼
[Answer with citations and status badges] ──► [Edge-TTS / gTTS audio] (app/speech/tts.py)
```

Orchestrated end-to-end by `app/agent/pipeline.py` (`KisanPipeline`).

**Chunking** (`app/rag/chunker.py`): each advisory section (one crop, one disease or pest) becomes one chunk, so topics are never mixed. Sections longer than `CHUNK_SIZE` (1000 characters) are split at sentence boundaries. Each piece repeats the crop, topic and source in a header and starts with up to `CHUNK_OVERLAP` (150) characters from the end of the previous piece: whole sentences when they fit, otherwise the last words. 14 sections give 22 chunks. A saved index is rebuilt automatically when the advisories or chunk settings change.

**Ranking by section** (`app/rag/hybrid_retriever.py`): dense and BM25 results are each reduced to the best chunk per advisory section before Reciprocal Rank Fusion, so a long section split into several chunks cannot fill every slot. The top 3 sections are returned, followed by their other matching chunks so the LLM sees the whole advisory.

**PAU's full chapters** (`app/rag/pau_kb.py`): topics our 14 advisories don't cover, for wheat, mustard, paddy and cotton (weeds, varieties, nutrients, other pests, nursery, harvest…), are answered from PAU's *Package of Practices* chapters, searched only for that crop, with PAU's page numbers. PAU's text is copyrighted, so it is not in the repository: `python scripts/build_pau_kb.py` downloads the two books from pau.edu and extracts the chapters (git-ignored), and the app does this on its first start (`PAU_AUTO_BUILD`). Without them the app works as before and refers those questions to the KVK. See [`evalset/pau/README.md`](evalset/pau/README.md).

**Corrective search** (`app/agent/pipeline.py`): the top advisory is trusted when the meaning-based and keyword searches both rank it first. If they disagree, the app searches again with the crop and the topic's English words ("ਕਣਕ ਨੂੰ ਪਾਣੀ ਕਦੋਂ ਲਾਈਏ?" -> "Wheat irrigation") and uses that result if keyword search confirms it; otherwise the first answer stands and goes to KVK expert review. On 95 labelled questions this raised the right advisory first from 79 to 82, and every corrected answer was right (KCC covered questions: top 3 23/25 -> 25/25).

**Advisory sources:** the crop advisories follow PAU's *Package of Practices for Crops of Punjab* (Rabi 2025-26 and Kharif 2026). Each section records the printed pages it comes from (`source_reference`), and citations show them, e.g. "PAU Package of Practices for Crops of Punjab, Rabi 2025-26, pages 18-21".

---

## 📂 Repository Structure

```
KisanSahayak/
├── app/
│   ├── config.py                 # Pydantic Settings & environment config
│   ├── api.py                    # FastAPI REST API over the same pipeline (/ask, /ask/image, /ask/voice, /weather, /speak)
│   ├── i18n.py                   # All farmer-facing text in English, Punjabi, Hinglish and Hindi
│   ├── crops.py                  # Covered crops and their names in every language
│   ├── textmatch.py              # Word matching in Latin, Devanagari and Gurmukhi script
│   ├── review.py                 # KVK expert review queue
│   ├── agent/
│   │   ├── state.py              # Pydantic schemas for intent, answer, conversation turn, farm profile
│   │   ├── router.py             # Intent classification & crop/pest/place/scheme extraction
│   │   ├── synthesizer.py        # Grounded response generator (Gemini/OpenAI/deterministic template)
│   │   ├── guardrails.py         # CIBRC banned chemical filter, grounding and number checks
│   │   ├── claims.py             # Checks figures and names stated in the question
│   │   ├── premises.py           # Checks assumptions stated in words (Gemini verifier, cited evidence)
│   │   └── pipeline.py           # End-to-end orchestrator (text, voice, photo)
│   ├── rag/
│   │   ├── chunker.py            # Structured agricultural chunking with metadata
│   │   ├── embeddings.py         # Local hashed n-gram / MiniLM / Gemini dense embeddings (+ Gemini vector cache)
│   │   ├── faiss_retriever.py    # FAISS dense index with cosine ranking
│   │   ├── bm25_retriever.py     # BM25Okapi sparse keyword index
│   │   ├── rrf.py                # Reciprocal Rank Fusion algorithm
│   │   ├── hybrid_retriever.py   # Hybrid FAISS + BM25 + RRF coordinator
│   │   ├── pau_kb.py             # Builds PAU's Package of Practices chapters (downloaded, git-ignored)
│   │   └── ingest.py             # Ingestion CLI for the advisories (and PAU's chapters)
│   ├── speech/
│   │   ├── stt.py                # Whisper (Groq) speech-to-text; Gemini audio for Punjabi
│   │   └── tts.py                # Edge-TTS (English, Hindi, Hinglish) and gTTS (Punjabi)
│   └── tools/
│       ├── weather_tool.py       # Open-Meteo ag-weather & spray window advisory
│       ├── location.py           # Place-name lookup (any place in India)
│       ├── market.py             # MSP table and live mandi prices
│       ├── dose.py               # Per-acre doses scaled to the farm size
│       ├── vision.py             # Gemini Vision crop-photo diagnosis
│       └── schemes.py            # Scheme guidance (PM-KISAN, PMFBY, KCC), PM-KISAN eligibility rules
├── data/
│   ├── raw/                      # Crop advisories from PAU's Package of Practices (with page numbers) & CIBRC safety (JSON)
│   ├── translations.json         # Punjabi, Hindi and Hinglish versions of the advisories
│   ├── schemes/                  # PM-KISAN, PMFBY crop insurance, Kisan Credit Card (official sources, 4 languages)
│   ├── market/msp.json           # Minimum Support Prices with source and date
│   ├── facts/                    # Sourced official statements for checking premises (4 languages)
│   ├── vectors/                  # Shipped Gemini embedding cache (numbers only)
│   ├── sample_photos/            # Crop photos for trying the photo diagnosis
│   ├── indices/                  # Serialized FAISS & BM25 indices (generated)
│   └── audio/                    # Generated TTS audio files
├── frontend/
│   ├── app.py                    # Streamlit chat UI (4 languages, text/voice/photo, weather card, farm profile)
│   ├── pages/1_KVK_expert_review.py  # Review page for KVK experts
│   └── requirements.txt          # Lightweight requirements for Streamlit Community Cloud
├── tests/                        # pytest suite (414 tests)
├── eval/                         # 67-question accuracy set and reports (scripts/evaluate.py)
├── evalset/                      # Feature scenarios, Kisan Call Centre (kcc/) and PAU (pau/) test sets
├── scripts/                      # Evaluation, cost estimate, PAU build, embedding cache, translation
├── docs/cost_estimate.md         # Cost per question
├── run_verification.py           # Runs 6 example queries through the pipeline
├── Dockerfile
├── .env.example
├── requirements.txt
├── AI_DISCLOSURE.md
└── README.md
```

---

## 🛠️ Quickstart

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure (optional)
Copy `.env.example` to `.env` and fill in the keys for the features you want:

| Variable | Purpose |
|---|---|
| `LLM_PROVIDER` | `gemini`, `openai`, or `mock` (default, no LLM) |
| `GEMINI_API_KEY` / `GEMINI_MODEL` | Gemini answers, photo diagnosis, premise checks (and optional embeddings) |
| `GEMINI_FALLBACK_MODEL` | Backup model when the main one is busy (default `gemini-flash-lite-latest`) |
| `OPENAI_API_KEY` / `OPENAI_MODEL` | OpenAI answer generation |
| `GROQ_API_KEY` | Voice input (Whisper STT) |
| `ENABLE_TTS` | Spoken answers (default `True`) |
| `EMBEDDING_PROVIDER` | `local` (default), `minilm`, or `gemini` |
| `HF_CACHE_DIR` | Folder for the MiniLM model download (empty = Hugging Face default cache) |
| `USE_PAU_KB` / `PAU_AUTO_BUILD` | Search PAU's *Package of Practices* chapters / build them on first start (both default `True`) |
| `DATA_GOV_API_KEY` | Live mandi prices from data.gov.in (the public sample key is used if empty) |
| `REVIEW_PASSCODE` / `REVIEW_QUEUE_PATH` | Passcode for the KVK expert review page / where the queue file is kept |

> Changing `EMBEDDING_PROVIDER` changes the vector size; the saved index is detected as stale and rebuilt automatically on next start (or run the ingest step below).

> `GEMINI_MODEL` defaults to `gemini-3.7-flash`. Set it to a model available on your Gemini account.

### 3. Ingest Agricultural Knowledge Base
Builds the FAISS dense and BM25 sparse indices from `data/raw/`. The app also does this automatically on first run if no indices exist.
```bash
python -m app.rag.ingest
```

### 4. Run Tests
```bash
pytest -v
```

All tests also run automatically on GitHub on every push and pull request (`.github/workflows/tests.yml`), with no API keys needed.

### 5. Try Example Queries
```bash
python run_verification.py
```
Prints the answers to 6 example questions. For scored results, see [Evaluation](#-evaluation).

### 6. Run the Streamlit Interface
```bash
streamlit run frontend/app.py
```

> Use `streamlit run`, not `python -m streamlit run`. The latter fails with `No module named 'app.agent'` because `frontend/app.py` shadows the `app` package.

### 7. Run the REST API (optional)
The same pipeline is available as a FastAPI service for other clients (mobile app, WhatsApp bot, IVR):
```bash
uvicorn app.api:app --port 8000
```
Interactive docs: http://localhost:8000/docs

| Endpoint | Purpose |
|---|---|
| `POST /ask` | Ask a question: `{"query": "...", "language": "en|pa|hinglish|hi", "history": [...], "profile": {...}}` |
| `POST /ask/voice` | Ask with a voice note (multipart: `audio`, `language`, `history` and optional `profile` as JSON) |
| `POST /ask/image` | Diagnose a crop photo (multipart: `image`, optional `question`, `language`, `history`, `profile`); `photo_diagnosis` shows what the vision model saw |
| `GET /weather?place=Delhi&language=en` | Weather with spray and irrigation advice for any place in India |
| `POST /speak` | Turn text into MP3 speech: `{"text": "...", "language": "pa"}` |
| (all answer endpoints) | `sent_for_review` holds the review-queue id when the answer was sent for KVK expert review |
| `GET /health` | Which services are active (index, LLM, speech-to-text, voices) |

`profile` is optional; every field can be left out. Example for a PM-KISAN question:
```bash
curl -X POST http://localhost:8000/ask -H "Content-Type: application/json"   -d '{"query": "Am I eligible for PM-KISAN?", "language": "pa", "profile": {"district": "Sangrur", "crops": ["wheat"], "owns_land": true, "income_tax_payer": false}}'
```

For follow-up questions, send the `turn` object from each `/ask` response back in `history` on the next request:
```bash
curl -X POST http://localhost:8000/ask -H "Content-Type: application/json" \
  -d '{"query": "What is the dose?", "language": "hi", "history": [{"query": "How to control aphids in mustard?", "answer": "...", "intent": "crop_question", "crop": "Mustard", "topic": "Aphid"}]}'
```

---

## 💰 Cost per question

Measured with real token counts (`python scripts/cost_estimate.py`, details in [`docs/cost_estimate.md`](docs/cost_estimate.md)): a typed question costs about **Rs 0.15** with Gemini 3.7 Flash, a voice question about Rs 0.18, and a photo diagnosis about Rs 0.34. Weather, market prices and referrals use no LLM, except one short check when the question states an assumption ("since ...", "I heard ..."). Every kind of question stays well under Rs 1.

## 🤖 AI tools disclosure

See [`AI_DISCLOSURE.md`](AI_DISCLOSURE.md): which AI tools helped build the project, which AI models run inside it, what is rule-based, and which data is AI-generated.

## 📊 Evaluation

The assistant is evaluated in three layers, each answering a different question:

| Layer | Question it answers |
|---|---|
| **1. Real farmer queries** | Does the system work on the questions farmers actually ask? |
| **2. Safety & adversarial tests** | Does it resist wrong assumptions, unsupported problems and unsafe inputs? |
| **3. Automated tests & CI** | Does the implementation stay reproducible and regression-safe? |

All numbers below are copied from the committed reports linked in each section; every report lists its failures too.

### 1. Real-world farmer evaluation: 200 Kisan Call Centre queries

**Evaluated on 200 real Kisan Call Centre queries from Punjab (Jan–Jul 2025), covering English, Hindi, Punjabi and Hinglish** (50 each), chosen by how often farmers asked them, not by whether KisanSahayak can answer them. Report: [`evalset/kcc/results.md`](evalset/kcc/results.md).

| Metric | Result | Scope |
|---|---|---|
| Answer in the requested language (script) | **200/200 (100%)** | all 200 queries |
| Weather answered for the right district | **15/15 (100%)** | weather queries |
| Right advisory in the top 3 | **25/25 (100%)** | queries our own advisories cover |
| Right advisory ranked first | **23/25 (92%)** | queries our own advisories cover |
| PM-KISAN questions recognised | 15/15 (100%) | PM-KISAN queries |
| Price questions answered with the MSP / mandi price | 4/4 (100%) | price queries |
| Banned-pesticide question warned | 1/1 | banned-pesticide queries |
| Answered from the right crop's chapter of PAU's *Package of Practices* | **125/140 (89%)** | queries outside our own advisories |
| … referred to the KVK / Kisan Call Centre instead | 9/140 (6%) | queries outside our own advisories |
| … shown advice on something else | 6/140 (4%) | queries outside our own advisories |

**Held-out check** (85 further real queries, ranked after the 200 and never used for tuning; [`evalset/kcc/heldout_results.md`](evalset/kcc/heldout_results.md)):

| Metric | Result | Scope |
|---|---|---|
| Answered from the right crop's PAU chapter | **55/74 (74%)** | held-out queries outside our own advisories |
| … shown advice on something else | 13/74 (18%) | held-out queries outside our own advisories |
| Right advisory in the top 3 | 4/7 (57%) | held-out queries our own advisories cover |

**Scope, stated plainly:**
- Only 26 of the 200 queries fall inside our own 4-crop advisories (crop and safety advisories); most calls are about weeds, nutrient deficiencies and varieties. The retrieval percentages above apply to that covered subset, not to all farmer questions.
- These are retrieval, routing and language checks, run with offline answers and local MiniLM search. They do not measure agronomic accuracy: answer and dose accuracy need an agronomist. [`evalset/kcc/review_sheet.csv`](evalset/kcc/review_sheet.csv) puts each answer next to the Kisan Call Centre advisor's answer for that review.
- English queries are the exact logged text; the Hindi, Punjabi and Hinglish queries are translations of other real queries (the logs are in English). Source: data.gov.in KCC transcripts via [huggingface.co/datasets/whitesnek/punjab_kcc](https://huggingface.co/datasets/whitesnek/punjab_kcc).

```bash
python evalset/kcc/run_kcc.py      # the 200 queries
python evalset/kcc/heldout.py      # the held-out queries
```

### 2. Safety & adversarial evaluation

**Controlled test set: 67 hand-written questions** in English, Punjabi, Hinglish and Hindi ([`eval/test_set.json`](eval/test_set.json)). It covers all 14 advisory sections (42 questions) plus targeted cases: weather places (8), greetings and off-topic questions (6), banned pesticides (5) and follow-ups (6). Reports: [`eval/results_minilm.md`](eval/results_minilm.md) and [`eval/results_gemini.md`](eval/results_gemini.md).

| Metric | MiniLM search (local) | Gemini search (live app) |
|---|---|---|
| Banned-pesticide questions warned (incl. Hindi/Punjabi script) | **5/5 (100%)** | **5/5 (100%)** |
| False banned-pesticide warnings | 0 of 39 | 0 of 39 |
| Follow-up questions kept context | 6/6 (100%) | 6/6 (100%) |
| Greetings / off-topic handled | 6/6 (100%) | 6/6 (100%) |
| Weather: right place detected | 8/8 (100%) | 8/8 (100%) |
| Right advisory in top 3 | 41/42 (98%) | **42/42 (100%)** |
| Right advisory ranked 1st | 35/42 (83%) | **41/42 (98%)** |
| Question type recognised | 41/42 (98%) | 41/42 (98%) |

These questions were written by the team, not collected from farmers.

**Real Gemini answers, number check** ([`eval/results_llm.md`](eval/results_llm.md)): every Gemini answer is checked before it is shown. Each amount ("400 g") must appear in the sources with the same unit, and every other number must appear in them; otherwise the checked advisory text is shown instead. On 24 real Gemini answers:
- 24/24 were in the requested script;
- 1 was replaced: Gemini wrote "40 ml" where PAU says "40 g Actara";
- so 24/24 answers shown contained only source numbers.

**Adversarial and failure cases covered by the automated tests**:

| Failure mode | What is checked | Tests |
|---|---|---|
| False premises | A wrong figure in the question (₹12,000/month PM-KISAN, 100 g Actara, a false MSP, "it will rain") is corrected from the source. A worded assumption ("Since MSP guarantees the government will buy all my wheat…") is corrected with the cited official text. Correct premises are left alone. The badge never says plain "Verified" after a correction. | [`test_false_premise.py`](tests/test_false_premise.py) (16), [`test_worded_premises.py`](tests/test_worded_premises.py) (15) |
| Unsupported / fake diseases | A disease the knowledge base never mentions ("golden blight") gets no treatment or dose. Synonyms and spellings it does know are not refused. | `test_false_premise.py`, `test_worded_premises.py` |
| Pesticide safety & banned chemicals | CIBRC banned-chemical scan in Latin, Devanagari and Gurmukhi script; spray disclaimers; no dose for a product the evidence does not recommend | [`test_guardrails.py`](tests/test_guardrails.py), [`test_router.py`](tests/test_router.py), `test_false_premise.py` |
| Cross-crop contamination | Uncovered crops and topics are referred, not answered with another crop's advisory; PAU answers come from the asked crop's chapter | `test_router.py`, [`test_pau.py`](tests/test_pau.py) |
| Missing evidence | The LLM's "not found" marker makes the answer *not verified*. Unbacked numbers are replaced. A declined scheme answer falls back to official text. | `test_false_premise.py`, [`test_numbers_check.py`](tests/test_numbers_check.py) |
| Follow-ups / context retention | Crop, pest and place carried across turns, topic switches, "spray again?" asks which crop | [`test_conversation.py`](tests/test_conversation.py) |
| Weather / market / tool failures | Unknown place reported (not silently replaced), mandi API offline, missing PAU index, missing speech keys, failed photo diagnosis | [`test_location.py`](tests/test_location.py), [`test_market.py`](tests/test_market.py), `test_pau.py`, [`test_speech.py`](tests/test_speech.py), [`test_vision.py`](tests/test_vision.py) |

```bash
python scripts/evaluate.py                      # offline, uses EMBEDDING_PROVIDER from .env
python scripts/evaluate.py --embeddings gemini  # the live app's search
python scripts/evaluate.py --llm 8              # also check 8 real Gemini answers (uses quota)
```

### 3. Automated testing & reliability

- **414 automated tests** (`pytest`) run on every push and pull request in GitHub Actions ([`.github/workflows/tests.yml`](.github/workflows/tests.yml)). They need no API keys: the tests force the offline answer template and local embeddings, so results are repeatable.
- **End-to-end feature scenarios** ([`evalset/results.md`](evalset/results.md)): 28 cases covering whole conversations in all four languages, the farm profile, PM-KISAN eligibility, crop insurance, Kisan Credit Card, weather, guardrails, photo and voice. The 25 automated cases pass **24/25** (38/39 conversation turns). The one failure is a Hindi symptoms-only bacterial blight question that local MiniLM search ranks under brown planthopper. Photo and voice (3 cases) are checked by hand.
- **PAU *Package of Practices* answers** ([`evalset/pau/results.md`](evalset/pau/results.md)): on 28 team-written questions outside our own advisories, 28/28 were answered from the right crop's chapter and the expected section was in the top 3 for 28/28.
- **Cold start**: Streamlit Cloud used to re-embed ~400 PAU chunks against the free Gemini quota, about 13 minutes. A shipped Gemini embedding cache ([`scripts/build_embedding_cache.py`](scripts/build_embedding_cache.py)) brought this to about 15 seconds. Both were observed on the deployed app, not measured with a benchmark script.

```bash
pytest -q                          # 414 tests
python evalset/run_evalset.py      # end-to-end feature scenarios
python evalset/pau/run_pau.py      # PAU answers
```

## 🐳 Running with Docker

The `Dockerfile` installs CPU-only PyTorch, pre-downloads the MiniLM model, builds the search index, and starts the Streamlit app. API keys are passed at run time, never baked into the image:
```bash
docker build -t kisansahayak .
docker run -p 8501:8501 -e GEMINI_API_KEY=your_key -e GROQ_API_KEY=your_key kisansahayak
```
Then open http://localhost:8501. The first visit after start-up loads the models (about a minute).

---

## ☁️ Deploying on Streamlit Community Cloud (free)

The cloud version uses `frontend/requirements.txt` (no PyTorch, so it fits the memory limit) and **Gemini embeddings** for search instead of the local MiniLM model. On the 67-question test set, Gemini embeddings rank the right advisory first for 41/42 questions (MiniLM: 35/42; see [Evaluation](#-evaluation)).

1. Sign in at https://share.streamlit.io with GitHub and click **Create app → Deploy a public app from GitHub**.
2. Repository `KanishkaSingh19/KisanSahayak`, branch `main`, main file path **`frontend/app.py`**.
3. Open **Advanced settings**, choose Python **3.12**, and paste into **Secrets**:
   ```toml
   GEMINI_API_KEY = "your_gemini_key"
   GROQ_API_KEY = "your_groq_key"
   LLM_PROVIDER = "gemini"
   EMBEDDING_PROVIDER = "gemini"
   ```
4. Click **Deploy**. The first start installs packages, downloads PAU's *Package of Practices* and builds the search index; the shipped Gemini vector cache means no chunks need re-embedding.

**After each push to `main`, reboot the app** (share.streamlit.io → ⋮ next to the app → **Reboot app**). The app turns Streamlit's file watcher off (`.streamlit/config.toml`, which keeps local runs with MiniLM fast), so a running app keeps its old code until it restarts. Apps sleep after a period without visitors; open the link before a demo so it's awake.
