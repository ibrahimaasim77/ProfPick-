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
RECENCY_BATCH = 40  # top-N professors to eagerly check for recency when course filter is active


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
    active_for_course: bool = True                 # False = no reviews for this course in last 24 months


def _run(coro):
    return asyncio.run(coro)


def _normalize_course(course: str) -> str:
    return re.sub(r"\s+", "", course.strip().upper())


def _course_key(course_filters: list[str]) -> str:
    normalized = [_normalize_course(course) for course in course_filters if course.strip()]
    return "__".join(sorted(normalized))


def _matches_courses(professor: dict, course_filters: list[str]) -> bool:
    if not course_filters:
        return True
    professor_courses = {_normalize_course(c) for c in professor.get("courses", [])}
    for cf in course_filters:
        cf_norm = _normalize_course(cf)
        for pc in professor_courses:
            if pc == cf_norm:
                return True  # exact match
            # prefix match: "CSCI" matches "CSCI101" — next char after prefix must be a digit
            if pc.startswith(cf_norm) and len(pc) > len(cf_norm) and pc[len(cf_norm)].isdigit():
                return True
    return False


_SNIPPET_DATE_FORMATS = ["%b %Y", "%B %Y"]


def _parse_snippet_date(date_str: str) -> Optional[datetime]:
    for fmt in _SNIPPET_DATE_FORMATS:
        try:
            return datetime.strptime(date_str.strip(), fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _is_recent(date_str: str, months: int = 24) -> bool:
    dt = _parse_snippet_date(date_str)
    if dt is None:
        return False
    return dt >= datetime.now(timezone.utc) - timedelta(days=months * 30)


def _compute_recency(card: "ProfessorCard", course_filters: list[str]) -> None:
    """Set last_course_review_date and active_for_course based on loaded snippets."""
    if not card.snippets:
        return  # no data — don't penalize, keep defaults

    if not course_filters:
        # No filter: just record the most recent snippet date overall
        dated = [s for s in card.snippets if s.date]
        if dated:
            best = max(dated, key=lambda s: _parse_snippet_date(s.date) or datetime.min.replace(tzinfo=timezone.utc))
            card.last_course_review_date = best.date
        return  # active_for_course stays True

    normed = [_normalize_course(cf) for cf in course_filters]

    def _snippet_matches_filter(s_course: str) -> bool:
        sn = _normalize_course(s_course)
        for cf_norm in normed:
            if sn == cf_norm:
                return True
            if sn.startswith(cf_norm) and len(sn) > len(cf_norm) and sn[len(cf_norm)].isdigit():
                return True
        return False

    relevant = [s for s in card.snippets if s.course and _snippet_matches_filter(s.course)]

    if not relevant:
        card.last_course_review_date = None
        # Only mark stale if we fetched enough snippets to be confident
        card.active_for_course = len(card.snippets) < 5
        return

    dated = [s for s in relevant if s.date]
    if dated:
        best = max(dated, key=lambda s: _parse_snippet_date(s.date) or datetime.min.replace(tzinfo=timezone.utc))
        card.last_course_review_date = best.date
        card.active_for_course = _is_recent(best.date, months=24)
    else:
        card.last_course_review_date = None
        card.active_for_course = False


def _to_snippets(raw_snippets: list[dict]) -> list[ReviewSnippet]:
    return [
        ReviewSnippet(
            comment=snippet.get("comment", ""),
            course=snippet.get("course", ""),
            date=snippet.get("date", ""),
            rating=float(snippet.get("rating") or 0),
            difficulty=float(snippet.get("difficulty") or 0),
        )
        for snippet in raw_snippets
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


async def _fetch_snippet_batch(
    cards: list[ProfessorCard], course_filters: list[str], max_snippets: int = 3
) -> list[list[dict]]:
    selected_course = course_filters[0] if len(course_filters) == 1 else ""
    tasks = [rmp.fetch_snippets(card.id, selected_course, max_snippets=max_snippets) for card in cards]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    snippet_payloads: list[list[dict]] = []
    for result in results:
        if isinstance(result, list):
            snippet_payloads.append(result)
        else:
            snippet_payloads.append([])
    return snippet_payloads


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

    schools = [
        SchoolOption(id=int(school["id"]), name=school["name"])
        for school in raw_results
    ]
    schools.sort(key=lambda school: school.name)
    return schools, None


def get_professor_cards(
    school_id: int,
    school_name: str,
    course_filters: list[str],
    snippet_batch_size: int = DEFAULT_SNIPPET_BATCH,
) -> tuple[list[ProfessorCard], str | None]:
    cached_professors = cache.get_professors(school_id)
    if cached_professors is None:
        try:
            cached_professors = _run(rmp.fetch_professors(school_id))
        except Exception:
            return [], "Rate My Professors could not be reached right now. Try again in a moment."
        cache.set_professors(school_id, school_name, cached_professors)

    if not cached_professors:
        return [], f"No professors found for '{school_name}'. The school may have limited Rate My Professors coverage."

    filtered_professors = [professor for professor in cached_professors if _matches_courses(professor, course_filters)]
    if not filtered_professors and course_filters:
        return [], (
            f"No professors found at '{school_name}' teaching {', '.join(course_filters)}. "
            "Try the exact course code used on Rate My Professors."
        )

    cards = [_to_card(professor) for professor in filtered_professors]
    cards.sort(key=lambda card: (card.rating, card.num_ratings), reverse=True)

    if not cards:
        return [], f"No professors found for '{school_name}'."

    course_key = _course_key(course_filters)

    # ── Recency pass (only when a course filter is active) ────────────────────
    if course_filters:
        recency_key = course_key + "_rec"
        recency_targets = cards[:RECENCY_BATCH]
        to_fetch_recency: list[ProfessorCard] = []
        for card in recency_targets:
            cached = cache.get_snippets(card.id, recency_key)
            if cached is not None:
                card.snippets = _to_snippets(cached)
                _compute_recency(card, course_filters)
            else:
                to_fetch_recency.append(card)
        if to_fetch_recency:
            payloads = _run(_fetch_snippet_batch(to_fetch_recency, course_filters, max_snippets=20))
            for card, raw in zip(to_fetch_recency, payloads):
                cache.set_snippets(card.id, recency_key, raw)
                card.snippets = _to_snippets(raw)
                _compute_recency(card, course_filters)
        # Re-sort: active professors first, then stale, both groups by rating
        active = sorted([c for c in recency_targets if c.active_for_course],
                        key=lambda c: (c.rating, c.num_ratings), reverse=True)
        stale  = sorted([c for c in recency_targets if not c.active_for_course],
                        key=lambda c: (c.rating, c.num_ratings), reverse=True)
        cards = active + stale + cards[RECENCY_BATCH:]

    # ── Display snippet pass (first batch_size cards) ─────────────────────────
    batch_size = max(0, min(snippet_batch_size, len(cards)))
    if batch_size == 0:
        return cards, None

    cards_to_fetch: list[ProfessorCard] = []
    for card in cards[:batch_size]:
        cached_snippets = cache.get_snippets(card.id, course_key)
        if cached_snippets is not None:
            card.snippets = _to_snippets(cached_snippets)
        elif card.snippets:
            pass  # already populated by recency pass
        else:
            cards_to_fetch.append(card)

    if cards_to_fetch:
        snippet_payloads = _run(_fetch_snippet_batch(cards_to_fetch, course_filters))
        for card, raw_snippets in zip(cards_to_fetch, snippet_payloads):
            cache.set_snippets(card.id, course_key, raw_snippets)
            card.snippets = _to_snippets(raw_snippets)

    return cards, None


def hydrate_snippets(cards: list[ProfessorCard], course_filters: list[str], limit: int | None = None) -> list[ProfessorCard]:
    """Load snippets for cards that do not have them yet."""
    course_key = _course_key(course_filters)
    unresolved = [card for card in cards if not card.snippets]
    if limit is not None:
        unresolved = unresolved[:limit]

    cards_to_fetch: list[ProfessorCard] = []
    for card in unresolved:
        cached_snippets = cache.get_snippets(card.id, course_key)
        if cached_snippets is not None:
            card.snippets = _to_snippets(cached_snippets)
            if card.last_course_review_date is None and course_filters:
                _compute_recency(card, course_filters)
        else:
            cards_to_fetch.append(card)

    if cards_to_fetch:
        snippet_payloads = _run(_fetch_snippet_batch(cards_to_fetch, course_filters))
        for card, raw_snippets in zip(cards_to_fetch, snippet_payloads):
            cache.set_snippets(card.id, course_key, raw_snippets)
            card.snippets = _to_snippets(raw_snippets)
            _compute_recency(card, course_filters)

    return cards
