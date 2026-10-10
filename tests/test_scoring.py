
import pytest

from app.services.scoring import analyze_resume_score, safe_clamp_score


@pytest.fixture
def scoring_config_path(app):
    return app.config["SCORING_CONFIG_FILE"]

@pytest.fixture
def perfect_resume_parsed_data():
    return {
        "raw_text": (
            "Jane Doe\n"
            "jane.doe@example.com | +91 9876543210\n"
            "linkedin.com/in/janedoe | github.com/janedoe\n\n"
            "PROFESSIONAL SUMMARY:\n"
            "Results-driven Senior Software Engineer with 6+ years of experience designing and optimizing "
            "scalable cloud microservices, REST APIs, and automated CI/CD pipelines.\n\n"
            "WORK EXPERIENCE:\n"
            "Senior Backend Engineer at TechCorp (2020 - Present)\n"
            "• Developed high-throughput microservices using Python Flask and PostgreSQL, handling 5M daily requests.\n"
            "• Optimized database queries and caching, reducing response latency by 45%.\n"
            "• Spearheaded automated deployment using Docker and Kubernetes.\n\n"
            "EDUCATION:\n"
            "Bachelor of Technology in Computer Science - State University (2016 - 2020), CGPA: 3.9/4.0\n\n"
            "TECHNICAL SKILLS:\n"
            "• Languages: Python, JavaScript, SQL, Go\n"
            "• Frameworks: Flask, Django, FastAPI, Pytest\n"
            "• DevOps & Tools: Docker, Kubernetes, Git, AWS, CI/CD, Redis\n\n"
            "PROJECTS:\n"
            "• Smart Resume Analyzer: Built automated resume scoring system using Python, spaCy, and Flask. github.com/janedoe/resume-analyzer\n"
            "• Microservices Gateway: Architected lightweight API gateway handling rate limiting and authentication.\n\n"
            "CERTIFICATIONS:\n"
            "• AWS Certified Solutions Architect Associate"
        ),
        "word_count": 420,
        "page_count": 1,
        "contacts": {
            "emails": ["jane.doe@example.com"],
            "phones": ["+91 9876543210"],
            "linkedin": ["https://linkedin.com/in/janedoe"],
            "github": ["https://github.com/janedoe"]
        },
        "detected_sections": {
            "contact": "Jane Doe\njane.doe@example.com | +91 9876543210\nlinkedin.com/in/janedoe | github.com/janedoe",
            "summary": "Results-driven Senior Software Engineer with 6+ years of experience designing and optimizing scalable cloud microservices.",
            "experience": "Senior Backend Engineer at TechCorp (2020 - Present)\n• Developed high-throughput microservices using Python Flask and PostgreSQL, handling 5M daily requests.\n• Optimized database queries and caching, reducing response latency by 45%.\n• Spearheaded automated deployment using Docker and Kubernetes.",
            "education": "Bachelor of Technology in Computer Science - State University (2016 - 2020), CGPA: 3.9/4.0",
            "skills": "• Languages: Python, JavaScript, SQL, Go\n• Frameworks: Flask, Django, FastAPI, Pytest\n• DevOps & Tools: Docker, Kubernetes, Git, AWS, CI/CD, Redis",
            "projects": "• Smart Resume Analyzer: Built automated resume scoring system using Python, spaCy, and Flask. github.com/janedoe/resume-analyzer\n• Microservices Gateway: Architected lightweight API gateway handling rate limiting and authentication.",
            "certifications": "• AWS Certified Solutions Architect Associate"
        }
    }


@pytest.fixture
def fresher_resume_parsed_data():
    return {
        "raw_text": (
            "Alex Smith\n"
            "alex.smith@email.com | +91 9123456789 | github.com/alexsmith\n\n"
            "PROFESSIONAL SUMMARY:\n"
            "Enthusiastic Computer Science graduate passionate about backend development and software engineering.\n\n"
            "EDUCATION:\n"
            "Bachelor of Engineering in Information Technology - City College (2020 - 2024), CGPA: 8.8/10\n\n"
            "TECHNICAL SKILLS:\n"
            "• Programming: Python, C++, Java, JavaScript\n"
            "• Web & Databases: Flask, HTML, CSS, SQL, MongoDB, Git\n\n"
            "PROJECTS:\n"
            "• E-Commerce Web App: Developed full-stack online store using Flask, SQLite, and HTML/CSS with shopping cart functionality. github.com/alexsmith/shop\n"
            "• Task Management Tool: Built REST API microservice for task tracking with automated pytest suite.\n\n"
            "CERTIFICATIONS:\n"
            "• Python for Data Science Certificate\n"
            "• Meta Front-End Developer Specialization"
        ),
        "word_count": 310,
        "page_count": 1,
        "contacts": {
            "emails": ["alex.smith@email.com"],
            "phones": ["+91 9123456789"],
            "linkedin": [],
            "github": ["https://github.com/alexsmith"]
        },
        "detected_sections": {
            "contact": "Alex Smith\nalex.smith@email.com | +91 9123456789",
            "summary": "Enthusiastic Computer Science graduate passionate about backend development.",
            "experience": "", # Zero work experience
            "education": "Bachelor of Engineering in Information Technology - City College (2020 - 2024), CGPA: 8.8/10",
            "skills": "• Programming: Python, C++, Java, JavaScript\n• Web & Databases: Flask, HTML, CSS, SQL, MongoDB, Git",
            "projects": "• E-Commerce Web App: Developed full-stack online store using Flask, SQLite, and HTML/CSS with shopping cart functionality. github.com/alexsmith/shop\n• Task Management Tool: Built REST API microservice for task tracking with automated pytest suite.",
            "certifications": "• Python for Data Science Certificate\n• Meta Front-End Developer Specialization"
        }
    }


@pytest.fixture
def weak_resume_parsed_data():
    return {
        "raw_text": "John\nSoftware guy\nLooking for job.",
        "word_count": 6,
        "page_count": 1,
        "contacts": {
            "emails": [],
            "phones": [],
            "linkedin": [],
            "github": []
        },
        "detected_sections": {
            "contact": "John",
            "summary": "Software guy Looking for job.",
            "experience": "",
            "education": "",
            "skills": "",
            "projects": "",
            "certifications": ""
        }
    }


def test_perfect_resume_score(perfect_resume_parsed_data, scoring_config_path):
    """Test that a complete, strong resume receives a high score (near top: >= 80)."""
    result = analyze_resume_score(perfect_resume_parsed_data, scoring_config_path)
    score = result["resume_score"]

    assert isinstance(score, int)
    assert 80 <= score <= 100

    # Verify breakdown structure
    breakdown = result["breakdown"]
    assert "structure" in breakdown
    assert "skills" in breakdown
    assert "education" in breakdown
    assert "projects" in breakdown
    assert "experience" in breakdown
    assert "contact" in breakdown
    assert "completeness" in breakdown

    # Verify all category max scores sum up to 100
    total_max = sum(cat["max_score"] for cat in breakdown.values())
    assert total_max == 100


def test_weak_resume_score(weak_resume_parsed_data, scoring_config_path):
    """Test that an incomplete, minimal resume receives a low score (near bottom: <= 35)."""
    result = analyze_resume_score(weak_resume_parsed_data, scoring_config_path)
    score = result["resume_score"]

    assert isinstance(score, int)
    assert 0 <= score <= 35


def test_fresher_resume_score_not_crushed(fresher_resume_parsed_data, scoring_config_path):
    """Test that a fresher with zero work experience is not crushed due to project/certification substitution."""
    result = analyze_resume_score(fresher_resume_parsed_data, scoring_config_path)
    score = result["resume_score"]

    assert isinstance(score, int)
    assert score >= 65 # Should receive a solid score

    exp_breakdown = result["breakdown"]["experience"]
    # Check that fresher substitution logic was triggered in reasons
    assert any("Fresher evaluation active" in r for r in exp_breakdown["reasons"])
    assert exp_breakdown["score"] > 0


def test_missing_sections_proportional_deduction(perfect_resume_parsed_data, scoring_config_path):
    """Test that removing sections results in proportional score deductions."""
    full_result = analyze_resume_score(perfect_resume_parsed_data, scoring_config_path)

    # Remove skills and projects
    partial_data = dict(perfect_resume_parsed_data)
    partial_data["detected_sections"] = dict(perfect_resume_parsed_data["detected_sections"])
    partial_data["detected_sections"]["skills"] = ""
    partial_data["detected_sections"]["projects"] = ""

    partial_result = analyze_resume_score(partial_data, scoring_config_path)

    assert partial_result["resume_score"] < full_result["resume_score"]
    assert partial_result["breakdown"]["skills"]["score"] < full_result["breakdown"]["skills"]["score"]
    assert partial_result["breakdown"]["projects"]["score"] < full_result["breakdown"]["projects"]["score"]


def test_boundary_values_and_edge_cases(scoring_config_path):
    """Test boundary values: empty dict, missing fields, single word, NaN inputs."""
    empty_data = {}
    res1 = analyze_resume_score(empty_data, scoring_config_path)
    assert isinstance(res1["resume_score"], int)
    assert 0 <= res1["resume_score"] <= 100

    single_word_data = {
        "raw_text": "Developer",
        "word_count": 1,
        "contacts": {},
        "detected_sections": {}
    }
    res2 = analyze_resume_score(single_word_data, scoring_config_path)
    assert isinstance(res2["resume_score"], int)
    assert 0 <= res2["resume_score"] <= 100

    # Safe clamp tests
    assert safe_clamp_score(None) == 0
    assert safe_clamp_score(float('nan')) == 0
    assert safe_clamp_score(155) == 100
    assert safe_clamp_score(-20) == 0
    assert safe_clamp_score(87.6) == 88


def test_strong_vs_weak_contrast(perfect_resume_parsed_data, weak_resume_parsed_data, scoring_config_path):
    """Assert clear contrast between strong and weak resume scores."""
    strong_score = analyze_resume_score(perfect_resume_parsed_data, scoring_config_path)["resume_score"]
    weak_score = analyze_resume_score(weak_resume_parsed_data, scoring_config_path)["resume_score"]

    assert (strong_score - weak_score) >= 40


def test_score_endpoint(client):
    """Test POST /api/score endpoint with a real database record."""
    from io import BytesIO

    from tests.test_upload import create_pdf_bytes

    sample_lines = [
        "Jane Doe",
        "jane@example.com | +91 9876543210 | github.com/janedoe",
        "PROFESSIONAL SUMMARY:",
        "Experienced Software Engineer with 4 years of expertise in building REST APIs, web apps, and databases.",
        "TECHNICAL SKILLS:",
        "Python, Flask, SQL, Docker, Git, REST API, Linux, Pytest, HTML, CSS, JavaScript",
        "EDUCATION:",
        "Bachelor of Technology in Computer Science - State University (2018 - 2022)",
        "PROJECTS:",
        "Smart Resume Analyzer - Built automated resume parsing and scoring system."
    ]

    pdf_bytes = create_pdf_bytes(sample_lines)
    upload_res = client.post("/api/upload", data={"file": (BytesIO(pdf_bytes), "sample.pdf")}, content_type="multipart/form-data")
    assert upload_res.status_code == 201
    resume_id = upload_res.get_json()["resume_id"]

    # Call POST /api/score
    score_res = client.post("/api/score", json={"resume_id": resume_id})
    assert score_res.status_code == 200
    res_data = score_res.get_json()

    assert "score_result" in res_data
    assert "resume_score" in res_data["score_result"]
    assert 0 <= res_data["score_result"]["resume_score"] <= 100
    assert "breakdown" in res_data["score_result"]


