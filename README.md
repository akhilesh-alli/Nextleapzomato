# AI-Powered Restaurant Recommendation System
> Zomato Use Case | Next Leap AI Project

An intelligent restaurant recommendation engine that combines the Zomato dataset with a Large Language Model to deliver personalized, explainable restaurant suggestions.

---

## Quick Start

### 1. Clone & Setup
```bash
git clone <repo-url>
cd next-leap-ai-restaurant
python -m venv .venv
.venv\Scripts\activate       # Windows
# source .venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
```

### 2. Configure API Keys
```bash
cp .env.example .env
# Edit .env and add your API key
```

### 3. Run the App

**New Obsidian Gourmet Concierge Web UI (Recommended):**
```bash
python run_web.py
# Opens at http://127.0.0.1:8000 with the latest Stitch AI design
```

**Streamlit Web UI:**
```bash
streamlit run ui/streamlit_app.py
```

**CLI:**
```bash
python ui/cli.py
```

---

## Project Structure

```
next-leap-ai-restaurant/
├── config/           # Settings & environment config
├── data/             # Cached dataset (auto-generated)
├── src/
│   ├── ingestion/    # Data loading & preprocessing
│   ├── filtering/    # Rule-based restaurant filtering
│   ├── llm/          # LLM engine, prompt builder, output parser
│   └── orchestrator.py
├── ui/               # CLI and Streamlit interfaces
├── tests/            # Unit & integration tests
├── .env.example      # Environment variable template
├── requirements.txt
└── README.md
```

---

## Architecture

See [architecture.md](../architecture.md) for full system design.

## Implementation Plan

See [implementation-plan.md](../implementation-plan.md) for phase-wise breakdown.

---

*Version 1.0 — Next Leap AI*
