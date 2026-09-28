import json
from pathlib import Path
from typing import Any, Dict, List
from pydantic import BaseModel, Field


class DocumentChunk(BaseModel):
    chunk_id: str
    text: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AgriculturalChunker:
    """Chunks structured agricultural documents with metadata preservation."""

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 100):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_structured_document(self, raw_doc: Dict[str, Any], doc_id: str) -> List[DocumentChunk]:
        """Convert a structured agricultural JSON document into contextual chunks."""
        chunks: List[DocumentChunk] = []
        source_org = raw_doc.get("source_organization", "ICAR")
        doc_title = raw_doc.get("document_title", "Agricultural Advisory")
        crop = raw_doc.get("crop", "General Agriculture")
        season = raw_doc.get("season", "All")
        pub_year = raw_doc.get("publication_year", 2024)

        sections = raw_doc.get("sections", [])
        for sec_idx, sec in enumerate(sections):
            sec_title = sec.get("section_title", f"Section {sec_idx + 1}")
            pest_or_topic = sec.get("disease_pest_name", "General")
            symptoms = sec.get("symptoms", "")
            action = sec.get("recommended_action", "")
            preventive = sec.get("preventive_measures", "")
            warning = sec.get("critical_safety_warning", "")

            # Compose coherent structured textual chunk
            text_parts = [
                f"Crop: {crop} ({season} Season)",
                f"Source: {source_org} ({pub_year})",
                f"Topic: {sec_title}",
            ]
            if pest_or_topic and pest_or_topic != "N/A":
                text_parts.append(f"Target Disease/Pest: {pest_or_topic}")
            if symptoms and symptoms != "N/A":
                text_parts.append(f"Symptoms & Identification: {symptoms}")
            if action and action != "N/A":
                text_parts.append(f"Recommended Action & Chemical Dosage: {action}")
            if preventive and preventive != "N/A":
                text_parts.append(f"Preventive Measures: {preventive}")
            if warning:
                text_parts.append(f"Safety Warning: {warning}")

            full_section_text = "\n".join(text_parts)

            # If section fits within chunk_size, keep as a single atomic chunk
            if len(full_section_text) <= self.chunk_size:
                chunk = DocumentChunk(
                    chunk_id=f"{doc_id}_s{sec_idx}_c0",
                    text=full_section_text,
                    metadata={
                        "doc_id": doc_id,
                        "source": source_org,
                        "title": doc_title,
                        "crop": crop,
                        "season": season,
                        "section": sec_title,
                        "pest_or_topic": pest_or_topic,
                        "has_warning": bool(warning),
                    },
                )
                chunks.append(chunk)
            else:
                # Sub-chunk while retaining the crop & section header
                header = f"Crop: {crop} | Topic: {sec_title} | Source: {source_org}\n"
                sub_chunks = self._sliding_window_split(full_section_text, header)
                for c_idx, sub_text in enumerate(sub_chunks):
                    chunk = DocumentChunk(
                        chunk_id=f"{doc_id}_s{sec_idx}_c{c_idx}",
                        text=sub_text,
                        metadata={
                            "doc_id": doc_id,
                            "source": source_org,
                            "title": doc_title,
                            "crop": crop,
                            "season": season,
                            "section": sec_title,
                            "pest_or_topic": pest_or_topic,
                            "has_warning": bool(warning),
                        },
                    )
                    chunks.append(chunk)

        return chunks

    def _sliding_window_split(self, text: str, header: str) -> List[str]:
        """Split text using sliding character window with sentence boundaries."""
        effective_chunk_size = self.chunk_size - len(header)
        if effective_chunk_size < 100:
            effective_chunk_size = self.chunk_size

        sentences = text.split(". ")
        chunks = []
        current_chunk = []
        current_len = 0

        for sentence in sentences:
            sentence_clean = sentence.strip()
            if not sentence_clean:
                continue
            sentence_with_dot = sentence_clean if sentence_clean.endswith(".") else sentence_clean + "."
            if current_len + len(sentence_with_dot) > effective_chunk_size and current_chunk:
                chunks.append(header + " ".join(current_chunk))
                # Overlap: keep last sentence
                current_chunk = [current_chunk[-1], sentence_with_dot]
                current_len = len(current_chunk[0]) + len(sentence_with_dot) + 1
            else:
                current_chunk.append(sentence_with_dot)
                current_len += len(sentence_with_dot) + 1

        if current_chunk:
            chunks.append(header + " ".join(current_chunk))

        return chunks

    def load_and_chunk_directory(self, raw_dir: Path) -> List[DocumentChunk]:
        """Load all json files from the raw directory and chunk them."""
        all_chunks: List[DocumentChunk] = []
        for file_path in raw_dir.glob("*.json"):
            doc_id = file_path.stem
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            chunks = self.chunk_structured_document(data, doc_id)
            all_chunks.extend(chunks)
        return all_chunks
