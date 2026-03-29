EXTRACTION_PROMPT = """You are an information extraction assistant for Hong Kong rental cases.

Extract the following fixed fields from the provided text and return JSON only.
Allowed fields:
- monthly_rent
- deposit
- agent_fee
- management_fee_included
- rates_included
- lease_term
- move_in_date
- furnished
- repair_responsibility

Rules:
1) Return JSON only.
2) Do not add extra keys.
3) If a value is missing or unclear, set it to "unknown".
4) Keep values short but informative.
5) For monetary values, include the currency symbol ($) if present.
6) For dates, use standard formats (e.g., "2025-05-01" or "May 1, 2025").
7) For "furnished", extract specific items mentioned (e.g., "AC, fridge, washer") or "unfurnished".
8) For "rates_included", indicate whether government rates (差饷) are included in rent (e.g., "yes", "no", "landlord pays").

Text:
{text}
"""


FOLLOWUP_QUESTION_PROMPT = """You are helping a tenant ask follow-up questions for a Hong Kong rental property.

Given the missing fields and risk items, generate 3 to 5 short, polite questions
that can be sent to an agent or landlord. Questions should be:
1. Specific and actionable
2. Polite but direct
3. Covering the most important gaps or concerns
4. Written in {language}

Return JSON only in this format:
{{"questions": ["...", "..."]}}

Missing fields:
{missing_fields}

Risks:
{risks}
"""


COMPARISON_SUMMARY_PROMPT = """You summarize a computed listing comparison for Hong Kong rental properties.

Write one concise sentence in English highlighting the key difference or recommendation.
Do not invent numbers. Use only given facts.
Focus on: price difference, completeness of information, or risk levels.

Comparison data:
{comparison_data}
"""


MULTI_COMPARISON_SUMMARY_PROMPT = """You are summarizing a comparison of {n} Hong Kong rental listings.

Listings data:
{listings_data}

Comparison results:
{comparison_result}

Write 2-3 sentences in {language} highlighting:
1. The best overall choice and why
2. Key trade-offs between top options
3. What the user should consider when deciding

Be concise and actionable. Do not invent numbers.
"""


# ==================== 新增提示词 ====================

PRICE_ANALYSIS_PROMPT = """You are a Hong Kong rental market expert.

Analyze the following rent price for reasonableness. Consider:
- Typical rental ranges in Hong Kong districts
- Property type and size implications
- Current market conditions

Rent: {monthly_rent}
Area: {area}
Property Type: {property_type}

Respond with JSON:
{{
    "assessment": "below_market|normal|above_market|uncertain",
    "market_range": "e.g., $15,000 - $20,000",
    "reasoning": "brief explanation"
}}
"""


FACILITY_ANALYSIS_PROMPT = """You are analyzing rental property facilities in Hong Kong.

Given the furnished/amenities information, extract:
1. What appliances/furniture are included
2. What might be missing for comfortable living
3. Any unusual inclusions or exclusions

Information: {furnished_info}

Respond with JSON:
{{
    "included_items": ["item1", "item2"],
    "missing_essentials": ["item1"],
    "notes": "any observations"
}}
"""


LISTING_NAME_PROMPT = """你是香港租房助手，请为房源生成一个简短、易识别的中文名称。

**命名原则**：
1. 长度控制在15个字符以内
2. 优先包含：区域、价格、房型等关键信息
3. 如果信息不全，用已有信息生成，不要猜测缺失信息
4. 名称要能帮助用户快速识别是哪套房

**原始房源文本**：
{combined_text}

**已提取的结构化信息**：
- 月租：{monthly_rent}
- 租期：{lease_term}
- 家具：{furnished}

请直接输出JSON格式：
{{"name": "生成的中文名称"}}
"""

