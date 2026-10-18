"""
src/orchestrator.py
--------------------
Main Pipeline Coordinator (Phase 4).
Bridges data ingestion, rule-based filtering, prompt engineering,
LLM querying, and output parsing into a single unified service.

Implements:
  - EC-601: Guard against None or empty return from filter engine
  - EC-602: Graceful fallback recommendations if LLM call fails
  - EC-603: Stateless design safe for multi-threaded / concurrent UI queries
  - EC-701: Location required validation
  - Detailed timing metrics and telemetry for every pipeline stage
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import pandas as pd

from src.filtering.filter_engine import filter_restaurants
from src.filtering.models import FilterResult, UserPreferences
from src.ingestion.loader import load_clean_dataset
from src.llm.engine import LLMEngine
from src.llm.output_parser import (
    ParsedRecommendation,
    RecommendationItem,
    parse_output,
)
from src.llm.prompt_builder import build_prompt

logger = logging.getLogger(__name__)


# ── RecommendationResult Data Model ──────────────────────────────────────────

@dataclass
class RecommendationResult:
    """
    Standard output contract returned to UI clients (CLI, Streamlit, API).

    Attributes
    ----------
    recommendations : list[RecommendationItem]
        Top ranked restaurant items with personalized explanations.
    summary : str
        Comparative overview comparing the recommended restaurants.
    raw_response : str
        Raw text output received from the LLM backend.
    error : str
        Error explanation if pipeline could not produce recommendations.
    is_fallback : bool
        True if recommendations were generated via rule-based ranking
        because the LLM backend was unavailable or failed (EC-602).
    filter_result : Optional[FilterResult]
        Detailed metadata from the filtering layer (candidate count, relaxation).
    timings : dict[str, float]
        Duration of each pipeline stage in milliseconds.
    candidate_count : int
        Number of candidates passed from filter to LLM.
    """
    recommendations: list[RecommendationItem] = field(default_factory=list)
    summary: str = ""
    raw_response: str = ""
    error: str = ""
    is_fallback: bool = False
    filter_result: Optional[FilterResult] = None
    timings: dict[str, float] = field(default_factory=dict)
    candidate_count: int = 0

    @property
    def is_success(self) -> bool:
        """True if recommendations were produced and no blocking error occurred."""
        return len(self.recommendations) > 0 and not self.error

    @property
    def has_recommendations(self) -> bool:
        return len(self.recommendations) > 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize result into a JSON-compatible dictionary."""
        return {
            "success": self.is_success,
            "error": self.error,
            "is_fallback": self.is_fallback,
            "summary": self.summary,
            "recommendations": [r.to_dict() for r in self.recommendations],
            "candidate_count": self.candidate_count,
            "timings_ms": self.timings,
            "relaxation_note": (
                self.filter_result.relaxation_note if self.filter_result else ""
            ),
        }


# ── Orchestrator Engine ──────────────────────────────────────────────────────

class Orchestrator:
    """
    Pipeline Coordinator for the AI Restaurant Recommendation System.

    Manages end-to-end execution:
      Preferences -> Filtering -> Prompt Building -> LLM Query -> Output Parsing
    """

    def __init__(
        self,
        df: Optional[pd.DataFrame] = None,
        llm: Optional[LLMEngine] = None,
        lazy_load: bool = True,
    ) -> None:
        """
        Initialize the orchestrator.

        Parameters
        ----------
        df : Optional[pd.DataFrame]
            Pre-loaded restaurant DataFrame. If None and lazy_load=False,
            loads from cache via `load_clean_dataset()`.
        llm : Optional[LLMEngine]
            Configured LLMEngine instance. If None, initialized from environment.
        lazy_load : bool
            If True and df is None, defers loading the dataset until the first query.
        """
        self._df = df
        self._llm = llm
        self.lazy_load = lazy_load

        if not lazy_load and self._df is None:
            self._load_data()

    @property
    def df(self) -> pd.DataFrame:
        """Get or lazily load the clean restaurant dataset."""
        if self._df is None:
            self._load_data()
        return self._df

    @property
    def llm(self) -> LLMEngine:
        """Get or lazily initialize the LLMEngine."""
        if self._llm is None:
            logger.info("Initializing default LLMEngine from configuration...")
            self._llm = LLMEngine()
        return self._llm

    def _load_data(self) -> None:
        """Load the cleaned restaurant dataset."""
        logger.info("Loading cleaned restaurant dataset into Orchestrator...")
        start_t = time.perf_counter()
        self._df = load_clean_dataset()
        load_ms = (time.perf_counter() - start_t) * 1000
        logger.info("Dataset loaded (%d rows) in %.1f ms.", len(self._df), load_ms)

    def recommend(
        self,
        preferences: UserPreferences,
    ) -> RecommendationResult:
        """
        Execute full recommendation pipeline for given user preferences.

        Parameters
        ----------
        preferences : UserPreferences
            User requirements (location, budget, cuisine, rating, etc.)

        Returns
        -------
        RecommendationResult
            Complete recommendations with explanations and telemetry.
        """
        pipeline_start = time.perf_counter()
        timings: dict[str, float] = {}

        # ── Step 1: Input Validation ─────────────────────────────────────────
        # EC-701: Location is strictly required
        if not preferences.location or not preferences.location.strip():
            logger.warning("[EC-701] Empty location received in Orchestrator.")
            return RecommendationResult(
                error="Location is required. Please specify a city or neighborhood (e.g. Bangalore, Indiranagar).",
                timings={"total_time_ms": (time.perf_counter() - pipeline_start) * 1000},
            )

        # ── Step 2: Filtering ────────────────────────────────────────────────
        filter_start = time.perf_counter()
        try:
            filter_result: Optional[FilterResult] = filter_restaurants(self.df, preferences)
        except Exception as exc:
            logger.error("Filter engine raised unexpected error: %s", exc)
            return RecommendationResult(
                error=f"Error while searching restaurants: {exc}",
                timings={"total_time_ms": (time.perf_counter() - pipeline_start) * 1000},
            )
        timings["filter_time_ms"] = round((time.perf_counter() - filter_start) * 1000, 2)

        # EC-601: Guard against None or empty return from filter engine
        if filter_result is None or not filter_result.has_results:
            err_msg = (
                filter_result.error
                if filter_result and filter_result.error
                else f"No restaurants matched your criteria in '{preferences.location}'."
            )
            logger.info("No candidates found after filtering: %s", err_msg)
            timings["total_time_ms"] = round((time.perf_counter() - pipeline_start) * 1000, 2)
            return RecommendationResult(
                error=err_msg,
                filter_result=filter_result,
                timings=timings,
                candidate_count=0,
            )

        candidates = filter_result.candidates
        candidate_count = len(candidates)
        logger.info(
            "Filter stage complete: %d candidates found (relaxed=%s) in %.1f ms.",
            candidate_count,
            filter_result.relaxed,
            timings["filter_time_ms"],
        )

        # ── Step 3: Build Prompt ─────────────────────────────────────────────
        prompt_start = time.perf_counter()
        try:
            prompt = build_prompt(preferences, candidates)
        except Exception as exc:
            logger.error("Failed to construct LLM prompt: %s", exc)
            return self._build_filter_fallback(
                candidates=candidates,
                filter_result=filter_result,
                timings=timings,
                pipeline_start=pipeline_start,
                reason=f"Prompt generation error: {exc}",
            )
        timings["prompt_time_ms"] = round((time.perf_counter() - prompt_start) * 1000, 2)

        # ── Step 4: Query LLM ────────────────────────────────────────────────
        llm_start = time.perf_counter()
        raw_response = ""
        try:
            raw_response = self.llm.query(prompt)
        except Exception as exc:
            # EC-602: LLM API failure -> graceful database fallback
            logger.warning("[EC-602] LLM call failed in Orchestrator: %s. Using rule-based fallback.", exc)
            timings["llm_time_ms"] = round((time.perf_counter() - llm_start) * 1000, 2)
            return self._build_filter_fallback(
                candidates=candidates,
                filter_result=filter_result,
                timings=timings,
                pipeline_start=pipeline_start,
                reason=f"AI service temporarily unavailable ({exc}). Showing top-rated candidates from database.",
            )
        timings["llm_time_ms"] = round((time.perf_counter() - llm_start) * 1000, 2)

        # ── Step 5: Parse Output ─────────────────────────────────────────────
        parse_start = time.perf_counter()
        try:
            parsed: ParsedRecommendation = parse_output(raw_response, candidates=candidates)
        except Exception as exc:
            logger.error("Output parser failed unexpectedly: %s", exc)
            timings["parse_time_ms"] = round((time.perf_counter() - parse_start) * 1000, 2)
            return self._build_filter_fallback(
                candidates=candidates,
                filter_result=filter_result,
                timings=timings,
                pipeline_start=pipeline_start,
                reason="Parsing error. Displaying verified candidate restaurants.",
                raw_response=raw_response,
            )
        timings["parse_time_ms"] = round((time.perf_counter() - parse_start) * 1000, 2)

        # ── Step 6: Construct Final Result ───────────────────────────────────
        timings["total_time_ms"] = round((time.perf_counter() - pipeline_start) * 1000, 2)

        logger.info(
            "Recommendation completed successfully: %d items produced in %.1f ms.",
            len(parsed.recommendations),
            timings["total_time_ms"],
        )

        return RecommendationResult(
            recommendations=parsed.recommendations,
            summary=parsed.summary,
            raw_response=raw_response,
            error="",
            is_fallback=parsed.is_fallback,
            filter_result=filter_result,
            timings=timings,
            candidate_count=candidate_count,
        )

    def _build_filter_fallback(
        self,
        candidates: list[dict[str, Any]],
        filter_result: Optional[FilterResult],
        timings: dict[str, float],
        pipeline_start: float,
        reason: str,
        raw_response: str = "",
    ) -> RecommendationResult:
        """
        EC-602 Helper: Creates graceful fallback recommendations from top filtered candidates
        when LLM query or parsing encounters an issue.
        """
        top_candidates = candidates[:5]
        fallback_items: list[RecommendationItem] = []

        for i, c in enumerate(top_candidates):
            name = c.get("name", "Unknown Restaurant")
            cuisine = c.get("cuisine", "")
            try:
                rating = float(c.get("rating", 0.0))
            except (ValueError, TypeError):
                rating = 0.0
            try:
                cost = int(str(c.get("cost", 0)).replace(",", ""))
            except (ValueError, TypeError):
                cost = 0

            loc = c.get("location", "")
            fallback_items.append(
                RecommendationItem(
                    rank=i + 1,
                    name=name,
                    cuisine=cuisine,
                    rating=rating,
                    cost=cost,
                    location=loc,
                    explanation=(
                        f"Ranked #{i+1} by verified diner ratings ({rating}/5.0). "
                        f"Serves {cuisine or 'popular cuisine'} in {loc}."
                    ),
                    is_hallucinated=False,
                )
            )

        timings["total_time_ms"] = round((time.perf_counter() - pipeline_start) * 1000, 2)

        return RecommendationResult(
            recommendations=fallback_items,
            summary=reason,
            raw_response=raw_response,
            error="",
            is_fallback=True,
            filter_result=filter_result,
            timings=timings,
            candidate_count=len(candidates),
        )
