"""
config/settings.py
------------------
Central configuration for the AI Restaurant Recommendation System.
Loads all settings from environment variables via .env file.
"""

import os
import sys
from dotenv import load_dotenv

# Load .env from the project root
load_dotenv()

# ──────────────────────────────────────────────
# LLM Configuration
# ──────────────────────────────────────────────

SUPPORTED_PROVIDERS = {"groq", "openai", "gemini", "ollama"}

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq").lower()
_default_model = "llama-3.3-70b-versatile" if LLM_PROVIDER == "groq" else "gpt-4o-mini"
LLM_MODEL    = os.getenv("LLM_MODEL", _default_model)

GROQ_API_KEY   = os.getenv("GROQ_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# ──────────────────────────────────────────────
# Startup Validation
# ──────────────────────────────────────────────

def validate_config() -> None:
    """
    Validate configuration at startup.
    Raises SystemExit with a helpful message if critical config is missing.
    """
    # Validate provider
    if LLM_PROVIDER not in SUPPORTED_PROVIDERS:
        sys.exit(
            f"[Config Error] Unsupported LLM_PROVIDER: '{LLM_PROVIDER}'.\n"
            f"Valid options: {', '.join(sorted(SUPPORTED_PROVIDERS))}\n"
            f"Set LLM_PROVIDER in your .env file."
        )

    # Validate API keys based on provider
    if LLM_PROVIDER == "groq" and not GROQ_API_KEY:
        sys.exit(
            "[Config Error] GROQ_API_KEY is not set.\n"
            "Add it to your .env file:\n"
            "  GROQ_API_KEY=gsk_..."
        )

    if LLM_PROVIDER == "openai" and not OPENAI_API_KEY:
        sys.exit(
            "[Config Error] OPENAI_API_KEY is not set.\n"
            "Add it to your .env file:\n"
            "  OPENAI_API_KEY=sk-..."
        )

    if LLM_PROVIDER == "gemini" and not GEMINI_API_KEY:
        sys.exit(
            "[Config Error] GEMINI_API_KEY is not set.\n"
            "Add it to your .env file:\n"
            "  GEMINI_API_KEY=AI..."
        )

# ──────────────────────────────────────────────
# Data & Filtering Configuration
# ──────────────────────────────────────────────

# Budget tier cost ranges (INR, for two people)
BUDGET_TIERS: dict[str, tuple[int, float]] = {
    "low":    (0,   300),
    "medium": (301, 800),
    "high":   (801, float("inf")),
}

BUDGET_SYNONYMS: dict[str, str] = {
    "cheap":      "low",
    "affordable": "low",
    "budget":     "low",
    "moderate":   "medium",
    "mid":        "medium",
    "expensive":  "high",
    "premium":    "high",
    "luxury":     "high",
}

CITY_ALIASES: dict[str, str] = {
    "bengaluru": "bangalore",
    "bombay":    "mumbai",
    "calcutta":  "kolkata",
    "madras":    "chennai",
    "new delhi": "delhi",
}

# Max number of candidates passed to LLM (EC-307: token budget)
MAX_CANDIDATES: int = 20

# Max length of user free-text notes (EC-203)
MAX_NOTES_LENGTH: int = 200

# Default minimum rating if user provides none
DEFAULT_MIN_RATING: float = 0.0

# Rating relaxation step (EC-103)
RATING_RELAXATION_STEP: float = 0.5

# ──────────────────────────────────────────────
# File Paths
# ──────────────────────────────────────────────

import pathlib

# Project root = two levels up from this file (config/settings.py)
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent

DATA_DIR             = PROJECT_ROOT / "data"
RAW_DATASET_PATH     = DATA_DIR / "restaurants_raw.csv"
CLEAN_DATASET_PATH   = DATA_DIR / "restaurants_clean.csv"

# HuggingFace dataset identifier
HF_DATASET_NAME = "ManikaSaini/zomato-restaurant-recommendation"
HF_DATASET_SPLIT = "train"

# ──────────────────────────────────────────────
# LLM Request Settings
# ──────────────────────────────────────────────

LLM_TIMEOUT_SECONDS: int = 30
LLM_MAX_RETRIES:     int = 2
LLM_TEMPERATURE:     float = 0.7
LLM_MAX_TOKENS:      int = 1500
