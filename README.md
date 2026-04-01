# ProfPick

Search, filter, and rank professors at any US university — powered by live RateMyProfessors data.

![Python](https://img.shields.io/badge/Python-3.11+-blue?style=flat-square)
![Streamlit](https://img.shields.io/badge/Streamlit-1.32+-red?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)

---

## What it does

ProfPick lets you find the best professor for a specific course at your school — not just any professor who could theoretically teach it, but ones with verified reviews tied to that course code.

- **Search any US university** by name with live autocomplete
- **Filter by course code** — supports exact match (`CSCI 111`) and prefix match (`CSCI`)
- **Ranked by rating**, difficulty, would-take-again percentage, and most-recent review date
- **Review snippets** pulled directly per professor so you can read what students actually said
- **Recency badges** — green if reviewed within 18 months, grey otherwise
- **Auto-updates** the list as soon as you change the course filter — no button click needed

---

## Tech stack

| Layer | What's used |
|-------|-------------|
| UI | [Streamlit](https://streamlit.io) |
| Data | RateMyProfessors GraphQL API (via `httpx`) |
| Async | `asyncio.gather` — concurrent batch professor fetches |
| Caching | File-based JSON cache with TTL (no database required) |
| Search | `streamlit-searchbox` for school autocomplete |

---

## How it works

1. **School search** — queries the RateMyProfessors GraphQL endpoint for matching schools and returns `legacyId` + display name
2. **Professor sweep** — fetches all professor IDs for a school by scanning the search index across all letters (A–Z + blank), then resolves each ID in parallel batches of 20
3. **Course filtering** — prefix-based matching: `CSCI` matches `CSCI101` (next char is a digit) but `CS` does not match `CSCI101` (next char is a letter)
4. **Review snippets** — fetches up to 3 recent reviews per professor using the ratings GraphQL query, with optional course-code filter
5. **Recency detection** — parses review dates (`"Jan 2024"`) from the snippet batch to annotate how recently each professor was reviewed for the course, adding zero extra API calls

---

## Setup

```bash
git clone https://github.com/ibrahimaasim77/ProfPick.git
cd ProfPick
pip install -r requirements.txt
streamlit run app.py
```

Requires Python 3.11+. No API keys or accounts needed.

---

## Project structure

```
ProfPick/
├── app.py              # Streamlit UI — search panel, podium, professor cards
├── rmp_data.py         # Synchronous orchestration layer — filtering, sorting, recency
├── backend/
│   ├── rmp.py          # Async RateMyProfessors GraphQL client
│   └── cache.py        # File-based JSON cache with TTL
└── requirements.txt
```

---

## Features in detail

### Podium view
The top 3 professors are displayed in a medal podium with animated entry, rating scores, and a one-line review summary derived from keyword extraction across their loaded snippets.

### Smart course matching
Filtering by `CSCI` will match professors who have reviews for `CSCI101`, `CSCI111`, `CSCI180`, etc. — but not `CS31` or `CSCM`. Filtering by `CSCI111` only matches that exact code.

### Caching
All school searches, professor lists, and review snippets are cached locally with a TTL so repeat queries are instant and the app doesn't hammer the RMP API.

### Auto-reload on filter change
Once a school is loaded, changing the course code filter (via the multiselect or text input) automatically re-filters and re-renders the results without requiring a button click.
