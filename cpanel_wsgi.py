"""Startup file for cPanel ("Setup Python App").

Passenger speaks WSGI while the app is ASGI, so a2wsgi bridges the two.

cPanel writes its own passenger_wsgi.py into the application root, a stub
that loads the configured startup file. That is why this lives under a
different name: a startup file called passenger_wsgi.py gets overwritten
by the stub, which then loads itself.
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
