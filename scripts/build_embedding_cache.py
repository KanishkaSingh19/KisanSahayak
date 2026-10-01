"""Compute Gemini vectors for every chunk the app searches, slowly, and save them for the app to ship.

    python scripts/build_pau_kb.py              # PAU's chapters (if not built yet)
    python scripts/build_embedding_cache.py     # needs GEMINI_API_KEY; resumes where it stopped

A cold start on Streamlit Cloud would otherwise embed ~400 chunks against the free tier's per-minute
limit (13 minutes, and then local vectors anyway). This script stays within the limit: small batches,
a pause after each, and a wait when the API says the quota is used up. It saves after every batch to
data/vectors/gemini_embedding_cache.npz (vectors only, no text), which is committed.
"""

import sys
import time
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.config import settings  # noqa: E402
from app.rag.chunker import AgriculturalChunker  # noqa: E402
from app.rag.embeddings import GeminiEmbedder  # noqa: E402
from app.rag.pau_kb import pau_kb_files  # noqa: E402

BATCH = 20
PAUSE_SEC = 15  # between batches
QUOTA_WAIT_SEC = 70  # after a 429
MAX_QUOTA_WAITS = 20  # then give up for today (the daily quota may be used up)


def all_texts() -> list:
    chunker = AgriculturalChunker(settings.CHUNK_SIZE, settings.CHUNK_OVERLAP)
    chunks = chunker.load_and_chunk_directory(settings.RAW_DATA_DIR)
    if pau_kb_files():
        chunks += chunker.load_and_chunk_directory(settings.PAU_KB_DIR)
    return list(dict.fromkeys(c.text for c in chunks))


def main() -> int:
    if not settings.GEMINI_API_KEY:
        print("GEMINI_API_KEY is not set in .env")
        return 1
    emb = GeminiEmbedder(settings.GEMINI_API_KEY)
    cache = emb.load_cache()
    missing = [t for t in all_texts() if emb.cache_key(t) not in cache]
    print(f"{len(cache)} vectors cached, {len(missing)} to compute", flush=True)
    waits = 0
    while missing:
        batch = missing[:BATCH]
        try:
            vectors = emb._embed(batch, "RETRIEVAL_DOCUMENT")
        except Exception as e:
            if "429" not in str(e) or waits >= MAX_QUOTA_WAITS:
                print(f"Stopped: {str(e)[:160]}\nRun again later; {len(missing)} still to compute.")
                return 2
            waits += 1
            print(f"Quota reached, waiting {QUOTA_WAIT_SEC} s ({waits}/{MAX_QUOTA_WAITS})", flush=True)
            time.sleep(QUOTA_WAIT_SEC)
            continue
        cache.update({emb.cache_key(t): v for t, v in zip(batch, vectors)})
        emb.save_cache()
        missing = missing[BATCH:]
        print(f"saved {len(cache)} vectors, {len(missing)} to go", flush=True)
        if missing:
            time.sleep(PAUSE_SEC)
    print("Done: every chunk has a cached Gemini vector.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
