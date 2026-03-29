from functools import lru_cache
from io import BytesIO
from typing import List

import easyocr
import numpy as np
from PIL import Image


@lru_cache(maxsize=1)
def get_reader() -> easyocr.Reader:
    # English + Simplified Chinese + Traditional Chinese are useful for HK content.
    return easyocr.Reader(["en", "ch_tra"], gpu=False)


def extract_text_from_image_bytes(image_bytes: bytes) -> str:
    image = Image.open(BytesIO(image_bytes)).convert("RGB")
    image_array = np.array(image)
    reader = get_reader()
    results = reader.readtext(image_array, detail=0, paragraph=True)
    return clean_ocr_text(results)


def clean_ocr_text(lines: List[str]) -> str:
    cleaned_lines = [line.strip() for line in lines if line and line.strip()]
    return "\n".join(cleaned_lines)