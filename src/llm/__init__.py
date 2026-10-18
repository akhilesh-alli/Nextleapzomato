"""
src/llm
-------
LLM Integration Layer:
  - LLMEngine: Unified interface for OpenAI, Gemini, and Ollama
  - build_prompt: Structured, grounded prompt construction
  - parse_output: Robust parsing and entity extraction of LLM recommendations
  - RecommendationItem, ParsedRecommendation: Structured output models
"""

from src.llm.engine import (
    LLMEngine,
    LLMError,
    LLMAuthenticationError,
    LLMTimeoutError,
    LLMRateLimitError,
    LLMEmptyResponseError,
)
from src.llm.prompt_builder import build_prompt
from src.llm.output_parser import (
    parse_output,
    RecommendationItem,
    ParsedRecommendation,
)

__all__ = [
    "LLMEngine",
    "LLMError",
    "LLMAuthenticationError",
    "LLMTimeoutError",
    "LLMRateLimitError",
    "LLMEmptyResponseError",
    "build_prompt",
    "parse_output",
    "RecommendationItem",
    "ParsedRecommendation",
]
