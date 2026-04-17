"""LLM prompt templates for extraction and analysis."""

EXTRACTION_PROMPT = """Extract the key rental fields from the Hong Kong rental evidence below.
The evidence may include listing copy, agent or landlord chat, tenant notes, and OCR text from screenshots.

Important rules:
1. You MUST return every key listed in the JSON schema below, in the exact order shown. Never skip a key. Use "unknown" only when the evidence is truly silent about that field.
2. Location fields (address_text, building_name, nearest_station, district) are especially important. If the evidence contains any building name, estate name, street, or station — even in English only — copy it into the matching field verbatim. Do not drop English place names.
3. Combine all sources into one current decision read. Do not assume the original listing is always the final truth.
4. If later chat or notes clarify a practical rental condition, you may use that clarification in the canonical field.
5. If sources conflict and you cannot safely resolve the current state, keep the canonical field conservative and add a decision signal about the conflict or ambiguity.
6. Relative timing notes such as "available at semester start", "move in at the start of school", or "after finals" are still usable timing notes. Do not mark them unknown just because they are not exact calendar dates.
7. Notes such as "school dorm, maintenance included", "owner covers repairs", or "landlord handles repairs" should not be treated as unknown repair responsibility.
8. decision_signals is only for the predefined keys listed below. Return an empty list when there is nothing clearly decision-relevant.
9. raw_facts is for any factual observation that does not fit the typed fields above but might still matter to the tenant (e.g. "landlord is the owner, not an agent", "unit renovated last year", "photos show air-conditioner in every room", "chat mentions pet-friendly"). Do NOT repeat facts already captured in the typed fields. Return an empty list if nothing noteworthy.

Evidence:
{text}

Return JSON only with these fields, in this exact order:
{{
    "address_text": "Best available address or partial address from the evidence. Prefer Chinese when available for geocoding accuracy (e.g. 彌敦道123號旺角). If only English is available, include it as-is (e.g. 123 Nathan Road Mong Kok). Return unknown if missing.",
    "building_name": "Building or estate name if mentioned. Prefer Chinese when available (e.g. 沙田第一城, 美孚新邨). If only English, include as-is (e.g. City One Shatin). Return unknown if missing.",
    "nearest_station": "Nearest MTR or transport station if mentioned or clearly implied. Prefer Chinese when available (e.g. 旺角東站, 沙田站). If only English, include as-is (e.g. Mong Kok East). Return unknown if missing.",
    "district": "District or area name",
    "location_confidence": "high if full or partial address is available, medium if building name or station is available but no street address, low if only district or vague area hint, unknown if no location information at all",
    "monthly_rent": "Monthly rent including currency symbol when available, e.g. $15000 or HKD 15,000",
    "management_fee_amount": "Management fee amount",
    "management_fee_included": true/false/unknown,
    "rates_amount": "Government rates amount",
    "rates_included": true/false/unknown,
    "deposit": "Deposit amount or months of rent",
    "agent_fee": "Agent fee amount",
    "lease_term": "A short normalized lease note, e.g. 2 years, 1 year fixed 1 year optional, monthly rolling, no break clause, short-term only, or unknown",
    "move_in_date": "A short normalized availability note, e.g. available now, available from May 2026, ready after current tenant leaves, negotiable timing, or unknown",
    "repair_responsibility": "A short normalized note about who appears to handle repairs, e.g. landlord handles major repairs, tenant pays minor repairs, agency says owner will cover repairs, or unknown",
    "furnished": "Furniture and appliance status",
    "size_sqft": "Size in square feet",
    "bedrooms": "Number of bedrooms or room type",
    "suspected_sdu": true/false/unknown,
    "sdu_detection_reason": "Short reason such as keyword_match, room_only_layout, or unknown",
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
        "Short neutral factual observation under 25 words, grounded in the evidence."
    ]
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
    "cost_risk_flag": "none/possible_additional_cost/hidden_cost_risk/over_budget",
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
    "potential_value_level": "high/medium/low",
    "completeness_level": "high/medium/low",
    "critical_uncertainty_level": "high/medium/low",
    "decision_risk_level": "high/medium/low",
    "information_gain_level": "high/medium/low",
    "recommendation_confidence": "high/medium/low",
    "next_best_action": "verify_cost/verify_clause/schedule_viewing/keep_warm/reject",
    "status": "new/needs_info/follow_up/high_risk_pending/recommended_reject/shortlisted",
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
