# Smart Resume Analyzer with AI-Based Feedback

A production-quality prototype college AI capstone project that analyzes resumes against target job roles, providing resume scores, ATS compatibility metrics, keyword breakdown, and actionable improvement recommendations.

## Features
- **Resume Upload**: Supports PDF (`pdfplumber` / `pypdf`) and DOCX (`python-docx`) up to 16MB.
- **Role Selection**: Configurable job role requirements loaded dynamically from backend JSON configs (`data/roles.json`).
- **Explainable Scoring**: Deterministic rule-based scoring engine evaluating skill matching, section presence, word counts, and formatting rules.
- **ATS Compatibility Check**: Skill gap analysis comparing target role skills with extracted resume keywords.
- **Smart Feedback Engine**: 20-rule catalog (`data/suggestions.json`) that generates prioritized, actionable suggestions based on score breakdowns, missing sections, and contact gaps — no LLMs, fully deterministic.
- **Interactive Dashboard**: Modern responsive UI with Chart.js visualization, score gauges, skill badges, and prioritized feedback suggestions.

## Tech Stack
- **Backend**: Python 3.11+, Flask 3.x, SQLAlchemy, SQLite
- **NLP & Parsing**: spaCy (`en_core_web_sm`), NLTK, `pdfplumber`, `python-docx`
- **Frontend**: HTML5, Vanilla JavaScript, Tailwind CSS (CDN), Chart.js
- **Testing**: `pytest` (98 tests, 100% pass rate)

## Quick Start

### 1. Environment Setup
```bash
python -m venv .venv
# On Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# On macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Run Application
```bash
python wsgi.py
```
Access the application at `http://127.0.0.1:5000`.

### 3. Run Tests
```bash
pytest
```

## API Endpoints

### Infrastructure
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health status and service version |
| `GET` | `/api/roles` | List all supported target job roles |

### Resume Management
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/upload` | Upload a PDF or DOCX resume; returns parsed sections and contacts |
| `GET` | `/api/resumes/<id>` | Retrieve a parsed resume by ID |

### Scoring & ATS
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/score` | Score a resume out of 100 with category breakdown |
| `POST` | `/api/ats` | ATS keyword match against a `role_id` or custom `job_description` |

### Unified Analysis (Module 4)
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/analyze` | Full pipeline: scoring + ATS + prioritized suggestions; persisted to DB |
| `GET` | `/api/analysis/<id>` | Retrieve a previously saved analysis by ID (404 if unknown) |
| `GET` | `/api/history` | Paginated list of recent analyses (`?page=1&per_page=10`, max 50) |

### `POST /api/analyze` — Request / Response

**Request body** (JSON):
```json
{"resume_id": 1, "role_id": "software_engineer"}
// OR
{"resume_id": 1, "job_description": "We need a Python developer with..."}
```

**Response** (201):
```json
{
  "analysis_id": 1,
  "resume_id": 1,
  "role": "software_engineer",
  "resume_score": 72,
  "breakdown": {"structure": {}, "skills": {}, "...": "..."},
  "ats_score": 65,
  "ats_details": {"target_title": "...", "category_scores": {}, "deductions": []},
  "matched_skills": [],
  "missing_critical_skills": ["docker", "algorithms"],
  "missing_nice_to_have_skills": ["aws"],
  "keyword_match_percentage": 57.1,
  "suggestions": [
    {
      "id": "add_missing_critical_skills",
      "category": "Skills",
      "priority": "high",
      "message": "...",
      "how_to_fix": "...",
      "example": "..."
    }
  ],
  "created_at": "2026-10-03T13:00:00+00:00"
}
```

### Error Format
All errors follow a consistent structure:
```json
{"error": {"code": "NOT_FOUND", "message": "Analysis with ID 99 not found."}}
```

## Feedback Engine (`app/services/feedback.py`)

The engine evaluates 20 declarative rules from `data/suggestions.json` against computed scoring and ATS outputs:

- **Condition types**: `section_missing`, `section_present`, `no_contact_field`, `score_below`, `score_at_least`, `ats_score_at_least`, `word_count_below`, `word_count_above`, `action_verb_count_below`, `pronoun_count_above`, `bullet_count_below`, `no_quantified_metrics`, `ats_deduction_contains`, `compound_and`, `compound_or`.
- **Output**: sorted by priority (`high → medium → low`), de-duplicated by rule id, capped at 12 actionable suggestions.
- **Positive note**: `positive_strong_profile` fires when `resume_score >= 75` and `ats_score >= 70`; always appended last, never counted toward the cap.
- **Adding new rules**: edit `data/suggestions.json` only — zero code changes required.

## Project Structure
```
Capstone/
├── app/
│   ├── __init__.py         # App factory & error handlers
│   ├── config.py           # Application configuration
│   ├── models.py           # SQLAlchemy models (Resume, Analysis)
│   ├── routes/
│   │   ├── api.py          # All API blueprints (upload, score, ats, analyze, history)
│   │   └── main.py         # Page routes
│   └── services/
│       ├── parser.py       # PDF/DOCX parsing & section detection
│       ├── scoring.py      # Deterministic resume scoring engine
│       ├── ats.py          # ATS keyword matching & compatibility score
│       └── feedback.py     # Smart feedback engine (Module 4)
├── data/                   # Zero-code-change config files
│   ├── roles.json          # Job role skill requirements & aliases
│   ├── scoring_config.json # Scoring weights & rules
│   ├── ats_config.json     # ATS scoring category weights
│   ├── sections.json       # Section heading patterns
│   ├── skills.json         # Master technical skills dictionary
│   └── suggestions.json    # 20-rule feedback catalog
├── tests/
│   ├── conftest.py
│   ├── test_health.py
│   ├── test_upload.py
│   ├── test_scoring.py
│   ├── test_ats.py
│   ├── test_feedback.py    # Feedback engine unit tests (Module 4)
│   └── test_analyze.py     # Analyze endpoint integration tests (Module 4)
├── static/                 # Frontend JS & CSS assets
├── templates/              # HTML templates (index.html, dashboard.html)
├── wsgi.py                 # Application entry point
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```
