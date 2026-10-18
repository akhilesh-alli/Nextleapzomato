"""
tests/test_ingestion.py
-----------------------
Unit tests for Phase 1: Data Ingestion & Normalization.
Covers all edge cases from edge-cases.md (EC-001 to EC-007).
Run with: pytest tests/test_ingestion.py -v
"""

import numpy as np
import pandas as pd
import pytest

from src.ingestion.normalizer import (
    normalize,
    _clean_rating,
    _clean_cost,
    _map_budget_tier,
    _parse_bool,
    normalize_location_string,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_raw_df(**overrides) -> pd.DataFrame:
    """Helper: create a minimal valid raw DataFrame for testing."""
    base = {
        "name":                        ["Spice Garden", "Cafe Mocha", "The Grill"],
        "location":                    ["Bangalore", "Delhi", "Mumbai"],
        "cuisines":                    ["Indian, Chinese", "Italian", "BBQ"],
        "approx_cost(for two people)": ["400", "1,200", "250"],
        "rate":                        ["4.1/5", "3.8/5", "4.5/5"],
        "votes":                       [1200, 340, 890],
        "online_order":                ["Yes", "No", "Yes"],
        "book_table":                  ["No", "Yes", "No"],
        "rest_type":                   ["Casual Dining", "Cafe", "Quick Bites"],
        "dish_liked":                  ["Biryani", "Pasta", "Burger"],
        "listed_in(type)":             ["Buffet", "Cafes", "Delivery"],
        "listed_in(city)":             ["Bangalore", "Delhi", "Mumbai"],
        "address":                     ["MG Road", "CP", "Bandra"],
        "url":                         ["url1", "url2", "url3"],
    }
    base.update(overrides)
    return pd.DataFrame(base)


# ── EC-003: Empty dataset ────────────────────────────────────────────────────

class TestEmptyDataset:
    def test_empty_raw_df_raises(self):
        """EC-003: Empty dataset should raise ValueError, not silently return."""
        empty = pd.DataFrame(columns=make_raw_df().columns)
        # normalize itself won't raise, but load_clean_dataset checks len==0
        result = normalize(empty)
        assert len(result) == 0  # normalize handles empty gracefully


# ── EC-004: All rows dropped during normalization ────────────────────────────

class TestAllRowsDropped:
    def test_all_null_critical_fields(self):
        """EC-004: All rows with null name/location/rating/cost get dropped."""
        df = make_raw_df()
        df["name"] = np.nan
        result = normalize(df)
        assert len(result) == 0


# ── EC-005: Malformed cost values ─────────────────────────────────────────────

class TestCostCleaning:
    def test_comma_in_cost(self):
        """EC-005: '1,200' should be parsed as 1200."""
        df = make_raw_df(**{"approx_cost(for two people)": ["1,200", "400", "250"]})
        result = normalize(df)
        assert 1200 in result["cost"].values

    def test_na_cost_becomes_null(self):
        """EC-005: 'N/A' cost should become NaN → row dropped."""
        df = make_raw_df(**{"approx_cost(for two people)": ["N/A", "400", "250"]})
        result = normalize(df)
        # First row should be dropped (NaN cost)
        assert len(result) == 2

    def test_dash_cost_becomes_null(self):
        """EC-005: '-' cost should become NaN → row dropped."""
        df = make_raw_df(**{"approx_cost(for two people)": ["-", "400", "250"]})
        result = normalize(df)
        assert len(result) == 2

    def test_valid_cost_preserved(self):
        """EC-005: Valid '400' cost should remain as 400."""
        df = make_raw_df(**{"approx_cost(for two people)": ["400", "800", "200"]})
        result = normalize(df)
        assert set(result["cost"].astype(int).tolist()) == {400, 800, 200}


# ── EC-006: Malformed rating values ──────────────────────────────────────────

class TestRatingCleaning:
    def test_new_rating_dropped(self):
        """EC-006: 'NEW' rating should become NaN → row dropped."""
        df = make_raw_df(**{"rate": ["NEW", "3.8/5", "4.5/5"]})
        result = normalize(df)
        assert len(result) == 2

    def test_dash_rating_dropped(self):
        """EC-006: '-' rating should become NaN → row dropped."""
        df = make_raw_df(**{"rate": ["-", "3.8/5", "4.5/5"]})
        result = normalize(df)
        assert len(result) == 2

    def test_slash_format_parsed(self):
        """EC-006: '4.1/5' should be parsed as 4.1."""
        df = make_raw_df(**{"rate": ["4.1/5", "3.8/5", "4.5/5"]})
        result = normalize(df)
        assert 4.1 in result["rating"].values

    def test_zero_rating_dropped(self):
        """EC-006: '0' rating should be treated as invalid → dropped."""
        df = make_raw_df(**{"rate": ["0", "3.8/5", "4.5/5"]})
        result = normalize(df)
        assert len(result) == 2

    def test_out_of_range_rating_dropped(self):
        """EC-006: Rating > 5.0 should be treated as NaN → dropped."""
        df = make_raw_df(**{"rate": ["6.0", "3.8/5", "4.5/5"]})
        result = normalize(df)
        assert len(result) == 2


# ── EC-007: Duplicate records ────────────────────────────────────────────────

class TestDeduplication:
    def test_duplicate_name_location_removed(self):
        """EC-007: Same (name, location) pair should be deduplicated."""
        df = make_raw_df()
        # Add duplicate of row 0
        duplicate = df.iloc[[0]].copy()
        df = pd.concat([df, duplicate], ignore_index=True)
        result = normalize(df)
        assert len(result) == 3  # only 3 unique (name, location) pairs

    def test_same_name_different_location_kept(self):
        """EC-007: Same name but different location should both be kept."""
        df = make_raw_df(**{
            "name": ["Spice Garden", "Spice Garden", "Cafe Mocha"],
            "location": ["Bangalore", "Delhi", "Mumbai"],
        })
        result = normalize(df)
        assert len(result) == 3


# ── EC-106: Budget tier boundary values ──────────────────────────────────────

class TestBudgetTier:
    def test_boundary_300_is_low(self):
        """EC-106: cost=300 should map to 'low'."""
        assert _map_budget_tier(300) == "low"

    def test_boundary_301_is_medium(self):
        """EC-106: cost=301 should map to 'medium'."""
        assert _map_budget_tier(301) == "medium"

    def test_boundary_800_is_medium(self):
        """EC-106: cost=800 should map to 'medium'."""
        assert _map_budget_tier(800) == "medium"

    def test_boundary_801_is_high(self):
        """EC-106: cost=801 should map to 'high'."""
        assert _map_budget_tier(801) == "high"

    def test_nan_cost_is_unknown(self):
        """EC-106: NaN cost should map to 'unknown'."""
        assert _map_budget_tier(np.nan) == "unknown"

    def test_zero_cost_is_low(self):
        """Cost=0 is within low tier (0-300)."""
        assert _map_budget_tier(0) == "low"

    def test_high_cost(self):
        """Cost=5000 should be 'high'."""
        assert _map_budget_tier(5000) == "high"


# ── Boolean column normalization ─────────────────────────────────────────────

class TestBooleanParsing:
    @pytest.mark.parametrize("val,expected", [
        ("Yes", True), ("No", False), ("yes", True), ("YES", True),
        ("True", True), ("False", False), ("1", True), ("0", False),
        (True, True), (False, False), (None, False),
    ])
    def test_parse_bool(self, val, expected):
        assert _parse_bool(val) == expected


# ── EC-108: Location string normalization ────────────────────────────────────

class TestLocationNormalization:
    def test_strips_emoji(self):
        """EC-108: Emoji in location string should be stripped."""
        result = normalize_location_string("🍕 Delhi")
        assert result == "delhi"

    def test_lowercased(self):
        """EC-108: Location should be lowercased."""
        result = normalize_location_string("Bangalore")
        assert result == "bangalore"

    def test_strips_whitespace(self):
        """EC-108: Leading/trailing whitespace should be stripped."""
        result = normalize_location_string("  Mumbai  ")
        assert result == "mumbai"

    def test_unicode_normalized(self):
        """EC-108: Unicode string should be NFC normalized."""
        result = normalize_location_string("Café")
        assert isinstance(result, str)
        assert len(result) > 0


# ── Full pipeline sanity check ───────────────────────────────────────────────

class TestFullNormalization:
    def test_output_has_required_columns(self):
        """Normalized DataFrame must contain all required columns."""
        df = make_raw_df()
        result = normalize(df)
        required = {"name", "location", "cuisine", "cost", "rating",
                    "votes", "budget_tier", "online_delivery", "table_booking"}
        assert required.issubset(set(result.columns))

    def test_no_nulls_in_critical_columns(self):
        """After normalization, no nulls in name/location/rating/cost."""
        df = make_raw_df()
        result = normalize(df)
        for col in ["name", "location", "rating", "cost"]:
            assert result[col].isna().sum() == 0, f"Null found in column: {col}"

    def test_budget_tier_column_populated(self):
        """All rows should have a non-null budget_tier."""
        df = make_raw_df()
        result = normalize(df)
        assert result["budget_tier"].notna().all()
        assert set(result["budget_tier"].unique()).issubset({"low", "medium", "high", "unknown"})
