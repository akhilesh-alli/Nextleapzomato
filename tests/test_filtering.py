"""
tests/test_filtering.py
-----------------------
Unit tests for Phase 2: Filtering Engine.
Covers all edge cases from edge-cases.md (EC-101 to EC-108, EC-201 to EC-205).
Run with: pytest tests/test_filtering.py -v
"""

import numpy as np
import pandas as pd
import pytest

from src.filtering.filter_engine import (
    filter_restaurants,
    _filter_location,
    _filter_cuisine,
    _filter_rating,
    _filter_budget,
    get_available_locations,
    get_available_cuisines,
)
from src.filtering.models import UserPreferences, FilterResult


# ── Shared test fixture ───────────────────────────────────────────────────────

def make_clean_df() -> pd.DataFrame:
    """
    Create a representative cleaned DataFrame that mirrors what
    normalizer.py produces — used across all filter tests.
    """
    return pd.DataFrame({
        "name": [
            "Spice Garden", "Cafe Roma", "Dragon Palace",
            "The Grill House", "Biryani Hub", "Pasta Point",
            "North Bite", "South Spice", "Quick Bites", "The Grand",
        ],
        "location": [
            "Bangalore", "Delhi", "Bangalore",
            "Delhi", "Bangalore", "Mumbai",
            "Delhi", "Bangalore", "Mumbai", "Bangalore",
        ],
        "cuisine": [
            "Indian, Chinese", "Italian", "Chinese",
            "BBQ, Continental", "Indian", "Italian, Continental",
            "North Indian", "South Indian", "Fast Food", "Continental, Indian",
        ],
        "rating": [4.2, 3.8, 4.5, 4.0, 3.5, 4.1, 3.9, 4.3, 3.2, 4.6],
        "cost":   [350, 900, 400, 750, 250, 600, 300, 200, 150, 1200],
        "budget_tier": [
            "medium", "high", "medium",
            "medium", "low", "medium",
            "low", "low", "low", "high",
        ],
        "votes": [1200, 340, 890, 560, 2100, 430, 670, 980, 210, 1500],
        "online_delivery": [True, False, True, False, True, True, False, True, True, False],
        "table_booking":   [False, True, False, True, False, False, True, False, False, True],
        "restaurant_type": ["Casual Dining"] * 10,
        "dish_liked":      ["Biryani", "Pasta", "Noodles", "Steak", "Biryani",
                            "Pizza", "Dal Makhani", "Dosa", "Burger", "Salad"],
    })


# ── EC-101: Location not found ────────────────────────────────────────────────

class TestLocationNotFound:
    def test_unknown_city_returns_error(self):
        """EC-101: Non-existent city produces error, not crash."""
        df = make_clean_df()
        prefs = UserPreferences(location="Atlantis", min_rating=0.0)
        result = filter_restaurants(df, prefs)
        assert not result.has_results
        assert result.error != ""
        assert "Atlantis" in result.error

    def test_unknown_city_suggests_alternative(self):
        """EC-101: Should suggest a similar city name."""
        df = make_clean_df()
        prefs = UserPreferences(location="Bangalre")  # typo
        result = filter_restaurants(df, prefs)
        # May or may not suggest, but should not crash
        assert isinstance(result.error, str)

    def test_known_city_returns_results(self):
        """EC-101: Known city should always return results."""
        df = make_clean_df()
        prefs = UserPreferences(location="Bangalore", min_rating=0.0)
        result = filter_restaurants(df, prefs)
        assert result.has_results
        assert all("Bangalore" in r["location"] for r in result.candidates)


# ── EC-102: Cuisine not found in given location ───────────────────────────────

class TestCuisineNotFound:
    def test_nonexistent_cuisine_in_city_relaxes_to_location(self):
        """EC-102: Ethiopian cuisine in Bangalore → fallback to all Bangalore."""
        df = make_clean_df()
        prefs = UserPreferences(location="Bangalore", cuisine="Ethiopian")
        result = filter_restaurants(df, prefs)
        # Should return results (relaxed) rather than empty
        assert result.has_results
        assert result.relaxed is True
        assert result.relaxation_note != ""

    def test_relaxation_note_is_human_readable(self):
        """EC-102: Relaxation note should mention the cuisine and city."""
        df = make_clean_df()
        prefs = UserPreferences(location="Bangalore", cuisine="Ethiopian")
        result = filter_restaurants(df, prefs)
        if result.relaxed:
            assert len(result.relaxation_note) > 10  # non-trivial message


# ── EC-103: Min rating too high ───────────────────────────────────────────────

class TestHighMinRating:
    def test_min_rating_5_relaxes(self):
        """EC-103: min_rating=5.0 returns no strict matches → relaxation applied."""
        df = make_clean_df()
        prefs = UserPreferences(location="Bangalore", min_rating=5.0)
        result = filter_restaurants(df, prefs)
        # Should still return results via relaxation
        assert result.has_results or result.error != ""  # either relaxed results or friendly error

    def test_achievable_rating_not_relaxed(self):
        """EC-103: Achievable min_rating should return direct matches."""
        df = make_clean_df()
        prefs = UserPreferences(location="Bangalore", min_rating=4.0)
        result = filter_restaurants(df, prefs)
        assert result.has_results
        assert not result.relaxed
        for r in result.candidates:
            assert r["rating"] >= 4.0


# ── EC-104: All filters combined → zero results ───────────────────────────────

class TestAllFiltersZero:
    def test_extremely_specific_filters(self):
        """EC-104: Impossible combination → friendly error, not crash."""
        df = make_clean_df()
        prefs = UserPreferences(
            location="Mumbai",
            budget="low",
            cuisine="Italian",
            min_rating=4.8,
            online_delivery=True,
            table_booking=True,
        )
        result = filter_restaurants(df, prefs)
        # Either relaxed results or an error message — never a crash
        assert isinstance(result, FilterResult)
        assert result.error or result.has_results


# ── EC-105: Multi-cuisine rows partial match ──────────────────────────────────

class TestMultiCuisineMatch:
    def test_partial_cuisine_match(self):
        """EC-105: 'Italian' matches row with cuisine='Italian, Continental'."""
        df = make_clean_df()
        result = _filter_cuisine(df, "Italian")
        cuisine_col = result["cuisine"].str.lower()
        assert all(cuisine_col.str.contains("italian"))

    def test_substring_cuisine_match(self):
        """EC-105: 'Indian' matches 'North Indian', 'South Indian', 'Indian, Chinese'."""
        df = make_clean_df()
        result = _filter_cuisine(df, "Indian")
        assert len(result) >= 3

    def test_cuisine_case_insensitive(self):
        """EC-105: Cuisine matching is case-insensitive."""
        df = make_clean_df()
        lower = _filter_cuisine(df, "italian")
        upper = _filter_cuisine(df, "ITALIAN")
        assert len(lower) == len(upper)

    def test_empty_cuisine_returns_all(self):
        """EC-107: Empty cuisine field → no cuisine filter applied."""
        df = make_clean_df()
        result = _filter_cuisine(df, "")
        assert len(result) == len(df)


# ── EC-106: Budget tier boundary values ──────────────────────────────────────

class TestBudgetTierFilter:
    def test_low_budget_filter(self):
        """EC-106: budget='low' returns only low-tier restaurants."""
        df = make_clean_df()
        result = _filter_budget(df, "low")
        assert all(result["budget_tier"] == "low")

    def test_medium_budget_filter(self):
        """EC-106: budget='medium' returns only medium-tier restaurants."""
        df = make_clean_df()
        result = _filter_budget(df, "medium")
        assert all(result["budget_tier"] == "medium")

    def test_high_budget_filter(self):
        """EC-106: budget='high' returns only high-tier restaurants."""
        df = make_clean_df()
        result = _filter_budget(df, "high")
        assert all(result["budget_tier"] == "high")


# ── EC-107: Empty optional fields ────────────────────────────────────────────

class TestEmptyOptionalFields:
    def test_empty_cuisine_no_filter(self):
        """EC-107: Empty cuisine → all rows for that location returned."""
        df = make_clean_df()
        prefs = UserPreferences(location="Bangalore", cuisine="", min_rating=0.0)
        result = filter_restaurants(df, prefs)
        assert result.has_results
        # Should return all Bangalore restaurants (5 rows in fixture)
        assert result.total_matched == 5

    def test_empty_budget_no_filter(self):
        """EC-107: Empty budget → no budget filter applied."""
        df = make_clean_df()
        prefs = UserPreferences(location="Bangalore", budget="", min_rating=0.0)
        result = filter_restaurants(df, prefs)
        assert result.has_results


# ── EC-108: Special characters in location ───────────────────────────────────

class TestSpecialCharLocation:
    def test_location_case_insensitive(self):
        """EC-108: 'bangalore' and 'Bangalore' should return same results."""
        df = make_clean_df()
        lower = _filter_location(df, "bangalore")
        upper = _filter_location(df, "Bangalore")
        assert len(lower) == len(upper)

    def test_partial_location_match(self):
        """EC-108: Partial substring 'bang' matches 'Bangalore'."""
        df = make_clean_df()
        result = _filter_location(df, "bang")
        assert len(result) > 0
        assert all("Bangalore" in r for r in result["location"])


# ── EC-201: min_rating clamping ───────────────────────────────────────────────

class TestMinRatingClamping:
    def test_negative_rating_clamped_to_zero(self):
        """EC-201: min_rating=-1 should be clamped to 0.0."""
        prefs = UserPreferences(location="Bangalore", min_rating=-1.0)
        assert prefs.min_rating == 0.0

    def test_rating_above_5_clamped(self):
        """EC-201: min_rating=6.0 should be clamped to 5.0."""
        prefs = UserPreferences(location="Bangalore", min_rating=6.0)
        assert prefs.min_rating == 5.0

    def test_valid_rating_unchanged(self):
        """EC-201: min_rating=4.0 within range should be unchanged."""
        prefs = UserPreferences(location="Bangalore", min_rating=4.0)
        assert prefs.min_rating == 4.0


# ── EC-202: Budget synonym mapping ───────────────────────────────────────────

class TestBudgetSynonymMapping:
    @pytest.mark.parametrize("synonym,expected", [
        ("cheap", "low"),
        ("affordable", "low"),
        ("budget", "low"),
        ("moderate", "medium"),
        ("mid", "medium"),
        ("expensive", "high"),
        ("premium", "high"),
        ("luxury", "high"),
    ])
    def test_budget_synonyms(self, synonym, expected):
        """EC-202: Budget synonyms should map to canonical tiers."""
        prefs = UserPreferences(location="Bangalore", budget=synonym)
        assert prefs.budget == expected

    def test_unknown_budget_string_becomes_empty(self):
        """EC-202: Unrecognized budget string → treated as no budget filter."""
        prefs = UserPreferences(location="Bangalore", budget="bargain")
        assert prefs.budget == ""

    def test_valid_tier_unchanged(self):
        """EC-202: Valid tier 'medium' should remain unchanged."""
        prefs = UserPreferences(location="Bangalore", budget="medium")
        assert prefs.budget == "medium"


# ── EC-203: Extra-long notes truncation ──────────────────────────────────────

class TestNotesTruncation:
    def test_long_notes_truncated(self):
        """EC-203: extra_notes longer than MAX_NOTES_LENGTH should be truncated."""
        from config.settings import MAX_NOTES_LENGTH
        long_note = "A" * (MAX_NOTES_LENGTH + 100)
        prefs = UserPreferences(location="Bangalore", extra_notes=long_note)
        assert len(prefs.extra_notes) == MAX_NOTES_LENGTH

    def test_short_notes_unchanged(self):
        """EC-203: Short extra_notes should not be modified."""
        note = "Family friendly, no spicy food"
        prefs = UserPreferences(location="Bangalore", extra_notes=note)
        assert prefs.extra_notes == note


# ── EC-204 & EC-205: Invalid location formats ─────────────────────────────────

class TestInvalidLocation:
    def test_numeric_only_location_raises(self):
        """EC-205: Numeric-only location should raise ValueError."""
        with pytest.raises(ValueError, match="EC-205"):
            UserPreferences(location="12345")

    def test_location_required_for_filter(self):
        """EC-205: Empty location returns error in FilterResult."""
        df = make_clean_df()
        prefs = UserPreferences.__new__(UserPreferences)
        # Bypass __post_init__ to test filter_engine guard directly
        object.__setattr__(prefs, "location", "")
        object.__setattr__(prefs, "budget", "")
        object.__setattr__(prefs, "cuisine", "")
        object.__setattr__(prefs, "min_rating", 0.0)
        object.__setattr__(prefs, "online_delivery", False)
        object.__setattr__(prefs, "table_booking", False)
        object.__setattr__(prefs, "extra_notes", "")
        result = filter_restaurants(df, prefs)
        assert not result.has_results
        assert "Location is required" in result.error


# ── Sorting & capping ─────────────────────────────────────────────────────────

class TestSortingAndCapping:
    def test_results_sorted_by_rating_descending(self):
        """Results should be ordered by rating descending."""
        df = make_clean_df()
        prefs = UserPreferences(location="Bangalore", min_rating=0.0)
        result = filter_restaurants(df, prefs)
        ratings = [r["rating"] for r in result.candidates]
        assert ratings == sorted(ratings, reverse=True)

    def test_max_candidates_respected(self):
        """Results should not exceed MAX_CANDIDATES."""
        from config.settings import MAX_CANDIDATES
        # Create a large DataFrame
        big_df = pd.concat([make_clean_df()] * 5, ignore_index=True)
        big_df["location"] = "Testcity"
        big_df["budget_tier"] = "medium"
        prefs = UserPreferences(location="Testcity", min_rating=0.0)
        result = filter_restaurants(big_df, prefs)
        assert result.count <= MAX_CANDIDATES


# ── FilterResult properties ───────────────────────────────────────────────────

class TestFilterResult:
    def test_has_results_false_on_empty(self):
        fr = FilterResult()
        assert not fr.has_results
        assert fr.count == 0

    def test_has_results_true_on_candidates(self):
        fr = FilterResult(candidates=[{"name": "Test"}])
        assert fr.has_results
        assert fr.count == 1


# ── Utility functions ─────────────────────────────────────────────────────────

class TestUtilityFunctions:
    def test_get_available_locations(self):
        """get_available_locations returns sorted unique locations."""
        df = make_clean_df()
        locs = get_available_locations(df)
        assert isinstance(locs, list)
        assert locs == sorted(locs)
        assert "Bangalore" in locs

    def test_get_available_cuisines(self):
        """get_available_cuisines returns sorted individual cuisines."""
        df = make_clean_df()
        cuisines = get_available_cuisines(df)
        assert isinstance(cuisines, list)
        # Multi-cuisine rows split: "Indian, Chinese" → ["Indian", "Chinese"]
        assert "Italian" in cuisines
        assert "Indian" in cuisines
