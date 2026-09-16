"""The aesthetic cache closes every SQLite connection it opens."""

import gc
from pathlib import Path

from local_shazam.aesthetic_cache import AestheticCache


def test_cache_round_trip_leaves_no_connection_open(tmp_path: Path) -> None:
    cache = AestheticCache(tmp_path / "cache.db")
    cache.put("Billie Eilish", "bad guy", "Lime green strobe.")

    assert cache.get("billie eilish", "BAD GUY") == "Lime green strobe."
    gc.collect()  # an unclosed connection warns here, and warnings are errors
