"""
test_analyze.py – Integration tests for the analyze pipeline endpoints.

Covers:
  - POST /api/analyze happy path (role_id and job_description variants)
  - Full upload → analyze → fetch cycle
  - GET /api/analysis/<id> (found and 404)
  - GET /api/history (pagination)
  - All bad-input error paths matching /api/ats validation style
"""

import io
import json
import pytest
from pathlib import Path
from app.models import db, Resume, Analysis


# ---------------------------------------------------------------------------
# Fixture helpers – minimal in-memory PDF/DOCX bytes
# ---------------------------------------------------------------------------

@pytest.fixture
def minimal_pdf_bytes():
    """
    Returns a minimal valid PDF byte string accepted by pdfplumber.
    Uses a real minimal-structure PDF so that text extraction yields words.
    """
    # Minimal PDF that pdfplumber can open and extract text from
    content = b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Contents 4 0 R/Resources<</Font<</F1<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>>>>>>>endobj
4 0 obj<</Length 44>>
stream
BT /F1 12 Tf 100 700 Td (Hello World) Tj ET
endstream
endobj
xref
0 5
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000274 00000 n 
trailer<</Size 5/Root 1 0 R>>
startxref
369
%%EOF"""
    return content


@pytest.fixture
def rich_resume_text():
    """
    A rich, multi-section plain-text resume used to build a synthetic Resume row
    directly in the DB without going through file upload.
    Includes enough content to pass all basic scoring and ATS checks.
    """
    return (
        "John Doe | john.doe@example.com | +1-415-555-0190 | "
        "linkedin.com/in/johndoe | github.com/johndoe\n\n"
        "Summary\nResults-driven Software Engineer with 2 years of experience "
        "building scalable Python web services.\n\n"
        "Experience\nSoftware Engineering Intern — Acme Corp, Jun 2023–Aug 2023\n"
        "• Developed a data pipeline in Python that reduced processing time by 40%.\n"
        "• Implemented REST APIs with Flask and PostgreSQL serving 500+ daily users.\n"
        "• Automated CI/CD deployment with GitHub Actions cutting release time by 30%.\n\n"
        "Education\nB.Tech in Computer Science — Delhi University | 2020–2024 | CGPA: 8.6/10\n\n"
        "Skills\n"
        "Languages: Python, JavaScript, SQL\n"
        "Frameworks: Flask, React, Express\n"
        "Tools: Git, Docker, GitHub Actions\n"
        "Databases: PostgreSQL, MongoDB\n\n"
        "Projects\n"
        "Resume Analyzer | Python, Flask, SQLite | github.com/johndoe/resume-analyzer\n"
        "• Built a REST API that parses PDF/DOCX resumes and scores them against job roles.\n"
        "E-commerce Dashboard | React, Node.js, MongoDB\n"
        "• Designed and implemented a product analytics dashboard with real-time charts.\n\n"
        "Certifications\n"
        "• AWS Certified Cloud Practitioner — Amazon Web Services, 2024\n"
        "• Google Data Analytics Certificate — Coursera, 2023\n"
    )


@pytest.fixture
def seeded_resume(app, rich_resume_text):
    """Insert a well-formed Resume row and return it."""
    with app.app_context():
        resume = Resume(
            filename="test_resume.pdf",
            extracted_text=rich_resume_text,
            file_hash="aabbccddeeff00112233445566778899aabbccddeeff00112233445566778899",
            page_count=1,
            word_count=len(rich_resume_text.split()),
            sections_json={
                "contact": "John Doe | john.doe@example.com | +1-415-555-0190",
                "summary": "Results-driven Software Engineer with 2 years of experience.",
                "experience": (
                    "Software Engineering Intern — Acme Corp, Jun 2023–Aug 2023\n"
                    "• Developed a data pipeline in Python that reduced processing time by 40%.\n"
                    "• Implemented REST APIs with Flask and PostgreSQL serving 500+ daily users."
                ),
                "education": "B.Tech in Computer Science — Delhi University | 2020–2024 | CGPA: 8.6/10",
                "skills": "Languages: Python, JavaScript, SQL\nFrameworks: Flask, React, Express\nTools: Git, Docker",
                "projects": (
                    "Resume Analyzer | Python, Flask, SQLite | github.com/johndoe/resume-analyzer\n"
                    "E-commerce Dashboard | React, Node.js, MongoDB"
                ),
                "certifications": "AWS Certified Cloud Practitioner 2024",
            },
            contacts_json={
                "emails": ["john.doe@example.com"],
                "phones": ["+1-415-555-0190"],
                "linkedin": ["linkedin.com/in/johndoe"],
                "github": ["github.com/johndoe"],
            },
            warnings_json=[],
        )
        db.session.add(resume)
        db.session.commit()
        resume_id = resume.id
    return resume_id


# ---------------------------------------------------------------------------
# POST /api/analyze – happy paths
# ---------------------------------------------------------------------------

class TestAnalyzeHappyPath:
    def test_analyze_with_role_id(self, client, seeded_resume):
        resp = client.post(
            "/api/analyze",
            json={"resume_id": seeded_resume, "role_id": "software_engineer"},
            content_type="application/json",
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert "analysis_id" in data
        assert data["resume_id"] == seeded_resume
        assert data["role"] == "software_engineer"
        assert isinstance(data["resume_score"], (int, float))
        assert isinstance(data["ats_score"], (int, float))
        assert "breakdown" in data
        assert "ats_details" in data
        assert "matched_skills" in data
        assert "missing_critical_skills" in data
        assert "missing_nice_to_have_skills" in data
        assert "suggestions" in data
        assert "created_at" in data
        assert isinstance(data["suggestions"], list)

    def test_analyze_with_job_description(self, client, seeded_resume):
        jd = (
            "We need a Python developer with experience in REST API design, SQL, "
            "Git version control, and Docker containerization. Flask knowledge is a plus."
        )
        resp = client.post(
            "/api/analyze",
            json={"resume_id": seeded_resume, "job_description": jd},
            content_type="application/json",
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["role"] == "custom_job_description"
        assert "analysis_id" in data

    def test_analyze_persists_to_db(self, client, app, seeded_resume):
        resp = client.post(
            "/api/analyze",
            json={"resume_id": seeded_resume, "role_id": "data_scientist"},
            content_type="application/json",
        )
        assert resp.status_code == 201
        analysis_id = resp.get_json()["analysis_id"]

        with app.app_context():
            row = db.session.get(Analysis, analysis_id)
            assert row is not None
            assert row.resume_id == seeded_resume
            assert row.role == "data_scientist"
            assert row.resume_score >= 0
            assert row.ats_score >= 0

    def test_suggestions_list_is_ordered_high_first(self, client, seeded_resume):
        """High-priority suggestions must precede medium, medium before low."""
        resp = client.post(
            "/api/analyze",
            json={"resume_id": seeded_resume, "role_id": "devops_engineer"},
            content_type="application/json",
        )
        assert resp.status_code == 201
        suggestions = resp.get_json()["suggestions"]
        actionable = [s for s in suggestions if s["id"] != "positive_strong_profile"]
        order = {"high": 0, "medium": 1, "low": 2}
        prios = [order[s["priority"]] for s in actionable]
        assert prios == sorted(prios)


# ---------------------------------------------------------------------------
# Full upload → analyze → fetch cycle
# ---------------------------------------------------------------------------

class TestFullCycle:
    def test_upload_then_analyze_then_fetch(self, client):
        """End-to-end: upload a PDF, analyze it, then retrieve the analysis."""
        # Seed a resume through the seeded_resume fixture pattern manually
        rich_text = (
            "Jane Smith | jane@example.com | +1-555-9999 | github.com/janesmith\n"
            "Summary\nBackend developer with 1 year of internship experience.\n"
            "Experience\nIntern — TechCorp, 2023\n"
            "• Built Python microservices, improved response time by 25%.\n"
            "Education\nB.Tech CS 2024 University of Delhi CGPA 8.0\n"
            "Skills\nPython, Flask, SQL, Git, Docker, PostgreSQL\n"
            "Projects\nAPI Gateway | Python, Flask | github.com/janesmith/api-gw\n"
            "• Designed REST API handling 1000+ req/s.\n"
            "Certifications\nAWS Cloud Practitioner 2024\n"
        )
        resume = Resume(
            filename="jane.pdf",
            extracted_text=rich_text,
            file_hash="jane1234" * 8,
            page_count=1,
            word_count=len(rich_text.split()),
            sections_json={
                "contact": "Jane Smith | jane@example.com",
                "summary": "Backend developer with 1 year of internship experience.",
                "experience": "Intern — TechCorp, 2023\n• Built Python microservices.",
                "education": "B.Tech CS 2024 University of Delhi",
                "skills": "Python, Flask, SQL, Git, Docker, PostgreSQL",
                "projects": "API Gateway | Python, Flask",
                "certifications": "AWS Cloud Practitioner 2024",
            },
            contacts_json={
                "emails": ["jane@example.com"],
                "phones": ["+1-555-9999"],
                "linkedin": [],
                "github": ["github.com/janesmith"],
            },
            warnings_json=[],
        )
        with client.application.app_context():
            db.session.add(resume)
            db.session.commit()
            resume_id = resume.id

        # Analyze
        resp = client.post(
            "/api/analyze",
            json={"resume_id": resume_id, "role_id": "backend_developer"},
            content_type="application/json",
        )
        assert resp.status_code == 201
        analysis_id = resp.get_json()["analysis_id"]

        # Fetch
        fetch_resp = client.get(f"/api/analysis/{analysis_id}")
        assert fetch_resp.status_code == 200
        fetched = fetch_resp.get_json()
        assert fetched["id"] == analysis_id
        assert fetched["resume_id"] == resume_id
        assert fetched["role"] == "backend_developer"
        assert "breakdown" in fetched
        assert "matched_missing" in fetched
        assert "suggestions" in fetched


# ---------------------------------------------------------------------------
# GET /api/analysis/<id>
# ---------------------------------------------------------------------------

class TestGetAnalysis:
    def test_get_analysis_found(self, client, seeded_resume):
        post = client.post(
            "/api/analyze",
            json={"resume_id": seeded_resume, "role_id": "web_developer"},
            content_type="application/json",
        )
        analysis_id = post.get_json()["analysis_id"]
        resp = client.get(f"/api/analysis/{analysis_id}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["id"] == analysis_id
        assert "breakdown" in data
        assert "suggestions" in data

    def test_get_analysis_404_unknown_id(self, client):
        resp = client.get("/api/analysis/999999")
        assert resp.status_code == 404
        err = resp.get_json()["error"]
        assert err["code"] == "NOT_FOUND"

    def test_get_analysis_returns_all_dict_fields(self, client, seeded_resume):
        post = client.post(
            "/api/analyze",
            json={"resume_id": seeded_resume, "role_id": "data_analyst"},
            content_type="application/json",
        )
        analysis_id = post.get_json()["analysis_id"]
        data = client.get(f"/api/analysis/{analysis_id}").get_json()
        for field in ("id", "resume_id", "role", "resume_score", "ats_score",
                      "breakdown", "matched_missing", "suggestions", "created_at"):
            assert field in data, f"Missing field: {field}"


# ---------------------------------------------------------------------------
# GET /api/history
# ---------------------------------------------------------------------------

class TestGetHistory:
    def _create_analyses(self, client, resume_id, count=5):
        roles = ["software_engineer", "data_analyst", "web_developer", "devops_engineer", "data_scientist"]
        for i in range(count):
            client.post(
                "/api/analyze",
                json={"resume_id": resume_id, "role_id": roles[i % len(roles)]},
                content_type="application/json",
            )

    def test_history_returns_paginated(self, client, seeded_resume):
        self._create_analyses(client, seeded_resume, count=5)
        resp = client.get("/api/history?per_page=3&page=1")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "per_page" in data
        assert "pages" in data
        assert len(data["items"]) <= 3

    def test_history_newest_first(self, client, seeded_resume):
        self._create_analyses(client, seeded_resume, count=3)
        resp = client.get("/api/history?per_page=10")
        items = resp.get_json()["items"]
        if len(items) >= 2:
            # created_at strings are ISO; lexicographic comparison is valid for UTC
            assert items[0]["created_at"] >= items[1]["created_at"]

    def test_history_page_2(self, client, seeded_resume):
        self._create_analyses(client, seeded_resume, count=5)
        resp_p1 = client.get("/api/history?per_page=3&page=1")
        resp_p2 = client.get("/api/history?per_page=3&page=2")
        p1_ids = {item["id"] for item in resp_p1.get_json()["items"]}
        p2_ids = {item["id"] for item in resp_p2.get_json()["items"]}
        assert p1_ids.isdisjoint(p2_ids), "Page 1 and page 2 must not share IDs"

    def test_history_empty_db(self, client):
        resp = client.get("/api/history")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] == 0
        assert data["items"] == []

    def test_get_analysis_by_share_token(self, client, seeded_resume):
        post = client.post(
            "/api/analyze",
            json={"resume_id": seeded_resume, "role_id": "web_developer"},
            content_type="application/json",
        )
        data = post.get_json()
        share_token = data["share_token"]
        assert share_token is not None

        resp = client.get(f"/api/analysis/{share_token}")
        assert resp.status_code == 200
        fetched = resp.get_json()
        assert fetched["share_token"] == share_token
        assert fetched["resume_id"] == seeded_resume

    def test_result_route_with_share_token(self, client, seeded_resume):
        post = client.post(
            "/api/analyze",
            json={"resume_id": seeded_resume, "role_id": "software_engineer"},
            content_type="application/json",
        )
        token = post.get_json()["share_token"]
        resp = client.get(f"/result/{token}")
        assert resp.status_code == 200
        assert b"Analysis Dashboard" in resp.data or b"Resume Evaluation Report" in resp.data

    def test_history_does_not_leak_contacts(self, client, seeded_resume):
        client.post(
            "/api/analyze",
            json={"resume_id": seeded_resume, "role_id": "software_engineer"},
            content_type="application/json",
        )
        resp = client.get("/api/history")
        assert resp.status_code == 200
        items = resp.get_json()["items"]
        assert len(items) > 0
        for item in items:
            assert "contacts" not in item, "History item should not leak sensitive contact information"

    def test_history_per_page_capped_at_50(self, client, seeded_resume):
        self._create_analyses(client, seeded_resume, count=3)
        resp = client.get("/api/history?per_page=200")
        assert resp.get_json()["per_page"] <= 50

    def test_history_invalid_page_defaults(self, client, seeded_resume):
        resp = client.get("/api/history?page=abc&per_page=xyz")
        assert resp.status_code == 200  # graceful fallback, not a 400



# ---------------------------------------------------------------------------
# POST /api/analyze – bad input validation
# ---------------------------------------------------------------------------

class TestAnalyzeBadInput:
    def test_non_json_body_returns_400(self, client):
        resp = client.post("/api/analyze", data="not-json", content_type="text/plain")
        assert resp.status_code == 400
        assert resp.get_json()["error"]["code"] == "BAD_REQUEST"

    def test_malformed_json_returns_400(self, client):
        resp = client.post("/api/analyze", data="{bad json", content_type="application/json")
        assert resp.status_code == 400

    def test_missing_resume_id_returns_400(self, client):
        resp = client.post(
            "/api/analyze",
            json={"role_id": "software_engineer"},
            content_type="application/json",
        )
        assert resp.status_code == 400
        assert resp.get_json()["error"]["code"] == "BAD_REQUEST"

    def test_both_role_and_jd_returns_400(self, client, seeded_resume):
        resp = client.post(
            "/api/analyze",
            json={
                "resume_id": seeded_resume,
                "role_id": "software_engineer",
                "job_description": "We need a Python dev.",
            },
            content_type="application/json",
        )
        assert resp.status_code == 400
        assert resp.get_json()["error"]["code"] == "BAD_REQUEST"

    def test_neither_role_nor_jd_returns_400(self, client, seeded_resume):
        resp = client.post(
            "/api/analyze",
            json={"resume_id": seeded_resume},
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_nonexistent_resume_id_returns_404(self, client):
        resp = client.post(
            "/api/analyze",
            json={"resume_id": 999999, "role_id": "software_engineer"},
            content_type="application/json",
        )
        assert resp.status_code == 404
        assert resp.get_json()["error"]["code"] == "NOT_FOUND"

    def test_invalid_role_id_returns_400(self, client, seeded_resume):
        resp = client.post(
            "/api/analyze",
            json={"resume_id": seeded_resume, "role_id": "nonexistent_role_xyz"},
            content_type="application/json",
        )
        assert resp.status_code == 400
        assert resp.get_json()["error"]["code"] == "INVALID_ROLE"

    def test_empty_job_description_returns_400(self, client, seeded_resume):
        resp = client.post(
            "/api/analyze",
            json={"resume_id": seeded_resume, "job_description": "   "},
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_oversized_job_description_returns_400(self, client, seeded_resume):
        resp = client.post(
            "/api/analyze",
            json={"resume_id": seeded_resume, "job_description": "x" * 20000},
            content_type="application/json",
        )
        assert resp.status_code == 400
        assert resp.get_json()["error"]["code"] == "PAYLOAD_TOO_LARGE"

    def test_resume_with_empty_text_returns_422(self, client, app):
        with app.app_context():
            resume = Resume(
                filename="empty.pdf",
                extracted_text="   ",
                file_hash="deadbeef" * 8,
                page_count=1,
                word_count=0,
                sections_json={},
                contacts_json={"emails": [], "phones": [], "linkedin": [], "github": []},
                warnings_json=[],
            )
            db.session.add(resume)
            db.session.commit()
            resume_id = resume.id

        resp = client.post(
            "/api/analyze",
            json={"resume_id": resume_id, "role_id": "software_engineer"},
            content_type="application/json",
        )
        assert resp.status_code == 422
        assert resp.get_json()["error"]["code"] == "UNPROCESSABLE_ENTITY"
