"""LLM深度风险分析模块 - 混合智能方案"""

from typing import List, Dict, Any

from llm_utils import chat_completion_json
from models import ListingInfo, RiskItem


DEEP_ANALYSIS_PROMPT = """You are a rental risk analysis expert for Hong Kong properties.

Analyze the following rental listing text and extracted information to identify HIDDEN RISKS that may not be obvious from missing fields alone.

Consider these risk categories:
1. FINANCIAL RISKS: Unusual payment terms, suspicious pricing, hidden costs
2. PRACTICAL RISKS: Unrealistic move-in dates, problematic facilities
3. FRAUD WARNING SIGNS: Warning signs of potential scams

Rules:
1. Only flag issues that are ACTUALLY PRESENT in the text
2. Do NOT invent risks that aren't supported by evidence
3. Use specific evidence from the text to support each risk
4. Distinguish between CERTAIN risks and SUSPICIOUS elements needing confirmation

Extracted Information:
- Monthly Rent: {monthly_rent}
- Deposit: {deposit}
- Agent Fee: {agent_fee}
- Management Fee Included: {management_fee_included}
- Lease Term: {lease_term}
- Move-in Date: {move_in_date}
- Furnished: {furnished}
- Repair Responsibility: {repair_responsibility}

Original Text:
{text}

IMPORTANT: Respond in {language}. Return JSON in this format:
{{
    "risks": [
        {{
            "level": "high|medium|low",
            "title": "Short risk title in {language}",
            "description": "Detailed explanation with specific evidence from text in {language}",
            "evidence": "Quote from text that supports this risk",
            "confidence": "certain|suspicious|uncertain"
        }}
    ]
}}

If no additional risks are found, return {{"risks": []}}.
"""

# Language mapping for prompts
LANGUAGE_NAMES = {
    "en": "English",
    "zh-cn": "简体中文 (Simplified Chinese)",
    "zh-hk": "繁體中文 (Traditional Chinese)"
}

# Confidence labels in different languages
CONFIDENCE_LABELS = {
    "en": {
        "suspicious": "[Needs Confirmation]",
        "uncertain": "[Uncertain]"
    },
    "zh-cn": {
        "suspicious": "[需要确认]",
        "uncertain": "[不确定]"
    },
    "zh-hk": {
        "suspicious": "[需要確認]",
        "uncertain": "[不確定]"
    }
}


def analyze_deep_risks(
    text: str,
    listing_info: ListingInfo,
    model: str = "llama3.3:is6620",
    lang: str = None
) -> List[RiskItem]:
    """
    使用LLM进行深度风险分析

    Args:
        text: 原始文本
        listing_info: 提取的房源信息
        model: LLM模型名称
        lang: 语言代码 (en, zh-cn, zh-hk)

    Returns:
        风险项目列表
    """
    # Determine language for response
    language = LANGUAGE_NAMES.get(lang, "English")

    prompt = DEEP_ANALYSIS_PROMPT.format(
        text=text[:4000],  # 限制长度避免超出token限制
        monthly_rent=listing_info.monthly_rent,
        deposit=listing_info.deposit,
        agent_fee=listing_info.agent_fee,
        management_fee_included=listing_info.management_fee_included,
        lease_term=listing_info.lease_term,
        move_in_date=listing_info.move_in_date,
        furnished=listing_info.furnished,
        repair_responsibility=listing_info.repair_responsibility,
        language=language
    )

    try:
        result = chat_completion_json(prompt=prompt, model=model, temperature=0.2)
        return _parse_risk_response(result, lang)
    except Exception as e:
        # LLM分析失败时返回空列表，不影响主流程
        print(f"LLM deep analysis failed: {e}")
        return []


def _parse_risk_response(data: Dict[str, Any], lang: str = "en") -> List[RiskItem]:
    """解析LLM返回的风险分析结果"""
    risks = []
    labels = CONFIDENCE_LABELS.get(lang, CONFIDENCE_LABELS["en"])

    raw_risks = data.get("risks", [])
    if not isinstance(raw_risks, list):
        return risks

    for item in raw_risks:
        if not isinstance(item, dict):
            continue

        level = item.get("level", "medium").lower()
        title = item.get("title", "Unknown Risk")
        description = item.get("description", "")
        evidence = item.get("evidence", "")
        confidence = item.get("confidence", "uncertain")

        # 验证level有效性
        if level not in ["high", "medium", "low"]:
            level = "medium"

        # 组合描述信息
        full_description = description
        if evidence:
            full_description += f" (Evidence: {evidence})"
        if confidence == "suspicious":
            full_description = f"{labels['suspicious']} {full_description}"
        elif confidence == "uncertain":
            full_description = f"{labels['uncertain']} {full_description}"

        risks.append(RiskItem(
            level=level,
            title=title,
            description=full_description,
            source="llm"
        ))

    return risks


def analyze_price_reasonableness(
    monthly_rent: str,
    area: str = "",
    property_type: str = "",
    model: str = "llama3.3:is6620"
) -> List[RiskItem]:
    """
    分析价格合理性（基于LLM知识）

    Note: 这是一个轻量级分析，仅供参考
    真实的价格比较需要接入实时市场数据
    """
    if monthly_rent == "unknown":
        return []

    prompt = f"""Given this Hong Kong rental property:
- Monthly Rent: {monthly_rent}
- Area: {area or "Unknown"}
- Property Type: {property_type or "Unknown"}

Is this rent amount suspiciously high or low for Hong Kong market?
Consider: General market rates in different districts.

Return JSON:
{{"assessment": "normal|high|low|uncertain", "reason": "brief explanation"}}

If uncertain, return {{"assessment": "uncertain", "reason": "Insufficient information"}}
"""

    try:
        result = chat_completion_json(prompt=prompt, model=model, temperature=0.1)
        assessment = result.get("assessment", "uncertain")
        reason = result.get("reason", "")

        if assessment == "high":
            return [RiskItem(
                level="medium",
                title="Rent appears above market rate",
                description=reason or "The rent may be higher than typical for this area.",
                source="llm"
            )]
        elif assessment == "low":
            return [RiskItem(
                level="medium",
                title="Rent appears below market rate",
                description=reason or "Unusually low rent may indicate issues. Verify property details.",
                source="llm"
            )]
    except Exception:
        pass

    return []
