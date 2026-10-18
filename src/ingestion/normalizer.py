"""
src/ingestion/normalizer.py
---------------------------
Normalizes the raw Zomato dataset:
  - Renames columns to clean snake_case names
  - Handles missing/malformed values (EC-005, EC-006)
  - Deduplicates records (EC-007)
  - Maps cost to budget_tier (EC-106)
  - Converts boolean columns
  - Logs how many rows were dropped at each step
"""

import logging
import re
import unicodedata

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ── Column rename map: raw HF column → normalized name ──────────────────────
# Actual HF dataset columns:
#   url, address, name, online_order, book_table, rate, votes, phone,
#   location, rest_type, dish_liked, cuisines, approx_cost(for two people),
#   reviews_list, menu_item, listed_in(type), listed_in(city)
COLUMN_RENAME_MAP: dict[str, str] = {
    "name":                        "name",
    "location":                    "location",
    "cuisines":                    "cuisine",
    "approx_cost(for two people)": "cost",
    "rate":                        "rating",
    "votes":                       "votes",
    "online_order":                "online_delivery",
    "book_table":                  "table_booking",
    "rest_type":                   "restaurant_type",
    "dish_liked":                  "dish_liked",
    "listed_in(type)":             "listed_type",
    "listed_in(city)":             "listed_city",
    "address":                     "address",
    "url":                         "url",
}

# Critical columns — rows with null in ANY of these will be dropped (EC-004)
CRITICAL_COLUMNS = ["name", "location", "rating", "cost"]

# Budget tier thresholds (INR for two) — must match config/settings.py
BUDGET_TIERS: dict[str, tuple[int, float]] = {
    "low":    (0,   300),
    "medium": (301, 800),
    "high":   (801, float("inf")),
}


# ── Main entry point ─────────────────────────────────────────────────────────

def normalize(raw_df: pd.DataFrame) -> pd.DataFrame:
    """
    Full normalization pipeline. Returns a cleaned DataFrame.
    Steps applied in order:
      1. Rename columns
      2. Select only needed columns
      3. Clean rating column (EC-006)
      4. Clean cost column (EC-005)
      5. Drop rows missing critical fields (EC-004)
      6. Deduplicate (EC-007)
      7. Map cost → budget_tier (EC-106)
      8. Normalize boolean columns
      9. Strip / clean text fields
    """
    initial_count = len(raw_df)
    logger.info("Starting normalization on %d raw rows...", initial_count)

    df = raw_df.copy()

    # ── Step 1: Rename columns ───────────────────────────────────────────────
    df = _rename_columns(df)

    # ── Step 2: Keep only normalized columns that exist ──────────────────────
    keep_cols = [c for c in COLUMN_RENAME_MAP.values() if c in df.columns]
    df = df[keep_cols]

    # ── Step 3: Clean rating (EC-006) ────────────────────────────────────────
    df = _clean_rating(df)

    # ── Step 4: Clean cost (EC-005) ──────────────────────────────────────────
    df = _clean_cost(df)

    # ── Step 5: Drop rows with nulls in critical columns ────────────────────
    before = len(df)
    df = df.dropna(subset=CRITICAL_COLUMNS)
    dropped = before - len(df)
    if dropped:
        logger.info("Dropped %d rows with null critical fields.", dropped)

    # ── Step 6: Deduplicate on (name, location) (EC-007) ────────────────────
    before = len(df)
    df = df.drop_duplicates(subset=["name", "location"], keep="first")
    dropped = before - len(df)
    if dropped:
        logger.info("Dropped %d duplicate (name, location) rows.", dropped)

    # ── Step 7: Map cost → budget_tier (EC-106) ──────────────────────────────
    df["budget_tier"] = df["cost"].apply(_map_budget_tier)

    # ── Step 8: Normalize boolean columns ───────────────────────────────────
    for col in ["online_delivery", "table_booking"]:
        if col in df.columns:
            df[col] = df[col].apply(_parse_bool)

    # ── Step 9: Strip and clean text fields ──────────────────────────────────
    for col in ["name", "location", "cuisine"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    # ── Step 10: Reset index ─────────────────────────────────────────────────
    df = df.reset_index(drop=True)

    total_dropped = initial_count - len(df)
    logger.info(
        "Normalization complete: %d → %d rows (%d dropped, %.1f%%).",
        initial_count, len(df), total_dropped,
        (total_dropped / initial_count * 100) if initial_count else 0,
    )
    return df


# ── Helper functions ──────────────────────────────────────────────────────────

def _rename_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename raw columns to normalized names where they exist."""
    existing_map = {k: v for k, v in COLUMN_RENAME_MAP.items() if k in df.columns}
    missing = set(COLUMN_RENAME_MAP.keys()) - set(df.columns)
    if missing:
        logger.debug("Raw columns not found (will be skipped): %s", missing)
    return df.rename(columns=existing_map)


def _clean_rating(df: pd.DataFrame) -> pd.DataFrame:
    """
    EC-006: Clean the rating column.
    - Handles formats like "4.1/5", "NEW", "-", "0", NaN
    - Extracts numeric part from "X.X/5" strings
    - Replaces invalid sentinels with NaN
    - Converts to float
    """
    if "rating" not in df.columns:
        logger.warning("'rating' column not found — skipping rating cleaning.")
        return df

    def parse_rating(val):
        if pd.isna(val):
            return np.nan
        s = str(val).strip()
        # Handle "4.1/5" format
        if "/" in s:
            s = s.split("/")[0].strip()
        # Replace known invalid sentinels
        if s in ("NEW", "-", "0", "0.0", ""):
            return np.nan
        try:
            r = float(s)
            # Clamp to valid range [0, 5]
            return r if 0.0 <= r <= 5.0 else np.nan
        except ValueError:
            return np.nan

    before_nulls = df["rating"].isna().sum()
    df["rating"] = df["rating"].apply(parse_rating)
    after_nulls = df["rating"].isna().sum()
    new_nulls = after_nulls - before_nulls
    if new_nulls > 0:
        logger.info("Rating cleaning: %d values converted to NaN (NEW/-/0/invalid).", new_nulls)
    return df


def _clean_cost(df: pd.DataFrame) -> pd.DataFrame:
    """
    EC-005: Clean the cost column.
    - Strips commas from values like "1,200"
    - Coerces non-numeric strings like "N/A", "-" to NaN
    - Converts to int (nullable Int64)
    """
    if "cost" not in df.columns:
        logger.warning("'cost' column not found — skipping cost cleaning.")
        return df

    def parse_cost(val):
        if pd.isna(val):
            return np.nan
        s = str(val).strip().replace(",", "").replace(" ", "")
        if s in ("", "-", "N/A", "NA", "nan"):
            return np.nan
        try:
            return int(float(s))
        except ValueError:
            return np.nan

    before_nulls = df["cost"].isna().sum()
    df["cost"] = df["cost"].apply(parse_cost)
    after_nulls = df["cost"].isna().sum()
    new_nulls = after_nulls - before_nulls
    if new_nulls > 0:
        logger.info("Cost cleaning: %d values converted to NaN (unparseable).", new_nulls)

    # Use nullable Int64 so NaN is representable
    df["cost"] = pd.to_numeric(df["cost"], errors="coerce")
    return df


def _map_budget_tier(cost) -> str:
    """
    EC-106: Map a numeric cost value to a budget tier.
    Boundary: cost=300 → "low"; cost=301 → "medium"
    Returns "unknown" if cost is NaN.
    """
    if pd.isna(cost):
        return "unknown"
    cost = float(cost)
    for tier, (low, high) in BUDGET_TIERS.items():
        if low <= cost <= high:
            return tier
    return "unknown"


def _parse_bool(val) -> bool:
    """
    Normalize boolean-like column values.
    Handles "Yes"/"No", True/False, 1/0, NaN.
    """
    if pd.isna(val):
        return False
    if isinstance(val, bool):
        return val
    s = str(val).strip().lower()
    return s in ("yes", "true", "1", "y")


def normalize_location_string(location: str) -> str:
    """
    EC-108: Normalize a user-supplied location string.
    - Unicode normalize (NFC)
    - Strip emoji and non-ASCII characters
    - Lowercase and strip whitespace
    Used by filter_engine before matching.
    """
    # NFC unicode normalization
    location = unicodedata.normalize("NFC", location)
    # Remove non-ASCII (including emoji)
    location = re.sub(r"[^\x00-\x7F]+", "", location)
    return location.strip().lower()
