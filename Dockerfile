# KisanSahayak container image:
#   docker build -t kisansahayak .
#   docker run -p 8501:8501 -e GEMINI_API_KEY=... -e GROQ_API_KEY=... kisansahayak
FROM python:3.12-slim

# Run as an unprivileged user, not root
RUN useradd -m -u 1000 user
USER user
# App settings: Gemini answers + MiniLM search. API keys are passed at run time, never baked into the image.
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    HF_HUB_DISABLE_SYMLINKS_WARNING=1 \
    LLM_PROVIDER=gemini \
    EMBEDDING_PROVIDER=minilm
WORKDIR /home/user/app

# CPU-only PyTorch first (much smaller than the default GPU build), then the rest
RUN pip install --no-cache-dir --user torch --index-url https://download.pytorch.org/whl/cpu
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Download the multilingual MiniLM model at build time so the app starts faster
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')"

COPY --chown=user . .

# Build the FAISS + BM25 search index from data/raw (generated files are not kept in git)
RUN python -m app.rag.ingest

EXPOSE 8501
CMD ["streamlit", "run", "frontend/app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
