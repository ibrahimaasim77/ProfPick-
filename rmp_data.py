"""RateMyProfessor data-fetching layer for ProfPick."""

import re
import requests
import ratemyprofessor
import ratemyprofessor.__init__ as _rmp_init
import ratemyprofessor.school as _rmp_school
import ratemyprofessor.professor as _rmp_prof
from dataclasses import dataclass, field
from typing import Optional

# ── Patch: update the User-Agent to avoid RMP 403 blocks ─────────────────────
_MODERN_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

def _patch_headers(module_headers: dict) -> None:
    module_headers["User-Agent"] = _MODERN_UA
    module_headers["Referer"] = "https://www.ratemyprofessors.com/"
    module_headers["Origin"] = "https://www.ratemyprofessors.com"

_patch_headers(_rmp_init.headers)

# Also patch the requests.get used by school.py (it doesn't pass headers)
_original_get = requests.get

def _patched_get(url, **kwargs):
    if "ratemyprofessors.com" in url:
        kwargs.setdefault("headers", {})
        kwargs["headers"].setdefault("User-Agent", _MODERN_UA)
        kwargs["headers"].setdefault("Authorization", "Basic dGVzdDp0ZXN0")
        kwargs["headers"].setdefault("Referer", "https://www.ratemyprofessors.com/")
    return _original_get(url, **kwargs)

requests.get = _patched_get
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class ReviewSnippet:
    comment: str
    course: str
    date: str
    rating: float
    difficulty: float


@dataclass
class ProfessorCard:
    name: str
    department: str
    rating: float
    difficulty: float
    would_take_again: Optional[float]  # percentage 0-100 or None
    num_ratings: int
    courses: list[str]
    snippets: list[ReviewSnippet] = field(default_factory=list)


def _normalize_course(course: str) -> str:
    """Normalize a course name for fuzzy matching (e.g. 'csci 101' -> 'CSCI101')."""
    return re.sub(r"\s+", "", course.strip().upper())


def _professor_matches_courses(prof, course_filters: list[str]) -> bool:
    """Return True if any of the professor's listed course codes match any filter."""
    if not course_filters:
        return True
    prof_courses_normalized = {_normalize_course(c.name) for c in prof.courses}
    for cf in course_filters:
        cf_norm = _normalize_course(cf)
        for pc in prof_courses_normalized:
            if cf_norm in pc or pc in cf_norm:
                return True
    return False


def _get_snippets(prof, course_filters: list[str], max_snippets: int = 3) -> list[ReviewSnippet]:
    """Fetch the most recent ratings and return snippets."""
    try:
        # Try fetching per-course if a single course filter is given
        course_name = None
        if len(course_filters) == 1:
            # Find the exact course name on the professor object
            cf_norm = _normalize_course(course_filters[0])
            for c in prof.courses:
                if cf_norm in _normalize_course(c.name) or _normalize_course(c.name) in cf_norm:
                    course_name = c.name
                    break

        ratings = prof.get_ratings(course_name=course_name)
        if not ratings:
            ratings = prof.get_ratings()

        # Sort by date descending (most recent first)
        ratings_sorted = sorted(ratings, key=lambda r: r.date, reverse=True)

        snippets = []
        for r in ratings_sorted[:max_snippets]:
            comment = r.comment.strip() if r.comment else ""
            if not comment or comment.lower() in ("", "no comments", "n/a"):
                continue
            snippets.append(ReviewSnippet(
                comment=comment[:300],
                course=r.class_name or "",
                date=r.date.strftime("%b %Y"),
                rating=r.rating,
                difficulty=r.difficulty,
            ))
        return snippets
    except Exception:
        return []


def search_school(school_name: str):
    """Return the first matching School object or None."""
    try:
        return ratemyprofessor.get_school_by_name(school_name)
    except Exception:
        return None


def get_professor_cards(
    school_name: str,
    course_filters: list[str],
    fetch_snippets: bool = True,
) -> tuple[list[ProfessorCard], str | None]:
    """
    Fetch professors for a school, optionally filtered by course codes.

    Returns (cards, error_message). error_message is None on success.
    """
    school = search_school(school_name)
    if school is None:
        return [], f"Could not find a school matching '{school_name}'. Try a more specific name."

    # Fetch professors by blank search to get as many as possible
    # The library only exposes get_professors_by_school_and_name — use a
    # few common letters to cast a wide net.
    raw_professors = []
    seen_ids: set[int] = set()

    search_terms = [""]  # Empty string still returns results in some versions
    # Supplement with alphabet sweeps to broaden coverage
    if not course_filters:
        search_terms += list("abcdefghijklmnopqrstuvwxyz")
    else:
        # For course-specific searches use abbreviated sweeps
        search_terms += list("aeiou") + list("bcdfghjklmnpqrstvwxyz")

    for term in search_terms:
        try:
            profs = ratemyprofessor.get_professors_by_school_and_name(school, term)
            for p in profs:
                if p.id not in seen_ids:
                    seen_ids.add(p.id)
                    raw_professors.append(p)
        except Exception:
            continue

    if not raw_professors:
        return [], f"No professors found at '{school.name}'. The school may have limited RateMyProfessor coverage."

    # Filter by course if provided
    filtered = [p for p in raw_professors if _professor_matches_courses(p, course_filters)]

    if not filtered and course_filters:
        return [], (
            f"No professors found at '{school.name}' teaching "
            f"{', '.join(course_filters)}. "
            "Try checking the exact course code used on RateMyProfessor."
        )

    # Build cards
    cards: list[ProfessorCard] = []
    for prof in filtered:
        course_names = [c.name for c in prof.courses] if prof.courses else []
        snippets = _get_snippets(prof, course_filters) if fetch_snippets else []
        # RMP returns -1 for unknown would_take_again; normalize to None
        wta = prof.would_take_again
        if wta is not None and wta < 0:
            wta = None
        cards.append(ProfessorCard(
            name=prof.name,
            department=prof.department or "",
            rating=prof.rating or 0.0,
            difficulty=prof.difficulty or 0.0,
            would_take_again=wta,
            num_ratings=prof.num_ratings or 0,
            courses=course_names,
            snippets=snippets,
        ))

    return cards, None
