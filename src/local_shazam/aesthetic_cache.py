"""SQLite cache for artist/song visual aesthetics."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from local_shazam.logger import get_logger

PROJECT_ROOT = Path(__file__).resolve().parents[2]

log = get_logger(__name__)


class AestheticCache:
    """SQLite cache for artist/song visual aesthetics.

    Stores full aesthetic descriptions keyed by normalized (artist, song) pairs.
    Thread-safe for read operations; writes use SQLite's built-in locking.
    """

    def __init__(self, db_path: Path | None = None) -> None:
        """Initialize the cache.

        Args:
            db_path: Path to SQLite database file. Defaults to data/aesthetic_cache.db.
        """
        self._db_path = db_path or (PROJECT_ROOT / "data" / "aesthetic_cache.db")
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Create the aesthetics table if it doesn't exist."""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS aesthetics (
                    artist TEXT NOT NULL,
                    song TEXT NOT NULL,
                    description TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (artist, song)
                )
            """)
            conn.commit()
        log.info("aesthetic cache initialized at %s", self._db_path)

    @staticmethod
    def _normalize(value: str) -> str:
        """Normalize artist/song names for consistent lookups."""
        return value.strip().lower()

    def get(self, artist: str, song: str) -> str | None:
        """Lookup cached aesthetic description.

        Args:
            artist: Artist name.
            song: Song title.

        Returns:
            Cached description if found, None otherwise.
        """
        artist_norm = self._normalize(artist)
        song_norm = self._normalize(song)

        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.execute(
                "SELECT description FROM aesthetics WHERE artist = ? AND song = ?",
                (artist_norm, song_norm),
            )
            row = cursor.fetchone()

        if row:
            log.info("cache hit: '%s' by %s", song, artist)
            result: str = row[0]
            return result

        log.info("cache miss: '%s' by %s", song, artist)
        return None

    def put(self, artist: str, song: str, description: str) -> None:
        """Store aesthetic description in cache.

        Args:
            artist: Artist name.
            song: Song title.
            description: Full aesthetic description to cache.
        """
        artist_norm = self._normalize(artist)
        song_norm = self._normalize(song)
        now = datetime.now(UTC).isoformat()

        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO aesthetics (artist, song, description, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (artist_norm, song_norm, description, now),
            )
            conn.commit()

        log.info("cached aesthetic: '%s' by %s", song, artist)
