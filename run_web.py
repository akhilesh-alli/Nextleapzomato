"""
run_web.py
----------
Launcher script for the new Zomato Concierge AI Web Application.
Starts the modern ASGI server on http://127.0.0.1:8000.

Usage:
  python run_web.py
  python run_web.py --port 8080
"""

import argparse
import sys
import pathlib

# Ensure workspace root is in path
_ROOT = pathlib.Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ui.server import run_server

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Zomato Concierge AI Web App")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port number (default: 8000)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")

    args = parser.parse_args()
    run_server(host=args.host, port=args.port, reload=args.reload)
