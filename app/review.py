"""KVK expert review queue.

Answers that need an expert's eye are saved here, and KVK experts review them on the
"KVK expert review" page of the Streamlit app:

- pesticide answers (any spray or dose), and banned-pesticide warnings
- AI answers that are only weakly backed by the retrieved advisories (low grounding score)
- photo diagnoses the vision model was not sure about
- questions the advisories do not cover, so experts can see what farmers need next

Only the question, the answer and why it was flagged are stored: no farm profile or personal details.
Items live in a JSON Lines file (data/review/queue.jsonl). Free hosting resets its disk on restart,
so a permanent deployment should point REVIEW_QUEUE_PATH at lasting storage.
"""

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from app.agent.state import GroundedAnswer
from app.config import settings
from app.i18n import STRINGS

DEFAULT_PATH = settings.DATA_DIR / "review" / "queue.jsonl"
LOW_GROUNDING = 0.5  # share of an AI answer's words found in its sources

REASONS = {
    "pesticide": "Pesticide spray or dose",
    "banned_pesticide": "Banned pesticide asked about",
    "low_grounding": "AI answer weakly backed by the sources",
    "photo_uncertain": "Photo diagnosis not certain",
    "low_retrieval_confidence": "Search could not confirm it used the right advisory",
    "not_covered": "Question our advisories do not cover",
}

_STATUTORY = set(STRINGS["statutory_disclaimer"].values())
_BANNED = set(STRINGS["monocrotophos_warning"].values()) | set(STRINGS["endosulfan_warning"].values())


def review_reasons(result: GroundedAnswer) -> List[str]:
    """Why an answer should go to a KVK expert (empty list: no review needed)."""
    meta = result.processing_metadata
    reasons = []
    disclaimers = set(result.safety_disclaimers)
    if disclaimers & _BANNED:
        reasons.append("banned_pesticide")
    if disclaimers & _STATUTORY:
        reasons.append("pesticide")
    score = meta.get("grounding_score")
    if meta.get("answer_source") == "llm" and score is not None and score < LOW_GROUNDING:
        reasons.append("low_grounding")
    vision = meta.get("vision") or {}
    healthy = str(vision.get("problem", "")).strip().lower() == "healthy"
    if vision and (vision.get("confidence") != "high" or (not result.retrieved_chunks and not healthy)):
        reasons.append("photo_uncertain")  # unsure, or no treatment could be given (unclear / crop not covered)
    if result.intent in ("crop_not_covered", "topic_not_covered"):
        reasons.append("not_covered")
    if meta.get("retrieval") == "low_confidence":
        reasons.append("low_retrieval_confidence")  # the search could not confirm the advisory it used
    return reasons


class ReviewQueue:
    """Flagged answers waiting for, or checked by, a KVK expert."""

    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path or settings.REVIEW_QUEUE_PATH or DEFAULT_PATH)
        self._lock = threading.Lock()

    def _read(self) -> List[Dict]:
        if not self.path.exists():
            return []
        items = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    items.append(json.loads(line))
                except ValueError:
                    continue  # skip a damaged line rather than lose the whole queue
        return items

    def _write(self, items: List[Dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text("".join(json.dumps(i, ensure_ascii=False) + "\n" for i in items), encoding="utf-8")
        tmp.replace(self.path)

    def submit(self, result: GroundedAnswer) -> Optional[str]:
        """Add the answer to the queue if it needs review; returns the item id, or None."""
        reasons = review_reasons(result)
        if not reasons:
            return None
        item = {
            "id": uuid.uuid4().hex[:10],
            "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "question": result.query,
            "language": result.detected_language,
            "intent": result.intent,
            "answer": result.answer,
            "sources": result.citations,
            "reasons": reasons,
            "grounding_score": result.processing_metadata.get("grounding_score"),
            "answer_source": result.processing_metadata.get("answer_source"),
            "status": "pending",
            "verdict": None,
            "correction": "",
            "reviewer": "",
            "reviewed": None,
        }
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        result.processing_metadata["kvk_review"] = item["id"]  # shown to the farmer as "sent for expert review"
        return item["id"]

    def items(self, status: Optional[str] = None) -> List[Dict]:
        """Newest first; `status` is "pending" or "reviewed" (None: all)."""
        items = [i for i in self._read() if status is None or i["status"] == status]
        return sorted(items, key=lambda i: i["created"], reverse=True)

    def review(self, item_id: str, verdict: str, correction: str = "", reviewer: str = "") -> bool:
        """Record an expert's verdict: "correct", "needs_correction" or "unsafe"."""
        if verdict not in ("correct", "needs_correction", "unsafe"):
            raise ValueError(f"Unknown verdict: {verdict}")
        with self._lock:
            items = self._read()
            for item in items:
                if item["id"] == item_id:
                    item.update(
                        status="reviewed", verdict=verdict, correction=correction.strip(), reviewer=reviewer.strip(),
                        reviewed=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    )
                    self._write(items)
                    return True
        return False

    def stats(self) -> Dict[str, int]:
        items = self._read()
        reviewed = [i for i in items if i["status"] == "reviewed"]
        return {
            "total": len(items),
            "pending": len(items) - len(reviewed),
            "reviewed": len(reviewed),
            "correct": sum(i["verdict"] == "correct" for i in reviewed),
            "needs_correction": sum(i["verdict"] == "needs_correction" for i in reviewed),
            "unsafe": sum(i["verdict"] == "unsafe" for i in reviewed),
        }
