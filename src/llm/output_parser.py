"""
src/llm/output_parser.py
-------------------------
Parses and structures the raw LLM text response into typed recommendation objects.

Implements:
  - EC-306: Cross-reference candidate list to detect and flag hallucinated names
  - EC-501: Graceful fallback for unstructured or unformatted LLM text
  - EC-502: Handling of fewer recommendations than expected
  - EC-503: Cleaning markdown code block wrappers (```json, ```markdown)
  - EC-504: Basic content filter to sanitize inappropriate text
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

logger = logging.getLogger(__name__)

# Basic safety blocklist for content moderation check (EC-504)
_BANNED_WORDS = {
    "hate", "racist", "kill", "violent", "abuse", "scam", "poison", "toxic",
    "disgusting", "filthy", "vomit", "unsafe"
}


@dataclass
class RecommendationItem:
    """A single structured restaurant recommendation."""
    rank: int
    name: str
    cuisine: str = ""
    rating: float = 0.0
    cost: int = 0
    location: str = ""
    explanation: str = ""
    is_hallucinated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "name": self.name,
            "cuisine": self.cuisine,
            "rating": self.rating,
            "cost": self.cost,
            "location": self.location,
            "explanation": self.explanation,
            "is_hallucinated": self.is_hallucinated,
        }


@dataclass
class ParsedRecommendation:
    """The complete parsed result containing top recommendations and summary."""
    recommendations: list[RecommendationItem] = field(default_factory=list)
    summary: str = ""
    raw_response: str = ""
    is_fallback: bool = False
    error: str = ""

    @property
    def count(self) -> int:
        return len(self.recommendations)

    def to_dict(self) -> dict[str, Any]:
        return {
            "recommendations": [r.to_dict() for r in self.recommendations],
            "summary": self.summary,
            "is_fallback": self.is_fallback,
            "count": self.count,
            "error": self.error,
        }


def _strip_markdown_fences(text: str) -> str:
    """
    Remove surrounding markdown code blocks such as ```markdown ... ``` (EC-503).
    """
    cleaned = text.strip()
    # Remove outer triple backtick block if present
    match = re.match(r"^```(?:markdown|json|text)?\s*\n?(.*?)\n?```$", cleaned, re.DOTALL | re.IGNORECASE)
    if match:
        cleaned = match.group(1).strip()
    # Remove any stray triple backticks
    cleaned = re.sub(r"```[a-zA-Z]*", "", cleaned)
    return cleaned.strip()


def _moderate_text(text: str) -> str:
    """
    Sanitize text if offensive words are detected (EC-504).
    """
    lower = text.lower()
    for word in _BANNED_WORDS:
        # Match whole word
        if re.search(r"\b" + re.escape(word) + r"\b", lower):
            logger.warning("Content filter triggered on word '%s'. Sanitizing.", word)
            return "Recommendation explanation is unavailable for this entry."
    return text


def _extract_field(block: str, patterns: list[str], default: str = "") -> str:
    """Helper to extract a bullet-pointed field from a restaurant section."""
    for pat in patterns:
        m = re.search(pat, block, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return default


def _match_with_candidates(
    name: str,
    candidates: Sequence[dict[str, Any]]
) -> tuple[bool, Optional[dict[str, Any]]]:
    """
    Cross-reference an extracted restaurant name against candidate list (EC-306).
    Returns (is_hallucinated, matched_candidate_dict).
    """
    if not candidates:
        return False, None

    clean_target = re.sub(r"[^\w\s]", "", name.lower()).strip()
    for c in candidates:
        c_name = str(c.get("name", "")).strip()
        clean_c = re.sub(r"[^\w\s]", "", c_name.lower()).strip()
        # Exact or substring match in either direction
        if clean_target == clean_c or clean_target in clean_c or clean_c in clean_target:
            return False, c

    return True, None


def parse_output(
    raw_text: str,
    candidates: Optional[Sequence[dict[str, Any]]] = None,
    supplement_threshold: int = 3,
) -> ParsedRecommendation:
    """
    Parse the LLM text output into structured recommendations.

    Parameters
    ----------
    raw_text : str
        The raw response text from the LLM.
    candidates : Optional[Sequence[dict]]
        Original candidate restaurants from the filtering layer for cross-referencing.
    supplement_threshold : int
        If parsed items are fewer than this, supplement from candidates if available (EC-502).

    Returns
    -------
    ParsedRecommendation
        Container with list of RecommendationItem objects and comparative summary.
    """
    if not raw_text or not raw_text.strip():
        logger.warning("Empty LLM output passed to parser.")
        return ParsedRecommendation(
            raw_response="",
            is_fallback=True,
            error="LLM returned an empty response.",
        )

    clean_text = _strip_markdown_fences(raw_text)

    # 1. Extract Summary section if present
    summary_match = re.search(
        r"###\s*(?:Summary|Overview|Conclusion)\s*\n+(.+?)(?=\n###|\Z)",
        clean_text,
        re.DOTALL | re.IGNORECASE,
    )
    summary = ""
    if summary_match:
        summary = summary_match.group(1).strip()
        # Remove the summary block from restaurant matching
        content_for_items = clean_text[:summary_match.start()]
    else:
        content_for_items = clean_text

    # 2. Extract Restaurant sections (splits by ### header or numbered headings)
    # Patterns like: "### 1. Restaurant Name" or "### [1] Restaurant Name" or "### Restaurant Name"
    item_header_pattern = re.compile(
        r"###\s*(?:(?:#|\b)?(\d+)[\.\)\]\-:]*\s*)?(.+?)(?=\n|$)",
        re.MULTILINE,
    )

    headers = list(item_header_pattern.finditer(content_for_items))
    items: list[RecommendationItem] = []

    if headers:
        for i, h in enumerate(headers):
            # Header text
            rank_str = h.group(1)
            raw_name = h.group(2).strip()

            # Skip if this is a meta-header (like "Summary", "Preferences", etc.)
            if raw_name.lower().startswith(("summary", "user preference", "candidate", "recommendation")):
                continue

            rank = int(rank_str) if rank_str else (len(items) + 1)
            # Clean name from brackets, quotes, or trailing markdown
            name = re.sub(r"^\[|\]$|^\"|\"$|^\'|\'$", "", raw_name).strip()
            name = re.sub(r"^\d+[\.\)\-]\s*", "", name).strip()

            # Section text until next header or end
            start_pos = h.end()
            end_pos = headers[i + 1].start() if i + 1 < len(headers) else len(content_for_items)
            section_body = content_for_items[start_pos:end_pos].strip()

            # Extract fields
            cuisine = _extract_field(section_body, [
                r"\*\*Cuisine\*\*\s*:\s*(.+?)(?=\n|$)",
                r"Cuisine\s*:\s*(.+?)(?=\n|$)",
            ])
            location = _extract_field(section_body, [
                r"\*\*Location\*\*\s*:\s*(.+?)(?=\n|$)",
                r"Location\s*:\s*(.+?)(?=\n|$)",
            ])
            rating_str = _extract_field(section_body, [
                r"\*\*Rating\*\*\s*:\s*([\d\.]+)",
                r"Rating\s*:\s*([\d\.]+)",
            ])
            cost_str = _extract_field(section_body, [
                r"\*\*Estimated Cost\*\*\s*:\s*(?:Rs\.?\s*)?([\d,]+)",
                r"Cost\s*:\s*(?:Rs\.?\s*)?([\d,]+)",
            ])
            explanation = _extract_field(section_body, [
                r"\*\*Why we recommend it\*\*\s*:\s*(.+?)(?=\n-|\n###|\Z)",
                r"Why we recommend it\s*:\s*(.+?)(?=\n-|\n###|\Z)",
                r"Explanation\s*:\s*(.+?)(?=\n-|\n###|\Z)",
            ])

            # If explanation wasn't caught by key, take remaining text as explanation
            if not explanation:
                lines = [
                    line.strip("- *").strip()
                    for line in section_body.splitlines()
                    if line.strip() and not any(k in line.lower() for k in ["cuisine:", "rating:", "cost:", "location:"])
                ]
                explanation = " ".join(lines)

            # Apply content moderation check (EC-504)
            explanation = _moderate_text(explanation)

            # Cast numeric types safely
            rating = 0.0
            if rating_str:
                try:
                    rating = float(rating_str)
                except ValueError:
                    rating = 0.0

            cost = 0
            if cost_str:
                try:
                    cost = int(cost_str.replace(",", ""))
                except ValueError:
                    cost = 0

            # Cross-reference with candidate list (EC-306)
            is_hallucinated, matched_candidate = _match_with_candidates(name, candidates or [])

            # If matched candidate exists, backfill any missing metadata accurately
            if matched_candidate:
                if not cuisine:
                    cuisine = str(matched_candidate.get("cuisine", ""))
                if rating == 0.0 and matched_candidate.get("rating") is not None:
                    try:
                        rating = float(matched_candidate["rating"])
                    except (ValueError, TypeError):
                        pass
                if cost == 0 and matched_candidate.get("cost") is not None:
                    try:
                        cost = int(str(matched_candidate["cost"]).replace(",", ""))
                    except (ValueError, TypeError):
                        pass
                if not location:
                    location = str(matched_candidate.get("location", ""))

            items.append(
                RecommendationItem(
                    rank=rank,
                    name=name,
                    cuisine=cuisine,
                    rating=rating,
                    cost=cost,
                    location=location,
                    explanation=explanation,
                    is_hallucinated=is_hallucinated,
                )
            )

    # 3. Fallback for completely unstructured output (EC-501)
    if not items:
        logger.warning("[EC-501] LLM output had no recognizable headers. Using unstructured fallback.")
        fallback_explanation = _moderate_text(clean_text)
        first_candidate_name = candidates[0].get("name", "Top Match") if candidates else "Recommended Restaurant"
        items.append(
            RecommendationItem(
                rank=1,
                name=first_candidate_name,
                explanation=fallback_explanation,
            )
        )
        return ParsedRecommendation(
            recommendations=items,
            summary="Extracted from unstructured response.",
            raw_response=raw_text,
            is_fallback=True,
        )

    # 4. EC-502: If fewer than supplement_threshold and candidates available, supplement
    if candidates and len(items) < supplement_threshold:
        existing_names = {i.name.lower() for i in items}
        for cand in candidates:
            c_name = str(cand.get("name", ""))
            if c_name.lower() not in existing_names:
                try:
                    c_rating = float(cand.get("rating", 0.0))
                except (ValueError, TypeError):
                    c_rating = 0.0
                try:
                    c_cost = int(str(cand.get("cost", 0)).replace(",", ""))
                except (ValueError, TypeError):
                    c_cost = 0

                items.append(
                    RecommendationItem(
                        rank=len(items) + 1,
                        name=c_name,
                        cuisine=str(cand.get("cuisine", "")),
                        rating=c_rating,
                        cost=c_cost,
                        location=str(cand.get("location", "")),
                        explanation=f"Highly rated option matching your criteria ({c_name}).",
                        is_hallucinated=False,
                    )
                )
                if len(items) >= supplement_threshold:
                    break

    return ParsedRecommendation(
        recommendations=items,
        summary=summary,
        raw_response=raw_text,
        is_fallback=False,
    )
