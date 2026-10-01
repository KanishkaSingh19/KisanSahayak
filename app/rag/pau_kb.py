"""PAU's Package of Practices for Crops of Punjab as searchable knowledge-base sections.

The PAU text is copyrighted, so it is not committed: `build_pau_kb()` downloads the official PDFs
from pau.edu and writes settings.PAU_KB_DIR/*.json (git-ignored). Sections are cut at PAU's own
headings, keep PAU's exact wording and record their printed page numbers, so answers can cite
"PAU Package of Practices ..., pages N-M". Tip boxes from the side column are kept as "PAU tips".
"""

import json
import re
from pathlib import Path
from typing import List

import requests

from app.config import settings

HEADERS = {"User-Agent": "KisanSahayak/1.0 (farmer advisory app; github.com/KanishkaSingh19/KisanSahayak)"}
PAGE_OFFSET = 8  # both books: PDF page 9 is printed page 1
KIND = "pau_package_of_practices"

BOOKS = {
    "rabi": {
        "url": "https://www.pau.edu/content/ccil/pf/pp_rabi.pdf",
        "title": "PAU Package of Practices for Crops of Punjab, Rabi 2025-26",
        "year": 2025,
    },
    "kharif": {
        "url": "https://www.pau.edu/content/ccil/pf/pp_kharif.pdf",
        "title": "PAU Package of Practices for Crops of Punjab, Kharif 2026",
        "year": 2026,
    },
}
# (book, crop, season, first and last PDF page of the chapter)
CHAPTERS = [
    ("rabi", "Wheat", "Rabi", 9, 30),
    ("rabi", "Mustard", "Rabi", 55, 65),
    ("kharif", "Paddy (Rice)", "Kharif", 9, 35),
    ("kharif", "Cotton", "Kharif", 53, 71),
    ("rabi", "All Crops", "All", 145, 146),  # Spray technology (the same chapter is in both books)
]
NEWLINE = "\n"
SUB_ITEM = re.compile(r"^(\(?[A-Za-z]{1,3}[.)]|\(?[ivx]{1,4}[.)]|\d{1,2}[.)])\s")  # "A. ", "ii. ", "(a) ", "2. "


def pau_kb_files(kb_dir: Path = settings.PAU_KB_DIR) -> List[Path]:
    """The built PAU section files (empty if the knowledge base hasn't been built)."""
    return sorted(Path(kb_dir).glob("pau_*.json")) if Path(kb_dir).is_dir() else []


def ensure_pau_kb(kb_dir: Path = settings.PAU_KB_DIR) -> bool:
    """Build the PAU knowledge base if it is missing and auto-build is on. Never raises: without
    it the app still answers from its own advisories and refers other questions to the KVK."""
    if not settings.USE_PAU_KB:
        return False
    if pau_kb_files(kb_dir):
        return True
    if not settings.PAU_AUTO_BUILD:
        return False
    try:
        build_pau_kb(kb_dir)
    except Exception as e:  # no network, pau.edu down, PyMuPDF missing
        print(f"[Warning] PAU Package of Practices not available: {str(e)[:200]}")
    return bool(pau_kb_files(kb_dir))


def download(book: str, pdf_dir: Path) -> Path:
    path = pdf_dir / f"pp_{book}.pdf"
    if not path.exists():
        pdf_dir.mkdir(parents=True, exist_ok=True)
        resp = requests.get(BOOKS[book]["url"], headers=HEADERS, timeout=120)
        resp.raise_for_status()
        path.write_bytes(resp.content)
    return path


def clean(text: str) -> str:
    text = text.replace("\t", " ")
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)  # words split across lines
    text = re.sub(r"\s*\n\s*", " ", text)
    return re.sub(r"\s{2,}", " ", text).strip()


def line_text(line) -> str:
    return "".join(s["text"] for s in line["spans"])


def line_heading_level(spans) -> int:
    """3 for a chapter or sub-chapter title in capitals ("BASMATI RICE"), 2 for a section heading
    (bold, 11.95 pt and up), 1 for a subsection (bold, 11-11.95 pt), 0 for ordinary text."""
    spans = [s for s in spans if s["text"].strip()]
    if not spans or not all(("Bold" in s["font"] or s["flags"] & 16) for s in spans):
        return 0
    text = "".join(s["text"] for s in spans).strip()
    size = max(s["size"] for s in spans)
    if len(re.findall(r"[A-Za-z]", text)) < 3 or len(text) > 90 or text.endswith("."):
        return 0  # bullets, sentences
    if text.isupper():
        return 3 if size >= 14.5 and not text[0].isdigit() else 0  # "1. CEREAL CROPS" is a book part, not a crop
    return 2 if size >= 11.95 else 1 if size >= 11.0 else 0


def chapter_sections(doc, crop: str, first: int, last: int) -> list:
    """PAU's text for one chapter, cut into sections at its bold headings (checked line by line,
    because a heading often shares a text block with the paragraph after it)."""
    sections, tips = [], []
    top = ""
    label = crop  # "Paddy (Rice)", then "Paddy (Rice) - Basmati Rice" once the Basmati sub-chapter starts
    current = None

    def start(title: str, page: int):
        nonlocal current
        if current and current["text"].strip():
            sections.append(current)
        current = {"title": title, "text": "", "pages": [page]}

    for pno in range(first - 1, last):
        page = doc[pno]
        width, page_no = page.rect.width, pno + 1 - PAGE_OFFSET
        main = []
        for block in page.get_text("dict")["blocks"]:
            if block.get("type") != 0:
                continue
            x0, y0, x1, _ = block["bbox"]
            lines = [ln for ln in block["lines"] if line_text(ln).strip()]
            text = NEWLINE.join(line_text(ln) for ln in lines).strip()
            if not text or text.isdigit():
                continue  # empty, or the printed page number
            if x0 > width * 0.55 and (x1 - x0) < width * 0.45:
                tips.append(clean(text))  # tip box in the side column
            else:
                main.append((round(y0), x0, lines))
        for _, _, lines in sorted(main, key=lambda m: (m[0], m[1])):
            for line in lines:
                level = line_heading_level(line["spans"])
                text = line_text(line)
                heading = clean(text)
                if level == 3:
                    # A crop chapter or sub-chapter ("WHEAT", "BASMATI RICE", "DESI COTTON")
                    name = heading.title()
                    label = crop if name.lower() in crop.lower() else f"{crop} - {name}"
                    top = ""
                    start(f"{label} - Introduction", page_no)
                elif level == 2:
                    top = heading
                    start(f"{label} - {top}", page_no)
                elif level == 1:
                    if SUB_ITEM.match(heading) and top:
                        start(f"{label} - {top} - {heading}", page_no)  # "Weed Control - B. Broadleaf weeds"
                    else:
                        top = heading  # a topic of its own ("Irrigation", "Storage")
                        start(f"{label} - {top}", page_no)
                else:
                    if current is None:
                        start(f"{crop} - Introduction", page_no)
                    current["text"] += NEWLINE + text
                    if page_no not in current["pages"]:
                        current["pages"].append(page_no)
    if current and current["text"].strip():
        sections.append(current)

    out = [{
        "section_title": s["title"],
        "pau_text": clean(s["text"]),
        "pages": f"{s['pages'][0]}-{s['pages'][-1]}" if len(s["pages"]) > 1 else str(s["pages"][0]),
    } for s in sections]
    if tips:
        out.append({"section_title": f"{crop} - PAU tips", "pau_text": " ".join(tips),
                    "pages": f"{first - PAGE_OFFSET}-{last - PAGE_OFFSET}"})
    return out


def build_pau_kb(kb_dir: Path = settings.PAU_KB_DIR) -> List[Path]:
    """Download the two books (if not already there) and write one JSON file per chapter."""
    import pymupdf  # only needed to build the knowledge base

    kb_dir = Path(kb_dir)
    kb_dir.mkdir(parents=True, exist_ok=True)
    docs = {book: pymupdf.open(download(book, kb_dir.parent)) for book in BOOKS}
    written = []
    for book, crop, season, first, last in CHAPTERS:
        sections = chapter_sections(docs[book], crop, first, last)
        name = re.sub(r"[^a-z]+", "_", f"pau_{book}_{crop}".lower()).strip("_")
        doc = {
            "source_organization": "Punjab Agricultural University (PAU), Ludhiana",
            "document_title": BOOKS[book]["title"],
            "source_url": BOOKS[book]["url"],
            "crop": crop,
            "season": season,
            "publication_year": BOOKS[book]["year"],
            "kind": KIND,
            "sections": sections,
        }
        path = kb_dir / f"{name}.json"
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
        written.append(path)
        print(f"{name}: {len(sections)} sections, {sum(len(s['pau_text']) for s in sections):,} characters")
    return written
