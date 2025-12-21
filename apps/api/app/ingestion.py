import hashlib
import os
from datetime import datetime, timezone
from typing import List, Tuple

from pypdf import PdfReader

from .config import CHUNK_OVERLAP, CHUNK_SIZE, PARSER_MODE, RAW_DIR


def compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def docs_snapshot_id_for(doc_sha256: str) -> str:
    return f"snap_{doc_sha256[:12]}"


def save_raw_pdf(doc_id: str, filename: str, data: bytes) -> str:
    safe_name = filename.replace(" ", "_")
    path = os.path.join(RAW_DIR, f"{doc_id}_{safe_name}")
    with open(path, "wb") as f:
        f.write(data)
    return path


def parse_pdf_pages(path: str) -> List[str]:
    reader = PdfReader(path)
    pages = []
    for page in reader.pages:
        text = page.extract_text() or ""
        pages.append(_normalize_whitespace(text))
    return pages


def _normalize_whitespace(text: str) -> str:
    return " ".join(text.split())


def chunk_page_text(page_text: str) -> List[Tuple[int, int, str]]:
    chunks = []
    start = 0
    while start < len(page_text):
        end = min(start + CHUNK_SIZE, len(page_text))
        chunk_text = page_text[start:end]
        chunks.append((start, end, chunk_text))
        if end == len(page_text):
            break
        start = max(end - CHUNK_OVERLAP, 0)
    return chunks


def make_chunk_id(doc_id: str, page_num: int, chunk_index: int) -> str:
    return f"{doc_id}-p{page_num}-c{chunk_index}"


def build_chunk_rows(
    doc_id: str,
    doc_sha256: str,
    docs_snapshot_id: str,
    pages: List[str],
) -> List[tuple]:
    rows = []
    for page_num, page_text in enumerate(pages, start=1):
        for chunk_index, (char_start, char_end, chunk_text) in enumerate(
            chunk_page_text(page_text)
        ):
            chunk_id = make_chunk_id(doc_id, page_num, chunk_index)
            rows.append(
                (
                    chunk_id,
                    docs_snapshot_id,
                    doc_id,
                    doc_sha256,
                    page_num,
                    chunk_index,
                    char_start,
                    char_end,
                    chunk_text,
                    PARSER_MODE,
                )
            )
    return rows


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
