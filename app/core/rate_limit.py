"""Rate limiting for every endpoint, shared by all worker processes.

Counters live in a small SQLite file rather than in memory. Behind a
process-per-request server (Passenger/LSAPI on cPanel) each worker would
otherwise keep its own counters, so a client spread across N workers got
N times the limit, and every worker restart reset it.

Each request is charged to one tier, chosen from its method and path:

===========  ===============================================  ==========
tier         what                                             default
===========  ===============================================  ==========
``read``     GET/HEAD: pages, assets, polling, downloads      600 / min
``transfer`` relay traffic: upload chunks, run, collect       600 / min
``write``    every other request                              120 / min
``heavy``    CPU or network hungry tools                      20 / min,
                                                              200 / hour
===========  ===============================================  ==========

Windows slide: the previous window is weighted by how much of it still
overlaps, so a client cannot double its budget across a boundary.
"""

import ipaddress
import logging
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from app.api import API_PREFIX
from app.core.config import settings

logger = logging.getLogger(__name__)

RELAY_PREFIX = f"{API_PREFIX}/relay"
_HEAVY_PREFIXES = tuple(
    f"{API_PREFIX}{path}"
    for path in (
        "/background/",
        "/compression/batch/",
        "/images/compress",
        "/tools/pdf/to-images",
        "/tools/text/text-to-speech",
        "/tools/video/",
    )
)
_READ_METHODS = {"GET", "HEAD"}
_PURGE_INTERVAL_SECONDS = 120
# Hidden so the temp-directory sweeper leaves it alone.
_DATABASE_NAME = ".rate_limit.sqlite3"


@dataclass(frozen=True)
class Rule:
    limit: int
    window_seconds: int


def rules_for(method: str, path: str) -> tuple[str, tuple[Rule, ...]]:
    """Return the tier a request is charged to and its limits."""
    window = settings.rate_limit_window_seconds
    if path.startswith(RELAY_PREFIX):
        return "transfer", (Rule(settings.rate_limit_transfer_max_requests, window),)
    if method in _READ_METHODS:
        return "read", (Rule(settings.rate_limit_read_max_requests, window),)
    if path.startswith(_HEAVY_PREFIXES):
        return "heavy", (
            Rule(settings.rate_limit_heavy_max_requests, window),
            Rule(settings.rate_limit_heavy_hourly_requests, 3600),
        )
    return "write", (Rule(settings.rate_limit_max_requests, window),)


def client_key(peer_host: str | None, headers) -> str:
    """Identify the client by an address it cannot choose.

    Forwarding headers are honored only when a trusted proxy is known to
    set them. Reading them unconditionally let a direct caller pick a
    fresh identity, and so a fresh budget, on every request.
    """
    address = ""
    for header in _trusted_headers():
        value = headers.get(header, "").split(",")[0].strip()
        if value:
            address = value
            break
    address = address or peer_host or "unknown"
    try:
        parsed = ipaddress.ip_address(address)
    except ValueError:
        return address
    if parsed.version == 6:
        # One subscriber usually holds a whole /64.
        return str(ipaddress.ip_network(f"{parsed}/64", strict=False).network_address)
    return str(parsed)


def _trusted_headers() -> tuple[str, ...]:
    configured = settings.trusted_proxy_header.strip().lower()
    if configured:
        return (configured,)
    if settings.storage_driver == "vercel":
        # Set by Vercel's edge; function URLs are not reachable directly.
        return ("x-vercel-forwarded-for", "x-real-ip")
    return ()


class RateLimiter:
    def __init__(self, database_path: Path | None = None) -> None:
        self._path = database_path
        self._lock = threading.Lock()
        self._connection: sqlite3.Connection | None = None
        self._last_purge = 0.0

    def check(self, key: str, tier: str, rules: tuple[Rule, ...]) -> int | None:
        """Count one request. Returns seconds to wait when over a limit."""
        now = time.time()
        with self._lock:
            try:
                return self._check(key, tier, rules, now)
            except (sqlite3.Error, OSError):
                # A limiter that is down must not take the site down.
                logger.warning("Rate limit store unavailable; allowing request", exc_info=True)
                self._close()
                return None

    def reset(self) -> None:
        with self._lock:
            try:
                self._connect().execute("DELETE FROM hits")
            except (sqlite3.Error, OSError):
                self._close()

    def _check(self, key: str, tier: str, rules: tuple[Rule, ...], now: float) -> int | None:
        connection = self._connect()
        connection.execute("BEGIN IMMEDIATE")
        try:
            for rule in rules:
                retry_after = self._over_limit(connection, key, tier, rule, now)
                if retry_after is not None:
                    connection.execute("ROLLBACK")
                    return retry_after
            for rule in rules:
                window = int(now // rule.window_seconds)
                connection.execute(
                    "INSERT INTO hits (client, tier, span, slot, count, expires) "
                    "VALUES (?, ?, ?, ?, 1, ?) "
                    "ON CONFLICT (client, tier, span, slot) DO UPDATE SET count = count + 1",
                    (key, tier, rule.window_seconds, window, (window + 2) * rule.window_seconds),
                )
            if now - self._last_purge > _PURGE_INTERVAL_SECONDS:
                connection.execute("DELETE FROM hits WHERE expires < ?", (now,))
                self._last_purge = now
            connection.execute("COMMIT")
        except BaseException:
            connection.execute("ROLLBACK")
            raise
        return None

    @staticmethod
    def _over_limit(connection, key: str, tier: str, rule: Rule, now: float) -> int | None:
        window = int(now // rule.window_seconds)
        counts = dict(
            connection.execute(
                "SELECT slot, count FROM hits "
                "WHERE client = ? AND tier = ? AND span = ? AND slot IN (?, ?)",
                (key, tier, rule.window_seconds, window, window - 1),
            ).fetchall()
        )
        elapsed = (now % rule.window_seconds) / rule.window_seconds
        used = counts.get(window, 0) + counts.get(window - 1, 0) * (1 - elapsed)
        if used < rule.limit:
            return None
        return max(1, int(rule.window_seconds * (1 - elapsed)))

    def _connect(self) -> sqlite3.Connection:
        if self._connection is None:
            path = self._path or Path(settings.temp_path) / _DATABASE_NAME
            path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(
                path,
                timeout=1.0,
                isolation_level=None,
                check_same_thread=False,
            )
            connection.execute("PRAGMA journal_mode=WAL")
            # Losing the last few counts in a crash is harmless.
            connection.execute("PRAGMA synchronous=OFF")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS hits ("
                "client TEXT NOT NULL, tier TEXT NOT NULL, span INTEGER NOT NULL, "
                "slot INTEGER NOT NULL, count INTEGER NOT NULL, expires REAL NOT NULL, "
                "PRIMARY KEY (client, tier, span, slot))"
            )
            self._connection = connection
        return self._connection

    def _close(self) -> None:
        if self._connection is not None:
            try:
                self._connection.close()
            except sqlite3.Error:
                pass
            self._connection = None


rate_limiter = RateLimiter()
