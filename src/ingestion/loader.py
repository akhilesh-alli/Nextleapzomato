"""
src/ingestion/loader.py
-----------------------
Loads the Zomato HuggingFace dataset, saves the raw CSV,
and returns a cleaned DataFrame (with local cache support).

Actual dataset columns (from ManikaSaini/zomato-restaurant-recommendation):
    url, address, name, online_order, book_table, rate, votes, phone,
    location, rest_type, dish_liked, cuisines, approx_cost(for two people),
    reviews_list, menu_item, listed_in(type), listed_in(city)
"""

import logging
import sys
import os
import pathlib
import pandas as pd

logger = logging.getLogger(__name__)

# ── Resolve paths relative to this file ─────────────────────────────────────
_SRC_DIR     = pathlib.Path(__file__).resolve().parent.parent        # src/
_PROJECT_ROOT = _SRC_DIR.parent                                       # project root
_DATA_DIR    = _PROJECT_ROOT / "data"

HF_DATASET_NAME  = "ManikaSaini/zomato-restaurant-recommendation"
HF_SPLIT         = "train"
RAW_CSV_PATH     = _DATA_DIR / "restaurants_raw.csv"
CLEAN_CSV_PATH   = _DATA_DIR / "restaurants_clean.csv"

# Required columns that MUST exist in the raw dataset (EC-002 guard)
REQUIRED_RAW_COLUMNS = {
    "name", "location", "rate", "votes",
    "cuisines", "approx_cost(for two people)",
    "online_order", "book_table"
}


def _ensure_data_dir() -> None:
    """Create the data/ directory if it does not exist."""
    _DATA_DIR.mkdir(parents=True, exist_ok=True)


def _load_from_huggingface() -> pd.DataFrame:
    """
    Pull the dataset from HuggingFace Hub.
    Saves raw CSV to data/restaurants_raw.csv.
    Raises RuntimeError on network failure (EC-001).
    """
    try:
        from datasets import load_dataset  # type: ignore
    except ImportError:
        logger.error("'datasets' package not installed. Run: pip install datasets")
        sys.exit(1)

    logger.info("Downloading dataset from HuggingFace: %s ...", HF_DATASET_NAME)
    try:
        dataset = load_dataset(HF_DATASET_NAME, split=HF_SPLIT)
    except Exception as exc:
        raise RuntimeError(
            f"[EC-001] Failed to download dataset from HuggingFace: {exc}\n"
            f"Check your internet connection or use the local cache."
        ) from exc

    df = dataset.to_pandas()
    logger.info("Downloaded %d rows from HuggingFace.", len(df))

    # Validate schema (EC-002)
    missing_cols = REQUIRED_RAW_COLUMNS - set(df.columns)
    if missing_cols:
        raise RuntimeError(
            f"[EC-002] Dataset schema has changed. Missing expected columns: {missing_cols}\n"
            f"Actual columns: {list(df.columns)}"
        )

    # Save raw snapshot
    _ensure_data_dir()
    df.to_csv(RAW_CSV_PATH, index=False)
    logger.info("Raw dataset saved to: %s", RAW_CSV_PATH)
    return df


def _load_from_raw_cache() -> pd.DataFrame:
    """Load the raw CSV snapshot saved from a previous HF download."""
    logger.info("Loading raw dataset from local cache: %s", RAW_CSV_PATH)
    df = pd.read_csv(RAW_CSV_PATH, low_memory=False)
    logger.info("Loaded %d rows from raw cache.", len(df))
    return df


def load_raw_dataset() -> pd.DataFrame:
    """
    Return the raw (un-normalized) restaurant DataFrame.

    Priority:
      1. Load from HuggingFace (saves raw cache on success)
      2. If network fails → fall back to raw cache (EC-001)
      3. If neither exists → exit with clear message
    """
    _ensure_data_dir()

    if RAW_CSV_PATH.exists():
        logger.info("Found local raw dataset at %s. Loading from cache.", RAW_CSV_PATH)
        return _load_from_raw_cache()

    try:
        return _load_from_huggingface()
    except RuntimeError as exc:
        logger.warning("%s", exc)
        if RAW_CSV_PATH.exists():
            logger.warning("Falling back to local raw cache.")
            return _load_from_raw_cache()
        logger.error(
            "No local cache found at %s and HF download failed. Cannot proceed without data.", RAW_CSV_PATH
        )
        sys.exit(1)


def load_clean_dataset() -> pd.DataFrame:
    """
    Return a fully normalized, cleaned DataFrame ready for filtering.

    Priority:
      1. Load from cleaned CSV cache if it exists (fast path)
      2. Otherwise: load raw → normalize → save clean cache
    """
    from src.ingestion.normalizer import normalize  # local import to avoid circular

    _ensure_data_dir()

    # Fast path: cleaned cache already exists (EC-001 / EC-802 safe)
    if CLEAN_CSV_PATH.exists():
        logger.info("Loading cleaned dataset from cache: %s", CLEAN_CSV_PATH)
        df = pd.read_csv(CLEAN_CSV_PATH, low_memory=False)
        logger.info("Loaded %d clean records from cache.", len(df))

        # EC-003: Empty dataset guard
        if len(df) == 0:
            raise ValueError(
                "[EC-003] Cached cleaned dataset is empty. "
                "Delete the cache file and re-run to rebuild it."
            )
        return df

    # Slow path: download + normalize
    logger.info("No cleaned cache found. Building from source...")
    raw_df = load_raw_dataset()

    # EC-003: Empty raw dataset
    if len(raw_df) == 0:
        raise ValueError("[EC-003] Loaded dataset is empty — cannot proceed.")

    df = normalize(raw_df)

    # EC-004: All rows dropped during cleaning
    if len(df) == 0:
        raise ValueError(
            "[EC-004] No valid restaurants remain after cleaning. "
            "Check the dataset for widespread null values."
        )

    # Save cleaned cache (EC-802: catch disk errors gracefully)
    try:
        df.to_csv(CLEAN_CSV_PATH, index=False)
        logger.info("Cleaned dataset cached to: %s", CLEAN_CSV_PATH)
    except OSError as e:
        logger.warning("[EC-802] Could not save cleaned cache (disk error): %s", e)
        logger.warning("Continuing without cache — data is still in memory.")

    return df


def log_ingestion_stats(df: pd.DataFrame) -> None:
    """
    Task 1.5 — Print ingestion statistics to the log.
    Covers: total rows, unique locations, unique cuisines.
    """
    logger.info("=" * 50)
    logger.info("INGESTION STATS")
    logger.info("  Total clean records : %d", len(df))
    logger.info("  Unique locations    : %d", df["location"].nunique())
    logger.info("  Unique cuisines     : %d (approx)", df["cuisine"].str.split(",").explode().str.strip().nunique())
    logger.info("  Budget tier counts  :")
    for tier, count in df["budget_tier"].value_counts().items():
        logger.info("    %-8s : %d", tier, count)
    logger.info("  Rating range        : %.1f – %.1f", df["rating"].min(), df["rating"].max())
    logger.info("=" * 50)
