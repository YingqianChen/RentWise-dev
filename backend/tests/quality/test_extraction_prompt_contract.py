"""Protect the explicit Hong Kong rental shorthand guidance in the prompt."""

from app.integrations.llm.prompts import EXTRACTION_PROMPT


def test_extraction_prompt_covers_hk_rental_shorthand() -> None:
    required_phrases = (
        "押2按1",
        "兩按一上",
        "免佣",
        "半佣",
        "差餉由業主負責",
        "租客自付",
        "無傢俬",
        "傢俬齊備",
        "劏房",
        "Do not infer that utilities include rates",
    )

    for phrase in required_phrases:
        assert phrase in EXTRACTION_PROMPT
