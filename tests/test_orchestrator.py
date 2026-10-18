"""
tests/test_orchestrator.py
--------------------------
Unit & Integration tests for Phase 4: Orchestration Layer.

Covers:
  - Task 4.1: Orchestrator execution flow
  - Task 4.2: RecommendationResult contract
  - Task 4.3: Timing telemetry & candidate logging
  - EC-601: Guard against None or empty filter result
  - EC-602: Graceful database fallback when LLM query fails
  - EC-701: Location required validation
"""

from unittest.mock import MagicMock, patch
import pandas as pd
import pytest

from src.filtering.models import FilterResult, UserPreferences
from src.llm.engine import LLMEngine, LLMError, LLMTimeoutError
from src.orchestrator import Orchestrator, RecommendationResult


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_df() -> pd.DataFrame:
    """Minimal normalized DataFrame for testing."""
    return pd.DataFrame([
        {
            "name": "Truffles",
            "location": "Koramangala",
            "cuisine": "American, Fast Food, Burger",
            "cost": 600,
            "budget_tier": "medium",
            "rating": 4.5,
            "votes": 12000,
            "online_delivery": True,
            "table_booking": False,
            "restaurant_type": "Casual Dining",
            "dish_liked": "Burgers, Steaks",
            "listed_type": "Dine-out",
            "listed_city": "Koramangala",
            "address": "St Marks Road",
            "url": "http://truffles.test",
        },
        {
            "name": "Toit Brewpub",
            "location": "Indiranagar",
            "cuisine": "Italian, Pizza, Finger Food",
            "cost": 1500,
            "budget_tier": "high",
            "rating": 4.6,
            "votes": 15000,
            "online_delivery": False,
            "table_booking": True,
            "restaurant_type": "Microbrewery",
            "dish_liked": "Pizzas, Brews",
            "listed_type": "Pubs and Bars",
            "listed_city": "Indiranagar",
            "address": "100ft Road",
            "url": "http://toit.test",
        },
        {
            "name": "Meghana Foods",
            "location": "Koramangala",
            "cuisine": "Biryani, Andhra",
            "cost": 500,
            "budget_tier": "medium",
            "rating": 4.4,
            "votes": 8500,
            "online_delivery": True,
            "table_booking": False,
            "restaurant_type": "Quick Bites",
            "dish_liked": "Chicken Biryani",
            "listed_type": "Delivery",
            "listed_city": "Koramangala",
            "address": "5th Block",
            "url": "http://meghana.test",
        },
    ])


@pytest.fixture
def mock_llm_response() -> str:
    return """
### 1. Truffles
- **Cuisine**: American, Fast Food, Burger
- **Rating**: 4.5 / 5.0
- **Estimated Cost**: Rs. 600 for two
- **Location**: Koramangala
- **Why we recommend it**: Truffles is famous for its legendary burgers and vibrant youthful atmosphere, fitting your medium budget perfectly.

### 2. Meghana Foods
- **Cuisine**: Biryani, Andhra
- **Rating**: 4.4 / 5.0
- **Estimated Cost**: Rs. 500 for two
- **Location**: Koramangala
- **Why we recommend it**: Outstanding spicy Andhra biryani with fast service and great value for money.

### Summary
For delicious burgers, pick Truffles; for mouth-watering Andhra biryani, head to Meghana Foods.
"""


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_orchestrator_initialization(sample_df):
    """Test dependency injection in Orchestrator."""
    mock_llm = MagicMock(spec=LLMEngine)
    orch = Orchestrator(df=sample_df, llm=mock_llm)

    assert orch.df is sample_df
    assert orch.llm is mock_llm


def test_orchestrator_successful_recommendation(sample_df, mock_llm_response):
    """E2E test: from UserPreferences to complete RecommendationResult."""
    mock_llm = MagicMock(spec=LLMEngine)
    mock_llm.query.return_value = mock_llm_response

    orch = Orchestrator(df=sample_df, llm=mock_llm)
    prefs = UserPreferences(location="Koramangala", budget="medium")

    result = orch.recommend(prefs)

    assert isinstance(result, RecommendationResult)
    assert result.is_success is True
    assert result.error == ""
    assert result.is_fallback is False
    assert len(result.recommendations) >= 2
    assert result.recommendations[0].name == "Truffles"
    assert result.recommendations[0].rank == 1
    assert "burgers" in result.recommendations[0].explanation.lower()
    assert "Truffles" in result.summary

    # Task 4.3: Telemetry timings
    assert "filter_time_ms" in result.timings
    assert "llm_time_ms" in result.timings
    assert "total_time_ms" in result.timings
    assert result.candidate_count >= 2


def test_orchestrator_empty_location_guard(sample_df):
    """EC-701: Missing location returns error immediately without querying LLM."""
    mock_llm = MagicMock(spec=LLMEngine)
    orch = Orchestrator(df=sample_df, llm=mock_llm)

    prefs = UserPreferences(location="", budget="low")
    result = orch.recommend(prefs)

    assert result.is_success is False
    assert "Location is required" in result.error
    assert mock_llm.query.call_count == 0


def test_orchestrator_no_matching_restaurants(sample_df):
    """Returns clean error result when no restaurants match the query."""
    mock_llm = MagicMock(spec=LLMEngine)
    orch = Orchestrator(df=sample_df, llm=mock_llm)

    prefs = UserPreferences(location="NonexistentCityXYZ")
    result = orch.recommend(prefs)

    assert result.is_success is False
    assert len(result.recommendations) == 0
    assert "No restaurants found" in result.error or "No restaurants matched" in result.error
    assert mock_llm.query.call_count == 0


def test_orchestrator_filter_returns_none(sample_df):
    """EC-601: Orchestrator safely handles filter_restaurants returning None."""
    mock_llm = MagicMock(spec=LLMEngine)
    orch = Orchestrator(df=sample_df, llm=mock_llm)

    with patch("src.orchestrator.filter_restaurants", return_value=None):
        prefs = UserPreferences(location="Koramangala")
        result = orch.recommend(prefs)

        assert result.is_success is False
        assert result.error != ""
        assert mock_llm.query.call_count == 0


def test_orchestrator_llm_failure_graceful_fallback(sample_df):
    """
    EC-602: When LLM call fails, orchestrator gracefully falls back
    to top-rated database candidates without crashing.
    """
    mock_llm = MagicMock(spec=LLMEngine)
    mock_llm.query.side_effect = LLMTimeoutError("[EC-302] Request timed out")

    orch = Orchestrator(df=sample_df, llm=mock_llm)
    prefs = UserPreferences(location="Koramangala", budget="medium")

    result = orch.recommend(prefs)

    # Must produce valid recommendations despite LLM failure
    assert result.has_recommendations is True
    assert result.is_fallback is True
    assert len(result.recommendations) >= 1
    first = result.recommendations[0]
    assert first.name == "Truffles"
    assert "AI service temporarily unavailable" in result.summary


def test_orchestrator_to_dict_serialization(sample_df, mock_llm_response):
    """Tests dictionary serialization of RecommendationResult for UI/API consumption."""
    mock_llm = MagicMock(spec=LLMEngine)
    mock_llm.query.return_value = mock_llm_response

    orch = Orchestrator(df=sample_df, llm=mock_llm)
    prefs = UserPreferences(location="Koramangala")
    result = orch.recommend(prefs)

    data = result.to_dict()
    assert isinstance(data, dict)
    assert data["success"] is True
    assert "recommendations" in data
    assert isinstance(data["recommendations"], list)
    assert "timings_ms" in data
