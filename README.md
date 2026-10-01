# 🌾 KisanSahayak (किसान सहायक) 

> **Voice-first Multilingual AI Farming Assistant for Indian Farmers**  
> *Grounded agricultural RAG (FAISS + BM25 + Reciprocal Rank Fusion) with voice input/output and live ag-weather spray advisories*

[![tests](https://github.com/KanishkaSingh19/KisanSahayak/actions/workflows/tests.yml/badge.svg)](https://github.com/KanishkaSingh19/KisanSahayak/actions/workflows/tests.yml)

### 🚀 Live app: **https://kisansahayak1.streamlit.app/**
*(Free hosting sleeps when idle: if you see a "wake up" screen, click it and allow about a minute to start.)*

Farmers ask about crops, pests, pesticides or weather in Hindi, Punjabi, Hinglish or English — by text or voice note. Answers are grounded strictly in curated ICAR, PAU Ludhiana and CIBRC advisories, with citations, banned-chemical checks and spray disclaimers.

---

## ✨ Features

- **Crop & pest advisories** for wheat, mustard, paddy and cotton (yellow rust, karnal bunt, aphid, white rust, BLB, BPH, pink bollworm, whitefly), with multilingual aliases (e.g. *sarson* / सरसों / ਸਰ੍ਹੋਂ).
- **Grounded answers only** — responses come from `data/raw/` advisories and list their sources; if nothing relevant is found, the farmer is referred to their local KVK.
- **Pesticide safety guardrails** — CIBRC banned-chemical scan (Monocrotophos, Endosulfan, DDT, Phorate, Paraquat, …) and a statutory disclaimer on any spray/dosage answer.
- **Ag-weather & spray window** — live [Open-Meteo](https://open-meteo.com/) data for 15 districts (Punjab, Haryana, UP, MP, Rajasthan, Bihar) with spray and irrigation advice; falls back to seasonal defaults when offline.
- **System status sidebar** — shows which LLM and speech-to-text services are actually active.
- **Voice input** — spoken questions are transcribed with Whisper Large v3 via Groq (Gemini audio for Punjabi, and as a backup); the API's `/ask/voice` also accepts voice-note files (WAV/MP3/M4A/OGG).
- **Voice output** — tap Listen to hear the answer: English, Hindi and Hinglish via Edge-TTS, Punjabi via gTTS (Edge-TTS has no Punjabi voice).
- **Real-time voice** — tap **Voice** inside the chat box, record your question, and it is sent when you stop; answers to spoken questions are read aloud.
- **Photo diagnosis** — tap **Photo** inside the chat box and choose **Upload a photo** (from the device) or **Take a photo** (phone or laptop camera); the photo is sent as soon as it is chosen or taken. Gemini Vision names the likely disease or pest and its confidence, and the treatment comes only from the verified advisories. Unclear photos, healthy plants and crops the advisories don't cover get no treatment, and every photo answer carries an "AI estimate, confirm with your KVK" note.
- **PM-KISAN guidance** — benefit, eligibility, exclusions, how to apply, eKYC, status checks and why an instalment can be held, from the official site ([pmkisan.gov.in](https://pmkisan.gov.in), checked 30 Sep 2026) in all four languages. Eligibility is decided by fixed rules from the farm profile, never by the LLM, and every answer says to confirm on the official portal.
- **Crop insurance (PMFBY) and Kisan Credit Card guidance** — premiums, what is covered, who can enrol, how to enrol and claim (72 hours, helpline 14447); KCC interest (7%, 4% with timely repayment), loan limit, collateral-free limit, who can get one and how to apply. Written from official sources (PMFBY operational guidelines, PIB releases of 2025-26, checked 1 Oct 2026) in all four languages. Crop insurance answers always say that **Punjab has not implemented PMFBY**. Other schemes (Soil Health Card, PM-KISAN Maandhan, PM-KUSUM, PMKSY) are recognised by name and referred to their official website instead of being answered with another scheme's rules.
- **My farm profile (optional)** — district, crops, land and a few yes/no PM-KISAN questions. Used for the local weather when no place is named, for the crop when a question names none (if only one covered crop is listed), and for eligibility. Nothing is stored: it lasts only for the browser session and asks for no name, phone or Aadhaar.
- **Language switch** — English (default), Punjabi, Hinglish or Hindi for the UI, the answer, warnings and voice.
- **Gemini fallback chain** — a busy main model hands over to a backup model, then to the offline template with a visible note.
- **Market prices** — asks like "MSP of wheat" or "sarson ka bhav Sangrur mandi" get the government Minimum Support Price (Kharif 2026-27 and Rabi 2026-27, with the previous season; `data/market/msp.json`, source and date shown) plus the latest mandi prices: per-mandi prices from data.gov.in, or, if that is down, the daily average from Agmarknet 2.0 (agmarknet.gov.in; district first, otherwise the state, and the answer says which). The app identifies itself as KisanSahayak in these requests. If both are unreachable, the answer says so and points to agmarknet.gov.in, eNAM and the Kisan Call Centre; a price is never guessed. Uses the farmer's district and crop from the profile.
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
| Speech-to-text | Groq-hosted `whisper-large-v3` | `GROQ_API_KEY` | Voice tab asks the farmer to type instead |
| Photo diagnosis | Gemini Vision (same main/backup models) identifies crop, likely problem and confidence; never gives treatment | `GEMINI_API_KEY` | "Couldn't analyse the photo" message |
| Text-to-speech | Microsoft Edge-TTS (`en-IN-NeerjaNeural`, `hi-IN-MadhurNeural`); gTTS for Punjabi, since Edge-TTS has no Punjabi voice | `edge-tts` and `gTTS` packages + internet, no key | Text-only answer |
| Dense embeddings | Hugging Face `paraphrase-multilingual-MiniLM-L12-v2` (384-dim, runs locally) | `EMBEDDING_PROVIDER=minilm` + `sentence-transformers` (one-time ~470 MB model download) | Local embedder |
| | Gemini `gemini-embedding-001` (768-dim) | `EMBEDDING_PROVIDER=gemini` + `GEMINI_API_KEY` | Local embedder |
| | Local hashed word + character n-gram vectors (256-dim) | Nothing (default, `EMBEDDING_PROVIDER=local`) | — |
| Intent routing | Rule-based multilingual keyword lexicons (no model) | — | — |

> **Note:** `LLM_PROVIDER` defaults to `mock` in `app/config.py`. With no `.env` file, no LLM is called and answers come from the deterministic template.

---

## 🚀 Architecture

```
Farmer Query (Text or Voice Note)
   │
   ├── Voice ──► [Groq Whisper STT] (app/speech/stt.py) ──► transcript
   │
   ▼
[Language Detection + Intent & Entity Extraction] (app/agent/router.py)
   │   crop · pest/disease · district
   │
   ├── Greeting / Out-of-Scope ────► Polite Redirection / Scope Advisory
   ├── Weather ────────────────────► [Open-Meteo Ag-Weather Tool] (app/tools/weather_tool.py)
   │                                   spray window + irrigation advice
   ▼ Crop / Safety / General Agriculture
[Hybrid Agricultural RAG] (app/rag/hybrid_retriever.py)
   ├── Dense Semantic Search (FAISS / app/rag/faiss_retriever.py)
   ├── Sparse Keyword Search (BM25Okapi / app/rag/bm25_retriever.py)
   └── Reciprocal Rank Fusion (k=60 / app/rag/rrf.py)
   │
   ▼
[Grounded Answer Synthesizer] (app/agent/synthesizer.py)
   │   Gemini / OpenAI / Deterministic
   ▼
[Safety Guardrails & Grounding Validator] (app/agent/guardrails.py)
   ├── Banned Chemical Scan (CIBRC Schedule)
   ├── Grounding & Overlap Verification
   └── Statutory Spray Disclaimers
   │
   ▼
[Structured Response with ICAR/PAU Citations] ──► [Edge-TTS Audio] (app/speech/tts.py)
```

Orchestrated end-to-end by `app/agent/pipeline.py` (`KisanPipeline`).

**Chunking** (`app/rag/chunker.py`): each advisory section (one crop, one disease or pest) becomes one chunk, so topics are never mixed. Sections longer than `CHUNK_SIZE` (1000 characters) are split at sentence boundaries. Each piece repeats the crop, topic and source in a header and starts with up to `CHUNK_OVERLAP` (150) characters from the end of the previous piece: whole sentences when they fit, otherwise the last words. 14 sections give 22 chunks. A saved index is rebuilt automatically when the advisories or chunk settings change.

**Ranking by section** (`app/rag/hybrid_retriever.py`): dense and BM25 results are each reduced to the best chunk per advisory section before Reciprocal Rank Fusion, so a long section split into several chunks cannot fill every slot. The top 3 sections are returned, followed by their other matching chunks so the LLM sees the whole advisory.

**PAU's full chapters** (`app/rag/pau_kb.py`): topics our 14 advisories don't cover, for wheat, mustard, paddy and cotton (weeds, varieties, nutrients, other pests, nursery, harvest…), are answered from PAU's *Package of Practices* chapters, searched only for that crop, with PAU's page numbers. PAU's text is copyrighted, so it is not in the repository: `python scripts/build_pau_kb.py` downloads the two books from pau.edu and extracts the chapters (git-ignored), and the app does this on its first start (`PAU_AUTO_BUILD`). Without them the app works as before and refers those questions to the KVK. See [`evalset/pau/README.md`](evalset/pau/README.md).

**Advisory sources:** the crop advisories follow PAU's *Package of Practices for Crops of Punjab* (Rabi 2025-26 and Kharif 2026). Each section records the printed pages it comes from (`source_reference`), and citations show them, e.g. "PAU Package of Practices for Crops of Punjab, Rabi 2025-26, pages 18-21".

---

## 📂 Repository Structure

```
KisanSahayak/
├── app/
│   ├── config.py                 # Pydantic Settings & environment config
│   ├── agent/
│   │   ├── state.py              # Pydantic schemas for query, intent & response
│   │   ├── router.py             # Intent classification & crop/pest/district extraction
│   │   ├── synthesizer.py        # Grounded response generator (Gemini/OpenAI/Deterministic)
│   │   ├── guardrails.py         # CIBRC banned chemical filter & grounding checks
│   │   └── pipeline.py           # End-to-end pipeline orchestrator (text + voice)
│   ├── rag/
│   │   ├── chunker.py            # Structured agricultural chunking with metadata
│   │   ├── embeddings.py         # Local hashed n-gram / MiniLM / Gemini dense embeddings
│   │   ├── faiss_retriever.py    # FAISS dense index with cosine ranking
│   │   ├── bm25_retriever.py     # BM25Okapi sparse keyword index
│   │   ├── rrf.py                # Reciprocal Rank Fusion algorithm
│   │   ├── hybrid_retriever.py   # Hybrid FAISS + BM25 + RRF coordinator
│   │   └── ingest.py             # Ingestion CLI for raw advisory docs
│   ├── speech/
│   │   ├── stt.py                # Groq Whisper speech-to-text adapter
│   │   └── tts.py                # Edge-TTS Hindi/Punjabi speech synthesis
│   └── tools/
│       ├── weather_tool.py       # Open-Meteo ag-weather & spray window advisory
│       ├── location.py           # Place-name lookup (any place in India)
│       ├── vision.py             # Gemini Vision crop-photo diagnosis
│       └── schemes.py            # Scheme guidance (PM-KISAN, PMFBY, KCC), PM-KISAN eligibility rules
├── data/
│   ├── raw/                      # Crop advisories from PAU's Package of Practices (with page numbers) & CIBRC safety (JSON)
│   │   ├── wheat_pau_icar.json
│   │   ├── mustard_crop_guide.json
│   │   ├── paddy_rice_management.json
│   │   ├── cotton_pest_control.json
│   │   └── pesticide_safety_cibrc.json
│   ├── schemes/                  # PM-KISAN, PMFBY crop insurance, Kisan Credit Card (official sources, 4 languages)
│   ├── indices/                  # Serialized FAISS & BM25 indices
│   └── audio/                    # Generated TTS audio files
├── frontend/
│   └── app.py                    # Streamlit chat UI (4 languages, voice, weather card)
├── app/api.py                    # FastAPI REST API over the same pipeline (/ask, /weather, /speak)
├── tests/                        # pytest suite (RAG, router, guardrails, pipeline, speech, weather)
├── run_verification.py           # Runs benchmark example queries through the pipeline
├── .env.example
├── requirements.txt
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
| `GEMINI_API_KEY` / `GEMINI_MODEL` | Gemini answer generation (and optional embeddings) |
| `OPENAI_API_KEY` / `OPENAI_MODEL` | OpenAI answer generation |
| `GROQ_API_KEY` | Voice input (Whisper STT) |
| `ENABLE_TTS` | Spoken answers (default `True`) |
| `EMBEDDING_PROVIDER` | `local` (default), `minilm`, or `gemini` |
| `HF_CACHE_DIR` | Folder for the MiniLM model download (empty = Hugging Face default cache) |

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

### 5. Run Benchmark Queries
```bash
python run_verification.py
```

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

Measured with real token counts (`python scripts/cost_estimate.py`, details in [`docs/cost_estimate.md`](docs/cost_estimate.md)): a typed question costs about **Rs 0.15** with Gemini 3.7 Flash, a voice question about Rs 0.18, and a photo diagnosis about Rs 0.34. Weather, market prices and referrals use no LLM. Every kind of question stays well under Rs 1.

## 🤖 AI tools disclosure

See [`AI_DISCLOSURE.md`](AI_DISCLOSURE.md): which AI tools helped build the project, which AI models run inside it, what is rule-based, and which data is AI-generated.

## 📊 Evaluation

`scripts/evaluate.py` scores the assistant on **67 hand-written test questions** in English, Punjabi, Hinglish and Hindi (`eval/test_set.json`), covering all 14 advisory sections, weather, greetings/off-topic, banned pesticides and follow-up questions. The core checks don't call the LLM, so they are repeatable and use no API quota.

| Metric | MiniLM search (local) | Gemini search (live app) |
|---|---|---|
| Right advisory ranked 1st | 83% (35/42) | **98% (41/42)** |
| Right advisory in top 3 | 98% (41/42) | **100% (42/42)** |
| Question type recognised | 98% (41/42) | 98% (41/42) |
| Weather: right place detected | 100% (8/8) | 100% (8/8) |
| Greetings / off-topic handled | 100% (6/6) | 100% (6/6) |
| Banned-pesticide questions warned (incl. Hindi/Punjabi script) | **100% (5/5)** | **100% (5/5)** |
| False banned-pesticide warnings | 0 of 39 | 0 of 39 |
| Follow-up questions kept context | 100% (6/6) | 100% (6/6) |
| Search + safety time, without LLM (median) | ~43 ms | ~0.6 s |

On 8 real Gemini answers: **8/8** written by Gemini, **8/8** in the requested script, **8/8** with no numbers (doses, dates) that aren't in the source advisories; median 3.3 s.

```bash
python scripts/evaluate.py                      # offline, uses EMBEDDING_PROVIDER from .env
python scripts/evaluate.py --embeddings gemini  # the live app's search
python scripts/evaluate.py --llm 8              # also check 8 real Gemini answers (uses quota)
```
Full reports, including every failure: `eval/results_minilm.md`, `eval/results_gemini.md`; the real Gemini answer check (with the full answers) is in `eval/results_llm.md` and `eval/results_llm.json`. The test questions were written by the team, not collected from farmers; a field test set is future work.

---

### Real farmer questions: Kisan Call Centre (200 questions)

[`evalset/kcc/`](evalset/kcc/) tests the assistant on **200 real farmer queries from Punjab Kisan Call Centre logs** (Jan–Jul 2025), 50 each in English, Hindi, Punjabi and Hinglish, chosen by how often farmers asked them.

| Metric | Result |
|---|---|
| Right advisory in top 3 (questions our advisories cover) | 23/25 (92%) |
| Banned-pesticide question warned | 1/1 |
| Weather for the right district / PM-KISAN recognised | 15/15 / 15/15 |
| Price (MSP) questions answered with the price | 4/4 |
| Answer in the requested language | 200/200 (100%) |
| Questions outside our advisories answered from the right crop's chapter of PAU's *Package of Practices* | **126/140 (90%)**; 55/74 (74%) on held-out queries not used for tuning |
| … referred to the Kisan Call Centre / KVK / shown advice on something else | 8/140 / 6/140 (held-out: 6/74 / 13/74) |

Only 26 of the 200 real questions fall within our 4-crop advisories: most calls are about weeds, nutrient deficiencies and varieties. For the four covered crops, those are now answered from PAU's *Package of Practices* chapter for that crop, citing PAU's pages ([`evalset/pau/`](evalset/pau/): on 28 questions written for it, 28/28 answered from PAU and the expected section in the top 3 for all; 23/28 before adding words that first run missed). Other crops and questions that name no crop are referred to the Kisan Call Centre (1800-180-1551). Answer and dose accuracy still need an agronomist: `evalset/kcc/review_sheet.csv` puts each answer next to the KCC advisor's answer for review.

### Feature test set (28 questions)

[`evalset/`](evalset/) checks every feature end to end: whole conversations with follow-ups, all four languages, the farm profile, PM-KISAN eligibility, crop insurance and Kisan Credit Card answers, weather, safety guardrails, the "crop not covered" guard, photo and voice. Cases 1–22 and 26–28 run automatically: **24/25 pass** (38/39 conversation turns) with offline answers; the miss is a Hindi symptom-only bacterial blight question ranked under brown planthopper by the local MiniLM search. The earlier run with real Gemini answers ([`evalset/results_llm.md`](evalset/results_llm.md), 22/22) predates the PAU update; photo and voice (23–25) are checked by hand.

```bash
python evalset/run_evalset.py
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

The cloud version uses `frontend/requirements.txt` (no PyTorch, so it fits the memory limit) and **Gemini embeddings** for search instead of the local MiniLM model. In our 8-question check, Gemini embeddings put the right crop first for 8/8 questions (MiniLM: 6/8).

1. Sign in at https://share.streamlit.io with GitHub and click **Create app → Deploy a public app from GitHub**.
2. Repository `KanishkaSingh19/KisanSahayak`, branch `main`, main file path **`frontend/app.py`**.
3. Open **Advanced settings**, choose Python **3.12**, and paste into **Secrets**:
   ```toml
   GEMINI_API_KEY = "your_gemini_key"
   GROQ_API_KEY = "your_groq_key"
   LLM_PROVIDER = "gemini"
   EMBEDDING_PROVIDER = "gemini"
   ```
4. Click **Deploy**. The first start installs packages and builds the search index (a few minutes).

**After each push to `main`, reboot the app** (share.streamlit.io → ⋮ next to the app → **Reboot app**). The app turns Streamlit's file watcher off (`.streamlit/config.toml`, which keeps local runs with MiniLM fast), so a running app keeps its old code until it restarts. Apps sleep after a period without visitors; open the link before a demo so it's awake.
