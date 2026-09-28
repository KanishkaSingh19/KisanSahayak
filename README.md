# 🌾 KisanSahayak (किसान सहायक) - Phase 2

> **Voice-first Multilingual AI Farming Assistant for Indian Farmers**  
> *Grounded agricultural RAG (FAISS + BM25 + Reciprocal Rank Fusion) with voice input/output and live ag-weather spray advisories*

Farmers ask about crops, pests, pesticides or weather in Hindi, Punjabi, Hinglish or English — by text or voice note. Answers are grounded strictly in curated ICAR, PAU Ludhiana and CIBRC advisories, with citations, banned-chemical checks and spray disclaimers.

---

## ✨ Features

- **Crop & pest advisories** for wheat, mustard, paddy and cotton (yellow rust, karnal bunt, aphid, white rust, BLB, BPH, pink bollworm, whitefly), with multilingual aliases (e.g. *sarson* / सरसों / ਸਰ੍ਹੋਂ).
- **Grounded answers only** — responses come from `data/raw/` advisories and list their sources; if nothing relevant is found, the farmer is referred to their local KVK.
- **Pesticide safety guardrails** — CIBRC banned-chemical scan (Monocrotophos, Endosulfan, DDT, Phorate, Paraquat, …) and a statutory disclaimer on any spray/dosage answer.
- **Ag-weather & spray window** — live [Open-Meteo](https://open-meteo.com/) data for 15 districts (Punjab, Haryana, UP, MP, Rajasthan, Bihar) with spray and irrigation advice; falls back to seasonal defaults when offline.
- **System status sidebar** — shows which LLM and speech-to-text services are actually active.
- **Voice input** — upload a voice note (WAV/MP3/M4A/OGG), transcribed with Whisper Large v3 via Groq.
- **Voice output** — tap Listen to hear the answer: English, Hindi and Hinglish via Edge-TTS, Punjabi via gTTS (Edge-TTS has no Punjabi voice).
- **Language switch** — English (default), Punjabi, Hinglish or Hindi for the UI, the answer, warnings and voice.
- **Gemini fallback chain** — a busy main model hands over to a backup model, then to the offline template with a visible note.
- **Scope handling** — greetings and off-topic queries (cricket, movies, politics, …) get a polite redirect.

---

## 🤖 AI Models & Providers

Every AI component is optional. Without API keys the app runs fully offline-capable with deterministic fallbacks.

| Component | Provider / Model | Needs | Fallback when not configured |
|---|---|---|---|
| Answer generation | Google Gemini (`GEMINI_MODEL`) or OpenAI `gpt-4o-mini` (`OPENAI_MODEL`) | `LLM_PROVIDER` + matching API key | Deterministic template filled from retrieved advisory text |
| Speech-to-text | Groq-hosted `whisper-large-v3` | `GROQ_API_KEY` | Voice tab asks the farmer to type instead |
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
│       └── weather_tool.py       # Open-Meteo ag-weather & spray window advisory
├── data/
│   ├── raw/                      # Curated ICAR, PAU & CIBRC advisories (JSON)
│   │   ├── wheat_pau_icar.json
│   │   ├── mustard_crop_guide.json
│   │   ├── paddy_rice_management.json
│   │   ├── cotton_pest_control.json
│   │   └── pesticide_safety_cibrc.json
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
| `POST /ask` | Ask a question: `{"query": "...", "language": "en|pa|hinglish|hi", "history": [...]}` |
| `POST /ask/voice` | Ask with a voice note (multipart: `audio`, `language`, `history` as JSON) |
| `GET /weather?place=Delhi&language=en` | Weather with spray and irrigation advice for any place in India |
| `POST /speak` | Turn text into MP3 speech: `{"text": "...", "language": "pa"}` |
| `GET /health` | Which services are active (index, LLM, speech-to-text, voices) |

For follow-up questions, send the `turn` object from each `/ask` response back in `history` on the next request:
```bash
curl -X POST http://localhost:8000/ask -H "Content-Type: application/json" \
  -d '{"query": "What is the dose?", "language": "hi", "history": [{"query": "How to control aphids in mustard?", "answer": "...", "intent": "crop_question", "crop": "Mustard", "topic": "Aphid"}]}'
```

---

## 🐳 Running with Docker

The `Dockerfile` installs CPU-only PyTorch, pre-downloads the MiniLM model, builds the search index, and starts the Streamlit app. API keys are passed at run time, never baked into the image:
```bash
docker build -t kisansahayak .
docker run -p 8501:8501 -e GEMINI_API_KEY=your_key -e GROQ_API_KEY=your_key kisansahayak
```
Then open http://localhost:8501. The first visit after start-up loads the models (about a minute).
