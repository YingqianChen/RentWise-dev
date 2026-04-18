"""Build the BM25 retrieval index over the HK tenancy ordinance guide.

The source PDF (``document/AGuideToTenancy_ch.pdf``) ships with a CID-encoded
Chinese font that pypdf / MuPDF's text-layer extraction can't decode, so we
render each page to an image with PyMuPDF and OCR it via the
``rapidocr_onnxruntime`` runtime already in ``requirements.txt`` (it's also
what the listing-image pipeline uses). OCR output is split into
overlapping Chinese-friendly chunks, jieba-tokenised, and written to
``backend/app/data/tenancy_index.json``. The resulting JSON is committed so
teammates don't need to reinstall OCR / rerun the ~5-minute build on first
checkout.

Run::

    cd backend
    python -m scripts.build_tenancy_index

Re-run whenever the source PDF or chunking strategy changes. Idempotent.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import jieba


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_PDF = REPO_ROOT / "document" / "AGuideToTenancy_ch.pdf"
DEFAULT_OUTPUT = Path(__file__).resolve().parent.parent / "app" / "data" / "tenancy_index.json"
INDEX_VERSION = 1

CHUNK_CHAR_LIMIT = 400
CHUNK_OVERLAP = 80
MIN_CHUNK_CHARS = 60
RENDER_ZOOM = 2.0  # 144 DPI is enough for printed HK gov Chinese text

# Known OCR artefacts — filler glyphs that the scanner emits around table
# borders. Drop them before chunking so BM25 tokens stay meaningful.
_OCR_NOISE = re.compile(r"[□■◎○●▲△◇◆★※～﹁﹂『』「」]+")


@dataclass(frozen=True)
class PageText:
    page: int
    text: str


def _ocr_pdf(pdf_path: Path) -> list[PageText]:
    try:
        import fitz  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "pymupdf (fitz) is required to render the tenancy PDF — run `pip install pymupdf`."
        ) from exc
    try:
        import numpy as np  # type: ignore
        from PIL import Image  # type: ignore
        from rapidocr_onnxruntime import RapidOCR  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "rapidocr_onnxruntime + Pillow + numpy are required to OCR the tenancy PDF."
        ) from exc

    if not pdf_path.exists():
        raise FileNotFoundError(f"tenancy PDF not found at {pdf_path}")

    ocr = RapidOCR()
    doc = fitz.open(str(pdf_path))
    pages: list[PageText] = []
    try:
        for idx, page in enumerate(doc, start=1):
            pix = page.get_pixmap(matrix=fitz.Matrix(RENDER_ZOOM, RENDER_ZOOM))
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            arr = np.array(img)
            result, _elapsed = ocr(arr)
            text = _clean_ocr_text(_join_ocr_lines(result or []))
            pages.append(PageText(page=idx, text=text))
            print(f"  page {idx}/{len(doc)}: {len(text)} chars", flush=True)
    finally:
        doc.close()
    return pages


def _join_ocr_lines(result: list) -> str:
    # rapidocr returns [ [bbox, text, confidence], ... ] roughly in reading
    # order. Keep ordering, drop low-confidence tokens, rebuild with line
    # breaks so the chunker can still see paragraph structure.
    lines: list[str] = []
    for entry in result:
        if not entry or len(entry) < 3:
            continue
        text, conf = entry[1], entry[2]
        if not isinstance(text, str) or not text.strip():
            continue
        try:
            confidence = float(conf)
        except (TypeError, ValueError):
            confidence = 1.0
        if confidence < 0.4:
            continue
        lines.append(text.strip())
    return "\n".join(lines)


def _clean_ocr_text(text: str) -> str:
    text = _OCR_NOISE.sub(" ", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    cleaned_lines = []
    for line in text.split("\n"):
        line = re.sub(r"\s+", " ", line).strip()
        if line and len(line) >= 2:
            cleaned_lines.append(line)
    return "\n".join(cleaned_lines)


def _chunk_page(page: PageText) -> Iterable[tuple[str, int]]:
    text = page.text
    if len(text) < MIN_CHUNK_CHARS:
        return
    start = 0
    n = len(text)
    while start < n:
        end = min(start + CHUNK_CHAR_LIMIT, n)
        if end < n:
            window = text[start:end]
            snap = max(window.rfind("\n"), window.rfind("。"), window.rfind("；"))
            if snap >= MIN_CHUNK_CHARS:
                end = start + snap + 1
        chunk = text[start:end].strip()
        if len(chunk) >= MIN_CHUNK_CHARS:
            yield chunk, page.page
        if end >= n:
            break
        start = max(end - CHUNK_OVERLAP, start + 1)


def _tokenise(text: str) -> list[str]:
    tokens: list[str] = []
    for tok in jieba.cut_for_search(text):
        tok = tok.strip()
        if not tok:
            continue
        if re.fullmatch(r"[\W_]+", tok):
            continue
        tokens.append(tok.lower())
    return tokens


def build_index(pdf_path: Path = DEFAULT_PDF, output_path: Path = DEFAULT_OUTPUT) -> dict:
    print(f"rendering + OCR'ing {pdf_path}", flush=True)
    pages = _ocr_pdf(pdf_path)
    chunks: list[dict] = []
    for page in pages:
        for chunk_text, source_page in _chunk_page(page):
            tokens = _tokenise(chunk_text)
            if not tokens:
                continue
            chunks.append(
                {
                    "id": f"p{source_page:03d}_c{len(chunks):04d}",
                    "text": chunk_text,
                    "source_page": source_page,
                    "tokens": tokens,
                }
            )

    payload = {
        "version": INDEX_VERSION,
        "source_pdf": pdf_path.name,
        "chunk_char_limit": CHUNK_CHAR_LIMIT,
        "chunk_overlap": CHUNK_OVERLAP,
        "chunks": chunks,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the tenancy RAG index.")
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    payload = build_index(args.pdf, args.out)
    print(
        f"wrote {args.out} — {len(payload['chunks'])} chunks from {payload['source_pdf']}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
