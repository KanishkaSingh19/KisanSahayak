# 🌾 KisanSahayak (किसान सहायक)

> **A multilingual, voice-first AI farming assistant for Punjab farmers: verified crop advice, weather, prices and government schemes in English, Hindi, Punjabi and Hinglish.**

[![tests](https://github.com/KanishkaSingh19/KisanSahayak/actions/workflows/tests.yml/badge.svg)](https://github.com/KanishkaSingh19/KisanSahayak/actions/workflows/tests.yml)

### 🚀 Live app: **https://kisansahayak1.streamlit.app/**
*(Free hosting sleeps when idle: if you see a "wake up" screen, click it and allow about a minute to start.)*

**Contents:** [💡 Project overview](#-project-overview) · [🛠️ Technologies used](#️-technologies-used) · [⚙️ Setup & installation](#️-setup--installation) · [🚀 How to run](#-how-to-run) · [📊 Evaluation](#-evaluation) · [📂 Repository structure](#-repository-structure)

---

## 💡 Project overview

### The problem
Farmers in Punjab call the Kisan Call Centre with tens of thousands of questions: **80,613 calls in January–July 2025 alone** ([`evalset/kcc/README.md`](evalset/kcc/README.md)). They ask about pests, weeds, fertilizer, weather, prices and schemes, in Punjabi, Hindi, Hinglish or English. Generic chatbots answer confidently but can invent doses, recommend banned pesticides or accept a wrong assumption ("PM-KISAN pays ₹12,000 a month").

### Our solution
KisanSahayak answers in the farmer's language, by **text, voice note or crop photo**, from verified sources only: PAU Ludhiana's *Package of Practices*, ICAR and CIBRC advisories, live weather, government MSP and mandi prices, and official scheme texts. Every answer shows its sources. **The AI explains; data and code decide the facts.**

### Key features
- **Crop & pest advice** for wheat, mustard, paddy and cotton.
  - Our checked advisories cover the main pests and diseases (yellow rust, Karnal bunt, aphid, white rust, BLB, BPH, sheath blight, pink bollworm, whitefly) plus sowing, fertilizer and irrigation, each citing PAU's page numbers.
  - Other topics for these crops (weeds, varieties, nutrients, other pests) are answered from PAU's *Package of Practices* chapter for that crop.
  - Other crops are referred to the KVK and the Kisan Call Centre (1800-180-1551), never answered with another crop's advice.
- **One chat box for text, voice and photo.**
  - Voice is transcribed by Whisper (Gemini audio for Punjabi).
  - Answers can be read aloud (Edge-TTS; gTTS for Punjabi).
  - **Photo diagnosis**: Gemini Vision names the likely problem; the treatment comes only from the verified advisories, labelled as an AI estimate.
- **Four languages:** English, Hindi, Punjabi (Gurmukhi) and Hinglish, for the UI, answers, warnings and voice.
- **Weather & spray window:** live Open-Meteo weather for any place in India, with spray and irrigation advice when asked.
- **Market prices:**
  - the government MSP;
  - the latest mandi prices from data.gov.in or Agmarknet.
  - If the live sources are unreachable the answer says so; a price is never guessed.
- **Government schemes:**
  - **Covered:** PM-KISAN (with rule-based eligibility from the farm profile), PMFBY crop insurance and the Kisan Credit Card, all from official sources in four languages.
  - **Other schemes** are referred to their official websites.
- **Farm profile (optional):** district, crops and land size.
  - Used for local weather and per-acre dose totals calculated in code.
  - Nothing is stored beyond the browser session; no name, phone or Aadhaar is asked.
- **Multi-turn conversation:** follow-ups like "What is the dose?" or "And in Sangrur?" keep the crop, pest and place.

### Built for trust
- **Every number is verified.** Each dose, price or amount in an AI answer must appear in the sources with the same unit; otherwise the checked source text is shown instead.
- **Wrong assumptions are corrected.**
  - "Since PM-KISAN gives ₹12,000 per month…" or "Since MSP guarantees the government will buy all my wheat…" gets a **Small correction** quoting the official source, then the answer to the rest of the question.
  - Corrected answers show the badge "Verified · premise corrected", never plain "Verified".
- **Pesticide safety:** CIBRC banned-chemical scan (in Latin, Devanagari and Gurmukhi script) and a statutory disclaimer on every spray or dose answer.
- **No invented treatments:** a disease the sources don't mention ("golden blight") gets no dose.
- **KVK expert review:** risky or uncertain answers go to a review queue, where experts mark them correct, needs correction or unsafe (`frontend/pages/1_KVK_expert_review.py`).
- **Always available:** if Gemini is busy, a backup model answers; if both fail, an offline template answers from the same verified text.

### Results at a glance
**Evaluated on 200 real Kisan Call Centre queries from Punjab (Jan–Jul 2025)**, 50 each in English, Hindi, Punjabi and Hinglish:

| Result | Scope |
|---|---|
| **200/200 (100%)** answered in the requested language | all 200 queries |
| **15/15 (100%)** weather for the right district | weather queries |
| **25/25 (100%)** right advisory in the top 3 (23/25 ranked first) | queries our own advisories cover |
| **125/140 (89%)** answered from the right crop's PAU chapter | queries outside our own advisories |
| **55/74 (74%)** answered from the right crop's PAU chapter | held-out queries never used for tuning |

Backed by safety and adversarial tests and **414 automated tests** in CI. Full details, scope and failures: [📊 Evaluation](#-evaluation).

### Architecture
```
Farmer message: text, voice note and/or photo (one chat box)
   │
   ├── Voice ──► Whisper STT via Groq; Gemini audio for Punjabi (app/speech/stt.py)
   ├── Photo ──► Gemini Vision: likely problem + confidence (app/tools/vision.py)
   ▼
Router: language, intent, crop, pest, place, scheme, follow-ups (rule-based, app/agent/router.py)
   │
   ├── Greeting / off-topic / crop not covered ──► polite redirect or KVK / Kisan Call Centre referral
   ├── Weather ──► Open-Meteo live weather + spray / irrigation advice (app/tools/weather_tool.py)
   ├── Prices ───► MSP table + data.gov.in / Agmarknet mandi prices (app/tools/market.py)
   ├── Schemes ──► PM-KISAN, PMFBY, KCC official texts + eligibility rules (app/tools/schemes.py)
   ▼ Crop / pest / safety questions
Hybrid RAG (app/rag/hybrid_retriever.py)
   ├── FAISS meaning search + BM25 keyword search, fused with Reciprocal Rank Fusion
   ├── Corrective retry in English terms when the two searches disagree (app/agent/pipeline.py)
   └── Our advisories, or PAU's Package of Practices chapter for the crop (app/rag/pau_kb.py)
   ▼
Answer: Gemini (main → backup model) or offline template (app/agent/synthesizer.py)
   ▼
Checks on every answer
   ├── Numbers must be in the sources (app/agent/guardrails.py); per-acre totals in code (app/tools/dose.py)
   ├── Claims in the question: figures in code (app/agent/claims.py), worded premises (app/agent/premises.py)
   ├── Banned-pesticide scan + spray disclaimers (app/agent/guardrails.py)
   └── Evidence / source / KVK review status (app/review.py)
   ▼
Answer with citations and status badges ──► spoken audio (app/speech/tts.py)
```
Orchestrated end to end by `app/agent/pipeline.py` (`KisanPipeline`). The same pipeline is also exposed as an optional FastAPI REST API (`app/api.py`) for future channels (mobile app, WhatsApp, IVR); the Streamlit app calls the pipeline directly.

---

## 🛠️ Technologies used

| Area | Technology |
|---|---|
| **Language & core** | Python 3.12, Pydantic, pydantic-settings |
| **Web interface** | Streamlit (chat UI, KVK review page) |
| **LLM** | Google Gemini 3.7 Flash, Gemini Flash-Lite as backup (`google-genai` SDK); OpenAI `gpt-4o-mini` optional |
| **Photo diagnosis** | Gemini Vision |
| **Speech-to-text** | Whisper Large v3 via Groq; Gemini audio for Punjabi and as backup |
| **Text-to-speech** | Microsoft Edge-TTS (English, Hindi, Hinglish); gTTS (Punjabi) |
| **Embeddings** | Gemini `gemini-embedding-001` (live app, with a shipped vector cache); multilingual MiniLM-L12-v2 (local); hashed n-grams (offline default) |
| **Retrieval** | FAISS (vector search), rank-bm25 (keyword search), Reciprocal Rank Fusion, corrective retry |
| **Document processing** | PyMuPDF (reads PAU's *Package of Practices* PDFs) |
| **Live data** | Open-Meteo (weather, place search), data.gov.in and Agmarknet (mandi prices) |
| **Knowledge sources** | PAU *Package of Practices for Crops of Punjab*, ICAR, CIBRC banned-pesticide list, PM-KISAN / PMFBY / KCC official texts, Government MSP decisions, PIB |
| **REST API (optional)** | FastAPI, Uvicorn |
| **Testing & CI** | pytest (414 tests), GitHub Actions |
| **Deployment** | Streamlit Community Cloud; Dockerfile for self-hosting |

Rule-based, not AI: question routing, the banned-pesticide filter, PM-KISAN eligibility, weather advice, prices, per-acre dose totals and choosing answers for KVK review. See [`AI_DISCLOSURE.md`](AI_DISCLOSURE.md) for which AI tools built the project and which run inside it.

---

## ⚙️ Setup & installation

### Prerequisites
- **Python 3.12** and Git
- Optional API keys (the app runs without them, using the offline template):
  - a **Gemini** key ([aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)) for AI answers, photo diagnosis and premise checks;
  - a **Groq** key ([console.groq.com/keys](https://console.groq.com/keys)) for voice input.

### 1. Clone the repository
```bash
git clone https://github.com/KanishkaSingh19/KisanSahayak.git
cd KisanSahayak
```

### 2. Create a virtual environment and install dependencies
```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```
`requirements.txt` includes the local MiniLM search model (PyTorch, about 470 MB on first use). For a lighter install without it, use `pip install -r frontend/requirements.txt`, which is the Streamlit Cloud set, and use Gemini or local embeddings.

### 3. Configure (optional)
Copy `.env.example` to `.env` and fill in the keys for the features you want:
```bash
cp .env.example .env             # Windows: copy .env.example .env
```

| Variable | Purpose |
|---|---|
| `LLM_PROVIDER` | `gemini`, `openai`, or `mock` (default in code: no LLM, offline template) |
| `GEMINI_API_KEY` / `GEMINI_MODEL` | Gemini answers, photo diagnosis, premise checks, embeddings (default model `gemini-3.7-flash`) |
| `GEMINI_FALLBACK_MODEL` | Backup model when the main one is busy (default `gemini-flash-lite-latest`) |
| `GROQ_API_KEY` | Voice input (Whisper speech-to-text) |
| `EMBEDDING_PROVIDER` | `local` (default), `minilm`, or `gemini` (used by the live app) |
| `USE_PAU_KB` / `PAU_AUTO_BUILD` | Search PAU's *Package of Practices* chapters / build them on first start (both default `True`) |
| `DATA_GOV_API_KEY` | Live mandi prices from data.gov.in (the public sample key is used if empty) |
| `REVIEW_PASSCODE` / `REVIEW_QUEUE_PATH` | Passcode for the KVK expert review page / where the queue file is kept |
| `ENABLE_TTS`, `HF_CACHE_DIR`, `OPENAI_API_KEY` / `OPENAI_MODEL` | Spoken answers (default on), MiniLM download folder, optional OpenAI answers |

Never commit `.env`: it is git-ignored.

### 4. Build the knowledge base (optional: done automatically on first run)
```bash
python -m app.rag.ingest         # FAISS + BM25 indices from data/raw/
python scripts/build_pau_kb.py   # downloads PAU's Package of Practices PDFs and extracts the chapters
```
PAU's text is copyrighted, so it is not in the repository. The script downloads it from pau.edu into a git-ignored folder, and the app does this on its first start. Without it, the app still runs and refers those topics to the KVK.

---

## 🚀 How to run

### Option A: use the live app (no setup)
Open **https://kisansahayak1.streamlit.app/**, pick a language, and try:
- *"How do I control aphids in mustard?"*, then the follow-up *"What is the dose?"*
- *"ਕਣਕ ਵਿੱਚ ਪੀਲੀ ਕੁੰਗੀ ਦਾ ਇਲਾਜ ਕੀ ਹੈ?"* (yellow rust in wheat, Punjabi)
- *"Weather in Ludhiana, can I spray today?"*
- *"What is the MSP of wheat?"*
- *"Since PM-KISAN gives ₹12,000 per month, how do I register?"* (watch the correction)
- *"Can I use endosulfan on cotton?"* (banned-pesticide warning)
- Attach a crop photo from [`data/sample_photos/`](data/sample_photos/) with the **+** button.

### Option B: run the Streamlit app locally
```bash
streamlit run frontend/app.py
```
Then open http://localhost:8501. Use `streamlit run`, not `python -m streamlit run`: the latter fails with `No module named 'app.agent'` because `frontend/app.py` shadows the `app` package.

### Option C: run with Docker
```bash
docker build -t kisansahayak .
docker run -p 8501:8501 -e GEMINI_API_KEY=your_key -e GROQ_API_KEY=your_key kisansahayak
```
Then open http://localhost:8501. API keys are passed at run time, never baked into the image.

### Run the tests
```bash
pytest -q
```
414 tests, with no API keys needed; they also run on every push in GitHub Actions (`.github/workflows/tests.yml`).

### Try example queries from the command line
```bash
python run_verification.py
```
Prints the answers to 6 example questions.

### Reproduce the evaluation
```bash
python evalset/kcc/run_kcc.py        # 200 real Kisan Call Centre queries
python evalset/kcc/heldout.py        # held-out real queries
python scripts/evaluate.py           # 67-question accuracy and safety set
python evalset/run_evalset.py        # end-to-end feature scenarios
python evalset/pau/run_pau.py        # PAU Package of Practices answers
```

### Run the REST API (optional)
```bash
uvicorn app.api:app --port 8000
```
Interactive docs: http://localhost:8000/docs

| Endpoint | Purpose |
|---|---|
| `POST /ask` | Ask a question: `{"query": "...", "language": "en|pa|hinglish|hi", "history": [...], "profile": {...}}` |
| `POST /ask/voice` | Ask with a voice note (multipart: `audio`, `language`, `history`, optional `profile` as JSON) |
| `POST /ask/image` | Diagnose a crop photo (multipart: `image`, optional `question`, `language`, `history`, `profile`) |
| `GET /weather?place=Delhi&language=en` | Weather with spray and irrigation advice for any place in India |
| `POST /speak` | Turn text into MP3 speech: `{"text": "...", "language": "pa"}` |
| `GET /health` | Which services are active (index, LLM, speech-to-text, voices) |

Every answer includes `evidence_status`, `source_type`, `review_status` and `premise_status`. For follow-ups, send the `turn` object from each response back in `history`:
```bash
curl -X POST http://localhost:8000/ask -H "Content-Type: application/json" \
  -d '{"query": "What is the dose?", "language": "hi", "history": [{"query": "How to control aphids in mustard?", "answer": "...", "intent": "crop_question", "crop": "Mustard", "topic": "Aphid"}]}'
```

### Deploy on Streamlit Community Cloud (free)
1. Sign in at https://share.streamlit.io with GitHub and click **Create app → Deploy a public app from GitHub**.
2. Repository `KanishkaSingh19/KisanSahayak`, branch `main`, main file path **`frontend/app.py`**. It uses `frontend/requirements.txt`, with no PyTorch, so it fits the memory limit.
3. Under **Advanced settings**, choose Python **3.12** and paste into **Secrets**:
   ```toml
   GEMINI_API_KEY = "your_gemini_key"
   GROQ_API_KEY = "your_groq_key"
   LLM_PROVIDER = "gemini"
   EMBEDDING_PROVIDER = "gemini"
   ```
4. Click **Deploy**. The first start installs packages, downloads PAU's *Package of Practices* and builds the search index. The shipped Gemini vector cache means no chunks need re-embedding.

After each push to `main`, **reboot the app** (share.streamlit.io → ⋮ → **Reboot app**). The file watcher is off (`.streamlit/config.toml`), so a running app keeps its old code until it restarts.

---

## 📊 Evaluation

The assistant is evaluated in three layers, each answering a different question:

| Layer | Question it answers |
|---|---|
| **1. Real farmer queries** | Does the system work on the questions farmers actually ask? |
| **2. Safety & adversarial tests** | Does it resist wrong assumptions, unsupported problems and unsafe inputs? |
| **3. Automated tests & CI** | Does the implementation stay reproducible and regression-safe? |

All numbers below are copied from the committed reports linked in each section; every report lists its failures too.

### 1. Real-world farmer evaluation: 200 Kisan Call Centre queries

**Evaluated on 200 real Kisan Call Centre queries from Punjab (Jan–Jul 2025), covering English, Hindi, Punjabi and Hinglish** (50 each). They were chosen by how often farmers asked them, not by whether KisanSahayak can answer them. Report: [`evalset/kcc/results.md`](evalset/kcc/results.md).

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

**Held-out check:** 85 further real queries, ranked after the 200 and never used for tuning ([`evalset/kcc/heldout_results.md`](evalset/kcc/heldout_results.md)).

| Metric | Result | Scope |
|---|---|---|
| Answered from the right crop's PAU chapter | **55/74 (74%)** | held-out queries outside our own advisories |
| … shown advice on something else | 13/74 (18%) | held-out queries outside our own advisories |
| Right advisory in the top 3 | 4/7 (57%) | held-out queries our own advisories cover |

**Scope, stated plainly:**
- **Coverage:** only 26 of the 200 queries fall inside our own 4-crop advisories (crop and safety); most calls are about weeds, nutrient deficiencies and varieties. The retrieval percentages apply to that covered subset, not to all farmer questions.
- **What is measured:** these are retrieval, routing and language checks, run with offline answers and local MiniLM search. They do not measure agronomic accuracy, which needs an agronomist. [`evalset/kcc/review_sheet.csv`](evalset/kcc/review_sheet.csv) puts each answer next to the Kisan Call Centre advisor's answer for that review.
- **Languages:** English queries are the exact logged text. The Hindi, Punjabi and Hinglish queries are translations of other real queries, because the logs are in English.
- **Source:** data.gov.in KCC transcripts via [huggingface.co/datasets/whitesnek/punjab_kcc](https://huggingface.co/datasets/whitesnek/punjab_kcc).

### 2. Safety & adversarial evaluation

**Controlled test set: 67 hand-written questions** in English, Punjabi, Hinglish and Hindi ([`eval/test_set.json`](eval/test_set.json)).
- **Covers:** all 14 advisory sections (42 questions), plus targeted cases: weather places (8), greetings and off-topic questions (6), banned pesticides (5) and follow-ups (6).
- **Reports:** [`eval/results_minilm.md`](eval/results_minilm.md) and [`eval/results_gemini.md`](eval/results_gemini.md).

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

**Adversarial and failure cases covered by the automated tests:**

| Failure mode | What is checked | Tests |
|---|---|---|
| False premises | A wrong figure in the question (₹12,000/month PM-KISAN, 100 g Actara, a false MSP, "it will rain") is corrected from the source. A worded assumption ("Since MSP guarantees the government will buy all my wheat…") is corrected with the cited official text. Correct premises are left alone. The badge never says plain "Verified" after a correction. | [`test_false_premise.py`](tests/test_false_premise.py) (16), [`test_worded_premises.py`](tests/test_worded_premises.py) (15) |
| Unsupported / fake diseases | A disease the knowledge base never mentions ("golden blight") gets no treatment or dose. Synonyms and spellings it does know are not refused. | `test_false_premise.py`, `test_worded_premises.py` |
| Pesticide safety & banned chemicals | CIBRC banned-chemical scan in Latin, Devanagari and Gurmukhi script; spray disclaimers; no dose for a product the evidence does not recommend | [`test_guardrails.py`](tests/test_guardrails.py), [`test_router.py`](tests/test_router.py), `test_false_premise.py` |
| Cross-crop contamination | Uncovered crops and topics are referred, not answered with another crop's advisory; PAU answers come from the asked crop's chapter | `test_router.py`, [`test_pau.py`](tests/test_pau.py) |
| Missing evidence | The LLM's "not found" marker makes the answer *not verified*. Unbacked numbers are replaced. A declined scheme answer falls back to official text. | `test_false_premise.py`, [`test_numbers_check.py`](tests/test_numbers_check.py) |
| Follow-ups / context retention | Crop, pest and place carried across turns, topic switches, "spray again?" asks which crop | [`test_conversation.py`](tests/test_conversation.py) |
| Weather / market / tool failures | Unknown place reported (not silently replaced), mandi API offline, missing PAU index, missing speech keys, failed photo diagnosis | [`test_location.py`](tests/test_location.py), [`test_market.py`](tests/test_market.py), `test_pau.py`, [`test_speech.py`](tests/test_speech.py), [`test_vision.py`](tests/test_vision.py) |

### 3. Automated testing & reliability

- **414 automated tests** (`pytest`) run on every push and pull request in GitHub Actions ([`.github/workflows/tests.yml`](.github/workflows/tests.yml)). They need no API keys: the tests force the offline answer template and local embeddings, so results are repeatable.
- **End-to-end feature scenarios** ([`evalset/results.md`](evalset/results.md)): 28 cases covering whole conversations in all four languages, the farm profile, PM-KISAN eligibility, crop insurance, Kisan Credit Card, weather, guardrails, photo and voice.
  - The 25 automated cases pass **24/25** (38/39 conversation turns).
  - The one failure is a Hindi symptoms-only bacterial blight question that local MiniLM search ranks under brown planthopper.
  - Photo and voice (3 cases) are checked by hand.
- **PAU *Package of Practices* answers** ([`evalset/pau/results.md`](evalset/pau/results.md)): on 28 team-written questions outside our own advisories, 28/28 were answered from the right crop's chapter, and the expected section was in the top 3 for 28/28.
- **Cold start:** Streamlit Cloud used to re-embed ~400 PAU chunks against the free Gemini quota, which took about 13 minutes. A shipped Gemini embedding cache ([`scripts/build_embedding_cache.py`](scripts/build_embedding_cache.py)) brought this to about 15 seconds. Both times were observed on the deployed app, not measured with a benchmark script.
- **Cost:** about **₹0.15** per typed question with Gemini 3.7 Flash, ₹0.18 per voice question and ₹0.34 per photo, all well under ₹1. Measured with real token counts: [`docs/cost_estimate.md`](docs/cost_estimate.md).
  - Weather, prices and referrals use no LLM, except one short check when the question states an assumption.

---

## 📂 Repository structure

```
KisanSahayak/
├── app/                          # The assistant
│   ├── agent/
│   │   ├── pipeline.py           # End-to-end orchestrator (text, voice, photo)
│   │   ├── router.py             # Intent classification & crop/pest/place/scheme extraction
│   │   ├── synthesizer.py        # Grounded answers (Gemini/OpenAI/offline template)
│   │   ├── guardrails.py         # Banned-chemical filter, grounding and number checks
│   │   ├── claims.py             # Checks figures and names stated in the question
│   │   ├── premises.py           # Checks assumptions stated in words (cited evidence)
│   │   └── state.py              # Data models: intent, answer, conversation turn, farm profile
│   ├── rag/                      # Chunking, embeddings, FAISS, BM25, RRF, hybrid search, PAU chapters, ingest
│   ├── tools/                    # Weather, places, market prices, schemes, per-acre doses, photo diagnosis
│   ├── speech/                   # Speech-to-text (Whisper/Gemini) and text-to-speech (Edge-TTS/gTTS)
│   ├── i18n.py                   # All farmer-facing text in four languages
│   ├── review.py                 # KVK expert review queue
│   ├── api.py                    # Optional FastAPI REST API over the same pipeline
│   └── config.py                 # Settings from .env
├── frontend/
│   ├── app.py                    # Streamlit chat app
│   ├── pages/1_KVK_expert_review.py  # Review page for KVK experts
│   └── requirements.txt          # Lightweight requirements for Streamlit Community Cloud
├── data/
│   ├── raw/                      # Crop advisories (PAU, with page numbers) & CIBRC safety
│   ├── translations.json         # Punjabi, Hindi and Hinglish versions of the advisories
│   ├── schemes/                  # PM-KISAN, PMFBY, Kisan Credit Card (official sources, 4 languages)
│   ├── market/msp.json           # Minimum Support Prices with source and date
│   ├── facts/                    # Sourced official statements for checking premises
│   ├── vectors/                  # Shipped Gemini embedding cache (numbers only)
│   └── sample_photos/            # Crop photos for trying the photo diagnosis
├── tests/                        # pytest suite (414 tests)
├── evalset/                      # Kisan Call Centre (kcc/), PAU (pau/) and feature test sets
├── eval/                         # 67-question accuracy and safety set and reports
├── scripts/                      # Evaluation, cost estimate, PAU build, embedding cache, translation
├── docs/cost_estimate.md         # Cost per question
├── run_verification.py           # 6 example queries from the command line
├── Dockerfile · .env.example · requirements.txt
├── AI_DISCLOSURE.md              # AI tools used to build the project, AI inside it, AI-generated data
└── README.md
```

---

## 🤖 AI tools disclosure

See [`AI_DISCLOSURE.md`](AI_DISCLOSURE.md): which AI tools helped build the project, which AI models run inside it, what is rule-based, and which data is AI-generated.

*Team Powerpuff Girls*
