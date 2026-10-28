"""Vercel Python serverless entrypoint for the ``channelmix-api`` project (root directory ``api/``).

Vercel only builds functions found under an ``api/`` folder, so this shim lives at ``api/api/index.py`` and puts
the project root (where the ``app`` package lives) on ``sys.path`` before importing the FastAPI app.
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.main import app  # noqa: E402,F401
