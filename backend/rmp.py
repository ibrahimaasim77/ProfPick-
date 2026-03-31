"""Async RateMyProfessor data layer — uses httpx directly, no ratemyprofessor library."""

import asyncio
import base64
import re
from datetime import datetime

import httpx

# ── Constants ─────────────────────────────────────────────────────────────────

BASE_URL = "https://www.ratemyprofessors.com"
GRAPHQL_URL = f"{BASE_URL}/graphql"

_HEADERS = {
    "Authorization": "Basic dGVzdDp0ZXN0",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Content-Type": "application/json",
    "Referer": f"{BASE_URL}/",
    "Origin": BASE_URL,
}

_PROF_QUERY = (
    "query RatingsListQuery($id: ID!) {"
    "node(id: $id) {"
    "... on Teacher {"
    "school {id} courseCodes {courseName courseCount} "
    "firstName lastName numRatings avgDifficulty avgRating department wouldTakeAgainPercent"
    "}}}"
)

_RATINGS_QUERY = (
    "query RatingsListQuery($count: Int! $id: ID! $courseFilter: String $cursor: String) {"
    "node(id: $id) {"
    "... on Teacher {"
    "ratings(first: $count, after: $cursor, courseFilter: $courseFilter) {"
    "edges {node {"
    "comment date class helpfulRating difficultyRating "
    "attendanceMandatory wouldTakeAgain grade isForOnlineClass isForCredit "
    "thumbsUpTotal thumbsDownTotal"
    "}}}}}}"
)

def _encode_teacher_id(prof_id: int) -> str:
    return base64.b64encode(f"Teacher-{prof_id}".encode()).decode()


# ── School search (GraphQL) ───────────────────────────────────────────────────

_SCHOOL_SEARCH_QUERY = (
    "query SchoolSearch($q: SchoolSearchQuery!) {"
    "  newSearch { schools(query: $q) { edges { node { legacyId name city state } } } }"
    "}"
)


async def search_schools(query: str) -> list[dict]:
    """Return list of {id, name} dicts matching query via GraphQL."""
    async with httpx.AsyncClient(headers=_HEADERS, timeout=10) as client:
        resp = await client.post(
            GRAPHQL_URL,
            json={"query": _SCHOOL_SEARCH_QUERY, "variables": {"q": {"text": query}}},
        )
        resp.raise_for_status()
        edges = (
            resp.json()
            .get("data", {})
            .get("newSearch", {})
            .get("schools", {})
            .get("edges", [])
        )

    seen: set[int] = set()
    results = []
    for edge in edges:
        node = edge.get("node", {})
        lid = int(node["legacyId"])
        if lid in seen:
            continue
        seen.add(lid)
        city = node.get("city") or ""
        state = node.get("state") or ""
        loc = f" — {city}, {state}" if city else ""
        results.append({"id": lid, "name": f"{node['name']}{loc}"})
    return results


# ── Professor ID sweep ────────────────────────────────────────────────────────

async def _ids_for_letter(client: httpx.AsyncClient, school_id: int, letter: str) -> list[int]:
    url = f"{BASE_URL}/search/professors/{school_id}?q={letter}"
    try:
        resp = await client.get(url)
        return [int(x) for x in re.findall(r'"legacyId":(\d+)', resp.text)]
    except Exception:
        return []


async def _fetch_all_professor_ids(client: httpx.AsyncClient, school_id: int) -> set[int]:
    letters = [""] + list("abcdefghijklmnopqrstuvwxyz")
    all_ids: set[int] = set()
    batch_size = 9

    for i in range(0, len(letters), batch_size):
        batch = letters[i : i + batch_size]
        results = await asyncio.gather(
            *[_ids_for_letter(client, school_id, l) for l in batch],
            return_exceptions=True,
        )
        for r in results:
            if isinstance(r, list):
                all_ids.update(r)
        await asyncio.sleep(0.15)  # polite inter-batch delay

    return all_ids


# ── Professor detail fetch ────────────────────────────────────────────────────

async def _fetch_single_professor(client: httpx.AsyncClient, prof_id: int) -> dict | None:
    encoded_id = _encode_teacher_id(prof_id)
    payload = {
        "query": _PROF_QUERY,
        "variables": {"id": encoded_id},
    }
    headers = {**_HEADERS, "Referer": f"{BASE_URL}/ShowRatings.jsp?tid={prof_id}"}
    try:
        resp = await client.post(GRAPHQL_URL, json=payload, headers=headers)
        data = resp.json()
        node = data.get("data", {}).get("node")
        if not node:
            return None

        courses = [c["courseName"] for c in (node.get("courseCodes") or [])]
        wta = node.get("wouldTakeAgainPercent")
        # RMP returns 0 or -1 when data is unavailable
        if wta is not None and wta <= 0:
            wta = None

        return {
            "id": prof_id,
            "name": f"{node['firstName']} {node['lastName']}".strip(),
            "department": node.get("department") or "",
            "rating": node.get("avgRating") or 0.0,
            "difficulty": node.get("avgDifficulty") or 0.0,
            "would_take_again": wta,
            "num_ratings": node.get("numRatings") or 0,
            "courses": courses,
        }
    except Exception:
        return None


async def _fetch_professor_details(
    client: httpx.AsyncClient, prof_ids: set[int]
) -> list[dict]:
    ids = list(prof_ids)
    professors: list[dict] = []
    batch_size = 20

    for i in range(0, len(ids), batch_size):
        batch = ids[i : i + batch_size]
        results = await asyncio.gather(
            *[_fetch_single_professor(client, pid) for pid in batch],
            return_exceptions=True,
        )
        for r in results:
            if isinstance(r, dict):
                professors.append(r)
        await asyncio.sleep(0.1)

    return professors


# ── Public fetch API ──────────────────────────────────────────────────────────

async def fetch_professors(school_id: int) -> list[dict]:
    """Fetch all professors at a school. Returns list of professor dicts."""
    async with httpx.AsyncClient(headers=_HEADERS, timeout=15) as client:
        prof_ids = await _fetch_all_professor_ids(client, school_id)
        if not prof_ids:
            return []
        professors = await _fetch_professor_details(client, prof_ids)

    # Filter out zero-rating placeholders and sort by rating desc
    professors = [p for p in professors if p["num_ratings"] > 0]
    professors.sort(key=lambda p: p["rating"], reverse=True)
    return professors


# ── Snippets ──────────────────────────────────────────────────────────────────

async def fetch_snippets(professor_id: int, course: str = "") -> list[dict]:
    """Fetch up to 3 recent review snippets for a professor."""
    encoded_id = _encode_teacher_id(professor_id)
    headers = {
        **_HEADERS,
        "Referer": f"{BASE_URL}/ShowRatings.jsp?tid={professor_id}",
    }

    # First get num_ratings
    detail_payload = {"query": _PROF_QUERY, "variables": {"id": encoded_id}}
    async with httpx.AsyncClient(headers=headers, timeout=10) as client:
        try:
            detail_resp = await client.post(GRAPHQL_URL, json=detail_payload)
            num_ratings = (
                detail_resp.json()
                .get("data", {})
                .get("node", {})
                .get("numRatings", 20)
            ) or 20
        except Exception:
            num_ratings = 20

        ratings_payload = {
            "query": _RATINGS_QUERY,
            "variables": {
                "id": encoded_id,
                "count": min(num_ratings, 100),
                "courseFilter": course if course else None,
                "cursor": "",
            },
        }
        try:
            ratings_resp = await client.post(GRAPHQL_URL, json=ratings_payload)
            edges = (
                ratings_resp.json()
                .get("data", {})
                .get("node", {})
                .get("ratings", {})
                .get("edges", [])
            )
        except Exception:
            return []

    snippets = []
    for edge in edges:
        node = edge.get("node", {})
        comment = (node.get("comment") or "").strip()
        if not comment or comment.lower() in ("no comments", "n/a", ""):
            continue

        try:
            date_str = node["date"][:19]
            date = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S").strftime("%b %Y")
        except Exception:
            date = ""

        snippets.append({
            "comment": comment[:300],
            "course": node.get("class") or "",
            "date": date,
            "rating": node.get("helpfulRating") or 0,
            "difficulty": node.get("difficultyRating") or 0,
        })

        if len(snippets) >= 3:
            break

    return snippets
