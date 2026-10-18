"""
ui/server.py
------------
ASGI Web Server for the Zomato AI Restaurant Concierge.
Built with Starlette & Uvicorn to serve the new Obsidian Gourmet Concierge frontend
and expose RESTful APIs for real-time recommendations, health monitoring,
and autocomplete services.

Endpoints:
  - GET  /               : Serves web/index.html
  - GET  /api/health     : System health and dataset metadata
  - POST /api/recommend  : Runs end-to-end recommendation pipeline via Orchestrator
  - GET  /api/locations  : Top distinct locations for autocomplete
  - GET  /api/cuisines   : Top distinct cuisines for autocomplete
"""

import os
import sys
import json
import logging
import pathlib
from typing import Any

# Ensure project root is in sys.path
_PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from starlette.applications import Starlette
from starlette.responses import JSONResponse, FileResponse
from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

from config.settings import LLM_MODEL, LLM_PROVIDER
from src.filtering.models import UserPreferences
from src.orchestrator import Orchestrator, RecommendationResult

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# ── CORS Configuration ────────────────────────────────────────────────────────
# Configurable via ALLOWED_ORIGINS environment variable (comma-separated).
# If unset or "*", allows all origins for seamless development & cross-origin access.
# If specific origins provided, restricts to those plus local dev and Vercel regex.
_raw_origins = os.getenv("ALLOWED_ORIGINS", "*")
if _raw_origins.strip() == "*":
    _ALLOWED_ORIGINS: list[str] = ["*"]
    _ALLOW_ORIGIN_REGEX: str | None = None
else:
    _ALLOWED_ORIGINS = [o.strip() for o in _raw_origins.split(",") if o.strip()]
    for _dev in ("http://localhost:8000", "http://127.0.0.1:8000", "http://localhost:3000", "http://localhost:5173"):
        if _dev not in _ALLOWED_ORIGINS:
            _ALLOWED_ORIGINS.append(_dev)
    _ALLOW_ORIGIN_REGEX = os.getenv("ALLOWED_ORIGIN_REGEX", r"https://.*\.vercel\.app")

# Web directory paths
_WEB_DIR = _PROJECT_ROOT / "web"
_CSS_DIR = _WEB_DIR / "css"
_JS_DIR = _WEB_DIR / "js"

# Singleton Orchestrator instance
_orchestrator: Orchestrator | None = None


def get_orchestrator() -> Orchestrator:
    """Lazy load orchestrator on first demand."""
    global _orchestrator
    if _orchestrator is None:
        logger.info("Initializing Orchestrator for web server...")
        _orchestrator = Orchestrator(lazy_load=False)
    return _orchestrator


# ── Route Handlers ────────────────────────────────────────────────────────────

async def index_endpoint(request) -> FileResponse:
    """Serve the Obsidian Gourmet Concierge UI."""
    index_file = _WEB_DIR / "index.html"
    return FileResponse(str(index_file))


async def health_endpoint(request) -> JSONResponse:
    """Return system telemetry and operational status."""
    orch = get_orchestrator()
    dataset_rows = len(orch.df) if orch._df is not None else 0
    return JSONResponse({
        "status": "healthy",
        "service": "Zomato Concierge AI",
        "provider": LLM_PROVIDER,
        "model": LLM_MODEL,
        "dataset_rows": dataset_rows,
        "neural_nodes": "active",
    })


async def recommend_endpoint(request) -> JSONResponse:
    """
    Process dining preferences and return curated recommendations.
    Accepts JSON payload with UserPreferences attributes.
    """
    try:
        data = await request.json()
    except Exception as exc:
        return JSONResponse({"success": False, "error": f"Invalid JSON payload: {exc}"}, status_code=400)

    location = data.get("location", "").strip()
    if not location:
        return JSONResponse({
            "success": False,
            "error": "Location is required (e.g. 'Koramangala, Bangalore').",
            "recommendations": [],
        }, status_code=400)

    # Normalize location by extracting primary neighborhood if formatted as 'Neighborhood, City'
    clean_loc = location
    if "," in location:
        parts = [p.strip() for p in location.split(",") if p.strip()]
        if parts:
            clean_loc = parts[0]

    try:
        prefs = UserPreferences(
            location=clean_loc,
            budget=data.get("budget", "").strip(),
            cuisine=data.get("cuisine", "").strip(),
            min_rating=float(data.get("min_rating", 3.8)),
            online_delivery=bool(data.get("online_delivery", False)),
            table_booking=bool(data.get("table_booking", False)),
            extra_notes=data.get("extra_notes", "").strip(),
        )

        orch = get_orchestrator()
        result: RecommendationResult = orch.recommend(prefs)

        payload = {
            "success": result.is_success,
            "error": result.error,
            "is_fallback": result.is_fallback,
            "summary": result.summary,
            "recommendations": [r.to_dict() for r in result.recommendations],
            "candidate_count": result.candidate_count,
            "timings_ms": result.timings,
            "model_name": f"{LLM_PROVIDER.upper()} {LLM_MODEL}",
            "relaxation_note": (
                result.filter_result.relaxation_note if result.filter_result else ""
            ),
        }
        return JSONResponse(payload)

    except Exception as exc:
        logger.exception("Error processing recommendation query: %s", exc)
        return JSONResponse({
            "success": False,
            "error": str(exc),
            "recommendations": [],
        }, status_code=500)


async def locations_endpoint(request) -> JSONResponse:
    """Return top distinct locations from dataset."""
    orch = get_orchestrator()
    if orch._df is not None and "location" in orch._df.columns:
        locs = orch._df["location"].dropna().value_counts().head(20).index.tolist()
    else:
        locs = ["Koramangala", "Indiranagar", "Whitefield", "Lavelle Road", "HSR Layout", "Jayanagar", "MG Road"]
    return JSONResponse({"locations": locs})


async def cuisines_endpoint(request) -> JSONResponse:
    """Return top distinct cuisine categories."""
    cuisines = [
        "Italian", "Wood-fired Pizza", "North Indian", "Biryani",
        "Artisanal Cafe", "Pan-Asian", "Cocktail Bar", "Continental",
        "South Indian", "Desserts & Bakery"
    ]
    return JSONResponse({"cuisines": cuisines})


# ── Starlette Application Setup ───────────────────────────────────────────────

routes = [
    Route("/", endpoint=index_endpoint, methods=["GET"]),
    Route("/api/health", endpoint=health_endpoint, methods=["GET"]),
    Route("/api/recommend", endpoint=recommend_endpoint, methods=["POST"]),
    Route("/api/locations", endpoint=locations_endpoint, methods=["GET"]),
    Route("/api/cuisines", endpoint=cuisines_endpoint, methods=["GET"]),
    Mount("/css", app=StaticFiles(directory=str(_CSS_DIR)), name="css"),
    Mount("/js", app=StaticFiles(directory=str(_JS_DIR)), name="js"),
]

middleware = [
    Middleware(
        CORSMiddleware,
        allow_origins=_ALLOWED_ORIGINS,
        allow_origin_regex=_ALLOW_ORIGIN_REGEX,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
        allow_credentials=True if _ALLOWED_ORIGINS != ["*"] else False,
    )
]

app = Starlette(routes=routes, middleware=middleware)


def run_server(host: str = "127.0.0.1", port: int = 8000, reload: bool = False):
    """Start uvicorn server serving the application."""
    import uvicorn
    # Support Railway/Render/Heroku $PORT and $HOST env vars
    env_port = os.getenv("PORT")
    if env_port:
        try:
            port = int(env_port)
            host = os.getenv("HOST", "0.0.0.0")
        except ValueError:
            pass
    print(f"\n>> Zomato Concierge AI is running at: http://{host}:{port}\n")
    uvicorn.run("ui.server:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    run_server()
