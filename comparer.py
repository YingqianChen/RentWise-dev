import re
from typing import Dict, Optional, List, Any

from llm_utils import chat_completion
from models import ListingInfo
from prompts import COMPARISON_SUMMARY_PROMPT, MULTI_COMPARISON_SUMMARY_PROMPT


def _parse_hkd_amount(text: str) -> Optional[float]:
    digits = re.findall(r"\d+(?:,\d{3})*(?:\.\d+)?", text.replace("HK$", ""))
    if not digits:
        return None
    try:
        return float(digits[0].replace(",", ""))
    except ValueError:
        return None


def compare_listings(
    listing_a: ListingInfo,
    listing_b: ListingInfo,
    missing_count_a: int,
    missing_count_b: int,
    risk_count_a: int,
    risk_count_b: int,
) -> Dict[str, str]:
    rent_a = _parse_hkd_amount(listing_a.monthly_rent)
    rent_b = _parse_hkd_amount(listing_b.monthly_rent)

    if rent_a is None or rent_b is None:
        cheaper = "unknown"
    elif rent_a < rent_b:
        cheaper = "A"
    elif rent_b < rent_a:
        cheaper = "B"
    else:
        cheaper = "same"

    if missing_count_a < missing_count_b:
        more_complete = "A"
    elif missing_count_b < missing_count_a:
        more_complete = "B"
    else:
        more_complete = "same"

    if risk_count_a < risk_count_b:
        lower_risk = "A"
    elif risk_count_b < risk_count_a:
        lower_risk = "B"
    else:
        lower_risk = "same"

    return {
        "cheaper_listing": cheaper,
        "more_complete_listing": more_complete,
        "lower_risk_listing": lower_risk,
    }


def _rank_values(values: List, lower_better: bool = True) -> List[int]:
    """Rank values, handling None/unknown. 1 = best rank"""
    n = len(values)
    # Handle None values by treating them as worst
    valid_indices = [(i, v) for i, v in enumerate(values) if v is not None and v != 0]

    if not valid_indices:
        return [n] * n  # All tied for worst

    sorted_indices = sorted(valid_indices, key=lambda x: x[1], reverse=not lower_better)
    rankings = [n + 1] * n  # Default to worst rank

    for rank, (idx, _) in enumerate(sorted_indices, 1):
        rankings[idx] = rank

    return rankings


def compare_multiple_listings(
    listings: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Compare multiple listings and generate structured comparison.

    Args:
        listings: List of dicts with keys:
            - listing_info: ListingInfo object
            - missing_count: int
            - risk_count: int
            - match_score: float (0-100)

    Returns:
        Dict with comparison_matrix, rankings, overall_scores, best_overall_index
    """
    n = len(listings)
    if n < 2:
        raise ValueError("At least 2 listings required for comparison")

    # Extract metrics for each listing
    monthly_rents = []
    deposits = []
    missing_counts = []
    risk_counts = []
    match_scores = []

    for listing_data in listings:
        info = listing_data["listing_info"]
        monthly_rents.append(_parse_hkd_amount(info.monthly_rent))
        deposits.append(info.deposit)
        missing_counts.append(listing_data["missing_count"])
        risk_counts.append(listing_data["risk_count"])
        match_scores.append(listing_data.get("match_score") or 0)

    # Calculate rankings (1 = best)
    price_rankings = _rank_values(monthly_rents, lower_better=True)
    completeness_rankings = _rank_values(missing_counts, lower_better=True)
    risk_rankings = _rank_values(risk_counts, lower_better=True)
    match_rankings = _rank_values(match_scores, lower_better=False)

    # Calculate overall scores (weighted average: price 25%, completeness 20%, risk 25%, match 30%)
    overall_scores = []
    for i in range(n):
        # Use normalized rank (lower is better, so invert)
        price_score = (n - price_rankings[i] + 1) / n * 25
        completeness_score = (n - completeness_rankings[i] + 1) / n * 20
        risk_score = (n - risk_rankings[i] + 1) / n * 25
        match_score = (n - match_rankings[i] + 1) / n * 30
        overall_scores.append(price_score + completeness_score + risk_score + match_score)

    best_overall = overall_scores.index(max(overall_scores))

    return {
        "comparison_matrix": {
            "monthly_rents": monthly_rents,
            "deposits": deposits,
            "missing_counts": missing_counts,
            "risk_counts": risk_counts,
            "match_scores": match_scores,
        },
        "rankings": {
            "price_rankings": price_rankings,
            "completeness_rankings": completeness_rankings,
            "risk_rankings": risk_rankings,
            "match_rankings": match_rankings,
        },
        "overall_scores": overall_scores,
        "best_overall_index": best_overall,
    }


def summarize_multi_comparison(
    listings_data: List[Dict[str, Any]],
    comparison_result: Dict[str, Any],
    model: str,
    lang: str = "en"
) -> str:
    """Generate LLM summary for multi-property comparison"""
    prompt = MULTI_COMPARISON_SUMMARY_PROMPT.format(
        n=len(listings_data),
        listings_data=_format_listings_for_prompt(listings_data),
        comparison_result=comparison_result,
        language="English" if lang == "en" else ("简体中文" if lang == "zh-cn" else "繁體中文")
    )
    return chat_completion(prompt=prompt, model=model, temperature=0.3, max_tokens=200).strip()


def _format_listings_for_prompt(listings: List[Dict[str, Any]]) -> str:
    """Format listings data for prompt"""
    lines = []
    for i, l in enumerate(listings):
        info = l["listing_info"]
        lines.append(
            f"Listing {i+1}: Rent={info.monthly_rent}, "
            f"Missing={l['missing_count']}, Risks={l['risk_count']}, "
            f"Match={l.get('match_score', 0)}%"
        )
    return "\n".join(lines)


def summarize_comparison(comparison_data: Dict[str, str], model: str) -> str:
    prompt = COMPARISON_SUMMARY_PROMPT.format(comparison_data=comparison_data)
    return chat_completion(prompt=prompt, model=model, temperature=0.2, max_tokens=60).strip()
