# Smart Resume Analyzer with AI-Based Feedback

A production-quality prototype college AI capstone project that analyzes resumes against target job roles, providing resume scores, ATS compatibility metrics, keyword breakdown, and actionable improvement recommendations.

## Features
- **Resume Upload**: Supports PDF (`pdfplumber` / `pypdf`) and DOCX (`python-docx`) up to 16MB.
- **Role Selection**: Configurable job role requirements loaded dynamically from backend JSON configs (`data/roles.json`).
- **Explainable Scoring**: Deterministic rule-based scoring engine evaluating skill matching, section presence, word counts, and formatting rules.
- **ATS Compatibility Check**: Skill gap analysis comparing target role skills with extracted resume keywords.
- **Interactive Dashboard**: Modern responsive UI with Chart.js visualization, score gauges, skill badges, and prioritized feedback suggestions.

## Tech Stack
- **Backend**: Python 3.11+, Flask 3.x, SQLAlchemy, SQLite
- **NLP & Parsing**: spaCy (`en_core_web_sm`), NLTK, `pdfplumber`, `python-docx`
- **Frontend**: HTML5, Vanilla JavaScript, Tailwind CSS (CDN), Chart.js
- **Testing**: `pytest`

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
- `GET /health` - Health status and service information
- `GET /api/roles` - Retrieve supported target job roles list
- `POST /api/analyze` - Submit resume for AI parsing and scoring analysis
- `GET /` - Resume Upload & Role Selection Landing Page
- `GET /dashboard` - Interactive Analytics Dashboard

## Project Structure
```
Capstone/
├── app/
│   ├── __init__.py         # App factory & error handlers
│   ├── config.py           # Application configuration
│   ├── models.py           # SQLAlchemy database models
│   ├── routes/             # Blueprint routes (pages & API)
│   └── services/           # Parsing, scoring, and feedback logic
├── data/                   # Dynamic JSON configs (roles, scoring, suggestions)
│   ├── roles.json
│   ├── scoring_config.json
│   └── suggestions.json
├── static/                 # Frontend JS & CSS assets
├── templates/              # HTML templates (index.html, dashboard.html)
├── tests/                  # Pytest test suite & fixtures
├── wsgi.py                 # Application entry point
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```
