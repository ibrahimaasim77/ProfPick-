"""Fullerton College live schedule data from schedule.nocccd.edu."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import httpx

FC_TERM = "202520"           # Winter/Spring 2026
FC_TERM_NAME = "Winter/Spring 2026"
FC_SCHOOL_ID = 1318          # RateMyProfessors school ID
FC_CAMP_CODES = {"2", "2NH"}  # Fullerton College campus codes (1/1NH = Cypress College)

_BASE = "https://schedule.nocccd.edu/data"
_CACHE_DIR = Path(__file__).parent / "cache"
_SCHEDULE_TTL_HOURS = 6

# Days encoded as individual keys in each meeting object
_DAY_KEYS = {
    "monDay": "M",
    "tueDay": "Tu",
    "wedDay": "W",
    "thuDay": "Th",
    "friDay": "F",
    "satDay": "Sa",
    "sunDay": "Su",
}


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class SectionMeeting:
    days: str        # e.g. "MWF", "Tu Th"
    start_time: str  # e.g. "7:40 PM"
    end_time: str    # e.g. "8:30 PM"
    building: str
    room: str

    def time_str(self) -> str:
        if self.start_time and self.end_time:
            return f"{self.days} {self.start_time}–{self.end_time}"
        return self.days or "Online"

    def location_str(self) -> str:
        if self.building and self.room:
            return f"{self.building} {self.room}"
        return ""


@dataclass
class CourseSection:
    crn: str
    subject: str
    course_number: str
    course_title: str
    instructor_name: str    # "Firstname Lastname"
    seats_available: int
    max_enrollment: int
    current_enrollment: int
    meetings: list[SectionMeeting] = field(default_factory=list)
    is_online: bool = False

    @property
    def course_code(self) -> str:
        return f"{self.subject} {self.course_number}".strip()

    @property
    def is_full(self) -> bool:
        return self.seats_available <= 0

    def primary_meeting(self) -> Optional[SectionMeeting]:
        return self.meetings[0] if self.meetings else None


# ── Name helpers ──────────────────────────────────────────────────────────────

def normalize_name(name: str) -> str:
    """Lowercase, strip non-alpha. Used for fuzzy matching RMP ↔ schedule."""
    return re.sub(r"[^a-z ]", "", name.lower()).strip()


def last_first_to_full(raw: str) -> str:
    """'Lastname, Firstname' → 'Firstname Lastname'."""
    if "," in raw:
        last, first = raw.split(",", 1)
        return f"{first.strip()} {last.strip()}"
    return raw.strip()


# ── Time formatting ───────────────────────────────────────────────────────────

def _fmt_time(t: str) -> str:
    """'1940' → '7:40 PM', '0800' → '8:00 AM'."""
    if not t or len(t) < 3:
        return t
    try:
        t = t.zfill(4)
        h, m = int(t[:2]), int(t[2:])
        period = "AM" if h < 12 else "PM"
        h12 = h % 12 or 12
        return f"{h12}:{m:02d} {period}"
    except Exception:
        return t


def _parse_days(meeting: dict) -> str:
    parts = [abbr for key, abbr in _DAY_KEYS.items() if meeting.get(key)]
    return " ".join(parts)


# ── Cache helpers ─────────────────────────────────────────────────────────────

def _cache_path(term: str) -> Path:
    return _CACHE_DIR / f"fc_schedule_{term}.json"


def _load_cache(term: str) -> list[dict] | None:
    path = _cache_path(term)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        fetched_at = datetime.fromisoformat(data["fetched_at"])
        if datetime.now(timezone.utc) - fetched_at > timedelta(hours=_SCHEDULE_TTL_HOURS):
            return None
        return data["sections"]
    except Exception:
        return None


def _save_cache(term: str, raw: list[dict]) -> None:
    _CACHE_DIR.mkdir(exist_ok=True)
    _cache_path(term).write_text(json.dumps({
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "term": term,
        "sections": raw,
    }))


# ── Parsing ───────────────────────────────────────────────────────────────────

def _parse_section(s: dict) -> CourseSection:
    meetings: list[SectionMeeting] = []
    is_online = False

    for m in (s.get("sectMeetings") or []):
        days = _parse_days(m)
        start = _fmt_time(m.get("beginTime") or "")
        end = _fmt_time(m.get("endTime") or "")
        building = (m.get("bldgDesc") or "").replace(" - CC", "").strip()
        room = m.get("roomCode") or ""

        if not days and not start:
            is_online = True

        meetings.append(SectionMeeting(
            days=days, start_time=start, end_time=end,
            building=building, room=room,
        ))

    instr_raw = s.get("sectInstrName") or "Staff"
    instr_name = last_first_to_full(instr_raw)

    title = (s.get("sectTitle") or s.get("sectLongText") or "").strip()
    # sectLongText is sometimes a long description — truncate to first sentence
    if len(title) > 80:
        title = title[:80].rsplit(" ", 1)[0] + "…"

    return CourseSection(
        crn=str(s.get("sectCrn") or ""),
        subject=(s.get("sectSubjCode") or "").strip(),
        course_number=(s.get("sectCrseNumb") or "").strip(),
        course_title=title,
        instructor_name=instr_name,
        seats_available=int(s.get("sectSeatsAvail") or 0),
        max_enrollment=int(s.get("sectMaxEnrl") or 0),
        current_enrollment=int(s.get("sectEnrl") or 0),
        meetings=meetings,
        is_online=is_online,
    )


# ── Public API ────────────────────────────────────────────────────────────────

def fetch_schedule(term: str = FC_TERM) -> list[CourseSection]:
    """Fetch Fullerton College sections for *term*, using cache when fresh."""
    raw = _load_cache(term)
    if raw is None:
        url = f"{_BASE}/{term}/sections.json"
        with httpx.Client(timeout=30) as client:
            resp = client.get(url)
            resp.raise_for_status()
            raw = resp.json()
        _save_cache(term, raw)
    # Filter to Fullerton College sections only (exclude Cypress College etc.)
    fc_raw = [s for s in raw if str(s.get("sectCampCode", "")) in FC_CAMP_CODES]
    return [_parse_section(s) for s in fc_raw]


def get_professor_sections_map(term: str = FC_TERM) -> dict[str, list[CourseSection]]:
    """Return {normalized_name: [sections]} for every instructor teaching this term."""
    result: dict[str, list[CourseSection]] = {}
    for sec in fetch_schedule(term):
        name = sec.instructor_name
        if name.lower() in ("staff", "tba", ""):
            continue
        key = normalize_name(name)
        result.setdefault(key, []).append(sec)
    return result


def get_subjects(term: str = FC_TERM) -> list[str]:
    """Return sorted list of unique subject codes offered this term."""
    return sorted({s.subject for s in fetch_schedule(term) if s.subject})


def get_sections_for_subject(subject: str, term: str = FC_TERM) -> list[CourseSection]:
    """All sections for a given subject code (e.g. 'MATH')."""
    subj = subject.strip().upper()
    return [s for s in fetch_schedule(term) if s.subject.upper() == subj]
