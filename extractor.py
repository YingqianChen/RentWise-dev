from typing import Dict, List

from llm_utils import chat_completion_json
from models import ListingInfo, RiskItem
from prompts import EXTRACTION_PROMPT, FOLLOWUP_QUESTION_PROMPT, LISTING_NAME_PROMPT
from utils import normalize_value


FIELD_NAMES = [
    "monthly_rent",
    "deposit",
    "agent_fee",
    "management_fee_included",
    "rates_included",
    "lease_term",
    "move_in_date",
    "furnished",
    "repair_responsibility",
]


def extract_listing_info(text: str, model: str) -> ListingInfo:
    prompt = EXTRACTION_PROMPT.format(text=text)
    data = chat_completion_json(prompt=prompt, model=model, temperature=0.0)
    normalized: Dict[str, str] = {}
    for field in FIELD_NAMES:
        normalized[field] = normalize_value(str(data.get(field, "unknown")))
    return ListingInfo(**normalized)


def generate_follow_up_questions(
    missing_fields: List[str], risks: List[RiskItem], model: str, lang: str = "zh-cn"
) -> List[str]:
    # 语言映射
    language_map = {
        "zh-cn": "简体中文",
    }
    language = language_map.get(lang, "简体中文")

    risk_lines = [f"{risk.level}: {risk.title} - {risk.description}" for risk in risks]
    prompt = FOLLOWUP_QUESTION_PROMPT.format(
        missing_fields=", ".join(missing_fields) if missing_fields else "none",
        risks="\n".join(risk_lines) if risk_lines else "none",
        language=language,
    )
    data = chat_completion_json(prompt=prompt, model=model, temperature=0.3)
    questions = data.get("questions", [])
    if not isinstance(questions, list):
        return []
    cleaned = [str(q).strip() for q in questions if str(q).strip()]
    return cleaned[:5]


def generate_listing_name(
    listing_info: ListingInfo,
    combined_text: str,
    model: str = "llama3.3:is6620"
) -> str:
    """
    使用LLM生成房源名称

    Args:
        listing_info: 房源信息
        combined_text: 原始文本（用于提取区域等信息）
        model: LLM模型名称

    Returns:
        生成的房源名称
    """
    # 截取文本前500字符，避免 prompt 过长
    text_preview = combined_text[:500] if combined_text else "无房源描述"

    prompt = LISTING_NAME_PROMPT.format(
        combined_text=text_preview,
        monthly_rent=listing_info.monthly_rent or "未知",
        lease_term=listing_info.lease_term or "未知",
        furnished=listing_info.furnished or "未知"
    )

    try:
        result = chat_completion_json(prompt=prompt, model=model, temperature=0.3)
        name = result.get("name", "")
        if name and len(name) <= 20:
            return name.strip()
    except Exception as e:
        print(f"Failed to generate listing name: {e}")

    # 回退：智能生成名称
    return _generate_fallback_name(listing_info, combined_text)


def _generate_fallback_name(listing_info: ListingInfo, combined_text: str) -> str:
    """回退命名策略：根据已有信息智能生成"""
    parts = []

    # 尝试提取区域
    area_keywords = [
        ("旺角", ["旺角", "mong kok", "mongkok"]),
        ("铜锣湾", ["铜锣湾", "銅鑼灣", "causeway bay"]),
        ("中环", ["中环", "中環", "central"]),
        ("湾仔", ["湾仔", "灣仔", "wan chai"]),
        ("尖沙咀", ["尖沙咀", "tsim sha tsui"]),
        ("深水埗", ["深水埗", "sham shui po"]),
        ("观塘", ["观塘", "觀塘", "kwun tong"]),
        ("沙田", ["沙田", "sha tin"]),
        ("荃湾", ["荃湾", "荃灣", "tsuen wan"]),
        ("屯门", ["屯门", "屯門", "tuen mun"]),
        ("元朗", ["元朗", "yuen long"]),
        ("北角", ["北角", "north point"]),
        ("红磡", ["红磡", "紅磡", "hung hom"]),
        ("坚尼地城", ["坚尼地城", "堅尼地城", "kennedy town"]),
        ("九龙城", ["九龙城", "九龍城", "kowloon city"]),
    ]

    text_lower = combined_text.lower() if combined_text else ""
    for area_name, keywords in area_keywords:
        if any(kw in text_lower for kw in keywords):
            parts.append(area_name)
            break

    # 添加月租
    if listing_info.monthly_rent and listing_info.monthly_rent != "unknown":
        rent = listing_info.monthly_rent.replace("$", "").replace("HKD", "").replace(",", "").strip()
        if rent:
            parts.append(f"${rent}")

    # 如果有家具信息，尝试提取房间数
    if listing_info.furnished and listing_info.furnished != "unknown":
        furnished = listing_info.furnished
        if "房" in furnished:
            # 尝试提取几房
            import re
            match = re.search(r"(\d)\s*房", furnished)
            if match:
                parts.append(f"{match.group(1)}房")

    # 组合名称
    if parts:
        name = " ".join(parts)
    else:
        # 最后的回退：使用时间戳
        from datetime import datetime
        name = f"房源{datetime.now().strftime('%m%d%H%M')}"

    return name[:20]  # 限制长度
