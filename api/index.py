"""Vercel Python serverless entrypoint. Exposes the FastAPI ASGI app as ``app``.

The Vercel project root is the repository root; this file lives in ``api/`` so ``app`` (the package next to
it) must be importable regardless of the working directory the runtime uses.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import app  # noqa: E402,F401
