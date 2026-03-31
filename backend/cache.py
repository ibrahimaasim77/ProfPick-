"""File-based JSON cache with TTL for professor data."""

import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

CACHE_DIR = Path(__file__).parent / "cache"
PROF_TTL_HOURS = 24


def _prof_path(school_id: int) -> Path:
    return CACHE_DIR / f"professors_{school_id}.json"


def get_professors(school_id: int) -> list[dict] | None:
    """Return cached professors or None if missing/stale."""
    path = _prof_path(school_id)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        fetched_at = datetime.fromisoformat(data["fetched_at"])
        if datetime.now(timezone.utc) - fetched_at > timedelta(hours=PROF_TTL_HOURS):
            return None
        return data["professors"]
    except Exception:
        return None


def set_professors(school_id: int, school_name: str, professors: list[dict]) -> None:
    """Write professors to cache file."""
    CACHE_DIR.mkdir(exist_ok=True)
    path = _prof_path(school_id)
    data = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "school_id": school_id,
        "school_name": school_name,
        "professors": professors,
    }
    path.write_text(json.dumps(data))
