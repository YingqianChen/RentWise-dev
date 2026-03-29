from typing import Dict, List

from models import UNKNOWN


def normalize_value(value: str) -> str:
    if not value:
        return UNKNOWN
    cleaned = value.strip()
    return cleaned if cleaned else UNKNOWN


def is_unknown(value: str) -> bool:
    return normalize_value(value).lower() == UNKNOWN


def build_combined_text(text_sections: Dict[str, str], ocr_texts: List[str]) -> str:
    parts: List[str] = []
    for name, value in text_sections.items():
        value = value.strip()
        if value:
            parts.append(f"[{name}]\n{value}")
    for idx, ocr_text in enumerate(ocr_texts, start=1):
        cleaned = ocr_text.strip()
        if cleaned:
            parts.append(f"[ocr_text_{idx}]\n{cleaned}")
    return "\n\n".join(parts)
