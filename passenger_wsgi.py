"""Passenger entry point for cPanel ("Setup Python App").

Passenger speaks WSGI while the app is ASGI, so a2wsgi bridges the two.
"""

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Storage, log and .env paths are relative to the project root, and
# Passenger does not guarantee it starts the process there.
os.chdir(BASE_DIR)
sys.path.insert(0, str(BASE_DIR))

from a2wsgi import ASGIMiddleware  # noqa: E402

from app.main import app  # noqa: E402

application = ASGIMiddleware(app)
