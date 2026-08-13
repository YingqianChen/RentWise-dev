"""LLM prompt templates for extraction and analysis."""

EXTRACTION_PROMPT = """Extract source-backed facts from the Hong Kong rental evidence below.
Each source has a stable identifier. Do not combine sources into a single answer and do not decide which source is newer or more trustworthy.

Important rules:
1. For each direct or reasonably inferred claim about one of the 14 core fields, return one field_claims item. Return no placeholder claim for a missing field.
2. The 14 allowed field_key values are: monthly_rent, management_fee_amount, management_fee_included, rates_amount, rates_included, deposit, agent_fee, lease_term, move_in_date, repair_responsibility, district, address_text, building_name, nearest_station.
3. Copy a short quote verbatim from the named source. The quote must occur in that exact source. Never invent or paraphrase a quote.
4. source_type must be listing, chat, note, or image_ocr. For image_ocr, copy its UUID into source_asset_id. For every other source type, source_asset_id must be null.
5. claim_kind is explicit only when the source directly states the value. Use inferred when interpretation is required. Do not turn an inferred claim into an explicit one merely because it seems likely.
6. Return money values as non-negative JSON numbers without currency symbols or commas. Return included fields as JSON booleans. Return every other core value as concise text.
7. Preserve separate contradictory claims. The application, not you, will calculate the final conflict state.
8. Relative timing such as "available at semester start" is valid text. A repair note such as "owner covers repairs" is also valid text.
9. The supplemental object preserves a few existing non-core observations. Use "unknown" when absent. decision_signals and raw_facts must stay grounded in the supplied sources.

Evidence:
{text}

Return JSON only in this shape:
{{
    "field_claims": [
        {{
            "field_key": "one of the 14 allowed keys",
            "value": "typed value: number, boolean, or text as required by the field",
            "source_type": "listing/chat/note/image_ocr",
            "source_asset_id": "image UUID when source_type is image_ocr, otherwise null",
            "quote": "short verbatim quote from that exact source",
            "claim_kind": "explicit/inferred",
            "confidence": "high/medium/low"
        }}
    ],
    "supplemental": {{
        "furnished": "Furniture and appliance status or unknown",
        "size_sqft": "Size in square feet or unknown",
        "bedrooms": "Number of bedrooms or room type or unknown",
        "suspected_sdu": true/false/unknown,
        "sdu_detection_reason": "Short source-grounded reason or unknown",
        "decision_signals": [
            {{
                "key": "One of commute_advantage, building_amenity, condition_positive, bathroom_sharing, listing_ambiguity, source_conflict, holding_fee_risk, agent_pressure, trust_concern, fee_discount, photo_quality_concern, repair_support_signal, move_in_timing_signal, other_decision_signal",
                "category": "One of fit, building, condition, living_arrangement, conflict, trust, cost, timing, other",
                "label": "Short neutral label under 60 characters",
                "source": "listing/chat/note/ocr/mixed",
                "evidence": "Short quote or paraphrase grounded in the evidence",
                "note": "Optional short explanation of why this matters, or null"
            }}
        ],
        "raw_facts": [
            "Short neutral factual observation under 25 words that does not duplicate a core field."
        ]
    }}
}}
"""


LISTING_NAME_PROMPT = """Based on the rental information below, generate a short, readable listing name.

Rules:
1. Keep it under 20 characters when possible.
2. Prefer district and rent if available.
3. Do not invent missing facts.
4. Return JSON only.

Text:
{combined_text}

Monthly rent: {monthly_rent}
Lease term: {lease_term}
Furnishing: {furnished}

Return:
{{"name": "Generated listing name"}}
"""


FOLLOWUP_QUESTION_PROMPT = """Given the missing fields and risk items below, generate up to three practical follow-up questions for the user to ask the landlord or agent.

Missing fields: {missing_fields}
Risks:
{risks}

Write the questions in {language} and return JSON only:
{{"questions": ["Question 1", "Question 2"]}}
"""


COST_ASSESSMENT_PROMPT = """Analyze the rental cost information below and estimate cost clarity and risk.

Monthly rent: {monthly_rent}
Management fee: {management_fee_amount} (included in rent: {management_fee_included})
Rates: {rates_amount} (included in rent: {rates_included})
Deposit: {deposit}
Agent fee: {agent_fee}
User budget cap: {max_budget}

Return JSON only:
{{
    "known_monthly_cost": "Known monthly total as a number, or null",
    "monthly_cost_confidence": "high/medium/low",
    "monthly_cost_missing_items": ["missing cost fields"],
    "move_in_cost_known_part": "Known upfront move-in cost as a number, or null",
    "move_in_cost_confidence": "high/medium/low",
    "cost_risk_flag": "none/incomplete/possible_additional_cost/over_budget",
    "summary": "Short English summary of the cost assessment"
}}
"""


CLAUSE_ASSESSMENT_PROMPT = """Analyze the rental clause risk from the information below.

Repair responsibility: {repair_responsibility}
Lease term: {lease_term}
Move-in date: {move_in_date}
Target move-in date: {move_in_target}

Return JSON only:
{{
    "repair_responsibility_level": "clear/unclear/tenant_heavy/unknown",
    "lease_term_level": "standard/rigid/unstable/unknown",
    "move_in_date_level": "fit/mismatch/uncertain/unknown",
    "clause_confidence": "high/medium/low",
    "clause_risk_flag": "none/needs_confirmation/high_risk",
    "summary": "Short English summary of the clause assessment"
}}
"""


CANDIDATE_ASSESSMENT_PROMPT = """Evaluate the rental candidate below.

Cost assessment:
- Known monthly cost: {known_monthly_cost}
- Cost confidence: {monthly_cost_confidence}
- Cost risk: {cost_risk_flag}

Clause assessment:
- Repair responsibility: {repair_responsibility_level}
- Lease term: {lease_term_level}
- Move-in timing: {move_in_date_level}
- Clause risk: {clause_risk_flag}

User preferences:
- Budget cap: {max_budget}
- Must have: {must_have}
- Deal breakers: {deal_breakers}
- Preferred districts: {preferred_districts}
- Actual district: {district}

Return JSON only:
{{
    "potential_value_level": "high/medium/low/unknown",
    "completeness_level": "high/medium/low",
    "critical_uncertainty_level": "high/medium/low",
    "decision_risk_level": "high/medium/low/unknown",
    "information_gain_level": "high/medium/low",
    "recommendation_confidence": "high/medium/low",
    "next_best_action": "verify_cost/verify_clause/schedule_viewing/keep_warm/reject",
    "status": "new/needs_info/follow_up/high_risk_pending/recommended_reject",
    "labels": ["label_1", "label_2"],
    "summary": "Short English summary under 100 words"
}}

Important rules:
1. If key cost fields are missing, recommendation_confidence must not be high.
2. If key clauses are unclear, recommendation_confidence must not be high.
3. If the candidate conflicts with hard user constraints, reject is allowed.
4. If the candidate has upside but key information is still missing, next_best_action should be verify_cost or verify_clause.
"""


DASHBOARD_ADVICE_PROMPT = """You are a rental research assistant. Based on the current candidate pool, give a short recommendation about what the user should focus on now.

Candidate pool stats:
- Total: {total}
- New: {new}
- Needs info: {needs_info}
- Follow-up: {follow_up}
- Shortlisted: {shortlisted}
- Rejected: {rejected}

Priority candidates:
{priority_candidates_info}

Open investigation items:
{open_items_info}

Write a concise English recommendation under 150 words.
"""


COMPARE_BRIEFING_PROMPT = """You are helping a renter compare a shortlist of Hong Kong rental candidates.

You will receive a structured comparison result. Do not invent facts and do not change the underlying compare decision.
Your job is to turn the structured result into a short, practical briefing.

Project context:
{project_context}

Compare summary:
{compare_summary}

Decision groups:
{decision_groups}

Key differences:
{key_differences}

Recommended next actions:
{recommended_actions}

Return JSON only in this format:
{{
    "current_take": "One or two sentences explaining the current lead or why no lead exists yet.",
    "why_now": "Explain why this is the current judgment, grounded in clarity, fit, and decision readiness.",
    "what_could_change": "Explain what missing information or blocker could still change the outcome.",
    "today_s_move": "Explain the most useful next move the user should take today.",
    "confidence_note": "Short note about how stable or unstable the current judgment is."
}}

Writing rules:
1. Write concise English.
2. Keep each field under 60 words.
3. Do not mention JSON, scores, or internal code names unless unavoidable.
4. Be specific about tradeoffs and blockers.
5. If the shortlist has no clear lead, say that directly.
"""


CONTACT_PLAN_PROMPT = """You are helping a renter prepare the next message to a landlord or agent about one rental candidate.

Your job is not to repeat the current assessment. Your job is to turn the current uncertainty into a short outreach plan.

Project context:
{project_context}

Candidate context:
{candidate_context}

Current decision state:
{decision_context}

Known blockers and missing information:
{blockers_context}

Return JSON only in this format:
{{
    "contact_goal": "One sentence describing what this outreach should achieve.",
    "questions": ["Question 1", "Question 2", "Question 3"],
    "message_draft": "A short, polite English message the renter can send to the agent or landlord."
}}

Writing rules:
1. Keep the goal under 25 words.
2. Return 2 to 3 questions only.
3. Questions should be concrete and decision-relevant, not generic small talk.
4. The message draft should sound natural and ready to send.
5. Do not repeat the whole assessment summary.
6. Do not invent facts that are not in the provided context.
"""
