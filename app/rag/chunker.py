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
        if not 0 <= chunk_overlap < chunk_size:
            raise ValueError("chunk_overlap must be at least 0 and smaller than chunk_size")
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
            # Printed pages for the citation ("PAU Package of Practices ..., pages 18-21"); kept out of the
            # chunk text so the same words in every chunk don't sway retrieval
            reference = sec.get("source_reference", "")

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
            metadata = {
                "doc_id": doc_id,
                "source": source_org,
                "title": doc_title,
                "crop": crop,
                "season": season,
                "section": sec_title,
                "pest_or_topic": pest_or_topic,
                "has_warning": bool(warning),
                "reference": reference,
                "kind": "advisory",
            }

            # If section fits within chunk_size, keep as a single atomic chunk
            if len(full_section_text) <= self.chunk_size:
                chunks.append(DocumentChunk(chunk_id=f"{doc_id}_s{sec_idx}_c0", text=full_section_text,
                                            metadata=dict(metadata)))
            else:
                # Sub-chunk while retaining the crop & section header
                header = f"Crop: {crop} | Topic: {sec_title} | Source: {source_org}\n"
                sub_chunks = self._sliding_window_split(full_section_text, header)
                for c_idx, sub_text in enumerate(sub_chunks):
                    chunks.append(DocumentChunk(chunk_id=f"{doc_id}_s{sec_idx}_c{c_idx}", text=sub_text,
                                                metadata=dict(metadata)))

        return chunks

    def _sliding_window_split(self, text: str, header: str) -> List[str]:
        """Split text into windows of whole sentences; each window after the first starts with
        up to `chunk_overlap` characters carried over from the end of the previous one."""
        effective_chunk_size = self.chunk_size - len(header)
        if effective_chunk_size < 100:
            effective_chunk_size = self.chunk_size

        sentences = []
        for sentence in text.split(". "):
            sentence_clean = sentence.strip()
            if sentence_clean:
                sentences.append(sentence_clean if sentence_clean.endswith(".") else sentence_clean + ".")

        chunks = []
        current_chunk: List[str] = []  # sentences (or an overlap tail) of the window being filled
        new_in_window = False  # the window holds more than just the overlap carried over

        for sentence in sentences:
            if new_in_window and len(" ".join(current_chunk + [sentence])) > effective_chunk_size:
                chunks.append(header + " ".join(current_chunk))
                current_chunk = self._overlap_tail(current_chunk)
                new_in_window = False
            current_chunk.append(sentence)
            new_in_window = True

        if new_in_window:
            chunks.append(header + " ".join(current_chunk))

        return chunks

    def _overlap_tail(self, window: List[str]) -> List[str]:
        """The end of a window to repeat at the start of the next one, at most `chunk_overlap`
        characters: whole trailing sentences when they fit, otherwise the last words of the last one."""
        if self.chunk_overlap == 0:
            return []
        tail: List[str] = []
        for sentence in reversed(window):
            if len(" ".join([sentence] + tail)) > self.chunk_overlap:
                break
            tail.insert(0, sentence)
        if tail:
            return tail
        words = window[-1].split()
        while words and len(" ".join(words)) > self.chunk_overlap:
            words.pop(0)
        return [" ".join(words)] if words else []

    def chunk_pau_document(self, doc: Dict[str, Any], doc_id: str) -> List[DocumentChunk]:
        """Chunks of a PAU Package of Practices chapter (see app/rag/pau_kb.py): PAU's own wording,
        one section per PAU heading, each citing the section's printed pages."""
        crop = doc.get("crop", "General Agriculture")
        season = doc.get("season", "All")
        source = doc.get("source_organization", "Punjab Agricultural University (PAU), Ludhiana")
        chunks: List[DocumentChunk] = []
        for sec_idx, sec in enumerate(doc.get("sections", [])):
            title, text, pages = sec.get("section_title", ""), sec.get("pau_text", ""), sec.get("pages", "")
            if not text:
                continue
            word = "pages" if "-" in pages else "page"
            metadata = {
                "doc_id": doc_id,
                "source": source,
                "title": doc.get("document_title", "PAU Package of Practices"),
                "crop": crop,
                "season": season,
                "section": title,
                "pest_or_topic": title,
                "has_warning": False,
                "reference": f"{doc.get('document_title', 'PAU Package of Practices')}, {word} {pages}",
                "kind": "pau",
            }
            full_text = f"Crop: {crop} ({season} Season)\nTopic: {title}\nPAU recommendation: {text}"
            if len(full_text) <= self.chunk_size:
                pieces = [full_text]
            else:
                pieces = self._sliding_window_split(f"PAU recommendation: {text}", f"Crop: {crop} | Topic: {title}\n")
            for c_idx, piece in enumerate(pieces):
                chunks.append(DocumentChunk(chunk_id=f"{doc_id}_s{sec_idx}_c{c_idx}", text=piece, metadata=dict(metadata)))
        return chunks

    def load_and_chunk_directory(self, raw_dir: Path) -> List[DocumentChunk]:
        """Load all json files from the directory and chunk them (advisories or PAU chapters)."""
        all_chunks: List[DocumentChunk] = []
        for file_path in sorted(Path(raw_dir).glob("*.json")):
            doc_id = file_path.stem
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("kind") == "pau_package_of_practices":
                all_chunks.extend(self.chunk_pau_document(data, doc_id))
            else:
                all_chunks.extend(self.chunk_structured_document(data, doc_id))
        return all_chunks
