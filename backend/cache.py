"""File-based JSON cache with TTL for ProfPick data."""

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

CACHE_DIR = Path(__file__).parent / "cache"
PROF_TTL_HOURS = 24
SCHOOL_TTL_HOURS = 12
SNIPPET_TTL_HOURS = 24
ALL_SCHOOLS_TTL_HOURS = 24 * 7


def _cache_path(prefix: str, key: str) -> Path:
    safe_key = re.sub(r"[^a-zA-Z0-9_.-]+", "_", key).strip("_") or "default"
    return CACHE_DIR / f"{prefix}_{safe_key}.json"


def _read_cached(path: Path, ttl_hours: int) -> dict | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        fetched_at = datetime.fromisoformat(data["fetched_at"])
        if datetime.now(timezone.utc) - fetched_at > timedelta(hours=ttl_hours):
            return None
        return data
    except Exception:
        return None


def _write_cached(path: Path, payload: dict) -> None:
    CACHE_DIR.mkdir(exist_ok=True)
    path.write_text(json.dumps(payload))


def _prof_path(school_id: int) -> Path:
    return _cache_path("professors", str(school_id))


def get_professors(school_id: int) -> list[dict] | None:
    """Return cached professors or None if missing/stale."""
    path = _prof_path(school_id)
    data = _read_cached(path, PROF_TTL_HOURS)
    return data["professors"] if data else None


def set_professors(school_id: int, school_name: str, professors: list[dict]) -> None:
    """Write professors to cache file."""
    path = _prof_path(school_id)
    _write_cached(path, {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "school_id": school_id,
        "school_name": school_name,
        "professors": professors,
    })


def _school_search_path(query: str) -> Path:
    return _cache_path("schools", query.lower())


def get_school_search(query: str) -> list[dict] | None:
    """Return cached school search results or None if missing/stale."""
    data = _read_cached(_school_search_path(query), SCHOOL_TTL_HOURS)
    return data["schools"] if data else None


def set_school_search(query: str, schools: list[dict]) -> None:
    """Cache school search results."""
    _write_cached(_school_search_path(query), {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "query": query,
        "schools": schools,
    })


def _all_schools_path() -> Path:
    return _cache_path("schools", "all")


def get_all_schools() -> list[dict] | None:
    """Return cached all-school index or None if missing/stale."""
    data = _read_cached(_all_schools_path(), ALL_SCHOOLS_TTL_HOURS)
    return data["schools"] if data else None


def set_all_schools(schools: list[dict]) -> None:
    """Cache the full indexed school list."""
    _write_cached(_all_schools_path(), {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "schools": schools,
    })


def _snippet_path(professor_id: int, course_key: str) -> Path:
    suffix = course_key or "all"
    return _cache_path("snippets", f"{professor_id}_{suffix}")


def get_snippets(professor_id: int, course_key: str) -> list[dict] | None:
    """Return cached snippets or None if missing/stale."""
    data = _read_cached(_snippet_path(professor_id, course_key), SNIPPET_TTL_HOURS)
    return data["snippets"] if data else None


def set_snippets(professor_id: int, course_key: str, snippets: list[dict]) -> None:
    """Cache review snippets for a professor and optional course filter."""
    _write_cached(_snippet_path(professor_id, course_key), {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "professor_id": professor_id,
        "course_key": course_key,
        "snippets": snippets,
    })
