"""Root WSGI entrypoint for local runs, tests, and Gunicorn."""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
BACKEND_DIR = ROOT / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from backend.app import create_app, client, get_model  # noqa: E402,F401

app = create_app()
