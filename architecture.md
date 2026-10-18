# Architecture Design
## AI-Powered Restaurant Recommendation System (Zomato Use Case)

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [High-Level Architecture](#2-high-level-architecture)
3. [Component Breakdown](#3-component-breakdown)
   - 3.1 [Data Ingestion Layer](#31-data-ingestion-layer)
   - 3.2 [Data Processing & Storage Layer](#32-data-processing--storage-layer)
   - 3.3 [User Interface Layer](#33-user-interface-layer)
   - 3.4 [Integration Layer (Orchestrator)](#34-integration-layer-orchestrator)
   - 3.5 [LLM Recommendation Engine](#35-llm-recommendation-engine)
   - 3.6 [Output Presentation Layer](#36-output-presentation-layer)
4. [Data Flow Diagram](#4-data-flow-diagram)
5. [Folder Structure](#5-folder-structure)
6. [Module Design](#6-module-design)
7. [Prompt Engineering Strategy](#7-prompt-engineering-strategy)
8. [Tech Stack](#8-tech-stack)
9. [Scalability & Extension Points](#9-scalability--extension-points)
10. [Error Handling & Guardrails](#10-error-handling--guardrails)

---

## 1. System Overview

The system is a **Retrieval-Augmented Generation (RAG)-lite** application that:

1. Loads and indexes a real-world Zomato restaurant dataset
2. Filters restaurants using rule-based logic against user preferences
3. Passes candidate restaurants to an LLM for intelligent ranking, explanation, and summarization
4. Returns structured, human-readable recommendations to the user

The design follows a **modular, pipeline-based architecture** allowing each layer to be independently tested, replaced, or scaled.

---

## 2. High-Level Architecture

```
+---------------------------+
|       User Interface       |  <-- CLI / Streamlit / Web App
+---------------------------+
            |
            v
+---------------------------+
|   Input Validation &       |
|   Preference Collector     |
+---------------------------+
            |
            v
+---------------------------+
|   Data Filtering Engine    |  <-- pandas / SQL-style filtering
|  (Structured Restaurant DB)|
+---------------------------+
            |
            v
+---------------------------+
|   Prompt Builder /         |
|   Orchestration Layer      |  <-- Constructs LLM-ready context
+---------------------------+
            |
            v
+---------------------------+
|   LLM Recommendation       |
|       Engine               |  <-- OpenAI / Gemini / Ollama
+---------------------------+
            |
            v
+---------------------------+
|   Output Formatter &       |
|   Display Layer            |  <-- Structured results to user
+---------------------------+
```

---

## 3. Component Breakdown

### 3.1 Data Ingestion Layer

**Responsibility:** Load, validate, and normalize the Zomato dataset.

**Steps:**
- Pull dataset from Hugging Face Hub using the `datasets` library:
  `ManikaSaini/zomato-restaurant-recommendation`
- Convert to a `pandas` DataFrame
- Normalize column names (lowercase, underscores)
- Handle missing values: drop nulls in critical fields (name, location, rating, cost)
- Standardize budget tiers: map cost ranges to `low / medium / high`
- Cache the preprocessed dataset locally as `data/restaurants_clean.csv` to avoid re-downloading

**Key Fields Extracted:**

| Raw Field         | Normalized Field    | Description                      |
|-------------------|---------------------|----------------------------------|
| Restaurant Name   | `name`              | Name of the restaurant           |
| City / Location   | `location`          | City or neighborhood              |
| Cuisines          | `cuisine`           | Comma-separated cuisine types    |
| Average Cost      | `cost`              | Average cost for two (INR)       |
| Budget Tier       | `budget_tier`       | low / medium / high (derived)    |
| Aggregate Rating  | `rating`            | Float (0.0 – 5.0)                |
| Votes             | `votes`             | Number of user votes             |
| Online Delivery   | `online_delivery`   | Boolean                          |
| Table Booking     | `table_booking`     | Boolean                          |

---

### 3.2 Data Processing & Storage Layer

**Responsibility:** Efficient filtering and retrieval of candidate restaurants.

**Approach:**
- In-memory `pandas` DataFrame (suitable for dataset of this size)
- Filtering pipeline:
  1. **Location filter** – case-insensitive substring match on `location`
  2. **Budget filter** – map user budget tier to cost range and filter
  3. **Cuisine filter** – partial match across `cuisine` column
  4. **Rating filter** – `rating >= user_min_rating`
  5. **Additional filters** – boolean flags (e.g., online delivery, table booking)
- Limit filtered candidates to **top 20** by rating + votes score before passing to LLM
- Serialize candidate list to a structured JSON/string block for prompt injection

**Budget Tier Mapping:**

| Tier     | Cost Range (INR for 2) |
|----------|------------------------|
| `low`    | <= 300                 |
| `medium` | 301 – 800              |
| `high`   | > 800                  |

---

### 3.3 User Interface Layer

**Responsibility:** Capture user preferences and display final output.

**Implementation Options (choose one):**

| Mode         | Library     | Best For                          |
|--------------|-------------|-----------------------------------|
| CLI          | `argparse` / `rich` | Quick testing, developer use  |
| Interactive  | `Streamlit` | Demo, non-technical users         |
| Web App      | FastAPI + HTML/JS | Production-ready deployment   |

**User Input Schema:**

```python
class UserPreferences:
    location: str            # e.g., "Bangalore"
    budget: str              # "low" | "medium" | "high"
    cuisine: str             # e.g., "Italian"
    min_rating: float        # e.g., 4.0
    online_delivery: bool    # True | False
    table_booking: bool      # True | False
    extra_notes: str         # Free-text additional preferences
```

---

### 3.4 Integration Layer (Orchestrator)

**Responsibility:** Bridge structured data with the LLM.

**Steps:**
1. Receive `UserPreferences` object from UI layer
2. Call `DataFilteringEngine.filter(preferences)` → returns list of candidate restaurants
3. If no candidates found: return a graceful "no restaurants found" message
4. Serialize candidates into a structured text block
5. Call `PromptBuilder.build(preferences, candidates)` → returns final prompt string
6. Call `LLMEngine.query(prompt)` → returns LLM response
7. Parse and return structured output to the UI

**Orchestrator Pseudocode:**

```python
def get_recommendations(preferences: UserPreferences) -> RecommendationResult:
    candidates = data_filter.filter(preferences)
    if not candidates:
        return RecommendationResult(error="No restaurants matched your criteria.")
    prompt = prompt_builder.build(preferences, candidates)
    raw_response = llm_engine.query(prompt)
    return output_parser.parse(raw_response)
```

---

### 3.5 LLM Recommendation Engine

**Responsibility:** Rank, explain, and summarize restaurant recommendations.

**LLM Tasks:**
- Rank candidate restaurants from the filtered list
- Generate a personalized explanation for each recommended restaurant
- Optionally produce a brief summary comparing the top choices

**Supported LLM Backends:**

| Backend     | Library              | Notes                              |
|-------------|----------------------|------------------------------------|
| OpenAI GPT  | `openai`             | Best quality, requires API key     |
| Google Gemini | `google-generativeai` | Great for Indian context         |
| Ollama      | `ollama` (local)     | Free, runs locally, privacy-safe   |
| HuggingFace | `transformers`       | Open-source, customizable          |

**LLM Interface (abstracted):**

```python
class LLMEngine:
    def __init__(self, provider: str, model: str, api_key: str = None): ...
    def query(self, prompt: str) -> str: ...
```

---

### 3.6 Output Presentation Layer

**Responsibility:** Parse and format the LLM response into a clean structure.

**Output Format per Restaurant:**

```
--------------------------------------------------
 #1  The Spice Route
--------------------------------------------------
 Cuisine      : Indian, Mughlai
 Rating       : 4.6 / 5.0
 Estimated Cost: Rs. 700 for two
 Location     : Connaught Place, Delhi

 Why we recommend it:
 "Perfect for your medium budget, The Spice Route
  offers authentic Mughlai cuisine in a family-friendly
  atmosphere with excellent ratings from 2,400+ diners."
--------------------------------------------------
```

---

## 4. Data Flow Diagram

```
[Hugging Face Dataset]
        |
        v
[Data Ingestion] --> [Clean CSV Cache] --> [In-Memory DataFrame]
                                                  |
                                    [User Preferences Input]
                                                  |
                                                  v
                                    [Data Filtering Engine]
                                    (location, budget, cuisine,
                                      rating, extra filters)
                                                  |
                                        [Candidate List (<=20)]
                                                  |
                                                  v
                                       [Prompt Builder]
                                    (Injects candidates +
                                     user context into prompt)
                                                  |
                                                  v
                                        [LLM Engine Call]
                                    (Rank + Explain + Summarize)
                                                  |
                                                  v
                                      [Output Parser/Formatter]
                                                  |
                                                  v
                                    [User-Facing Recommendation]
```

---

## 5. Folder Structure

```
next-leap-ai-restaurant/
|
|-- data/
|   |-- restaurants_clean.csv       # Cached preprocessed dataset
|
|-- src/
|   |-- ingestion/
|   |   |-- __init__.py
|   |   |-- loader.py               # Loads & preprocesses HF dataset
|   |   |-- normalizer.py           # Normalizes columns, maps budget tiers
|   |
|   |-- filtering/
|   |   |-- __init__.py
|   |   |-- filter_engine.py        # Rule-based filtering logic
|   |   |-- models.py               # UserPreferences dataclass
|   |
|   |-- llm/
|   |   |-- __init__.py
|   |   |-- engine.py               # Abstracted LLM backend interface
|   |   |-- prompt_builder.py       # Constructs LLM prompts
|   |   |-- output_parser.py        # Parses & structures LLM response
|   |
|   |-- orchestrator.py             # Main pipeline coordinator
|
|-- ui/
|   |-- cli.py                      # Rich CLI interface
|   |-- streamlit_app.py            # Streamlit web UI
|
|-- config/
|   |-- settings.py                 # API keys, model names, budget tiers
|   |-- .env                        # Environment variables (gitignored)
|
|-- tests/
|   |-- test_ingestion.py
|   |-- test_filtering.py
|   |-- test_llm.py
|   |-- test_orchestrator.py
|
|-- requirements.txt
|-- README.md
|-- problemStatement.md
|-- architecture.md
```

---

## 6. Module Design

### `loader.py`
```python
from datasets import load_dataset
import pandas as pd

def load_zomato_dataset() -> pd.DataFrame:
    """Load and cache the Zomato HF dataset as a DataFrame."""
    dataset = load_dataset("ManikaSaini/zomato-restaurant-recommendation")
    df = dataset["train"].to_pandas()
    return df
```

### `filter_engine.py`
```python
def filter_restaurants(df, prefs: UserPreferences) -> pd.DataFrame:
    result = df.copy()
    if prefs.location:
        result = result[result["location"].str.contains(prefs.location, case=False, na=False)]
    if prefs.cuisine:
        result = result[result["cuisine"].str.contains(prefs.cuisine, case=False, na=False)]
    if prefs.min_rating:
        result = result[result["rating"] >= prefs.min_rating]
    if prefs.budget:
        result = result[result["budget_tier"] == prefs.budget]
    return result.sort_values("rating", ascending=False).head(20)
```

### `prompt_builder.py`
```python
def build_prompt(preferences: UserPreferences, candidates: list[dict]) -> str:
    candidate_text = "\n".join([
        f"- {r['name']} | Cuisine: {r['cuisine']} | Rating: {r['rating']} | "
        f"Cost: Rs.{r['cost']} | Location: {r['location']}"
        for r in candidates
    ])
    return f"""
You are a restaurant recommendation expert. A user is looking for restaurants with these preferences:
- Location: {preferences.location}
- Budget: {preferences.budget}
- Cuisine: {preferences.cuisine}
- Minimum Rating: {preferences.min_rating}
- Additional Notes: {preferences.extra_notes}

Here are candidate restaurants from the database:
{candidate_text}

Please:
1. Select the top 5 restaurants best matching the user preferences.
2. For each, provide a personalized explanation (2-3 sentences) of why it fits.
3. Give a brief summary comparing all 5 choices.

Format your response clearly with restaurant names as headers.
"""
```

---

## 7. Prompt Engineering Strategy

| Principle             | Implementation                                          |
|-----------------------|---------------------------------------------------------|
| **Context Grounding** | Always inject real filtered restaurant data into prompt |
| **Role Assignment**   | LLM is framed as a "restaurant recommendation expert"   |
| **Structured Output** | Ask LLM for numbered rankings with explanations         |
| **Tone**              | Warm, helpful, human-like language                      |
| **Fallback**          | If LLM returns unstructured text, regex-parse it        |
| **Token Budget**      | Cap candidate list at 20 entries to stay within limits  |

---

## 8. Tech Stack

| Layer                  | Technology                          | Purpose                            |
|------------------------|-------------------------------------|------------------------------------|
| Dataset                | `datasets` (Hugging Face)           | Load Zomato restaurant data        |
| Data Processing        | `pandas`                            | Filter, sort, normalize             |
| LLM Backend            | `openai` / `google-generativeai`    | Generate ranked recommendations    |
| Local LLM (optional)   | `ollama`                            | Privacy-safe local inference       |
| CLI Interface          | `rich`, `argparse`                  | Terminal-based user interaction    |
| Web UI (optional)      | `Streamlit`                         | Browser-based interactive demo     |
| Config Management      | `python-dotenv`                     | API key & env management           |
| Testing                | `pytest`                            | Unit & integration tests           |
| Packaging              | `requirements.txt` / `pyproject.toml` | Dependency management             |

---

## 9. Scalability & Extension Points

| Feature                    | How to Extend                                              |
|----------------------------|------------------------------------------------------------|
| Vector Search              | Add `FAISS` / `ChromaDB` for semantic restaurant search    |
| Multi-language Support     | Translate output via LLM or `googletrans`                  |
| Real-time Data             | Replace HF dataset with live Zomato/Swiggy API feed        |
| User Profiles              | Store preferences in SQLite / Redis for personalization    |
| Feedback Loop              | Collect ratings on recommendations to fine-tune filtering  |
| Caching LLM Responses      | Use `Redis` / `diskcache` to cache repeated queries        |
| REST API                   | Wrap orchestrator in a `FastAPI` endpoint                  |
| Containerization           | Dockerize for deployment on cloud (GCP / AWS / Azure)      |

---

## 10. Error Handling & Guardrails

| Scenario                        | Handling Strategy                                        |
|---------------------------------|----------------------------------------------------------|
| No restaurants match filters    | Return friendly message; suggest relaxing filters        |
| LLM API failure / timeout       | Retry once; fallback to top-rated filtered list only     |
| Dataset not available           | Load from local cache `data/restaurants_clean.csv`       |
| Malformed LLM response          | Regex-based parser to extract key fields                 |
| Invalid user input              | Input validation with clear error messages               |
| API key missing                 | Early exit with instructions on setting up `.env`        |

---

*Architecture Document — AI-Powered Restaurant Recommendation System*
*Version 1.0 | Next Leap AI Project*
