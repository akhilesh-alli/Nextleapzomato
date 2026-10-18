"""
src/filtering/models.py
-----------------------
Data models for the filtering layer.

Defines:
  - UserPreferences  : input schema from the user
  - FilterResult     : output schema from the filter engine
"""

import sys
from dataclasses import dataclass, field


# ── UserPreferences ──────────────────────────────────────────────────────────

@dataclass
class UserPreferences:
    """
    Captures everything a user wants in a restaurant recommendation.

    Fields
    ------
    location        : City / neighborhood (e.g. "Bangalore", "Delhi")
    budget          : "low" | "medium" | "high"  (maps to cost ranges in settings.py)
    cuisine         : Cuisine type, partial match (e.g. "Italian", "North Indian")
    min_rating      : Minimum acceptable rating  [0.0 – 5.0]
    online_delivery : If True, only restaurants offering online delivery are included
    table_booking   : If True, only restaurants offering table booking are included
    extra_notes     : Free-text additional preferences forwarded to the LLM prompt

    Edge-case guards applied by validators below:
      EC-201  min_rating clamped to [0.0, 5.0]
      EC-202  budget mapped from synonyms (cheap → low, etc.)
      EC-203  extra_notes truncated to MAX_NOTES_LENGTH
      EC-205  location must contain at least one alpha character
    """
    location:        str   = ""
    budget:          str   = ""       # "low" | "medium" | "high" | ""
    cuisine:         str   = ""
    min_rating:      float = 0.0
    online_delivery: bool  = False
    table_booking:   bool  = False
    extra_notes:     str   = ""

    # ── post-init validation & normalisation ─────────────────────────────────

    def __post_init__(self) -> None:
        self._validate_and_normalise()

    def _validate_and_normalise(self) -> None:
        from config.settings import (
            BUDGET_SYNONYMS, MAX_NOTES_LENGTH,
            DEFAULT_MIN_RATING,
        )

        # EC-201: clamp min_rating to [0.0, 5.0]
        if self.min_rating < 0.0 or self.min_rating > 5.0:
            clamped = max(0.0, min(5.0, self.min_rating))
            self.min_rating = clamped

        # EC-202: map budget synonyms to canonical tiers
        canonical_tiers = {"low", "medium", "high", ""}
        budget_lower = self.budget.strip().lower()
        if budget_lower in BUDGET_SYNONYMS:
            self.budget = BUDGET_SYNONYMS[budget_lower]
        elif budget_lower in canonical_tiers:
            self.budget = budget_lower
        else:
            # Unknown tier — ignore and apply no budget filter
            self.budget = ""

        # EC-203: truncate extra_notes
        if len(self.extra_notes) > MAX_NOTES_LENGTH:
            self.extra_notes = self.extra_notes[:MAX_NOTES_LENGTH]

        # EC-204: strip emojis / non-ASCII from location
        import re, unicodedata
        loc = unicodedata.normalize("NFC", self.location)
        loc = re.sub(r"[^\x00-\x7F]+", "", loc).strip()
        self.location = loc

        # EC-205: numeric-only location is rejected
        if self.location and not any(c.isalpha() for c in self.location):
            raise ValueError(
                f"[EC-205] Location '{self.location}' appears to contain no alphabetic characters. "
                f"Please enter a valid city name."
            )

        # Apply city aliases (e.g. bengaluru → bangalore)
        from config.settings import CITY_ALIASES
        loc_key = self.location.strip().lower()
        if loc_key in CITY_ALIASES:
            # Replace only the alias part, preserve original casing structure
            self.location = CITY_ALIASES[loc_key].title()

        # Normalise cuisine: strip and title-case
        self.cuisine = self.cuisine.strip()

    # ── convenience helpers ───────────────────────────────────────────────────

    def is_empty(self) -> bool:
        """Return True if no meaningful filter criteria have been set."""
        return not (
            self.location or self.budget or self.cuisine
            or self.min_rating > 0.0
            or self.online_delivery or self.table_booking
        )

    def to_dict(self) -> dict:
        return {
            "location":        self.location,
            "budget":          self.budget,
            "cuisine":         self.cuisine,
            "min_rating":      self.min_rating,
            "online_delivery": self.online_delivery,
            "table_booking":   self.table_booking,
            "extra_notes":     self.extra_notes,
        }

    def __repr__(self) -> str:
        return (
            f"UserPreferences(location={self.location!r}, budget={self.budget!r}, "
            f"cuisine={self.cuisine!r}, min_rating={self.min_rating}, "
            f"online_delivery={self.online_delivery}, table_booking={self.table_booking})"
        )


# ── FilterResult ─────────────────────────────────────────────────────────────

@dataclass
class FilterResult:
    """
    Output of the filter engine.

    Attributes
    ----------
    candidates      : List of matching restaurant dicts (max 20)
    total_searched  : Number of rows in the full dataset that were searched
    total_matched   : Number of rows that passed all filters (before top-N cap)
    relaxed         : True if any filter was relaxed to produce results
    relaxation_note : Human-readable note about which filter was relaxed
    error           : Non-empty string if no results found (for UI display)
    """
    candidates:      list  = field(default_factory=list)
    total_searched:  int   = 0
    total_matched:   int   = 0
    relaxed:         bool  = False
    relaxation_note: str   = ""
    error:           str   = ""

    @property
    def has_results(self) -> bool:
        return len(self.candidates) > 0

    @property
    def count(self) -> int:
        return len(self.candidates)
