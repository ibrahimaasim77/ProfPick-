"""ProfPick — Rate My Professor browser built with Streamlit."""

import streamlit as st
from rmp_data import get_professor_cards, ProfessorCard

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ProfPick",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    /* Dark base */
    html, body, [data-testid="stAppViewContainer"] {
        background-color: #0e1117;
        color: #e0e0e0;
    }
    [data-testid="stHeader"] { background-color: #0e1117; }

    /* Hide Streamlit footer */
    footer { visibility: hidden; }

    /* Search inputs */
    .stTextInput > div > div > input {
        background-color: #1c2333;
        color: #e0e0e0;
        border: 1px solid #2d3748;
        border-radius: 8px;
    }
    .stTextInput label { color: #a0aec0 !important; font-size: 0.85rem; }

    /* Select box */
    .stSelectbox > div > div {
        background-color: #1c2333;
        color: #e0e0e0;
        border: 1px solid #2d3748;
        border-radius: 8px;
    }

    /* Professor card */
    .prof-card {
        background: #1a1f2e;
        border: 1px solid #2d3748;
        border-radius: 12px;
        padding: 20px 24px;
        margin-bottom: 16px;
        position: relative;
    }
    .prof-card:hover { border-color: #4a5568; }

    /* Rating badge */
    .rating-badge {
        display: inline-block;
        font-size: 2rem;
        font-weight: 700;
        padding: 8px 18px;
        border-radius: 10px;
        line-height: 1;
    }
    .rating-green  { background: #1a3a2a; color: #68d391; }
    .rating-yellow { background: #3a3420; color: #f6e05e; }
    .rating-red    { background: #3a1a1a; color: #fc8181; }
    .rating-gray   { background: #2d3748; color: #a0aec0; }

    /* Stat pills */
    .stat-pill {
        display: inline-block;
        background: #2d3748;
        border-radius: 20px;
        padding: 4px 12px;
        font-size: 0.82rem;
        color: #a0aec0;
        margin-right: 8px;
        margin-bottom: 6px;
    }
    .stat-pill span { color: #e2e8f0; font-weight: 600; }

    /* Course tags */
    .course-tag {
        display: inline-block;
        background: #1e3a5f;
        color: #90cdf4;
        border-radius: 6px;
        padding: 2px 8px;
        font-size: 0.75rem;
        margin-right: 4px;
        margin-bottom: 4px;
    }

    /* Review snippet */
    .snippet {
        background: #0e1117;
        border-left: 3px solid #4a5568;
        border-radius: 0 8px 8px 0;
        padding: 8px 12px;
        margin: 6px 0;
        font-size: 0.83rem;
        color: #cbd5e0;
    }
    .snippet-meta {
        font-size: 0.72rem;
        color: #718096;
        margin-bottom: 2px;
    }

    /* Section headers */
    .section-label {
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #718096;
        margin-bottom: 6px;
    }

    /* Prof name */
    .prof-name {
        font-size: 1.25rem;
        font-weight: 700;
        color: #e2e8f0;
        margin-bottom: 2px;
    }
    .prof-dept {
        font-size: 0.85rem;
        color: #718096;
        margin-bottom: 12px;
    }

    /* No results */
    .no-results {
        text-align: center;
        padding: 60px 20px;
        color: #718096;
        font-size: 1rem;
    }

    /* Search button */
    .stButton > button {
        background: #3b82f6;
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.5rem 2rem;
        font-weight: 600;
        width: 100%;
    }
    .stButton > button:hover { background: #2563eb; }

    /* Spinner */
    [data-testid="stSpinner"] > div { color: #3b82f6 !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Helper functions ──────────────────────────────────────────────────────────

def rating_class(rating: float) -> str:
    if rating >= 4.0:
        return "rating-green"
    if rating >= 3.0:
        return "rating-yellow"
    if rating > 0:
        return "rating-red"
    return "rating-gray"


def render_card(card: ProfessorCard, idx: int) -> None:
    rc = rating_class(card.rating)
    rating_display = f"{card.rating:.1f}" if card.rating else "N/A"
    difficulty_display = f"{card.difficulty:.1f}" if card.difficulty else "—"
    wta_display = f"{card.would_take_again:.0f}%" if card.would_take_again is not None else "—"
    num_display = str(card.num_ratings)

    courses_html = "".join(f'<span class="course-tag">{c}</span>' for c in card.courses[:8])
    courses_html = courses_html or '<span style="color:#718096;font-size:0.8rem">No courses listed</span>'

    snippets_html = ""
    for s in card.snippets:
        course_label = f"· {s.course}" if s.course else ""
        snippets_html += f"""
        <div class="snippet">
            <div class="snippet-meta">{s.date} {course_label}</div>
            {s.comment}
        </div>"""
    if not snippets_html:
        snippets_html = '<div style="color:#718096;font-size:0.8rem">No recent reviews available.</div>'

    html = f"""
    <div class="prof-card">
        <div style="display:flex;align-items:flex-start;gap:20px;flex-wrap:wrap">
            <div style="flex:0 0 auto">
                <div class="rating-badge {rc}">{rating_display}</div>
                <div style="text-align:center;font-size:0.7rem;color:#718096;margin-top:4px">/ 5.0</div>
            </div>
            <div style="flex:1;min-width:200px">
                <div class="prof-name">#{idx + 1} {card.name}</div>
                <div class="prof-dept">{card.department or "Department not listed"}</div>
                <div>
                    <span class="stat-pill">Difficulty <span>{difficulty_display}</span>/5</span>
                    <span class="stat-pill">Would Take Again <span>{wta_display}</span></span>
                    <span class="stat-pill">Ratings <span>{num_display}</span></span>
                </div>
            </div>
        </div>
        <div style="margin-top:16px">
            <div class="section-label">Courses</div>
            {courses_html}
        </div>
        <div style="margin-top:16px">
            <div class="section-label">Recent Reviews</div>
            {snippets_html}
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def sort_cards(cards: list[ProfessorCard], sort_by: str) -> list[ProfessorCard]:
    if sort_by == "Rating (highest first)":
        return sorted(cards, key=lambda c: c.rating, reverse=True)
    if sort_by == "Difficulty (easiest first)":
        return sorted(cards, key=lambda c: c.difficulty)
    if sort_by == "Would Take Again (highest first)":
        return sorted(cards, key=lambda c: c.would_take_again if c.would_take_again is not None else -1, reverse=True)
    if sort_by == "Number of Ratings (most first)":
        return sorted(cards, key=lambda c: c.num_ratings, reverse=True)
    return cards


# ── App header ────────────────────────────────────────────────────────────────
st.markdown(
    """
    <div style="text-align:center;padding:32px 0 8px">
        <div style="font-size:2.6rem;font-weight:800;color:#e2e8f0;letter-spacing:-0.5px">
            🎓 ProfPick
        </div>
        <div style="color:#718096;font-size:1rem;margin-top:4px">
            Find the best professor for your course
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Search bar ────────────────────────────────────────────────────────────────
st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
col_school, col_courses, col_btn = st.columns([3, 3, 1], gap="small")

with col_school:
    school_input = st.text_input(
        "University / College",
        placeholder="e.g. University of California Los Angeles",
        key="school_input",
    )

with col_courses:
    courses_input = st.text_input(
        "Course codes (optional, comma-separated)",
        placeholder="e.g. CSCI 101, MATH 141",
        key="courses_input",
    )

with col_btn:
    st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
    search_clicked = st.button("Search", use_container_width=True)

# Sort + filter row (only shown when results exist)
sort_by = "Rating (highest first)"
if "last_cards" in st.session_state and st.session_state.last_cards:
    col_sort, col_spacer = st.columns([2, 4], gap="small")
    with col_sort:
        sort_by = st.selectbox(
            "Sort by",
            ["Rating (highest first)", "Difficulty (easiest first)",
             "Would Take Again (highest first)", "Number of Ratings (most first)"],
            key="sort_select",
        )

st.markdown("<hr style='border-color:#2d3748;margin:16px 0'>", unsafe_allow_html=True)

# ── Search logic ──────────────────────────────────────────────────────────────
if search_clicked:
    if not school_input.strip():
        st.warning("Please enter a school name.")
    else:
        course_list = [c.strip() for c in courses_input.split(",") if c.strip()]

        with st.spinner("Fetching professors from Rate My Professor… this may take a moment."):
            cards, error = get_professor_cards(
                school_name=school_input.strip(),
                course_filters=course_list,
                fetch_snippets=True,
            )

        if error:
            st.error(error)
            st.session_state.last_cards = []
            st.session_state.last_school = ""
            st.session_state.last_courses = []
        else:
            st.session_state.last_cards = cards
            st.session_state.last_school = school_input.strip()
            st.session_state.last_courses = course_list
            st.rerun()

# ── Results display ───────────────────────────────────────────────────────────
if "last_cards" in st.session_state and st.session_state.last_cards:
    cards = st.session_state.last_cards
    sorted_cards = sort_cards(cards, sort_by)

    school_label = st.session_state.get("last_school", "")
    course_label = (
        " · ".join(st.session_state.get("last_courses", []))
        if st.session_state.get("last_courses")
        else "All Courses"
    )

    st.markdown(
        f"""<div style="color:#a0aec0;font-size:0.9rem;margin-bottom:16px">
            <b style="color:#e2e8f0">{len(cards)}</b> professor{'s' if len(cards) != 1 else ''}
            found at <b style="color:#e2e8f0">{school_label}</b>
            &nbsp;·&nbsp; {course_label}
        </div>""",
        unsafe_allow_html=True,
    )

    for i, card in enumerate(sorted_cards):
        render_card(card, i)

elif "last_cards" in st.session_state and st.session_state.last_cards == []:
    pass  # Error already shown above
else:
    st.markdown(
        """<div class="no-results">
            Enter your school name above and click <b>Search</b> to get started.<br>
            <span style="font-size:0.85rem">Optionally add course codes to filter professors who teach those classes.</span>
        </div>""",
        unsafe_allow_html=True,
    )
