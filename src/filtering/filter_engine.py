"""
src/filtering/filter_engine.py
-------------------------------
Rule-based restaurant filtering engine.

Pipeline (applied in order):
  1.  Location   — case-insensitive substring match  (EC-101, EC-108)
  2.  Budget     — exact match on budget_tier        (EC-106)
  3.  Cuisine    — case-insensitive partial match     (EC-105)
  4.  Min rating — rating >= prefs.min_rating         (EC-103)
  5.  Delivery   — online_delivery == True            (optional)
  6.  Booking    — table_booking  == True             (optional)

Relaxation strategy (EC-102, EC-103, EC-104):
  If < MIN_RESULTS rows survive strict filtering, the engine progressively
  relaxes filters in this order:
    1. Cuisine filter removed
    2. min_rating lowered by RATING_RELAXATION_STEP until 0.0
    3. Budget filter removed

  Each relaxation is noted in FilterResult.relaxation_note.
"""

import logging
import re
import unicodedata
from typing import Optional

import pandas as pd

from src.filtering.models import FilterResult, UserPreferences

logger = logging.getLogger(__name__)

# Minimum results before we consider relaxing filters
MIN_RESULTS = 3


# ── Public API ────────────────────────────────────────────────────────────────

def filter_restaurants(
    df: pd.DataFrame,
    prefs: UserPreferences,
) -> FilterResult:
    """
    Main entry point. Filters `df` against `prefs` and returns a FilterResult.

    Parameters
    ----------
    df    : Cleaned DataFrame from load_clean_dataset()
    prefs : UserPreferences dataclass

    Returns
    -------
    FilterResult with .candidates (list of dicts), .error, .relaxed flags
    """
    from config.settings import MAX_CANDIDATES, RATING_RELAXATION_STEP

    total_searched = len(df)

    # EC-201: location is required (checked by caller/UI, but guard here too)
    if not prefs.location.strip():
        return FilterResult(
            total_searched=total_searched,
            error="Location is required. Please enter a city name.",
        )

    # ── Strict pass ───────────────────────────────────────────────────────────
    result = _apply_all_filters(df, prefs)

    if len(result) >= MIN_RESULTS:
        return _build_result(result, prefs, total_searched, relaxed=False)

    # ── EC-101: location not found at all ─────────────────────────────────────
    location_only = _filter_location(df, prefs.location)
    if location_only.empty:
        available = sorted(df["location"].dropna().unique().tolist())
        suggestion = _suggest_city(prefs.location, available)
        msg = f"No restaurants found in '{prefs.location}'."
        if suggestion:
            msg += f" Did you mean '{suggestion}'?"
        else:
            msg += " Try a different city name."
        return FilterResult(total_searched=total_searched, error=msg)

    # ── Relaxation cascade ────────────────────────────────────────────────────
    notes: list[str] = []

    # Relax 1: remove cuisine filter (EC-102)
    if prefs.cuisine:
        result = _apply_filters_no_cuisine(df, prefs)
        if len(result) >= MIN_RESULTS:
            notes.append(
                f"No '{prefs.cuisine}' restaurants matched in '{prefs.location}'. "
                f"Showing top-rated restaurants in '{prefs.location}' instead."
            )
            return _build_result(result, prefs, total_searched,
                                  relaxed=True, note=" | ".join(notes))

    # Relax 2: progressively lower min_rating (EC-103)
    relaxed_rating = prefs.min_rating - RATING_RELAXATION_STEP
    while relaxed_rating >= 0.0:
        relaxed_prefs = UserPreferences(
            location=prefs.location,
            budget=prefs.budget,
            cuisine="",                  # already relaxed cuisine
            min_rating=relaxed_rating,
            online_delivery=prefs.online_delivery,
            table_booking=prefs.table_booking,
            extra_notes=prefs.extra_notes,
        )
        result = _apply_all_filters(df, relaxed_prefs)
        if len(result) >= MIN_RESULTS:
            notes.append(
                f"Lowered minimum rating to {relaxed_rating:.1f} to find enough matches."
            )
            return _build_result(result, relaxed_prefs, total_searched,
                                  relaxed=True, note=" | ".join(notes))
        relaxed_rating -= RATING_RELAXATION_STEP

    # Relax 3: remove budget filter too (EC-104)
    no_budget_prefs = UserPreferences(
        location=prefs.location,
        budget="",
        cuisine="",
        min_rating=0.0,
        online_delivery=False,
        table_booking=False,
        extra_notes=prefs.extra_notes,
    )
    result = _apply_all_filters(df, no_budget_prefs)
    if not result.empty:
        notes.append(
            "Showing all restaurants in your location — "
            "try relaxing your filters (cuisine, budget, rating) for better results."
        )
        return _build_result(result, no_budget_prefs, total_searched,
                              relaxed=True, note=" | ".join(notes))

    # Truly no results
    return FilterResult(
        total_searched=total_searched,
        error=(
            f"No restaurants found matching your criteria in '{prefs.location}'. "
            f"Try: a lower minimum rating, a different cuisine, or a different budget."
        ),
    )


# ── Filter steps ──────────────────────────────────────────────────────────────

def _apply_all_filters(df: pd.DataFrame, prefs: UserPreferences) -> pd.DataFrame:
    """Apply all six filter steps in sequence."""
    result = df.copy()
    result = _filter_location(result, prefs.location)
    if prefs.budget:
        result = _filter_budget(result, prefs.budget)
    if prefs.cuisine:
        result = _filter_cuisine(result, prefs.cuisine)
    if prefs.min_rating > 0.0:
        result = _filter_rating(result, prefs.min_rating)
    if prefs.online_delivery:
        result = _filter_delivery(result)
    if prefs.table_booking:
        result = _filter_booking(result)
    return result


def _apply_filters_no_cuisine(df: pd.DataFrame, prefs: UserPreferences) -> pd.DataFrame:
    """Apply all filters except cuisine (relaxation step 1)."""
    result = df.copy()
    result = _filter_location(result, prefs.location)
    if prefs.budget:
        result = _filter_budget(result, prefs.budget)
    if prefs.min_rating > 0.0:
        result = _filter_rating(result, prefs.min_rating)
    if prefs.online_delivery:
        result = _filter_delivery(result)
    if prefs.table_booking:
        result = _filter_booking(result)
    return result


def _filter_location(df: pd.DataFrame, location: str) -> pd.DataFrame:
    """
    EC-101, EC-108: Case-insensitive substring match on location column.
    Normalises both sides (strip non-ASCII, lowercase).
    """
    if df.empty or not location.strip():
        return df
    loc_norm = _normalise_str(location)
    mask = df["location"].fillna("").apply(
        lambda x: loc_norm in _normalise_str(x)
    )
    return df[mask]


def _filter_budget(df: pd.DataFrame, budget: str) -> pd.DataFrame:
    """Exact match on budget_tier column (EC-106)."""
    if df.empty:
        return df
    return df[df["budget_tier"].str.lower() == budget.lower()]


def _filter_cuisine(df: pd.DataFrame, cuisine: str) -> pd.DataFrame:
    """
    EC-105: Case-insensitive partial match on multi-cuisine field.
    e.g. cuisine="Italian" matches "Italian, Chinese, Indian"
    """
    if df.empty or not cuisine.strip():
        return df
    cuis_norm = cuisine.strip().lower()
    mask = df["cuisine"].fillna("").str.lower().str.contains(
        re.escape(cuis_norm), na=False
    )
    return df[mask]


def _filter_rating(df: pd.DataFrame, min_rating: float) -> pd.DataFrame:
    """EC-103: Keep rows where rating >= min_rating."""
    if df.empty:
        return df
    return df[df["rating"] >= min_rating]


def _filter_delivery(df: pd.DataFrame) -> pd.DataFrame:
    """Keep only restaurants that offer online delivery."""
    if df.empty or "online_delivery" not in df.columns:
        return df
    return df[df["online_delivery"] == True]


def _filter_booking(df: pd.DataFrame) -> pd.DataFrame:
    """Keep only restaurants that offer table booking."""
    if df.empty or "table_booking" not in df.columns:
        return df
    return df[df["table_booking"] == True]


# ── Result builder ────────────────────────────────────────────────────────────

def _build_result(
    df: pd.DataFrame,
    prefs: UserPreferences,
    total_searched: int,
    relaxed: bool = False,
    note: str = "",
) -> FilterResult:
    """
    Sort filtered DataFrame, cap at MAX_CANDIDATES, convert to list of dicts.
    Sort: rating DESC, votes DESC.
    """
    from config.settings import MAX_CANDIDATES

    total_matched = len(df)

    # Sort: primary = rating DESC, secondary = votes DESC
    sort_cols = []
    if "rating" in df.columns:
        sort_cols.append("rating")
    if "votes" in df.columns:
        sort_cols.append("votes")

    if sort_cols:
        df = df.sort_values(sort_cols, ascending=[False] * len(sort_cols))

    # Cap at MAX_CANDIDATES
    df = df.head(MAX_CANDIDATES)

    # Select display-relevant columns only
    display_cols = [c for c in [
        "name", "location", "cuisine", "rating", "cost",
        "budget_tier", "votes", "online_delivery", "table_booking",
        "restaurant_type", "dish_liked",
    ] if c in df.columns]

    candidates = df[display_cols].to_dict(orient="records")

    logger.info(
        "Filter result: %d searched | %d matched | %d returned | relaxed=%s",
        total_searched, total_matched, len(candidates), relaxed,
    )

    return FilterResult(
        candidates=candidates,
        total_searched=total_searched,
        total_matched=total_matched,
        relaxed=relaxed,
        relaxation_note=note,
    )


# ── Utility helpers ───────────────────────────────────────────────────────────

def _normalise_str(s: str) -> str:
    """
    EC-108: Normalize a string for matching.
    - NFC unicode
    - Strip non-ASCII (emoji, accents that didn't NFC-compose)
    - Lowercase, strip whitespace
    """
    s = unicodedata.normalize("NFC", s)
    s = re.sub(r"[^\x00-\x7F]+", "", s)
    return s.strip().lower()


def _suggest_city(query: str, available: list[str]) -> Optional[str]:
    """
    EC-101: Simple fuzzy suggestion — find the city with the most
    overlapping characters with the query.
    Returns None if no reasonable match found.
    """
    if not available:
        return None
    query_l = query.lower()
    best, best_score = None, 0
    for city in available:
        city_l = city.lower()
        # Score = number of common characters (set intersection)
        score = len(set(query_l) & set(city_l))
        if score > best_score and score >= 2:
            best, best_score = city, score
    return best


def get_available_locations(df: pd.DataFrame) -> list[str]:
    """Return sorted list of unique locations in the dataset (for UI hints)."""
    return sorted(df["location"].dropna().unique().tolist())


def get_available_cuisines(df: pd.DataFrame) -> list[str]:
    """Return sorted list of all individual cuisines found in the dataset."""
    all_cuisines = (
        df["cuisine"]
        .dropna()
        .str.split(",")
        .explode()
        .str.strip()
        .unique()
        .tolist()
    )
    return sorted(c for c in all_cuisines if c)
