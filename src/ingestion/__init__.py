"""
src/ingestion
-------------
Public API for Phase 1 — Data Ingestion & Preprocessing.
"""

from src.ingestion.loader import load_clean_dataset, load_raw_dataset, log_ingestion_stats
from src.ingestion.normalizer import normalize, normalize_location_string

__all__ = [
    "load_clean_dataset",
    "load_raw_dataset",
    "log_ingestion_stats",
    "normalize",
    "normalize_location_string",
]
