"""Vercel Python serverless entrypoint. Exposes the FastAPI ASGI app as ``app``.

The Vercel project ``channelmix-api`` has root directory ``api/``; ``app`` (the package next to this file) is
put on ``sys.path`` so it imports regardless of the working directory the runtime uses.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import app  # noqa: E402,F401
