"""Synchronous data orchestration layer for the ProfPick Streamlit app."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from backend import cache
from backend import rmp

DEFAULT_SNIPPET_BATCH = 12


@dataclass(frozen=True)
class SchoolOption:
    id: int
    name: str


@dataclass
class ReviewSnippet:
    comment: str
    course: str
    date: str
    rating: float
    difficulty: float


@dataclass
class ProfessorCard:
    id: int
    name: str
    department: str
    rating: float
    difficulty: float
    would_take_again: Optional[float]
    num_ratings: int
    courses: list[str]
    snippets: list[ReviewSnippet] = field(default_factory=list)
    last_course_review_date: Optional[str] = None  # e.g. "Jan 2024"
    recently_active: bool = False                   # True = reviewed for this course within 18 months


def _run(coro):
    return asyncio.run(coro)


def _normalize_course(course: str) -> str:
    return re.sub(r"\s+", "", course.strip().upper())


def _course_key(course_filters: list[str]) -> str:
    normalized = [_normalize_course(c) for c in course_filters if c.strip()]
    return "__".join(sorted(normalized))


def _matches_courses(professor: dict, course_filters: list[str]) -> bool:
    """Return True if the professor has ever taught any of the filtered courses on RMP.

    Matching rules:
    - Exact: "CSCI101" matches "CSCI101"
    - Prefix-to-digit: "CSCI" matches "CSCI101" (next char after prefix is a digit)
    - NOT loose substring: "CS" does NOT match "CSCI101" (next char is a letter)
    """
    if not course_filters:
        return True
    professor_courses = {_normalize_course(c) for c in professor.get("courses", [])}
    for cf in course_filters:
        cf_norm = _normalize_course(cf)
        for pc in professor_courses:
            if pc == cf_norm:
                return True
            if pc.startswith(cf_norm) and len(pc) > len(cf_norm) and pc[len(cf_norm)].isdigit():
                return True
    return False


# ── Date helpers ──────────────────────────────────────────────────────────────

_SNIPPET_DATE_FORMATS = ["%b %Y", "%B %Y"]


def _parse_snippet_date(date_str: str) -> Optional[datetime]:
    for fmt in _SNIPPET_DATE_FORMATS:
        try:
            return datetime.strptime(date_str.strip(), fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _months_ago(months: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=months * 30)


def _annotate_recency(card: ProfessorCard, course_filters: list[str]) -> None:
    """Populate last_course_review_date and recently_active from already-loaded snippets.

    Uses the 3-snippet display batch — no extra API calls.
    recently_active = True if the professor has a review for this course within 18 months.
    """
    if not card.snippets:
        return

    if not course_filters:
        # No filter — record most recent review date for context
        dated = [s for s in card.snippets if s.date]
        if dated:
            best = max(dated, key=lambda s: _parse_snippet_date(s.date) or datetime.min.replace(tzinfo=timezone.utc))
            card.last_course_review_date = best.date
        return

    normed = [_normalize_course(cf) for cf in course_filters]

    def _matches(s_course: str) -> bool:
        sn = _normalize_course(s_course)
        for cf in normed:
            if sn == cf:
                return True
            if sn.startswith(cf) and len(sn) > len(cf) and sn[len(cf)].isdigit():
                return True
        return False

    relevant = [s for s in card.snippets if s.course and _matches(s.course)]

    if not relevant:
        # Snippets exist but none tagged with this course (can happen when RMP
        # didn't filter them server-side — treat as unknown, leave defaults)
        return

    dated = [s for s in relevant if s.date]
    if not dated:
        return

    best = max(dated, key=lambda s: _parse_snippet_date(s.date) or datetime.min.replace(tzinfo=timezone.utc))
    card.last_course_review_date = best.date

    dt = _parse_snippet_date(best.date)
    card.recently_active = dt is not None and dt >= _months_ago(18)


# ── Internal converters ───────────────────────────────────────────────────────

def _to_snippets(raw: list[dict]) -> list[ReviewSnippet]:
    return [
        ReviewSnippet(
            comment=s.get("comment", ""),
            course=s.get("course", ""),
            date=s.get("date", ""),
            rating=float(s.get("rating") or 0),
            difficulty=float(s.get("difficulty") or 0),
        )
        for s in raw
    ]


def _to_card(professor: dict) -> ProfessorCard:
    return ProfessorCard(
        id=int(professor["id"]),
        name=professor.get("name", "").strip(),
        department=professor.get("department", "") or "",
        rating=float(professor.get("rating") or 0),
        difficulty=float(professor.get("difficulty") or 0),
        would_take_again=professor.get("would_take_again"),
        num_ratings=int(professor.get("num_ratings") or 0),
        courses=list(professor.get("courses") or []),
        snippets=[],
    )


# ── Async snippet fetching ────────────────────────────────────────────────────

async def _fetch_snippet_batch(
    cards: list[ProfessorCard], course_filters: list[str]
) -> list[list[dict]]:
    selected_course = course_filters[0] if len(course_filters) == 1 else ""
    tasks = [rmp.fetch_snippets(card.id, selected_course) for card in cards]
    raw_results = await asyncio.gather(*tasks, return_exceptions=True)
    return [r if isinstance(r, list) else [] for r in raw_results]


# ── Public API ────────────────────────────────────────────────────────────────

def search_school_options(query: str) -> tuple[list[SchoolOption], str | None]:
    trimmed = query.strip()
    if not trimmed:
        return [], None

    cached = cache.get_school_search(trimmed)
    if cached is not None:
        raw_results = cached
    else:
        try:
            raw_results = _run(rmp.search_schools(trimmed))
        except Exception:
            return [], "School search is unavailable right now. Check your internet connection and try again."
        cache.set_school_search(trimmed, raw_results)

    deduped: list[SchoolOption] = []
    seen_ids: set[int] = set()
    for school in raw_results:
        school_id = int(school["id"])
        if school_id in seen_ids:
            continue
        seen_ids.add(school_id)
        deduped.append(SchoolOption(id=school_id, name=school["name"]))
    return deduped, None


def get_all_school_options() -> tuple[list[SchoolOption], str | None]:
    cached = cache.get_all_schools()
    if cached is not None:
        raw_results = cached
    else:
        try:
            raw_results = _run(rmp.fetch_all_schools())
        except Exception:
            return [], "The school index could not be loaded right now. Check your internet connection and try again."
        cache.set_all_schools(raw_results)

    schools = [SchoolOption(id=int(s["id"]), name=s["name"]) for s in raw_results]
    schools.sort(key=lambda s: s.name)
    return schools, None


def get_professor_cards(
    school_id: int,
    school_name: str,
    course_filters: list[str],
    snippet_batch_size: int = DEFAULT_SNIPPET_BATCH,
) -> tuple[list[ProfessorCard], str | None]:
    """Return professors at *school_id* matching *course_filters*, sorted by rating.

    When course_filters is non-empty only professors whose RMP course list
    contains a matching code are included.  All matches are returned — no
    semester-specific filtering is applied because RMP does not carry schedule
    data.  The recently_active badge on each card is populated from the review
    dates loaded in the display-snippet pass.
    """
    # ── Load professor list (cached per school) ───────────────────────────────
    cached_professors = cache.get_professors(school_id)
    if cached_professors is None:
        try:
            cached_professors = _run(rmp.fetch_professors(school_id))
        except Exception:
            return [], "Rate My Professors could not be reached right now. Try again in a moment."
        cache.set_professors(school_id, school_name, cached_professors)

    if not cached_professors:
        return [], f"No professors found for '{school_name}'. The school may have limited Rate My Professors coverage."

    # ── Filter by course code ─────────────────────────────────────────────────
    matched = [p for p in cached_professors if _matches_courses(p, course_filters)]
    if not matched and course_filters:
        return [], (
            f"No professors found at '{school_name}' for {', '.join(course_filters)}. "
            "Try the exact course prefix shown on Rate My Professors (e.g. 'COMSCI' not 'CS')."
        )

    cards = [_to_card(p) for p in matched]
    if not cards:
        return [], f"No professors found for '{school_name}'."

    # Sort by rating then number of ratings, best first
    cards.sort(key=lambda c: (c.rating, c.num_ratings), reverse=True)

    # ── Load display snippets for the first batch ─────────────────────────────
    course_key = _course_key(course_filters)
    batch = cards[: max(0, min(snippet_batch_size, len(cards)))]
    if not batch:
        return cards, None

    to_fetch: list[ProfessorCard] = []
    for card in batch:
        cached_snips = cache.get_snippets(card.id, course_key)
        if cached_snips is not None:
            card.snippets = _to_snippets(cached_snips)
        else:
            to_fetch.append(card)

    if to_fetch:
        payloads = _run(_fetch_snippet_batch(to_fetch, course_filters))
        for card, raw in zip(to_fetch, payloads):
            cache.set_snippets(card.id, course_key, raw)
            card.snippets = _to_snippets(raw)

    # Annotate recency badges from the snippets we just loaded
    for card in batch:
        _annotate_recency(card, course_filters)

    return cards, None


def hydrate_snippets(
    cards: list[ProfessorCard], course_filters: list[str], limit: int | None = None
) -> list[ProfessorCard]:
    """Load snippets for cards that do not have them yet (lazy load pass)."""
    course_key = _course_key(course_filters)
    unresolved = [c for c in cards if not c.snippets]
    if limit is not None:
        unresolved = unresolved[:limit]

    to_fetch: list[ProfessorCard] = []
    for card in unresolved:
        cached_snips = cache.get_snippets(card.id, course_key)
        if cached_snips is not None:
            card.snippets = _to_snippets(cached_snips)
            _annotate_recency(card, course_filters)
        else:
            to_fetch.append(card)

    if to_fetch:
        payloads = _run(_fetch_snippet_batch(to_fetch, course_filters))
        for card, raw in zip(to_fetch, payloads):
            cache.set_snippets(card.id, course_key, raw)
            card.snippets = _to_snippets(raw)
            _annotate_recency(card, course_filters)

    return cards
