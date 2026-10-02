---
trigger: always_on
---

You are building a complete, production-quality prototype called "Smart Resume Analyzer with AI-Based Feedback". It is a college AI capstone, graded on: Functionality 30%, AI Logic 20%, UI/UX 15%, Code Quality 15%, Deployment 10%, Documentation/Presentation 10%.

WHAT IT MUST DO
Users upload a resume (PDF or DOCX), pick a target job role, and get: a resume score out of 100, a separate ATS compatibility score, matched and missing keywords/skills for the role, prioritized improvement suggestions, and a dashboard showing all of it.

STACK (fixed)
- Backend: Python 3.11+, Flask
- NLP: spaCy (en_core_web_sm) and NLTK only. Rule-based and keyword logic.
- DB: SQLite via SQLAlchemy
- Frontend: HTML, CSS, Tailwind (CDN is fine), vanilla JS, Chart.js for charts. No React.
- PDF parsing: pdfplumber (fallback pypdf). DOCX parsing: python-docx.

HARD SCOPE LIMITS
No deep learning, no LLM training, no complex recommendation engines, no enterprise auth, no large-scale cloud architecture. Do not call external AI APIs. All analysis is deterministic and explainable.

ENGINEERING RULES
1. Generic solutions only. Never hardcode behavior for a specific sample resume or test case. Logic must work for any resume and any role.
2. Roles, keywords, aliases, scoring weights and suggestion rules live in JSON/config files, not inside functions. Adding a new role must need zero code changes.
3. Clean architecture: app factory, blueprints, and separate modules (parsing, scoring, ats, feedback, storage). Small functions, type hints, docstrings, no dead code.
4. Every endpoint returns consistent JSON errors: {"error": {"code": "...", "message": "..."}} with correct HTTP status codes. No stack traces ever reach the user. Log them server-side.
5. Validate everything on the server (never trust the frontend): file presence, extension, MIME, magic bytes, size, role validity.
6. Secrets and settings come from environment variables with safe defaults. Include .env.example.
7. Write tests with pytest alongside each feature, not at the end.
8. Keep the README current as you go.

Before writing code for each task, produce a short plan, then implement, then run the app and tests yourself and fix failures before reporting done.
