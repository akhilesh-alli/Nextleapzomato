# Phase-Wise Implementation Plan
## AI-Powered Restaurant Recommendation System (Zomato Use Case)
*Next Leap AI Project | Version 1.0*

---

## Overview

This document outlines a structured, phase-by-phase implementation roadmap derived from the `architecture.md` and `problemStatement.md`. Each phase is self-contained with clear goals, deliverables, tasks, and acceptance criteria.

| Phase | Name                            | Estimated Effort |
|-------|---------------------------------|-----------------|
| 0     | Project Setup & Environment     | 0.5 day         |
| 1     | Data Ingestion & Preprocessing  | 1 day           |
| 2     | Filtering Engine                | 1 day           |
| 3     | LLM Integration & Prompt Design | 1.5 days        |
| 4     | Orchestration Layer             | 0.5 day         |
| 5     | User Interface (CLI / Streamlit)| 1 day           |
| 6     | Output Formatting & Display     | 0.5 day         |
| 7     | Testing & Validation            | 1 day           |
| 8     | Polish, Docs & Deployment Prep  | 0.5 day         |

**Total Estimated Effort: ~7 days**

---

## Phase 0 — Project Setup & Environment

### Goal
Establish the project skeleton, development environment, and dependency management before writing any logic.

### Tasks

- [ ] **0.1** Create the root project folder `next-leap-ai-restaurant/`
- [ ] **0.2** Initialise a Python virtual environment
  ```bash
  python -m venv .venv
  source .venv/bin/activate   # Windows: .venv\Scripts\activate
  ```
- [ ] **0.3** Create `requirements.txt` with initial dependencies:
  ```
  datasets
  pandas
  openai
  google-generativeai
  python-dotenv
  rich
  streamlit
  pytest
  ```
- [ ] **0.4** Install dependencies:
  ```bash
  pip install -r requirements.txt
  ```
- [ ] **0.5** Create `.env` file for API keys (add to `.gitignore`):
  ```
  OPENAI_API_KEY=your_key_here
  GEMINI_API_KEY=your_key_here
  LLM_PROVIDER=openai          # openai | gemini | ollama
  LLM_MODEL=gpt-4o-mini
  ```
- [ ] **0.6** Create `config/settings.py` to load env variables:
  ```python
  from dotenv import load_dotenv
  import os
  load_dotenv()

  OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
  GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
  LLM_PROVIDER   = os.getenv("LLM_PROVIDER", "openai")
  LLM_MODEL      = os.getenv("LLM_MODEL", "gpt-4o-mini")

  BUDGET_TIERS = {
      "low":    (0, 300),
      "medium": (301, 800),
      "high":   (801, float("inf"))
  }
  MAX_CANDIDATES = 20
  ```
- [ ] **0.7** Create the full folder structure as defined in `architecture.md`
- [ ] **0.8** Initialise a Git repository and create `.gitignore`

### Deliverables
- Working project scaffold with all directories
- `requirements.txt`, `.env.example`, `config/settings.py`
- Git repository initialised

### Acceptance Criteria
- `pip install -r requirements.txt` runs without errors
- `from config.settings import LLM_PROVIDER` works in Python

---

## Phase 1 — Data Ingestion & Preprocessing

### Goal
Load the Hugging Face Zomato dataset, clean it, normalize fields, and cache it locally for fast reuse.

### Reference
- Architecture Section 3.1 — *Data Ingestion Layer*
- Dataset: `ManikaSaini/zomato-restaurant-recommendation`

### Tasks

- [ ] **1.1** Create `src/ingestion/loader.py`
  - Load the HuggingFace dataset using `datasets.load_dataset()`
  - Convert to a `pandas` DataFrame
  - Save raw dataset to `data/restaurants_raw.csv`

- [ ] **1.2** Explore dataset columns interactively (Jupyter or script):
  - Print `.columns`, `.dtypes`, `.head()`, `.isnull().sum()`
  - Document the actual column names from the raw dataset

- [ ] **1.3** Create `src/ingestion/normalizer.py`
  - Rename columns to snake_case normalized names:
    - `Restaurant Name` → `name`
    - `City` → `location`
    - `Cuisines` → `cuisine`
    - `Average Cost for two` → `cost`
    - `Aggregate rating` → `rating`
    - `Votes` → `votes`
    - `Has Online delivery` → `online_delivery`
    - `Has Table booking` → `table_booking`
  - Drop rows where `name`, `location`, `rating`, or `cost` is null
  - Convert `rating` to float; replace `"NEW"` or `"-"` with `NaN` then drop
  - Convert `cost` to int (strip commas if present)
  - Map `cost` values to `budget_tier` using `config/settings.py` ranges
  - Save cleaned dataset to `data/restaurants_clean.csv`

- [ ] **1.4** Add cache-check logic in `loader.py`:
  ```python
  if os.path.exists("data/restaurants_clean.csv"):
      return pd.read_csv("data/restaurants_clean.csv")
  ```

- [ ] **1.5** Log ingestion stats: total rows loaded, rows dropped, unique locations, unique cuisines

### Deliverables
- `src/ingestion/loader.py`
- `src/ingestion/normalizer.py`
- `data/restaurants_clean.csv` (cached output)

### Acceptance Criteria
- Dataset loads without errors
- `restaurants_clean.csv` contains all required normalized columns
- No null values in `name`, `location`, `rating`, `cost`
- `budget_tier` column is correctly populated

---

## Phase 2 — Filtering Engine

### Goal
Build a robust, composable rule-based filtering engine that narrows the dataset to relevant candidates based on user preferences.

### Reference
- Architecture Section 3.2 — *Data Processing & Storage Layer*
- Architecture Section 6 — `filter_engine.py` module design

### Tasks

- [ ] **2.1** Create `src/filtering/models.py` — define `UserPreferences` dataclass:
  ```python
  from dataclasses import dataclass, field

  @dataclass
  class UserPreferences:
      location: str = ""
      budget: str = ""            # "low" | "medium" | "high"
      cuisine: str = ""
      min_rating: float = 0.0
      online_delivery: bool = False
      table_booking: bool = False
      extra_notes: str = ""
  ```

- [ ] **2.2** Create `src/filtering/filter_engine.py`:
  - Implement `filter_restaurants(df, prefs)` function
  - Apply filters sequentially:
    1. Location: case-insensitive substring match
    2. Budget tier: exact match on `budget_tier`
    3. Cuisine: case-insensitive partial match (handle multi-cuisine rows like `"Italian, Chinese"`)
    4. Min rating: `rating >= prefs.min_rating`
    5. Online delivery: boolean match (only if `prefs.online_delivery=True`)
    6. Table booking: boolean match (only if `prefs.table_booking=True`)
  - Sort by `rating` descending, secondary sort by `votes` descending
  - Return top N=20 results (from `config/settings.py`)

- [ ] **2.3** Handle edge cases:
  - If location not found → return empty DataFrame with a flag
  - If too few results (<3) after filtering → relax cuisine filter and retry

- [ ] **2.4** Write a quick smoke test script `tests/test_filtering.py`:
  - Test with known location (e.g., "Delhi") + cuisine ("Indian")
  - Assert result is non-empty and all ratings >= min_rating

### Deliverables
- `src/filtering/models.py`
- `src/filtering/filter_engine.py`
- `tests/test_filtering.py`

### Acceptance Criteria
- Filter returns correct, non-empty results for common queries
- All returned rows satisfy all active filter conditions
- Empty result is handled gracefully with a clear signal

---

## Phase 3 — LLM Integration & Prompt Design

### Goal
Integrate the LLM backend, engineer an effective prompt, and implement response parsing to produce structured recommendations.

### Reference
- Architecture Section 3.5 — *LLM Recommendation Engine*
- Architecture Section 7 — *Prompt Engineering Strategy*

### Tasks

- [ ] **3.1** Create `src/llm/engine.py` — Abstracted LLM interface:
  ```python
  class LLMEngine:
      def __init__(self, provider, model, api_key=None): ...
      def query(self, prompt: str) -> str: ...
  ```
  - Implement `_query_openai()` using `openai` SDK
  - Implement `_query_gemini()` using `google-generativeai` SDK
  - Select backend from `config/settings.py` `LLM_PROVIDER`
  - Add retry logic (max 2 retries on timeout/rate-limit)

- [ ] **3.2** Create `src/llm/prompt_builder.py`:
  - Implement `build_prompt(preferences, candidates)` function
  - Inject user preferences clearly in a structured block
  - Inject candidate restaurant list (max 20) as formatted text
  - Include explicit instructions for:
    - Select top 5 restaurants
    - Give 2-3 sentence explanation per restaurant
    - Brief comparative summary at the end
  - Ask LLM to format output with restaurant name as a header (e.g., `### 1. Restaurant Name`)

- [ ] **3.3** Design and iterate on the prompt template:
  - Test prompt with 3–5 different preference combos
  - Evaluate: Are explanations relevant? Are rankings sensible?
  - Refine wording until responses are consistently good

- [ ] **3.4** Create `src/llm/output_parser.py`:
  - Parse LLM text response into a list of structured dicts:
    ```python
    {
        "rank": 1,
        "name": "Restaurant Name",
        "explanation": "...",
        "summary": "..."
    }
    ```
  - Use regex or string splitting to extract sections by `###` headers
  - Extract final summary paragraph (last section)
  - Fallback: if parsing fails, return raw LLM text as single item

- [ ] **3.5** Write `tests/test_llm.py`:
  - Mock the LLM API call
  - Test `prompt_builder` produces valid non-empty prompt
  - Test `output_parser` on a sample LLM response string

### Deliverables
- `src/llm/engine.py`
- `src/llm/prompt_builder.py`
- `src/llm/output_parser.py`
- `tests/test_llm.py`

### Acceptance Criteria
- LLM call returns a non-empty string response
- `output_parser` correctly extracts at least 1 restaurant with explanation
- Prompt length stays within LLM token limits (~2000 tokens)
- API errors are caught and retried

---

## Phase 4 — Orchestration Layer

### Goal
Wire all components together into a single, clean pipeline coordinator that the UI can call with a simple interface.

### Reference
- Architecture Section 3.4 — *Integration Layer (Orchestrator)*

### Tasks

- [ ] **4.1** Create `src/orchestrator.py`:
  ```python
  class Orchestrator:
      def __init__(self): 
          self.df = load_zomato_dataset()
          self.llm = LLMEngine(...)
      
      def recommend(self, preferences: UserPreferences) -> RecommendationResult:
          candidates = filter_restaurants(self.df, preferences)
          if candidates.empty:
              return RecommendationResult(error="No matches found.")
          prompt = build_prompt(preferences, candidates.to_dict("records"))
          raw = self.llm.query(prompt)
          parsed = parse_output(raw)
          return RecommendationResult(recommendations=parsed)
  ```

- [ ] **4.2** Define `RecommendationResult` dataclass:
  ```python
  @dataclass
  class RecommendationResult:
      recommendations: list = field(default_factory=list)
      error: str = ""
      raw_response: str = ""
  ```

- [ ] **4.3** Add timing/logging to the orchestrator:
  - Log: time taken for filtering, LLM call, parsing
  - Log: number of candidates passed to LLM

- [ ] **4.4** Write `tests/test_orchestrator.py`:
  - End-to-end test with mocked LLM
  - Verify result object is populated correctly

### Deliverables
- `src/orchestrator.py`
- `tests/test_orchestrator.py`

### Acceptance Criteria
- `orchestrator.recommend(prefs)` returns a valid `RecommendationResult`
- Error case (no matches) is handled and returned cleanly
- Pipeline completes in < 30 seconds end-to-end

---

## Phase 5 — User Interface

### Goal
Build both a CLI and Streamlit UI so users can interactively input preferences and receive recommendations.

### Reference
- Architecture Section 3.3 — *User Interface Layer*

### Tasks

#### Sub-phase 5A — CLI Interface

- [ ] **5A.1** Create `ui/cli.py` using `rich` library:
  - Display a welcome banner
  - Prompt user for each preference field interactively:
    - Location (text input)
    - Budget (choice: low / medium / high)
    - Cuisine (text input)
    - Minimum rating (float input, default 3.5)
    - Online delivery? (y/n)
    - Table booking? (y/n)
    - Additional notes (optional text)
  - Validate inputs; re-prompt on invalid values
  - Call `Orchestrator.recommend(preferences)` and display results

- [ ] **5A.2** Add a loading spinner while LLM is processing:
  ```python
  with Progress() as progress:
      task = progress.add_task("Getting recommendations...", total=None)
  ```

#### Sub-phase 5B — Streamlit Web UI

- [ ] **5B.1** Create `ui/streamlit_app.py`:
  - Title + description header
  - Sidebar for preference inputs:
    - `st.text_input` for location and cuisine
    - `st.selectbox` for budget tier
    - `st.slider` for minimum rating (0.0 – 5.0)
    - `st.checkbox` for online delivery and table booking
    - `st.text_area` for additional notes
  - "Find Restaurants" button triggers `Orchestrator.recommend()`
  - Display results as styled `st.expander` cards per restaurant
  - Show spinner during LLM processing with `st.spinner`

- [ ] **5B.2** Add session state to avoid re-running on re-render:
  ```python
  if "result" not in st.session_state:
      st.session_state.result = None
  ```

- [ ] **5B.3** Run Streamlit locally:
  ```bash
  streamlit run ui/streamlit_app.py
  ```

### Deliverables
- `ui/cli.py`
- `ui/streamlit_app.py`

### Acceptance Criteria
- CLI collects all preferences and displays formatted output
- Streamlit app loads in browser without errors
- Both UIs correctly call the orchestrator and render results

---

## Phase 6 — Output Formatting & Display

### Goal
Polish how recommendations are rendered — both in CLI and Streamlit — so the output is clear, structured, and user-friendly.

### Reference
- Architecture Section 3.6 — *Output Presentation Layer*
- Problem Statement: *Output Display* section

### Tasks

- [ ] **6.1** CLI output format using `rich`:
  - Display each restaurant as a styled panel:
    ```
    ╭─────────────────────────────────────────╮
    │  #1  The Spice Route                    │
    ├─────────────────────────────────────────┤
    │  Cuisine    : Indian, Mughlai           │
    │  Rating     : 4.6 / 5.0                │
    │  Est. Cost  : Rs. 700 for two          │
    │  Location   : Connaught Place, Delhi   │
    │                                         │
    │  Why recommended:                       │
    │  "Perfect for your medium budget..."    │
    ╰─────────────────────────────────────────╯
    ```
  - Display final summary in a separate highlighted block

- [ ] **6.2** Streamlit output format:
  - Each restaurant in its own `st.expander` with emoji icons
  - Use `st.metric` for Rating and Cost
  - Use `st.info` for the AI explanation text
  - Use `st.success` for the overall summary

- [ ] **6.3** Add a "No results" graceful UI in both CLI and Streamlit:
  - Suggest relaxing filters (e.g., "Try a lower minimum rating or different city")

- [ ] **6.4** Display metadata (e.g., "Searched 3,400 restaurants · Found 18 matches · Ranked by AI"):

### Deliverables
- Updated `ui/cli.py` with rich formatting
- Updated `ui/streamlit_app.py` with polished cards
- `src/llm/output_parser.py` updated to include restaurant metadata fields

### Acceptance Criteria
- Output shows all 5 fields: Name, Cuisine, Rating, Cost, AI Explanation
- Summary paragraph is clearly visible
- No-result scenario displays a helpful message

---

## Phase 7 — Testing & Validation

### Goal
Ensure every component works correctly in isolation and as an integrated system through automated tests.

### Tasks

- [ ] **7.1** Write/complete unit tests:
  | Test File                   | What to Test                                        |
  |-----------------------------|-----------------------------------------------------|
  | `tests/test_ingestion.py`   | Dataset loads, columns normalized, no null key fields |
  | `tests/test_filtering.py`   | Filter returns correct rows; edge cases work        |
  | `tests/test_llm.py`         | Prompt built correctly; parser extracts data        |
  | `tests/test_orchestrator.py`| Full pipeline with mocked LLM returns valid result  |

- [ ] **7.2** Integration test: Run the full pipeline with a real LLM call (manually):
  - Input: `location="Delhi", budget="medium", cuisine="Indian", min_rating=4.0`
  - Verify: 5 restaurants returned, each with an explanation

- [ ] **7.3** Edge case tests:
  - [ ] Unknown city (e.g., "Atlantis") → graceful no-result message
  - [ ] Very high min rating (5.0) → few or no results handled
  - [ ] Empty cuisine field → no cuisine filter applied
  - [ ] LLM returns empty string → fallback to top-rated filtered list

- [ ] **7.4** Run full test suite:
  ```bash
  pytest tests/ -v
  ```

- [ ] **7.5** Manual QA checklist:
  - [ ] CLI works end-to-end on Windows and Linux
  - [ ] Streamlit app loads and displays results correctly in browser
  - [ ] LLM explanations are relevant and non-hallucinated

### Deliverables
- All 4 test files complete
- Pytest run passes with no failures
- Manual QA checklist signed off

### Acceptance Criteria
- All unit tests pass
- Integration test produces valid recommendations
- Edge cases handled without crashes

---

## Phase 8 — Polish, Documentation & Deployment Prep

### Goal
Finalize documentation, clean up code, and prepare the project for sharing or deployment.

### Tasks

- [ ] **8.1** Write `README.md` with:
  - Project description (from `problemStatement.md`)
  - Setup instructions
  - How to run CLI and Streamlit app
  - Environment variable setup guide
  - Sample output screenshot

- [ ] **8.2** Add docstrings to all public functions and classes

- [ ] **8.3** Create `requirements.txt` final pinned version:
  ```bash
  pip freeze > requirements.txt
  ```

- [ ] **8.4** Clean up:
  - Remove debug print statements
  - Ensure no API keys are hardcoded
  - Verify `.env` is in `.gitignore`

- [ ] **8.5** Optional — Dockerize the app:
  ```dockerfile
  FROM python:3.11-slim
  WORKDIR /app
  COPY . .
  RUN pip install -r requirements.txt
  CMD ["streamlit", "run", "ui/streamlit_app.py", "--server.port=8501"]
  ```

- [ ] **8.6** Optional — Deploy to Streamlit Cloud:
  - Push to GitHub
  - Connect repo at https://share.streamlit.io
  - Set environment secrets in Streamlit Cloud dashboard

### Deliverables
- Complete `README.md`
- Fully documented codebase
- Optional: `Dockerfile` and deployed Streamlit URL

### Acceptance Criteria
- A new developer can clone the repo, follow README, and run the app in < 10 minutes
- No secrets exposed in the codebase
- App runs successfully in Docker container

---

## Implementation Checklist Summary

| Phase | Key Milestone                          | Done |
|-------|----------------------------------------|------|
| 0     | Project scaffold + env setup           | [ ]  |
| 1     | Dataset loaded and cached as CSV       | [ ]  |
| 2     | Filter engine returns correct results  | [ ]  |
| 3     | LLM call returns valid recommendations | [ ]  |
| 4     | Orchestrator wires pipeline end-to-end | [ ]  |
| 5     | CLI + Streamlit UI functional          | [ ]  |
| 6     | Output display polished and complete   | [ ]  |
| 7     | All tests pass + QA done               | [ ]  |
| 8     | README complete + deployment ready     | [ ]  |

---

## Dependency Graph

```
Phase 0 (Setup)
    └── Phase 1 (Data Ingestion)
            └── Phase 2 (Filtering Engine)
                    └── Phase 4 (Orchestrator)
                            └── Phase 5 (UI)
                                    └── Phase 6 (Output Display)
    └── Phase 3 (LLM Integration)
            └── Phase 4 (Orchestrator)

Phase 7 (Testing) — runs after Phase 4 is complete
Phase 8 (Polish)  — runs after Phase 7 is complete
```

---

*Implementation Plan — AI-Powered Restaurant Recommendation System*
*Version 1.0 | Next Leap AI Project*
