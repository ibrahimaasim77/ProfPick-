"""ProfPick Streamlit app."""

from __future__ import annotations

import streamlit as st
from streamlit_searchbox import st_searchbox

from rmp_data import (
    DEFAULT_SNIPPET_BATCH,
    ProfessorCard,
    SchoolOption,
    _normalize_course,
    search_school_options,
    hydrate_snippets,
    get_professor_cards,
)

st.set_page_config(
    page_title="ProfPick",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    html,body,[data-testid="stAppViewContainer"]{font-family:'Inter',sans-serif;background:#07090f;color:#e2e8f0;}
    header[data-testid="stHeader"]{display:none!important;}
    [data-testid="stToolbar"]{display:none!important;}
    [data-testid="stDecoration"]{display:none!important;}
    [data-testid="stStatusWidget"]{display:none!important;}
    footer{display:none!important;}
    #MainMenu{display:none!important;}
    .block-container{max-width:1060px;padding-top:2rem;padding-bottom:5rem;}

    .hero{padding:2rem 0 1.8rem 0;text-align:center;}
    .hero-title{font-size:2.5rem;font-weight:800;letter-spacing:-0.05em;line-height:1.1;
        background:linear-gradient(135deg,#f1f5f9 30%,#60a5fa 100%);
        -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;margin-bottom:.5rem;}
    .hero-sub{font-size:.92rem;color:#475569;line-height:1.6;}

    .search-panel{background:rgba(15,23,42,.65);border:1px solid #1e293b;border-radius:16px;
        padding:1.4rem 1.6rem 1.2rem 1.6rem;margin-bottom:2rem;}

    .stTextInput>div>div>input{background:#0d1117!important;color:#e2e8f0!important;
        border:1px solid #1e293b!important;border-radius:10px!important;font-size:.9rem!important;
        transition:border-color .15s,box-shadow .15s;}
    .stTextInput>div>div>input:focus{border-color:#2563eb!important;box-shadow:0 0 0 3px rgba(37,99,235,.14)!important;}
    .stTextInput label,.stSelectbox label,.stMultiSelect label{color:#64748b!important;font-size:.75rem!important;
        font-weight:600!important;letter-spacing:.07em!important;text-transform:uppercase!important;}
    .stMultiSelect [data-baseweb="select"]>div{background:#0d1117!important;border:1px solid #1e293b!important;
        border-radius:10px!important;min-height:42px!important;}
    .stMultiSelect [data-baseweb="select"]>div:focus-within{border-color:#2563eb!important;
        box-shadow:0 0 0 3px rgba(37,99,235,.14)!important;}
    .stMultiSelect [data-baseweb="tag"]{background:rgba(37,99,235,.18)!important;
        border:1px solid rgba(59,130,246,.35)!important;border-radius:6px!important;color:#93c5fd!important;}
    .stMultiSelect [data-baseweb="menu"]{background:#0d1117!important;border:1px solid #1e293b!important;border-radius:8px!important;}
    .stMultiSelect input{color:#e2e8f0!important;}

    /* searchbox component container */
    [data-testid="stCustomComponentV1"]{border-radius:10px;overflow:visible;}
    [data-testid="stCustomComponentV1"] iframe{outline:none!important;border:none!important;}

    .stButton>button{background:#2563eb!important;color:#fff!important;border:none!important;
        border-radius:10px!important;font-weight:700!important;font-size:.88rem!important;
        width:100%!important;transition:background .15s!important;}
    .stButton>button:hover{background:#1d4ed8!important;}

    @keyframes podiumRise{from{transform:translateY(80px);opacity:0;}to{transform:translateY(0);opacity:1;}}
    @keyframes crownBounce{0%,100%{transform:translateY(0) scale(1);}45%{transform:translateY(-12px) scale(1.12);}75%{transform:translateY(-5px) scale(1.05);}}

    .podium-section{margin-bottom:2rem;border-radius:20px;overflow:hidden;
        background:rgba(10,14,26,.80);border:1px solid #1e293b;}
    .podium-hdr{text-align:center;padding:1.4rem 1rem .4rem 1rem;font-size:.62rem;font-weight:700;
        letter-spacing:.22em;text-transform:uppercase;color:#334155;}
    .podium-stage{display:flex;align-items:flex-end;justify-content:center;padding:0 1.5rem;gap:0;}
    .podium-col{display:flex;flex-direction:column;align-items:center;flex:1;max-width:320px;
        animation:podiumRise .6s cubic-bezier(.34,1.5,.64,1) both;}
    .p-avatar{font-size:2.8rem;line-height:1;margin-bottom:.1rem;
        animation:crownBounce .6s ease-in-out 1.7s 2 both;}
    .p-medal{font-size:1.15rem;margin-bottom:.35rem;}
    .p-name{font-size:.84rem;font-weight:700;color:#f1f5f9;text-align:center;
        max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;
        margin-bottom:.2rem;padding:0 .5rem;}
    .p-dept{font-size:.67rem;color:#475569;margin-bottom:.3rem;text-align:center;
        max-width:190px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
    .p-score{font-size:1.8rem;font-weight:800;border-radius:10px;
        padding:.18rem .7rem;margin-bottom:.5rem;line-height:1;}
    .p-block{width:100%;display:flex;flex-direction:column;align-items:center;
        justify-content:flex-start;padding-top:.7rem;border-radius:10px 10px 0 0;}
    .p-block-1{height:130px;background:linear-gradient(180deg,rgba(120,80,0,.35) 0%,rgba(30,16,0,.80) 100%);
        border:1px solid rgba(251,191,36,.25);border-bottom:none;box-shadow:0 0 40px rgba(251,191,36,.06) inset;}
    .p-block-2{height:92px;background:linear-gradient(180deg,rgba(71,85,105,.22) 0%,rgba(15,23,42,.80) 100%);
        border:1px solid rgba(100,116,139,.18);border-bottom:none;}
    .p-block-3{height:62px;background:linear-gradient(180deg,rgba(5,90,60,.18) 0%,rgba(15,23,42,.80) 100%);
        border:1px solid rgba(52,211,153,.12);border-bottom:none;}
    .p-rank-lbl{font-size:.65rem;font-weight:800;letter-spacing:.1em;opacity:.35;}
    .p-rank-lbl-1{color:#fbbf24;}.p-rank-lbl-2{color:#94a3b8;}.p-rank-lbl-3{color:#34d399;}
    .podium-footer{padding:0 1.5rem 1.4rem 1.5rem;display:flex;gap:0;}
    .p-quote{flex:1;max-width:320px;font-size:.71rem;color:#475569;font-style:italic;
        text-align:center;line-height:1.45;padding:.6rem .6rem 0 .6rem;}

    .rating-green{background:rgba(5,150,105,.15);color:#34d399;border:1px solid rgba(52,211,153,.20);}
    .rating-yellow{background:rgba(245,158,11,.15);color:#fbbf24;border:1px solid rgba(251,191,36,.20);}
    .rating-red{background:rgba(239,68,68,.15);color:#f87171;border:1px solid rgba(248,113,113,.20);}
    .rating-gray{background:rgba(71,85,105,.25);color:#94a3b8;border:1px solid rgba(148,163,184,.15);}

    .results-bar{display:flex;align-items:center;gap:.75rem;margin-bottom:1.2rem;
        font-size:.82rem;color:#475569;}
    .results-bar strong{color:#94a3b8;font-weight:700;}
    .results-bar .rschool{color:#60a5fa;font-weight:600;}

    .prof-card{background:rgba(10,14,26,.85);border:1px solid #1e293b;border-radius:14px;
        padding:18px 20px;margin-bottom:10px;transition:border-color .15s;}
    .prof-card:hover{border-color:#2563eb40;}
    .card-rating{display:flex;align-items:center;justify-content:center;font-size:1.75rem;
        font-weight:800;width:70px;height:70px;border-radius:12px;flex-shrink:0;line-height:1;}
    .card-out-of{font-size:.64rem;color:#334155;text-align:center;margin-top:.25rem;}
    .rank-chip{display:inline-block;font-size:.66rem;font-weight:700;color:#334155;
        background:#0d1117;border:1px solid #1e293b;border-radius:5px;
        padding:.12rem .38rem;margin-right:.38rem;}
    .card-name{font-size:1.1rem;font-weight:700;color:#f1f5f9;margin-bottom:.1rem;}
    .card-dept{font-size:.78rem;color:#475569;margin-bottom:.45rem;}
    .card-summary{font-size:.79rem;color:#64748b;font-style:italic;margin-bottom:.55rem;
        line-height:1.45;border-left:2px solid #1e293b;padding-left:.6rem;}
    .stat-row{display:flex;flex-wrap:wrap;gap:.35rem;}
    .stat-chip{display:inline-flex;align-items:center;gap:.3rem;background:#0d1117;
        border:1px solid #1e293b;border-radius:7px;padding:.22rem .55rem;
        font-size:.76rem;color:#475569;}
    .stat-chip strong{color:#94a3b8;font-weight:600;}
    .section-lbl{font-size:.62rem;text-transform:uppercase;letter-spacing:.14em;
        color:#1e293b;font-weight:700;margin:.85rem 0 .35rem 0;}
    .course-wrap{display:flex;flex-wrap:wrap;gap:.25rem;}
    .course-tag{background:rgba(37,99,235,.09);color:#60a5fa;border:1px solid rgba(59,130,246,.18);
        border-radius:5px;padding:.18rem .5rem;font-size:.72rem;font-weight:500;
        font-family:'SF Mono',monospace;}
    .snippet{background:#07090f;border:1px solid #1e293b;border-radius:8px;
        padding:.6rem .75rem;margin-top:.35rem;color:#94a3b8;font-size:.82rem;line-height:1.5;}
    .snippet-meta{font-size:.66rem;color:#334155;margin-bottom:.25rem;}

    [data-testid="stAlert"]{background:rgba(239,68,68,.07)!important;
        border:1px solid rgba(239,68,68,.20)!important;border-radius:10px!important;color:#fca5a5!important;}
    .stCaption{color:#334155!important;font-size:.76rem!important;}

    .empty-wrap{text-align:center;padding:4rem 1rem 3rem;}
    .empty-title{font-size:1.1rem;font-weight:700;color:#1e293b;margin-bottom:.5rem;}
    .empty-steps{display:flex;justify-content:center;align-items:center;
        gap:.75rem;margin-top:1.8rem;flex-wrap:wrap;}
    .step-pill{display:flex;align-items:center;gap:.5rem;background:rgba(15,23,42,.7);
        border:1px solid #1e293b;border-radius:999px;padding:.4rem .9rem;
        font-size:.78rem;color:#475569;}
    .step-num{width:20px;height:20px;display:flex;align-items:center;justify-content:center;
        background:rgba(37,99,235,.15);border:1px solid rgba(59,130,246,.2);
        border-radius:50%;font-size:.7rem;font-weight:700;color:#3b82f6;flex-shrink:0;}
    .step-arrow{color:#1e293b;font-size:.8rem;}

    .btn-secondary .stButton>button{background:transparent!important;border:1px solid #1e293b!important;
        color:#64748b!important;font-weight:600!important;}
    .btn-secondary .stButton>button:hover{border-color:#2563eb!important;color:#60a5fa!important;
        background:rgba(37,99,235,.06)!important;}

    .course-tag-active{background:rgba(37,99,235,.22)!important;color:#93c5fd!important;
        border-color:rgba(59,130,246,.45)!important;font-weight:700!important;}
    </style>""",
    unsafe_allow_html=True,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def ensure_state() -> None:
    for k, v in {
        "results": [], "last_school": None, "last_courses": [], "error": None,
        "school_map": {}, "available_courses": [],
    }.items():
        st.session_state.setdefault(k, v)


def rc(r: float) -> str:
    if r >= 4.0: return "rating-green"
    if r >= 3.0: return "rating-yellow"
    if r > 0:    return "rating-red"
    return "rating-gray"


def parse_courses(raw: str) -> list[str]:
    return [c.strip() for c in raw.split(",") if c.strip()]


_MONTH_NUM = {"jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,
              "jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12}

def _date_sort_key(date_str: str | None) -> tuple[int, int]:
    if not date_str:
        return (0, 0)
    parts = date_str.strip().split()
    if len(parts) != 2:
        return (0, 0)
    return (int(parts[1]) if parts[1].isdigit() else 0,
            _MONTH_NUM.get(parts[0].lower()[:3], 0))


def _e(t: str) -> str:
    return t.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;")


# ── School searchbox ──────────────────────────────────────────────────────────

def _school_search_fn(query: str) -> list[str]:
    if not query or len(query) < 2:
        return []
    schools, _ = search_school_options(query)
    if "school_map" not in st.session_state:
        st.session_state.school_map = {}
    for s in schools:
        st.session_state.school_map[s.name] = s
    return [s.name for s in schools]


# ── Review summary ────────────────────────────────────────────────────────────

_POS = {"great":"great teacher","amazing":"amazing","excellent":"excellent",
        "helpful":"very helpful","clear":"explains clearly","best":"one of the best",
        "easy":"easy to follow","love":"loved by students","engaging":"engaging",
        "fair":"fair grader","organized":"well organized","passionate":"passionate",
        "approachable":"approachable","recommend":"highly recommended",
        "interesting":"interesting","knowledgeable":"knowledgeable","caring":"caring"}
_NEG = {"hard":"tough exams","difficult":"difficult coursework","boring":"dry lectures",
        "confusing":"can be confusing","unfair":"grading can feel unfair",
        "strict":"strict grader","avoid":"students advise caution",
        "disorganized":"disorganized","rude":"can be dismissive"}

def _summary(card: ProfessorCard) -> str:
    if not card.snippets:
        return ""
    txt = " ".join(s.comment for s in card.snippets).lower()
    pos = [ph for kw, ph in _POS.items() if kw in txt]
    neg = [ph for kw, ph in _NEG.items() if kw in txt]
    parts: list[str] = []
    if pos: parts.append(", ".join(pos[:2]))
    if neg: parts.append(neg[0])
    if parts:
        wta = card.would_take_again
        tail = f" · {wta:.0f}% would retake" if wta is not None else ""
        return ". ".join(parts) + "." + tail
    t = card.snippets[0].comment
    return (t[:115] + "…") if len(t) > 115 else t


# ── Podium ────────────────────────────────────────────────────────────────────

def render_podium(cards: list[ProfessorCard]) -> None:
    if not cards:
        return
    top = cards[:3]

    def _col(card: ProfessorCard, rank: int, delay: float) -> str:
        score = f"{card.rating:.1f}" if card.rating else "N/A"
        medal = {1:"🥇",2:"🥈",3:"🥉"}[rank]
        q = _summary(card)
        q_html = f'<div class="p-quote">{_e(q[:120] + ("…" if len(q)>120 else ""))}</div>' if q else '<div class="p-quote"></div>'
        return (
            f'<div class="podium-col" style="animation-delay:{delay}s">'
            f'<div class="p-avatar">👨\u200d🏫</div>'
            f'<div class="p-medal">{medal}</div>'
            f'<div class="p-name">{_e(card.name)}</div>'
            f'<div class="p-dept">{_e(card.department or "")}</div>'
            f'<div class="p-score {rc(card.rating)}">{score}</div>'
            f'<div class="p-block p-block-{rank}"><div class="p-rank-lbl p-rank-lbl-{rank}">#{rank}</div></div>'
            f'{q_html}'
            f'</div>'
        )

    # Visual: 2nd|1st|3rd   animate: 3rd(0s)→2nd(.35s)→1st(.72s)
    col2 = _col(top[1], 2, 0.35) if len(top) >= 2 else '<div class="podium-col"></div>'
    col1 = _col(top[0], 1, 0.72)
    col3 = _col(top[2], 3, 0.00) if len(top) >= 3 else '<div class="podium-col"></div>'

    st.markdown(
        '<div class="podium-section">'
        '<div class="podium-hdr">Top Professors</div>'
        f'<div class="podium-stage">{col2}{col1}{col3}</div>'
        '</div>',
        unsafe_allow_html=True,
    )


# ── Sort ──────────────────────────────────────────────────────────────────────

def sort_cards(cards: list[ProfessorCard], by: str) -> list[ProfessorCard]:
    if by == "Rating ↓":       return sorted(cards, key=lambda c:(c.rating,c.num_ratings), reverse=True)
    if by == "Easiest first":  return sorted(cards, key=lambda c:(c.difficulty or 99,-c.rating))
    if by == "Would Take Again ↓": return sorted(cards, key=lambda c:(c.would_take_again if c.would_take_again is not None else -1,c.rating), reverse=True)
    if by == "Most Ratings":   return sorted(cards, key=lambda c:(c.num_ratings,c.rating), reverse=True)
    if by == "Most Recent":    return sorted(cards, key=lambda c:_date_sort_key(c.last_course_review_date), reverse=True)
    return cards


# ── Card ──────────────────────────────────────────────────────────────────────

def _is_active_course(c: str, filters: list[str]) -> bool:
    cn = _normalize_course(c)
    for cf in filters:
        cf_n = _normalize_course(cf)
        if cn == cf_n:
            return True
        if cn.startswith(cf_n) and len(cn) > len(cf_n) and cn[len(cf_n)].isdigit():
            return True
    return False


def render_card(
    card: ProfessorCard,
    index: int,
    course_filters: list[str] | None = None,
) -> None:
    score = f"{card.rating:.1f}" if card.rating else "N/A"
    diff  = f"{card.difficulty:.1f}" if card.difficulty else "—"
    wta   = f"{card.would_take_again:.0f}%" if card.would_take_again is not None else "—"

    active_filters = course_filters or []
    courses = "".join(
        f'<span class="course-tag{" course-tag-active" if _is_active_course(c, active_filters) else ""}">{_e(c)}</span>'
        for c in card.courses[:12]
    ) or '<span style="color:#1e293b;font-size:.76rem">None listed</span>'

    sm = _summary(card)
    sm_html = f'<div class="card-summary">{_e(sm)}</div>' if sm else ""

    top = card.snippets[0] if card.snippets else None
    if top:
        cb = f" · {_e(top.course)}" if top.course else ""
        snips = f'<div class="snippet"><div class="snippet-meta">{_e(top.date)}{cb}</div>{_e(top.comment)}</div>'
    else:
        snips = '<div style="color:#1e293b;font-size:.78rem;margin-top:.3rem">No review loaded yet.</div>'

    # Recency badge — green if active within 18 months, gray with date otherwise
    if card.last_course_review_date:
        if card.recently_active:
            recency_chip = (
                f'<span class="stat-chip" style="border-color:#34d39940;color:#34d399">'
                f'Last reviewed {_e(card.last_course_review_date)}</span>'
            )
        else:
            recency_chip = (
                f'<span class="stat-chip" style="border-color:#47556940;color:#475569">'
                f'Last reviewed {_e(card.last_course_review_date)}</span>'
            )
    else:
        recency_chip = ""

    # Build HTML as a joined list — NO blank lines, NO leading whitespace.
    # A blank line inside st.markdown HTML terminates the HTML block in CommonMark,
    # causing subsequent indented content to be rendered as a code block.
    html = "".join([
        '<div class="prof-card">',
        '<div style="display:flex;gap:14px;align-items:flex-start">',
        '<div style="flex-shrink:0;text-align:center">',
        f'<div class="card-rating {rc(card.rating)}">{score}</div>',
        '<div class="card-out-of">/ 5.0</div>',
        '</div>',
        '<div style="flex:1;min-width:0">',
        f'<div class="card-name"><span class="rank-chip">#{index+1}</span>{_e(card.name)}</div>',
        f'<div class="card-dept">{_e(card.department or "Department not listed")}</div>',
        sm_html,
        '<div class="stat-row">',
        f'<span class="stat-chip">Difficulty <strong>{diff}</strong>/5</span>',
        f'<span class="stat-chip">Would Take Again <strong>{wta}</strong></span>',
        f'<span class="stat-chip">Ratings <strong>{card.num_ratings}</strong></span>',
        recency_chip,
        '</div>',
        '<div class="section-lbl">Courses</div>',
        f'<div class="course-wrap">{courses}</div>',
        '<div class="section-lbl">Reviews</div>',
        snips,
        '</div>',
        '</div>',
        '</div>',
    ])
    st.markdown(html, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# App
# ─────────────────────────────────────────────────────────────────────────────

ensure_state()
results: list[ProfessorCard] = st.session_state.results

# Podium is the first thing you see when results exist
if results:
    _current_sort = st.session_state.get("sort_select", "Rating ↓")
    render_podium(sort_cards(results, _current_sort))

# Hero
st.markdown(
    '<div class="hero">'
    '<div class="hero-title">ProfPick</div>'
    '<div class="hero-sub">Search your campus · filter by course · rank professors instantly</div>'
    '</div>',
    unsafe_allow_html=True,
)

# Search panel
col_school, col_courses = st.columns([1, 1], gap="medium")

with col_school:
    selected_name: str | None = st_searchbox(
        _school_search_fn,
        key="school_searchbox",
        placeholder="UCLA, MIT, Ohio State…",
        label="School",
        clear_on_submit=False,
        debounce=200,
        style_overrides={
            "wrapper": {"outline": "none"},
            "searchbox": {
                "control": {
                    "backgroundColor": "#0d1117",
                    "border": "1px solid #1e293b",
                    "borderRadius": "10px",
                    "boxShadow": "none",
                    "outline": "none",
                },
                "menuList": {
                    "backgroundColor": "#0d1117",
                    "border": "1px solid #1e293b",
                    "borderRadius": "8px",
                    "padding": "4px",
                },
                "input": {"color": "#e2e8f0"},
                "singleValue": {"color": "#e2e8f0"},
                "placeholder": {"color": "#475569"},
                "option": {
                    "color": "#cbd5e1",
                    "backgroundColor": "#0d1117",
                    "highlightColor": "#1e293b",
                },
            },
        },
    )
    school_map: dict[str, SchoolOption] = st.session_state.get("school_map", {})
    selected_school_obj: SchoolOption | None = school_map.get(selected_name) if selected_name else None

with col_courses:
    _available_courses: list[str] = st.session_state.get("available_courses", [])
    if _available_courses:
        _multi_selected: list[str] = st.multiselect(
            "Course codes (optional)",
            options=_available_courses,
            placeholder="Pick a course…",
            key="course_multiselect",
        )
        _course_input_raw = st.text_input(
            "Or type additional codes",
            placeholder="CSCI 101, MATH 141",
            key="course_text_input",
            label_visibility="collapsed",
        )
    else:
        _multi_selected = []
        _course_input_raw = st.text_input(
            "Course codes (optional)",
            placeholder="CSCI 101, MATH 141",
            key="course_text_input",
        )

# Compute current course filters once (used by both manual load and auto-reload)
_typed_courses = parse_courses(_course_input_raw)
_current_courses = list(dict.fromkeys(_multi_selected + _typed_courses))

col_btn, col_hint = st.columns([1, 3], gap="medium")
with col_btn:
    load_clicked = st.button("Load Professors", use_container_width=True)
with col_hint:
    if selected_school_obj:
        msg = f"✓ {selected_school_obj.name}"
        color = "#475569"
    elif selected_name:
        msg = "School not found — try searching again"
        color = "#ef4444"
    else:
        msg = "Type a school name above to search"
        color = "#334155"
    st.markdown(f'<div style="padding-top:.68rem;font-size:.82rem;color:{color}">{_e(msg)}</div>', unsafe_allow_html=True)

if load_clicked:
    if not selected_school_obj:
        st.session_state.error = "Search for a school and select it before loading professors."
        st.session_state.results = []
    else:
        with st.spinner(f"Loading professors at {selected_school_obj.name}…"):
            cards, err = get_professor_cards(
                school_id=selected_school_obj.id,
                school_name=selected_school_obj.name,
                course_filters=_current_courses,
                snippet_batch_size=DEFAULT_SNIPPET_BATCH,
            )
        st.session_state.results      = cards
        st.session_state.last_school  = selected_school_obj
        st.session_state.last_courses = _current_courses
        st.session_state.error        = err
        # Collect all unique course codes for the multiselect (only on manual load)
        if cards:
            st.session_state.available_courses = sorted(
                {c for card in cards for c in card.courses if c}
            )

# Auto-reload when course filter changes (results already loaded, no manual click needed)
_reload_school: SchoolOption | None = st.session_state.get("last_school")
if (
    not load_clicked
    and _reload_school is not None
    and st.session_state.get("results")
    and sorted(_current_courses) != sorted(st.session_state.get("last_courses", []))
):
    with st.spinner("Updating professor list…"):
        _ac, _ae = get_professor_cards(
            school_id=_reload_school.id,
            school_name=_reload_school.name,
            course_filters=_current_courses,
            snippet_batch_size=DEFAULT_SNIPPET_BATCH,
        )
    st.session_state.results      = _ac
    st.session_state.last_courses = _current_courses
    st.session_state.error        = _ae
    st.rerun()

# Error
if st.session_state.error:
    st.error(st.session_state.error)

# Results
if results:
    last_school: SchoolOption = st.session_state.last_school
    last_courses: list[str]   = st.session_state.last_courses
    course_label = ", ".join(last_courses) if last_courses else "All courses"

    col_meta, col_sort = st.columns([3, 1], gap="medium")
    with col_meta:
        st.markdown(
            '<div class="results-bar">'
            f'<strong>{len(results)}</strong> professors at '
            f'<span class="rschool">{_e(last_school.name)}</span>'
            f' · <span style="color:#475569">{_e(course_label)}</span>'
            '</div>',
            unsafe_allow_html=True,
        )
    with col_sort:
        _base_sorts = ["Rating ↓", "Easiest first", "Would Take Again ↓", "Most Ratings"]
        sort_options = (["Most Recent"] + _base_sorts) if last_courses else _base_sorts
        sort_by = st.selectbox("Sort by", sort_options, index=0, key="sort_select")

    sorted_cards = sort_cards(results, sort_by)

    missing = sum(1 for c in sorted_cards if not c.snippets)
    if missing:
        col_more, col_note = st.columns([1, 3], gap="medium")
        with col_more:
            st.markdown('<div class="btn-secondary">', unsafe_allow_html=True)
            load_more = st.button("Load More Reviews", use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)
        with col_note:
            st.markdown(
                f'<div style="padding-top:.65rem;font-size:.78rem;color:#334155">'
                f'{missing} professor{"s" if missing!=1 else ""} still need reviews loaded.</div>',
                unsafe_allow_html=True,
            )
        if load_more:
            with st.spinner("Loading reviews…"):
                hydrate_snippets(sorted_cards, last_courses, limit=DEFAULT_SNIPPET_BATCH)
            st.session_state.results = sorted_cards
            st.rerun()

    for i, card in enumerate(sorted_cards):
        render_card(card, i, course_filters=last_courses)

else:
    st.markdown(
        '<div class="empty-wrap">'
        '<div class="empty-title">No results yet</div>'
        '<div class="empty-steps">'
        '<div class="step-pill"><div class="step-num">1</div>Type school name</div>'
        '<div class="step-arrow">→</div>'
        '<div class="step-pill"><div class="step-num">2</div>Click a result</div>'
        '<div class="step-arrow">→</div>'
        '<div class="step-pill"><div class="step-num">3</div>Add course codes</div>'
        '<div class="step-arrow">→</div>'
        '<div class="step-pill"><div class="step-num">4</div>Load Professors</div>'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )
