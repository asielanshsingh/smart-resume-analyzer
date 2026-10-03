import json
import pytest
from uuid import uuid4
from pathlib import Path
from app.models import db, Resume
from app.services.ats import (
    get_spacy_nlp,
    build_skill_regex,
    match_skills_in_text,
    analyze_ats_compatibility
)

def test_spacy_lazy_singleton():
    """Verify spaCy NLP model is loaded once per process as a lazy singleton."""
    nlp1 = get_spacy_nlp()
    nlp2 = get_spacy_nlp()
    assert nlp1 is nlp2, "get_spacy_nlp should return the exact same instance"


def test_punctuation_and_lookaround_boundaries():
    """Test regex lookarounds for C++, C#, .NET, Node.js, CI/CD, and short tokens like C, R, AI."""
    # Special character skills matching
    cpp_regex = build_skill_regex("C++")
    assert cpp_regex.search("Proficient in C++ and Python") is not None
    assert cpp_regex.search("C++ Developer") is not None

    csharp_regex = build_skill_regex("C#")
    assert csharp_regex.search("Experienced in C# .NET") is not None

    dotnet_regex = build_skill_regex(".NET")
    assert dotnet_regex.search("Worked with .NET Core") is not None

    nodejs_regex = build_skill_regex("Node.js")
    assert nodejs_regex.search("Built backend with Node.js and Express") is not None

    cicd_regex = build_skill_regex("CI/CD")
    assert cicd_regex.search("Configured CI/CD pipelines") is not None

    # Short token boundary tests (Ensure 'C', 'R', 'AI' do not falsely match inside words)
    c_regex = build_skill_regex("C")
    assert c_regex.search("Enrolled in Course 101") is None
    assert c_regex.search("Drove a Car to work") is None
    assert c_regex.search("Languages: C, Python, Java") is not None

    r_regex = build_skill_regex("R")
    assert r_regex.search("React Developer") is None
    assert r_regex.search("Server administration") is None
    assert r_regex.search("Data Analysis with R and Python") is not None

    ai_regex = build_skill_regex("AI")
    assert ai_regex.search("Send email to support") is None
    assert ai_regex.search("Main Mail server") is None
    assert ai_regex.search("Applied AI Engineer") is not None


def test_alias_matching_and_sections():
    """Verify alias resolution (JS -> javascript, K8s -> kubernetes) and section location tracking."""
    raw_text = "Experience: Built backend with NodeJS and K8s. Skills: JS, postgres, sklearn."
    sections = {
        "experience": "Built backend with NodeJS and K8s.",
        "skills": "JS, postgres, sklearn."
    }

    # Match JS for javascript
    matched, term, secs = match_skills_in_text("javascript", ["js"], raw_text, sections)
    assert matched is True
    assert term == "js"
    assert "skills" in secs

    # Match K8s for kubernetes
    matched, term, secs = match_skills_in_text("kubernetes", ["k8s"], raw_text, sections)
    assert matched is True
    assert term == "k8s"
    assert "experience" in secs


def test_critical_vs_nice_to_have_split():
    """Verify matching engine splits missing skills into critical vs nice-to-have."""
    parsed_resume = {
        "extracted_text": "Experienced Software Engineer skilled in Python, SQL, and Git.",
        "sections_json": {
            "skills": "Python, SQL, Git",
            "experience": "Software Engineer developing REST API."
        },
        "contacts_json": {"email": "test@example.com", "phone": "1234567890"},
        "word_count": 400
    }
    role_config = {
        "title": "Software Engineer",
        "required_skills": ["python", "javascript", "sql"],  # missing javascript (critical)
        "preferred_skills": ["docker", "flask"],             # missing docker, flask (nice-to-have)
        "skill_aliases": {"javascript": ["js"]}
    }

    result = analyze_ats_compatibility(parsed_resume, role_config=role_config)
    
    assert "javascript" in result["missing_critical_skills"]
    assert "python" not in result["missing_critical_skills"]
    assert "docker" in result["missing_nice_to_have_skills"]
    assert "flask" in result["missing_nice_to_have_skills"]
    assert len(result["matched_skills"]) == 2  # python, sql


def test_ats_score_deductions_with_reasons(app):
    """Verify ATS score deductions generate clear explanatory reason strings."""
    parsed_resume = {
        "extracted_text": "Short resume without contacts.",
        "sections_json": {"skills": "Python"},
        "contacts_json": {},  # missing email & phone
        "word_count": 50,     # too short
        "warnings_json": ["Table formatting detected"]
    }
    role_config = {
        "title": "Data Scientist",
        "required_skills": ["python", "sql", "pandas"],
        "preferred_skills": ["r"]
    }

    result = analyze_ats_compatibility(
        parsed_resume,
        role_config=role_config,
        ats_config_file=app.config["ATS_CONFIG_FILE"]
    )

    assert result["ats_score"] < 100
    assert len(result["deductions"]) > 0
    # Check that reasons mention missing items
    reasons_str = " ".join(result["deductions"])
    assert "email" in reasons_str.lower() or "phone" in reasons_str.lower()
    assert "section" in reasons_str.lower() or "length" in reasons_str.lower() or "risk" in reasons_str.lower()


def test_api_ats_unknown_resume_id(client):
    """POST /api/ats returns 404 for unknown resume_id."""
    res = client.post("/api/ats", json={"resume_id": 99999, "role_id": "software_engineer"})
    assert res.status_code == 404
    data = res.get_json()
    assert data["error"]["code"] == "NOT_FOUND"


def test_api_ats_both_inputs_sent(client, app):
    """POST /api/ats returns 400 if both role_id and job_description are provided."""
    with app.app_context():
        r = Resume(filename="test.pdf", file_hash=f"hash_{uuid4().hex}", extracted_text="Python SQL developer with 5 years experience.", word_count=350)
        db.session.add(r)
        db.session.commit()
        resume_id = r.id

    res = client.post("/api/ats", json={
        "resume_id": resume_id,
        "role_id": "software_engineer",
        "job_description": "We are looking for a Python developer..."
    })
    assert res.status_code == 400
    data = res.get_json()
    assert data["error"]["code"] == "BAD_REQUEST"
    assert "not both" in data["error"]["message"].lower()


def test_api_ats_invalid_role_id(client, app):
    """POST /api/ats returns 400 with valid roles list for invalid role_id."""
    with app.app_context():
        r = Resume(filename="test.pdf", file_hash=f"hash_{uuid4().hex}", extracted_text="Python SQL developer with 5 years experience.", word_count=350)
        db.session.add(r)
        db.session.commit()
        resume_id = r.id

    res = client.post("/api/ats", json={
        "resume_id": resume_id,
        "role_id": "quantum_blockchain_architect"
    })
    assert res.status_code == 400
    data = res.get_json()
    assert data["error"]["code"] == "INVALID_ROLE"
    assert "software_engineer" in data["error"]["message"]


def test_api_ats_custom_job_description_path(client, app):
    """POST /api/ats handles custom job description keyword extraction and scoring."""
    with app.app_context():
        r = Resume(filename="test.pdf", file_hash=f"hash_{uuid4().hex}", extracted_text="Experienced in Docker, Kubernetes, AWS, and Linux administration.", word_count=400)
        db.session.add(r)
        db.session.commit()
        resume_id = r.id

    jd_text = "We are seeking a Cloud Infrastructure Specialist proficient in Docker, Kubernetes, and AWS."
    res = client.post("/api/ats", json={
        "resume_id": resume_id,
        "job_description": jd_text
    })
    assert res.status_code == 200
    data = res.get_json()
    eval_res = data["ats_evaluation"]
    assert eval_res["target_title"] == "Custom Job Description"
    assert eval_res["matched_skills_count"] > 0


def test_api_ats_zero_match_resume(client, app):
    """POST /api/ats handles resume with zero matching keywords safely without division by zero."""
    with app.app_context():
        r = Resume(filename="test.pdf", file_hash=f"hash_{uuid4().hex}", extracted_text="Accountant specializing in taxation, auditing, payroll, and bookkeeping.", word_count=350)
        db.session.add(r)
        db.session.commit()
        resume_id = r.id

    res = client.post("/api/ats", json={
        "resume_id": resume_id,
        "role_id": "software_engineer"
    })
    assert res.status_code == 200
    data = res.get_json()
    eval_res = data["ats_evaluation"]
    assert eval_res["keyword_match_percentage"] == 0.0
    assert eval_res["matched_skills_count"] == 0


def test_dynamic_role_addition_at_runtime(client, app, tmp_path):
    """Verify adding a new role to roles.json at runtime works without code modifications."""
    roles_file = Path(app.config["ROLES_FILE"])
    with open(roles_file, "r", encoding="utf-8") as f:
        roles_data = json.load(f)

    # Backup original roles
    original_roles = list(roles_data["roles"])
    
    try:
        new_role = {
            "id": "cybersecurity_analyst",
            "title": "Cybersecurity Analyst",
            "category": "Security",
            "required_skills": ["python", "linux", "networking", "siem"],
            "preferred_skills": ["wireshark", "metasploit"],
            "skill_aliases": {},
            "expected_sections": ["experience", "education", "skills"]
        }
        roles_data["roles"].append(new_role)
        with open(roles_file, "w", encoding="utf-8") as f:
            json.dump(roles_data, f, indent=2)

        with app.app_context():
            r = Resume(filename="sec.pdf", file_hash=f"hash_{uuid4().hex}", extracted_text="Cybersecurity expert skilled in Python, Linux, and Networking.", word_count=400)
            db.session.add(r)
            db.session.commit()
            resume_id = r.id

        res = client.post("/api/ats", json={
            "resume_id": resume_id,
            "role_id": "cybersecurity_analyst"
        })
        assert res.status_code == 200
        data = res.get_json()
        assert data["ats_evaluation"]["target_title"] == "Cybersecurity Analyst"
    finally:
        # Restore original roles.json
        roles_data["roles"] = original_roles
        with open(roles_file, "w", encoding="utf-8") as f:
            json.dump(roles_data, f, indent=2)
